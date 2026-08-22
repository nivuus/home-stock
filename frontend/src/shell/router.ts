/** `path` ⇄ écran, dans les deux sens, à partir de la SEULE table des
 *  destinations. Home Assistant nous livre `route.path` (voir
 *  `ha-panel-custom`) : tout ce qui suit `/home-stock`. */
import type { Ecran } from '../panneau';
import { DESTINATIONS, destinationOf } from './destinations';

export type Route = { screen: Ecran; param: string | null };

export const DEFAULT_PATH = '/list';

const PAR_SEGMENT = new Map(DESTINATIONS.map((d) => [d.segment, d]));

export function parsePath(path: string): Route | null {
  const morceaux = path.split('/').filter((m) => m.length > 0);
  if (morceaux.length === 0) return null;
  const destination = PAR_SEGMENT.get(morceaux[0]);
  if (!destination) return null;
  if (!destination.param) {
    // Un paramètre surnuméraire est ignoré, pas rejeté : `/list/42` reste la
    // liste. Rejeter renverrait l'utilisateur à la racine pour une URL qui
    // désigne sans ambiguïté l'écran qu'il voulait.
    return { screen: destination.screen, param: null };
  }
  // Un écran paramétré SANS paramètre n'a rien à montrer : `recette` sans
  // `recipeId` rendrait un écran vide. On préfère la retombée sur la racine.
  if (morceaux.length < 2) return null;
  return { screen: destination.screen, param: morceaux[1] };
}

export function pathOf(screen: Ecran, param: string | number | null = null): string {
  const destination = destinationOf(screen);
  if (!destination.param || param === null || param === undefined) return `/${destination.segment}`;
  return `/${destination.segment}/${param}`;
}
