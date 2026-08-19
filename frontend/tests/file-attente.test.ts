import { describe, expect, it, vi } from 'vitest';
import { FileAttente } from '../src/file-attente';

class StockageFactice implements Storage {
  private donnees = new Map<string, string>();
  get length() { return this.donnees.size; }
  clear() { this.donnees.clear(); }
  getItem(cle: string) { return this.donnees.get(cle) ?? null; }
  key(index: number) { return [...this.donnees.keys()][index] ?? null; }
  removeItem(cle: string) { this.donnees.delete(cle); }
  setItem(cle: string, valeur: string) { this.donnees.set(cle, valeur); }
}

describe('file d’attente hors ligne', () => {
  it('rend une clé d’idempotence différente à chaque ajout', () => {
    const file = new FileAttente(new StockageFactice(), async () => {});
    const a = file.ajouter('home_stock/session/add_line', { article_id: 1 });
    const b = file.ajouter('home_stock/session/add_line', { article_id: 1 });
    expect(a).not.toBe(b);
  });

  it('survit à un rechargement de la page', () => {
    const stockage = new StockageFactice();
    new FileAttente(stockage, async () => {}).ajouter('t', { a: 1 });
    expect(new FileAttente(stockage, async () => {}).taille()).toBe(1);
  });

  it('rejoue dans l’ordre où les scans ont eu lieu', async () => {
    const vus: number[] = [];
    const file = new FileAttente(new StockageFactice(), async (_t, charge) => {
      vus.push((charge as { n: number }).n);
    });
    file.ajouter('t', { n: 1 });
    file.ajouter('t', { n: 2 });
    file.ajouter('t', { n: 3 });

    await file.rejouer();

    expect(vus).toEqual([1, 2, 3]);
    expect(file.taille()).toBe(0);
  });

  it('garde l’action qui échoue et s’arrête là', async () => {
    // Rejouer la suivante réordonnerait le panier : on préfère réessayer plus tard.
    const file = new FileAttente(new StockageFactice(), async (_t, charge) => {
      if ((charge as { n: number }).n === 2) throw new Error('hors ligne');
    });
    file.ajouter('t', { n: 1 });
    file.ajouter('t', { n: 2 });
    file.ajouter('t', { n: 3 });

    await file.rejouer();

    expect(file.taille()).toBe(2);
  });

  it('renvoie la même clé si la même action est rejouée', async () => {
    const cles: string[] = [];
    const file = new FileAttente(new StockageFactice(), async (_t, charge) => {
      cles.push((charge as { idempotency_key: string }).idempotency_key);
      throw new Error('hors ligne');
    });
    file.ajouter('t', { article_id: 1 });

    await file.rejouer();
    await file.rejouer();

    expect(cles[0]).toBe(cles[1]);
  });

  it('n’écrase pas une clé fournie par l’appelant', () => {
    const file = new FileAttente(new StockageFactice(), async () => {});
    const cle = file.ajouter('t', { idempotency_key: 'imposée' });
    expect(cle).toBe('imposée');
  });

  it('repart vide plutôt que de planter si le stockage est corrompu', () => {
    const stockage = new StockageFactice();
    stockage.setItem('home_stock.file', '{ceci n’est pas du JSON valide');

    expect(() => new FileAttente(stockage, async () => {})).not.toThrow();
    expect(new FileAttente(stockage, async () => {}).taille()).toBe(0);
  });
});

