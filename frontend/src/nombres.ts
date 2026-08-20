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
