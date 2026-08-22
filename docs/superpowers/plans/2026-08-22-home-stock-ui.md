# Refonte UI/UX du panneau Garde-manger — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Donner au panneau `/home-stock` une coquille navigable (en-tête, quatre familles, routes d'URL) et un langage visuel unique adossé aux composants Home Assistant, puis reprendre les trois écrans dont le défaut est structurel.

**Architecture:** Un nouveau module `src/shell/` devient le seul propriétaire de la structure ; `panneau.ts` se réduit à l'orchestration métier. Les dix-sept écrans existants héritent d'une feuille de jetons `--hs-*` partagée sans être réécrits. Trois enveloppes (`hs-card`, `hs-button`, `hs-icon`) rendent les vrais éléments `ha-*` quand ils sont chargés et un repli identique sinon.

**Tech Stack:** TypeScript, `lit` 3, rollup + terser, vitest (jsdom), playwright-core pour `outils/verifier-rendu.mjs`.

**Spec:** `docs/superpowers/specs/2026-08-22-home-stock-ui-design.md`

## Global Constraints

Ces règles s'appliquent à **toutes** les tâches. Les valeurs sont copiées de la spec.

- **Langue du code** : tout fichier créé sous `src/shell/` et tout identifiant qu'il expose sont en **anglais**. Les dix-sept écrans existants (`src/ecrans/*.ts`) gardent leurs noms français. **Les libellés affichés à l'utilisateur restent en français.**
- **Langue des commentaires** : français, comme le reste du dépôt.
- **Routes d'URL** : en anglais (table § 5.2 de la spec).
- **Cible tactile** : `min-height` **62 px** (contrainte Fire 7 de la cuisine). Jamais 48.
- **Contraste** : ≥ **4,5:1**.
- **Chrome 100** (tablette cuisine) : interdit — `dvh`, `:has()`, `@container`, imbrication CSS native, `:is()` avec sélecteurs complexes.
- **Aucun geste de navigation** : le retour est un bouton. Une action destructive demande deux appuis (armement puis confirmation).
- **Aucune couleur littérale** (`#rrggbb`, `rgb(...)`) hors du repli d'un `var()` dans `src/shell/ui/tokens.ts`.
- **Jamais de paire découplée** : un fond `--hs-accent` impose son texte `--hs-on-accent`.
- **Aucun texte sur un aplat `--hs-danger`** (spec § 6.1 ter) : `#db4437`, le rouge d'erreur
  par défaut de HA, a une luminance au point de bascule exact — blanc dessus 4,29:1, noir
  dessus 4,29:1, aucune couleur ne passe 4,5:1. Le danger se dit par une bordure et une
  icône. Le jeton `--hs-on-danger` n'existe pas.
- **Ne jamais toucher** : le métier, les commandes websocket, la base, `custom_components/home_stock/**` (sauf le bundle que `npm run build` écrit).
- **`npm run build` DÉPLOIE en production.** Ne l'exécuter qu'aux points explicitement indiqués (fin de lot).
- Toutes les commandes s'exécutent depuis `/opt/nivuus/HomeAssistant/data/meal/frontend`.

---

# LOT 1 — Outillage et fondations

## Task 1 : le harnais cesse d'inventer sa palette

Le vérificateur mesure aujourd'hui les contrastes sous une palette **inventée** (`--primary-color: #01579b`, choisie pour passer le seuil par construction) et n'y définit que cinq des dix variables lues par le panneau. Résultat : bordures et fonds annulés, police Times, et des contrôles verts qui ne prouvent rien.

