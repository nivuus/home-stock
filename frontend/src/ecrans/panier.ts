/** L'écran panier : ce qu'on lit en marchant dans le magasin.
 *
 *  Les lignes viennent de `home_stock/session/current`, déjà triées côté
 *  serveur par rayon puis par nom de produit (l'ordre du parcours) : cet
 *  écran ne fait qu'un passage linéaire pour les grouper visuellement par
 *  rayon, il ne les retrie jamais — c'est ce tri-là qui est testé côté
 *  serveur, le refaire ici laisserait les deux dériver.
 *
 *  Le total affiché est `totals.total`, tel quel : jamais recalculé à partir
 *  des lignes affichées. Un panier qui contredit la caisse est pire qu'un
 *  panier sans total.
 */
import { LitElement, html, css, nothing, type PropertyValues } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import type { Connexion } from '../connexion';
import type { FileAttente } from '../file-attente';
import { prixBaseDepuisSaisie, prixPaquetAffiche, type UniteBase } from './fiche';
import { tokens } from '../shell/ui/tokens';

/** Une ligne de panier, exactement comme `home_stock/session/current` la
 *  rend (voir `_LINE_SELECT_SQL` côté serveur) — aucun champ n'est renommé
 *  ni recalculé ici. */
export type LigneSession = {
  id: number;
  article_id: number;
  quantity: number;
  unit_price: number | null;
  stored_at: string | null;
  batch_id: number | null;
  product_id: number;
  product_name: string;
  base_unit: UniteBase;
  default_location_id: number | null;
  default_shelf_life_days: number | null;
  days_after_opening: number | null;
  article_label: string | null;
  brand: string | null;
  image: string | null;
  net_quantity: number | null;
  aisle_name: string | null;
  aisle_position: number;
};

/** L'en-tête de la session (pas une ligne : `store`/`state`/dates) — nommé à
 *  part de `LigneSession` pour ne pas laisser croire que c'est une ligne de
 *  plus. */
export type EnTeteSession = {
  id: number;
  state: 'shopping' | 'to_store' | 'done';
  store: string | null;
  started_at: string;
  closed_at: string | null;
};

/** Les totaux d'une session. Le lot 4 ajoute la RÉPARTITION du même total :
 *  ce qui a été constaté (un humain a tapé le prix devant l'étiquette, ou le
 *  ticket l'a dit) et ce qui reste une supposition. Optionnelles, parce que
 *  la même enveloppe est encore rendue par des chemins du lot 1. */
export type Totaux = {
  lines: number;
  pending: number;
  total: number;
  observed?: number;
  estimated?: number;
  unpriced_lines?: number;
  off_list_lines?: number;
  checked_items?: number;
  list_items?: number;
};

/** Ce que `home_stock/session/current` répond quand une session existe. */
/** Un magasin, tel que `home_stock/stores/list` le rend depuis le lot 4 :
 *  une LIGNE avec un identifiant, plus une chaîne. */
export type Magasin = {
  id: number;
  name: string;
  position: number;
  active: number;
  observed_sessions: number;
  last_seen: string | null;
};

export type DonneesSession = {
  session: EnTeteSession;
  lines: LigneSession[];
  totals: Totaux;
  stores: Magasin[];
};

function formaterEuros(valeur: number): string {
  return `${valeur.toFixed(2).replace('.', ',')} €`;
}

/** Le pas d'incrément d'une ligne : un paquet. À la pièce, un paquet est une
 *  unité. Au poids, un paquet fait `net_quantity` — quand ce poids n'est pas
 *  connu, on retombe sur 1 (unité de base) plutôt que de bloquer le bouton,
 *  faute de mieux. */
function pas(ligne: LigneSession): number {
  if (ligne.base_unit === 'piece') return 1;
  return ligne.net_quantity && ligne.net_quantity > 0 ? ligne.net_quantity : 1;
}

/** Regroupe des lignes déjà triées par rayon, par un simple passage linéaire
 *  — ne jamais trier ici, seulement grouper ce qui est déjà contigu. */
