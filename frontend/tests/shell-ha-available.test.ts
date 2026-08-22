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

  it('n’abonne qu’une fois par élément, même avec plusieurs instances', async () => {
    const nom = `ha-card-partage-${Math.random().toString(36).slice(2)}`;
    const a = vi.fn();
    const b = vi.fn();
    whenDefined(nom, a);
    whenDefined(nom, b);
    customElements.define(nom, class extends HTMLElement {});
    await customElements.whenDefined(nom);
    await Promise.resolve();
    expect(a).toHaveBeenCalledTimes(1);
    expect(b).toHaveBeenCalledTimes(1);
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
});
