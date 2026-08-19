/** File des écritures que le panneau n'a pas pu envoyer.
 *
 *  En magasin, le réseau tombe. La session vit côté serveur, mais un scan doit
 *  quand même partir : on l'empile ici avec sa clé d'idempotence, et on rejoue
 *  à la reconnexion. Le serveur reconnaît la clé et ne double rien.
 */
export type Envoyeur = (type: string, charge: object) => Promise<unknown>;

type Action = { type: string; charge: Record<string, unknown> };

const CLE_STOCKAGE = 'home_stock.file';

export class FileAttente {
  private actions: Action[] = [];

  constructor(private stockage: Storage, private envoyer: Envoyeur) {
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

  /** Rejoue dans l'ordre. S'arrête à la première qui échoue. */
  async rejouer(): Promise<void> {
    while (this.actions.length) {
      const action = this.actions[0];
      try {
        await this.envoyer(action.type, action.charge);
      } catch {
        return;   // toujours hors ligne : on garde la file intacte et on réessaiera
      }
      this.actions.shift();
      this.ecrire();
    }
  }

  private ecrire(): void {
    this.stockage.setItem(CLE_STOCKAGE, JSON.stringify(this.actions));
  }
}
