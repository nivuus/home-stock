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
}
