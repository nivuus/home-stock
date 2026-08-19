/** La fiche article : ce que le scan rend, avant que l'article ne rejoigne le
 *  panier ou le rangement.
 *
 *  Les prix de la maison sont TOUJOURS par unité de base (le gramme, le
 *  millilitre ou la pièce) — c'est ce que `home_stock/lookup` renvoie dans
 *  `price.price_per_base_unit`, et ce que `home_stock/session/add_line`
 *  attend en `unit_price`. Mais personne ne lit « 0,004 € » sur une étiquette
 *  de rayon : ce qui s'y lit, c'est le prix du paquet. Le champ de saisie de
 *  cette fiche est donc en prix-du-paquet — précisément ce que l'utilisateur
 *  a sous les yeux — et la conversion vers le prix par unité de base se fait
 *  juste avant l'envoi, jamais dans l'autre sens : un prix tapé « 2,50 » pour
 *  un paquet de 500 g doit devenir 0,005 €/g, pas rester 2,50 €/g.
 */
import { LitElement, html, css, nothing, type PropertyValues } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import type { Connexion } from '../connexion';

export type Off = {
  off_source: string;
  aisle: string;
  label: string | null;
  generic_name: string | null;
  brand: string | null;
  net_quantity: number | null;
  net_unit: string | null;
  image: string | null;
  nutriscore: string | null;
  nova: number | null;
  ecoscore: string | null;
  allergens: string | null;
  traces: string | null;
  additives: string | null;
  off_labels: string | null;
  nutrition_per_100: Record<string, number> | null;
  rejections: string[];
};

export type Candidat = { product_id: number; name: string; score: number };

export type Prix = {
  price_per_base_unit: number | null;
  source: 'store' | 'open_prices' | 'last_known' | null;
  store: string | null;
};

export type OffreConversion = { product_id: number; to_unit: string; reference_quantity: number };

export type ResultatLookup = {
  code: string;
  known: boolean;
  article: Record<string, any> | null;
  product: Record<string, any> | null;
  off: Off | null;
  off_raw: Record<string, any> | null;
  off_source: string | null;
  candidates: Candidat[];
  preselected_product_id: number | null;
  price: Prix | null;
  conversion_offer: OffreConversion | null;
  throttled: boolean;
  timed_out: boolean;
};

type ArticleCree = { article_id: number; product_id: number; created: boolean; off_dropped_fields: string[] };

/** Ce qu'Open Food Facts appelle chaque colonne, en français, pour dire ce
 *  qui a été jugé trop peu fiable pour être enregistré. Une clé absente d'ici
 *  s'affiche telle quelle plutôt que de disparaître. */
const LIBELLES_CHAMPS: Record<string, string> = {
  nutriscore: 'Nutri-Score', nova: 'classification NOVA', ecoscore: 'Éco-score',
  kcal_per_base_unit: 'calories', proteins: 'protéines', carbohydrates: 'glucides',
  sugars: 'sucres', added_sugars: 'sucres ajoutés', fat: 'matières grasses',
  saturated_fat: 'graisses saturées', fiber: 'fibres', salt: 'sel',
};

/** Le prix par unité de base, ramené à ce qu'affiche le champ : le prix du
 *  paquet tel qu'il se lit sur l'étiquette. `null` quand il n'y a pas de prix. */
export function prixPaquetAffiche(prixParBase: number | null | undefined,
                                  netQuantity: number | null | undefined): string {
  if (prixParBase === null || prixParBase === undefined) return '';
  const base = netQuantity && netQuantity > 0 ? netQuantity : 1;
  return (prixParBase * base).toFixed(2).replace('.', ',');
}

/** L'inverse : ce que l'utilisateur a tapé pour le paquet, ramené au prix par
 *  unité de base — la seule forme que la maison enregistre. Accepte la
 *  virgule ou le point. `null` quand la saisie n'est pas un nombre. */
export function prixBaseDepuisSaisie(saisie: string,
                                     netQuantity: number | null | undefined): number | null {
  const nombre = Number.parseFloat(saisie.trim().replace(',', '.'));
  if (!Number.isFinite(nombre)) return null;
  const base = netQuantity && netQuantity > 0 ? netQuantity : 1;
  return nombre / base;
}

