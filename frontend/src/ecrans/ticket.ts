/** L'écran « Ticket » : de la photo aux prix appliqués.
 *
 *  Deux fils PARALLÈLES partent de la caisse : ranger les sacs, et lire le
 *  ticket. Aucun des deux n'attend l'autre — on vide les sacs pendant que le
 *  modèle lit, et on lit le lendemain matin si le réseau du parking était
 *  mauvais. Cet écran ne bloque donc jamais rien.
 *
 *  On n'y entre pas par un bouton nu : depuis la session, ou depuis un
 *  bandeau de ticket en attente — comme `recette` et `validation` au lot 3.
 *
 *  Appliquer demande DEUX appuis, parce que ça peut écrire des
 *  contrepassations dans un journal en ajout seul ; rapprocher une ligne
 *  n'en demande qu'un, parce que ça se refait.
 */
import { LitElement, html, css, nothing } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import type { Connexion } from '../connexion';
import type { FileAttente } from '../file-attente';

export type CandidatLigne = { line_id: number; label: string; score: number };

export type LigneTicket = {
  id: number;
  receipt_id: number;
  position: number;
  label: string;
  quantity: number | null;
  unit_price: number | null;
  total_price: number | null;
  line_id: number | null;
  article_id: number | null;
  match_state: 'unmatched' | 'auto' | 'confirmed' | 'ignored';
  applied_at: string | null;
  candidates: CandidatLigne[];
};

export type LigneChariot = {
  id: number;
  article_label: string | null;
  product_name: string;
  quantity: number;
  unit_price: number | null;
  base_unit: string;
  brand: string | null;
  stored_at?: string | null;
  /** Combien de mouvements ce lot porte déjà : ce que l'application devra
   *  contrepasser. Rendu par le serveur, jamais deviné ici. */
  movements?: number;
};

export type DonneesTicket = {
  id: number;
  session_id: number | null;
  media_content_id: string;
  captured_at: string;
  state: 'pending' | 'read' | 'failed' | 'applied' | 'discarded';
  store_id: number | null;
  purchased_on: string | null;
  total: number | null;
  agent_entity_id: string | null;
  read_at: string | null;
  attempts: number;
  error: string | null;
  raw: string | null;
  lines: LigneTicket[];
  cart_lines: LigneChariot[];
  lines_total: number;
  total_gap: number | null;
};

const ETATS: Record<DonneesTicket['state'], string> = {
  pending: 'Lecture en cours…',
  read: 'Ticket lu',
  failed: 'Lecture impossible',
  applied: 'Prix appliqués',
  discarded: 'Ticket abandonné',
};

function formaterEuros(valeur: number): string {
  return `${valeur.toFixed(2).replace('.', ',')} €`;
}

/** Traduit un refus du téléversement de Home Assistant. Les deux cas qui
 *  arrivent réellement : le compte n'est pas administrateur (403), et le
 *  fichier dépasse ce que la vue accepte (413). Un rond qui tourne sans rien
 *  dire est pire que les deux. */
export function messageTeleversement(erreur: unknown): string {
  const texte = String((erreur as Error)?.message ?? erreur);
  if (texte.includes('403') || texte.includes('401')) {
    return 'Le téléversement demande un compte administrateur : '
      + 'connectez-vous avec celui du foyer.';
  }
  if (texte.includes('413')) {
    return 'Photo refusée : elle dépasse 20 Mo. Reprenez-la en moins grand.';
  }
  if (texte.includes('415') || texte.toLowerCase().includes('image')) {
    return 'Photo refusée : seules les images sont acceptées.';
  }
  return `Le téléversement a échoué (${texte}).`;
}

/** Jamais sous `www/` : tout ce qui y vit est servi sur `/local/` SANS
 *  authentification, et un ticket porte un magasin, une heure et des
 *  habitudes. */
export const DOSSIER_TICKETS = 'media-source://media_source/local/home_stock/receipts';

@customElement('home-stock-ticket')
export class EcranTicket extends LitElement {
  @property({ attribute: false }) ticket: DonneesTicket | null = null;
  @property({ attribute: false }) connexion?: Connexion;
  /** Au-delà de 1000 px, la place existe pour une mise en page dense. Posé par
   *  le panneau, qui la MESURE (`window.innerWidth`) et laisse un hôte étroit
   *  la refuser. Faux par défaut : l'écran étroit reste la mise en page de
   *  référence, et c'est la large qui doit se justifier. */
  @property({ type: Boolean }) large = false;
  @property({ attribute: false }) file?: FileAttente;
  @property({ attribute: false }) enAttente = 0;
  /** Faux quand aucune entité `ai_task` n'est réglée : on n'affiche alors
   *  pas de bouton mort, on dit pourquoi. Un réglage, pas une panne. */
  @property({ attribute: false }) agentConfigure = true;
  /** Le téléversement, injecté : la vue de Home Assistant est du HTTP, pas
   *  du websocket, et un test n'a aucune raison d'ouvrir une socket. */
  @property({ attribute: false }) televerser?: (fichier: File) => Promise<string>;

