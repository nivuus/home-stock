import { beforeEach, describe, expect, it, vi } from 'vitest';
import '../src/ecrans/validation';
import { feuilleDe, regleDe } from './aides-style';

function preview(surcharge: Record<string, unknown> = {}) {
  return {
    meal_id: 12, day: '2026-08-21', slot_key: 'dinner',
    recipe: { id: 4, name: 'Gratin de courgettes', servings: 2 },
    servings: 3, factor: 1.5,
    lines: [
      { ingredient_id: 41, label: '450 g', product_id: 8,
        product_name: 'Courgette', base_unit: 'g', status: 'ok',
        needed: 450, available: 900, raw_text: '300 g de courgettes',
        batches: [{ batch_id: 3, quantity: 450 }] },
    ],
    by_hand: [
      { ingredient_id: 42, label: '', product_id: null, product_name: null,
        base_unit: null, status: 'unmatched', needed: null, available: 0,
        raw_text: 'une gousse d’ail', batches: [] },
    ],
    dish: { product_name: 'Reste — Gratin de courgettes', parts: 3,
            best_before: '2026-08-24', cost: 4.12, kcal: 540, unvalued: 0 },
    blocking: [],
    ...surcharge,
  };
}

function monter(options: { preview?: unknown; sort?: string } = {}) {
  const element = document.createElement('home-stock-validation') as any;
  element.connexion = { appeler: vi.fn(async () => options.preview ?? preview()) };
  element.file = {
    ajouter: vi.fn(() => ({
      cle: 'k', sort: Promise.resolve(options.sort ?? 'envoyee'),
    })),
    rejouer: vi.fn(async () => {}),
  };
  element.mealId = 12;
  document.body.append(element);
  return element;
}

async function stabiliser(element: any) {
  await element.updateComplete;
  await element.updateComplete;
  await element.updateComplete;
}

const textes = (element: any, selecteur: string) =>
  [...element.shadowRoot.querySelectorAll(selecteur)]
    .map((n: Element) => n.textContent?.trim());

