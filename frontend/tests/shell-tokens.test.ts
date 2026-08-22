import { describe, expect, it } from 'vitest';
import { tokens } from '../src/shell/ui/tokens';

/** Le texte CSS brut de la feuille — c'est tout ce que jsdom permet
 *  d'inspecter : il ne calcule aucune mise en page et n'applique pas les
 *  feuilles adoptées d'un shadow root. Les vraies mesures sont le travail de
 *  `outils/verifier-rendu.mjs`. */
const css = tokens.cssText;

describe('jetons partagés', () => {
  it('définit chaque jeton documenté dans la spec', () => {
    for (const jeton of [
      '--hs-space-1', '--hs-space-2', '--hs-space-3', '--hs-space-4',
      '--hs-space-5', '--hs-space-6',
      '--hs-radius-s', '--hs-radius-m', '--hs-radius-l',
      '--hs-text', '--hs-text-2', '--hs-surface', '--hs-surface-2',
      '--hs-divider', '--hs-accent', '--hs-on-accent',
      '--hs-danger', '--hs-on-danger', '--hs-warning', '--hs-on-warning',
      '--hs-font', '--hs-touch',
    ]) {
      expect(css).toContain(`${jeton}:`);
    }
  });

  it('donne un repli à CHAQUE variable Home Assistant lue', () => {
    // C'est l'absence de repli qui a rendu invalides les bordures du Planning
    // sous un thème incomplet : `var(--divider-color)` sans repli annule la
    // déclaration entière à la valeur calculée.
    // Seules les variables HOME ASSISTANT sont visées : les jetons --hs-* sont
    // définis dans ce même bloc `:host`, ils résolvent toujours, et leur donner
    // un repli créerait une seconde source de vérité.
    const sansRepli = [...css.matchAll(/var\((--(?!hs-)[a-z-]+)\s*\)/g)].map((m) => m[1]);
    expect(sansRepli).toEqual([]);
  });

  it('impose la cible tactile de la tablette cuisine', () => {
    expect(css).toContain('--hs-touch: 62px');
  });

  it('ne pose de couleur littérale QUE sur les trois jetons recalculés', () => {
    // Les --hs-on-* n'ont pas de variable de thème correcte (§ 6.1 bis) : ils
    // portent un défaut prudent que `on-color.ts` remplace au montage. Partout
    // ailleurs, une couleur littérale est une couleur qui ignore le thème.
    const sansVar = css.replace(/var\([^)]*\)/g, '');
    const litteraux = [...sansVar.matchAll(/(--[a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{3,8}|rgba?\([^)]*\))/g)];
    expect(litteraux.map((m) => m[1]).sort())
      .toEqual(['--hs-on-accent', '--hs-on-danger', '--hs-on-warning']);
    // Et ce défaut est le SOMBRE : sur une couleur de marque inconnue, le
    // sombre est le pari le moins risqué (la plupart des primaires de thème
    // sont des teintes moyennes à vives, où le blanc échoue).
    for (const m of litteraux) expect(m[2]).toBe('#141414');
  });
});