export function grouperParRayon(lignes: LigneSession[]): { rayon: string; lignes: LigneSession[] }[] {
  const groupes: { rayon: string; lignes: LigneSession[] }[] = [];
  for (const ligne of lignes) {
    const rayon = ligne.aisle_name ?? 'Sans rayon';
    const dernier = groupes[groupes.length - 1];
    if (dernier && dernier.rayon === rayon) {
      dernier.lignes.push(ligne);
    } else {
      groupes.push({ rayon, lignes: [ligne] });
    }
  }
  return groupes;
}

@customElement('home-stock-panier')
export class EcranPanier extends LitElement {
  @property({ attribute: false }) donnees: DonneesSession | null = null;
  @property({ attribute: false }) connexion?: Connexion;
  /** La file hors-ligne : la raison d'être de cet écran est le rayon d'un
   *  magasin, l'endroit où le réseau lâche le plus souvent. Chaque écriture
   *  y passe — il n'existe plus de chemin direct par `connexion` : un
   *  contournement de la file est exactement le défaut que ce lot interdit. */
  @property({ attribute: false }) file?: FileAttente;
  /** Nombre d'écritures en attente dans la file — affiché seulement si non nul. */
  @property({ attribute: false }) enAttente = 0;

  /** Id de la ligne dont la suppression est armée (premier appui) : le
   *  deuxième appui, sur le même bouton, confirme. Toute autre action —
   *  ajuster une quantité, valider un prix, passer en caisse — ou un
   *  simple rafraîchissement des données désarme : un « × » retrouvé deux
   *  rayons plus loin ne doit jamais rester une gâchette armée. */
  @state() private ligneArmee: number | null = null;
  /** Saisie de prix en cours, par id de ligne, tant qu'elle n'a pas été
   *  validée : la même logique que la fiche (état local jusqu'à l'envoi). */
  @state() private prixSaisiParLigne: Record<number, string> = {};
  /** Message affiché quand un prix tapé n'a pas pu être converti (poids de
   *  paquet inconnu) : la saisie reste visible, mais n'est pas envoyée en
   *  silence — sans ce message, le champ semblerait avoir juste oublié ce
   *  qui a été tapé. */
  @state() private erreurPrixParLigne: Record<number, string> = {};
  /** Ce que l'utilisateur a demandé en plus de la dernière quantité connue
   *  du serveur, par id de ligne : trois appuis sur « + » hors ligne doivent
   *  faire bouger le chiffre affiché trois fois, pas une seule fois de plus
   *  que la dernière valeur reçue. Remis à zéro dès qu'une nouvelle quantité
   *  serveur arrive pour cette ligne (voir `willUpdate`). */
  @state() private deltaParLigne: Record<number, number> = {};
  /** La dernière quantité serveur vue par ligne, pour détecter qu'un
   *  rafraîchissement vient d'arriver (et donc remettre `deltaParLigne` à
   *  zéro pour cette ligne) plutôt que de comparer à une valeur déjà stale. */
  private quantiteVueParLigne: Record<number, number> = {};

  /** Vrai quand on n'affiche que ce qui s'est invité dans le chariot. Un
   *  appui, réversible : ce n'est qu'un filtre d'affichage. */
  @state() private seulementHorsListe = false;

  protected willUpdate(changed: PropertyValues): void {
    if (changed.has('donnees')) {
      // Un rafraîchissement désarme une suppression en attente : re-armer
      // est un appui, le risque de la garder est un panier vidé par erreur.
      this.ligneArmee = null;
      for (const ligne of this.donnees?.lines ?? []) {
        if (this.quantiteVueParLigne[ligne.id] !== ligne.quantity) {
          this.quantiteVueParLigne[ligne.id] = ligne.quantity;
          if (this.deltaParLigne[ligne.id]) {
            const { [ligne.id]: _oublie, ...reste } = this.deltaParLigne;
            this.deltaParLigne = reste;
          }
        }
      }
    }
  }

