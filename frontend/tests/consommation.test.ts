import { beforeEach, describe, expect, it, vi } from 'vitest';
import '../src/ecrans/consommation';

const PRODUIT_G = {
  product: { id: 1, name: 'Riz', base_unit: 'g' },
  suggested_portion: 80, portion_source: 'learned', serving_quantity: null,
  next_batch: { id: 7, remaining: 500, best_before: '2026-09-01' },
};

const PRODUIT_PIECE = {
  product: { id: 2, name: 'Yaourt', base_unit: 'piece' },
  suggested_portion: null, portion_source: null, serving_quantity: null,
  next_batch: { id: 8, remaining: 4, best_before: null },
};

/** Reprend le montage de `fiche.test.ts` : jsdom, `Connexion` factice (la
 *  vraie classe n'expose que `appeler`, jamais `envoyer` — c'est l'erreur du
 *  brief, corrigée ici), `FileAttente` factice dont `ajouter` répond « envoyée »
 *  par défaut, chaque test qui veut inspecter la charge envoyée remplaçant
 *  `element.file` par la sienne. */
function monter(reponse: unknown) {
  const element = document.createElement('home-stock-consommation') as any;
  element.connexion = { appeler: vi.fn(async () => reponse) };
  element.file = {
    ajouter: () => ({ cle: 'k', sort: Promise.resolve('envoyee') }),
    rejouer: async () => undefined,
  };
  element.productId = 1;
  document.body.append(element);
  return element;
}

/** Une `FileAttente` factice qui journalise chaque charge envoyée à
 *  `envoi`, et répond toujours « envoyée ». */
function fileEspionne(envoi: ReturnType<typeof vi.fn>) {
  return {
    ajouter: (type: string, charge: any) => {
      envoi(type, charge);
      return { cle: 'k', sort: Promise.resolve('envoyee') };
    },
    rejouer: async () => undefined,
  };
}

