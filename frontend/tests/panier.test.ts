import { afterEach, describe, expect, it, vi } from 'vitest';
import '../src/ecrans/panier';
import { grouperParRayon, type DonneesSession, type LigneSession } from '../src/ecrans/panier';
import type { Connexion } from '../src/connexion';

function ligne(partiel: Partial<LigneSession> & { id: number }): LigneSession {
  return {
    article_id: partiel.id, quantity: 500, unit_price: 0.005, stored_at: null,
    batch_id: null, product_id: partiel.id, product_name: `Produit ${partiel.id}`, base_unit: 'g',
    default_location_id: null, default_shelf_life_days: null, days_after_opening: null,
    article_label: null, brand: null, image: null, net_quantity: 500,
    aisle_name: 'Épicerie', aisle_position: 0,
    ...partiel,
  };
}

function donnees(lignes: LigneSession[], total: number): DonneesSession {
  return {
    session: { id: 1, state: 'shopping', store: 'Leclerc', started_at: '2026-08-19T10:00:00', closed_at: null },
    lines: lignes,
    totals: { lines: lignes.length, pending: lignes.length, total },
    stores: ['Leclerc'],
  };
}

describe('grouperParRayon : regroupe sans jamais retrier', () => {
  it('regroupe des lignes contiguës du même rayon', () => {
    const lignes = [
      ligne({ id: 1, aisle_name: 'Épicerie' }),
      ligne({ id: 2, aisle_name: 'Épicerie' }),
      ligne({ id: 3, aisle_name: 'Frais' }),
    ];
    const groupes = grouperParRayon(lignes);
    expect(groupes.map((g) => g.rayon)).toEqual(['Épicerie', 'Frais']);
    expect(groupes[0].lignes.map((l) => l.id)).toEqual([1, 2]);
    expect(groupes[1].lignes.map((l) => l.id)).toEqual([3]);
  });

  it('préserve l’ordre reçu, y compris si un rayon réapparaît plus loin (le serveur ne le ferait pas, '
     + 'mais la fonction ne doit jamais recomposer les groupes par nom)', () => {
    const lignes = [
      ligne({ id: 1, aisle_name: 'Épicerie' }),
      ligne({ id: 2, aisle_name: 'Frais' }),
      ligne({ id: 3, aisle_name: 'Épicerie' }),
    ];
    const groupes = grouperParRayon(lignes);
    // Deux groupes « Épicerie » distincts, pas fusionnés : fusionner supposerait
    // de retrier, ce que la fonction ne fait jamais.
    expect(groupes.map((g) => g.rayon)).toEqual(['Épicerie', 'Frais', 'Épicerie']);
  });

  it('groupe les lignes sans rayon sous un intitulé stable', () => {
    const lignes = [ligne({ id: 1, aisle_name: null })];
    const groupes = grouperParRayon(lignes);
    expect(groupes[0].rayon).toBe('Sans rayon');
  });

  it('rend une liste vide pour un panier vide', () => {
    expect(grouperParRayon([])).toEqual([]);
  });
});

function monter(props: { donnees?: DonneesSession | null; connexion?: Connexion;
                         file?: { ajouter: ReturnType<typeof vi.fn>; rejouer?: ReturnType<typeof vi.fn> };
                         enAttente?: number } = {}) {
  const element = document.createElement('home-stock-panier') as HTMLElement & {
    donnees: DonneesSession | null; connexion?: Connexion; file?: unknown; enAttente: number;
    updateComplete: Promise<boolean>;
  };
  element.donnees = props.donnees ?? null;
  if (props.connexion) element.connexion = props.connexion;
  if (props.file) element.file = props.file;
  element.enAttente = props.enAttente ?? 0;
  document.body.appendChild(element);
  return element;
}