  @state() private erreur: string | null = null;
  @state() private applicationArmee = false;

  private ecrire(type: string, charge: Record<string, unknown>): void {
    if (!this.file) return;
    this.file.ajouter(type, charge);
    this.avertirFile();
    void this.file.rejouer().then(() => this.avertirFile());
  }

  private avertirFile(): void {
    this.dispatchEvent(new CustomEvent('file-changee', { bubbles: true, composed: true }));
  }

  private async surPhoto(evenement: Event): Promise<void> {
    const champ = evenement.target as HTMLInputElement;
    const fichier = champ.files?.[0];
    const envoyer = this.televerser
      ?? ((f: File) => this.connexion!.televerserMedia(f, DOSSIER_TICKETS));
    if (!fichier || (!this.televerser && !this.connexion)) return;
    this.erreur = null;
    let identifiant: string;
    try {
      identifiant = await envoyer(fichier);
    } catch (erreur) {
      // La photo n'est PAS perdue : elle est encore sur le téléphone, et le
      // message dit quoi faire. Une file d'attente ne sert à rien ici — c'est
      // le téléversement lui-même qui a été refusé, pas le réseau.
      this.erreur = messageTeleversement(erreur);
      return;
    }
    this.ecrire('home_stock/receipt/submit', { media_content_id: identifiant });
  }

  private rapprocher(ligne: LigneTicket, lineId: number): void {
    this.ecrire('home_stock/receipt/line/match',
      { line_id: ligne.id, shopping_line_id: lineId, state: 'confirmed' });
  }

  private ignorer(ligne: LigneTicket): void {
    this.ecrire('home_stock/receipt/line/match',
      { line_id: ligne.id, shopping_line_id: null, state: 'ignored' });
  }

  private reessayer(): void {
    if (!this.ticket) return;
    this.ecrire('home_stock/receipt/retry', { receipt_id: this.ticket.id });
  }

  private appliquer(): void {
    if (!this.ticket) return;
    this.ecrire('home_stock/receipt/apply', { receipt_id: this.ticket.id });
    this.applicationArmee = false;
  }

  /** Combien de mouvements déjà écrits l'application corrigera. Compté sur
   *  les lignes de panier RANGÉES que le ticket vise — le seul cas où
   *  appliquer touche au journal. */
  private mouvementsACorriger(): number {
    const ticket = this.ticket;
    if (!ticket) return 0;
    const visees = new Set(ticket.lines
      .filter((l) => l.line_id !== null && l.match_state !== 'ignored')
      .map((l) => l.line_id));
    return ticket.cart_lines
      .filter((l) => visees.has(l.id))
      .reduce((total, l) => total + (l.movements ?? 0), 0);
  }

  private chariotPour(ligne: LigneTicket): LigneChariot | null {
    if (ligne.line_id === null) return null;
    return this.ticket?.cart_lines.find((l) => l.id === ligne.line_id) ?? null;
  }

  private rendreLigne(ligne: LigneTicket) {
    const chariot = this.chariotPour(ligne);
    const candidat = ligne.candidates[0] ?? null;
    return html`
      <article class="ligne-ticket">
        <div class="cote-ticket">
          <p class="libelle">${ligne.label}</p>
          <p class="prix">${ligne.total_price === null ? '—' : formaterEuros(ligne.total_price)}</p>
        </div>
        <div class="cote-chariot">
          ${chariot ? html`
            <p class="rapproche">${chariot.article_label ?? chariot.product_name}</p>
          ` : html`
            <p class="orphelin">Aucune ligne de panier — Scanner l’article pour la rattacher</p>
          `}
          ${ligne.match_state === 'ignored' ? html`<p class="ignoree">Ignorée</p>` : nothing}
        </div>
        <div class="actions-ligne">
          ${candidat ? html`
            <button class="rapprocher" @click=${() => this.rapprocher(ligne, candidat.line_id)}>
              ${candidat.label}
            </button>
          ` : nothing}
          <button class="ignorer" @click=${() => this.ignorer(ligne)}>Ignorer</button>
        </div>
      </article>
    `;
  }

  render() {
    if (!this.agentConfigure) {
      return html`
        <p class="vide">
          Aucune entité de lecture n’est configurée : choisissez-en une dans les
          réglages du garde-manger pour photographier vos tickets.
        </p>`;
    }
    const ticket = this.ticket;
    return html`
      ${this.enAttente > 0 ? html`
        <p class="en-attente">
          ${this.enAttente} envoi${this.enAttente > 1 ? 's' : ''} en attente de réseau
        </p>
      ` : nothing}

      ${ticket === null ? html`
        <section class="bloc-principal">
          <label class="prendre-photo">
            Photographier le ticket
            <input class="photo" type="file" accept="image/*" capture="environment"
              @change=${this.surPhoto} />
          </label>
        </section>
      ` : this.rendreTicket(ticket)}

      ${this.erreur ? html`<p class="erreur">${this.erreur}</p>` : nothing}
    `;
  }

