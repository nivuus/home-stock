/** File des écritures que le panneau n'a pas pu envoyer.
 *
 *  En magasin, le réseau tombe. La session vit côté serveur, mais un scan doit
 *  quand même partir : on l'empile ici avec sa clé d'idempotence, et on rejoue
 *  à la reconnexion. Le serveur reconnaît la clé et ne double rien.
 */
export type Envoyeur = (type: string, charge: object) => Promise<unknown>;

/** `resoudre` n'est jamais sérialisé dans le stockage local (voir `ecrire`) :
 *  une fonction ne passe pas par `JSON.stringify`, et une action restaurée
 *  au démarrage n'a de toute façon plus d'appelant à prévenir. */
type Action = { type: string; charge: Record<string, unknown>; resoudre?: (sort: ResultatAction) => void };

/** Un refus tranché par le serveur (mauvaise requête, règle métier) répond
 *  toujours avec ce couple — c'est ainsi que `send_error` répond côté HA. Une
 *  panne de transport (réseau coupé, connexion perdue) ne porte jamais de
 *  `code` : c'est ce qui distingue les deux. */
type ErreurServeur = { code: string; message: string };

function estRefusServeur(erreur: unknown): erreur is ErreurServeur {
  return !!erreur && typeof erreur === 'object'
    && typeof (erreur as { code?: unknown }).code === 'string'
    && typeof (erreur as { message?: unknown }).message === 'string';
}

/** Les codes que le domaine de la maison (pas la couche transport de Home
 *  Assistant) choisit lui-même en réponse à un refus — voir
 *  `websocket_api.py` : `_send_domain_error`, `_send_integrity_error`,
 *  `_shopping_error`, `_send_not_loaded`. Leur `message` est rédigé en
 *  français pour être lu tel quel. Tout le reste — au premier rang
 *  `invalid_format`, le code que Home Assistant lui-même répond quand le
 *  schéma refuse un champ — porte un texte anglais de voluptuous avec un
 *  dict Python imprimé dedans (« extra keys not allowed. Got {'id': 5,
 *  … } »), jamais montrable tel quel à quelqu'un debout dans un magasin.
 *  Liste blanche plutôt que liste noire : un code de refus qu'on ne
 *  reconnaît pas obtient le message générique, jamais son texte brut. */
const CODES_DE_REFUS_EN_FRANCAIS: ReadonlySet<string> = new Set([
  'not_loaded', 'invalid_field', 'invalid_value', 'not_found',
  'already_exists', 'conversion_refused', 'shopping_refused', 'insufficient_stock',
]);

const MESSAGE_REFUS_GENERIQUE = 'Une action a été refusée et n’a pas pu être envoyée.';

function messageAffichable(erreur: ErreurServeur): string {
  return CODES_DE_REFUS_EN_FRANCAIS.has(erreur.code) ? erreur.message : MESSAGE_REFUS_GENERIQUE;
}

/** Prévenu quand une action est abandonnée parce que le serveur l'a refusée
 *  (jamais pour une simple panne réseau, celle-là reste en file). */
export type SurRefus = (action: { type: string; charge: Record<string, unknown> }, message: string) => void;

/** Le sort d'une action, une fois son passage en file connu. `en-attente`
 *  n'est ni un succès ni un refus : c'est ce que rend une action toujours
 *  bloquée par une panne de transport, pour que son appelant obtienne quand
 *  même une réponse tout de suite au lieu d'attendre indéfiniment un réseau
 *  qui reviendra peut-être — l'action, elle, reste en file et repartira. */
export type ResultatAction = 'envoyee' | 'refusee' | 'en-attente';

/** Ce que `ajouter` rend à l'appelant : sa clé d'idempotence, et une
 *  promesse de SON sort à elle — jamais celui d'une autre action. */
export type SuiviAction = { cle: string; sort: Promise<ResultatAction> };

const CLE_STOCKAGE = 'home_stock.file';

export class FileAttente {
  private actions: Action[] = [];
  /** Le rejeu en cours, s'il y en a un : c'est le verrou qui sérialise les
   *  trois déclencheurs de `rejouer()` (voir sa documentation). `null` quand
   *  rien n'est en vol. */
  private enVol: Promise<void> | null = null;

  constructor(private stockage: Storage, private envoyer: Envoyeur, private surRefus?: SurRefus) {
    try {
      this.actions = JSON.parse(this.stockage.getItem(CLE_STOCKAGE) ?? '[]');
    } catch {
      this.actions = [];   // stockage corrompu : on repart vide plutôt que de planter
    }
  }

