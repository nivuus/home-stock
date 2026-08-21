import { beforeEach, describe, expect, it, vi } from 'vitest';
import '../src/ecrans/reglages';

/** Un rapport de contrôle tel que `home_stock/migration/check` le rend :
 *  un bloquant, un « rien mesuré », un à acquitter, et le reste au vert. */
const RAPPORT = {
  ok: false,
  blocking: ['C0', 'C1', 'C4'],
  archive_path: null,
  checks: [
    { code: 'C0', label: 'Schéma et gel de Grocy', grocy_count: 0, home_count: 0,
      gap: 0, verdict: 'empty', blocking: true,
      details: ['la copie de grocy.db est introuvable'] },
    { code: 'C1', label: 'Un lot par ligne de stock', grocy_count: 108,
      home_count: 107, gap: 1, verdict: 'gap', blocking: true,
      details: ['grocy:stock:541 (Sorbet Fraise) : aucun lot importé'] },
    { code: 'C2', label: 'Les quantités', grocy_count: 108, home_count: 108,
      gap: 0, verdict: 'ok', blocking: false, details: [] },
    { code: 'C3', label: 'Les dates', grocy_count: 108, home_count: 98,
      gap: 0, verdict: 'ok', blocking: false, details: [] },
    { code: 'C4', label: 'Les prix écartés', grocy_count: 7, home_count: 92,
      gap: 0, verdict: 'unacknowledged', blocking: true,
      details: ['grocy:stock:419 : prix écarté'] },
    { code: 'C5', label: "Un mouvement d'entrée par lot", grocy_count: 108,
      home_count: 108, gap: 0, verdict: 'ok', blocking: false, details: [] },
    { code: 'C6', label: 'Les trois cumuls', grocy_count: 108, home_count: 108,
      gap: 0, verdict: 'ok', blocking: false, details: [] },
    { code: 'C7', label: 'Piles et équipements', grocy_count: 34,
      home_count: 34, gap: 0, verdict: 'ok', blocking: false, details: [] },
    { code: 'C8', label: 'Recettes', grocy_count: 102, home_count: 102,
      gap: 0, verdict: 'ok', blocking: false, details: [] },
    { code: 'C9', label: 'Les images', grocy_count: 82, home_count: 82,
      gap: 0, verdict: 'ok', blocking: false, details: [] },
    { code: 'C10', label: 'Planning et liste', grocy_count: 42, home_count: 42,
      gap: 0, verdict: 'ok', blocking: false, details: [] },
    { code: 'C11', label: 'Ce qui lit encore Grocy', grocy_count: 0,
      home_count: 0, gap: 0, verdict: 'ok', blocking: false, details: [] },
  ],
};

function monter(options: { rapport?: unknown; erreur?: unknown } = {}) {
  const appeler = vi.fn(async (type: string) => {
    if (type === 'home_stock/migration/check') {
      if (options.erreur) throw options.erreur;
      return options.rapport ?? RAPPORT;
    }
    if (type === 'home_stock/aisles/list') return { aisles: [] };
    if (type === 'home_stock/locations/list') return { locations: [] };
    if (type === 'home_stock/stores/list') return { stores: [] };
    if (type === 'home_stock/recurring/list') return { recurring: [] };
    return {};
  });
  const element = document.createElement('home-stock-reglages') as any;
  element.connexion = { appeler, appelerService: vi.fn(async () => {}) };
  element.file = { ajouter: vi.fn(), rejouer: vi.fn(async () => {}) };
  document.body.append(element);
  return { element, appeler };
}

const attendre = async (element: any) => {
  for (let tour = 0; tour < 6; tour += 1) {
    await Promise.resolve();
    await element.updateComplete;
  }
};
const texte = (element: any) => element.shadowRoot.textContent as string;
const noeuds = (element: any, selecteur: string) =>
  Array.from(element.shadowRoot.querySelectorAll(selecteur)) as HTMLElement[];

async function controler(options: Parameters<typeof monter>[0] = {}) {
  const { element, appeler } = monter(options);
  await attendre(element);
  (element.shadowRoot.querySelector('.controler') as HTMLElement).click();
  await attendre(element);
  return { element, appeler };
}

