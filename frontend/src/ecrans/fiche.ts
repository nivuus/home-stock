/** La fiche article : ce que le scan rend, avant que l'article ne rejoigne le
 *  panier ou le rangement.
 *
 *  Les prix de la maison sont TOUJOURS par unité de base (le gramme, le
 *  millilitre ou la pièce) — c'est ce que `home_stock/lookup` renvoie dans
 *  `price.price_per_base_unit`, et ce que `home_stock/session/add_line`
 *  attend en `unit_price`. Mais personne ne lit « 0,004 € » sur une étiquette
 *  de rayon, et le diviseur qui fait le lien dépend de l'unité de suivi du
 *  PRODUIT (`product.base_unit`), pas de la simple présence d'un poids :
 *
 *   - à la pièce : le paquet EST l'unité. Pas de diviseur — un poids net
 *     d'Open Food Facts n'a rien à faire dans ce calcul.
 *   - au gramme/millilitre, poids connu : le prix du paquet divisé par ce
 *     poids.
 *   - au gramme/millilitre, poids inconnu — le cas le plus courant du
 *     catalogue actuel : on ne devine JAMAIS de diviseur. Le poids est
 *     demandé, pré-rempli depuis Open Food Facts quand il y en a un, et
 *     envoyé comme correction du champ `net_quantity` pour ne plus jamais
 *     être redemandé.
 */
import { LitElement, html, css, nothing, type PropertyValues } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import type { Connexion } from '../connexion';
import type { FileAttente } from '../file-attente';

export type UniteBase = 'g' | 'ml' | 'piece';

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

export type RapportConversion = {
  applied: boolean;
  already_converted?: boolean;
  articles: number;
  batches: number;
  movements: number;
  articles_using_reference: unknown[];
};

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

export type ArticlePret = {
  articleId: number;
  quantite: number;
  prixUnitaire: number | null;
  mode: 'panier' | 'rangement';
  offDroppedFields: string[];
};

/** Ce qu'Open Food Facts appelle chaque colonne, en français, pour dire ce
 *  qui a été jugé trop peu fiable pour être enregistré. Une clé absente d'ici
 *  s'affiche telle quelle plutôt que de disparaître — jamais un nom de
 *  colonne brut comme « net_quantity » dans un panneau en français. */
export const LIBELLES_CHAMPS: Record<string, string> = {
  label: 'nom', brand: 'marque', net_quantity: 'poids net', image: 'image',
  kcal_per_base_unit: 'calories', proteins: 'protéines', carbohydrates: 'glucides',
  sugars: 'sucres', added_sugars: 'sucres ajoutés', fat: 'matières grasses',
  saturated_fat: 'graisses saturées', fiber: 'fibres', salt: 'sel',
  nutriscore: 'Nutri-Score', nova: 'classification NOVA', ecoscore: 'Éco-score',
  allergens: 'allergènes', traces: 'traces', additives: 'additifs',
  off_labels: 'labels', off_raw: 'réponse Open Food Facts',
};

export function libellesChamps(colonnes: string[]): string {
  return colonnes.map((c) => LIBELLES_CHAMPS[c] ?? c).join(', ');
}

/** Le prix par unité de base, ramené à ce qu'affiche le champ.
 *
 *  À la pièce, le prix du paquet EST le prix par unité de base : rien à
 *  convertir. Au gramme/millilitre, il faut le poids du paquet — sans lui,
 *  aucune conversion n'est possible, et mieux vaut un champ vide qu'un
 *  chiffre faux. */
export function prixPaquetAffiche(prixParBase: number | null | undefined,
                                  unite: UniteBase | null, poids: number | null): string {
  if (prixParBase === null || prixParBase === undefined) return '';
  if (unite === 'piece') return prixParBase.toFixed(2).replace('.', ',');
  if (unite === 'g' || unite === 'ml') {
    if (poids === null || poids <= 0) return '';
    return (prixParBase * poids).toFixed(2).replace('.', ',');
  }
  return '';
}

