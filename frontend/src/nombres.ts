/** Lecture des nombres saisis à la main, et leur affichage en français. */

export type ResultatNombre = { ok: true; valeur: number | null } | { ok: false };

/** Un champ numérique saisi à la main peut être vide (effacé exprès →
 *  `null`), un nombre valide, ou du texte qui n'en est pas — jamais un
 *  `NaN` silencieux : `Number('1,5')` vaut `NaN`, `NaN !== ancienneValeur`
 *  est toujours vrai, et `JSON.stringify(NaN)` vaut `'null'`. Un incident
 *  réel a montré qu'une simple virgule décimale suffisait ainsi à effacer
 *  un seuil de réapprovisionnement en silence tout en laissant croire à un
 *  enregistrement réussi. Accepte donc la virgule comme le point ; refuse
 *  explicitement (`{ok:false}`) tout le reste plutôt que de deviner un
 *  nombre dans du texte (« 7 jours » n'est pas 7). */
export function analyserNombre(saisie: string): ResultatNombre {
  const texte = saisie.trim();
  if (texte === '') return { ok: true, valeur: null };
  const nombre = Number(texte.replace(',', '.'));
  if (!Number.isFinite(nombre)) return { ok: false };
  return { ok: true, valeur: nombre };
}

/** Un nombre tel qu'on l'écrit en français, sans zéro décimal inutile. */
export function formaterNombre(valeur: number): string {
  return (Math.round(valeur * 100) / 100).toString().replace('.', ',');
}

/** Les fractions qu'on écrit vraiment en cuisine, et rien d'autre.
 *
 *  Volontairement court : on veut « ½ » et « ¾ », pas une bibliothèque de
 *  rationnels. Ce qui ne tombe pas sur l'une de ces cinq valeurs se lit
 *  simplement à la virgule. */
const FRACTIONS: ReadonlyArray<readonly [number, string]> = [
  [1 / 4, '¼'], [1 / 3, '⅓'], [1 / 2, '½'], [2 / 3, '⅔'], [3 / 4, '¾'],
];

/** La tolérance de reconnaissance d'une fraction. `1/3` vaut 0,3333… en
 *  binaire : comparer à l'égalité stricte ne reconnaîtrait jamais un tiers,
 *  et une tolérance trop large ferait passer 0,4 pour un tiers. */
const TOLERANCE = 0.005;

/** Un nombre écrit comme on le dit : « ½ », « 1 ½ », « 2 ».
 *
 *  Grocy affichait « ½ » et le stockait tel quel. Ici `amount` vaut `0.5` en
 *  base et c'est le RENDU qui écrit la fraction : un seul nombre stocké,
 *  plusieurs façons de le lire. */
export function formaterFraction(valeur: number): string {
  const entier = Math.floor(valeur);
  const reste = valeur - entier;
  if (reste < TOLERANCE) return String(entier);
  for (const [fraction, glyphe] of FRACTIONS) {
    if (Math.abs(reste - fraction) < TOLERANCE) {
      return entier === 0 ? glyphe : `${entier} ${glyphe}`;
    }
  }
  return formaterNombre(valeur);
}

/** Le pluriel français d'une mesure ou d'un conditionnement, à partir de deux.
 *
 *  Le `s` va sur le NOM DE TÊTE : deux valent « cuillères à soupe », jamais
 *  « cuillère à soupes ». Même règle que côté Python (`domain/recipes.py`). */
function pluriel(nom: string, quantite: number): string {
  if (quantite < 2) return nom;
  const [tete, ...suite] = nom.split(' ');
  const accorde = tete.endsWith('s') ? tete : `${tete}s`;
  return [accorde, ...suite].join(' ');
}

const UNITE_LISIBLE: Record<string, string> = { g: 'g', ml: 'ml', piece: '' };

/** La quantité d'une ligne de recette, telle qu'on la lit.
 *
 *  Une quantité inconnue rend une chaîne VIDE, jamais « 0 » : `null` veut dire
 *  inconnu, et afficher zéro affirmerait qu'il n'en faut pas.
 *
 *  Les fractions ne servent QUE pour un produit suivi à la pièce. Personne ne
 *  dit « ½ cuillère à soupe d'huile » en cuisine, et « ½ g » serait ridicule :
 *  une demi-cuillère s'écrit « 0,5 cuillère à soupe ». */
export function formaterQuantiteRecette(
  quantite: number | null,
  unite: 'g' | 'ml' | 'piece',
  mesure: string | null,
  conditionnement: string | null,
): string {
  if (quantite === null) return '';
  const nom = conditionnement ?? mesure;
  if (nom) return `${formaterNombre(quantite)} ${pluriel(nom, quantite)}`;
  if (unite === 'piece') return formaterFraction(quantite);
  return `${formaterNombre(quantite)} ${UNITE_LISIBLE[unite]}`.trim();
}
