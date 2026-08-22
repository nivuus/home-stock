import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import '../src/ecrans/planning';
import { creerCarteCalendrier, entiteCalendrierRepas } from '../src/shell/ui/carte-calendrier';

const REGISTRE = {
  'calendar.famille': { platform: 'google' },
  'calendar.repas_de_la_maison': { platform: 'home_stock' },
};

function hassAvec(surcharge: Record<string, unknown> = {}) {
  return {
    states: { 'calendar.repas_de_la_maison': { state: 'off' } },
    entities: REGISTRE,
    ...surcharge,
  };
}

function monter(hass?: unknown) {
  const element = document.createElement('home-stock-planning') as any;
  element.connexion = { appeler: vi.fn(async () => ({ meals: [] })) };
  element.file = { ajouter: vi.fn(), rejouer: vi.fn(async () => {}) };
  if (hass !== undefined) element.hass = hass;
  document.body.append(element);
  return element;
}

async function attendre(element: any) {
  for (let tour = 0; tour < 6; tour += 1) {
    await Promise.resolve();
    await element.updateComplete;
  }
}

/** Une fausse carte Lovelace : ce que `createCardElement` rend vraiment est
 *  un élément à qui l'on repose `hass`, rien de plus exigeant que ça. */
function fausseCarte() {
  const carte = document.createElement('div');
  carte.className = 'fausse-carte-calendrier';
  return carte;
}

describe('entiteCalendrierRepas', () => {
  it('trouve l’entité par sa PLATEFORME, pas par son nom', () => {
    // Renommée à la main : une recherche par nom la manquerait en silence.
    expect(entiteCalendrierRepas(hassAvec())).toBe('calendar.repas_de_la_maison');
  });

  it('retombe sur le nom par défaut quand le registre n’est pas peuplé', () => {
    expect(entiteCalendrierRepas({ states: { 'calendar.home_stock_meals': {} } }))
      .toBe('calendar.home_stock_meals');
  });

  it('rend null quand aucun calendrier du garde-manger n’existe', () => {
    expect(entiteCalendrierRepas({ states: {}, entities: { 'calendar.famille': { platform: 'google' } } }))
      .toBeNull();
    expect(entiteCalendrierRepas(undefined)).toBeNull();
  });
});

describe('creerCarteCalendrier', () => {
  it('rend null quand Lovelace n’a jamais été chargé (loadCardHelpers absent)', async () => {
    expect(await creerCarteCalendrier('calendar.x', {} as any)).toBeNull();
  });

  it('rend null — sans lever — quand createCardElement refuse la config', async () => {
    const win = { loadCardHelpers: async () => ({
      createCardElement: () => { throw new Error('Entities must be specified'); },
    }) };
    expect(await creerCarteCalendrier('calendar.x', win as any)).toBeNull();
  });

  it('rend null — sans lever — quand loadCardHelpers lui-même échoue', async () => {
    const win = { loadCardHelpers: async () => { throw new Error('chunk absent'); } };
    expect(await creerCarteCalendrier('calendar.x', win as any)).toBeNull();
  });

  it('demande une carte « calendar » sur l’entité, en vue mois', async () => {
    const createCardElement = vi.fn(() => fausseCarte());
    const win = { loadCardHelpers: async () => ({ createCardElement }) };
    await creerCarteCalendrier('calendar.repas_de_la_maison', win as any);
    expect(createCardElement).toHaveBeenCalledWith({
      type: 'calendar',
      entities: ['calendar.repas_de_la_maison'],
      initial_view: 'dayGridMonth',
    });
  });
});

describe('<home-stock-planning> et la carte Home Assistant', () => {
  const fenetre = window as any;
  beforeEach(() => { document.body.innerHTML = ''; });
  afterEach(() => { delete fenetre.loadCardHelpers; });

  it('affiche la carte HA, et PAS la grille maison, quand elle est disponible', async () => {
    fenetre.loadCardHelpers = async () => ({ createCardElement: () => fausseCarte() });
    const element = monter(hassAvec());
    await attendre(element);
    expect(element.shadowRoot.querySelector('.fausse-carte-calendrier')).not.toBeNull();
    // Les deux ensemble seraient deux plannings sur un écran, chacun avec sa
    // propre idée de la semaine affichée.
    expect(element.shadowRoot.querySelector('.grille')).toBeNull();
  });

  it('garde la grille maison quand Lovelace n’a pas chargé la carte', async () => {
    const element = monter(hassAvec());
    await attendre(element);
    expect(element.shadowRoot.querySelector('.grille')).not.toBeNull();
  });

  it('garde la grille maison quand aucun calendrier du garde-manger n’existe', async () => {
    fenetre.loadCardHelpers = async () => ({ createCardElement: () => fausseCarte() });
    const element = monter({ states: {}, entities: {} });
    await attendre(element);
    expect(element.shadowRoot.querySelector('.grille')).not.toBeNull();
  });

  it('repasse hass à la carte à chaque changement, comme le ferait un tableau de bord', async () => {
    fenetre.loadCardHelpers = async () => ({ createCardElement: () => fausseCarte() });
    const element = monter(hassAvec());
    await attendre(element);
    const carte = element.shadowRoot.querySelector('.fausse-carte-calendrier') as any;
    const suivant = hassAvec({ states: { 'calendar.repas_de_la_maison': { state: 'on' } } });
    element.hass = suivant;
    await attendre(element);
    expect(carte.hass).toBe(suivant);
  });

  it('ne rebâtit pas la carte à chaque hass — sinon elle clignote et perd sa vue', async () => {
    const createCardElement = vi.fn(() => fausseCarte());
    fenetre.loadCardHelpers = async () => ({ createCardElement });
    const element = monter(hassAvec());
    await attendre(element);
    for (let i = 0; i < 5; i += 1) {
      element.hass = hassAvec({ states: { [`x${i}`]: {} } });
      await attendre(element);
    }
    expect(createCardElement).toHaveBeenCalledTimes(1);
  });
});