**Files:**
- Modify: `outils/verifier-rendu.mjs:115-136` (constante `THEME_CSS` et `pageHtml`)
- Modify: `outils/verifier-rendu.mjs` (orchestration `principal`, ajout d'un balayage multi-palettes)

**Interfaces:**
- Consumes: rien.
- Produces: `PALETTES` (tableau de `{nom, css}`), `themeCss(palette)`, `SCENARIOS_BALAYAGE` (sous-ensemble de `SCENARIOS`), fonction `executerBalayagePalettes(navigateur, urlHarnais)`.

- [ ] **Step 1 : remplacer `THEME_CSS` par trois palettes réelles**

Remplacer le bloc `const THEME_CSS = \`...\`` (lignes 125-135) par :

```js
// --- palettes RÉELLES ---------------------------------------------------
//
// L'ancien THEME_CSS n'était pas seulement incomplet (cinq variables sur les
// dix que le panneau lit, d'où des bordures et des fonds annulés à la valeur
// calculée, et du Times New Roman) : il INVENTAIT sa couleur primaire, un
// `#01579b` choisi pour passer le seuil de contraste par construction. Le
// remplacer par « la bonne » palette recréerait le même mensonge, puisque
// aucun des deux comptes de la maison n'utilise le thème par défaut.
//
// Valeurs relevées le 2026-08-22 dans `hass_frontend` de HA 2026.8.2
// (`--ha-color-neutral-05`, `--ha-color-primary-40`…) et dans
// `config/themes/graphite/graphite-light.yaml`.
const PALETTES = [
  {
    nom: 'HA clair (défaut)',
    variables: {
      '--primary-background-color': '#fafafa',
      '--secondary-background-color': '#e5e5e5',
      '--card-background-color': '#ffffff',
      '--primary-text-color': '#141414',
      '--secondary-text-color': '#5e5e5e',
      '--primary-color': '#009ac7',
      '--text-primary-color': '#ffffff',
      '--divider-color': '#0000001f',
      '--error-color': '#db4437',
      '--warning-color': '#ffa600',
    },
  },
  {
    nom: 'HA sombre',
    variables: {
      '--primary-background-color': '#111111',
      '--secondary-background-color': '#282828',
      '--card-background-color': '#1c1c1c',
      '--primary-text-color': '#e1e1e1',
      '--secondary-text-color': '#9b9b9b',
      '--primary-color': '#009ac7',
      '--text-primary-color': '#ffffff',
      '--divider-color': '#e1e1e11f',
      '--error-color': '#db4437',
      '--warning-color': '#ffa600',
    },
  },
  {
    // Le thème RÉELLEMENT en service sur un des deux comptes de la maison
    // (`.storage/frontend.user_data_*` → « Graphite Auto »). Sa primaire est
    // ORANGE et son texte-sur-primaire est un navy, pas du blanc : c'est
    // exactement le cas qu'un `#fff` écrit en dur casse.
    nom: 'Graphite clair (en service)',
    variables: {
      '--primary-background-color': 'rgb(234, 235, 238)',
      '--secondary-background-color': 'rgb(234, 235, 238)',
      '--card-background-color': 'rgb(255, 255, 255)',
      '--primary-text-color': 'rgb(19, 21, 54)',
      '--secondary-text-color': 'rgb(85, 87, 110)',
      '--primary-color': 'rgb(238, 147, 0)',
      '--text-primary-color': 'rgb(19, 21, 54)',
      '--divider-color': 'rgba(19, 21, 54, 0.12)',
      '--error-color': '#db4437',
      '--warning-color': '#ffa600',
    },
  },
];

function themeCss(palette) {
  const lignes = Object.entries(palette.variables)
    .map(([nom, valeur]) => `    ${nom}: ${valeur};`).join('\n');
  return `
  :root {
${lignes}
    /* HA impose sa police sur le document ; sans elle le harnais mesurait
       du Times New Roman et faisait passer le Planning pour du serif. */
    --ha-font-family-body: Roboto, Noto, sans-serif;
  }
  html, body {
    margin: 0; padding: 0; height: 100%;
    background: var(--primary-background-color);
    font-family: var(--ha-font-family-body);
  }
  home-stock-panel { display: block; height: 100%; }
`;
}
```

- [ ] **Step 2 : paramétrer `pageHtml` par la palette**

```js
function pageHtml(bundleJs, palette = PALETTES[0]) {
  return `<!doctype html>
<html><head><meta charset="utf-8">
<style>${themeCss(palette)}</style>
</head><body>
<home-stock-panel></home-stock-panel>
<script type="module">${bundleJs}</script>
</body></html>`;
}
```

Le serveur statique sert aujourd'hui une page unique. Le rendre capable d'en servir trois : `servirPageStatique` reçoit un objet `{'/': htmlPalette0, '/p1': htmlPalette1, '/p2': htmlPalette2}` et route sur `requete.url`.

```js
async function servirPagesStatiques(pagesParChemin) {
  const serveur = createServer((requete, reponse) => {
    const html = pagesParChemin[requete.url] ?? pagesParChemin['/'];
    reponse.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    reponse.end(html);
  });
  // … même écoute sur 127.0.0.1, port éphémère, qu'auparavant
}
```

- [ ] **Step 3 : lancer le vérificateur et CONSTATER les nouveaux défauts**

Run: `node outils/verifier-rendu.mjs --sans-auto-verification`

Expected: **ÉCHEC**. C'est le résultat attendu et le but de la tâche. Un vérificateur qui resterait vert ici prouverait que la palette n'a pas été prise en compte.

Attendu en particulier : tout texte blanc posé sur `var(--primary-color)` tombe à **3,26:1** sous `HA clair`. Consigner la liste complète des défauts dans le message de commit — c'est l'inventaire de travail des Tasks 6 et suivantes.

- [ ] **Step 4 : ajouter le balayage des deux autres palettes**

Après `executerScenariosLarges`, ajouter :

```js
// Trois scénarios représentatifs seulement : la suite complète × 3 palettes
// × 3 formats ferait 219 mesures pour un gain marginal. Ce qui compte ici,
// c'est qu'aucune des deux autres palettes ne soit JAMAIS mesurée — pas
// qu'elles le soient partout.
const NOMS_BALAYAGE = [
  'Scanner (écran par défaut)',
  'Liste (quatre rayons, deux origines, trois cochées repliées)',
  'Bannière de refus (écriture rejetée par le serveur)',
];

async function executerBalayagePalettes(navigateur, urlsParPalette) {
  let fautes = 0;
  let total = 0;
  for (let i = 1; i < PALETTES.length; i += 1) {
    console.log(`\n=== Balayage : ${PALETTES[i].nom} ===`);
    for (const scenario of SCENARIOS.filter((s) => NOMS_BALAYAGE.includes(s.nom))) {
      total += 1;
      const contexte = await navigateur.newContext({ viewport: { width: 412, height: 915 } });
      const page = await contexte.newPage();
      await page.goto(urlsParPalette[i], { waitUntil: 'load' });
      await page.waitForFunction(() => Boolean(window.customElements.get('home-stock-panel')));
      const resultat = await page.evaluate(monterEtMesurer, {
        fixture: scenario.fixture, actions: scenario.actions,
        cibleMinPx: CIBLE_MIN_PX, contrasteMin: CONTRASTE_MIN,
        ecranAttendu: scenario.ecranAttendu ?? null,
        elementAttendu: scenario.elementAttendu ?? null,
        sansScannerNatif: scenario.sansScannerNatif ?? false,
      });
      await contexte.close();
      if (aDesDefauts(resultat)) {
        fautes += 1;
        console.log(`  ✗ ${scenario.nom}`);
        for (const ligne of formaterDefauts(resultat)) console.log(ligne);
      } else {
        console.log(`  ✓ ${scenario.nom}`);
      }
    }
  }
  return { fautes, total };
}
```

Brancher l'appel dans `principal()`, en ajoutant ses `fautes` et son `total` aux compteurs existants.

- [ ] **Step 5 : porter la cible tactile à 62 px**

```js
const CIBLE_MIN_PX = 62;
```

Mettre à jour le commentaire d'en-tête du fichier (point 4, qui annonce « **48 px** de cible tactile ») : la tablette cuisine ouvre le même panneau, donc c'est le seuil du mur qui prime.

- [ ] **Step 6 : commit**

```bash
git add outils/verifier-rendu.mjs
git commit -m "test(verifier): trois palettes réelles au lieu d'une inventée

Le harnais ne définissait que cinq des dix variables lues par le panneau, et
sa primaire #01579b avait été CHOISIE pour passer le seuil de contraste. Les
bordures du Planning, ses fonds de boutons et sa police tombaient donc à la
valeur calculée, et soixante-treize contrôles verts ne prouvaient rien.

Il connaît maintenant HA clair, HA sombre et Graphite clair — ce dernier
étant le thème réellement en service dans la maison, dont la primaire est
orange et le texte-sur-primaire un navy. Le vérificateur échoue désormais,
et la liste ci-dessous est l'inventaire de travail du lot :

<coller ici la sortie de l'étape 3>"
```

---

## Task 2 : la feuille de jetons, et la couleur de texte qui se calcule

Deux fichiers, parce qu'ils répondent à la même question. Mesuré sur les palettes
réelles : `--primary-color` `#009ac7` avec le `--text-primary-color` `#ffffff`
que HA lui associe donne **3,26:1**, et `--error-color` `#db4437` avec le même
blanc donne **4,29:1**. Home Assistant ne garantit donc pas la lisibilité de son
propre texte-sur-primaire, et aucune variable de thème ne donne la bonne
réponse. On la calcule. Voir § 6.1 bis de la spec.

**Files:**
- Create: `src/shell/ui/tokens.ts`
- Create: `src/shell/ui/on-color.ts`
- Test: `tests/shell-tokens.test.ts`
- Test: `tests/shell-on-color.test.ts`

**Interfaces:**
- Consumes: rien.
- Produces:
  - `export const tokens: CSSResult` — à composer par les écrans en `static styles = [tokens, css`…`]`.
  - `export function parseRgb(couleur: string): [number, number, number] | null`
  - `export function meilleureCouleurDeTexte(fond: [number, number, number]): string`
  - `export function appliquerCouleursDeTexte(hote: HTMLElement): void`

- [ ] **Step 1 : écrire le test des jetons**

`tests/shell-tokens.test.ts` :

```ts
import { describe, expect, it } from 'vitest';
import { tokens } from '../src/shell/ui/tokens';

/** Le texte CSS brut de la feuille — c'est tout ce que jsdom permet
 *  d'inspecter : il ne calcule aucune mise en page et n'applique pas les
 *  feuilles adoptées d'un shadow root. Les vraies mesures sont le travail de
 *  `outils/verifier-rendu.mjs`. */
const css = tokens.cssText;

describe('jetons partagés', () => {
  it('définit chaque jeton documenté dans la spec', () => {
    for (const jeton of [
      '--hs-space-1', '--hs-space-2', '--hs-space-3', '--hs-space-4',
      '--hs-space-5', '--hs-space-6',
      '--hs-radius-s', '--hs-radius-m', '--hs-radius-l',
      '--hs-text', '--hs-text-2', '--hs-surface', '--hs-surface-2',
      '--hs-divider', '--hs-accent', '--hs-on-accent',
      '--hs-danger', '--hs-warning', '--hs-on-warning',
      '--hs-font', '--hs-touch',
    ]) {
      expect(css).toContain(`${jeton}:`);
    }
  });

  it('donne un repli à CHAQUE variable Home Assistant lue', () => {
    // C'est l'absence de repli qui a rendu invalides les bordures du Planning
    // sous un thème incomplet : `var(--divider-color)` sans repli annule la
    // déclaration entière à la valeur calculée.
    // Seules les variables HOME ASSISTANT sont visées : les jetons --hs-* sont
    // définis dans ce même bloc `:host`, ils résolvent toujours, et leur donner
    // un repli créerait une seconde source de vérité.
    const sansRepli = [...css.matchAll(/var\((--(?!hs-)[a-z-]+)\s*\)/g)].map((m) => m[1]);
    expect(sansRepli).toEqual([]);
  });

  it('impose la cible tactile de la tablette cuisine', () => {
    expect(css).toContain('--hs-touch: 62px');
  });

  it('ne pose de couleur littérale QUE sur les trois jetons recalculés', () => {
    // Les --hs-on-* n'ont pas de variable de thème correcte (§ 6.1 bis) : ils
    // portent un défaut prudent que `on-color.ts` remplace au montage. Partout
    // ailleurs, une couleur littérale est une couleur qui ignore le thème.
    const sansVar = css.replace(/var\([^)]*\)/g, '');
    const litteraux = [...sansVar.matchAll(/(--[a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{3,8}|rgba?\([^)]*\))/g)];
    expect(litteraux.map((m) => m[1]).sort())
      .toEqual(['--hs-on-accent', '--hs-on-warning']);
    // Et ce défaut est le SOMBRE : sur une couleur de marque inconnue, le
    // sombre est le pari le moins risqué (la plupart des primaires de thème
    // sont des teintes moyennes à vives, où le blanc échoue).
    for (const m of litteraux) expect(m[2]).toBe('#141414');
  });
});
```

- [ ] **Step 2 : lancer le test pour vérifier qu'il échoue**

Run: `npx vitest run tests/shell-tokens.test.ts`
Expected: FAIL — `Failed to resolve import "../src/shell/ui/tokens"`.

- [ ] **Step 3 : écrire la feuille**

`src/shell/ui/tokens.ts` :

```ts
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
       risqué sur une couleur de marque inconnue. */
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
```

- [ ] **Step 4 : lancer le test des jetons**

Run: `npx vitest run tests/shell-tokens.test.ts`
Expected: PASS (4 tests).

- [ ] **Step 5 : écrire le test des couleurs calculées**

`tests/shell-on-color.test.ts` :

```ts
import { describe, expect, it } from 'vitest';
import { meilleureCouleurDeTexte, parseRgb } from '../src/shell/ui/on-color';

describe('analyse d’une couleur résolue', () => {
  it('lit les formes que rend getComputedStyle', () => {
    expect(parseRgb('rgb(0, 154, 199)')).toEqual([0, 154, 199]);
    expect(parseRgb('rgba(238, 147, 0, 1)')).toEqual([238, 147, 0]);
    expect(parseRgb('  rgb(19,21,54)  ')).toEqual([19, 21, 54]);
  });

  it('rend null sur ce qu’elle ne sait pas lire', () => {
    // jsdom ne résout pas var() et rend '' : le module doit alors garder le
    // défaut du jeton plutôt que poser une couleur au hasard.
    expect(parseRgb('')).toBeNull();
    expect(parseRgb('var(--primary-color)')).toBeNull();
    expect(parseRgb('transparent')).toBeNull();
  });
});

describe('choix de la couleur de texte', () => {
  it('choisit le sombre sur le cyan du thème HA par défaut', () => {
    // Le cas qui motive tout ce module : HA associe du BLANC à cette
    // primaire, et blanc sur #009ac7 ne fait que 3,26:1.
    expect(meilleureCouleurDeTexte([0, 154, 199])).toBe('#141414');
  });

  it('choisit le sombre sur l’orange de Graphite', () => {
    expect(meilleureCouleurDeTexte([238, 147, 0])).toBe('#141414');
  });

  it('choisit le clair sur un fond franchement sombre', () => {
    expect(meilleureCouleurDeTexte([20, 20, 20])).toBe('#ffffff');
  });

  it('choisit toujours celle des deux qui contraste le mieux', () => {
    // Propriété, pas cas particulier : sur cent teintes, la couleur rendue
    // doit toujours être la meilleure des deux candidates.
    for (let i = 0; i < 100; i += 1) {
      const fond: [number, number, number] = [(i * 37) % 256, (i * 91) % 256, (i * 53) % 256];
      const choisie = meilleureCouleurDeTexte(fond);
      const autre = choisie === '#ffffff' ? '#141414' : '#ffffff';
      expect(contraste(fond, parseRgb(choisie)!))
        .toBeGreaterThanOrEqual(contraste(fond, parseRgb(autre)!));
    }
  });
});

/** Recalculé ici plutôt qu'importé : un test qui réutiliserait la fonction
 *  testée pour se vérifier lui-même ne prouverait rien. */
function contraste(a: [number, number, number], b: [number, number, number]): number {
  const l = (c: [number, number, number]) => {
    const v = c.map((x) => x / 255).map((u) => (u <= 0.03928 ? u / 12.92 : ((u + 0.055) / 1.055) ** 2.4));
    return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2];
  };
  const [clair, sombre] = l(a) > l(b) ? [l(a), l(b)] : [l(b), l(a)];
  return (clair + 0.05) / (sombre + 0.05);
}
```

Note : `parseRgb('#141414')` doit donc aussi savoir lire une notation hexadécimale, puisque le test l'emploie sur ses propres constantes.

- [ ] **Step 6 : lancer le test pour vérifier qu'il échoue**

Run: `npx vitest run tests/shell-on-color.test.ts`
Expected: FAIL — module introuvable.

- [ ] **Step 7 : écrire le module**

`src/shell/ui/on-color.ts` :

```ts
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
```

- [ ] **Step 8 : lancer les deux fichiers de tests**

Run: `npx vitest run tests/shell-tokens.test.ts tests/shell-on-color.test.ts`
Expected: PASS (4 + 6 tests).

- [ ] **Step 9 : commit**

```bash
git add src/shell/ui/tokens.ts src/shell/ui/on-color.ts tests/shell-tokens.test.ts tests/shell-on-color.test.ts
git commit -m "feat(shell): des jetons à repli obligatoire, et un texte-sur-marque calculé

Home Assistant ne garantit pas la lisibilité de son propre texte-sur-primaire :
blanc sur #009ac7 fait 3,26:1 sous le thème par défaut. Aucune variable de
thème ne donne la bonne réponse, donc on la mesure — sonde comprise, la valeur
calculée d'une propriété personnalisée n'étant pas une couleur mais un flux de
jetons."
```

---

## Task 3 : savoir si Home Assistant a chargé ses composants

`ha-card`, `ha-button` et `ha-svg-icon` vivent dans des chunks chargés à la demande (vérifié : absents de `app.*.js` en HA 2026.8.2). Ils sont là si l'utilisateur a d'abord vu Lovelace — ce qui est le cas courant, `default_panel` valant `lovelace` — et absents si `/home-stock` est ouvert directement, ce que fait la tablette cuisine. Un élément inconnu se rend en `display: inline` **sans erreur en console**.

**Files:**
- Create: `src/shell/ui/ha-available.ts`
- Test: `tests/shell-ha-available.test.ts`

**Interfaces:**
- Consumes: rien.
- Produces:
  - `export function isDefined(name: string): boolean`
  - `export function whenDefined(name: string, onDefined: () => void): void`
  - `export function primeHaComponents(win?: Window): void`
  - `export function resetForTests(): void`

- [ ] **Step 1 : écrire le test qui échoue**

`tests/shell-ha-available.test.ts` :

```ts
import { afterEach, describe, expect, it, vi } from 'vitest';
import { isDefined, primeHaComponents, resetForTests, whenDefined }
  from '../src/shell/ui/ha-available';

afterEach(() => {
  resetForTests();
});

describe('détection des composants Home Assistant', () => {
  it('dit faux pour un élément que HA n’a pas chargé', () => {
    expect(isDefined('ha-card-jamais-defini')).toBe(false);
  });

  it('dit vrai pour un élément défini', () => {
    const nom = `ha-card-test-${Math.random().toString(36).slice(2)}`;
    customElements.define(nom, class extends HTMLElement {});
    expect(isDefined(nom)).toBe(true);
  });

  it('rappelle son abonné quand l’élément arrive APRÈS le premier rendu', async () => {
    // Le cas qui compte : la coquille rend son repli, puis Lovelace charge
    // son chunk. Sans ce rappel, l'utilisateur garderait le repli jusqu'à
    // ce qu'il quitte la page.
    const nom = `ha-card-tardif-${Math.random().toString(36).slice(2)}`;
    const rendreANouveau = vi.fn();
    whenDefined(nom, rendreANouveau);
    expect(rendreANouveau).not.toHaveBeenCalled();

    customElements.define(nom, class extends HTMLElement {});
    await customElements.whenDefined(nom);
    await Promise.resolve();

    expect(rendreANouveau).toHaveBeenCalledTimes(1);
  });

  it('n’abonne qu’une fois par élément, même avec plusieurs instances', async () => {
    const nom = `ha-card-partage-${Math.random().toString(36).slice(2)}`;
    const a = vi.fn();
    const b = vi.fn();
    whenDefined(nom, a);
    whenDefined(nom, b);
    customElements.define(nom, class extends HTMLElement {});
    await customElements.whenDefined(nom);
    await Promise.resolve();
    expect(a).toHaveBeenCalledTimes(1);
    expect(b).toHaveBeenCalledTimes(1);
  });

  it('appelle loadCardHelpers une seule fois, et survit à son absence', () => {
    const loadCardHelpers = vi.fn().mockResolvedValue({});
    const fenetre = { loadCardHelpers } as unknown as Window;
    primeHaComponents(fenetre);
    primeHaComponents(fenetre);
    expect(loadCardHelpers).toHaveBeenCalledTimes(1);

    resetForTests();
    // Une fenêtre SANS loadCardHelpers : c'est le cas de la tablette qui
    // ouvre /home-stock directement. Ne doit pas lever.
    expect(() => primeHaComponents({} as unknown as Window)).not.toThrow();
  });
});
```

- [ ] **Step 2 : lancer le test pour vérifier qu'il échoue**

Run: `npx vitest run tests/shell-ha-available.test.ts`
Expected: FAIL — module introuvable.

- [ ] **Step 3 : écrire le module**

`src/shell/ui/ha-available.ts` :

```ts
/** Les éléments `ha-*` ne sont PAS enregistrés par notre bundle : ils
 *  viennent de chunks que Home Assistant charge à la demande. Vérifié en HA
 *  2026.8.2 : ni `ha-card`, ni `ha-svg-icon`, ni `loadCardHelpers` ne sont
 *  dans `app.*.js`.
 *
 *  Ils sont donc présents quand on arrive depuis Lovelace (le cas courant,
 *  `default_panel` valant `lovelace`) et absents quand on ouvre
 *  `/home-stock` directement — ce que fait la tablette de la cuisine. Et un
 *  élément inconnu ne lève rien : il se rend en `display: inline`,
 *  silencieusement. D'où ce module, et les enveloppes qui s'en servent. */

type Rappel = () => void;

const abonnes = new Map<string, Rappel[]>();
let amorcageDemande = false;

/** Synchrone, parce que le rendu de Lit l'est : une enveloppe doit décider
 *  MAINTENANT si elle rend `<ha-card>` ou son repli. */
export function isDefined(name: string): boolean {
  return typeof customElements !== 'undefined' && Boolean(customElements.get(name));
}

/** Rappelle `onDefined` si l'élément est enregistré plus tard. Un seul
 *  `customElements.whenDefined` par nom, quel que soit le nombre
 *  d'instances : elles sont potentiellement des dizaines à l'écran. */
export function whenDefined(name: string, onDefined: Rappel): void {
  if (isDefined(name)) return;
  const existants = abonnes.get(name);
  if (existants) {
    existants.push(onDefined);
    return;
  }
  abonnes.set(name, [onDefined]);
  void customElements.whenDefined(name).then(() => {
    for (const rappel of abonnes.get(name) ?? []) rappel();
    abonnes.delete(name);
  });
}

/** Tente une fois de forcer le chunk Lovelace, qui enregistre `ha-card` et
 *  ses voisins. `loadCardHelpers` est lui-même posé par ce chunk : son
 *  absence signifie simplement qu'on est arrivé sans passer par Lovelace,
 *  et c'est exactement le cas où les replis servent. Jamais une erreur. */
export function primeHaComponents(win: Window = window): void {
  if (amorcageDemande) return;
  amorcageDemande = true;
  const charger = (win as unknown as { loadCardHelpers?: () => Promise<unknown> }).loadCardHelpers;
  if (typeof charger !== 'function') return;
  void Promise.resolve(charger.call(win)).catch(() => {
    // Rien à faire : les enveloppes rendent leur repli, qui est correct.
  });
}

/** Uniquement pour les tests : l'état ci-dessus est un module singleton. */
export function resetForTests(): void {
  abonnes.clear();
  amorcageDemande = false;
}
```

- [ ] **Step 4 : lancer le test pour vérifier qu'il passe**

Run: `npx vitest run tests/shell-ha-available.test.ts`
Expected: PASS (5 tests).

- [ ] **Step 5 : commit**

```bash
git add src/shell/ui/ha-available.ts tests/shell-ha-available.test.ts
git commit -m "feat(shell): détecter les ha-* que HA charge à la demande, sans jamais lever"
```

---

## Task 4 : les icônes, dont nous portons les tracés

**Files:**
- Create: `src/shell/ui/icons.ts`
- Create: `src/shell/ui/hs-icon.ts`
- Test: `tests/shell-icons.test.ts`

**Interfaces:**
- Consumes: `isDefined`, `whenDefined` (Task 3).
- Produces:
  - `export type IconName = 'cart' | 'package' | 'cutlery' | 'home' | 'back' | 'scan' | 'plus' | 'check' | 'close' | 'search' | 'settings' | 'battery' | 'menu' | 'alert' | 'clock'`
  - `export const ICON_PATHS: Record<IconName, string>`
  - L'élément `<hs-icon name="cart" label="Courses">`. `label` absent ⇒ `aria-hidden="true"`.

- [ ] **Step 1 : écrire le test qui échoue**

`tests/shell-icons.test.ts` :

```ts
import { afterEach, describe, expect, it } from 'vitest';
import { ICON_PATHS } from '../src/shell/ui/icons';
import { resetForTests } from '../src/shell/ui/ha-available';
import '../src/shell/ui/hs-icon';

afterEach(() => {
  document.body.innerHTML = '';
  resetForTests();
});

async function monter(attributs: Record<string, string>): Promise<HTMLElement> {
  const el = document.createElement('hs-icon');
  for (const [nom, valeur] of Object.entries(attributs)) el.setAttribute(nom, valeur);
  document.body.appendChild(el);
  await (el as HTMLElement & { updateComplete: Promise<unknown> }).updateComplete;
  return el;
}

describe('hs-icon', () => {
  it('porte tous les tracés dont la coquille a besoin', () => {
    for (const nom of ['cart', 'package', 'cutlery', 'home', 'back', 'scan',
                       'plus', 'check', 'close', 'search', 'settings',
                       'battery', 'menu', 'alert', 'clock']) {
      expect(ICON_PATHS[nom as keyof typeof ICON_PATHS]).toMatch(/^M/);
    }
  });

  it('rend un svg à nous quand ha-svg-icon n’est pas chargé', async () => {
    const el = await monter({ name: 'cart' });
    const svg = el.shadowRoot!.querySelector('svg');
    expect(svg).not.toBeNull();
    expect(svg!.querySelector('path')!.getAttribute('d')).toBe(ICON_PATHS.cart);
  });

  it('est masqué aux lecteurs d’écran quand il n’a pas de libellé', async () => {
    const el = await monter({ name: 'cart' });
    expect(el.shadowRoot!.querySelector('svg')!.getAttribute('aria-hidden')).toBe('true');
  });

  it('annonce son libellé quand il en a un', async () => {
    const el = await monter({ name: 'cart', label: 'Courses' });
    const svg = el.shadowRoot!.querySelector('svg')!;
    expect(svg.getAttribute('aria-hidden')).toBeNull();
    expect(svg.getAttribute('role')).toBe('img');
    expect(svg.querySelector('title')!.textContent).toBe('Courses');
  });

  it('préfère ha-svg-icon dès qu’il est disponible, avec NOTRE tracé', async () => {
    // Le tracé vient de nous dans les deux cas : on ne dépend jamais du
    // chargement de l'iconset mdi de Home Assistant.
    if (!customElements.get('ha-svg-icon')) {
      customElements.define('ha-svg-icon', class extends HTMLElement {});
    }
    const el = await monter({ name: 'home' });
    const haIcon = el.shadowRoot!.querySelector('ha-svg-icon');
    expect(haIcon).not.toBeNull();
    expect((haIcon as HTMLElement & { path?: string }).path).toBe(ICON_PATHS.home);
    expect(el.shadowRoot!.querySelector('svg')).toBeNull();
  });
});
```

- [ ] **Step 2 : lancer le test pour vérifier qu'il échoue**

Run: `npx vitest run tests/shell-icons.test.ts`
Expected: FAIL — modules introuvables.

- [ ] **Step 3 : écrire les tracés**

`src/shell/ui/icons.ts`. Récupérer les tracés depuis `@mdi/js` **sans ajouter la dépendance** : les copier en dur, c'est quelques centaines d'octets contre un paquet de plusieurs mégaoctets dont le tree-shaking dépend du bundler.

```ts
/** Les tracés `mdi` dont la coquille a besoin, portés par nous.
 *
 *  Home Assistant sait rendre une icône `mdi:` par son nom, mais seulement
 *  après avoir chargé son iconset — un chunk de plus, de la même famille que
 *  ceux de `ha-available.ts`. Porter quinze tracés coûte quelques centaines
 *  d'octets et supprime cette dépendance : `hs-icon` fournit le `path` aussi
 *  bien à `ha-svg-icon` qu'à son propre `<svg>`.
 *
 *  Source : @mdi/js 7.x, mêmes noms d'icônes que ceux cités dans la spec.
 */
export type IconName =
  | 'cart' | 'package' | 'cutlery' | 'home'
  | 'back' | 'scan' | 'plus' | 'check' | 'close'
  | 'search' | 'settings' | 'battery' | 'menu' | 'alert' | 'clock';

export const ICON_PATHS: Record<IconName, string> = {
  // mdi:cart
  cart: 'M17,18C15.89,18 15,18.89 15,20A2,2 0 0,0 17,22A2,2 0 0,0 19,20C19,18.89 18.1,18 17,18M1,2V4H3L6.6,11.59L5.24,14.04C5.09,14.32 5,14.65 5,15A2,2 0 0,0 7,17H19V15H7.42A0.25,0.25 0 0,1 7.17,14.75C7.17,14.7 7.18,14.66 7.2,14.63L8.1,13H15.55C16.3,13 16.96,12.58 17.3,11.97L20.88,5.5C20.95,5.34 21,5.17 21,5A1,1 0 0,0 20,4H5.21L4.27,2M7,18C5.89,18 5,18.89 5,20A2,2 0 0,0 7,22A2,2 0 0,0 9,20C9,18.89 8.1,18 7,18Z',
  // mdi:package-variant
  package: 'M2,10.96C1.5,10.68 1.35,10.07 1.63,9.59L3.13,7C3.24,6.8 3.41,6.66 3.6,6.58L11.43,2.18C11.59,2.06 11.79,2 12,2C12.21,2 12.41,2.06 12.57,2.18L20.47,6.62C20.66,6.72 20.82,6.88 20.91,7.08L22.36,9.6C22.64,10.08 22.47,10.69 22,10.96L21,11.54V16.5C21,16.88 20.79,17.21 20.47,17.38L12.57,21.82C12.41,21.94 12.21,22 12,22C11.79,22 11.59,21.94 11.43,21.82L3.53,17.38C3.21,17.21 3,16.88 3,16.5V10.96C2.7,11.13 2.32,11.14 2,10.96M12,4.15V4.15L12,10.85V10.85L17.96,7.5L12,4.15M5,15.91L11,19.29V12.58L5,9.21V15.91M19,15.91V12.5L13,15.86V19.29L19,15.91M13.85,13.36L19.5,10.5L18.5,8.75L13.85,13.36Z',
  // mdi:silverware-fork-knife
  cutlery: 'M11,9H9V2H7V9H5V2H3V9C3,11.12 4.66,12.84 6.75,12.97V22H9.25V12.97C11.34,12.84 13,11.12 13,9V2H11V9M16,6V14H18.5V22H21V2C18.24,2 16,4.24 16,6Z',
  // mdi:home-outline — la maison SEULE. Le tracé initialement écrit ici était
  // celui de `mdi:home-account`, une maison avec un personnage dedans : rien à
  // voir avec une famille qui regroupe piles, équipements et réglages. Rendu
  // et contrôlé à l'œil le 2026-08-22, comme les quatorze autres.
  home: 'M12,3L2,12H5V20H19V12H22L12,3M12,7.7L17,12.2V18H15V14H9V18H7V12.2L12,7.7Z',
  // mdi:arrow-left
  back: 'M20,11V13H8L13.5,18.5L12.08,19.92L4.16,12L12.08,4.08L13.5,5.5L8,11H20Z',
  // mdi:barcode-scan
  scan: 'M4,6H6V18H4V6M7,6H8V18H7V6M9,6H12V18H9V6M13,6H14V18H13V6M16,6H18V18H16V6M19,6H20V18H19V6M2,4V8H0V4A2,2 0 0,1 2,2H6V4H2M22,2A2,2 0 0,1 24,4V8H22V4H18V2H22M2,16V20H6V22H2A2,2 0 0,1 0,20V16H2M22,20V16H24V20A2,2 0 0,1 22,22H18V20H22Z',
  // mdi:plus
  plus: 'M19,13H13V19H11V13H5V11H11V5H13V11H19V13Z',
  // mdi:check
  check: 'M21,7L9,19L3.5,13.5L4.91,12.09L9,16.17L19.59,5.59L21,7Z',
  // mdi:close
  close: 'M19,6.41L17.59,5L12,10.59L6.41,5L5,6.41L10.59,12L5,17.59L6.41,19L12,13.41L17.59,19L19,17.59L13.41,12L19,6.41Z',
  // mdi:magnify
  search: 'M9.5,3A6.5,6.5 0 0,1 16,9.5C16,11.11 15.41,12.59 14.44,13.73L14.71,14H15.5L20.5,19L19,20.5L14,15.5V14.71L13.73,14.44C12.59,15.41 11.11,16 9.5,16A6.5,6.5 0 0,1 3,9.5A6.5,6.5 0 0,1 9.5,3M9.5,5C7,5 5,7 5,9.5C5,12 7,14 9.5,14C12,14 14,12 14,9.5C14,7 12,5 9.5,5Z',
  // mdi:cog-outline
  settings: 'M12,8A4,4 0 0,1 16,12A4,4 0 0,1 12,16A4,4 0 0,1 8,12A4,4 0 0,1 12,8M12,10A2,2 0 0,0 10,12A2,2 0 0,0 12,14A2,2 0 0,0 14,12A2,2 0 0,0 12,10M10,22C9.75,22 9.54,21.82 9.5,21.58L9.13,18.93C8.5,18.68 7.96,18.34 7.44,17.94L4.95,18.95C4.73,19.03 4.46,18.95 4.34,18.73L2.34,15.27C2.21,15.05 2.27,14.78 2.46,14.63L4.57,12.97L4.5,12L4.57,11L2.46,9.37C2.27,9.22 2.21,8.95 2.34,8.73L4.34,5.27C4.46,5.05 4.73,4.96 4.95,5.05L7.44,6.05C7.96,5.66 8.5,5.32 9.13,5.07L9.5,2.42C9.54,2.18 9.75,2 10,2H14C14.25,2 14.46,2.18 14.5,2.42L14.87,5.07C15.5,5.32 16.04,5.66 16.56,6.05L19.05,5.05C19.27,4.96 19.54,5.05 19.66,5.27L21.66,8.73C21.79,8.95 21.73,9.22 21.54,9.37L19.43,11L19.5,12L19.43,13L21.54,14.63C21.73,14.78 21.79,15.05 21.66,15.27L19.66,18.73C19.54,18.95 19.27,19.04 19.05,18.95L16.56,17.95C16.04,18.34 15.5,18.68 14.87,18.93L14.5,21.58C14.46,21.82 14.25,22 14,22H10M11.25,4L10.88,6.61C9.68,6.86 8.62,7.5 7.85,8.39L5.44,7.35L4.69,8.65L6.8,10.2C6.4,11.37 6.4,12.64 6.8,13.8L4.68,15.36L5.43,16.66L7.86,15.62C8.63,16.5 9.68,17.14 10.87,17.38L11.24,20H12.76L13.13,17.39C14.32,17.14 15.37,16.5 16.14,15.62L18.57,16.66L19.32,15.36L17.2,13.81C17.6,12.64 17.6,11.37 17.2,10.2L19.31,8.65L18.56,7.35L16.15,8.39C15.38,7.5 14.32,6.86 13.12,6.62L12.75,4H11.25Z',
  // mdi:battery-alert-variant-outline
  battery: 'M12,2A2,2 0 0,1 14,4V6H15A2,2 0 0,1 17,8V20A2,2 0 0,1 15,22H9A2,2 0 0,1 7,20V8A2,2 0 0,1 9,6H10V4A2,2 0 0,1 12,2M9,8V20H15V8H9M11,10H13V15H11V10M11,16H13V18H11V16Z',
  // mdi:menu
  menu: 'M3,6H21V8H3V6M3,11H21V13H3V11M3,16H21V18H3V16Z',
  // mdi:alert-circle-outline
  alert: 'M11,15H13V17H11V15M11,7H13V13H11V7M12,2C6.47,2 2,6.5 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2M12,20A8,8 0 0,1 4,12A8,8 0 0,1 12,4A8,8 0 0,1 20,12A8,8 0 0,1 12,20Z',
  // mdi:clock-outline
  clock: 'M12,20A8,8 0 0,0 20,12A8,8 0 0,0 12,4A8,8 0 0,0 4,12A8,8 0 0,0 12,20M12,2A10,10 0 0,1 22,12A10,10 0 0,1 12,22C6.47,22 2,17.5 2,12A10,10 0 0,1 12,2M12.5,7V12.25L17,14.92L16.25,16.15L11,13V7H12.5Z',
};
```

- [ ] **Step 4 : écrire l'élément**

`src/shell/ui/hs-icon.ts` :

```ts
/** Une icône, rendue par `ha-svg-icon` quand Home Assistant l'a chargé et par
 *  notre propre `<svg>` sinon. Le tracé vient de `icons.ts` DANS LES DEUX
 *  CAS : voir le commentaire de tête de ce fichier. */
import { LitElement, html, css, nothing, svg } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { tokens } from './tokens';
import { ICON_PATHS, type IconName } from './icons';
import { isDefined, whenDefined } from './ha-available';

const HA_SVG_ICON = 'ha-svg-icon';

@customElement('hs-icon')
export class HsIcon extends LitElement {
  @property({ type: String }) name: IconName = 'home';
  /** Absent ⇒ l'icône est décorative et masquée aux lecteurs d'écran. Une
   *  icône seule dans un bouton DOIT en porter un. */
  @property({ type: String }) label: string | null = null;

  connectedCallback(): void {
    super.connectedCallback();
    whenDefined(HA_SVG_ICON, () => this.requestUpdate());
  }

  static styles = [tokens, css`
    :host { display: inline-flex; width: 24px; height: 24px; }
    svg, ha-svg-icon { width: 100%; height: 100%; fill: currentColor; }
  `];

  render() {
    const path = ICON_PATHS[this.name];
    if (isDefined(HA_SVG_ICON)) {
      return html`<ha-svg-icon .path=${path} .label=${this.label ?? undefined}></ha-svg-icon>`;
    }
    return html`
      <svg viewBox="0 0 24 24"
           role=${this.label ? 'img' : nothing}
           aria-hidden=${this.label ? nothing : 'true'}>
        ${this.label ? svg`<title>${this.label}</title>` : nothing}
        <path d=${path}></path>
      </svg>`;
  }
}
```

- [ ] **Step 5 : lancer le test pour vérifier qu'il passe**

Run: `npx vitest run tests/shell-icons.test.ts`
Expected: PASS (5 tests).

- [ ] **Step 6 : commit**

```bash
git add src/shell/ui/icons.ts src/shell/ui/hs-icon.ts tests/shell-icons.test.ts
git commit -m "feat(shell): des icônes dont nous portons les tracés, ha-svg-icon ou pas"
```

---

## Task 5 : les enveloppes carte et bouton

**Files:**
- Create: `src/shell/ui/hs-card.ts`
- Create: `src/shell/ui/hs-button.ts`
- Test: `tests/shell-enveloppes.test.ts`

**Interfaces:**
- Consumes: `tokens` (Task 2), `isDefined`/`whenDefined`/`pendingCountForTests` (Task 3).
  ⚠️ `whenDefined(nom, rappel)` **rend une fonction de désabonnement** (signature
  étendue au round de correction de la Task 4) : ne pas l'appeler au démontage
  refait la fuite que cette signature existe pour éviter.
- Produces:
  - `<hs-card>` — un `<slot>`, rien d'autre.
  - `<hs-button variant="primary"|"neutral"|"danger" ?disabled ?full>` — un `<slot>`. Émet le `click` natif ; ne le réémet jamais.

- [ ] **Step 1 : écrire le test qui échoue**

`tests/shell-enveloppes.test.ts` :

```ts
import { afterEach, describe, expect, it, vi } from 'vitest';
import { pendingCountForTests, resetForTests } from '../src/shell/ui/ha-available';
import '../src/shell/ui/hs-card';
import '../src/shell/ui/hs-button';

afterEach(() => {
  document.body.innerHTML = '';
  resetForTests();
});

async function monter(balise: string, attributs: Record<string, string> = {}) {
  const el = document.createElement(balise);
  for (const [n, v] of Object.entries(attributs)) el.setAttribute(n, v);
  document.body.appendChild(el);
  await (el as HTMLElement & { updateComplete: Promise<unknown> }).updateComplete;
  return el;
}

describe('hs-card', () => {
  it('rend son repli quand ha-card n’est pas chargé', async () => {
    const el = await monter('hs-card');
    expect(el.shadowRoot!.querySelector('.repli')).not.toBeNull();
    expect(el.shadowRoot!.querySelector('ha-card')).toBeNull();
  });

  it('rend ha-card quand il est chargé', async () => {
    if (!customElements.get('ha-card')) {
      customElements.define('ha-card', class extends HTMLElement {});
    }
    const el = await monter('hs-card');
    expect(el.shadowRoot!.querySelector('ha-card')).not.toBeNull();
    expect(el.shadowRoot!.querySelector('.repli')).toBeNull();
  });
});

describe('hs-button', () => {
  it('rend un bouton natif quand ha-button n’est pas chargé', async () => {
    const el = await monter('hs-button');
    expect(el.shadowRoot!.querySelector('button')).not.toBeNull();
  });

  it('laisse le clic remonter, sans le dupliquer', async () => {
    // Réémettre un `click` depuis l'enveloppe le ferait compter DEUX fois
    // chez l'appelant : le natif traverse déjà le shadow DOM.
    const el = await monter('hs-button');
    const surClic = vi.fn();
    el.addEventListener('click', surClic);
    el.shadowRoot!.querySelector('button')!.click();
    expect(surClic).toHaveBeenCalledTimes(1);
  });

  it('n’émet aucun clic quand il est désactivé', async () => {
    const el = await monter('hs-button', { disabled: '' });
    const surClic = vi.fn();
    el.addEventListener('click', surClic);
    el.shadowRoot!.querySelector('button')!.click();
    expect(surClic).not.toHaveBeenCalled();
  });

  it('se désabonne au démontage, dans les deux enveloppes', async () => {
    // La fuite que ce test interdit est bornée à l'appareil où l'élément HA
    // n'arrive jamais — la tablette cuisine — mais c'est un kiosque qui tourne
    // en continu, avec des dizaines de boutons remontés à chaque navigation.
    const avant = pendingCountForTests();
    const carte = await monter('hs-card');
    const bouton = await monter('hs-button');
    carte.remove();
    bouton.remove();
    expect(pendingCountForTests()).toBe(avant);
  });

  it('tient la cible tactile de la tablette', async () => {
    const el = await monter('hs-button');
    const styles = (el.constructor as typeof HTMLElement & { styles: { cssText: string }[] });
    const texte = styles.styles.map((s) => s.cssText).join('');
    expect(texte).toContain('min-height: var(--hs-touch)');
  });
});
```

- [ ] **Step 2 : lancer le test pour vérifier qu'il échoue**

Run: `npx vitest run tests/shell-enveloppes.test.ts`
Expected: FAIL — modules introuvables.

- [ ] **Step 3 : écrire `hs-card.ts`**

```ts
/** Une carte : `<ha-card>` si Home Assistant l'a chargée, un repli visuellement
 *  identique sinon. Voir `ha-available.ts` pour pourquoi ce n'est pas
 *  simplement `<ha-card>` partout. */
import { LitElement, html, css } from 'lit';
import { customElement } from 'lit/decorators.js';
import { tokens } from './tokens';
import { isDefined, whenDefined } from './ha-available';

const HA_CARD = 'ha-card';

@customElement('hs-card')
export class HsCard extends LitElement {
  /** Le désabonnement rendu par `whenDefined`, à rappeler au démontage. Sans
   *  lui, chaque montage empile un rappel qui n'est vidé qu'à la définition de
   *  l'élément — or sur la tablette de la cuisine, qui ouvre `/home-stock`
   *  sans passer par Lovelace, `ha-card` n'est JAMAIS défini. Le kiosque
   *  tourne en continu : la table grossirait sans fin. */
  private desabonner?: () => void;

  connectedCallback(): void {
    super.connectedCallback();
    this.desabonner = whenDefined(HA_CARD, () => this.requestUpdate());
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    this.desabonner?.();
    this.desabonner = undefined;
  }

  static styles = [tokens, css`
    :host { display: block; }
    .repli {
      background: var(--hs-surface);
      color: var(--hs-text);
      border-radius: var(--hs-radius-m);
      border: 1px solid var(--hs-divider);
      overflow: hidden;
    }
  `];

  render() {
    if (isDefined(HA_CARD)) return html`<ha-card><slot></slot></ha-card>`;
    return html`<div class="repli"><slot></slot></div>`;
  }
}
```

- [ ] **Step 4 : écrire `hs-button.ts`**

```ts
/** Un bouton. Trois variantes seulement — c'est assez pour tout le panneau, et
 *  chacune porte SA paire fond/texte : jamais un `#fff` en dur sur une couleur
 *  de thème, qui donnerait 2,38:1 sous Graphite (primaire orange). */
import { LitElement, html, css } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { tokens } from './tokens';
import { isDefined, whenDefined } from './ha-available';

const HA_BUTTON = 'ha-button';

@customElement('hs-button')
export class HsButton extends LitElement {
  @property({ type: String }) variant: 'primary' | 'neutral' | 'danger' = 'neutral';
  @property({ type: Boolean, reflect: true }) disabled = false;
  /** Occupe toute la largeur disponible. */
  @property({ type: Boolean }) full = false;

  /** Même raison que dans `hs-card` : `whenDefined` rend un désabonnement, et
   *  ne pas l'appeler fait fuir la table sur l'appareil où `ha-button` ne se
   *  charge jamais. */
  private desabonner?: () => void;

  connectedCallback(): void {
    super.connectedCallback();
    this.desabonner = whenDefined(HA_BUTTON, () => this.requestUpdate());
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    this.desabonner?.();
    this.desabonner = undefined;
  }

  static styles = [tokens, css`
    :host { display: inline-block; }
    :host([disabled]) { pointer-events: none; opacity: 0.5; }
    button {
      display: inline-flex; align-items: center; justify-content: center;
      gap: var(--hs-space-2);
      min-height: var(--hs-touch);
      padding: 0 var(--hs-space-4);
      border-radius: var(--hs-radius-s);
      border: 1px solid transparent;
      font-family: var(--hs-font);
      font-size: 1rem;
      cursor: pointer;
    }
    .full { width: 100%; }
    .neutral { background: var(--hs-surface-2); color: var(--hs-text);
               border-color: var(--hs-divider); }
    .primary { background: var(--hs-accent); color: var(--hs-on-accent); }
    /* Bordure, jamais aplat : aucun texte ne tient 4,5:1 sur --hs-danger sous
       le thème HA par défaut. Voir spec § 6.1 ter. */
    .danger  { background: var(--hs-surface); color: var(--hs-text);
               border-color: var(--hs-danger); border-width: 2px; }
  `];

  render() {
    const classes = `${this.variant}${this.full ? ' full' : ''}`;
    // `ha-button` n'est utilisé que lorsqu'il est chargé ; sa variante est
    // portée par la classe, comme pour le repli, pour que les deux chemins
    // aient exactement le même contrat de style.
    if (isDefined(HA_BUTTON)) {
      return html`<ha-button class=${classes} ?disabled=${this.disabled}>
        <slot></slot>
      </ha-button>`;
    }
    return html`<button class=${classes} ?disabled=${this.disabled}>
      <slot></slot>
    </button>`;
  }
}
```

- [ ] **Step 5 : lancer le test pour vérifier qu'il passe**

Run: `npx vitest run tests/shell-enveloppes.test.ts`
Expected: PASS (6 tests).

- [ ] **Step 6 : commit**

```bash
git add src/shell/ui/hs-card.ts src/shell/ui/hs-button.ts tests/shell-enveloppes.test.ts
git commit -m "feat(shell): carte et bouton, ha-* quand ils sont là, repli identique sinon"
```

---

## Task 6 : brancher les dix-sept écrans sur les jetons

Mécanique, mais c'est la tâche qui fait disparaître les défauts inventoriés en Task 1.

**Files:**
- Modify: les 17 `src/ecrans/*.ts` (bloc `static styles` de chacun)
- Modify: `src/panneau.ts` (bloc `static styles`)
- Modify: `src/shell/ui/tokens.ts`, `src/shell/ui/on-color.ts`, `src/shell/ui/hs-button.ts`
- Modify: `tests/shell-tokens.test.ts`, `tests/shell-on-color.test.ts`, `tests/shell-enveloppes.test.ts`

**Réconciliation préalable (spec § 6.1 ter, tranchée après l'écriture des Tasks 2 et 5)** :
retirer le jeton `--hs-on-danger` de `tokens.ts`, retirer sa paire de la table `PAIRES` de
`on-color.ts`, adapter les deux assertions de `tests/shell-tokens.test.ts` qui l'énumèrent,
et passer la variante `danger` de `hs-button.ts` en bordure plutôt qu'en aplat (avec son
test). Faire cela **d'abord** : les dix-sept écrans s'y appuient ensuite.

**Interfaces:**
- Consumes: `tokens` (Task 2).
- Produces: rien de nouveau. Aucune signature ne change.

- [ ] **Step 1 : composer la feuille dans chaque écran**

Pour chacun des dix-huit fichiers : ajouter `import { tokens } from '../shell/ui/tokens';` (`'./shell/ui/tokens'` pour `panneau.ts`) et transformer

```ts
static styles = css`…`;
```

en

```ts
static styles = [tokens, css`…`];
```

- [ ] **Step 2 : remplacer chaque lecture directe par un jeton**

Dans les mêmes fichiers, substituer :

| Avant | Après |
|---|---|
| `var(--primary-text-color)` | `var(--hs-text)` |
| `var(--secondary-text-color)` | `var(--hs-text-2)` |
| `var(--card-background-color)` | `var(--hs-surface)` |
| `var(--secondary-background-color)` | `var(--hs-surface-2)` |
| `var(--primary-background-color)` | `var(--hs-surface-2)` |
| `var(--divider-color)` | `var(--hs-divider)` |
| `var(--primary-color)` | `var(--hs-accent)` |
| `var(--text-primary-color, #fff)` | `var(--hs-on-accent)` |
| `var(--error-color, #b3261e)` | `var(--hs-danger)` — **en bordure ou en icône, jamais en fond sous du texte** |
| `var(--warning-color)` | `var(--hs-warning)` |

Puis, **et c'est le cœur de la tâche** : tout `color: #fff` (ou toute autre couleur littérale) posé sur un fond de thème devient le `--hs-on-*` de ce fond. Exemples présents dans `panneau.ts` :

```ts
/* avant */ background: var(--error-color, #b3261e); color: #fff;
/* après */ background: var(--hs-surface); color: var(--hs-text);
            border-left: 4px solid var(--hs-danger);

/* avant */ background: rgba(255, 255, 255, 0.2); color: #fff;
/* après */ background: var(--hs-surface); color: var(--hs-text);
            border: 2px solid var(--hs-danger);
```

> ⚠️ **Aucun texte ne se pose sur un aplat `--hs-danger`** (spec § 6.1 ter).
> `--error-color` vaut `#db4437` sous le thème HA par défaut, dont la luminance
> tombe **exactement au point de bascule** : blanc dessus 4,29:1, noir dessus
> 4,29:1 — aucune couleur de texte ne passe 4,5:1. Un aplat rouge sous du texte
> ferait donc échouer le vérificateur quoi qu'on écrive. Le danger se dit par
> une **bordure**, une **icône** et un **liseré**, le texte restant
> `--hs-text` sur `--hs-surface`. Le jeton `--hs-on-danger` n'existe pas.
>
> Le geste destructif reste protégé par ce qui le protégeait déjà : **deux
> appuis**, armement puis confirmation.

- [ ] **Step 3 : porter les cibles tactiles à 62 px**

Remplacer partout `min-height: 48px` par `min-height: var(--hs-touch)` et `min-width: 88px` par `min-width: var(--hs-touch)` dans les blocs `static styles`. Ne PAS toucher aux `min-height` qui ne sont pas des cibles tactiles (`.case` du planning, par exemple, est une zone de dépôt).

- [ ] **Step 4 : vérifier qu'aucune couleur littérale ne subsiste**

Run:
```bash
grep -rnE '#[0-9a-fA-F]{3,8}\b|\brgba?\(' src/ecrans/ src/panneau.ts
```
Expected: **aucune sortie**. Toute occurrence restante est un défaut à corriger avant de continuer.

- [ ] **Step 5 : lancer toute la suite unitaire**

Run: `npx vitest run`
Expected: PASS — les 547 tests. Aucun ne mesure de style calculé (jsdom n'en calcule pas) ; un échec ici signale une faute de frappe dans un sélecteur, pas une régression visuelle.

- [ ] **Step 6 : lancer le vérificateur, qui doit REDEVENIR vert**

Run: `node outils/verifier-rendu.mjs`
Expected: PASS sur les trois palettes, cible 62 px, contraste 4,5:1, auto-vérification comprise.

Si des défauts subsistent, ce sont de vrais défauts : les corriger dans l'écran concerné, sans jamais abaisser un seuil ni réintroduire une couleur en dur.

- [ ] **Step 7 : déployer et commiter**

```bash
npm run build   # DÉPLOIE : écrit custom_components/home_stock/panel/
node outils/verifier-rendu.mjs --deploye
git add -A src/ ../custom_components/home_stock/panel/
git commit -m "refactor(ecrans): dix-sept feuilles, une seule échelle

Chaque écran lit désormais un jeton --hs-*, plus jamais une variable HA
directement, et aucune couleur littérale ne survit. Les #fff écrits en dur
sur des fonds de thème étaient le vrai défaut : sous Graphite, dont la
primaire est orange, ils donnaient 2,38:1."
```

---

# LOT 2 — Coquille et routes

## Task 7 : la table des destinations

**Files:**
- Create: `src/shell/destinations.ts`
- Test: `tests/shell-destinations.test.ts`

**Interfaces:**
- Consumes: `IconName` (Task 4).
- Produces:
  - `export type FamilyId = 'shopping' | 'stock' | 'kitchen' | 'house'`
  - `export type Destination = { screen: Ecran; label: string; family: FamilyId; segment: string; param?: 'id' | 'code'; root: boolean }`
  - `export const FAMILIES: ReadonlyArray<{ id: FamilyId; label: string; icon: IconName; root: Ecran }>`
  - `export const DESTINATIONS: ReadonlyArray<Destination>`
  - `export function destinationOf(screen: Ecran): Destination`
  - `export function familyOf(screen: Ecran): FamilyId`

`Ecran` reste exporté par `src/panneau.ts` — l'import croise donc les deux langues, ce qui est voulu : le type existant ne se renomme pas (contrainte globale).

- [ ] **Step 1 : écrire le test qui échoue**

`tests/shell-destinations.test.ts` :

```ts
import { describe, expect, it } from 'vitest';
import { DESTINATIONS, FAMILIES, destinationOf, familyOf }
  from '../src/shell/destinations';
import type { Ecran } from '../src/panneau';

const TOUS_LES_ECRANS: Ecran[] = ['scanner', 'fiche', 'panier', 'rangement', 'session',
  'catalogue', 'reglages', 'consommation', 'journal', 'recettes', 'recette',
  'planning', 'validation', 'piles', 'equipements', 'liste', 'ticket'];

describe('table des destinations', () => {
  it('couvre les dix-sept écrans, sans trou ni doublon', () => {
    const declares = DESTINATIONS.map((d) => d.screen).sort();
    expect(declares).toEqual([...TOUS_LES_ECRANS].sort());
  });

  it('donne un segment d’URL unique à chaque écran', () => {
    const segments = DESTINATIONS.map((d) => d.segment);
    expect(new Set(segments).size).toBe(segments.length);
  });

  it('n’emploie que des segments anglais en minuscules', () => {
    for (const d of DESTINATIONS) expect(d.segment).toMatch(/^[a-z][a-z-]*$/);
  });

  it('déclare exactement quatre familles, chacune avec une racine', () => {
    expect(FAMILIES).toHaveLength(4);
    for (const famille of FAMILIES) {
      const racines = DESTINATIONS.filter((d) => d.family === famille.id && d.root);
      expect(racines).toHaveLength(1);
      expect(racines[0].screen).toBe(famille.root);
    }
  });

  it('place les racines là où la spec les met', () => {
    expect(FAMILIES.map((f) => f.root)).toEqual(['liste', 'catalogue', 'planning', 'piles']);
  });

  it('rattache chaque écran à sa famille', () => {
    expect(familyOf('ticket')).toBe('shopping');
    expect(familyOf('journal')).toBe('stock');
    expect(familyOf('recette')).toBe('kitchen');
    expect(familyOf('reglages')).toBe('house');
  });

  it('garde un libellé français pour l’utilisateur', () => {
    expect(destinationOf('liste').label).toBe('Liste de courses');
    expect(destinationOf('rangement').label).toBe('Rangement');
  });
});
```

- [ ] **Step 2 : lancer le test pour vérifier qu'il échoue**

Run: `npx vitest run tests/shell-destinations.test.ts`
Expected: FAIL — module introuvable.

- [ ] **Step 3 : écrire la table**

```ts
/** LA source de vérité de la structure du panneau : la barre, le rail, le
 *  titre de l'en-tête et le routeur la lisent tous. Aucune seconde table à
 *  tenir synchronisée — c'était le défaut de l'ancienne barre, où l'ordre des
 *  boutons, leur libellé et l'écran atteint étaient répétés à trois endroits.
 *
 *  Les identifiants et les segments d'URL sont en ANGLAIS ; les libellés
 *  affichés restent en français. */
import type { Ecran } from '../panneau';
import type { IconName } from './ui/icons';

export type FamilyId = 'shopping' | 'stock' | 'kitchen' | 'house';

export type Destination = {
  screen: Ecran;
  /** Affiché : en français. */
  label: string;
  family: FamilyId;
  /** Le segment d'URL sous `/home-stock/`. */
  segment: string;
  /** Ce que la route porte après le segment, s'il y a lieu. */
  param?: 'id' | 'code';
  /** La destination racine de sa famille : celle qu'atteint la barre. */
  root: boolean;
};

export const FAMILIES: ReadonlyArray<{
  id: FamilyId; label: string; icon: IconName; root: Ecran;
}> = [
  { id: 'shopping', label: 'Courses', icon: 'cart', root: 'liste' },
  { id: 'stock', label: 'Stock', icon: 'package', root: 'catalogue' },
  { id: 'kitchen', label: 'Cuisine', icon: 'cutlery', root: 'planning' },
  { id: 'house', label: 'Maison', icon: 'home', root: 'piles' },
];

export const DESTINATIONS: ReadonlyArray<Destination> = [
  { screen: 'liste', label: 'Liste de courses', family: 'shopping', segment: 'list', root: true },
  { screen: 'session', label: 'Courses', family: 'shopping', segment: 'shopping', root: false },
  { screen: 'panier', label: 'Panier', family: 'shopping', segment: 'cart', root: false },
  { screen: 'rangement', label: 'Rangement', family: 'shopping', segment: 'put-away', root: false },
  { screen: 'ticket', label: 'Ticket', family: 'shopping', segment: 'receipt', param: 'id', root: false },
  { screen: 'scanner', label: 'Scanner', family: 'shopping', segment: 'scan', root: false },
  { screen: 'fiche', label: 'Article', family: 'shopping', segment: 'item', param: 'code', root: false },

  { screen: 'catalogue', label: 'Catalogue', family: 'stock', segment: 'catalog', root: true },
  { screen: 'journal', label: 'Journal', family: 'stock', segment: 'log', root: false },
  { screen: 'consommation', label: 'Manger', family: 'stock', segment: 'eat', param: 'id', root: false },

  { screen: 'planning', label: 'Planning', family: 'kitchen', segment: 'planner', root: true },
  { screen: 'recettes', label: 'Recettes', family: 'kitchen', segment: 'recipes', root: false },
  { screen: 'recette', label: 'Recette', family: 'kitchen', segment: 'recipe', param: 'id', root: false },
  { screen: 'validation', label: 'Validation du repas', family: 'kitchen', segment: 'validate', param: 'id', root: false },

  { screen: 'piles', label: 'Piles', family: 'house', segment: 'batteries', root: true },
  { screen: 'equipements', label: 'Équipements', family: 'house', segment: 'equipment', root: false },
  { screen: 'reglages', label: 'Réglages', family: 'house', segment: 'settings', root: false },
];

const PAR_ECRAN = new Map<Ecran, Destination>(DESTINATIONS.map((d) => [d.screen, d]));

export function destinationOf(screen: Ecran): Destination {
  const destination = PAR_ECRAN.get(screen);
  // Un écran absent de la table serait un écran sans titre, sans route et sans
  // famille : mieux vaut le bruit d'une exception au développement qu'un
  // en-tête vide en production.
  if (!destination) throw new Error(`Écran hors de la table des destinations : ${screen}`);
  return destination;
}

export function familyOf(screen: Ecran): FamilyId {
  return destinationOf(screen).family;
}
```

- [ ] **Step 4 : lancer le test pour vérifier qu'il passe**

Run: `npx vitest run tests/shell-destinations.test.ts`
Expected: PASS (7 tests).

- [ ] **Step 5 : commit**

```bash
git add src/shell/destinations.ts tests/shell-destinations.test.ts
git commit -m "feat(shell): une table des destinations, et une seule"
```

---

## Task 8 : le routeur

**Files:**
- Create: `src/shell/router.ts`
- Test: `tests/shell-router.test.ts`

**Interfaces:**
- Consumes: `DESTINATIONS`, `destinationOf` (Task 7).
- Produces:
  - `export type Route = { screen: Ecran; param: string | null }`
  - `export function parsePath(path: string): Route | null`
  - `export function pathOf(screen: Ecran, param?: string | number | null): string`
  - `export const DEFAULT_PATH = '/list'`

- [ ] **Step 1 : écrire le test qui échoue**

`tests/shell-router.test.ts` :

```ts
import { describe, expect, it } from 'vitest';
import { DEFAULT_PATH, parsePath, pathOf } from '../src/shell/router';
import { DESTINATIONS } from '../src/shell/destinations';

describe('routeur', () => {
  it('lit un segment simple', () => {
    expect(parsePath('/list')).toEqual({ screen: 'liste', param: null });
    expect(parsePath('/catalog')).toEqual({ screen: 'catalogue', param: null });
  });

  it('lit un segment paramétré', () => {
    expect(parsePath('/recipe/12')).toEqual({ screen: 'recette', param: '12' });
    expect(parsePath('/item/3229820129488'))
      .toEqual({ screen: 'fiche', param: '3229820129488' });
  });

  it('tolère la barre finale et la barre initiale absente', () => {
    expect(parsePath('list')).toEqual({ screen: 'liste', param: null });
    expect(parsePath('/list/')).toEqual({ screen: 'liste', param: null });
  });

  it('rend null sur une route inconnue, ou sur un paramètre manquant', () => {
    expect(parsePath('/nawak')).toBeNull();
    expect(parsePath('')).toBeNull();
    // `recipe` SANS identifiant n'a pas d'écran à montrer : l'écran recette
    // exige un `recipeId`. Mieux vaut retomber sur la racine que rendre du vide.
    expect(parsePath('/recipe')).toBeNull();
  });

  it('ignore un paramètre passé à un écran qui n’en attend pas', () => {
    expect(parsePath('/list/42')).toEqual({ screen: 'liste', param: null });
  });

  it('fabrique le chemin d’un écran', () => {
    expect(pathOf('liste')).toBe('/list');
    expect(pathOf('recette', 12)).toBe('/recipe/12');
    expect(pathOf('fiche', '3229820129488')).toBe('/item/3229820129488');
  });

  it('fait l’aller-retour pour chaque destination de la table', () => {
    for (const d of DESTINATIONS) {
      const chemin = pathOf(d.screen, d.param ? '7' : null);
      expect(parsePath(chemin)).toEqual({ screen: d.screen, param: d.param ? '7' : null });
    }
  });

  it('sait où retomber', () => {
    expect(DEFAULT_PATH).toBe('/list');
    expect(parsePath(DEFAULT_PATH)).toEqual({ screen: 'liste', param: null });
  });
});
```

- [ ] **Step 2 : lancer le test pour vérifier qu'il échoue**

Run: `npx vitest run tests/shell-router.test.ts`
Expected: FAIL — module introuvable.

- [ ] **Step 3 : écrire le routeur**

```ts
/** `path` ⇄ écran, dans les deux sens, à partir de la SEULE table des
 *  destinations. Home Assistant nous livre `route.path` (voir
 *  `ha-panel-custom`) : tout ce qui suit `/home-stock`. */
import type { Ecran } from '../panneau';
import { DESTINATIONS, destinationOf } from './destinations';

export type Route = { screen: Ecran; param: string | null };

export const DEFAULT_PATH = '/list';

const PAR_SEGMENT = new Map(DESTINATIONS.map((d) => [d.segment, d]));

export function parsePath(path: string): Route | null {
  const morceaux = path.split('/').filter((m) => m.length > 0);
  if (morceaux.length === 0) return null;
  const destination = PAR_SEGMENT.get(morceaux[0]);
  if (!destination) return null;
  if (!destination.param) {
    // Un paramètre surnuméraire est ignoré, pas rejeté : `/list/42` reste la
    // liste. Rejeter renverrait l'utilisateur à la racine pour une URL qui
    // désigne sans ambiguïté l'écran qu'il voulait.
    return { screen: destination.screen, param: null };
  }
  // Un écran paramétré SANS paramètre n'a rien à montrer : `recette` sans
  // `recipeId` rendrait un écran vide. On préfère la retombée sur la racine.
  if (morceaux.length < 2) return null;
  return { screen: destination.screen, param: morceaux[1] };
}

export function pathOf(screen: Ecran, param: string | number | null = null): string {
  const destination = destinationOf(screen);
  if (!destination.param || param === null || param === undefined) return `/${destination.segment}`;
  return `/${destination.segment}/${param}`;
}
```

- [ ] **Step 4 : lancer le test pour vérifier qu'il passe**

Run: `npx vitest run tests/shell-router.test.ts`
Expected: PASS (8 tests).

- [ ] **Step 5 : commit**

```bash
git add src/shell/router.ts tests/shell-router.test.ts
git commit -m "feat(shell): un routeur qui ne connaît que la table des destinations"
```

---

## Task 9 : la barre de navigation

**Files:**
- Create: `src/shell/nav-bar.ts`
- Test: `tests/shell-nav-bar.test.ts`

**Interfaces:**
- Consumes: `FAMILIES`, `familyOf` (Task 7), `hs-icon` (Task 4), `tokens` (Task 2).
- Produces: `<hs-nav-bar .current=${Ecran} .rail=${boolean} .badges=${Partial<Record<FamilyId, number>>}>`, émet `CustomEvent<{ family: FamilyId }>('famille-choisie', {bubbles, composed})`.

- [ ] **Step 1 : écrire le test qui échoue**

`tests/shell-nav-bar.test.ts` :

```ts
import { afterEach, describe, expect, it, vi } from 'vitest';
import '../src/shell/nav-bar';
import type { FamilyId } from '../src/shell/destinations';

afterEach(() => { document.body.innerHTML = ''; });

async function monter(props: Record<string, unknown> = {}) {
  const el = document.createElement('hs-nav-bar') as HTMLElement
    & { updateComplete: Promise<unknown> } & Record<string, unknown>;
  Object.assign(el, { current: 'liste', rail: false, badges: {} }, props);
  document.body.appendChild(el);
  await el.updateComplete;
  return el;
}

describe('barre de navigation', () => {
  it('rend TOUJOURS les quatre familles, y compris celle où l’on est', async () => {
    // Le défaut de l'ancienne barre : elle masquait le bouton de l'écran
    // courant, ce qui décalait tous les autres à chaque navigation.
    const el = await monter({ current: 'liste' });
    const boutons = el.shadowRoot!.querySelectorAll('.destination');
    expect(boutons).toHaveLength(4);
  });

  it('marque la famille courante, et elle seule', async () => {
    const el = await monter({ current: 'journal' });   // famille « stock »
    const actives = el.shadowRoot!.querySelectorAll('.destination.active');
    expect(actives).toHaveLength(1);
    expect(actives[0].getAttribute('data-family')).toBe('stock');
    expect(actives[0].getAttribute('aria-current')).toBe('page');
  });

  it('marque la famille depuis un SOUS-écran, pas seulement depuis la racine', async () => {
    const el = await monter({ current: 'reglages' });  // famille « house »
    expect(el.shadowRoot!.querySelector('.destination.active')!
      .getAttribute('data-family')).toBe('house');
  });

  it('émet la famille choisie', async () => {
    const el = await monter({ current: 'liste' });
    const recu = vi.fn();
    el.addEventListener('famille-choisie', (e) => recu((e as CustomEvent).detail));
    (el.shadowRoot!.querySelector('[data-family="kitchen"]') as HTMLElement).click();
    expect(recu).toHaveBeenCalledWith({ family: 'kitchen' });
  });

  it('affiche une pastille de compte, et rien quand le compte est nul', async () => {
    const el = await monter({ badges: { shopping: 3, house: 0 } as Partial<Record<FamilyId, number>> });
    expect(el.shadowRoot!.querySelector('[data-family="shopping"] .badge')!.textContent!.trim())
      .toBe('3');
    expect(el.shadowRoot!.querySelector('[data-family="house"] .badge')).toBeNull();
  });

  it('annonce la pastille aux lecteurs d’écran', async () => {
    const el = await monter({ badges: { shopping: 3 } });
    expect(el.shadowRoot!.querySelector('[data-family="shopping"]')!
      .getAttribute('aria-label')).toBe('Courses, 3 en attente');
  });

  it('passe en rail quand on le lui demande', async () => {
    const el = await monter({ rail: true });
    expect(el.shadowRoot!.querySelector('.barre')!.classList.contains('rail')).toBe(true);
  });
});
```

- [ ] **Step 2 : lancer le test pour vérifier qu'il échoue**

Run: `npx vitest run tests/shell-nav-bar.test.ts`
Expected: FAIL — module introuvable.

- [ ] **Step 3 : écrire la barre**

```ts
/** Les quatre familles, en bas sur téléphone et tablette, en rail à gauche sur
 *  bureau. Elles sont TOUJOURS les quatre : l'ancienne barre masquait le
 *  bouton de l'écran courant, ce qui décalait tous les autres à chaque
 *  navigation et faisait perdre le repère. */
import { LitElement, html, css, nothing } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { tokens } from './ui/tokens';
import './ui/hs-icon';
import { FAMILIES, familyOf, type FamilyId } from './destinations';
import type { Ecran } from '../panneau';

@customElement('hs-nav-bar')
export class HsNavBar extends LitElement {
  @property({ attribute: false }) current: Ecran = 'liste';
  @property({ type: Boolean }) rail = false;
  @property({ attribute: false }) badges: Partial<Record<FamilyId, number>> = {};

  static styles = [tokens, css`
    :host { display: block; }
    .barre {
      display: flex; background: var(--hs-surface);
      border-top: 1px solid var(--hs-divider);
    }
    .barre.rail {
      flex-direction: column;
      border-top: none; border-right: 1px solid var(--hs-divider);
      height: 100%;
    }
    .destination {
      flex: 1 1 0; position: relative;
      display: flex; flex-direction: column; align-items: center; justify-content: center;
      gap: var(--hs-space-1);
      min-height: var(--hs-touch); min-width: var(--hs-touch);
      padding: var(--hs-space-2) var(--hs-space-1);
      border: none; background: none; cursor: pointer;
      font-family: var(--hs-font); font-size: 0.75rem;
      color: var(--hs-text-2);
    }
    .barre.rail .destination { flex: 0 0 auto; }
    .destination.active { color: var(--hs-accent); font-weight: 600; }
    .badge {
      position: absolute; top: var(--hs-space-1);
      /* Décalé vers la droite du centre : la pastille se pose sur l'angle de
         l'icône, pas sur le libellé. */
      left: 56%;
      min-width: 18px; height: 18px; box-sizing: border-box;
      padding: 0 4px; border-radius: 9px;
      background: var(--hs-accent); color: var(--hs-on-accent);
      font-size: 0.7rem; line-height: 18px; text-align: center;
    }
  `];

  private choisir(family: FamilyId): void {
    this.dispatchEvent(new CustomEvent('famille-choisie', {
      detail: { family }, bubbles: true, composed: true,
    }));
  }

  render() {
    const familleCourante = familyOf(this.current);
    return html`
      <nav class="barre ${this.rail ? 'rail' : ''}">
        ${FAMILIES.map((famille) => {
          const compte = this.badges[famille.id] ?? 0;
          const active = famille.id === familleCourante;
          return html`
            <button class="destination ${active ? 'active' : ''}"
                    data-family=${famille.id}
                    aria-current=${active ? 'page' : nothing}
                    aria-label=${compte > 0 ? `${famille.label}, ${compte} en attente` : famille.label}
                    @click=${() => this.choisir(famille.id)}>
              <hs-icon name=${famille.icon}></hs-icon>
              <span>${famille.label}</span>
              ${compte > 0 ? html`<span class="badge">${compte}</span>` : nothing}
            </button>`;
        })}
      </nav>`;
  }
}
```

- [ ] **Step 4 : lancer le test pour vérifier qu'il passe**

Run: `npx vitest run tests/shell-nav-bar.test.ts`
Expected: PASS (7 tests).

- [ ] **Step 5 : commit**

```bash
git add src/shell/nav-bar.ts tests/shell-nav-bar.test.ts
git commit -m "feat(shell): quatre destinations qui ne bougent plus"
```

---

## Task 10 : l'en-tête

**Files:**
- Create: `src/shell/header.ts`
- Test: `tests/shell-header.test.ts`

**Interfaces:**
- Consumes: `destinationOf`, `familyOf`, `FAMILIES` (Task 7), `hs-icon`, `hs-button`, `tokens`.
- Produces: `<hs-header .current=${Ecran} .pending=${number} .error=${string|null}>`, émet `retour-demande` (sans détail) et `erreur-acquittee`.

- [ ] **Step 1 : écrire le test qui échoue**

`tests/shell-header.test.ts` :

```ts
import { afterEach, describe, expect, it, vi } from 'vitest';
import '../src/shell/header';

afterEach(() => { document.body.innerHTML = ''; });

async function monter(props: Record<string, unknown> = {}) {
  const el = document.createElement('hs-header') as HTMLElement
    & { updateComplete: Promise<unknown> } & Record<string, unknown>;
  Object.assign(el, { current: 'liste', pending: 0, error: null }, props);
  document.body.appendChild(el);
  await el.updateComplete;
  return el;
}

describe('en-tête', () => {
  it('porte le titre de l’écran, en français', async () => {
    const el = await monter({ current: 'rangement' });
    expect(el.shadowRoot!.querySelector('.titre')!.textContent!.trim()).toBe('Rangement');
  });

  it('n’offre pas de retour sur une racine de famille', async () => {
    const el = await monter({ current: 'liste' });
    expect(el.shadowRoot!.querySelector('.retour')).toBeNull();
  });

  it('offre un retour sur un sous-écran', async () => {
    const el = await monter({ current: 'reglages' });
    expect(el.shadowRoot!.querySelector('.retour')).not.toBeNull();
  });

  it('émet la demande de retour', async () => {
    const el = await monter({ current: 'reglages' });
    const recu = vi.fn();
    el.addEventListener('retour-demande', recu);
    (el.shadowRoot!.querySelector('.retour') as HTMLElement).click();
    expect(recu).toHaveBeenCalledTimes(1);
  });

  it('montre le nombre d’écritures en attente, et rien à zéro', async () => {
    const avec = await monter({ pending: 2 });
    expect(avec.shadowRoot!.querySelector('.attente')!.textContent).toContain('2');
    document.body.innerHTML = '';
    const sans = await monter({ pending: 0 });
    expect(sans.shadowRoot!.querySelector('.attente')).toBeNull();
  });

  it('porte la bannière de refus et son accusé de réception', async () => {
    const el = await monter({ error: 'Stock insuffisant' });
    expect(el.shadowRoot!.querySelector('.erreur')!.textContent)
      .toContain('Stock insuffisant');
    const recu = vi.fn();
    el.addEventListener('erreur-acquittee', recu);
    (el.shadowRoot!.querySelector('.fermer-erreur') as HTMLElement).click();
    expect(recu).toHaveBeenCalledTimes(1);
  });

  it('annonce la bannière comme une alerte', async () => {
    const el = await monter({ error: 'Stock insuffisant' });
    expect(el.shadowRoot!.querySelector('.erreur')!.getAttribute('role')).toBe('alert');
  });
});
```

- [ ] **Step 2 : lancer le test pour vérifier qu'il échoue**

Run: `npx vitest run tests/shell-header.test.ts`
Expected: FAIL — module introuvable.

- [ ] **Step 3 : écrire l'en-tête**

```ts
/** L'en-tête constant : retour, titre, et les deux indicateurs qui étaient
 *  jusqu'ici posés à la main dans `panneau.ts` — le nombre d'écritures en
 *  file, et le dernier refus du serveur. */
import { LitElement, html, css, nothing } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { tokens } from './ui/tokens';
import './ui/hs-icon';
import { destinationOf } from './destinations';
import type { Ecran } from '../panneau';

@customElement('hs-header')
export class HsHeader extends LitElement {
  @property({ attribute: false }) current: Ecran = 'liste';
  @property({ type: Number }) pending = 0;
  /** Le message du serveur, déjà en français : on ne le reformule pas. */
  @property({ attribute: false }) error: string | null = null;

  static styles = [tokens, css`
    :host { display: block; }
    .barre {
      display: flex; align-items: center; gap: var(--hs-space-2);
      min-height: var(--hs-touch);
      padding: var(--hs-space-2) var(--hs-space-3);
      background: var(--hs-surface); color: var(--hs-text);
      border-bottom: 1px solid var(--hs-divider);
    }
    .retour {
      display: inline-flex; align-items: center; justify-content: center;
      min-height: var(--hs-touch); min-width: var(--hs-touch);
      border: none; background: none; color: inherit; cursor: pointer;
      border-radius: var(--hs-radius-s);
    }
    .titre { flex: 1; font-size: 1.15rem; font-weight: 600; }
    .attente {
      display: inline-flex; align-items: center; gap: var(--hs-space-1);
      color: var(--hs-text-2); font-size: 0.85rem;
    }
    /* Pas d'aplat rouge sous ce texte : --error-color vaut #db4437 sous le
       thème HA par défaut, une luminance au point de bascule exact où blanc et
       noir donnent tous deux 4,29:1 — sous le seuil. Le danger passe par le
       liseré et l'icône ; le texte garde 17:1. Voir spec § 6.1 ter. */
    .erreur {
      display: flex; align-items: center; gap: var(--hs-space-2);
      margin: 0; padding: var(--hs-space-2) var(--hs-space-3);
      background: var(--hs-surface); color: var(--hs-text);
      border-left: 4px solid var(--hs-danger);
      border-bottom: 1px solid var(--hs-divider);
      font-size: 0.9rem;
    }
    .erreur hs-icon { color: var(--hs-danger); flex: 0 0 auto; }
    .message-erreur { flex: 1; }
    .fermer-erreur {
      min-height: var(--hs-touch); min-width: var(--hs-touch);
      border: 1px solid var(--hs-divider); border-radius: var(--hs-radius-s);
      background: var(--hs-surface-2); color: var(--hs-text);
      font-weight: 600; cursor: pointer;
    }
  `];

  render() {
    const destination = destinationOf(this.current);
    return html`
      <div class="barre">
        ${destination.root ? nothing : html`
          <button class="retour" aria-label="Retour" @click=${() => this.dispatchEvent(
            new CustomEvent('retour-demande', { bubbles: true, composed: true }))}>
            <hs-icon name="back" label="Retour"></hs-icon>
          </button>`}
        <span class="titre">${destination.label}</span>
        ${this.pending > 0 ? html`
          <span class="attente">
            <hs-icon name="clock"></hs-icon>${this.pending} en attente
          </span>` : nothing}
      </div>
      ${this.error ? html`
        <p class="erreur" role="alert">
          <hs-icon name="alert"></hs-icon>
          <span class="message-erreur">${this.error}</span>
          <button class="fermer-erreur" @click=${() => this.dispatchEvent(
            new CustomEvent('erreur-acquittee', { bubbles: true, composed: true }))}>OK</button>
        </p>` : nothing}`;
  }
}
```

- [ ] **Step 4 : lancer le test pour vérifier qu'il passe**

Run: `npx vitest run tests/shell-header.test.ts`
Expected: PASS (7 tests).

- [ ] **Step 5 : commit**

```bash
git add src/shell/header.ts tests/shell-header.test.ts
git commit -m "feat(shell): un en-tête qui dit où l'on est et comment en sortir"
```

---

## Task 11 : le panneau adopte la coquille et les routes

La plus délicate du lot : `panneau.ts` perd `rendreNavigation` et `rendreErreurFile`, gagne la propriété `route`, et devient l'orchestrateur qu'il aurait dû rester.

**Files:**
- Modify: `src/panneau.ts` (méthodes `rendreNavigation` lignes 389-447, `rendreErreurFile` lignes 449-458, `render`, `static styles`, `connectedCallback`)
- Test: `tests/panneau-routes.test.ts` (créer)
- Modify: `tests/panneau.test.ts` (les assertions qui cherchent les anciens boutons par leur texte)

**Interfaces:**
- Consumes: `parsePath`, `pathOf`, `DEFAULT_PATH` (Task 8), `FAMILIES`, `familyOf`, `destinationOf` (Task 7), `<hs-nav-bar>` (Task 9), `<hs-header>` (Task 10), `primeHaComponents` (Task 3).
- Produces: `@property({attribute:false}) route: {prefix: string; path: string} | undefined` sur `<home-stock-panel>`.

- [ ] **Step 1 : écrire le test qui échoue**

`tests/panneau-routes.test.ts` :

```ts
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import '../src/panneau';
import type { Hass } from '../src/connexion';

function hassFactice(): Hass {
  return {
    connection: {
      sendMessagePromise: vi.fn().mockResolvedValue(null),
      subscribeMessage: vi.fn().mockResolvedValue(() => {}),
    },
    language: 'fr',
  } as unknown as Hass;
}

function laisserPasserLesMicrotaches(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

async function monter(path: string) {
  const el = document.createElement('home-stock-panel') as HTMLElement
    & { updateComplete: Promise<unknown>; hass: Hass; route: unknown; ecran: string };
  el.hass = hassFactice();
  el.route = { prefix: '/home-stock', path };
  document.body.appendChild(el);
  await laisserPasserLesMicrotaches();
  await el.updateComplete;
  return el;
}

describe('panneau : routes d’URL', () => {
  beforeEach(() => { window.localStorage.clear(); });
  afterEach(() => { document.body.innerHTML = ''; vi.restoreAllMocks(); });

  it('ouvre l’écran que l’URL désigne', async () => {
    const el = await monter('/catalog');
    expect(el.ecran).toBe('catalogue');
  });

  it('ouvre un écran paramétré avec son paramètre', async () => {
    const el = await monter('/recipe/12');
    expect(el.ecran).toBe('recette');
    expect(el.shadowRoot!.querySelector('home-stock-recette')).not.toBeNull();
  });

  it('retombe sur la liste devant une route inconnue', async () => {
    const el = await monter('/nawak');
    expect(el.ecran).toBe('liste');
  });

  it('suit un changement de route venu de Home Assistant (bouton Retour)', async () => {
    const el = await monter('/catalog');
    el.route = { prefix: '/home-stock', path: '/batteries' };
    await el.updateComplete;
    expect(el.ecran).toBe('piles');
  });

  it('pousse l’URL et prévient Home Assistant quand on navigue', async () => {
    const el = await monter('/list');
    const pushState = vi.spyOn(window.history, 'pushState');
    const evenements: string[] = [];
    window.addEventListener('location-changed', () => evenements.push('vu'));

    const barre = el.shadowRoot!.querySelector('hs-nav-bar')!;
    barre.dispatchEvent(new CustomEvent('famille-choisie', {
      detail: { family: 'kitchen' }, bubbles: true, composed: true,
    }));
    await el.updateComplete;

    expect(el.ecran).toBe('planning');
    expect(pushState).toHaveBeenCalledWith(null, '', '/home-stock/planner');
    expect(evenements).toHaveLength(1);
  });

  it('rend la barre et l’en-tête sur tout écran sauf la fiche', async () => {
    const el = await monter('/list');
    expect(el.shadowRoot!.querySelector('hs-nav-bar')).not.toBeNull();
    expect(el.shadowRoot!.querySelector('hs-header')).not.toBeNull();
  });

  it('remonte au retour de l’en-tête vers la racine de la famille', async () => {
    const el = await monter('/settings');           // famille « house »
    const entete = el.shadowRoot!.querySelector('hs-header')!;
    entete.dispatchEvent(new CustomEvent('retour-demande', { bubbles: true, composed: true }));
    await el.updateComplete;
    expect(el.ecran).toBe('piles');                  // la racine de « house »
  });
});
```

- [ ] **Step 2 : lancer le test pour vérifier qu'il échoue**

Run: `npx vitest run tests/panneau-routes.test.ts`
Expected: FAIL — `el.route` n'est pas une propriété observée, l'écran reste `scanner`.

- [ ] **Step 3 : brancher la route dans `panneau.ts`**

Ajouter les imports et la propriété :

```ts
import type { PropertyValues } from 'lit';
import './shell/nav-bar';
import './shell/header';
import { primeHaComponents } from './shell/ui/ha-available';
import { tokens } from './shell/ui/tokens';
import type { IconName } from './shell/ui/icons';
import { FAMILIES, familyOf, type FamilyId } from './shell/destinations';
import { parsePath, pathOf } from './shell/router';
```

`DEFAULT_PATH` n'est pas importé ici : la retombée passe par
`naviguerVers('liste', null, true)`, qui reconstruit le chemin depuis la table.
Importer les deux ferait deux façons de dire la même chose.

```ts
  /** Posée par `ha-panel-custom` : `{prefix: '/home-stock', path: '/list'}`.
   *  C'est aussi par elle que revient le bouton Retour du navigateur — HA
   *  écoute `popstate` et nous repasse la route, donc rien à écouter ici. */
  @property({ attribute: false }) route?: { prefix: string; path: string };
```

Et la réaction :

```ts
  /** Le dernier `path` déjà appliqué : sans lui, chaque rendu rejouerait la
   *  route et écraserait une navigation faite entre-temps par un événement
   *  métier (`recette-ouverte`, par exemple). */
  private dernierChemin: string | null = null;

  willUpdate(changees: PropertyValues): void {
    if (!changees.has('route')) return;
    const chemin = this.route?.path ?? '';
    if (chemin === this.dernierChemin) return;
    this.dernierChemin = chemin;
    this.appliquerChemin(chemin);
  }

  private appliquerChemin(chemin: string): void {
    const route = parsePath(chemin);
    if (!route) {
      // `replace` : une route inconnue ne mérite pas une entrée d'historique
      // dans laquelle le bouton Retour viendrait retomber.
      this.naviguerVers('liste', null, true);
      return;
    }
    this.ecran = route.screen;
    this.appliquerParametre(route.screen, route.param);
  }

  /** Chaque écran paramétré range son paramètre là où son composant le lit. */
  private appliquerParametre(ecran: Ecran, param: string | null): void {
    if (param === null) return;
    if (ecran === 'recette') this.recetteOuverte = Number(param);
    else if (ecran === 'validation') this.repasAValider = Number(param);
    else if (ecran === 'consommation') this.produitAManger = Number(param);
    else if (ecran === 'ticket') this.ticketOuvert = Number(param);
    else if (ecran === 'fiche') void this.surCodeLu(
      new CustomEvent('code-lu', { detail: { code: param } }));
  }
```

- [ ] **Step 4 : faire naviguer le panneau par l'URL**

Remplacer le corps de `demanderNavigation` pour qu'il passe par l'URL — la navigation devient un effet de la route, jamais l'inverse :

```ts
  /** La navigation passe TOUJOURS par l'URL : `history.pushState` puis
   *  `location-changed`, la convention du frontend HA. Home Assistant nous
   *  repasse alors `route`, et `willUpdate` applique l'écran. Un seul chemin
   *  de navigation, donc le bouton Retour du navigateur et le geste système
   *  d'Android marchent sans une ligne de plus. */
  private naviguerVers(ecran: Ecran, param: string | number | null = null,
                       remplacer = false): void {
    const chemin = pathOf(ecran, param);
    const url = `${this.route?.prefix ?? '/home-stock'}${chemin}`;
    if (remplacer) window.history.replaceState(null, '', url);
    else window.history.pushState(null, '', url);
    window.dispatchEvent(new CustomEvent('location-changed', {
      detail: { replace: remplacer }, bubbles: true, composed: true,
    }));
    // HA ne nous repassera `route` que s'il écoute vraiment ; en test, et si
    // une version future changeait de convention, on applique nous-mêmes.
    this.dernierChemin = chemin;
    this.ecran = ecran;
    this.appliquerParametre(ecran, param === null ? null : String(param));
  }
```

Conserver le garde-fou existant : si `this.enAttenteRangement.length > 0` et que l'on quitte `rangement`, armer `navigationArmee` **avant** d'appeler `naviguerVers`. La confirmation ne change pas de texte ni de comportement.

- [ ] **Step 5 : remplacer le rendu de la navigation**

Supprimer `rendreNavigation()` et `rendreErreurFile()`. Nouveau `render()` :

```ts
  private get pastilles(): Partial<Record<FamilyId, number>> {
    const aRanger = this.lignesARanger.length;
    const enPanier = this.session?.session?.state === 'shopping'
      ? this.session.totals.lines : 0;
    return { shopping: aRanger || enPanier };
  }

  render() {
    // La fiche occupe l'écran entier : c'était déjà le cas (l'ancienne
    // `rendreNavigation` rendait `nothing` sur `fiche`), et pour la même
    // raison — on y scanne, la coquille ne doit rien voler à la caméra.
    if (this.ecran === 'fiche') return this.rendreEcran();
    if (this.navigationArmee) return this.rendreConfirmationQuitter();
    return html`
      <div class="coquille ${this.large ? 'large' : ''}">
        <hs-nav-bar class="navigation" .current=${this.ecran} .rail=${this.large}
          .badges=${this.pastilles} @famille-choisie=${this.surFamilleChoisie}></hs-nav-bar>
        <div class="colonne">
          <hs-header .current=${this.ecran} .pending=${this.enAttente} .error=${this.erreurFile}
            @retour-demande=${this.surRetour}
            @erreur-acquittee=${() => { this.erreurFile = null; }}></hs-header>
          <main class="contenu">${this.rendreEcran()}</main>
        </div>
      </div>`;
  }

  private surFamilleChoisie = (evenement: CustomEvent<{ family: FamilyId }>): void => {
    const famille = FAMILIES.find((f) => f.id === evenement.detail.family)!;
    this.demanderNavigation(famille.root);
  };

  /** Le retour remonte à la racine de la famille courante — jamais à
   *  `history.back()`, qui ramènerait à l'écran précédent quelle que soit sa
   *  famille et ferait sauter l'utilisateur d'un bout à l'autre du panneau. */
  private surRetour = (): void => {
    this.demanderNavigation(FAMILIES.find((f) => f.id === familyOf(this.ecran))!.root);
  };
```

Et les styles de la coquille, en remplacement de `.navigation` / `.nav-bouton` / `.erreur-file` :

```ts
  static styles = [tokens, css`
    :host { display: block; height: 100%; background: var(--hs-surface-2); }
    /* Ordre du DOM : la barre AVANT la colonne, pour que le rail se pose
       naturellement à gauche en row. En column-reverse, la barre repasse en
       bas de l'écran sans quitter sa place dans le DOM — donc sans casser
       l'ordre de tabulation, et sans dvh ni :has(), absents de Chrome 100
       (la tablette de la cuisine). */
    .coquille { display: flex; flex-direction: column-reverse; height: 100%; }
    .coquille.large { flex-direction: row; }
    .colonne { flex: 1; display: flex; flex-direction: column; min-height: 0; }
    .contenu { flex: 1; overflow-y: auto; }
    .navigation { flex: 0 0 auto; }
    .confirmation-quitter-rangement {
      display: flex; flex-direction: column; gap: var(--hs-space-2);
      padding: var(--hs-space-3);
      background: var(--hs-surface); color: var(--hs-text);
    }
    .confirmation-quitter-rangement p { margin: 0; }
    .confirmer-quitter, .annuler-quitter {
      min-height: var(--hs-touch); width: 100%;
      border-radius: var(--hs-radius-s); border: none; font-size: 0.95rem;
      font-family: var(--hs-font); cursor: pointer;
    }
    /* Bordure, pas aplat : aucun texte ne tient 4,5:1 sur --hs-danger sous le
       thème HA par défaut (spec § 6.1 ter). Ce qui protège ce geste, c'est
       qu'il demande deux appuis — pas sa couleur. */
    .confirmer-quitter {
      background: var(--hs-surface); color: var(--hs-text);
      border: 2px solid var(--hs-danger);
    }
    .annuler-quitter { background: var(--hs-accent); color: var(--hs-on-accent); }
  `];
```

Appeler `primeHaComponents()` en tête de `connectedCallback`, et
`appliquerCouleursDeTexte(this)` en tête de `firstUpdated()` — pas dans
`connectedCallback`, où la sonde ne pourrait pas encore résoudre les jetons de
la feuille adoptée. Le rappeler à chaque changement de `hass` (Home Assistant
en fournit un nouvel objet quand le thème change), en sortant tôt si les
couleurs résolues n'ont pas bougé :

```ts
  updated(changees: PropertyValues): void {
    // Le thème peut changer sous nos pieds (bascule clair/sombre, changement
    // de thème dans le profil) : HA repasse alors un nouvel objet `hass`.
    // L'appel est bon marché — une sonde, trois lectures — et `on-color.ts`
    // ne pose rien s'il ne sait pas lire.
    if (changees.has('hass')) appliquerCouleursDeTexte(this);
  }
```

et importer `import { appliquerCouleursDeTexte } from './shell/ui/on-color';`.

- [ ] **Step 6 : lancer les tests de routes**

Run: `npx vitest run tests/panneau-routes.test.ts`
Expected: PASS (7 tests).

- [ ] **Step 7 : réparer les tests existants qui cherchaient les anciens boutons**

Run: `npx vitest run`
Expected: quelques échecs dans `tests/panneau.test.ts` et les tests d'écran qui cliquaient un bouton de navigation par son texte (`Catalogue`, `Piles`…).

Les réparer en pilotant la nouvelle coquille : `hs-nav-bar` pour changer de famille, ou en posant directement `element.route`. **Ne jamais** contourner en forçant `element.ecran` : ce serait tester un chemin que l'utilisateur n'emprunte pas.

Run: `npx vitest run`
Expected: PASS — toute la suite.

- [ ] **Step 8 : mettre le vérificateur à la nouvelle coquille**

Dans `outils/verifier-rendu.mjs`, l'action `click-nav` cherche un bouton par son texte dans le panneau. La réécrire pour cliquer la famille puis, s'il y a lieu, la destination :

```js
// La navigation ne se fait plus par un bouton texte par écran, mais par
// famille : le scénario nomme l'ÉCRAN voulu, et le harnais trouve sa famille
// dans la table, comme le ferait un utilisateur.
if (action.type === 'click-nav') {
  const barre = panneau.shadowRoot.querySelector('hs-nav-bar');
  const famille = FAMILLE_PAR_ECRAN[action.ecran];
  const bouton = barre.shadowRoot.querySelector(`[data-family="${famille}"]`);
  if (!bouton) throw new Error(`Famille introuvable dans la barre : ${famille}`);
  bouton.click();
}
```

Remplacer dans chaque scénario `{ type: 'click-nav', texte: 'Catalogue' }` par `{ type: 'click-nav', ecran: 'catalogue' }`, et **ajouter** un `{ type: 'route', path: '/log' }` pour les écrans qui ne sont pas la racine de leur famille (Journal, Recettes, Équipements, Réglages, Ticket…) :

```js
if (action.type === 'route') {
  panneau.route = { prefix: '/home-stock', path: action.path };
}
```

Run: `node outils/verifier-rendu.mjs`
Expected: PASS. Le contrôle « écran jamais atteint » du harnais garantit qu'aucun de ces remplacements n'est un no-op silencieux.

- [ ] **Step 9 : ajouter les scénarios propres à la coquille**

Ajouter à `SCENARIOS` : « Coquille : barre basse, en-tête sans retour (racine) », « Coquille : en-tête avec retour (sous-écran) », « Coquille : pastille de compte sur Courses ». Ajouter à `SCENARIOS_LARGES` : « Coquille : rail à gauche, en-tête et contenu à droite ».

Ajouter enfin un jeu `SCENARIOS_HA_CHARGE` qui définit des `ha-*` minimaux **avant** de monter le panneau, pour mesurer le chemin réellement servi en production :

```js
// Sans ceci, le harnais et jsdom mesurent TOUJOURS le repli des enveloppes,
// jamais `<ha-card>` — c'est-à-dire jamais ce que voit l'utilisateur qui
// arrive depuis Lovelace, soit le cas courant (`default_panel: lovelace`).
const DEFINIR_HA_MINIMAL = `
  for (const nom of ['ha-card', 'ha-button', 'ha-svg-icon']) {
    if (!customElements.get(nom)) {
      customElements.define(nom, class extends HTMLElement {
        connectedCallback() {
          if (!this.shadowRoot) this.attachShadow({ mode: 'open' }).innerHTML = '<slot></slot>';
        }
      });
    }
  }
`;
```

Cette page se sert par le **routage de chemins posé en Task 1** : ajouter une entrée de plus à `pagesParChemin` (par exemple `/ha`), dont le HTML insère `DEFINIR_HA_MINIMAL` dans un `<script>` **avant** celui du bundle, et pointer les scénarios de ce jeu sur cette URL.

Run: `node outils/verifier-rendu.mjs`
Expected: PASS sur tous les jeux.

- [ ] **Step 10 : déployer et commiter**

```bash
npm run build
node outils/verifier-rendu.mjs --deploye
git add -A src/ tests/ outils/ ../custom_components/home_stock/panel/
git commit -m "feat(panneau): une coquille, des routes, et un panneau qui orchestre

panneau.ts perd sa barre de dix boutons et son rendu d'erreur : il ne fait
plus que l'orchestration métier. La navigation passe désormais par l'URL, ce
qui donne gratuitement le bouton Retour du navigateur et le geste système
d'Android — et rend enfin /home-stock/recipe/12 atteignable."
```

---

# LOT 3 — Les trois écrans

## Task 12 : le Catalogue cesse de rendre trois cents produits d'un coup

Sur 412 px, l'écran mesure **25 949 px** de haut. Recherche collante et fenêtrage.

**Files:**
- Modify: `src/ecrans/catalogue.ts`
- Test: `tests/catalogue.test.ts` (compléter)

**Interfaces:**
- Consumes: `tokens`, `hs-icon`.
- Produces: rien de public. Le comportement de recherche et d'édition ne change pas.

- [ ] **Step 1 : écrire le test qui échoue**

Ajouter à `tests/catalogue.test.ts` :

```ts
describe('catalogue : la liste ne se rend pas en entier', () => {
  it('ne rend qu’une fenêtre de produits, pas les trois cents', async () => {
    const produits = Array.from({ length: 300 }, (_, i) => ({
      id: i + 1, name: `Produit ${i + 1}`, base_unit: 'piece',
      default_location_id: null, default_shelf_life_days: null,
      aisle_id: null, min_stock: null, stock: 0,
    }));
    const el = await monterCatalogue({ large: false, produits });
    // La classe est `.ligne` — vérifié dans catalogue.ts : `<article class="ligne">`
    // en étroit, `<tr class="ligne …">` en dense.
    const lignes = el.shadowRoot!.querySelectorAll('.ligne');
    expect(lignes.length).toBeGreaterThan(0);
    expect(lignes.length).toBeLessThan(80);
  });

  it('garde la recherche atteignable en tête de liste', async () => {
    const el = await monterCatalogue({ large: false, produits: [] });
    // `.recherche` est l'<input> LUI-MÊME, pas un conteneur : c'est donc lui
    // qui devient collant.
    const recherche = el.shadowRoot!.querySelector('input.recherche');
    expect(recherche).not.toBeNull();
    const styles = (el.constructor as unknown as { styles: { cssText: string }[] });
    expect(styles.styles.map((s) => s.cssText).join('')).toContain('position: sticky');
  });

  it('rend le produit cherché même s’il est au-delà de la fenêtre', async () => {
    // Le fenêtrage ne doit pas rendre un produit INTROUVABLE : la recherche
    // filtre d'abord, la fenêtre s'applique ensuite.
    const produits = Array.from({ length: 300 }, (_, i) => ({
      id: i + 1, name: `Produit ${i + 1}`, base_unit: 'piece',
      default_location_id: null, default_shelf_life_days: null,
      aisle_id: null, min_stock: null, stock: 0,
    }));
    const el = await monterCatalogue({ large: false, produits });
    const champ = el.shadowRoot!.querySelector('input.recherche') as HTMLInputElement;
    champ.value = 'Produit 287';
    champ.dispatchEvent(new Event('input'));
    await el.updateComplete;
    expect(el.shadowRoot!.textContent).toContain('Produit 287');
  });
});
```

**Vérifié** : `monterCatalogue` existe (ligne 523 de `tests/catalogue.test.ts`) mais ne prend que `{ large, file }`. Lui ajouter une clé `produits` optionnelle, qui alimente la réponse de `home_stock/products/list`.

- [ ] **Step 2 : lancer le test pour vérifier qu'il échoue**

Run: `npx vitest run tests/catalogue.test.ts`
Expected: FAIL — 300 lignes rendues, pas de `position: sticky`.

- [ ] **Step 3 : implémenter le fenêtrage**

```ts
  /** Le nombre de lignes rendues à la fois. Trois cents lignes en produisaient
   *  25 949 px sur 412 px de large : le navigateur les met toutes en page à
   *  chaque frappe dans la recherche. Cinquante suffisent à remplir l'écran
   *  le plus haut, et le bouton « voir plus » évite un défilement infini que
   *  la tablette (pas de geste) ne saurait pas piloter. */
  private static readonly FENETRE = 50;

  @state() private nbAffiches = EcranCatalogue.FENETRE;

  /** La recherche filtre AVANT la fenêtre : un produit cherché doit se
   *  trouver, même s'il est le trois-centième. */
  private get produitsVisibles(): Produit[] {
    return this.produitsFiltres.slice(0, this.nbAffiches);
  }
```

**Les DEUX rendus mappent `produitsFiltres`** — `render()` en étroit (ligne 492) et `rendreDense()` en large (ligne 478, le `<tbody>`). Remplacer `this.produitsFiltres.map(...)` par `this.produitsVisibles.map(...)` **aux deux endroits** : n'en corriger qu'un laisserait le bureau rendre trois cents lignes.

Remettre `nbAffiches` à `FENETRE` à chaque changement de la recherche. Ajouter sous la liste, dans les deux rendus :

```ts
${this.produitsFiltres.length > this.nbAffiches ? html`
  <hs-button full @click=${() => { this.nbAffiches += EcranCatalogue.FENETRE; }}>
    Voir ${Math.min(EcranCatalogue.FENETRE, this.produitsFiltres.length - this.nbAffiches)}
    produits de plus (${this.produitsFiltres.length - this.nbAffiches} restants)
  </hs-button>` : nothing}
```

Et rendre la recherche collante :

```css
.recherche {
  position: sticky; top: 0; z-index: 1;
  background: var(--hs-surface); padding: var(--hs-space-2) 0;
  border-bottom: 1px solid var(--hs-divider);
}
```

- [ ] **Step 4 : lancer les tests**

Run: `npx vitest run tests/catalogue.test.ts`
Expected: PASS.

- [ ] **Step 5 : vérifier le rendu**

Run: `node outils/verifier-rendu.mjs`
Expected: PASS. Le scénario « Catalogue (quelques centaines de produits) » mesure désormais une page de hauteur raisonnable.

- [ ] **Step 6 : commit**

```bash
git add src/ecrans/catalogue.ts tests/catalogue.test.ts
git commit -m "perf(catalogue): cinquante lignes à la fois, pas trois cents

25 949 px de page sur un téléphone, remis en page à chaque frappe dans la
recherche. La recherche filtre avant la fenêtre : rien ne devient
introuvable."
```

---

## Task 13 : le Scanner devient une action, plus un écran vide

**Files:**
- Modify: `src/shell/nav-bar.ts` (ajout du bouton d'action)
- Modify: `src/panneau.ts` (rendu de l'action, route `/scan` conservée)
- Test: `tests/shell-nav-bar.test.ts` (compléter), `tests/panneau-routes.test.ts` (compléter)

**Interfaces:**
- Consumes: `hs-icon`, `hs-button`.
- Produces: `<hs-nav-bar .action=${{icon: IconName, label: string} | null}>`, émet `action-primaire`.

- [ ] **Step 1 : écrire le test qui échoue**

Ajouter à `tests/shell-nav-bar.test.ts` :

```ts
it('rend une action primaire quand on lui en donne une', async () => {
  const el = await monter({ action: { icon: 'scan', label: 'Scanner un article' } });
  const bouton = el.shadowRoot!.querySelector('.action') as HTMLElement;
  expect(bouton).not.toBeNull();
  expect(bouton.getAttribute('aria-label')).toBe('Scanner un article');
});

it('n’en rend aucune quand il n’y en a pas', async () => {
  const el = await monter({ action: null });
  expect(el.shadowRoot!.querySelector('.action')).toBeNull();
});

it('émet l’action primaire', async () => {
  const el = await monter({ action: { icon: 'scan', label: 'Scanner un article' } });
  const recu = vi.fn();
  el.addEventListener('action-primaire', recu);
  (el.shadowRoot!.querySelector('.action') as HTMLElement).click();
  expect(recu).toHaveBeenCalledTimes(1);
});
```

Ajouter à `tests/panneau-routes.test.ts` :

```ts
it('propose le scan sur la famille Courses, et pas sur les autres', async () => {
  const surListe = await monter('/list');
  expect(surListe.shadowRoot!.querySelector('hs-nav-bar')!
    .shadowRoot!.querySelector('.action')).not.toBeNull();
  document.body.innerHTML = '';
  const surPiles = await monter('/batteries');
  expect(surPiles.shadowRoot!.querySelector('hs-nav-bar')!
    .shadowRoot!.querySelector('.action')).toBeNull();
});

it('l’action primaire conduit au scanner, avec son URL', async () => {
  const el = await monter('/list');
  const barre = el.shadowRoot!.querySelector('hs-nav-bar')!;
  barre.dispatchEvent(new CustomEvent('action-primaire', { bubbles: true, composed: true }));
  await el.updateComplete;
  expect(el.ecran).toBe('scanner');
  expect(window.location.pathname).toBe('/home-stock/scan');
});
```

- [ ] **Step 2 : lancer les tests pour vérifier qu'ils échouent**

Run: `npx vitest run tests/shell-nav-bar.test.ts tests/panneau-routes.test.ts`
Expected: FAIL — `.action` n'existe pas.

- [ ] **Step 3 : ajouter l'action à la barre**

Dans `nav-bar.ts` :

```ts
  /** L'action primaire de la famille courante — pour l'instant le scan, sur
   *  Courses. `null` ailleurs : un bouton flottant sans action à offrir vaut
   *  moins que rien. */
  @property({ attribute: false }) action: { icon: IconName; label: string } | null = null;
```

Rendue à l'intérieur de `<nav>`, en tête de la liste en rail et posée au-dessus de la barre en bas :

```ts
${this.action ? html`
  <button class="action" aria-label=${this.action.label}
          @click=${() => this.dispatchEvent(new CustomEvent('action-primaire',
            { bubbles: true, composed: true }))}>
    <hs-icon name=${this.action.icon} label=${this.action.label}></hs-icon>
  </button>` : nothing}
```

```css
.action {
  position: absolute; right: var(--hs-space-4); bottom: 100%;
  margin-bottom: var(--hs-space-3);
  width: var(--hs-touch); height: var(--hs-touch);
  display: inline-flex; align-items: center; justify-content: center;
  border: none; border-radius: 50%;
  background: var(--hs-accent); color: var(--hs-on-accent);
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.3);
  cursor: pointer;
}
.barre { position: relative; }
/* En rail, l'action reprend le flux, en tête de colonne. */
.barre.rail .action {
  position: static; margin: var(--hs-space-3) auto 0;
}
```

> ⚠️ `box-shadow` est la **seule** exception admise à l'interdiction de couleur littérale : une ombre n'a pas de jeton et ne participe à aucun contraste texte/fond. L'ajouter à la liste d'exclusions du `grep` de la Task 6, Step 4.

- [ ] **Step 3 bis : retirer le Scanner de la sous-navigation**

Il devient l'action flottante : l'y laisser en pastille le mettrait **deux fois**
sur le même écran. Or `familyScreens` ne filtre que sur `!d.param`, et le
scanner n'a pas de paramètre — il y figure donc encore.

Mesuré sur la capture actuelle : la famille Courses a cinq pastilles, qui
passent sur **deux rangées** sur 412 px (~145 px), en plus des ~62 px de la
barre de titre. Le retirer ramène la famille à quatre.

Ajoute à `Destination` un drapeau explicite plutôt qu'une exception cachée dans
`familyScreens` :

```ts
  /** Écarté de la ligne secondaire parce qu'il est offert autrement — le
   *  scanner est l'action flottante de sa famille, l'y remettre en pastille
   *  le proposerait deux fois sur le même écran. */
  hiddenInFamilyNav?: boolean;
```

`{ screen: 'scanner', …, hiddenInFamilyNav: true }`, et `familyScreens` filtre
aussi dessus.

**Le test de couverture de la Task 16 doit rester vrai** : il compare la
sous-navigation à l'ensemble des écrans sans paramètre, et le scanner en sort.
Adapte-le pour qu'il exige que **tout écran sans paramètre soit dans la ligne
OU explicitement marqué `hiddenInFamilyNav`** — pas pour qu'il ignore le
scanner en dur. C'est ce test qui interdit à la régression des six écrans
inatteignables de revenir : il doit continuer d'attraper un écran oublié.

- [ ] **Step 4 : offrir l'action depuis le panneau**

Dans `panneau.ts` :

```ts
  private get actionPrimaire(): { icon: IconName; label: string } | null {
    // Le scan appartient aux Courses : c'est là qu'on rapporte un article,
    // qu'on le mette au panier ou qu'on le range. Ailleurs il n'aurait rien à
    // faire de ce qu'il lirait.
    return familyOf(this.ecran) === 'shopping' && this.ecran !== 'scanner'
      ? { icon: 'scan', label: 'Scanner un article' } : null;
  }
```

Passer `.action=${this.actionPrimaire}` à `<hs-nav-bar>` et brancher
`@action-primaire=${() => this.demanderNavigation('scanner')}`.

- [ ] **Step 5 : lancer les tests**

Run: `npx vitest run`
Expected: PASS — toute la suite.

- [ ] **Step 6 : vérifier le rendu et commiter**

Run: `node outils/verifier-rendu.mjs`
Expected: PASS.

```bash
git add src/shell/nav-bar.ts src/panneau.ts tests/
git commit -m "feat(shell): le scan devient une action des Courses, plus un écran vide

Il était l'accueil et n'affichait rien : un gros bouton bleu et six cents
pixels de blanc. La Liste prend sa place, il devient le bouton flottant de
sa famille."
```

---

## Task 14 : le Planning en icônes

Sept colonnes × quatre créneaux, deux boutons texte par repas : cinquante-six libellés « Valider » / « Annuler » à l'écran.

**Files:**
- Modify: `src/ecrans/planning.ts`
- Test: `tests/planning.test.ts` (compléter)

**Interfaces:**
- Consumes: `hs-icon`, `tokens`.
- Produces: rien de public. Les classes `.valider-repas` et `.annuler-repas` sont **conservées** — les tests existants et le vérificateur s'en servent.

- [ ] **Step 1 : écrire le test qui échoue**

Ajouter à `tests/planning.test.ts` :

```ts
describe('planning : des actions qui ne noient pas la grille', () => {
  it('rend les actions en icônes, pas en libellés répétés', async () => {
    // L'aide existante s'appelle `monter({ repas })` (ligne 16 de
    // tests/planning.test.ts) — il n'y a pas de `monterPlanningCharge`.
    const el = await monter({ repas: [REPAS_PLANIFIE] });
    const valider = el.shadowRoot!.querySelector('.valider-repas')!;
    expect(valider.querySelector('hs-icon')).not.toBeNull();
    expect(valider.textContent!.trim()).toBe('');
  });

  it('garde l’action annonçable, et nommant SON repas', async () => {
    // Cinquante-six boutons « Valider » identiques ne se distinguent pas au
    // lecteur d'écran : chacun doit dire lequel il valide.
    const el = await monter({ repas: [REPAS_PLANIFIE] });
    const valider = el.shadowRoot!.querySelector('.valider-repas')!;
    expect(valider.getAttribute('aria-label')).toMatch(/^Valider /);
    expect(valider.getAttribute('aria-label')!.length).toBeGreaterThan('Valider '.length);
  });

  it('se désabonne au démontage, dans les deux enveloppes', async () => {
    // La fuite que ce test interdit est bornée à l'appareil où l'élément HA
    // n'arrive jamais — la tablette cuisine — mais c'est un kiosque qui tourne
    // en continu, avec des dizaines de boutons remontés à chaque navigation.
    const avant = pendingCountForTests();
    const carte = await monter('hs-card');
    const bouton = await monter('hs-button');
    carte.remove();
    bouton.remove();
    expect(pendingCountForTests()).toBe(avant);
  });

  it('tient la cible tactile de la tablette', async () => {
    const el = await monter({ repas: [REPAS_PLANIFIE] });
    const styles = (el.constructor as unknown as { styles: { cssText: string }[] });
    const texte = styles.styles.map((s) => s.cssText).join('');
    expect(texte).toContain('min-height: var(--hs-touch)');
  });
});
```

`REPAS_PLANIFIE` est la constante de repas déjà employée par ce fichier de tests ; réutiliser celle qui s'y trouve plutôt que d'en écrire une nouvelle.

- [ ] **Step 2 : lancer le test pour vérifier qu'il échoue**

Run: `npx vitest run tests/planning.test.ts`
Expected: FAIL — les boutons contiennent encore leur libellé texte.

- [ ] **Step 3 : passer les actions en icônes**

```ts
<button class="valider-repas"
        aria-label="Valider ${nomDuRepas}"
        @click=${() => this.valider(repas)}>
  <hs-icon name="check"></hs-icon>
</button>
<button class="annuler-repas"
        aria-label="Retirer ${nomDuRepas} du planning"
        @click=${() => this.annuler(repas)}>
  <hs-icon name="close"></hs-icon>
</button>
```

```css
.valider-repas, .annuler-repas {
  display: inline-flex; align-items: center; justify-content: center;
  min-height: var(--hs-touch); min-width: var(--hs-touch);
  padding: 0; border-radius: var(--hs-radius-s);
  border: 1px solid var(--hs-divider);
  background: var(--hs-surface); color: var(--hs-text);
  cursor: pointer;
}
.repas { flex-direction: row; align-items: center; }
```

Sur 412 px, l'écran ne montre **qu'une journée** (comportement existant, cf. l'en-tête de `planning.ts`) : deux icônes de 62 px y tiennent à côté du nom du repas. En 1280, les sept colonnes en portent deux chacune, ce que la ligne texte ne permettait pas.

- [ ] **Step 4 : lancer les tests**

Run: `npx vitest run tests/planning.test.ts`
Expected: PASS.

- [ ] **Step 5 : vérifier le rendu — c'est ici que ça peut coincer**

Run: `node outils/verifier-rendu.mjs`
Expected: PASS.

Le risque réel : sur 1280 px, sept colonnes × (nom + 2 × 62 px) peuvent déborder. Si le vérificateur signale un débordement horizontal, **ne pas rétrécir les cibles** (le seuil est une contrainte matérielle) : passer les deux icônes sous le nom du repas dans la case, en `flex-direction: column` au-delà de six colonnes.

- [ ] **Step 6 : déployer et commiter**

```bash
npm run build
node outils/verifier-rendu.mjs --deploye
git add -A src/ tests/ ../custom_components/home_stock/panel/
git commit -m "feat(planning): deux icônes par repas, pas cinquante-six libellés

Sept colonnes × quatre créneaux × « Valider »/« Annuler » : le bruit était
là, pas dans les bordures — qui existaient déjà et que seul le harnais
effaçait. Chaque bouton nomme son repas pour le lecteur d'écran."
```

---

## Task 15 : la documentation d'exploitation suit

**Files:**
- Modify: `docs/exploitation.md`
- Modify: `/opt/nivuus/HomeAssistant/data/CLAUDE.md` (section « Garde-manger »)

- [ ] **Step 1 : consigner ce qui a changé**

Dans `docs/exploitation.md`, ajouter une section « Le panneau » :

- les quatre familles et leurs racines ;
- la table des routes, et le fait que `/home-stock/recipe/12` est désormais une URL valide ;
- **le piège** : `src/shell/destinations.ts` est la seule table ; ajouter un écran sans l'y déclarer fait lever `destinationOf` au premier rendu ;
- **le piège** : toute couleur passe par un jeton `--hs-*` de `src/shell/ui/tokens.ts`. Une couleur littérale dans un écran ignore le thème de l'utilisateur — sous Graphite, en service dans la maison, la primaire est orange et le texte-sur-primaire un navy ;
- **le piège** : `verifier-rendu.mjs` mesure trois palettes. En ajouter une nouvelle si un thème de la maison change.

Dans `CLAUDE.md`, ajouter sous « Garde-manger » :

```markdown
- **Le panneau a des routes d'URL depuis le 2026-08-22** : `/home-stock/list`,
  `/home-stock/recipe/<id>`, `/home-stock/batteries`… (table complète dans
  `data/meal/src/shell/destinations.ts`). Le bouton Retour du navigateur
  fonctionne. ⚠️ Le contrôle **C11** de `check_grocy_migration` reste rouge :
  `script.afficher_recette_cuisine` passe par `browser_mod`, `unavailable` sur
  la tablette cuisine — c'est un travail côté `tools/wallpanel-app`.
- **Toute couleur du panneau passe par un jeton `--hs-*`** (`src/shell/ui/tokens.ts`).
  Une couleur en dur ignore le thème : les deux comptes de la maison n'ont pas
  le même (« Graphite Auto » et `default`), et la primaire de Graphite est
  orange avec un texte-sur-primaire navy.
```

- [ ] **Step 2 : commit**

```bash
git add docs/exploitation.md ../CLAUDE.md
git commit -m "docs: les routes, les jetons, et les deux pièges qui reviendront"
```

---

## Task 16 : la sous-navigation de famille (URGENT — régression en production)

**Découvert en branchant la coquille.** Six écrans — Réglages, Équipements,
Journal, Recettes, Courses, Panier — n'ont plus **aucun point d'entrée** dans
l'application : ils ne sont ni racines de famille, ni ouverts par un événement
métier. La barre de dix boutons les exposait tous. Le bundle de la Task 11
étant déployé, la régression est **en production**.

**Files:**
- Modify: `src/shell/destinations.ts` (marquer les écrans de la ligne secondaire)
- Modify: `src/shell/header.ts` (rendre la ligne secondaire)
- Modify: `src/panneau.ts` (câbler l'événement de navigation)
- Test: `tests/shell-destinations.test.ts`, `tests/shell-header.test.ts`, `tests/panneau-routes.test.ts`
- Modify: `outils/verifier-rendu.mjs` (un scénario)

**Interfaces:**
- Consumes: `DESTINATIONS`, `familyOf` (Task 7), `tokens`, `hs-icon`.
- Produces: `export function familyScreens(family: FamilyId): Destination[]`
  — les écrans de la famille qui figurent dans la ligne secondaire, dans
  l'ordre de la table. `<hs-header>` émet
  `CustomEvent<{ screen: Ecran }>('ecran-choisi', {bubbles, composed})`.

- [ ] **Step 1 : écrire les tests de la table**

Dans `tests/shell-destinations.test.ts` :

```ts
describe('sous-navigation de famille', () => {
  it('donne les écrans atteignables de chaque famille, dans l’ordre', () => {
    expect(familyScreens('shopping').map((d) => d.screen))
      .toEqual(['liste', 'session', 'panier', 'rangement', 'scanner']);
    expect(familyScreens('stock').map((d) => d.screen)).toEqual(['catalogue', 'journal']);
    expect(familyScreens('kitchen').map((d) => d.screen)).toEqual(['planning', 'recettes']);
    expect(familyScreens('house').map((d) => d.screen))
      .toEqual(['piles', 'equipements', 'reglages']);
  });

  it('exclut les écrans qui exigent un paramètre', () => {
    // fiche, recette, validation, ticket, manger : un bouton nu ne saurait pas
    // quel identifiant leur passer. On y entre depuis l'écran qui le connaît.
    for (const famille of FAMILIES) {
      for (const d of familyScreens(famille.id)) expect(d.param).toBeUndefined();
    }
  });

  it('couvre TOUT écran sans paramètre — aucun ne doit rester inatteignable', () => {
    // C'est le test qui interdit la régression : la barre de dix boutons
    // exposait les dix-sept écrans, les quatre familles n'exposaient que leurs
    // racines, et six écrans étaient devenus introuvables autrement que par
    // leur URL.
    const dansLaNav = FAMILIES.flatMap((f) => familyScreens(f.id).map((d) => d.screen));
    const sansParametre = DESTINATIONS.filter((d) => !d.param).map((d) => d.screen);
    expect([...dansLaNav].sort()).toEqual([...sansParametre].sort());
  });
});
```

- [ ] **Step 2 : lancer, voir échouer**

Run: `npx vitest run tests/shell-destinations.test.ts`
Expected: FAIL — `familyScreens` n'existe pas.

- [ ] **Step 3 : ajouter `familyScreens`**

```ts
/** Les écrans d'une famille qui figurent dans la ligne secondaire de
 *  l'en-tête. Ceux qui exigent un paramètre en sont exclus : un bouton nu ne
 *  saurait pas quel identifiant leur passer, on y entre depuis l'écran qui le
 *  connaît. Panier et Rangement y restent même sans session ouverte — des
 *  boutons qui apparaissent et disparaissent font perdre le repère, ce qui
 *  était le défaut de l'ancienne barre. */
export function familyScreens(family: FamilyId): Destination[] {
  return DESTINATIONS.filter((d) => d.family === family && !d.param);
}
```

- [ ] **Step 4 : les tests de l'en-tête**

Dans `tests/shell-header.test.ts` :

```ts
describe('en-tête : ligne secondaire', () => {
  it('rend les écrans de la famille courante', async () => {
    const el = await monter({ current: 'piles' });
    const liens = el.shadowRoot!.querySelectorAll('.sous-nav .sous-lien');
    expect([...liens].map((n) => n.textContent!.trim()))
      .toEqual(['Piles', 'Équipements', 'Réglages']);
  });

  it('marque l’écran courant, et lui seul', async () => {
    const el = await monter({ current: 'reglages' });
    const actifs = el.shadowRoot!.querySelectorAll('.sous-lien.actif');
    expect(actifs).toHaveLength(1);
    expect(actifs[0].getAttribute('aria-current')).toBe('page');
    expect(actifs[0].textContent!.trim()).toBe('Réglages');
  });

  it('ne change pas de contenu entre deux écrans d’une même famille', async () => {
    // La ligne est stable : seule la marque d'actif se déplace. C'est ce qui
    // distingue cette navigation de l'ancienne barre, où les boutons bougeaient.
    const a = await monter({ current: 'piles' });
    const avant = [...a.shadowRoot!.querySelectorAll('.sous-lien')].map((n) => n.textContent!.trim());
    document.body.innerHTML = '';
    const b = await monter({ current: 'reglages' });
    const apres = [...b.shadowRoot!.querySelectorAll('.sous-lien')].map((n) => n.textContent!.trim());
    expect(apres).toEqual(avant);
  });

  it('émet l’écran choisi', async () => {
    const el = await monter({ current: 'piles' });
    const recu = vi.fn();
    el.addEventListener('ecran-choisi', (e) => recu((e as CustomEvent).detail));
    (el.shadowRoot!.querySelectorAll('.sous-lien')[2] as HTMLElement).click();
    expect(recu).toHaveBeenCalledWith({ screen: 'reglages' });
  });

  it('n’émet rien pour l’écran déjà affiché', async () => {
    const el = await monter({ current: 'piles' });
    const recu = vi.fn();
    el.addEventListener('ecran-choisi', recu);
    (el.shadowRoot!.querySelectorAll('.sous-lien')[0] as HTMLElement).click();
    expect(recu).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 5 : rendre la ligne dans `header.ts`**

Sous la barre de titre, avant la bannière :

```ts
${this.rendreSousNav()}
```

```ts
  private rendreSousNav() {
    const ecrans = familyScreens(familyOf(this.current));
    // Une famille à un seul écran n'a rien à proposer : la ligne serait un
    // bouton qui ne mène qu'à lui-même.
    if (ecrans.length < 2) return nothing;
    return html`
      <nav class="sous-nav">
        ${ecrans.map((d) => {
          const actif = d.screen === this.current;
          return html`
            <button class="sous-lien ${actif ? 'actif' : ''}"
                    aria-current=${actif ? 'page' : nothing}
                    ?disabled=${actif}
                    @click=${() => this.dispatchEvent(new CustomEvent('ecran-choisi', {
                      detail: { screen: d.screen }, bubbles: true, composed: true }))}>
              ${d.label}
            </button>`;
        })}
      </nav>`;
  }
```

```css
    .sous-nav {
      display: flex; flex-wrap: wrap; gap: var(--hs-space-2);
      padding: 0 var(--hs-space-3) var(--hs-space-2);
      background: var(--hs-surface);
      border-bottom: 1px solid var(--hs-divider);
    }
    .sous-lien {
      min-height: var(--hs-touch); padding: 0 var(--hs-space-3);
      border: 1px solid var(--hs-divider); border-radius: var(--hs-radius-s);
      background: var(--hs-surface-2); color: var(--hs-text);
      font-family: var(--hs-font); font-size: 0.9rem; cursor: pointer;
    }
    /* L'actif se dit par l'aplat et la graisse, JAMAIS par la couleur du
       libellé : --hs-accent en texte donne 3,26:1 sous HA et 2,38:1 sous
       Graphite (spec § 6.5). */
    .sous-lien.actif {
      background: var(--hs-accent); color: var(--hs-on-accent);
      border-color: var(--hs-accent); font-weight: 600;
    }
```

- [ ] **Step 6 : câbler dans `panneau.ts`**

```ts
@ecran-choisi=${(e: CustomEvent<{ screen: Ecran }>) => this.demanderNavigation(e.detail.screen)}
```

Passe par `demanderNavigation`, **pas** `naviguerVers` : quitter un rangement inachevé doit continuer d'armer la confirmation.

- [ ] **Step 7 : le test de bout en bout**

Dans `tests/panneau-routes.test.ts` :

```ts
it('atteint Réglages depuis Piles, sans passer par une URL tapée à la main', async () => {
  // La régression que ce test interdit : Réglages n'était plus atteignable
  // dans l'application, seulement en tapant son URL.
  const el = await monter('/batteries');
  const entete = el.shadowRoot!.querySelector('hs-header')!;
  entete.dispatchEvent(new CustomEvent('ecran-choisi', {
    detail: { screen: 'reglages' }, bubbles: true, composed: true }));
  await el.updateComplete;
  expect(el.ecran).toBe('reglages');
  expect(window.location.pathname).toBe('/home-stock/settings');
});
```

- [ ] **Step 8 : le scénario de rendu**

Ajouter à `SCENARIOS` : « Coquille : ligne secondaire de la famille Maison, Réglages actif ». La famille Courses en a cinq — vérifier qu'ils tiennent sur 412 px sans déborder (la ligne a `flex-wrap`, donc elle passe à la ligne plutôt que de rétrécir sous 62 px).

Run: `npx vitest run` puis `node outils/verifier-rendu.mjs`
Expected: tout vert.

- [ ] **Step 9 : déployer et commiter**

```bash
npm run build
node outils/verifier-rendu.mjs --deploye
git add -A src/ tests/ outils/ ../custom_components/home_stock/panel/
git commit -m "fix(shell): six écrans étaient devenus inatteignables

Réglages, Équipements, Journal, Recettes, Courses et Panier n'avaient plus
aucun point d'entrée : ni racines de famille, ni ouverts par un événement.
La barre de dix boutons les exposait tous ; les quatre familles n'exposaient
que leurs racines. L'en-tête porte désormais la ligne des écrans de la
famille courante, stable d'un écran à l'autre — seule la marque d'actif s'y
déplace."
```

---

## Auto-revue du plan

**Couverture de la spec :**

| Spec | Tâche |
|---|---|
| § 3 harnais menteur | Task 1 |
| § 4.1 module `shell/` | Tasks 2-5, 7-10 |
| § 4.2 quatre familles | Tasks 7, 9 |
| § 4.3 comportements conservés | Task 11 (Step 4, Step 5) |
| § 5 routes | Tasks 8, 11 |
| § 5.4 C11 hors périmètre | Task 15 |
| § 6.1 jetons | Tasks 2, 6 |
| § 6.2 enveloppes | Tasks 4, 5 |
| § 6.3 détection `ha-*` | Task 3 |
| § 7.1 Catalogue | Task 12 |
| § 7.2 Scanner | Task 13 |
| § 7.3 Planning | Task 14 |
| § 8.1 harnais réparé | Task 1 |
| § 8.2 rendu HA mesuré | Tasks 3-5 (tests), Task 11 Step 9 |
| § 8.3 nouveaux scénarios | Task 11 Steps 8-9, Tasks 12-14 |
| § 8.4 non-régression | Task 6 Step 5, Task 11 Step 7 |

Aucune section de la spec sans tâche.

**Cohérence des noms** (vérifiée d'un bout à l'autre) : `tokens`, `isDefined`, `whenDefined`, `primeHaComponents`, `resetForTests`, `ICON_PATHS`, `IconName`, `FAMILIES`, `DESTINATIONS`, `destinationOf`, `familyOf`, `FamilyId`, `parsePath`, `pathOf`, `DEFAULT_PATH`, `naviguerVers`, `appliquerChemin`, `appliquerParametre`.

**Point d'attention pour l'exécutant** : la Task 1 se termine sur un vérificateur **rouge**, volontairement. C'est le seul endroit du plan où un échec est le résultat attendu. La Task 6 le remet au vert.
