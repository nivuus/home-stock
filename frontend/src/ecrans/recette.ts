/** La vue cuisine : une page par étape, debout, les mains sales.
 *
 *  On est à un mètre de l'écran. Donc : gros texte, plein écran, et une seule
 *  chose à lire à la fois — une couverture, un bloc Ingrédients, puis une page
 *  par étape.
 *
 *  Cinq règles, toutes contraignantes :
 *
 *  1. Navigation au BOUTON uniquement. Aucun geste, aucun appui long : la
 *     contrainte des tablettes de la maison vaut ici aussi, et des doigts
 *     couverts de farine glissent mal.
 *  2. Le bloc Ingrédients s'atteint en un appui depuis n'importe quelle étape
 *     et REVIENT où on en était. Perdre sa place au milieu d'une pâte est la
 *     raison pour laquelle on retourne au papier.
 *  3. Les minuteurs sont des boutons dessinés depuis `timer_label` /
 *     `timer_seconds`, décomptés ici via `minuteur.ts`. Aucune entité Home
 *     Assistant : une recette de quatre étapes en créerait quatre.
 *  4. `navigator.wakeLock` quand l'API existe. Son absence n'est jamais une
 *     erreur — jsdom ne l'a pas, la WebView Fire non plus.
 *  5. AUCUN appel réseau après le chargement. Hors ligne, une recette déjà
 *     ouverte reste lisible : le Wi-Fi de la cuisine ne vaut pas mieux que
 *     celui d'un rayon de supermarché.
 */
import { LitElement, html, css, nothing } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import type { Connexion } from '../connexion';
import type { FileAttente } from '../file-attente';
import { formaterQuantiteRecette } from '../nombres';
import {
  type EtatMinuteur, avancer, demarrer, formaterDuree, remettreAZero,
} from '../minuteur';

export type PuceRecette = {
  id: number;
  position: number;
  text: string;
  timer_label: string | null;
  timer_seconds: number | null;
};

export type EtapeRecette = {
  id: number;
  position: number;
  title: string | null;
  image_url: string | null;
  instructions: PuceRecette[];
};

export type LigneIngredient = {
  id: number;
  position: number;
  product_id: number | null;
  product_name: string | null;
  product_base_unit: 'g' | 'ml' | 'piece' | null;
  amount: number | null;
  measure_name: string | null;
  packaging_name: string | null;
  raw_text: string;
  match_state: string;
  display_amount?: string;
  /** Les cinq meilleurs produits, calculés par le serveur pour une ligne non
   *  appariée. C'est ce qui rend l'appariement faisable ici, en un appui,
   *  plutôt que de renvoyer quelqu'un vers un écran d'administration. */
  candidates?: { product_id: number; name: string; score: number }[];
};

export type VueRecette = {
  recipe: {
    id: number; name: string; servings: number; total_minutes: number | null;
    utensils: string | null; summary: string | null; image_url: string | null;
    language: string; needs_review: number;
  };
  steps: EtapeRecette[];
  ingredients: LigneIngredient[];
};

/** La page affichée : la couverture, puis une par étape. */
const COUVERTURE = 0;

@customElement('home-stock-recette')
export class EcranRecette extends LitElement {
  @property({ attribute: false }) connexion?: Connexion;
  @property({ attribute: false }) file?: FileAttente;
  @property({ type: Number }) recipeId?: number;
  @property({ type: Number }) mealId?: number;

  @state() vue: VueRecette | null = null;
  @state() page = COUVERTURE;
  /** Ouvert par-dessus la page en cours, jamais à sa place : on revient
   *  exactement où on en était. */
  @state() ingredientsOuverts = false;
  @state() minuteurs: Record<number, EtatMinuteur> = {};

  private _wakeLock: { release: () => Promise<void> } | null = null;
  private _tic?: ReturnType<typeof setInterval>;

  connectedCallback(): void {
    super.connectedCallback();
    void this.charger();
    void this.garderEveille();
    this._tic = setInterval(() => this.avancerLesMinuteurs(), 1000);
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    if (this._tic) clearInterval(this._tic);
    void this.relacherEveil();
  }

  async charger(): Promise<void> {
    if (!this.connexion || this.recipeId === undefined) return;
    this.vue = await this.connexion.appeler<VueRecette>(
      'home_stock/recipe/get', { recipe_id: this.recipeId });
  }

  /** Garde l'écran allumé pendant qu'on cuisine. L'absence de l'API n'est pas
   *  une erreur : jsdom ne l'a pas, la WebView Fire non plus. */
  private async garderEveille(): Promise<void> {
    const lock = (navigator as any)?.wakeLock;
    if (!lock?.request) return;
    try {
      this._wakeLock = await lock.request('screen');
    } catch {
      this._wakeLock = null;
    }
  }

  private async relacherEveil(): Promise<void> {
    try {
      await this._wakeLock?.release();
    } catch {
      /* Relâcher un verrou déjà perdu n'est pas un incident. */
    }
    this._wakeLock = null;
  }

