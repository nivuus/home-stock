import { afterEach, describe, expect, it, vi } from 'vitest';
import '../src/ecrans/catalogue';
import { brouillonDepuis, champsModifies, filtrerProduits, analyserNombre, CHAMPS_CATALOGUE_MODIFIABLES,
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
      name: 'Produit 1', aisle_id: '', default_location_id: '',
      min_quantity: '', default_shelf_life_days: '',
    });
  });

  it('convertit chaque identifiant et nombre connu en chaîne', () => {
    const b = brouillonDepuis(produit({
      id: 1, aisle_id: 2, default_location_id: 1,
      min_quantity: 200, default_shelf_life_days: 7,
    }));
    expect(b).toEqual({
      name: 'Produit 1', aisle_id: '2', default_location_id: '1',
      min_quantity: '200', default_shelf_life_days: '7',
    });
  });

  it('ne porte aucune trace de category_id : ce champ n’est plus éditable (lecture seule, comme base_unit)', () => {
    const b = brouillonDepuis(produit({ id: 1, category_id: 5 }));
    expect(b).not.toHaveProperty('category_id');
  });
});

describe('analyserNombre', () => {
  it('accepte la virgule décimale d’un clavier français, comme le point', () => {
    expect(analyserNombre('1,5')).toEqual({ ok: true, valeur: 1.5 });
    expect(analyserNombre('1.5')).toEqual({ ok: true, valeur: 1.5 });
  });

  it('un champ vide est un effacement voulu : null, pas un refus', () => {
    expect(analyserNombre('')).toEqual({ ok: true, valeur: null });
    expect(analyserNombre('   ')).toEqual({ ok: true, valeur: null });
  });

  it('refuse explicitement du texte qui n’est pas un nombre, plutôt que de rendre NaN', () => {
    expect(analyserNombre('7 jours')).toEqual({ ok: false });
    expect(analyserNombre('abc')).toEqual({ ok: false });
  });
});