describe('<home-stock-panier>', () => {
  afterEach(() => {
    document.body.innerHTML = '';
  });

  it('affiche les lignes groupées par rayon dans l’ordre reçu, sans les retrier', async () => {
    const lignes = [
      ligne({ id: 1, aisle_name: 'Épicerie', product_name: 'Farine' }),
      ligne({ id: 2, aisle_name: 'Frais', product_name: 'Lait' }),
      ligne({ id: 3, aisle_name: 'Frais', product_name: 'Yaourt' }),
    ];
    const element = monter({ donnees: donnees(lignes, 12.5) });
    await element.updateComplete;

    const titres = Array.from(element.shadowRoot!.querySelectorAll('.rayon-nom')).map((n) => n.textContent);
    expect(titres).toEqual(['Épicerie', 'Frais']);
    const noms = Array.from(element.shadowRoot!.querySelectorAll('.nom')).map((n) => n.textContent);
    expect(noms).toEqual(['Farine', 'Lait', 'Yaourt']);
  });

  it('affiche le total du serveur, jamais recalculé côté client', async () => {
    // Les lignes, prises isolément, vaudraient 500*0,005 = 2,5 € ; le total
    // serveur affiché ici est délibérément différent (ristourne, arrondi
    // serveur...) pour prouver qu'il n'est pas recalculé.
    const lignes = [ligne({ id: 1, quantity: 500, unit_price: 0.005 })];
    const element = monter({ donnees: donnees(lignes, 9.99) });
    await element.updateComplete;

    expect(element.shadowRoot!.querySelector('.total')!.textContent).toContain('9,99');
  });

  it('demande deux appuis avant de supprimer une ligne', async () => {
    const ajouter = vi.fn();
    const lignes = [ligne({ id: 1 })];
    const element = monter({ donnees: donnees(lignes, 2.5), file: { ajouter, rejouer: vi.fn().mockResolvedValue(undefined) } });
    await element.updateComplete;

    const boutonSupprimer = element.shadowRoot!.querySelector('.supprimer') as HTMLButtonElement;
    boutonSupprimer.click();
    await element.updateComplete;

    // Premier appui : armement seulement, rien envoyé.
    expect(ajouter).not.toHaveBeenCalled();
    const boutonConfirmer = element.shadowRoot!.querySelector('.confirmer-suppression') as HTMLButtonElement;
    expect(boutonConfirmer).not.toBeNull();

    boutonConfirmer.click();
    await element.updateComplete;

    expect(ajouter).toHaveBeenCalledWith('home_stock/session/remove_line', { line_id: 1 });
  });

  it('annule l’armement sans rien envoyer', async () => {
    const ajouter = vi.fn();
    const lignes = [ligne({ id: 1 })];
    const element = monter({ donnees: donnees(lignes, 2.5), file: { ajouter, rejouer: vi.fn().mockResolvedValue(undefined) } });
    await element.updateComplete;

    (element.shadowRoot!.querySelector('.supprimer') as HTMLButtonElement).click();
    await element.updateComplete;
    (element.shadowRoot!.querySelector('.annuler-suppression') as HTMLButtonElement).click();
    await element.updateComplete;

    expect(element.shadowRoot!.querySelector('.supprimer')).not.toBeNull();
    expect(ajouter).not.toHaveBeenCalled();
  });

  it('n’affiche le compteur d’actions en attente que si la file n’est pas vide', async () => {
    const lignes = [ligne({ id: 1 })];
    const sansAttente = monter({ donnees: donnees(lignes, 2.5), enAttente: 0 });
    await sansAttente.updateComplete;
    expect(sansAttente.shadowRoot!.querySelector('.en-attente')).toBeNull();

    document.body.innerHTML = '';
    const avecAttente = monter({ donnees: donnees(lignes, 2.5), enAttente: 2 });
    await avecAttente.updateComplete;
    expect(avecAttente.shadowRoot!.querySelector('.en-attente')!.textContent).toContain('2');
  });

  it('ajuste la quantité par paquet (net_quantity) via update_line', async () => {
    const ajouter = vi.fn();
    const lignes = [ligne({ id: 1, quantity: 1000, net_quantity: 500, base_unit: 'g' })];
    const element = monter({ donnees: donnees(lignes, 5), file: { ajouter, rejouer: vi.fn().mockResolvedValue(undefined) } });
    await element.updateComplete;

    (element.shadowRoot!.querySelector('.plus') as HTMLButtonElement).click();
    expect(ajouter).toHaveBeenCalledWith('home_stock/session/update_line', { line_id: 1, quantity: 1500 });

    (element.shadowRoot!.querySelector('.moins') as HTMLButtonElement).click();
    expect(ajouter).toHaveBeenCalledWith('home_stock/session/update_line', { line_id: 1, quantity: 500 });
  });

  it('convertit le prix de paquet saisi en prix par unité de base avant l’envoi', async () => {
    const ajouter = vi.fn();
    const lignes = [ligne({ id: 1, base_unit: 'g', net_quantity: 500, unit_price: 0.004 })];
    const element = monter({ donnees: donnees(lignes, 2), file: { ajouter, rejouer: vi.fn().mockResolvedValue(undefined) } });
    await element.updateComplete;

    const champPrix = element.shadowRoot!.querySelector('.prix-champ') as HTMLInputElement;
    champPrix.value = '3,00';
    champPrix.dispatchEvent(new Event('input'));
    champPrix.dispatchEvent(new Event('change'));

    // 3,00 € pour 500 g → 0,006 €/g.
    expect(ajouter).toHaveBeenCalledWith('home_stock/session/update_line', { line_id: 1, unit_price: 0.006 });
  });

  it('désactive le passage en caisse quand le panier est vide', async () => {
    const element = monter({ donnees: donnees([], 0) });
    await element.updateComplete;
    expect((element.shadowRoot!.querySelector('.checkout') as HTMLButtonElement).disabled).toBe(true);
  });

  it('affiche un message quand aucune session n’est ouverte', async () => {
    const element = monter({ donnees: null });
    await element.updateComplete;
    expect(element.shadowRoot!.querySelector('.vide')).not.toBeNull();
  });
});
