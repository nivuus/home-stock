/** Un bouton. Trois variantes seulement — c'est assez pour tout le panneau, et
 *  chacune porte SA paire fond/texte : jamais un `#fff` en dur sur une couleur
 *  de thème, qui donnerait 2,38:1 sous Graphite (primaire orange). */
import { LitElement, html, css } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { tokens } from './tokens';
import { isDefined, whenDefined } from './ha-available';

const HA_BUTTON = 'ha-button';

@customElement('hs-button')
export class HsButton extends LitElement {
  @property({ type: String }) variant: 'primary' | 'neutral' | 'danger' = 'neutral';
  @property({ type: Boolean, reflect: true }) disabled = false;
  /** Occupe toute la largeur disponible. */
  @property({ type: Boolean }) full = false;

  /** Même raison que dans `hs-card` : `whenDefined` rend un désabonnement, et
   *  ne pas l'appeler fait fuir la table sur l'appareil où `ha-button` ne se
   *  charge jamais. */
  private desabonner?: () => void;

  connectedCallback(): void {
    super.connectedCallback();
    this.desabonner = whenDefined(HA_BUTTON, () => this.requestUpdate());
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    this.desabonner?.();
    this.desabonner = undefined;
  }

  static styles = [tokens, css`
    :host { display: inline-block; }
    :host([disabled]) { pointer-events: none; opacity: 0.5; }
    button {
      display: inline-flex; align-items: center; justify-content: center;
      gap: var(--hs-space-2);
      min-height: var(--hs-touch);
      padding: 0 var(--hs-space-4);
      border-radius: var(--hs-radius-s);
      border: 1px solid transparent;
      font-family: var(--hs-font);
      font-size: 1rem;
      cursor: pointer;
    }
    .full { width: 100%; }
    .neutral { background: var(--hs-surface-2); color: var(--hs-text);
               border-color: var(--hs-divider); }
    .primary { background: var(--hs-accent); color: var(--hs-on-accent); }
    .danger  { background: var(--hs-danger); color: var(--hs-on-danger); }
  `];

  render() {
    const classes = `${this.variant}${this.full ? ' full' : ''}`;
    // `ha-button` n'est utilisé que lorsqu'il est chargé ; sa variante est
    // portée par la classe, comme pour le repli, pour que les deux chemins
    // aient exactement le même contrat de style.
    if (isDefined(HA_BUTTON)) {
      return html`<ha-button class=${classes} ?disabled=${this.disabled}>
        <slot></slot>
      </ha-button>`;
    }
    return html`<button class=${classes} ?disabled=${this.disabled}>
      <slot></slot>
    </button>`;
  }
}
