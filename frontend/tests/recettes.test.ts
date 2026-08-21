import { beforeEach, describe, expect, it, vi } from 'vitest';
import '../src/ecrans/recettes';

const RECETTES = [
  { id: 1, name: 'Bœuf bourguignon', servings: 4, total_minutes: 180,
    image_url: null, summary: null, language: 'fr', needs_review: 0,
    unmatched_count: 0 },
  { id: 2, name: 'Teriyaki Chicken Casserole', servings: 2, total_minutes: 35,
    image_url: null, summary: null, language: 'en', needs_review: 1,
    unmatched_count: 3 },
  { id: 3, name: 'Tartiflette', servings: 6, total_minutes: 60,
    image_url: null, summary: null, language: 'fr', needs_review: 0,
    unmatched_count: 1 },
];

const FICHES = [
  { source_ref: '52772', name: 'Teriyaki Chicken Casserole', image_url: null,
    category: 'Chicken', area: 'Japanese' },
];

function monter(options: { recettes?: unknown[]; hits?: unknown[];
                           reachable?: boolean; adapted?: boolean } = {}) {
  const element = document.createElement('home-stock-recettes') as any;
  const appeler = vi.fn(async (type: string) => {
    if (type === 'home_stock/recipes/list') {
      return { recipes: options.recettes ?? RECETTES };
    }
    if (type === 'home_stock/recipe/search_external') {
      return { hits: options.hits ?? FICHES, reachable: options.reachable ?? true };
    }
    if (type === 'home_stock/recipe/import_external') {
      return { recipe_id: 9, adapted: options.adapted ?? false };
    }
    return {};
  });
  element.connexion = { appeler };
  element.file = { ajouter: vi.fn(() => ({ cle: 'k', sort: Promise.resolve('envoyee') })) };
  document.body.append(element);
  return element;
}

async function stabiliser(element: any) {
  await element.updateComplete;
  await element.updateComplete;
}

const textes = (element: any, selecteur: string) =>
  [...element.shadowRoot.querySelectorAll(selecteur)]
    .map((n: Element) => n.textContent?.trim());