  /** Empile puis rejoue tout de suite : la file existe pour tenir bon quand
   *  le réseau refuse, pas pour attendre un déclencheur extérieur. Le panneau
   *  garde le compteur de la file — `file-changee` le prévient, avant l'envoi
   *  (la ligne vient d'être ajoutée) et après (elle a pu partir, être
   *  refusée, ou rester). Sans `file` il n'y a rien à faire : il n'existe
   *  plus de deuxième chemin d'écriture par `connexion` directe.
   *
   *  Rend `true` si CETTE action a bien été envoyée (voir la même méthode
   *  dans `<home-stock-rangement>`) — le panier ne s'en sert pas encore pour
   *  changer son affichage (aucune ligne locale à faire disparaître ici,
   *  contrairement à une ligne autonome du rangement), mais la même
   *  signature évite deux contrats différents pour la même méthode dupliquée
   *  dans les deux écrans. */
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

  private quantiteAffichee(ligne: LigneSession): number {
    return ligne.quantity + (this.deltaParLigne[ligne.id] ?? 0);
  }

  private ajusterQuantite(ligne: LigneSession, pasSigne: number): void {
    this.ligneArmee = null;
    const nouveauDelta = (this.deltaParLigne[ligne.id] ?? 0) + pasSigne;
    const nouvelleQuantite = ligne.quantity + nouveauDelta;
    if (nouvelleQuantite <= 0) return;
    this.deltaParLigne = { ...this.deltaParLigne, [ligne.id]: nouveauDelta };
    void this.ecrire('home_stock/session/update_line', { line_id: ligne.id, quantity: nouvelleQuantite });
  }

  private saisirPrix(ligne: LigneSession, texte: string): void {
    this.ligneArmee = null;
    this.prixSaisiParLigne = { ...this.prixSaisiParLigne, [ligne.id]: texte };
  }

  private validerPrix(ligne: LigneSession): void {
    this.ligneArmee = null;
    const texte = this.prixSaisiParLigne[ligne.id];
    if (texte === undefined) return;
    const valeur = prixBaseDepuisSaisie(texte, ligne.base_unit, ligne.net_quantity);
    if (valeur === null) {
      // On ne fait pas disparaître la saisie en silence : sans poids de
      // paquet connu il n'y a aucune conversion possible, et un champ qui
      // reviendrait tout seul à l'ancien prix laisserait croire à une saisie
      // acceptée puis oubliée.
      this.erreurPrixParLigne = { ...this.erreurPrixParLigne, [ligne.id]: 'Prix non enregistré : poids du paquet inconnu.' };
      return;
    }
    if (this.erreurPrixParLigne[ligne.id]) {
      const { [ligne.id]: _oublie, ...reste } = this.erreurPrixParLigne;
      this.erreurPrixParLigne = reste;
    }
    void this.ecrire('home_stock/session/update_line', { line_id: ligne.id, unit_price: valeur });
    const { [ligne.id]: _oublie, ...reste } = this.prixSaisiParLigne;
    this.prixSaisiParLigne = reste;
  }

  private supprimer(ligne: LigneSession): void {
    void this.ecrire('home_stock/session/remove_line', { line_id: ligne.id });
    this.ligneArmee = null;
  }

  private passerEnCaisse(): void {
    this.ligneArmee = null;
    void this.ecrire('home_stock/session/checkout', {});
  }

  private valeurPrix(ligne: LigneSession): string {
    const saisie = this.prixSaisiParLigne[ligne.id];
    if (saisie !== undefined) return saisie;
    return prixPaquetAffiche(ligne.unit_price, ligne.base_unit, ligne.net_quantity);
  }

