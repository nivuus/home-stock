import { afterEach, describe, expect, it, vi } from 'vitest';
import '../src/ecrans/ticket';
import type { DonneesTicket } from '../src/ecrans/ticket';

function ligneLue(partiel: Partial<DonneesTicket['lines'][number]> & { id: number }) {
  return {
    receipt_id: 1, position: partiel.id, label: `LIGNE ${partiel.id}`,
    quantity: 1, unit_price: 1.05, total_price: 1.05, line_id: null,
    article_id: null, match_state: 'unmatched' as const, applied_at: null,
    candidates: [],
    ...partiel,
  };
}

function ligneChariot(id: number, label: string) {
  return { id, article_label: label, product_name: label, quantity: 1,
           unit_price: 1.0, base_unit: 'ml', brand: null };
}

function ticket(partiel: Partial<DonneesTicket> = {}): DonneesTicket {
  return {
    id: 1, session_id: 1, media_content_id: 'media-source://media_source/local/t.jpg',
    captured_at: '2026-08-21T20:00:00', state: 'read', store_id: 1,
    purchased_on: '2026-08-21', total: 2.10, agent_entity_id: 'ai_task.gemini',
    read_at: '2026-08-21T20:00:10', attempts: 1, error: null, raw: '{}',
    lines: [ligneLue({ id: 1 })], cart_lines: [ligneChariot(10, 'Lait 1 L')],
    lines_total: 2.10, total_gap: null,
    ...partiel,
  };
}

function fausseFile() {
  return { ajouter: vi.fn().mockReturnValue({ cle: 'k', sort: Promise.resolve('envoyee') }),
           rejouer: vi.fn().mockResolvedValue(undefined) };
}

function monter(props: {
  ticket?: DonneesTicket | null;
  agentConfigure?: boolean;
  file?: ReturnType<typeof fausseFile>;
  televerser?: ReturnType<typeof vi.fn>;
  enAttente?: number;
} = {}) {
  const element = document.createElement('home-stock-ticket') as HTMLElement & {
    ticket: DonneesTicket | null; agentConfigure: boolean; file?: unknown;
    televerser?: unknown; enAttente: number; updateComplete: Promise<boolean>;
  };
  element.ticket = props.ticket ?? null;
  element.agentConfigure = props.agentConfigure ?? true;
  if (props.file) element.file = props.file;
  if (props.televerser) element.televerser = props.televerser;
  element.enAttente = props.enAttente ?? 0;
  document.body.appendChild(element);
  return element;
}

function fichier() {
  return new File(['x'], 'ticket.jpg', { type: 'image/jpeg' });
}

async function deposer(element: HTMLElement & { updateComplete: Promise<boolean> }) {
  const champ = element.shadowRoot!.querySelector('.photo') as HTMLInputElement;
  Object.defineProperty(champ, 'files', { value: [fichier()], configurable: true });
  champ.dispatchEvent(new Event('change'));
  await element.updateComplete;
  await Promise.resolve();
  await Promise.resolve();
  await element.updateComplete;
}