describe('<home-stock-recettes>', () => {
  beforeEach(() => { document.body.innerHTML = ''; });

  it('liste les recettes rendues par le serveur', async () => {
    const element = monter();
    await stabiliser(element);
    expect(textes(element, '.recette-nom')).toEqual([
      'Bœuf bourguignon', 'Teriyaki Chicken Casserole', 'Tartiflette']);
  });

  it('affiche le badge « à relire » sur une recette needs_review', async () => {
    const element = monter();
    await stabiliser(element);
    expect(textes(element, '.badge.relire')).toEqual(['à relire']);
  });

  it('affiche « n non appariés » quand il en reste', async () => {
    const element = monter();
    await stabiliser(element);
    expect(textes(element, '.badge.manque')).toEqual(['3 non appariés',
                                                      '1 non apparié']);
  });

  it('n’affiche aucun badge quand tout est apparié', async () => {
    const element = monter({ recettes: [RECETTES[0]] });
    await stabiliser(element);
    expect(element.shadowRoot.querySelectorAll('.badge')).toHaveLength(0);
  });

  it('filtre localement sur la saisie, sans rappeler le serveur', async () => {
    const element = monter();
    await stabiliser(element);
    const avant = element.connexion.appeler.mock.calls.length;

    const champ = element.shadowRoot.querySelector('.recherche');
    champ.value = 'tarti';
    champ.dispatchEvent(new Event('input'));
    await stabiliser(element);

    expect(textes(element, '.recette-nom')).toEqual(['Tartiflette']);
    expect(element.connexion.appeler.mock.calls.length).toBe(avant);
  });

  it('replie les accents et les ligatures dans le filtre', async () => {
    const element = monter();
    await stabiliser(element);
    const champ = element.shadowRoot.querySelector('.recherche');
    champ.value = 'boeuf';
    champ.dispatchEvent(new Event('input'));
    await stabiliser(element);
    expect(textes(element, '.recette-nom')).toEqual(['Bœuf bourguignon']);
  });

  it('émet « recette-ouverte » avec l’identifiant au clic sur une ligne', async () => {
    const element = monter();
    await stabiliser(element);
    const vu: any[] = [];
    element.addEventListener('recette-ouverte', (e: any) => vu.push(e.detail));
    element.shadowRoot.querySelectorAll('.recette')[2].click();
    expect(vu).toEqual([{ recipe_id: 3 }]);
  });

  it('appelle recipe/search_external au clic sur « Chercher ailleurs »', async () => {
    const element = monter();
    await stabiliser(element);
    element.shadowRoot.querySelector('.ailleurs').click();
    await stabiliser(element);
    expect(element.connexion.appeler).toHaveBeenCalledWith(
      'home_stock/recipe/search_external', { query: '' });
    expect(textes(element, '.fiche-nom')).toEqual(['Teriyaki Chicken Casserole']);
  });

  it('affiche un message explicite quand la source ne répond rien', async () => {
    const element = monter({ hits: [], reachable: false });
    await stabiliser(element);
    element.shadowRoot.querySelector('.ailleurs').click();
    await stabiliser(element);
    expect(element.shadowRoot.querySelector('.message').textContent)
      .toContain('injoignable');
  });

  it('distingue une source muette d’une recherche infructueuse', async () => {
    const element = monter({ hits: [], reachable: true });
    await stabiliser(element);
    element.shadowRoot.querySelector('.ailleurs').click();
    await stabiliser(element);
    expect(element.shadowRoot.querySelector('.message').textContent)
      .toContain('Aucune recette trouvée');
  });

  it('désactive « Chercher ailleurs » hors ligne', async () => {
    // La recherche en ligne est le SEUL bouton désactivé hors ligne : tout le
    // reste de l'écran fonctionne sur ce qui est déjà en base.
    const element = monter();
    element.enAttente = true;
    await stabiliser(element);
    expect(element.shadowRoot.querySelector('.ailleurs').disabled).toBe(true);
    expect(element.shadowRoot.querySelector('.recherche').disabled).toBeFalsy();
    expect(element.shadowRoot.querySelectorAll('.recette')).toHaveLength(3);
  });

  it('importe une fiche et signale si l’adaptation a eu lieu', async () => {
    const element = monter({ adapted: true });
    await stabiliser(element);
    element.shadowRoot.querySelector('.ailleurs').click();
    await stabiliser(element);
    element.shadowRoot.querySelector('.fiche').click();
    await stabiliser(element);
    expect(element.connexion.appeler).toHaveBeenCalledWith(
      'home_stock/recipe/import_external', { source_ref: '52772' });
    expect(element.shadowRoot.querySelector('.message').textContent)
      .toContain('adaptée en français');
  });

  it('dit qu’une recette importée sans agent reste à relire', async () => {
    const element = monter({ adapted: false });
    await stabiliser(element);
    element.shadowRoot.querySelector('.ailleurs').click();
    await stabiliser(element);
    element.shadowRoot.querySelector('.fiche').click();
    await stabiliser(element);
    expect(element.shadowRoot.querySelector('.message').textContent)
      .toContain('à relire');
  });

  it('affiche « aucune recette » plutôt qu’une liste vide muette', async () => {
    const element = monter({ recettes: [] });
    await stabiliser(element);
    expect(element.shadowRoot.querySelector('.vide').textContent)
      .toContain('Aucune recette');
  });

  it('marque une recette relue par la file hors-ligne', async () => {
    const element = monter();
    await stabiliser(element);
    await element.marquerRelue(RECETTES[1]);
    await stabiliser(element);
    expect(element.file.ajouter).toHaveBeenCalledWith(
      'home_stock/recipe/update', { recipe_id: 2, fields: { needs_review: 0 } });
    expect(textes(element, '.badge.relire')).toEqual([]);
  });

  it('offre des cibles tactiles d’au moins 48 px', async () => {
    const element = monter();
    await stabiliser(element);
    const styles = (element.constructor as any).styles.cssText;
    expect(styles).toContain('min-height: 48px');
  });
});