  // --- navigation ---------------------------------------------------------

  get nombreDePages(): number {
    return (this.vue?.steps.length ?? 0) + 1;
  }

  get peutReculer(): boolean {
    return this.page > COUVERTURE;
  }

  get peutAvancer(): boolean {
    return this.page < this.nombreDePages - 1;
  }

  reculer(): void {
    if (this.peutReculer) this.page -= 1;
  }

  avancerPage(): void {
    if (this.peutAvancer) this.page += 1;
  }

  ouvrirIngredients(): void {
    this.ingredientsOuverts = true;
  }

  fermerIngredients(): void {
    this.ingredientsOuverts = false;
  }

  fermer(): void {
    this.dispatchEvent(new CustomEvent('recette-fermee',
                                       { bubbles: true, composed: true }));
  }

  validerRepas(): void {
    if (this.mealId === undefined) return;
    this.dispatchEvent(new CustomEvent('valider-repas', {
      detail: { meal_id: this.mealId }, bubbles: true, composed: true,
    }));
  }

  // --- minuteurs ----------------------------------------------------------

  basculerMinuteur(puce: PuceRecette): void {
    if (puce.timer_seconds === null) return;
    const actuel = this.minuteurs[puce.id];
    this.minuteurs = {
      ...this.minuteurs,
      [puce.id]: actuel && (actuel.enMarche || actuel.termine)
        ? remettreAZero(puce.timer_seconds)
        : demarrer(puce.timer_seconds),
    };
  }

  private avancerLesMinuteurs(): void {
    const entrees = Object.entries(this.minuteurs);
    if (!entrees.some(([, etat]) => etat.enMarche)) return;
    this.minuteurs = Object.fromEntries(
      entrees.map(([id, etat]) => [id, avancer(etat, 1)]));
  }

  // --- rendu --------------------------------------------------------------

  private libelleQuantite(ligne: LigneIngredient): string {
    if (ligne.display_amount) return ligne.display_amount;
    if (ligne.amount === null) return '';
    return formaterQuantiteRecette(
      ligne.amount, ligne.product_base_unit ?? 'g',
      ligne.measure_name, ligne.packaging_name);
  }

  /** Apparier une ligne sur un produit, depuis la cuisine.
   *
   *  Passe par la file : c'est une écriture, et le Wi-Fi de la cuisine ne vaut
   *  pas mieux que celui d'un rayon. `create_alias` est vrai parce que ce
   *  geste-ci est une décision HUMAINE explicite — c'est exactement le seul
   *  cas où un alias s'apprend.
   */
  async apparier(ligne: LigneIngredient, produitId: number): Promise<void> {
    if (!this.file) return;
    this.file.ajouter('home_stock/recipe/ingredient/match', {
      ingredient_id: ligne.id, product_id: produitId,
      state: 'confirmed', create_alias: true,
    });
    void this.file.rejouer?.();
    if (this.vue) {
      const nom = ligne.candidates?.find((c) => c.product_id === produitId)?.name
        ?? null;
      this.vue = {
        ...this.vue,
        ingredients: this.vue.ingredients.map((l) => l.id === ligne.id
          ? { ...l, match_state: 'confirmed', product_id: produitId,
              product_name: nom, candidates: [] }
          : l),
      };
    }
  }

