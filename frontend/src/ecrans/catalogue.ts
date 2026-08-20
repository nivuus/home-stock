/** L'écran Catalogue : consultation et correction des produits.
 *
 *  Pensé pour le PC — un champ de recherche, une liste dense, l'édition
 *  d'un produit — pas pour le rayon d'un magasin : la souris et les listes
 *  longues sont ici tolérées, contrairement au scanner ou au panier.
 *
 *  Toute écriture passe quand même par la file hors-ligne (`FileAttente`),
 *  comme le panier et le rangement : aucun deuxième chemin d'écriture par
 *  `connexion` directe.
 *
 *  `home_stock/product/update` ne connaît que la liste blanche du serveur
 *  (`PRODUCT_EDITABLE`) et refuse tout le reste — `base_unit` y compris : un
 *  changement d'unité réécrirait le sens de chaque quantité déjà enregistrée
 *  (lots, prix, nutrition), ce que seul `home_stock/product/convert_unit`
 *  fait, atomiquement. Cet écran n'offre donc **jamais** de champ pour
 *  `base_unit` — juste sa valeur, en lecture seule.
 *
 *  La catégorie est, de la même façon, en lecture seule : aucun
 *  `home_stock/categories/list` n'existe côté serveur (seul
 *  `insert_category` est utilisé, par l'import Grocy), donc aucun nom n'est
 *  disponible pour vérifier une saisie — un mauvais identifiant, mais
 *  valide, filerait un produit sous la catégorie de quelqu'un d'autre sans
 *  le moindre avertissement, une donnée que les lots recettes et liste de
 *  courses liront un jour. Plutôt qu'inventer une commande hors périmètre,
 *  cet écran affiche l'identifiant tel quel et n'en propose pas l'édition.
 *
 *  Un champ numérique saisi à la main (seuil, durée de conservation) peut
 *  contenir une virgule décimale — celle qu'un clavier français produit, et
 *  que `inputmode="decimal"` encourage. `Number('1,5')` vaut `NaN`, et
 *  `NaN` sérialisé en JSON vaut `null` : sans précaution, une simple
 *  virgule effacerait silencieusement un seuil tout en laissant croire à un
 *  enregistrement réussi — voir `analyserNombre` et `champsModifies`, qui
 *  refusent explicitement l'envoi plutôt que de deviner.
 */
import { LitElement, html, css, nothing } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import type { Connexion } from '../connexion';
import type { FileAttente } from '../file-attente';
import type { UniteBase } from './fiche';
import type { Emplacement } from './rangement';

export type Rayon = { id: number; name: string; position: number };

/** Une ligne de la table `product`, telle que `home_stock/products/list` et
 *  `home_stock/product/get` la rendent (`SELECT *`) — aucun champ renommé. */
export type Produit = {
  id: number;
  name: string;
  base_unit: UniteBase;
  category_id: number | null;
  aisle_id: number | null;
  edible: number;
  default_location_id: number | null;
  min_quantity: number | null;
  days_after_opening: number | null;
  default_shelf_life_days: number | null;
  reference_kcal: number | null;
  active: number;
  external_ref: string | null;
};

/** Les seuls noms de colonnes que cet écran peut envoyer à
 *  `home_stock/product/update` — un filet de sécurité statique, vérifié
 *  directement par le test plutôt que déduit d'une convention de nom de
 *  classe CSS. `base_unit` et `category_id` en sont volontairement absents
 *  (voir l'en-tête du fichier). */
export const CHAMPS_CATALOGUE_MODIFIABLES = [
  'name', 'aisle_id', 'default_location_id', 'min_quantity', 'default_shelf_life_days',
] as const;

/** Les seuls champs que cet écran propose de modifier. Une saisie vide vaut
 *  « aucun » (`null`) pour un identifiant, jamais une chaîne vide que le
 *  serveur refuserait pour un champ numérique. */
export type Brouillon = {
  name: string;
  aisle_id: string;
  default_location_id: string;
  min_quantity: string;
  default_shelf_life_days: string;
};

export function brouillonDepuis(produit: Produit): Brouillon {
  return {
    name: produit.name,
    aisle_id: produit.aisle_id !== null ? String(produit.aisle_id) : '',
    default_location_id: produit.default_location_id !== null ? String(produit.default_location_id) : '',
    min_quantity: produit.min_quantity !== null ? String(produit.min_quantity) : '',
    default_shelf_life_days: produit.default_shelf_life_days !== null ? String(produit.default_shelf_life_days) : '',
  };
}

