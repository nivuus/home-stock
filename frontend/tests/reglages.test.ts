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
    const ajouter = vi.fn().mockReturnValue('cle-test');
    const file = { ajouter, rejouer: vi.fn().mockResolvedValue(undefined), resultatDe: vi.fn().mockReturnValue('envoyee') };
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
