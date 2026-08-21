/** L'écran « recettes » : la liste, la recherche locale, « Chercher ailleurs ».
 *
 *  La liste vient de la base et se filtre EN LOCAL : quelques dizaines de
 *  recettes tiennent en mémoire, et rappeler le serveur à chaque frappe ferait
 *  clignoter l'écran pour rien.
 *
 *  Un seul bouton dépend du réseau — « Chercher ailleurs », qui interroge
 *  TheMealDB. Tout le reste de l'écran fonctionne hors ligne sur ce qui est
 *  déjà en base, parce qu'il n'y a aucune raison qu'une panne de box empêche
 *  de relire ses propres recettes.
 */
import { LitElement, html, css, nothing } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import type { Connexion } from '../connexion';
import type { FileAttente } from '../file-attente';

/** Une recette telle que `home_stock/recipes/list` la rend. */
export type LigneRecette = {
  id: number;
  name: string;
  servings: number;
  total_minutes: number | null;
  image_url: string | null;
  summary: string | null;
  language: string;
  needs_review: number;
  unmatched_count: number;
};

/** Une fiche de la source en ligne. Rien n'est encore écrit en base. */
export type FicheExterne = {
  source_ref: string;
  name: string;
  image_url: string | null;
  category: string | null;
  area: string | null;
};

/** Replie casse, accents et ponctuation, comme le fait le serveur. Sans cela
 *  « boeuf » ne trouverait pas « Bœuf » dans la liste déjà chargée. */
function replier(texte: string): string {
  return texte
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/œ/g, 'oe')
    .replace(/æ/g, 'ae')
    .toLowerCase();
}

@customElement('home-stock-recettes')
export class EcranRecettes extends LitElement {
  @property({ attribute: false }) connexion?: Connexion;
  @property({ attribute: false }) file?: FileAttente;
  @property({ type: Boolean }) enAttente = false;

  @state() recettes: LigneRecette[] = [];
  @state() filtre = '';
  @state() fiches: FicheExterne[] | null = null;
  @state() chercheEnLigne = false;
  @state() message = '';

  connectedCallback(): void {
    super.connectedCallback();
    void this.charger();
  }

  async charger(): Promise<void> {
    if (!this.connexion) return;
    const reponse = await this.connexion.appeler<{ recipes: LigneRecette[] }>(
      'home_stock/recipes/list', {});
    this.recettes = reponse.recipes ?? [];
  }

  /** Le filtre s'applique en mémoire, sans aller-retour serveur. */
  private get recettesFiltrees(): LigneRecette[] {
    if (!this.filtre.trim()) return this.recettes;
    const aiguille = replier(this.filtre.trim());
    return this.recettes.filter((r) => replier(r.name).includes(aiguille));
  }

  private ouvrir(recette: LigneRecette): void {
    this.dispatchEvent(new CustomEvent('recette-ouverte', {
      detail: { recipe_id: recette.id }, bubbles: true, composed: true,
    }));
  }

  async chercherAilleurs(): Promise<void> {
    if (!this.connexion || this.enAttente) return;
    this.chercheEnLigne = true;
    this.message = '';
    try {
      const reponse = await this.connexion.appeler<{
        hits: FicheExterne[]; reachable: boolean;
      }>('home_stock/recipe/search_external', { query: this.filtre.trim() });
      this.fiches = reponse.hits ?? [];
      if (!this.fiches.length) {
        // Une source injoignable et une recherche infructueuse se disent de la
        // même façon à l'écran : dans les deux cas, il n'y a rien à importer.
        this.message = reponse.reachable === false
          ? 'La source de recettes est injoignable pour le moment.'
          : 'Aucune recette trouvée à la source.';
      }
    } finally {
      this.chercheEnLigne = false;
    }
  }

  async importer(fiche: FicheExterne): Promise<void> {
    if (!this.connexion) return;
    const reponse = await this.connexion.appeler<{
      recipe_id: number; adapted: boolean;
    }>('home_stock/recipe/import_external', { source_ref: fiche.source_ref });
    this.message = reponse.adapted
      ? `« ${fiche.name} » a été importée et adaptée en français.`
      : `« ${fiche.name} » a été importée. Elle est en anglais : à relire.`;
    this.fiches = null;
    await this.charger();
  }

