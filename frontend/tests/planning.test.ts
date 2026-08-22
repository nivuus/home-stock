import { beforeEach, describe, expect, it, vi } from 'vitest';
import '../src/ecrans/planning';
import { feuilleDe, regleDe } from './aides-style';

const REPAS = [
  { id: 1, uid: 'u1', day: '2026-08-21', slot_key: 'dinner', position: 0,
    recipe_id: 4, recipe_name: 'Gratin de courgettes', product_id: null,
    product_name: null, note: null, servings: 3, state: 'planned' },
  { id: 2, uid: 'u2', day: '2026-08-21', slot_key: 'snack', position: 0,
    recipe_id: null, recipe_name: null, product_id: 8, product_name: 'Yaourt',
    note: null, servings: 1, state: 'planned' },
  { id: 3, uid: 'u3', day: '2026-08-21', slot_key: 'lunch', position: 0,
    recipe_id: null, recipe_name: null, product_id: null, product_name: null,
    note: 'Restaurant', servings: 1, state: 'done' },
];

function monter(options: { large?: boolean; repas?: unknown[] } = {}) {
  const element = document.createElement('home-stock-planning') as any;
  element.connexion = {
    appeler: vi.fn(async () => ({ meals: options.repas ?? REPAS })),
  };
  element.file = {
    ajouter: vi.fn(() => ({ cle: 'k', sort: Promise.resolve('envoyee') })),
    rejouer: vi.fn(async () => {}),
  };
  element.large = options.large ?? false;
  element.debut = '2026-08-21';
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

describe('<home-stock-planning>', () => {
  beforeEach(() => { document.body.innerHTML = ''; });

  it('affiche sept colonnes et quatre créneaux en large', async () => {
    const element = monter({ large: true });
    await stabiliser(element);
    expect(element.shadowRoot.querySelectorAll('.jour')).toHaveLength(7);
    expect(element.shadowRoot.querySelectorAll('.ligne-creneau')).toHaveLength(4);
    expect(element.shadowRoot.querySelectorAll('.ligne-creneau .case'))
      .toHaveLength(28);
  });

  it('affiche une seule journée en étroit, avec précédent et suivant', async () => {
    // Pas de grille de sept colonnes réduite : elle produirait des cibles sous
    // 48 px, que `verifier-rendu.mjs` refuse à juste titre.
    const element = monter({ large: false });
    await stabiliser(element);
    expect(element.shadowRoot.querySelectorAll('.ligne-creneau .case'))
      .toHaveLength(4);
    expect(element.shadowRoot.querySelector('.precedent-jour')).not.toBeNull();
    expect(element.shadowRoot.querySelector('.suivant-jour')).not.toBeNull();
  });

  it('nomme les créneaux en français dans l’ordre du planning', async () => {
    const element = monter();
    await stabiliser(element);
    expect(textes(element, '.creneau')).toEqual([
      'Petit-déjeuner', 'Déjeuner', 'Dîner', 'En-cas']);
  });

  it('affiche un repas de recette, un repas de produit et une note', async () => {
    const element = monter();
    await stabiliser(element);
    expect(textes(element, '.repas-nom').sort()).toEqual(
      ['Gratin de courgettes', 'Restaurant', 'Yaourt']);
  });

  it('marque visuellement un repas validé', async () => {
    const element = monter();
    await stabiliser(element);
    expect(element.shadowRoot.querySelectorAll('.etat-done')).toHaveLength(1);
    expect(textes(element, '.valide')).toEqual(['validé']);
  });

  it('pose un repas par meal/plan avec le jour et le créneau cliqués', async () => {
    const element = monter();
    await stabiliser(element);
    element.shadowRoot.querySelectorAll('.poser')[2].click();
    await stabiliser(element);
    expect(element.file.ajouter).toHaveBeenCalledWith('home_stock/meal/plan', {
      day: '2026-08-21', slot_key: 'dinner', note: 'Repas', servings: 1,
    });
  });

  it('déplace un repas par meal/move', async () => {
    const element = monter();
    await stabiliser(element);
    await element.deplacer(REPAS[0], '2026-08-23', 'lunch');
    expect(element.file.ajouter).toHaveBeenCalledWith('home_stock/meal/move', {
      meal_id: 1, day: '2026-08-23', slot_key: 'lunch',
    });
  });

  it('refuse de déplacer un repas validé, et le dit', async () => {
    const element = monter();
    await stabiliser(element);
    await element.deplacer(REPAS[2], '2026-08-23', 'lunch');
    await stabiliser(element);
    expect(element.file.ajouter).not.toHaveBeenCalled();
    expect(element.shadowRoot.querySelector('.message').textContent)
      .toContain('date figée');
  });

  it('annule un repas planifié en deux appuis', async () => {
    // Les boutons sont passés en icônes (Task 14) : plus de texte
    // « Confirmer » à lire, le second appui se lit dans l'aria-label.
    const element = monter();
    await stabiliser(element);
    const bouton = element.shadowRoot.querySelector('.annuler-repas');
    bouton.click();
    await stabiliser(element);
    expect(element.file.ajouter).not.toHaveBeenCalled();
    expect(element.shadowRoot.querySelector('.annuler-repas').getAttribute('aria-label'))
      .toMatch(/^Confirmer /);

    element.shadowRoot.querySelector('.annuler-repas').click();
    await stabiliser(element);
    expect(element.file.ajouter).toHaveBeenCalledWith(
      'home_stock/meal/cancel', expect.objectContaining({ meal_id: expect.any(Number) }));
  });

  it('ouvre la recette au clic sur un repas de recette', async () => {
    const element = monter();
    await stabiliser(element);
    const vu: any[] = [];
    element.addEventListener('recette-ouverte', (e: any) => vu.push(e.detail));
    element.ouvrirRecette(REPAS[0]);
    expect(vu).toEqual([{ recipe_id: 4, meal_id: 1 }]);
  });

  it('n’ouvre pas de recette sur un repas qui n’en a pas', async () => {
    const element = monter();
    await stabiliser(element);
    const vu: any[] = [];
    element.addEventListener('recette-ouverte', (e: any) => vu.push(e.detail));
    element.ouvrirRecette(REPAS[1]);
    expect(vu).toEqual([]);
  });

  it('ouvre la validation au clic sur « Valider »', async () => {
    const element = monter();
    await stabiliser(element);
    const vu: any[] = [];
    element.addEventListener('valider-repas', (e: any) => vu.push(e.detail));
    element.shadowRoot.querySelector('.valider-repas').click();
    expect(vu.length).toBe(1);
  });

  it('n’ouvre pas la validation sur un repas déjà validé', async () => {
    const element = monter();
    await stabiliser(element);
    const vu: any[] = [];
    element.addEventListener('valider-repas', (e: any) => vu.push(e.detail));
    element.ouvrirValidation(REPAS[2]);
    expect(vu).toEqual([]);
    // Et le bouton n'est même pas offert.
    const valides = element.shadowRoot.querySelectorAll('.etat-done .valider-repas');
    expect(valides).toHaveLength(0);
  });

  it('affiche un jour vide sans planter', async () => {
    const element = monter({ repas: [] });
    await stabiliser(element);
    expect(element.shadowRoot.querySelectorAll('.repas')).toHaveLength(0);
    expect(element.shadowRoot.querySelectorAll('.poser')).toHaveLength(4);
  });

  it('avance d’un jour en étroit et d’une semaine en large', async () => {
    const etroit = monter({ large: false });
    await stabiliser(etroit);
    await etroit.allerA(1);
    expect(etroit.debut).toBe('2026-08-22');

    document.body.innerHTML = '';
    const large = monter({ large: true });
    await stabiliser(large);
    await large.allerA(1);
    expect(large.debut).toBe('2026-08-28');
  });

  it('offre des cibles tactiles d’au moins 62 px, sur CHAQUE geste de la grille', async () => {
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
      '.entete button',
      '.poser',
      '.repas-nom',
      '.valider-repas',
      '.annuler-repas',
    ]) {
      expect(regleDe(feuille, selecteur), selecteur).toContain('min-height: var(--hs-touch)');
    }
  });
});

