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

/** Prévenu quand une action est abandonnée parce que le serveur l'a refusée
 *  (jamais pour une simple panne réseau, celle-là reste en file). */
export type SurRefus = (action: { type: string; charge: Record<string, unknown> }, message: string) => void;

const CLE_STOCKAGE = 'home_stock.file';

export class FileAttente {
  private actions: Action[] = [];

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

  /** Rejoue dans l'ordre. Une panne de transport arrête tout et garde la file
   *  intacte en tête (on réessaiera). Un refus du serveur, en revanche, ne
   *  changera jamais d'avis à un prochain essai : le garder en tête bloquerait
   *  tout ce qui le suit pour toujours — un seul `+` refusé au début d'un
   *  trajet couperait la totalité du panier. On le retire donc, on prévient
   *  l'appelant (message déjà en français, c'est celui du serveur), et on
   *  continue avec le reste. */
  async rejouer(): Promise<void> {
    while (this.actions.length) {
      const action = this.actions[0];
      try {
        await this.envoyer(action.type, action.charge);
      } catch (erreur) {
        if (estRefusServeur(erreur)) {
          this.actions.shift();
          this.ecrire();
          this.surRefus?.(action, erreur.message);
          continue;
        }
        return;   // panne de transport : on garde la file intacte et on réessaiera
      }
      this.actions.shift();
      this.ecrire();
    }
  }

  private ecrire(): void {
    this.stockage.setItem(CLE_STOCKAGE, JSON.stringify(this.actions));
  }
}
