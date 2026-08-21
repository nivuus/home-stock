/** L'écran « planning » : la semaine en large, la journée en étroit.
 *
 *  Sept colonnes × quatre créneaux en 1280 × 800. En 412 × 915, UNE journée à
 *  la fois avec précédent / suivant — pas une grille de sept colonnes réduite,
 *  qui produirait des cibles sous 48 px et que `verifier-rendu.mjs` refuserait
 *  à juste titre.
 *
 *  Les jours sont des journées ALIMENTAIRES : elles courent de 4 h à 4 h.
 */
import { LitElement, html, css, nothing } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import type { Connexion } from '../connexion';
import type { FileAttente } from '../file-attente';

export type CleCreneau = 'breakfast' | 'lunch' | 'dinner' | 'snack';

/** Les créneaux dans l'ordre du planning, avec leur nom français. Repris de
 *  `meal_slot.position` : la même liste que celle que `m004` sème. */
export const CRENEAUX: ReadonlyArray<readonly [CleCreneau, string]> = [
  ['breakfast', 'Petit-déjeuner'],
  ['lunch', 'Déjeuner'],
  ['dinner', 'Dîner'],
  ['snack', 'En-cas'],
];

const JOURS = ['dimanche', 'lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi',
               'samedi'];

export type RepasPlanning = {
  id: number;
  uid: string;
  day: string;
  slot_key: CleCreneau;
  position: number;
  recipe_id: number | null;
  recipe_name: string | null;
  product_id: number | null;
  product_name: string | null;
  note: string | null;
  servings: number;
  state: 'planned' | 'done' | 'skipped';
};

export type ProduitManquant = { product_id: number; product_name: string };

