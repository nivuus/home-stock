/** L'en-tête constant : retour, titre, et les deux indicateurs qui étaient
 *  jusqu'ici posés à la main dans `panneau.ts` — le nombre d'écritures en
 *  file, et le dernier refus du serveur. */
import { LitElement, html, css, nothing } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { tokens } from './ui/tokens';
import './ui/hs-icon';
import { destinationOf } from './destinations';
import type { Ecran } from '../panneau';

@customElement('hs-header')
export class HsHeader extends LitElement {
  @property({ attribute: false }) current: Ecran = 'liste';
  @property({ type: Number }) pending = 0;
  /** Le message du serveur, déjà en français : on ne le reformule pas. */
  @property({ attribute: false }) error: string | null = null;

  static styles = [tokens, css`
    :host { display: block; }
    .barre {
      display: flex; align-items: center; gap: var(--hs-space-2);
      min-height: var(--hs-touch);
      padding: var(--hs-space-2) var(--hs-space-3);
      background: var(--hs-surface); color: var(--hs-text);
      border-bottom: 1px solid var(--hs-divider);
    }
    .retour {
      display: inline-flex; align-items: center; justify-content: center;
      min-height: var(--hs-touch); min-width: var(--hs-touch);
      border: none; background: none; color: inherit; cursor: pointer;
      border-radius: var(--hs-radius-s);
    }
    .titre { flex: 1; font-size: 1.15rem; font-weight: 600; }
    .attente {
      display: inline-flex; align-items: center; gap: var(--hs-space-1);
      color: var(--hs-text-2); font-size: 0.85rem;
    }
    /* Pas d'aplat rouge sous ce texte : --error-color vaut #db4437 sous le
       thème HA par défaut, une luminance au point de bascule exact où blanc et
       noir donnent tous deux 4,29:1 — sous le seuil. Le danger passe par le
       liseré et l'icône ; le texte garde 17:1. Voir spec § 6.1 ter. */
    .erreur {
      display: flex; align-items: center; gap: var(--hs-space-2);
      margin: 0; padding: var(--hs-space-2) var(--hs-space-3);
      background: var(--hs-surface); color: var(--hs-text);
      border-left: 4px solid var(--hs-danger);
      border-bottom: 1px solid var(--hs-divider);
      font-size: 0.9rem;
    }
    .erreur hs-icon { color: var(--hs-danger); flex: 0 0 auto; }
    .message-erreur { flex: 1; }
    .fermer-erreur {
      min-height: var(--hs-touch); min-width: var(--hs-touch);
      border: 1px solid var(--hs-divider); border-radius: var(--hs-radius-s);
      background: var(--hs-surface-2); color: var(--hs-text);
      font-weight: 600; cursor: pointer;
    }
  `];

  render() {
    const destination = destinationOf(this.current);
    return html`
      <div class="barre">
        ${destination.root ? nothing : html`
          <button class="retour" aria-label="Retour" @click=${() => this.dispatchEvent(
            new CustomEvent('retour-demande', { bubbles: true, composed: true }))}>
            <hs-icon name="back" label="Retour"></hs-icon>
          </button>`}
        <span class="titre">${destination.label}</span>
        ${this.pending > 0 ? html`
          <span class="attente">
            <hs-icon name="clock"></hs-icon>${this.pending} en attente
          </span>` : nothing}
      </div>
      ${this.error ? html`
        <p class="erreur" role="alert">
          <hs-icon name="alert"></hs-icon>
          <span class="message-erreur">${this.error}</span>
          <button class="fermer-erreur" @click=${() => this.dispatchEvent(
            new CustomEvent('erreur-acquittee', { bubbles: true, composed: true }))}>OK</button>
        </p>` : nothing}`;
  }
}
