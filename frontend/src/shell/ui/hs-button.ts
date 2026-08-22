/** Un bouton. Trois variantes seulement — c'est assez pour tout le panneau, et
 *  chacune porte SA paire fond/texte : jamais un `#fff` en dur sur une couleur
 *  de thème, qui donnerait 2,38:1 sous Graphite (primaire orange).
 *
 *  Contrairement à `hs-card` et `hs-icon`, PAS d'enveloppe autour de `ha-button`
 *  : vérifié dans le bundle HA 2026.8.2 (chunk `52345.8a897507db31c9f9.js`),
 *  `ha-button` peint son fond sur un `.button` interne à SON shadow DOM, piloté
 *  par ses propres attributs `appearance`/`variant` (défaut `variant = "brand"`)
 *  via des variables `--wa-color-*`/`--button-color-*`. Une classe posée sur
 *  l'hôte ne touche jamais ce `.button` interne : la variante serait invisible
 *  dès que HA est chargé — un bouton « danger » sans rien de dangereux à
 *  l'œil, la même panne silencieuse que le `label` muet de `ha-svg-icon`.
 *  Épouser cette API interne nous lierait à un contrat non public, qui a déjà
 *  changé une fois (mwc → Web Awesome). On rend donc TOUJOURS notre `<button>`
 *  ; il tire ses couleurs des mêmes jetons HA, donc il a déjà l'air natif. */
import { LitElement, html, css } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { tokens } from './tokens';

@customElement('hs-button')
export class HsButton extends LitElement {
  @property({ type: String }) variant: 'primary' | 'neutral' | 'danger' = 'neutral';
  @property({ type: Boolean, reflect: true }) disabled = false;
  /** Occupe toute la largeur disponible. */
  @property({ type: Boolean }) full = false;

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
    /* Pas d'aplat : --error-color tombe pile à 4,29:1 des deux côtés (spec
       § 6.1 ter), donc aucune couleur de texte ne passerait 4,5:1 dessus. Le
       danger se dit par une bordure, le texte restant --hs-text. */
    .danger  { background: var(--hs-surface); color: var(--hs-text);
               border-color: var(--hs-danger); border-width: 2px; }
  `];

  render() {
    const classes = `${this.variant}${this.full ? ' full' : ''}`;
    return html`<button class=${classes} ?disabled=${this.disabled}>
      <slot></slot>
    </button>`;
  }
}
