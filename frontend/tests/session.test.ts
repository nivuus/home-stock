import { afterEach, describe, expect, it, vi } from 'vitest';
import '../src/ecrans/session';
import type { Connexion } from '../src/connexion';
import type { DonneesSession } from '../src/ecrans/panier';

function laisserPasserLesMicrotaches(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

/** `sort` dit ce que `resultatDe` répondra : « envoyee », « refusee », ou
 *  « en-file » — ce dernier étant le `undefined` que rend la vraie file
 *  quand l'action attend encore le réseau. (Écrit comme une chaîne et non
 *  comme `undefined` : un argument `undefined` réactiverait la valeur par
 *  défaut du paramètre, et le cas hors ligne se testerait en ligne.) */
function fileFactice(sort: 'envoyee' | 'refusee' | 'en-file' = 'envoyee') {
  return {
    ajouter: vi.fn().mockReturnValue('cle-1'),
    rejouer: vi.fn().mockResolvedValue(undefined),
    resultatDe: vi.fn().mockReturnValue(sort === 'en-file' ? undefined : sort),
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

function connexionFactice(stores: string[] = ['Leclerc', 'Lidl']): Connexion {
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
    const file = fileFactice('en-file');   // ni envoyée ni refusée : toujours en file
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
    stores: ['Leclerc'],
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
