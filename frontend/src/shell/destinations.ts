/** LA source de vérité de la structure du panneau : la barre, le rail, le
 *  titre de l'en-tête et le routeur la lisent tous. Aucune seconde table à
 *  tenir synchronisée — c'était le défaut de l'ancienne barre, où l'ordre des
 *  boutons, leur libellé et l'écran atteint étaient répétés à trois endroits.
 *
 *  Les identifiants et les segments d'URL sont en ANGLAIS ; les libellés
 *  affichés restent en français. */
import type { Ecran } from '../panneau';
import type { IconName } from './ui/icons';

export type FamilyId = 'shopping' | 'stock' | 'kitchen' | 'house';

export type Destination = {
  screen: Ecran;
  /** Affiché : en français. */
  label: string;
  family: FamilyId;
  /** Le segment d'URL sous `/home-stock/`. */
  segment: string;
  /** Ce que la route porte après le segment, s'il y a lieu. */
  param?: 'id' | 'code';
  /** La destination racine de sa famille : celle qu'atteint la barre. */
  root: boolean;
  /** Écarté de la ligne secondaire parce qu'il est offert autrement — le
   *  scanner est l'action flottante de sa famille, l'y remettre en pastille
   *  le proposerait deux fois sur le même écran. */
  hiddenInFamilyNav?: boolean;
};

export const FAMILIES: ReadonlyArray<{
  id: FamilyId; label: string; icon: IconName; root: Ecran;
}> = [
  { id: 'shopping', label: 'Courses', icon: 'cart', root: 'liste' },
  { id: 'stock', label: 'Stock', icon: 'package', root: 'catalogue' },
  { id: 'kitchen', label: 'Cuisine', icon: 'cutlery', root: 'planning' },
  { id: 'house', label: 'Maison', icon: 'home', root: 'piles' },
];

export const DESTINATIONS: ReadonlyArray<Destination> = [
  { screen: 'liste', label: 'Liste de courses', family: 'shopping', segment: 'list', root: true },
  { screen: 'session', label: 'Magasin', family: 'shopping', segment: 'shopping', root: false },
  { screen: 'panier', label: 'Panier', family: 'shopping', segment: 'cart', root: false },
  { screen: 'rangement', label: 'Rangement', family: 'shopping', segment: 'put-away', root: false },
  { screen: 'ticket', label: 'Ticket', family: 'shopping', segment: 'receipt', param: 'id', root: false },
  { screen: 'scanner', label: 'Scanner', family: 'shopping', segment: 'scan', root: false, hiddenInFamilyNav: true },
  { screen: 'fiche', label: 'Article', family: 'shopping', segment: 'item', param: 'code', root: false },

  { screen: 'catalogue', label: 'Catalogue', family: 'stock', segment: 'catalog', root: true },
  { screen: 'journal', label: 'Journal', family: 'stock', segment: 'log', root: false },
  { screen: 'consommation', label: 'Manger', family: 'stock', segment: 'eat', param: 'id', root: false },

  { screen: 'planning', label: 'Planning', family: 'kitchen', segment: 'planner', root: true },
  { screen: 'recettes', label: 'Recettes', family: 'kitchen', segment: 'recipes', root: false },
  { screen: 'recette', label: 'Recette', family: 'kitchen', segment: 'recipe', param: 'id', root: false },
  { screen: 'validation', label: 'Validation du repas', family: 'kitchen', segment: 'validate', param: 'id', root: false },

  { screen: 'piles', label: 'Piles', family: 'house', segment: 'batteries', root: true },
  { screen: 'equipements', label: 'Équipements', family: 'house', segment: 'equipment', root: false },
  { screen: 'reglages', label: 'Réglages', family: 'house', segment: 'settings', root: false },
];

const PAR_ECRAN = new Map<Ecran, Destination>(DESTINATIONS.map((d) => [d.screen, d]));

export function destinationOf(screen: Ecran): Destination {
  const destination = PAR_ECRAN.get(screen);
  // Un écran absent de la table serait un écran sans titre, sans route et sans
  // famille : mieux vaut le bruit d'une exception au développement qu'un
  // en-tête vide en production.
  if (!destination) throw new Error(`Écran hors de la table des destinations : ${screen}`);
  return destination;
}

export function familyOf(screen: Ecran): FamilyId {
  return destinationOf(screen).family;
}

/** Les écrans d'une famille qui figurent dans la ligne secondaire de
 *  l'en-tête. Ceux qui exigent un paramètre en sont exclus : un bouton nu ne
 *  saurait pas quel identifiant leur passer, on y entre depuis l'écran qui le
 *  connaît. Panier et Rangement y restent même sans session ouverte — des
 *  boutons qui apparaissent et disparaissent font perdre le repère, ce qui
 *  était le défaut de l'ancienne barre. `hiddenInFamilyNav` en écarte aussi
 *  ce qui est offert autrement (le scanner, devenu l'action flottante de sa
 *  famille) : sans ce second filtre, il y figurerait deux fois. */
export function familyScreens(family: FamilyId): Destination[] {
  return DESTINATIONS.filter((d) => d.family === family && !d.param && !d.hiddenInFamilyNav);
}