describe('<home-stock-consommation>', () => {
  beforeEach(() => { document.body.innerHTML = ''; });

  it('arme « 1 pièce » pour un produit à la pièce', async () => {
    const element = monter(PRODUIT_PIECE);
    await element.updateComplete;
    await element.updateComplete;
    expect(element.quantite).toBe(1);
  });

  it('propose la portion apprise pour un produit au gramme', async () => {
    const element = monter(PRODUIT_G);
    await element.updateComplete;
    await element.updateComplete;
    const libelles = [...element.shadowRoot.querySelectorAll('.raccourci')]
      .map((b: Element) => b.textContent?.trim());
    expect(libelles[0]).toContain('1 portion (80 g)');
  });

  it('envoie la quantité, le motif et rien d’autre par défaut', async () => {
    const envoi = vi.fn();
    const element = monter(PRODUIT_G);
    element.file = fileEspionne(envoi);
    await element.updateComplete;
    await element.updateComplete;
    element.quantite = 80;
    await element.enregistrer();
    expect(envoi).toHaveBeenCalledWith('home_stock/stock/consume', expect.objectContaining({
      product_id: 1, batch_id: 7, quantity: 80, reason: 'consumption',
    }));
    // Pas de parts quand on n'a rien partagé : NULL en base, pas 1/1.
    expect(envoi.mock.calls[0][1]).not.toHaveProperty('parts_total');
  });

  it('perd le lot visé quand la quantité déborde son reste, pour laisser le '
     + 'serveur étaler sur les lots suivants (spec 12.1)', async () => {
    const envoi = vi.fn();
    // Reste 120 g sur le lot visé : un paquet entamé. Un neuf de 1 kg
    // existe côté serveur mais n'apparaît pas ici — l'écran ne connaît que
    // le lot FIFO — c'est justement pourquoi il ne peut pas se permettre de
    // désigner ce lot pour une quantité qui le dépasse.
    const element = monter({ ...PRODUIT_G, next_batch: { id: 7, remaining: 120, best_before: null } });
    element.file = fileEspionne(envoi);
    await element.updateComplete;
    await element.updateComplete;
    element.quantite = 200;
    await element.enregistrer();
    expect(envoi.mock.calls[0][1]).not.toHaveProperty('batch_id');
  });

  it('garde le lot visé quand la quantité tient dedans', async () => {
    const envoi = vi.fn();
    const element = monter({ ...PRODUIT_G, next_batch: { id: 7, remaining: 120, best_before: null } });
    element.file = fileEspionne(envoi);
    await element.updateComplete;
    await element.updateComplete;
    element.quantite = 100;
    await element.enregistrer();
    expect(envoi.mock.calls[0][1]).toMatchObject({ batch_id: 7 });
  });

  it('envoie les deux parts quand on partage', async () => {
    const envoi = vi.fn();
    const element = monter(PRODUIT_G);
    element.file = fileEspionne(envoi);
    await element.updateComplete;
    await element.updateComplete;
    element.quantite = 400;
    element.partage = true;
    element.partsTotal = 4;
    element.partsMoi = 1;
    await element.enregistrer();
    expect(envoi.mock.calls[0][1]).toMatchObject({ parts_total: 4, parts_mine: 1 });
  });

  it('escamote les parts dès qu’on choisit « jeté »', async () => {
    const element = monter(PRODUIT_G);
    await element.updateComplete;
    await element.updateComplete;
    element.partage = true;
    element.motif = 'waste';
    await element.updateComplete;
    expect(element.shadowRoot.querySelector('.parts')).toBeNull();
  });

  it('n’envoie jamais de parts sur un motif « jeté »', async () => {
    const envoi = vi.fn();
    const element = monter(PRODUIT_G);
    element.file = fileEspionne(envoi);
    await element.updateComplete;
    await element.updateComplete;
    element.quantite = 100;
    element.partage = true;
    element.partsTotal = 4;
    element.partsMoi = 1;
    element.motif = 'waste';
    await element.enregistrer();
    expect(envoi.mock.calls[0][1]).not.toHaveProperty('parts_total');
  });

  it('accepte la virgule décimale au pavé', async () => {
    const element = monter(PRODUIT_G);
    await element.updateComplete;
    await element.updateComplete;
    element.saisirQuantite('12,5');
    expect(element.quantite).toBe(12.5);
    expect(element.erreur).toBeNull();
  });

  it('refuse un texte qui n’est pas un nombre plutôt que d’envoyer NaN', async () => {
    const envoi = vi.fn();
    const element = monter(PRODUIT_G);
    element.file = fileEspionne(envoi);
    await element.updateComplete;
    await element.updateComplete;
    element.saisirQuantite('deux cuillères');
    await element.enregistrer();
    expect(envoi).not.toHaveBeenCalled();
    expect(element.erreur).toContain('nombre');
  });

  it('refuse une quantité nulle ou négative', async () => {
    const element = monter(PRODUIT_G);
    await element.updateComplete;
    await element.updateComplete;
    element.saisirQuantite('0');
    await element.enregistrer();
    expect(element.erreur).not.toBeNull();
  });

  it('refuse de manger plus de parts qu’il n’en a été servi, sans aller au serveur', async () => {
    const envoi = vi.fn();
    const element = monter(PRODUIT_G);
    element.file = fileEspionne(envoi);
    await element.updateComplete;
    await element.updateComplete;
    element.quantite = 100;
    element.partage = true;
    element.partsTotal = 2;
    element.partsMoi = 3;
    await element.enregistrer();
    expect(envoi).not.toHaveBeenCalled();
  });

  it('refuse plus de 24 parts servies, sans aller au serveur', async () => {
    const envoi = vi.fn();
    const element = monter(PRODUIT_G);
    element.file = fileEspionne(envoi);
    await element.updateComplete;
    await element.updateComplete;
    element.quantite = 100;
    element.partage = true;
    element.partsTotal = 25;
    element.partsMoi = 1;
    await element.enregistrer();
    expect(envoi).not.toHaveBeenCalled();
    expect(element.erreur).not.toBeNull();
  });

  it('dit qu’il ne reste rien plutôt que de proposer une quantité', async () => {
    const element = monter({ ...PRODUIT_G, next_batch: null });
    await element.updateComplete;
    await element.updateComplete;
    expect(element.shadowRoot.textContent).toContain('Plus rien en stock');
    expect(element.shadowRoot.querySelectorAll('.raccourci').length).toBe(0);
  });

  it('émet « consommation-enregistree » — et donc se referme — quand l’envoi part', async () => {
    const element = monter(PRODUIT_G);
    element.file = {
      ajouter: () => ({ cle: 'k', sort: Promise.resolve('envoyee') }),
      rejouer: async () => undefined,
    };
    const fermeture = vi.fn();
    element.addEventListener('consommation-enregistree', fermeture);
    await element.updateComplete;
    await element.updateComplete;
    element.quantite = 80;
    await element.enregistrer();
    expect(fermeture).toHaveBeenCalledTimes(1);
  });

  it('reste ouvert — n’émet PAS « consommation-enregistree » — quand l’envoi n’est pas parti', async () => {
    const element = monter(PRODUIT_G);
    element.file = {
      ajouter: () => ({ cle: 'k', sort: Promise.resolve('en-attente') }),
      rejouer: async () => undefined,
    };
    const fermeture = vi.fn();
    element.addEventListener('consommation-enregistree', fermeture);
    await element.updateComplete;
    await element.updateComplete;
    element.quantite = 80;
    await element.enregistrer();
    expect(element.enAttenteEnvoi).toBe(true);
    expect(fermeture).not.toHaveBeenCalled();
  });

  it('ne montre PAS « ça repartira » pour un refus — la file l’a déjà retiré, '
     + 'rien ne repartira jamais (le refus lui-même est déjà annoncé par la '
     + 'bannière du panneau, voir panneau.ts)', async () => {
    const element = monter(PRODUIT_G);
    element.file = {
      ajouter: () => ({ cle: 'k', sort: Promise.resolve('refusee') }),
      rejouer: async () => undefined,
    };
    const fermeture = vi.fn();
    element.addEventListener('consommation-enregistree', fermeture);
    await element.updateComplete;
    await element.updateComplete;
    element.quantite = 80;
    await element.enregistrer();
    await element.updateComplete;
    expect(fermeture).not.toHaveBeenCalled();
    expect(element.enAttenteEnvoi).toBe(false);
    expect(element.shadowRoot.textContent).not.toContain('repartira');
  });

  it('montre « ça repartira » seulement pour une vraie attente réseau', async () => {
    const element = monter(PRODUIT_G);
    element.file = {
      ajouter: () => ({ cle: 'k', sort: Promise.resolve('en-attente') }),
      rejouer: async () => undefined,
    };
    await element.updateComplete;
    await element.updateComplete;
    element.quantite = 80;
    await element.enregistrer();
    await element.updateComplete;
    expect(element.shadowRoot.textContent).toContain('repartira');
  });

  it('affiche la DLC à la française plutôt qu’au format brut du serveur', async () => {
    const element = monter({ ...PRODUIT_G, next_batch: { id: 7, remaining: 500, best_before: '2026-09-01' } });
    await element.updateComplete;
    await element.updateComplete;
    expect(element.shadowRoot.textContent).toContain('01/09/2026');
    expect(element.shadowRoot.textContent).not.toContain('2026-09-01');
  });
});