function idOuNull(saisie: string): number | null {
  const s = saisie.trim();
  return s === '' ? null : Number(s);
}

export type ResultatNombre = { ok: true; valeur: number | null } | { ok: false };

/** Un champ numérique saisi à la main peut être vide (effacé exprès →
 *  `null`), un nombre valide, ou du texte qui n'en est pas — jamais un
 *  `NaN` silencieux : `Number('1,5')` vaut `NaN`, `NaN !== ancienneValeur`
 *  est toujours vrai, et `JSON.stringify(NaN)` vaut `'null'`. Un incident
 *  réel a montré qu'une simple virgule décimale suffisait ainsi à effacer
 *  un seuil de réapprovisionnement en silence tout en laissant croire à un
 *  enregistrement réussi. Accepte donc la virgule comme le point ; refuse
 *  explicitement (`{ok:false}`) tout le reste plutôt que de deviner un
 *  nombre dans du texte (« 7 jours » n'est pas 7). */
export function analyserNombre(saisie: string): ResultatNombre {
  const texte = saisie.trim();
  if (texte === '') return { ok: true, valeur: null };
  const nombre = Number(texte.replace(',', '.'));
  if (!Number.isFinite(nombre)) return { ok: false };
  return { ok: true, valeur: nombre };
}

const LIBELLE_CHAMP_NUMERIQUE = {
  min_quantity: 'Seuil de réapprovisionnement',
  default_shelf_life_days: 'Durée de conservation',
} as const;

function appliquerChampNumerique(
  cle: keyof typeof LIBELLE_CHAMP_NUMERIQUE, brouillon: Brouillon, produit: Produit,
  champs: Record<string, unknown>,
): string | null {
  const resultat = analyserNombre(brouillon[cle]);
  if (!resultat.ok) {
    return `${LIBELLE_CHAMP_NUMERIQUE[cle]} : nombre invalide (« ${brouillon[cle]} »).`;
  }
  if (resultat.valeur !== produit[cle]) champs[cle] = resultat.valeur;
  return null;
}

export type ResultatChampsModifies =
  | { ok: true; champs: Record<string, unknown> }
  | { ok: false; erreur: string };

/** Ce que `home_stock/product/update` doit recevoir dans `fields` : seuls
 *  les champs qui ont réellement changé — jamais tous, pour ne jamais
 *  réécrire une valeur inchangée sous prétexte de tout renvoyer. `{ok:
 *  false}` dès qu'un champ numérique n'est pas lisible comme un nombre :
 *  l'appelant doit alors refuser l'édition entière plutôt que d'en envoyer
 *  une partie avec un champ effacé par erreur. */
export function champsModifies(brouillon: Brouillon, produit: Produit): ResultatChampsModifies {
  const champs: Record<string, unknown> = {};
  const nom = brouillon.name.trim();
  if (nom && nom !== produit.name) champs.name = nom;

  if (idOuNull(brouillon.aisle_id) !== produit.aisle_id) champs.aisle_id = idOuNull(brouillon.aisle_id);
  if (idOuNull(brouillon.default_location_id) !== produit.default_location_id) {
    champs.default_location_id = idOuNull(brouillon.default_location_id);
  }

  const erreurSeuil = appliquerChampNumerique('min_quantity', brouillon, produit, champs);
  if (erreurSeuil) return { ok: false, erreur: erreurSeuil };
  const erreurConservation = appliquerChampNumerique('default_shelf_life_days', brouillon, produit, champs);
  if (erreurConservation) return { ok: false, erreur: erreurConservation };

  return { ok: true, champs };
}

/** Filtre par nom de produit ou nom de rayon, insensible à la casse — un
 *  simple passage linéaire, la liste reste de quelques centaines de lignes. */
export function filtrerProduits(produits: Produit[], recherche: string, nomRayon: (id: number | null) => string): Produit[] {
  const q = recherche.trim().toLowerCase();
  if (!q) return produits;
  return produits.filter((p) => p.name.toLowerCase().includes(q) || nomRayon(p.aisle_id).toLowerCase().includes(q));
}

@customElement('home-stock-catalogue')
export class EcranCatalogue extends LitElement {
  @property({ attribute: false }) connexion?: Connexion;
  /** La file hors-ligne : une correction depuis le catalogue est une
   *  écriture comme une autre (spec §14), même si le contexte — un bureau,
   *  pas un rayon — la rend rarement nécessaire en pratique. */
  @property({ attribute: false }) file?: FileAttente;
  @property({ attribute: false }) enAttente = 0;

