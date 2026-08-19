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
});
