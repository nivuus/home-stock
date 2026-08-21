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


describe('panneau : un refus du serveur sur une écriture en file remonte en français', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    document.body.innerHTML = '';
  });

  it('affiche le message du serveur et le retire au clic sur OK', async () => {
    const hass = hassAvecReponses((msg: any) => {
      if (msg.type === 'home_stock/session/current') return Promise.resolve(sessionOuverte('shopping', null));
      if (msg.type === 'home_stock/lookup') return Promise.resolve(RESULTAT_FACTICE);
      if (msg.type === 'home_stock/session/add_line') {
        return Promise.reject({ code: 'shopping_refused', message: 'Cette ligne est déjà rangée.' });
      }
      return Promise.resolve({});
    });
    const element = document.createElement('home-stock-panel') as HTMLElement & {
      hass: Hass; updateComplete: Promise<boolean>;
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
      detail: { articleId: 42, quantite: 500, prixUnitaire: 0.005, mode: 'panier', offDroppedFields: [] },
      bubbles: true, composed: true,
    }));
    await laisserPasserLesMicrotaches();
    await (element as any).updateComplete;

    const banniere = element.shadowRoot!.querySelector('.erreur-file');
    expect(banniere).not.toBeNull();
    expect(banniere!.textContent).toContain('Cette ligne est déjà rangée.');

    (element.shadowRoot!.querySelector('.fermer-erreur-file') as HTMLButtonElement).click();
    await (element as any).updateComplete;
    expect(element.shadowRoot!.querySelector('.erreur-file')).toBeNull();
  });
});

describe('panneau : quitter le rangement avec des articles autonomes en attente prévient d’abord', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    document.body.innerHTML = '';
    vi.restoreAllMocks();
  });

  async function monterSurLeRangement(): Promise<HTMLElement & { ecran: string; updateComplete: Promise<boolean> }> {
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
    await element.updateComplete;

    const fiche = element.shadowRoot!.querySelector('home-stock-fiche')!;
    fiche.dispatchEvent(new CustomEvent('article-pret', {
      detail: { articleId: 42, quantite: 500, prixUnitaire: 0.005, mode: 'rangement', offDroppedFields: [] },
      bubbles: true, composed: true,
    }));
    await laisserPasserLesMicrotaches();
    await element.updateComplete;
    expect(element.ecran).toBe('rangement');
    return element;
  }

  // Volontairement AUCUN test ici ne stub `window.confirm` : c'est
  // exactement ce que la popup native empêchait de vérifier. Là où les
  // popups système sont coupées (Fully Kiosk, et jsdom qui répond « Not
  // implemented »), `confirm()` rend `undefined` — un panneau qui en
  // dépendrait resterait bloqué sur l'écran de rangement sans le moindre
  // avertissement visible. Le remplacement est un geste à deux appuis, en
  // boutons, dans l'écran — le même que la suppression d'une ligne.

  it('arme un avertissement en boutons (pas de popup) au lieu de naviguer tout de suite', async () => {
    const element = await monterSurLeRangement();

    const boutonScanner = Array.from(element.shadowRoot!.querySelectorAll('.nav-bouton'))
      .find((b) => b.textContent?.includes('Scanner')) as HTMLButtonElement;
    boutonScanner.click();
    await element.updateComplete;

    // Toujours sur le rangement : le premier appui arme, il ne navigue pas.
    expect(element.ecran).toBe('rangement');
    expect(element.shadowRoot!.querySelector('.confirmation-quitter-rangement')).not.toBeNull();
    expect(element.shadowRoot!.querySelector('.confirmer-quitter')).not.toBeNull();
    expect(element.shadowRoot!.querySelector('.annuler-quitter')).not.toBeNull();
  });

  it('reste sur le rangement si l’utilisateur choisit « Rester ici »', async () => {
    const element = await monterSurLeRangement();

    (Array.from(element.shadowRoot!.querySelectorAll('.nav-bouton'))
      .find((b) => b.textContent?.includes('Scanner')) as HTMLButtonElement).click();
    await element.updateComplete;

    (element.shadowRoot!.querySelector('.annuler-quitter') as HTMLButtonElement).click();
    await element.updateComplete;

    expect(element.ecran).toBe('rangement');
    // L'avertissement lui-même a disparu : un appui sur « Scanner » sans
    // confirmer ne doit pas laisser une gâchette armée en silence.
    expect(element.shadowRoot!.querySelector('.confirmation-quitter-rangement')).toBeNull();
  });

  it('quitte le rangement quand l’utilisateur confirme « Quitter quand même »', async () => {
    const element = await monterSurLeRangement();

    (Array.from(element.shadowRoot!.querySelectorAll('.nav-bouton'))
      .find((b) => b.textContent?.includes('Scanner')) as HTMLButtonElement).click();
    await element.updateComplete;

    (element.shadowRoot!.querySelector('.confirmer-quitter') as HTMLButtonElement).click();
    await element.updateComplete;

    expect(element.ecran).toBe('scanner');
  });

  it('ne demande rien pour naviguer ailleurs quand rien n’est en attente', async () => {
    const hass = hassAvecReponses((msg: any) => {
      if (msg.type === 'home_stock/session/current') return Promise.resolve(sessionOuverte('shopping', 'Leclerc'));
      return Promise.resolve({});
    });
    const element = document.createElement('home-stock-panel') as HTMLElement & {
      hass: Hass; updateComplete: Promise<boolean>; ecran: string;
    };
    element.hass = hass;
    document.body.appendChild(element);
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    const boutonPanier = Array.from(element.shadowRoot!.querySelectorAll('.nav-bouton'))
      .find((b) => b.textContent?.includes('Panier')) as HTMLButtonElement;
    boutonPanier.click();
    await element.updateComplete;

    expect(element.ecran).toBe('panier');
    expect(element.shadowRoot!.querySelector('.confirmation-quitter-rangement')).toBeNull();
  });
});