  @state() private produits: Produit[] = [];
  @state() private rayons: Rayon[] = [];
  @state() private emplacements: Emplacement[] = [];
  @state() private quantitesParProduit: Record<number, number> = {};
  @state() private erreurChargement: string | null = null;
  @state() private recherche = '';

  @state() private produitEditeId: number | null = null;
  @state() private produitEnEdition: Produit | null = null;
  @state() private brouillon: Brouillon | null = null;
  @state() private erreurEdition: string | null = null;
  @state() private enCours = false;
  @state() private enAttenteEnvoi = false;

  connectedCallback(): void {
    super.connectedCallback();
    void this.charger();
  }

  private async charger(): Promise<void> {
    if (!this.connexion) return;
    this.erreurChargement = null;
    try {
      const [produits, rayons, emplacements, lots] = await Promise.all([
        this.connexion.appeler<{ products: Produit[] }>('home_stock/products/list'),
        this.connexion.appeler<{ aisles: Rayon[] }>('home_stock/aisles/list'),
        this.connexion.appeler<{ locations: Emplacement[] }>('home_stock/locations/list'),
        this.connexion.appeler<{ batches: { product_id: number; remaining: number }[] }>('home_stock/batches/list'),
      ]);
      this.produits = produits.products;
      this.rayons = rayons.aisles;
      this.emplacements = emplacements.locations;
      const quantites: Record<number, number> = {};
      for (const lot of lots.batches) {
        quantites[lot.product_id] = (quantites[lot.product_id] ?? 0) + lot.remaining;
      }
      this.quantitesParProduit = quantites;
    } catch {
      this.erreurChargement = 'Impossible de récupérer le catalogue. Vérifiez la connexion.';
    }
  }

  private nomRayon = (id: number | null): string => {
    if (id === null) return 'Sans rayon';
    return this.rayons.find((r) => r.id === id)?.name ?? 'Sans rayon';
  };

  private nomEmplacement(id: number | null): string {
    if (id === null) return 'Aucun';
    return this.emplacements.find((e) => e.id === id)?.name ?? 'Aucun';
  }

  private get produitsFiltres(): Produit[] {
    return filtrerProduits(this.produits, this.recherche, this.nomRayon);
  }

  private async ouvrirEdition(produit: Produit): Promise<void> {
    this.produitEditeId = produit.id;
    // Ligne de la liste : peut dater depuis le dernier chargement (une autre
    // fenêtre, un resync en cours). L'édition part d'une lecture fraîche.
    this.produitEnEdition = produit;
    this.brouillon = brouillonDepuis(produit);
    this.erreurEdition = null;
    this.enAttenteEnvoi = false;
    if (!this.connexion) return;
    try {
      const reponse = await this.connexion.appeler<{ product: Produit }>('home_stock/product/get', {
        product_id: produit.id,
      });
      if (this.produitEditeId === produit.id) {
        this.produitEnEdition = reponse.product;
        this.brouillon = brouillonDepuis(reponse.product);
      }
    } catch {
      // La ligne de la liste reste affichée en édition : mieux qu'un écran
      // bloqué, même si elle a pu dater un peu.
    }
  }

  private fermerEdition(): void {
    this.produitEditeId = null;
    this.produitEnEdition = null;
    this.brouillon = null;
    this.erreurEdition = null;
    this.enAttenteEnvoi = false;
  }

  private modifierBrouillon(champ: keyof Brouillon, valeur: string): void {
    if (!this.brouillon) return;
    this.brouillon = { ...this.brouillon, [champ]: valeur };
  }

  /** Empile puis rejoue tout de suite, comme `<home-stock-panier>` et
   *  `<home-stock-rangement>` : `file-changee` tient le compteur du panneau
   *  à jour, avant l'envoi puis après. Sans `file`, aucune écriture — il
   *  n'existe plus de deuxième chemin par `connexion` directe. */
  private ecrire(type: string, charge: Record<string, unknown>): Promise<boolean> {
    if (!this.file) return Promise.resolve(false);
    const cle = this.file.ajouter(type, charge);
    this.avertirFile();
    return this.file.rejouer().then(() => {
      this.avertirFile();
      return this.file!.resultatDe(cle) === 'envoyee';
    });
  }

  private avertirFile(): void {
    this.dispatchEvent(new CustomEvent('file-changee', { bubbles: true, composed: true }));
  }

