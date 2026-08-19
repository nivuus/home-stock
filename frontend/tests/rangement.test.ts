import { afterEach, describe, expect, it, vi } from 'vitest';
import '../src/ecrans/rangement';
import { grouperParEmplacement, type Emplacement, type LigneRangement,
         type LigneRangementAutonome, type LigneRangementSession } from '../src/ecrans/rangement';
import type { Connexion } from '../src/connexion';

function ligneSession(partiel: Partial<LigneRangementSession> & { id: number }): LigneRangementSession {
  return {
    source: 'session', article_id: partiel.id, quantity: 500, unit_price: 0.005,
    stored_at: null, batch_id: null, product_id: partiel.id, product_name: `Produit ${partiel.id}`,
    base_unit: 'g', default_location_id: null, default_shelf_life_days: null, days_after_opening: null,
    article_label: `Produit ${partiel.id}`, brand: null, image: null, net_quantity: 500,
    aisle_name: 'Épicerie', aisle_position: 0,
    ...partiel,
  };
}

function ligneAutonome(partiel: Partial<LigneRangementAutonome> & { id: string }): LigneRangementAutonome {
  return {
    source: 'autonome', article_id: 1, quantity: 1, unit_price: null,
    product_name: 'Article seul', base_unit: 'piece', default_location_id: null,
    default_shelf_life_days: null, brand: null, image: null, net_quantity: null,
    ...partiel,
  };
}

const EMPLACEMENTS: Emplacement[] = [
  { id: 1, name: 'Placard', kind: 'cupboard', position: 0 },
  { id: 2, name: 'Frigo', kind: 'fridge', position: 1 },
];

describe('grouperParEmplacement', () => {
  it('regroupe par emplacement suggéré, dans l’ordre de première apparition', () => {
    const lignes: LigneRangement[] = [
      ligneSession({ id: 1, default_location_id: 2 }),
      ligneSession({ id: 2, default_location_id: 1 }),
      ligneSession({ id: 3, default_location_id: 2 }),
    ];
    const groupes = grouperParEmplacement(lignes, EMPLACEMENTS);
    expect(groupes.map((g) => g.nom)).toEqual(['Frigo', 'Placard']);
    expect(groupes[0].lignes.map((l) => l.id)).toEqual([1, 3]);
    expect(groupes[1].lignes.map((l) => l.id)).toEqual([2]);
  });

  it('groupe les lignes sans emplacement suggéré sous un intitulé dédié', () => {
    const lignes: LigneRangement[] = [ligneSession({ id: 1, default_location_id: null })];
    const groupes = grouperParEmplacement(lignes, EMPLACEMENTS);
    expect(groupes[0].nom).toBe('Emplacement à choisir');
  });
});

function monter(props: { lignes?: LigneRangement[]; connexion?: Connexion;
                         file?: { ajouter: ReturnType<typeof vi.fn>; rejouer?: ReturnType<typeof vi.fn> } } = {}) {
  const element = document.createElement('home-stock-rangement') as HTMLElement & {
    lignes: LigneRangement[]; connexion?: Connexion; file?: unknown; updateComplete: Promise<boolean>;
  };
  element.lignes = props.lignes ?? [];
  if (props.connexion) element.connexion = props.connexion;
  if (props.file) element.file = props.file;
  document.body.appendChild(element);
  return element;
}

function connexionFactice(locations: Emplacement[] = EMPLACEMENTS): Connexion {
  return { appeler: vi.fn().mockResolvedValue({ locations }) } as unknown as Connexion;
}