  private rendreLigne(ligne: LigneSession) {
    const pasLigne = pas(ligne);
    const quantite = this.quantiteAffichee(ligne);
    const nom = ligne.article_label ?? ligne.product_name;
    return html`
      <article class="ligne">
        ${ligne.image ? html`<img class="image" src=${ligne.image} alt="" />` : nothing}
        <div class="infos">
          <p class="nom">${nom}${ligne.brand ? ` — ${ligne.brand}` : ''}</p>
          <div class="quantite">
            <button class="moins" aria-label="Retirer un paquet" ?disabled=${quantite <= pasLigne}
              @click=${() => this.ajusterQuantite(ligne, -pasLigne)}>−</button>
            <span class="valeur-quantite">
              ${quantite}${ligne.base_unit !== 'piece' ? ` ${ligne.base_unit}` : ''}
            </span>
            <button class="plus" aria-label="Ajouter un paquet"
              @click=${() => this.ajusterQuantite(ligne, pasLigne)}>+</button>
          </div>
          <label class="prix-label">
            Prix
            <input class="prix-champ" inputmode="decimal" .value=${this.valeurPrix(ligne)}
              @input=${(e: InputEvent) => this.saisirPrix(ligne, (e.target as HTMLInputElement).value)}
              @change=${() => this.validerPrix(ligne)} />
          </label>
          ${this.erreurPrixParLigne[ligne.id] ? html`
            <p class="erreur-prix">${this.erreurPrixParLigne[ligne.id]}</p>
          ` : nothing}
        </div>
        ${this.ligneArmee === ligne.id ? html`
          <div class="confirmation-suppression">
            <button class="confirmer-suppression" @click=${() => this.supprimer(ligne)}>Confirmer</button>
            <button class="annuler-suppression" @click=${() => { this.ligneArmee = null; }}>Annuler</button>
          </div>
        ` : html`
          <button class="supprimer" aria-label="Retirer du panier" @click=${() => { this.ligneArmee = ligne.id; }}>
            ×
          </button>
        `}
      </article>
    `;
  }

  /** Le même total, dit en trois faits : « 47,20 € — dont 12,30 € estimés,
   *  2 lignes sans prix ». C'est le chiffre qu'on compare mentalement au
   *  ticket, et un écart inexpliqué détruit la confiance dans tout le
   *  reste. Absent quand le serveur n'a pas donné la répartition — un lot 1
   *  qui répond encore. */
  private rendreRepartition(totaux: Totaux) {
    if (totaux.estimated === undefined) return nothing;
    const sansPrix = totaux.unpriced_lines ?? 0;
    const progression = (totaux.list_items ?? 0) > 0
      ? `${totaux.checked_items ?? 0} / ${totaux.list_items} de la liste`
      : null;
    return html`
      <p class="repartition">${
        `dont ${formaterEuros(totaux.estimated)} estimé`
        + (sansPrix > 0 ? `, ${sansPrix} ligne${sansPrix > 1 ? 's' : ''} sans prix` : '')
      }</p>
      ${progression ? html`<p class="progression">${progression}</p>` : nothing}
    `;
  }

  render() {
    const donnees = this.donnees;
    if (!donnees) return html`<p class="vide">Aucune session de courses ouverte.</p>`;
    const groupes = grouperParRayon(donnees.lines);
    const enCaisse = donnees.session.state !== 'shopping';
    return html`
      <section class="entete">
        <p class="magasin">${donnees.session.store ?? 'Sans enseigne'}</p>
        <p class="total">${formaterEuros(donnees.totals.total)}</p>
      </section>

      ${this.rendreRepartition(donnees.totals)}

      ${this.enAttente > 0 ? html`
        <p class="en-attente">${this.enAttente} envoi${this.enAttente > 1 ? 's' : ''} en attente de réseau</p>
      ` : nothing}

      ${donnees.lines.length === 0 ? html`<p class="vide">Le panier est vide.</p>` : nothing}

      ${(donnees.totals.off_list_lines ?? 0) > 0 ? html`
        <button class="hors-liste"
          aria-pressed=${this.seulementHorsListe ? 'true' : 'false'}
          @click=${() => { this.seulementHorsListe = !this.seulementHorsListe; }}>
          ${`${donnees.totals.off_list_lines} hors liste`}
        </button>
      ` : nothing}

      ${groupes.map((groupe) => html`
        <section class="rayon">
          <h3 class="rayon-nom">${groupe.rayon}</h3>
          ${groupe.lignes.map((ligne) => this.rendreLigne(ligne))}
        </section>
      `)}

      <button class="checkout" ?disabled=${donnees.totals.lines === 0 || enCaisse} @click=${this.passerEnCaisse}>
        ${enCaisse ? 'Déjà en caisse' : 'Passage en caisse'}
      </button>
    `;
  }

