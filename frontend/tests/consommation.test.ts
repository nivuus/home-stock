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
});
