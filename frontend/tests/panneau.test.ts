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
  product: { id: 9, name: 'Muesli', base_unit: 'g', default_location_id: 3, default_shelf_life_days: 10 },
  off: null, off_raw: null, off_source: null, candidates: [], preselected_product_id: null,
  price: { price_per_base_unit: 0.004, source: 'last_known', store: null },
  conversion_offer: null, throttled: false, timed_out: false,
};

/** Ce que `home_stock/session/current` répond réellement (voir
 *  `ShoppingService.current`, Task 13) : jamais `{store}` seul — l'enveloppe
 *  complète, ou `null`. */
function sessionOuverte(etat: 'shopping' | 'to_store', store: string | null, lignes: any[] = []) {
  const total = lignes.reduce((s, l) => s + l.quantity * (l.unit_price ?? 0), 0);
  return {
    session: { id: 1, state: etat, store, started_at: '2026-08-19T10:00:00', closed_at: null },
    lines: lignes,
    totals: {
      lines: lignes.length,
      pending: lignes.filter((l) => l.stored_at === null).length,
      total: Math.round(total * 100) / 100,
    },
    stores: store ? [store] : [],
  };
}

const LIGNE_SESSION = {
  id: 100, article_id: 42, quantity: 500, unit_price: 0.005, stored_at: null, batch_id: null,
  product_id: 9, product_name: 'Muesli', base_unit: 'g', default_location_id: 3,
  default_shelf_life_days: 10, days_after_opening: null, article_label: 'Muesli', brand: null,
  image: null, net_quantity: 500, aisle_name: 'Petit-déjeuner', aisle_position: 1,
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

  it('appelle home_stock/lookup puis affiche la fiche avec mode panier quand une session « shopping » est ouverte',
     async () => {
    const hass = hassAvecReponses((msg: any) => {
      if (msg.type === 'home_stock/session/current') return Promise.resolve(sessionOuverte('shopping', 'Leclerc'));
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

  it('route vers la fiche en mode rangement quand la session est « to_store » (passée en caisse)', async () => {
    // Le panier peut se vider (checkout) pendant qu'on est encore devant un
    // rayon : une session « to_store » n'est plus une session de courses
    // ouverte, un nouveau scan ne doit donc plus rejoindre le panier.
    const hass = hassAvecReponses((msg: any) => {
      if (msg.type === 'home_stock/session/current') {
        return Promise.resolve(sessionOuverte('to_store', 'Leclerc', [{ ...LIGNE_SESSION }]));
      }
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
      if (msg.type === 'home_stock/session/current') return Promise.resolve(sessionOuverte('shopping', null));
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
      if (msg.type === 'home_stock/session/current') return Promise.resolve(sessionOuverte('shopping', null));
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

describe('panneau : un article rapporté seul route directement au rangement', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    document.body.innerHTML = '';
  });

  it('bascule sur l’écran de rangement avec une ligne autonome, plutôt que de garder la fiche', async () => {
    const hass = hassAvecReponses((msg: any) => {
      if (msg.type === 'home_stock/session/current') return Promise.resolve(null); // pas de session : rangement
      if (msg.type === 'home_stock/lookup') return Promise.resolve(RESULTAT_FACTICE);
      if (msg.type === 'home_stock/locations/list') return Promise.resolve({ locations: [] });
      return Promise.resolve({});
    });
    const element = document.createElement('home-stock-panel') as HTMLElement & {
      hass: Hass; updateComplete: Promise<boolean>; ecran: string;
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
    fiche.dispatchEvent(new CustomEvent('article-pret', {
      detail: { articleId: 42, quantite: 500, prixUnitaire: 0.005, mode: 'rangement', offDroppedFields: [] },
      bubbles: true, composed: true,
    }));
    await laisserPasserLesMicrotaches();
    await (element as any).updateComplete;

    expect(element.ecran).toBe('rangement');
    const rangement = element.shadowRoot!.querySelector('home-stock-rangement') as any;
    expect(rangement).not.toBeNull();
    expect(rangement.lignes).toHaveLength(1);
    expect(rangement.lignes[0]).toMatchObject({
      source: 'autonome', article_id: 42, quantity: 500, unit_price: 0.005,
      base_unit: 'g', default_location_id: 3, default_shelf_life_days: 10,
    });
  });
});

describe('panneau : parcours complet, du scan au lot rangé', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    document.body.innerHTML = '';
  });

  it('scanne, ajoute au panier, passe en caisse puis range la ligne via un raccourci de DLC', async () => {
    let etatSession = sessionOuverte('shopping', 'Leclerc', []);
    const appels: any[] = [];
    // Le vrai serveur pousse un événement à chaque écriture (rafraîchissement
    // du coordinator) : le panneau ré-interroge `session/current` sur ce
    // signal. Le mock `subscribeMessage` ne pousse rien tout seul — le test
    // simule ce signal explicitement après chaque écriture, comme le ferait
    // le serveur.
    let rappelAbonnement: (() => void) | undefined;
    const hass: Hass & { connection: { sendMessagePromise: ReturnType<typeof vi.fn> } } = {
      connection: {
        sendMessagePromise: vi.fn().mockImplementation((msg: any) => {
          appels.push(msg);
          if (msg.type === 'home_stock/session/current') return Promise.resolve(etatSession);
          if (msg.type === 'home_stock/lookup') return Promise.resolve(RESULTAT_FACTICE);
          if (msg.type === 'home_stock/locations/list') {
            return Promise.resolve({ locations: [{ id: 3, name: 'Placard', kind: 'cupboard', position: 0 }] });
          }
          if (msg.type === 'home_stock/session/add_line') {
            etatSession = sessionOuverte('shopping', 'Leclerc', [{ ...LIGNE_SESSION }]);
            return Promise.resolve({ ...LIGNE_SESSION });
          }
          if (msg.type === 'home_stock/session/checkout') {
            etatSession = sessionOuverte('to_store', 'Leclerc', [{ ...LIGNE_SESSION }]);
            return Promise.resolve({});
          }
          if (msg.type === 'home_stock/session/store_line') {
            etatSession = sessionOuverte('to_store', 'Leclerc',
              [{ ...LIGNE_SESSION, stored_at: '2026-08-19', batch_id: 7 }]);
            return Promise.resolve({ line_id: LIGNE_SESSION.id, batch_id: 7, already_stored: false });
          }
          return Promise.resolve({});
        }),
        subscribeMessage: vi.fn().mockImplementation((rappel: () => void) => {
          rappelAbonnement = rappel;
          return Promise.resolve(() => {});
        }),
      },
      language: 'fr',
    } as unknown as Hass & { connection: { sendMessagePromise: ReturnType<typeof vi.fn> } };

    const element = document.createElement('home-stock-panel') as HTMLElement & {
      hass: Hass; updateComplete: Promise<boolean>; ecran: string;
    };
    element.hass = hass;
    document.body.appendChild(element);
    await laisserPasserLesMicrotaches();

    // 1. Scan → fiche en mode panier.
    const scanner = element.shadowRoot!.querySelector('home-stock-scanner')!;
    scanner.dispatchEvent(new CustomEvent('code-lu', {
      detail: { code: '3229820129488' }, bubbles: true, composed: true,
    }));
    await laisserPasserLesMicrotaches();
    await (element as any).updateComplete;
    const fiche = element.shadowRoot!.querySelector('home-stock-fiche')!;
    expect((fiche as any).mode).toBe('panier');

    // 2. Confirmation → ajouté au panier (file), retour scanner.
    fiche.dispatchEvent(new CustomEvent('article-pret', {
      detail: { articleId: 42, quantite: 500, prixUnitaire: 0.005, mode: 'panier', offDroppedFields: [] },
      bubbles: true, composed: true,
    }));
    await laisserPasserLesMicrotaches();
    await (element as any).updateComplete;
    expect(element.ecran).toBe('scanner');

    // Le serveur a traité add_line et rafraîchi le coordinator : le panneau
    // ré-interroge session/current sur ce signal.
    rappelAbonnement!();
    await laisserPasserLesMicrotaches();
    await (element as any).updateComplete;

    // 3. Le bouton de navigation « Panier » doit apparaître (session shopping,
    // au moins une ligne) : on l'utilise pour aller voir le panier.
    const boutonPanier = Array.from(element.shadowRoot!.querySelectorAll('.nav-bouton'))
      .find((b) => b.textContent?.includes('Panier')) as HTMLButtonElement | undefined;
    expect(boutonPanier).not.toBeUndefined();
    boutonPanier!.click();
    await (element as any).updateComplete;
    expect(element.ecran).toBe('panier');
    const panier = element.shadowRoot!.querySelector('home-stock-panier') as any;
    expect(panier.donnees.lines).toHaveLength(1);
    expect(panier.donnees.totals.total).toBe(etatSession.totals.total);

    // 4. Passage en caisse depuis l'écran panier.
    const boutonCaisse = panier.shadowRoot.querySelector('.checkout') as HTMLButtonElement;
    boutonCaisse.click();
    await laisserPasserLesMicrotaches();
    await (element as any).updateComplete;
    expect(appels.some((m) => m.type === 'home_stock/session/checkout')).toBe(true);

    rappelAbonnement!();
    await laisserPasserLesMicrotaches();
    await (element as any).updateComplete;

    // 5. Le bouton « Ranger » doit apparaître (session to_store, ligne en
    // attente) : on y va.
    const boutonRanger = Array.from(element.shadowRoot!.querySelectorAll('.nav-bouton'))
      .find((b) => b.textContent?.includes('Ranger')) as HTMLButtonElement | undefined;
    expect(boutonRanger).not.toBeUndefined();
    boutonRanger!.click();
    await laisserPasserLesMicrotaches();
    await (element as any).updateComplete;
    expect(element.ecran).toBe('rangement');

    const rangement = element.shadowRoot!.querySelector('home-stock-rangement') as any;
    await laisserPasserLesMicrotaches();
    await (element as any).updateComplete;

    // 6. Un appui sur un raccourci de DLC range la ligne : store_line est
    // appelé avec le bon emplacement et la bonne date.
    const boutonRaccourci = rangement.shadowRoot.querySelector('.raccourci-dlc') as HTMLButtonElement;
    boutonRaccourci.click();
    await laisserPasserLesMicrotaches();

    expect(appels.some((m) => m.type === 'home_stock/session/store_line'
      && m.line_id === LIGNE_SESSION.id && m.location_id === 3)).toBe(true);

    // 7. Le rafraîchissement (abonnement) fait redescendre une session sans
    // ligne en attente (stored_at posé) : le panneau revient au scanner.
    rappelAbonnement!();
    await laisserPasserLesMicrotaches();
    await (element as any).updateComplete;
    await laisserPasserLesMicrotaches();
    await (element as any).updateComplete;
    expect(element.ecran).toBe('scanner');
  });
});
