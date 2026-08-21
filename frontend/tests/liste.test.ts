import { afterEach, describe, expect, it, vi } from 'vitest';
import '../src/ecrans/liste';
import { grouperListeParRayon, type DonneesListe, type LigneListe } from '../src/ecrans/liste';

function ligne(partiel: Partial<LigneListe> & { id: number }): LigneListe {
  return {
    product_id: partiel.id, free_text: null, quantity: 500, note: null,
    added_at: '2026-08-21T09:00:00', checked_at: null, removed_at: null,
    session_id: null, line_id: null, product_name: `Produit ${partiel.id}`,
    base_unit: 'g', aisle_id: 1, aisle_name: 'Épicerie', aisle_position: 1,
    claims: [],
    ...partiel,
  };
}

function donnees(lignes: LigneListe[], extra: Partial<DonneesListe> = {}): DonneesListe {
  return {
    items: lignes,
    store_id: 1,
    store_name: 'Leclerc',
    estimate: { amount: 62, confidence: 0.8, priced: 4, total: 5 },
    ...extra,
  };
}

function monter(props: { donnees?: DonneesListe | null;
                         file?: { ajouter: ReturnType<typeof vi.fn>;
                                  rejouer?: ReturnType<typeof vi.fn> };
                         enAttente?: number } = {}) {
  const element = document.createElement('home-stock-liste') as HTMLElement & {
    donnees: DonneesListe | null; file?: unknown; enAttente: number;
    updateComplete: Promise<boolean>;
  };
  element.donnees = props.donnees ?? null;
  if (props.file) element.file = props.file;
  element.enAttente = props.enAttente ?? 0;
  document.body.appendChild(element);
  return element;
}

function fausseFile() {
  return { ajouter: vi.fn().mockReturnValue({ cle: 'k', sort: Promise.resolve('envoyee') }),
           rejouer: vi.fn().mockResolvedValue(undefined) };
}

describe('grouperListeParRayon', () => {
  it('groupe sans jamais retrier : le serveur a déjà rendu l’ordre du magasin', () => {
    const lignes = [
      ligne({ id: 1, aisle_name: 'Surgelés' }),
      ligne({ id: 2, aisle_name: 'Boissons' }),
      ligne({ id: 3, aisle_name: 'Boissons' }),
    ];
    const groupes = grouperListeParRayon(lignes);
    expect(groupes.map((g) => g.rayon)).toEqual(['Surgelés', 'Boissons']);
    expect(groupes[1].lignes.map((l) => l.id)).toEqual([2, 3]);
  });

  it('range les lignes sans rayon sous un intitulé stable', () => {
    expect(grouperListeParRayon([ligne({ id: 1, aisle_name: null })])[0].rayon)
      .toBe('Sans rayon');
  });
});

