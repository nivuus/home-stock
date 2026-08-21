import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import '../src/ecrans/recette';

const RECETTE = {
  recipe: {
    id: 4, name: 'Gratin de courgettes', servings: 2, total_minutes: 45,
    utensils: 'poêle, four', summary: 'Un gratin simple', image_url: null,
    language: 'fr', needs_review: 0,
  },
  steps: [
    { id: 1, position: 1, title: 'Préparer', image_url: null, instructions: [
      { id: 11, position: 1, text: 'Éplucher les courgettes',
        timer_label: null, timer_seconds: null },
      { id: 12, position: 2, text: 'Émincer', timer_label: null,
        timer_seconds: null },
    ]},
    { id: 2, position: 2, title: 'Cuire', image_url: null, instructions: [
      { id: 21, position: 1, text: 'Enfourner', timer_label: 'Cuisson',
        timer_seconds: 600 },
    ]},
    { id: 3, position: 3, title: 'Servir', image_url: null, instructions: [
      { id: 31, position: 1, text: 'Laisser reposer', timer_label: null,
        timer_seconds: null },
    ]},
  ],
  ingredients: [
    { id: 41, position: 1, product_id: 8, product_name: 'Courgette',
      product_base_unit: 'g', amount: 300, measure_name: null,
      packaging_name: null, raw_text: '300 g de courgettes',
      match_state: 'auto', display_amount: '300 g' },
    { id: 42, position: 2, product_id: null, product_name: null,
      product_base_unit: null, amount: null, measure_name: null,
      packaging_name: null, raw_text: 'une gousse d’ail',
      match_state: 'unmatched' },
  ],
};

function monter(options: { mealId?: number; recette?: unknown } = {}) {
  const element = document.createElement('home-stock-recette') as any;
  element.connexion = {
    appeler: vi.fn(async () => options.recette ?? RECETTE),
  };
  element.recipeId = 4;
  if (options.mealId !== undefined) element.mealId = options.mealId;
  document.body.append(element);
  return element;
}

async function stabiliser(element: any) {
  await element.updateComplete;
  await element.updateComplete;
}

const texte = (element: any, selecteur: string) =>
  element.shadowRoot.querySelector(selecteur)?.textContent?.trim();

