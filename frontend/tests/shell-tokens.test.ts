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
      '--hs-danger', '--hs-warning', '--hs-on-warning',
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

  it('ne pose aucune couleur littérale hors des replis des deux jetons recalculés', () => {
    // Les --hs-on-* n'ont pas de variable de thème correcte (§ 6.1 bis) : ils
    // portent un repli prudent que `on-color.ts` remplace au montage. Partout
    // ailleurs, une couleur littérale est une couleur qui ignore le thème.
    // Pas de --hs-on-danger : le danger ne se pose jamais en aplat sous du
    // texte (§ 6.1 ter), donc rien ne le lit.
    // On efface d'abord les `var(…)` — c'est-à-dire aussi les replis, qui y
    // sont désormais — puis on exige qu'il ne reste RIEN.
    const sansVar = css.replace(/var\([^)]*\)/g, '');
    const litteraux = [...sansVar.matchAll(/(--[a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{3,8}|rgba?\([^)]*\))/g)];
    expect(litteraux.map((m) => m[1])).toEqual([]);
  });

  it('lit les --hs-on-* PAR INDIRECTION, avec leur repli sombre', () => {
    // Le point de tout le mécanisme, et ce qu'aucun contrôle n'attrapait :
    // cette feuille est adoptée par CHAQUE composant, donc chaque `:host`
    // enfant redéclare ces jetons — un `--hs-on-accent: #141414` littéral y
    // écrase la valeur que `on-color.ts` pose en style inline sur l'hôte, et
    // le calcul n'atteint jamais un seul bouton (sonde du 2026-08-22 sur le
    // bundle déployé : hôte #ff0000, hs-nav-bar #141414).
    // `--hs-computed-on-*` n'est déclaré dans aucun `:host` : l'héritage le
    // traverse. Le repli reste obligatoire — sans lui, jsdom et tout thème où
    // la sonde ne rend rien perdraient la couleur de texte entière.
    for (const jeton of ['accent', 'warning']) {
      expect(css).toContain(`--hs-on-${jeton}: var(--hs-computed-on-${jeton}, #141414)`);
    }
    // Et rien ne redéclare `--hs-computed-on-*` ici : le déclarer dans ce
    // `:host` reproduirait exactement le défaut corrigé.
    expect(css).not.toMatch(/--hs-computed-on-[a-z]+\s*:/);
  });
});
