/** L'écran de rangement : ce qu'on fait en rentrant du magasin.
 *
 *  Deux sources alimentent la liste :
 *   - les lignes d'une session passée en caisse (`stored_at` encore nul) —
 *     un appui les range via `home_stock/session/store_line` ;
 *   - un article rapporté seul, hors session (`home_stock/stock/add`), que
 *     le panneau construit lui-même faute de ligne serveur à interroger.
 *
 *  Les deux se rangent au même geste : choisir un emplacement (préposé sur
 *  celui du produit) et un raccourci de DLC (`raccourcisDlc`), en un appui.
 *  Quand la liste se vide, l'écran l'annonce puis revient au scanner.
 */
import { LitElement, html, css, nothing, type PropertyValues } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import type { Connexion } from '../connexion';
import type { FileAttente } from '../file-attente';
import { raccourcisDlc, type Raccourci } from '../dlc';
import type { UniteBase } from './fiche';
import type { LigneSession } from './panier';

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

function idLigne(ligne: LigneRangement): number | string {
  return ligne.id;
}

function nomLigne(ligne: LigneRangement): string {
  return ligne.source === 'session' ? (ligne.article_label ?? ligne.product_name) : ligne.product_name;
}

/** Regroupe par emplacement suggéré, en préservant l'ordre d'arrivée des
 *  groupes (première ligne rencontrée pour cet emplacement) — jamais un tri
 *  alphabétique qui mélangerait l'ordre du parcours de rayon. */
export function grouperParEmplacement(
  lignes: LigneRangement[], emplacements: Emplacement[],
): { emplacementId: number | null; nom: string; lignes: LigneRangement[] }[] {
  const nomDe = (id: number | null): string => {
    if (id === null) return 'Emplacement à choisir';
    return emplacements.find((e) => e.id === id)?.name ?? 'Emplacement à choisir';
  };
  const groupes: { emplacementId: number | null; nom: string; lignes: LigneRangement[] }[] = [];
  for (const ligne of lignes) {
    const emplacementId = ligne.default_location_id;
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

  @state() private emplacements: Emplacement[] = [];
  @state() private erreurEmplacements: string | null = null;
  /** Emplacement choisi à la main, par id de ligne — tant qu'absent, le
   *  sélecteur reste préposé sur `default_location_id`. */
  @state() private emplacementChoisi: Record<string, number> = {};
  /** Lignes dont le rangement est en cours d'envoi : ignorées d'un second
   *  appui, réaffichées seulement si l'envoi échoue. */
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

  private emplacementPour(ligne: LigneRangement): number | null {
    const choisi = this.emplacementChoisi[String(idLigne(ligne))];
    if (choisi !== undefined) return choisi;
    if (ligne.default_location_id !== null) return ligne.default_location_id;
    return this.emplacements[0]?.id ?? null;
  }

  /** Empile puis rejoue tout de suite — voir la même méthode dans
   *  `<home-stock-panier>` : `file-changee` tient le compteur du panneau à
   *  jour, avant l'envoi puis après. */
  private ecrire(type: string, charge: Record<string, unknown>): void {
    if (this.file) {
      this.file.ajouter(type, charge);
      this.avertirFile();
      void this.file.rejouer().then(() => this.avertirFile());
    } else if (this.connexion) {
      void this.connexion.appeler(type, charge).catch(() => {});
    }
  }

  private avertirFile(): void {
    this.dispatchEvent(new CustomEvent('file-changee', { bubbles: true, composed: true }));
  }

  private ranger(ligne: LigneRangement, raccourci: Raccourci): void {
    const emplacementId = this.emplacementPour(ligne);
    if (emplacementId === null) return;
    const cle = String(idLigne(ligne));
    if (this.enCours.has(cle)) return;
    this.enCours = new Set(this.enCours).add(cle);

    if (ligne.source === 'session') {
      this.ecrire('home_stock/session/store_line', {
        line_id: ligne.id, location_id: emplacementId, best_before: raccourci.date,
      });
      // La ligne disparaîtra de la liste quand le résumé de session se
      // rafraîchira (le panneau y est abonné) : rien à faire ici de plus,
      // sous peine d'afficher un état que le serveur n'a pas encore confirmé.
    } else {
      this.ecrire('home_stock/stock/add', {
        article_id: ligne.article_id, quantity: ligne.quantity, location_id: emplacementId,
        best_before: raccourci.date, price_per_base_unit: ligne.unit_price,
      });
      // Un article autonome n'existe nulle part côté serveur tant qu'il
      // n'est pas rangé : rien à réconcilier, on le retire tout de suite.
      this.dispatchEvent(new CustomEvent('ligne-autonome-rangee', {
        detail: { id: ligne.id }, bubbles: true, composed: true,
      }));
    }
  }

  private rendreLigne(ligne: LigneRangement) {
    const cle = String(idLigne(ligne));
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
              ${this.emplacements.map((emp) => html`
                <option value=${String(emp.id)} ?selected=${emp.id === emplacementId}>${emp.name}</option>
              `)}
            </select>
          </label>
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
    const groupes = grouperParEmplacement(this.lignes, this.emplacements);
    return html`
      ${groupes.map((groupe) => html`
        <section class="emplacement">
          <h3 class="emplacement-nom">${groupe.nom}</h3>
          ${groupe.lignes.map((ligne) => this.rendreLigne(ligne))}
        </section>
      `)}
    `;
  }

  static styles = css`
    :host { display: block; padding: 12px; box-sizing: border-box; color: var(--primary-text-color); }
    .tout-range { text-align: center; font-size: 1.2rem; margin-top: 32px; }
    .emplacement-nom {
      margin: 16px 0 4px; font-size: 0.9rem; text-transform: uppercase;
      color: var(--secondary-text-color); letter-spacing: 0.04em;
    }
    .ligne {
      display: flex; gap: 8px; padding: 8px 0; border-bottom: 1px solid var(--divider-color, #ddd);
    }
    .image { width: 48px; height: 48px; object-fit: cover; border-radius: 6px; flex-shrink: 0; }
    .infos { flex: 1; min-width: 0; }
    .nom { margin: 0 0 4px; }
    .quantite { margin: 0 0 4px; color: var(--secondary-text-color); }
    .emplacement-label { display: block; font-size: 0.85rem; margin-bottom: 8px; }
    .emplacement-champ { min-height: 48px; width: 100%; box-sizing: border-box; font-size: 1rem; }
    .erreur { color: var(--error-color, #b3261e); font-size: 0.85rem; }
    .raccourcis-dlc { display: flex; flex-wrap: wrap; gap: 8px; }
    .raccourci-dlc {
      min-height: 48px; padding: 0 12px; border-radius: 8px; border: none; font-size: 0.95rem;
      background: var(--primary-color); color: var(--text-primary-color, #fff);
    }
    .raccourci-dlc:disabled { opacity: 0.5; }
  `;
}
