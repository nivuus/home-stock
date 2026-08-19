/** `BarcodeDetector` sur le flux de la caméra. Exige un contexte sécurisé,
 *  ce que home.allanic.me fournit. */
import type { Scanner } from './index';

const FORMATS = ['ean_13', 'ean_8', 'upc_a', 'upc_e', 'code_128'];

export class ScannerNavigateur implements Scanner {
  private flux?: MediaStream;

  constructor(private fenetre: any) {}

  disponible(): boolean {
    return Boolean(this.fenetre?.BarcodeDetector
      && this.fenetre?.navigator?.mediaDevices);
  }

  async lire(): Promise<string | null> {
    const detecteur = new this.fenetre.BarcodeDetector({ formats: FORMATS });
    this.flux = await this.fenetre.navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'environment' },
    });
    const video = this.fenetre.document.createElement('video');
    video.srcObject = this.flux;
    await video.play();

    try {
      // Une lecture par image : un code-barres flou n'est lu qu'au bout de
      // quelques images, et rendre la main trop tôt ferait clignoter l'écran.
      for (let essai = 0; essai < 300; essai += 1) {
        const trouves = await detecteur.detect(video);
        if (trouves.length) return String(trouves[0].rawValue);
        await new Promise((r) => this.fenetre.requestAnimationFrame(r));
      }
      return null;
    } finally {
      this.arreter();
    }
  }

  arreter(): void {
    this.flux?.getTracks().forEach((piste) => piste.stop());
    this.flux = undefined;
  }
}