async function laisserPasserLesMicrotaches(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

describe('<home-stock-rangement>', () => {
  afterEach(() => {
    document.body.innerHTML = '';
  });

  it('propose les raccourcis de DLC construits sur la durée apprise du produit', async () => {
    const element = monter({
      lignes: [ligneSession({ id: 1, default_shelf_life_days: 5 })],
      connexion: connexionFactice(),
    });
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    const boutons = Array.from(element.shadowRoot!.querySelectorAll('.raccourci-dlc')).map((b) => b.textContent);
    expect(boutons.some((t) => t?.includes('5'))).toBe(true);
    expect(boutons.some((t) => t?.includes('Sans DLC'))).toBe(true);
  });

  it('range une ligne de session d’un appui : appelle store_line avec l’emplacement préposé', async () => {
    const ajouter = vi.fn();
    const element = monter({
      lignes: [ligneSession({ id: 42, default_location_id: 2, default_shelf_life_days: null })],
      connexion: connexionFactice(), file: { ajouter, rejouer: vi.fn().mockResolvedValue(undefined) },
    });
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    const boutonSansDlc = Array.from(element.shadowRoot!.querySelectorAll('.raccourci-dlc'))
      .find((b) => b.textContent?.includes('Sans DLC')) as HTMLButtonElement;
    boutonSansDlc.click();

    expect(ajouter).toHaveBeenCalledWith('home_stock/session/store_line', {
      line_id: 42, location_id: 2, best_before: null,
    });
  });

  it('range une ligne autonome d’un appui : appelle stock/add et signale la ligne rangée', async () => {
    const ajouter = vi.fn();
    const recu = vi.fn();
    const element = monter({
      lignes: [ligneAutonome({ id: 'auto-1', article_id: 7, quantity: 2, unit_price: 1.5, default_location_id: 1 })],
      connexion: connexionFactice(), file: { ajouter, rejouer: vi.fn().mockResolvedValue(undefined) },
    });
    element.addEventListener('ligne-autonome-rangee', (e) => recu((e as CustomEvent).detail));
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    const boutonSansDlc = Array.from(element.shadowRoot!.querySelectorAll('.raccourci-dlc'))
      .find((b) => b.textContent?.includes('Sans DLC')) as HTMLButtonElement;
    boutonSansDlc.click();

    expect(ajouter).toHaveBeenCalledWith('home_stock/stock/add', {
      article_id: 7, quantity: 2, location_id: 1, best_before: null, price_per_base_unit: 1.5,
    });
    expect(recu).toHaveBeenCalledWith({ id: 'auto-1' });
  });

  it('respecte l’emplacement choisi à la main plutôt que la suggestion', async () => {
    const ajouter = vi.fn();
    const element = monter({
      lignes: [ligneSession({ id: 1, default_location_id: 1 })],
      connexion: connexionFactice(), file: { ajouter, rejouer: vi.fn().mockResolvedValue(undefined) },
    });
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    const select = element.shadowRoot!.querySelector('.emplacement-champ') as HTMLSelectElement;
    select.value = '2';
    select.dispatchEvent(new Event('change'));
    await element.updateComplete;

    const boutonSansDlc = Array.from(element.shadowRoot!.querySelectorAll('.raccourci-dlc'))
      .find((b) => b.textContent?.includes('Sans DLC')) as HTMLButtonElement;
    boutonSansDlc.click();

    expect(ajouter).toHaveBeenCalledWith('home_stock/session/store_line', {
      line_id: 1, location_id: 2, best_before: null,
    });
  });

  it('annonce « Tout est rangé » et prévient le panneau quand la liste se vide', async () => {
    const element = monter({ lignes: [ligneSession({ id: 1 })], connexion: connexionFactice() });
    await laisserPasserLesMicrotaches();
    await element.updateComplete;
    expect(element.shadowRoot!.querySelector('.tout-range')).toBeNull();

    const termine = vi.fn();
    element.addEventListener('termine', termine);

    element.lignes = [];
    await element.updateComplete;

    expect(element.shadowRoot!.querySelector('.tout-range')).not.toBeNull();
    expect(element.shadowRoot!.querySelector('.tout-range')!.textContent).toContain('Tout est rangé');
    expect(termine).toHaveBeenCalledTimes(1);
  });

  it('ne prévient jamais le panneau si la liste est vide dès le montage (rien n’a été rangé)', async () => {
    const termine = vi.fn();
    const element = monter({ lignes: [], connexion: connexionFactice() });
    element.addEventListener('termine', termine);
    await laisserPasserLesMicrotaches();
    await element.updateComplete;

    expect(termine).not.toHaveBeenCalled();
  });
});
