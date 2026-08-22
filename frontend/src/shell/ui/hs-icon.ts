/** Une icône, rendue par `ha-svg-icon` quand Home Assistant l'a chargé et par
 *  notre propre `<svg>` sinon. Le tracé vient de `icons.ts` DANS LES DEUX
 *  CAS : voir le commentaire de tête de ce fichier.
 *
 *  `ha-svg-icon` ne déclare que `path`, `secondaryPath` et `viewBox`
 *  (vérifié dans le bundle HA 2026.8.2, chunk `10077.c8e1d4226b02fb78.js`) —
 *  pas de `label` — et son propre svg interne écrit
 *  `aria-hidden="true"` en dur. Le nom accessible ne peut donc jamais venir
 *  de l'intérieur d'une des deux branches : il est porté par l'HÔTE
 *  (`<hs-icon>` elle-même), le seul point que l'arbre d'accessibilité voit
 *  quelle que soit la branche rendue. */
import { LitElement, html, css } from 'lit';
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

  private annulerAbonnementHaSvgIcon: (() => void) | null = null;

  connectedCallback(): void {
    super.connectedCallback();
    this.annulerAbonnementHaSvgIcon = whenDefined(HA_SVG_ICON, () => this.requestUpdate());
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    // Sans ça, chaque montage sur la tablette cuisine (ha-svg-icon n'y
    // charge jamais) empilerait un rappel jamais résolu.
    this.annulerAbonnementHaSvgIcon?.();
    this.annulerAbonnementHaSvgIcon = null;
  }

  static styles = [tokens, css`
    :host { display: inline-flex; width: 24px; height: 24px; }
    svg, ha-svg-icon { width: 100%; height: 100%; fill: currentColor; }
  `];

  /** Reflète le libellé sur l'hôte avant chaque rendu, pas dans le shadow
   *  DOM : voir le commentaire de tête du fichier. */
  willUpdate(): void {
    if (this.label) {
      this.setAttribute('role', 'img');
      this.setAttribute('aria-label', this.label);
      this.removeAttribute('aria-hidden');
    } else {
      this.removeAttribute('role');
      this.removeAttribute('aria-label');
      this.setAttribute('aria-hidden', 'true');
    }
  }

  render() {
    const path = ICON_PATHS[this.name];
    if (isDefined(HA_SVG_ICON)) {
      return html`<ha-svg-icon .path=${path}></ha-svg-icon>`;
    }
    // Toujours décoratif : le nom accessible est déjà sur l'hôte.
    return html`
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d=${path}></path>
      </svg>`;
  }
}