  /** Empile une action et rend un passage de relais **par clé** : sa clé
   *  d'idempotence, et la promesse de SON sort à elle. L'entrée garde son
   *  propre résolveur — `boucle()` l'appelle au moment où le sort de CETTE
   *  action précise est connu, jamais via une table partagée qu'un rejeu
   *  concurrent pourrait vider avant que l'appelant n'ait lu sa réponse. */
  ajouter(type: string, charge: object): SuiviAction {
    const contenu = { ...charge } as Record<string, unknown>;
    // La clé est posée à l'ajout, pas à l'envoi : un rejeu doit porter LA MÊME
    // clé, sinon le serveur voit deux scans distincts et le panier double.
    if (typeof contenu.idempotency_key !== 'string') {
      contenu.idempotency_key = crypto.randomUUID();
    }
    let resoudre!: (sort: ResultatAction) => void;
    const sort = new Promise<ResultatAction>((resolve) => { resoudre = resolve; });
    this.actions.push({ type, charge: contenu, resoudre });
    this.ecrire();
    return { cle: contenu.idempotency_key as string, sort };
  }

  taille(): number {
    return this.actions.length;
  }

  /** Rejoue dans l'ordre, **un rejeu à la fois**.
   *
   *  Trois déclencheurs appellent cette méthode : le `connectedCallback` du
   *  panneau, l'écouteur `online`, et le `ecrire()` de chaque écran. Sans
   *  sérialisation, deux boucles pouvaient lire toutes les deux
   *  `actions[0]`, l'envoyer chacune, puis faire chacune un `shift()` — la
   *  seconde retirant une action DIFFÉRENTE, ajoutée entre-temps, qui n'a
   *  donc jamais été envoyée, alors que son appelant s'entend répondre
   *  qu'elle est toujours en file. La victime concrète était la correction
   *  de poids posée par la fiche (`article/update`), qui n'a aucun rejeu à
   *  elle.
   *
   *  Un appel pendant un rejeu en cours attend donc son tour, puis rejoue à
   *  son tour : quand il retombe, sa propre action a bien été tentée.
   *
   *  La course qui restait ici au lot 1 — un rejeu générique du panneau
   *  pouvant emporter le sort qu'un écran attendait encore — est fermée
   *  depuis que ce sort n'est plus lu dans une table partagée (voir
   *  `ajouter` et `SuiviAction`) : chaque action porte désormais sa propre
   *  promesse, résolue une fois pour toutes par son entrée, peu importe
   *  quel appel à `rejouer()` la traite. */
  async rejouer(): Promise<void> {
    const precedent = this.enVol;
    const courant = (async () => {
      // Un rejeu ne rejette jamais de lui-même ; le `catch` protège d'un
      // stockage local qui lèverait, pour qu'une panne d'un rejeu n'empêche
      // pas les suivants d'avoir lieu.
      if (precedent) await precedent.catch(() => {});
      await this.boucle();
    })();
    this.enVol = courant;
    try {
      await courant;
    } finally {
      if (this.enVol === courant) this.enVol = null;
    }
  }

  /** Le rejeu lui-même. Une panne de transport arrête tout et garde la file
   *  intacte en tête (on réessaiera). Un refus du serveur, en revanche, ne
   *  changera jamais d'avis à un prochain essai : le garder en tête bloquerait
   *  tout ce qui le suit pour toujours — un seul `+` refusé au début d'un
   *  trajet couperait la totalité du panier. On le retire donc, on prévient
   *  l'appelant d'un message TOUJOURS montrable (voir `messageAffichable` —
   *  jamais le texte brut d'un refus de schéma), et on continue avec le reste. */
  private async boucle(): Promise<void> {
    while (this.actions.length) {
      const action = this.actions[0];
      try {
        await this.envoyer(action.type, action.charge);
      } catch (erreur) {
        if (estRefusServeur(erreur)) {
          this.actions.shift();
          this.ecrire();
          action.resoudre?.('refusee');
          this.surRefus?.(action, messageAffichable(erreur));
          continue;
        }
        // Panne de transport : la file reste intacte, elle repartira au
        // prochain rejeu — mais son appelant, lui, ne peut pas attendre
        // indéfiniment un réseau qui reviendra peut-être : chaque entrée
        // encore en file (celle-ci comprise) obtient tout de suite un sort
        // « en-attente », puis perd son résolveur pour ne pas être rappelée
        // en vain au prochain passage.
        for (const restante of this.actions) {
          restante.resoudre?.('en-attente');
          restante.resoudre = undefined;
        }
        return;
      }
      this.actions.shift();
      this.ecrire();
      action.resoudre?.('envoyee');
    }
  }

  /** Ne persiste que `type` et `charge` : `resoudre` est une fonction, donc
   *  non sérialisable, et une action restaurée au démarrage n'a de toute
   *  façon plus d'appelant à prévenir (voir le type `Action`). */
  private ecrire(): void {
    this.stockage.setItem(CLE_STOCKAGE, JSON.stringify(
      this.actions.map(({ type, charge }) => ({ type, charge })),
    ));
  }
}
