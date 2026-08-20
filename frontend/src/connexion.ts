/** Accès à Home Assistant depuis un panneau enregistré.
 *
 *  HA passe l'objet `hass` au composant : la connexion websocket et
 *  l'authentification sont déjà les siennes. On ne lit aucun jeton, on n'ouvre
 *  aucune seconde session.
 */
export type Hass = {
  connection: {
    sendMessagePromise<T>(message: object): Promise<T>;
    subscribeMessage<T>(rappel: (event: T) => void, message: object): Promise<() => void>;
  };
  language: string;
  /** L'appel de service de Home Assistant, tel que le composant custom le
   *  reçoit déjà dans `hass` — aucune requête REST, aucun jeton à part. Ne
   *  sert aujourd'hui qu'à `home_stock.resync_off` (écran Réglages) : ce
   *  service n'a pas d'équivalent websocket, un appel de service est le seul
   *  moyen de le déclencher depuis le panneau. */
  callService(domain: string, service: string, serviceData?: Record<string, unknown>): Promise<unknown>;
};

export class Connexion {
  constructor(private hass: Hass) {}

  appeler<T>(type: string, charge: object = {}): Promise<T> {
    return this.hass.connection.sendMessagePromise<T>({ type, ...charge });
  }

  /** S'abonne au résumé : le stock bouge sur le téléphone pendant qu'on range. */
  abonner<T>(rappel: (resume: T) => void): Promise<() => void> {
    return this.hass.connection.subscribeMessage<T>(rappel, { type: 'home_stock/subscribe' });
  }

  /** Appelle un service Home Assistant (pas une commande websocket du
   *  domaine) — voir `home_stock.resync_off`, qui n'existe que sous cette
   *  forme (spec 13 : un service, pas une commande websocket). */
  appelerService(domaine: string, service: string, donnees: Record<string, unknown> = {}): Promise<unknown> {
    return this.hass.callService(domaine, service, donnees);
  }
}
