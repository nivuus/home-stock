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
  it('rend un bouton natif quand ha-button n’est pas chargé', async () => {
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

  it('se désabonne au démontage, dans les deux enveloppes', async () => {
    // La fuite que ce test interdit est bornée à l'appareil où l'élément HA
    // n'arrive jamais — la tablette cuisine — mais c'est un kiosque qui tourne
    // en continu, avec des dizaines de boutons remontés à chaque navigation.
    const avant = pendingCountForTests();
    const carte = await monter('hs-card');
    const bouton = await monter('hs-button');
    carte.remove();
    bouton.remove();
    expect(pendingCountForTests()).toBe(avant);
  });

  it('tient la cible tactile de la tablette', async () => {
    const el = await monter('hs-button');
    const styles = (el.constructor as typeof HTMLElement & { styles: { cssText: string }[] });
    const texte = styles.styles.map((s) => s.cssText).join('');
    expect(texte).toContain('min-height: var(--hs-touch)');
  });
});
