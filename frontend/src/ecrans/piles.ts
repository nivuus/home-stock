/** L'écran « Piles » : ce qui est suivi, ce qui reste à déclarer, et le geste
 *  « je viens de la changer ».
 *
 *  Trois règles gouvernent tout ce fichier :
 *
 *  - **Rien ne s'écrit à l'ouverture.** `batteries/discover` ne crée aucune
 *    ligne : le seul fait d'ouvrir cet écran ne doit pas peupler la base de
 *    vingt-huit piles. C'est le bouton qui déclare.
 *  - **Toute écriture passe par la file hors-ligne**, jamais par
 *    `connexion.appeler` : une pile changée dans un couloir sans Wi-Fi ne
 *    doit pas être perdue.
 *  - **Aucune couleur ne porte seule l'information.** Un niveau bas se lit au
 *    chiffre et au mot ; la teinte ne fait que redire ce que le texte dit
 *    déjà, parce que le vérificateur de rendu mesure le contraste, jamais la
 *    sémantique.
 */
import { LitElement, html, css, nothing } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import type { Connexion } from '../connexion';
import type { FileAttente } from '../file-attente';

export type Pile = {
  id: number;
  label: string;
  kind: 'primary' | 'rechargeable_cell' | 'built_in';
  verb: string;
  tracked: boolean | null;
  exclusion_reason: string | null;
  entity_id: string | null;
  state: string | null;
  orphaned: boolean;
  device_name: string | null;
  model: string | null;
  equipment_id: number | null;
  cell_count: number;
  low_percent: number;
  keep_percent: number;
  last_percent: number | null;
  last_reading_at: string | null;
  installed_on: string | null;
  note: string | null;
  spare_label: string | null;
  spare_in_stock: number | null;
};

export type PileADeclarer = {
  entity_registry_id: string;
  entity_id: string;
  device_id: string | null;
  device_name: string | null;
  model: string | null;
  state: string | null;
};

export type EvenementPile = {
  id: number;
  occurred_at: string;
  kind: string;
  movement_id: number | null;
  note: string | null;
};

const LIBELLE_EVENEMENT: Record<string, string> = {
  install: 'posée',
  charge: 'rechargée',
  replacement: 'changée',
  removal: 'retirée',
};

function jour(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  const deux = (n: number) => String(n).padStart(2, '0');
  return `${deux(date.getDate())}/${deux(date.getMonth() + 1)}/${date.getFullYear()}`;
}

/** Ce que la ligne dit du niveau. Jamais « 0 % » pour « on ne sait pas » :
 *  les deux phrases ne veulent pas dire la même chose, et c'est la seconde
 *  qui est vraie quand on n'a rien relevé. */
function niveauLisible(pile: Pile): string {
  if (pile.orphaned) return 'entité introuvable';
  if (pile.last_percent === null) return 'jamais relevée';
  if (pile.state === 'unavailable' || pile.state === 'unknown') {
    return `${Math.trunc(pile.last_percent)} % — muette depuis le dernier relevé`;
  }
  return `${Math.trunc(pile.last_percent)} %`;
}

function rechangeLisible(pile: Pile): string | null {
  if (!pile.spare_label) return null;
  const feminin = pile.kind !== 'built_in';
  const stock = pile.spare_in_stock ?? 0;
  const reste = stock > 0
    ? `${Number.isInteger(stock) ? stock : stock.toFixed(1)} en stock`
    : `${feminin ? 'aucune' : 'aucun'} en stock`;
  return `${pile.cell_count}× ${pile.spare_label}, ${reste}`;
}

@customElement('home-stock-piles')
export class EcranPiles extends LitElement {
  @property({ attribute: false }) connexion?: Connexion;
  /** Au-delà de 1000 px, la place existe pour une mise en page dense. Posé par
   *  le panneau, qui la MESURE (`window.innerWidth`) et laisse un hôte étroit
   *  la refuser. Faux par défaut : l'écran étroit reste la mise en page de
   *  référence, et c'est la large qui doit se justifier. */
  @property({ type: Boolean }) large = false;
  @property({ attribute: false }) file?: FileAttente;

