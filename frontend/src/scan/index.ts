import { ScannerCompanion } from './companion';
import { ScannerNavigateur } from './navigateur';

export type Scanner = {
  disponible(): boolean;
  lire(): Promise<string | null>;
};

/** Le clavier : ni caméra système, ni BarcodeDetector. La saisie est faite par
 *  l'écran appelant ; ce scanner-là ne fait que dire « à toi de jouer ». */
export class ScannerClavier implements Scanner {
  disponible(): boolean { return true; }
  async lire(): Promise<string | null> { return null; }
}

/** L'application HA d'abord, le navigateur ensuite, le clavier en dernier. */
export function choisirScanner(fenetre: Window | any): Scanner {
  const companion = new ScannerCompanion(fenetre);
  if (companion.disponible()) return companion;
  const navigateur = new ScannerNavigateur(fenetre);
  if (navigateur.disponible()) return navigateur;
  return new ScannerClavier();
}
