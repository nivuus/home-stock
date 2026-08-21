import { afterEach, describe, expect, it, vi } from 'vitest';
import '../src/ecrans/session';
import type { Connexion } from '../src/connexion';
import type { DonneesSession } from '../src/ecrans/panier';

function laisserPasserLesMicrotaches(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

/** `sort` dit ce que `suivi.sort` résoudra : « envoyee », « refusee », ou
 *  « en-attente » — ce dernier étant ce que rend la vraie file quand
 *  l'action reste en attente du réseau (voir `FileAttente.ajouter`). */
function fileFactice(sort: 'envoyee' | 'refusee' | 'en-attente' = 'envoyee') {
  return {
    ajouter: vi.fn().mockReturnValue({ cle: 'cle-1', sort: Promise.resolve(sort) }),
    rejouer: vi.fn().mockResolvedValue(undefined),
    taille: vi.fn().mockReturnValue(0),
  };
}

function monter(props: { donnees?: DonneesSession | null; connexion?: Connexion; file?: unknown } = {}) {
  const element = document.createElement('home-stock-session') as HTMLElement & {
    donnees: DonneesSession | null; connexion?: Connexion; file?: unknown;
    updateComplete: Promise<boolean>;
  };
  element.donnees = props.donnees ?? null;
  if (props.connexion) element.connexion = props.connexion;
  if (props.file) element.file = props.file;
  document.body.appendChild(element);
  return element;
}

/** Depuis le lot 4, `home_stock/stores/list` rend des LIGNES : un magasin
 *  porte un identifiant, et le panneau l'envoie à la place d'une chaîne. */
function connexionFactice(noms: string[] = ['Leclerc', 'Lidl']): Connexion {
  const stores = noms.map((name, index) => ({
    id: index + 1, name, position: index, active: 1,
    observed_sessions: 0, last_seen: null,
  }));
  return { appeler: vi.fn().mockResolvedValue({ stores }) } as unknown as Connexion;
}

afterEach(() => {
  document.body.innerHTML = '';
});

describe('écran Courses : ouvrir une session', () => {
  it('propose en pastilles les magasins déjà utilisés', async () => {
    const element = monter({ connexion: connexionFactice(), file: fileFactice() });
    await element.updateComplete;
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    const pastilles = Array.from(element.shadowRoot!.querySelectorAll('.pastille'));
    expect(pastilles.map((p) => p.textContent!.trim())).toEqual(['Leclerc', 'Lidl']);
  });

  it('accepte un magasin saisi à la main, qui prend le pas sur la pastille choisie', async () => {
    const file = fileFactice();
    const element = monter({ connexion: connexionFactice(), file });
    await element.updateComplete;
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    (element.shadowRoot!.querySelector('.pastille') as HTMLButtonElement).click();
    await element.updateComplete;
    const champ = element.shadowRoot!.querySelector('.champ-magasin') as HTMLInputElement;
    champ.value = 'Grand Frais';
    champ.dispatchEvent(new InputEvent('input'));
    await element.updateComplete;

    (element.shadowRoot!.querySelector('.ouvrir-session') as HTMLButtonElement).click();
    await laisserPasserLesMicrotaches();

    expect(file.ajouter).toHaveBeenCalledWith('home_stock/session/start', { store: 'Grand Frais' });
  });

  it('ouvre une session sans enseigne quand aucun magasin n’est choisi', async () => {
    const file = fileFactice();
    const element = monter({ connexion: connexionFactice([]), file });
    await element.updateComplete;
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    (element.shadowRoot!.querySelector('.ouvrir-session') as HTMLButtonElement).click();
    await laisserPasserLesMicrotaches();

    expect(file.ajouter).toHaveBeenCalledWith('home_stock/session/start', {});
  });

  it('le dit quand l’ouverture reste en file faute de réseau, plutôt que de faire semblant', async () => {
    const file = fileFactice('en-attente');   // ni envoyée ni refusée : toujours en file
    const element = monter({ connexion: connexionFactice(), file });
    await element.updateComplete;
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    const change = vi.fn();
    element.addEventListener('session-changee', change);
    (element.shadowRoot!.querySelector('.ouvrir-session') as HTMLButtonElement).click();
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    expect(change).not.toHaveBeenCalled();
    expect(element.shadowRoot!.querySelector('.message')!.textContent).toContain('attente de réseau');
  });

  it('laisse la saisie libre ouverte quand la liste des magasins n’a pas pu être lue', async () => {
    const connexion = { appeler: vi.fn().mockRejectedValue(new Error('hors ligne')) } as unknown as Connexion;
    const element = monter({ connexion, file: fileFactice() });
    await element.updateComplete;
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    expect(element.shadowRoot!.querySelector('.erreur')).not.toBeNull();
    expect(element.shadowRoot!.querySelector('.champ-magasin')).not.toBeNull();
    expect(element.shadowRoot!.querySelector('.ouvrir-session')).not.toBeNull();
  });
});

function sessionOuverte(etat: 'shopping' | 'to_store', pending: number): DonneesSession {
  return {
    session: { id: 1, state: etat, store: 'Leclerc', started_at: '2026-08-19T10:00:00', closed_at: null },
    lines: [],
    totals: { lines: 3, pending, total: 12.5 },
    stores: [{ id: 1, name: 'Leclerc', position: 0, active: 1,
               observed_sessions: 0, last_seen: null }],
  };
}

describe('écran Courses : clore une session', () => {
  it('exige deux appuis — armement puis confirmation', async () => {
    const file = fileFactice();
    const element = monter({ donnees: sessionOuverte('to_store', 2), connexion: connexionFactice(), file });
    await element.updateComplete;
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    (element.shadowRoot!.querySelector('.clore-session') as HTMLButtonElement).click();
    await element.updateComplete;
    expect(file.ajouter).not.toHaveBeenCalled();

    (element.shadowRoot!.querySelector('.confirmer-cloture') as HTMLButtonElement).click();
    await laisserPasserLesMicrotaches();
    expect(file.ajouter).toHaveBeenCalledWith('home_stock/session/close', {});
  });

  it('annuler désarme sans rien écrire', async () => {
    const file = fileFactice();
    const element = monter({ donnees: sessionOuverte('shopping', 0), connexion: connexionFactice(), file });
    await element.updateComplete;
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    (element.shadowRoot!.querySelector('.clore-session') as HTMLButtonElement).click();
    await element.updateComplete;
    (element.shadowRoot!.querySelector('.annuler-cloture') as HTMLButtonElement).click();
    await element.updateComplete;

    expect(file.ajouter).not.toHaveBeenCalled();
    expect(element.shadowRoot!.querySelector('.clore-session')).not.toBeNull();
  });

  it('dit combien de lignes seront abandonnées, et se tait quand il n’y en a aucune', async () => {
    const avec = monter({ donnees: sessionOuverte('to_store', 2), connexion: connexionFactice(), file: fileFactice() });
    await avec.updateComplete;
    await laisserPasserLesMicrotaches();
    await avec.updateComplete;
    expect(avec.shadowRoot!.querySelector('.restantes')!.textContent).toContain('2 lignes');

    document.body.innerHTML = '';

    const sans = monter({ donnees: sessionOuverte('to_store', 0), connexion: connexionFactice(), file: fileFactice() });
    await sans.updateComplete;
    await laisserPasserLesMicrotaches();
    await sans.updateComplete;
    expect(sans.shadowRoot!.querySelector('.restantes')).toBeNull();
  });
});

describe('écran Courses : une clôture armée ne survit pas à un rafraîchissement', () => {
  it('un second appui après une poussée du coordinateur ne clôt rien', async () => {
    // Le scénario réel : on arme, une mise à jour arrive (l'autre tablette,
    // son propre rangement), on pose l'appareil, et le suivant appuie sur ce
    // qui ressemble à un bouton rouge ordinaire. `panier.ts` énonce et
    // applique déjà cette règle pour la suppression d'une ligne ; ici
    // l'enjeu est un voyage entier abandonné.
    const file = fileFactice();
    const element = monter({ donnees: sessionOuverte('to_store', 2), connexion: connexionFactice(), file });
    await element.updateComplete;
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    (element.shadowRoot!.querySelector('.clore-session') as HTMLButtonElement).click();
    await element.updateComplete;
    const confirmation = element.shadowRoot!.querySelector('.confirmer-cloture') as HTMLButtonElement;
    expect(confirmation).not.toBeNull();

    // La poussée : une NOUVELLE enveloppe de session (une ligne rangée
    // entre-temps), exactement ce que `session/current` rend au panneau.
    element.donnees = sessionOuverte('to_store', 1);
    await element.updateComplete;

    expect(element.shadowRoot!.querySelector('.confirmer-cloture')).toBeNull();
    expect(element.shadowRoot!.querySelector('.clore-session')).not.toBeNull();

    // Le bouton que le doigt avait sous lui n'est plus dans l'arbre ; s'il
    // était encore cliqué (référence gardée), rien ne doit partir non plus.
    confirmation.click();
    await laisserPasserLesMicrotaches();
    expect(file.ajouter).not.toHaveBeenCalled();
  });
});

describe('<home-stock-session> : ce que le lot 4 ajoute', () => {
  afterEach(() => { document.body.innerHTML = ''; });

  const MAGASINS = [
    { id: 3, name: 'Leclerc', position: 0, active: 1, observed_sessions: 4, last_seen: null },
    { id: 7, name: 'Lidl', position: 1, active: 1, observed_sessions: 1, last_seen: null },
  ];

  function connexionAvec(stores: unknown[]) {
    return { appeler: vi.fn().mockImplementation(async (type: string) => {
      if (type === 'home_stock/stores/list') return { stores };
      if (type === 'home_stock/list/items') return { items: [{ id: 1 }] };
      return {};
    }) } as unknown as import('../src/connexion').Connexion;
  }

  function fausseFile() {
    return { ajouter: vi.fn().mockReturnValue({ cle: 'k', sort: Promise.resolve('envoyee') }),
             rejouer: vi.fn().mockResolvedValue(undefined) };
  }

  function monterSession(props: Record<string, unknown>) {
    const element = document.createElement('home-stock-session') as HTMLElement & {
      updateComplete: Promise<boolean>; [k: string]: unknown;
    };
    for (const [cle, valeur] of Object.entries(props)) element[cle] = valeur;
    document.body.appendChild(element);
    return element;
  }

  it('affiche les magasins comme des pastilles portant un identifiant', async () => {
    const file = fausseFile();
    const element = monterSession({ donnees: null, connexion: connexionAvec(MAGASINS), file });
    await element.updateComplete;
    await Promise.resolve();
    await Promise.resolve();
    await element.updateComplete;

    const pastilles = Array.from(element.shadowRoot!.querySelectorAll('.pastille'));
    expect(pastilles.map((p) => p.textContent!.trim())).toEqual(['Leclerc', 'Lidl']);

    (pastilles[1] as HTMLButtonElement).click();
    await element.updateComplete;
    (element.shadowRoot!.querySelector('.ouvrir-session') as HTMLButtonElement).click();
    await Promise.resolve();

    expect(file.ajouter).toHaveBeenCalledWith('home_stock/session/start', { store_id: 7 });
  });

  it('accepte encore un magasin saisi à la main', async () => {
    const file = fausseFile();
    const element = monterSession({ donnees: null, connexion: connexionAvec([]), file });
    await element.updateComplete;

    const champ = element.shadowRoot!.querySelector('.champ-magasin') as HTMLInputElement;
    champ.value = 'Biocoop';
    champ.dispatchEvent(new Event('input'));
    await element.updateComplete;
    (element.shadowRoot!.querySelector('.ouvrir-session') as HTMLButtonElement).click();
    await Promise.resolve();

    expect(file.ajouter).toHaveBeenCalledWith('home_stock/session/start', { store: 'Biocoop' });
  });

  it('propose « emporter la liste » quand la liste n’est pas vide', async () => {
    const element = monterSession({
      donnees: {
        session: { id: 1, state: 'shopping', store: 'Leclerc',
                   started_at: '2026-08-21T09:00:00', closed_at: null },
        lines: [], totals: { lines: 0, pending: 0, total: 0, list_items: 5, checked_items: 1 },
        stores: MAGASINS,
      },
    });
    await element.updateComplete;

    const bouton = element.shadowRoot!.querySelector('.emporter-liste') as HTMLButtonElement;
    expect(bouton.textContent).toContain('5');
    const evenements: string[] = [];
    element.addEventListener('aller-liste', () => evenements.push('liste'));
    bouton.click();
    expect(evenements).toEqual(['liste']);
  });

  it('propose « photographier le ticket » à la clôture', async () => {
    const element = monterSession({
      donnees: {
        session: { id: 1, state: 'to_store', store: 'Leclerc',
                   started_at: '2026-08-21T09:00:00', closed_at: null },
        lines: [], totals: { lines: 2, pending: 0, total: 12 }, stores: MAGASINS,
      },
    });
    await element.updateComplete;

    const bouton = element.shadowRoot!.querySelector('.photographier') as HTMLButtonElement;
    const detail: unknown[] = [];
    element.addEventListener('ticket-ouvert', (e) => detail.push((e as CustomEvent).detail));
    bouton.click();
    expect(detail).toEqual([{ ticket: null, agent_configure: true }]);
  });

  it('ne propose pas de photographier avant la caisse', async () => {
    const element = monterSession({
      donnees: {
        session: { id: 1, state: 'shopping', store: 'Leclerc',
                   started_at: '2026-08-21T09:00:00', closed_at: null },
        lines: [], totals: { lines: 2, pending: 2, total: 12 }, stores: MAGASINS,
      },
    });
    await element.updateComplete;
    expect(element.shadowRoot!.querySelector('.photographier')).toBeNull();
  });
});
