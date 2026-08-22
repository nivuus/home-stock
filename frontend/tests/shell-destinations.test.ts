import { describe, expect, it } from 'vitest';
import { DESTINATIONS, FAMILIES, destinationOf, familyOf, familyScreens }
  from '../src/shell/destinations';
import type { Ecran } from '../src/panneau';

const TOUS_LES_ECRANS: Ecran[] = ['scanner', 'fiche', 'panier', 'rangement', 'session',
  'catalogue', 'reglages', 'consommation', 'journal', 'recettes', 'recette',
  'planning', 'validation', 'piles', 'equipements', 'liste', 'ticket'];

describe('table des destinations', () => {
  it('couvre les dix-sept écrans, sans trou ni doublon', () => {
    const declares = DESTINATIONS.map((d) => d.screen).sort();
    expect(declares).toEqual([...TOUS_LES_ECRANS].sort());
  });

  it('donne un segment d’URL unique à chaque écran', () => {
    const segments = DESTINATIONS.map((d) => d.segment);
    expect(new Set(segments).size).toBe(segments.length);
  });

  it('n’emploie que des segments anglais en minuscules', () => {
    for (const d of DESTINATIONS) expect(d.segment).toMatch(/^[a-z][a-z-]*$/);
  });

  it('déclare exactement quatre familles, chacune avec une racine', () => {
    expect(FAMILIES).toHaveLength(4);
    for (const famille of FAMILIES) {
      const racines = DESTINATIONS.filter((d) => d.family === famille.id && d.root);
      expect(racines).toHaveLength(1);
      expect(racines[0].screen).toBe(famille.root);
    }
  });

  it('place les racines là où la spec les met', () => {
    expect(FAMILIES.map((f) => f.root)).toEqual(['liste', 'catalogue', 'planning', 'piles']);
  });

  it('rattache chaque écran à sa famille', () => {
    expect(familyOf('ticket')).toBe('shopping');
    expect(familyOf('journal')).toBe('stock');
    expect(familyOf('recette')).toBe('kitchen');
    expect(familyOf('reglages')).toBe('house');
  });

  it('garde un libellé français pour l’utilisateur', () => {
    expect(destinationOf('liste').label).toBe('Liste de courses');
    expect(destinationOf('rangement').label).toBe('Rangement');
  });
});

describe('sous-navigation de famille', () => {
  it('donne les écrans atteignables de chaque famille, dans l’ordre', () => {
    expect(familyScreens('shopping').map((d) => d.screen))
      .toEqual(['liste', 'session', 'panier', 'rangement', 'scanner']);
    expect(familyScreens('stock').map((d) => d.screen)).toEqual(['catalogue', 'journal']);
    expect(familyScreens('kitchen').map((d) => d.screen)).toEqual(['planning', 'recettes']);
    expect(familyScreens('house').map((d) => d.screen))
      .toEqual(['piles', 'equipements', 'reglages']);
  });

  it('exclut les écrans qui exigent un paramètre', () => {
    // fiche, recette, validation, ticket, manger : un bouton nu ne saurait pas
    // quel identifiant leur passer. On y entre depuis l'écran qui le connaît.
    for (const famille of FAMILIES) {
      for (const d of familyScreens(famille.id)) expect(d.param).toBeUndefined();
    }
  });

  it('couvre TOUT écran sans paramètre — aucun ne doit rester inatteignable', () => {
    // C'est le test qui interdit la régression : la barre de dix boutons
    // exposait les dix-sept écrans, les quatre familles n'exposaient que leurs
    // racines, et six écrans étaient devenus introuvables autrement que par
    // leur URL.
    const dansLaNav = FAMILIES.flatMap((f) => familyScreens(f.id).map((d) => d.screen));
    const sansParametre = DESTINATIONS.filter((d) => !d.param).map((d) => d.screen);
    expect([...dansLaNav].sort()).toEqual([...sansParametre].sort());
  });
});
