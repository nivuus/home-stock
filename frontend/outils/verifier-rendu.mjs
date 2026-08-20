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
 *      Catalogue/Réglages) — avec des seuils plus stricts que le mur
 *      (`wallpanel` vise 62 px / 5:1 pour une dalle regardée à bout de
 *      bras) : ce panneau se tient en main ou se pilote à la souris, donc
 *      **48 px** de cible tactile et **4,5:1** de contraste — les seuils
 *      WCAG AA standards.
 *
 *  Échoue sur : un débordement horizontal, une cible tactile sous 48 px,
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
 */
import esbuild from 'esbuild';
import { chromium } from 'playwright-core';
import { createServer } from 'node:http';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const ICI = dirname(fileURLToPath(import.meta.url));
const RACINE = join(ICI, '..');
const SRC = join(RACINE, 'src');
const TSCONFIG = join(RACINE, 'tsconfig.json');

const CIBLE_MIN_PX = 48;
const CONTRASTE_MIN = 4.5;

const FORMATS = [
  { nom: 'Téléphone (Pixel, 412×915)', width: 412, height: 915 },
  { nom: 'Bureau (PC, 1280×800)', width: 1280, height: 800 },
];

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

// --- thème HA de secours -----------------------------------------------
//
// Le panneau lit ses couleurs dans les variables CSS que Home Assistant pose
// sur la page (`--primary-color`, `--primary-text-color`…) : aucune instance
// réelle n'étant accessible ici, ce thème en tient lieu. Choisi pour un
// contraste correct par construction (un bleu suffisamment sombre pour du
// texte blanc à 4,5:1, cf. le calcul dans le rapport de tâche) plutôt que
// pour ressembler exactement au thème par défaut de Home Assistant — ce
// script vérifie le CODE du panneau, pas le thème de la maison, qui n'est
// de toute façon pas sous sa main.
const THEME_CSS = `
  :root {
    --primary-background-color: #ffffff;
    --secondary-background-color: #eeeeee;
    --primary-text-color: #212121;
    --secondary-text-color: #5f5f5f;
    --primary-color: #01579b;
  }
  html, body { margin: 0; padding: 0; height: 100%; background: var(--primary-background-color); }
  home-stock-panel { display: block; height: 100%; }
`;

function pageHtml(bundleJs) {
  return `<!doctype html>
<html><head><meta charset="utf-8">
<style>${THEME_CSS}</style>
</head><body>
<home-stock-panel></home-stock-panel>
<script type="module">${bundleJs}</script>
</body></html>`;
}

/** Sert `html` sur 127.0.0.1, port éphémère — jamais exposé au-delà de la
 *  machine, jamais un vrai réseau. Nécessaire : `page.setContent()`
 *  produit un document d'origine opaque où `window.localStorage` lève une
 *  `SecurityError` à la simple lecture de la propriété, ce qui fait
 *  échouer `connectedCallback()` du panneau AVANT même qu'il construise sa
 *  `FileAttente` — silencieusement, puisque c'est une exception non
 *  interceptée dans un cycle de vie Lit, jamais rapportée comme un défaut
 *  de rendu. Une vraie origine `http://127.0.0.1` n'a pas ce problème. */
async function servirPageStatique(html) {
  const serveur = createServer((_requete, reponse) => {
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
const MAGASINS = ['Carrefour', 'Leclerc', 'Lidl', 'Grand Frais', 'Biocoop Les Quatre Chemins'];

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

// --- scénarios ---------------------------------------------------------------
//
// Chacun mène `<home-stock-panel>`, via son `hass` factice et les mêmes
// gestes qu'une personne (clic sur un bouton de navigation, scan, appui sur
// « ranger »), jusqu'à l'un des six écrans du spec — jamais en modifiant
// directement son état interne, pour que le vérificateur exerce vraiment le
// câblage plutôt que de le contourner.
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
  },
  {
    nom: 'Panier (plusieurs lignes, plusieurs rayons)',
    fixture: {
      reponses: {
        'home_stock/session/current': sessionOuverte('shopping', 'Carrefour', LIGNES_PANIER),
      },
    },
    actions: [{ type: 'click-nav', texte: 'Panier' }],
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
    actions: [{ type: 'click-nav', texte: 'Ranger' }],
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
    actions: [{ type: 'click-nav', texte: 'Courses' }],
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
      { type: 'click-nav', texte: 'Courses' },
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
      { type: 'click-nav', texte: 'Catalogue' },
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
      { type: 'click-nav', texte: 'Réglages' },
      { type: 'click-in-child', enfant: 'home-stock-reglages', selector: '.resynchroniser' },
    ],
    ecranAttendu: 'home-stock-reglages',
    elementAttendu: { enfant: 'home-stock-reglages', selector: '.message-resync' },
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
    elementAttendu: { enfant: null, selector: '.erreur-file' },
  },
];