describe('file d’attente hors ligne : refus du serveur contre panne réseau', () => {
  it('un refus (avec code) est retiré de la file et n’empêche pas la suite de partir', async () => {
    // Une file empoisonnée : la première action est refusée par le serveur
    // (mauvaise règle métier), la seconde ne l'est pas. Un `+` refusé au
    // début d'un trajet ne doit jamais couper tout ce qui vient après.
    const vus: number[] = [];
    const file = new FileAttente(new StockageFactice(), async (_t, charge) => {
      const n = (charge as { n: number }).n;
      if (n === 1) throw { code: 'shopping_refused', message: 'Cette ligne est déjà rangée.' };
      vus.push(n);
    });
    file.ajouter('t', { n: 1 });
    file.ajouter('t', { n: 2 });

    await file.rejouer();

    expect(vus).toEqual([2]);          // la bonne action est bien partie
    expect(file.taille()).toBe(0);     // les deux ont quitté la file (l'une refusée, l'autre envoyée)
  });

  it('prévient l’appelant avec le message du serveur quand une action est refusée', async () => {
    const surRefus = vi.fn();
    const file = new FileAttente(new StockageFactice(), async () => {
      throw { code: 'invalid_field', message: 'Écriture refusée : donnée invalide.' };
    }, surRefus);
    file.ajouter('home_stock/session/update_line', { line_id: 1, quantity: -5 });

    await file.rejouer();

    expect(surRefus).toHaveBeenCalledTimes(1);
    const [action, message] = surRefus.mock.calls[0];
    expect(action.type).toBe('home_stock/session/update_line');
    expect(message).toBe('Écriture refusée : donnée invalide.');
  });

  it('une panne réseau (sans code) reste bien en tête de file, elle', async () => {
    const file = new FileAttente(new StockageFactice(), async () => {
      throw new Error('hors ligne');
    });
    file.ajouter('t', { n: 1 });

    await file.rejouer();

    expect(file.taille()).toBe(1);
  });

  it('ne montre jamais le texte brut d’un refus de schéma (voluptuous, en anglais, avec '
     + 'un dict Python dedans) : un code inconnu obtient le message générique', async () => {
    const surRefus = vi.fn();
    const file = new FileAttente(new StockageFactice(), async () => {
      throw {
        code: 'invalid_format',
        message: "extra keys not allowed @ data['idempotency_key']. Got {'id': 5, 'type': 'home_stock/session/checkout'}",
      };
    }, surRefus);
    file.ajouter('home_stock/session/checkout', {});

    await file.rejouer();

    expect(surRefus).toHaveBeenCalledTimes(1);
    const [, message] = surRefus.mock.calls[0];
    expect(message).not.toContain('extra keys');
    expect(message).not.toContain('{');
    expect(message).toMatch(/^[A-ZÀ-Ü]/); // une vraie phrase française, pas un fragment technique
  });

  it('montre le message du serveur tel quel pour un code de refus métier connu (déjà en français)', async () => {
    const surRefus = vi.fn();
    const file = new FileAttente(new StockageFactice(), async () => {
      throw { code: 'shopping_refused', message: 'Cette ligne est déjà rangée : corrigez le lot, pas la liste.' };
    }, surRefus);
    file.ajouter('home_stock/session/remove_line', { line_id: 1 });

    await file.rejouer();

    expect(surRefus).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'home_stock/session/remove_line' }),
      'Cette ligne est déjà rangée : corrigez le lot, pas la liste.',
    );
  });
});

describe('file d’attente hors ligne : le sort d’une action ne s’accumule pas indéfiniment', () => {
  it('retire une entrée dès qu’elle est lue : un deuxième appel ne retrouve plus rien', async () => {
    const file = new FileAttente(new StockageFactice(), async () => {});
    const cle = file.ajouter('t', { n: 1 });

    await file.rejouer();

    expect(file.resultatDe(cle)).toBe('envoyee');
    expect(file.resultatDe(cle)).toBeUndefined();
  });

  it('purge les sorts jamais réclamés (viderResultats) — le rejeu générique du panneau, au démarrage '
     + 'ou au retour réseau, ne connaît aucune clé précise à réclamer lui-même', async () => {
    const file = new FileAttente(new StockageFactice(), async () => {});
    const cle = file.ajouter('t', { n: 1 });
    await file.rejouer(); // personne ne lit `cle` — exactement ce que fait un rejeu générique

    file.viderResultats();

    expect(file.resultatDe(cle)).toBeUndefined();
  });

  it('un refus jamais réclamé est purgé de la même façon qu’un envoi réussi', async () => {
    const file = new FileAttente(new StockageFactice(), async () => {
      throw { code: 'invalid_field', message: 'Écriture refusée : donnée invalide.' };
    });
    const cle = file.ajouter('t', { n: 1 });
    await file.rejouer();

    file.viderResultats();

    expect(file.resultatDe(cle)).toBeUndefined();
  });
});
