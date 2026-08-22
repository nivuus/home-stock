/** La carte calendrier de Home Assistant, empruntée telle quelle.
 *
 *  Le planning des repas existe DÉJÀ côté Home Assistant comme un vrai
 *  calendrier : `custom_components/home_stock/calendar.py` publie une entité
 *  `calendar.*` qui déclare CREATE_EVENT | UPDATE_EVENT | DELETE_EVENT. Rien
 *  n'oblige donc le panneau à redessiner une grille de semaine à la main : la
 *  carte `calendar` de Lovelace sait afficher cette entité, avec les vues
 *  mois / semaine / jour / liste, le thème de l'utilisateur, sa langue, son
 *  premier jour de semaine et son fuseau — et un clic sur un jour ouvre la
 *  boîte de dialogue de création de Home Assistant, qui écrit un vrai repas.
 *
 *  Le prix à payer, et il est réel : `loadCardHelpers` N'EST PAS dans
 *  `app.*.js` (vérifié en HA 2026.8.2 : il vit dans un chunk séparé, posé par
 *  Lovelace). Il est donc là quand on arrive au panneau depuis un tableau de
 *  bord — le cas courant — et absent quand on ouvre `/home-stock` d'emblée.
 *  D'où le contrat de ce module : il rend `null` plutôt que de lever, et
 *  l'appelant garde sa propre grille en repli. Même discipline que
 *  `ha-available.ts` pour `ha-card`.
 */

/** Ce qu'on lit de `hass` ici, et rien de plus. */
export type HassCalendrier = {
  states?: Record<string, unknown>;
  entities?: Record<string, { platform?: string } | undefined>;
};

type FenetreAvecHelpers = {
  loadCardHelpers?: () => Promise<{
    createCardElement: (config: Record<string, unknown>) => HTMLElement;
  }>;
};

/** Le nom que la plateforme calendrier de `home_stock` donne à son entité
 *  quand rien ne l'a renommée. Repli seulement : c'est le registre qui fait
 *  foi, parce que l'utilisateur a le droit de renommer l'entité et que la
 *  suivre à la trace vaut mieux que la coder en dur. */
const ENTITE_PAR_DEFAUT = 'calendar.home_stock_meals';

/** L'entité calendrier du garde-manger, telle que Home Assistant la connaît.
 *
 *  Cherchée par PLATEFORME dans le registre (`hass.entities`), pas par nom :
 *  un `entity_id` renommé à la main casserait une recherche par nom, en
 *  silence, et l'écran retomberait sur sa grille sans que rien ne le dise. */
export function entiteCalendrierRepas(hass: HassCalendrier | undefined): string | null {
  const registre = hass?.entities;
  if (registre) {
    for (const [entityId, entree] of Object.entries(registre)) {
      if (entityId.startsWith('calendar.') && entree?.platform === 'home_stock') {
        return entityId;
      }
    }
  }
  // Le registre n'est pas toujours peuplé (ouverture directe, version plus
  // ancienne du frontend) : l'état, lui, suffit à savoir que l'entité existe.
  if (hass?.states && Object.prototype.hasOwnProperty.call(hass.states, ENTITE_PAR_DEFAUT)) {
    return ENTITE_PAR_DEFAUT;
  }
  return null;
}

/** La carte, ou `null` si Home Assistant n'a pas chargé de quoi la faire.
 *
 *  Jamais d'exception : `loadCardHelpers` vient d'un chunk tiers, et
 *  `createCardElement` lève sur une configuration qu'il n'aime pas. Les deux
 *  situations veulent la même réponse — pas de carte, l'appelant affiche son
 *  repli — donc les deux passent par le même `catch`. */
export async function creerCarteCalendrier(
  entityId: string,
  win: FenetreAvecHelpers = window as unknown as FenetreAvecHelpers,
): Promise<HTMLElement | null> {
  if (typeof win.loadCardHelpers !== 'function') return null;
  try {
    const helpers = await win.loadCardHelpers();
    if (!helpers || typeof helpers.createCardElement !== 'function') return null;
    return helpers.createCardElement({
      type: 'calendar',
      entities: [entityId],
      // Le mois : c'est la vue qui répond à « ça ne ressemble pas à un
      // calendrier ». Les vues semaine, jour et liste restent à un appui.
      initial_view: 'dayGridMonth',
    });
  } catch {
    return null;
  }
}
