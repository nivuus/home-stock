/** L'écran de validation d'un repas : ce qui va sortir, et ce qu'on a mangé.
 *
 *  Une validation écrit dans un journal en AJOUT SEUL. C'est destructif au sens
 *  du panneau, donc c'est le même geste que le cochage d'une tâche sur les
 *  tablettes : armement, puis confirmation, en boutons. Jamais de
 *  `window.confirm`, qui n'est ni stylable ni désarmable.
 *
 *  Et l'écran DIT qu'il n'y a pas de retour en arrière, en toutes lettres et
 *  avant l'appui de confirmation, plutôt que de laisser croire à une annulation
 *  possible qui n'existe pas au lot 3.
 *
 *  Le sélecteur de parts est repris tel quel de l'écran « manger » du lot 2 :
 *  mêmes classes, même borne, mêmes messages de refus. Deux sélecteurs de
 *  parts divergeraient.
 */
import { LitElement, html, css, nothing } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import type { Connexion } from '../connexion';
import type { FileAttente } from '../file-attente';
import { analyserNombre, formaterNombre } from '../nombres';

/** Repris du lot 2 (`consommation.ts`) : la même borne, parce que c'est la
 *  même question posée au même endroit. */
const PARTS_MAX = 24;

export type LignePreview = {
  ingredient_id: number;
  label: string;
  product_id: number | null;
  product_name: string | null;
  base_unit: string | null;
  status: 'ok' | 'short' | 'unmatched' | 'unquantified' | 'ignored';
  needed: number | null;
  available: number;
  raw_text: string;
  batches: { batch_id: number; quantity: number }[];
};

export type PlatPreview = {
  product_name: string;
  parts: number;
  best_before: string;
  cost: number | null;
  kcal: number | null;
  unvalued: number;
  [nutriment: string]: unknown;
};

export type Preview = {
  meal_id: number;
  day: string;
  slot_key: string;
  recipe: { id: number; name: string; servings: number } | null;
  servings: number;
  factor: number;
  lines: LignePreview[];
  by_hand: LignePreview[];
  dish: PlatPreview | null;
  blocking: string[];
};

const LIBELLE_STATUT: Record<string, string> = {
  ok: 'prêt',
  short: 'stock insuffisant',
  unmatched: 'produit non identifié',
  unquantified: 'quantité inconnue',
  ignored: 'ignoré',
};

@customElement('home-stock-validation')
export class EcranValidation extends LitElement {
  @property({ attribute: false }) connexion?: Connexion;
  @property({ attribute: false }) file?: FileAttente;
  @property({ type: Number }) mealId?: number;

  @state() preview: Preview | null = null;
  @state() partsMangees: number | null = 1;
  @state() partage = false;
  @state() partsTotal = 4;
  @state() partsMoi = 1;
  /** Les lignes que l'utilisateur a retirées de ce décrément. */
  @state() retirees: number[] = [];
  @state() arme = false;
  @state() enCours = false;
  @state() enAttenteEnvoi = false;
  @state() erreur: string | null = null;

  connectedCallback(): void {
    super.connectedCallback();
    void this.simuler();
  }

  /** Rappelle la simulation. N'écrit jamais rien : `meal/preview` est en
   *  lecture seule, et c'est elle qu'on rejoue à chaque retrait de ligne. */
  async simuler(): Promise<void> {
    if (!this.connexion || this.mealId === undefined) return;
    this.preview = await this.connexion.appeler<Preview>('home_stock/meal/preview', {
      meal_id: this.mealId, skip_ingredient_ids: this.retirees,
    });
  }

  async retirerLigne(ligne: LignePreview): Promise<void> {
    this.retirees = [...this.retirees, ligne.ingredient_id];
    this.arme = false;
    await this.simuler();
  }

  get bloque(): boolean {
    return (this.preview?.blocking.length ?? 0) > 0;
  }

  private valider(): void {
    if (this.bloque || this.enCours) return;
    if (!this.arme) {
      this.arme = true;
      return;
    }
    void this.envoyer();
  }

  annuler(): void {
    this.arme = false;
  }

