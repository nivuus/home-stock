/** Sonder une feuille de style d'un composant Lit, sans se mentir.
 *
 *  Le piège que ce module supprime : `expect(feuille).toContain('min-height:
 *  var(--hs-touch)')` cherche la déclaration N'IMPORTE OÙ dans la feuille
 *  concaténée. Une seule autre règle qui la porte — et il y en a toujours une
 *  — suffit à garder le test vert pendant que le bouton visé retombe à 20 px.
 *  Sonde du 2026-08-22 : cinq tests de cible tactile réduits à `min-height:
 *  20px` sur leur bouton restaient tous verts.
 *
 *  La parade est celle que `tests/catalogue.test.ts` et
 *  `tests/shell-enveloppes.test.ts` emploient déjà : ISOLER la règle avant de
 *  la sonder. Ici, en tenant compte des listes de sélecteurs
 *  (`.valider-repas, .annuler-repas { … }`), que ces regex écrites à la main
 *  ratent une fois sur deux.
 */

/** La feuille d'un composant, concaténée. `static styles` est un tableau
 *  `[tokens, css\`…\`]` depuis la Task 6 : il n'y a pas de `.cssText` unique à
 *  lire. */
export function feuilleDe(composant: unknown): string {
  const styles = (composant as { styles?: unknown }).styles;
  return [styles].flat().map((s) => (s as { cssText: string }).cssText).join('\n');
}

/** La feuille de l'élément personnalisé `balise`, tel qu'il est enregistré. */
export function feuilleDeLaBalise(balise: string): string {
  const classe = customElements.get(balise);
  if (!classe) throw new Error(`Balise non enregistrée : ${balise}`);
  return feuilleDe(classe);
}

/** Le corps de la règle dont la liste de sélecteurs contient EXACTEMENT
 *  `selecteur`. Rend `''` si aucune règle ne le porte — l'appelant doit alors
 *  échouer, un sélecteur renommé étant précisément la régression à voir. */
export function regleDe(feuille: string, selecteur: string): string {
  // `[^{}]+\{[^{}]*\}` ignore naturellement les enveloppes @media : leur
  // en-tête est suivi d'un `{`, jamais d'un corps sans accolade, et les règles
  // qu'elles contiennent sont retrouvées une à une.
  for (const regle of feuille.match(/[^{}]+\{[^{}]*\}/g) ?? []) {
    const [tete, corps] = regle.split('{');
    if (tete.split(',').some((s) => s.trim() === selecteur)) return corps;
  }
  return '';
}
