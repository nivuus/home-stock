import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import '../src/panneau';
import type { Hass } from '../src/connexion';

/** Attend que les microtâches en attente (les .then() de connectedCallback,
 *  notamment celui de l'abonnement) se soient exécutées. */
function laisserPasserLesMicrotaches(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

/** --- piloter la NOUVELLE coquille -----------------------------------------
 *
 *  La barre ne porte plus un bouton par écran : quatre familles, chacune vers
 *  SA racine, et tout le reste s'atteint par son URL. Ces trois fonctions sont
 *  les seuls gestes réellement à la disposition d'un utilisateur — on ne pose
 *  JAMAIS `element.ecran` à la main pour naviguer, ce serait éprouver un
 *  chemin que personne n'emprunte. */
async function barreDe(element: any): Promise<any> {
  await element.updateComplete;
  const barre = element.shadowRoot!.querySelector('hs-nav-bar');
  expect(barre, 'la barre de navigation').not.toBeNull();
  await barre.updateComplete;
  return barre;
}

async function cliquerFamille(element: any, famille: string): Promise<void> {
  const barre = await barreDe(element);
  const bouton = barre.shadowRoot!.querySelector(`[data-family="${famille}"]`) as HTMLButtonElement;
  expect(bouton, `famille ${famille}`).not.toBeNull();
  bouton.click();
}

/** Home Assistant repasse la route au panneau : c'est par là qu'arrivent
 *  aussi le bouton Retour du navigateur et le geste système d'Android. */
function allerA(element: any, chemin: string): void {
  element.route = { prefix: '/home-stock', path: chemin };
}

async function famillesAffichees(element: any): Promise<string[]> {
  const barre = await barreDe(element);
  return Array.from(barre.shadowRoot!.querySelectorAll('.destination'))
    .map((b: any) => b.querySelector('span').textContent.trim());
}

/** Le compte affiché en pastille sur une famille, ou `null` s'il n'y en a pas. */
async function pastilleFamille(element: any, famille: string): Promise<string | null> {
  const barre = await barreDe(element);
  const bouton = barre.shadowRoot!.querySelector(`[data-family="${famille}"]`);
  return bouton?.querySelector('.badge')?.textContent?.trim() ?? null;
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

/** Une liste de courses vide, mais BIEN FORMÉE : `home-stock-liste` se charge
 *  toute seule au montage, et un `{}` la fait exploser au rendu. */
const LISTE_VIDE = {
  items: [], store_id: null, store_name: null,
  estimate: { amount: 0, confidence: 0, priced: 0, total: 0 },
};

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

    // 3. La barre n'a plus de bouton « Panier » : la famille « Courses » porte
    // le compte en pastille, et le panier s'ouvre par son URL.
    expect(await pastilleFamille(element, 'shopping')).toBe('1');
    allerA(element, '/cart');
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

    // 5. Une ligne reste à ranger : la pastille de « Courses » le dit, et le
    // rangement s'ouvre par son URL.
    expect(await pastilleFamille(element, 'shopping')).toBe('1');
    allerA(element, '/put-away');
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

    // La bannière a déménagé dans l'en-tête (Task 10) : même message du
    // serveur, même acquittement, un cran plus bas dans l'arbre.
    const entete = element.shadowRoot!.querySelector('hs-header') as any;
    await entete.updateComplete;
    const banniere = entete.shadowRoot!.querySelector('.erreur');
    expect(banniere).not.toBeNull();
    expect(banniere!.textContent).toContain('Cette ligne est déjà rangée.');

    (entete.shadowRoot!.querySelector('.fermer-erreur') as HTMLButtonElement).click();
    await (element as any).updateComplete;
    await entete.updateComplete;
    expect(entete.shadowRoot!.querySelector('.erreur')).toBeNull();
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
      // Quitter le rangement mène désormais à la LISTE (racine de la famille
      // « Courses »), qui se charge toute seule au montage.
      if (msg.type === 'home_stock/list/items') return Promise.resolve(LISTE_VIDE);
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

    await cliquerFamille(element, 'shopping');
    await element.updateComplete;

    // Toujours sur le rangement : le premier appui arme, il ne navigue pas.
    expect(element.ecran).toBe('rangement');
    expect(element.shadowRoot!.querySelector('.confirmation-quitter-rangement')).not.toBeNull();
    expect(element.shadowRoot!.querySelector('.confirmer-quitter')).not.toBeNull();
    expect(element.shadowRoot!.querySelector('.annuler-quitter')).not.toBeNull();
  });

  it('reste sur le rangement si l’utilisateur choisit « Rester ici »', async () => {
    const element = await monterSurLeRangement();

    await cliquerFamille(element, 'shopping');
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

    await cliquerFamille(element, 'shopping');
    await element.updateComplete;

    (element.shadowRoot!.querySelector('.confirmer-quitter') as HTMLButtonElement).click();
    await element.updateComplete;

    // La famille « Courses » mène à sa racine, la liste — plus au scanner,
    // qui n'est plus une destination de la barre.
    expect(element.ecran).toBe('liste');
  });

  it('ne demande rien pour naviguer ailleurs quand rien n’est en attente', async () => {
    const hass = hassAvecReponses((msg: any) => {
      if (msg.type === 'home_stock/session/current') return Promise.resolve(sessionOuverte('shopping', 'Leclerc'));
      if (msg.type === 'home_stock/list/items') return Promise.resolve(LISTE_VIDE);
      return Promise.resolve({});
    });
    const element = document.createElement('home-stock-panel') as HTMLElement & {
      hass: Hass; updateComplete: Promise<boolean>; ecran: string;
    };
    element.hass = hass;
    document.body.appendChild(element);
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    await cliquerFamille(element, 'shopping');
    await element.updateComplete;

    expect(element.ecran).toBe('liste');
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

  it('la famille « Stock » mène à <home-stock-catalogue>, avec connexion et file', async () => {
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

    await cliquerFamille(element, 'stock');
    await (element as any).updateComplete;

    // « Catalogue » est la racine de la famille « Stock » : c'est elle que la
    // barre atteint.
    expect(element.ecran).toBe('catalogue');
    const catalogue = element.shadowRoot!.querySelector('home-stock-catalogue') as any;
    expect(catalogue).not.toBeNull();
    expect(catalogue.connexion).toBeDefined();
    expect(catalogue.file).toBeDefined();
  });

  it('l’URL /settings mène à <home-stock-reglages>, avec connexion et file', async () => {
    const hass = hassAvecReponses((msg: any) => {
      if (msg.type === 'home_stock/session/current') return Promise.resolve(null);
      if (msg.type === 'home_stock/aisles/list') return Promise.resolve({ aisles: [] });
      if (msg.type === 'home_stock/locations/list') return Promise.resolve({ locations: [] });
      return Promise.resolve({});
    });
    const element = monter(hass);
    await laisserPasserLesMicrotaches();
    await (element as any).updateComplete;

    // « Réglages » n'est pas la racine de sa famille : on y va par son URL,
    // comme le ferait un lien ou le bouton Retour du navigateur.
    allerA(element, '/settings');
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

    await cliquerFamille(element, 'stock');
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
      // La liste est la racine de « Courses » : toute retombée de route y
      // atterrit, et elle se charge toute seule au montage.
      if (msg.type === 'home_stock/list/items') {
        return Promise.resolve({ items: [], store_id: null, store_name: null,
          estimate: { amount: 0, confidence: 0, priced: 0, total: 0 } });
      }
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

  it('expose le journal par son URL, mais « manger » par aucune destination', async () => {
    const panneau = await monterPanneau();
    // La barre ne porte que quatre familles : ni « Journal » ni « Manger »
    // n'y figurent en propre.
    expect(await famillesAffichees(panneau)).not.toContain('Journal');
    // « Manger » a besoin d'un produit : aucune destination nue n'y mène,
    // l'écran n'aurait rien à montrer. Son segment EXIGE l'identifiant.
    allerA(panneau, '/eat');
    await panneau.updateComplete;
    expect(panneau.ecran).toBe('liste');
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

  it('l’URL /log mène à <home-stock-journal>, avec connexion', async () => {
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

    allerA(element, '/log');
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
  // Depuis le lot 4, `home_stock/stores/list` rend des LIGNES : le panneau
  // envoie `store_id` à la place d'une chaîne quand on touche une pastille.
  const magasins = [
    { id: 1, name: 'Leclerc', position: 0, active: 1, observed_sessions: 0, last_seen: null },
    { id: 2, name: 'Lidl', position: 1, active: 1, observed_sessions: 0, last_seen: null },
  ];
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
        // Comme le service réel : `store_id` prime, et c'est le nom du
        // magasin trouvé qui est écrit sur la session.
        session = {
          id: prochainId++, state: 'shopping',
          store: msg.store_id
            ? magasins.find((m) => m.id === msg.store_id)?.name ?? null
            : msg.store ?? null,
          store_id: msg.store_id ?? null,
          started_at: '2026-08-19T10:00:00', closed_at: null,
        };
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

    const dans = (nom: string, selecteur: string) => element.shadowRoot!
      .querySelector(nom)!.shadowRoot!.querySelector(selecteur) as HTMLElement | null;
    const tous = (nom: string, selecteur: string) => Array.from(element.shadowRoot!
      .querySelector(nom)!.shadowRoot!.querySelectorAll(selecteur)) as HTMLElement[];
    const reglerTout = async () => {
      await laisserPasserLesMicrotaches();
      await element.updateComplete;
      // La coquille interpose une div : les écrans ne sont plus des enfants
      // DIRECTS du shadow root, il faut descendre.
      for (const enfant of Array.from(element.shadowRoot!.querySelectorAll('*'))) {
        if ((enfant as any).updateComplete) await (enfant as any).updateComplete;
      }
      await laisserPasserLesMicrotaches();
      await element.updateComplete;
    };

    // --- 1. ouvrir la session, magasin choisi en pastille -------------------
    expect(element.ecran).toBe('scanner');
    allerA(element, '/shopping');
    await reglerTout();

    const pastilles = tous('home-stock-session', '.pastille');
    expect(pastilles.map((p) => p.textContent!.trim())).toEqual(['Leclerc', 'Lidl']);
    pastilles[0].click();
    await reglerTout();
    dans('home-stock-session', '.ouvrir-session')!.click();
    await reglerTout();

    expect(serveur.envoyes.some((m) => m.type === 'home_stock/session/start' && m.store_id === 1))
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
    allerA(element, '/cart');
    await reglerTout();
    expect(tous('home-stock-panier', '.ligne')).toHaveLength(2);

    dans('home-stock-panier', '.checkout')!.click();
    await reglerTout();
    pousserLeResume();
    await reglerTout();
    expect(serveur.etat().state).toBe('to_store');

    // --- 4. ranger une ligne ------------------------------------------------
    allerA(element, '/put-away');
    await reglerTout();
    expect(tous('home-stock-rangement', '.ligne')).toHaveLength(2);

    tous('home-stock-rangement', '.raccourci-dlc')[0].click();
    await reglerTout();
    pousserLeResume();
    await reglerTout();
    expect(serveur.lignes.filter((l) => l.stored_at !== null)).toHaveLength(1);

    // --- 5. clore le reste, en deux appuis ---------------------------------
    allerA(element, '/shopping');
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
    allerA(element, '/shopping');
    await reglerTout();
    expect(dans('home-stock-session', '.ouvrir-session')).not.toBeNull();
  });
});

/** Lot 3 — les points d'entrée FONT PARTIE du livrable.
 *
 *  Sans eux, les écrans des tâches 18 à 20 sont des composants que rien
 *  n'ouvre : exactement le défaut qui a échappé aux dix-sept revues du lot 1,
 *  où `session/start` n'était appelé par personne et emportait avec lui le
 *  panier, deux capteurs et tout le parcours en magasin.
 */
describe('<home-stock-panel> — navigation du lot 3', () => {
  beforeEach(() => { document.body.innerHTML = ''; });
  afterEach(() => { document.body.innerHTML = ''; });

  function monterPanneau() {
    const hass = hassAvecReponses((msg: any) => {
      // L'écran « rangement » charge ses emplacements dès qu'il est monté :
      // sans cette réponse il rend `undefined.map` et pollue le run d'erreurs
      // qui n'ont rien à voir avec la navigation testée ici.
      if (msg.type === 'home_stock/locations/list') return Promise.resolve({ locations: [] });
      if (msg.type === 'home_stock/recipes/list') return Promise.resolve({ recipes: [] });
      if (msg.type === 'home_stock/meals/list') return Promise.resolve({ meals: [] });
      if (msg.type === 'home_stock/recipe/get') {
        return Promise.resolve({
          recipe: { id: 4, name: 'Gratin', servings: 2, total_minutes: null,
                    utensils: null, summary: null, image_url: null,
                    language: 'fr', needs_review: 0 },
          steps: [], ingredients: [],
        });
      }
      if (msg.type === 'home_stock/meal/preview') {
        return Promise.resolve({
          meal_id: 12, day: '2026-08-21', slot_key: 'dinner', recipe: null,
          servings: 1, factor: 1, lines: [], by_hand: [], dish: null,
          blocking: [],
        });
      }
      return Promise.resolve({});
    });
    const element = document.createElement('home-stock-panel') as any;
    element.hass = hass;
    document.body.appendChild(element);
    return element;
  }

  async function stabiliser(element: any) {
    await laisserPasserLesMicrotaches();
    await element.updateComplete;
    await element.updateComplete;
  }

  it('affiche la famille « Cuisine », et ses deux écrans sont atteignables', async () => {
    const element = monterPanneau();
    await stabiliser(element);
    expect(await famillesAffichees(element)).toContain('Cuisine');
    // Le planning est la RACINE de la famille : la barre y mène.
    await cliquerFamille(element, 'kitchen');
    await stabiliser(element);
    expect(element.ecran).toBe('planning');
    // Les recettes n'en sont pas la racine : leur URL, comme un lien.
    allerA(element, '/recipes');
    await stabiliser(element);
    expect(element.ecran).toBe('recettes');
  });

  it('n’affiche que les quatre familles, jamais un bouton par écran', async () => {
    // La vue cuisine et la validation s'ouvrent depuis une liste ou depuis le
    // planning, comme `fiche` et `consommation` au lot 2 — et depuis le lot 7,
    // AUCUN écran n'a plus son propre bouton : la barre ne dit que la famille.
    const element = monterPanneau();
    await stabiliser(element);
    expect(await famillesAffichees(element))
      .toEqual(['Courses', 'Stock', 'Cuisine', 'Maison']);
  });

  it('ouvre l’écran Recettes par son URL', async () => {
    const element = monterPanneau();
    await stabiliser(element);
    allerA(element, '/recipes');
    await stabiliser(element);
    expect(element.shadowRoot.querySelector('home-stock-recettes')).not.toBeNull();
  });

  it('ouvre le planning au clic sur sa famille', async () => {
    const element = monterPanneau();
    await stabiliser(element);
    await cliquerFamille(element, 'kitchen');
    await stabiliser(element);
    expect(element.shadowRoot.querySelector('home-stock-planning')).not.toBeNull();
  });

  it('ouvre la vue cuisine sur « recette-ouverte » et retient l’identifiant',
     async () => {
    const element = monterPanneau();
    await stabiliser(element);
    allerA(element, '/recipes');
    await stabiliser(element);

    element.shadowRoot.querySelector('home-stock-recettes')!.dispatchEvent(
      new CustomEvent('recette-ouverte', {
        detail: { recipe_id: 4 }, bubbles: true, composed: true }));
    await stabiliser(element);

    expect(element.recetteOuverte).toBe(4);
    expect(element.shadowRoot.querySelector('home-stock-recette')).not.toBeNull();
  });

  it('n’ouvre pas la vue cuisine sans recetteOuverte', async () => {
    const element = monterPanneau();
    await stabiliser(element);
    element.ecran = 'recette';
    await stabiliser(element);
    expect(element.shadowRoot.querySelector('home-stock-recette')).toBeNull();
    expect(element.shadowRoot.querySelector('home-stock-scanner')).not.toBeNull();
  });

  it('ouvre la validation sur « valider-repas »', async () => {
    const element = monterPanneau();
    await stabiliser(element);
    await cliquerFamille(element, 'kitchen');
    await stabiliser(element);

    element.shadowRoot.querySelector('home-stock-planning')!.dispatchEvent(
      new CustomEvent('valider-repas', {
        detail: { meal_id: 12 }, bubbles: true, composed: true }));
    await stabiliser(element);

    expect(element.repasAValider).toBe(12);
    expect(element.shadowRoot.querySelector('home-stock-validation')).not.toBeNull();
  });

  it('revient au planning après « repas-valide »', async () => {
    const element = monterPanneau();
    await stabiliser(element);
    // Par l'URL, comme un lien vers le repas à valider : elle pose l'écran ET
    // son identifiant.
    allerA(element, '/validate/12');
    await stabiliser(element);
    expect(element.repasAValider).toBe(12);

    element.shadowRoot.querySelector('home-stock-validation')!.dispatchEvent(
      new CustomEvent('repas-valide', {
        detail: { meal_id: 12 }, bubbles: true, composed: true }));
    await stabiliser(element);

    expect(element.ecran).toBe('planning');
    expect(element.repasAValider).toBeNull();
  });

  // Les quatre racines de famille : les SEULES cibles qu'un doigt atteint
  // depuis la barre. « Recettes » n'en est plus une (elle s'ouvre par son
  // URL, qui ne passe pas par `demanderNavigation`) — le garde-fou, lui,
  // reste le même chokepoint pour toutes.
  it.each([['shopping', 'liste'], ['stock', 'catalogue'],
           ['kitchen', 'planning'], ['house', 'piles']])(
    'applique le garde-fou du rangement en attente à la famille %s', async (famille, cible) => {
      const element = monterPanneau();
      await stabiliser(element);
      element.ecran = 'rangement';
      // Une ligne complète, pas un objet minimal : l'écran « rangement » la
      // rend vraiment, et un fantôme y déclencherait des erreurs de rendu qui
      // n'ont rien à voir avec le garde-fou qu'on teste.
      element.enAttenteRangement = [{
        source: 'autonome', id: 'a1', article_id: 42, quantity: 500,
        unit_price: null, product_name: 'Muesli', base_unit: 'g',
        default_location_id: null, default_shelf_life_days: null,
        brand: null, image: null, net_quantity: null,
      }];
      await stabiliser(element);

      await cliquerFamille(element, famille);
      await stabiliser(element);

      // Armé, pas navigué : quitter un rangement inachevé demande deux appuis.
      expect(element.ecran).toBe('rangement');
      expect(element.navigationArmee).toBe(cible);
    });
});

describe('panneau : les deux écrans du lot 5', () => {
  beforeEach(() => { window.localStorage.clear(); });
  afterEach(() => { document.body.innerHTML = ''; vi.restoreAllMocks(); });

  async function monterPanneauLot5() {
    const hass = hassAvecReponses((msg: any) => {
      if (msg.type === 'home_stock/session/current') return Promise.resolve(null);
      if (msg.type === 'home_stock/batteries/list') return Promise.resolve({ batteries: [] });
      if (msg.type === 'home_stock/batteries/discover') return Promise.resolve({ sensors: [] });
      if (msg.type === 'home_stock/equipment/list') return Promise.resolve({ equipment: [] });
      return Promise.resolve({});
    });
    const element = document.createElement('home-stock-panel') as HTMLElement & {
      hass: Hass; updateComplete: Promise<boolean>; ecran: string;
    };
    element.hass = hass;
    document.body.appendChild(element);
    await laisserPasserLesMicrotaches();
    await element.updateComplete;
    return element;
  }

  it('expose la famille « Maison », qui porte les deux écrans du lot 5', async () => {
    const element = await monterPanneauLot5();
    expect(await famillesAffichees(element)).toContain('Maison');
  });

  it('ouvre l’écran Piles et l’écran Équipements', async () => {
    const element = await monterPanneauLot5();
    // « Piles » est la racine de la famille « Maison » : la barre y mène.
    await cliquerFamille(element, 'house');
    await laisserPasserLesMicrotaches();
    await element.updateComplete;
    expect(element.ecran).toBe('piles');
    expect(element.shadowRoot!.querySelector('home-stock-piles')).not.toBeNull();

    // « Équipements » n'en est pas la racine : son URL.
    allerA(element, '/equipment');
    await laisserPasserLesMicrotaches();
    await element.updateComplete;
    expect(element.ecran).toBe('equipements');
    expect(element.shadowRoot!.querySelector('home-stock-equipements')).not.toBeNull();
  });

  it('demande confirmation avant de quitter le rangement vers Piles', async () => {
    const element = await monterSurLeRangementLot5();
    await cliquerFamille(element, 'house');
    await element.updateComplete;
    // Le garde-fou du lot 1 s'applique à ces cibles comme aux autres : c'est
    // `demanderNavigation` qui le porte, donc c'est gratuit — mais c'est un
    // test qui le prouve, pas un raisonnement.
    expect(element.ecran).toBe('rangement');
    expect(element.shadowRoot!.querySelector('.confirmation-quitter-rangement')).not.toBeNull();
  });

  it('demande confirmation avant de remonter par le retour de l’en-tête', async () => {
    // Le retour de l'en-tête est une navigation comme une autre : il passe
    // par `demanderNavigation`, donc par le même garde-fou. Sans ce test, le
    // seul chemin de sortie qui ne soit pas la barre resterait non couvert.
    const element = await monterSurLeRangementLot5();
    const entete = element.shadowRoot!.querySelector('hs-header') as any;
    await entete.updateComplete;
    (entete.shadowRoot!.querySelector('.retour') as HTMLButtonElement).click();
    await element.updateComplete;
    expect(element.ecran).toBe('rangement');
    expect(element.shadowRoot!.querySelector('.confirmation-quitter-rangement')).not.toBeNull();
  });

  async function monterSurLeRangementLot5() {
    const hass = hassAvecReponses((msg: any) => {
      if (msg.type === 'home_stock/session/current') return Promise.resolve(null);
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
    element.shadowRoot!.querySelector('home-stock-scanner')!.dispatchEvent(
      new CustomEvent('code-lu', { detail: { code: '3229820129488' },
                                   bubbles: true, composed: true }));
    await laisserPasserLesMicrotaches();
    await element.updateComplete;
    element.shadowRoot!.querySelector('home-stock-fiche')!.dispatchEvent(
      new CustomEvent('article-pret', {
        detail: { articleId: 42, quantite: 500, prixUnitaire: 0.005,
                  mode: 'rangement', offDroppedFields: [] },
        bubbles: true, composed: true }));
    await laisserPasserLesMicrotaches();
    await element.updateComplete;
    expect(element.ecran).toBe('rangement');
    return element;
  }
});

describe('la navigation du lot 4', () => {
  afterEach(() => { document.body.innerHTML = ''; });

  function monterPanneau() {
    const element = document.createElement('home-stock-panel') as HTMLElement & {
      hass: Hass; ecran: string; updateComplete: Promise<boolean>;
    };
    element.hass = hassAvecReponses(async () => null);
    document.body.appendChild(element);
    return element;
  }

  it('expose la famille « Courses », dont la liste est la racine', async () => {
    const element = monterPanneau();
    await element.updateComplete;

    expect(await famillesAffichees(element)).toContain('Courses');
  });

  it('bascule sur l’écran Liste et GARDE les quatre familles en place', async () => {
    const element = monterPanneau();
    await element.updateComplete;

    await cliquerFamille(element, 'shopping');
    await element.updateComplete;

    expect(element.ecran).toBe('liste');
    expect(element.shadowRoot!.querySelector('home-stock-liste')).not.toBeNull();
    // L'ancienne barre retirait le bouton de l'écran courant, ce qui décalait
    // tous les autres à chaque navigation. Les quatre familles ne bougent
    // plus jamais — c'est le repère.
    expect(await famillesAffichees(element))
      .toEqual(['Courses', 'Stock', 'Cuisine', 'Maison']);
  });
});

// --- lot 6 : le socle de la vue dense ---------------------------------------
//
// `large` est MESURÉ (`window.innerWidth >= 1000`), jamais déduit d'un agent
// utilisateur : c'est ce qui le rend testable sans navigateur, et c'est aussi
// pourquoi il vaut hors du panneau Home Assistant, dans le harnais du
// vérificateur de rendu, qui ne fournit aucun `narrow`.

/** Les sept écrans que la largeur sert, plus `planning` qui la recevait déjà. */
const ECRANS_DENSES = ['catalogue', 'journal', 'liste', 'reglages', 'ticket',
                       'equipements', 'piles', 'planning'] as const;

/** Les dix autres. Une main, debout, ou un magasin : la largeur ne leur
 *  apporte rien, et une mise en page conditionnelle est une seconde mise en
 *  page à tenir. */
const ECRANS_ETROITS = ['scanner', 'fiche', 'panier', 'rangement', 'session',
                        'recettes', 'recette', 'validation', 'consommation'] as const;

/** De quoi laisser CHAQUE écran se charger sans lever : ce bloc les monte
 *  tous les dix-sept pour vérifier qui reçoit `large`, et un écran qui
 *  explose au chargement produirait un rejet non capturé — du bruit qui n'a
 *  rien à voir avec ce qu'on mesure ici, et qui fait sortir vitest en erreur. */
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
  'home_stock/journal/series': { granularity: 'day', buckets: [] },
  'home_stock/journal/day': {
    food_day: '2026-08-21', start: '2026-08-21T02:00:00', end: '2026-08-22T02:00:00',
    entries: [], totals: { kcal: 0, cost: 0, waste_cost: 0, unvalued: 0 },
  },
  'home_stock/list/items': { items: [], store_id: null, store_name: null,
                             estimate: { amount: 0, confidence: 0, priced: 0, total: 0 } },
};

const BALISE_ECRAN: Record<string, string> = {
  scanner: 'home-stock-scanner', fiche: 'home-stock-fiche', panier: 'home-stock-panier',
  rangement: 'home-stock-rangement', session: 'home-stock-session',
  catalogue: 'home-stock-catalogue', reglages: 'home-stock-reglages',
  consommation: 'home-stock-consommation', journal: 'home-stock-journal',
  recettes: 'home-stock-recettes', recette: 'home-stock-recette',
  planning: 'home-stock-planning', validation: 'home-stock-validation',
  piles: 'home-stock-piles', equipements: 'home-stock-equipements',
  liste: 'home-stock-liste', ticket: 'home-stock-ticket',
};

describe('panneau : le socle de la vue dense (lot 6)', () => {
  const largeurInitiale = window.innerWidth;

  beforeEach(() => { window.localStorage.clear(); });
  afterEach(() => {
    document.body.innerHTML = '';
    redimensionner(largeurInitiale);
  });

  function redimensionner(largeur: number): void {
    Object.defineProperty(window, 'innerWidth', { value: largeur, configurable: true, writable: true });
    window.dispatchEvent(new Event('resize'));
  }

  async function monterLarge(options: { largeurFenetre: number; narrow?: boolean }) {
    redimensionner(options.largeurFenetre);
    const element = document.createElement('home-stock-panel') as HTMLElement & {
      hass: Hass; narrow: boolean; large: boolean; ecran: string;
      updateComplete: Promise<boolean>;
    };
    element.hass = hassAvecReponses(async (msg: any) =>
      (msg.type in REPONSES_VIDES ? REPONSES_VIDES[msg.type] : {}) as any);
    if (options.narrow !== undefined) element.narrow = options.narrow;
    document.body.appendChild(element);
    await element.updateComplete;
    return element;
  }

  it('bascule large sur resize, dans les deux sens', async () => {
    const p = await monterLarge({ largeurFenetre: 412 });
    expect(p.large).toBe(false);
    redimensionner(1280); await p.updateComplete;
    expect(p.large).toBe(true);
    redimensionner(999); await p.updateComplete;
    expect(p.large).toBe(false);        // le retour compte autant que l'aller
  });

  it('un hôte qui se dit étroit gagne contre la largeur mesurée', async () => {
    // Barre latérale Home Assistant dépliée sur une tablette large :
    // `innerWidth` ment sur la place réellement laissée au panneau, et une
    // mise en page dense écrasée dans 400 px est pire que l'étroite.
    const p = await monterLarge({ largeurFenetre: 1280, narrow: true });
    expect(p.large).toBe(false);
  });

  it('passe large aux sept écrans denses et à eux seuls', async () => {
    // Le garde-fou de la décision « dix écrans ne changent pas » : si demain
    // quelqu'un branche `large` sur le scanner, ce test le dit tout de suite.
    const p = await monterLarge({ largeurFenetre: 1280 });
    for (const ecran of ECRANS_DENSES) {
      p.ecran = ecran;
      await p.updateComplete;
      const enfant = p.shadowRoot!.querySelector(BALISE_ECRAN[ecran]) as any;
      expect(enfant, ecran).not.toBeNull();
      expect(enfant.large, ecran).toBe(true);
    }
    for (const ecran of ECRANS_ETROITS) {
      p.ecran = ecran;
      await p.updateComplete;
      const enfant = p.shadowRoot!.querySelector(BALISE_ECRAN[ecran]) as any;
      // `fiche`, `recette` et `validation` n'ont rien à montrer sans leur
      // donnée : absents, ils ne reçoivent rien non plus, ce qui est le
      // verdict attendu.
      if (enfant === null) continue;
      expect(enfant.large ?? false, ecran).toBe(false);
    }
  });

  it('ne casse aucun écran étroit', async () => {
    // Chaque écran atteignable se monte et se démonte à 412 px, comme avant
    // le lot : le câblage seul ne doit rien changer à ce qui se voit.
    const p = await monterLarge({ largeurFenetre: 412 });
    for (const ecran of [...ECRANS_DENSES, ...ECRANS_ETROITS]) {
      p.ecran = ecran;
      await p.updateComplete;
      const enfant = p.shadowRoot!.querySelector(BALISE_ECRAN[ecran]) as any;
      if (enfant === null) continue;
      expect(enfant.large ?? false, ecran).toBe(false);
    }
  });
});
