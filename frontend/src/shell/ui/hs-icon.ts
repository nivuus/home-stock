/** Une icône, rendue par `ha-svg-icon` quand Home Assistant l'a chargé et par
 *  notre propre `<svg>` sinon. Le tracé vient de `icons.ts` DANS LES DEUX
 *  CAS : voir le commentaire de tête de ce fichier. */
import { LitElement, html, css, nothing, svg } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { tokens } from './tokens';
import { ICON_PATHS, type IconName } from './icons';
import { isDefined, whenDefined } from './ha-available';

const HA_SVG_ICON = 'ha-svg-icon';

@customElement('hs-icon')
export class HsIcon extends LitElement {
  @property({ type: String }) name: IconName = 'home';
  /** Absent ⇒ l'icône est décorative et masquée aux lecteurs d'écran. Une
   *  icône seule dans un bouton DOIT en porter un. */
  @property({ type: String }) label: string | null = null;

  connectedCallback(): void {
    super.connectedCallback();
    whenDefined(HA_SVG_ICON, () => this.requestUpdate());
  }

  static styles = [tokens, css`
    :host { display: inline-flex; width: 24px; height: 24px; }
    svg, ha-svg-icon { width: 100%; height: 100%; fill: currentColor; }
  `];

  render() {
    const path = ICON_PATHS[this.name];
    if (isDefined(HA_SVG_ICON)) {
      return html`<ha-svg-icon .path=${path} .label=${this.label ?? undefined}></ha-svg-icon>`;
    }
    return html`
      <svg viewBox="0 0 24 24"
           role=${this.label ? 'img' : nothing}
           aria-hidden=${this.label ? nothing : 'true'}>
        ${this.label ? svg`<title>${this.label}</title>` : nothing}
        <path d=${path}></path>
      </svg>`;
  }
}
