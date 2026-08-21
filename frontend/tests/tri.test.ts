import { describe, expect, it } from 'vitest';
import { consigneDeTri } from '../src/tri';

describe('consigneDeTri', () => {
  it('nomme chaque bac en français', () => {
    expect(consigneDeTri(['yellow'])).toBe('Bac jaune');
    expect(consigneDeTri(['glass'])).toBe('Bac à verre');
    expect(consigneDeTri(['household'])).toBe('Ordures ménagères');
    expect(consigneDeTri(['dropoff'])).toBe('Déchèterie');
  });

  it('joint deux bacs par « et »', () => {
    expect(consigneDeTri(['yellow', 'glass'])).toBe('Bac jaune et bac à verre');
  });

  it('ne répète pas deux fois le même bac', () => {
    expect(consigneDeTri(['yellow', 'yellow'])).toBe('Bac jaune');
  });

  it('ignore un bac inconnu sans perdre les autres', () => {
    expect(consigneDeTri(['martien' as any, 'glass'])).toBe('Bac à verre');
  });

  it('rend null quand il n’y a rien de connu à dire', () => {
    // Rien de connu → rien d'affiché : une consigne inventée enverrait du
    // verre dans le bac jaune avec l'assurance de l'écran.
    expect(consigneDeTri([])).toBeNull();
    expect(consigneDeTri(['martien' as any])).toBeNull();
  });
});