  private async envoyer(): Promise<void> {
    if (!this.file || this.mealId === undefined || this.enCours) return;
    const parts = this.partsMangees;
    if (parts === null || parts < 0) {
      this.erreur = 'Parts mangées : donne un nombre positif ou zéro.';
      return;
    }
    if (this.preview?.dish && parts > this.preview.dish.parts) {
      this.erreur = 'On ne mange pas plus de parts que le plat n’en fait.';
      return;
    }
    if (this.partage && !(this.partsTotal >= 1 && this.partsTotal <= PARTS_MAX
                          && this.partsMoi >= 0 && this.partsMoi <= this.partsTotal)) {
      this.erreur = this.partsTotal > PARTS_MAX
        ? `On ne sert pas plus de ${PARTS_MAX} parts.`
        : 'On ne mange pas plus de parts qu’il n’en a été servi.';
      return;
    }

    this.erreur = null;
    this.enCours = true;
    this.arme = false;
    const charge: Record<string, unknown> = {
      meal_id: this.mealId, portions_eaten: parts,
      skip_ingredient_ids: this.retirees,
    };
    if (this.partage) {
      charge.parts_total = this.partsTotal;
      charge.parts_mine = this.partsMoi;
    }
    const suivi = this.file.ajouter('home_stock/meal/validate', charge);
    void this.file.rejouer?.();
    const sort = await suivi.sort;
    this.enCours = false;
    this.enAttenteEnvoi = sort === 'en-attente';
    if (sort === 'refusee') {
      this.erreur = 'La validation a été refusée.';
      return;
    }
    this.dispatchEvent(new CustomEvent('repas-valide', {
      detail: { meal_id: this.mealId }, bubbles: true, composed: true,
    }));
  }

  // --- rendu --------------------------------------------------------------

  private rendreLigne(ligne: LignePreview, retirable: boolean) {
    return html`
      <li class="ligne statut-${ligne.status}">
        <span class="ligne-quantite">${ligne.label}</span>
        <span class="ligne-nom">${ligne.product_name ?? ligne.raw_text}</span>
        <span class="ligne-statut">${LIBELLE_STATUT[ligne.status]}</span>
        ${retirable
          ? html`<button class="retirer" @click=${() => this.retirerLigne(ligne)}>
              Retirer
            </button>`
          : nothing}
      </li>
    `;
  }

  private rendreValeur(valeur: unknown, suffixe = ''): string {
    // Un tiret, jamais « 0 » : `null` veut dire inconnu, et zéro affirmerait
    // une mesure que personne n'a faite.
    if (typeof valeur !== 'number') return '—';
    return `${formaterNombre(valeur)}${suffixe}`;
  }

  private rendrePlat() {
    const plat = this.preview?.dish;
    if (!plat) return nothing;
    return html`
      <section class="plat">
        <h2>${plat.product_name}</h2>
        <dl>
          <div><dt>Parts</dt><dd class="plat-parts">${formaterNombre(plat.parts)}</dd></div>
          <div><dt>À consommer avant</dt>
               <dd class="plat-dlc">${plat.best_before}</dd></div>
          <div><dt>Coût</dt>
               <dd class="plat-cout">${this.rendreValeur(plat.cost, ' €')}</dd></div>
          <div><dt>Par part</dt>
               <dd class="plat-kcal">${this.rendreValeur(plat.kcal, ' kcal')}</dd></div>
        </dl>
      </section>
    `;
  }

  /** Repris tel quel du lot 2 : mêmes classes, mêmes bornes. */
  private rendreParts() {
    return html`
      <section class="parts">
        <label class="partage-bascule">
          <input type="checkbox" .checked=${this.partage}
            @change=${(e: Event) => {
              this.partage = (e.target as HTMLInputElement).checked;
            }} />
          Je partage
        </label>
        ${this.partage ? html`
          <div class="compteurs">
            <label class="compteur">
              Parts servies
              <input class="parts-total" type="number" inputmode="numeric"
                min="1" max=${PARTS_MAX} .value=${String(this.partsTotal)}
                @input=${(e: Event) => {
                  const valeur = Number.parseInt((e.target as HTMLInputElement).value, 10);
                  if (Number.isFinite(valeur)) this.partsTotal = valeur;
                }} />
            </label>
            <label class="compteur">
              Les miennes
              <input class="parts-moi" type="number" inputmode="numeric"
                min="0" max=${this.partsTotal} .value=${String(this.partsMoi)}
                @input=${(e: Event) => {
                  const valeur = Number.parseInt((e.target as HTMLInputElement).value, 10);
                  if (Number.isFinite(valeur)) this.partsMoi = valeur;
                }} />
            </label>
          </div>` : nothing}
      </section>
    `;
  }

