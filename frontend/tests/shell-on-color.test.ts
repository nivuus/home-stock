import { describe, expect, it } from 'vitest';
import { meilleureCouleurDeTexte, parseRgb } from '../src/shell/ui/on-color';

describe('analyse d’une couleur résolue', () => {
  it('lit les formes que rend getComputedStyle', () => {
    expect(parseRgb('rgb(0, 154, 199)')).toEqual([0, 154, 199]);
    expect(parseRgb('rgba(238, 147, 0, 1)')).toEqual([238, 147, 0]);
    expect(parseRgb('  rgb(19,21,54)  ')).toEqual([19, 21, 54]);
  });

  it('rend null sur ce qu’elle ne sait pas lire', () => {
    // jsdom ne résout pas var() et rend '' : le module doit alors garder le
    // défaut du jeton plutôt que poser une couleur au hasard.
    expect(parseRgb('')).toBeNull();
    expect(parseRgb('var(--primary-color)')).toBeNull();
    expect(parseRgb('transparent')).toBeNull();
  });
});

describe('choix de la couleur de texte', () => {
  it('choisit le sombre sur le cyan du thème HA par défaut', () => {
    // Le cas qui motive tout ce module : HA associe du BLANC à cette
    // primaire, et blanc sur #009ac7 ne fait que 3,26:1.
    expect(meilleureCouleurDeTexte([0, 154, 199])).toBe('#141414');
  });

  it('choisit le sombre sur l’orange de Graphite', () => {
    expect(meilleureCouleurDeTexte([238, 147, 0])).toBe('#141414');
  });

  it('choisit le clair sur un fond franchement sombre', () => {
    expect(meilleureCouleurDeTexte([20, 20, 20])).toBe('#ffffff');
  });

  it('choisit toujours celle des deux qui contraste le mieux', () => {
    // Propriété, pas cas particulier : sur cent teintes, la couleur rendue
    // doit toujours être la meilleure des deux candidates.
    for (let i = 0; i < 100; i += 1) {
      const fond: [number, number, number] = [(i * 37) % 256, (i * 91) % 256, (i * 53) % 256];
      const choisie = meilleureCouleurDeTexte(fond);
      const autre = choisie === '#ffffff' ? '#141414' : '#ffffff';
      expect(contraste(fond, parseRgb(choisie)!))
        .toBeGreaterThanOrEqual(contraste(fond, parseRgb(autre)!));
    }
  });
});

/** Recalculé ici plutôt qu'importé : un test qui réutiliserait la fonction
 *  testée pour se vérifier lui-même ne prouverait rien. */
function contraste(a: [number, number, number], b: [number, number, number]): number {
  const l = (c: [number, number, number]) => {
    const v = c.map((x) => x / 255).map((u) => (u <= 0.03928 ? u / 12.92 : ((u + 0.055) / 1.055) ** 2.4));
    return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2];
  };
  const [clair, sombre] = l(a) > l(b) ? [l(a), l(b)] : [l(b), l(a)];
  return (clair + 0.05) / (sombre + 0.05);
}
