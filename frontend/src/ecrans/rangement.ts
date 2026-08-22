/** L'écran de rangement : ce qu'on fait en rentrant du magasin.
 *
 *  Deux sources alimentent la liste :
 *   - les lignes d'une session passée en caisse (`stored_at` encore nul) —
 *     un appui les range via `home_stock/session/store_line` ;
 *   - un article rapporté seul, hors session (`home_stock/stock/add`), que
 *     le panneau construit lui-même faute de ligne serveur à interroger.
 *
 *  Les deux se rangent au même geste : choisir un emplacement (préposé sur
 *  celui du produit s'il en a un, sinon un choix explicite est exigé — voir
 *  `emplacementPour`) et un raccourci de DLC (`raccourcisDlc`), en un appui.
 *  Quand la liste se vide, l'écran l'annonce puis revient au scanner.
 */
import { LitElement, html, css, nothing, type PropertyValues } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import type { Connexion } from '../connexion';
import type { FileAttente } from '../file-attente';
import { raccourcisDlc, type Raccourci } from '../dlc';
import type { UniteBase } from './fiche';
import type { LigneSession } from './panier';
import { tokens } from '../shell/ui/tokens';

export type LigneRangementSession = LigneSession & { source: 'session' };

/** Un article rapporté seul, hors session : rien en base pour le représenter
 *  tant qu'il n'est pas rangé, donc un id local suffit à le distinguer. */
export type LigneRangementAutonome = {
  source: 'autonome';
  id: string;
  article_id: number;
  quantity: number;
  unit_price: number | null;
  product_name: string;
  base_unit: UniteBase;
  default_location_id: number | null;
  default_shelf_life_days: number | null;
  brand: string | null;
  image: string | null;
  net_quantity: number | null;
};

export type LigneRangement = LigneRangementSession | LigneRangementAutonome;

export type Emplacement = { id: number; name: string; kind: string; position: number };

function nomLigne(ligne: LigneRangement): string {
  return ligne.source === 'session' ? (ligne.article_label ?? ligne.product_name) : ligne.product_name;
}

/** Regroupe par emplacement, en préservant l'ordre d'arrivée des groupes
 *  (première ligne rencontrée pour cet emplacement) — jamais un tri
 *  alphabétique qui mélangerait l'ordre du parcours de rayon.
 *
 *  `emplacementResolu` décide QUEL emplacement compte pour une ligne — par
 *  défaut la seule suggestion (`default_location_id`), mais le composant lui
 *  passe `emplacementPour`, qui tient aussi compte d'un choix fait à la
 *  main : sans ça, une ligne choisie par le sélecteur resterait affichée
 *  sous « Emplacement à choisir » alors que le sélecteur montre déjà le bon
 *  nom — l'intitulé du groupe doit suivre exactement ce que la ligne va
 *  réellement recevoir, pas seulement ce qui a été suggéré au départ. */
export function grouperParEmplacement(
  lignes: LigneRangement[], emplacements: Emplacement[],
  emplacementResolu: (ligne: LigneRangement) => number | null = (l) => l.default_location_id,
): { emplacementId: number | null; nom: string; lignes: LigneRangement[] }[] {
  const nomDe = (id: number | null): string => {
    if (id === null) return 'Emplacement à choisir';
    return emplacements.find((e) => e.id === id)?.name ?? 'Emplacement à choisir';
  };
  const groupes: { emplacementId: number | null; nom: string; lignes: LigneRangement[] }[] = [];
  for (const ligne of lignes) {
    const emplacementId = emplacementResolu(ligne);
    let groupe = groupes.find((g) => g.emplacementId === emplacementId);
    if (!groupe) {
      groupe = { emplacementId, nom: nomDe(emplacementId), lignes: [] };
      groupes.push(groupe);
    }
    groupe.lignes.push(ligne);
  }
  return groupes;
}

@customElement('home-stock-rangement')
export class EcranRangement extends LitElement {
  @property({ attribute: false }) lignes: LigneRangement[] = [];
  @property({ attribute: false }) connexion?: Connexion;
  @property({ attribute: false }) file?: FileAttente;
  /** Nombre d'écritures en attente dans la file — comme sur le panier. */
  @property({ attribute: false }) enAttente = 0;

  @state() private emplacements: Emplacement[] = [];
  @state() private erreurEmplacements: string | null = null;
  /** Emplacement choisi à la main, par id de ligne — tant qu'absent, le
   *  sélecteur reste préposé sur `default_location_id`. Sans l'un ni
   *  l'autre, il n'y a PAS de repli implicite (voir `emplacementPour`) :
   *  ranger un produit jamais vu dans n'importe quel emplacement qui trie
   *  premier serait le classer au hasard, en silence. */
  @state() private emplacementChoisi: Record<string, number> = {};
  /** Lignes dont le rangement est en cours d'envoi : ignorées d'un second
   *  appui pendant l'attente, puis réactivées dans tous les cas quand
   *  l'envoi se termine — qu'il ait réussi, été refusé, ou simplement pas
   *  pu partir (hors ligne). Rien ne doit rester grisé pour toujours. */
  @state() private enCours: Set<string> = new Set();

