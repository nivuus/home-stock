/** La feuille de jetons partagée par les dix-sept écrans.
 *
 *  Trois règles, toutes nées d'un défaut constaté :
 *
 *  1. CHAQUE variable Home Assistant lue ici porte un repli. Sans repli,
 *     `var(--divider-color)` sous un thème qui ne la définit pas rend la
 *     déclaration entière invalide à la valeur calculée — la bordure ne
 *     devient pas noire, elle DISPARAÎT, sans la moindre erreur.
 *  2. Un fond et son texte voyagent en paire (`--hs-accent` /
 *     `--hs-on-accent`). Un `#fff` écrit en dur casse l'accord : sous
 *     Graphite — en service dans la maison — la primaire est orange, et du
 *     blanc dessus donne 2,38:1.
 *  3. Mais l'accord du THÈME ne suffit pas non plus : sous le thème HA par
 *     défaut, le `--text-primary-color` blanc sur la primaire `#009ac7` ne
 *     donne que 3,26:1. Les trois `--hs-on-*` portent donc ici un défaut
 *     prudent, et `on-color.ts` les recalcule au montage à partir de la
 *     couleur réellement résolue.
 *
 *  Les valeurs de repli sont les défauts RÉELS de HA 2026.8.2, relevés dans
 *  `hass_frontend`, pas des approximations.
 */
import { css } from 'lit';

export const tokens = css`
  :host {
    --hs-space-1: 4px;
    --hs-space-2: 8px;
    --hs-space-3: 12px;
    --hs-space-4: 16px;
    --hs-space-5: 24px;
    --hs-space-6: 32px;

    --hs-radius-s: 8px;
    --hs-radius-m: 12px;
    --hs-radius-l: 16px;

    --hs-text: var(--primary-text-color, #141414);
    --hs-text-2: var(--secondary-text-color, #5e5e5e);
    --hs-surface: var(--card-background-color, #ffffff);
    --hs-surface-2: var(--secondary-background-color, #e5e5e5);
    --hs-divider: var(--divider-color, #0000001f);

    --hs-accent: var(--primary-color, #009ac7);
    --hs-danger: var(--error-color, #db4437);
    --hs-warning: var(--warning-color, #ffa600);

    /* Recalculés par on-color.ts au montage. Le sombre est le défaut le moins
       risqué sur une couleur de marque inconnue. Pas de --hs-on-danger : le
       danger ne se pose jamais en aplat sous du texte (spec § 6.1 ter,
       --error-color tombe pile à 4,29:1 des deux côtés), donc rien ne le lit. */
    --hs-on-accent: #141414;
    --hs-on-warning: #141414;

    --hs-font: var(--ha-font-family-body, Roboto, Noto, sans-serif);

    /* 62 px, pas 48 : la tablette cuisine (Fire 7) ouvre le même panneau, et
       c'est son seuil qui prime — il satisfait aussi le téléphone. */
    --hs-touch: 62px;

    font-family: var(--hs-font);
    color: var(--hs-text);
  }
`;
