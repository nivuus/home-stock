import { describe, expect, it } from 'vitest';
import { foldText, matchesSearch } from '../src/fold';
// The table the server's test reads too (tests/test_text_folding_contract.py).
import table from '../../tests/fixtures/text_folding.json';

describe('foldText', () => {
  it.each(table.cases)('folds $text as the server does', ({ text, folded }) => {
    expect(foldText(text)).toBe(folded);
  });
});

describe('matchesSearch', () => {
  it.each([
    ['Œufs', 'oeufs'],
    ['Crème fraîche', 'creme'],
    ['Straße', 'strasse'],
    ['ΣΊΣΥΦΟΣ', 'σίσυφος'],
    ['ЁЛКА', 'ёлка'],
    ['ガス', 'ガス'],
    ['عَسَل', 'عَسَل'],
    ['İstanbul', 'istanbul'],
  ])('%s is found by %s', (text, query) => {
    expect(matchesSearch(text, query)).toBe(true);
  });

  it.each([
    ['カス', 'ガス'],       // the dakuten makes another word
    ['Йогурт', 'иогурт'],  // й and и are two letters
    ['हिंदी', 'हिदी'],       // the anusvara is part of the word
  ])('%s is NOT found by %s', (text, query) => {
    expect(matchesSearch(text, query)).toBe(false);
  });

  it('an empty query matches everything', () => {
    expect(matchesSearch('Lait', '  ')).toBe(true);
  });
});
