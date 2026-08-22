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

  it('est masqué aux lecteurs d’écran, sur l’HÔTE, quand il n’a pas de libellé', async () => {
    // `ha-svg-icon` n'a pas de `label` (vérifié dans le bundle HA 2026.8.2)
    // et écrit lui-même `aria-hidden="true"` en dur dans SON svg interne :
    // le nom accessible ne peut donc jamais venir de l'intérieur d'une des
    // deux branches de rendu, il doit être porté par `<hs-icon>` elle-même.
    const el = await monter({ name: 'cart' });
    expect(el.getAttribute('aria-hidden')).toBe('true');
    expect(el.getAttribute('role')).toBeNull();
    // Le svg interne reste, lui aussi, toujours décoratif.
    expect(el.shadowRoot!.querySelector('svg')!.getAttribute('aria-hidden')).toBe('true');
  });

  it('annonce son libellé sur l’HÔTE quand il en a un (repli, sans ha-svg-icon)', async () => {
    const el = await monter({ name: 'cart', label: 'Courses' });
    expect(el.getAttribute('role')).toBe('img');
    expect(el.getAttribute('aria-label')).toBe('Courses');
    expect(el.getAttribute('aria-hidden')).toBeNull();
    expect(el.shadowRoot!.querySelector('svg')!.getAttribute('aria-hidden')).toBe('true');
  });

  // Les tests qui suivent enregistrent `ha-svg-icon` dans le registre des
  // éléments custom via `customElements.define` — une opération DÉFINITIVE
  // qu'aucun `resetForTests` ne peut annuler. Ils DOIVENT donc rester groupés
  // en fin de fichier, dans cet ordre précis : le premier fait la
  // définition (et a besoin qu'elle n'existe pas encore), tous les suivants
  // la trouvent déjà là.

  it('re-rend avec ha-svg-icon quand il se charge APRÈS le montage', async () => {
    // Le cas qui compte : la coquille rend son repli en premier (accès
    // direct à /home-stock, tablette cuisine), puis Lovelace charge son
    // chunk plus tard. Monter APRÈS avoir défini ha-svg-icon (comme le
    // faisait l'ancien test) ne prouve rien sur ce chemin : `isDefined`
    // serait déjà vrai au tout premier rendu.
    const el = await monter({ name: 'home' });
    expect(el.shadowRoot!.querySelector('svg')).not.toBeNull();
    expect(el.shadowRoot!.querySelector('ha-svg-icon')).toBeNull();

    customElements.define('ha-svg-icon', class extends HTMLElement {});
    await customElements.whenDefined('ha-svg-icon');
    await (el as HTMLElement & { updateComplete: Promise<unknown> }).updateComplete;

    expect(el.shadowRoot!.querySelector('svg')).toBeNull();
    const haIcon = el.shadowRoot!.querySelector('ha-svg-icon');
    expect(haIcon).not.toBeNull();
    expect((haIcon as HTMLElement & { path?: string }).path).toBe(ICON_PATHS.home);
  });

  it('préfère ha-svg-icon dès qu’il est disponible, avec NOTRE tracé', async () => {
    // ha-svg-icon est déjà défini par le test précédent : un nouveau montage
    // le trouve disponible dès le premier rendu.
    const el = await monter({ name: 'home' });
    const haIcon = el.shadowRoot!.querySelector('ha-svg-icon');
    expect(haIcon).not.toBeNull();
    expect((haIcon as HTMLElement & { path?: string }).path).toBe(ICON_PATHS.home);
    expect(el.shadowRoot!.querySelector('svg')).toBeNull();
    // ha-svg-icon ne déclare pas de `label` (vérifié dans le bundle HA
    // 2026.8.2) : le lui passer ne ferait rien, silencieusement — on ne le
    // fait donc plus.
    expect((haIcon as HTMLElement & { label?: unknown }).label).toBeUndefined();
  });

  it('annonce son libellé sur l’HÔTE quand ha-svg-icon est chargé', async () => {
    const el = await monter({ name: 'home', label: 'Accueil' });
    expect(el.getAttribute('role')).toBe('img');
    expect(el.getAttribute('aria-label')).toBe('Accueil');
    expect(el.getAttribute('aria-hidden')).toBeNull();
  });

  it('reste masqué sur l’HÔTE sans libellé, même avec ha-svg-icon chargé', async () => {
    const el = await monter({ name: 'home' });
    expect(el.getAttribute('aria-hidden')).toBe('true');
    expect(el.getAttribute('role')).toBeNull();
  });
});
