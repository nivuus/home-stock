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

/** Un hass dont les réponses dépendent du type de message — nécessaire dès
 *  qu'un test doit distinguer `session/current` de `lookup` de
 *  `session/add_line`, ce que le mock à réponse unique ne peut pas faire. */
function hassAvecReponses(reponses: (msg: any) => Promise<unknown>): Hass & {
  connection: { sendMessagePromise: ReturnType<typeof vi.fn> };
} {
  return {
    connection: {
      sendMessagePromise: vi.fn().mockImplementation(reponses),
      subscribeMessage: vi.fn().mockResolvedValue(() => {}),
    },
    language: 'fr',
  } as unknown as Hass & { connection: { sendMessagePromise: ReturnType<typeof vi.fn> } };
}

const RESULTAT_FACTICE = {
  code: '3229820129488', known: true,
  article: { id: 42, label: 'Muesli', brand: null, net_quantity: 500, image: null,
            nutriscore: null, kcal_per_base_unit: null },
  product: { id: 9, name: 'Muesli', base_unit: 'g' },
  off: null, off_raw: null, off_source: null, candidates: [], preselected_product_id: null,
  price: { price_per_base_unit: 0.004, source: 'last_known', store: null },
  conversion_offer: null, throttled: false, timed_out: false,
};

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

describe('panneau : le scan devient une fiche, avec le bon mode', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    document.body.innerHTML = '';
  });

  function monter(hass: Hass) {
    const element = document.createElement('home-stock-panel') as HTMLElement & {
      hass: Hass; updateComplete: Promise<boolean>;
    };
    element.hass = hass;
    document.body.appendChild(element);
    return element;
  }

  function emettreCodeLu(element: HTMLElement, code: string): void {
    const scanner = element.shadowRoot!.querySelector('home-stock-scanner')!;
    scanner.dispatchEvent(new CustomEvent('code-lu', { detail: { code }, bubbles: true, composed: true }));
  }

  it('appelle home_stock/lookup puis affiche la fiche avec mode panier quand une session est ouverte', async () => {
    const hass = hassAvecReponses((msg: any) => {
      if (msg.type === 'home_stock/session/current') return Promise.resolve({ store: 'Leclerc' });
      if (msg.type === 'home_stock/lookup') return Promise.resolve(RESULTAT_FACTICE);
      return Promise.resolve({});
    });
    const element = monter(hass);
    await laisserPasserLesMicrotaches();

    emettreCodeLu(element, '3229820129488');
    await laisserPasserLesMicrotaches();
    await (element as any).updateComplete;

    expect(hass.connection.sendMessagePromise).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'home_stock/lookup', code: '3229820129488' }));
    const fiche = element.shadowRoot!.querySelector('home-stock-fiche') as any;
    expect(fiche).not.toBeNull();
    expect(fiche.mode).toBe('panier');
    expect(fiche.resultat).toEqual(RESULTAT_FACTICE);
  });

  it('route vers la fiche en mode rangement quand il n’y a pas de session', async () => {
    const hass = hassAvecReponses((msg: any) => {
      if (msg.type === 'home_stock/session/current') return Promise.resolve(null);
      if (msg.type === 'home_stock/lookup') return Promise.resolve(RESULTAT_FACTICE);
      return Promise.resolve({});
    });
    const element = monter(hass);
    await laisserPasserLesMicrotaches();

    emettreCodeLu(element, '3229820129488');
    await laisserPasserLesMicrotaches();
    await (element as any).updateComplete;

    const fiche = element.shadowRoot!.querySelector('home-stock-fiche') as any;
    expect(fiche.mode).toBe('rangement');
  });
});

describe('panneau : l’ajout au panier passe par la file hors-ligne', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    document.body.innerHTML = '';
  });

  /** Amène le panneau jusqu'à la fiche montée (session ouverte, donc mode
   *  panier), pour pouvoir émettre `article-pret` depuis un vrai enfant —
   *  un événement composé sur le panneau lui-même ne traverse pas son
   *  propre DOM interne, il faut passer par l'élément qui l'écoute. */
  async function monterSurLaFiche(hass: Hass & { connection: { sendMessagePromise: ReturnType<typeof vi.fn> } }) {
    const element = document.createElement('home-stock-panel') as HTMLElement & {
      hass: Hass; updateComplete: Promise<boolean>; enAttente: number;
    };
    element.hass = hass;
    document.body.appendChild(element);
    await laisserPasserLesMicrotaches();

    const scanner = element.shadowRoot!.querySelector('home-stock-scanner')!;
    scanner.dispatchEvent(new CustomEvent('code-lu', {
      detail: { code: '3229820129488' }, bubbles: true, composed: true,
    }));
    await laisserPasserLesMicrotaches();
    await (element as any).updateComplete;

    const fiche = element.shadowRoot!.querySelector('home-stock-fiche')!;
    return { element, fiche };
  }

  it('met l’ajout en file et le tient en attente quand le réseau refuse, sans le perdre', async () => {
    const hass = hassAvecReponses((msg: any) => {
      if (msg.type === 'home_stock/session/current') return Promise.resolve({ store: null });
      if (msg.type === 'home_stock/lookup') return Promise.resolve(RESULTAT_FACTICE);
      if (msg.type === 'home_stock/session/add_line') return Promise.reject(new Error('hors ligne'));
      return Promise.resolve({});
    });
    const { element, fiche } = await monterSurLaFiche(hass);

    fiche.dispatchEvent(new CustomEvent('article-pret', {
      detail: { articleId: 42, quantite: 500, prixUnitaire: 0.005, mode: 'panier', offDroppedFields: [] },
      bubbles: true, composed: true,
    }));
    await laisserPasserLesMicrotaches();
    await (element as any).updateComplete;

    // La commande n'a jamais dû partir en appel direct hors file : c'est
    // FileAttente.ajouter qui l'a prise en charge, et elle est restée en
    // attente puisque l'envoi a été refusé.
    const file = JSON.parse(window.localStorage.getItem('home_stock.file') ?? '[]');
    expect(file).toHaveLength(1);
    expect(file[0].type).toBe('home_stock/session/add_line');
    expect(file[0].charge.article_id).toBe(42);
    expect((element as any).enAttente).toBe(1);
  });

  it('envoie tout de suite quand le réseau répond, et vide la file', async () => {
    const hass = hassAvecReponses((msg: any) => {
      if (msg.type === 'home_stock/session/current') return Promise.resolve({ store: null });
      if (msg.type === 'home_stock/lookup') return Promise.resolve(RESULTAT_FACTICE);
      return Promise.resolve({ id: 1 });
    });
    const { element, fiche } = await monterSurLaFiche(hass);

    fiche.dispatchEvent(new CustomEvent('article-pret', {
      detail: { articleId: 42, quantite: 500, prixUnitaire: 0.005, mode: 'panier', offDroppedFields: [] },
      bubbles: true, composed: true,
    }));
    await laisserPasserLesMicrotaches();

    expect((element as any).enAttente).toBe(0);
    expect(hass.connection.sendMessagePromise).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'home_stock/session/add_line', article_id: 42 }));
  });
});
