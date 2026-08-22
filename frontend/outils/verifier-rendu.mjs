#!/usr/bin/env node
/** Vérificateur de rendu du panneau `home_stock`.
 *
 *  Le plan de la Task 17 le calque sur celui de `tools/wallpanel-app` : ce
 *  dernier ouvre ses pages contre l'instance Home Assistant réelle de la
 *  maison, avec une session injectée à partir du jeton de `data/.mcp.json`.
 *
 *  Une tâche antérieure de ce lot a redémarré cette instance pour vérifier
 *  quelque chose, et ça a interrompu une vraie maison en plein
 *  fonctionnement. La règle depuis : plus rien ne touche l'instance en
 *  service. Ce script s'en écarte donc délibérément sur quatre points :
 *
 *   1. Il construit le bundle **en mémoire** depuis `src/panneau.ts`
 *      (esbuild, `write: false`) — un vérificateur ne déploie jamais, un
 *      `npm run build` s'en charge (voir `docs/exploitation.md`).
 *   2. Il sert une page de test locale — un petit serveur HTTP posé sur
 *      127.0.0.1, port éphémère, jamais exposé au-delà de la machine — qui
 *      monte `<home-stock-panel>` avec un `hass`
 *      FACTICE : un objet minimal qui répond aux mêmes formes que le vrai
 *      (`connection.sendMessagePromise`, `connection.subscribeMessage`,
 *      `callService`), piloté par des scénarios ci-dessous plutôt que par
 *      ce que la maison contient aujourd'hui — un panier de plusieurs
 *      lignes sur plusieurs rayons, une liste à ranger, un catalogue de
 *      quelques centaines de produits, l'écran de réglages, et un refus
 *      serveur affiché en bannière.
 *   3. Aucun jeton n'est lu, aucune session n'est ouverte : le hass factice
 *      n'a besoin d'aucun secret. (Un `page.setContent()` direct semblait
 *      suffire, mais produit un document d'origine opaque où l'accès à
 *      `window.localStorage` lève une `SecurityError` — `FileAttente` en a
 *      besoin dès `connectedCallback()`, donc TOUT le panneau échouait à se
 *      monter silencieusement ; voir le rapport de tâche. Le petit serveur
 *      local ci-dessus donne une vraie origine `http://127.0.0.1`, sous
 *      laquelle `localStorage` marche normalement.)
 *   4. Deux formats, ceux du spec du panneau (§14) — 412 × 915 (le
 *      téléphone qui scanne en rayon) et 1280 × 800 (le bureau, écran
 *      Catalogue/Réglages) — mesurés avec les MÊMES seuils que le mur
 *      (`wallpanel` : 62 px de cible tactile) : la tablette cuisine ouvre
 *      ce même panneau, donc c'est le seuil du mur qui prime pour la cible
 *      tactile, même si ce panneau se pilote aussi en main ou à la souris.
 *      Le contraste, lui, reste à **4,5:1**, le seuil WCAG AA standard —
 *      rien dans la maison n'impose 5:1 en dehors du mur.
 *
 *  Échoue sur : un débordement horizontal, une cible tactile sous 62 px,
 *  un contraste texte/fond sous 4,5:1, ou du texte tronqué.
 *
 *  Chaque scénario vérifie aussi qu'il a bien ATTEINT l'écran attendu (le
 *  bon composant enfant monté dans le panneau) avant de le mesurer : un
 *  clic de navigation qui ne trouve pas son bouton (`if (bouton) bouton.
 *  click()`) est un no-op silencieux qui, sans ce contrôle, ferait mesurer
 *  l'écran précédent sous le nom d'un autre — et rapporterait « aucun
 *  défaut » sur un écran jamais rendu.
 *
 *  Usage : `node outils/verifier-rendu.mjs` (ou `npm run verifier`).
 *  Auto-vérification (par défaut, après la vérification normale) : casse
 *  volontairement cinq choses sur une page jetable — une cible, un
 *  contraste, un débordement, une troncature, et un clic de navigation qui
 *  ne trouve pas son bouton — et vérifie que chacune est bien détectée : la
 *  preuve que ce script échoue vraiment quand il le doit, pas seulement
 *  qu'il n'a rien trouvé à dire. Désactivable avec `--sans-auto-verification`.
 *
 *  `--deploye` : mesure le bundle réellement écrit par `npm run build`
 *  (`custom_components/home_stock/panel/home-stock-panel.js`) au lieu de
 *  celui construit en mémoire — le seul moyen de savoir que ce que Home
 *  Assistant sert vraiment est aussi propre que ce que ce script mesure
 *  d'habitude. Ce mode ne lit le fichier que pour le servir tel quel ; il ne
 *  déclenche jamais lui-même de build.
 */
import esbuild from 'esbuild';
import { chromium } from 'playwright-core';
import { createServer } from 'node:http';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const ICI = dirname(fileURLToPath(import.meta.url));
const RACINE = join(ICI, '..');
const SRC = join(RACINE, 'src');
const TSCONFIG = join(RACINE, 'tsconfig.json');
const BUNDLE_DEPLOYE = join(RACINE, '..', 'custom_components', 'home_stock', 'panel', 'home-stock-panel.js');

const CIBLE_MIN_PX = 62;
const CONTRASTE_MIN = 4.5;

const FORMATS = [
  { nom: 'Téléphone (Pixel, 412×915)', width: 412, height: 915 },
  { nom: 'Bureau (PC, 1280×800)', width: 1280, height: 800 },
  // Lot 6 : le 1280 × 800 est à peine au-dessus du seuil `large` (1000 px) —
  // il attrape les débordements, le cas où la mise en page dense est la plus
  // serrée. Celui-ci attrape l'inverse : l'étirement, le vide, la ligne de
  // texte trop longue pour être lue. Les deux défauts existent, aucun des
  // deux formats précédents ne les voit tous les deux, et c'est pour ça qu'on
  // garde les trois.
  { nom: 'Grand écran (bureau, 1920×1080)', width: 1920, height: 1080 },
];

/** Le format dans lequel la vue dense est la plus lâche — celui où les
 *  scénarios de `SCENARIOS_LARGES` s'exécutent, et le seul. */
const FORMAT_LARGE = FORMATS[FORMATS.length - 1];

// --- construction du bundle, en mémoire ------------------------------------

async function bundlerApplication({ minifier = false } = {}) {
  const resultat = await esbuild.build({
    entryPoints: [join(SRC, 'panneau.ts')],
    bundle: true,
    write: false,
    minify: minifier,
    format: 'esm',
    target: 'es2022',
    tsconfig: TSCONFIG,
    legalComments: 'none',
    logLevel: 'silent',
  });
  return resultat.outputFiles[0].text.replaceAll('</script', '<\\/script');
}

/** La table des destinations, lue DANS LA SOURCE plutôt que recopiée ici.
 *  Une seconde table à tenir synchronisée est exactement ce que
 *  `src/shell/destinations.ts` a supprimé (voir son commentaire de tête) : un
 *  libellé recopié qui dérive, et c'est le harnais qui ment. esbuild sait
 *  déjà lire ce fichier ; il n'importe que des types, donc il se bundle seul. */
async function chargerDestinations() {
  const resultat = await esbuild.build({
    entryPoints: [join(SRC, 'shell', 'destinations.ts')],
    bundle: true, write: false, format: 'esm', target: 'es2022',
    tsconfig: TSCONFIG, logLevel: 'silent',
  });
  const base64 = Buffer.from(resultat.outputFiles[0].text, 'utf8').toString('base64');
  return import(`data:text/javascript;base64,${base64}`);
}

/** Traduit les actions d'un scénario en gestes que la page sait exécuter.
 *  La navigation ne se fait plus par un bouton texte par écran, mais par
 *  FAMILLE : le scénario nomme l'ÉCRAN voulu, et le harnais trouve sa famille
 *  dans la table, comme le ferait un utilisateur qui sait où ranger les
 *  choses. Un écran absent de la table est une faute d'écriture du scénario,
 *  pas un défaut de rendu : on lève ici, en Node, avant même d'ouvrir la page.
 *
 *  (Ce qui reste SILENCIEUX, volontairement, c'est un bouton de famille
 *  introuvable dans la barre : c'est le contrôle « écran jamais atteint » qui
 *  doit l'attraper, et l'auto-vérification en fait la preuve.) */
