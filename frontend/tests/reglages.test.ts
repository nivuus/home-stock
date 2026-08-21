import { afterEach, describe, expect, it, vi } from 'vitest';
import '../src/ecrans/reglages';
import { deplacer } from '../src/ecrans/reglages';
import type { Rayon } from '../src/ecrans/catalogue';
import type { Emplacement } from '../src/ecrans/rangement';
import type { Connexion } from '../src/connexion';

describe('deplacer', () => {
  const liste = ['a', 'b', 'c'];

  it('permute avec le voisin suivant', () => {
    expect(deplacer(liste, 0, 1)).toEqual(['b', 'a', 'c']);
  });

  it('permute avec le voisin précédent', () => {
    expect(deplacer(liste, 2, -1)).toEqual(['a', 'c', 'b']);
  });

  it('rend null pour un mouvement hors limites (déjà en haut ou en bas)', () => {
    expect(deplacer(liste, 0, -1)).toBeNull();
    expect(deplacer(liste, 2, 1)).toBeNull();
  });

  it('ne touche jamais le reste de la liste', () => {
    expect(deplacer(['a', 'b', 'c', 'd'], 1, 1)).toEqual(['a', 'c', 'b', 'd']);
  });
});

const RAYONS: Rayon[] = [
  { id: 1, name: 'Épicerie', position: 0 },
  { id: 2, name: 'Frais', position: 1 },
  { id: 3, name: 'Surgelés', position: 2 },
];
const EMPLACEMENTS: Emplacement[] = [
  { id: 1, name: 'Placard', kind: 'cupboard', position: 0 },
  { id: 2, name: 'Frigo', kind: 'fridge', position: 1 },
];

function connexionFactice(
  reponses: (type: string, charge?: object) => Promise<unknown> = () => Promise.resolve({}),
): Connexion & { appeler: ReturnType<typeof vi.fn>; appelerService: ReturnType<typeof vi.fn> } {
  return {
    appeler: vi.fn().mockImplementation(reponses),
    appelerService: vi.fn().mockResolvedValue(undefined),
  } as unknown as Connexion & { appeler: ReturnType<typeof vi.fn>; appelerService: ReturnType<typeof vi.fn> };
}

function reponsesParDefaut(type: string): Promise<unknown> {
  if (type === 'home_stock/aisles/list') return Promise.resolve({ aisles: RAYONS });
  if (type === 'home_stock/locations/list') return Promise.resolve({ locations: EMPLACEMENTS });
  return Promise.resolve({});
}

function monter(props: { connexion?: Connexion; file?: unknown; enAttente?: number } = {}) {
  const element = document.createElement('home-stock-reglages') as HTMLElement & {
    connexion?: Connexion; file?: unknown; enAttente: number; updateComplete: Promise<boolean>;
  };
  if (props.connexion) element.connexion = props.connexion;
  if (props.file) element.file = props.file;
  if (props.enAttente !== undefined) element.enAttente = props.enAttente;
  document.body.appendChild(element);
  return element;
}