describe('<home-stock-validation>', () => {
  beforeEach(() => { document.body.innerHTML = ''; });

  it('affiche une ligne par ingrédient avec son statut', async () => {
    const element = monter();
    await stabiliser(element);
    expect(textes(element, '.sorties .ligne-nom')).toEqual(['Courgette']);
    expect(textes(element, '.sorties .ligne-statut')).toEqual(['prêt']);
  });

  it.each([['ok', 'prêt'], ['short', 'stock insuffisant'],
           ['unmatched', 'produit non identifié'],
           ['unquantified', 'quantité inconnue']])(
    'donne un libellé français au statut %s', async (statut, libelle) => {
      const donnees = preview() as any;
      donnees.lines[0].status = statut;
      if (statut === 'short') donnees.blocking = ['short'];
      const element = monter({ preview: donnees });
      await stabiliser(element);
      expect(textes(element, '.sorties .ligne-statut')).toEqual([libelle]);
    });

  it('n’affiche pas les lignes ignorées', async () => {
    // Sel, poivre, eau : ignorés SANS signalement. Le serveur ne les renvoie
    // ni dans `lines` ni dans `by_hand`, et l'écran n'en invente pas.
    const element = monter();
    await stabiliser(element);
    expect(textes(element, '.ligne-statut')).not.toContain('ignoré');
  });

  it('groupe les lignes non décrémentables sous « à sortir à la main »', async () => {
    const element = monter();
    await stabiliser(element);
    expect(textes(element, '.a-la-main h2')).toEqual(['À sortir à la main']);
    expect(textes(element, '.a-la-main .ligne-nom')).toEqual(['une gousse d’ail']);
  });

  it('ne propose pas de retirer une ligne qu’on sort déjà à la main', async () => {
    const element = monter();
    await stabiliser(element);
    expect(element.shadowRoot.querySelectorAll('.a-la-main .retirer')).toHaveLength(0);
    expect(element.shadowRoot.querySelectorAll('.sorties .retirer')).toHaveLength(1);
  });

  it('retire une ligne au clic et rappelle meal/preview, jamais meal/validate',
     async () => {
    const element = monter();
    await stabiliser(element);
    element.shadowRoot.querySelector('.sorties .retirer').click();
    await stabiliser(element);

    const types = element.connexion.appeler.mock.calls.map((c: any[]) => c[0]);
    expect(types.every((t: string) => t === 'home_stock/meal/preview')).toBe(true);
    expect(element.connexion.appeler).toHaveBeenLastCalledWith(
      'home_stock/meal/preview', { meal_id: 12, skip_ingredient_ids: [41] });
    expect(element.file.ajouter).not.toHaveBeenCalled();
  });

  it('bloque la validation tant qu’une ligne « short » n’est pas arbitrée',
     async () => {
    const donnees = preview({ blocking: ['short'] });
    (donnees.lines[0] as any).status = 'short';
    const element = monter({ preview: donnees });
    await stabiliser(element);
    expect(element.shadowRoot.querySelector('.valider').disabled).toBe(true);
    expect(element.shadowRoot.querySelector('.blocage')).not.toBeNull();
  });

  it('débloque la validation quand le blocage disparaît', async () => {
    const element = monter();
    await stabiliser(element);
    expect(element.shadowRoot.querySelector('.valider').disabled).toBe(false);
    expect(element.shadowRoot.querySelector('.blocage')).toBeNull();
  });

  it('affiche le récapitulatif du plat : parts, DLC, coût, kcal', async () => {
    const element = monter();
    await stabiliser(element);
    expect(textes(element, '.plat h2')).toEqual(['Reste — Gratin de courgettes']);
    expect(element.shadowRoot.querySelector('.plat-parts').textContent.trim()).toBe('3');
    expect(element.shadowRoot.querySelector('.plat-dlc').textContent.trim())
      .toBe('2026-08-24');
    expect(element.shadowRoot.querySelector('.plat-cout').textContent.trim())
      .toBe('4,12 €');
    expect(element.shadowRoot.querySelector('.plat-kcal').textContent.trim())
      .toBe('540 kcal');
  });

  it('affiche un tiret plutôt que « 0 » pour un nutriment inconnu', async () => {
    const donnees = preview();
    (donnees.dish as any).kcal = null;
    (donnees.dish as any).cost = null;
    const element = monter({ preview: donnees });
    await stabiliser(element);
    expect(element.shadowRoot.querySelector('.plat-kcal').textContent.trim()).toBe('—');
    expect(element.shadowRoot.querySelector('.plat-cout').textContent.trim()).toBe('—');
  });

  it('reprend le sélecteur de parts du lot 2 à l’identique', async () => {
    const element = monter();
    await stabiliser(element);
    expect(element.shadowRoot.querySelector('.partage-bascule')).not.toBeNull();
    element.shadowRoot.querySelector('.partage-bascule input').click();
    await stabiliser(element);
    expect(element.shadowRoot.querySelector('.parts-total')).not.toBeNull();
    expect(element.shadowRoot.querySelector('.parts-moi')).not.toBeNull();
  });

  it('accepte la virgule décimale dans les parts mangées', async () => {
    // `analyserNombre` gère déjà virgule ET point : ne pas réécrire un parseur.
    const element = monter();
    await stabiliser(element);
    const champ = element.shadowRoot.querySelector('.parts-mangees');
    champ.value = '1,5';
    champ.dispatchEvent(new Event('input'));
    await stabiliser(element);
    expect(element.partsMangees).toBe(1.5);
  });

  it('refuse localement plus de parts mangées que le plat n’en fait', async () => {
    const element = monter();
    await stabiliser(element);
    element.partsMangees = 4;
    element.shadowRoot.querySelector('.valider').click();
    await stabiliser(element);
    element.shadowRoot.querySelector('.valider').click();
    await stabiliser(element);
    expect(element.shadowRoot.querySelector('.erreur').textContent)
      .toContain('plus de parts que le plat');
    expect(element.file.ajouter).not.toHaveBeenCalled();
  });

  it('refuse localement parts_moi > parts_total', async () => {
    const element = monter();
    await stabiliser(element);
    element.partage = true;
    element.partsTotal = 2;
    element.partsMoi = 3;
    element.shadowRoot.querySelector('.valider').click();
    await stabiliser(element);
    element.shadowRoot.querySelector('.valider').click();
    await stabiliser(element);
    expect(element.shadowRoot.querySelector('.erreur').textContent)
      .toContain('plus de parts qu’il n’en a été servi');
    expect(element.file.ajouter).not.toHaveBeenCalled();
  });

  it('demande deux appuis : le premier arme, le second envoie', async () => {
    const element = monter();
    await stabiliser(element);

    element.shadowRoot.querySelector('.valider').click();
    await stabiliser(element);
    expect(element.file.ajouter).not.toHaveBeenCalled();
    expect(element.shadowRoot.querySelector('.valider').textContent.trim())
      .toBe('Confirmer la validation');

    element.shadowRoot.querySelector('.valider').click();
    await stabiliser(element);
    expect(element.file.ajouter).toHaveBeenCalledTimes(1);
  });

  it('un appui sur « Annuler » désarme sans rien envoyer', async () => {
    const element = monter();
    await stabiliser(element);
    element.shadowRoot.querySelector('.valider').click();
    await stabiliser(element);
    element.shadowRoot.querySelector('.annuler').click();
    await stabiliser(element);
    expect(element.file.ajouter).not.toHaveBeenCalled();
    expect(element.shadowRoot.querySelector('.valider').textContent.trim())
      .toBe('Valider le repas');
  });

  it('dit en toutes lettres qu’une validation ne s’annule pas', async () => {
    const element = monter();
    await stabiliser(element);
    expect(element.shadowRoot.querySelector('.sans-retour')).toBeNull();
    element.shadowRoot.querySelector('.valider').click();
    await stabiliser(element);
    expect(element.shadowRoot.querySelector('.sans-retour').textContent)
      .toContain('ne s\'annule pas');
  });

  it('n’utilise jamais window.confirm', async () => {
    const espion = vi.spyOn(window, 'confirm');
    const element = monter();
    await stabiliser(element);
    element.shadowRoot.querySelector('.valider').click();
    await stabiliser(element);
    element.shadowRoot.querySelector('.valider').click();
    await stabiliser(element);
    expect(espion).not.toHaveBeenCalled();
    espion.mockRestore();
  });

  it('envoie meal/validate par la file avec les parts retirées', async () => {
    const element = monter();
    await stabiliser(element);
    element.shadowRoot.querySelector('.sorties .retirer').click();
    await stabiliser(element);
    element.shadowRoot.querySelector('.valider').click();
    await stabiliser(element);
    element.shadowRoot.querySelector('.valider').click();
    await stabiliser(element);
    expect(element.file.ajouter).toHaveBeenCalledWith('home_stock/meal/validate', {
      meal_id: 12, portions_eaten: 1, skip_ingredient_ids: [41],
    });
  });

  it('émet « repas-valide » quand l’envoi est parti', async () => {
    const element = monter();
    await stabiliser(element);
    const vu: any[] = [];
    element.addEventListener('repas-valide', (e: any) => vu.push(e.detail));
    element.shadowRoot.querySelector('.valider').click();
    await stabiliser(element);
    element.shadowRoot.querySelector('.valider').click();
    await stabiliser(element);
    expect(vu).toEqual([{ meal_id: 12 }]);
  });

  it('affiche « en attente » quand la file garde l’action hors ligne', async () => {
    const element = monter({ sort: 'en-attente' });
    await stabiliser(element);
    element.shadowRoot.querySelector('.valider').click();
    await stabiliser(element);
    element.shadowRoot.querySelector('.valider').click();
    await stabiliser(element);
    expect(element.shadowRoot.querySelector('.en-attente')).not.toBeNull();
  });

  it('n’envoie rien deux fois si on double-clique la confirmation', async () => {
    const element = monter();
    await stabiliser(element);
    element.shadowRoot.querySelector('.valider').click();
    await stabiliser(element);
    const bouton = element.shadowRoot.querySelector('.valider');
    bouton.click();
    bouton.click();
    await stabiliser(element);
    expect(element.file.ajouter).toHaveBeenCalledTimes(1);
  });

  it('offre des cibles tactiles d’au moins 62 px, sur CHAQUE règle qui le promet', async () => {
    const element = monter();
    await stabiliser(element);
    // Chercher `min-height: var(--hs-touch)` dans la feuille ENTIÈRE ne prouve
    // rien : une seule autre règle qui le porte garde le test vert pendant que
    // le bouton visé retombe à 20 px (sonde du 2026-08-22). On isole donc
    // CHAQUE règle par son sélecteur avant de la sonder — la technique de
    // `tests/catalogue.test.ts` et `tests/shell-enveloppes.test.ts`, ici
    // généralisée aux listes de sélecteurs.
    const feuille = feuilleDe(element.constructor);
    for (const selecteur of [
      '.ligne',
      '.retirer',
      '.valider',
      '.annuler',
      '.parts-mangees',
      '.partage-bascule',
      '.parts-total',
      '.parts-moi',
    ]) {
      expect(regleDe(feuille, selecteur), selecteur).toContain('min-height: var(--hs-touch)');
    }
  });
});