  static styles = [tokens, css`
    :host { display: block; padding: 12px; box-sizing: border-box; color: var(--hs-text); }
    .entete { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 8px; }
    .magasin { font-weight: 600; margin: 0; }
    .total { font-size: 1.3rem; font-weight: 700; margin: 0; }
    .repartition, .progression { margin: 0 0 4px; font-size: 0.85rem; color: var(--hs-text-2); }
    .hors-liste {
      min-height: var(--hs-touch); width: 100%; border-radius: 8px; border: none; font-size: 0.9rem;
      background: var(--hs-surface-2); color: var(--hs-text);
      margin-bottom: 8px;
    }
    .hors-liste[aria-pressed='true'] { background: var(--hs-accent); color: var(--hs-on-accent); }
    .en-attente { text-align: center; color: var(--hs-text-2); font-size: 0.85rem; margin: 4px 0 8px; }
    .vide { color: var(--hs-text-2); text-align: center; }
    .rayon-nom {
      margin: 16px 0 4px; font-size: 0.9rem; text-transform: uppercase;
      color: var(--hs-text-2); letter-spacing: 0.04em;
    }
    .ligne {
      display: flex; align-items: center; gap: 8px; padding: 8px 0;
      border-bottom: 1px solid var(--hs-divider);
    }
    .image { width: 48px; height: 48px; object-fit: cover; border-radius: 6px; flex-shrink: 0; }
    .infos { flex: 1; min-width: 0; }
    .nom { margin: 0 0 4px; }
    .quantite { display: flex; align-items: center; gap: 8px; }
    .quantite button {
      min-width: var(--hs-touch); min-height: var(--hs-touch); font-size: 1.3rem; border-radius: 8px; border: none;
      background: var(--hs-accent); color: var(--hs-on-accent);
    }
    .quantite button:disabled { opacity: 0.5; }
    .valeur-quantite { min-width: 56px; text-align: center; }
    .prix-label { display: block; font-size: 0.85rem; margin-top: 4px; }
    .prix-champ { min-height: var(--hs-touch); width: 100%; box-sizing: border-box; font-size: 1rem; padding: 4px 8px; }
    /* Pas d'aplat sous du texte (§ 6.1 ter) : le texte reste --hs-text, la
       bordure porte --hs-danger. */
    .erreur-prix {
      color: var(--hs-text); border-left: 3px solid var(--hs-danger);
      padding-left: 8px; font-size: 0.8rem; margin: 4px 0 0;
    }
    .supprimer {
      min-width: var(--hs-touch); min-height: var(--hs-touch); border-radius: 8px; border: 2px solid var(--hs-danger);
      background: var(--hs-surface); color: var(--hs-text); font-size: 1.2rem; flex-shrink: 0;
    }
    .confirmation-suppression { display: flex; flex-direction: column; gap: 4px; flex-shrink: 0; }
    .confirmer-suppression, .annuler-suppression {
      min-height: var(--hs-touch); min-width: var(--hs-touch); border-radius: 8px; border: none; font-size: 0.9rem;
    }
    .confirmer-suppression {
      background: var(--hs-surface); color: var(--hs-text); border: 2px solid var(--hs-danger);
    }
    .annuler-suppression { background: var(--hs-surface-2); color: var(--hs-text); }
    .checkout {
      display: block; width: 100%; min-height: var(--hs-touch); font-size: 1.2rem; border-radius: 12px; border: none;
      background: var(--hs-accent); color: var(--hs-on-accent); margin-top: 16px;
    }
    .checkout:disabled { opacity: 0.5; }
  `];
}
