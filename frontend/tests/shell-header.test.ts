import { afterEach, describe, expect, it, vi } from 'vitest';
import '../src/shell/header';

afterEach(() => { document.body.innerHTML = ''; });

async function monter(props: Record<string, unknown> = {}) {
  const el = document.createElement('hs-header') as HTMLElement
    & { updateComplete: Promise<unknown> } & Record<string, unknown>;
  Object.assign(el, { current: 'liste', pending: 0, error: null }, props);
  document.body.appendChild(el);
  await el.updateComplete;
  return el;
}

describe('en-tête', () => {
  it('porte le titre de l’écran, en français', async () => {
    const el = await monter({ current: 'rangement' });
    expect(el.shadowRoot!.querySelector('.titre')!.textContent!.trim()).toBe('Rangement');
  });

  it('n’offre pas de retour sur une racine de famille', async () => {
    const el = await monter({ current: 'liste' });
    expect(el.shadowRoot!.querySelector('.retour')).toBeNull();
  });

  it('offre un retour sur un sous-écran', async () => {
    const el = await monter({ current: 'reglages' });
    expect(el.shadowRoot!.querySelector('.retour')).not.toBeNull();
  });

  it('émet la demande de retour', async () => {
    const el = await monter({ current: 'reglages' });
    const recu = vi.fn();
    el.addEventListener('retour-demande', recu);
    (el.shadowRoot!.querySelector('.retour') as HTMLElement).click();
    expect(recu).toHaveBeenCalledTimes(1);
  });

  it('montre le nombre d’écritures en attente, et rien à zéro', async () => {
    const avec = await monter({ pending: 2 });
    expect(avec.shadowRoot!.querySelector('.attente')!.textContent).toContain('2');
    document.body.innerHTML = '';
    const sans = await monter({ pending: 0 });
    expect(sans.shadowRoot!.querySelector('.attente')).toBeNull();
  });

  it('porte la bannière de refus et son accusé de réception', async () => {
    const el = await monter({ error: 'Stock insuffisant' });
    expect(el.shadowRoot!.querySelector('.erreur')!.textContent)
      .toContain('Stock insuffisant');
    const recu = vi.fn();
    el.addEventListener('erreur-acquittee', recu);
    (el.shadowRoot!.querySelector('.fermer-erreur') as HTMLElement).click();
    expect(recu).toHaveBeenCalledTimes(1);
  });

  it('annonce la bannière comme une alerte', async () => {
    const el = await monter({ error: 'Stock insuffisant' });
    expect(el.shadowRoot!.querySelector('.erreur')!.getAttribute('role')).toBe('alert');
  });
});