/** L'inverse : ce que l'utilisateur a tapé pour le paquet, ramené au prix par
 *  unité de base — la seule forme que la maison enregistre. `null` quand la
 *  saisie n'est pas un nombre, ou quand convertir demanderait de deviner un
 *  diviseur (unité inconnue, ou poids manquant pour un produit pesé). */
export function prixBaseDepuisSaisie(saisie: string, unite: UniteBase | null,
                                     poids: number | null): number | null {
  const nombre = Number.parseFloat(saisie.trim().replace(',', '.'));
  if (!Number.isFinite(nombre)) return null;
  if (unite === 'piece') return nombre;
  if (unite === 'g' || unite === 'ml') {
    if (poids === null || poids <= 0) return null;
    return nombre / poids;
  }
  return null;
}

function nombreDepuisSaisie(saisie: string): number | null {
  const nombre = Number.parseFloat(saisie.trim().replace(',', '.'));
  return Number.isFinite(nombre) && nombre > 0 ? nombre : null;
}

/** Le poids déjà enregistré, sans jamais en deviner un : celui de l'article
 *  s'il existe déjà, celui qu'Open Food Facts donne pour le paquet scanné
 *  sinon (le même quel que soit le produit choisi — c'est le poids du
 *  paquet, pas du produit). */
function poidsDejaConnu(resultat: ResultatLookup): number | null {
  return resultat.known ? (resultat.article?.net_quantity ?? null) : (resultat.off?.net_quantity ?? null);
}

function texteProvenancePrix(prix: Prix | null): string {
  if (!prix || prix.price_per_base_unit == null || !prix.source) return 'Aucun prix connu';
  if (prix.source === 'store') return prix.store ? `dernier prix ${prix.store}` : 'dernier prix en magasin';
  if (prix.source === 'open_prices') return 'Open Prices';
  return 'dernier prix connu';
}

function kcalPour100g(resultat: ResultatLookup): number | null {
  const direct = resultat.off?.nutrition_per_100?.kcal;
  if (direct != null) return direct;
  const parBase = resultat.article?.kcal_per_base_unit;
  const unite = resultat.product?.base_unit;
  if (parBase != null && (unite === 'g' || unite === 'ml')) return parBase * 100;
  return null;
}

function messageErreur(err: unknown): string {
  if (err && typeof err === 'object' && 'message' in err && typeof (err as any).message === 'string') {
    return (err as any).message;
  }
  return 'Une erreur est survenue.';
}

@customElement('home-stock-fiche')
export class FicheArticle extends LitElement {
  @property({ attribute: false }) resultat!: ResultatLookup;
  @property({ attribute: false }) mode: 'panier' | 'rangement' = 'rangement';
  @property({ attribute: false }) connexion?: Connexion;
  /** La file hors-ligne du panneau. Utilisée pour la correction de poids
   *  d'un article déjà connu (`article/update`) : comme les ajouts au
   *  panier, elle ne doit jamais faire échouer tout le geste parce que le
   *  réseau est mauvais — exactement la situation d'un rayon de magasin. */
  @property({ attribute: false }) file?: FileAttente;

  @state() private productChoisi: number | 'new' | null = null;
  @state() private nomNouveauProduit = '';
  @state() private uniteNouveauProduit: UniteBase = 'piece';
  /** `null` tant que l'utilisateur n'a pas touché le champ : la valeur
   *  affichée suit alors le prix suggéré ET l'unité, qui peut se résoudre
   *  après coup (candidat existant, le temps que `products/list` réponde) —
   *  un état figé au montage raterait cette mise à jour. */
  @state() private prixSaisi: string | null = null;
  @state() private poidsPaquet = '';
  @state() private quantitePaquets = 1;
  @state() private produitsBaseUnit: Record<number, UniteBase> = {};
  @state() private rapportConversion: RapportConversion | null = null;
  @state() private erreurConversion: string | null = null;
  @state() private erreurAction: string | null = null;
  @state() private erreurUnites: string | null = null;
  @state() private enCours = false;

