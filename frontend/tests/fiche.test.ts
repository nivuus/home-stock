import { afterEach, describe, expect, it, vi } from 'vitest';
import '../src/ecrans/fiche';
import { prixBaseDepuisSaisie, prixPaquetAffiche } from '../src/ecrans/fiche';
import type { Connexion } from '../src/connexion';
import type { ResultatLookup } from '../src/ecrans/fiche';

/** Attend que les microtâches en attente (le `.then()` de la validation, qui
 *  appelle le réseau avant d'émettre l'événement) se soient exécutées. */
function laisserPasserLesMicrotaches(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

const CANDIDATS = [
  { product_id: 1, name: 'Muesli Bio', score: 0.92 },
  { product_id: 2, name: 'Muesli Classique', score: 0.4 },
  { product_id: 3, name: 'Granola', score: 0.3 },
  { product_id: 4, name: 'Céréales', score: 0.2 },
  { product_id: 5, name: 'Porridge', score: 0.1 },
];

function resultatInconnu(partiel: Partial<ResultatLookup> = {}): ResultatLookup {
  return {
    code: '3229820129488', known: false, article: null, product: null,
    off: {
      off_source: 'food', aisle: 'Petit-déjeuner', label: 'Muesli Bjorg',
      generic_name: 'Muesli', brand: 'Bjorg', net_quantity: 500, net_unit: 'g',
      image: null, nutriscore: 'a', nova: 1, ecoscore: null, allergens: null,
      traces: null, additives: null, off_labels: null,
      nutrition_per_100: { kcal: 360 }, rejections: [],
    },
    off_raw: { brands: 'Bjorg' }, off_source: 'food',
    candidates: CANDIDATS, preselected_product_id: 1,
    price: { price_per_base_unit: 0.004, source: 'open_prices', store: null },
    conversion_offer: null, throttled: false, timed_out: false,
    ...partiel,
  };
}

function resultatConnu(partiel: Partial<ResultatLookup> = {}): ResultatLookup {
  return {
    code: '1', known: true,
    article: { id: 42, label: 'Muesli Bjorg', brand: 'Bjorg', net_quantity: 500,
              image: null, nutriscore: 'a', kcal_per_base_unit: 3.6 },
    product: { id: 9, name: 'Muesli', base_unit: 'g' },
    off: null, off_raw: null, off_source: null,
    candidates: [], preselected_product_id: null,
    price: { price_per_base_unit: 0.004, source: 'last_known', store: null },
    conversion_offer: null, throttled: false, timed_out: false,
    ...partiel,
  };
}

function creer(resultat: ResultatLookup, options: {
  mode?: 'panier' | 'rangement'; connexion?: Connexion; file?: { ajouter: ReturnType<typeof vi.fn> };
} = {}) {
  const element = document.createElement('home-stock-fiche') as HTMLElement & {
    resultat: ResultatLookup; mode: 'panier' | 'rangement'; connexion?: Connexion; file?: unknown;
    updateComplete: Promise<boolean>;
  };
  element.resultat = resultat;
  element.mode = options.mode ?? 'rangement';
  if (options.connexion) element.connexion = options.connexion;
  if (options.file) element.file = options.file;
  document.body.appendChild(element);
  return element;
}

function saisir(champ: HTMLInputElement, valeur: string): void {
  champ.value = valeur;
  champ.dispatchEvent(new Event('input'));
}

/** Une connexion dont la réponse dépend du type de message — nécessaire dès
 *  qu'un candidat déjà au catalogue est choisi : la fiche doit d'abord
 *  résoudre son unité via `products/list` avant de savoir quoi faire du
 *  prix, et un mock à réponse unique ne peut pas simuler ça. */
function connexionFactice(options: {
  productsList?: { id: number; base_unit: string }[];
  create?: unknown;
  createRejette?: unknown;
} = {}): { connexion: Connexion; appeler: ReturnType<typeof vi.fn> } {
  const appeler = vi.fn((type: string) => {
    if (type === 'home_stock/products/list') {
      return Promise.resolve({ products: options.productsList ?? [] });
    }
    if (type === 'home_stock/article/create') {
      if (options.createRejette) return Promise.reject(options.createRejette);
      return Promise.resolve(options.create
        ?? { article_id: 1, product_id: 1, created: true, off_dropped_fields: [] });
    }
    return Promise.resolve({});
  });
  return { connexion: { appeler } as unknown as Connexion, appeler };
}

afterEach(() => {
  document.body.innerHTML = '';
});

describe('rattachement au produit', () => {
  it('coche le candidat présélectionné', async () => {
    const el = creer(resultatInconnu());
    await el.updateComplete;

    const radios = el.shadowRoot!.querySelectorAll<HTMLInputElement>('input[name="produit"]');
    const coche = Array.from(radios).find((r) => r.checked);
    expect(coche?.value).toBe('1');
  });

  it('coche la présélection du serveur même quand ce n’est PAS le premier candidat de la '
     + 'liste — un bug qui prendrait candidates[0] doit faire échouer ce test', async () => {
    // L'ordre du tableau (1,2,3,4,5) et l'id présélectionné (4) divergent
    // exprès : un `candidates[0].product_id` à la place de
    // `preselected_product_id` cocherait le 1, pas le 4.
    const el = creer(resultatInconnu({ preselected_product_id: 4 }));
    await el.updateComplete;

    const radios = el.shadowRoot!.querySelectorAll<HTMLInputElement>('input[name="produit"]');
    const coches = Array.from(radios).filter((r) => r.checked).map((r) => r.value);
    expect(coches).toEqual(['4']);
  });

  it('ne coche aucun candidat quand la présélection est ambiguë', async () => {
    const el = creer(resultatInconnu({ preselected_product_id: null }));
    await el.updateComplete;

    const radiosProduits = el.shadowRoot!.querySelectorAll<HTMLInputElement>(
      'input[name="produit"][value="1"], input[name="produit"][value="2"], '
      + 'input[name="produit"][value="3"], input[name="produit"][value="4"], '
      + 'input[name="produit"][value="5"]');
    expect(Array.from(radiosProduits).some((r) => r.checked)).toBe(false);
  });
});

describe('provenance du prix', () => {
  it('affiche le magasin quand le prix vient du magasin', async () => {
    const el = creer(resultatConnu({ price: { price_per_base_unit: 0.004, source: 'store', store: 'Leclerc' } }));
    await el.updateComplete;
    expect(el.shadowRoot!.querySelector('.prix-provenance')!.textContent).toContain('Leclerc');
  });

  it('affiche Open Prices quand le prix en vient', async () => {
    const el = creer(resultatConnu({ price: { price_per_base_unit: 0.004, source: 'open_prices', store: null } }));
    await el.updateComplete;
    expect(el.shadowRoot!.querySelector('.prix-provenance')!.textContent).toContain('Open Prices');
  });

  it('affiche « dernier prix connu » quand le prix vient de l’historique', async () => {
    const el = creer(resultatConnu({ price: { price_per_base_unit: 0.004, source: 'last_known', store: null } }));
    await el.updateComplete;
    expect(el.shadowRoot!.querySelector('.prix-provenance')!.textContent).toContain('dernier prix connu');
  });
});

describe('offre de conversion', () => {
  it('n’apparaît pas quand conversion_offer est absent', async () => {
    const el = creer(resultatConnu({ conversion_offer: null }));
    await el.updateComplete;
    expect(el.shadowRoot!.querySelector('.conversion-offre')).toBeNull();
  });

  it('apparaît quand conversion_offer est fourni', async () => {
    const el = creer(resultatConnu({
      conversion_offer: { product_id: 9, to_unit: 'g', reference_quantity: 500 },
    }));
    await el.updateComplete;
    const bloc = el.shadowRoot!.querySelector('.conversion-offre');
    expect(bloc).not.toBeNull();
    expect(bloc!.textContent).toContain('500');
  });

  it('le premier appui ne fait qu’un essai (dry_run) — jamais une application réelle', async () => {
    const appeler = vi.fn().mockResolvedValue({
      applied: false, articles: 2, batches: 1, movements: 2, articles_using_reference: [7],
    });
    const connexionFactice = { appeler } as unknown as Connexion;
    const el = creer(resultatConnu({
      conversion_offer: { product_id: 9, to_unit: 'g', reference_quantity: 500 },
    }), { connexion: connexionFactice });
    await el.updateComplete;

    el.shadowRoot!.querySelector<HTMLButtonElement>('.voir-effet')!.click();
    await laisserPasserLesMicrotaches();
    await el.updateComplete;

    expect(appeler).toHaveBeenCalledTimes(1);
    expect(appeler).toHaveBeenCalledWith('home_stock/product/convert_unit',
      expect.objectContaining({ dry_run: true }));
    // Le rapport s'affiche, mais rien n'a encore été appliqué : le bouton
    // proposé ensuite doit être un second appui, pas un fait accompli.
    expect(el.shadowRoot!.querySelector('.rapport-conversion')!.textContent).toContain('2 article');
    expect(el.shadowRoot!.querySelector('.appliquer-conversion')).not.toBeNull();
  });

  it('le second appui applique réellement (dry_run: false), et seulement lui', async () => {
    const appeler = vi.fn()
      .mockResolvedValueOnce({ applied: false, articles: 2, batches: 1, movements: 2, articles_using_reference: [] })
      .mockResolvedValueOnce({ applied: true, articles: 2, batches: 1, movements: 2, articles_using_reference: [] });
    const connexionFactice = { appeler } as unknown as Connexion;
    const el = creer(resultatConnu({
      conversion_offer: { product_id: 9, to_unit: 'g', reference_quantity: 500 },
    }), { connexion: connexionFactice });
    await el.updateComplete;

    el.shadowRoot!.querySelector<HTMLButtonElement>('.voir-effet')!.click();
    await laisserPasserLesMicrotaches();
    await el.updateComplete;
    el.shadowRoot!.querySelector<HTMLButtonElement>('.appliquer-conversion')!.click();
    await laisserPasserLesMicrotaches();
    await el.updateComplete;

    expect(appeler).toHaveBeenCalledTimes(2);
    expect(appeler).toHaveBeenLastCalledWith('home_stock/product/convert_unit',
      expect.objectContaining({ dry_run: false }));
    expect(el.shadowRoot!.querySelector('.conversion-appliquee')).not.toBeNull();
  });

  it('montre le refus du serveur (ex. lignes de courses en attente) au lieu de le laisser filer', async () => {
    const appeler = vi.fn().mockRejectedValue({ code: 'conversion_refused',
      message: '2 ligne(s) de courses en attente de rangement.' });
    const connexionFactice = { appeler } as unknown as Connexion;
    const el = creer(resultatConnu({
      conversion_offer: { product_id: 9, to_unit: 'g', reference_quantity: 500 },
    }), { connexion: connexionFactice });
    await el.updateComplete;

    el.shadowRoot!.querySelector<HTMLButtonElement>('.voir-effet')!.click();
    await laisserPasserLesMicrotaches();
    await el.updateComplete;

    expect(el.shadowRoot!.querySelector('.erreur-conversion')!.textContent)
      .toContain('en attente de rangement');
    // Le bouton « Voir l'effet » doit être encore là : rien n'a été
    // silencieusement marqué comme fait.
    expect(el.shadowRoot!.querySelector('.voir-effet')).not.toBeNull();
  });

  it('dit combien d’articles seraient repesés avec un poids estimé', async () => {
    const appeler = vi.fn().mockResolvedValue({
      applied: false, articles: 5, batches: 2, movements: 4, articles_using_reference: [1, 2, 3],
    });
    const el = creer(resultatConnu({
      conversion_offer: { product_id: 9, to_unit: 'g', reference_quantity: 500 },
    }), { connexion: { appeler } as unknown as Connexion });
    await el.updateComplete;

    el.shadowRoot!.querySelector<HTMLButtonElement>('.voir-effet')!.click();
    await laisserPasserLesMicrotaches();
    await el.updateComplete;

    expect(el.shadowRoot!.querySelector('.rapport-conversion')!.textContent).toContain('3');
  });
});

describe('bouton principal', () => {
  it('dit « Au panier » en session', async () => {
    const el = creer(resultatConnu(), { mode: 'panier' });
    await el.updateComplete;
    expect(el.shadowRoot!.querySelector('.action-principale')!.textContent!.trim()).toBe('Au panier');
  });

  it('dit « Ranger » hors session', async () => {
    const el = creer(resultatConnu(), { mode: 'rangement' });
    await el.updateComplete;
    expect(el.shadowRoot!.querySelector('.action-principale')!.textContent!.trim()).toBe('Ranger');
  });
});

describe('conversion prix paquet <-> prix par unité de base (fonctions pures)', () => {
  it('un prix de paquet de 2,50 € pour 500 g devient 0,005 €/g, jamais 2,50 €/g', () => {
    const parBase = prixBaseDepuisSaisie('2,50', 'g', 500);
    expect(parBase).toBeCloseTo(0.005);
    expect(parBase).not.toBe(2.5);
  });

  it('à la pièce, le prix du paquet EST le prix par unité de base — pas de diviseur', () => {
    expect(prixBaseDepuisSaisie('2,50', 'piece', null)).toBe(2.5);
    // Même avec un poids d'article renseigné (ex. 500 g imprimé sur la
    // boîte), un produit à la pièce ne doit JAMAIS être divisé par ce poids.
    expect(prixBaseDepuisSaisie('2,50', 'piece', 500)).toBe(2.5);
  });

  it('ne devine jamais de diviseur : un produit pesé sans poids ne rend aucun prix', () => {
    expect(prixBaseDepuisSaisie('2,50', 'g', null)).toBeNull();
    expect(prixBaseDepuisSaisie('2,50', 'ml', null)).toBeNull();
  });

  it('ne devine rien non plus quand l’unité elle-même est inconnue', () => {
    expect(prixBaseDepuisSaisie('2,50', null, 500)).toBeNull();
  });

  it('accepte le point comme séparateur décimal', () => {
    expect(prixBaseDepuisSaisie('2.50', 'g', 500)).toBeCloseTo(0.005);
  });

  it('rend null pour une saisie vide ou invalide', () => {
    expect(prixBaseDepuisSaisie('', 'g', 500)).toBeNull();
    expect(prixBaseDepuisSaisie('abc', 'g', 500)).toBeNull();
  });

  it('affiche le prix du paquet à partir du prix par unité de base (aller-retour, au poids)', () => {
    expect(prixPaquetAffiche(0.005, 'g', 500)).toBe('2,50');
    expect(prixPaquetAffiche(prixBaseDepuisSaisie('2,50', 'g', 500), 'g', 500)).toBe('2,50');
  });

  it('affiche le prix par unité de base tel quel à la pièce', () => {
    expect(prixPaquetAffiche(2.5, 'piece', null)).toBe('2,50');
  });

  it('n’affiche rien pour un produit pesé sans poids : pas de faux diviseur visible', () => {
    expect(prixPaquetAffiche(0.005, 'g', null)).toBe('');
  });

  it('rend une chaîne vide quand il n’y a pas de prix', () => {
    expect(prixPaquetAffiche(null, 'g', 500)).toBe('');
  });
});

describe('cas n°1 — produit à la pièce : le paquet est l’unité, jamais de diviseur', () => {
  function resultatPiece(partiel: Partial<ResultatLookup> = {}): ResultatLookup {
    return resultatConnu({
      article: { id: 42, label: 'Œufs', brand: null, net_quantity: 500, image: null,
                nutriscore: null, kcal_per_base_unit: null },
      product: { id: 20, name: 'Œufs', base_unit: 'piece' },
      price: { price_per_base_unit: 0.3, source: 'last_known', store: null },
      ...partiel,
    });
  }

  it('étiquette le champ « € / unité », pas « prix du paquet »', async () => {
    const el = creer(resultatPiece());
    await el.updateComplete;
    expect(el.shadowRoot!.querySelector('.prix-label')!.textContent).toContain('unité');
    expect(el.shadowRoot!.querySelector('.poids-champ')).toBeNull();
  });

  it('préremplit le prix par pièce tel quel (0,30, pas 0,0006)', async () => {
    const el = creer(resultatPiece());
    await el.updateComplete;
    expect(el.shadowRoot!.querySelector<HTMLInputElement>('.prix-champ')!.value).toBe('0,30');
  });

  it('ÉCHEC PINGLÉ : ne divise jamais par le poids de l’article — la quantité envoyée '
     + 'est un compte de pièces, pas des grammes', async () => {
    const el = creer(resultatPiece(), { mode: 'panier' });
    await el.updateComplete;

    saisir(el.shadowRoot!.querySelector<HTMLInputElement>('.prix-champ')!, '3,00');
    await el.updateComplete;

    const recu = vi.fn();
    el.addEventListener('article-pret', (e) => recu((e as CustomEvent).detail));
    el.shadowRoot!.querySelector<HTMLButtonElement>('.action-principale')!.click();
    await laisserPasserLesMicrotaches();

    const detail = recu.mock.calls[0][0];
    expect(detail.prixUnitaire).toBe(3);
    expect(detail.quantite).toBe(1); // une pièce, pas 500 (le poids de l'article)
  });

  it('deux pièces demandées donnent une quantité de 2, pas 1000', async () => {
    const el = creer(resultatPiece(), { mode: 'panier' });
    await el.updateComplete;
    el.shadowRoot!.querySelector<HTMLButtonElement>('.plus')!.click();
    await el.updateComplete;

    const recu = vi.fn();
    el.addEventListener('article-pret', (e) => recu((e as CustomEvent).detail));
    el.shadowRoot!.querySelector<HTMLButtonElement>('.action-principale')!.click();
    await laisserPasserLesMicrotaches();

    expect(recu.mock.calls[0][0].quantite).toBe(2);
  });

  it('ÉCHEC PINGLÉ : n’affiche aucun détail « €/kg » — le prix par unité EST déjà '
     + 'la forme lisible, à la pièce', async () => {
    const el = creer(resultatPiece());
    await el.updateComplete;
    expect(el.shadowRoot!.querySelector('.prix-detail')).toBeNull();
    expect(el.shadowRoot!.textContent).not.toContain('€/kg');
  });
});

describe('cas n°2 — produit pesé, poids déjà connu : diviseur normal', () => {
  it('préremplit le prix du paquet, pas le prix par gramme', async () => {
    // price_per_base_unit = 0,004 €/g, net_quantity = 500 g => 2,00 € le paquet.
    const el = creer(resultatConnu());
    await el.updateComplete;
    const champ = el.shadowRoot!.querySelector<HTMLInputElement>('.prix-champ')!;
    expect(champ.value).toBe('2,00');
    expect(el.shadowRoot!.querySelector('.poids-champ')).toBeNull(); // poids déjà connu : rien à demander
  });

  it('convertit la saisie en prix par unité de base avant de l’envoyer, sans réseau', async () => {
    const el = creer(resultatConnu(), { mode: 'panier' });
    await el.updateComplete;

    saisir(el.shadowRoot!.querySelector<HTMLInputElement>('.prix-champ')!, '2,50');
    await el.updateComplete;

    const recu = vi.fn();
    el.addEventListener('article-pret', (e) => recu((e as CustomEvent).detail));
    el.shadowRoot!.querySelector<HTMLButtonElement>('.action-principale')!.click();
    await laisserPasserLesMicrotaches();

    expect(recu).toHaveBeenCalledTimes(1);
    const detail = recu.mock.calls[0][0];
    expect(detail.prixUnitaire).toBeCloseTo(0.005);
    expect(detail.prixUnitaire).not.toBe(2.5);
    expect(detail.articleId).toBe(42);
    expect(detail.quantite).toBe(500);
    expect(detail.mode).toBe('panier');
  });

  it('affiche le détail au kilo, pas au gramme (illisible en rayon)', async () => {
    const el = creer(resultatConnu());
    await el.updateComplete;
    expect(el.shadowRoot!.querySelector('.prix-detail')!.textContent).toContain('€/kg');
  });
});

describe('cas n°3 — produit pesé, poids INCONNU : le cas le plus courant du catalogue', () => {
  function resultatPoidsInconnu(partiel: Partial<ResultatLookup> = {}): ResultatLookup {
    return resultatConnu({
      article: { id: 55, label: 'Farine', brand: null, net_quantity: null, image: null,
                nutriscore: null, kcal_per_base_unit: null },
      product: { id: 20, name: 'Farine', base_unit: 'g' },
      price: { price_per_base_unit: null, source: null, store: null },
      ...partiel,
    });
  }

  it('ÉCHEC PINGLÉ : sans poids, aucun prix par unité de base n’est calculé ni envoyable', async () => {
    const el = creer(resultatPoidsInconnu());
    await el.updateComplete;

    expect(el.shadowRoot!.querySelector<HTMLInputElement>('.prix-champ')!.value).toBe('');
    expect(el.shadowRoot!.querySelector('.prix-detail')).toBeNull();
    const bouton = el.shadowRoot!.querySelector<HTMLButtonElement>('.action-principale')!;
    expect(bouton.disabled).toBe(true);
    expect(el.shadowRoot!.querySelector('.motif-blocage')!.textContent).toContain('poids');
  });

  it('demande le poids avec un champ requis, vide (rien à deviner ici)', async () => {
    const el = creer(resultatPoidsInconnu());
    await el.updateComplete;
    const champPoids = el.shadowRoot!.querySelector<HTMLInputElement>('.poids-champ');
    expect(champPoids).not.toBeNull();
    expect(champPoids!.value).toBe('');
  });

  it('une fois le poids tapé, le prix se calcule et le bouton se débloque', async () => {
    const el = creer(resultatPoidsInconnu(), { mode: 'panier',
      connexion: { appeler: vi.fn().mockResolvedValue({}) } as unknown as Connexion });
    await el.updateComplete;

    saisir(el.shadowRoot!.querySelector<HTMLInputElement>('.poids-champ')!, '500');
    await el.updateComplete;
    saisir(el.shadowRoot!.querySelector<HTMLInputElement>('.prix-champ')!, '2,50');
    await el.updateComplete;

    expect(el.shadowRoot!.querySelector<HTMLButtonElement>('.action-principale')!.disabled).toBe(false);

    const recu = vi.fn();
    el.addEventListener('article-pret', (e) => recu((e as CustomEvent).detail));
    el.shadowRoot!.querySelector<HTMLButtonElement>('.action-principale')!.click();
    await laisserPasserLesMicrotaches();

    const detail = recu.mock.calls[0][0];
    expect(detail.prixUnitaire).toBeCloseTo(0.005);
    expect(detail.quantite).toBe(500);
  });

  it('envoie le poids tapé comme correction (article/update, l’article existe déjà) '
     + 'par la file hors-ligne — comme les ajouts au panier, jamais par un appel direct '
     + 'qui bloquerait tout en cas de coupure', async () => {
    const ajouter = vi.fn();
    // Si la correction passait encore par un appel direct, ce rejet la
    // ferait échouer et l'événement ne partirait jamais : la connexion ne
    // doit tout simplement plus être sollicitée pour cet appel-là.
    const appeler = vi.fn().mockRejectedValue(new Error('ne doit jamais être appelé pour cette correction'));
    const el = creer(resultatPoidsInconnu(), { mode: 'rangement',
      connexion: { appeler } as unknown as Connexion, file: { ajouter } });
    await el.updateComplete;

    saisir(el.shadowRoot!.querySelector<HTMLInputElement>('.poids-champ')!, '500');
    await el.updateComplete;

    const recu = vi.fn();
    el.addEventListener('article-pret', (e) => recu((e as CustomEvent).detail));
    el.shadowRoot!.querySelector<HTMLButtonElement>('.action-principale')!.click();
    await laisserPasserLesMicrotaches();

    expect(ajouter).toHaveBeenCalledWith('home_stock/article/update', {
      article_id: 55, fields: { net_quantity: 500 },
    });
    expect(appeler).not.toHaveBeenCalledWith('home_stock/article/update', expect.anything());
    // Et l'ajout n'a pas été bloqué : la file ne rejette jamais à l'appel.
    expect(recu).toHaveBeenCalledTimes(1);
  });

  it('préremplit depuis Open Food Facts quand un poids scanné existe (chemin article inconnu)', async () => {
    const { connexion } = connexionFactice({ productsList: [{ id: 1, base_unit: 'g' }] });
    const el = creer(resultatInconnu(), { connexion }); // off.net_quantity = 500
    await el.updateComplete;
    await laisserPasserLesMicrotaches();
    await el.updateComplete;
    expect(el.shadowRoot!.querySelector<HTMLInputElement>('.poids-champ')).toBeNull(); // déjà connu par OFF
  });

  it('n’envoie pas de correction net_quantity à la création quand Open Food Facts la '
     + 'fournit déjà : le serveur l’a déjà via `off`, la retaper ne doit pas la marquer '
     + '« manuelle » pour rien', async () => {
    const { connexion, appeler } = connexionFactice({ productsList: [{ id: 1, base_unit: 'g' }] });
    const el = creer(resultatInconnu(), { mode: 'rangement', connexion });
    await el.updateComplete;
    await laisserPasserLesMicrotaches();
    await el.updateComplete;

    el.shadowRoot!.querySelector<HTMLButtonElement>('.action-principale')!.click();
    await laisserPasserLesMicrotaches();

    const appelCreation = appeler.mock.calls.find((appel) => appel[0] === 'home_stock/article/create')!;
    expect(appelCreation[1].fields).toBeUndefined();
  });
});

describe('création d’un article inconnu', () => {
  it('crée l’article via la connexion puis émet article-pret avec l’id reçu et les '
     + 'champs ignorés, pour que l’écran suivant puisse les montrer', async () => {
    const { connexion, appeler } = connexionFactice({
      productsList: [{ id: 1, base_unit: 'g' }],
      create: { article_id: 77, product_id: 1, created: true, off_dropped_fields: ['nova', 'ecoscore'] },
    });

    const el = creer(resultatInconnu(), { mode: 'rangement', connexion });
    await el.updateComplete;
    await laisserPasserLesMicrotaches();
    await el.updateComplete;

    const recu = vi.fn();
    el.addEventListener('article-pret', (e) => recu((e as CustomEvent).detail));

    el.shadowRoot!.querySelector<HTMLButtonElement>('.action-principale')!.click();
    await laisserPasserLesMicrotaches();
    await el.updateComplete;

    expect(appeler).toHaveBeenCalledWith('home_stock/article/create', expect.objectContaining({
      code: '3229820129488', product_id: 1,
    }));
    expect(recu).toHaveBeenCalledTimes(1);
    expect(recu.mock.calls[0][0].articleId).toBe(77);
    // La fiche elle-même va disparaître dans le même geste (retour au
    // scanner) : c'est l'événement qui doit porter ce qui a été ignoré,
    // pas un état interne qui ne sera jamais peint.
    expect(recu.mock.calls[0][0].offDroppedFields).toEqual(['nova', 'ecoscore']);
  });

  it('affiche le refus du serveur (ex. nom de produit déjà pris) au lieu de rester muette', async () => {
    const { connexion } = connexionFactice({
      productsList: [{ id: 1, base_unit: 'g' }],
      createRejette: { code: 'integrity_error', message: 'Un produit nommé « Muesli » existe déjà.' },
    });
    const el = creer(resultatInconnu(), { mode: 'rangement', connexion });
    await el.updateComplete;
    await laisserPasserLesMicrotaches();
    await el.updateComplete;

    el.shadowRoot!.querySelector<HTMLButtonElement>('.action-principale')!.click();
    await laisserPasserLesMicrotaches();
    await el.updateComplete;

    expect(el.shadowRoot!.querySelector('.erreur-action')!.textContent)
      .toContain('existe déjà');
    // Le bouton redevient utilisable pour corriger et réessayer.
    expect(el.shadowRoot!.querySelector<HTMLButtonElement>('.action-principale')!.disabled).toBe(false);
  });

  it('résout l’unité d’un candidat déjà au catalogue via products/list, sans la deviner', async () => {
    const appeler = vi.fn().mockImplementation((type: string) => {
      if (type === 'home_stock/products/list') {
        return Promise.resolve({ products: [{ id: 1, base_unit: 'piece' }, { id: 2, base_unit: 'g' }] });
      }
      return Promise.resolve({ article_id: 99, product_id: 1, created: true, off_dropped_fields: [] });
    });
    const el = creer(resultatInconnu({ preselected_product_id: 1 }), { mode: 'panier',
      connexion: { appeler } as unknown as Connexion });
    await el.updateComplete;
    await laisserPasserLesMicrotaches();
    await el.updateComplete;

    // Le candidat présélectionné (id 1) est à la pièce d'après products/list :
    // le champ poids ne doit pas apparaître, et le prix se prend tel quel.
    expect(el.shadowRoot!.querySelector('.poids-champ')).toBeNull();
  });

  it('ÉCHEC PINGLÉ : un products/list qui échoue ne bloque pas la fiche pour toujours — '
     + 'un message apparaît, et un bouton Réessayer relance le même appel', async () => {
    const appeler = vi.fn().mockRejectedValueOnce(new Error('hors ligne'))
      .mockResolvedValueOnce({ products: [{ id: 1, base_unit: 'g' }] });
    const el = creer(resultatInconnu({ preselected_product_id: 1 }),
      { connexion: { appeler } as unknown as Connexion });
    await el.updateComplete;
    await laisserPasserLesMicrotaches();
    await el.updateComplete;

    // Premier échec : un message visible, pas un « Chargement… » éternel,
    // et le bouton principal reste bloqué puisque l'unité est toujours
    // inconnue pour ce candidat.
    expect(el.shadowRoot!.querySelector('.erreur-unite')).not.toBeNull();
    expect(el.shadowRoot!.querySelector<HTMLButtonElement>('.action-principale')!.disabled).toBe(true);
    const bouton = el.shadowRoot!.querySelector<HTMLButtonElement>('.reessayer-unite');
    expect(bouton).not.toBeNull();

    bouton!.click();
    await laisserPasserLesMicrotaches();
    await el.updateComplete;

    expect(appeler).toHaveBeenCalledTimes(2);
    expect(el.shadowRoot!.querySelector('.erreur-unite')).toBeNull();
    expect(el.shadowRoot!.querySelector<HTMLButtonElement>('.action-principale')!.disabled).toBe(false);
  });

  it('reste utilisable pour ce que products/list ne conditionne pas : choisir '
     + '« Nouveau produit » ne demande jamais la liste et n’est jamais bloqué par son échec', async () => {
    const appeler = vi.fn().mockRejectedValue(new Error('hors ligne'));
    const el = creer(resultatInconnu({ preselected_product_id: 1 }), { mode: 'rangement',
      connexion: { appeler } as unknown as Connexion });
    await el.updateComplete;
    await laisserPasserLesMicrotaches();
    await el.updateComplete;

    const radioNouveau = el.shadowRoot!.querySelector<HTMLInputElement>('input[name="produit"][value="new"]')!;
    radioNouveau.dispatchEvent(new Event('change'));
    await el.updateComplete;

    expect(el.shadowRoot!.querySelector<HTMLButtonElement>('.action-principale')!.disabled).toBe(false);
  });
});

describe('code scanné pour lequel Open Food Facts n’a pas répondu', () => {
  it('dit qu’Open Food Facts a été limité, plutôt que de ressembler à un produit inconnu', async () => {
    const el = creer(resultatInconnu({ off: null, off_raw: null, off_source: null,
      candidates: [], preselected_product_id: null, throttled: true }));
    await el.updateComplete;
    expect(el.shadowRoot!.querySelector('.alerte-off')!.textContent).toContain('limite');
  });

  it('dit qu’Open Food Facts n’a pas répondu à temps', async () => {
    const el = creer(resultatInconnu({ off: null, off_raw: null, off_source: null,
      candidates: [], preselected_product_id: null, timed_out: true }));
    await el.updateComplete;
    expect(el.shadowRoot!.querySelector('.alerte-off')!.textContent).toContain('temps');
  });

  it('n’affiche rien de tel pour un code vraiment inconnu (ni throttled ni timed_out)', async () => {
    const el = creer(resultatInconnu({ off: null, off_raw: null, off_source: null,
      candidates: [], preselected_product_id: null }));
    await el.updateComplete;
    expect(el.shadowRoot!.querySelector('.alerte-off')).toBeNull();
  });
});

describe('le bouton « Manger »', () => {
  // Le brief de cette tâche attend `vus).toEqual([1])`, sur un montage
  // laissé à compléter — mais aucune fixture de ce fichier n'a de produit
  // d'id 1 : `resultatConnu()` (le montage réellement utilisé par les
  // autres tests « article déjà connu » de ce fichier) rattache le produit
  // d'id 9. Corrigé ici plutôt que d'inventer une fixture qui n'existe pas
  // ailleurs dans ce fichier.
  it('offre de manger le produit rattaché', async () => {
    const element = creer(resultatConnu());
    await element.updateComplete;

    const vus: number[] = [];
    element.addEventListener('manger-produit', (e: any) => vus.push(e.detail.product_id));
    element.shadowRoot!.querySelector('.manger')?.dispatchEvent(new Event('click'));

    expect(vus).toEqual([9]);
  });

  it('ne propose rien tant qu’aucun produit n’est rattaché', async () => {
    const element = creer(resultatInconnu());
    await element.updateComplete;

    expect(element.shadowRoot!.querySelector('.manger')).toBeNull();
  });
});
