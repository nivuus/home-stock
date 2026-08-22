import { describe, expect, it } from 'vitest';
import { DEFAULT_PATH, parsePath, pathOf } from '../src/shell/router';
import { DESTINATIONS } from '../src/shell/destinations';

describe('routeur', () => {
  it('lit un segment simple', () => {
    expect(parsePath('/list')).toEqual({ screen: 'liste', param: null });
    expect(parsePath('/catalog')).toEqual({ screen: 'catalogue', param: null });
  });

  it('lit un segment paramétré', () => {
    expect(parsePath('/recipe/12')).toEqual({ screen: 'recette', param: '12' });
    expect(parsePath('/item/3229820129488'))
      .toEqual({ screen: 'fiche', param: '3229820129488' });
  });

  it('tolère la barre finale et la barre initiale absente', () => {
    expect(parsePath('list')).toEqual({ screen: 'liste', param: null });
    expect(parsePath('/list/')).toEqual({ screen: 'liste', param: null });
  });

  it('rend null sur une route inconnue, ou sur un paramètre manquant', () => {
    expect(parsePath('/nawak')).toBeNull();
    expect(parsePath('')).toBeNull();
    // `recipe` SANS identifiant n'a pas d'écran à montrer : l'écran recette
    // exige un `recipeId`. Mieux vaut retomber sur la racine que rendre du vide.
    expect(parsePath('/recipe')).toBeNull();
  });

  it('ignore un paramètre passé à un écran qui n’en attend pas', () => {
    expect(parsePath('/list/42')).toEqual({ screen: 'liste', param: null });
  });

  it('fabrique le chemin d’un écran', () => {
    expect(pathOf('liste')).toBe('/list');
    expect(pathOf('recette', 12)).toBe('/recipe/12');
    expect(pathOf('fiche', '3229820129488')).toBe('/item/3229820129488');
  });

  it('fait l’aller-retour pour chaque destination de la table', () => {
    for (const d of DESTINATIONS) {
      const chemin = pathOf(d.screen, d.param ? '7' : null);
      expect(parsePath(chemin)).toEqual({ screen: d.screen, param: d.param ? '7' : null });
    }
  });

  it('sait où retomber', () => {
    expect(DEFAULT_PATH).toBe('/list');
    expect(parsePath(DEFAULT_PATH)).toEqual({ screen: 'liste', param: null });
  });
});