describe('panneau : le catalogue et les réglages sont toujours atteignables', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    document.body.innerHTML = '';
  });

  function monter(hass: Hass) {
    const element = document.createElement('home-stock-panel') as HTMLElement & {
      hass: Hass; updateComplete: Promise<boolean>; ecran: string;
    };
    element.hass = hass;
    document.body.appendChild(element);
    return element;
  }

  it('le bouton « Catalogue » mène à <home-stock-catalogue>, avec connexion et file', async () => {
    const hass = hassAvecReponses((msg: any) => {
      if (msg.type === 'home_stock/session/current') return Promise.resolve(null);
      if (msg.type === 'home_stock/products/list') return Promise.resolve({ products: [] });
      if (msg.type === 'home_stock/aisles/list') return Promise.resolve({ aisles: [] });
      if (msg.type === 'home_stock/locations/list') return Promise.resolve({ locations: [] });
      if (msg.type === 'home_stock/batches/list') return Promise.resolve({ batches: [] });
      return Promise.resolve({});
    });
    const element = monter(hass);
    await laisserPasserLesMicrotaches();
    await (element as any).updateComplete;

    const bouton = Array.from(element.shadowRoot!.querySelectorAll('.nav-bouton'))
      .find((b) => b.textContent?.includes('Catalogue')) as HTMLButtonElement;
    expect(bouton).not.toBeUndefined();
    bouton.click();
    await (element as any).updateComplete;

    expect(element.ecran).toBe('catalogue');
    const catalogue = element.shadowRoot!.querySelector('home-stock-catalogue') as any;
    expect(catalogue).not.toBeNull();
    expect(catalogue.connexion).toBeDefined();
    expect(catalogue.file).toBeDefined();
  });

  it('le bouton « Réglages » mène à <home-stock-reglages>, avec connexion et file', async () => {
    const hass = hassAvecReponses((msg: any) => {
      if (msg.type === 'home_stock/session/current') return Promise.resolve(null);
      if (msg.type === 'home_stock/aisles/list') return Promise.resolve({ aisles: [] });
      if (msg.type === 'home_stock/locations/list') return Promise.resolve({ locations: [] });
      return Promise.resolve({});
    });
    const element = monter(hass);
    await laisserPasserLesMicrotaches();
    await (element as any).updateComplete;

    const bouton = Array.from(element.shadowRoot!.querySelectorAll('.nav-bouton'))
      .find((b) => b.textContent?.includes('Réglages')) as HTMLButtonElement;
    expect(bouton).not.toBeUndefined();
    bouton.click();
    await (element as any).updateComplete;

    expect(element.ecran).toBe('reglages');
    const reglages = element.shadowRoot!.querySelector('home-stock-reglages') as any;
    expect(reglages).not.toBeNull();
    expect(reglages.connexion).toBeDefined();
    expect(reglages.file).toBeDefined();
  });

  it('quitter un rangement en attente vers le catalogue prévient d’abord, comme vers tout autre écran', async () => {
    const hass = hassAvecReponses((msg: any) => {
      if (msg.type === 'home_stock/session/current') return Promise.resolve(null);
      if (msg.type === 'home_stock/lookup') return Promise.resolve(RESULTAT_FACTICE);
      if (msg.type === 'home_stock/locations/list') return Promise.resolve({ locations: [] });
      return Promise.resolve({});
    });
    const element = monter(hass);
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

    const boutonCatalogue = Array.from(element.shadowRoot!.querySelectorAll('.nav-bouton'))
      .find((b) => b.textContent?.includes('Catalogue')) as HTMLButtonElement;
    boutonCatalogue.click();
    await (element as any).updateComplete;

    expect(element.ecran).toBe('rangement');
    expect(element.shadowRoot!.querySelector('.confirmation-quitter-rangement')).not.toBeNull();
  });
});

