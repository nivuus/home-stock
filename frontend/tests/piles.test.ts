import { beforeEach, describe, expect, it, vi } from 'vitest';
import '../src/ecrans/piles';

const PILES = [
  { id: 1, label: 'Velux (CH)', kind: 'primary', verb: 'Pile à changer',
    tracked: true, exclusion_reason: null, entity_id: 'sensor.velux_ch_batterie',
    state: '18', orphaned: false, device_name: 'Velux', model: 'PARASOLL',
    equipment_id: null, cell_count: 1, low_percent: 20, keep_percent: 25,
    last_percent: 18, last_reading_at: '2026-08-21T06:00:00',
    installed_on: null, note: null, spare_label: 'CR2032', spare_in_stock: 0 },
  { id: 2, label: 'Rideau Cuisine', kind: 'built_in', verb: 'Recharger',
    tracked: true, exclusion_reason: null, entity_id: 'sensor.rideau_batterie',
    state: '5', orphaned: false, device_name: null, model: null,
    equipment_id: null, cell_count: 1, low_percent: 20, keep_percent: 25,
    last_percent: 5, last_reading_at: '2026-08-21T06:00:00',
    installed_on: null, note: null, spare_label: null, spare_in_stock: null },
  { id: 3, label: 'Capteur', kind: 'rechargeable_cell', verb: 'Piles à recharger',
    tracked: true, exclusion_reason: null, entity_id: 'sensor.capteur_batterie',
    state: 'unavailable', orphaned: false, device_name: null, model: null,
    equipment_id: null, cell_count: 2, low_percent: 20, keep_percent: 25,
    last_percent: 40, last_reading_at: '2026-08-19T06:00:00',
    installed_on: null, note: null, spare_label: 'AAA', spare_in_stock: 4 },
  { id: 4, label: 'Disparue', kind: 'primary', verb: 'Pile à changer',
    tracked: true, exclusion_reason: null, entity_id: null, state: null,
    orphaned: true, device_name: null, model: null, equipment_id: null,
    cell_count: 1, low_percent: 20, keep_percent: 25, last_percent: null,
    last_reading_at: null, installed_on: null, note: null,
    spare_label: null, spare_in_stock: null },
  { id: 5, label: 'Jamais relevée', kind: 'primary', verb: 'Pile à changer',
    tracked: true, exclusion_reason: null, entity_id: 'sensor.neuve_batterie',
    state: 'unknown', orphaned: false, device_name: null, model: null,
    equipment_id: null, cell_count: 1, low_percent: 20, keep_percent: 25,
    last_percent: null, last_reading_at: null, installed_on: null, note: null,
    spare_label: null, spare_in_stock: null },
];

const DECOUVERTES = [
  { entity_registry_id: 'u9', entity_id: 'sensor.nouveau_batterie',
    device_id: 'd9', device_name: 'Nouveau capteur', model: 'ZG-204ZV', state: '77' },
];

const EVENEMENTS = [
  { id: 2, occurred_at: '2026-06-01T10:00:00', kind: 'replacement',
    movement_id: 4, note: null },
  { id: 1, occurred_at: '2026-01-01T10:00:00', kind: 'install',
    movement_id: null, note: null },
];

function monter(options: { piles?: unknown[]; decouvertes?: unknown[]; reponseFile?: unknown } = {}) {
  const appeler = vi.fn(async (type: string) => {
    if (type === 'home_stock/batteries/list') return { batteries: options.piles ?? PILES };
    if (type === 'home_stock/batteries/discover') return { sensors: options.decouvertes ?? [] };
    if (type === 'home_stock/battery/events') return { events: EVENEMENTS };
    return {};
  });
  const ajouter = vi.fn(() => ({
    cle: 'k',
    sort: Promise.resolve('envoyee'),
    reponse: Promise.resolve(options.reponseFile),
  }));
  const element = document.createElement('home-stock-piles') as any;
  element.connexion = { appeler };
  element.file = { ajouter, rejouer: vi.fn(async () => {}) };
  document.body.append(element);
  return { element, appeler, ajouter };
}