function quantiteNetteActuelle(resultat: ResultatLookup): number | null {
  return resultat.article?.net_quantity ?? resultat.off?.net_quantity ?? null;
}

function uniteActuelle(resultat: ResultatLookup): string {
  return resultat.product?.base_unit ?? resultat.off?.net_unit ?? '';
}

function kcalPour100g(resultat: ResultatLookup): number | null {
  const direct = resultat.off?.nutrition_per_100?.kcal;
  if (direct != null) return direct;
  const parBase = resultat.article?.kcal_per_base_unit;
  const unite = resultat.product?.base_unit;
  if (parBase != null && (unite === 'g' || unite === 'ml')) return parBase * 100;
  return null;
}

function texteProvenancePrix(prix: Prix | null): string {
  if (!prix || prix.price_per_base_unit == null || !prix.source) return 'Aucun prix connu';
  if (prix.source === 'store') return prix.store ? `dernier prix ${prix.store}` : 'dernier prix en magasin';
  if (prix.source === 'open_prices') return 'Open Prices';
  return 'dernier prix connu';
}

@customElement('home-stock-fiche')
export class FicheArticle extends LitElement {
  @property({ attribute: false }) resultat!: ResultatLookup;
  @property({ attribute: false }) mode: 'panier' | 'rangement' = 'rangement';
  @property({ attribute: false }) connexion?: Connexion;

  @state() private productChoisi: number | 'new' | null = null;
  @state() private nomNouveauProduit = '';
  @state() private uniteNouveauProduit: 'g' | 'ml' | 'piece' = 'piece';
  @state() private prixPaquet = '';
  @state() private quantitePaquets = 1;
  @state() private rapportConversion: Record<string, unknown> | null = null;
  @state() private enCours = false;
  @state() private creeInfo: ArticleCree | null = null;

  protected willUpdate(changed: PropertyValues): void {
    if (changed.has('resultat') && this.resultat) {
      this.productChoisi = this.resultat.preselected_product_id;
      this.nomNouveauProduit = this.resultat.off?.generic_name ?? '';
      this.uniteNouveauProduit = (this.resultat.off?.net_unit as 'g' | 'ml') ?? 'piece';
      this.prixPaquet = prixPaquetAffiche(
        this.resultat.price?.price_per_base_unit, quantiteNetteActuelle(this.resultat));
      this.quantitePaquets = 1;
      this.rapportConversion = null;
      this.creeInfo = null;
    }
  }

  private get peutValider(): boolean {
    if (!this.resultat || this.enCours) return false;
    if (this.resultat.known) return true;
    if (!this.connexion) return false;
    if (this.productChoisi === 'new') return this.nomNouveauProduit.trim().length > 0;
    return typeof this.productChoisi === 'number';
  }

  private async valider(): Promise<void> {
    if (!this.peutValider) return;
    this.enCours = true;
    try {
      let articleId: number;
      if (this.resultat.known) {
        articleId = this.resultat.article!.id;
      } else {
        const charge: Record<string, unknown> = { code: this.resultat.code };
        if (this.resultat.off_raw) charge.off = this.resultat.off_raw;
        if (this.resultat.off_source) charge.off_source = this.resultat.off_source;
        if (this.productChoisi === 'new') {
          charge.new_product = { name: this.nomNouveauProduit.trim(), base_unit: this.uniteNouveauProduit };
        } else {
          charge.product_id = this.productChoisi;
        }
        const cree = await this.connexion!.appeler<ArticleCree>('home_stock/article/create', charge);
        articleId = cree.article_id;
        this.creeInfo = cree;
      }

      const net = quantiteNetteActuelle(this.resultat);
      const base = net && net > 0 ? net : 1;
      this.dispatchEvent(new CustomEvent('article-pret', {
        detail: {
          articleId, quantite: base * this.quantitePaquets,
          prixUnitaire: prixBaseDepuisSaisie(this.prixPaquet, net), mode: this.mode,
        },
        bubbles: true, composed: true,
      }));
    } finally {
      this.enCours = false;
    }
  }

