import { describe, expect, it } from 'vitest';
import { formatMoney } from '../src/money';

// Intl separates with no-break spaces; compare on plain spaces.
const plain = (text: string) => text.replace(/[\u00a0\u202f]/g, ' ');

describe('formatMoney', () => {
  it.each([
    [12.3, 'fr', 'EUR', '12,30 €'],
    [1234.5, 'de', 'EUR', '1.234,50 €'],
    [3.5, 'en-US', 'USD', '$3.50'],
    [1200, 'ja', 'JPY', '￥1,200'],
    [1.5, 'ar-KW', 'KWD', null],
  ])('%d in %s / %s', (value, locale, currency, expected) => {
    const text = plain(formatMoney(value, { locale, currency }));
    if (expected !== null) expect(text).toBe(expected);
    else expect(text).toMatch(/[٠-٩0-9]/);
  });

  it('never writes a currency the household does not use', () => {
    expect(formatMoney(3, { locale: 'fr', currency: 'JPY' })).not.toContain('€');
  });
});
