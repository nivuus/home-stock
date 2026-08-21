/** L'écran « Équipements » : la liste par emplacement, et la fiche.
 *
 *  Trois règles de présentation, chacune payée par une vraie leçon :
 *
 *  - **Trois états de garantie, trois phrases distinctes** : à venir,
 *    terminée, absente. Jamais une case vide — une case vide se lit « bug ».
 *  - **Une notice introuvable est signalée, pas masquée.** Le lien reste, avec
 *    la mention ; et rien ne devient indisponible pour autant.
 *  - **Aucun bouton de téléversement**, nulle part. Déposer un fichier dans
 *    `media/` est une copie faite une ou deux fois par an, et 0 des 34
 *    équipements Grocy avait une notice alors que la colonne existait.
 */
import { LitElement, html, css, nothing } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import type { Connexion } from '../connexion';
import type { FileAttente } from '../file-attente';

export type Equipement = {
  id: number;
  name: string;
  location_name: string | null;
  brand: string | null;
  model: string | null;
  serial: string | null;
  purchased_on: string | null;
  warranty_months: number | null;
  warranty_ends_on: string | null;
  days_left: number | null;
  manual_url: string | null;
  manual_media_id: string | null;
  note: string | null;
  consumable_count?: number;
  device_id: string | null;
};

export type Consommable = {
  id: number;
  product_id: number;
  role: string;
  label: string | null;
  unit: string | null;
  low_value: number | null;
  keep_value: number | null;
  product_name: string;
  in_stock: number;
};

export type PileRattachee = {
  id: number;
  label: string;
  verb: string;
  last_percent: number | null;
};

export type FicheEquipement = Equipement & {
  consumables: Consommable[];
  batteries: PileRattachee[];
  /** Renseigné par le serveur quand le chemin ne pointe sur aucun fichier.
   *  L'absence du fichier n'est pas une erreur : on le dit, c'est tout. */
  manual_introuvable?: boolean;
};

const SANS_EMPLACEMENT = 'Sans emplacement';

function jour(iso: string): string {
  const [annee, mois, jourDuMois] = iso.split('-');
  return `${jourDuMois}/${mois}/${annee}`;
}

/** Les trois phrases. Jamais de quatrième, jamais de case vide. */
function garantieLisible(equipement: Equipement): string {
  if (!equipement.warranty_ends_on || equipement.days_left === null) {
    return 'garantie non renseignée';
  }
  if (equipement.days_left < 0) {
    return `garantie terminée depuis le ${jour(equipement.warranty_ends_on)}`;
  }
  return `garantie jusqu’au ${jour(equipement.warranty_ends_on)} — ${equipement.days_left} jours`;
}

function stockLisible(consommable: Consommable): string {
  const stock = consommable.in_stock ?? 0;
  if (stock <= 0) return 'aucun en stock';
  return `${Number.isInteger(stock) ? stock : stock.toFixed(1)} en stock`;
}

@customElement('home-stock-equipements')
export class EcranEquipements extends LitElement {
  @property({ attribute: false }) connexion?: Connexion;
  /** Au-delà de 1000 px, la place existe pour une mise en page dense. Posé par
   *  le panneau, qui la MESURE (`window.innerWidth`) et laisse un hôte étroit
   *  la refuser. Faux par défaut : l'écran étroit reste la mise en page de
   *  référence, et c'est la large qui doit se justifier. */
  @property({ type: Boolean }) large = false;
  @property({ attribute: false }) file?: FileAttente;

  @state() private equipements: Equipement[] = [];
  @state() private fiche: FicheEquipement | null = null;
  /** L'action destructive armée : délier demande deux appuis, comme tout ce
   *  qui défait quelque chose. */
  @state() private armee: number | null = null;

  connectedCallback(): void {
    super.connectedCallback();
    void this.charger();
  }

  private async charger(): Promise<void> {
    if (!this.connexion) return;
    const reponse = await this.connexion.appeler<{ equipment: Equipement[] }>(
      'home_stock/equipment/list');
    this.equipements = reponse.equipment;
  }

  private async ouvrir(equipement: Equipement): Promise<void> {
    if (!this.connexion) return;
    this.armee = null;
    const reponse = await this.connexion.appeler<{ equipment: FicheEquipement }>(
      'home_stock/equipment/get', { equipment_id: equipement.id });
    this.fiche = reponse.equipment;
  }

  private async delier(consommable: Consommable): Promise<void> {
    if (this.armee !== consommable.id) {
      this.armee = consommable.id;
      return;
    }
    this.armee = null;
    if (!this.file) return;
    this.file.ajouter('home_stock/equipment/consumable/unlink',
      { consumable_id: consommable.id });
    this.dispatchEvent(new CustomEvent('file-changee', { bubbles: true, composed: true }));
    await this.file.rejouer();
    this.dispatchEvent(new CustomEvent('file-changee', { bubbles: true, composed: true }));
    if (this.fiche) await this.ouvrir(this.fiche);
  }