// --- ce qui s'exécute DANS la page ------------------------------------------
//
// Playwright sérialise cette fonction telle quelle et l'exécute dans le
// navigateur : elle ne doit fermer sur rien d'extérieur, seulement sur son
// argument.
async function monterEtMesurer({ fixture, actions, cibleMinPx, contrasteMin, styleCasse, ecranAttendu = null, elementAttendu = null, sansScannerNatif = false }) {
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
  if (styleCasse) {
    await attendre(0);
    await panneau.updateComplete;
    const style = document.createElement('style');
    style.textContent = styleCasse;
    panneau.shadowRoot.appendChild(style);
  }

  async function reglerAttente() {
    await panneau.updateComplete;
    const enfants = ['home-stock-scanner', 'home-stock-fiche', 'home-stock-panier',
      'home-stock-rangement', 'home-stock-catalogue', 'home-stock-reglages'];
    for (const nom of enfants) {
      const enfant = panneau.shadowRoot.querySelector(nom);
      if (enfant && enfant.updateComplete) await enfant.updateComplete;
    }
  }

  await attendre(0);
  await reglerAttente();
  await attendre(20);
  await reglerAttente();

  function boutonNav(texte) {
    const boutons = panneau.shadowRoot.querySelectorAll('.nav-bouton');
    for (const b of boutons) if (b.textContent && b.textContent.includes(texte)) return b;
    return null;
  }

  for (const action of actions) {
    if (action.type === 'click-nav') {
      const bouton = boutonNav(action.texte);
      if (bouton) bouton.click();
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
  let elementManquant = null;
  if (elementAttendu) {
    const racine = elementAttendu.enfant
      ? panneau.shadowRoot.querySelector(elementAttendu.enfant)?.shadowRoot
      : panneau.shadowRoot;
    if (!racine || !racine.querySelector(elementAttendu.selector)) {
      elementManquant = `${elementAttendu.enfant ?? '<home-stock-panel>'} ${elementAttendu.selector}`;
    }
  }

  // --- mesures -----------------------------------------------------------

  const debordement = document.documentElement.scrollWidth > document.documentElement.clientWidth + 1
    || document.body.scrollWidth > document.body.clientWidth + 1;

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
  // débordement (overflow ≠ visible) : un élément `overflow: visible` ne
  // tronque jamais rien, il déborde dans le flux — ce que le test de
  // débordement ci-dessus couvre déjà séparément.
  const texteTronque = [];
  for (const el of elements) {
    if (el.tagName === 'OPTION' || el.tagName === 'SCRIPT' || el.tagName === 'STYLE') continue;
    const style = getComputedStyle(el);
    if (style.overflowX === 'visible') continue;
    if (el.scrollWidth > el.clientWidth + 1) {
      texteTronque.push({ element: decrire(el) });
    }
  }

  return { debordement, ciblesTropPetites, contrasteInsuffisant, texteTronque, ecranManquant, elementManquant };
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
  return Boolean(resultat.ecranManquant) || Boolean(resultat.elementManquant) || resultat.debordement
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

async function executerScenarios(navigateur, urlHarnais) {
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
        fixture: scenario.fixture, actions: scenario.actions,
        cibleMinPx: CIBLE_MIN_PX, contrasteMin: CONTRASTE_MIN,
        ecranAttendu: scenario.ecranAttendu ?? null, elementAttendu: scenario.elementAttendu ?? null,
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
const SCENARIOS_MINIFIES = [
  {
    nom: 'Repli clavier du scanner (sans caméra système ni BarcodeDetector)',
    fixture: { reponses: { 'home_stock/session/current': null } },
    actions: [{ type: 'click-in-child', enfant: 'home-stock-scanner', selector: '.bouton-scan' }],
    ecranAttendu: 'home-stock-scanner',
    elementAttendu: { enfant: 'home-stock-scanner', selector: '.saisie-manuelle' },
    sansScannerNatif: true,
  },
];

async function verifierBundleMinifie(navigateur, urlMinifie) {
  console.log('\n=== Bundle minifié (celui qui part en production) ===');
  let fautes = 0;
  for (const scenario of SCENARIOS_MINIFIES) {
    const contexte = await navigateur.newContext({ viewport: { width: 412, height: 915 } });
    const page = await contexte.newPage();
    await page.goto(urlMinifie, { waitUntil: 'load' });
    await page.waitForFunction(() => Boolean(window.customElements.get('home-stock-panel')));
    const resultat = await page.evaluate(monterEtMesurer, {
      fixture: scenario.fixture, actions: scenario.actions,
      cibleMinPx: CIBLE_MIN_PX, contrasteMin: CONTRASTE_MIN,
      ecranAttendu: scenario.ecranAttendu, elementAttendu: scenario.elementAttendu,
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

// --- auto-vérification : le script sait-il vraiment échouer ? ---------------
//
// Casse volontairement une chose par catégorie de défaut, sur une page
// jetable, et vérifie que `monterEtMesurer` la détecte bien — la preuve que
// « aucun défaut trouvé » ci-dessus signifie quelque chose.
const CASSURES = [
  {
    nom: 'cible tactile réduite sous 48 px',
    css: '.nav-bouton { min-height: 20px !important; min-width: 20px !important; height: 20px !important; padding: 0 !important; }',
    verifie: (r) => r.ciblesTropPetites.length > 0,
  },
  {
    nom: 'contraste texte/fond effondré',
    css: '.nav-bouton { background: #f5f5f5 !important; color: #f0f0f0 !important; }',
    verifie: (r) => r.contrasteInsuffisant.length > 0,
  },
  {
    nom: 'débordement horizontal forcé',
    css: '.navigation { width: 4000px !important; }',
    verifie: (r) => r.debordement,
  },
  {
    nom: 'texte tronqué (ellipsis + overflow hidden)',
    css: '.nav-bouton { max-width: 24px !important; min-width: 0 !important; overflow: hidden !important; white-space: nowrap !important; text-overflow: ellipsis !important; }',
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
      cibleMinPx: CIBLE_MIN_PX, contrasteMin: CONTRASTE_MIN, styleCasse: cassure.css,
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
      actions: [{ type: 'click-nav', texte: 'Bouton Introuvable Exprès' }],
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

  console.log('Construction du bundle (esbuild, en mémoire — rien n’est écrit sur disque)…');
  const bundle = await bundlerApplication();
  const bundleMinifie = await bundlerApplication({ minifier: true });
  console.log(`Bundle : ${(bundle.length / 1024).toFixed(0)} ko `
    + `(minifié : ${(bundleMinifie.length / 1024).toFixed(0)} ko).`);

  // Une seule page servie pour tout le run (127.0.0.1, port éphémère) : le
  // contenu ne change jamais d'un scénario à l'autre — seul ce qu'on y
  // injecte après coup (fixture, actions, cassure) varie. Voir
  // `servirPageStatique` pour pourquoi `page.setContent()` seul ne suffit pas.
  const { url: urlHarnais, fermer: fermerServeur } = await servirPageStatique(pageHtml(bundle));
  // Une seconde page, servie sur son propre port, avec le bundle MINIFIÉ —
  // celui que `npm run build` déploie réellement. Voir SCENARIOS_MINIFIES.
  const { url: urlMinifie, fermer: fermerServeurMinifie } =
    await servirPageStatique(pageHtml(bundleMinifie));

  const navigateur = await lancerNavigateur();
  try {
    let { fautes, total } = await executerScenarios(navigateur, urlHarnais);
    const fautesMinifie = await verifierBundleMinifie(navigateur, urlMinifie);
    fautes += fautesMinifie;
    total += SCENARIOS_MINIFIES.length;

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