  /** Marquer une recette relue. Passe par la file : c'est une écriture, et
   *  elle doit survivre à une coupure comme toutes les autres. */
  async marquerRelue(recette: LigneRecette): Promise<void> {
    if (!this.file) return;
    this.file.ajouter('home_stock/recipe/update', {
      recipe_id: recette.id, fields: { needs_review: 0 },
    });
    this.recettes = this.recettes.map((r) =>
      r.id === recette.id ? { ...r, needs_review: 0 } : r);
  }

  private rendreRecette(recette: LigneRecette) {
    return html`
      <button class="recette" @click=${() => this.ouvrir(recette)}>
        <span class="recette-nom">${recette.name}</span>
        <span class="badges">
          ${recette.needs_review
            ? html`<span class="badge relire">à relire</span>`
            : nothing}
          ${recette.unmatched_count > 0
            ? html`<span class="badge manque">${recette.unmatched_count} non apparié${
                recette.unmatched_count > 1 ? 's' : ''}</span>`
            : nothing}
        </span>
      </button>
    `;
  }

  private rendreFiche(fiche: FicheExterne) {
    return html`
      <button class="fiche" @click=${() => this.importer(fiche)}>
        <span class="fiche-nom">${fiche.name}</span>
        <span class="fiche-meta">${[fiche.category, fiche.area]
          .filter(Boolean).join(' · ')}</span>
      </button>
    `;
  }

  render() {
    const recettes = this.recettesFiltrees;
    return html`
      <div class="entete">
        <input class="recherche" type="search" placeholder="Chercher une recette"
               .value=${this.filtre}
               @input=${(e: Event) => {
                 this.filtre = (e.target as HTMLInputElement).value;
               }} />
        <button class="ailleurs" ?disabled=${this.enAttente || this.chercheEnLigne}
                @click=${() => this.chercherAilleurs()}>
          ${this.chercheEnLigne ? 'Recherche…' : 'Chercher ailleurs'}
        </button>
      </div>

      ${this.message ? html`<p class="message">${this.message}</p>` : nothing}

      ${this.fiches
        ? html`<section class="fiches">
            <h2>Trouvées à la source</h2>
            ${this.fiches.map((f) => this.rendreFiche(f))}
          </section>`
        : nothing}

      ${recettes.length
        ? html`<section class="liste">
            ${recettes.map((r) => this.rendreRecette(r))}
          </section>`
        : html`<p class="vide">${this.filtre
            ? 'Aucune recette ne correspond.'
            : 'Aucune recette pour le moment.'}</p>`}
    `;
  }

  static styles = css`
    :host { display: block; padding: 12px; color: var(--primary-text-color); }
    .entete { display: flex; gap: 8px; margin-bottom: 12px; }
    .recherche {
      flex: 1; min-height: 48px; padding: 0 12px; font-size: 1rem;
      border: 1px solid var(--divider-color); border-radius: 8px;
      background: var(--card-background-color); color: var(--primary-text-color);
    }
    .ailleurs {
      min-height: 48px; padding: 0 16px; border-radius: 8px; cursor: pointer;
      border: 1px solid var(--divider-color);
      background: var(--card-background-color); color: var(--primary-text-color);
    }
    .ailleurs[disabled] { opacity: 0.5; cursor: default; }
    .message { margin: 8px 0; }
    .liste, .fiches { display: flex; flex-direction: column; gap: 8px; }
    h2 { font-size: 1rem; margin: 12px 0 4px; }
    .recette, .fiche {
      display: flex; justify-content: space-between; align-items: center;
      gap: 8px; min-height: 48px; padding: 8px 12px; text-align: left;
      border: 1px solid var(--divider-color); border-radius: 8px; cursor: pointer;
      background: var(--card-background-color); color: var(--primary-text-color);
      font-size: 1rem;
    }
    .recette-nom, .fiche-nom { flex: 1; }
    .badges { display: flex; gap: 6px; }
    .badge {
      padding: 2px 8px; border-radius: 999px; font-size: 0.8rem; white-space: nowrap;
    }
    /* Le repli est un orange FONCÉ, pas celui de Material : blanc sur
       #b26a00 ne donne que 4,24:1, sous le seuil de 4,5:1 que
       verifier-rendu.mjs applique. #8a5300 monte à 6,3:1. On corrige la
       couleur, jamais le seuil. */
    .relire { background: var(--warning-color, #8a5300); color: #fff; }
    .manque { background: var(--error-color, #a01b1b); color: #fff; }
    .fiche-meta { opacity: 0.75; font-size: 0.85rem; }
    .vide { opacity: 0.75; }
    @media (max-width: 700px) {
      .entete { flex-direction: column; }
    }
  `;
}
