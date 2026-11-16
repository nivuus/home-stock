/** Text folding for search, the same as the server's `domain/textfold.fold`.
 *
 *  One folding for every search of the panel, so that what the server finds
 *  and what a screen filters locally agree. The steps mirror the server:
 *  expand the œ/æ ligatures, apply Unicode full case folding (Python's
 *  `str.casefold`: "ß" → "ss", final sigma → σ), decompose, drop combining
 *  marks only when they sit on a Latin letter (an accent there is a variant of
 *  the letter; in Japanese, Devanagari, Thai or Cyrillic it is part of it),
 *  and recompose. `tests/fixtures/text_folding.json` holds both sides to it.
 *
 *  JavaScript has no case folding of its own (`toLowerCase` keeps "ß"), hence
 *  `unicode-case-folding`, generated from the Unicode Character Database. */
import { caseFold } from 'unicode-case-folding';

const LIGATURES: ReadonlyArray<[RegExp, string]> = [
  [/œ/g, 'oe'], [/æ/g, 'ae'], [/Œ/g, 'OE'], [/Æ/g, 'AE'],
];
const LATIN = /\p{Script=Latin}/u;
const MARK = /\p{M}/u;

export function foldText(text: string): string {
  let expanded = text;
  for (const [ligature, replacement] of LIGATURES) expanded = expanded.replace(ligature, replacement);
  let kept = '';
  let base = '';
  for (const char of caseFold(expanded).normalize('NFD')) {
    if (MARK.test(char)) {
      if (LATIN.test(base)) continue;
    } else {
      base = char;
    }
    kept += char;
  }
  return kept.normalize('NFC');
}

/** Whether `query` occurs in `text`, both folded. An empty query matches. */
export function matchesSearch(text: string, query: string): boolean {
  const needle = foldText(query.trim());
  return needle === '' || foldText(text).includes(needle);
}
