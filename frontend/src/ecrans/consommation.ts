/** L'écran « manger » : ce qui sort du stock, et pour qui.
 *
 *  Il vise TOUJOURS le lot que le FIFO prendrait — le plus ancien lot ouvert
 *  du produit — et le dit. Les raccourcis sont calculés sur le reste de CE
 *  lot ; le pavé numérique, lui, accepte davantage, et la sortie déborde
 *  alors sur les lots suivants comme le fait le service.
 *
 *  Les parts ne sont envoyées que sur le motif « mangé », et seulement si on
 *  a explicitement partagé : sans partage, les colonnes restent NULL en base,
 *  ce qui vaut 1/1 à la lecture. Écrire 1/1 en dur salirait le journal d'une
 *  donnée qui n'a jamais été saisie.
 */
import { LitElement, html, css, nothing } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import type { Connexion } from '../connexion';
import type { FileAttente } from '../file-attente';
import type { UniteBase } from './fiche';
import { analyserNombre, formaterNombre } from '../nombres';
import { raccourcisQuantite } from '../portion';

export type Motif = 'consumption' | 'waste' | 'expired';

const LIBELLE_MOTIF: Record<Motif, string> = {
  consumption: 'Mangé', waste: 'Jeté', expired: 'Périmé',
};

/** Ce que reste d'un lot se lit en toutes lettres, jamais un chiffre nu :
 *  « 4 pièces », « 500 g ». Ne convertit jamais en kg/l ici — contrairement
 *  aux libellés de `raccourcisQuantite`, c'est une quantité brute de lot,
 *  pas un choix parmi plusieurs. */
function afficherReste(quantite: number, unite: UniteBase): string {
  if (unite === 'piece') return `${formaterNombre(quantite)} pièce${quantite >= 2 ? 's' : ''}`;
  return `${formaterNombre(quantite)} ${unite}`;
}

@customElement('home-stock-consommation')
export class EcranConsommation extends LitElement {
  @property({ attribute: false }) connexion?: Connexion;
  @property({ attribute: false }) file?: FileAttente;
  @property({ type: Number }) productId: number | null = null;

  @state() produit: { id: number; name: string; base_unit: UniteBase } | null = null;
  @state() lot: { id: number; remaining: number; best_before: string | null } | null = null;
  @state() portion: number | null = null;
  @state() quantite: number | null = null;
  @state() motif: Motif = 'consumption';
  @state() partage = false;
  @state() partsTotal = 2;
  @state() partsMoi = 1;
  @state() erreur: string | null = null;
  @state() enCours = false;
  @state() enAttenteEnvoi = false;

  /** Ce que le pavé affiche tel quel — y compris une virgule qui n'a pas
   *  encore de chiffre après elle. Distinct de `quantite` (la valeur
   *  numérique retenue) pour ne jamais reformater une saisie en cours. */
  @state() private texteQuantite = '';

  connectedCallback(): void {
    super.connectedCallback();
    void this.charger();
  }

  /** Charge le produit, son lot FIFO et sa portion en un aller-retour. */
  private async charger(): Promise<void> {
    if (!this.connexion || this.productId === null) return;
    const reponse = await this.connexion.appeler('home_stock/product/get',
                                                 { product_id: this.productId }) as any;
    this.produit = reponse.produit ?? reponse.product;
    this.lot = reponse.next_batch;
    this.portion = reponse.suggested_portion;
    // Un produit à la pièce a « 1 » déjà armé : un appui suffit, et c'est le
    // cas de 239 des 299 produits du catalogue.
    this.quantite = this.produit?.base_unit === 'piece' && this.lot ? 1 : null;
    this.texteQuantite = this.quantite === null ? '' : String(this.quantite);
  }

  /** Le pavé numérique. La virgule est acceptée comme le point : un incident
   *  réel du lot 1 a montré qu'une virgule suffisait à effacer un champ en
   *  silence, ici elle effacerait un repas. */
  saisirQuantite(saisie: string): void {
    this.texteQuantite = saisie;
    const resultat = analyserNombre(saisie);
    if (!resultat.ok) {
      this.erreur = 'Quantité : ce n’est pas un nombre.';
      this.quantite = null;
      return;
    }
    this.erreur = null;
    this.quantite = resultat.valeur;
  }

  private choisirRaccourci(quantite: number): void {
    this.erreur = null;
    this.quantite = quantite;
    this.texteQuantite = String(quantite);
  }

  private avertirFile(): void {
    this.dispatchEvent(new CustomEvent('file-changee', { bubbles: true, composed: true }));
  }

  /** Ce qui part au serveur. Refuse tout ce que le serveur refuserait, mais
   *  sans aller le lui demander : debout dans une cuisine, un aller-retour
   *  pour apprendre qu'on a tapé trois parts sur deux est un aller-retour de
   *  trop. */
  async enregistrer(): Promise<void> {
    if (this.enCours || !this.file || !this.lot || this.produit === null) return;
    if (this.quantite === null || !(this.quantite > 0)) {
      this.erreur = 'Quantité : donne un nombre supérieur à zéro.';
      return;
    }
    const partage = this.partage && this.motif === 'consumption';
    if (partage && !(this.partsTotal >= 1 && this.partsMoi >= 0
                     && this.partsMoi <= this.partsTotal)) {
      this.erreur = 'On ne mange pas plus de parts qu’il n’en a été servi.';
      return;
    }
    this.erreur = null;
    this.enCours = true;
    this.enAttenteEnvoi = false;
    const charge: Record<string, unknown> = {
      product_id: this.produit.id, batch_id: this.lot.id,
      quantity: this.quantite, reason: this.motif,
    };
    if (partage) {
      charge.parts_total = this.partsTotal;
      charge.parts_mine = this.partsMoi;
    }
    const suivi = this.file.ajouter('home_stock/stock/consume', charge);
    this.avertirFile();
    void this.file.rejouer().then(() => this.avertirFile());
    const sort = await suivi.sort;
    this.enCours = false;
    if (sort === 'envoyee') {
      this.dispatchEvent(new CustomEvent('consommation-enregistree',
                                         { bubbles: true, composed: true }));
    } else {
      // Refusé (le panneau l'affiche en français) ou encore en file (hors
      // ligne) : l'écran reste ouvert, rien n'est perdu.
      this.enAttenteEnvoi = true;
    }
  }

