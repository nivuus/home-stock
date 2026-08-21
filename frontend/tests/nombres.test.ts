import { describe, expect, it } from 'vitest';
import { formaterFraction, formaterQuantiteRecette } from '../src/nombres';

describe('formaterFraction', () => {
  it.each([[0.5, '½'], [0.25, '¼'], [0.75, '¾'], [1 / 3, '⅓'], [2 / 3, '⅔']])(
    'écrit %s en fraction', (valeur, attendu) => {
      expect(formaterFraction(valeur as number)).toBe(attendu);
    });

  it('laisse un entier tel quel', () => {
    expect(formaterFraction(2)).toBe('2');
    expect(formaterFraction(0)).toBe('0');
  });

  it('écrit 1,5 en « 1 ½ »', () => {
    expect(formaterFraction(1.5)).toBe('1 ½');
    expect(formaterFraction(2.25)).toBe('2 ¼');
  });

  it('replie sur la virgule quand aucune fraction ne colle', () => {
    expect(formaterFraction(0.4)).toBe('0,4');
    expect(formaterFraction(1.7)).toBe('1,7');
  });

  it('reconnaît un tiers malgré le binaire', () => {
    // 1/3 vaut 0,3333… : une égalité stricte ne le reconnaîtrait jamais.
    expect(formaterFraction(0.333)).toBe('⅓');
    expect(formaterFraction(0.3333333333)).toBe('⅓');
  });
});

describe('formaterQuantiteRecette', () => {
  it('n’écrit jamais « 0 » pour une quantité inconnue', () => {
    // `null` veut dire inconnu ; afficher zéro affirmerait qu'il n'en faut pas.
    expect(formaterQuantiteRecette(null, 'g', null, null)).toBe('');
    expect(formaterQuantiteRecette(null, 'piece', null, 'oignon')).toBe('');
  });

  it('n’utilise les fractions que pour les pièces', () => {
    expect(formaterQuantiteRecette(0.5, 'piece', null, null)).toBe('½');
    expect(formaterQuantiteRecette(0.5, 'g', null, null)).toBe('0,5 g');
    expect(formaterQuantiteRecette(0.5, 'ml', null, null)).toBe('0,5 ml');
  });

  it('écrit une demi-cuillère en toutes lettres, pas en fraction', () => {
    // Personne ne dit « ½ cuillère à soupe d'huile » en cuisine.
    expect(formaterQuantiteRecette(0.5, 'ml', 'cuillère à soupe', null))
      .toBe('0,5 cuillère à soupe');
  });

  it('accorde le pluriel de la mesure sur le nom de tête', () => {
    expect(formaterQuantiteRecette(2, 'ml', 'cuillère à soupe', null))
      .toBe('2 cuillères à soupe');
    expect(formaterQuantiteRecette(1, 'ml', 'cuillère à soupe', null))
      .toBe('1 cuillère à soupe');
  });

  it('préfère le conditionnement du produit à la mesure', () => {
    expect(formaterQuantiteRecette(2, 'g', 'cuillère à soupe', 'tranche'))
      .toBe('2 tranches');
  });

  it('écrit une masse et un volume avec leur unité', () => {
    expect(formaterQuantiteRecette(150, 'g', null, null)).toBe('150 g');
    expect(formaterQuantiteRecette(20, 'ml', null, null)).toBe('20 ml');
  });
});
