/** Amounts of money, in the household's currency and the person's locale.
 *
 *  Both come from Home Assistant: `hass.config.currency` (ISO 4217, set in
 *  General settings) and `hass.locale.language` (the profile's language).
 *  `Intl.NumberFormat` then places the symbol, the separators and the number
 *  of decimals (two for EUR, none for JPY, three for KWD). */
export type MoneyFormat = { locale: string; currency: string };

const formatters = new Map<string, Intl.NumberFormat>();

export function formatMoney(value: number, format: MoneyFormat): string {
  const key = `${format.locale}|${format.currency}`;
  let formatter = formatters.get(key);
  if (!formatter) {
    formatter = new Intl.NumberFormat(format.locale, { style: 'currency', currency: format.currency });
    formatters.set(key, formatter);
  }
  return formatter.format(value);
}
