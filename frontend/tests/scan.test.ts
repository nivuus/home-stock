import { describe, expect, it, vi } from 'vitest';
import { choisirScanner } from '../src/scan';
import { ScannerCompanion, DELAI_REPONSE_MS } from '../src/scan/companion';

function fenetreAvecCompanion(): any {
  return {
    externalApp: { externalBus: vi.fn() },
    BarcodeDetector: undefined,
  };
}

function fenetreNavigateur(): any {
  return { BarcodeDetector: class {}, navigator: { mediaDevices: {} } };
}

describe('choix du scanner', () => {
  it('préfère l’application Home Assistant quand elle est là', () => {
    expect(choisirScanner(fenetreAvecCompanion()).constructor.name)
      .toBe('ScannerCompanion');
  });

  it('retombe sur BarcodeDetector dans un navigateur ordinaire', () => {
    expect(choisirScanner(fenetreNavigateur()).constructor.name)
      .toBe('ScannerNavigateur');
  });

  it('retombe sur le clavier quand ni l’un ni l’autre n’existe', () => {
    expect(choisirScanner({} as any).constructor.name).toBe('ScannerClavier');
  });

  it('choisit l’application HA même quand BarcodeDetector est AUSSI disponible : la '
     + 'priorité n’est vraie que si elle tient face à un choix, pas seulement en son absence', () => {
    const fenetre: any = {
      externalApp: { externalBus: vi.fn() }, BarcodeDetector: class {},
      navigator: { mediaDevices: {} },
    };
    expect(choisirScanner(fenetre).constructor.name).toBe('ScannerCompanion');
  });
});

describe('scanner de l’application Home Assistant', () => {
  it('rend le code lu par l’appareil photo du système', async () => {
    const fenetre: any = { externalApp: { externalBus: vi.fn() } };
    const scanner = new ScannerCompanion(fenetre);

    const promesse = scanner.lire();
    fenetre.externalBus({ command: 'bar_code/scan_result',
                          payload: { rawValue: '3229820129488', format: 'ean_13' } });

    expect(await promesse).toBe('3229820129488');
  });

  it('rend null quand l’utilisateur annule', async () => {
    const fenetre: any = { externalApp: { externalBus: vi.fn() } };
    const scanner = new ScannerCompanion(fenetre);

    const promesse = scanner.lire();
    fenetre.externalBus({ command: 'bar_code/aborted', payload: { reason: 'canceled' } });

    expect(await promesse).toBeNull();
  });

  it('ferme le scanner du système après une lecture', async () => {
    const envoyes: any[] = [];
    const fenetre: any = { externalApp: { externalBus: (m: string) => envoyes.push(JSON.parse(m)) } };
    const scanner = new ScannerCompanion(fenetre);

    const promesse = scanner.lire();
    fenetre.externalBus({ command: 'bar_code/scan_result', payload: { rawValue: '1' } });
    await promesse;

    expect(envoyes.map((m) => m.type)).toContain('bar_code/close');
  });

  it('rend null si l’application ne répond jamais, plutôt que de bloquer le bouton pour toujours', async () => {
    vi.useFakeTimers();
    try {
      const fenetre: any = { externalApp: { externalBus: vi.fn() } };
      const scanner = new ScannerCompanion(fenetre);

      const promesse = scanner.lire();
      expect(fenetre.externalBus).toBeTypeOf('function'); // le scan a bien pris la main sur le bus

      await vi.advanceTimersByTimeAsync(DELAI_REPONSE_MS);

      expect(await promesse).toBeNull();
      // Le bus doit être rendu — sinon il reste accroché à une lecture qui
      // n'aboutira jamais, et le prochain scan ne recevrait plus rien.
      expect(fenetre.externalBus).toBeUndefined();
    } finally {
      vi.useRealTimers();
    }
  });
});
