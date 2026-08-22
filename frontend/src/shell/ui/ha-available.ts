/** Les éléments `ha-*` ne sont PAS enregistrés par notre bundle : ils
 *  viennent de chunks que Home Assistant charge à la demande. Vérifié en HA
 *  2026.8.2 : ni `ha-card`, ni `ha-svg-icon`, ni `loadCardHelpers` ne sont
 *  dans `app.*.js`.
 *
 *  Ils sont donc présents quand on arrive depuis Lovelace (le cas courant,
 *  `default_panel` valant `lovelace`) et absents quand on ouvre
 *  `/home-stock` directement — ce que fait la tablette de la cuisine. Et un
 *  élément inconnu ne lève rien : il se rend en `display: inline`,
 *  silencieusement. D'où ce module, et les enveloppes qui s'en servent. */

type Rappel = () => void;

const abonnes = new Map<string, Rappel[]>();
let amorcageDemande = false;

/** Synchrone, parce que le rendu de Lit l'est : une enveloppe doit décider
 *  MAINTENANT si elle rend `<ha-card>` ou son repli. */
export function isDefined(name: string): boolean {
  return typeof customElements !== 'undefined' && Boolean(customElements.get(name));
}

/** Rappelle `onDefined` si l'élément est enregistré plus tard. Un seul
 *  `customElements.whenDefined` par nom, quel que soit le nombre
 *  d'instances : elles sont potentiellement des dizaines à l'écran.
 *
 *  Retourne une fonction de désabonnement. Sur la tablette cuisine — qui
 *  ouvre `/home-stock` directement, sans jamais charger `ha-svg-icon` —
 *  chaque montage d'icône empilerait un rappel qui ne se résout jamais si
 *  rien ne pouvait le retirer au démontage : une fuite qui grossit à chaque
 *  navigation sur un kiosque qui tourne en continu. */
export function whenDefined(name: string, onDefined: Rappel): () => void {
  if (isDefined(name)) return () => {};
  const existants = abonnes.get(name);
  if (existants) {
    existants.push(onDefined);
  } else {
    abonnes.set(name, [onDefined]);
    void customElements.whenDefined(name).then(() => {
      for (const rappel of abonnes.get(name) ?? []) rappel();
      abonnes.delete(name);
    });
  }
  return () => {
    const restants = abonnes.get(name);
    if (!restants) return;
    const index = restants.indexOf(onDefined);
    if (index >= 0) restants.splice(index, 1);
    // Ne pas laisser une entrée vide dans la table : sinon
    // `pendingCountForTests` (et tout futur code qui s'y fierait) verrait un
    // nom encore « en attente » alors que plus personne n'écoute.
    if (restants.length === 0) abonnes.delete(name);
  };
}

/** Tente une fois de forcer le chunk Lovelace, qui enregistre `ha-card` et
 *  ses voisins. `loadCardHelpers` est lui-même posé par ce chunk : son
 *  absence signifie simplement qu'on est arrivé sans passer par Lovelace,
 *  et c'est exactement le cas où les replis servent. Jamais une erreur.
 *
 *  Le `try` synchrone est nécessaire en plus du `.catch` : `loadCardHelpers`
 *  vient d'un chunk tiers, rien ne garantit qu'il renvoie toujours une
 *  promesse plutôt que de lever avant même d'en créer une. Un jet immédiat
 *  et un rejet différé sont la même situation de notre point de vue — pas
 *  de Lovelace, les replis prennent le relais — donc les deux doivent mener
 *  au même repli silencieux. */
export function primeHaComponents(win: Window = window): void {
  if (amorcageDemande) return;
  amorcageDemande = true;
  const charger = (win as unknown as { loadCardHelpers?: () => Promise<unknown> }).loadCardHelpers;
  if (typeof charger !== 'function') return;
  try {
    void Promise.resolve(charger.call(win)).catch(() => {
      // Rien à faire : les enveloppes rendent leur repli, qui est correct.
    });
  } catch {
    // Idem, pour le jet synchrone : les enveloppes rendent leur repli.
  }
}

/** Uniquement pour les tests : l'état ci-dessus est un module singleton. */
export function resetForTests(): void {
  abonnes.clear();
  amorcageDemande = false;
}

/** Uniquement pour les tests : le nombre de noms encore en attente. La purge
 *  de `abonnes` n'est observable par aucune API publique — `whenDefined`
 *  court-circuite sur `isDefined` dès que l'élément existe — et un test qui
 *  prétendrait la vérifier sans y accéder mesurerait autre chose. */
export function pendingCountForTests(): number {
  return abonnes.size;
}