function preparerActions(actions, familleParEcran) {
  return actions.map((action) => {
    if (action.type !== 'click-nav' || action.famille) return action;
    const famille = familleParEcran.get(action.ecran);
    if (!famille) {
      throw new Error(`Scénario : écran hors de la table des destinations — ${action.ecran}`);
    }
    return { ...action, famille };
  });
}

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
    //
    // Chaîne de résolution, jeton par jeton, depuis
    // `config/themes/graphite/graphite-light.yaml` (relecture du
    // 2026-08-22, round 1 : cinq des dix valeurs posées initialement
    // étaient inventées, pas relevées — à revérifier ici plutôt qu'à
    // croire sur parole) :
    //   --secondary-background-color : l.245 → token-color-background-secondary (l.64)
    //   --secondary-text-color       : l.211 → token-color-text-secondary (l.57)
    //   --divider-color              : l.230 → token-color-background-divider (l.71)
    //                                   → token-color-background-sidebar (l.65)
    //                                   → token-color-background-base (l.63)
    //   --error-color                : l.240 → token-color-feedback-error (l.50)
    //   --warning-color              : l.239 → token-color-feedback-warning (l.49)
    // Les cinq autres variables (background, card, primary-text,
    // text-primary, primary) étaient déjà correctes et n'ont pas bougé.
    //
    // `--error-color` de Graphite est un ROSE PÂLE (`rgb(234, 114, 135)`),
    // son `--warning-color` un JAUNE PÂLE (`rgb(255, 219, 117)`) : du texte
    // blanc posé dessus tombe à 2,89:1. C'est un défaut RÉEL du panneau
    // (tâche 6 le corrigera) — le harnais doit désormais le voir, pas le
    // masquer derrière un rouge/orange Material inventés.
    nom: 'Graphite clair (en service)',
    variables: {
      '--primary-background-color': 'rgb(234, 235, 238)',
      '--secondary-background-color': 'rgb(245, 245, 245)',
      '--card-background-color': 'rgb(255, 255, 255)',
      '--primary-text-color': 'rgb(19, 21, 54)',
      '--secondary-text-color': 'rgba(19, 21, 54, 0.96)',
      '--primary-color': 'rgb(238, 147, 0)',
      '--text-primary-color': 'rgb(19, 21, 54)',
      '--divider-color': 'rgb(234, 235, 238)',
      '--error-color': 'rgb(234, 114, 135)',
      '--warning-color': 'rgb(255, 219, 117)',
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

/** Les éléments `ha-*` que Home Assistant charge avec son chunk Lovelace, en
 *  version minimale. Sans eux, le harnais et jsdom mesurent TOUJOURS le repli
 *  des enveloppes, jamais `<ha-card>` ni `<ha-svg-icon>` — c'est-à-dire jamais
 *  ce que voit l'utilisateur qui arrive depuis Lovelace, soit le cas courant
 *  (`default_panel: lovelace`). Défini AVANT le bundle : `hs-icon` et
 *  `hs-card` décident au premier rendu, synchronement. */
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

function pageHtml(bundleJs, palette = PALETTES[0], avantLeBundle = '') {
  return `<!doctype html>
<html><head><meta charset="utf-8">
<style>${themeCss(palette)}</style>
</head><body>
<home-stock-panel></home-stock-panel>
${avantLeBundle ? `<script>${avantLeBundle}</script>` : ''}
<script type="module">${bundleJs}</script>
</body></html>`;
}

/** Sert `pagesParChemin` (un objet `{chemin: html}`) sur 127.0.0.1, port
 *  éphémère — jamais exposé au-delà de la machine, jamais un vrai réseau.
 *  Une seule page ne suffit plus depuis le balayage multi-palettes : `'/'`
 *  reste la palette par défaut (compat de tout ce qui n'en connaît qu'une),
 *  les chemins supplémentaires (`/p1`, `/p2`…) portent les autres. Route sur
 *  `requete.url`, avec repli sur `'/'` pour tout chemin inconnu — il suffit
 *  d'ajouter une entrée au dictionnaire pour servir une page de plus.
 *
 *  Nécessaire : `page.setContent()` produit un document d'origine opaque où
 *  `window.localStorage` lève une `SecurityError` à la simple lecture de la
 *  propriété, ce qui fait échouer `connectedCallback()` du panneau AVANT
 *  même qu'il construise sa `FileAttente` — silencieusement, puisque c'est
 *  une exception non interceptée dans un cycle de vie Lit, jamais rapportée
 *  comme un défaut de rendu. Une vraie origine `http://127.0.0.1` n'a pas ce
 *  problème. */
async function servirPagesStatiques(pagesParChemin) {
  const serveur = createServer((requete, reponse) => {
    const html = pagesParChemin[requete.url] ?? pagesParChemin['/'];
    reponse.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    reponse.end(html);
  });
  await new Promise((resolve, reject) => {
    serveur.once('error', reject);
    serveur.listen(0, '127.0.0.1', resolve);
  });
  const { port } = serveur.address();
  return { url: `http://127.0.0.1:${port}/`, fermer: () => serveur.close() };
}

// --- fixtures ---------------------------------------------------------------

const RAYONS = [
  { id: 1, name: 'Épicerie salée', position: 0 },
  { id: 2, name: 'Épicerie sucrée', position: 1 },
  { id: 3, name: 'Frais', position: 2 },
  { id: 4, name: 'Surgelés', position: 3 },
  { id: 5, name: 'Hygiène et entretien', position: 4 },
];

// Des enseignes réelles et de longueur variable : les pastilles doivent
// passer à la ligne plutôt que déborder, sur les deux formats.
// Depuis le lot 4, un magasin est une LIGNE : le panneau envoie un
// identifiant à la place d'une chaîne.
const MAGASINS = ['Carrefour', 'Leclerc', 'Lidl', 'Grand Frais', 'Biocoop Les Quatre Chemins']
  .map((name, index) => ({ id: index + 1, name, position: index, active: 1,
                           observed_sessions: index, last_seen: null }));

// --- lot 4 : la liste de courses et le ticket de caisse ---------------------
//
// Une liste réaliste : quatre rayons, les quatre origines, des lignes sans
// quantité (« ce qu'il faut »), des libellés longs, et trois cochées repliées
// en bas. C'est la forme qui déborde si elle doit déborder.
const LIGNES_LISTE = [
  ['Crémerie', 'Lait demi-écrémé', 'ml', 2000, [['shortage', 'sous le seuil']]],
  ['Crémerie', 'Yaourt nature x16', 'piece', 16, [['meal_plan', 'dîner de jeudi']]],
  ['Crémerie', 'Beurre demi-sel de baratte', 'g', null, [['manual', 'ajouté à la main']]],
  ['Épicerie salée', 'Coquillettes', 'g', 1000,
   [['shortage', 'seuil 500'], ['meal_plan', 'gratin de mardi']]],
  ['Épicerie salée', 'Huile d’olive vierge extra première pression à froid', 'ml', 750,
   [['recurring', 'tous les 60 j']]],
  ['Entretien et maison', 'Sacs poubelle 30 L', 'piece', 20, [['recurring', 'tous les 30 j']]],
  ['Entretien et maison', 'Pile CR2032', 'piece', 4, [['shortage', 'sous le seuil']]],
  ['Fruits et légumes', 'Courgettes', 'g', 900, [['meal_plan', 'gratin de mardi']]],
].map(([rayon, nom, unite, quantite, origines], index) => ({
  id: index + 1, product_id: index + 1, free_text: null, quantity: quantite,
  note: null, added_at: '2026-08-21T09:00:00', checked_at: null, removed_at: null,
  session_id: null, line_id: null, product_name: nom, base_unit: unite,
  aisle_id: index + 1, aisle_name: rayon, aisle_position: index,
  claims: origines.map(([origin, detail]) => ({ origin, quantity: quantite, detail })),
}));

const LISTE_CHARGEE = {
  items: [
    ...LIGNES_LISTE,
    ...[9, 10, 11].map((id) => ({
      ...LIGNES_LISTE[0], id, product_name: `Déjà dans le chariot ${id}`,
      checked_at: '2026-08-21T10:00:00',
    })),
  ],
  store_id: 1,
  store_name: 'Carrefour',
  estimate: { amount: 62.4, confidence: 0.72, priced: 8, total: 11 },
};

const TICKET_LU = {
  id: 1, session_id: 1,
  media_content_id: 'media-source://media_source/local/home_stock/receipts/t.jpg',
  captured_at: '2026-08-21T20:00:00', state: 'read', store_id: 1,
  purchased_on: '2026-08-21', total: 61.4, agent_entity_id: 'ai_task.gemini',
  read_at: '2026-08-21T20:00:12', attempts: 1, error: null, raw: '{}',
  lines: [
    ['LT DEMI ECR 1L X6', 6.54, 10], ['COQUILL PANZ 500G', 1.35, 11],
    ['HUIL OLIV VIERG EXTRA 75CL', 8.9, null], ['SACS POUB 30L X20', 3.2, null],
    ['CRG COURGETTE VRAC', 2.7, 12], ['PILE CR2032 X4', 5.4, 13],
  ].map(([label, prix, ligne], index) => ({
    id: index + 1, receipt_id: 1, position: index + 1, label,
    quantity: 1, unit_price: prix, total_price: prix,
    line_id: ligne, article_id: null,
    match_state: ligne === null ? 'unmatched' : 'auto', applied_at: null,
    candidates: ligne === null ? [] : [{ line_id: ligne, label: 'Ligne du panier', score: 0.9 }],
  })),
  cart_lines: [10, 11, 12, 13].map((id) => ({
    id, article_label: `Article du panier ${id}`, product_name: `Produit ${id}`,
    quantity: 1, unit_price: 1.2, base_unit: 'g', brand: null,
    stored_at: '2026-08-21T21:00:00', movements: 2,
  })),
  lines_total: 28.09,
  total_gap: 33.31,
};

const EMPLACEMENTS = [
  { id: 1, name: 'Placard cuisine', kind: 'cupboard', position: 0 },
  { id: 2, name: 'Frigo', kind: 'fridge', position: 1 },
  { id: 3, name: 'Congélateur', kind: 'freezer', position: 2 },
  { id: 4, name: 'Cave', kind: 'pantry', position: 3 },
];

function ligneSession(id, extra) {
  return {
    id, article_id: id, quantity: 500, unit_price: 0.0042, stored_at: null, batch_id: null,
    product_id: id, product_name: `Produit ${id}`, base_unit: 'g', default_location_id: 1,
    default_shelf_life_days: 10, days_after_opening: null, article_label: null, brand: null,
    image: null, net_quantity: 500, aisle_name: 'Épicerie salée', aisle_position: 0,
    ...extra,
  };
}

// Un panier de plusieurs lignes sur plusieurs rayons, avec un nom et une
// marque volontairement très longs — de quoi éprouver le renvoi à la ligne
// plutôt qu'une troncature, sur les deux formats.
const LIGNES_PANIER = [
  ligneSession(1, { product_name: 'Farine de blé T55', aisle_name: 'Épicerie salée', aisle_position: 0,
                    quantity: 1000, base_unit: 'g' }),
  ligneSession(2, { product_name: 'Yaourts nature', aisle_name: 'Frais', aisle_position: 2,
                    base_unit: 'piece', quantity: 8, unit_price: 0.35, net_quantity: 125 }),
  ligneSession(3, {
    product_name: 'Petits pois extra-fins surgelés en sachet refermable format familial',
    brand: 'Marque Repère Sélection Grand Format Économique Édition Limitée',
    aisle_name: 'Surgelés', aisle_position: 3, quantity: 1000, base_unit: 'g',
  }),
  ligneSession(4, { product_name: 'Liquide vaisselle citron', aisle_name: 'Hygiène et entretien',
                    aisle_position: 4, base_unit: 'ml', quantity: 500, unit_price: 0.006 }),
];

// Une liste à ranger : certaines lignes ont un emplacement suggéré, d'autres
// non (« Emplacement à choisir »), pour éprouver les deux groupes.
const LIGNES_RANGEMENT = [
  ligneSession(10, { product_name: 'Riz basmati', stored_at: null, default_location_id: 1,
                     aisle_name: 'Épicerie salée', quantity: 1000, base_unit: 'g' }),
  ligneSession(11, { product_name: 'Lait demi-écrémé', stored_at: null, default_location_id: 2,
                     aisle_name: 'Frais', quantity: 1000, base_unit: 'ml' }),
  ligneSession(12, { product_name: 'Article jamais rangé auparavant', stored_at: null,
                     default_location_id: null, default_shelf_life_days: null,
                     aisle_name: 'Épicerie sucrée', quantity: 1, base_unit: 'piece' }),
];

function sessionOuverte(etat, store, lignes) {
  const total = lignes.reduce((s, l) => s + l.quantity * (l.unit_price ?? 0), 0);
  return {
    session: { id: 1, state: etat, store, started_at: '2026-08-19T10:00:00', closed_at: null },
    lines: lignes,
    totals: {
      lines: lignes.length,
      pending: lignes.filter((l) => l.stored_at === null).length,
      total: Math.round(total * 100) / 100,
    },
    stores: store ? [store] : [],
  };
}

// Un catalogue de quelques centaines de produits, sur les cinq rayons, avec
// quelques noms très longs pour éprouver la liste dense sans troncature.
const NOMS_BASE = [
  'Farine de blé', 'Yaourt nature', 'Petits pois surgelés', 'Liquide vaisselle', 'Café moulu',
  'Pâtes coquillettes', 'Riz basmati', 'Lait demi-écrémé', 'Compote de pommes', "Huile d'olive vierge extra",
  'Savon noir', 'Lessive écologique concentrée', 'Chocolat noir 70%', 'Confiture de fraises maison',
  'Beurre doux', 'Fromage râpé emmental', "Jus d'orange sans pulpe", 'Céréales complètes petit-déjeuner',
  'Sauce tomate basilic', 'Moutarde de Dijon',
];

function genererProduits(n) {
  const produits = [];
  for (let i = 1; i <= n; i += 1) {
    const rayon = RAYONS[i % RAYONS.length];
    const base = NOMS_BASE[i % NOMS_BASE.length];
    const nomLong = i % 37 === 0;
    const nom = nomLong
      ? `${base} format familial économique édition limitée collection artisanale numéro ${i}`
      : `${base} ${i}`;
    produits.push({
      id: i, name: nom, base_unit: i % 5 === 1 ? 'piece' : (i % 3 === 0 ? 'ml' : 'g'),
      category_id: (i % 12) + 1, aisle_id: rayon.id, edible: 1,
      default_location_id: EMPLACEMENTS[i % EMPLACEMENTS.length].id,
      min_quantity: i % 4 === 0 ? null : (i % 5) * 50 + 50,
      days_after_opening: null, default_shelf_life_days: i % 6 === 0 ? null : (i % 20) + 3,
      reference_kcal: null, active: 1, external_ref: null,
    });
  }
  return produits;
}

const PRODUITS_CATALOGUE = genererProduits(320);
const LOTS_CATALOGUE = PRODUITS_CATALOGUE
  .filter((_, i) => i % 2 === 0)
  .map((p, i) => ({ product_id: p.id, remaining: (i % 9) * 37.5 + 12 }));

const RESULTAT_LOOKUP_INCONNU = {
  code: '3229820129488', known: false, article: null, product: null,
  off: {
    off_source: 'food', aisle: 'Épicerie salée',
    label: 'Petits pois extra-fins surgelés en sachet refermable format familial économique',
    generic_name: 'Petits pois surgelés', brand: 'Marque Repère Sélection Grand Format Économique',
    net_quantity: 1000, net_unit: 'g', image: null, nutriscore: 'a', nova: 1, ecoscore: 'b',
    allergens: null, traces: null, additives: null, off_labels: null,
    nutrition_per_100: { kcal: 65, proteins: 5.4 }, rejections: [],
  },
  off_raw: {}, off_source: 'food',
  candidates: [
    { product_id: 1, name: 'Petits pois surgelés classiques', score: 0.9 },
    { product_id: 2, name: 'Petits pois carottes', score: 0.5 },
  ],
  preselected_product_id: 1,
  price: { price_per_base_unit: 0.0021, source: 'open_prices', store: null },
  conversion_offer: null, throttled: false, timed_out: false,
};

const RESULTAT_LOOKUP_CONNU = {
  code: '1234567890123', known: true,
  article: { id: 99, label: 'Farine de blé T55', brand: 'Francine', net_quantity: 1000, image: null,
            nutriscore: null, kcal_per_base_unit: null },
  product: { id: 50, name: 'Farine de blé T55', base_unit: 'g', default_location_id: 1,
            default_shelf_life_days: 180 },
  off: null, off_raw: null, off_source: null, candidates: [], preselected_product_id: null,
  price: { price_per_base_unit: 0.0018, source: 'store', store: 'Carrefour' },
  conversion_offer: null, throttled: false, timed_out: false,
};

function entreeJournal(id, extra) {
  return {
    id, occurred_at: '2026-08-18T12:00:00', product_name: `Produit ${id}`, quantity: 100,
    base_unit: 'g', reason: 'consumption', kcal: 100, parts_total: null, parts_mine: null,
    ...extra,
  };
}

// Une journée chargée, réaliste — douze entrées, pas trois : une journée à
// trois lignes ne prouve rien sur le débordement. Une jetée (yaourt périmé),
// une partagée à 1/4 (le poulet du dîner, coût jamais divisé — seuls les
// nutriments le sont), une sans kcal (soupe maison, aucune fiche
// nutritionnelle) — et un dernier grignotage à 1 h du matin, qui compte
// encore pour la soirée du 18 (frontière de 4 h, voir docs/exploitation.md).
const JOURNEE_CHARGEE = {
  food_day: '2026-08-18', start: '2026-08-18T04:00:00', end: '2026-08-19T04:00:00',
  entries: [
    entreeJournal(1, { occurred_at: '2026-08-18T07:15:00', product_name: 'Café noir',
                       quantity: 250, base_unit: 'ml', kcal: 5 }),
    entreeJournal(2, { occurred_at: '2026-08-18T07:20:00', product_name: 'Pain complet',
                       quantity: 80, base_unit: 'g', kcal: 190 }),
    entreeJournal(3, { occurred_at: '2026-08-18T07:22:00', product_name: 'Beurre doux',
                       quantity: 15, base_unit: 'g', kcal: 108 }),
    entreeJournal(4, { occurred_at: '2026-08-18T07:23:00', product_name: 'Confiture de fraises maison',
                       quantity: 20, base_unit: 'g', kcal: 52 }),
    entreeJournal(5, { occurred_at: '2026-08-18T12:30:00', product_name: 'Poulet rôti',
                       quantity: 400, base_unit: 'g', kcal: 480, parts_total: 4, parts_mine: 1 }),
    entreeJournal(6, { occurred_at: '2026-08-18T12:32:00', product_name: 'Riz basmati demi-complet',
                       quantity: 150, base_unit: 'g', kcal: 195 }),
    entreeJournal(7, { occurred_at: '2026-08-18T16:45:00', product_name: 'Fromage râpé emmental',
                       quantity: 30, base_unit: 'g', kcal: 112 }),
    entreeJournal(8, { occurred_at: '2026-08-18T16:47:00', product_name: 'Compote de pommes',
                       quantity: 1, base_unit: 'piece', kcal: 60 }),
    entreeJournal(9, { occurred_at: '2026-08-18T18:05:00', product_name: 'Yaourt nature',
                       quantity: 1, base_unit: 'piece', kcal: 65, reason: 'waste' }),
    entreeJournal(10, { occurred_at: '2026-08-18T19:30:00', product_name: 'Soupe de légumes maison',
                        quantity: 300, base_unit: 'ml', kcal: null }),
    entreeJournal(11, { occurred_at: '2026-08-18T20:15:00', product_name: 'Chocolat noir 70%',
                        quantity: 20, base_unit: 'g', kcal: 118 }),
    entreeJournal(12, { occurred_at: '2026-08-19T01:10:00', product_name: 'Eau gazeuse aromatisée',
                        quantity: 500, base_unit: 'ml', kcal: 0 }),
  ],
  totals: { kcal: 960, cost: 5.51, waste_cost: 0.35, unvalued: 1 },
};

// Quatorze seaux (deux semaines de jours) : un jour à zéro (absence du
// foyer) et un maximum net qui se détache vraiment des autres, sinon les
// barres ne prouvent rien sur les proportions extrêmes du graphe.
const SERIE_QUATORZE_JOURS = {
  granularity: 'day',
  buckets: [
    { label: '2026-08-06', kcal: 1850, cost: 4.20, waste_cost: 0 },
    { label: '2026-08-07', kcal: 2100, cost: 5.10, waste_cost: 0.35 },
    { label: '2026-08-08', kcal: 1920, cost: 4.60, waste_cost: 0 },
    { label: '2026-08-09', kcal: 0, cost: 0, waste_cost: 0 },
    { label: '2026-08-10', kcal: 2260, cost: 6.05, waste_cost: 0 },
    { label: '2026-08-11', kcal: 1780, cost: 4.15, waste_cost: 0.60 },
    { label: '2026-08-12', kcal: 2010, cost: 4.85, waste_cost: 0 },
    { label: '2026-08-13', kcal: 1990, cost: 4.70, waste_cost: 0 },
    { label: '2026-08-14', kcal: 2150, cost: 5.30, waste_cost: 0 },
    { label: '2026-08-15', kcal: 3420, cost: 9.80, waste_cost: 0 },
    { label: '2026-08-16', kcal: 2080, cost: 4.95, waste_cost: 0.20 },
    { label: '2026-08-17', kcal: 1940, cost: 4.55, waste_cost: 0 },
    { label: '2026-08-18', kcal: 960, cost: 5.51, waste_cost: 0.35 },
    { label: '2026-08-19', kcal: 2040, cost: 4.90, waste_cost: 0 },
  ],
};

// --- scénarios ---------------------------------------------------------------
//
// Chacun mène `<home-stock-panel>`, via son `hass` factice et les mêmes
// gestes qu'une personne (clic sur un bouton de navigation, scan, appui sur
// « ranger », événement de la fiche vers l'écran « manger »), jusqu'à l'un
// des neuf écrans du spec — jamais en modifiant directement son état
// interne, pour que le vérificateur exerce vraiment le câblage plutôt que
// de le contourner.
// --- lot 3 : des fixtures RÉALISTES, pas symboliques -----------------------
//
// Une liste à trois entrées ne prouve rien sur le débordement. Quarante
// recettes avec des noms longs, sept jours × quatre créneaux, huit lignes de
// validation : c'est à cette densité-là qu'une grille casse.

const RECETTES_DENSES = {
  recipes: Array.from({ length: 40 }, (_, i) => ({
    id: i + 1,
    name: i % 3 === 0
      ? `Bœuf bourguignon à l'ancienne et ses légumes racines ${i + 1}`
      : `Recette ${i + 1}`,
    servings: (i % 6) + 1,
    total_minutes: 20 + (i % 8) * 15,
    image_url: null,
    summary: null,
    language: i % 4 === 0 ? 'en' : 'fr',
    needs_review: i % 4 === 0 ? 1 : 0,
    unmatched_count: i % 5,
  })),
};

const RECETTE_LONGUE = {
  recipe: {
    id: 4, name: 'Gratin de courgettes au chèvre et thym frais', servings: 4,
    total_minutes: 75, utensils: 'mandoline, plat à gratin, poêle',
    summary: 'Un gratin fondant, doré au four, qui se prépare la veille.',
    image_url: null, language: 'fr', needs_review: 0,
  },
  steps: Array.from({ length: 6 }, (_, i) => ({
    id: i + 1, position: i + 1,
    title: `Étape ${i + 1} — préparation détaillée du gratin`,
    image_url: null,
    instructions: i === 1
      ? [
        { id: 21, position: 1, text: 'Émincer les courgettes à la mandoline, en rondelles de trois millimètres.', timer_label: null, timer_seconds: null },
        { id: 22, position: 2, text: 'Faire suer les rondelles à la poêle avec un filet d’huile d’olive.', timer_label: 'Cuisson', timer_seconds: 600 },
        { id: 23, position: 3, text: 'Saler, poivrer, ajouter le thym frais effeuillé.', timer_label: null, timer_seconds: null },
        { id: 24, position: 4, text: 'Égoutter sur un papier absorbant pour retirer l’eau de végétation.', timer_label: null, timer_seconds: null },
        { id: 25, position: 5, text: 'Réserver hors du feu pendant la préparation de l’appareil.', timer_label: null, timer_seconds: null },
      ]
      : [{ id: 100 + i, position: 1, text: `Instruction de l’étape ${i + 1}, suffisamment longue pour occuper deux lignes sur une dalle étroite.`, timer_label: null, timer_seconds: null }],
  })),
  ingredients: [
    { id: 41, position: 1, product_id: 8, product_name: 'Courgette', product_base_unit: 'g', amount: 900, measure_name: null, packaging_name: null, raw_text: '900 g de courgettes', match_state: 'auto', display_amount: '900 g' },
    { id: 42, position: 2, product_id: 9, product_name: 'Bûche de chèvre', product_base_unit: 'g', amount: 200, measure_name: null, packaging_name: null, raw_text: '200 g de chèvre', match_state: 'confirmed', display_amount: '200 g' },
    { id: 43, position: 3, product_id: null, product_name: null, product_base_unit: null, amount: null, measure_name: null, packaging_name: null, raw_text: 'quelques brins de thym frais', match_state: 'unmatched', candidates: [{ product_id: 12, name: 'Thym', score: 0.8 }, { product_id: 13, name: 'Thym citron', score: 0.6 }] },
  ],
};

const SEMAINE_CHARGEE = {
  meals: (() => {
    const jours = Array.from({ length: 7 },
      (_, i) => `2026-08-${String(21 + i).padStart(2, '0')}`);
    const creneaux = ['breakfast', 'lunch', 'dinner', 'snack'];
    const repas = [];
    let id = 1;
    jours.forEach((jour, j) => {
      creneaux.forEach((creneau, c) => {
        if ((j + c) % 3 === 0) return;          // partiellement rempli
        repas.push({
          id: id++, uid: `u${id}`, day: jour, slot_key: creneau, position: 0,
          recipe_id: c === 2 ? 4 : null,
          recipe_name: c === 2 ? 'Gratin de courgettes au chèvre et thym frais' : null,
          product_id: c === 3 ? 8 : null,
          product_name: c === 3 ? 'Yaourt nature' : null,
          note: c < 2 ? 'Restes de la veille' : null,
          servings: 2,
          state: j === 0 && c === 1 ? 'done' : 'planned',
        });
      });
    });
    // Un jour à trois repas sur le même créneau.
    repas.push({ id: id++, uid: 'x1', day: jours[3], slot_key: 'dinner', position: 1, recipe_id: null, recipe_name: null, product_id: null, product_name: null, note: 'Entrée', servings: 1, state: 'planned' });
    repas.push({ id: id++, uid: 'x2', day: jours[3], slot_key: 'dinner', position: 2, recipe_id: null, recipe_name: null, product_id: null, product_name: null, note: 'Dessert', servings: 1, state: 'planned' });
    return repas;
  })(),
};

const PREVIEW_AVEC_MANQUE = {
  meal_id: 12, day: '2026-08-21', slot_key: 'dinner',
  recipe: { id: 4, name: 'Gratin de courgettes au chèvre et thym frais', servings: 2 },
  servings: 4, factor: 2,
  lines: [
    { ingredient_id: 41, label: '1,8 kg', product_id: 8, product_name: 'Courgette', base_unit: 'g', status: 'ok', needed: 1800, available: 2400, raw_text: '900 g de courgettes', batches: [{ batch_id: 3, quantity: 1800 }] },
    { ingredient_id: 42, label: '400 g', product_id: 9, product_name: 'Bûche de chèvre affinée', base_unit: 'g', status: 'short', needed: 400, available: 180, raw_text: '200 g de chèvre', batches: [{ batch_id: 5, quantity: 180 }] },
    { ingredient_id: 44, label: '4 cuillères à soupe', product_id: 10, product_name: "Huile d'olive vierge extra", base_unit: 'ml', status: 'ok', needed: 60, available: 500, raw_text: '2 cs d’huile', batches: [{ batch_id: 7, quantity: 60 }] },
    { ingredient_id: 45, label: '200 g', product_id: 11, product_name: 'Crème fraîche épaisse', base_unit: 'ml', status: 'ok', needed: 200, available: 400, raw_text: '100 g de crème', batches: [{ batch_id: 9, quantity: 200 }] },
    { ingredient_id: 46, label: '4 pièces', product_id: 14, product_name: 'Œufs plein air', base_unit: 'piece', status: 'ok', needed: 4, available: 12, raw_text: '2 œufs', batches: [{ batch_id: 11, quantity: 4 }] },
    { ingredient_id: 47, label: '100 g', product_id: 15, product_name: 'Parmesan râpé', base_unit: 'g', status: 'ok', needed: 100, available: 250, raw_text: '50 g de parmesan', batches: [{ batch_id: 13, quantity: 100 }] },
  ],
  by_hand: [
    { ingredient_id: 43, label: '', product_id: null, product_name: null, base_unit: null, status: 'unmatched', needed: null, available: 0, raw_text: 'quelques brins de thym frais', batches: [] },
    { ingredient_id: 48, label: '', product_id: 16, product_name: 'Muscade', base_unit: 'piece', status: 'unquantified', needed: null, available: 1, raw_text: 'une pointe de muscade', batches: [] },
  ],
  dish: {
    product_name: 'Reste — Gratin de courgettes au chèvre et thym frais',
    parts: 4, best_before: '2026-08-24', cost: 7.35, kcal: 486, unvalued: 0,
  },
  blocking: ['short'],
};

// --- lot 5 : les pires cas réels des deux nouveaux écrans --------------------
//
// Quatorze piles suivies (le compte de la maison), dont une muette, une
// orpheline et une jamais relevée ; trois capteurs à déclarer ; des libellés
// longs (« Interrupteur salle de bain ») ; un stock de rechange à zéro. Un
// écran qui ne déborde que sur les cas faciles n'a pas été vérifié.
const PILES_QUATORZE = { batteries: [
  { id: 1, label: 'Interrupteur salle de bain', kind: 'primary', verb: 'Pile à changer',
    tracked: true, exclusion_reason: null, entity_id: 'sensor.interrupteur_sdb_batterie',
    state: '4', orphaned: false, device_name: 'Philips Hue RWL022', model: 'RWL022',
    equipment_id: null, cell_count: 1, low_percent: 20, keep_percent: 25,
    last_percent: 4, last_reading_at: '2026-08-21T06:00:00', installed_on: null,
    note: null, spare_label: 'CR2032', spare_in_stock: 0 },
  { id: 2, label: 'Rideau Cuisine', kind: 'built_in', verb: 'Recharger', tracked: true,
    exclusion_reason: null, entity_id: 'sensor.0xa4c1386d02de3c39_battery', state: '12',
    orphaned: false, device_name: 'Rideau Cuisine', model: 'TS030F', equipment_id: null,
    cell_count: 1, low_percent: 20, keep_percent: 25, last_percent: 12,
    last_reading_at: '2026-08-21T06:00:00', installed_on: null, note: null,
    spare_label: null, spare_in_stock: null },
  { id: 3, label: 'Capteur Chambre', kind: 'rechargeable_cell', verb: 'Piles à recharger',
    tracked: true, exclusion_reason: null, entity_id: 'sensor.capteur_batterie_2',
    state: 'unavailable', orphaned: false, device_name: null, model: null,
    equipment_id: null, cell_count: 2, low_percent: 20, keep_percent: 25,
    last_percent: 18, last_reading_at: '2026-08-19T06:00:00', installed_on: null,
    note: null, spare_label: 'AAA', spare_in_stock: 4 },
  { id: 4, label: 'Thermomètre Salon (retiré)', kind: 'primary', verb: 'Pile à changer',
    tracked: true, exclusion_reason: null, entity_id: null, state: null, orphaned: true,
    device_name: null, model: null, equipment_id: null, cell_count: 1,
    low_percent: 20, keep_percent: 25, last_percent: null, last_reading_at: null,
    installed_on: null, note: null, spare_label: null, spare_in_stock: null },
  { id: 5, label: 'Aqara Smart lock U200 Lite', kind: 'built_in', verb: 'Recharger',
    tracked: true, exclusion_reason: null, entity_id: 'sensor.aqara_smart_lock_u200_lite_batterie',
    state: 'unknown', orphaned: false, device_name: 'Aqara Smart lock U200 Lite',
    model: 'U200 Lite', equipment_id: null, cell_count: 1, low_percent: 20,
    keep_percent: 25, last_percent: null, last_reading_at: null, installed_on: null,
    note: null, spare_label: null, spare_in_stock: null },
  ...Array.from({ length: 9 }, (unused, index) => ({
    id: 6 + index, label: `Capteur ${index + 1}`, kind: 'primary', verb: 'Pile à changer',
    tracked: true, exclusion_reason: null, entity_id: `sensor.capteur_${index}_batterie`,
    state: String(30 + index * 7), orphaned: false, device_name: null, model: null,
    equipment_id: null, cell_count: 1, low_percent: 20, keep_percent: 25,
    last_percent: 30 + index * 7, last_reading_at: '2026-08-21T06:00:00',
    installed_on: null, note: null, spare_label: 'CR2032', spare_in_stock: 0 })),
] };

const PILES_A_DECLARER = { sensors: [
  { entity_registry_id: 'u-a', entity_id: 'sensor.browser_mod_606bfd06_browser_battery',
    device_id: 'd-a', device_name: 'tablette-cuisine Browser battery',
    model: 'browser_mod', state: '100' },
  { entity_registry_id: 'u-b', entity_id: 'sensor.cle_de_la_peugeot_e208_batterie_ble',
    device_id: 'd-b', device_name: 'Sac Batterie BLE', model: 'MiTag', state: '100' },
  { entity_registry_id: 'u-c', entity_id: 'sensor.collier_soraya_batterie_ble',
    device_id: 'd-c', device_name: 'Collier Soraya Batterie BLE', model: 'FnR', state: '100' },
] };

// Trente-quatre équipements sur quatre emplacements, dont une garantie
// expirée, une absente, et une fiche avec trois consommables dont un en
// rupture et une notice introuvable.
const EQUIPEMENTS_TRENTE_QUATRE = { equipment: [
  { id: 1, name: 'Purificateur d’air Xiaomi zhimi.airpurifier.mb4', location_name: 'Salon',
    brand: 'Xiaomi', model: 'zhimi.airpurifier.mb4', serial: 'SN-000000042',
    purchased_on: '2025-01-01', warranty_months: 24, warranty_ends_on: '2027-01-01',
    days_left: 133, manual_url: null, manual_media_id: 'notices/purificateur.pdf',
    note: null, consumable_count: 3, device_id: null },
  { id: 2, name: 'Aspirateur Roborock S5', location_name: 'Cuisine', brand: 'Roborock',
    model: 'S5', serial: null, purchased_on: '2020-01-01', warranty_months: 24,
    warranty_ends_on: '2022-01-01', days_left: -1693, manual_url: null,
    manual_media_id: null, note: null, consumable_count: 4, device_id: null },
  { id: 3, name: 'Poêle 28 cm', location_name: null, brand: null, model: null,
    serial: null, purchased_on: null, warranty_months: null, warranty_ends_on: null,
    days_left: null, manual_url: null, manual_media_id: null, note: null,
    consumable_count: 0, device_id: null },
  ...Array.from({ length: 31 }, (unused, index) => ({
    id: 4 + index, name: `Équipement ${index + 1}`,
    location_name: ['Salon', 'Cuisine', 'Chambre', 'Salle de bain'][index % 4],
    brand: null, model: null, serial: null, purchased_on: null, warranty_months: null,
    warranty_ends_on: null, days_left: null, manual_url: null, manual_media_id: null,
    note: null, consumable_count: 0, device_id: null })),
] };

const FICHE_PURIFICATEUR = { equipment: {
  ...EQUIPEMENTS_TRENTE_QUATRE.equipment[0],
  manual_introuvable: true,
  consumables: [
    { id: 10, equipment_id: 1, product_id: 5, role: 'filter', label: 'filtre HEPA',
      unit: 'percent', low_value: 15, keep_value: 20,
      product_name: 'Filtre HEPA MB4', in_stock: 0 },
    { id: 11, equipment_id: 1, product_id: 6, role: 'brush', label: 'brosse latérale',
      unit: null, low_value: null, keep_value: null,
      product_name: 'Brosse latérale Roborock S5', in_stock: 2 },
    { id: 12, equipment_id: 1, product_id: 7, role: 'other', label: null,
      unit: 'minutes', low_value: 900, keep_value: 1350,
      product_name: 'Charbon actif', in_stock: 1 },
  ],
  batteries: [
    { id: 4, label: 'Télécommande du purificateur', verb: 'Pile à changer',
      last_percent: 4 },
  ],
} };

/** Lot 2bis : la même journée, plus les plafonds réglés et la moyenne des
 *  sept journées closes. Deux objectifs cèdent sur la journée, un troisième
 *  seulement sur la moyenne — la ligne grise. */
const JOURNEE_AVEC_OBJECTIFS = {
  ...JOURNEE_CHARGEE,
  totals: { kcal: 2450, cost: 5.51, waste_cost: 0.35, unvalued: 1,
            salt: 9.1, sugars: 41.2 },
  goals: { kcal: 2000, salt: 6, sugars: 50 },
  week_mean: { kcal: 1980, cost: 6.2, waste_cost: 0.4, unvalued: 0,
               salt: 5.4, sugars: 58.3 },
};

/** Le rapport de bascule du scénario de rendu. Douze contrôles, dont trois
 *  bloquants de trois natures différentes : un qui n'a rien mesuré, un qui a
 *  un écart, un qui attend un acquittement nominatif. */
const RAPPORT_BASCULE = {
  ok: false,
  blocking: ['C0', 'C1', 'C4'],
  archive_path: null,
  checks: [
    { code: 'C0', label: 'Schéma et gel de Grocy', grocy_count: 0, home_count: 0,
      gap: 0, verdict: 'empty', blocking: true,
      details: ['la copie de grocy.db est introuvable'] },
    { code: 'C1', label: 'Un lot par ligne de stock', grocy_count: 108,
      home_count: 107, gap: 1, verdict: 'gap', blocking: true,
      details: ['grocy:stock:541 (Sorbet Fraise) : aucun lot importé'] },
    { code: 'C2', label: 'Les quantités, au millionième près', grocy_count: 108,
      home_count: 108, gap: 0, verdict: 'ok', blocking: false, details: [] },
    { code: 'C3', label: 'Les dates de péremption', grocy_count: 108,
      home_count: 98, gap: 0, verdict: 'ok', blocking: false,
      details: ['10 sentinelles 2999-12-31 attendues à NULL'] },
    { code: 'C4', label: 'Les prix écartés, acquittés nommément', grocy_count: 7,
      home_count: 92, gap: 0, verdict: 'unacknowledged', blocking: true,
      details: ['grocy:stock:419 (Petits pois) : prix écarté — 1487 × 2.45'] },
    { code: 'C5', label: "Un mouvement d'entrée par lot", grocy_count: 108,
      home_count: 108, gap: 0, verdict: 'ok', blocking: false, details: [] },
    { code: 'C6', label: "Les trois cumuls n'ont pas bougé", grocy_count: 108,
      home_count: 108, gap: 0, verdict: 'ok', blocking: false,
      details: ['kcal_total', 'cost_total', 'cost_waste_total'] },
    { code: 'C7', label: 'Piles et équipements (lot 5)', grocy_count: 34,
      home_count: 34, gap: 0, verdict: 'ok', blocking: false, details: [] },
    { code: 'C8', label: 'Recettes, ingrédients, instructions, minuteurs',
      grocy_count: 102, home_count: 102, gap: 0, verdict: 'ok', blocking: false,
      details: ['102 recettes', '510 ingrédients'] },
    { code: 'C9', label: 'Les images, sur le disque', grocy_count: 82,
      home_count: 82, gap: 0, verdict: 'ok', blocking: false, details: [] },
    { code: 'C10', label: 'Planning et liste de courses', grocy_count: 42,
      home_count: 42, gap: 0, verdict: 'ok', blocking: false,
      details: ['42 repas à venir'] },
    { code: 'C11', label: 'Ce qui lit encore Grocy dans la maison',
      grocy_count: 0, home_count: 0, gap: 0, verdict: 'ok', blocking: false,
      details: [] },
  ],
};

const SCENARIOS = [
  {
    nom: 'Scanner (écran par défaut)',
    fixture: { reponses: { 'home_stock/session/current': null } },
    actions: [],
    ecranAttendu: 'home-stock-scanner',
  },
  {
    nom: 'Fiche (article inconnu, plusieurs candidats)',
    fixture: {
      reponses: {
        'home_stock/session/current': null,
        'home_stock/lookup': RESULTAT_LOOKUP_INCONNU,
      },
    },
    actions: [{ type: 'dispatch-code-lu', code: '3229820129488' }],
    ecranAttendu: 'home-stock-fiche',
    // La fiche occupe l'écran ENTIER : on y scanne, la coquille ne doit rien
    // voler à la caméra. Le test unitaire ne prouvait que la moitié positive
    // (« la barre est là partout ailleurs ») ; voici l'autre moitié.
    elementAbsent: { enfant: null, selector: 'hs-nav-bar' },
  },
  {
    nom: 'Panier (plusieurs lignes, plusieurs rayons)',
    fixture: {
      reponses: {
        'home_stock/session/current': sessionOuverte('shopping', 'Carrefour', LIGNES_PANIER),
      },
    },
    actions: [{ type: 'route', path: '/cart' }],
    ecranAttendu: 'home-stock-panier',
  },
  {
    nom: 'Rangement (liste à ranger)',
    fixture: {
      reponses: {
        'home_stock/session/current': sessionOuverte('to_store', 'Carrefour', LIGNES_RANGEMENT),
        'home_stock/locations/list': { locations: EMPLACEMENTS },
      },
    },
    actions: [{ type: 'route', path: '/put-away' }],
    ecranAttendu: 'home-stock-rangement',
  },
  {
    nom: 'Courses (ouverture : pastilles de magasins et saisie libre)',
    fixture: {
      reponses: {
        'home_stock/session/current': null,
        'home_stock/stores/list': { stores: MAGASINS },
      },
    },
    actions: [{ type: 'route', path: '/shopping' }],
    ecranAttendu: 'home-stock-session',
    elementAttendu: { enfant: 'home-stock-session', selector: '.ouvrir-session' },
  },
  {
    nom: 'Courses (clôture armée : session à ranger, lignes abandonnées)',
    fixture: {
      reponses: {
        'home_stock/session/current': sessionOuverte('to_store', 'Carrefour', LIGNES_RANGEMENT),
        'home_stock/stores/list': { stores: MAGASINS },
      },
    },
    actions: [
      { type: 'route', path: '/shopping' },
      { type: 'click-in-child', enfant: 'home-stock-session', selector: '.clore-session' },
    ],
    ecranAttendu: 'home-stock-session',
    // Le second appui doit vraiment être proposé : sans ce contrôle, un
    // armement qui ne rendrait aucun bouton passerait pour « rien à signaler ».
    elementAttendu: { enfant: 'home-stock-session', selector: '.confirmer-cloture' },
  },
  {
    nom: 'Catalogue (quelques centaines de produits, édition ouverte)',
    fixture: {
      reponses: {
        'home_stock/session/current': null,
        'home_stock/products/list': { products: PRODUITS_CATALOGUE },
        'home_stock/aisles/list': { aisles: RAYONS },
        'home_stock/locations/list': { locations: EMPLACEMENTS },
        'home_stock/batches/list': { batches: LOTS_CATALOGUE },
        'home_stock/product/get': { product: PRODUITS_CATALOGUE[0] },
      },
    },
    actions: [
      { type: 'click-nav', ecran: 'catalogue' },
      { type: 'click-in-child', enfant: 'home-stock-catalogue', selector: '.modifier' },
    ],
    ecranAttendu: 'home-stock-catalogue',
    // Le clic sur « Modifier » doit vraiment avoir ouvert le panneau
    // d'édition — sans quoi son propre débordement (le bug réel trouvé
    // pendant le développement de ce script) ne serait jamais mesuré.
    elementAttendu: { enfant: 'home-stock-catalogue', selector: '.edition' },
  },
  {
    nom: 'Réglages (rayons, emplacements, resynchronisation lancée)',
    fixture: {
      reponses: {
        'home_stock/session/current': null,
        'home_stock/aisles/list': { aisles: RAYONS },
        'home_stock/locations/list': { locations: EMPLACEMENTS },
      },
      service: { 'home_stock.resync_off': {} },
    },
    actions: [
      { type: 'route', path: '/settings' },
      { type: 'click-in-child', enfant: 'home-stock-reglages', selector: '.resynchroniser' },
    ],
    ecranAttendu: 'home-stock-reglages',
    elementAttendu: { enfant: 'home-stock-reglages', selector: '.message-resync' },
  },
  {
    // Un scénario où tout serait vert ne mesurerait pas le rouge, et c'est
    // exactement le piège du lot 6 rejoué au niveau du rendu : le rapport
    // porte donc un bloquant sur écart (C1), un « rien mesuré » (C0) et un
    // « à acquitter » (C4). Le rouge du bloquant doit passer le contraste.
    nom: 'Réglages / Bascule (un contrôle vide, un écart, un à acquitter)',
    fixture: {
      reponses: {
        'home_stock/session/current': null,
        'home_stock/aisles/list': { aisles: RAYONS },
        'home_stock/locations/list': { locations: EMPLACEMENTS },
        'home_stock/migration/check': RAPPORT_BASCULE,
      },
    },
    actions: [
      { type: 'route', path: '/settings' },
      { type: 'click-in-child', enfant: 'home-stock-reglages', selector: '.controler' },
    ],
    ecranAttendu: 'home-stock-reglages',
    elementAttendu: { enfant: 'home-stock-reglages', selector: '.controle.bloquant' },
  },
  {
    nom: 'Bannière de refus (écriture rejetée par le serveur)',
    fixture: {
      reponses: {
        'home_stock/session/current': sessionOuverte('shopping', 'Carrefour', []),
        'home_stock/lookup': RESULTAT_LOOKUP_CONNU,
        'home_stock/session/add_line': { __erreur: { code: 'shopping_refused', message: 'Cette ligne est déjà rangée.' } },
      },
    },
    actions: [
      { type: 'dispatch-code-lu', code: '1234567890123' },
      { type: 'dispatch-article-pret', detail: {
        articleId: 99, quantite: 1000, prixUnitaire: 0.0018, mode: 'panier', offDroppedFields: [],
      } },
    ],
    // Un refus renvoie au scanner (voir panneau.ts : surArticlePret bascule
    // l'écran avant même de connaître le sort de l'écriture) — la bannière,
    // elle, est posée par le panneau lui-même, hors de tout enfant.
    ecranAttendu: 'home-stock-scanner',
    // La bannière a déménagé dans `<hs-header>` (Task 10) : même message du
    // serveur, un cran plus bas dans l'arbre.
    elementAttendu: { enfant: 'hs-header', selector: '.erreur' },
  },
  {
    nom: 'Manger (produit au gramme, portion apprise, partage ouvert)',
    fixture: {
      reponses: {
        'home_stock/session/current': null,
        'home_stock/product/get': {
          product: { id: 1, name: 'Riz basmati demi-complet', base_unit: 'g' },
          suggested_portion: 80, portion_source: 'learned', serving_quantity: null,
          next_batch: { id: 7, remaining: 500, best_before: '2026-09-01' },
        },
      },
    },
    // Pas de navigation ici : « manger » n'a ni bouton de famille ni URL
    // sans identifiant, il s'ouvre sur un produit désigné (tâche 15). Le
    // brief décrivait un type d'action `click` inexistant — corrigé en
    // `click-in-child`, le vocabulaire déjà utilisé pour cliquer dans un
    // écran monté sous le panneau (voir Catalogue et Réglages ci-dessus).
    actions: [
      { type: 'dispatch-evenement', nom: 'manger-produit', detail: { product_id: 1 } },
      { type: 'click-in-child', enfant: 'home-stock-consommation', selector: '.partage-bascule' },
    ],
    ecranAttendu: 'home-stock-consommation',
    elementAttendu: { enfant: 'home-stock-consommation', selector: '.compteurs' },
  },
  {
    nom: 'Journal (journée chargée, barres sur quatorze jours)',
    fixture: {
      reponses: {
        'home_stock/session/current': null,
        'home_stock/journal/day': JOURNEE_CHARGEE,
        'home_stock/journal/series': SERIE_QUATORZE_JOURS,
      },
    },
    actions: [{ type: 'route', path: '/log' }],
    ecranAttendu: 'home-stock-journal',
  },
  {
    nom: 'Recettes (liste dense, badges à relire et non appariés)',
    fixture: { reponses: { 'home_stock/session/current': null,
                           'home_stock/recipes/list': RECETTES_DENSES } },
    actions: [{ type: 'route', path: '/recipes' }],
    ecranAttendu: 'home-stock-recettes',
  },
  {
    // Pas de `click-nav` : la vue cuisine n'est pas une destination de la
    // barre, on y entre depuis une liste — d'où l'événement, comme « manger ».
    nom: 'Recette (étape avec minuteur, vue cuisine)',
    fixture: { reponses: { 'home_stock/session/current': null,
                           'home_stock/recipe/get': RECETTE_LONGUE } },
    actions: [
      { type: 'dispatch-evenement', nom: 'recette-ouverte', detail: { recipe_id: 4 } },
      { type: 'click-in-child', enfant: 'home-stock-recette', selector: '.suivant' },
      { type: 'click-in-child', enfant: 'home-stock-recette', selector: '.suivant' },
    ],
    ecranAttendu: 'home-stock-recette',
    elementAttendu: { enfant: 'home-stock-recette', selector: '.minuteur' },
  },
  {
    nom: 'Planning (semaine chargée)',
    fixture: { reponses: { 'home_stock/session/current': null,
                           'home_stock/meals/list': SEMAINE_CHARGEE } },
    actions: [{ type: 'click-nav', ecran: 'planning' }],
    ecranAttendu: 'home-stock-planning',
  },
  {
    nom: 'Validation (un ingrédient manquant, partage ouvert)',
    fixture: { reponses: { 'home_stock/session/current': null,
                           'home_stock/meal/preview': PREVIEW_AVEC_MANQUE } },
    actions: [
      { type: 'dispatch-evenement', nom: 'valider-repas', detail: { meal_id: 12 } },
      { type: 'click-in-child', enfant: 'home-stock-validation',
        selector: '.partage-bascule input' },
    ],
    ecranAttendu: 'home-stock-validation',
  },
  {
    nom: 'Piles (quatorze suivies, trois à déclarer, une orpheline)',
    fixture: {
      reponses: {
        'home_stock/session/current': null,
        'home_stock/batteries/list': PILES_QUATORZE,
        'home_stock/batteries/discover': PILES_A_DECLARER,
      },
    },
    actions: [{ type: 'click-nav', ecran: 'piles' }],
    ecranAttendu: 'home-stock-piles',
  },
  {
    nom: 'Piles (fiche ouverte, geste destructif armé)',
    fixture: {
      reponses: {
        'home_stock/session/current': null,
        'home_stock/batteries/list': PILES_QUATORZE,
        'home_stock/batteries/discover': { sensors: [] },
        'home_stock/battery/events': { events: [
          { id: 2, occurred_at: '2026-06-01T10:00:00', kind: 'replacement',
            movement_id: 4, note: null },
          { id: 1, occurred_at: '2026-01-01T10:00:00', kind: 'install',
            movement_id: null, note: null },
        ] },
      },
    },
    actions: [
      { type: 'click-nav', ecran: 'piles' },
      { type: 'click-in-child', enfant: 'home-stock-piles', selector: '.pile' },
      { type: 'click-in-child', enfant: 'home-stock-piles', selector: '.evenement' },
    ],
    ecranAttendu: 'home-stock-piles',
    elementAttendu: { enfant: 'home-stock-piles', selector: '.evenement-passe' },
  },
  {
    nom: 'Équipements (fiche chargée : garantie, notice, trois consommables)',
    fixture: {
      reponses: {
        'home_stock/session/current': null,
        'home_stock/equipment/list': EQUIPEMENTS_TRENTE_QUATRE,
        'home_stock/equipment/get': FICHE_PURIFICATEUR,
      },
    },
    actions: [
      { type: 'route', path: '/equipment' },
      { type: 'click-in-child', enfant: 'home-stock-equipements', selector: '.equipement' },
    ],
    ecranAttendu: 'home-stock-equipements',
    elementAttendu: { enfant: 'home-stock-equipements', selector: '.delier' },
  },
  {
    nom: 'Liste (quatre rayons, deux origines, trois cochées repliées)',
    fixture: {
      reponses: {
        'home_stock/session/current': null,
        'home_stock/list/items': LISTE_CHARGEE,
      },
    },
    actions: [{ type: 'click-nav', ecran: 'liste' }],
    ecranAttendu: 'home-stock-liste',
    elementAttendu: { enfant: 'home-stock-liste', selector: '.cochees' },
  },
  {
    // Pas de `click-nav` : « Ticket » n'est pas une destination de la barre,
    // on y entre depuis la session ou depuis un bandeau — d'où l'événement,
    // comme la vue cuisine et la validation d'un repas.
    nom: 'Ticket (lu, deux lignes non rapprochées, écart au total, application armée)',
    fixture: { reponses: { 'home_stock/session/current': null } },
    actions: [
      { type: 'dispatch-evenement', nom: 'ticket-ouvert',
        detail: { ticket: TICKET_LU, agent_configure: true } },
      { type: 'click-in-child', enfant: 'home-stock-ticket', selector: '.appliquer' },
    ],
    ecranAttendu: 'home-stock-ticket',
    elementAttendu: { enfant: 'home-stock-ticket', selector: '.avertissement' },
  },
  {
    // Lot 2bis. Le même écran « manger » que ci-dessus, motif « Jeté » : la
    // consigne de tri doit être visible, et rester UNE LIGNE — la hauteur de
    // l'écran ne doit pas dépendre de ce qu'Open Food Facts sait de
    // l'emballage.
    nom: 'Manger (consigne de tri sur un rebut)',
    fixture: {
      reponses: {
        'home_stock/session/current': null,
        'home_stock/product/get': {
          product: { id: 1, name: 'Yaourt nature brassé bio', base_unit: 'g' },
          suggested_portion: 125, portion_source: 'manual', serving_quantity: null,
          next_batch: { id: 9, remaining: 500, best_before: '2026-09-01' },
          packaging: { bins: ['yellow', 'glass'],
                       materials: ['en:pp-polypropylene', 'en:glass'] },
        },
      },
    },
    actions: [
      { type: 'dispatch-evenement', nom: 'manger-produit', detail: { product_id: 1 } },
      // Deuxième bouton de motif : « Jeté ».
      { type: 'click-in-child', enfant: 'home-stock-consommation',
        selector: '.motifs .motif:nth-child(2)' },
    ],
    ecranAttendu: 'home-stock-consommation',
    elementAttendu: { enfant: 'home-stock-consommation', selector: '.tri' },
  },
  {
    // Lot 2bis. Trois objectifs réglés, deux dépassés sur la journée et un
    // troisième sur la seule moyenne des sept journées closes : les lignes
    // doivent tenir sous les totaux, sans débordement.
    nom: 'Journal (trois objectifs, deux dépassés)',
    fixture: {
      reponses: {
        'home_stock/session/current': null,
        'home_stock/journal/day': JOURNEE_AVEC_OBJECTIFS,
        'home_stock/journal/series': SERIE_QUATORZE_JOURS,
      },
    },
    actions: [{ type: 'route', path: '/log' }],
    ecranAttendu: 'home-stock-journal',
    elementAttendu: { enfant: 'home-stock-journal', selector: '.objectif-semaine' },
  },
  // --- lot 7 : la coquille elle-même ---------------------------------------
  //
  // Trois choses qu'aucun écran ne peut prouver à sa place : la barre en bas,
  // l'en-tête qui sait quand il n'y a nulle part où remonter, et la pastille.
  {
    nom: 'Coquille : barre basse, en-tête sans retour (racine)',
    fixture: {
      reponses: {
        'home_stock/session/current': null,
        'home_stock/list/items': LISTE_CHARGEE,
      },
    },
    actions: [{ type: 'click-nav', ecran: 'liste' }],
    ecranAttendu: 'home-stock-liste',
    elementAttendu: { enfant: 'hs-nav-bar', selector: '.destination.active' },
    // Une racine n'a nulle part où remonter : pas de bouton Retour. Sans ce
    // contrôle en négatif, un en-tête qui en afficherait toujours un
    // passerait pour irréprochable.
    elementAbsent: { enfant: 'hs-header', selector: '.retour' },
  },
  {
    nom: 'Coquille : en-tête avec retour (sous-écran)',
    fixture: {
      reponses: {
        'home_stock/session/current': null,
        'home_stock/journal/day': JOURNEE_CHARGEE,
        'home_stock/journal/series': SERIE_QUATORZE_JOURS,
      },
    },
    actions: [{ type: 'route', path: '/log' }],
    ecranAttendu: 'home-stock-journal',
    elementAttendu: { enfant: 'hs-header', selector: '.retour' },
  },
  {
    // La surcouche de confirmation n'était mesurée par RIEN : ni sa cible
    // tactile, ni son contraste, ni son débordement. Et `ecranAttendu` vaut
    // ici `home-stock-rangement` : c'est la preuve, dans un vrai navigateur,
    // que la confirmation se pose PAR-DESSUS l'écran sans le démonter — donc
    // que « Rester ici » ne jette pas les emplacements déjà saisis.
    nom: 'Coquille : confirmation de départ, en surcouche du rangement',
    fixture: {
      reponses: {
        'home_stock/session/current': null,
        'home_stock/lookup': RESULTAT_LOOKUP_CONNU,
        'home_stock/locations/list': { locations: EMPLACEMENTS },
        'home_stock/list/items': LISTE_CHARGEE,
      },
    },
    actions: [
      { type: 'dispatch-code-lu', code: '1234567890123' },
      { type: 'dispatch-article-pret', detail: {
        articleId: 99, quantite: 1000, prixUnitaire: 0.0018,
        mode: 'rangement', offDroppedFields: [],
      } },
      { type: 'click-nav', ecran: 'liste' },
    ],
    ecranAttendu: 'home-stock-rangement',
    elementAttendu: { enfant: null, selector: '.confirmation-quitter-rangement' },
  },
  {
    nom: 'Coquille : pastille de compte sur Courses',
    fixture: {
      reponses: {
        'home_stock/session/current': sessionOuverte('shopping', 'Carrefour', LIGNES_PANIER),
      },
    },
    actions: [],
    ecranAttendu: 'home-stock-scanner',
    elementAttendu: { enfant: 'hs-nav-bar', selector: '.badge' },
  },
];

// --- ce qui s'exécute DANS la page ------------------------------------------
//
// Playwright sérialise cette fonction telle quelle et l'exécute dans le
// navigateur : elle ne doit fermer sur rien d'extérieur, seulement sur son
// argument.
async function monterEtMesurer({ fixture, actions, cibleMinPx, contrasteMin, styleCasse, racineCassure = null, ecranAttendu = null, elementAttendu = null, elementAbsent = null, sansScannerNatif = false }) {
  function attendre(ms) { return new Promise((resolve) => { setTimeout(resolve, ms); }); }

  function reponsePour(msg) {
    const reponse = fixture.reponses ? fixture.reponses[msg.type] : undefined;
    if (reponse && typeof reponse === 'object' && '__erreur' in reponse) {
      return Promise.reject(reponse.__erreur);
    }
    return Promise.resolve(reponse === undefined ? {} : reponse);
  }

  const hass = {
    connection: {
      sendMessagePromise: (msg) => reponsePour(msg),
      subscribeMessage: () => Promise.resolve(() => {}),
    },
    language: 'fr',
    callService: (domaine, service) => {
      const cle = `${domaine}.${service}`;
      const reponse = fixture.service ? fixture.service[cle] : undefined;
      if (reponse && typeof reponse === 'object' && '__erreur' in reponse) {
        return Promise.reject(reponse.__erreur);
      }
      return Promise.resolve(reponse === undefined ? {} : reponse);
    },
  };

  // Le repli clavier du scanner ne se déclenche que sans bus companion NI
  // `BarcodeDetector`. Le premier est absent d'une page ordinaire ; le second
  // dépend de la plateforme (absent de Chrome sous Linux, présent ailleurs),
  // et un scénario qui ouvrirait vraiment la caméra ne finirait jamais. On
  // le retire donc explicitement plutôt que d'en dépendre.
  if (sansScannerNatif) {
    Object.defineProperty(window, 'BarcodeDetector', { value: undefined, configurable: true });
  }

  const panneau = document.createElement('home-stock-panel');
  panneau.hass = hass;
  document.body.appendChild(panneau);

  // L'auto-vérification casse volontairement le rendu en injectant une
  // feuille de style DANS le shadow DOM du panneau : une balise <style> posée
  // dans le <head> de la page ne franchit jamais la frontière du shadow DOM
  // (chaque composant Lit encapsule la sienne), donc une régression réelle
  // dans un composant ne se laisserait jamais casser depuis l'extérieur de
  // cette façon-là — il faut viser le même shadow root que celui qui sera mesuré.
  // `racineCassure` : depuis la coquille (Task 11), les boutons de navigation
  // vivent dans le shadow root de `<hs-nav-bar>`, pas dans celui du panneau —
  // et une feuille posée dans le second ne franchit pas la frontière du
  // premier. Viser le bon shadow root est la condition pour que la cassure
  // porte vraiment sur ce qui sera mesuré.
  function racineDe(selecteur) {
    if (!selecteur) return panneau.shadowRoot;
    const hote = panneau.shadowRoot.querySelector(selecteur);
    return hote && hote.shadowRoot ? hote.shadowRoot : null;
  }

  if (styleCasse) {
    await attendre(0);
    await panneau.updateComplete;
    const racine = racineDe(racineCassure);
    if (racine) {
      const hote = racineCassure ? panneau.shadowRoot.querySelector(racineCassure) : null;
      if (hote && hote.updateComplete) await hote.updateComplete;
      const style = document.createElement('style');
      style.textContent = styleCasse;
      racine.appendChild(style);
    }
  }

  async function reglerAttente() {
    await panneau.updateComplete;
    // La coquille d'abord (elle décide de la mise en page), puis l'écran. Les
    // dix-sept écrans y sont, pas douze : un écran oublié se mesurait à
    // moitié peint.
    const enfants = ['hs-nav-bar', 'hs-header',
      'home-stock-scanner', 'home-stock-fiche', 'home-stock-panier',
      'home-stock-rangement', 'home-stock-session', 'home-stock-catalogue',
      'home-stock-reglages', 'home-stock-consommation', 'home-stock-journal',
      'home-stock-recettes', 'home-stock-recette', 'home-stock-validation',
      'home-stock-planning', 'home-stock-piles', 'home-stock-equipements',
      'home-stock-liste', 'home-stock-ticket'];
    for (const nom of enfants) {
      const enfant = panneau.shadowRoot.querySelector(nom);
      if (enfant && enfant.updateComplete) await enfant.updateComplete;
      if (enfant && enfant.shadowRoot) {
        for (const petit of enfant.shadowRoot.querySelectorAll('hs-icon, hs-card, hs-button')) {
          if (petit.updateComplete) await petit.updateComplete;
        }
      }
    }
  }

  await attendre(0);
  await reglerAttente();
  await attendre(20);
  await reglerAttente();

  // Un bouton de FAMILLE, dans la barre de la coquille. Rend `null` quand il
  // n'existe pas — un no-op silencieux, exactement comme avant : c'est le
  // contrôle « écran jamais atteint » plus bas qui doit l'attraper, et
  // l'auto-vérification en fait la preuve à chaque exécution.
  function boutonFamille(famille) {
    const barre = panneau.shadowRoot.querySelector('hs-nav-bar');
    if (!barre || !barre.shadowRoot) return null;
    return barre.shadowRoot.querySelector(`[data-family="${famille}"]`);
  }

  for (const action of actions) {
    if (action.type === 'click-nav') {
      const bouton = boutonFamille(action.famille);
      if (bouton) bouton.click();
    } else if (action.type === 'route') {
      // Ce que Home Assistant repasse au panneau quand l'URL change — donc
      // aussi ce que fait le bouton Retour du navigateur.
      panneau.route = { prefix: '/home-stock', path: action.path };
    } else if (action.type === 'dispatch-code-lu') {
      const scanner = panneau.shadowRoot.querySelector('home-stock-scanner');
      if (scanner) {
        scanner.dispatchEvent(new CustomEvent('code-lu', {
          detail: { code: action.code }, bubbles: true, composed: true,
        }));
      }
    } else if (action.type === 'dispatch-article-pret') {
      const fiche = panneau.shadowRoot.querySelector('home-stock-fiche');
      if (fiche) {
        fiche.dispatchEvent(new CustomEvent('article-pret', {
          detail: action.detail, bubbles: true, composed: true,
        }));
      }
    } else if (action.type === 'dispatch-evenement') {
      // L'écran « manger » n'a aucun bouton de navigation qui y mène (voir
      // SCENARIOS) : la fiche et le catalogue le désignent tous les deux par
      // un événement `manger-produit` écouté sur le panneau lui-même
      // (`this.addEventListener` dans panneau.ts, jamais câblé à un enfant
      // précis). On l'émet donc directement sur `panneau`, comme le ferait
      // n'importe lequel des deux écrans qui l'émettent réellement.
      panneau.dispatchEvent(new CustomEvent(action.nom, {
        detail: action.detail, bubbles: true, composed: true,
      }));
    } else if (action.type === 'click-in-child') {
      const enfant = panneau.shadowRoot.querySelector(action.enfant);
      if (enfant && enfant.shadowRoot) {
        const cible = enfant.shadowRoot.querySelector(action.selector);
        if (cible) cible.click();
      }
    }
    await attendre(30);
    await reglerAttente();
    await attendre(30);
    await reglerAttente();
  }

  await attendre(50);

  // --- l'écran attendu a-t-il seulement été atteint ? ---------------------
  //
  // `boutonNav` ci-dessus fait `if (bouton) bouton.click()` : un bouton
  // introuvable (un libellé renommé, un écran qui ne s'est jamais monté) est
  // un no-op SILENCIEUX — sans ce contrôle, le scénario mesurerait alors
  // l'écran resté affiché sous le nom d'un autre, et un vrai défaut sur
  // l'écran jamais atteint (le débordement de `.edition`, trouvé une
  // première fois de cette façon pendant le développement de ce script)
  // resterait invisible tout en rapportant « aucun défaut ». Un vérificateur
  // qui ne sait pas distinguer « cet écran est propre » de « je ne l'ai
  // jamais atteint » est pire qu'aucun vérificateur, parce qu'on lui fait
  // confiance.
  let ecranManquant = null;
  if (ecranAttendu && !panneau.shadowRoot.querySelector(ecranAttendu)) {
    ecranManquant = ecranAttendu;
  }
  // `enfant` accepte une CHAÎNE de shadow roots (« hs-nav-bar hs-icon ») :
  // depuis la coquille, ce qui compte peut vivre à trois niveaux de
  // profondeur — `<ha-svg-icon>` dans `<hs-icon>` dans `<hs-nav-bar>`.
  function racineEnfant(chemin) {
    let racine = panneau.shadowRoot;
    if (!chemin) return racine;
    for (const nom of chemin.trim().split(/\s+/)) {
      const hote = racine.querySelector(nom);
      if (!hote || !hote.shadowRoot) return null;
      racine = hote.shadowRoot;
    }
    return racine;
  }

  let elementManquant = null;
  if (elementAttendu) {
    const racine = racineEnfant(elementAttendu.enfant);
    if (!racine || !racine.querySelector(elementAttendu.selector)) {
      elementManquant = `${elementAttendu.enfant ?? '<home-stock-panel>'} ${elementAttendu.selector}`;
    }
  }
  // L'inverse : ce qui ne DOIT PAS être là. « L'en-tête d'une racine n'a pas
  // de bouton Retour » ne se prouve pas autrement — et un scénario qui ne
  // prouve rien vaut mieux supprimé qu'affiché en vert.
  let elementEnTrop = null;
  if (elementAbsent) {
    const racine = racineEnfant(elementAbsent.enfant);
    if (racine && racine.querySelector(elementAbsent.selector)) {
      elementEnTrop = `${elementAbsent.enfant ?? '<home-stock-panel>'} ${elementAbsent.selector}`;
    }
  }

  // --- mesures -----------------------------------------------------------

  // Le document ne déborde plus tout seul depuis la coquille : `.contenu`
  // porte `overflow-y: auto`, et le CSS force alors `overflow-x` de `visible`
  // à `auto` — un écran trop large y gagne une barre de défilement au lieu de
  // pousser la page. Sans la mesure ci-dessous, le contrôle de débordement
  // serait devenu inerte sur les dix-sept écrans d'un coup.
  const contenu = panneau.shadowRoot.querySelector('.contenu');
  const debordement = document.documentElement.scrollWidth > document.documentElement.clientWidth + 1
    || document.body.scrollWidth > document.body.clientWidth + 1
    || Boolean(contenu && contenu.scrollWidth > contenu.clientWidth + 1);

  function tousLesElements() {
    const resultat = [];
    (function parcourir(racine) {
      for (const el of racine.querySelectorAll('*')) {
        resultat.push(el);
        if (el.shadowRoot) parcourir(el.shadowRoot);
      }
    })(document);
    return resultat;
  }

  function decrire(el) {
    const classe = typeof el.className === 'string' && el.className
      ? `.${el.className.trim().split(/\s+/).join('.')}` : '';
    const texte = (el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 50);
    return `${el.tagName.toLowerCase()}${classe} « ${texte} »`;
  }

  const elements = tousLesElements();

  const SELECTEUR_INTERACTIF = 'button, a[href], select, input, [role="button"]';
  const ciblesTropPetites = [];
  const dejaVerifiees = new Set();
  for (const el of elements) {
    if (el.tagName === 'OPTION') continue;
    if (!el.matches(SELECTEUR_INTERACTIF)) continue;
    if ('disabled' in el && el.disabled) continue;
    // Une case à cocher ou un bouton radio a une cible native minuscule par
    // défaut, mais quand un <label> l'enveloppe (le motif de `fiche.ts`),
    // c'est LUI la cible réellement tapée — un clic n'importe où dedans
    // active le contrôle. C'est ce label qu'il faut mesurer, pas le rond
    // natif, sous peine de faux positifs sur un motif par ailleurs correct.
    let cible = el;
    if ((el.tagName === 'INPUT') && (el.type === 'radio' || el.type === 'checkbox')) {
      cible = el.closest('label') || el;
    }
    if (dejaVerifiees.has(cible)) continue;
    dejaVerifiees.add(cible);
    const r = cible.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) continue;
    if (Math.min(r.width, r.height) < cibleMinPx) {
      ciblesTropPetites.push({ element: decrire(cible), largeur: Math.round(r.width), hauteur: Math.round(r.height) });
    }
  }

  function parseCouleur(chaine) {
    if (!chaine) return [0, 0, 0, 0];
    const m = chaine.match(/rgba?\(([^)]+)\)/);
    if (!m) return [0, 0, 0, 0];
    const parts = m[1].split(',').map((s) => parseFloat(s.trim()));
    return [parts[0] || 0, parts[1] || 0, parts[2] || 0, parts.length > 3 ? parts[3] : 1];
  }
  function fondEffectif(el) {
    const couches = [];
    let noeud = el;
    while (noeud) {
      const style = getComputedStyle(noeud);
      const [r, g, b, a] = parseCouleur(style.backgroundColor);
      if (a > 0) couches.push([r, g, b, a]);
      if (a >= 0.999) break;
      noeud = noeud.parentElement || (noeud.getRootNode && noeud.getRootNode().host) || null;
    }
    let [r, g, b] = [255, 255, 255];
    for (let i = couches.length - 1; i >= 0; i -= 1) {
      const [cr, cg, cb, ca] = couches[i];
      r = cr * ca + r * (1 - ca);
      g = cg * ca + g * (1 - ca);
      b = cb * ca + b * (1 - ca);
    }
    return [r, g, b];
  }
  function luminance([r, g, b]) {
    const lin = (c) => { const v = c / 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
  }
  function ratioContraste(c1, c2) {
    const L1 = luminance(c1); const L2 = luminance(c2);
    const [clair, sombre] = L1 > L2 ? [L1, L2] : [L2, L1];
    return (clair + 0.05) / (sombre + 0.05);
  }

  const contrasteInsuffisant = [];
  for (const el of elements) {
    if (el.tagName === 'OPTION' || el.tagName === 'SCRIPT' || el.tagName === 'STYLE') continue;
    if ('disabled' in el && el.disabled) continue;
    let aTexte = false;
    for (const enfant of el.childNodes) {
      if (enfant.nodeType === 3 && enfant.textContent.trim().length > 0) { aTexte = true; break; }
    }
    if (!aTexte) continue;
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    const style = getComputedStyle(el);
    if (style.visibility === 'hidden' || style.display === 'none') continue;
    const [tr, tg, tb, ta] = parseCouleur(style.color);
    if (ta === 0) continue;
    const c = ratioContraste([tr, tg, tb], fondEffectif(el));
    if (c < contrasteMin) {
      contrasteInsuffisant.push({ element: decrire(el), ratio: Math.round(c * 100) / 100 });
    }
  }

  // Une troncature suppose un conteneur qui masque réellement le
  // débordement SANS offrir de moyen de le voir : `overflow: visible` ne
  // tronque jamais rien (déborde dans le flux, couvert par le test de
  // débordement ci-dessus) — et `auto`/`scroll` non plus : le contenu qui
  // dépasse `clientWidth` y reste entièrement accessible par défilement,
  // c'est un choix délibéré, pas une perte. Round de correction 1 (Task 6) :
  // seuls `hidden` et `clip` masquent réellement quelque chose sans recours,
  // donc seuls eux comptent comme troncature. Avant cette correction, tout
  // `overflow-x: auto` scrollable était signalé à tort — c'est ce faux
  // positif qui avait fait écarter une colonne de graphique défilable au
  // profit d'un `flex-wrap` qui, lui, étalait des barres orphelines.
  const texteTronque = [];
  for (const el of elements) {
    if (el.tagName === 'OPTION' || el.tagName === 'SCRIPT' || el.tagName === 'STYLE') continue;
    const style = getComputedStyle(el);
    if (style.overflowX !== 'hidden' && style.overflowX !== 'clip') continue;
    if (el.scrollWidth > el.clientWidth + 1) {
      texteTronque.push({ element: decrire(el) });
    }
  }

  return { debordement, ciblesTropPetites, contrasteInsuffisant, texteTronque,
           ecranManquant, elementManquant, elementEnTrop };
}

