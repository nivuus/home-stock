import { afterEach, describe, expect, it, vi } from 'vitest';
import { isDefined, primeHaComponents, resetForTests, whenDefined }
  from '../src/shell/ui/ha-available';

afterEach(() => {
  resetForTests();
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

    const appelsAvantTardif = espion.mock.calls.filter(([n]) => n === nom).length;
    // La table interne doit être purgée après résolution : un nouvel
    // abonnement sur ce nom ne doit plus rien y ajouter — `isDefined`
    // répond déjà vrai, donc `whenDefined` sort tout de suite (l'appelant
    // sait déjà qu'il peut rendre l'élément réel, il n'a pas besoin d'un
    // rappel). Ni rappel, ni nouvelle promesse native.
    const tardif = vi.fn();
    whenDefined(nom, tardif);
    expect(tardif).not.toHaveBeenCalled();
    expect(espion.mock.calls.filter(([n]) => n === nom)).toHaveLength(appelsAvantTardif);

    espion.mockRestore();
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