describe('panneau : le journal et l’écran « manger »', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    document.body.innerHTML = '';
  });

  // Le brief de cette tâche renvoie à un « helper déjà présent dans ce
  // fichier » nommé `monterPanneau` — il n'existe pas ; chaque describe de
  // ce fichier définit son propre montage local (voir `monter` ci-dessus,
  // dans « le catalogue et les réglages »). Celui-ci en reprend le même
  // schéma : un hass dont `session/current` répond `null`, pour ne pas
  // dépendre d'une session de courses ouverte.
  async function monterPanneau() {
    const hass = hassAvecReponses((msg: any) => {
      if (msg.type === 'home_stock/session/current') return Promise.resolve(null);
      return Promise.resolve({});
    });
    const element = document.createElement('home-stock-panel') as HTMLElement & {
      hass: Hass; updateComplete: Promise<boolean>; ecran: string;
    };
    element.hass = hass;
    document.body.appendChild(element);
    await laisserPasserLesMicrotaches();
    await (element as any).updateComplete;
    return element as any;
  }

  it('expose le journal dans la navigation, mais pas « manger »', async () => {
    const panneau = await monterPanneau();
    const libelles = [...panneau.shadowRoot.querySelectorAll('.nav-bouton')]
      .map((b: Element) => b.textContent?.trim());
    expect(libelles).toContain('Journal');
    // « Manger » a besoin d'un produit : un bouton de navigation nu ouvrirait
    // un écran qui n'a rien à montrer.
    expect(libelles).not.toContain('Manger');
  });

  it('ouvre l’écran « manger » sur le produit qu’on lui désigne', async () => {
    const panneau = await monterPanneau();
    panneau.dispatchEvent(new CustomEvent('manger-produit',
      { detail: { product_id: 42 }, bubbles: true, composed: true }));
    await panneau.updateComplete;
    expect(panneau.ecran).toBe('consommation');
    expect(panneau.shadowRoot.querySelector('home-stock-consommation').productId).toBe(42);
  });

  it('revient au scanner quand une consommation est enregistrée', async () => {
    const panneau = await monterPanneau();
    panneau.ecran = 'consommation';
    await panneau.updateComplete;
    panneau.shadowRoot.querySelector('home-stock-consommation')
      ?.dispatchEvent(new CustomEvent('consommation-enregistree',
                                      { bubbles: true, composed: true }));
    await panneau.updateComplete;
    expect(panneau.ecran).toBe('scanner');
  });

  it('le bouton « Journal » mène à <home-stock-journal>, avec connexion', async () => {
    const hass = hassAvecReponses((msg: any) => {
      if (msg.type === 'home_stock/session/current') return Promise.resolve(null);
      if (msg.type === 'home_stock/journal/day') {
        return Promise.resolve({ food_day: '2026-08-21', start: '', end: '', entries: [],
          totals: { kcal: 0, cost: 0, waste_cost: 0, unvalued: 0 } });
      }
      if (msg.type === 'home_stock/journal/series') return Promise.resolve({ granularity: 'day', buckets: [] });
      return Promise.resolve({});
    });
    const element = document.createElement('home-stock-panel') as HTMLElement & {
      hass: Hass; updateComplete: Promise<boolean>; ecran: string;
    };
    element.hass = hass;
    document.body.appendChild(element);
    await laisserPasserLesMicrotaches();
    await (element as any).updateComplete;

    const bouton = Array.from(element.shadowRoot!.querySelectorAll('.nav-bouton'))
      .find((b: Element) => b.textContent?.includes('Journal')) as HTMLButtonElement;
    expect(bouton).not.toBeUndefined();
    bouton.click();
    await (element as any).updateComplete;

    expect(element.ecran).toBe('journal');
    const journal = element.shadowRoot!.querySelector('home-stock-journal') as any;
    expect(journal).not.toBeNull();
    expect(journal.connexion).toBeDefined();
  });

  it('quitter un rangement en attente vers « manger » prévient d’abord, comme vers tout autre écran', async () => {
    const hass = hassAvecReponses((msg: any) => {
      if (msg.type === 'home_stock/session/current') return Promise.resolve(null);
      if (msg.type === 'home_stock/lookup') return Promise.resolve(RESULTAT_FACTICE);
      if (msg.type === 'home_stock/locations/list') return Promise.resolve({ locations: [] });
      return Promise.resolve({});
    });
    const element = document.createElement('home-stock-panel') as HTMLElement & {
      hass: Hass; updateComplete: Promise<boolean>; ecran: string; shadowRoot: ShadowRoot;
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

    element.dispatchEvent(new CustomEvent('manger-produit',
      { detail: { product_id: 42 }, bubbles: true, composed: true }));
    await (element as any).updateComplete;

    expect(element.ecran).toBe('rangement');
    expect(element.shadowRoot!.querySelector('.confirmation-quitter-rangement')).not.toBeNull();
  });
});

