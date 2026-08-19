/** Les boutons de date de péremption.
 *
 *  Ranger trente articles sans clavier suppose qu'une DLC se pose en un appui.
 *  La durée apprise par produit passe donc en tête, suivie de trois durées
 *  génériques et de « sans DLC ».
 */
export type Raccourci = { libelle: string; date: string | null };

/** `depuis` construit en heures locales, jamais `toISOString()` : celle-ci
 *  formate un instant UTC, donc un rangement à 00 h 30 à Paris donnerait
 *  « +3 j » pour la veille. Les composants locaux de `Date` gèrent déjà le
 *  report de mois/année (`getDate() + jours` au-delà de la fin du mois roule
 *  correctement) ; le validateur du serveur est strict sur `AAAA-MM-JJ`, donc
 *  la forme rendue doit rester exactement celle-là. */
function dans(jours: number, depuis: Date): string {
  const local = new Date(depuis.getFullYear(), depuis.getMonth(), depuis.getDate() + jours);
  const annee = String(local.getFullYear()).padStart(4, '0');
  const mois = String(local.getMonth() + 1).padStart(2, '0');
  const jour = String(local.getDate()).padStart(2, '0');
  return `${annee}-${mois}-${jour}`;
}

export function raccourcisDlc(aujourdhui: Date, dureeParDefaut: number | null): Raccourci[] {
  const proposees: Raccourci[] = [];
  if (dureeParDefaut && dureeParDefaut > 0) {
    proposees.push({ libelle: `+${dureeParDefaut} j (habituel)`, date: dans(dureeParDefaut, aujourdhui) });
  }
  proposees.push(
    { libelle: '+3 j', date: dans(3, aujourdhui) },
    { libelle: '+1 sem', date: dans(7, aujourdhui) },
    { libelle: '+1 mois', date: dans(31, aujourdhui) },
  );
  // Une durée apprise de 7 jours produirait deux boutons identiques.
  const vues = new Set<string>();
  const uniques = proposees.filter((r) => r.date && !vues.has(r.date) && vues.add(r.date));
  return [...uniques, { libelle: 'Sans DLC', date: null }];
}