  @state() private piles: Pile[] = [];
  @state() private aDeclarer: PileADeclarer[] = [];
  @state() private selection: number | null = null;
  @state() private evenements: EvenementPile[] = [];
  /** L'action destructive armée, en attente de sa confirmation. Deux appuis,
   *  jamais un appui long : c'est la contrainte du foyer. */
  @state() private armee: string | null = null;
  @state() private refus: string | null = null;
  @state() private ignoree: PileADeclarer | null = null;
  @state() private motif = '';
  @state() private erreurMotif: string | null = null;

  connectedCallback(): void {
    super.connectedCallback();
    void this.charger();
  }

  private async charger(): Promise<void> {
    if (!this.connexion) return;
    const [suivies, decouvertes] = await Promise.all([
      this.connexion.appeler<{ batteries: Pile[] }>('home_stock/batteries/list'),
      this.connexion.appeler<{ sensors: PileADeclarer[] }>('home_stock/batteries/discover'),
    ]);
    this.piles = [...suivies.batteries].sort((a, b) => {
      const na = a.last_percent ?? Number.POSITIVE_INFINITY;
      const nb = b.last_percent ?? Number.POSITIVE_INFINITY;
      return na - nb || a.label.localeCompare(b.label);
    });
    this.aDeclarer = decouvertes.sensors;
  }

  /** Toute écriture passe par ici, donc par la file. Rend la réponse du
   *  serveur quand il y en a une — `spare_refused` en est la seule
   *  aujourd'hui, et la perdre laisserait croire qu'il reste une CR2032. */
  private async ecrire(type: string, charge: Record<string, unknown>): Promise<unknown> {
    if (!this.file) return undefined;
    const suivi = this.file.ajouter(type, charge);
    this.dispatchEvent(new CustomEvent('file-changee', { bubbles: true, composed: true }));
    void this.file.rejouer().then(() => {
      this.dispatchEvent(new CustomEvent('file-changee', { bubbles: true, composed: true }));
    });
    return suivi.reponse;
  }

  private async ouvrir(pile: Pile): Promise<void> {
    this.selection = pile.id;
    this.armee = null;
    this.refus = null;
    this.evenements = [];
    if (!this.connexion) return;
    const reponse = await this.connexion.appeler<{ events: EvenementPile[] }>(
      'home_stock/battery/events', { battery_id: pile.id });
    this.evenements = reponse.events;
  }

  /** Le geste destructif : il écrit un mouvement et décrémente le placard.
   *  Armement puis confirmation — le premier appui n'écrit rien. */
  private async surEvenement(pile: Pile): Promise<void> {
    const kind = pile.kind === 'built_in' || pile.kind === 'rechargeable_cell'
      ? 'charge' : 'replacement';
    const cle = `${pile.id}:${kind}`;
    if (this.armee !== cle) {
      this.armee = cle;
      return;
    }
    this.armee = null;
    const reponse = await this.ecrire('home_stock/battery/event',
      { battery_id: pile.id, kind }) as { spare_refused?: string } | undefined;
    this.refus = reponse?.spare_refused ?? null;
    await this.charger();
  }

  private async suivre(capteur: PileADeclarer): Promise<void> {
    await this.ecrire('home_stock/battery/declare', {
      label: capteur.device_name || capteur.entity_id,
      kind: 'primary',
      entity_registry_id: capteur.entity_registry_id,
      device_id: capteur.device_id,
      tracked: true,
    });
    await this.charger();
  }

