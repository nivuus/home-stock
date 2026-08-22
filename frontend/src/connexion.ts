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
  /** Le jeton de la session en cours, tel que Home Assistant le pose sur
   *  `hass`. Le seul usage est le téléversement d'une photo de ticket, qui
   *  passe par une vue HTTP (`/api/media_source/local_source/upload`) et pas
   *  par le websocket : on ne lit aucun jeton stocké ailleurs, on n'ouvre
   *  aucune seconde session. */
  auth?: { data?: { access_token?: string } };
  /** Ce que Home Assistant ne remplace QUE quand le thème bouge. L'objet
   *  `hass`, lui, est remplacé à chaque changement d'état de la maison —
   *  plusieurs fois par seconde sur la tablette de la cuisine. Le panneau
   *  compare ces deux références pour ne recalculer les couleurs de texte
   *  qu'à bon escient (voir `panneau.ts`, `themeAChange`). */
  themes?: { darkMode?: boolean };
  selectedTheme?: unknown;
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

  /** Téléverse une image dans un dossier de `media/` et rend le
   *  `media_content_id` que Home Assistant lui donne.
   *
   *  Le composant n'écrit AUCUNE vue HTTP : celle-ci est fournie par Home
   *  Assistant, plafonne à 20 Mo, refuse ce qui n'est pas une image, et
   *  exige un compte administrateur. Un refus de sa part remonte tel quel —
   *  l'écran le traduit en français.
   */
  async televerserMedia(fichier: File, dossier: string): Promise<string> {
    const corps = new FormData();
    corps.append('media_content_id', dossier);
    corps.append('file', fichier);
    const jeton = this.hass.auth?.data?.access_token;
    const reponse = await fetch('/api/media_source/local_source/upload', {
      method: 'POST',
      body: corps,
      headers: jeton ? { authorization: `Bearer ${jeton}` } : {},
    });
    if (!reponse.ok) throw new Error(String(reponse.status));
    const rendu = (await reponse.json()) as { media_content_id: string };
    return rendu.media_content_id;
  }
}
