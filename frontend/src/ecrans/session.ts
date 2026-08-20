/** L'écran « Courses » : ouvrir une session, et la clore.
 *
 *  Sans lui, tout le mode magasin était injoignable : `home_stock/session/
 *  start` n'était appelé par rien, un scan en rayon ne proposait que
 *  « Ranger », et le panier répondait « Aucune session de courses ouverte. »
 *  sans le moindre moyen d'en ouvrir une. Les deux capteurs de panier, le
 *  parcours trié par rayon et tout le rangement de session étaient morts.
 *
 *  Le magasin se choisit parmi ceux déjà utilisés — présentés en pastilles,
 *  spec §11 — ou se saisit. La liste vient de `home_stock/stores/list` :
 *  `session/current` porte la même, mais répond `null` quand aucune session
 *  n'existe, c'est-à-dire précisément au moment où il faut en choisir un.
 *
 *  Clore est destructif (les lignes jamais rangées ne le seront plus) : deux
 *  appuis, armement puis confirmation, comme partout ailleurs dans ce
 *  panneau. Sans cette sortie, une session abandonnée bloque le voyage
 *  suivant — l'index partiel de la base refuse une seconde session ouverte.
 */
import { LitElement, html, css, nothing } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import type { Connexion } from '../connexion';
import type { FileAttente } from '../file-attente';
import type { DonneesSession } from './panier';

function formaterEuros(valeur: number): string {
  return `${valeur.toFixed(2).replace('.', ',')} €`;
}

@customElement('home-stock-session')
export class EcranSession extends LitElement {
  /** L'enveloppe de `session/current`, ou `null` quand aucune session
   *  n'existe — c'est ce qui décide de l'écran montré : ouvrir, ou clore. */
  @property({ attribute: false }) donnees: DonneesSession | null = null;
  @property({ attribute: false }) connexion?: Connexion;
  /** La file hors-ligne : ouvrir une session est une écriture comme les
   *  autres, et le parking d'un magasin n'a pas plus de réseau que son
   *  rayon. */
  @property({ attribute: false }) file?: FileAttente;
  @property({ attribute: false }) enAttente = 0;

  @state() private magasins: string[] = [];
  @state() private magasinChoisi: string | null = null;
  @state() private magasinSaisi = '';
  @state() private erreurMagasins: string | null = null;
  /** Vrai après le premier appui sur « Clore la session » : le second, sur
   *  le bouton de confirmation, exécute. Aucun appui long, aucune popup
   *  système — la même règle que la suppression d'une ligne de panier. */
  @state() private clotureArmee = false;
  @state() private enCours = false;
  @state() private message: string | null = null;

  connectedCallback(): void {
    super.connectedCallback();
    void this.chargerMagasins();
  }

  private async chargerMagasins(): Promise<void> {
    this.erreurMagasins = null;
    // Ce que `session/current` a déjà rapporté, s'il y avait une session :
    // évite un écran vide le temps de la réponse.
    if (this.donnees?.stores?.length) this.magasins = this.donnees.stores;
    if (!this.connexion) return;
    try {
      const reponse = await this.connexion.appeler<{ stores: string[] }>('home_stock/stores/list');
      this.magasins = reponse.stores;
    } catch {
      // Hors ligne : on garde les pastilles déjà connues (souvent aucune) et
      // la saisie libre reste ouverte — jamais un écran qui ne permet plus
      // rien parce qu'une lecture accessoire a échoué.
      this.erreurMagasins = 'Impossible de récupérer les magasins connus. Saisissez-en un.';
    }
  }

  /** Empile puis rejoue tout de suite, comme le panier et le rangement.
   *  Rend `true` seulement si CETTE action est bien partie. */
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

  private get magasinRetenu(): string | null {
    const saisi = this.magasinSaisi.trim();
    if (saisi) return saisi;
    return this.magasinChoisi;
  }

  private async ouvrir(): Promise<void> {
    if (this.enCours) return;
    this.enCours = true;
    this.message = null;
    const magasin = this.magasinRetenu;
    const partie = await this.ecrire('home_stock/session/start',
                                     magasin ? { store: magasin } : {});
    this.enCours = false;
    if (partie) {
      this.dispatchEvent(new CustomEvent('session-changee', {
        detail: { action: 'ouverte' }, bubbles: true, composed: true,
      }));
      return;
    }
    // Ni envoyée ni refusée : elle attend le réseau. Le refus, lui, est
    // déjà annoncé en français par la bannière du panneau (`surRefus`).
    this.message = 'Envoi en attente de réseau : la session s’ouvrira à la reconnexion.';
  }

  private async clore(): Promise<void> {
    if (this.enCours) return;
    this.enCours = true;
    this.message = null;
    const partie = await this.ecrire('home_stock/session/close', {});
    this.enCours = false;
    this.clotureArmee = false;
    if (partie) {
      this.dispatchEvent(new CustomEvent('session-changee', {
        detail: { action: 'fermee' }, bubbles: true, composed: true,
      }));
      return;
    }
    this.message = 'Envoi en attente de réseau : la session se clora à la reconnexion.';
  }

