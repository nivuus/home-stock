/** Les quatre familles, en bas sur téléphone et tablette, en rail à gauche sur
 *  bureau. Elles sont TOUJOURS les quatre : l'ancienne barre masquait le
 *  bouton de l'écran courant, ce qui décalait tous les autres à chaque
 *  navigation et faisait perdre le repère. */
import { LitElement, html, css, nothing } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { tokens } from './ui/tokens';
import './ui/hs-icon';
import { FAMILIES, familyOf, type FamilyId } from './destinations';
import type { Ecran } from '../panneau';

@customElement('hs-nav-bar')
export class HsNavBar extends LitElement {
  @property({ attribute: false }) current: Ecran = 'liste';
  @property({ type: Boolean }) rail = false;
  @property({ attribute: false }) badges: Partial<Record<FamilyId, number>> = {};

  static styles = [tokens, css`
    :host { display: block; }
    .barre {
      display: flex; background: var(--hs-surface);
      border-top: 1px solid var(--hs-divider);
    }
    .barre.rail {
      flex-direction: column;
      border-top: none; border-right: 1px solid var(--hs-divider);
      height: 100%;
    }
    .destination {
      flex: 1 1 0; position: relative;
      display: flex; flex-direction: column; align-items: center; justify-content: center;
      gap: var(--hs-space-1);
      min-height: var(--hs-touch); min-width: var(--hs-touch);
      padding: var(--hs-space-2) var(--hs-space-1);
      border: none; background: none; cursor: pointer;
      font-family: var(--hs-font); font-size: 0.75rem;
      color: var(--hs-text-2);
    }
    .barre.rail .destination { flex: 0 0 auto; }
    .destination.active { color: var(--hs-accent); font-weight: 600; }
    .badge {
      position: absolute; top: var(--hs-space-1);
      /* Décalé vers la droite du centre : la pastille se pose sur l'angle de
         l'icône, pas sur le libellé. */
      left: 56%;
      min-width: 18px; height: 18px; box-sizing: border-box;
      padding: 0 4px; border-radius: 9px;
      background: var(--hs-accent); color: var(--hs-on-accent);
      font-size: 0.7rem; line-height: 18px; text-align: center;
    }
  `];

  private choisir(family: FamilyId): void {
    this.dispatchEvent(new CustomEvent('famille-choisie', {
      detail: { family }, bubbles: true, composed: true,
    }));
  }

  render() {
    const familleCourante = familyOf(this.current);
    return html`
      <nav class="barre ${this.rail ? 'rail' : ''}">
        ${FAMILIES.map((famille) => {
          const compte = this.badges[famille.id] ?? 0;
          const active = famille.id === familleCourante;
          return html`
            <button class="destination ${active ? 'active' : ''}"
                    data-family=${famille.id}
                    aria-current=${active ? 'page' : nothing}
                    aria-label=${compte > 0 ? `${famille.label}, ${compte} en attente` : famille.label}
                    @click=${() => this.choisir(famille.id)}>
              <hs-icon name=${famille.icon}></hs-icon>
              <span>${famille.label}</span>
              ${compte > 0 ? html`<span class="badge">${compte}</span>` : nothing}
            </button>`;
        })}
      </nav>`;
  }
}