/** Un serveur en mémoire qui se comporte comme le vrai : une seule session
 *  ouverte à la fois, `current` qui ne rend que les sessions `shopping` ou
 *  `to_store`, et une session qui se clôt d'elle-même quand toutes ses
 *  lignes sont rangées (voir `ShoppingService.store_line`). C'est ce qu'il
 *  faut pour éprouver le PARCOURS, pas seulement un écran isolé. */
function serveurDeCourses() {
  const magasins = ['Leclerc', 'Lidl'];
  const emplacements = [{ id: 3, name: 'Placard', kind: 'cupboard', position: 0 }];
  const lignes: any[] = [];
  let session: any = null;
  let prochainId = 1;
  const envoyes: any[] = [];

  const totaux = () => {
    const miennes = lignes.filter((l) => l.session_id === session.id);
    return {
      lines: miennes.length,
      pending: miennes.filter((l) => l.stored_at === null).length,
      total: Math.round(miennes.reduce((s, l) => s + l.quantity * (l.unit_price ?? 0), 0) * 100) / 100,
    };
  };

  const repondre = async (msg: any): Promise<unknown> => {
    envoyes.push(msg);
    switch (msg.type) {
      case 'home_stock/stores/list':
        return { stores: magasins };
      case 'home_stock/locations/list':
        return { locations: emplacements };
      case 'home_stock/lookup':
        return RESULTAT_FACTICE;
      case 'home_stock/session/current':
        if (!session || session.state === 'done') return null;
        return {
          session, lines: lignes.filter((l) => l.session_id === session.id),
          totals: totaux(), stores: magasins,
        };
      case 'home_stock/session/start':
        if (session && session.state === 'shopping') {
          return Promise.reject({ code: 'shopping_refused', message: 'Une session de courses est déjà ouverte.' });
        }
        session = { id: prochainId++, state: 'shopping', store: msg.store ?? null,
                    started_at: '2026-08-19T10:00:00', closed_at: null };
        return session;
      case 'home_stock/session/add_line': {
        const ligne = { ...LIGNE_SESSION, id: 100 + lignes.length, session_id: session.id,
                        article_id: msg.article_id, quantity: msg.quantity,
                        unit_price: msg.unit_price ?? null, stored_at: null, batch_id: null };
        lignes.push(ligne);
        return ligne;
      }
      case 'home_stock/session/checkout':
        session = { ...session, state: 'to_store' };
        return session;
      case 'home_stock/session/store_line': {
        const ligne = lignes.find((l) => l.id === msg.line_id);
        ligne.stored_at = '2026-08-19T18:00:00';
        ligne.batch_id = 7;
        if (totaux().pending === 0) {
          session = { ...session, state: 'done', closed_at: '2026-08-19T18:00:00' };
        }
        return { line_id: msg.line_id, batch_id: 7, already_stored: false };
      }
      case 'home_stock/session/close':
        if (!session || session.state === 'done') {
          return Promise.reject({ code: 'shopping_refused', message: 'Aucune session de courses en cours.' });
        }
        session = { ...session, state: 'done', closed_at: '2026-08-19T18:00:00' };
        return session;
      default:
        return {};
    }
  };

  return { repondre, envoyes, lignes, etat: () => session };
}

