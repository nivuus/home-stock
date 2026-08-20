import { ScannerCompanion } from './companion';
import { ScannerNavigateur } from './navigateur';

/** La voie de lecture qu'un scanner représente.
 *
 *  Déclarée en donnée, jamais déduite du nom de la classe : le build de
 *  production passe par `terser`, qui renomme les classes. `scanner.
 *  constructor.name === 'ScannerClavier'` était donc toujours faux dans le
 *  bundle déployé — sur un appareil sans bus companion ni `BarcodeDetector`,
 *  le plus gros bouton de l'écran ne faisait alors strictement rien, sans
 *  erreur ni pavé de saisie. Invisible en vitest comme au vérificateur de
 *  rendu, qui construisent tous deux sans minification. */
export type VoieDeScan = 'companion' | 'navigateur' | 'clavier';

export type Scanner = {
  readonly voie: VoieDeScan;
  disponible(): boolean;
  lire(): Promise<string | null>;
};

/** Le clavier : ni caméra système, ni BarcodeDetector. La saisie est faite par
 *  l'écran appelant ; ce scanner-là ne fait que dire « à toi de jouer ». */
export class ScannerClavier implements Scanner {
  readonly voie = 'clavier' as const;
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