  protected willUpdate(changed: PropertyValues): void {
    if (changed.has('resultat') && this.resultat) {
      this.productChoisi = this.resultat.preselected_product_id;
      this.nomNouveauProduit = this.resultat.off?.generic_name ?? '';
      this.uniteNouveauProduit = (this.resultat.off?.net_unit as UniteBase) ?? 'piece';
      const poidsConnu = poidsDejaConnu(this.resultat);
      this.poidsPaquet = poidsConnu !== null ? String(poidsConnu) : '';
      this.prixSaisi = null;
      this.quantitePaquets = 1;
      this.rapportConversion = null;
      this.erreurConversion = null;
      this.erreurAction = null;
      this.erreurUnites = null;
      this.produitsBaseUnit = {};
    }
  }

  protected updated(changed: PropertyValues): void {
    // L'unité d'un candidat déjà au catalogue n'arrive pas dans `candidates`
    // (id/nom/score seulement) : impossible de savoir si c'est un produit à
    // la pièce ou au poids sans la demander. Un seul appel, à chaque nouveau
    // résultat qui en a besoin — jamais pour deviner, seulement pour savoir.
    // `valeurPrix` relit `produitsBaseUnit` à chaque rendu, donc le champ
    // prix suit automatiquement cette résolution une fois qu'elle arrive.
    if (changed.has('resultat') && this.resultat && !this.resultat.known
        && this.resultat.candidates.length && this.connexion) {
      void this.chargerUnitesProduits();
    }
  }

  private async chargerUnitesProduits(): Promise<void> {
    this.erreurUnites = null;
    try {
      const reponse = await this.connexion!.appeler<{ products: { id: number; base_unit: UniteBase }[] }>(
        'home_stock/products/list');
      const carte: Record<number, UniteBase> = {};
      for (const p of reponse.products) carte[p.id] = p.base_unit;
      this.produitsBaseUnit = carte;
    } catch {
      // Un échec ici ne doit jamais laisser « Chargement… » affiché pour
      // toujours : c'est le chemin le plus courant (code-barres neuf,
      // candidat déjà au catalogue) et le réseau y est justement le moins
      // fiable — un rayon de magasin. Le bouton « Réessayer » du template
      // relance le même appel.
      this.erreurUnites = 'Impossible de récupérer les informations du produit. Vérifiez la connexion.';
    }
  }

  /** L'unité du produit visé, ou `null` tant qu'elle n'est pas connue —
   *  jamais devinée. */
  private uniteConnue(): UniteBase | null {
    if (this.resultat.known) return (this.resultat.product?.base_unit as UniteBase) ?? null;
    if (this.productChoisi === 'new') return this.uniteNouveauProduit;
    if (typeof this.productChoisi === 'number') return this.produitsBaseUnit[this.productChoisi] ?? null;
    return null;
  }

  private get poidsEffectif(): number | null {
    return nombreDepuisSaisie(this.poidsPaquet);
  }

  /** Ce que le champ prix affiche : la saisie de l'utilisateur si elle
   *  existe, sinon le prix suggéré converti en prix-du-paquet pour l'unité
   *  et le poids actuellement connus — jamais un diviseur deviné. */
  private get valeurPrix(): string {
    if (this.prixSaisi !== null) return this.prixSaisi;
    const unite = this.uniteConnue();
    const poids = unite === 'piece' ? null : this.poidsEffectif;
    return prixPaquetAffiche(this.resultat.price?.price_per_base_unit, unite, poids);
  }

  private get raisonBlocage(): string | null {
    if (!this.resultat) return null;
    if (!this.resultat.known) {
      if (!this.connexion) return 'Connexion indisponible.';
      if (this.productChoisi === null) return 'Choisissez un produit.';
      if (this.productChoisi === 'new' && !this.nomNouveauProduit.trim()) {
        return 'Donnez un nom au nouveau produit.';
      }
    }
    const unite = this.uniteConnue();
    if (unite === null) return this.erreurUnites ?? 'Chargement des informations du produit…';
    if ((unite === 'g' || unite === 'ml') && this.poidsEffectif === null) {
      return 'Indiquez le poids du paquet pour calculer le prix.';
    }
    return null;
  }

