import { afterEach, describe, expect, it, vi } from 'vitest';
import '../src/ecrans/panier';
import { grouperParRayon, type DonneesSession, type LigneSession,
         type Totaux as Totaux4 } from '../src/ecrans/panier';
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
    stores: [{ id: 1, name: 'Leclerc', position: 0, active: 1,
               observed_sessions: 0, last_seen: null }],
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
    // Volontairement PAS alphabétique, ni au niveau des rayons ni des noms
    // dans un même rayon : une fixture triée par accident laisse passer un
    // .sort() ajouté par erreur dans render() (un relecteur a confirmé qu'un
    // tel .sort() survit à toute la suite si la fixture est déjà triée).
    // « Surgelés » avant « Boissons » (S > B), « Vin » avant « Eau » (V > E).
    const lignes = [
      ligne({ id: 1, aisle_name: 'Surgelés', product_name: 'Glace' }),
      ligne({ id: 2, aisle_name: 'Boissons', product_name: 'Vin' }),
      ligne({ id: 3, aisle_name: 'Boissons', product_name: 'Eau' }),
    ];
    const element = monter({ donnees: donnees(lignes, 12.5) });
    await element.updateComplete;

    const titres = Array.from(element.shadowRoot!.querySelectorAll('.rayon-nom')).map((n) => n.textContent);
    expect(titres).toEqual(['Surgelés', 'Boissons']);
    const noms = Array.from(element.shadowRoot!.querySelectorAll('.nom')).map((n) => n.textContent);
    expect(noms).toEqual(['Glace', 'Vin', 'Eau']);
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
    const ajouter = vi.fn().mockReturnValue({ cle: 'cle-test', sort: Promise.resolve('envoyee') });
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
    const ajouter = vi.fn().mockReturnValue({ cle: 'cle-test', sort: Promise.resolve('envoyee') });
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
    const ajouter = vi.fn().mockReturnValue({ cle: 'cle-test', sort: Promise.resolve('envoyee') });
    const lignes = [ligne({ id: 1, quantity: 1000, net_quantity: 500, base_unit: 'g' })];
    const element = monter({ donnees: donnees(lignes, 5), file: { ajouter, rejouer: vi.fn().mockResolvedValue(undefined) } });
    await element.updateComplete;

    (element.shadowRoot!.querySelector('.plus') as HTMLButtonElement).click();
    expect(ajouter).toHaveBeenCalledWith('home_stock/session/update_line', { line_id: 1, quantity: 1500 });

    (element.shadowRoot!.querySelector('.moins') as HTMLButtonElement).click();
    // Le serveur n'a pas encore répondu (donnees.quantity reste 1000, la
    // prop ne bouge pas dans ce test) : un « − » après un « + » doit annuler
    // l'intention précédente, pas repartir de la base serveur comme si le
    // premier appui n'avait pas eu lieu.
    expect(ajouter).toHaveBeenCalledWith('home_stock/session/update_line', { line_id: 1, quantity: 1000 });
  });

  it('accumule l’intention hors ligne : trois appuis sur « + » demandent bien trois paquets de plus, '
     + 'et l’affichage bouge à chaque appui', async () => {
    const ajouter = vi.fn().mockReturnValue({ cle: 'cle-test', sort: Promise.resolve('en-attente') });
    const rejouer = vi.fn().mockResolvedValue(undefined); // ne se résout jamais vers un nouveau `donnees` : hors ligne
    const lignes = [ligne({ id: 1, quantity: 1000, net_quantity: 500, base_unit: 'g' })];
    const element = monter({ donnees: donnees(lignes, 5), file: { ajouter, rejouer } });
    await element.updateComplete;

    const plus = element.shadowRoot!.querySelector('.plus') as HTMLButtonElement;
    plus.click();
    await element.updateComplete;
    expect(element.shadowRoot!.querySelector('.valeur-quantite')!.textContent).toContain('1500');

    plus.click();
    await element.updateComplete;
    expect(element.shadowRoot!.querySelector('.valeur-quantite')!.textContent).toContain('2000');

    plus.click();
    await element.updateComplete;
    expect(element.shadowRoot!.querySelector('.valeur-quantite')!.textContent).toContain('2500');

    // Trois envois distincts, un par appui — trois paquets voulus, pas un.
    expect(ajouter).toHaveBeenCalledTimes(3);
    expect(ajouter).toHaveBeenNthCalledWith(1, 'home_stock/session/update_line', { line_id: 1, quantity: 1500 });
    expect(ajouter).toHaveBeenNthCalledWith(2, 'home_stock/session/update_line', { line_id: 1, quantity: 2000 });
    expect(ajouter).toHaveBeenNthCalledWith(3, 'home_stock/session/update_line', { line_id: 1, quantity: 2500 });
  });

  it('efface l’intention locale dès qu’une quantité serveur fraîche arrive pour la ligne', async () => {
    const ajouter = vi.fn().mockReturnValue({ cle: 'cle-test', sort: Promise.resolve('envoyee') });
    const lignes = [ligne({ id: 1, quantity: 1000, net_quantity: 500, base_unit: 'g' })];
    const element = monter({ donnees: donnees(lignes, 5), file: { ajouter, rejouer: vi.fn().mockResolvedValue(undefined) } });
    await element.updateComplete;

    (element.shadowRoot!.querySelector('.plus') as HTMLButtonElement).click();
    await element.updateComplete;
    expect(element.shadowRoot!.querySelector('.valeur-quantite')!.textContent).toContain('1500');

    // Le serveur a confirmé 1500 (nouvelle valeur reçue) : l'intention locale
    // n'a plus lieu d'être, l'affichage doit rester à 1500, pas grimper à 2000.
    element.donnees = donnees([{ ...lignes[0], quantity: 1500 }], 7.5);
    await element.updateComplete;
    expect(element.shadowRoot!.querySelector('.valeur-quantite')!.textContent).toContain('1500');
  });

  it('convertit le prix de paquet saisi en prix par unité de base avant l’envoi', async () => {
    const ajouter = vi.fn().mockReturnValue({ cle: 'cle-test', sort: Promise.resolve('envoyee') });
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

  it('désactive le passage en caisse une fois la session sortie de « shopping » '
     + '(un second appui serait refusé pour toujours)', async () => {
    const lignes = [ligne({ id: 1 })];
    const enCaisse: DonneesSession = {
      ...donnees(lignes, 2.5),
      session: { ...donnees(lignes, 2.5).session, state: 'to_store' },
    };
    const element = monter({ donnees: enCaisse });
    await element.updateComplete;
    expect((element.shadowRoot!.querySelector('.checkout') as HTMLButtonElement).disabled).toBe(true);
  });

  it('n’écrit jamais directement par connexion : sans file, un appui ne fait rien '
     + '(il n’existe plus de chemin d’écriture hors file)', async () => {
    const appeler = vi.fn().mockResolvedValue({});
    const connexion = { appeler } as unknown as Connexion;
    const lignes = [ligne({ id: 1 })];
    const element = monter({ donnees: donnees(lignes, 2.5), connexion });
    await element.updateComplete;

    (element.shadowRoot!.querySelector('.plus') as HTMLButtonElement).click();
    await element.updateComplete;

    expect(appeler).not.toHaveBeenCalled();
  });

  it('désarme une suppression en attente dès qu’une autre action a lieu (ajuster une quantité)', async () => {
    const lignes = [ligne({ id: 1 }), ligne({ id: 2 })];
    const element = monter({
      donnees: donnees(lignes, 2.5),
      file: { ajouter: vi.fn().mockReturnValue({ cle: 'cle-test', sort: Promise.resolve('envoyee') }),
              rejouer: vi.fn().mockResolvedValue(undefined) },
    });
    await element.updateComplete;

    (element.shadowRoot!.querySelectorAll('.supprimer')[0] as HTMLButtonElement).click();
    await element.updateComplete;
    expect(element.shadowRoot!.querySelector('.confirmer-suppression')).not.toBeNull();

    // On ajuste la quantité d'une AUTRE ligne : la suppression armée doit
    // retomber, pas rester une gâchette prête pour un appui égaré.
    (element.shadowRoot!.querySelectorAll('.plus')[1] as HTMLButtonElement).click();
    await element.updateComplete;

    expect(element.shadowRoot!.querySelector('.confirmer-suppression')).toBeNull();
  });

  it('désarme une suppression en attente sur un rafraîchissement des données', async () => {
    const lignes = [ligne({ id: 1 })];
    const element = monter({ donnees: donnees(lignes, 2.5) });
    await element.updateComplete;

    (element.shadowRoot!.querySelector('.supprimer') as HTMLButtonElement).click();
    await element.updateComplete;
    expect(element.shadowRoot!.querySelector('.confirmer-suppression')).not.toBeNull();

    // Un rafraîchissement arrive (deux rayons plus loin, l'utilisateur a
    // continué de scanner) : l'armement ne doit pas survivre.
    element.donnees = donnees(lignes, 2.5);
    await element.updateComplete;

    expect(element.shadowRoot!.querySelector('.confirmer-suppression')).toBeNull();
  });

  it('prévient plutôt que d’effacer en silence un prix tapé sur une ligne au poids sans poids connu', async () => {
    const ajouter = vi.fn().mockReturnValue({ cle: 'cle-test', sort: Promise.resolve('envoyee') });
    const lignes = [ligne({ id: 1, base_unit: 'g', net_quantity: null })];
    const element = monter({ donnees: donnees(lignes, 2.5), file: { ajouter, rejouer: vi.fn().mockResolvedValue(undefined) } });
    await element.updateComplete;

    const champPrix = element.shadowRoot!.querySelector('.prix-champ') as HTMLInputElement;
    champPrix.value = '3,00';
    champPrix.dispatchEvent(new Event('input'));
    champPrix.dispatchEvent(new Event('change'));
    await element.updateComplete;

    // Rien n'est parti (aucune conversion possible sans poids connu), et la
    // saisie reste affichée avec une raison — pas de retour muet à l'ancien prix.
    expect(ajouter).not.toHaveBeenCalled();
    expect(champPrix.value).toBe('3,00');
    expect(element.shadowRoot!.querySelector('.erreur-prix')).not.toBeNull();
  });
});