describe('<home-stock-liste>', () => {
  afterEach(() => { document.body.innerHTML = ''; });

  it('groupe les lignes par rayon, dans l’ordre du magasin', async () => {
    const element = monter({ donnees: donnees([
      ligne({ id: 1, aisle_name: 'Surgelés', product_name: 'Glace' }),
      ligne({ id: 2, aisle_name: 'Boissons', product_name: 'Eau' }),
    ]) });
    await element.updateComplete;

    const titres = Array.from(element.shadowRoot!.querySelectorAll('.rayon-nom'))
      .map((n) => n.textContent);
    expect(titres).toEqual(['Surgelés', 'Boissons']);
  });

  it('affiche l’origine de chaque ligne en clair', async () => {
    const element = monter({ donnees: donnees([ligne({ id: 1, claims: [
      { origin: 'shortage', quantity: 500, detail: 'sous le seuil' },
      { origin: 'meal_plan', quantity: 300, detail: 'dîner de jeudi' },
    ] })]) });
    await element.updateComplete;

    expect(element.shadowRoot!.querySelector('.origines')!.textContent)
      .toContain('sous le seuil · dîner de jeudi');
  });

  it('affiche « ce qu’il faut » quand aucune quantité n’est connue', async () => {
    const element = monter({ donnees: donnees([ligne({ id: 1, quantity: null })]) });
    await element.updateComplete;
    expect(element.shadowRoot!.querySelector('.quantite')!.textContent)
      .toContain('ce qu’il faut');
  });

  it('coche une ligne en un seul appui', async () => {
    const file = fausseFile();
    const element = monter({ donnees: donnees([ligne({ id: 7 })]), file });
    await element.updateComplete;

    (element.shadowRoot!.querySelector('.cocher') as HTMLButtonElement).click();

    expect(file.ajouter).toHaveBeenCalledWith('home_stock/list/check', { item_id: 7 });
  });

  it('replie les lignes cochées en bas et les garde décochables', async () => {
    const file = fausseFile();
    const element = monter({ donnees: donnees([
      ligne({ id: 1, product_name: 'Lait' }),
      ligne({ id: 2, product_name: 'Pain', checked_at: '2026-08-21T10:00:00' }),
    ]), file });
    await element.updateComplete;

    const cochees = element.shadowRoot!.querySelector('.cochees')!;
    expect(cochees.textContent).toContain('Pain');
    expect(cochees.textContent).not.toContain('Lait');

    (cochees.querySelector('.decocher') as HTMLButtonElement).click();
    expect(file.ajouter).toHaveBeenCalledWith('home_stock/list/uncheck', { item_id: 2 });
  });

  it('ajoute un texte libre', async () => {
    const file = fausseFile();
    const element = monter({ donnees: donnees([]), file });
    await element.updateComplete;

    const champ = element.shadowRoot!.querySelector('.champ-ajout') as HTMLInputElement;
    champ.value = 'Piles télécommande salon';
    champ.dispatchEvent(new Event('input'));
    await element.updateComplete;
    (element.shadowRoot!.querySelector('.ajouter') as HTMLButtonElement).click();

    expect(file.ajouter).toHaveBeenCalledWith('home_stock/list/add',
      { free_text: 'Piles télécommande salon' });
  });

  it('n’ajoute rien sur un champ vide', async () => {
    const file = fausseFile();
    const element = monter({ donnees: donnees([]), file });
    await element.updateComplete;
    (element.shadowRoot!.querySelector('.ajouter') as HTMLButtonElement).click();
    expect(file.ajouter).not.toHaveBeenCalled();
  });

  it('retire une ligne sans la supprimer', async () => {
    const file = fausseFile();
    const element = monter({ donnees: donnees([ligne({ id: 3 })]), file });
    await element.updateComplete;

    (element.shadowRoot!.querySelector('.retirer') as HTMLButtonElement).click();

    expect(file.ajouter).toHaveBeenCalledWith('home_stock/list/remove', { item_id: 3 });
  });

  it('affiche le bandeau « n lignes, ≈ 62 € » et dit que c’est une estimation', async () => {
    const element = monter({ donnees: donnees([ligne({ id: 1 }), ligne({ id: 2 })]) });
    await element.updateComplete;

    const bandeau = element.shadowRoot!.querySelector('.bandeau')!.textContent!;
    expect(bandeau).toContain('2 lignes');
    expect(bandeau).toContain('≈');
    expect(bandeau).toContain('62,00 €');
    expect(bandeau).toContain('estimation sur 4 lignes sur 5');
  });

  it('n’affiche jamais deux fois la même donnée sur le même écran', async () => {
    const element = monter({ donnees: donnees([ligne({ id: 1, product_name: 'Lait' })]) });
    await element.updateComplete;
    const texte = element.shadowRoot!.textContent!;
    expect(texte.split('Lait').length - 1).toBe(1);
  });

  it('passe toutes ses écritures par la file hors ligne, avec une clé', async () => {
    const file = fausseFile();
    const element = monter({ donnees: donnees([ligne({ id: 1 })]), file });
    await element.updateComplete;

    (element.shadowRoot!.querySelector('.cocher') as HTMLButtonElement).click();
    (element.shadowRoot!.querySelector('.retirer') as HTMLButtonElement).click();

    expect(file.ajouter).toHaveBeenCalledTimes(2);
    expect(file.rejouer).toHaveBeenCalled();
  });

  it('reste utilisable hors ligne : une ligne cochée le reste à l’écran', async () => {
    const file = fausseFile();
    const element = monter({ donnees: donnees([ligne({ id: 1, product_name: 'Lait' })]),
                             file, enAttente: 1 });
    await element.updateComplete;

    (element.shadowRoot!.querySelector('.cocher') as HTMLButtonElement).click();
    await element.updateComplete;

    expect(element.shadowRoot!.querySelector('.cochees')!.textContent).toContain('Lait');
    expect(element.shadowRoot!.querySelector('.en-attente')!.textContent)
      .toContain('1 envoi');
  });

  it('affiche une liste vide sans erreur et dit quoi faire', async () => {
    const element = monter({ donnees: donnees([]) });
    await element.updateComplete;
    const vide = element.shadowRoot!.querySelector('.vide')!.textContent!;
    expect(vide).toContain('Rien à acheter');
  });

  it('affiche le magasin dont l’ordre est utilisé', async () => {
    const element = monter({ donnees: donnees([ligne({ id: 1 })]) });
    await element.updateComplete;
    expect(element.shadowRoot!.querySelector('.magasin')!.textContent).toContain('Leclerc');
  });

  it('n’affiche rien de cassé sans données', async () => {
    const element = monter({ donnees: null });
    await element.updateComplete;
    expect(element.shadowRoot!.textContent).toContain('Liste indisponible');
  });
});
