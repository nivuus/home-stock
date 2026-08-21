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

describe('raccourcisQuantite — d’où vient la portion', () => {
  it('dit « Ma portion » quand la valeur a été saisie', () => {
    const [premier] = raccourcisQuantite(500, 'g', 45, 'manual');
    expect(premier.libelle).toBe('Ma portion (45 g)');
  });

  it('dit « 1 portion » pour une valeur déduite, ou sans source', () => {
    for (const source of ['learned', 'serving', null] as const) {
      const [premier] = raccourcisQuantite(500, 'g', 45, source);
      expect(premier.libelle).toBe('1 portion (45 g)');
    }
    // Argument omis : les appels existants restent valides.
    expect(raccourcisQuantite(500, 'g', 45)[0].libelle).toBe('1 portion (45 g)');
  });

  it('ne change pas le libellé à la pièce, où une portion vaut une pièce', () => {
    const [premier] = raccourcisQuantite(4, 'piece', 45, 'manual');
    expect(premier.libelle).toBe('1 pièce');
  });
});