  private async enregistrer(): Promise<void> {
    const produit = this.produitEnEdition;
    const brouillon = this.brouillon;
    if (!produit || !brouillon || this.enCours) return;
    const resultat = champsModifies(brouillon, produit);
    if (!resultat.ok) {
      // Une virgule, une unité tapée avec le nombre (« 7 jours ») : on
      // refuse l'envoi entier plutôt que d'en laisser passer une partie
      // avec un champ effacé par erreur (voir `analyserNombre`).
      this.erreurEdition = resultat.erreur;
      return;
    }
    if (Object.keys(resultat.champs).length === 0) {
      this.fermerEdition();
      return;
    }
    this.enCours = true;
    this.erreurEdition = null;
    this.enAttenteEnvoi = false;
    const reussi = await this.ecrire('home_stock/product/update', {
      product_id: produit.id, fields: resultat.champs,
    });
    this.enCours = false;
    if (reussi) {
      await this.charger();
      this.fermerEdition();
    } else {
      // Refusé (le panneau l'affiche déjà en français dans sa bannière) ou
      // simplement encore en file (hors ligne) : l'édition reste ouverte,
      // rien n'est perdu.
      this.enAttenteEnvoi = true;
    }
  }

  private rendreEdition(produit: Produit) {
    const brouillon = this.brouillon;
    if (!brouillon) return nothing;
    return html`
      <div class="edition">
        <label class="champ">
          Nom
          <input class="champ-nom" .value=${brouillon.name}
            @input=${(e: InputEvent) => this.modifierBrouillon('name', (e.target as HTMLInputElement).value)} />
        </label>
        <label class="champ">
          Rayon
          <select class="champ-rayon" .value=${brouillon.aisle_id}
            @change=${(e: Event) => this.modifierBrouillon('aisle_id', (e.target as HTMLSelectElement).value)}>
            <option value="">Sans rayon</option>
            ${this.rayons.map((r) => html`<option value=${String(r.id)}>${r.name}</option>`)}
          </select>
        </label>
        <label class="champ">
          Emplacement par défaut
          <select class="champ-emplacement" .value=${brouillon.default_location_id}
            @change=${(e: Event) => this.modifierBrouillon('default_location_id', (e.target as HTMLSelectElement).value)}>
            <option value="">Aucun</option>
            ${this.emplacements.map((e) => html`<option value=${String(e.id)}>${e.name}</option>`)}
          </select>
        </label>
        <label class="champ">
          Seuil de réapprovisionnement${produit.base_unit !== 'piece' ? ` (${produit.base_unit})` : ''}
          <input class="champ-seuil" inputmode="decimal" placeholder="ex. 200" .value=${brouillon.min_quantity}
            @input=${(e: InputEvent) => this.modifierBrouillon('min_quantity', (e.target as HTMLInputElement).value)} />
        </label>
        <label class="champ">
          Durée de conservation (jours)
          <input class="champ-conservation" inputmode="decimal" placeholder="ex. 5" .value=${brouillon.default_shelf_life_days}
            @input=${(e: InputEvent) =>
              this.modifierBrouillon('default_shelf_life_days', (e.target as HTMLInputElement).value)} />
        </label>
        <p class="champ-lecture-seule">
          Catégorie : ${produit.category_id ?? 'aucune'} (identifiant interne) — non modifiable ici : aucune
          liste de noms n'existe côté serveur pour vérifier une saisie.
        </p>
        <p class="champ-lecture-seule">
          Unité de base : ${produit.base_unit === 'piece' ? 'à la pièce' : produit.base_unit}
          — se change uniquement par une conversion, pas depuis cet écran.
        </p>
        ${this.enAttenteEnvoi ? html`
          <p class="etat-envoi">Enregistrement en file d'attente (hors ligne) ou refusé — voir le message ci-dessus.</p>
        ` : nothing}
        ${this.erreurEdition ? html`<p class="erreur">${this.erreurEdition}</p>` : nothing}
        <div class="actions-edition">
          <button class="enregistrer" ?disabled=${this.enCours} @click=${this.enregistrer}>
            ${this.enCours ? 'Enregistrement…' : 'Enregistrer'}
          </button>
          <button class="annuler" ?disabled=${this.enCours} @click=${() => this.fermerEdition()}>Annuler</button>
        </div>
      </div>
    `;
  }

