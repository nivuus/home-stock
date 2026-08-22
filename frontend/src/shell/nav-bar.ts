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
    /* L'accent NE PEUT PAS servir de couleur de texte ici : posé sur
       --hs-surface, il donne 3,26:1 sous le thème HA par défaut et 2,38:1
       sous Graphite (en service dans la maison) — les deux sous le seuil de
       4,5:1, relevé par outils/verifier-rendu.mjs dès que la barre a été
       branchée au panneau. L'état actif se dit donc par la GRAISSE du
       libellé, qui garde le contraste du texte ordinaire, et par une pastille
       d'accent derrière l'icône — un aplat, avec sa paire --hs-on-accent
       recalculée par on-color.ts, donc lisible sous n'importe quel thème.
       C'est aussi le motif de la barre de navigation Material 3. */
    .destination.active { color: var(--hs-text); font-weight: 600; }
    .destination.active hs-icon {
      box-sizing: content-box;
      padding: 2px 12px;
      border-radius: 999px;
      background: var(--hs-accent);
      color: var(--hs-on-accent);
    }
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
