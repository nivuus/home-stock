import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import '../src/panneau';
import type { Hass } from '../src/connexion';

/** Attend que les microtâches en attente (les .then() de connectedCallback,
 *  notamment celui de l'abonnement) se soient exécutées. */
function laisserPasserLesMicrotaches(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

function hassFactice(surAbonnement: () => Promise<() => void>): Hass {
  return {
    connection: {
      sendMessagePromise: vi.fn().mockResolvedValue({}),
      subscribeMessage: vi.fn().mockImplementation(surAbonnement),
    },
    language: 'fr',
  } as unknown as Hass;
}

describe('panneau : cycle de vie de l’abonnement au résumé', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    document.body.innerHTML = '';
  });

  it('se désabonne quand il quitte le DOM', async () => {
    const desabonner = vi.fn();
    const element = document.createElement('home-stock-panel') as HTMLElement & { hass: Hass };
    element.hass = hassFactice(async () => desabonner);
    document.body.appendChild(element);

    // Laisse connectedCallback recevoir la fonction de désabonnement avant
    // de retirer l'élément — c'est le chemin normal : ouvrir le panneau,
    // puis en sortir.
    await laisserPasserLesMicrotaches();

    element.remove();

    expect(desabonner).toHaveBeenCalledTimes(1);
  });

  it('se désabonne tout de suite si l’élément part avant que l’abonnement ne réponde', async () => {
    const desabonner = vi.fn();
    let resoudre!: (valeur: () => void) => void;
    const abonnementEnVol = new Promise<() => void>((resolve) => { resoudre = resolve; });

    const element = document.createElement('home-stock-panel') as HTMLElement & { hass: Hass };
    element.hass = hassFactice(() => abonnementEnVol);
    document.body.appendChild(element);

    // L'élément part alors que la promesse d'abonnement est encore en vol :
    // disconnectedCallback s'exécute maintenant et ne sera pas rappelé.
    element.remove();
    resoudre(desabonner);
    await laisserPasserLesMicrotaches();

    expect(desabonner).toHaveBeenCalledTimes(1);
  });

  it('ne se désabonne pas tant qu’il reste dans le DOM', async () => {
    const desabonner = vi.fn();
    const element = document.createElement('home-stock-panel') as HTMLElement & { hass: Hass };
    element.hass = hassFactice(async () => desabonner);
    document.body.appendChild(element);

    await laisserPasserLesMicrotaches();

    expect(desabonner).not.toHaveBeenCalled();
    element.remove();
  });
});