// --- orchestration -----------------------------------------------------------

function formaterDefauts(resultat) {
  const lignes = [];
  if (resultat.ecranManquant) {
    lignes.push(`  - Écran jamais atteint : <${resultat.ecranManquant}> absent du panneau — le scénario a `
      + 'mesuré autre chose sous ce nom (bouton de navigation introuvable, ou action sans effet).');
  }
  if (resultat.elementManquant) {
    lignes.push(`  - Élément attendu absent : ${resultat.elementManquant} — l'action censée le produire `
      + 'n’a apparemment pas eu lieu.');
  }
  if (resultat.elementEnTrop) {
    lignes.push(`  - Élément qui ne devrait pas être là : ${resultat.elementEnTrop}.`);
  }
  if (resultat.debordement) lignes.push('  - Débordement horizontal de la page.');
  for (const c of resultat.ciblesTropPetites) {
    lignes.push(`  - Cible tactile trop petite (${c.largeur}×${c.hauteur}px) : ${c.element}`);
  }
  for (const c of resultat.contrasteInsuffisant) {
    lignes.push(`  - Contraste insuffisant (${c.ratio}:1) : ${c.element}`);
  }
  for (const t of resultat.texteTronque) {
    lignes.push(`  - Texte tronqué : ${t.element}`);
  }
  return lignes;
}

