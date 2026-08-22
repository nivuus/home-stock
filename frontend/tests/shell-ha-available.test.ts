import { afterEach, describe, expect, it, vi } from 'vitest';
import { isDefined, pendingCountForTests, primeHaComponents, resetForTests, whenDefined }
  from '../src/shell/ui/ha-available';

afterEach(() => {
  resetForTests();
  // `vi.restoreAllMocks()` plutôt qu'un `espion.mockRestore()` local en fin
  // de test : si une assertion lève AVANT ce restore (précisément le
  // scénario que l'espion sert à détecter), un `afterEach` global le
  // rattrape quand même — un `mockRestore()` en dernière ligne d'un test en
  // échec ne s'exécute jamais, et l'espion pollue les tests suivants.
  vi.restoreAllMocks();
});

describe('détection des composants Home Assistant', () => {
  it('dit faux pour un élément que HA n’a pas chargé', () => {
    expect(isDefined('ha-card-jamais-defini')).toBe(false);
  });

  it('dit vrai pour un élément défini', () => {
    const nom = `ha-card-test-${Math.random().toString(36).slice(2)}`;
    customElements.define(nom, class extends HTMLElement {});
    expect(isDefined(nom)).toBe(true);
  });

  it('rappelle son abonné quand l’élément arrive APRÈS le premier rendu', async () => {
    // Le cas qui compte : la coquille rend son repli, puis Lovelace charge
    // son chunk. Sans ce rappel, l'utilisateur garderait le repli jusqu'à
    // ce qu'il quitte la page.
    const nom = `ha-card-tardif-${Math.random().toString(36).slice(2)}`;
    const rendreANouveau = vi.fn();
    whenDefined(nom, rendreANouveau);
    expect(rendreANouveau).not.toHaveBeenCalled();

    customElements.define(nom, class extends HTMLElement {});
    await customElements.whenDefined(nom);
    await Promise.resolve();

    expect(rendreANouveau).toHaveBeenCalledTimes(1);
  });

  it('n’ouvre qu’UNE promesse native, quel que soit le nombre d’abonnés', async () => {
    // Le test précédent (appeler a et b une fois chacun) était creux : il
    // resterait vrai même avec une promesse native PAR abonné. La propriété
    // qui compte, c'est l'appel natif lui-même — on l'espionne.
    const nom = `ha-card-partage-${Math.random().toString(36).slice(2)}`;
    const espion = vi.spyOn(customElements, 'whenDefined');
    const a = vi.fn();
    const b = vi.fn();
    const c = vi.fn();
    whenDefined(nom, a);
    whenDefined(nom, b);
    whenDefined(nom, c);
    // C'est CELA la propriété : trois abonnés, une seule promesse native.
    expect(espion.mock.calls.filter(([n]) => n === nom)).toHaveLength(1);

    customElements.define(nom, class extends HTMLElement {});
    // On attend la résolution SANS repasser par `customElements.whenDefined`
    // ici : cet appel est lui-même intercepté par l'espion, il fausserait
    // le compte ci-dessous. `isDefined(nom)` est déjà vrai juste après
    // `define()` (synchrone), donc on ne peut pas s'en servir comme
    // condition d'arrêt ; on vide plutôt une poignée de microtasks à
    // l'aveugle pour laisser le `.then()` interne du module s'exécuter.
    for (let tour = 0; tour < 5; tour += 1) await Promise.resolve();
    for (const rappel of [a, b, c]) expect(rappel).toHaveBeenCalledTimes(1);
  });

  it('purge la table d’attente après résolution', async () => {
    // `whenDefined` court-circuite sur `isDefined` dès que l'élément existe
    // (couvert ailleurs) : appeler `whenDefined` APRÈS résolution ne prouve
    // donc rien sur la purge, cette voie ne touche jamais `abonnes`. Seul
    // `pendingCountForTests` (une fenêtre réservée aux tests sur l'état
    // interne) observe réellement si l'entrée a été retirée.
    const nom = `ha-card-purge-${Math.random().toString(36).slice(2)}`;
    whenDefined(nom, vi.fn());
    whenDefined(nom, vi.fn());
    whenDefined(nom, vi.fn());
    // Trois abonnés sur le MÊME nom : une seule entrée dans la table.
    expect(pendingCountForTests()).toBe(1);

    customElements.define(nom, class extends HTMLElement {});
    for (let tour = 0; tour < 5; tour += 1) await Promise.resolve();

    expect(pendingCountForTests()).toBe(0);
  });

  it('ne rappelle plus un abonné qui s’est désabonné', async () => {
    // La tablette cuisine ouvre /home-stock directement : ha-svg-icon ne s'y
    // charge JAMAIS. Chaque montage/démontage d'icône doit donc pouvoir se
    // retirer de la file d'attente, sinon elle grossit sans fin sur ce
    // kiosque qui tourne en continu.
    const nom = `ha-card-desabonne-${Math.random().toString(36).slice(2)}`;
    const rappel = vi.fn();
    const seDesabonner = whenDefined(nom, rappel);
    seDesabonner();

    customElements.define(nom, class extends HTMLElement {});
    for (let tour = 0; tour < 5; tour += 1) await Promise.resolve();

    expect(rappel).not.toHaveBeenCalled();
  });

  it('ne laisse pas d’entrée morte quand le dernier abonné d’un nom se désabonne', () => {
    const nom = `ha-card-derniere-entree-${Math.random().toString(36).slice(2)}`;
    const seDesabonnerA = whenDefined(nom, vi.fn());
    const seDesabonnerB = whenDefined(nom, vi.fn());
    expect(pendingCountForTests()).toBe(1);

    seDesabonnerA();
    expect(pendingCountForTests()).toBe(1); // B reste abonné : l'entrée doit rester.

    seDesabonnerB();
    expect(pendingCountForTests()).toBe(0); // Plus aucun abonné : rien ne doit rester.
  });

  it('appelle loadCardHelpers une seule fois, et survit à son absence', () => {
    const loadCardHelpers = vi.fn().mockResolvedValue({});
    const fenetre = { loadCardHelpers } as unknown as Window;
    primeHaComponents(fenetre);
    primeHaComponents(fenetre);
    expect(loadCardHelpers).toHaveBeenCalledTimes(1);

    resetForTests();
    // Une fenêtre SANS loadCardHelpers : c'est le cas de la tablette qui
    // ouvre /home-stock directement. Ne doit pas lever.
    expect(() => primeHaComponents({} as unknown as Window)).not.toThrow();
  });

  it('survit à un rejet asynchrone de loadCardHelpers', async () => {
    // Le chunk Lovelace peut échouer à se charger (réseau, cache…) : le
    // rejet doit être avalé, pas remonter en rejet non intercepté.
    const loadCardHelpers = vi.fn().mockRejectedValue(new Error('chunk indisponible'));
    const fenetre = { loadCardHelpers } as unknown as Window;
    expect(() => primeHaComponents(fenetre)).not.toThrow();
    // Laisse le rejet se propager jusqu'au `.catch` du module ; si celui-ci
    // manquait, vitest signalerait un rejet non intercepté sur ce test.
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(loadCardHelpers).toHaveBeenCalledTimes(1);
  });

  it('survit à un jet SYNCHRONE de loadCardHelpers', () => {
    // `loadCardHelpers` est fourni par un chunk tiers : rien ne garantit
    // qu'il renvoie toujours une promesse. S'il lève avant même de créer
    // cette promesse, ça doit rester un cas « pas de Lovelace », pas une
    // exception qui remonte.
    const loadCardHelpers = vi.fn(() => {
      throw new Error('chunk cassé');
    });
    const fenetre = { loadCardHelpers } as unknown as Window;
    expect(() => primeHaComponents(fenetre)).not.toThrow();
    expect(loadCardHelpers).toHaveBeenCalledTimes(1);
  });
});
