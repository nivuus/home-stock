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
import type { IconName } from './ui/icons';

@customElement('hs-nav-bar')
export class HsNavBar extends LitElement {
  @property({ attribute: false }) current: Ecran = 'liste';
  @property({ type: Boolean }) rail = false;
  @property({ attribute: false }) badges: Partial<Record<FamilyId, number>> = {};
  /** L'action primaire de la famille courante — le scan, sur Courses et sur
   *  Stock. `null` ailleurs : un bouton flottant sans action à offrir vaut
   *  moins que rien. `text` est ce qui s'AFFICHE ; `label` reste le nom
   *  accessible, qui peut être plus long. */
  @property({ attribute: false }) action:
    { icon: IconName; label: string; text: string } | null = null;

  static styles = [tokens, css`
    :host { display: block; }
    .barre {
      position: relative;
      display: flex; background: var(--hs-surface);
      border-top: 1px solid var(--hs-divider);
    }
    .barre.rail {
      flex-direction: column;
      border-top: none; border-right: 1px solid var(--hs-divider);
      height: 100%;
    }
    /* Un bouton flottant NOMMÉ, pas un rond muet. La version ronde ne portait
       son libellé que dans son aria-label : à l'œil, c'était une pastille de
       couleur sans rien qui dise « scanner », et c'est le premier geste de
       l'application. Le texte n'est pas un ornement — c'est la seule chose
       qui distingue ce bouton d'une décoration. */
    .action {
      position: absolute; right: var(--hs-space-4); bottom: 100%;
      margin-bottom: var(--hs-space-3);
      min-width: var(--hs-touch); height: var(--hs-touch);
      padding: 0 var(--hs-space-4); gap: var(--hs-space-2);
      display: inline-flex; align-items: center; justify-content: center;
      border: none; border-radius: 999px;
      font-family: var(--hs-font); font-size: 0.95rem; font-weight: 600;
      background: var(--hs-accent); color: var(--hs-on-accent);
      /* Seule couleur littérale tolérée dans tout le projet (voir la Task
         13) : une ombre n'a pas de jeton et ne participe à aucun contraste
         texte/fond. */
      box-shadow: 0 2px 6px rgba(0, 0, 0, 0.3);
      cursor: pointer;
    }
    /* En rail, l'action reprend le flux, en tête de colonne. */
    .barre.rail .action {
      position: static; margin: var(--hs-space-3) auto 0;
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
        ${this.action ? html`
          <button class="action" aria-label=${this.action.label}
                  @click=${() => this.dispatchEvent(new CustomEvent('action-primaire',
                    { bubbles: true, composed: true }))}>
            <!-- Le nom accessible vient du bouton, pas de l'icône : sans
                 label, hs-icon reste décorative et s'efface aux lecteurs
                 d'écran (même parti pris que les pastilles de famille
                 ci-dessus, qui portent déjà leur aria-label sur le bouton). -->
            <hs-icon name=${this.action.icon}></hs-icon>
            <span class="action-libelle">${this.action.text}</span>
          </button>` : nothing}
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
