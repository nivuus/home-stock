import { afterEach, describe, expect, it } from 'vitest';
import { ICON_PATHS } from '../src/shell/ui/icons';
import { resetForTests } from '../src/shell/ui/ha-available';
import '../src/shell/ui/hs-icon';

afterEach(() => {
  document.body.innerHTML = '';
  resetForTests();
});

async function monter(attributs: Record<string, string>): Promise<HTMLElement> {
  const el = document.createElement('hs-icon');
  for (const [nom, valeur] of Object.entries(attributs)) el.setAttribute(nom, valeur);
  document.body.appendChild(el);
  await (el as HTMLElement & { updateComplete: Promise<unknown> }).updateComplete;
  return el;
}

describe('hs-icon', () => {
  it('porte tous les tracés dont la coquille a besoin', () => {
    for (const nom of ['cart', 'package', 'cutlery', 'home', 'back', 'scan',
                       'plus', 'check', 'close', 'search', 'settings',
                       'battery', 'menu', 'alert', 'clock']) {
      expect(ICON_PATHS[nom as keyof typeof ICON_PATHS]).toMatch(/^M/);
    }
  });

  it('rend un svg à nous quand ha-svg-icon n’est pas chargé', async () => {
    const el = await monter({ name: 'cart' });
    const svg = el.shadowRoot!.querySelector('svg');
    expect(svg).not.toBeNull();
    expect(svg!.querySelector('path')!.getAttribute('d')).toBe(ICON_PATHS.cart);
  });

  it('est masqué aux lecteurs d’écran quand il n’a pas de libellé', async () => {
    const el = await monter({ name: 'cart' });
    expect(el.shadowRoot!.querySelector('svg')!.getAttribute('aria-hidden')).toBe('true');
  });

  it('annonce son libellé quand il en a un', async () => {
    const el = await monter({ name: 'cart', label: 'Courses' });
    const svg = el.shadowRoot!.querySelector('svg')!;
    expect(svg.getAttribute('aria-hidden')).toBeNull();
    expect(svg.getAttribute('role')).toBe('img');
    expect(svg.querySelector('title')!.textContent).toBe('Courses');
  });

  // Ce test DOIT rester le dernier du fichier : `customElements.define` est
  // définitif, aucun `resetForTests` ne peut désenregistrer `ha-svg-icon`
  // une fois posé. Un test placé après verrait donc toujours l'élément
  // disponible, même s'il veut vérifier le repli `<svg>`.
  it('préfère ha-svg-icon dès qu’il est disponible, avec NOTRE tracé', async () => {
    // Le tracé vient de nous dans les deux cas : on ne dépend jamais du
    // chargement de l'iconset mdi de Home Assistant.
    if (!customElements.get('ha-svg-icon')) {
      customElements.define('ha-svg-icon', class extends HTMLElement {});
    }
    const el = await monter({ name: 'home' });
    const haIcon = el.shadowRoot!.querySelector('ha-svg-icon');
    expect(haIcon).not.toBeNull();
    expect((haIcon as HTMLElement & { path?: string }).path).toBe(ICON_PATHS.home);
    expect(el.shadowRoot!.querySelector('svg')).toBeNull();
  });
});