describe('<home-stock-ticket>', () => {
  afterEach(() => { document.body.innerHTML = ''; });

  it('affiche « aucune entité de lecture configurée » plutôt qu’un bouton mort', async () => {
    const element = monter({ ticket: null, agentConfigure: false });
    await element.updateComplete;
    expect(element.shadowRoot!.textContent).toContain('Aucune entité de lecture');
    expect(element.shadowRoot!.querySelector('.photo')).toBeNull();
  });

  it('téléverse la photo puis envoie le media_content_id', async () => {
    const file = fausseFile();
    const televerser = vi.fn().mockResolvedValue(
      'media-source://media_source/local/home_stock/receipts/a.jpg');
    const element = monter({ ticket: null, file, televerser });
    await element.updateComplete;

    await deposer(element);

    expect(televerser).toHaveBeenCalled();
    expect(file.ajouter).toHaveBeenCalledWith('home_stock/receipt/submit', {
      media_content_id: 'media-source://media_source/local/home_stock/receipts/a.jpg',
    });
  });

  it('affiche un 403 en français et n’envoie rien', async () => {
    const file = fausseFile();
    const televerser = vi.fn().mockRejectedValue(new Error('403'));
    const element = monter({ ticket: null, file, televerser });
    await element.updateComplete;

    await deposer(element);

    expect(element.shadowRoot!.querySelector('.erreur')!.textContent)
      .toContain('administrateur');
    expect(file.ajouter).not.toHaveBeenCalled();
  });

  it('traduit un refus de taille ou de type', async () => {
    const televerser = vi.fn().mockRejectedValue(new Error('413'));
    const element = monter({ ticket: null, file: fausseFile(), televerser });
    await element.updateComplete;
    await deposer(element);
    expect(element.shadowRoot!.querySelector('.erreur')!.textContent).toContain('20 Mo');
  });

  it('affiche l’état de lecture : en attente, lu, échoué', async () => {
    for (const [etat, attendu] of [['pending', 'Lecture en cours'],
                                   ['read', 'Ticket lu'],
                                   ['failed', 'Lecture impossible']] as const) {
      const element = monter({ ticket: ticket({ state: etat }) });
      await element.updateComplete;
      expect(element.shadowRoot!.querySelector('.etat')!.textContent).toContain(attendu);
      element.remove();
    }
  });

  it('affiche l’erreur du modèle en français, telle qu’elle est stockée', async () => {
    const element = monter({ ticket: ticket({ state: 'failed',
                                              error: 'Le délai a été dépassé.' }) });
    await element.updateComplete;
    expect(element.shadowRoot!.querySelector('.erreur')!.textContent)
      .toContain('Le délai a été dépassé.');
  });

  it('met les lignes lues face aux lignes de panier', async () => {
    const element = monter({ ticket: ticket({
      lines: [ligneLue({ id: 1, label: 'LT DEMI ECR 1L', line_id: 10,
                         match_state: 'auto' })],
      cart_lines: [ligneChariot(10, 'Lait 1 L')],
    }) });
    await element.updateComplete;

    const ligne = element.shadowRoot!.querySelector('.ligne-ticket')!;
    expect(ligne.textContent).toContain('LT DEMI ECR 1L');
    expect(ligne.textContent).toContain('Lait 1 L');
  });

  it('rapproche une ligne en un appui, et l’ignore en un appui', async () => {
    const file = fausseFile();
    const element = monter({ file, ticket: ticket({
      lines: [ligneLue({ id: 1, candidates: [{ line_id: 10, label: 'Lait 1 L', score: 0.9 }] })],
    }) });
    await element.updateComplete;

    (element.shadowRoot!.querySelector('.rapprocher') as HTMLButtonElement).click();
    expect(file.ajouter).toHaveBeenCalledWith('home_stock/receipt/line/match',
      { line_id: 1, shopping_line_id: 10, state: 'confirmed' });

    (element.shadowRoot!.querySelector('.ignorer') as HTMLButtonElement).click();
    expect(file.ajouter).toHaveBeenCalledWith('home_stock/receipt/line/match',
      { line_id: 1, shopping_line_id: null, state: 'ignored' });
  });

  it('affiche l’écart au total quand il dépasse 2 %', async () => {
    const element = monter({ ticket: ticket({ total: 20, lines_total: 2.10,
                                              total_gap: 17.9 }) });
    await element.updateComplete;
    expect(element.shadowRoot!.querySelector('.ecart')!.textContent).toContain('17,90 €');
  });

  it('n’affiche aucun écart quand la somme tombe juste', async () => {
    const element = monter({ ticket: ticket({ total_gap: null }) });
    await element.updateComplete;
    expect(element.shadowRoot!.querySelector('.ecart')).toBeNull();
  });

  it('demande deux appuis pour appliquer', async () => {
    const file = fausseFile();
    const element = monter({ file, ticket: ticket() });
    await element.updateComplete;

    (element.shadowRoot!.querySelector('.appliquer') as HTMLButtonElement).click();
    await element.updateComplete;
    expect(file.ajouter).not.toHaveBeenCalled();

    (element.shadowRoot!.querySelector('.confirmer-application') as HTMLButtonElement).click();
    expect(file.ajouter).toHaveBeenCalledWith('home_stock/receipt/apply', { receipt_id: 1 });
  });

  it('annonce le nombre de contrepassations avant d’appliquer', async () => {
    const element = monter({ ticket: ticket({
      lines: [ligneLue({ id: 1, line_id: 10, match_state: 'auto' })],
      cart_lines: [{ ...ligneChariot(10, 'Lait 1 L'), stored_at: '2026-08-21T21:00:00',
                     movements: 3 }],
    }) });
    await element.updateComplete;

    (element.shadowRoot!.querySelector('.appliquer') as HTMLButtonElement).click();
    await element.updateComplete;

    expect(element.shadowRoot!.querySelector('.avertissement')!.textContent)
      .toContain('3 mouvements');
  });

  it('dit « aucun mouvement déjà écrit » quand il n’y en a pas', async () => {
    const element = monter({ ticket: ticket() });
    await element.updateComplete;
    (element.shadowRoot!.querySelector('.appliquer') as HTMLButtonElement).click();
    await element.updateComplete;
    expect(element.shadowRoot!.querySelector('.avertissement')!.textContent)
      .toContain('Aucun mouvement déjà écrit');
  });

  it('laisse les lignes non rapprochées visibles et propose de scanner', async () => {
    const element = monter({ ticket: ticket({
      lines: [ligneLue({ id: 1, label: 'SAC CABAS' })], cart_lines: [] }) });
    await element.updateComplete;

    const ligne = element.shadowRoot!.querySelector('.ligne-ticket')!;
    expect(ligne.textContent).toContain('SAC CABAS');
    expect(ligne.textContent).toContain('Scanner l’article');
  });

  it('ne propose jamais de créer un article depuis un libellé de caisse', async () => {
    const element = monter({ ticket: ticket({
      lines: [ligneLue({ id: 1, label: 'SAC CABAS' })], cart_lines: [] }) });
    await element.updateComplete;
    const texte = element.shadowRoot!.textContent!;
    expect(texte).not.toContain('Créer l’article');
    expect(texte).not.toContain('Créer le produit');
  });

  it('permet de réessayer une lecture échouée', async () => {
    const file = fausseFile();
    const element = monter({ file, ticket: ticket({ state: 'failed',
                                                    error: 'Délai dépassé.' }) });
    await element.updateComplete;

    (element.shadowRoot!.querySelector('.reessayer') as HTMLButtonElement).click();

    expect(file.ajouter).toHaveBeenCalledWith('home_stock/receipt/retry',
      { receipt_id: 1 });
  });

  it('n’ajoute pas de hauteur : un bandeau REMPLACE un bloc, il ne s’ajoute pas', async () => {
    const element = monter({ ticket: ticket() });
    await element.updateComplete;
    const avant = element.shadowRoot!.querySelectorAll('.bloc-principal').length;

    (element.shadowRoot!.querySelector('.appliquer') as HTMLButtonElement).click();
    await element.updateComplete;

    expect(element.shadowRoot!.querySelectorAll('.bloc-principal').length).toBe(avant);
  });

  it('affiche le nombre d’envois en attente', async () => {
    const element = monter({ ticket: ticket(), enAttente: 2 });
    await element.updateComplete;
    expect(element.shadowRoot!.querySelector('.en-attente')!.textContent)
      .toContain('2 envois');
  });
});

