import { beforeEach, describe, expect, it, vi } from 'vitest';
import '../src/ecrans/equipements';

const EQUIPEMENTS = [
  { id: 1, name: 'Purificateur', location_name: 'Salon', brand: 'Xiaomi',
    model: 'zhimi.airpurifier.mb4', serial: 'SN-42', purchased_on: '2025-01-01',
    warranty_months: 24, warranty_ends_on: '2027-01-01', days_left: 133,
    manual_url: null, manual_media_id: 'notices/purificateur.pdf',
    note: null, consumable_count: 3, device_id: null },
  { id: 2, name: 'Aspirateur', location_name: 'Cuisine', brand: 'Roborock',
    model: 'S5', serial: null, purchased_on: '2020-01-01', warranty_months: 24,
    warranty_ends_on: '2022-01-01', days_left: -1693, manual_url: null,
    manual_media_id: null, note: null, consumable_count: 0, device_id: null },
  { id: 3, name: 'Poêle 28 cm', location_name: null, brand: null, model: null,
    serial: null, purchased_on: null, warranty_months: null,
    warranty_ends_on: null, days_left: null, manual_url: null,
    manual_media_id: null, note: null, consumable_count: 0, device_id: null },
];

const FICHE = {
  ...EQUIPEMENTS[0],
  consumables: [
    { id: 10, equipment_id: 1, product_id: 5, role: 'filter', label: 'filtre HEPA',
      unit: 'percent', low_value: 15, keep_value: 20, product_name: 'Filtre HEPA MB4',
      in_stock: 1 },
    { id: 11, equipment_id: 1, product_id: 6, role: 'brush', label: null,
      unit: null, low_value: null, keep_value: null, product_name: 'Brosse latérale',
      in_stock: 0 },
  ],
  batteries: [
    { id: 4, label: 'Télécommande', verb: 'Pile à changer', last_percent: 55 },
  ],
};

function monter(options: { fiche?: unknown; notice?: boolean } = {}) {
  const appeler = vi.fn(async (type: string) => {
    if (type === 'home_stock/equipment/list') return { equipment: EQUIPEMENTS };
    if (type === 'home_stock/equipment/get') return { equipment: options.fiche ?? FICHE };
    return {};
  });
  const ajouter = vi.fn(() => ({ cle: 'k', sort: Promise.resolve('envoyee'),
                                 reponse: Promise.resolve(undefined) }));
  const element = document.createElement('home-stock-equipements') as any;
  element.connexion = { appeler };
  element.file = { ajouter, rejouer: vi.fn(async () => {}) };
  document.body.append(element);
  return { element, appeler, ajouter };
}

const attendre = async (element: any) => {
  for (let tour = 0; tour < 6; tour += 1) {
    await Promise.resolve();
    await element.updateComplete;
  }
};
const texte = (element: any) => element.shadowRoot.textContent as string;
const boutons = (element: any, selecteur: string) =>
  Array.from(element.shadowRoot.querySelectorAll(selecteur)) as HTMLElement[];

describe('<home-stock-equipements>', () => {
  beforeEach(() => { document.body.innerHTML = ''; });

  it('groupe les équipements par emplacement', async () => {
    const { element } = monter();
    await attendre(element);
    const titres = boutons(element, '.emplacement').map((n) => n.textContent!.trim());
    expect(titres).toEqual(['Cuisine', 'Salon', 'Sans emplacement']);
  });

  it('affiche une garantie à venir avec ses jours restants', async () => {
    const { element } = monter();
    await attendre(element);
    expect(texte(element)).toContain('garantie jusqu’au 01/01/2027');
    expect(texte(element)).toContain('133 jours');
  });

  it('dit qu’une garantie est terminée plutôt que de la masquer', async () => {
    const { element } = monter();
    await attendre(element);
    expect(texte(element)).toContain('garantie terminée depuis le 01/01/2022');
  });

  it('dit « garantie non renseignée » plutôt que de laisser vide', async () => {
    const { element } = monter();
    await attendre(element);
    expect(texte(element)).toContain('garantie non renseignée');
  });

  it('signale une notice introuvable sans casser la fiche', async () => {
    const { element } = monter({
      fiche: { ...FICHE, manual_media_id: 'notices/absente.pdf', manual_introuvable: true },
    });
    await attendre(element);
    boutons(element, '.equipement')[1].click();   // Purificateur, dans Salon
    await attendre(element);
    expect(texte(element)).toContain('notices/absente.pdf');
    expect(texte(element)).toContain('Purificateur');
  });

  it('n’offre aucun bouton de téléversement', async () => {
    const { element } = monter();
    await attendre(element);
    boutons(element, '.equipement')[1].click();
    await attendre(element);
    expect(element.shadowRoot.querySelector('input[type="file"]')).toBeNull();
    expect(texte(element).toLowerCase()).not.toContain('téléverser');
  });

  it('affiche un consommable avec son usure et son stock', async () => {
    const { element } = monter();
    await attendre(element);
    boutons(element, '.equipement')[1].click();
    await attendre(element);
    expect(texte(element)).toContain('Filtre HEPA MB4');
    expect(texte(element)).toContain('1 en stock');
  });

  it('dit « aucun en stock » pour un consommable en rupture', async () => {
    const { element } = monter();
    await attendre(element);
    boutons(element, '.equipement')[1].click();
    await attendre(element);
    expect(texte(element)).toContain('aucun en stock');
  });

  it('délie un consommable en deux appuis', async () => {
    const { element, ajouter } = monter();
    await attendre(element);
    boutons(element, '.equipement')[1].click();
    await attendre(element);
    boutons(element, '.delier')[0].click();
    await attendre(element);
    expect(ajouter).not.toHaveBeenCalled();
    expect(texte(element)).toContain('Confirmer');
    boutons(element, '.delier')[0].click();
    await attendre(element);
    expect(ajouter).toHaveBeenCalledWith('home_stock/equipment/consumable/unlink',
      { consumable_id: 10 });
  });

  it('affiche les piles rattachées à l’équipement', async () => {
    const { element } = monter();
    await attendre(element);
    boutons(element, '.equipement')[1].click();
    await attendre(element);
    expect(texte(element)).toContain('Télécommande');
  });

  it('n’écrit rien à l’ouverture de l’écran', async () => {
    const { element, ajouter } = monter();
    await attendre(element);
    boutons(element, '.equipement')[1].click();
    await attendre(element);
    expect(ajouter).not.toHaveBeenCalled();
  });
});