  private rendreMotifs() {
    return html`
      <section class="motifs">
        ${(Object.keys(LIBELLE_MOTIF) as Motif[]).map((m) => html`
          <button type="button" class="motif ${this.motif === m ? 'motif-actif' : ''}"
            @click=${() => { this.motif = m; }}>
            ${LIBELLE_MOTIF[m]}
          </button>
        `)}
      </section>
    `;
  }

  private rendreParts() {
    if (this.motif !== 'consumption') return nothing;
    return html`
      <section class="parts">
        <label class="partage-bascule">
          <input type="checkbox" .checked=${this.partage}
            @change=${(e: Event) => { this.partage = (e.target as HTMLInputElement).checked; }} />
          Je partage
        </label>
        ${this.partage ? html`
          <div class="compteurs">
            <label class="compteur">
              Parts servies
              <input class="parts-total" type="number" inputmode="numeric" min="1" .value=${String(this.partsTotal)}
                @input=${(e: Event) => {
                  const valeur = Number.parseInt((e.target as HTMLInputElement).value, 10);
                  if (Number.isFinite(valeur)) this.partsTotal = valeur;
                }} />
            </label>
            <label class="compteur">
              Les miennes
              <input class="parts-moi" type="number" inputmode="numeric" min="0" .value=${String(this.partsMoi)}
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
    if (!this.produit) return nothing;

    if (!this.lot) {
      return html`
        <section class="entete">
          <h2 class="nom">${this.produit.name}</h2>
        </section>
        <p class="plus-rien">Plus rien en stock.</p>
      `;
    }

    const raccourcis = raccourcisQuantite(this.lot.remaining, this.produit.base_unit, this.portion);

    return html`
      <section class="entete">
        <h2 class="nom">${this.produit.name}</h2>
        <p class="reste">
          Reste ${afficherReste(this.lot.remaining, this.produit.base_unit)} sur le lot visé
          ${this.lot.best_before ? html` — DLC ${this.lot.best_before}` : nothing}
        </p>
      </section>

      <section class="raccourcis">
        ${raccourcis.map((r) => html`
          <button type="button" class="raccourci" @click=${() => this.choisirRaccourci(r.quantite)}>
            ${r.libelle}
          </button>
        `)}
      </section>

      <label class="pave-label">
        Autre quantité
        <input class="pave" inputmode="decimal" .value=${this.texteQuantite}
          @input=${(e: Event) => this.saisirQuantite((e.target as HTMLInputElement).value)} />
      </label>

      ${this.rendreMotifs()}
      ${this.rendreParts()}

      ${this.erreur ? html`<p class="erreur">${this.erreur}</p>` : nothing}
      ${this.enAttenteEnvoi ? html`
        <p class="en-attente">Pas encore envoyé — ça repartira dès que le réseau revient.</p>
      ` : nothing}

      <button type="button" class="enregistrer" ?disabled=${this.enCours} @click=${this.enregistrer}>
        ${LIBELLE_MOTIF[this.motif]}
      </button>
    `;
  }

  static styles = css`
    :host { display: block; padding: 12px; box-sizing: border-box; color: var(--primary-text-color); }
    .nom { margin: 0; font-size: 1.2rem; }
    .reste { margin: 2px 0; color: var(--secondary-text-color); }
    .plus-rien { color: var(--secondary-text-color); }
    .raccourcis { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0; }
    .raccourci {
      min-height: 62px; min-width: 62px; flex: 1 1 auto; font-size: 1rem; border-radius: 8px; border: none;
      background: var(--primary-color); color: var(--text-primary-color, #fff); padding: 4px 8px;
    }
    .pave-label { display: block; margin: 8px 0; }
    .pave { min-height: 48px; font-size: 1rem; padding: 4px 8px; box-sizing: border-box; width: 100%; }
    .motifs { display: flex; gap: 8px; margin: 12px 0; }
    .motif {
      min-height: 62px; flex: 1 1 auto; font-size: 1rem; border-radius: 8px; border: none;
      background: var(--secondary-background-color); color: var(--primary-text-color);
    }
    .motif-actif { background: var(--primary-color); color: var(--text-primary-color, #fff); }
    .parts { margin: 12px 0; padding: 8px; border-radius: 8px; background: var(--secondary-background-color); }
    .partage-bascule { display: flex; align-items: center; gap: 8px; min-height: 48px; }
    .partage-bascule input { width: 22px; height: 22px; }
    .compteurs { display: flex; gap: 12px; margin-top: 8px; }
    .compteur { flex: 1 1 auto; display: block; }
    .parts-total, .parts-moi { min-height: 48px; font-size: 1rem; padding: 4px 8px; box-sizing: border-box; width: 100%; }
    .erreur, .en-attente { color: var(--error-color, #b3261e); font-size: 0.9rem; }
    .enregistrer {
      display: block; width: 100%; min-height: 62px; font-size: 1.2rem; border-radius: 12px;
      border: none; background: var(--primary-color); color: var(--text-primary-color, #fff);
      margin-top: 12px;
    }
    .enregistrer:disabled { opacity: 0.5; }
  `;
}