function ajouterJours(jour: string, delta: number): string {
  const date = new Date(`${jour}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() + delta);
  return date.toISOString().slice(0, 10);
}

function libelleJour(jour: string): string {
  const date = new Date(`${jour}T12:00:00Z`);
  return `${JOURS[date.getUTCDay()]} ${date.getUTCDate()}`;
}

@customElement('home-stock-planning')
export class EcranPlanning extends LitElement {
  @property({ attribute: false }) connexion?: Connexion;
  @property({ attribute: false }) file?: FileAttente;
  @property({ type: Boolean }) large = false;
  /** Le premier jour affiché. En étroit, le seul. */
  @property({ type: String }) debut = new Date().toISOString().slice(0, 10);

  @state() repas: RepasPlanning[] = [];
  @state() manquants: ProduitManquant[] = [];
  @state() armeAnnulation: number | null = null;
  @state() message: string | null = null;

  connectedCallback(): void {
    super.connectedCallback();
    void this.charger();
  }

  get jours(): string[] {
    const nombre = this.large ? 7 : 1;
    return Array.from({ length: nombre }, (_, i) => ajouterJours(this.debut, i));
  }

  async charger(): Promise<void> {
    if (!this.connexion) return;
    const jours = this.jours;
    const reponse = await this.connexion.appeler<{ meals: RepasPlanning[] }>(
      'home_stock/meals/list',
      { start: jours[0], end: jours[jours.length - 1] });
    this.repas = reponse.meals ?? [];
  }

  async allerA(delta: number): Promise<void> {
    this.debut = ajouterJours(this.debut, this.large ? delta * 7 : delta);
    this.armeAnnulation = null;
    await this.charger();
  }

  repasDe(jour: string, creneau: CleCreneau): RepasPlanning[] {
    return this.repas
      .filter((r) => r.day === jour && r.slot_key === creneau)
      .sort((a, b) => a.position - b.position);
  }

  // --- écritures, toutes par la file ---------------------------------------

  async poser(jour: string, creneau: CleCreneau): Promise<void> {
    if (!this.file) return;
    this.file.ajouter('home_stock/meal/plan', {
      day: jour, slot_key: creneau, note: 'Repas', servings: 1,
    });
    void this.file.rejouer?.();
    await this.charger();
  }

  async deplacer(repas: RepasPlanning, jour: string,
                 creneau: CleCreneau): Promise<void> {
    if (!this.file) return;
    if (repas.state === 'done') {
      // Ses mouvements portent une date figée : déplacer la ligne les
      // décorrélerait en silence.
      this.message = 'Un repas validé ne se déplace pas : ses mouvements '
        + 'portent une date figée.';
      return;
    }
    this.message = null;
    this.file.ajouter('home_stock/meal/move', {
      meal_id: repas.id, day: jour, slot_key: creneau,
    });
    void this.file.rejouer?.();
    await this.charger();
  }

  /** Deux appuis, comme toute action destructive du panneau. */
  async annuler(repas: RepasPlanning): Promise<void> {
    if (this.armeAnnulation !== repas.id) {
      this.armeAnnulation = repas.id;
      return;
    }
    if (!this.file) return;
    this.armeAnnulation = null;
    this.file.ajouter('home_stock/meal/cancel', { meal_id: repas.id });
    void this.file.rejouer?.();
    await this.charger();
  }

  ouvrirRecette(repas: RepasPlanning): void {
    if (repas.recipe_id === null) return;
    this.dispatchEvent(new CustomEvent('recette-ouverte', {
      detail: { recipe_id: repas.recipe_id, meal_id: repas.id },
      bubbles: true, composed: true,
    }));
  }

  ouvrirValidation(repas: RepasPlanning): void {
    if (repas.state === 'done') return;
    this.dispatchEvent(new CustomEvent('valider-repas', {
      detail: { meal_id: repas.id }, bubbles: true, composed: true,
    }));
  }

  // --- rendu ---------------------------------------------------------------

  private nomDe(repas: RepasPlanning): string {
    return repas.recipe_name ?? repas.product_name ?? repas.note ?? 'Repas';
  }

  private rendreRepas(repas: RepasPlanning) {
    return html`
      <div class="repas etat-${repas.state}">
        <button class="repas-nom" @click=${() => this.ouvrirRecette(repas)}>
          ${this.nomDe(repas)}
        </button>
        ${repas.state === 'done'
          ? html`<span class="valide">validé</span>`
          : html`
            <button class="valider-repas" @click=${() => this.ouvrirValidation(repas)}>
              Valider
            </button>
            <button class="annuler-repas" @click=${() => this.annuler(repas)}>
              ${this.armeAnnulation === repas.id ? 'Confirmer' : 'Annuler'}
            </button>`}
      </div>
    `;
  }

  private rendreCase(jour: string, creneau: CleCreneau) {
    const repas = this.repasDe(jour, creneau);
    return html`
      <div class="case">
        ${repas.map((r) => this.rendreRepas(r))}
        <button class="poser" @click=${() => this.poser(jour, creneau)}>+</button>
      </div>
    `;
  }

  render() {
    const jours = this.jours;
    return html`
      <div class="entete">
        <button class="precedent-jour" @click=${() => this.allerA(-1)}>Précédent</button>
        <span class="periode">${this.large
          ? `${libelleJour(jours[0])} — ${libelleJour(jours[jours.length - 1])}`
          : libelleJour(jours[0])}</span>
        <button class="suivant-jour" @click=${() => this.allerA(1)}>Suivant</button>
      </div>

      ${this.message ? html`<p class="message">${this.message}</p>` : nothing}
      ${this.manquants.length
        ? html`<p class="manquants">${this.manquants.length} produit${
            this.manquants.length > 1 ? 's' : ''} à acheter</p>`
        : nothing}

      <div class="grille ${this.large ? 'large' : 'etroit'}">
        ${this.large
          ? html`<div class="ligne-jours">
              <span class="coin"></span>
              ${jours.map((j) => html`<span class="jour">${libelleJour(j)}</span>`)}
            </div>`
          : nothing}
        ${CRENEAUX.map(([cle, nom]) => html`
          <div class="ligne-creneau">
            <span class="creneau">${nom}</span>
            ${jours.map((j) => this.rendreCase(j, cle))}
          </div>`)}
      </div>
    `;
  }

  static styles = css`
    :host { display: block; padding: 12px; color: var(--primary-text-color); }
    .entete { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
    .periode { flex: 1; text-align: center; font-weight: 600; }
    .entete button, .poser, .repas-nom, .valider-repas, .annuler-repas {
      min-height: 48px; padding: 0 12px; border-radius: 8px; cursor: pointer;
      border: 1px solid var(--divider-color); font-size: 1rem;
      background: var(--card-background-color); color: var(--primary-text-color);
    }
    .grille { display: flex; flex-direction: column; gap: 8px; }
    .ligne-jours, .ligne-creneau { display: flex; gap: 8px; align-items: stretch; }
    .creneau, .coin { flex: 0 0 7em; display: flex; align-items: center;
                      font-weight: 600; }
    .jour { flex: 1; text-align: center; font-weight: 600; }
    .case {
      flex: 1; display: flex; flex-direction: column; gap: 6px; padding: 6px;
      border: 1px dashed var(--divider-color); border-radius: 8px;
      min-height: 48px;
    }
    .repas { display: flex; flex-wrap: wrap; gap: 4px; align-items: center; }
    .repas-nom { flex: 1; text-align: left; }
    .etat-done .repas-nom { text-decoration: line-through; opacity: 0.7; }
    .valide { opacity: 0.75; font-size: 0.85rem; }
    .poser { align-self: stretch; }
    .message, .manquants { margin: 4px 0; }
    .etroit .creneau { flex: 0 0 6em; }
    @media (max-width: 700px) {
      .creneau, .coin { flex: 0 0 5.5em; }
      .repas { flex-direction: column; align-items: stretch; }
    }
  `;
}