describe('<home-stock-recette>', () => {
  beforeEach(() => { document.body.innerHTML = ''; vi.useRealTimers(); });
  afterEach(() => { vi.useRealTimers(); });

  it('affiche la couverture avant la première étape', async () => {
    const element = monter();
    await stabiliser(element);
    expect(texte(element, 'h1')).toBe('Gratin de courgettes');
    expect(element.shadowRoot.querySelector('.etape')).toBeNull();
  });

  it('affiche la ligne méta durée / parts / ustensiles et l’accroche', async () => {
    const element = monter();
    await stabiliser(element);
    expect(texte(element, '.duree')).toContain('45');
    expect(texte(element, '.parts')).toContain('2 parts');
    expect(texte(element, '.ustensiles')).toContain('poêle, four');
    expect(texte(element, '.accroche')).toBe('Un gratin simple');
  });

  it('découpe en autant de pages qu’il y a d’étapes, plus la couverture', async () => {
    const element = monter();
    await stabiliser(element);
    expect(element.nombreDePages).toBe(4);
    expect(texte(element, '.position')).toBe('1 / 4');
  });

  it('avance et recule au bouton, et jamais au-delà des bornes', async () => {
    const element = monter();
    await stabiliser(element);
    expect(element.shadowRoot.querySelector('.precedent').disabled).toBe(true);

    element.shadowRoot.querySelector('.suivant').click();
    await stabiliser(element);
    expect(texte(element, 'h2')).toBe('Préparer');

    element.shadowRoot.querySelector('.suivant').click();
    element.shadowRoot.querySelector('.suivant').click();
    await stabiliser(element);
    expect(texte(element, 'h2')).toBe('Servir');
    expect(element.shadowRoot.querySelector('.suivant').disabled).toBe(true);

    element.shadowRoot.querySelector('.precedent').click();
    await stabiliser(element);
    expect(texte(element, 'h2')).toBe('Cuire');
  });

  it('n’installe aucun écouteur de geste', async () => {
    // Preuve directe : la contrainte des tablettes interdit tout geste, et des
    // doigts couverts de farine glissent mal.
    const espion = vi.spyOn(Element.prototype, 'addEventListener');
    const element = monter();
    await stabiliser(element);
    const gestes = espion.mock.calls
      .map(([nom]) => nom)
      .filter((nom) => ['touchstart', 'touchmove', 'touchend', 'pointerdown',
                        'pointermove', 'swipe', 'contextmenu'].includes(nom as string));
    expect(gestes).toEqual([]);
    espion.mockRestore();
  });

  it('ouvre le bloc Ingrédients depuis l’étape 2 et y revient à la fermeture', async () => {
    // Perdre sa place au milieu d'une pâte est la raison pour laquelle on
    // retourne au papier.
    const element = monter();
    await stabiliser(element);
    element.shadowRoot.querySelector('.suivant').click();
    element.shadowRoot.querySelector('.suivant').click();
    await stabiliser(element);
    expect(texte(element, 'h2')).toBe('Cuire');

    element.shadowRoot.querySelector('.ingredients-bouton').click();
    await stabiliser(element);
    expect(element.shadowRoot.querySelector('.ingredients')).not.toBeNull();

    element.shadowRoot.querySelector('.fermer-ingredients').click();
    await stabiliser(element);
    expect(texte(element, 'h2')).toBe('Cuire');
  });

  it('affiche une ligne sans quantité avec son texte d’origine', async () => {
    const element = monter();
    await stabiliser(element);
    element.shadowRoot.querySelector('.ingredients-bouton').click();
    await stabiliser(element);
    const noms = [...element.shadowRoot.querySelectorAll('.ingredient-nom')]
      .map((n: Element) => n.textContent?.trim());
    expect(noms).toEqual(['Courgette', 'une gousse d’ail']);
  });

  it('marque une ligne non appariée comme « à sortir à la main »', async () => {
    const element = monter();
    await stabiliser(element);
    element.shadowRoot.querySelector('.ingredients-bouton').click();
    await stabiliser(element);
    expect(texte(element, '.mention')).toBe('à sortir à la main');
  });

  it('n’affiche pas de « 0 » pour une quantité inconnue', async () => {
    const element = monter();
    await stabiliser(element);
    element.shadowRoot.querySelector('.ingredients-bouton').click();
    await stabiliser(element);
    const quantites = [...element.shadowRoot.querySelectorAll('.quantite')]
      .map((n: Element) => n.textContent?.trim());
    expect(quantites).toEqual(['300 g', '']);
  });

  it('dessine un bouton de minuteur depuis timer_label et timer_seconds', async () => {
    const element = monter();
    await stabiliser(element);
    element.shadowRoot.querySelector('.suivant').click();
    element.shadowRoot.querySelector('.suivant').click();
    await stabiliser(element);
    expect(texte(element, '.minuteur')).toContain('Cuisson');
    expect(texte(element, '.minuteur')).toContain('10:00');
  });

  it('ne crée aucun minuteur quand la puce n’en porte pas', async () => {
    const element = monter();
    await stabiliser(element);
    element.shadowRoot.querySelector('.suivant').click();
    await stabiliser(element);
    expect(element.shadowRoot.querySelectorAll('.minuteur')).toHaveLength(0);
  });

  it('démarre le minuteur au clic et décompte', async () => {
    vi.useFakeTimers();
    const element = monter();
    await stabiliser(element);
    element.shadowRoot.querySelector('.suivant').click();
    element.shadowRoot.querySelector('.suivant').click();
    await stabiliser(element);

    element.shadowRoot.querySelector('.minuteur').click();
    await stabiliser(element);
    expect(element.minuteurs[21].enMarche).toBe(true);

    vi.advanceTimersByTime(3000);
    await stabiliser(element);
    expect(element.minuteurs[21].restant).toBe(597);
    expect(texte(element, '.minuteur')).toContain('9:57');
  });

  it('remet le minuteur à zéro au second appui', async () => {
    vi.useFakeTimers();
    const element = monter();
    await stabiliser(element);
    element.shadowRoot.querySelector('.suivant').click();
    element.shadowRoot.querySelector('.suivant').click();
    await stabiliser(element);

    element.shadowRoot.querySelector('.minuteur').click();
    vi.advanceTimersByTime(5000);
    await stabiliser(element);
    element.shadowRoot.querySelector('.minuteur').click();
    await stabiliser(element);

    expect(element.minuteurs[21].restant).toBe(600);
    expect(element.minuteurs[21].enMarche).toBe(false);
  });

  it('demande le wakeLock à l’ouverture et le relâche à la sortie', async () => {
    const release = vi.fn(async () => {});
    const request = vi.fn(async () => ({ release }));
    (navigator as any).wakeLock = { request };

    const element = monter();
    await stabiliser(element);
    expect(request).toHaveBeenCalledWith('screen');

    element.remove();
    await Promise.resolve();
    expect(release).toHaveBeenCalled();
    delete (navigator as any).wakeLock;
  });

  it('survit à l’absence totale de navigator.wakeLock', async () => {
    // jsdom ne l'a pas : c'est le cas nominal du test, pas un cas limite.
    expect((navigator as any).wakeLock).toBeUndefined();
    const element = monter();
    await stabiliser(element);
    expect(texte(element, 'h1')).toBe('Gratin de courgettes');
    element.remove();
  });

  it('n’appelle recipe/get qu’une seule fois', async () => {
    const element = monter();
    await stabiliser(element);
    element.shadowRoot.querySelector('.suivant').click();
    element.shadowRoot.querySelector('.ingredients-bouton').click();
    await stabiliser(element);
    expect(element.connexion.appeler).toHaveBeenCalledTimes(1);
  });

  it('reste lisible quand la connexion échoue après le chargement', async () => {
    // Le Wi-Fi de la cuisine ne vaut pas mieux que celui d'un rayon.
    const element = monter();
    await stabiliser(element);
    element.connexion.appeler = vi.fn(async () => { throw new Error('hors ligne'); });
    element.shadowRoot.querySelector('.suivant').click();
    await stabiliser(element);
    expect(texte(element, 'h2')).toBe('Préparer');
  });

  it('propose « J’ai cuisiné » seulement quand un mealId est fourni', async () => {
    const sansRepas = monter();
    await stabiliser(sansRepas);
    sansRepas.page = 3;
    await stabiliser(sansRepas);
    expect(sansRepas.shadowRoot.querySelector('.cuisine')).toBeNull();

    document.body.innerHTML = '';
    const avecRepas = monter({ mealId: 12 });
    await stabiliser(avecRepas);
    avecRepas.page = 3;
    await stabiliser(avecRepas);
    expect(avecRepas.shadowRoot.querySelector('.cuisine')).not.toBeNull();
  });

  it('émet « valider-repas » avec le meal_id depuis la dernière étape', async () => {
    const element = monter({ mealId: 12 });
    await stabiliser(element);
    element.page = 3;
    await stabiliser(element);

    const vu: any[] = [];
    element.addEventListener('valider-repas', (e: any) => vu.push(e.detail));
    element.shadowRoot.querySelector('.cuisine').click();
    expect(vu).toEqual([{ meal_id: 12 }]);
  });

  it('offre des cibles tactiles d’au moins 48 px', async () => {
    const element = monter();
    await stabiliser(element);
    expect((element.constructor as any).styles.cssText).toContain('min-height: 48px');
  });
});

