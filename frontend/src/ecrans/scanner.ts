/** L'écran d'accueil du panneau : le geste pour lequel tout le lot existe.
 *
 *  Le bouton de scan est la plus grande chose à l'écran — c'est lui qui
 *  choisit la voie de lecture (`choisirScanner`) : l'appareil photo du
 *  système d'abord, puis `BarcodeDetector`, et sinon la saisie manuelle
 *  s'ouvre d'elle-même, puisqu'il n'y a alors rien d'autre à faire.
 */
import { LitElement, html, css, nothing } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { choisirScanner, type Scanner } from '../scan';
import { libellesChamps } from './fiche';

export type ResumeDerniereFiche = {
  nom: string;
  marque: string | null;
  image: string | null;
  statut: string;
  /** Colonnes qu'Open Food Facts proposait et que la maison a jugées trop
   *  peu fiables pour les enregistrer. La fiche elle-même disparaît de
   *  l'écran dans le même geste qui produit cette liste (retour au
   *  scanner) : c'est ici, sur ce qui reste affiché, qu'elle doit se voir. */
  ignores?: string[];
  /** Rangement seulement : la quantité (en unité de base) et le prix total
   *  que la fiche avait déjà calculés avant que l'écran d'emplacement/DLC
   *  (Task 16) n'existe pour les reprendre — montrés ici pour ne pas les
   *  perdre en route. */
  quantite?: number;
  prixTotal?: number | null;
};

@customElement('home-stock-scanner')
export class EcranScanner extends LitElement {
  /** Injectable pour les tests ; en production, `window`. */
  @property({ attribute: false }) fenetre: any = window;
  @property({ attribute: false }) derniereFiche: ResumeDerniereFiche | null = null;
  @property({ attribute: false }) session: { store: string | null } | null = null;
  /** Nombre d'écritures en attente dans la file hors-ligne. */
  @property({ attribute: false }) enAttente = 0;

  @state() private saisieOuverte = false;
  @state() private codeSaisi = '';
  @state() private enCours = false;
  @state() private erreur: string | null = null;

  private scanner?: Scanner;

  private obtenirScanner(): Scanner {
    if (!this.scanner) this.scanner = choisirScanner(this.fenetre ?? window);
    return this.scanner;
  }

  private async lancerScan(): Promise<void> {
    const scanner = this.obtenirScanner();
    if (scanner.constructor.name === 'ScannerClavier') {
      // Ni appareil photo système, ni BarcodeDetector : la saisie manuelle
      // EST le scan, ici — pas la peine de demander un second appui.
      this.saisieOuverte = true;
      return;
    }
    this.enCours = true;
    this.erreur = null;
    try {
      const code = await scanner.lire();
      if (code) this.emettreCode(code);
    } catch {
      this.erreur = 'La caméra n’a pas pu être utilisée. Essayez la saisie manuelle.';
    } finally {
      this.enCours = false;
    }
  }

  private emettreCode(code: string): void {
    this.saisieOuverte = false;
    this.codeSaisi = '';
    this.dispatchEvent(new CustomEvent('code-lu', { detail: { code }, bubbles: true, composed: true }));
  }

  private validerSaisie(): void {
    const code = this.codeSaisi.trim();
    if (code) this.emettreCode(code);
  }

  render() {
    return html`
      ${this.session ? html`
        <p class="session-banniere">
          Session ouverte${this.session.store ? ` — ${this.session.store}` : ''}
        </p>` : nothing}

      <button class="bouton-scan" ?disabled=${this.enCours} @click=${this.lancerScan}>
        ${this.enCours ? 'Scan en cours…' : 'Scanner un article'}
      </button>

      ${this.erreur ? html`<p class="erreur">${this.erreur}</p>` : nothing}

      ${this.derniereFiche ? html`
        <section class="derniere-fiche">
          ${this.derniereFiche.image ? html`<img src=${this.derniereFiche.image} alt="" />` : nothing}
          <p class="derniere-fiche-nom">
            ${this.derniereFiche.nom}${this.derniereFiche.marque ? ` — ${this.derniereFiche.marque}` : ''}
          </p>
          <p class="derniere-fiche-statut">${this.derniereFiche.statut}</p>
          ${this.derniereFiche.quantite !== undefined ? html`
            <p class="derniere-fiche-quantite">
              Quantité : ${this.derniereFiche.quantite}${this.derniereFiche.prixTotal != null
                ? ` — ${this.derniereFiche.prixTotal.toFixed(2).replace('.', ',')} €` : ''}
            </p>` : nothing}
          ${this.derniereFiche.ignores?.length ? html`
            <p class="derniere-fiche-ignores">
              Ignoré par Open Food Facts : ${libellesChamps(this.derniereFiche.ignores)}
            </p>` : nothing}
        </section>` : nothing}

      ${this.enAttente > 0 ? html`
        <p class="en-attente">${this.enAttente} envoi${this.enAttente > 1 ? 's' : ''} en attente de réseau</p>
      ` : nothing}

      <button class="bouton-saisie" @click=${() => { this.saisieOuverte = !this.saisieOuverte; }}>
        Saisir le code
      </button>

      ${this.saisieOuverte ? html`
        <div class="saisie-manuelle">
          <input class="champ-code" inputmode="numeric" placeholder="Code-barres" .value=${this.codeSaisi}
            @input=${(e: InputEvent) => { this.codeSaisi = (e.target as HTMLInputElement).value; }}
            @keydown=${(e: KeyboardEvent) => { if (e.key === 'Enter') this.validerSaisie(); }} />
          <button class="valider-saisie" @click=${this.validerSaisie}>Valider</button>
        </div>` : nothing}
    `;
  }

  static styles = css`
    :host { display: block; padding: 12px; box-sizing: border-box; color: var(--primary-text-color); }
    .session-banniere {
      background: var(--secondary-background-color); padding: 8px 12px; border-radius: 8px;
      margin: 0 0 12px; text-align: center;
    }
    .bouton-scan {
      display: block; width: 100%; min-height: 96px; font-size: 1.4rem; font-weight: 600;
      border-radius: 16px; border: none; background: var(--primary-color);
      color: var(--text-primary-color, #fff);
    }
    .bouton-scan:disabled { opacity: 0.6; }
    .erreur { color: var(--error-color, #b3261e); }
    .derniere-fiche {
      margin: 16px 0; padding: 8px; border-radius: 8px; background: var(--secondary-background-color);
      display: flex; flex-direction: column; align-items: center; gap: 4px;
    }
    .derniere-fiche img { max-height: 72px; max-width: 100%; border-radius: 6px; }
    .derniere-fiche-ignores, .derniere-fiche-quantite {
      color: var(--secondary-text-color); font-size: 0.85rem; text-align: center;
    }
    .en-attente {
      text-align: center; color: var(--secondary-text-color); font-size: 0.85rem; margin: 8px 0 0;
    }
    .bouton-saisie {
      display: block; width: 100%; min-height: 48px; margin-top: 16px; border-radius: 8px;
      border: 1px solid var(--divider-color, #ccc); background: transparent; color: var(--primary-text-color);
    }
    .saisie-manuelle { display: flex; gap: 8px; margin-top: 8px; }
    .champ-code { flex: 1; min-height: 48px; font-size: 1rem; padding: 4px 8px; box-sizing: border-box; }
    .valider-saisie {
      min-height: 48px; min-width: 62px; border-radius: 8px; border: none;
      background: var(--primary-color); color: var(--text-primary-color, #fff);
    }
  `;
}
