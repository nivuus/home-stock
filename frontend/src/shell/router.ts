/** `path` ⇄ écran, dans les deux sens, à partir de la SEULE table des
 *  destinations. Home Assistant nous livre `route.path` (voir
 *  `ha-panel-custom`) : tout ce qui suit `/home-stock`. */
import type { Ecran } from '../panneau';
import { DESTINATIONS, destinationOf } from './destinations';

export type Route = { screen: Ecran; param: string | null };

/** Le chemin de repli : celui qu'atteint une route inconnue, et celui que le
 *  panneau pose quand personne ne lui a rien demandé. */
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

/** Le MÊME repli, en écran — dérivé du chemin, jamais écrit une seconde fois.
 *  `panneau.ts` navigue par écran, pas par chaîne : il écrivait donc `'liste'`
 *  en dur à deux endroits, de sorte que changer `DEFAULT_PATH` ne changeait
 *  rien du tout et que son test restait vert quand même. Le dériver ici rend
 *  le lien réel : `DEFAULT_PATH` est désormais lu, et une valeur qui ne
 *  désigne aucun écran fait du bruit au chargement du module plutôt qu'une
 *  navigation muette vers nulle part. */
export const DEFAULT_SCREEN: Ecran = ecranDeRepli();

function ecranDeRepli(): Ecran {
  const route = parsePath(DEFAULT_PATH);
  if (!route) throw new Error(`DEFAULT_PATH ne désigne aucun écran : ${DEFAULT_PATH}`);
  return route.screen;
}

export function pathOf(screen: Ecran, param: string | number | null = null): string {
  const destination = destinationOf(screen);
  if (!destination.param) return `/${destination.segment}`;
  // Un écran paramétré sans son paramètre produirait un chemin que `parsePath`
  // rend `null` : une URL illisible, donc une navigation qui retombe
  // silencieusement sur la racine. Même parti pris que `destinationOf` : le
  // bruit d'une exception plutôt qu'une panne muette.
  if (param === null || param === undefined) {
    throw new Error(`L'écran « ${screen} » exige un paramètre : pathOf(${screen}, …)`);
  }
  return `/${destination.segment}/${param}`;
}