describe('le bloc Bascule', () => {
  beforeEach(() => { document.body.innerHTML = ''; });

  it('affiche les douze lignes de contrôle', async () => {
    const { element } = await controler();
    expect(noeuds(element, '.controle')).toHaveLength(12);
    expect(texte(element)).toContain('C0');
    expect(texte(element)).toContain('C11');
  });

  it('met en rouge une ligne bloquante et elle seule', async () => {
    const { element } = await controler();
    const bloquantes = noeuds(element, '.controle.bloquant')
      .map((n) => n.dataset.code);
    expect(bloquantes).toEqual(['C0', 'C1', 'C4']);
  });

  it("affiche l'écart chiffré des deux côtés", async () => {
    // 108 chez Grocy, 107 chez nous, écart 1 : les trois nombres sont
    // visibles, parce qu'un « écart : 1 » sans ses deux termes ne dit pas
    // de quel côté il manque quelque chose.
    const { element } = await controler();
    const ligne = noeuds(element, '.controle')
      .find((n) => n.dataset.code === 'C1')!;
    expect(ligne.textContent).toContain('108');
    expect(ligne.textContent).toContain('107');
    expect(ligne.textContent).toContain('1');
  });

  it("dit qu'un contrôle n'a rien mesuré, au lieu d'afficher « écart : 0 »", async () => {
    // Le verdict "empty" ne se rend JAMAIS comme un succès. C'est la leçon
    // du lot 6, portée jusque dans le rendu.
    const { element } = await controler();
    const ligne = noeuds(element, '.controle')
      .find((n) => n.dataset.code === 'C0')!;
    expect(ligne.textContent).toContain('rien mesuré');
    expect(ligne.textContent).not.toContain('écart : 0');
    expect(ligne.classList.contains('bloquant')).toBe(true);
  });

  it("n'offre aucun bouton d'import", async () => {
    // Un import de masse se lance depuis Outils de développement, une fois.
    const { element } = await controler();
    const libelles = noeuds(element, 'button').map((n) => n.textContent ?? '');
    expect(libelles.some((l) => /importer/i.test(l))).toBe(false);
  });

  it("n'offre aucun bouton d'extinction", async () => {
    // Arrêter un conteneur de la maison est un geste humain. Le panneau ne
    // doit même pas suggérer que c'est un clic.
    const { element } = await controler();
    expect(texte(element)).not.toMatch(/éteindre|arrêter Grocy|docker/i);
  });

  it("affiche « à acquitter » sans offrir d'acquitter en un geste", async () => {
    // L'acquittement est nominatif et passe par le service. Un bouton
    // « tout va bien » finit toujours par être pressé sans regarder.
    const { element } = await controler();
    const ligne = noeuds(element, '.controle')
      .find((n) => n.dataset.code === 'C4')!;
    expect(ligne.textContent).toContain('à acquitter');
    const libelles = noeuds(element, 'button').map((n) => n.textContent ?? '');
    expect(libelles.some((l) => /acquitter|tout va bien/i.test(l))).toBe(false);
  });

  it('ne casse pas la hauteur quand le rapport est absent', async () => {
    const { element } = monter();
    await attendre(element);
    expect(noeuds(element, '.controle')).toHaveLength(0);
    expect(texte(element)).toContain('Bascule');
    expect(element.shadowRoot.querySelector('.controler')).not.toBeNull();
  });

  it("affiche un état d'attente pendant le contrôle", async () => {
    let liberer: (valeur: unknown) => void = () => {};
    const appeler = vi.fn(async (type: string) => {
      if (type === 'home_stock/migration/check') {
        return new Promise((resolve) => { liberer = resolve; });
      }
      return { aisles: [], locations: [], stores: [], recurring: [] };
    });
    const element = document.createElement('home-stock-reglages') as any;
    element.connexion = { appeler, appelerService: vi.fn(async () => {}) };
    element.file = { ajouter: vi.fn(), rejouer: vi.fn(async () => {}) };
    document.body.append(element);
    await attendre(element);
    (element.shadowRoot.querySelector('.controler') as HTMLElement).click();
    await attendre(element);
    expect(texte(element)).toContain('Contrôle en cours');
    liberer(RAPPORT);
    await attendre(element);
    expect(texte(element)).not.toContain('Contrôle en cours');
  });

  it('rend lisible une erreur de service en français', async () => {
    const { element } = await controler({ erreur: new Error('boom') });
    expect(texte(element)).toContain("Le contrôle n'a pas pu être lancé.");
    expect(texte(element)).not.toContain('boom');
  });

  it('dit en une ligne si la bascule est prête', async () => {
    const { element } = await controler();
    expect(texte(element)).toContain('3 contrôles bloquants');
  });
});