  private aEuDesLignes = false;
  private termineEnvoye = false;

  connectedCallback(): void {
    super.connectedCallback();
    void this.chargerEmplacements();
  }

  protected willUpdate(changed: PropertyValues): void {
    if (changed.has('lignes')) {
      if (this.lignes.length > 0) this.aEuDesLignes = true;
    }
  }

  protected updated(): void {
    if (this.aEuDesLignes && this.lignes.length === 0 && !this.termineEnvoye) {
      this.termineEnvoye = true;
      this.dispatchEvent(new CustomEvent('termine', { bubbles: true, composed: true }));
    }
  }

  private async chargerEmplacements(): Promise<void> {
    if (!this.connexion) return;
    this.erreurEmplacements = null;
    try {
      const reponse = await this.connexion.appeler<{ locations: Emplacement[] }>('home_stock/locations/list');
      this.emplacements = reponse.locations;
    } catch {
      this.erreurEmplacements = 'Impossible de récupérer les emplacements. Vérifiez la connexion.';
    }
  }

  /** L'emplacement qui recevra le lot, ou `null` si rien n'a encore été
   *  décidé — jamais un premier emplacement pris au hasard faute de mieux.
   *  Un produit sans emplacement suggéré exige un choix explicite : les
   *  raccourcis de DLC restent désactivés tant qu'il n'est pas fait (voir
   *  `rendreLigne`). */
  private emplacementPour(ligne: LigneRangement): number | null {
    const choisi = this.emplacementChoisi[String(ligne.id)];
    if (choisi !== undefined) return choisi;
    return ligne.default_location_id;
  }

  /** Empile puis rejoue tout de suite — voir la même méthode dans
   *  `<home-stock-panier>` : `file-changee` tient le compteur du panneau à
   *  jour, avant l'envoi puis après. Sans `file`, rien à faire : il n'existe
   *  plus de chemin d'écriture direct par `connexion`.
   *
   *  Rend `true` seulement si CETTE action a bien été envoyée — ni encore en
   *  file (panne de transport), ni refusée. `ranger()` s'en sert pour ne
   *  signaler une ligne autonome rangée qu'une fois que c'est vraiment le
   *  cas : la signaler avant de connaître l'issue perdrait l'article pour de
   *  bon dès le premier refus (rien côté serveur ne le représente). */
  private ecrire(type: string, charge: Record<string, unknown>): Promise<boolean> {
    if (!this.file) return Promise.resolve(false);
    const suivi = this.file.ajouter(type, charge);
    this.avertirFile();
    void this.file.rejouer().then(() => this.avertirFile());
    return suivi.sort.then((sort) => sort === 'envoyee');
  }

  private avertirFile(): void {
    this.dispatchEvent(new CustomEvent('file-changee', { bubbles: true, composed: true }));
  }

  private ranger(ligne: LigneRangement, raccourci: Raccourci): void {
    const emplacementId = this.emplacementPour(ligne);
    if (emplacementId === null) return;
    const cle = String(ligne.id);
    if (this.enCours.has(cle)) return;
    this.enCours = new Set(this.enCours).add(cle);

    const terminer = (): void => {
      const restant = new Set(this.enCours);
      restant.delete(cle);
      this.enCours = restant;
    };

    if (ligne.source === 'session') {
      // La ligne disparaîtra de la liste quand le résumé de session se
      // rafraîchira (le panneau y est abonné) : rien à faire ici de plus,
      // sous peine d'afficher un état que le serveur n'a pas encore confirmé.
      void this.ecrire('home_stock/session/store_line', {
        line_id: ligne.id, location_id: emplacementId, best_before: raccourci.date,
      }).then(terminer);
    } else {
      void this.ecrire('home_stock/stock/add', {
        article_id: ligne.article_id, quantity: ligne.quantity, location_id: emplacementId,
        best_before: raccourci.date, price_per_base_unit: ligne.unit_price,
        // Clé STABLE, dérivée de l'identité locale de la ligne : au sous-sol,
        // un appui sur « +3 j » qui ne part pas laisse la ligne en place et
        // on réappuie. Sans cette clé, `FileAttente.ajouter` en tirait une
        // nouvelle au hasard à chaque appel, le contrôle d'idempotence de
        // `add_stock` ne reconnaissait rien, et le retour du réseau créait
        // DEUX lots et deux mouvements d'achat dans un journal en ajout
        // seul. Le chemin session n'a jamais eu ce défaut : `store_line`
        // dérive sa clé côté serveur de l'identifiant de ligne.
        idempotency_key: `rangement:${ligne.id}`,
      }).then((reussi) => {
        terminer();
        // Un article autonome n'existe nulle part côté serveur : le signaler
        // rangé AVANT de savoir si l'envoi a réussi le perdrait pour de bon
        // au premier refus (retiré de la liste locale, introuvable ailleurs).
        // Sur un échec (refus ou panne réseau), on le garde : il reste dans
        // la liste, prêt à être retenté d'un appui.
        if (reussi) {
          this.dispatchEvent(new CustomEvent('ligne-autonome-rangee', {
            detail: { id: ligne.id }, bubbles: true, composed: true,
          }));
        }
      });
    }
  }

