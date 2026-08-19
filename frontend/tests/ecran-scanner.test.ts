import { afterEach, describe, expect, it, vi } from 'vitest';
import '../src/ecrans/scanner';

function laisserPasserLesMicrotaches(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

function creer(fenetre: any) {
  const element = document.createElement('home-stock-scanner') as HTMLElement & {
    fenetre: any; updateComplete: Promise<boolean>;
  };
  element.fenetre = fenetre;
  document.body.appendChild(element);
  return element;
}

afterEach(() => {
  document.body.innerHTML = '';
});

describe('écran scanner : choix de la voie de scan au clic', () => {
  it('émet code-lu tout de suite quand l’application HA rend un code', async () => {
    const fenetre: any = { externalApp: { externalBus: vi.fn() } };
    const el = creer(fenetre);
    await el.updateComplete;

    const recu = vi.fn();
    el.addEventListener('code-lu', (e) => recu((e as CustomEvent).detail));

    el.shadowRoot!.querySelector<HTMLButtonElement>('.bouton-scan')!.click();
    await laisserPasserLesMicrotaches();
    fenetre.externalBus({ command: 'bar_code/scan_result', payload: { rawValue: '123' } });
    await laisserPasserLesMicrotaches();

    expect(recu).toHaveBeenCalledWith({ code: '123' });
  });

  it('n’émet rien quand l’utilisateur annule le scan', async () => {
    const fenetre: any = { externalApp: { externalBus: vi.fn() } };
    const el = creer(fenetre);
    await el.updateComplete;

    const recu = vi.fn();
    el.addEventListener('code-lu', recu);

    el.shadowRoot!.querySelector<HTMLButtonElement>('.bouton-scan')!.click();
    await laisserPasserLesMicrotaches();
    fenetre.externalBus({ command: 'bar_code/aborted', payload: {} });
    await laisserPasserLesMicrotaches();

    expect(recu).not.toHaveBeenCalled();
  });

  it('ouvre la saisie manuelle directement quand ni l’appli ni BarcodeDetector n’existent', async () => {
    const el = creer({});
    await el.updateComplete;

    el.shadowRoot!.querySelector<HTMLButtonElement>('.bouton-scan')!.click();
    await el.updateComplete;

    expect(el.shadowRoot!.querySelector('.saisie-manuelle')).not.toBeNull();
  });

  it('émet code-lu à la validation de la saisie manuelle', async () => {
    const el = creer({});
    await el.updateComplete;
    el.shadowRoot!.querySelector<HTMLButtonElement>('.bouton-saisie')!.click();
    await el.updateComplete;

    const champ = el.shadowRoot!.querySelector<HTMLInputElement>('.champ-code')!;
    champ.value = '3229820129488';
    champ.dispatchEvent(new Event('input'));
    await el.updateComplete;

    const recu = vi.fn();
    el.addEventListener('code-lu', (e) => recu((e as CustomEvent).detail));
    el.shadowRoot!.querySelector<HTMLButtonElement>('.valider-saisie')!.click();

    expect(recu).toHaveBeenCalledWith({ code: '3229820129488' });
  });

  it('affiche la bannière de session avec le magasin quand une session est ouverte', async () => {
    const element = document.createElement('home-stock-scanner') as HTMLElement & {
      fenetre: any; session: any; updateComplete: Promise<boolean>;
    };
    element.fenetre = {};
    element.session = { store: 'Leclerc' };
    document.body.appendChild(element);
    await element.updateComplete;

    expect(element.shadowRoot!.querySelector('.session-banniere')!.textContent).toContain('Leclerc');
  });

  it('n’affiche aucune bannière hors session', async () => {
    const el = creer({});
    await el.updateComplete;
    expect(el.shadowRoot!.querySelector('.session-banniere')).toBeNull();
  });
});