  private async confirmerIgnorer(): Promise<void> {
    const capteur = this.ignoree;
    if (!capteur) return;
    // La colonne exige un motif, donc le panneau en demande un, donc le
    // serveur refuse sans : les trois disent la même chose.
    if (!this.motif.trim()) {
      this.erreurMotif = 'Un motif est nécessaire pour ignorer une pile.';
      return;
    }
    this.erreurMotif = null;
    await this.ecrire('home_stock/battery/declare', {
      label: capteur.device_name || capteur.entity_id,
      kind: 'primary',
      entity_registry_id: capteur.entity_registry_id,
      device_id: capteur.device_id,
      tracked: false,
      exclusion_reason: this.motif.trim(),
    });
    this.ignoree = null;
    this.motif = '';
    await this.charger();
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
    .pile, .capteur {
      display: block; width: 100%; min-height: 62px; text-align: left;
      margin-bottom: 8px; padding: 10px 12px; border: none; border-radius: 8px;
      background: var(--secondary-background-color); color: var(--primary-text-color);
      font-size: 0.95rem;
    }
    .libelle { display: block; font-weight: 600; }
    .detail { display: block; font-size: 0.85rem; }
    .verbe { display: block; font-size: 0.85rem; }
    button.action {
      min-height: 62px; width: 100%; border-radius: 8px; border: none;
      margin-bottom: 8px; font-size: 0.95rem;
      background: var(--primary-color); color: var(--text-primary-color, #fff);
    }
    button.ignorer { background: var(--secondary-background-color); color: var(--primary-text-color); }
    .motif { width: 100%; min-height: 62px; font-size: 1rem; box-sizing: border-box; }
    .refus, .erreur { margin: 8px 0; font-size: 0.9rem; }
    .evenement-passe { display: block; font-size: 0.85rem; margin-bottom: 4px; }

    /* --- la vue dense (lot 6), au-delà de 1000 px -------------------------
       Les classes de libellé, de détail et de verbe sont des blocs en étroit ;
       dans une cellule de tableau elles redeviennent du contenu de cellule,
       sans quoi chaque colonne se casse en hauteur. Pas de backtick dans ce
       commentaire : il est DANS un littéral de gabarit. */
    .tableau { width: 100%; border-collapse: collapse; table-layout: fixed; }
    .tableau th, .tableau td {
      text-align: left; padding: 4px 8px; border-bottom: 1px solid var(--divider-color, #ddd);
      overflow-wrap: anywhere; font-size: 0.9rem;
    }
    .tableau th { font-size: 0.85rem; color: var(--secondary-text-color); font-weight: 600; }
    .tableau .ligne { height: 62px; }
    /* Le bouton d'ouverture garde la classe de la carte étroite : c'est le
       MÊME geste, et un seul sélecteur le désigne dans les deux mises en page
       — y compris pour le vérificateur de rendu, qui n'a pas à connaître deux
       noms pour une seule action. */
    .tableau .ouvrir {
      display: block; width: 100%; min-height: 48px; text-align: left; border: none;
      border-radius: 8px; padding: 8px; margin-bottom: 0; font-size: 0.95rem;
      font-weight: 600;
      background: var(--secondary-background-color); color: var(--primary-text-color);
    }
  `;

  private rendreADeclarer() {
    if (this.aDeclarer.length === 0) return nothing;
    return html`
      <section class="section">
        <h2>${this.aDeclarer.length} pile(s) à déclarer</h2>
        ${this.aDeclarer.map((capteur) => html`
          <div class="capteur">
            <span class="libelle">${capteur.device_name ?? capteur.entity_id}</span>
            <span class="detail">${capteur.entity_id}${capteur.model ? ` — ${capteur.model}` : ''}</span>
            <span class="detail">${capteur.state !== null ? `${capteur.state} %` : 'sans relevé'}</span>
          </div>
          <button class="action suivre" @click=${() => this.suivre(capteur)}>Suivre</button>
          <button class="action ignorer" @click=${() => {
            this.ignoree = capteur; this.erreurMotif = null;
          }}>Ignorer</button>
        `)}
        ${this.ignoree ? html`
          <label class="detail" for="motif">Motif — pourquoi cette pile n’est pas suivie</label>
          <input id="motif" class="motif" .value=${this.motif}
            @input=${(e: Event) => { this.motif = (e.target as HTMLInputElement).value; }}>
          ${this.erreurMotif ? html`<p class="erreur">${this.erreurMotif}</p>` : nothing}
          <button class="action confirmer-ignorer" @click=${() => this.confirmerIgnorer()}>
            Confirmer et ignorer
          </button>
        ` : nothing}
      </section>
    `;
  }

  private rendreFiche(pile: Pile) {
    const kind = pile.kind === 'built_in' || pile.kind === 'rechargeable_cell'
      ? 'charge' : 'replacement';
    const arme = this.armee === `${pile.id}:${kind}`;
    const verbe = kind === 'charge' ? 'de la recharger' : 'de la changer';
    return html`
      <section class="section">
        <h2>${pile.label}</h2>
        <span class="detail">${pile.verb} — ${niveauLisible(pile)}</span>
        ${rechangeLisible(pile) ? html`<span class="detail">${rechangeLisible(pile)}</span>` : nothing}
        <span class="detail">Seuils : ${pile.low_percent} % / ${pile.keep_percent} %</span>
        ${pile.entity_id ? html`<span class="detail">${pile.entity_id}</span>` : nothing}
        <button class="action evenement" @click=${() => this.surEvenement(pile)}>
          ${arme ? `Confirmer : je viens ${verbe}` : `Je viens ${verbe}`}
        </button>
        ${this.refus ? html`<p class="refus">${this.refus}</p>` : nothing}
        <h2>Historique</h2>
        ${this.evenements.length === 0
          ? html`<span class="detail">Aucun événement enregistré.</span>`
          : this.evenements.map((evenement) => html`
              <span class="evenement-passe">
                ${jour(evenement.occurred_at)} — ${LIBELLE_EVENEMENT[evenement.kind] ?? evenement.kind}
              </span>`)}
        <button class="action" @click=${() => { this.selection = null; this.refus = null; }}>
          Retour à la liste
        </button>
      </section>
    `;
  }

  /** Le tableau de la vue dense. Quatorze piles empilées en cartes tiennent
   *  sur deux écrans ; en lignes, elles se comparent d'un coup d'œil — et
   *  c'est justement ce qu'on veut d'un inventaire de piles. Les mêmes
   *  phrases qu'en étroit : une pile muette ou orpheline le dit encore. */
  private rendreTableau() {
    return html`
      ${this.rendreADeclarer()}
      <section class="section">
        <h2>${this.piles.length} pile(s) suivie(s)</h2>
        <table class="tableau">
          <thead>
            <tr><th>Pile</th><th>À faire</th><th>Niveau</th><th>Rechange</th></tr>
          </thead>
          <tbody>
            ${this.piles.map((pile) => html`
              <tr class="ligne">
                <td class="libelle">
                  <button class="pile ouvrir" @click=${() => this.ouvrir(pile)}>${pile.label}</button>
                </td>
                <td class="verbe">${pile.verb}</td>
                <td class="detail">${niveauLisible(pile)}</td>
                <td class="detail">${rechangeLisible(pile) ?? '—'}</td>
              </tr>
            `)}
          </tbody>
        </table>
      </section>
    `;
  }

  render() {
    const choisie = this.piles.find((pile) => pile.id === this.selection) ?? null;
    if (choisie) return this.rendreFiche(choisie);
    if (this.large) return this.rendreTableau();
    return html`
      ${this.rendreADeclarer()}
      <section class="section">
        <h2>${this.piles.length} pile(s) suivie(s)</h2>
        ${this.piles.map((pile) => html`
          <button class="pile" @click=${() => this.ouvrir(pile)}>
            <span class="libelle">${pile.label}</span>
            <span class="verbe">${pile.verb}</span>
            <span class="detail">${niveauLisible(pile)}</span>
            ${rechangeLisible(pile) ? html`<span class="detail">${rechangeLisible(pile)}</span>` : nothing}
          </button>
        `)}
      </section>
    `;
  }
}
