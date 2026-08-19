import { LitElement, html, css } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { Connexion, type Hass } from './connexion';
import { FileAttente } from './file-attente';

export type Ecran = 'scanner' | 'fiche' | 'panier' | 'rangement' | 'catalogue' | 'reglages';

@customElement('home-stock-panel')
export class PanneauGardeManger extends LitElement {
  @property({ attribute: false }) hass!: Hass;
  @property({ attribute: false }) narrow = false;
  @state() ecran: Ecran = 'scanner';
  @state() enAttente = 0;

  private connexion?: Connexion;
  private file?: FileAttente;
  private desabonner?: () => void;

  connectedCallback(): void {
    super.connectedCallback();
    this.connexion = new Connexion(this.hass);
    this.file = new FileAttente(window.localStorage, (type, charge) =>
      this.connexion!.appeler(type, charge));
    this.enAttente = this.file.taille();
    void this.file.rejouer().then(() => { this.enAttente = this.file!.taille(); });
    void this.connexion.abonner(() => this.requestUpdate());
    window.addEventListener('online', this.auRetourDuReseau);
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    this.desabonner?.();
    window.removeEventListener('online', this.auRetourDuReseau);
  }

  private auRetourDuReseau = (): void => {
    void this.file?.rejouer().then(() => { this.enAttente = this.file!.taille(); });
  };

  static styles = css`
    :host { display: block; height: 100%; background: var(--primary-background-color); }
  `;

  render() {
    return html`<div class="ecran">${this.ecran}</div>`;
  }
}
