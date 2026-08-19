/** `BarcodeDetector` sur le flux de la caméra. Exige un contexte sécurisé,
 *  ce que home.allanic.me fournit. */
import type { Scanner } from './index';

const FORMATS = ['ean_13', 'ean_8', 'upc_a', 'upc_e', 'code_128'];

export class ScannerNavigateur implements Scanner {
  private flux?: MediaStream;
  private video?: any;

  constructor(private fenetre: any) {}

  disponible(): boolean {
    return Boolean(this.fenetre?.BarcodeDetector
      && this.fenetre?.navigator?.mediaDevices);
  }

  async lire(): Promise<string | null> {
    // Tout, de l'ouverture de la caméra à la lecture, est dans le try : si
    // `getUserMedia` ou `play()` échoue en cours de route, `finally` doit
    // quand même couper le flux déjà ouvert — sinon la caméra reste allumée
    // pour rien.
    try {
      const detecteur = new this.fenetre.BarcodeDetector({ formats: FORMATS });
      this.flux = await this.fenetre.navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment' },
      });
      const video = this.fenetre.document.createElement('video');
      video.srcObject = this.flux;
      video.setAttribute('playsinline', 'true');
      video.setAttribute('muted', 'true');
      // Un viseur réel, pas une caméra qui tourne dans le vide : sans lui,
      // rien ne dit à l'utilisateur où viser le code-barres.
      video.style.cssText = 'position:fixed;inset:0;width:100%;height:100%;'
        + 'object-fit:cover;z-index:2147483647;background:#000;';
      this.fenetre.document.body.appendChild(video);
      this.video = video;
      await video.play();

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
    this.video?.remove();
    this.video = undefined;
  }
}