describe('<home-stock-recette> — apparier depuis la cuisine', () => {
  beforeEach(() => { document.body.innerHTML = ''; });

  function monterAvecCandidats() {
    const recette = JSON.parse(JSON.stringify(RECETTE));
    recette.ingredients[1].candidates = [
      { product_id: 12, name: 'Ail', score: 0.9 },
      { product_id: 13, name: 'Ail des ours', score: 0.6 },
    ];
    const element = document.createElement('home-stock-recette') as any;
    element.connexion = { appeler: vi.fn(async () => recette) };
    element.file = {
      ajouter: vi.fn(() => ({ cle: 'k', sort: Promise.resolve('envoyee') })),
      rejouer: vi.fn(async () => {}),
    };
    element.recipeId = 4;
    document.body.append(element);
    return element;
  }

  it('propose les candidats d’une ligne non appariée', async () => {
    const element = monterAvecCandidats();
    await stabiliser(element);
    element.shadowRoot.querySelector('.ingredients-bouton').click();
    await stabiliser(element);
    const noms = [...element.shadowRoot.querySelectorAll('.candidat')]
      .map((n: Element) => n.textContent?.trim());
    expect(noms).toEqual(['Ail', 'Ail des ours']);
  });

  it('n’en propose aucun pour une ligne déjà appariée', async () => {
    const element = monterAvecCandidats();
    await stabiliser(element);
    element.shadowRoot.querySelector('.ingredients-bouton').click();
    await stabiliser(element);
    const lignes = element.shadowRoot.querySelectorAll('.ingredient');
    expect(lignes[0].querySelectorAll('.candidat')).toHaveLength(0);
  });

  it('apparie par la file et apprend l’alias, ce geste étant humain', async () => {
    const element = monterAvecCandidats();
    await stabiliser(element);
    element.shadowRoot.querySelector('.ingredients-bouton').click();
    await stabiliser(element);

    element.shadowRoot.querySelector('.candidat').click();
    await stabiliser(element);

    expect(element.file.ajouter).toHaveBeenCalledWith(
      'home_stock/recipe/ingredient/match',
      { ingredient_id: 42, product_id: 12, state: 'confirmed', create_alias: true });
  });

  it('retire la mention « à sortir à la main » une fois apparié', async () => {
    const element = monterAvecCandidats();
    await stabiliser(element);
    element.shadowRoot.querySelector('.ingredients-bouton').click();
    await stabiliser(element);
    element.shadowRoot.querySelector('.candidat').click();
    await stabiliser(element);

    expect(element.shadowRoot.querySelector('.mention')).toBeNull();
    expect(element.shadowRoot.querySelectorAll('.candidat')).toHaveLength(0);
    const noms = [...element.shadowRoot.querySelectorAll('.ingredient-nom')]
      .map((n: Element) => n.textContent?.trim());
    expect(noms).toEqual(['Courgette', 'Ail']);
  });
});
