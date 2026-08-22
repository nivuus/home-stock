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
  'home_stock/lookup': {
    code: '3229820129488', known: true,
    article: { id: 42, label: 'Muesli', brand: null, net_quantity: 500, image: null,
               nutriscore: null, kcal_per_base_unit: null },
    product: { id: 9, name: 'Muesli', base_unit: 'g', default_location_id: 3,
               default_shelf_life_days: 10 },
    off: null, off_raw: null, off_source: null, candidates: [],
    preselected_product_id: null,
    price: { price_per_base_unit: 0.004, source: 'last_known', store: null },
    conversion_offer: null, throttled: false, timed_out: false,
  },
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

  // --- le garde-fou du rangement vaut AUSSI pour les routes -----------------
  //
  // Le bouton Retour du navigateur et le geste système d'Android arrivent par
  // `route`, pas par un bouton de l'application : un garde-fou posé sur les
  // seuls gestes de l'application n'en est pas un.

  /** Amène le panneau sur le rangement avec un article rapporté seul en
   *  attente — le seul état où quitter perd vraiment quelque chose. */
  async function monterSurUnRangementInacheve() {
    const el = await monter('/scan');
    const scanner = el.shadowRoot!.querySelector('home-stock-scanner')!;
    scanner.dispatchEvent(new CustomEvent('code-lu', {
      detail: { code: '3229820129488' }, bubbles: true, composed: true,
    }));
    await laisserPasserLesMicrotaches();
    await el.updateComplete;
    el.shadowRoot!.querySelector('home-stock-fiche')!.dispatchEvent(
      new CustomEvent('article-pret', {
        detail: { articleId: 42, quantite: 500, prixUnitaire: 0.005,
                  mode: 'rangement', offDroppedFields: [] },
        bubbles: true, composed: true,
      }));
    await laisserPasserLesMicrotaches();
    await el.updateComplete;
    expect(el.ecran).toBe('rangement');
    return el;
  }

  it('arme la confirmation quand une ROUTE veut sortir d’un rangement inachevé',
     async () => {
    const el = await monterSurUnRangementInacheve();
    // Ce que fait le bouton Retour du navigateur : Home Assistant nous
    // repasse une route, sans qu'aucun bouton de l'application soit touché.
    el.route = { prefix: '/home-stock', path: '/catalog' };
    await el.updateComplete;

    expect(el.ecran).toBe('rangement');
    expect(el.shadowRoot!.querySelector('.confirmation-quitter-rangement')).not.toBeNull();
  });

  it('arme la confirmation même sur une route INCONNUE, qui retombe sur la liste',
     async () => {
    const el = await monterSurUnRangementInacheve();
    el.route = { prefix: '/home-stock', path: '/nawak' };
    await el.updateComplete;

    expect(el.ecran).toBe('rangement');
    expect(el.shadowRoot!.querySelector('.confirmation-quitter-rangement')).not.toBeNull();
    // La cible retenue est bien la racine, prête pour « Quitter quand même ».
    expect((el as any).navigationArmee).toBe('liste');
  });

  it('repose l’URL du rangement une seule fois, et jamais en pushState', async () => {
    // Ce test ne prouve QUE ça : une repose, en `replace`. Il ne distingue pas
    // les deux verrous qui empêchent l'écho de route de réarmer (l'égalité de
    // `dernierChemin` et l'idempotence du chemin reposé) — c'est le test
    // suivant qui s'en charge, et lui seul.
    const el = await monterSurUnRangementInacheve();
    const replaceState = vi.spyOn(window.history, 'replaceState');
    const pushState = vi.spyOn(window.history, 'pushState');

    el.route = { prefix: '/home-stock', path: '/catalog' };
    await el.updateComplete;

    expect(replaceState).toHaveBeenCalledTimes(1);
    expect(replaceState).toHaveBeenCalledWith(null, '', '/home-stock/put-away');
    // Un départ refusé ne mérite aucune entrée d'historique.
    expect(pushState).not.toHaveBeenCalled();
    expect(el.ecran).toBe('rangement');
  });

  it('un écho de route qui désigne le rangement AUTREMENT ne réarme rien', async () => {
    // Le vrai verrou n'est pas `dernierChemin` mais l'IDEMPOTENCE du chemin
    // reposé : `/put-away` reparse vers `rangement`, donc la cible est l'écran
    // courant et `departARisque` est faux. Pour le prouver, il faut un écho
    // que `dernierChemin` ne peut PAS court-circuiter : un chemin
    // textuellement différent qui désigne le même écran — exactement ce que
    // produirait une normalisation de chemin côté Home Assistant. Si le
    // verrou tenait à la seule égalité de chaînes, ce second passage
    // réarmerait et reposerait l'URL une seconde fois.
    const el = await monterSurUnRangementInacheve();
    const replaceState = vi.spyOn(window.history, 'replaceState');

    el.route = { prefix: '/home-stock', path: '/catalog' };
    await el.updateComplete;
    expect(replaceState).toHaveBeenCalledTimes(1);

    el.route = { prefix: '/home-stock', path: '/put-away/42' };
    await el.updateComplete;

    expect(replaceState).toHaveBeenCalledTimes(1);
    expect(el.ecran).toBe('rangement');
    // Et la confirmation précédente n'a pas été remplacée par une nouvelle
    // qui viserait le rangement lui-même.
    expect((el as any).navigationArmee).toBe('catalogue');
  });

  it('« Quitter quand même » vers un écran PARAMÉTRÉ applique son paramètre', async () => {
    // L'historique typique est /scan → /item/<code> → /put-away : un Retour
    // depuis le rangement vise donc la fiche de l'article qu'on vient de
    // rapporter. C'est le cas le plus fréquent, et c'était le pire — le
    // panneau tombait sur le scanner, sans barre ni en-tête (l'écran entier
    // de la fiche), sous une URL d'article : aucun bouton pour sortir.
    const el = await monterSurUnRangementInacheve();
    el.route = { prefix: '/home-stock', path: '/item/3229820129488' };
    await el.updateComplete;
    expect((el as any).navigationArmee).toBe('fiche');

    (el.shadowRoot!.querySelector('.confirmer-quitter') as HTMLButtonElement).click();
    await laisserPasserLesMicrotaches();
    await el.updateComplete;

    expect(el.ecran).toBe('fiche');
    // Pas seulement l'écran : la fiche doit être MONTÉE, avec son résultat.
    const fiche = el.shadowRoot!.querySelector('home-stock-fiche') as any;
    expect(fiche).not.toBeNull();
    expect(fiche.resultat.code).toBe('3229820129488');
    expect(el.shadowRoot!.querySelector('home-stock-scanner')).toBeNull();
  });

  it('… et vaut pour un second écran paramétré, /recipe/12', async () => {
    const el = await monterSurUnRangementInacheve();
    el.route = { prefix: '/home-stock', path: '/recipe/12' };
    await el.updateComplete;
    expect((el as any).navigationArmee).toBe('recette');

    (el.shadowRoot!.querySelector('.confirmer-quitter') as HTMLButtonElement).click();
    await laisserPasserLesMicrotaches();
    await el.updateComplete;

    expect(el.ecran).toBe('recette');
    expect((el as any).recetteOuverte).toBe(12);
    expect(el.shadowRoot!.querySelector('home-stock-recette')).not.toBeNull();
  });

  it('« Quitter quand même » va bien où la route voulait aller', async () => {
    const el = await monterSurUnRangementInacheve();
    el.route = { prefix: '/home-stock', path: '/catalog' };
    await el.updateComplete;

    (el.shadowRoot!.querySelector('.confirmer-quitter') as HTMLButtonElement).click();
    await el.updateComplete;
    expect(el.ecran).toBe('catalogue');
  });

  it('garde l’écran de rangement MONTÉ pendant la confirmation, et la même instance',
     async () => {
    const el = await monterSurUnRangementInacheve();
    const avant = el.shadowRoot!.querySelector('home-stock-rangement') as HTMLElement;
    expect(avant).not.toBeNull();
    // Une marque que seul un remontage effacerait : c'est l'analogue de
    // `emplacementChoisi`, l'état local que l'utilisateur vient de saisir.
    avant.dataset.temoin = 'saisie-en-cours';

    el.route = { prefix: '/home-stock', path: '/catalog' };
    await el.updateComplete;

    const pendant = el.shadowRoot!.querySelector('home-stock-rangement');
    expect(pendant).toBe(avant);

    (el.shadowRoot!.querySelector('.annuler-quitter') as HTMLButtonElement).click();
    await el.updateComplete;

    const apres = el.shadowRoot!.querySelector('home-stock-rangement') as HTMLElement;
    expect(apres).toBe(avant);
    expect(apres.dataset.temoin).toBe('saisie-en-cours');
  });

  it('dit à voix haute qu’un ticket désigné par l’URL est introuvable', async () => {
    // Un `catch` muet laisserait un écran vide sans dire pourquoi. Le refus
    // remonte par la bannière de l'en-tête, le canal qui existe déjà.
    const el = document.createElement('home-stock-panel') as HTMLElement
      & { updateComplete: Promise<unknown>; hass: Hass; route: unknown; ecran: string };
    el.hass = {
      connection: {
        sendMessagePromise: vi.fn().mockImplementation((msg: { type: string }) => {
          if (msg.type === 'home_stock/receipt/get') {
            return Promise.reject({ code: 'not_found', message: 'unknown receipt 999' });
          }
          return Promise.resolve(msg.type in REPONSES_VIDES ? REPONSES_VIDES[msg.type] : {});
        }),
        subscribeMessage: vi.fn().mockResolvedValue(() => {}),
      },
      language: 'fr',
    } as unknown as Hass;
    el.route = { prefix: '/home-stock', path: '/receipt/999' };
    document.body.appendChild(el);
    await laisserPasserLesMicrotaches();
    await el.updateComplete;

    const entete = el.shadowRoot!.querySelector('hs-header') as any;
    await entete.updateComplete;
    expect(entete.shadowRoot!.querySelector('.erreur')!.textContent)
      .toContain('Ticket n° 999');
  });

  it('remonte au retour de l’en-tête vers la racine de la famille', async () => {
    const el = await monter('/settings');           // famille « house »
    const entete = el.shadowRoot!.querySelector('hs-header')!;
    entete.dispatchEvent(new CustomEvent('retour-demande', { bubbles: true, composed: true }));
    await el.updateComplete;
    expect(el.ecran).toBe('piles');                  // la racine de « house »
  });

  it('atteint Réglages depuis Piles, sans passer par une URL tapée à la main', async () => {
    // La régression que ce test interdit : Réglages n'était plus atteignable
    // dans l'application, seulement en tapant son URL.
    const el = await monter('/batteries');
    const entete = el.shadowRoot!.querySelector('hs-header')!;
    entete.dispatchEvent(new CustomEvent('ecran-choisi', {
      detail: { screen: 'reglages' }, bubbles: true, composed: true }));
    await el.updateComplete;
    expect(el.ecran).toBe('reglages');
    expect(window.location.pathname).toBe('/home-stock/settings');
  });
});
