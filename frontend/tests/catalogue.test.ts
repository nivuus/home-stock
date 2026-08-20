import { afterEach, describe, expect, it, vi } from 'vitest';
import '../src/ecrans/catalogue';
import { brouillonDepuis, champsModifies, filtrerProduits,
         type Brouillon, type Produit, type Rayon } from '../src/ecrans/catalogue';
import type { Connexion } from '../src/connexion';
import type { Emplacement } from '../src/ecrans/rangement';

function produit(partiel: Partial<Produit> & { id: number }): Produit {
  return {
    name: `Produit ${partiel.id}`, base_unit: 'g', category_id: null, aisle_id: null,
    edible: 1, default_location_id: null, min_quantity: null, days_after_opening: null,
    default_shelf_life_days: null, reference_kcal: null, active: 1, external_ref: null,
    ...partiel,
  };
}

const RAYONS: Rayon[] = [
  { id: 1, name: 'Épicerie', position: 0 },
  { id: 2, name: 'Frais', position: 1 },
];
const EMPLACEMENTS: Emplacement[] = [
  { id: 1, name: 'Placard', kind: 'cupboard', position: 0 },
];

describe('brouillonDepuis', () => {
  it('rend une chaîne vide pour chaque champ optionnel absent, jamais "null"', () => {
    const b = brouillonDepuis(produit({ id: 1 }));
    expect(b).toEqual({
      name: 'Produit 1', aisle_id: '', category_id: '', default_location_id: '',
      min_quantity: '', default_shelf_life_days: '',
    });
  });

  it('convertit chaque identifiant et nombre connu en chaîne', () => {
    const b = brouillonDepuis(produit({
      id: 1, aisle_id: 2, category_id: 5, default_location_id: 1,
      min_quantity: 200, default_shelf_life_days: 7,
    }));
    expect(b).toEqual({
      name: 'Produit 1', aisle_id: '2', category_id: '5', default_location_id: '1',
      min_quantity: '200', default_shelf_life_days: '7',
    });
  });
});

describe('champsModifies', () => {
  it('ne rend rien quand rien n’a changé', () => {
    const p = produit({ id: 1, aisle_id: 2 });
    expect(champsModifies(brouillonDepuis(p), p)).toEqual({});
  });

  it('ne rend que les champs modifiés, jamais tous', () => {
    const p = produit({ id: 1, aisle_id: 2, min_quantity: 100 });
    const brouillon: Brouillon = { ...brouillonDepuis(p), min_quantity: '150' };
    expect(champsModifies(brouillon, p)).toEqual({ min_quantity: 150 });
  });

  it('efface un champ optionnel avec null plutôt qu’une chaîne vide', () => {
    const p = produit({ id: 1, aisle_id: 2 });
    const brouillon: Brouillon = { ...brouillonDepuis(p), aisle_id: '' };
    expect(champsModifies(brouillon, p)).toEqual({ aisle_id: null });
  });

  it('ignore une saisie de nom vide (le nom est requis, jamais effacé)', () => {
    const p = produit({ id: 1, name: 'Muesli' });
    const brouillon: Brouillon = { ...brouillonDepuis(p), name: '   ' };
    expect(champsModifies(brouillon, p)).toEqual({});
  });

  it('n’offre jamais de champ base_unit : le type Brouillon ne le porte pas', () => {
    const p = produit({ id: 1 });
    const champs = champsModifies(brouillonDepuis(p), p);
    expect(champs).not.toHaveProperty('base_unit');
  });
});

describe('filtrerProduits', () => {
  const nomRayon = (id: number | null) => RAYONS.find((r) => r.id === id)?.name ?? 'Sans rayon';
  const produits = [
    produit({ id: 1, name: 'Muesli Bio', aisle_id: 1 }),
    produit({ id: 2, name: 'Yaourt nature', aisle_id: 2 }),
  ];

  it('rend tout quand la recherche est vide', () => {
    expect(filtrerProduits(produits, '', nomRayon)).toHaveLength(2);
  });

  it('filtre par nom, insensible à la casse', () => {
    expect(filtrerProduits(produits, 'muesli', nomRayon).map((p) => p.id)).toEqual([1]);
  });

  it('filtre aussi par nom de rayon', () => {
    expect(filtrerProduits(produits, 'frais', nomRayon).map((p) => p.id)).toEqual([2]);
  });
});