/** Laisse retomber la chaîne de promesses de l'écran avant de regarder le
 *  DOM : une écriture traverse la file, sa réponse, puis un rechargement de
 *  la liste — trois tours de boucle, pas un. */
const attendre = async (element: any) => {
  for (let tour = 0; tour < 6; tour += 1) {
    await Promise.resolve();
    await element.updateComplete;
  }
};
const texte = (element: any) => element.shadowRoot.textContent as string;
const boutons = (element: any, selecteur: string) =>
  Array.from(element.shadowRoot.querySelectorAll(selecteur)) as HTMLElement[];

describe('<home-stock-piles>', () => {
  beforeEach(() => { document.body.innerHTML = ''; });

  it('trie les piles par niveau croissant', async () => {
    const { element } = monter();
    await attendre(element);
    const libelles = boutons(element, '.pile .libelle').map((n) => n.textContent!.trim());
    expect(libelles.slice(0, 2)).toEqual(['Rideau Cuisine', 'Velux (CH)']);
  });

  it('affiche les trois verbes selon la nature', async () => {
    const { element } = monter();
    await attendre(element);
    expect(texte(element)).toContain('Pile à changer');
    expect(texte(element)).toContain('Recharger');
    expect(texte(element)).toContain('Piles à recharger');
  });

  it('dit « aucune en stock » quand la rechange manque', async () => {
    const { element } = monter();
    await attendre(element);
    expect(texte(element)).toContain('1× CR2032, aucune en stock');
  });

  it('affiche le stock de rechange quand il y en a', async () => {
    const { element } = monter();
    await attendre(element);
    expect(texte(element)).toContain('2× AAA, 4 en stock');
  });

  it('dit « jamais relevée » plutôt que 0 %', async () => {
    const { element } = monter();
    await attendre(element);
    const ligne = boutons(element, '.pile')
      .find((n) => n.textContent!.includes('Jamais relevée'))!;
    expect(ligne.textContent).toContain('jamais relevée');
    // « 0 % » et « on ne sait rien » ne sont pas la même phrase, et c'est la
    // seconde qui est vraie ici.
    expect(ligne.textContent).not.toMatch(/\d+\s%/);
  });

  it('montre une pile orpheline sans inventer de niveau', async () => {
    const { element } = monter();
    await attendre(element);
    expect(texte(element)).toContain('Disparue');
    expect(texte(element)).toContain('entité introuvable');
  });

  it('signale une pile muette sans la déclarer vide', async () => {
    const { element } = monter();
    await attendre(element);
    expect(texte(element)).toContain('muette');
  });

  it('liste le bloc « à déclarer » en tête quand discover rend des capteurs', async () => {
    const { element } = monter({ decouvertes: DECOUVERTES });
    await attendre(element);
    const blocs = boutons(element, '.section');
    expect(blocs[0].textContent).toContain('à déclarer');
    expect(texte(element)).toContain('sensor.nouveau_batterie');
  });

  it('n’écrit rien à l’ouverture de l’écran', async () => {
    const { element, ajouter, appeler } = monter({ decouvertes: DECOUVERTES });
    await attendre(element);
    expect(ajouter).not.toHaveBeenCalled();
    const types = appeler.mock.calls.map((appel) => appel[0]);
    expect(types.every((t) => t.endsWith('/list') || t.endsWith('/discover'))).toBe(true);
  });

  it('refuse d’ignorer une pile sans motif', async () => {
    const { element, ajouter } = monter({ decouvertes: DECOUVERTES });
    await attendre(element);
    boutons(element, '.ignorer')[0].click();
    await attendre(element);
    boutons(element, '.confirmer-ignorer')[0].click();
    await attendre(element);
    expect(ajouter).not.toHaveBeenCalled();
    expect(texte(element)).toContain('motif');
  });

  it('ignore une pile avec son motif, par la file d’attente', async () => {
    const { element, ajouter } = monter({ decouvertes: DECOUVERTES });
    await attendre(element);
    boutons(element, '.ignorer')[0].click();
    await attendre(element);
    const champ = element.shadowRoot.querySelector('.motif') as HTMLInputElement;
    champ.value = 'tablette sur secteur';
    champ.dispatchEvent(new Event('input'));
    await attendre(element);
    boutons(element, '.confirmer-ignorer')[0].click();
    await attendre(element);
    expect(ajouter).toHaveBeenCalledWith('home_stock/battery/declare',
      expect.objectContaining({ tracked: false, exclusion_reason: 'tablette sur secteur' }));
  });

  it('suit une pile découverte en un appui, par la file', async () => {
    const { element, ajouter } = monter({ decouvertes: DECOUVERTES });
    await attendre(element);
    boutons(element, '.suivre')[0].click();
    await attendre(element);
    expect(ajouter).toHaveBeenCalledWith('home_stock/battery/declare',
      expect.objectContaining({ tracked: true, entity_registry_id: 'u9' }));
  });

  it('demande deux appuis avant « je viens de la changer »', async () => {
    const { element, ajouter } = monter();
    await attendre(element);
    boutons(element, '.pile')[0].click();
    await attendre(element);
    boutons(element, '.evenement')[0].click();
    await attendre(element);
    expect(ajouter).not.toHaveBeenCalled();
    expect(texte(element)).toContain('Confirmer');
    boutons(element, '.evenement')[0].click();
    await attendre(element);
    expect(ajouter).toHaveBeenCalledWith('home_stock/battery/event',
      expect.objectContaining({ kind: 'charge' }));
  });

  it('n’écrit rien au premier appui', async () => {
    const { element, ajouter } = monter();
    await attendre(element);
    boutons(element, '.pile')[1].click();
    await attendre(element);
    boutons(element, '.evenement')[0].click();
    await attendre(element);
    expect(ajouter).not.toHaveBeenCalled();
  });

  it('propose « recharger » et non « changer » sur une batterie intégrée', async () => {
    const { element } = monter();
    await attendre(element);
    // La deuxième pile de la liste triée est le rideau (built_in).
    boutons(element, '.pile')[0].click();
    await attendre(element);
    const libelle = boutons(element, '.evenement')[0].textContent!;
    expect(libelle).toContain('recharger');
    expect(libelle).not.toContain('changer');
  });

  it('propose « changer » sur une pile jetable', async () => {
    const { element } = monter();
    await attendre(element);
    boutons(element, '.pile')[1].click();
    await attendre(element);
    expect(boutons(element, '.evenement')[0].textContent).toContain('changer');
  });

  it('affiche le refus de stock renvoyé par le serveur', async () => {
    const { element } = monter({
      reponseFile: { event_id: 1, movement_id: null,
                     spare_refused: 'Stock insuffisant : 1 demandé, 0 disponible.' },
    });
    await attendre(element);
    boutons(element, '.pile')[1].click();
    await attendre(element);
    boutons(element, '.evenement')[0].click();
    await attendre(element);
    boutons(element, '.evenement')[0].click();
    await attendre(element);
    expect(texte(element)).toContain('Stock insuffisant');
  });

  it('passe toutes les écritures par la file, jamais par appeler()', async () => {
    const { element, appeler, ajouter } = monter({ decouvertes: DECOUVERTES });
    await attendre(element);
    boutons(element, '.suivre')[0].click();
    await attendre(element);
    boutons(element, '.pile')[1].click();
    await attendre(element);
    boutons(element, '.evenement')[0].click();
    await attendre(element);
    boutons(element, '.evenement')[0].click();
    await attendre(element);
    const ecritures = appeler.mock.calls.map((appel) => appel[0])
      .filter((type: string) => !type.endsWith('/list') && !type.endsWith('/discover')
        && !type.endsWith('/events'));
    expect(ecritures).toEqual([]);
    expect(ajouter).toHaveBeenCalledTimes(2);
  });

  it('affiche l’historique des événements de la fiche, plus récent d’abord', async () => {
    const { element } = monter();
    await attendre(element);
    boutons(element, '.pile')[0].click();
    await attendre(element);
    const lignes = boutons(element, '.evenement-passe').map((n) => n.textContent!.trim());
    expect(lignes[0]).toContain('01/06/2026');
    expect(lignes[1]).toContain('01/01/2026');
  });
});