  private rendreIngredients() {
    const lignes = this.vue?.ingredients ?? [];
    return html`
      <section class="ingredients">
        <h2>Ingrédients</h2>
        <ul>
          ${lignes.map((ligne) => html`
            <li class="ingredient ${ligne.match_state === 'unmatched'
              ? 'a-la-main' : ''}">
              <span class="quantite">${this.libelleQuantite(ligne)}</span>
              <span class="ingredient-nom">${ligne.product_name ?? ligne.raw_text}</span>
              ${ligne.match_state === 'unmatched'
                ? html`<span class="mention">à sortir à la main</span>`
                : nothing}
              ${ligne.match_state === 'unmatched' && ligne.candidates?.length
                ? html`<span class="candidats">
                    ${ligne.candidates.map((c) => html`
                      <button class="candidat"
                              @click=${() => this.apparier(ligne, c.product_id)}>
                        ${c.name}
                      </button>`)}
                  </span>`
                : nothing}
            </li>`)}
        </ul>
        <button class="fermer-ingredients" @click=${() => this.fermerIngredients()}>
          Revenir à la recette
        </button>
      </section>
    `;
  }

  private rendreCouverture() {
    const recette = this.vue!.recipe;
    return html`
      <section class="couverture">
        ${recette.image_url
          ? html`<img class="image" src=${recette.image_url} alt="" />`
          : nothing}
        <h1>${recette.name}</h1>
        <p class="meta">
          ${recette.total_minutes
            ? html`<span class="duree">⏱ ${recette.total_minutes} min</span>`
            : nothing}
          <span class="parts">🔥 ${recette.servings} part${
            recette.servings > 1 ? 's' : ''}</span>
          ${recette.utensils
            ? html`<span class="ustensiles">🍳 ${recette.utensils}</span>`
            : nothing}
        </p>
        ${recette.summary ? html`<p class="accroche">${recette.summary}</p>` : nothing}
      </section>
    `;
  }

  private rendrePuce(puce: PuceRecette) {
    const etat = this.minuteurs[puce.id];
    return html`
      <li class="puce">
        <span class="puce-texte">${puce.text}</span>
        ${puce.timer_label !== null && puce.timer_seconds !== null
          ? html`<button class="minuteur ${etat?.termine ? 'termine' : ''}"
                         @click=${() => this.basculerMinuteur(puce)}>
              ${puce.timer_label} ·
              ${formaterDuree(etat ? etat.restant : puce.timer_seconds)}
            </button>`
          : nothing}
      </li>
    `;
  }

  private rendreEtape(etape: EtapeRecette) {
    return html`
      <section class="etape">
        ${etape.image_url
          ? html`<img class="image" src=${etape.image_url} alt="" />`
          : nothing}
        <h2>${etape.title ?? `Étape ${etape.position}`}</h2>
        <ol class="puces">${etape.instructions.map((p) => this.rendrePuce(p))}</ol>
      </section>
    `;
  }

  render() {
    if (!this.vue) return html`<p class="chargement">Chargement…</p>`;
    if (this.ingredientsOuverts) return this.rendreIngredients();

    const derniere = !this.peutAvancer;
    return html`
      ${this.page === COUVERTURE
        ? this.rendreCouverture()
        : this.rendreEtape(this.vue.steps[this.page - 1])}

      <nav class="barre">
        <button class="precedent" ?disabled=${!this.peutReculer}
                @click=${() => this.reculer()}>Précédent</button>
        <button class="ingredients-bouton" @click=${() => this.ouvrirIngredients()}>
          Ingrédients
        </button>
        <span class="position">${this.page + 1} / ${this.nombreDePages}</span>
        ${derniere && this.mealId !== undefined
          ? html`<button class="cuisine" @click=${() => this.validerRepas()}>
              J'ai cuisiné
            </button>`
          : html`<button class="suivant" ?disabled=${!this.peutAvancer}
                         @click=${() => this.avancerPage()}>Suivant</button>`}
      </nav>
    `;
  }

  static styles = css`
    :host {
      display: block; padding: 16px; font-size: 1.25rem;
      color: var(--primary-text-color);
    }
    .image { width: 100%; max-height: 40vh; object-fit: cover; border-radius: 12px; }
    h1 { font-size: 1.8rem; margin: 12px 0 4px; }
    h2 { font-size: 1.5rem; margin: 12px 0 8px; }
    .meta { display: flex; flex-wrap: wrap; gap: 12px; opacity: 0.85; margin: 4px 0; }
    .accroche { opacity: 0.9; }
    .puces { display: flex; flex-direction: column; gap: 12px; padding-left: 1.2em; }
    .puce { line-height: 1.5; }
    .minuteur {
      display: block; margin-top: 8px; min-height: 48px; padding: 0 16px;
      font-size: 1.1rem; border-radius: 8px; cursor: pointer;
      border: 1px solid var(--divider-color);
      background: var(--card-background-color); color: var(--primary-text-color);
    }
    .minuteur.termine { background: var(--error-color, #a01b1b); color: #fff; }
    .ingredients ul { list-style: none; padding: 0; display: flex;
                      flex-direction: column; gap: 12px; }
    .ingredient { display: flex; flex-wrap: wrap; gap: 10px;
                  align-items: baseline; min-height: 48px; }
    .quantite { font-weight: 600; min-width: 6em; }
    .a-la-main .mention { opacity: 0.8; font-size: 0.9rem; font-style: italic; }
    .candidats { display: flex; flex-wrap: wrap; gap: 6px; width: 100%; }
    .candidat {
      min-height: 48px; padding: 0 12px; border-radius: 8px; cursor: pointer;
      border: 1px solid var(--divider-color); font-size: 0.95rem;
      background: var(--card-background-color); color: var(--primary-text-color);
    }
    .barre {
      display: flex; gap: 8px; align-items: center; margin-top: 20px;
      position: sticky; bottom: 0; padding: 8px 0;
      background: var(--card-background-color);
    }
    .barre button, .fermer-ingredients {
      min-height: 48px; padding: 0 16px; font-size: 1rem; border-radius: 8px;
      cursor: pointer; border: 1px solid var(--divider-color);
      background: var(--card-background-color); color: var(--primary-text-color);
    }
    .barre button[disabled] { opacity: 0.4; cursor: default; }
    .position { margin-left: auto; opacity: 0.75; }
    .cuisine { background: var(--primary-color, #03a9f4); color: #fff; }
    @media (max-width: 700px) {
      :host { font-size: 1.15rem; }
      .quantite { min-width: 4.5em; }
    }
  `;
}