// --- lot 6 : le rapprochement côte à côte -----------------------------------
//
// Le brief demandait « la photo à gauche, les lignes à droite ». Le panneau
// n'a JAMAIS affiché la photo d'un ticket : `DonneesTicket` ne porte qu'un
// `media_content_id`, un identifiant de source média que le navigateur ne sait
// pas charger tel quel. Ce qu'on compare vraiment en rapprochant, c'est le
// TEXTE LU (`raw`) contre les lignes — et lui existe. C'est donc lui qui passe
// à gauche.

function monterTicket(options: { large: boolean; ticket?: DonneesTicket;
                                 file?: ReturnType<typeof fausseFile> }) {
  const element = monter({ ticket: options.ticket ?? ticket({
    raw: 'LECLERC\nLAIT 1L      1,05\nPAIN         1,05\nTOTAL        2,10',
    lines: [ligneLue({ id: 1, candidates: [{ line_id: 10, label: 'Lait 1 L', score: 0.9 }] }),
            ligneLue({ id: 2 })],
  }), file: options.file }) as HTMLElement & { large: boolean; updateComplete: Promise<boolean> };
  element.large = options.large;
  return element;
}

describe('<home-stock-ticket> : la vue dense (lot 6)', () => {
  afterEach(() => { document.body.innerHTML = ''; });

  it('montre le texte lu et les lignes en même temps au-delà de 1000 px', async () => {
    const e = monterTicket({ large: true });
    await e.updateComplete;
    expect(e.shadowRoot!.querySelector('.deux-volets')).not.toBeNull();
    expect(e.shadowRoot!.querySelector('.volet-ticket')!.textContent)
      .toContain('LAIT 1L');
    expect(e.shadowRoot!.querySelectorAll('.ligne-ticket')).toHaveLength(2);
  });

  it('reste empilé en étroit', async () => {
    const e = monterTicket({ large: false });
    await e.updateComplete;
    expect(e.shadowRoot!.querySelector('.deux-volets')).toBeNull();
    expect(e.shadowRoot!.querySelectorAll('.ligne-ticket')).toHaveLength(2);
  });

  it('garde le volet du ticket lisible : il ne prend jamais la moitié de la largeur', async () => {
    // Un ticket de caisse est haut et étroit. Lui donner la moitié d'un
    // 1920 px l'étirerait en lignes illisibles et écraserait les lignes
    // rapprochées, qui sont le vrai travail de cet écran.
    const styles = (customElements.get('home-stock-ticket') as any).styles;
    const css = [styles].flat().map((s: any) => s.cssText).join('\n');
    expect(css).toContain('.deux-volets');
    expect(css).toMatch(/\.deux-volets\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*\d+px\)/);
  });

  it('rapproche une ligne sans faire disparaître le texte lu', async () => {
    const file = fausseFile();
    const e = monterTicket({ large: true, file });
    await e.updateComplete;
    const avant = e.shadowRoot!.querySelector('.volet-ticket')!.textContent;

    (e.shadowRoot!.querySelector('.rapprocher') as HTMLButtonElement).click();
    await e.updateComplete;

    expect(file.ajouter).toHaveBeenCalled();
    expect(e.shadowRoot!.querySelector('.volet-ticket')!.textContent).toBe(avant);
  });

  it('dit ce qu’il en est quand le ticket n’a pas encore été lu', async () => {
    // Pas de texte brut : le volet gauche ne reste pas vide sans explication.
    const e = monterTicket({ large: true, ticket: ticket({ raw: null, state: 'pending' }) });
    await e.updateComplete;
    expect(e.shadowRoot!.querySelector('.volet-ticket')!.textContent!.trim()).not.toBe('');
  });
});