  private rendreLigne(ligne: LigneRangement) {
    const cle = String(ligne.id);
    const enCours = this.enCours.has(cle);
    const emplacementId = this.emplacementPour(ligne);
    const raccourcis = raccourcisDlc(new Date(), ligne.default_shelf_life_days);
    return html`
      <article class="ligne">
        ${ligne.image ? html`<img class="image" src=${ligne.image} alt="" />` : nothing}
        <div class="infos">
          <p class="nom">${nomLigne(ligne)}${ligne.brand ? ` — ${ligne.brand}` : ''}</p>
          <p class="quantite">
            ${ligne.quantity}${ligne.base_unit !== 'piece' ? ` ${ligne.base_unit}` : ''}
          </p>
          <label class="emplacement-label">
            Emplacement
            <select class="emplacement-champ" .value=${emplacementId !== null ? String(emplacementId) : ''}
              ?disabled=${enCours}
              @change=${(e: Event) => {
                this.emplacementChoisi = {
                  ...this.emplacementChoisi,
                  [cle]: Number((e.target as HTMLSelectElement).value),
                };
              }}>
              ${emplacementId === null ? html`
                <option value="" disabled selected>Choisir…</option>
              ` : nothing}
              ${this.emplacements.map((emp) => html`
                <option value=${String(emp.id)} ?selected=${emp.id === emplacementId}>${emp.name}</option>
              `)}
            </select>
          </label>
          ${emplacementId === null ? html`
            <p class="emplacement-manquant">Choisissez un emplacement avant de ranger.</p>
          ` : nothing}
          ${this.erreurEmplacements ? html`<p class="erreur">${this.erreurEmplacements}</p>` : nothing}
          <div class="raccourcis-dlc">
            ${raccourcis.map((raccourci) => html`
              <button class="raccourci-dlc" ?disabled=${enCours || emplacementId === null}
                @click=${() => this.ranger(ligne, raccourci)}>
                ${enCours ? 'Rangement…' : raccourci.libelle}
              </button>
            `)}
          </div>
        </div>
      </article>
    `;
  }

  render() {
    if (this.lignes.length === 0) {
      return html`<p class="tout-range">Tout est rangé.</p>`;
    }
    const groupes = grouperParEmplacement(this.lignes, this.emplacements, (l) => this.emplacementPour(l));
    return html`
      ${this.enAttente > 0 ? html`
        <p class="en-attente">${this.enAttente} envoi${this.enAttente > 1 ? 's' : ''} en attente de réseau</p>
      ` : nothing}
      ${groupes.map((groupe) => html`
        <section class="emplacement">
          <h3 class="emplacement-nom">${groupe.nom}</h3>
          ${groupe.lignes.map((ligne) => this.rendreLigne(ligne))}
        </section>
      `)}
    `;
  }

  static styles = [tokens, css`
    :host { display: block; padding: 12px; box-sizing: border-box; color: var(--hs-text); }
    .tout-range { text-align: center; font-size: 1.2rem; margin-top: 32px; }
    .en-attente { text-align: center; color: var(--hs-text-2); font-size: 0.85rem; margin: 0 0 8px; }
    .emplacement-nom {
      margin: 16px 0 4px; font-size: 0.9rem; text-transform: uppercase;
      color: var(--hs-text-2); letter-spacing: 0.04em;
    }
    .ligne {
      display: flex; gap: 8px; padding: 8px 0; border-bottom: 1px solid var(--hs-divider);
    }
    .image { width: 48px; height: 48px; object-fit: cover; border-radius: 6px; flex-shrink: 0; }
    .infos { flex: 1; min-width: 0; }
    .nom { margin: 0 0 4px; }
    .quantite { margin: 0 0 4px; color: var(--hs-text-2); }
    .emplacement-label { display: block; font-size: 0.85rem; margin-bottom: 8px; }
    .emplacement-champ { min-height: var(--hs-touch); width: 100%; box-sizing: border-box; font-size: 1rem; }
    /* Pas d'aplat sous du texte (§ 6.1 ter) : le texte reste --hs-text, la
       bordure porte --hs-danger. */
    .emplacement-manquant {
      color: var(--hs-text); border-left: 3px solid var(--hs-danger);
      padding-left: 8px; font-size: 0.85rem; margin: 0 0 8px;
    }
    .erreur {
      color: var(--hs-text); border-left: 3px solid var(--hs-danger);
      padding-left: 8px; font-size: 0.85rem;
    }
    .raccourcis-dlc { display: flex; flex-wrap: wrap; gap: 8px; }
    .raccourci-dlc {
      min-height: var(--hs-touch); min-width: var(--hs-touch); padding: 0 12px; border-radius: 8px; border: none; font-size: 0.95rem;
      background: var(--hs-accent); color: var(--hs-on-accent);
    }
    .raccourci-dlc:disabled { opacity: 0.5; }
  `];
}