/** L'emballage tel que `home_stock/product/get` le rend depuis le lot 2bis. */
const EMBALLAGE = { bins: ['yellow', 'glass'], materials: ['en:pp-polypropylene', 'en:glass'] };

describe('<home-stock-consommation> — la consigne de tri', () => {
  beforeEach(() => { document.body.innerHTML = ''; });

  async function monterAvecEmballage(reponse: unknown = { ...PRODUIT_G, packaging: EMBALLAGE }) {
    const element = monter(reponse);
    await element.updateComplete;
    await element.updateComplete;
    return element;
  }

  it('s’affiche sur « Jeté » et sur « Périmé »', async () => {
    for (const motif of ['waste', 'expired'] as const) {
      document.body.innerHTML = '';
      const element = await monterAvecEmballage();
      element.motif = motif;
      await element.updateComplete;
      expect(element.shadowRoot.textContent).toContain('Bac jaune et bac à verre');
    }
  });

  it('s’affiche quand la quantité choisie vide le lot visé', async () => {
    const element = await monterAvecEmballage();
    element.choisirRaccourci(500);
    await element.updateComplete;
    expect(element.shadowRoot.textContent).toContain('Bac jaune et bac à verre');
  });

  it('s’affiche pour une saisie manuelle supérieure au reste', async () => {
    const element = await monterAvecEmballage();
    element.saisirQuantite('600');
    await element.updateComplete;
    expect(element.shadowRoot.textContent).toContain('Bac jaune et bac à verre');
  });

  it('reste absente sur une sortie partielle en « Mangé »', async () => {
    // Au rangement comme à la bouchée, l'emballage est encore plein : le bon
    // moment est le rebut, pas la mise au placard.
    const element = await monterAvecEmballage();
    element.choisirRaccourci(80);
    await element.updateComplete;
    expect(element.shadowRoot.textContent).not.toContain('Bac jaune');
  });

  it('reste absente quand le serveur ne connaît pas l’emballage', async () => {
    const element = await monterAvecEmballage({ ...PRODUIT_G, packaging: null });
    element.motif = 'waste';
    await element.updateComplete;
    expect(element.shadowRoot.textContent).not.toContain('Bac');
  });

  it('reste absente quand la liste des bacs est vide', async () => {
    const element = await monterAvecEmballage({ ...PRODUIT_G, packaging: { bins: [], materials: [] } });
    element.motif = 'waste';
    await element.updateComplete;
    expect(element.shadowRoot.textContent).not.toContain('Bac');
  });

  it('dit « Ma portion » quand la portion vient d’une saisie', async () => {
    const element = await monterAvecEmballage({
      ...PRODUIT_G, suggested_portion: 45, portion_source: 'manual' });
    const libelles = [...element.shadowRoot.querySelectorAll('.raccourci')]
      .map((b: Element) => b.textContent?.trim());
    expect(libelles[0]).toContain('Ma portion (45 g)');
  });
});