  render() {
    if (!this.preview) return html`<p class="chargement">Chargement…</p>`;
    const preview = this.preview;
    return html`
      <h1>${preview.recipe?.name ?? 'Repas'}</h1>

      <section class="sorties">
        <h2>Ce qui sort du stock</h2>
        <ul>${preview.lines.map((l) => this.rendreLigne(l, true))}</ul>
      </section>

      ${preview.by_hand.length
        ? html`<section class="a-la-main">
            <h2>À sortir à la main</h2>
            <ul>${preview.by_hand.map((l) => this.rendreLigne(l, false))}</ul>
          </section>`
        : nothing}

      ${this.rendrePlat()}

      <label class="mangees">
        Parts mangées
        <input class="parts-mangees" type="text" inputmode="decimal"
          .value=${this.partsMangees === null ? '' : formaterNombre(this.partsMangees)}
          @input=${(e: Event) => {
            const lu = analyserNombre((e.target as HTMLInputElement).value);
            // `analyserNombre` gère déjà la virgule ET le point : réécrire un
            // parseur ici referait l'incident du lot 1, où une virgule effaçait
            // un seuil en silence.
            if (lu.ok) this.partsMangees = lu.valeur;
          }} />
      </label>

      ${this.rendreParts()}

      ${this.bloque
        ? html`<p class="blocage">
            Il manque du stock pour au moins un ingrédient : ajustez la quantité
            ou retirez ces lignes avant de valider.
          </p>`
        : nothing}

      ${this.erreur ? html`<p class="erreur">${this.erreur}</p>` : nothing}
      ${this.enAttenteEnvoi
        ? html`<p class="en-attente">Enregistré, en attente de réseau.</p>`
        : nothing}

      ${this.arme
        ? html`<p class="sans-retour">
            Cette validation ne s'annule pas : les mouvements écrits restent au
            journal.
          </p>`
        : nothing}

      <div class="actions">
        <button class="valider" ?disabled=${this.bloque || this.enCours}
                @click=${() => this.valider()}>
          ${this.arme ? 'Confirmer la validation' : 'Valider le repas'}
        </button>
        ${this.arme
          ? html`<button class="annuler" @click=${() => this.annuler()}>Annuler</button>`
          : nothing}
      </div>
    `;
  }

  static styles = css`
    :host { display: block; padding: 12px; color: var(--primary-text-color); }
    h1 { font-size: 1.4rem; margin: 0 0 12px; }
    h2 { font-size: 1.05rem; margin: 16px 0 6px; }
    ul { list-style: none; padding: 0; display: flex; flex-direction: column; gap: 6px; }
    .ligne {
      display: flex; align-items: center; gap: 10px; min-height: 48px;
      padding: 4px 8px; border-radius: 8px;
      border: 1px solid var(--divider-color);
    }
    .ligne-quantite { font-weight: 600; min-width: 6em; }
    .ligne-nom { flex: 1; }
    .ligne-statut { opacity: 0.75; font-size: 0.85rem; }
    .statut-short { border-color: var(--error-color, #a01b1b); }
    .retirer, .valider, .annuler {
      min-height: 48px; padding: 0 16px; border-radius: 8px; cursor: pointer;
      border: 1px solid var(--divider-color); font-size: 1rem;
      background: var(--card-background-color); color: var(--primary-text-color);
    }
    .valider { background: var(--primary-color, #03a9f4); color: #fff; }
    .valider[disabled] { opacity: 0.4; cursor: default; }
    .plat dl { display: flex; flex-wrap: wrap; gap: 12px; margin: 0; }
    .plat dt { opacity: 0.75; font-size: 0.85rem; }
    .plat dd { margin: 0; font-weight: 600; }
    .mangees { display: flex; flex-direction: column; gap: 4px; margin-top: 16px; }
    .parts-mangees { min-height: 48px; font-size: 1rem; padding: 4px 8px;
                     box-sizing: border-box; }
    .partage-bascule { display: flex; align-items: center; gap: 8px; min-height: 48px; }
    .partage-bascule input { width: 22px; height: 22px; }
    .compteurs { display: flex; gap: 12px; }
    .parts-total, .parts-moi { min-height: 48px; font-size: 1rem; padding: 4px 8px;
                               box-sizing: border-box; width: 100%; }
    .blocage, .erreur { color: var(--error-color, #a01b1b); }
    .sans-retour { font-weight: 600; }
    .actions { display: flex; gap: 8px; margin-top: 16px; }
    @media (max-width: 700px) {
      .ligne { flex-wrap: wrap; }
      .compteurs { flex-direction: column; }
    }
  `;
}