function aDesDefauts(resultat) {
  return Boolean(resultat.ecranManquant) || Boolean(resultat.elementManquant)
    || Boolean(resultat.elementEnTrop) || resultat.debordement
    || resultat.ciblesTropPetites.length > 0 || resultat.contrasteInsuffisant.length > 0
    || resultat.texteTronque.length > 0;
}

async function lancerNavigateur() {
  try {
    return await chromium.launch({ headless: true });
  } catch {
    // L'exécutable chromium propre à cette version de playwright-core n'est
    // pas forcément téléchargé sur cette machine — Google Chrome, lui, l'est
    // presque toujours (utilisé par d'autres outils du dépôt).
    return chromium.launch({ headless: true, channel: 'chrome' });
  }
}

async function executerScenarios(navigateur, urlHarnais, familleParEcran) {
  let fautes = 0;
  let total = 0;
  for (const format of FORMATS) {
    console.log(`\n=== ${format.nom} ===`);
    for (const scenario of SCENARIOS) {
      total += 1;
      const contexte = await navigateur.newContext({ viewport: { width: format.width, height: format.height } });
      const page = await contexte.newPage();
      await page.goto(urlHarnais, { waitUntil: 'load' });
      await page.waitForFunction(() => Boolean(window.customElements.get('home-stock-panel')));
      const resultat = await page.evaluate(monterEtMesurer, {
        fixture: scenario.fixture, actions: preparerActions(scenario.actions, familleParEcran),
        cibleMinPx: CIBLE_MIN_PX, contrasteMin: CONTRASTE_MIN,
        ecranAttendu: scenario.ecranAttendu ?? null, elementAttendu: scenario.elementAttendu ?? null,
        elementAbsent: scenario.elementAbsent ?? null,
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

// --- le bundle tel qu'il est DÉPLOYÉ : minifié -----------------------------
//
// Tout le reste de ce script — et toute la suite vitest — construit sans
// minification. Une branche qui dépendait du NOM d'une classe
// (`scanner.constructor.name === 'ScannerClavier'`) passait donc partout et
// ne marchait nulle part : `rollup.config.mjs` minifie avec `terser`, qui
// renomme les classes. Sur un appareil sans bus companion ni
// `BarcodeDetector` — le seul cas où cette branche compte — le plus gros
// bouton de l'écran ne faisait alors rien du tout : ni erreur, ni pavé de
// saisie. Ce contrôle-ci construit avec minification et pilote le repli
// clavier pour de vrai.
// --- les scénarios propres à la vue dense -----------------------------------
//
// Exécutés dans le SEUL 1920 × 1080. Ajoutés à `SCENARIOS`, ils tourneraient
// aussi en 412 px, où ils mesureraient la mise en page ÉTROITE en croyant
// mesurer la dense — un contrôle vert qui ne prouve rien. Une liste à part,
// et son nom le dit.
const SCENARIOS_LARGES = [
  {
    nom: 'Catalogue dense : tableau de trois cents produits, édition ouverte à côté',
    fixture: {
      reponses: {
        'home_stock/session/current': null,
        'home_stock/products/list': { products: PRODUITS_CATALOGUE },
        'home_stock/aisles/list': { aisles: RAYONS },
        'home_stock/locations/list': { locations: EMPLACEMENTS },
        'home_stock/batches/list': { batches: LOTS_CATALOGUE },
        'home_stock/product/get': { product: PRODUITS_CATALOGUE[0] },
      },
    },
    actions: [
      { type: 'click-nav', ecran: 'catalogue' },
      { type: 'click-in-child', enfant: 'home-stock-catalogue', selector: '.modifier' },
    ],
    ecranAttendu: 'home-stock-catalogue',
    // Le tableau ET le volet d'édition : c'est leur COEXISTENCE qui fait
    // l'écran dense, et un volet qui aurait remplacé la liste passerait ce
    // contrôle-ci sans elle.
    elementAttendu: { enfant: 'home-stock-catalogue', selector: '.dense .volet-edition' },
  },
  {
    // La coquille bascule en rail à gauche au-delà de 1000 px. C'est le seul
    // format où ça se mesure, et le seul endroit où `flex-direction: row`
    // remplace `column-reverse` sans que l'ordre du DOM ne bouge.
    nom: 'Coquille : rail à gauche, en-tête et contenu à droite',
    fixture: {
      reponses: {
        'home_stock/session/current': null,
        'home_stock/products/list': { products: PRODUITS_CATALOGUE },
        'home_stock/aisles/list': { aisles: RAYONS },
        'home_stock/locations/list': { locations: EMPLACEMENTS },
        'home_stock/batches/list': { batches: LOTS_CATALOGUE },
      },
    },
    actions: [{ type: 'click-nav', ecran: 'catalogue' }],
    ecranAttendu: 'home-stock-catalogue',
    elementAttendu: { enfant: 'hs-nav-bar', selector: '.barre.rail' },
  },
];

async function executerScenariosLarges(navigateur, urlHarnais, familleParEcran) {
  console.log(`\n=== Vue dense (${FORMAT_LARGE.nom}) ===`);
  let fautes = 0;
  for (const scenario of SCENARIOS_LARGES) {
    const contexte = await navigateur.newContext({
      viewport: { width: FORMAT_LARGE.width, height: FORMAT_LARGE.height },
    });
    const page = await contexte.newPage();
    await page.goto(urlHarnais, { waitUntil: 'load' });
    await page.waitForFunction(() => Boolean(window.customElements.get('home-stock-panel')));
    const resultat = await page.evaluate(monterEtMesurer, {
      fixture: scenario.fixture, actions: preparerActions(scenario.actions, familleParEcran),
      cibleMinPx: CIBLE_MIN_PX, contrasteMin: CONTRASTE_MIN,
      ecranAttendu: scenario.ecranAttendu ?? null,
      elementAttendu: scenario.elementAttendu ?? null,
      elementAbsent: scenario.elementAbsent ?? null,
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
  return fautes;
}

// Trois scénarios représentatifs seulement : la suite complète × 3 palettes
// × 3 formats ferait 219 mesures pour un gain marginal. Ce qui compte ici,
// c'est qu'aucune des deux autres palettes ne soit JAMAIS mesurée — pas
// qu'elles le soient partout.
const NOMS_BALAYAGE = [
  'Scanner (écran par défaut)',
  'Liste (quatre rayons, deux origines, trois cochées repliées)',
  'Bannière de refus (écriture rejetée par le serveur)',
];

async function executerBalayagePalettes(navigateur, urlsParPalette, familleParEcran) {
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
        fixture: scenario.fixture, actions: preparerActions(scenario.actions, familleParEcran),
        cibleMinPx: CIBLE_MIN_PX, contrasteMin: CONTRASTE_MIN,
        ecranAttendu: scenario.ecranAttendu ?? null,
        elementAttendu: scenario.elementAttendu ?? null,
        elementAbsent: scenario.elementAbsent ?? null,
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

const SCENARIOS_MINIFIES = [
  {
    nom: 'Repli clavier du scanner (sans caméra système ni BarcodeDetector)',
    fixture: { reponses: { 'home_stock/session/current': null } },
    actions: [{ type: 'click-in-child', enfant: 'home-stock-scanner', selector: '.bouton-scan' }],
    ecranAttendu: 'home-stock-scanner',
    elementAttendu: { enfant: 'home-stock-scanner', selector: '.saisie-manuelle' },
    sansScannerNatif: true,
  },
  {
    // « Manger » s'atteint par un événement, jamais un `.nav-bouton` — le
    // motif que `terser` pourrait casser ici est celui de l'écouteur posé
    // sur le panneau (`this.addEventListener('manger-produit', …)`), pas un
    // sélecteur de bouton. Sur le bundle non minifié il n'y a aucune raison
    // que ça diffère ; c'est justement ce que ce contrôle prouve.
    nom: 'Manger (bundle minifié, atteint par événement)',
    fixture: {
      reponses: {
        'home_stock/session/current': null,
        'home_stock/product/get': {
          product: { id: 1, name: 'Riz basmati demi-complet', base_unit: 'g' },
          suggested_portion: 80, portion_source: 'learned', serving_quantity: null,
          next_batch: { id: 7, remaining: 500, best_before: '2026-09-01' },
        },
      },
    },
    actions: [{ type: 'dispatch-evenement', nom: 'manger-produit', detail: { product_id: 1 } }],
    ecranAttendu: 'home-stock-consommation',
  },
  {
    // La vue cuisine est l'écran qui dépend le plus de noms de classes CSS —
    // minuteurs, puces, bloc Ingrédients — et `terser` est passé par là. Elle
    // s'atteint elle aussi par un événement, donc elle exerce le même
    // écouteur d'hôte que « manger », sur le bundle réellement livré.
    nom: 'Recette (bundle minifié, vue cuisine avec minuteur)',
    fixture: { reponses: { 'home_stock/session/current': null,
                           'home_stock/recipe/get': RECETTE_LONGUE } },
    actions: [
      { type: 'dispatch-evenement', nom: 'recette-ouverte', detail: { recipe_id: 4 } },
      { type: 'click-in-child', enfant: 'home-stock-recette', selector: '.suivant' },
      { type: 'click-in-child', enfant: 'home-stock-recette', selector: '.suivant' },
    ],
    ecranAttendu: 'home-stock-recette',
    elementAttendu: { enfant: 'home-stock-recette', selector: '.minuteur' },
  },
];

async function verifierBundleMinifie(navigateur, urlMinifie, familleParEcran) {
  console.log('\n=== Bundle minifié (celui qui part en production) ===');
  let fautes = 0;
  for (const scenario of SCENARIOS_MINIFIES) {
    const contexte = await navigateur.newContext({ viewport: { width: 412, height: 915 } });
    const page = await contexte.newPage();
    await page.goto(urlMinifie, { waitUntil: 'load' });
    await page.waitForFunction(() => Boolean(window.customElements.get('home-stock-panel')));
    const resultat = await page.evaluate(monterEtMesurer, {
      fixture: scenario.fixture, actions: preparerActions(scenario.actions, familleParEcran),
      cibleMinPx: CIBLE_MIN_PX, contrasteMin: CONTRASTE_MIN,
      ecranAttendu: scenario.ecranAttendu, elementAttendu: scenario.elementAttendu,
      elementAbsent: scenario.elementAbsent ?? null,
      sansScannerNatif: scenario.sansScannerNatif,
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
  return fautes;
}

// --- ce que voit celui qui arrive depuis Lovelace ---------------------------
//
// Servis par la page `/ha`, où `DEFINIR_HA_MINIMAL` enregistre `ha-card`,
// `ha-button` et `ha-svg-icon` AVANT le bundle. Partout ailleurs, le harnais
// mesure le repli des enveloppes — le cas de la tablette de la cuisine, qui
// ouvre `/home-stock` directement. Les deux chemins existent en production ;
// un seul était mesuré.
const SCENARIOS_HA_CHARGE = [
  {
    nom: 'Coquille servie par Lovelace (ha-svg-icon rendu, pas le repli)',
    fixture: {
      reponses: {
        'home_stock/session/current': null,
        'home_stock/list/items': LISTE_CHARGEE,
      },
    },
    actions: [{ type: 'click-nav', ecran: 'liste' }],
    ecranAttendu: 'home-stock-liste',
    // La preuve que c'est bien la branche `<ha-svg-icon>` de `hs-icon` qui
    // est rendue : sans elle, ce scénario mesurerait le même repli que les
    // autres et ne prouverait rien de plus.
    elementAttendu: { enfant: 'hs-nav-bar hs-icon', selector: 'ha-svg-icon' },
  },
  {
    nom: 'En-tête servi par Lovelace : refus du serveur, icônes HA',
    fixture: {
      reponses: {
        'home_stock/session/current': sessionOuverte('shopping', 'Carrefour', []),
        'home_stock/lookup': RESULTAT_LOOKUP_CONNU,
        'home_stock/session/add_line': { __erreur: { code: 'shopping_refused', message: 'Cette ligne est déjà rangée.' } },
      },
    },
    actions: [
      { type: 'dispatch-code-lu', code: '1234567890123' },
      { type: 'dispatch-article-pret', detail: {
        articleId: 99, quantite: 1000, prixUnitaire: 0.0018, mode: 'panier', offDroppedFields: [],
      } },
    ],
    ecranAttendu: 'home-stock-scanner',
    elementAttendu: { enfant: 'hs-header hs-icon', selector: 'ha-svg-icon' },
  },
];

async function executerScenariosHaCharge(navigateur, urlHa, familleParEcran) {
  console.log('\n=== Éléments Home Assistant chargés (arrivée depuis Lovelace) ===');
  let fautes = 0;
  for (const scenario of SCENARIOS_HA_CHARGE) {
    const contexte = await navigateur.newContext({ viewport: { width: 412, height: 915 } });
    const page = await contexte.newPage();
    await page.goto(urlHa, { waitUntil: 'load' });
    await page.waitForFunction(() => Boolean(window.customElements.get('home-stock-panel')));
    const resultat = await page.evaluate(monterEtMesurer, {
      fixture: scenario.fixture, actions: preparerActions(scenario.actions, familleParEcran),
      cibleMinPx: CIBLE_MIN_PX, contrasteMin: CONTRASTE_MIN,
      ecranAttendu: scenario.ecranAttendu ?? null,
      elementAttendu: scenario.elementAttendu ?? null,
      elementAbsent: scenario.elementAbsent ?? null,
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
  return fautes;
}

// --- auto-vérification : le script sait-il vraiment échouer ? ---------------
//
// Casse volontairement une chose par catégorie de défaut, sur une page
// jetable, et vérifie que `monterEtMesurer` la détecte bien — la preuve que
// « aucun défaut trouvé » ci-dessus signifie quelque chose.
// `racine` : les boutons de navigation vivent désormais dans le shadow root
// de `<hs-nav-bar>`, et une feuille posée dans celui du panneau ne les
// atteint pas. Casser à côté de ce qui sera mesuré, c'est prouver que le
// vérificateur détecte une régression qu'aucune régression réelle ne
// produirait — pire que rien.
const CASSURES = [
  {
    nom: 'cible tactile réduite sous 62 px',
    racine: 'hs-nav-bar',
    css: '.destination { min-height: 20px !important; min-width: 20px !important; height: 20px !important; padding: 0 !important; }',
    verifie: (r) => r.ciblesTropPetites.length > 0,
  },
  {
    nom: 'contraste texte/fond effondré',
    racine: 'hs-nav-bar',
    css: '.destination { background: #f5f5f5 !important; color: #f0f0f0 !important; }',
    verifie: (r) => r.contrasteInsuffisant.length > 0,
  },
  {
    nom: 'débordement horizontal forcé',
    css: '.navigation { width: 4000px !important; }',
    verifie: (r) => r.debordement,
  },
  {
    // La cassure ci-dessus déborde HORS de la zone défilante, et fait donc
    // encore grandir le document. Celle-ci déborde DEDANS : depuis la
    // coquille, `.contenu` porte `overflow-y: auto`, le CSS force alors son
    // `overflow-x` de `visible` à `auto`, et un écran trop large y gagne une
    // barre de défilement au lieu de pousser la page — invisible au contrôle
    // sur le document. C'est la mesure sur `.contenu` qui l'attrape, et
    // c'est cette cassure-ci qui prouve qu'elle sert.
    nom: 'débordement DANS la zone de contenu (invisible au document)',
    css: 'home-stock-scanner { display: block !important; width: 4000px !important; }',
    verifie: (r) => r.debordement,
  },
  {
    nom: 'texte tronqué (ellipsis + overflow hidden)',
    racine: 'hs-nav-bar',
    css: '.destination { max-width: 24px !important; min-width: 0 !important; overflow: hidden !important; white-space: nowrap !important; text-overflow: ellipsis !important; }',
    verifie: (r) => r.texteTronque.length > 0,
  },
];

async function autoVerification(navigateur, urlHarnais) {
  console.log('\n=== Auto-vérification : le script sait-il détecter une régression ? ===');
  let toutDetecte = true;
  for (const cassure of CASSURES) {
    const contexte = await navigateur.newContext({ viewport: { width: 412, height: 915 } });
    const page = await contexte.newPage();
    await page.goto(urlHarnais, { waitUntil: 'load' });
    await page.waitForFunction(() => Boolean(window.customElements.get('home-stock-panel')));
    const resultat = await page.evaluate(monterEtMesurer, {
      fixture: { reponses: { 'home_stock/session/current': null } }, actions: [],
      cibleMinPx: CIBLE_MIN_PX, contrasteMin: CONTRASTE_MIN,
      styleCasse: cassure.css, racineCassure: cassure.racine ?? null,
    });
    await contexte.close();

    const detecte = cassure.verifie(resultat);
    console.log(`  ${detecte ? '✓' : '✗'} ${cassure.nom} — ${detecte ? 'détectée' : 'NON DÉTECTÉE (bug du vérificateur)'}`);
    if (!detecte) toutDetecte = false;
  }

  // Cinquième cassure, d'une nature différente : pas une feuille de style,
  // mais un clic de navigation qui ne trouve JAMAIS son bouton — exactement
  // la régression qu'une relecture a reproduite en renommant un libellé de
  // navigation : `boutonNav` rend `null`, `if (bouton) bouton.click()` ne
  // fait rien, et l'écran reste celui d'avant sous le nom d'un autre. Cette
  // preuve passe par le VRAI chemin de scénario (`monterEtMesurer` avec de
  // vraies `actions`), pas une simulation à côté, pour être fidèle à ce
  // qu'un bouton renommé produirait réellement.
  {
    const contexte = await navigateur.newContext({ viewport: { width: 412, height: 915 } });
    const page = await contexte.newPage();
    await page.goto(urlHarnais, { waitUntil: 'load' });
    await page.waitForFunction(() => Boolean(window.customElements.get('home-stock-panel')));
    const resultat = await page.evaluate(monterEtMesurer, {
      fixture: { reponses: { 'home_stock/session/current': null } },
      // Une FAMILLE qui n'existe pas dans la barre : `boutonFamille` rend
      // `null`, le clic ne part jamais, et l'écran reste celui d'avant sous
      // le nom d'un autre. (Un ÉCRAN inconnu, lui, lève en Node dans
      // `preparerActions` — c'est une faute d'écriture, pas une régression.)
      actions: [{ type: 'click-nav', famille: 'famille-introuvable-expres' }],
      cibleMinPx: CIBLE_MIN_PX, contrasteMin: CONTRASTE_MIN, ecranAttendu: 'home-stock-catalogue',
    });
    await contexte.close();

    const detecte = resultat.ecranManquant === 'home-stock-catalogue';
    console.log(`  ${detecte ? '✓' : '✗'} un clic de navigation qui ne trouve pas son bouton — `
      + `${detecte ? 'détecté comme écran manquant' : 'NON DÉTECTÉ (bug du vérificateur)'}`);
    if (!detecte) toutDetecte = false;
  }

  return toutDetecte;
}

async function main() {
  const sansAutoVerification = process.argv.includes('--sans-auto-verification');
  const deploye = process.argv.includes('--deploye');

  let bundle;
  let bundleMinifie;
  if (deploye) {
    // Le bundle déployé EST déjà celui que `terser` a produit : il n'existe
    // aucune version « non minifiée » de lui à côté pour rejouer la
    // distinction SCENARIOS / SCENARIOS_MINIFIES — les deux jeux de
    // scénarios tournent donc ici sur le même fichier, lu une seule fois.
    console.log(`Lecture du bundle déployé (${BUNDLE_DEPLOYE})…`);
    bundle = readFileSync(BUNDLE_DEPLOYE, 'utf8');
    bundleMinifie = bundle;
    console.log(`Bundle déployé : ${(bundle.length / 1024).toFixed(0)} ko.`);
  } else {
    console.log('Construction du bundle (esbuild, en mémoire — rien n’est écrit sur disque)…');
    bundle = await bundlerApplication();
    bundleMinifie = await bundlerApplication({ minifier: true });
    console.log(`Bundle : ${(bundle.length / 1024).toFixed(0)} ko `
      + `(minifié : ${(bundleMinifie.length / 1024).toFixed(0)} ko).`);
  }

  // Trois pages servies pour tout le run sur le MÊME serveur (127.0.0.1,
  // port éphémère) — une par palette (voir PALETTES) : `'/'` reste la
  // palette par défaut, celle de tout ce qui n'en connaît qu'une (scénarios
  // ordinaires, vue dense, auto-vérification). Le contenu ne change jamais
  // d'un scénario à l'autre au sein d'une même page — seul ce qu'on y
  // injecte après coup (fixture, actions, cassure) varie. Voir
  // `servirPagesStatiques` pour pourquoi `page.setContent()` seul ne suffit
  // pas.
  const { DESTINATIONS } = await chargerDestinations();
  const familleParEcran = new Map(DESTINATIONS.map((d) => [d.screen, d.family]));

  const { url: urlHarnais, fermer: fermerServeur } = await servirPagesStatiques({
    '/': pageHtml(bundle, PALETTES[0]),
    '/p1': pageHtml(bundle, PALETTES[1]),
    '/p2': pageHtml(bundle, PALETTES[2]),
    // La même page, mais avec les `ha-*` enregistrés avant le bundle : voir
    // SCENARIOS_HA_CHARGE.
    '/ha': pageHtml(bundle, PALETTES[0], DEFINIR_HA_MINIMAL),
  });
  const urlsParPalette = PALETTES.map((_, i) => (i === 0 ? urlHarnais : `${urlHarnais}p${i}`));
  const urlHa = `${urlHarnais}ha`;
  // Une seconde page, servie sur son propre port, avec le bundle MINIFIÉ —
  // celui que `npm run build` déploie réellement. Voir SCENARIOS_MINIFIES.
  // Ces scénarios-là ne connaissent que la palette par défaut : le bundle
  // minifié est le même code, la mesure ne dépend pas de la palette.
  const { url: urlMinifie, fermer: fermerServeurMinifie } =
    await servirPagesStatiques({ '/': pageHtml(bundleMinifie, PALETTES[0]) });

  const navigateur = await lancerNavigateur();
  try {
    let { fautes, total } = await executerScenarios(navigateur, urlHarnais, familleParEcran);
    // Le compte porte sur des EXÉCUTIONS, pas sur des scénarios : chaque
    // scénario de `SCENARIOS` tourne dans les trois formats. Les scénarios
    // denses, eux, n'en connaissent qu'un — et ils comptent quand même, sans
    // quoi le chiffre affiché mentirait.
    fautes += await executerScenariosLarges(navigateur, urlHarnais, familleParEcran);
    total += SCENARIOS_LARGES.length;
    const fautesMinifie = await verifierBundleMinifie(navigateur, urlMinifie, familleParEcran);
    fautes += fautesMinifie;
    total += SCENARIOS_MINIFIES.length;
    // Le chemin réellement servi à qui arrive depuis Lovelace.
    fautes += await executerScenariosHaCharge(navigateur, urlHa, familleParEcran);
    total += SCENARIOS_HA_CHARGE.length;
    // Le balayage : trois scénarios représentatifs, sous les deux palettes
    // qu'aucun autre passage ne mesure jamais (voir NOMS_BALAYAGE).
    const balayage = await executerBalayagePalettes(navigateur, urlsParPalette, familleParEcran);
    fautes += balayage.fautes;
    total += balayage.total;

    let autoOk = true;
    if (!sansAutoVerification) {
      autoOk = await autoVerification(navigateur, urlHarnais);
    }

    console.log(`\n${total - fautes}/${total} scénarios sans défaut.`);
    if (fautes > 0) {
      console.log(`${fautes} scénario(s) en défaut — voir le détail ci-dessus.`);
      process.exitCode = 1;
    } else if (!autoOk) {
      console.log('Le vérificateur n’a pas su détecter une régression injectée volontairement : ne pas lui faire confiance.');
      process.exitCode = 1;
    } else {
      console.log('Aucun défaut signalé, et l’auto-vérification confirme que le script sait échouer quand il le faut.');
    }
  } finally {
    await navigateur.close();
    fermerServeur();
    fermerServeurMinifie();
  }
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