  private async voirEffetConversion(): Promise<void> {
    const offre = this.resultat.conversion_offer;
    if (!offre || !this.connexion) return;
    this.rapportConversion = await this.connexion.appeler('home_stock/product/convert_unit', {
      product_id: offre.product_id, to_unit: offre.to_unit,
      reference_quantity: offre.reference_quantity, dry_run: true,
    });
  }

  private async appliquerConversion(): Promise<void> {
    const offre = this.resultat.conversion_offer;
    if (!offre || !this.connexion || !this.rapportConversion) return;
    this.rapportConversion = await this.connexion.appeler('home_stock/product/convert_unit', {
      product_id: offre.product_id, to_unit: offre.to_unit,
      reference_quantity: offre.reference_quantity, dry_run: false,
    });
  }

  private rendreRattachement() {
    if (this.resultat.known) return nothing;
    return html`
      <section class="rattachement">
        ${this.resultat.candidates.map((c) => html`
          <label class="candidat">
            <input type="radio" name="produit" .value=${String(c.product_id)}
              .checked=${this.productChoisi === c.product_id}
              @change=${() => { this.productChoisi = c.product_id; }} />
            <span>${c.name}</span>
          </label>
        `)}
        <label class="candidat nouveau">
          <input type="radio" name="produit" value="new"
            .checked=${this.productChoisi === 'new'}
            @change=${() => { this.productChoisi = 'new'; }} />
          <span>Nouveau produit</span>
        </label>
        ${this.productChoisi === 'new' ? html`
          <div class="nouveau-produit">
            <input class="nom-nouveau" placeholder="Nom du produit" .value=${this.nomNouveauProduit}
              @input=${(e: InputEvent) => { this.nomNouveauProduit = (e.target as HTMLInputElement).value; }} />
            <select class="unite-nouveau" .value=${this.uniteNouveauProduit}
              @change=${(e: Event) => {
                this.uniteNouveauProduit = (e.target as HTMLSelectElement).value as 'g' | 'ml' | 'piece';
              }}>
              <option value="g">grammes</option>
              <option value="ml">millilitres</option>
              <option value="piece">à la pièce</option>
            </select>
          </div>` : nothing}
      </section>
    `;
  }

  private rendreConversion() {
    const offre = this.resultat.conversion_offer;
    if (!offre) return nothing;
    return html`
      <section class="conversion-offre">
        <p>Passer de pièce à ${offre.to_unit} — 1 unité = ${offre.reference_quantity} ${offre.to_unit}</p>
        ${this.rapportConversion ? html`
          <p class="rapport-conversion">
            ${this.rapportConversion.articles as number} article(s),
            ${this.rapportConversion.batches as number} lot(s),
            ${this.rapportConversion.movements as number} mouvement(s) concernés.
          </p>
          ${this.rapportConversion.applied
            ? html`<p class="conversion-appliquee">Conversion appliquée.</p>`
            : html`<button class="appliquer-conversion" @click=${this.appliquerConversion}>
                Appliquer la conversion
              </button>`}
        ` : html`<button class="voir-effet" @click=${this.voirEffetConversion}>
            Voir l'effet du changement d'unité
          </button>`}
      </section>
    `;
  }

