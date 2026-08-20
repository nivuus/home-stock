import { describe, expect, it } from 'vitest';
import { raccourcisQuantite } from '../src/portion';

describe('raccourcisQuantite', () => {
  it('arme « 1 » pour un produit à la pièce', () => {
    const raccourcis = raccourcisQuantite(3, 'piece', null);
    expect(raccourcis[0]).toEqual({ libelle: '1 pièce', quantite: 1 });
  });

  it('ne propose jamais plus que ce qui reste', () => {
    const raccourcis = raccourcisQuantite(1, 'piece', null);
    expect(raccourcis.every((r) => r.quantite <= 1)).toBe(true);
  });

  it('propose la portion apprise en tête quand elle existe', () => {
    const [premier] = raccourcisQuantite(500, 'g', 125);
    expect(premier).toEqual({ libelle: '1 portion (125 g)', quantite: 125 });
  });

  it('n’invente pas de portion quand on n’en connaît aucune', () => {
    const libelles = raccourcisQuantite(500, 'g', null).map((r) => r.libelle);
    expect(libelles).toEqual(['La moitié (250 g)', 'Tout le reste (500 g)']);
  });

  it('n’affiche pas deux boutons identiques', () => {
    // Une portion qui vaut exactement la moitié du reste.
    const raccourcis = raccourcisQuantite(250, 'g', 125);
    const quantites = raccourcis.map((r) => r.quantite);
    expect(new Set(quantites).size).toBe(quantites.length);
  });

  it('écarte une portion plus grosse que ce qui reste', () => {
    const libelles = raccourcisQuantite(100, 'g', 125).map((r) => r.libelle);
    expect(libelles.some((l) => l.startsWith('1 portion'))).toBe(false);
  });

  it('affiche les millilitres et les litres comme le reste du panneau', () => {
    const [, dernier] = raccourcisQuantite(1500, 'ml', null);
    expect(dernier.libelle).toBe('Tout le reste (1,5 l)');
  });

  it('rend une liste vide quand il ne reste rien', () => {
    expect(raccourcisQuantite(0, 'g', 125)).toEqual([]);
  });
});