  private get peutValider(): boolean {
    return !this.enCours && this.raisonBlocage === null;
  }

  /** La correction de poids d'un article déjà connu, envoyée comme les
   *  ajouts au panier : par la file hors-ligne quand elle existe, pour
   *  qu'une coupure réseau ne bloque jamais l'ajout lui-même — le poids
   *  suivra dès que la file rejoue. Sans file (l'élément peut être utilisé
   *  seul, hors du panneau), on tente quand même l'appel direct, mais sans
   *  jamais faire échouer la validation à cause de lui. */
  private enregistrerPoidsCorrige(articleId: number, poids: number): void {
    const charge = { article_id: articleId, fields: { net_quantity: poids } };
    if (this.file) {
      this.file.ajouter('home_stock/article/update', charge);
    } else if (this.connexion) {
      void this.connexion.appeler('home_stock/article/update', charge).catch(() => {});
    }
  }

  private async valider(): Promise<void> {
    if (!this.peutValider) return;
    this.enCours = true;
    this.erreurAction = null;
    try {
      const unite = this.uniteConnue()!;
      const poids = unite === 'piece' ? null : this.poidsEffectif!;
      const poidsEtaitInconnu = poidsDejaConnu(this.resultat) === null;
      let articleId: number;
      let dropped: string[] = [];

      if (this.resultat.known) {
        articleId = this.resultat.article!.id;
        if (poids !== null && poidsEtaitInconnu) {
          this.enregistrerPoidsCorrige(articleId, poids);
        }
      } else {
        const charge: Record<string, unknown> = { code: this.resultat.code };
        if (this.resultat.off_raw) charge.off = this.resultat.off_raw;
        if (this.resultat.off_source) charge.off_source = this.resultat.off_source;
        if (this.productChoisi === 'new') {
          charge.new_product = { name: this.nomNouveauProduit.trim(), base_unit: this.uniteNouveauProduit };
        } else {
          charge.product_id = this.productChoisi;
        }
        // Open Food Facts fournit déjà le poids quand il en a un (via `off`
        // ci-dessus) : on ne complète en `fields` QUE ce qu'il n'a pas dit,
        // pour ne jamais écraser une valeur OFF valable par une resaisie
        // identique marquée « manuelle » pour rien.
        if (poids !== null && poidsEtaitInconnu) {
          charge.fields = { net_quantity: poids };
        }
        const cree = await this.connexion!.appeler<ArticleCree>('home_stock/article/create', charge);
        articleId = cree.article_id;
        dropped = cree.off_dropped_fields ?? [];
      }

      const quantite = unite === 'piece' ? this.quantitePaquets : poids! * this.quantitePaquets;
      const detail: ArticlePret = {
        articleId, quantite,
        prixUnitaire: prixBaseDepuisSaisie(this.valeurPrix, unite, poids),
        mode: this.mode, offDroppedFields: dropped,
      };
      this.dispatchEvent(new CustomEvent('article-pret', { detail, bubbles: true, composed: true }));
    } catch (err) {
      this.erreurAction = messageErreur(err);
    } finally {
      this.enCours = false;
    }
  }

  private async voirEffetConversion(): Promise<void> {
    const offre = this.resultat.conversion_offer;
    if (!offre || !this.connexion) return;
    this.erreurConversion = null;
    try {
      this.rapportConversion = await this.connexion.appeler<RapportConversion>(
        'home_stock/product/convert_unit', {
          product_id: offre.product_id, to_unit: offre.to_unit,
          reference_quantity: offre.reference_quantity, dry_run: true,
        });
    } catch (err) {
      this.erreurConversion = messageErreur(err);
    }
  }