  private rendreTicket(ticket: DonneesTicket) {
    const mouvements = this.mouvementsACorriger();
    return html`
      <section class="entete">
        <p class="etat">${ETATS[ticket.state]}</p>
        ${ticket.total !== null ? html`
          <p class="total">${formaterEuros(ticket.total)}</p>
        ` : nothing}
      </section>

      ${ticket.error ? html`<p class="erreur">${ticket.error}</p>` : nothing}

      ${ticket.total_gap !== null ? html`
        <p class="ecart">
          ${`La somme des lignes s’écarte du total de ${formaterEuros(Math.abs(ticket.total_gap))}.`}
        </p>
      ` : nothing}

      ${ticket.state === 'failed' ? html`
        <button class="reessayer" @click=${this.reessayer}>Réessayer la lecture</button>
      ` : nothing}

      <section class="bloc-principal">
        ${ticket.lines.map((ligne) => this.rendreLigne(ligne))}
      </section>

      ${this.applicationArmee ? html`
        <div class="confirmation">
          <p class="avertissement">${
            mouvements === 0
              ? 'Aucun mouvement déjà écrit ne sera corrigé.'
              : `${mouvements} mouvement${mouvements > 1 ? 's' : ''} déjà écrit${
                  mouvements > 1 ? 's' : ''} seront corrigés.`
          }</p>
          <button class="confirmer-application" @click=${this.appliquer}>Confirmer</button>
          <button class="annuler-application"
            @click=${() => { this.applicationArmee = false; }}>Annuler</button>
        </div>
      ` : html`
        <button class="appliquer" ?disabled=${ticket.state !== 'read'}
          @click=${() => { this.applicationArmee = true; }}>
          Appliquer les prix
        </button>
      `}
    `;
  }

  static styles = css`
    :host { display: block; padding: 12px; box-sizing: border-box; color: var(--primary-text-color); }
    .vide { color: var(--secondary-text-color); text-align: center; }
    .en-attente { text-align: center; color: var(--secondary-text-color); font-size: 0.85rem; margin: 4px 0 8px; }
    .entete { display: flex; justify-content: space-between; align-items: baseline; }
    .etat { font-weight: 600; margin: 0; }
    .total { font-size: 1.3rem; font-weight: 700; margin: 0; }
    .erreur {
      margin: 8px 0; padding: 8px 12px; border-radius: 8px;
      background: var(--error-color, #b3261e); color: #fff; font-size: 0.9rem;
    }
    .ecart { color: var(--warning-color, #8a5300); font-size: 0.9rem; margin: 8px 0; }
    .prendre-photo {
      display: block; min-height: 62px; padding: 16px; border-radius: 12px; text-align: center;
      background: var(--primary-color); color: var(--text-primary-color, #fff);
    }
    .photo { display: block; margin: 8px auto 0; color: inherit; }
    .ligne-ticket {
      display: flex; flex-wrap: wrap; gap: 8px; padding: 8px 0;
      border-bottom: 1px solid var(--divider-color, #ddd);
    }
    .cote-ticket { flex: 1 1 40%; min-width: 0; }
    .cote-chariot { flex: 1 1 40%; min-width: 0; }
    .libelle { margin: 0; font-family: monospace; }
    .prix { margin: 2px 0 0; font-size: 0.9rem; color: var(--secondary-text-color); }
    .rapproche { margin: 0; }
    .orphelin, .ignoree { margin: 0; font-size: 0.85rem; color: var(--secondary-text-color); }
    .actions-ligne { display: flex; gap: 8px; flex-basis: 100%; }
    .rapprocher, .ignorer, .reessayer {
      min-height: 48px; min-width: 88px; border-radius: 8px; border: none; font-size: 0.9rem;
      background: var(--secondary-background-color); color: var(--primary-text-color);
    }
    .appliquer, .confirmer-application, .annuler-application {
      display: block; width: 100%; min-height: 62px; font-size: 1.1rem; border-radius: 12px;
      border: none; margin-top: 12px;
    }
    .appliquer, .confirmer-application {
      background: var(--primary-color); color: var(--text-primary-color, #fff);
    }
    .appliquer:disabled { opacity: 0.5; }
    .annuler-application {
      background: var(--secondary-background-color); color: var(--primary-text-color);
    }
    .avertissement { margin: 12px 0 0; font-size: 0.9rem; }
  `;
}
