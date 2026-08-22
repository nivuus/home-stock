import { afterEach, describe, expect, it, vi } from 'vitest';
import '../src/shell/nav-bar';
import type { FamilyId } from '../src/shell/destinations';

afterEach(() => { document.body.innerHTML = ''; });

async function monter(props: Record<string, unknown> = {}) {
  const el = document.createElement('hs-nav-bar') as HTMLElement
    & { updateComplete: Promise<unknown> } & Record<string, unknown>;
  Object.assign(el, { current: 'liste', rail: false, badges: {} }, props);
  document.body.appendChild(el);
  await el.updateComplete;
  return el;
}

describe('barre de navigation', () => {
  it('rend TOUJOURS les quatre familles, y compris celle où l’on est', async () => {
    // Le défaut de l'ancienne barre : elle masquait le bouton de l'écran
    // courant, ce qui décalait tous les autres à chaque navigation.
    const el = await monter({ current: 'liste' });
    const boutons = el.shadowRoot!.querySelectorAll('.destination');
    expect(boutons).toHaveLength(4);
  });

  it('marque la famille courante, et elle seule', async () => {
    const el = await monter({ current: 'journal' });   // famille « stock »
    const actives = el.shadowRoot!.querySelectorAll('.destination.active');
    expect(actives).toHaveLength(1);
    expect(actives[0].getAttribute('data-family')).toBe('stock');
    expect(actives[0].getAttribute('aria-current')).toBe('page');
  });

  it('marque la famille depuis un SOUS-écran, pas seulement depuis la racine', async () => {
    const el = await monter({ current: 'reglages' });  // famille « house »
    expect(el.shadowRoot!.querySelector('.destination.active')!
      .getAttribute('data-family')).toBe('house');
  });

  it('émet la famille choisie', async () => {
    const el = await monter({ current: 'liste' });
    const recu = vi.fn();
    el.addEventListener('famille-choisie', (e) => recu((e as CustomEvent).detail));
    (el.shadowRoot!.querySelector('[data-family="kitchen"]') as HTMLElement).click();
    expect(recu).toHaveBeenCalledWith({ family: 'kitchen' });
  });

  it('affiche une pastille de compte, et rien quand le compte est nul', async () => {
    const el = await monter({ badges: { shopping: 3, house: 0 } as Partial<Record<FamilyId, number>> });
    expect(el.shadowRoot!.querySelector('[data-family="shopping"] .badge')!.textContent!.trim())
      .toBe('3');
    expect(el.shadowRoot!.querySelector('[data-family="house"] .badge')).toBeNull();
  });

  it('annonce la pastille aux lecteurs d’écran', async () => {
    const el = await monter({ badges: { shopping: 3 } });
    expect(el.shadowRoot!.querySelector('[data-family="shopping"]')!
      .getAttribute('aria-label')).toBe('Courses, 3 en attente');
  });

  it('passe en rail quand on le lui demande', async () => {
    const el = await monter({ rail: true });
    expect(el.shadowRoot!.querySelector('.barre')!.classList.contains('rail')).toBe(true);
  });

  it('rend une action primaire quand on lui en donne une', async () => {
    const el = await monter({ action: { icon: 'scan', label: 'Scanner un article' } });
    const bouton = el.shadowRoot!.querySelector('.action') as HTMLElement;
    expect(bouton).not.toBeNull();
    expect(bouton.getAttribute('aria-label')).toBe('Scanner un article');
  });

  it('n’en rend aucune quand il n’y en a pas', async () => {
    const el = await monter({ action: null });
    expect(el.shadowRoot!.querySelector('.action')).toBeNull();
  });

  it('émet l’action primaire', async () => {
    const el = await monter({ action: { icon: 'scan', label: 'Scanner un article' } });
    const recu = vi.fn();
    el.addEventListener('action-primaire', recu);
    (el.shadowRoot!.querySelector('.action') as HTMLElement).click();
    expect(recu).toHaveBeenCalledTimes(1);
  });
});