  private rendreLigne(produit: Produit) {
    const quantite = this.quantitesParProduit[produit.id] ?? 0;
    const suffixe = produit.base_unit !== 'piece' ? ` ${produit.base_unit}` : '';
    return html`
      <article class="ligne">
        <div class="infos">
          <p class="nom">${produit.name}</p>
          <p class="meta">
            ${this.nomRayon(produit.aisle_id)} · en stock : ${quantite}${suffixe}
            ${produit.min_quantity !== null ? html` · seuil : ${produit.min_quantity}${suffixe}` : nothing}
            · emplacement : ${this.nomEmplacement(produit.default_location_id)}
          </p>
        </div>
        <button class="modifier" @click=${() => this.ouvrirEdition(produit)}>Modifier</button>
        ${this.produitEditeId === produit.id ? this.rendreEdition(this.produitEnEdition ?? produit) : nothing}
      </article>
    `;
  }

  render() {
    return html`
      <input class="recherche" type="search" placeholder="Rechercher un produit ou un rayon…"
        .value=${this.recherche}
        @input=${(e: InputEvent) => { this.recherche = (e.target as HTMLInputElement).value; }} />

      ${this.enAttente > 0 ? html`
        <p class="en-attente">${this.enAttente} envoi${this.enAttente > 1 ? 's' : ''} en attente de réseau</p>
      ` : nothing}

      ${this.erreurChargement ? html`
        <p class="erreur">${this.erreurChargement}</p>
        <button class="reessayer" @click=${() => { void this.charger(); }}>Réessayer</button>
      ` : nothing}

      ${!this.erreurChargement && this.produitsFiltres.length === 0 ? html`
        <p class="vide">Aucun produit.</p>
      ` : nothing}

      <div class="liste">
        ${this.produitsFiltres.map((p) => this.rendreLigne(p))}
      </div>
    `;
  }

  static styles = css`
    :host { display: block; padding: 12px; box-sizing: border-box; color: var(--primary-text-color); }
    .recherche {
      display: block; width: 100%; min-height: 48px; box-sizing: border-box; font-size: 1rem;
      padding: 4px 12px; border-radius: 8px; border: 1px solid var(--divider-color, #ddd); margin-bottom: 8px;
    }
    .en-attente { text-align: center; color: var(--secondary-text-color); font-size: 0.85rem; margin: 0 0 8px; }
    .vide { color: var(--secondary-text-color); text-align: center; }
    .erreur { color: var(--error-color, #b3261e); font-size: 0.9rem; }
    .reessayer {
      min-height: 48px; width: 100%; border-radius: 8px; border: none;
      background: var(--primary-color); color: var(--text-primary-color, #fff);
    }
    .ligne {
      display: flex; flex-wrap: wrap; align-items: center; gap: 8px; padding: 8px 0;
      border-bottom: 1px solid var(--divider-color, #ddd);
    }
    .infos { flex: 1; min-width: 0; }
    .nom { margin: 0 0 4px; font-weight: 600; }
    .meta { margin: 0; color: var(--secondary-text-color); font-size: 0.85rem; }
    .modifier {
      min-height: 48px; min-width: 48px; padding: 0 16px; border-radius: 8px; border: none;
      background: var(--primary-color); color: var(--text-primary-color, #fff); flex-shrink: 0;
    }
    .edition {
      flex: 1 0 100%; display: flex; flex-direction: column; gap: 8px; margin-top: 8px;
      padding: 12px; border-radius: 8px; background: var(--secondary-background-color);
      box-sizing: border-box;
    }
    .champ { display: block; font-size: 0.85rem; }
    .champ-nom, .champ-rayon, .champ-emplacement, .champ-seuil, .champ-conservation {
      display: block; width: 100%; min-height: 48px; box-sizing: border-box; font-size: 1rem;
      padding: 4px 8px; margin-top: 4px;
    }
    .champ-lecture-seule { color: var(--secondary-text-color); font-size: 0.85rem; margin: 4px 0; }
    .etat-envoi { color: var(--secondary-text-color); font-size: 0.85rem; }
    .actions-edition { display: flex; flex-wrap: wrap; gap: 8px; }
    .enregistrer, .annuler {
      min-height: 48px; flex: 1; border-radius: 8px; border: none; font-size: 0.95rem;
    }
    .enregistrer { background: var(--primary-color); color: var(--text-primary-color, #fff); }
    .enregistrer:disabled { opacity: 0.5; }
    .annuler { background: var(--secondary-background-color); color: var(--primary-text-color); border: 1px solid var(--divider-color, #ddd); }
  `;
}
