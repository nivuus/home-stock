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
    void this.connexion.abonner(() => this.requestUpdate()).then((desabonner) => {
      // L'élément a pu quitter le DOM pendant que l'abonnement était en vol :
      // disconnectedCallback s'est déjà exécuté et ne sera pas rappelé, donc
      // stocker la fonction ici la laisserait fuiter pour toujours. On s'en
      // sert tout de suite à la place de la garder.
      if (this.isConnected) {
        this.desabonner = desabonner;
      } else {
        desabonner();
      }
    });
    window.addEventListener('online', this.auRetourDuReseau);
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    this.desabonner?.();
    this.desabonner = undefined;
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
