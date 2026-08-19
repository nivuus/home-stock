import { afterEach, describe, expect, it, vi } from 'vitest';
import '../src/ecrans/fiche';
import { prixBaseDepuisSaisie, prixPaquetAffiche } from '../src/ecrans/fiche';
import type { Connexion } from '../src/connexion';
import type { ResultatLookup } from '../src/ecrans/fiche';

/** Attend que les microtâches en attente (le `.then()` de la validation, qui
 *  appelle `article/create` avant d'émettre l'événement) se soient exécutées. */
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

function creer(resultat: ResultatLookup, options: { mode?: 'panier' | 'rangement'; connexion?: Connexion } = {}) {
  const element = document.createElement('home-stock-fiche') as HTMLElement & {
    resultat: ResultatLookup; mode: 'panier' | 'rangement'; connexion?: Connexion;
    updateComplete: Promise<boolean>;
  };
  element.resultat = resultat;
  element.mode = options.mode ?? 'rangement';
  if (options.connexion) element.connexion = options.connexion;
  document.body.appendChild(element);
  return element;
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
    const parBase = prixBaseDepuisSaisie('2,50', 500);
    expect(parBase).toBeCloseTo(0.005);
    expect(parBase).not.toBe(2.5);
  });

  it('accepte le point comme séparateur décimal', () => {
    expect(prixBaseDepuisSaisie('2.50', 500)).toBeCloseTo(0.005);
  });

  it('traite un paquet sans poids net comme une unité de base (ex: à la pièce)', () => {
    expect(prixBaseDepuisSaisie('2,50', null)).toBeCloseTo(2.5);
  });

  it('rend null pour une saisie vide ou invalide', () => {
    expect(prixBaseDepuisSaisie('', 500)).toBeNull();
    expect(prixBaseDepuisSaisie('abc', 500)).toBeNull();
  });

  it('affiche le prix du paquet à partir du prix par unité de base (aller-retour)', () => {
    expect(prixPaquetAffiche(0.005, 500)).toBe('2,50');
    expect(prixPaquetAffiche(prixBaseDepuisSaisie('2,50', 500), 500)).toBe('2,50');
  });

  it('rend une chaîne vide quand il n’y a pas de prix', () => {
    expect(prixPaquetAffiche(null, 500)).toBe('');
  });
});

describe('le champ prix, sur la fiche elle-même', () => {
  it('préremplit le prix du paquet, pas le prix par gramme', async () => {
    // price_per_base_unit = 0,004 €/g, net_quantity = 500 g => 2,00 € le paquet.
    const el = creer(resultatConnu());
    await el.updateComplete;
    const champ = el.shadowRoot!.querySelector<HTMLInputElement>('.prix-champ')!;
    expect(champ.value).toBe('2,00');
  });

  it('convertit la saisie en prix par unité de base avant de l’envoyer, sans réseau', async () => {
    const el = creer(resultatConnu(), { mode: 'panier' });
    await el.updateComplete;

    const champ = el.shadowRoot!.querySelector<HTMLInputElement>('.prix-champ')!;
    champ.value = '2,50';
    champ.dispatchEvent(new Event('input'));
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
});

describe('création d’un article inconnu', () => {
  it('crée l’article via la connexion puis émet article-pret avec l’id reçu', async () => {
    const appeler = vi.fn().mockResolvedValue({
      article_id: 77, product_id: 1, created: true, off_dropped_fields: ['nova', 'ecoscore'],
    });
    const connexionFactice = { appeler } as unknown as Connexion;

    const el = creer(resultatInconnu(), { mode: 'rangement', connexion: connexionFactice });
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

    // Ce que Open Food Facts a proposé et que l'on a jugé trop peu fiable
    // pour l'enregistrer doit rester visible, pas disparaître en silence.
    const note = el.shadowRoot!.querySelector('.ignores');
    expect(note?.textContent).toContain('NOVA');
    expect(note?.textContent).toContain('Éco-score');
  });
});