describe('champsModifies', () => {
  it('ne rend rien quand rien n’a changé', () => {
    const p = produit({ id: 1, aisle_id: 2 });
    expect(champsModifies(brouillonDepuis(p), p)).toEqual({ ok: true, champs: {} });
  });

  it('ne rend que les champs modifiés, jamais tous', () => {
    const p = produit({ id: 1, aisle_id: 2, min_quantity: 100 });
    const brouillon: Brouillon = { ...brouillonDepuis(p), min_quantity: '150' };
    expect(champsModifies(brouillon, p)).toEqual({ ok: true, champs: { min_quantity: 150 } });
  });

  it('efface un champ optionnel avec null plutôt qu’une chaîne vide', () => {
    const p = produit({ id: 1, aisle_id: 2 });
    const brouillon: Brouillon = { ...brouillonDepuis(p), aisle_id: '' };
    expect(champsModifies(brouillon, p)).toEqual({ ok: true, champs: { aisle_id: null } });
  });

  it('ignore une saisie de nom vide (le nom est requis, jamais effacé)', () => {
    const p = produit({ id: 1, name: 'Muesli' });
    const brouillon: Brouillon = { ...brouillonDepuis(p), name: '   ' };
    expect(champsModifies(brouillon, p)).toEqual({ ok: true, champs: {} });
  });

  it('n’offre jamais de champ base_unit ni category_id : le type Brouillon ne les porte pas, '
     + 'et toute clé émise reste dans la liste blanche de l’écran', () => {
    const p = produit({ id: 1, aisle_id: 2, default_location_id: 1, min_quantity: 100, default_shelf_life_days: 5 });
    // Brouillon où chaque champ modifiable a changé : le pire cas pour une fuite de clé imprévue.
    const brouillon: Brouillon = {
      name: 'Nouveau nom', aisle_id: '1', default_location_id: '',
      min_quantity: '150', default_shelf_life_days: '10',
    };
    const resultat = champsModifies(brouillon, p);
    expect(resultat.ok).toBe(true);
    if (!resultat.ok) throw new Error('inattendu');
    expect(Object.keys(resultat.champs).length).toBeGreaterThan(0);
    for (const cle of Object.keys(resultat.champs)) {
      expect(CHAMPS_CATALOGUE_MODIFIABLES).toContain(cle);
    }
    expect(resultat.champs).not.toHaveProperty('base_unit');
    expect(resultat.champs).not.toHaveProperty('category_id');
  });

  describe('un champ numérique mal saisi refuse l’édition entière, sans rien envoyer', () => {
    it('« 1,5 » (virgule décimale) est accepté et envoyé comme 1.5 — pas effacé', () => {
      const p = produit({ id: 1, min_quantity: 100 });
      const brouillon: Brouillon = { ...brouillonDepuis(p), min_quantity: '1,5' };
      expect(champsModifies(brouillon, p)).toEqual({ ok: true, champs: { min_quantity: 1.5 } });
    });

    it('« 7 jours » (texte, pas un nombre pur) refuse l’édition avec un message en français, '
       + 'sans jamais renvoyer null pour ce champ', () => {
      const p = produit({ id: 1, default_shelf_life_days: 5 });
      const brouillon: Brouillon = { ...brouillonDepuis(p), default_shelf_life_days: '7 jours' };
      const resultat = champsModifies(brouillon, p);
      expect(resultat.ok).toBe(false);
      if (resultat.ok) throw new Error('inattendu');
      expect(resultat.erreur).toContain('Durée de conservation');
      expect(resultat.erreur).toContain('7 jours');
    });

    it('un champ vidé exprès reste un null explicite, jamais confondu avec une saisie invalide', () => {
      const p = produit({ id: 1, min_quantity: 100 });
      const brouillon: Brouillon = { ...brouillonDepuis(p), min_quantity: '' };
      expect(champsModifies(brouillon, p)).toEqual({ ok: true, champs: { min_quantity: null } });
    });
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

const PRODUITS = [produit({ id: 1, name: 'Muesli Bio', aisle_id: 1, category_id: 7, min_quantity: 200 })];

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

async function ouvrirEditionDuPremierProduit(element: HTMLElement & { updateComplete: Promise<boolean> }): Promise<void> {
  (element.shadowRoot!.querySelector('.modifier') as HTMLButtonElement).click();
  await laisserPasserLesMicrotaches();
  await element.updateComplete;
}

function saisir(element: HTMLElement, selecteur: string, valeur: string): void {
  const champ = element.shadowRoot!.querySelector(selecteur) as HTMLInputElement;
  champ.value = valeur;
  champ.dispatchEvent(new Event('input'));
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

    saisir(element, '.recherche', 'yaourt');
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

  it('ouvre l’édition d’un produit avec une lecture fraîche (product/get), pré-remplie ; '
     + 'unité de base ET catégorie sont en lecture seule, jamais un champ modifiable', async () => {
    const connexion = connexionFactice(reponsesParDefaut);
    const element = monter({ connexion });
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    await ouvrirEditionDuPremierProduit(element);

    expect(connexion.appeler).toHaveBeenCalledWith('home_stock/product/get', { product_id: 1 });
    const champNom = element.shadowRoot!.querySelector('.champ-nom') as HTMLInputElement;
    expect(champNom.value).toBe('Muesli Bio');

    // Aucun input ni select pour l'unité de base ou la catégorie : seulement
    // du texte en lecture seule, deux paragraphes distincts.
    expect(element.shadowRoot!.querySelector('.champ-categorie')).toBeNull();
    expect(element.shadowRoot!.querySelector('.champ-unite')).toBeNull();
    const lectureSeule = Array.from(element.shadowRoot!.querySelectorAll('.champ-lecture-seule'))
      .map((p) => p.textContent);
    expect(lectureSeule.some((t) => t?.includes('g'))).toBe(true);
    expect(lectureSeule.some((t) => t?.includes('Catégorie') && t.includes('7'))).toBe(true);

    // Chaque input/select réellement présent correspond à un nom de classe
    // qui figure dans la liste blanche des champs modifiables — pas de
    // champ fantôme qu'on aurait oublié de retirer du DOM.
    const champsPresents = Array.from(element.shadowRoot!.querySelectorAll('.edition input, .edition select'))
      .map((c) => c.className.replace('champ-', ''));
    expect(champsPresents).toEqual(
      expect.arrayContaining(['nom', 'rayon', 'emplacement', 'seuil', 'conservation']));
    expect(champsPresents).not.toContain('categorie');
    expect(champsPresents).not.toContain('unite');
  });

  it('n’envoie que les champs modifiés à home_stock/product/update, via la file', async () => {
    const connexion = connexionFactice(reponsesParDefaut);
    const ajouter = vi.fn().mockReturnValue('cle-test');
    const file = { ajouter, rejouer: vi.fn().mockResolvedValue(undefined), resultatDe: vi.fn().mockReturnValue('envoyee') };
    const element = monter({ connexion, file });
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    await ouvrirEditionDuPremierProduit(element);
    saisir(element, '.champ-seuil', '250');
    await element.updateComplete;

    (element.shadowRoot!.querySelector('.enregistrer') as HTMLButtonElement).click();
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    expect(ajouter).toHaveBeenCalledWith('home_stock/product/update', {
      product_id: 1, fields: { min_quantity: 250 },
    });
  });

  it('« 1,5 » tapé dans le seuil est envoyé comme 1.5, pas effacé par la virgule française', async () => {
    const connexion = connexionFactice(reponsesParDefaut);
    const ajouter = vi.fn().mockReturnValue('cle-test');
    const file = { ajouter, rejouer: vi.fn().mockResolvedValue(undefined), resultatDe: vi.fn().mockReturnValue('envoyee') };
    const element = monter({ connexion, file });
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    await ouvrirEditionDuPremierProduit(element);
    saisir(element, '.champ-seuil', '1,5');
    await element.updateComplete;

    (element.shadowRoot!.querySelector('.enregistrer') as HTMLButtonElement).click();
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    expect(ajouter).toHaveBeenCalledWith('home_stock/product/update', {
      product_id: 1, fields: { min_quantity: 1.5 },
    });
  });

  it('« 7 jours » tapé dans la durée de conservation refuse l’envoi entier : rien n’est mis en file, '
     + 'et un message en français explique pourquoi — jamais un null silencieux', async () => {
    const connexion = connexionFactice(reponsesParDefaut);
    const ajouter = vi.fn().mockReturnValue('cle-test');
    const file = { ajouter, rejouer: vi.fn().mockResolvedValue(undefined), resultatDe: vi.fn().mockReturnValue('envoyee') };
    const element = monter({ connexion, file });
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    await ouvrirEditionDuPremierProduit(element);
    saisir(element, '.champ-conservation', '7 jours');
    await element.updateComplete;

    (element.shadowRoot!.querySelector('.enregistrer') as HTMLButtonElement).click();
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    expect(ajouter).not.toHaveBeenCalled();
    const erreur = element.shadowRoot!.querySelector('.edition .erreur');
    expect(erreur).not.toBeNull();
    expect(erreur!.textContent).toContain('Durée de conservation');
    // L'édition reste ouverte, avec la saisie fautive toujours visible —
    // rien n'est perdu ni faussement annoncé comme enregistré.
    expect(element.shadowRoot!.querySelector('.edition')).not.toBeNull();
  });

  it('vider le champ seuil (effacement voulu) envoie explicitement null, pas un refus', async () => {
    const connexion = connexionFactice(reponsesParDefaut);
    const ajouter = vi.fn().mockReturnValue('cle-test');
    const file = { ajouter, rejouer: vi.fn().mockResolvedValue(undefined), resultatDe: vi.fn().mockReturnValue('envoyee') };
    const element = monter({ connexion, file });
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    await ouvrirEditionDuPremierProduit(element);
    saisir(element, '.champ-seuil', '');
    await element.updateComplete;

    (element.shadowRoot!.querySelector('.enregistrer') as HTMLButtonElement).click();
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    expect(ajouter).toHaveBeenCalledWith('home_stock/product/update', {
      product_id: 1, fields: { min_quantity: null },
    });
  });

  it('n’écrit jamais directement par connexion : sans file, un enregistrement ne fait rien', async () => {
    const connexion = connexionFactice(reponsesParDefaut);
    const element = monter({ connexion });
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    await ouvrirEditionDuPremierProduit(element);
    (connexion.appeler as ReturnType<typeof vi.fn>).mockClear();

    saisir(element, '.champ-seuil', '250');
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

    await ouvrirEditionDuPremierProduit(element);

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
