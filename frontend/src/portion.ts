/** Les boutons de quantité de l'écran « manger ».
 *
 *  Pur, comme `dlc.ts` : déclarer un repas doit tenir en un appui, et ce qui
 *  décide du libellé de ces boutons se teste sans monter d'écran.
 *
 *  Aucun bouton ne propose plus que ce qui reste dans le lot visé : une
 *  quantité au-delà déborderait sur le lot suivant, ce qui est légitime au
 *  pavé numérique mais n'a rien à faire dans un raccourci qui prétend dire
 *  « tout le reste ».
 */
import { formaterNombre } from './nombres';
import type { UniteBase } from './ecrans/fiche';

export type Raccourci = { libelle: string; quantite: number };

/** D'où vient la portion proposée, telle que `home_stock/product/get` la
 *  nomme. Ce module ne fait qu'une chose de cette source : choisir entre
 *  « Ma portion » et « 1 portion » — on doit voir d'où vient le chiffre. */
export type SourcePortion = 'manual' | 'learned' | 'serving' | null;

function afficher(quantite: number, unite: UniteBase): string {
  if (unite === 'piece') return `${formaterNombre(quantite)} pièce${quantite >= 2 ? 's' : ''}`;
  if (unite === 'g') {
    return quantite >= 1000 ? `${formaterNombre(quantite / 1000)} kg` : `${formaterNombre(quantite)} g`;
  }
  return quantite >= 1000 ? `${formaterNombre(quantite / 1000)} l` : `${formaterNombre(quantite)} ml`;
}

export function raccourcisQuantite(restant: number, unite: UniteBase,
                                   portion: number | null,
                                   source: SourcePortion = null): Raccourci[] {
  if (restant <= 0) return [];

  const proposes: Raccourci[] = [];
  if (unite === 'piece') {
    proposes.push({ libelle: afficher(1, unite), quantite: 1 });
  } else if (portion !== null && portion > 0 && portion <= restant) {
    const titre = source === 'manual' ? 'Ma portion' : '1 portion';
    proposes.push({ libelle: `${titre} (${afficher(portion, unite)})`, quantite: portion });
  }
  if (unite !== 'piece') {
    proposes.push({ libelle: `La moitié (${afficher(restant / 2, unite)})`, quantite: restant / 2 });
  }
  proposes.push({ libelle: `Tout le reste (${afficher(restant, unite)})`, quantite: restant });

  // Une portion qui vaut exactement la moitié, ou un lot qui n'a plus qu'une
  // pièce : deux boutons identiques valent moins que zéro.
  const vues = new Set<number>();
  return proposes.filter((r) => r.quantite <= restant && !vues.has(r.quantite) && vues.add(r.quantite));
}