async function laisserPasserLesMicrotaches(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

describe('<home-stock-reglages>', () => {
  afterEach(() => {
    document.body.innerHTML = '';
  });

  it('charge et affiche les rayons dans l’ordre reçu, et les emplacements', async () => {
    const connexion = connexionFactice(reponsesParDefaut);
    const element = monter({ connexion });
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    const noms = Array.from(element.shadowRoot!.querySelectorAll('.rayon-nom')).map((n) => n.textContent);
    expect(noms).toEqual(['Épicerie', 'Frais', 'Surgelés']);
    const emplacements = Array.from(element.shadowRoot!.querySelectorAll('.emplacement-nom')).map((n) => n.textContent);
    expect(emplacements).toEqual(['Placard', 'Frigo']);
  });

  it('désactive « monter » sur le premier rayon et « descendre » sur le dernier', async () => {
    const connexion = connexionFactice(reponsesParDefaut);
    const element = monter({ connexion });
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    const monterBoutons = element.shadowRoot!.querySelectorAll('.monter') as NodeListOf<HTMLButtonElement>;
    const descendreBoutons = element.shadowRoot!.querySelectorAll('.descendre') as NodeListOf<HTMLButtonElement>;
    expect(monterBoutons[0].disabled).toBe(true);
    expect(descendreBoutons[descendreBoutons.length - 1].disabled).toBe(true);
    expect(monterBoutons[1].disabled).toBe(false);
    expect(descendreBoutons[0].disabled).toBe(false);
  });

  it('« descendre » envoie la liste complète réordonnée à aisles/reorder, via la file', async () => {
    const connexion = connexionFactice(reponsesParDefaut);
    const ajouter = vi.fn().mockReturnValue({ cle: 'cle-test', sort: Promise.resolve('envoyee') });
    const file = { ajouter, rejouer: vi.fn().mockResolvedValue(undefined) };
    const element = monter({ connexion, file });
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    (element.shadowRoot!.querySelectorAll('.descendre')[0] as HTMLButtonElement).click();
    await element.updateComplete;

    expect(ajouter).toHaveBeenCalledWith('home_stock/aisles/reorder', { aisle_ids: [2, 1, 3] });
    const noms = Array.from(element.shadowRoot!.querySelectorAll('.rayon-nom')).map((n) => n.textContent);
    expect(noms).toEqual(['Frais', 'Épicerie', 'Surgelés']);
  });

  it('n’écrit jamais directement par connexion : sans file, un appui ne fait rien', async () => {
    const connexion = connexionFactice(reponsesParDefaut);
    const element = monter({ connexion });
    await laisserPasserLesMicrotaches();
    await element.updateComplete;
    (connexion.appeler as ReturnType<typeof vi.fn>).mockClear();

    (element.shadowRoot!.querySelectorAll('.descendre')[0] as HTMLButtonElement).click();
    await element.updateComplete;

    expect(connexion.appeler).not.toHaveBeenCalledWith('home_stock/aisles/reorder', expect.anything());
  });

  it('recharge les rayons depuis le serveur quand un réordonnancement est refusé, au lieu de continuer '
     + 'à afficher (et à renvoyer) un ordre que le serveur n’a jamais accepté', async () => {
    const appeler = vi.fn().mockImplementation(reponsesParDefaut);
    const connexion = { appeler } as unknown as Connexion;
    const ajouter = vi.fn().mockReturnValue({ cle: 'cle-test', sort: Promise.resolve('refusee') });
    const file = { ajouter, rejouer: vi.fn().mockResolvedValue(undefined) };
    const element = monter({ connexion, file });
    await laisserPasserLesMicrotaches();
    await element.updateComplete;
    appeler.mockClear();

    (element.shadowRoot!.querySelectorAll('.descendre')[0] as HTMLButtonElement).click();
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    // L'ordre optimiste a bien été tenté...
    expect(ajouter).toHaveBeenCalledWith('home_stock/aisles/reorder', { aisle_ids: [2, 1, 3] });
    // ...mais le refus a déclenché un rechargement de la vraie liste, qui
    // répond toujours l'ordre d'origine ici : l'écran doit refléter CELA,
    // pas l'ordre optimiste que le serveur a refusé.
    expect(appeler).toHaveBeenCalledWith('home_stock/aisles/list');
    const noms = Array.from(element.shadowRoot!.querySelectorAll('.rayon-nom')).map((n) => n.textContent);
    expect(noms).toEqual(['Épicerie', 'Frais', 'Surgelés']);
  });

  it('ne recharge rien quand le réordonnancement reste simplement en file (hors ligne, pas un refus)', async () => {
    const appeler = vi.fn().mockImplementation(reponsesParDefaut);
    const connexion = { appeler } as unknown as Connexion;
    // « en-attente » : toujours en file, comme `FileAttente.ajouter` le rend
    // tant qu'aucun sort n'est connu (panne de transport).
    const ajouter = vi.fn().mockReturnValue({ cle: 'cle-test', sort: Promise.resolve('en-attente') });
    const file = { ajouter, rejouer: vi.fn().mockResolvedValue(undefined) };
    const element = monter({ connexion, file });
    await laisserPasserLesMicrotaches();
    await element.updateComplete;
    appeler.mockClear();

    (element.shadowRoot!.querySelectorAll('.descendre')[0] as HTMLButtonElement).click();
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    expect(appeler).not.toHaveBeenCalledWith('home_stock/aisles/list');
    // L'ordre optimiste reste affiché : la file retentera d'elle-même.
    const noms = Array.from(element.shadowRoot!.querySelectorAll('.rayon-nom')).map((n) => n.textContent);
    expect(noms).toEqual(['Frais', 'Épicerie', 'Surgelés']);
  });

  it('appelle le service home_stock.resync_off avec all: true, pas une commande websocket', async () => {
    const connexion = connexionFactice(reponsesParDefaut);
    const element = monter({ connexion });
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    (element.shadowRoot!.querySelector('.resynchroniser') as HTMLButtonElement).click();
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    expect((connexion as any).appelerService).toHaveBeenCalledWith('home_stock', 'resync_off', { all: true });
    expect(element.shadowRoot!.querySelector('.message-resync')!.textContent).toContain('40 minutes');
  });

  it('affiche le refus du serveur (déjà en cours) en français plutôt que de le taire', async () => {
    const connexion = connexionFactice(reponsesParDefaut);
    (connexion as any).appelerService = vi.fn().mockRejectedValue({
      message: 'Une resynchronisation Open Food Facts est déjà en cours.',
    });
    const element = monter({ connexion });
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    (element.shadowRoot!.querySelector('.resynchroniser') as HTMLButtonElement).click();
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    expect(element.shadowRoot!.querySelector('.erreur')!.textContent)
      .toContain('déjà en cours');
    expect(element.shadowRoot!.querySelector('.message-resync')).toBeNull();
  });

  it('remplace un message de service imprévu (une exception Python non traduite) par le message '
     + 'générique en français plutôt que de l’afficher tel quel', async () => {
    const connexion = connexionFactice(reponsesParDefaut);
    (connexion as any).appelerService = vi.fn().mockRejectedValue({
      message: 'ValueError: division by zero in _write_resync',
    });
    const element = monter({ connexion });
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    (element.shadowRoot!.querySelector('.resynchroniser') as HTMLButtonElement).click();
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    const erreur = element.shadowRoot!.querySelector('.erreur')!.textContent;
    expect(erreur).not.toContain('ValueError');
    expect(erreur).not.toContain('division by zero');
    expect(erreur).toContain('pas pu être lancée');
  });

  it('affiche une erreur en français si le chargement des rayons échoue', async () => {
    const connexion = connexionFactice(() => Promise.reject(new Error('offline')));
    const element = monter({ connexion });
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    expect(element.shadowRoot!.querySelector('.erreur')!.textContent)
      .toContain('Impossible de récupérer les rayons');
  });

  it('affiche le compteur d’actions en attente comme les autres écrans', async () => {
    const connexion = connexionFactice(reponsesParDefaut);
    const element = monter({ connexion, enAttente: 4 });
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    expect(element.shadowRoot!.querySelector('.en-attente')!.textContent).toContain('4');
  });
});

describe('<home-stock-reglages> : magasins, parcours et récurrences (lot 4)', () => {
  afterEach(() => { document.body.innerHTML = ''; });

  const MAGASINS = [
    { id: 1, name: 'Leclerc', position: 0, active: 1, observed_sessions: 2, last_seen: null },
    { id: 2, name: 'E.Leclerc', position: 1, active: 1, observed_sessions: 1, last_seen: null },
  ];
  const RAYONS_MAGASIN = {
    store_id: 1,
    aisles: [
      { store_id: 1, aisle_id: 10, position: 1, source: 'manual', mean_rank: 0.8,
        observed_sessions: 3, updated_at: null, aisle_name: 'Crémerie',
        default_position: 2 },
      { store_id: 1, aisle_id: 11, position: 2, source: 'learned', mean_rank: 0.2,
        observed_sessions: 3, updated_at: null, aisle_name: 'Épicerie salée',
        default_position: 1 },
    ],
    observed_sessions: 2, required_sessions: 3, reliable: false,
  };

  function monterLot4(surAppel?: (type: string, charge: any) => unknown) {
    const appeler = vi.fn(async (type: string, charge: any = {}) => {
      const perso = surAppel?.(type, charge);
      if (perso !== undefined) return perso;
      if (type === 'home_stock/aisles/list') return { aisles: [] };
      if (type === 'home_stock/locations/list') return { locations: [] };
      if (type === 'home_stock/stores/list') return { stores: MAGASINS };
      if (type === 'home_stock/store/aisles') return RAYONS_MAGASIN;
      if (type === 'home_stock/store/reorder_aisles') return RAYONS_MAGASIN;
      if (type === 'home_stock/store/unpin_aisle') return RAYONS_MAGASIN;
      if (type === 'home_stock/recurring/list') {
        return { recurring: [{ id: 5, product_id: null, free_text: 'Café',
                               quantity: null, every_days: 21,
                               last_added_on: null, active: 1,
                               product_name: null, base_unit: null }] };
      }
      if (type === 'home_stock/recurring/save' || type === 'home_stock/recurring/delete') {
        return { recurring: [] };
      }
      return {};
    });
    const element = document.createElement('home-stock-reglages') as any;
    element.connexion = { appeler, appelerService: vi.fn() };
    element.file = { ajouter: vi.fn().mockReturnValue({ cle: 'k', sort: Promise.resolve('envoyee') }),
                     rejouer: vi.fn().mockResolvedValue(undefined) };
    document.body.append(element);
    return { element, appeler };
  }

  async function stabiliser(element: any) {
    await element.updateComplete;
    for (let i = 0; i < 8; i += 1) await Promise.resolve();
    await element.updateComplete;
  }

  it('réordonne les rayons magasin par magasin', async () => {
    const { element, appeler } = monterLot4();
    await stabiliser(element);

    (element.shadowRoot.querySelectorAll('.magasin-onglet')[0] as HTMLButtonElement).click();
    await stabiliser(element);
    (element.shadowRoot.querySelector('.descendre-rayon-magasin') as HTMLButtonElement).click();
    await stabiliser(element);

    expect(appeler).toHaveBeenCalledWith('home_stock/store/reorder_aisles',
      { store_id: 1, aisle_ids: [11, 10] });
  });

  it('dit combien de sessions manquent avant que l’ordre soit fiable', async () => {
    const { element } = monterLot4();
    await stabiliser(element);
    (element.shadowRoot.querySelectorAll('.magasin-onglet')[0] as HTMLButtonElement).click();
    await stabiliser(element);

    expect(element.shadowRoot.querySelector('.fiabilite').textContent)
      .toContain('2 session');
    expect(element.shadowRoot.querySelector('.fiabilite').textContent).toContain('3');
  });

  it('montre qu’un rayon épinglé contredit l’ordre appris', async () => {
    const { element } = monterLot4();
    await stabiliser(element);
    (element.shadowRoot.querySelectorAll('.magasin-onglet')[0] as HTMLButtonElement).click();
    await stabiliser(element);

    const epingle = element.shadowRoot.querySelector('.rayon-magasin.epingle');
    expect(epingle).not.toBeNull();
    expect(epingle.textContent).toContain('épinglé');
  });

  it('propose « reprendre l’apprentissage » sur un rayon épinglé', async () => {
    const { element, appeler } = monterLot4();
    await stabiliser(element);
    (element.shadowRoot.querySelectorAll('.magasin-onglet')[0] as HTMLButtonElement).click();
    await stabiliser(element);

    (element.shadowRoot.querySelector('.reprendre-apprentissage') as HTMLButtonElement).click();
    await stabiliser(element);

    expect(appeler).toHaveBeenCalledWith('home_stock/store/unpin_aisle',
      { store_id: 1, aisle_id: 10 });
  });

  it('fusionne deux magasins en deux appuis', async () => {
    const fusion = vi.fn();
    const { element } = monterLot4((type, charge) => {
      if (type === 'home_stock/store/merge') { fusion(charge); return { stores: [MAGASINS[0]] }; }
      return undefined;
    });
    await stabiliser(element);

    (element.shadowRoot.querySelectorAll('.fusionner')[1] as HTMLButtonElement).click();
    await stabiliser(element);
    expect(fusion).not.toHaveBeenCalled();

    (element.shadowRoot.querySelector('.confirmer-fusion') as HTMLButtonElement).click();
    await stabiliser(element);
    expect(fusion).toHaveBeenCalledWith({ keep_id: 1, merge_id: 2 });
  });

  it('refuse la fusion pendant une session ouverte, en français', async () => {
    const { element } = monterLot4((type) => {
      if (type === 'home_stock/store/merge') {
        throw new Error('Une session de courses est en cours dans ce magasin : '
                        + 'clôturez-la avant de fusionner.');
      }
      return undefined;
    });
    await stabiliser(element);

    (element.shadowRoot.querySelectorAll('.fusionner')[1] as HTMLButtonElement).click();
    await stabiliser(element);
    (element.shadowRoot.querySelector('.confirmer-fusion') as HTMLButtonElement).click();
    await stabiliser(element);

    expect(element.shadowRoot.querySelector('.erreur-fusion').textContent)
      .toContain('en cours');
  });

  it('gère les lignes récurrentes', async () => {
    const enregistrements: unknown[] = [];
    const { element } = monterLot4((type, charge) => {
      if (type === 'home_stock/recurring/save') {
        enregistrements.push(charge);
        return { recurring: [] };
      }
      return undefined;
    });
    await stabiliser(element);

    expect(element.shadowRoot.querySelector('.recurrente').textContent).toContain('Café');
    expect(element.shadowRoot.querySelector('.recurrente').textContent).toContain('21');

    const champ = element.shadowRoot.querySelector('.champ-recurrente') as HTMLInputElement;
    champ.value = 'Sacs poubelle';
    champ.dispatchEvent(new Event('input'));
    const jours = element.shadowRoot.querySelector('.champ-jours') as HTMLInputElement;
    jours.value = '30';
    jours.dispatchEvent(new Event('input'));
    await stabiliser(element);
    (element.shadowRoot.querySelector('.ajouter-recurrente') as HTMLButtonElement).click();
    await stabiliser(element);

    expect(enregistrements).toEqual([{ free_text: 'Sacs poubelle', every_days: 30 }]);
  });

  it('supprime une ligne récurrente', async () => {
    const suppressions: unknown[] = [];
    const { element } = monterLot4((type, charge) => {
      if (type === 'home_stock/recurring/delete') {
        suppressions.push(charge);
        return { recurring: [] };
      }
      return undefined;
    });
    await stabiliser(element);

    (element.shadowRoot.querySelector('.supprimer-recurrente') as HTMLButtonElement).click();
    await stabiliser(element);

    expect(suppressions).toEqual([{ recurring_id: 5 }]);
  });

  it('affiche l’entité ai_task, ou dit qu’il n’y en a pas', async () => {
    const { element } = monterLot4();
    await stabiliser(element);
    expect(element.shadowRoot.querySelector('.agent-ticket').textContent)
      .toContain('Aucune');

    element.agentTicket = 'ai_task.gemini';
    await stabiliser(element);
    expect(element.shadowRoot.querySelector('.agent-ticket').textContent)
      .toContain('ai_task.gemini');
  });

  it('affiche la taille du dossier des tickets', async () => {
    const { element } = monterLot4();
    element.tailleTickets = '12,4 Mo';
    await stabiliser(element);
    expect(element.shadowRoot.querySelector('.taille-tickets').textContent)
      .toContain('12,4 Mo');
  });
});

// --- lot 6 : trois colonnes au-delà de 1000 px ------------------------------

const MAGASINS = [
  { id: 1, name: 'Leclerc' },
  { id: 2, name: 'Biocoop' },
];

function reponsesCompletes(type: string): Promise<unknown> {
  if (type === 'home_stock/stores/list') return Promise.resolve({ stores: MAGASINS });
  if (type === 'home_stock/recurring/list') return Promise.resolve({ recurring: [] });
  return reponsesParDefaut(type);
}

async function monterReglages(options: { large: boolean; file?: unknown }) {
  const connexion = connexionFactice(reponsesCompletes);
  const element = monter({ connexion, file: options.file }) as HTMLElement & {
    large: boolean; updateComplete: Promise<boolean>;
  };
  element.large = options.large;
  await laisserPasserLesMicrotaches();
  await element.updateComplete;
  return element;
}

const ordreDes = (element: HTMLElement, selecteur: string): string[] =>
  Array.from(element.shadowRoot!.querySelectorAll(selecteur)).map((n) => n.textContent!.trim());

describe('<home-stock-reglages> : la vue dense (lot 6)', () => {
  afterEach(() => { document.body.innerHTML = ''; });

  it('rend trois colonnes au-delà de 1000 px', async () => {
    const e = await monterReglages({ large: true });
    const colonnes = e.shadowRoot!.querySelector('.trois-colonnes');
    expect(colonnes).not.toBeNull();
    // Les sept sections restent les sept sections : la largeur les dispose,
    // elle n'en ajoute ni n'en retire une seule. (Six au lot 6, sept depuis
    // que le lot 7 a ajouté « Bascule ».)
    expect(e.shadowRoot!.querySelectorAll('.section')).toHaveLength(7);
  });

  it('reste empilée en étroit', async () => {
    const e = await monterReglages({ large: false });
    expect(e.shadowRoot!.querySelector('.trois-colonnes')).toBeNull();
    expect(e.shadowRoot!.querySelectorAll('.section')).toHaveLength(7);
  });

  it('réordonne dans la BONNE liste quand elles sont côte à côte', async () => {
    // Le piège de la tâche : trois listes réordonnables côte à côte. Déplacer
    // « Frais » ne doit jamais toucher aux magasins — ce qui arriverait si la
    // cible du déplacement se calculait sur la position dans le document
    // plutôt que dans sa propre liste.
    const file = { ajouter: vi.fn().mockReturnValue({ cle: 'k', sort: Promise.resolve('envoyee') }),
                   rejouer: vi.fn().mockResolvedValue(undefined) };
    const e = await monterReglages({ large: true, file });
    const magasinsAvant = ordreDes(e, '.magasin-onglet');

    const monterBoutons = e.shadowRoot!.querySelectorAll('.monter') as NodeListOf<HTMLButtonElement>;
    monterBoutons[1].click();                       // « Frais » remonte d'un cran
    await e.updateComplete;

    expect(file.ajouter).toHaveBeenCalledWith('home_stock/aisles/reorder',
      { aisle_ids: [2, 1, 3] });
    expect(file.ajouter).toHaveBeenCalledTimes(1);  // une seule liste touchée
    expect(ordreDes(e, '.rayon-nom')).toEqual(['Frais', 'Épicerie', 'Surgelés']);
    expect(ordreDes(e, '.magasin-onglet')).toEqual(magasinsAvant);
  });

  it('garde emplacements et magasins lisibles et intacts en large', async () => {
    const e = await monterReglages({ large: true });
    expect(ordreDes(e, '.emplacement-nom')).toEqual(['Placard', 'Frigo']);
    expect(ordreDes(e, '.magasin-onglet')).toEqual(['Leclerc', 'Biocoop']);
    expect(e.shadowRoot!.querySelector('.resynchroniser')).not.toBeNull();
  });
});
