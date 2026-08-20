/** Le scanner natif de l'application Home Assistant.
 *
 *  C'est l'appareil photo du système, pas une WebView : mise au point, torche,
 *  lecture en rafale. Le dialogue passe par le bus externe de l'application —
 *  `bar_code/scan` à l'aller, `bar_code/scan_result` / `bar_code/aborted` au
 *  retour, `bar_code/close` pour refermer.
 */
import type { Scanner } from './index';

/** Si l'application ne répond jamais (fermée en tâche de fond, bus perdu),
 *  le bouton de scan ne doit pas rester mort pour le reste de la session. */
export const DELAI_REPONSE_MS = 60_000;

export class ScannerCompanion implements Scanner {
  readonly voie = 'companion' as const;

  constructor(private fenetre: any) {}

  disponible(): boolean {
    return Boolean(this.fenetre?.externalApp?.externalBus
      || this.fenetre?.webkit?.messageHandlers?.externalBus);
  }

  lire(): Promise<string | null> {
    return new Promise((resoudre) => {
      const precedent = this.fenetre.externalBus;
      let repondu = false;
      const finir = (valeur: string | null): void => {
        if (repondu) return;
        repondu = true;
        clearTimeout(delai);
        this.fenetre.externalBus = precedent;
        resoudre(valeur);
      };
      const delai = setTimeout(() => finir(null), DELAI_REPONSE_MS);
      this.fenetre.externalBus = (message: any) => {
        const evenement = typeof message === 'string' ? JSON.parse(message) : message;
        if (evenement.command === 'bar_code/scan_result') {
          this.envoyer({ type: 'bar_code/close' });
          finir(String(evenement.payload.rawValue));
        } else if (evenement.command === 'bar_code/aborted'
                   || evenement.command === 'bar_code/close') {
          finir(null);
        }
        return true;
      };
      this.envoyer({
        type: 'bar_code/scan',
        payload: {
          title: 'Scanner un article',
          description: 'Visez le code-barres',
          alternative_option_label: 'Saisir le code',
        },
      });
    });
  }

  private envoyer(message: object): void {
    const brut = JSON.stringify(message);
    if (this.fenetre.externalApp?.externalBus) {
      this.fenetre.externalApp.externalBus(brut);
    } else {
      this.fenetre.webkit.messageHandlers.externalBus.postMessage(message);
    }
  }
}