describe('panneau : le parcours complet d’une session de courses', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    document.body.innerHTML = '';
  });

  it('ouvrir, scanner, panier, caisse, ranger, clore — tout depuis le panneau assemblé', async () => {
    const serveur = serveurDeCourses();
    let pousserLeResume: () => void = () => {};
    const hass = {
      connection: {
        sendMessagePromise: vi.fn().mockImplementation(serveur.repondre),
        subscribeMessage: vi.fn().mockImplementation((rappel: () => void) => {
          pousserLeResume = rappel;
          return Promise.resolve(() => {});
        }),
      },
      language: 'fr',
    } as unknown as Hass;

    const element = document.createElement('home-stock-panel') as HTMLElement & {
      hass: Hass; ecran: string; updateComplete: Promise<boolean>;
    };
    element.hass = hass;
    document.body.appendChild(element);
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    const nav = (texte: string) => Array.from(element.shadowRoot!.querySelectorAll('.nav-bouton'))
      .find((b) => b.textContent?.includes(texte)) as HTMLButtonElement | undefined;
    const dans = (nom: string, selecteur: string) => element.shadowRoot!
      .querySelector(nom)!.shadowRoot!.querySelector(selecteur) as HTMLElement | null;
    const tous = (nom: string, selecteur: string) => Array.from(element.shadowRoot!
      .querySelector(nom)!.shadowRoot!.querySelectorAll(selecteur)) as HTMLElement[];
    const reglerTout = async () => {
      await laisserPasserLesMicrotaches();
      await element.updateComplete;
      for (const enfant of Array.from(element.shadowRoot!.children)) {
        if ((enfant as any).updateComplete) await (enfant as any).updateComplete;
      }
      await laisserPasserLesMicrotaches();
      await element.updateComplete;
    };

    // --- 1. ouvrir la session, magasin choisi en pastille -------------------
    expect(element.ecran).toBe('scanner');
    nav('Courses')!.click();
    await reglerTout();

    const pastilles = tous('home-stock-session', '.pastille');
    expect(pastilles.map((p) => p.textContent!.trim())).toEqual(['Leclerc', 'Lidl']);
    pastilles[0].click();
    await reglerTout();
    dans('home-stock-session', '.ouvrir-session')!.click();
    await reglerTout();

    expect(serveur.envoyes.some((m) => m.type === 'home_stock/session/start' && m.store === 'Leclerc'))
      .toBe(true);
    // Une session ouverte n'a qu'un but : scanner. Le panneau y renvoie.
    expect(element.ecran).toBe('scanner');
    expect(dans('home-stock-scanner', '.session-banniere')!.textContent).toContain('Leclerc');

    // --- 2. scanner deux articles, qui rejoignent le panier ----------------
    for (const articleId of [42, 43]) {
      element.shadowRoot!.querySelector('home-stock-scanner')!.dispatchEvent(
        new CustomEvent('code-lu', { detail: { code: '3229820129488' }, bubbles: true, composed: true }));
      await reglerTout();
      const fiche = element.shadowRoot!.querySelector('home-stock-fiche') as any;
      expect(fiche.mode).toBe('panier');
      fiche.dispatchEvent(new CustomEvent('article-pret', {
        detail: { articleId, quantite: 500, prixUnitaire: 0.005, mode: 'panier', offDroppedFields: [] },
        bubbles: true, composed: true,
      }));
      await reglerTout();
    }
    expect(serveur.lignes).toHaveLength(2);

    // Le coordinateur pousse son résumé après une écriture : c'est ce signal
    // qui fait relire `session/current` au panneau.
    pousserLeResume();
    await reglerTout();

    // --- 3. le panier, puis la caisse --------------------------------------
    nav('Panier')!.click();
    await reglerTout();
    expect(tous('home-stock-panier', '.ligne')).toHaveLength(2);

    dans('home-stock-panier', '.checkout')!.click();
    await reglerTout();
    pousserLeResume();
    await reglerTout();
    expect(serveur.etat().state).toBe('to_store');

    // --- 4. ranger une ligne ------------------------------------------------
    nav('Ranger')!.click();
    await reglerTout();
    expect(tous('home-stock-rangement', '.ligne')).toHaveLength(2);

    tous('home-stock-rangement', '.raccourci-dlc')[0].click();
    await reglerTout();
    pousserLeResume();
    await reglerTout();
    expect(serveur.lignes.filter((l) => l.stored_at !== null)).toHaveLength(1);

    // --- 5. clore le reste, en deux appuis ---------------------------------
    nav('Courses')!.click();
    await reglerTout();
    expect(dans('home-stock-session', '.restantes')!.textContent).toContain('1 ligne');

    dans('home-stock-session', '.clore-session')!.click();
    await reglerTout();
    // Un seul appui n'a rien clos : c'est un geste destructif.
    expect(serveur.etat().state).toBe('to_store');

    dans('home-stock-session', '.confirmer-cloture')!.click();
    await reglerTout();

    expect(serveur.etat().state).toBe('done');
    expect(element.ecran).toBe('scanner');
    expect(dans('home-stock-scanner', '.session-banniere')).toBeNull();

    // Et le voyage suivant peut commencer : plus rien ne bloque.
    nav('Courses')!.click();
    await reglerTout();
    expect(dans('home-stock-session', '.ouvrir-session')).not.toBeNull();
  });
});
