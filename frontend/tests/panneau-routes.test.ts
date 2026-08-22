import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import '../src/panneau';
import type { Hass } from '../src/connexion';

/** Des réponses VIDES mais BIEN FORMÉES. Un `null` universel suffirait aux
 *  assertions de ce fichier, mais chaque écran atteint charge ses données au
 *  montage : `null.batteries` part alors en rejet non capturé, et vitest fait
 *  échouer le run entier sur un bruit qui n'a rien à voir avec les routes. */
const REPONSES_VIDES: Record<string, unknown> = {
  'home_stock/session/current': null,
  'home_stock/products/list': { products: [] },
  'home_stock/aisles/list': { aisles: [] },
  'home_stock/locations/list': { locations: [] },
  'home_stock/batches/list': { batches: [] },
  'home_stock/stores/list': { stores: [] },
  'home_stock/recurring/list': { recurring: [] },
  'home_stock/batteries/list': { batteries: [] },
  'home_stock/batteries/discover': { sensors: [] },
  'home_stock/equipment/list': { equipment: [] },
  'home_stock/recipes/list': { recipes: [] },
  'home_stock/meals/list': { meals: [] },
  'home_stock/recipe/get': {
    recipe: { id: 12, name: 'Gratin', servings: 2, total_minutes: null, utensils: null,
              summary: null, image_url: null, language: 'fr', needs_review: 0 },
    steps: [], ingredients: [],
  },
  'home_stock/list/items': { items: [], store_id: null, store_name: null,
                             estimate: { amount: 0, confidence: 0, priced: 0, total: 0 } },
};

function hassFactice(): Hass {
  return {
    connection: {
      sendMessagePromise: vi.fn().mockImplementation((msg: { type: string }) =>
        Promise.resolve(msg.type in REPONSES_VIDES ? REPONSES_VIDES[msg.type] : {})),
      subscribeMessage: vi.fn().mockResolvedValue(() => {}),
    },
    language: 'fr',
  } as unknown as Hass;
}

function laisserPasserLesMicrotaches(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

async function monter(path: string) {
  const el = document.createElement('home-stock-panel') as HTMLElement
    & { updateComplete: Promise<unknown>; hass: Hass; route: unknown; ecran: string };
  el.hass = hassFactice();
  el.route = { prefix: '/home-stock', path };
  document.body.appendChild(el);
  await laisserPasserLesMicrotaches();
  await el.updateComplete;
  return el;
}

describe('panneau : routes d’URL', () => {
  beforeEach(() => { window.localStorage.clear(); });
  afterEach(() => { document.body.innerHTML = ''; vi.restoreAllMocks(); });

  it('ouvre l’écran que l’URL désigne', async () => {
    const el = await monter('/catalog');
    expect(el.ecran).toBe('catalogue');
  });

  it('ouvre un écran paramétré avec son paramètre', async () => {
    const el = await monter('/recipe/12');
    expect(el.ecran).toBe('recette');
    expect(el.shadowRoot!.querySelector('home-stock-recette')).not.toBeNull();
  });

  it('retombe sur la liste devant une route inconnue', async () => {
    const el = await monter('/nawak');
    expect(el.ecran).toBe('liste');
  });

  it('suit un changement de route venu de Home Assistant (bouton Retour)', async () => {
    const el = await monter('/catalog');
    el.route = { prefix: '/home-stock', path: '/batteries' };
    await el.updateComplete;
    expect(el.ecran).toBe('piles');
  });

  it('pousse l’URL et prévient Home Assistant quand on navigue', async () => {
    const el = await monter('/list');
    const pushState = vi.spyOn(window.history, 'pushState');
    const evenements: string[] = [];
    window.addEventListener('location-changed', () => evenements.push('vu'));

    const barre = el.shadowRoot!.querySelector('hs-nav-bar')!;
    barre.dispatchEvent(new CustomEvent('famille-choisie', {
      detail: { family: 'kitchen' }, bubbles: true, composed: true,
    }));
    await el.updateComplete;

    expect(el.ecran).toBe('planning');
    expect(pushState).toHaveBeenCalledWith(null, '', '/home-stock/planner');
    expect(evenements).toHaveLength(1);
  });

  it('rend la barre et l’en-tête sur tout écran sauf la fiche', async () => {
    const el = await monter('/list');
    expect(el.shadowRoot!.querySelector('hs-nav-bar')).not.toBeNull();
    expect(el.shadowRoot!.querySelector('hs-header')).not.toBeNull();
  });

  it('remonte au retour de l’en-tête vers la racine de la famille', async () => {
    const el = await monter('/settings');           // famille « house »
    const entete = el.shadowRoot!.querySelector('hs-header')!;
    entete.dispatchEvent(new CustomEvent('retour-demande', { bubbles: true, composed: true }));
    await el.updateComplete;
    expect(el.ecran).toBe('piles');                  // la racine de « house »
  });
});