  render() {
    if (!this.resultat) return nothing;
    const r = this.resultat;
    const nom = r.off?.label ?? r.article?.label ?? r.product?.name ?? 'Article';
    const marque = r.off?.brand ?? r.article?.brand ?? null;
    const poids = quantiteNetteActuelle(r);
    const unite = uniteActuelle(r);
    const image = r.off?.image ?? r.article?.image ?? null;
    const nutriscore = r.off?.nutriscore ?? r.article?.nutriscore ?? null;
    const kcal = kcalPour100g(r);
    const detailPrix = prixBaseDepuisSaisie(this.prixPaquet, quantiteNetteActuelle(r));

    return html`
      <section class="entete">
        ${image ? html`<img class="image" src=${image} alt="" />` : nothing}
        <h2 class="nom">${nom}</h2>
        ${marque ? html`<p class="marque">${marque}</p>` : nothing}
        ${poids ? html`<p class="poids">${poids} ${unite}</p>` : nothing}
        ${nutriscore ? html`<p class="nutriscore">Nutri-Score ${nutriscore.toUpperCase()}</p>` : nothing}
        ${kcal != null ? html`<p class="kcal">${Math.round(kcal)} kcal / 100 g</p>` : nothing}
      </section>

      ${this.rendreRattachement()}

      <section class="prix">
        <p class="prix-provenance">${texteProvenancePrix(r.price)}</p>
        <label class="prix-label">
          Prix payé (paquet)
          <input class="prix-champ" inputmode="decimal" .value=${this.prixPaquet}
            @input=${(e: InputEvent) => { this.prixPaquet = (e.target as HTMLInputElement).value; }} />
        </label>
        ${detailPrix != null ? html`
          <p class="prix-detail">soit ${detailPrix.toFixed(4).replace('.', ',')} €/${unite || 'unité'}</p>
        ` : nothing}
      </section>

      <section class="quantite">
        <span>Quantité</span>
        <button class="moins" aria-label="Retirer un" ?disabled=${this.quantitePaquets <= 1}
          @click=${() => { this.quantitePaquets = Math.max(1, this.quantitePaquets - 1); }}>−</button>
        <span class="valeur-quantite">${this.quantitePaquets}</span>
        <button class="plus" aria-label="Ajouter un"
          @click=${() => { this.quantitePaquets += 1; }}>+</button>
      </section>

      ${this.rendreConversion()}

      ${this.creeInfo && this.creeInfo.off_dropped_fields.length ? html`
        <p class="ignores">
          Ignoré par Open Food Facts :
          ${this.creeInfo.off_dropped_fields.map((c) => LIBELLES_CHAMPS[c] ?? c).join(', ')}
        </p>` : nothing}

      <button class="action-principale" ?disabled=${!this.peutValider} @click=${this.valider}>
        ${this.mode === 'panier' ? 'Au panier' : 'Ranger'}
      </button>
    `;
  }

  static styles = css`
    :host { display: block; padding: 12px; box-sizing: border-box; color: var(--primary-text-color); }
    .image { max-width: 100%; max-height: 160px; display: block; margin: 0 auto 8px; border-radius: 8px; }
    .nom { margin: 0; font-size: 1.2rem; }
    .marque, .poids, .nutriscore, .kcal { margin: 2px 0; color: var(--secondary-text-color); }
    .candidat { display: flex; align-items: center; gap: 8px; min-height: 48px; }
    .candidat input { width: 22px; height: 22px; }
    .nom-nouveau, .prix-champ, .unite-nouveau {
      min-height: 48px; font-size: 1rem; padding: 4px 8px; box-sizing: border-box; width: 100%;
    }
    .prix { margin: 12px 0; }
    .prix-provenance { color: var(--secondary-text-color); margin: 0 0 4px; }
    .prix-detail { color: var(--secondary-text-color); font-size: 0.85rem; }
    .quantite { display: flex; align-items: center; gap: 12px; margin: 12px 0; }
    .quantite button {
      min-width: 62px; min-height: 62px; font-size: 1.5rem; border-radius: 8px; border: none;
      background: var(--primary-color); color: var(--text-primary-color, #fff);
    }
    .valeur-quantite { min-width: 32px; text-align: center; font-size: 1.2rem; }
    .conversion-offre { margin: 12px 0; padding: 8px; border-radius: 8px; background: var(--secondary-background-color); }
    .ignores { color: var(--secondary-text-color); font-size: 0.85rem; }
    .action-principale {
      display: block; width: 100%; min-height: 62px; font-size: 1.2rem; border-radius: 12px;
      border: none; background: var(--primary-color); color: var(--text-primary-color, #fff);
      margin-top: 12px;
    }
    .action-principale:disabled { opacity: 0.5; }
    button.voir-effet, button.appliquer-conversion {
      min-height: 48px; width: 100%; border-radius: 8px; border: none;
      background: var(--primary-color); color: var(--text-primary-color, #fff);
    }
  `;
}
