import { afterEach, describe, expect, it, vi } from 'vitest';
import '../src/ecrans/catalogue';
import { brouillonDepuis, champsModifies, filtrerProduits, CHAMPS_CATALOGUE_MODIFIABLES,
         type Brouillon, type Produit, type Rayon } from '../src/ecrans/catalogue';
import { analyserNombre } from '../src/nombres';
import type { Connexion } from '../src/connexion';
import type { Emplacement } from '../src/ecrans/rangement';

function produit(partiel: Partial<Produit> & { id: number }): Produit {
  return {
    name: `Produit ${partiel.id}`, base_unit: 'g', category_id: null, aisle_id: null,
    edible: 1, default_location_id: null, min_quantity: null, days_after_opening: null,
    default_shelf_life_days: null, reference_kcal: null, manual_portion: null,
    active: 1, external_ref: null,
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
      min_quantity: '', default_shelf_life_days: '', manual_portion: '',
    });
  });

  it('convertit chaque identifiant et nombre connu en chaîne', () => {
    const b = brouillonDepuis(produit({
      id: 1, aisle_id: 2, default_location_id: 1,
      min_quantity: 200, default_shelf_life_days: 7,
    }));
    expect(b).toEqual({
      name: 'Produit 1', aisle_id: '2', default_location_id: '1',
      min_quantity: '200', default_shelf_life_days: '7', manual_portion: '',
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
      min_quantity: '150', default_shelf_life_days: '10', manual_portion: '45',
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
    const ajouter = vi.fn().mockReturnValue({ cle: 'cle-test', sort: Promise.resolve('envoyee') });
    const file = { ajouter, rejouer: vi.fn().mockResolvedValue(undefined) };
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
    const ajouter = vi.fn().mockReturnValue({ cle: 'cle-test', sort: Promise.resolve('envoyee') });
    const file = { ajouter, rejouer: vi.fn().mockResolvedValue(undefined) };
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
    const ajouter = vi.fn().mockReturnValue({ cle: 'cle-test', sort: Promise.resolve('envoyee') });
    const file = { ajouter, rejouer: vi.fn().mockResolvedValue(undefined) };
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
    const ajouter = vi.fn().mockReturnValue({ cle: 'cle-test', sort: Promise.resolve('envoyee') });
    const file = { ajouter, rejouer: vi.fn().mockResolvedValue(undefined) };
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
    const ajouter = vi.fn().mockReturnValue({ cle: 'cle-test', sort: Promise.resolve('envoyee') });
    const file = { ajouter, rejouer: vi.fn().mockResolvedValue(undefined) };
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

  it('offre de manger un produit du catalogue', async () => {
    const connexion = connexionFactice(reponsesParDefaut);
    const element = monter({ connexion });
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    const vus: number[] = [];
    element.addEventListener('manger-produit', (e: any) => vus.push(e.detail.product_id));
    element.shadowRoot!.querySelector('.manger')?.dispatchEvent(new Event('click'));

    expect(vus.length).toBe(1);
    expect(vus).toEqual([1]);
  });
});

describe('« Ma portion » au catalogue', () => {
  afterEach(() => { document.body.innerHTML = ''; });

  it('figure dans la liste blanche des champs modifiables', () => {
    // Filet statique : le serveur refuse toute colonne hors PRODUCT_EDITABLE,
    // et cet écran ne doit pas pouvoir en tenter une autre.
    expect(CHAMPS_CATALOGUE_MODIFIABLES).toContain('manual_portion');
  });

  it('rend une chaîne vide quand aucune portion n’a été fixée', () => {
    expect(brouillonDepuis(produit({ id: 1 })).manual_portion).toBe('');
    expect(brouillonDepuis(produit({ id: 1, manual_portion: 45 })).manual_portion).toBe('45');
  });

  it('une saisie vide efface la portion (null), et rend la main à la médiane apprise', () => {
    const p = produit({ id: 1, manual_portion: 45 });
    const brouillon: Brouillon = { ...brouillonDepuis(p), manual_portion: '' };
    expect(champsModifies(brouillon, p)).toEqual({ ok: true, champs: { manual_portion: null } });
  });

  it('accepte la virgule décimale, comme partout ailleurs', () => {
    const p = produit({ id: 1 });
    const brouillon: Brouillon = { ...brouillonDepuis(p), manual_portion: '45,5' };
    expect(champsModifies(brouillon, p)).toEqual({ ok: true, champs: { manual_portion: 45.5 } });
  });

  it('une saisie illisible refuse l’édition ENTIÈRE, sans envoyer les autres champs', () => {
    const p = produit({ id: 1 });
    const brouillon: Brouillon = {
      ...brouillonDepuis(p), name: 'Riz complet', manual_portion: 'une louche' };
    const resultat = champsModifies(brouillon, p);
    expect(resultat.ok).toBe(false);
    expect((resultat as { erreur: string }).erreur).toContain('Ma portion');
  });

  it('ne renvoie pas une valeur inchangée', () => {
    const p = produit({ id: 1, manual_portion: 45 });
    expect(champsModifies(brouillonDepuis(p), p)).toEqual({ ok: true, champs: {} });
  });

  it('masque le champ pour un produit suivi à la pièce', async () => {
    const piece = produit({ id: 1, name: 'Yaourt', base_unit: 'piece', aisle_id: 1 });
    const connexion = connexionFactice((type: string, charge?: any) => {
      if (type === 'home_stock/products/list') return Promise.resolve({ products: [piece] });
      if (type === 'home_stock/product/get') return Promise.resolve({ product: piece });
      return reponsesParDefaut(type, charge);
    });
    const element = monter({ connexion });
    await laisserPasserLesMicrotaches();
    await element.updateComplete;
    await ouvrirEditionDuPremierProduit(element);

    expect(element.shadowRoot!.querySelector('.champ-portion')).toBeNull();
  });

  it('affiche le champ et sa mention pour un produit au gramme', async () => {
    const connexion = connexionFactice(reponsesParDefaut);
    const element = monter({ connexion });
    await laisserPasserLesMicrotaches();
    await element.updateComplete;
    await ouvrirEditionDuPremierProduit(element);

    expect(element.shadowRoot!.querySelector('.champ-portion')).not.toBeNull();
    expect(element.shadowRoot!.textContent).toContain('vide = déduite automatiquement');
  });
});

// --- lot 6 : la vue dense, au-delà de 1000 px -------------------------------

const TROIS_CENTS = Array.from({ length: 300 }, (_, i) =>
  produit({ id: i + 1, name: `Produit ${i + 1}`, aisle_id: (i % 2) + 1,
            category_id: 7, min_quantity: 200 }));

function reponsesCatalogue(produits: Produit[]) {
  return (type: string, charge?: any): Promise<unknown> => {
    if (type === 'home_stock/products/list') return Promise.resolve({ products: produits });
    if (type === 'home_stock/batches/list') return Promise.resolve({ batches: [] });
    if (type === 'home_stock/product/get') {
      return Promise.resolve({ product: produits.find((p) => p.id === charge?.product_id) });
    }
    return reponsesParDefaut(type, charge);
  };
}

// `produits` par défaut à TROIS_CENTS : les tests existants (« vue dense »)
// n'ont pas à connaître le fenêtrage pour continuer de monter le catalogue.
async function monterCatalogue(options: { large: boolean; file?: unknown; produits?: Produit[] }) {
  const connexion = connexionFactice(reponsesCatalogue(options.produits ?? TROIS_CENTS));
  const element = monter({ connexion, file: options.file }) as HTMLElement & {
    large: boolean; updateComplete: Promise<boolean>;
  };
  element.large = options.large;
  await laisserPasserLesMicrotaches();
  await element.updateComplete;
  return element;
}

function entetes(element: HTMLElement): string[] {
  return Array.from(element.shadowRoot!.querySelectorAll('thead th'))
    .map((th) => th.textContent!.trim());
}

function ligne(element: HTMLElement, index: number): HTMLElement {
  return element.shadowRoot!.querySelectorAll('tbody tr')[index] as HTMLElement;
}

describe('<home-stock-catalogue> : la vue dense (lot 6)', () => {
  afterEach(() => { document.body.innerHTML = ''; });

  it('rend un tableau à colonnes au-delà de 1000 px', async () => {
    const e = await monterCatalogue({ large: true });
    expect(e.shadowRoot!.querySelector('table')).not.toBeNull();
    // Les cinq colonnes de données de la spec, plus la colonne d'actions —
    // les boutons doivent bien tenir quelque part, et son en-tête reste vide
    // pour ne pas annoncer une donnée qui n'en est pas une.
    expect(entetes(e)).toEqual(['Nom', 'Unité', 'Seuil', 'Catégorie',
                                'Conservation', '']);
    // Fenêtrée depuis la tâche 12 (cinquante à la fois, pas trois cents) —
    // voir la description « ne rend pas la liste en entier », plus bas.
    expect(e.shadowRoot!.querySelectorAll('tbody tr')).toHaveLength(50);
  });

  it('reste une liste empilée en étroit', async () => {
    const e = await monterCatalogue({ large: false });
    expect(e.shadowRoot!.querySelector('table')).toBeNull();
    expect(e.shadowRoot!.querySelectorAll('.ligne')).toHaveLength(50);
  });

  it('édite une ligne sans quitter la liste', async () => {
    // C'est TOUT l'intérêt de la largeur : corriger, voir la ligne suivante,
    // corriger. Un formulaire qui remplace la liste annule le gain.
    const ajouter = vi.fn().mockReturnValue({ cle: 'c', sort: Promise.resolve('envoyee') });
    const file = { ajouter, rejouer: vi.fn().mockResolvedValue(undefined) };
    const e = await monterCatalogue({ large: true, file });

    (ligne(e, 12).querySelector('.modifier') as HTMLButtonElement).click();
    await laisserPasserLesMicrotaches();
    await e.updateComplete;
    expect(e.shadowRoot!.querySelectorAll('tbody tr')).toHaveLength(50);

    saisir(e, '.champ-seuil', '4');
    await e.updateComplete;
    (e.shadowRoot!.querySelector('.enregistrer') as HTMLButtonElement).click();
    await laisserPasserLesMicrotaches();
    await e.updateComplete;

    // `min_stock` n'existe pas : la colonne s'appelle `min_quantity`, des
    // deux côtés du websocket depuis le lot 1.
    expect(ajouter).toHaveBeenCalledWith('home_stock/product/update', {
      product_id: 13, fields: { min_quantity: 4 },
    });
  });

  it("n'ouvre jamais l'unité de base ni la catégorie, même en large", async () => {
    // Élargir un écran n'élargit pas ses droits : seul
    // `home_stock/product/convert_unit` change une unité, atomiquement, et
    // aucun `categories/list` n'existe pour vérifier une saisie.
    const e = await monterCatalogue({ large: true });
    (ligne(e, 12).querySelector('.modifier') as HTMLButtonElement).click();
    await laisserPasserLesMicrotaches();
    await e.updateComplete;

    expect(e.shadowRoot!.querySelector('.champ-unite')).toBeNull();
    expect(e.shadowRoot!.querySelector('.champ-categorie')).toBeNull();
  });

  it('refuse une virgule décimale mal formée plutôt que de deviner, en large aussi', async () => {
    // `Number('7 jours')` vaut NaN et NaN sérialisé vaut null : sans ce refus,
    // une saisie douteuse EFFACE un seuil en laissant croire à un
    // enregistrement réussi. La règle vient de l'étroit ; elle ne se perd pas
    // en chemin.
    const ajouter = vi.fn().mockReturnValue({ cle: 'c', sort: Promise.resolve('envoyee') });
    const file = { ajouter, rejouer: vi.fn().mockResolvedValue(undefined) };
    const e = await monterCatalogue({ large: true, file });

    (ligne(e, 0).querySelector('.modifier') as HTMLButtonElement).click();
    await laisserPasserLesMicrotaches();
    await e.updateComplete;
    saisir(e, '.champ-conservation', '7 jours');
    await e.updateComplete;
    (e.shadowRoot!.querySelector('.enregistrer') as HTMLButtonElement).click();
    await laisserPasserLesMicrotaches();
    await e.updateComplete;

    expect(ajouter).not.toHaveBeenCalled();
    expect(e.shadowRoot!.querySelector('.erreur')!.textContent)
      .toContain('nombre invalide');
  });

  it('passe toute écriture par la file hors-ligne, jamais par la connexion', async () => {
    const e = await monterCatalogue({ large: true });   // aucune file fournie
    const connexion = (e as any).connexion;
    (ligne(e, 0).querySelector('.modifier') as HTMLButtonElement).click();
    await laisserPasserLesMicrotaches();
    await e.updateComplete;
    saisir(e, '.champ-seuil', '9');
    await e.updateComplete;
    (e.shadowRoot!.querySelector('.enregistrer') as HTMLButtonElement).click();
    await laisserPasserLesMicrotaches();

    expect(connexion.appeler).not.toHaveBeenCalledWith(
      'home_stock/product/update', expect.anything());
  });
});

// --- tâche 12 : le fenêtrage -------------------------------------------
//
// Réutilise TROIS_CENTS (défini plus haut pour le lot 6) plutôt que de
// redéfinir trois cents objets ad hoc à chaque test : mêmes données, un
// seul type `Produit` correctement rempli (`produit()`), et « Produit 287 »
// existe bien dedans (id 287, nom `Produit 287`).

describe('catalogue : la liste ne se rend pas en entier', () => {
  afterEach(() => { document.body.innerHTML = ''; });

  it('ne rend qu’une fenêtre de produits, pas les trois cents', async () => {
    const el = await monterCatalogue({ large: false, produits: TROIS_CENTS });
    // La classe est `.ligne` — vérifié dans catalogue.ts : `<article class="ligne">`
    // en étroit, `<tr class="ligne …">` en dense.
    const lignes = el.shadowRoot!.querySelectorAll('.ligne');
    expect(lignes.length).toBeGreaterThan(0);
    expect(lignes.length).toBeLessThan(80);
  });

  // La même preuve côté DENSE (le `<tbody>` de `rendreDense`) : les deux
  // rendus mappent `produitsFiltres` indépendamment, et ne fenêtrer que l'un
  // laisserait le bureau rendre les trois cents lignes.
  it('ne rend qu’une fenêtre de produits en vue dense non plus', async () => {
    const el = await monterCatalogue({ large: true, produits: TROIS_CENTS });
    const lignes = el.shadowRoot!.querySelectorAll('tbody tr');
    expect(lignes.length).toBeGreaterThan(0);
    expect(lignes.length).toBeLessThan(80);
  });

  it('garde la recherche atteignable en tête de liste', async () => {
    const el = await monterCatalogue({ large: false, produits: [] });
    // Preuve que `produits: []` a vraiment été transmis à `monterCatalogue`
    // (et pas silencieusement retombé sur le défaut TROIS_CENTS, non vide) :
    // sans ça, ce test resterait vert même si la clé `produits` était
    // ignorée — vérifié en cassant `monterCatalogue` (rapport de tâche).
    expect(el.shadowRoot!.textContent).toContain('Aucun produit.');
    // `.recherche` est l'<input> LUI-MÊME, pas un conteneur : c'est donc lui
    // qui devient collant.
    const recherche = el.shadowRoot!.querySelector('input.recherche');
    expect(recherche).not.toBeNull();
    const styles = (el.constructor as unknown as { styles: { cssText: string }[] });
    const feuille = styles.styles.map((s) => s.cssText).join('');
    // `.volet-edition` (lot 6) porte déjà `position: sticky` ailleurs dans la
    // même feuille : un `toContain('position: sticky')` global passerait
    // sans que `.recherche` soit collante pour autant — vérifié en cassant
    // ce test (voir le rapport de tâche). On isole donc la règle
    // `.recherche { … }` avant de la sonder.
    const regleRecherche = feuille.match(/\.recherche\s*\{[^}]*\}/);
    expect(regleRecherche).not.toBeNull();
    expect(regleRecherche![0]).toContain('position: sticky');
  });

  it('rend le produit cherché même s’il est au-delà de la fenêtre', async () => {
    // Le fenêtrage ne doit pas rendre un produit INTROUVABLE : la recherche
    // filtre d'abord, la fenêtre s'applique ensuite.
    const el = await monterCatalogue({ large: false, produits: TROIS_CENTS });
    const champ = el.shadowRoot!.querySelector('input.recherche') as HTMLInputElement;
    champ.value = 'Produit 287';
    champ.dispatchEvent(new Event('input'));
    await el.updateComplete;
    expect(el.shadowRoot!.textContent).toContain('Produit 287');
  });

  it('un bouton « voir plus » agrandit la fenêtre sans tout recharger', async () => {
    const el = await monterCatalogue({ large: false, produits: TROIS_CENTS });
    const avant = el.shadowRoot!.querySelectorAll('.ligne').length;
    const boutonVoirPlus = Array.from(el.shadowRoot!.querySelectorAll('hs-button'))
      .find((b) => b.textContent?.includes('produits de plus')) as HTMLElement;
    expect(boutonVoirPlus).toBeTruthy();
    boutonVoirPlus.click();
    await el.updateComplete;
    const apres = el.shadowRoot!.querySelectorAll('.ligne').length;
    expect(apres).toBeGreaterThan(avant);
  });

  it('remet la fenêtre à sa taille de départ quand la recherche change', async () => {
    const el = await monterCatalogue({ large: false, produits: TROIS_CENTS });
    const boutonVoirPlus = Array.from(el.shadowRoot!.querySelectorAll('hs-button'))
      .find((b) => b.textContent?.includes('produits de plus')) as HTMLElement;
    boutonVoirPlus.click();
    await el.updateComplete;
    expect(el.shadowRoot!.querySelectorAll('.ligne').length).toBeGreaterThan(50);

    saisir(el, 'input.recherche', 'Produit 1');
    await el.updateComplete;
    // La recherche « Produit 1 » trouve CENT ONZE produits sur les trois cents
    // (1, 10-19, 100-199, 120-199 compris) — soit largement PLUS que la
    // fenêtre par défaut. C'est précisément ce qui rend l'assertion
    // discriminante : sans remise à cinquante, la fenêtre agrandie par
    // « voir plus » laisserait passer les cent onze. Un filtre qui ne
    // rendrait que dix résultats, lui, tiendrait sous cinquante dans les deux
    // cas et ne prouverait rien.
    expect(el.shadowRoot!.querySelectorAll('.ligne').length).toBeLessThanOrEqual(50);
  });
});
