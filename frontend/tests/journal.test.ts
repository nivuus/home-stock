import { beforeEach, describe, expect, it, vi } from 'vitest';
import '../src/ecrans/journal';

const JOUR = {
  food_day: '2026-08-20', start: '2026-08-20T02:00:00', end: '2026-08-21T02:00:00',
  entries: [
    { id: 1, occurred_at: '2026-08-20T08:30:00', product_name: 'Café',
      quantity: -20, base_unit: 'g', reason: 'consumption', kcal: 8,
      parts_total: null, parts_mine: null },
    { id: 2, occurred_at: '2026-08-20T12:15:00', product_name: 'Riz',
      quantity: -400, base_unit: 'g', reason: 'consumption', kcal: 1360,
      parts_total: 4, parts_mine: 1 },
    { id: 3, occurred_at: '2026-08-20T19:00:00', product_name: 'Salade',
      quantity: -150, base_unit: 'g', reason: 'waste', kcal: 30,
      parts_total: null, parts_mine: null },
  ],
  totals: { kcal: 348, cost: 2.4, waste_cost: 0.9, unvalued: 0,
            proteins: 12, salt: 1.2 },
};

const SERIE = { granularity: 'day', buckets: [
  { label: '2026-08-18', kcal: 1800, cost: 9.4, waste_cost: 0 },
  { label: '2026-08-19', kcal: 2100, cost: 11.0, waste_cost: 1.2 },
  { label: '2026-08-20', kcal: 348, cost: 2.4, waste_cost: 0.9 },
]};

// Le brief de cette tâche appelle la méthode de connexion « envoyer » ; elle
// n'existe pas — `Connexion` (src/connexion.ts) n'expose que `appeler`
// (voir aussi fiche.ts, catalogue.ts, panier.ts…). Corrigé ici.
function monter() {
  const element = document.createElement('home-stock-journal') as any;
  element.connexion = { appeler: vi.fn(async (type: string) =>
    type === 'home_stock/journal/day' ? JOUR : SERIE) };
  document.body.append(element);
  return element;
}

describe('<home-stock-journal>', () => {
  beforeEach(() => { document.body.innerHTML = ''; });

  it('liste les entrées de la journée dans l’ordre', async () => {
    const element = monter();
    await element.updateComplete; await element.updateComplete;
    const noms = [...element.shadowRoot.querySelectorAll('.entree-nom')]
      .map((n: Element) => n.textContent?.trim());
    expect(noms).toEqual(['Café', 'Riz', 'Salade']);
  });

  it('affiche la part quand elle n’est pas 1/1, et rien sinon', async () => {
    const element = monter();
    await element.updateComplete; await element.updateComplete;
    const parts = [...element.shadowRoot.querySelectorAll('.entree')]
      .map((e: Element) => e.querySelector('.entree-parts')?.textContent?.trim() ?? '');
    expect(parts[0]).toBe('');
    expect(parts[1]).toContain('1');
    expect(parts[1]).toContain('4');
  });

  it('distingue visiblement ce qui a été jeté', async () => {
    const element = monter();
    await element.updateComplete; await element.updateComplete;
    const entrees = element.shadowRoot.querySelectorAll('.entree');
    expect(entrees[2].classList.contains('jete')).toBe(true);
  });

  it('affiche le total du jour', async () => {
    const element = monter();
    await element.updateComplete; await element.updateComplete;
    expect(element.shadowRoot.querySelector('.total-kcal').textContent).toContain('348');
  });

  it('signale les sorties non chiffrées, et se tait quand il n’y en a pas', async () => {
    const element = monter();
    await element.updateComplete; await element.updateComplete;
    expect(element.shadowRoot.querySelector('.non-chiffre')).toBeNull();

    element.jour = { ...JOUR, totals: { ...JOUR.totals, unvalued: 3 } };
    await element.updateComplete;
    expect(element.shadowRoot.querySelector('.non-chiffre').textContent).toContain('3');
  });

  it('dessine une barre par seau, la plus haute à l’échelle', async () => {
    const element = monter();
    await element.updateComplete; await element.updateComplete;
    const barres = element.shadowRoot.querySelectorAll('.barre');
    expect(barres.length).toBe(3);
    // 2100 est le maximum : sa barre est pleine hauteur.
    expect(Number(barres[1].getAttribute('data-part'))).toBe(1);
  });

  it('ne divise jamais par zéro quand tous les seaux sont vides', async () => {
    const element = monter();
    await element.updateComplete;
    element.serie = { granularity: 'day', buckets: [
      { label: '2026-08-20', kcal: 0, cost: 0, waste_cost: 0 }] };
    await element.updateComplete;
    const barre = element.shadowRoot.querySelector('.barre');
    expect(Number(barre.getAttribute('data-part'))).toBe(0);
  });

  it('demande la bonne granularité quand on change de vue', async () => {
    const element = monter();
    await element.updateComplete; await element.updateComplete;
    await element.choisirGranularite('month');
    expect(element.connexion.appeler).toHaveBeenCalledWith(
      'home_stock/journal/series', { granularity: 'month', count: 12 });
  });

  it('ouvre le jour d’une barre quand on la touche', async () => {
    const element = monter();
    await element.updateComplete; await element.updateComplete;
    await element.ouvrirSeau('2026-08-19');
    expect(element.connexion.appeler).toHaveBeenCalledWith(
      'home_stock/journal/day', { date: '2026-08-19' });
  });

  it('affiche une journée vide sans se plaindre', async () => {
    const element = monter();
    await element.updateComplete;
    element.jour = { ...JOUR, entries: [],
                     totals: { kcal: 0, cost: 0, waste_cost: 0, unvalued: 0 } };
    await element.updateComplete;
    expect(element.shadowRoot.textContent).toContain('Rien de déclaré');
  });
});
