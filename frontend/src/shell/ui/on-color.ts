/** La couleur du texte posé sur un aplat de marque, calculée plutôt que
 *  supposée.
 *
 *  Home Assistant ne garantit pas la lisibilité de son propre
 *  texte-sur-primaire : sous le thème par défaut, `--text-primary-color` vaut
 *  `#ffffff` et `--primary-color` `#009ac7`, soit 3,26:1 — sous le seuil AA.
 *  Sous Graphite (en service dans la maison), la paire tient (7,41:1), mais
 *  rien ne dit qu'elle tiendra sous le prochain thème installé. On mesure.
 *
 *  LA SONDE EST NÉCESSAIRE : la valeur calculée d'une propriété personnalisée
 *  est son flux de jetons, pas une couleur. `getComputedStyle(hôte)
 *  .getPropertyValue('--primary-color')` rend littéralement
 *  `var(--ha-color-primary-40)` sous Home Assistant. Il faut poser
 *  `color: var(--primary-color)` sur un élément et lire son `color` calculé,
 *  qui, lui, est toujours un `rgb(...)`.
 *
 *  jsdom ne résout ni l'un ni l'autre : les tests unitaires couvrent les
 *  fonctions pures, et le câblage DOM n'est vérifié que par
 *  `outils/verifier-rendu.mjs`, qui tourne dans un vrai Chromium.
 */

const CLAIR = '#ffffff';
const SOMBRE = '#141414';

/** Les paires fond → jeton de texte à recalculer. */
const PAIRES: ReadonlyArray<readonly [string, string]> = [
  ['--hs-accent', '--hs-on-accent'],
  ['--hs-danger', '--hs-on-danger'],
  ['--hs-warning', '--hs-on-warning'],
];

export function parseRgb(couleur: string): [number, number, number] | null {
  const texte = couleur.trim();
  const fonctionnel = /^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/.exec(texte);
  if (fonctionnel) {
    return [Number(fonctionnel[1]), Number(fonctionnel[2]), Number(fonctionnel[3])];
  }
  const hexa = /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/.exec(texte);
  if (hexa) {
    const chiffres = hexa[1].length === 3
      ? hexa[1].split('').map((c) => c + c).join('') : hexa[1];
    return [0, 2, 4].map((i) => parseInt(chiffres.slice(i, i + 2), 16)) as [number, number, number];
  }
  // Tout le reste — '', `var(...)` non résolu, `transparent`, un nom CSS —
  // n'est pas exploitable : l'appelant garde le défaut du jeton.
  return null;
}

function luminance([r, v, b]: [number, number, number]): number {
  const canal = (x: number) => {
    const u = x / 255;
    return u <= 0.03928 ? u / 12.92 : ((u + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * canal(r) + 0.7152 * canal(v) + 0.0722 * canal(b);
}

function contraste(a: [number, number, number], b: [number, number, number]): number {
  const [clair, sombre] = luminance(a) > luminance(b)
    ? [luminance(a), luminance(b)] : [luminance(b), luminance(a)];
  return (clair + 0.05) / (sombre + 0.05);
}

export function meilleureCouleurDeTexte(fond: [number, number, number]): string {
  return contraste(fond, [255, 255, 255]) > contraste(fond, [20, 20, 20]) ? CLAIR : SOMBRE;
}

/** Pose les trois `--hs-on-*` sur l'hôte, d'après les couleurs réellement
 *  résolues. Sans effet là où la sonde ne rend rien (jsdom) : les jetons
 *  gardent alors leur défaut, et aucun écran ne casse. */
export function appliquerCouleursDeTexte(hote: HTMLElement): void {
  const sonde = document.createElement('span');
  sonde.style.cssText = 'position:absolute;width:0;height:0;opacity:0;pointer-events:none';
  hote.appendChild(sonde);
  try {
    for (const [fond, cible] of PAIRES) {
      sonde.style.color = `var(${fond})`;
      const resolue = parseRgb(getComputedStyle(sonde).color);
      if (resolue) hote.style.setProperty(cible, meilleureCouleurDeTexte(resolue));
    }
  } finally {
    sonde.remove();
  }
}
