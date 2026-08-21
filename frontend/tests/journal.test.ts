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

  it('parle de calories, pas de prix, pour les sorties non chiffrées '
     + '(le compteur compte des kcal NULL, pas des coûts manquants)', async () => {
    const element = monter();
    await element.updateComplete; await element.updateComplete;
    element.jour = { ...JOUR, totals: { ...JOUR.totals, unvalued: 3 } };
    await element.updateComplete;
    const texte = element.shadowRoot.querySelector('.non-chiffre').textContent;
    expect(texte).toContain('calories');
    expect(texte).not.toContain('prix');
  });

  it('affiche un tiret plutôt que « 0 kcal » quand les calories d’une '
     + 'sortie sont inconnues (gel à NULL, l’invariant que la spec défend '
     + 'le plus explicitement)', async () => {
    const element = monter();
    await element.updateComplete; await element.updateComplete;
    element.jour = { ...JOUR, entries: [{ ...JOUR.entries[0], kcal: null }] };
    await element.updateComplete;
    const kcalAffichees = element.shadowRoot.querySelector('.entree-kcal').textContent?.trim();
    expect(kcalAffichees).toBe('—');
    expect(kcalAffichees).not.toContain('0 kcal');
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

  it('ouvre le jour d’une barre quand on la touche, en vue « jour »', async () => {
    const element = monter();
    await element.updateComplete; await element.updateComplete;
    await element.ouvrirSeau({ label: '2026-08-19', kcal: 2100, cost: 11.0, waste_cost: 1.2 });
    expect(element.connexion.appeler).toHaveBeenCalledWith(
      'home_stock/journal/day', { date: '2026-08-19' });
  });

  it('n’ouvre PAS le premier jour d’un seau « semaine » ou « mois » — affiche ses '
     + 'propres totaux à la place (il n’existe aucune commande serveur qui rende '
     + 'le détail d’un seau, et son premier jour ne représenterait qu’une '
     + 'fraction du seau)', async () => {
    const element = monter();
    await element.updateComplete; await element.updateComplete;
    element.granularite = 'week';
    await element.updateComplete;
    const appelsAvant = element.connexion.appeler.mock.calls.length;

    await element.ouvrirSeau({ label: '2026-07-27', kcal: 55000, cost: 210.5, waste_cost: 12 });
    await element.updateComplete;

    // Aucun nouvel appel réseau : pas de home_stock/journal/day pour ce seau.
    expect(element.connexion.appeler.mock.calls.length).toBe(appelsAvant);
    expect(element.shadowRoot.textContent).toContain('55000');
    expect(element.shadowRoot.textContent).not.toContain('2026-07-27T');
    // La barre « mois » ne doit jamais montrer le total d'un seul jour :
    // pas le total du jour resté en mémoire de la vue « jour » précédente.
    expect(element.shadowRoot.textContent).not.toContain('348 kcal');
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

describe('<home-stock-journal> : corriger une ligne (lot 4)', () => {
  beforeEach(() => { document.body.innerHTML = ''; });

  const APERCU = {
    movement_id: 1, product_name: 'Pâtes', base_unit: 'g', quantity: 200,
    kcal: 310, cost: 0.42, reason: 'consumption',
    occurred_at: '2026-08-14T18:00:00', batch_id: 5,
    batch_entered_at: '2026-08-14T10:00:00', correctable: true, refusal: null,
  };

  function jourAvec(entrees: unknown[]) {
    return { ...JOUR, entries: entrees };
  }

  function monterAvec(entrees: unknown[], apercu: unknown = APERCU) {
    const element = document.createElement('home-stock-journal') as any;
    const file = { ajouter: vi.fn().mockReturnValue({ cle: 'k', sort: Promise.resolve('envoyee') }),
                   rejouer: vi.fn().mockResolvedValue(undefined) };
    element.connexion = { appeler: vi.fn(async (type: string) => {
      if (type === 'home_stock/journal/day') return jourAvec(entrees);
      if (type === 'home_stock/movement/correction_preview') return apercu;
      return SERIE;
    }) };
    element.file = file;
    document.body.append(element);
    return { element, file };
  }

  const LIGNE = { id: 1, occurred_at: '2026-08-14T18:00:00', product_name: 'Pâtes',
                  quantity: -200, base_unit: 'g', reason: 'consumption', kcal: 310,
                  parts_total: null, parts_mine: null, batch_id: 5,
                  corrects_id: null, corrected_by: null };

  async function stabiliser(element: any) {
    await element.updateComplete;
    for (let i = 0; i < 6; i += 1) await Promise.resolve();
    await element.updateComplete;
  }

  it('ouvre le détail d’une ligne en un appui', async () => {
    const { element } = monterAvec([LIGNE]);
    await stabiliser(element);

    (element.shadowRoot.querySelector('.entree-ouvrir') as HTMLButtonElement).click();
    await stabiliser(element);

    expect(element.shadowRoot.querySelector('.detail')).not.toBeNull();
  });

  it('annonce exactement ce que la correction va faire', async () => {
    const { element } = monterAvec([LIGNE]);
    await stabiliser(element);
    (element.shadowRoot.querySelector('.entree-ouvrir') as HTMLButtonElement).click();
    await stabiliser(element);

    const texte = element.shadowRoot.querySelector('.detail').textContent;
    expect(texte).toContain('Annule 200 g de Pâtes');
    expect(texte).toContain('310 kcal');
    expect(texte).toContain('0,42 €');
    expect(texte).toContain('2026-08-14');
  });

  it('demande deux appuis pour corriger', async () => {
    const { element, file } = monterAvec([LIGNE]);
    await stabiliser(element);
    (element.shadowRoot.querySelector('.entree-ouvrir') as HTMLButtonElement).click();
    await stabiliser(element);

    (element.shadowRoot.querySelector('.corriger') as HTMLButtonElement).click();
    await stabiliser(element);
    expect(file.ajouter).not.toHaveBeenCalled();

    (element.shadowRoot.querySelector('.confirmer-correction') as HTMLButtonElement).click();
    expect(file.ajouter).toHaveBeenCalledWith('home_stock/movement/correct',
      { movement_id: 1 });
  });

  it('laisse la ligne corrigée visible et barrée', async () => {
    const { element } = monterAvec([
      { ...LIGNE, corrected_by: 9 },
      { ...LIGNE, id: 9, quantity: 200, kcal: -310, corrects_id: 1 },
    ]);
    await stabiliser(element);

    const lignes = Array.from(element.shadowRoot.querySelectorAll('.entree'));
    expect(lignes.length).toBe(2);
    expect((lignes[0] as HTMLElement).classList.contains('corrigee')).toBe(true);
  });

  it('affiche la contrepassation juste en dessous', async () => {
    const { element } = monterAvec([
      { ...LIGNE, corrected_by: 9 },
      { ...LIGNE, id: 9, quantity: 200, kcal: -310, corrects_id: 1 },
    ]);
    await stabiliser(element);

    const lignes = Array.from(element.shadowRoot.querySelectorAll('.entree'));
    expect((lignes[1] as HTMLElement).classList.contains('contrepassation')).toBe(true);
  });

  it('refuse de proposer « Corriger » sur une ligne déjà corrigée', async () => {
    const { element } = monterAvec([{ ...LIGNE, corrected_by: 9 }],
                                   { ...APERCU, correctable: false,
                                     refusal: 'Cette ligne a déjà été corrigée.' });
    await stabiliser(element);
    (element.shadowRoot.querySelector('.entree-ouvrir') as HTMLButtonElement).click();
    await stabiliser(element);

    expect(element.shadowRoot.querySelector('.corriger')).toBeNull();
    expect(element.shadowRoot.querySelector('.detail').textContent)
      .toContain('déjà été corrigée');
  });

  it('refuse de proposer « Corriger » sur un transfert', async () => {
    const { element } = monterAvec(
      [{ ...LIGNE, reason: 'transfer' }],
      { ...APERCU, correctable: false, reason: 'transfer',
        refusal: 'Un transfert ne se corrige pas : il ne change aucune quantité, '
                 + 'seulement un emplacement.' });
    await stabiliser(element);
    (element.shadowRoot.querySelector('.entree-ouvrir') as HTMLButtonElement).click();
    await stabiliser(element);

    expect(element.shadowRoot.querySelector('.corriger')).toBeNull();
    expect(element.shadowRoot.querySelector('.detail').textContent)
      .toContain('Un transfert ne se corrige pas');
  });

  it('propose « corriger le repas » sur un mouvement cuisiné', async () => {
    const { element, file } = monterAvec(
      [{ ...LIGNE, reason: 'cooked', ref_type: 'meal', ref_id: 42 }],
      { ...APERCU, correctable: false, reason: 'cooked',
        refusal: 'Un mouvement de cuisine s’annule en corrigeant le repas entier, '
                 + 'pas ligne à ligne.', meal_id: 42 });
    await stabiliser(element);
    (element.shadowRoot.querySelector('.entree-ouvrir') as HTMLButtonElement).click();
    await stabiliser(element);

    (element.shadowRoot.querySelector('.corriger-repas') as HTMLButtonElement).click();
    await stabiliser(element);
    (element.shadowRoot.querySelector('.confirmer-correction') as HTMLButtonElement).click();

    expect(file.ajouter).toHaveBeenCalledWith('home_stock/meal/correct', { meal_id: 42 });
  });
});

describe('<home-stock-journal> — les objectifs', () => {
  beforeEach(() => { document.body.innerHTML = ''; });

  const SEMAINE = { kcal: 2100, cost: 9, waste_cost: 0, unvalued: 0, proteins: 60, salt: 7.2 };

  async function monterAvec(goals: Record<string, number>, week_mean = SEMAINE) {
    const element = monter();
    await element.updateComplete;
    element.jour = { ...JOUR, goals, week_mean };
    await element.updateComplete;
    return element;
  }

  it('rend une ligne par objectif réglé', async () => {
    const element = await monterAvec({ kcal: 2000, salt: 6, proteins: 100 });
    expect(element.shadowRoot.querySelectorAll('.objectif').length).toBe(3);
    expect(element.shadowRoot.textContent).toContain('Sel');
  });

  it('n’affiche aucune ligne sans objectif, et laisse l’écran du lot 2 intact', async () => {
    const sans = await monterAvec({});
    const rendu = sans.shadowRoot.innerHTML;
    expect(sans.shadowRoot.querySelectorAll('.objectif').length).toBe(0);

    document.body.innerHTML = '';
    const element = monter();
    await element.updateComplete;
    element.jour = JOUR;                       // exactement la charge du lot 2
    await element.updateComplete;
    expect(element.shadowRoot.innerHTML).toBe(rendu);
  });

  it('marque la ligne dépassée du jour, et pas les autres', async () => {
    // 348 kcal contre 2000 : tenu. 1,2 g de sel contre 1 : dépassé.
    const element = await monterAvec({ kcal: 2000, salt: 1 });
    const depassees = [...element.shadowRoot.querySelectorAll('.objectif-depasse')]
      .map((l: Element) => l.textContent?.trim());
    expect(depassees.length).toBe(1);
    expect(depassees[0]).toContain('Sel');
  });

  it('ajoute une ligne grise quand seule la moyenne des sept journées dépasse', async () => {
    // Le jour tient (1,2 g), la moyenne hebdomadaire non (7,2 g contre 6).
    const element = await monterAvec({ salt: 6 });
    expect(element.shadowRoot.querySelectorAll('.objectif-depasse').length).toBe(0);
    const semaine = element.shadowRoot.querySelector('.objectif-semaine');
    expect(semaine).not.toBeNull();
    expect(semaine.textContent).toContain('7,2');
  });

  it('utilise la virgule décimale, comme tout le panneau', async () => {
    const element = await monterAvec({ salt: 6 });
    const ligne = element.shadowRoot.querySelector('.objectif');
    expect(ligne.textContent).toContain('1,2');
    expect(ligne.textContent).not.toContain('1.2');
  });
});
