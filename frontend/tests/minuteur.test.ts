import { describe, expect, it } from 'vitest';
import {
  avancer, demarrer, formaterDuree, mettreEnPause, remettreAZero, reprendre,
} from '../src/minuteur';

describe('minuteur', () => {
  it('décompte sans jamais passer sous zéro', () => {
    let etat = demarrer(10);
    etat = avancer(etat, 4);
    expect(etat.restant).toBe(6);
    etat = avancer(etat, 600);
    expect(etat.restant).toBe(0);
  });

  it('se déclare terminé exactement à zéro', () => {
    let etat = demarrer(5);
    etat = avancer(etat, 4);
    expect(etat.termine).toBe(false);
    etat = avancer(etat, 1);
    expect(etat.termine).toBe(true);
    expect(etat.enMarche).toBe(false);
  });

  it('une fois terminé, reste terminé', () => {
    // Repartir demande un geste explicite, pas un tour d'horloge de plus.
    let etat = avancer(demarrer(1), 1);
    etat = avancer(etat, 10);
    expect(etat.termine).toBe(true);
    expect(etat.restant).toBe(0);
  });

  it('remis à zéro, il repart de la durée d’origine et n’est pas en marche', () => {
    let etat = demarrer(600);
    etat = avancer(etat, 300);
    etat = remettreAZero(etat.duree);
    expect(etat.restant).toBe(600);
    expect(etat.enMarche).toBe(false);
    expect(etat.termine).toBe(false);
  });

  it('en pause, il ne décompte plus', () => {
    let etat = mettreEnPause(avancer(demarrer(60), 10));
    etat = avancer(etat, 30);
    expect(etat.restant).toBe(50);
    etat = avancer(reprendre(etat), 30);
    expect(etat.restant).toBe(20);
  });

  it('reprendre un minuteur terminé ne le relance pas', () => {
    const etat = reprendre(avancer(demarrer(1), 1));
    expect(etat.enMarche).toBe(false);
  });

  it.each([[90, '1:30'], [3661, '1:01:01'], [0, '0:00'], [59, '0:59'],
           [600, '10:00'], [3600, '1:00:00']])(
    'formate %s secondes en %s', (secondes, attendu) => {
      expect(formaterDuree(secondes as number)).toBe(attendu);
    });

  it('n’affiche l’heure que si elle existe', () => {
    // « 0:12:30 » pour douze minutes ferait lire une heure là où il n'y en a pas.
    expect(formaterDuree(750)).toBe('12:30');
  });

  it('ne dépend d’aucune horloge globale', () => {
    // Deux décomptes identiques à des « instants » différents doivent donner
    // exactement le même état : le module reçoit le temps, il ne le lit pas.
    const a = avancer(demarrer(60, 0), 15);
    const b = avancer(demarrer(60, 1_000_000), 15);
    expect(a).toEqual(b);
  });
});
