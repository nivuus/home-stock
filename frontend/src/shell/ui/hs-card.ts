/** Une carte : `<ha-card>` si Home Assistant l'a chargée, un repli visuellement
 *  identique sinon. Voir `ha-available.ts` pour pourquoi ce n'est pas
 *  simplement `<ha-card>` partout. */
import { LitElement, html, css } from 'lit';
import { customElement } from 'lit/decorators.js';
import { tokens } from './tokens';
import { isDefined, whenDefined } from './ha-available';

const HA_CARD = 'ha-card';

@customElement('hs-card')
export class HsCard extends LitElement {
  /** Le désabonnement rendu par `whenDefined`, à rappeler au démontage. Sans
   *  lui, chaque montage empile un rappel qui n'est vidé qu'à la définition de
   *  l'élément — or sur la tablette de la cuisine, qui ouvre `/home-stock`
   *  sans passer par Lovelace, `ha-card` n'est JAMAIS défini. Le kiosque
   *  tourne en continu : la table grossirait sans fin. */
  private desabonner?: () => void;

  connectedCallback(): void {
    super.connectedCallback();
    this.desabonner = whenDefined(HA_CARD, () => this.requestUpdate());
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    this.desabonner?.();
    this.desabonner = undefined;
  }

  static styles = [tokens, css`
    :host { display: block; }
    .repli {
      background: var(--hs-surface);
      color: var(--hs-text);
      border-radius: var(--hs-radius-m);
      border: 1px solid var(--hs-divider);
      overflow: hidden;
    }
  `];

  render() {
    if (isDefined(HA_CARD)) return html`<ha-card><slot></slot></ha-card>`;
    return html`<div class="repli"><slot></slot></div>`;
  }
}
