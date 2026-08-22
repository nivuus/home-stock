import { afterEach, describe, expect, it, vi } from 'vitest';
import { pendingCountForTests, resetForTests } from '../src/shell/ui/ha-available';
import '../src/shell/ui/hs-card';
import '../src/shell/ui/hs-button';

afterEach(() => {
  document.body.innerHTML = '';
  resetForTests();
});

async function monter(balise: string, attributs: Record<string, string> = {}) {
  const el = document.createElement(balise);
  for (const [n, v] of Object.entries(attributs)) el.setAttribute(n, v);
  document.body.appendChild(el);
  await (el as HTMLElement & { updateComplete: Promise<unknown> }).updateComplete;
  return el;
}

describe('hs-card', () => {
  // DOIT rester le premier test de `hs-card` : `customElements.define('ha-card', …)`,
  // plus bas dans ce fichier, est une opération irréversible qu'aucun `resetForTests`
  // ne peut annuler. Si ce test s'exécutait après, `isDefined('ha-card')` serait déjà
  // vrai au montage, `whenDefined` court-circuiterait sans jamais entrer l'instance
  // dans la table de `ha-available.ts`, et le test « passerait » sans avoir observé
  // le désabonnement — même piège qu'à la Task 3, une assertion vraie pour une
  // raison différente de celle qu'elle annonce. Voir le même ordre imposé dans
  // `shell-icons.test.ts`. `hs-button` n'a plus d'abonnement du tout depuis la
  // correction 1 (plus de branche `ha-button`) : ce test ne concerne donc plus que
  // `hs-card`.
  it('se désabonne au démontage', async () => {
    const avant = pendingCountForTests();
    const el = await monter('hs-card');
    el.remove();
    expect(pendingCountForTests()).toBe(avant);
  });

  it('rend son repli quand ha-card n’est pas chargé', async () => {
    const el = await monter('hs-card');
    expect(el.shadowRoot!.querySelector('.repli')).not.toBeNull();
    expect(el.shadowRoot!.querySelector('ha-card')).toBeNull();
  });

  it('rend ha-card quand il est chargé', async () => {
    if (!customElements.get('ha-card')) {
      customElements.define('ha-card', class extends HTMLElement {});
    }
    const el = await monter('hs-card');
    expect(el.shadowRoot!.querySelector('ha-card')).not.toBeNull();
    expect(el.shadowRoot!.querySelector('.repli')).toBeNull();
  });
});

describe('hs-button', () => {
  // Pas de branche `ha-button` à tester : `hs-button` rend toujours son propre
  // `<button>` (voir le commentaire de tête de `hs-button.ts` — `ha-button` peint
  // sa variante sur un élément interne à SON shadow DOM, hors d'atteinte d'une
  // classe posée sur l'hôte).
  it('rend un bouton natif', async () => {
    const el = await monter('hs-button');
    expect(el.shadowRoot!.querySelector('button')).not.toBeNull();
  });

  it('laisse le clic remonter, sans le dupliquer', async () => {
    // Réémettre un `click` depuis l'enveloppe le ferait compter DEUX fois
    // chez l'appelant : le natif traverse déjà le shadow DOM.
    const el = await monter('hs-button');
    const surClic = vi.fn();
    el.addEventListener('click', surClic);
    el.shadowRoot!.querySelector('button')!.click();
    expect(surClic).toHaveBeenCalledTimes(1);
  });

  it('n’émet aucun clic quand il est désactivé', async () => {
    const el = await monter('hs-button', { disabled: '' });
    const surClic = vi.fn();
    el.addEventListener('click', surClic);
    el.shadowRoot!.querySelector('button')!.click();
    expect(surClic).not.toHaveBeenCalled();
  });

  it('tient la cible tactile de la tablette', async () => {
    const el = await monter('hs-button');
    const styles = (el.constructor as typeof HTMLElement & { styles: { cssText: string }[] });
    const texte = styles.styles.map((s) => s.cssText).join('');
    expect(texte).toContain('min-height: var(--hs-touch)');
  });

  it('dit le danger par une bordure, jamais par un aplat sous du texte', async () => {
    // --error-color tombe pile à 4,29:1 des deux côtés (spec § 6.1 ter) :
    // aucune couleur de texte ne passerait 4,5:1 sur un aplat --hs-danger.
    const el = await monter('hs-button');
    const styles = (el.constructor as typeof HTMLElement & { styles: { cssText: string }[] });
    const texte = styles.styles.map((s) => s.cssText).join('');
    const regleDanger = /\.danger\s*\{[^}]*\}/.exec(texte)?.[0] ?? '';
    expect(regleDanger).toContain('border-color: var(--hs-danger)');
    expect(regleDanger).toContain('color: var(--hs-text)');
    expect(regleDanger).not.toContain('background: var(--hs-danger)');
  });
});