  private async appliquerConversion(): Promise<void> {
    const offre = this.resultat.conversion_offer;
    if (!offre || !this.connexion || !this.rapportConversion) return;
    this.erreurConversion = null;
    try {
      this.rapportConversion = await this.connexion.appeler<RapportConversion>(
        'home_stock/product/convert_unit', {
          product_id: offre.product_id, to_unit: offre.to_unit,
          reference_quantity: offre.reference_quantity, dry_run: false,
        });
    } catch (err) {
      this.erreurConversion = messageErreur(err);
    }
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
                this.uniteNouveauProduit = (e.target as HTMLSelectElement).value as UniteBase;
              }}>
              <option value="g">grammes</option>
              <option value="ml">millilitres</option>
              <option value="piece">à la pièce</option>
            </select>
          </div>` : nothing}
        ${this.erreurUnites ? html`
          <p class="erreur-unite">${this.erreurUnites}</p>
          <button class="reessayer-unite" @click=${() => { void this.chargerUnitesProduits(); }}>
            Réessayer
          </button>` : nothing}
      </section>
    `;
  }

  private rendreAlerteOff() {
    const r = this.resultat;
    if (r.known || r.off) return nothing;
    if (r.throttled) {
      return html`<p class="alerte-off">Open Food Facts limite les requêtes en ce moment — réessayez
        dans un instant plutôt que de créer un doublon.</p>`;
    }
    if (r.timed_out) {
      return html`<p class="alerte-off">Open Food Facts n'a pas répondu à temps — le produit existe
        peut-être déjà là-bas, réessayez avant de créer un doublon.</p>`;
    }
    return nothing;
  }

  private rendreConversion() {
    const offre = this.resultat.conversion_offer;
    if (!offre) return nothing;
    return html`
      <section class="conversion-offre">
        <p>Passer de pièce à ${offre.to_unit} — 1 unité = ${offre.reference_quantity} ${offre.to_unit}</p>
        ${this.rapportConversion ? html`
          <p class="rapport-conversion">
            ${this.rapportConversion.articles} article(s), ${this.rapportConversion.batches} lot(s),
            ${this.rapportConversion.movements} mouvement(s) concernés
            ${this.rapportConversion.articles_using_reference.length ? html`
              — dont ${this.rapportConversion.articles_using_reference.length} article(s) qui seront
              re-pesé(s) avec un poids de référence estimé, faute de poids propre.` : '.'}
          </p>
          ${this.rapportConversion.applied
            ? html`<p class="conversion-appliquee">Conversion appliquée.</p>`
            : html`<button class="appliquer-conversion" @click=${this.appliquerConversion}>
                Appliquer la conversion
              </button>`}
        ` : html`<button class="voir-effet" @click=${this.voirEffetConversion}>
            Voir l'effet du changement d'unité
          </button>`}
        ${this.erreurConversion ? html`<p class="erreur-conversion">${this.erreurConversion}</p>` : nothing}
      </section>
    `;
  }

  render() {
    if (!this.resultat) return nothing;
    const r = this.resultat;
    const nom = r.off?.label ?? r.article?.label ?? r.product?.name ?? 'Article';
    const marque = r.off?.brand ?? r.article?.brand ?? null;
    const poidsAffiche = r.article?.net_quantity ?? r.off?.net_quantity ?? null;
    const uniteAffichee = r.product?.base_unit ?? r.off?.net_unit ?? '';
    const image = r.off?.image ?? r.article?.image ?? null;
    const nutriscore = r.off?.nutriscore ?? r.article?.nutriscore ?? null;
    const kcal = kcalPour100g(r);

    const unite = this.uniteConnue();
    const poidsEffectif = unite === 'piece' ? null : this.poidsEffectif;
    // Le détail au kilo/litre n'a de sens qu'au poids : à la pièce, le champ
    // prix EST déjà la forme lisible, un « soit X €/kg » ne ferait
    // qu'inventer un troisième chiffre à côté d'un « €/unité » déjà clair.
    const detailPrix = (unite === 'g' || unite === 'ml')
      ? prixBaseDepuisSaisie(this.valeurPrix, unite, poidsEffectif) : null;
    const detailParMille = detailPrix != null ? detailPrix * 1000 : null;
    const uniteDetail = unite === 'ml' ? 'L' : 'kg';

    return html`
      <section class="entete">
        ${image ? html`<img class="image" src=${image} alt="" />` : nothing}
        <h2 class="nom">${nom}</h2>
        ${marque ? html`<p class="marque">${marque}</p>` : nothing}
        ${poidsAffiche ? html`<p class="poids">${poidsAffiche} ${uniteAffichee}</p>` : nothing}
        ${nutriscore ? html`<p class="nutriscore">Nutri-Score ${nutriscore.toUpperCase()}</p>` : nothing}
        ${kcal != null ? html`<p class="kcal">${Math.round(kcal)} kcal / 100 g</p>` : nothing}
      </section>

      ${this.rendreAlerteOff()}
      ${this.rendreRattachement()}

      <section class="prix">
        <p class="prix-provenance">${texteProvenancePrix(r.price)}</p>
        ${(unite === 'g' || unite === 'ml') && poidsDejaConnu(r) === null ? html`
          <label class="poids-label">
            Poids du paquet
            <input class="poids-champ" inputmode="decimal" placeholder="ex. 500" .value=${this.poidsPaquet}
              @input=${(e: InputEvent) => { this.poidsPaquet = (e.target as HTMLInputElement).value; }} />
            <span>${unite === 'ml' ? 'ml' : 'g'}</span>
          </label>` : nothing}
        <label class="prix-label">
          ${unite === 'piece' ? 'Prix payé (€ / unité)' : 'Prix payé (paquet)'}
          <input class="prix-champ" inputmode="decimal" .value=${this.valeurPrix}
            @input=${(e: InputEvent) => { this.prixSaisi = (e.target as HTMLInputElement).value; }} />
        </label>
        ${detailParMille != null ? html`
          <p class="prix-detail">soit ${detailParMille.toFixed(2).replace('.', ',')} €/${uniteDetail}</p>
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

      ${this.raisonBlocage ? html`<p class="motif-blocage">${this.raisonBlocage}</p>` : nothing}
      ${this.erreurAction ? html`<p class="erreur-action">${this.erreurAction}</p>` : nothing}

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
    .alerte-off {
      background: var(--warning-color, #fff3cd); color: var(--primary-text-color);
      padding: 8px; border-radius: 8px; margin: 8px 0;
    }
    .candidat { display: flex; align-items: center; gap: 8px; min-height: 48px; }
    .candidat input { width: 22px; height: 22px; }
    .nom-nouveau, .prix-champ, .poids-champ, .unite-nouveau {
      min-height: 48px; font-size: 1rem; padding: 4px 8px; box-sizing: border-box; width: 100%;
    }
    .prix { margin: 12px 0; }
    .prix-provenance { color: var(--secondary-text-color); margin: 0 0 4px; }
    .prix-detail { color: var(--secondary-text-color); font-size: 0.85rem; }
    .poids-label, .prix-label { display: block; margin: 8px 0; }
    .quantite { display: flex; align-items: center; gap: 12px; margin: 12px 0; }
    .quantite button {
      min-width: 62px; min-height: 62px; font-size: 1.5rem; border-radius: 8px; border: none;
      background: var(--primary-color); color: var(--text-primary-color, #fff);
    }
    .valeur-quantite { min-width: 32px; text-align: center; font-size: 1.2rem; }
    .conversion-offre { margin: 12px 0; padding: 8px; border-radius: 8px; background: var(--secondary-background-color); }
    .motif-blocage, .erreur-action, .erreur-conversion, .erreur-unite {
      color: var(--error-color, #b3261e); font-size: 0.9rem;
    }
    .reessayer-unite {
      min-height: 48px; width: 100%; margin-top: 4px; border-radius: 8px; border: none;
      background: var(--primary-color); color: var(--text-primary-color, #fff);
    }
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
