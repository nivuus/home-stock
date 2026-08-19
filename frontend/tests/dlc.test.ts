import { describe, expect, it } from 'vitest';
import { raccourcisDlc } from '../src/dlc';

const LE_19_AOUT = new Date('2026-08-19T10:00:00Z');

describe('raccourcis de date de péremption', () => {
  it('propose la durée apprise en premier quand elle existe', () => {
    const [premier] = raccourcisDlc(LE_19_AOUT, 5);
    expect(premier.date).toBe('2026-08-24');
    expect(premier.libelle).toContain('5');
  });

  it('propose trois durées génériques quand rien n’a été appris', () => {
    const dates = raccourcisDlc(LE_19_AOUT, null).map((r) => r.date);
    expect(dates).toEqual(['2026-08-22', '2026-08-26', '2026-09-19', null]);
  });

  it('offre toujours « sans DLC »', () => {
    for (const duree of [null, 3, 400]) {
      expect(raccourcisDlc(LE_19_AOUT, duree).some((r) => r.date === null)).toBe(true);
    }
  });

  it('ne propose jamais deux fois la même date', () => {
    // Une durée apprise de 7 jours coïncide avec « +1 semaine » : un bouton en double
    // fait hésiter pour rien.
    const dates = raccourcisDlc(LE_19_AOUT, 7).map((r) => r.date);
    expect(new Set(dates).size).toBe(dates.length);
  });

  it('rend une date ISO, jamais un horodatage', () => {
    for (const raccourci of raccourcisDlc(LE_19_AOUT, 5)) {
      if (raccourci.date) expect(raccourci.date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    }
  });
});