  private rendreOuverture() {
    return html`
      <h2 class="titre">Nouvelle session de courses</h2>
      <p class="explication">
        Choisissez le magasin : les scans partiront au panier au lieu d’aller directement au rangement.
      </p>

      ${this.magasins.length ? html`
        <div class="pastilles">
          ${this.magasins.map((magasin) => html`
            <button class="pastille ${this.magasinRetenu === magasin ? 'choisie' : ''}"
              aria-pressed=${this.magasinRetenu === magasin ? 'true' : 'false'}
              @click=${() => { this.magasinChoisi = magasin; this.magasinSaisi = ''; }}>
              ${magasin}
            </button>
          `)}
        </div>` : nothing}

      ${this.erreurMagasins ? html`<p class="erreur">${this.erreurMagasins}</p>` : nothing}

      <label class="magasin-label">
        Autre magasin
        <input class="champ-magasin" placeholder="ex. Leclerc" .value=${this.magasinSaisi}
          @input=${(e: InputEvent) => {
            this.magasinSaisi = (e.target as HTMLInputElement).value;
            this.magasinChoisi = null;
          }} />
      </label>

      <p class="magasin-retenu">
        ${this.magasinRetenu ? `Magasin : ${this.magasinRetenu}` : 'Aucun magasin choisi — la session sera sans enseigne.'}
      </p>

      <button class="ouvrir-session" ?disabled=${this.enCours} @click=${this.ouvrir}>
        ${this.enCours ? 'Ouverture…' : 'Ouvrir la session'}
      </button>
    `;
  }

  private rendreCloture(donnees: DonneesSession) {
    const enCourses = donnees.session.state === 'shopping';
    const restantes = donnees.totals.pending;
    return html`
      <h2 class="titre">${enCourses ? 'Session en cours' : 'Courses à ranger'}</h2>
      <p class="magasin-retenu">${donnees.session.store ?? 'Sans enseigne'}</p>
      <p class="resume">
        ${donnees.totals.lines} ligne${donnees.totals.lines > 1 ? 's' : ''} —
        ${formaterEuros(donnees.totals.total)}
      </p>
      ${restantes > 0 ? html`
        <p class="restantes">
          ${restantes} ligne${restantes > 1 ? 's' : ''} pas encore rangée${restantes > 1 ? 's' : ''}.
          Clore la session les abandonne : rien n’entrera en stock pour elles.
        </p>` : nothing}

      ${this.clotureArmee ? html`
        <div class="confirmation-cloture">
          <button class="confirmer-cloture" ?disabled=${this.enCours} @click=${this.clore}>
            Confirmer la clôture
          </button>
          <button class="annuler-cloture" @click=${() => { this.clotureArmee = false; }}>
            Annuler
          </button>
        </div>
      ` : html`
        <button class="clore-session" @click=${() => { this.clotureArmee = true; }}>
          Clore la session
        </button>
      `}
    `;
  }

  render() {
    return html`
      ${this.enAttente > 0 ? html`
        <p class="en-attente">${this.enAttente} envoi${this.enAttente > 1 ? 's' : ''} en attente de réseau</p>
      ` : nothing}
      ${this.donnees ? this.rendreCloture(this.donnees) : this.rendreOuverture()}
      ${this.message ? html`<p class="message">${this.message}</p>` : nothing}
    `;
  }

  static styles = css`
    :host { display: block; padding: 12px; box-sizing: border-box; color: var(--primary-text-color); }
    .titre { margin: 0 0 8px; font-size: 1.2rem; }
    .explication, .resume, .magasin-retenu { margin: 4px 0; color: var(--secondary-text-color); }
    .en-attente { text-align: center; color: var(--secondary-text-color); font-size: 0.85rem; margin: 0 0 8px; }
    .pastilles { display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0; }
    .pastille {
      min-height: 48px; min-width: 88px; padding: 0 16px; border-radius: 24px; border: none;
      font-size: 1rem; background: var(--secondary-background-color); color: var(--primary-text-color);
    }
    .pastille.choisie { background: var(--primary-color); color: var(--text-primary-color, #fff); }
    .magasin-label { display: block; margin: 8px 0; }
    .champ-magasin {
      min-height: 48px; width: 100%; box-sizing: border-box; font-size: 1rem; padding: 4px 8px;
    }
    .erreur { color: var(--error-color, #b3261e); font-size: 0.9rem; }
    .restantes { color: var(--error-color, #b3261e); font-size: 0.9rem; }
    .message { color: var(--secondary-text-color); font-size: 0.9rem; }
    .ouvrir-session {
      display: block; width: 100%; min-height: 62px; font-size: 1.2rem; border-radius: 12px;
      border: none; background: var(--primary-color); color: var(--text-primary-color, #fff);
      margin-top: 16px;
    }
    .ouvrir-session:disabled { opacity: 0.5; }
    .clore-session, .confirmer-cloture, .annuler-cloture {
      display: block; width: 100%; min-height: 62px; font-size: 1.1rem; border-radius: 12px;
      border: none; margin-top: 12px;
    }
    .clore-session, .confirmer-cloture {
      background: var(--error-color, #b3261e); color: #fff;
    }
    .annuler-cloture {
      background: var(--secondary-background-color); color: var(--primary-text-color);
    }
    .confirmation-cloture { display: block; }
  `;
}