  /** Les emplacements, dans l'ordre alphabétique, « Sans emplacement » en
   *  dernier : une poêle n'a pas de pièce, et ce n'est pas une anomalie. */
  private groupes(): [string, Equipement[]][] {
    const par = new Map<string, Equipement[]>();
    for (const equipement of this.equipements) {
      const cle = equipement.location_name ?? SANS_EMPLACEMENT;
      par.set(cle, [...(par.get(cle) ?? []), equipement]);
    }
    return [...par.entries()].sort(([a], [b]) => {
      if (a === SANS_EMPLACEMENT) return 1;
      if (b === SANS_EMPLACEMENT) return -1;
      return a.localeCompare(b);
    });
  }

  static styles = css`
    :host { display: block; padding: 12px; color: var(--primary-text-color); box-sizing: border-box; }
    * { box-sizing: border-box; max-width: 100%; }
    /* Un entity_id est long et sans espace (sensor.browser_mod_606bfd06_
       browser_battery) : sans coupure, il pousse la page au-delà des 412 px
       de la dalle du téléphone, et le vérificateur de rendu le refuse — à
       juste titre. Pas de backtick dans ce commentaire : il est DANS un
       littéral de gabarit, et il le terminerait. */
    .libelle, .detail, .verbe, .lien { overflow-wrap: anywhere; }
    h2 { font-size: 1rem; margin: 12px 0 8px; }
    .equipement {
      display: block; width: 100%; min-height: 62px; text-align: left;
      margin-bottom: 8px; padding: 10px 12px; border: none; border-radius: 8px;
      background: var(--secondary-background-color); color: var(--primary-text-color);
      font-size: 0.95rem;
    }
    .libelle { display: block; font-weight: 600; }
    .detail { display: block; font-size: 0.85rem; }
    button.action {
      min-height: 62px; width: 100%; border-radius: 8px; border: none;
      margin-bottom: 8px; font-size: 0.95rem;
      background: var(--primary-color); color: var(--text-primary-color, #fff);
    }
    button.delier { background: var(--secondary-background-color); color: var(--primary-text-color); }
    .lien { word-break: break-all; }
  `;

  private rendreFiche(fiche: FicheEquipement) {
    return html`
      <section class="section">
        <h2>${fiche.name}</h2>
        <span class="detail">${fiche.location_name ?? SANS_EMPLACEMENT}</span>
        ${fiche.brand || fiche.model ? html`
          <span class="detail">${[fiche.brand, fiche.model].filter(Boolean).join(' ')}</span>` : nothing}
        ${fiche.serial ? html`<span class="detail">N° de série : ${fiche.serial}</span>` : nothing}
        ${fiche.purchased_on
          ? html`<span class="detail">Acheté le ${jour(fiche.purchased_on)}</span>`
          : html`<span class="detail">Date d’achat non renseignée</span>`}
        <span class="detail">${garantieLisible(fiche)}</span>
        ${fiche.manual_media_id || fiche.manual_url ? html`
          <span class="detail lien">
            Notice : ${fiche.manual_url ?? fiche.manual_media_id}
            ${fiche.manual_introuvable ? ' — fichier introuvable' : ''}
          </span>` : html`<span class="detail">Notice non renseignée</span>`}

        <h2>Consommables</h2>
        ${fiche.consumables.length === 0
          ? html`<span class="detail">Aucun consommable rattaché.</span>`
          : fiche.consumables.map((consommable) => html`
              <div class="equipement">
                <span class="libelle">${consommable.product_name}</span>
                <span class="detail">
                  ${consommable.label ?? consommable.role} — ${stockLisible(consommable)}
                </span>
                ${consommable.low_value !== null ? html`
                  <span class="detail">
                    Seuils : ${consommable.low_value} / ${consommable.keep_value}
                    ${consommable.unit === 'percent' ? '%' : consommable.unit ?? ''}
                  </span>` : nothing}
              </div>
              <button class="action delier" @click=${() => this.delier(consommable)}>
                ${this.armee === consommable.id
                  ? 'Confirmer : délier ce consommable'
                  : 'Délier ce consommable'}
              </button>
            `)}

        <h2>Piles</h2>
        ${fiche.batteries.length === 0
          ? html`<span class="detail">Aucune pile rattachée.</span>`
          : fiche.batteries.map((pile) => html`
              <span class="detail">
                ${pile.label} — ${pile.verb}${pile.last_percent !== null
                  ? ` — ${Math.trunc(pile.last_percent)} %` : ' — jamais relevée'}
              </span>`)}

        <button class="action" @click=${() => { this.fiche = null; this.armee = null; }}>
          Retour à la liste
        </button>
      </section>
    `;
  }

  render() {
    if (this.fiche) return this.rendreFiche(this.fiche);
    return html`
      ${this.groupes().map(([emplacement, equipements]) => html`
        <section class="section">
          <h2 class="emplacement">${emplacement}</h2>
          ${equipements.map((equipement) => html`
            <button class="equipement" @click=${() => this.ouvrir(equipement)}>
              <span class="libelle">${equipement.name}</span>
              <span class="detail">${garantieLisible(equipement)}</span>
              ${equipement.consumable_count
                ? html`<span class="detail">${equipement.consumable_count} consommable(s)</span>`
                : nothing}
            </button>
          `)}
        </section>
      `)}
    `;
  }
}
