/** Les boutons de date de péremption.
 *
 *  Ranger trente articles sans clavier suppose qu'une DLC se pose en un appui.
 *  La durée apprise par produit passe donc en tête, suivie de trois durées
 *  génériques et de « sans DLC ».
 */
export type Raccourci = { libelle: string; date: string | null };

const JOUR_MS = 86_400_000;

function dans(jours: number, depuis: Date): string {
  return new Date(depuis.getTime() + jours * JOUR_MS).toISOString().slice(0, 10);
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
