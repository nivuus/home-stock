/** File des écritures que le panneau n'a pas pu envoyer.
 *
 *  En magasin, le réseau tombe. La session vit côté serveur, mais un scan doit
 *  quand même partir : on l'empile ici avec sa clé d'idempotence, et on rejoue
 *  à la reconnexion. Le serveur reconnaît la clé et ne double rien.
 */
export type Envoyeur = (type: string, charge: object) => Promise<unknown>;

type Action = { type: string; charge: Record<string, unknown> };

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
  'already_exists', 'conversion_refused', 'shopping_refused',
]);

const MESSAGE_REFUS_GENERIQUE = 'Une action a été refusée et n’a pas pu être envoyée.';

function messageAffichable(erreur: ErreurServeur): string {
  return CODES_DE_REFUS_EN_FRANCAIS.has(erreur.code) ? erreur.message : MESSAGE_REFUS_GENERIQUE;
}

/** Prévenu quand une action est abandonnée parce que le serveur l'a refusée
 *  (jamais pour une simple panne réseau, celle-là reste en file). */
export type SurRefus = (action: { type: string; charge: Record<string, unknown> }, message: string) => void;

export type ResultatAction = 'envoyee' | 'refusee';

const CLE_STOCKAGE = 'home_stock.file';

export class FileAttente {
  private actions: Action[] = [];
  /** Le sort de chaque action qui vient de quitter la file, par clé
   *  d'idempotence — le temps que l'appelant qui l'a posée le récupère (voir
   *  `resultatDe`, qui le consomme). Une action qui reste bloquée par une
   *  panne de transport n'y apparaît jamais : elle n'a pas encore de sort,
   *  elle est toujours en file. */
  private resultats = new Map<string, ResultatAction>();
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

  /** Empile une action et rend sa clé d'idempotence. */
  ajouter(type: string, charge: object): string {
    const contenu = { ...charge } as Record<string, unknown>;
    // La clé est posée à l'ajout, pas à l'envoi : un rejeu doit porter LA MÊME
    // clé, sinon le serveur voit deux scans distincts et le panier double.
    if (typeof contenu.idempotency_key !== 'string') {
      contenu.idempotency_key = crypto.randomUUID();
    }
    this.actions.push({ type, charge: contenu });
    this.ecrire();
    return contenu.idempotency_key as string;
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
   *  Ce que cela ne règle PAS : la course entre `viderResultats()` et un
   *  `resultatDe()` concurrent. Ordonner les boucles n'ordonne pas les
   *  continuations posées dessus — voir `viderResultats`, qui la décrit et
   *  nomme la forme de sa vraie correction. */
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
      const cle = action.charge.idempotency_key as string | undefined;
      try {
        await this.envoyer(action.type, action.charge);
      } catch (erreur) {
        if (estRefusServeur(erreur)) {
          this.actions.shift();
          this.ecrire();
          if (cle) this.resultats.set(cle, 'refusee');
          this.surRefus?.(action, messageAffichable(erreur));
          continue;
        }
        return;   // panne de transport : on garde la file intacte et on réessaiera
      }
      this.actions.shift();
      this.ecrire();
      if (cle) this.resultats.set(cle, 'envoyee');
    }
  }

  /** Le sort d'une action posée par `ajouter`, une fois `rejouer` retombé —
   *  `undefined` tant qu'elle est toujours en file (panne de transport, ou
   *  simplement pas encore essayée). Consommé au premier appel : un appelant
   *  ne lit le sort de SA propre action qu'une fois, ce n'est pas un journal —
   *  l'entrée est retirée dès sa lecture, elle ne traîne pas derrière. */
  resultatDe(cle: string): ResultatAction | undefined {
    const resultat = this.resultats.get(cle);
    this.resultats.delete(cle);
    return resultat;
  }

  /** Purge tout ce qui n'a jamais été réclamé. Pour les rejeux qui ne
   *  connaissent aucune clé précise à réclamer — au démarrage du panneau et
   *  au retour réseau, `rejouer()` vide alors la file entière plutôt qu'une
   *  action qu'on vient d'ajouter soi-même — et dont l'appelant d'origine
   *  (un écran déjà démonté, une page précédente) ne lira donc jamais le
   *  sort. Sans ce nettoyage explicite ces entrées-là resteraient pour
   *  toujours : `resultatDe` ne les retire que si quelqu'un les demande, et
   *  ici personne ne le fera jamais.
   *
   *  ⚠️ **Cet appel peut encore emporter le résultat qu'un écran attendait.**
   *  Sérialiser `rejouer()` a ordonné les BOUCLES, pas les continuations :
   *  quand le rejeu générique du panneau démarre avant l'écriture d'un
   *  écran, son `.then(viderResultats)` est mis en file d'attente AVANT le
   *  `.then(resultatDe)` de l'écran, et efface le sort le premier —
   *  l'écran croit alors son action encore en file alors que le serveur l'a
   *  bien reçue (« Envoi en attente de réseau » sur une session pourtant
   *  ouverte). Le coût est faible : un rafraîchissement ultérieur corrige
   *  l'affichage, et la clé d'idempotence garantit qu'aucune action n'est
   *  envoyée deux fois.
   *
   *  La vraie correction n'est pas un verrou de plus : c'est un passage de
   *  relais **par clé** — `ajouter` rend une promesse, l'entrée de file la
   *  résout elle-même au moment où son sort est connu, et l'appelant n'a
   *  plus jamais à relire une table partagée après coup. Reporté au lot 2 ;
   *  ne pas écrire ici que la course est fermée tant qu'elle ne l'est
   *  pas. */
  viderResultats(): void {
    this.resultats.clear();
  }

  private ecrire(): void {
    this.stockage.setItem(CLE_STOCKAGE, JSON.stringify(this.actions));
  }
}