describe('planning : des actions qui ne noient pas la grille', () => {
  // Le brief de cette tâche portait un quatrième test, « se désabonne au
  // démontage, dans les deux enveloppes », copié depuis
  // `tests/shell-enveloppes.test.ts` (monte `hs-card`/`hs-button` via un
  // `monter(balise)` qui n'existe pas ici, importe `pendingCountForTests`
  // sans l'importer). `planning.ts` ne porte aucun abonnement `whenDefined`
  // propre — c'est `hs-icon` qui gère ce cycle de vie, déjà couvert par les
  // tests de `shell-ha-available` et `shell-enveloppes`. Test omis ici :
  // il ne vérifie rien de ce fichier.

  it('rend les actions en icônes, pas en libellés répétés', async () => {
    const el = await monter({ repas: [REPAS[0]] });
    await stabiliser(el);
    const valider = el.shadowRoot!.querySelector('.valider-repas')!;
    expect(valider.querySelector('hs-icon')).not.toBeNull();
    expect(valider.textContent!.trim()).toBe('');
  });

  it('garde l’action annonçable, et nommant SON repas', async () => {
    // Cinquante-six boutons « Valider » identiques ne se distinguent pas au
    // lecteur d'écran : chacun doit dire lequel il valide.
    const el = await monter({ repas: [REPAS[0]] });
    await stabiliser(el);
    const valider = el.shadowRoot!.querySelector('.valider-repas')!;
    expect(valider.getAttribute('aria-label')).toMatch(/^Valider /);
    expect(valider.getAttribute('aria-label')!.length).toBeGreaterThan('Valider '.length);
  });

  // Pas de test de cible tactile ici : la Task 14 en avait recopié un, mot
  // pour mot, depuis la Task 6 — deux titres, un seul corps, et aucun des
  // deux ne sondait sa propre règle. `.valider-repas` et `.annuler-repas`
  // sont désormais couverts, nommément, par le test unique du bloc ci-dessus.
});