function monter(props: { connexion?: Connexion; file?: unknown; enAttente?: number } = {}) {
  const element = document.createElement('home-stock-catalogue') as HTMLElement & {
    connexion?: Connexion; file?: unknown; enAttente: number; updateComplete: Promise<boolean>;
  };
  if (props.connexion) element.connexion = props.connexion;
  if (props.file) element.file = props.file;
  if (props.enAttente !== undefined) element.enAttente = props.enAttente;
  document.body.appendChild(element);
  return element;
}

function connexionFactice(reponses: (type: string, charge?: any) => Promise<unknown>): Connexion & {
  appeler: ReturnType<typeof vi.fn>;
} {
  return { appeler: vi.fn().mockImplementation(reponses) } as unknown as Connexion & { appeler: ReturnType<typeof vi.fn> };
}

async function laisserPasserLesMicrotaches(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

const PRODUITS = [produit({ id: 1, name: 'Muesli Bio', aisle_id: 1, min_quantity: 200 })];

function reponsesParDefaut(type: string, charge?: any): Promise<unknown> {
  if (type === 'home_stock/products/list') return Promise.resolve({ products: PRODUITS });
  if (type === 'home_stock/aisles/list') return Promise.resolve({ aisles: RAYONS });
  if (type === 'home_stock/locations/list') return Promise.resolve({ locations: EMPLACEMENTS });
  if (type === 'home_stock/batches/list') {
    return Promise.resolve({ batches: [{ product_id: 1, remaining: 350 }] });
  }
  if (type === 'home_stock/product/get') {
    return Promise.resolve({ product: PRODUITS.find((p) => p.id === charge?.product_id) });
  }
  return Promise.resolve({});
}

describe('<home-stock-catalogue>', () => {
  afterEach(() => {
    document.body.innerHTML = '';
  });

  it('charge produits, rayons, emplacements et lots au montage, et affiche la liste', async () => {
    const connexion = connexionFactice(reponsesParDefaut);
    const element = monter({ connexion });
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    expect(connexion.appeler).toHaveBeenCalledWith('home_stock/products/list');
    expect(connexion.appeler).toHaveBeenCalledWith('home_stock/aisles/list');
    expect(connexion.appeler).toHaveBeenCalledWith('home_stock/locations/list');
    expect(connexion.appeler).toHaveBeenCalledWith('home_stock/batches/list');

    const ligne = element.shadowRoot!.querySelector('.ligne')!;
    expect(ligne.querySelector('.nom')!.textContent).toBe('Muesli Bio');
    expect(ligne.querySelector('.meta')!.textContent).toContain('Épicerie');
    expect(ligne.querySelector('.meta')!.textContent).toContain('350');
  });

  it('filtre la liste affichée en tapant dans la recherche', async () => {
    const connexion = connexionFactice((type, charge) => {
      if (type === 'home_stock/products/list') {
        return Promise.resolve({ products: [...PRODUITS, produit({ id: 2, name: 'Yaourt', aisle_id: 2 })] });
      }
      return reponsesParDefaut(type, charge);
    });
    const element = monter({ connexion });
    await laisserPasserLesMicrotaches();
    await element.updateComplete;
    expect(element.shadowRoot!.querySelectorAll('.ligne')).toHaveLength(2);

    const recherche = element.shadowRoot!.querySelector('.recherche') as HTMLInputElement;
    recherche.value = 'yaourt';
    recherche.dispatchEvent(new Event('input'));
    await element.updateComplete;

    const lignes = element.shadowRoot!.querySelectorAll('.ligne');
    expect(lignes).toHaveLength(1);
    expect(lignes[0].querySelector('.nom')!.textContent).toBe('Yaourt');
  });

  it('affiche une erreur en français et un bouton « Réessayer » si le chargement échoue', async () => {
    const connexion = connexionFactice(() => Promise.reject(new Error('offline')));
    const element = monter({ connexion });
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    expect(element.shadowRoot!.querySelector('.erreur')!.textContent)
      .toContain('Impossible de récupérer le catalogue');
    expect(element.shadowRoot!.querySelector('.reessayer')).not.toBeNull();
  });

  it('ouvre l’édition d’un produit avec une lecture fraîche (product/get), pré-remplie', async () => {
    const connexion = connexionFactice(reponsesParDefaut);
    const element = monter({ connexion });
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    (element.shadowRoot!.querySelector('.modifier') as HTMLButtonElement).click();
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    expect(connexion.appeler).toHaveBeenCalledWith('home_stock/product/get', { product_id: 1 });
    const champNom = element.shadowRoot!.querySelector('.champ-nom') as HTMLInputElement;
    expect(champNom.value).toBe('Muesli Bio');
    // Le champ « unité de base » n'est jamais un input ni un select modifiable.
    expect(element.shadowRoot!.querySelector('[class*="unite"]')).toBeNull();
    expect(element.shadowRoot!.querySelector('.champ-lecture-seule')!.textContent).toContain('g');
  });

  it('n’envoie que les champs modifiés à home_stock/product/update, via la file', async () => {
    const connexion = connexionFactice(reponsesParDefaut);
    const ajouter = vi.fn().mockReturnValue('cle-test');
    const file = { ajouter, rejouer: vi.fn().mockResolvedValue(undefined), resultatDe: vi.fn().mockReturnValue('envoyee') };
    const element = monter({ connexion, file });
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    (element.shadowRoot!.querySelector('.modifier') as HTMLButtonElement).click();
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    const champSeuil = element.shadowRoot!.querySelector('.champ-seuil') as HTMLInputElement;
    champSeuil.value = '250';
    champSeuil.dispatchEvent(new Event('input'));
    await element.updateComplete;

    (element.shadowRoot!.querySelector('.enregistrer') as HTMLButtonElement).click();
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    expect(ajouter).toHaveBeenCalledWith('home_stock/product/update', {
      product_id: 1, fields: { min_quantity: 250 },
    });
  });

  it('n’écrit jamais directement par connexion : sans file, un enregistrement ne fait rien', async () => {
    const connexion = connexionFactice(reponsesParDefaut);
    const element = monter({ connexion });
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    (element.shadowRoot!.querySelector('.modifier') as HTMLButtonElement).click();
    await laisserPasserLesMicrotaches();
    await element.updateComplete;
    (connexion.appeler as ReturnType<typeof vi.fn>).mockClear();

    const champSeuil = element.shadowRoot!.querySelector('.champ-seuil') as HTMLInputElement;
    champSeuil.value = '250';
    champSeuil.dispatchEvent(new Event('input'));
    await element.updateComplete;

    (element.shadowRoot!.querySelector('.enregistrer') as HTMLButtonElement).click();
    await laisserPasserLesMicrotaches();

    expect(connexion.appeler).not.toHaveBeenCalledWith('home_stock/product/update', expect.anything());
  });

  it('ferme l’édition sans rien envoyer sur « Annuler »', async () => {
    const connexion = connexionFactice(reponsesParDefaut);
    const ajouter = vi.fn().mockReturnValue('cle-test');
    const file = { ajouter, rejouer: vi.fn().mockResolvedValue(undefined), resultatDe: vi.fn().mockReturnValue('envoyee') };
    const element = monter({ connexion, file });
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    (element.shadowRoot!.querySelector('.modifier') as HTMLButtonElement).click();
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    (element.shadowRoot!.querySelector('.annuler') as HTMLButtonElement).click();
    await element.updateComplete;

    expect(element.shadowRoot!.querySelector('.edition')).toBeNull();
    expect(ajouter).not.toHaveBeenCalled();
  });

  it('affiche le compteur d’actions en attente comme les autres écrans', async () => {
    const connexion = connexionFactice(reponsesParDefaut);
    const element = monter({ connexion, enAttente: 2 });
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    expect(element.shadowRoot!.querySelector('.en-attente')!.textContent).toContain('2');
  });
});
