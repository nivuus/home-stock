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
    expect(a.cle).not.toBe(b.cle);
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
    const { cle } = file.ajouter('t', { idempotency_key: 'imposée' });
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

describe('file d’attente : un seul rejeu à la fois', () => {
  it('n’avale jamais une action ajoutée pendant qu’un rejeu est en vol', async () => {
    // Trois déclencheurs appellent `rejouer()` : le connectedCallback du
    // panneau, l'écouteur `online`, et le `ecrire()` de chaque écran. Deux
    // boucles concurrentes lisaient toutes les deux `actions[0]`, puis
    // faisaient chacune un `shift()` — la seconde retirant une action
    // DIFFÉRENTE, ajoutée entre-temps, jamais envoyée. La victime concrète
    // était la correction de poids posée par la fiche, qui n'a aucun rejeu
    // à elle.
    const stockage = new StockageFactice();
    const envoyes: string[] = [];
    let debloquerLaPremiere: () => void = () => {};
    const premiereEnVol = new Promise<void>((resolve) => { debloquerLaPremiere = resolve; });

    const file = new FileAttente(stockage, async (type) => {
      envoyes.push(type);
      if (type === 'lent') await premiereEnVol;
    });

    file.ajouter('lent', {});
    const premier = file.rejouer();            // bloqué dans l'envoi de « lent »
    await Promise.resolve();

    file.ajouter('home_stock/article/update', { article_id: 1 });
    const second = file.rejouer();             // arrive pendant que « lent » est en vol

    debloquerLaPremiere();
    await Promise.all([premier, second]);

    expect(envoyes).toEqual(['lent', 'home_stock/article/update']);
    expect(file.taille()).toBe(0);
  });

  it('rend la main seulement quand l’action de l’appelant a été tentée', async () => {
    const stockage = new StockageFactice();
    let debloquer: () => void = () => {};
    const bloquee = new Promise<void>((resolve) => { debloquer = resolve; });
    const file = new FileAttente(stockage, async (type) => {
      if (type === 'lent') await bloquee;
    });

    file.ajouter('lent', {});
    const premier = file.rejouer();
    await Promise.resolve();

    const suivi = file.ajouter('t', {});
    const second = file.rejouer();

    debloquer();
    await Promise.all([premier, second]);

    expect(await suivi.sort).toBe('envoyee');
  });
});

describe('file d’attente : le passage de relais par clé', () => {
  it('rend un sort par action, sans table partagée', async () => {
    const file = new FileAttente(new StockageFactice(), async () => undefined);
    const premier = file.ajouter('home_stock/stock/consume', { product_id: 1 });
    const second = file.ajouter('home_stock/stock/consume', { product_id: 2 });
    await file.rejouer();
    expect(await premier.sort).toBe('envoyee');
    expect(await second.sort).toBe('envoyee');
  });

  it('un rejeu générique concurrent n’emporte plus le sort d’un écran', async () => {
    // La course exacte que le lot 1 avait laissée ouverte : le rejeu du panneau
    // démarre avant l'écriture d'un écran, et son `.then` effaçait la table
    // partagée avant que l'écran n'ait lu SON résultat.
    const file = new FileAttente(new StockageFactice(), async () => undefined);
    const generique = file.rejouer();
    const suivi = file.ajouter('home_stock/stock/consume', { product_id: 1 });
    await Promise.all([generique, file.rejouer()]);
    expect(await suivi.sort).toBe('envoyee');
  });

  it('résout « en-attente » quand le transport est tombé, sans vider la file', async () => {
    const file = new FileAttente(new StockageFactice(), async () => { throw new Error('hors ligne'); });
    const suivi = file.ajouter('home_stock/stock/consume', { product_id: 1 });
    await file.rejouer();
    expect(await suivi.sort).toBe('en-attente');
    expect(file.taille()).toBe(1);
  });

  it('résout « refusee » sur un refus du serveur et retire l’action', async () => {
    const file = new FileAttente(new StockageFactice(), async () => {
      throw { code: 'invalid_field', message: 'Les parts sont incohérentes.' };
    });
    const suivi = file.ajouter('home_stock/stock/consume', { product_id: 1 });
    await file.rejouer();
    expect(await suivi.sort).toBe('refusee');
    expect(file.taille()).toBe(0);
  });

  it('une action restaurée du stockage local n’attend personne', async () => {
    const stockage = new StockageFactice();
    stockage.setItem('home_stock.file', JSON.stringify(
      [{ type: 'home_stock/stock/add', charge: { idempotency_key: 'x' } }]));
    const file = new FileAttente(stockage, async () => undefined);
    await expect(file.rejouer()).resolves.toBeUndefined();
    expect(file.taille()).toBe(0);
  });
});