describe('<home-stock-panier> : ce que le lot 4 ajoute', () => {
  afterEach(() => { document.body.innerHTML = ''; });

  function donneesLot4(lignes: LigneSession[], totaux: Partial<Totaux4> = {}) {
    return {
      session: { id: 1, state: 'shopping' as const, store: 'Leclerc',
                 started_at: '2026-08-19T10:00:00', closed_at: null },
      lines: lignes,
      totals: {
        lines: lignes.length, pending: lignes.length, total: 47.2,
        observed: 34.9, estimated: 12.3, unpriced_lines: 2, off_list_lines: 3,
        checked_items: 12, list_items: 17,
        ...totaux,
      },
      stores: [{ id: 1, name: 'Leclerc', position: 0, active: 1,
                 observed_sessions: 3, last_seen: null }],
    } as unknown as DonneesSession;
  }

  it('dit combien du total est estimé', async () => {
    const element = monter({ donnees: donneesLot4([ligne({ id: 1 })]) });
    await element.updateComplete;
    const total = element.shadowRoot!.querySelector('.repartition')!.textContent!;
    expect(total).toContain('12,30 €');
    expect(total).toContain('estimé');
  });

  it('signale les lignes sans prix sans les compter dans le total', async () => {
    const element = monter({ donnees: donneesLot4([ligne({ id: 1 })]) });
    await element.updateComplete;
    expect(element.shadowRoot!.querySelector('.repartition')!.textContent)
      .toContain('2 lignes sans prix');
    expect(element.shadowRoot!.querySelector('.total')!.textContent).toContain('47,20');
  });

  it('compte les lignes hors liste et permet de les isoler en un appui', async () => {
    const element = monter({ donnees: donneesLot4([
      ligne({ id: 1, product_name: 'Prévu' }),
      ligne({ id: 2, product_name: 'Imprévu' }),
    ]) });
    await element.updateComplete;

    const bouton = element.shadowRoot!.querySelector('.hors-liste') as HTMLButtonElement;
    expect(bouton.textContent).toContain('3 hors liste');
    bouton.click();
    await element.updateComplete;
    expect(element.shadowRoot!.querySelector('.hors-liste')!.getAttribute('aria-pressed'))
      .toBe('true');
  });

  it('affiche la progression sur la liste', async () => {
    const element = monter({ donnees: donneesLot4([ligne({ id: 1 })]) });
    await element.updateComplete;
    expect(element.shadowRoot!.querySelector('.progression')!.textContent)
      .toContain('12 / 17');
  });

  it('n’affiche pas de progression quand la liste est vide', async () => {
    const element = monter({ donnees: donneesLot4([ligne({ id: 1 })],
                                                  { checked_items: 0, list_items: 0 }) });
    await element.updateComplete;
    expect(element.shadowRoot!.querySelector('.progression')).toBeNull();
  });

  it('reste lisible avec les totaux du lot 1, sans les clés nouvelles', async () => {
    const element = monter({ donnees: donnees([ligne({ id: 1 })], 2.5) });
    await element.updateComplete;
    expect(element.shadowRoot!.querySelector('.total')!.textContent).toContain('2,50');
    expect(element.shadowRoot!.querySelector('.repartition')).toBeNull();
  });
});
