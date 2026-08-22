# home_stock — Refonte UI/UX du panneau Garde-manger

Date : 2026-08-22
Statut : validé en brainstorming, à découper en plan d'implémentation.

## 1. Objectif

Le panneau `/home-stock` rend dix-sept écrans derrière une barre de dix boutons
texte. Il fonctionne, mais il ne se navigue pas et il ne ressemble pas à Home
Assistant. Cette refonte pose une coquille (en-tête, navigation, routes d'URL)
et un langage visuel commun, puis reprend les trois écrans dont le défaut est
structurel.

Elle ne touche **ni le métier, ni les commandes websocket, ni la base**.

## 2. Décisions validées

| Sujet | Décision |
|---|---|
| Douleurs à traiter | Navigation, cohérence visuelle, intégration HA. **Pas** la performance des flux |
| Appareils | Les trois : téléphone 412, bureau 1280+, tablette cuisine (Fire 7) |
| Navigation | Barre de 4 destinations (basse sur téléphone/tablette, rail à gauche sur bureau) + en-tête constant |
| Langage visuel | **Composants HA réels** (`ha-card`, `ha-button`, `ha-svg-icon`) derrière une enveloppe qui replie proprement |
| Périmètre | Coquille + routes d'URL + les trois écrans les plus abîmés. Pas les dix-sept |
| Langue | **Nouveau code et routes d'URL en anglais.** Les dix-sept écrans existants gardent leurs noms français. **L'interface reste en français** |

## 3. Ce que la revue initiale a cru voir, et qui était faux

À consigner, parce que la même erreur se reproduira sinon.

Le thème de secours de `frontend/outils/verifier-rendu.mjs` (constante
`THEME_CSS`, ligne 126) définit **cinq** variables CSS :
`--primary-background-color`, `--secondary-background-color`,
`--primary-text-color`, `--secondary-text-color`, `--primary-color`.

Le panneau en lit **dix**. Les cinq absentes — `--divider-color`,
`--card-background-color`, `--text-primary-color`, `--error-color`,
`--warning-color` — rendent **invalides à la valeur calculée** toutes les
déclarations qui les emploient sans repli. Le harnais n'impose pas non plus de
`font-family`.

Conséquences observées sur les captures, et attribuées à tort au code :

- Planning « sans bordures » : `.case { border: 1px dashed var(--divider-color) }`
  est correct ; c'est la variable manquante qui annule la déclaration.
- Planning « actions en texte nu » : `.valider-repas` / `.annuler-repas` sont
  des boutons de 48 px bordés ; leur fond `var(--card-background-color)` tombe.
- Planning « en serif gras » : Times New Roman est le défaut du navigateur.
  Home Assistant impose Roboto en production.

**Défaut d'outillage réel mis au jour** : le vérificateur mesure ses contrastes
sur une palette qui n'est pas celle servie à l'utilisateur, avec cinq variables
mortes. Ses soixante-treize contrôles verts prouvent moins qu'ils ne le
laissent croire. Réparer le harnais est donc un préalable, pas un bonus
(§ 8.1).

Ce qui reste vrai après vérification : la barre de dix boutons sur trois lignes,
l'onglet courant qui s'efface, dix-sept blocs `static styles` sans base
commune, le Catalogue de 25 949 px sur téléphone, l'accueil vide sous le pli.

## 4. Architecture

### 4.1 Le module `src/shell/`

Nouveau, seul propriétaire de la structure. `panneau.ts` (609 lignes,
aujourd'hui mi-orchestrateur mi-barre de navigation) se réduit à
l'orchestration métier : session, file d'attente, résultat de `lookup`,
articles autonomes en attente de rangement.

| Fichier | Rôle | Dépend de |
|---|---|---|
| `shell/destinations.ts` | La table des 4 familles et des 17 écrans | rien |
| `shell/router.ts` | `path` ⇄ écran, dans les deux sens | `destinations.ts` |
| `shell/nav-bar.ts` | Barre basse ou rail gauche | `destinations.ts`, `ui/` |
| `shell/header.ts` | Retour, titre, actions, file d'attente, bannière | `destinations.ts`, `ui/` |
| `shell/ui/tokens.ts` | La feuille de jetons partagée (`CSSResult`) | rien |
| `shell/ui/hs-card.ts` | Enveloppe de `ha-card` | `ha-available.ts` |
| `shell/ui/hs-button.ts` | Enveloppe de `ha-button` | `ha-available.ts` |
| `shell/ui/hs-icon.ts` | Enveloppe de `ha-svg-icon` | `ha-available.ts`, `icons.ts` |
| `shell/ui/icons.ts` | Les tracés `mdi` que nous portons nous-mêmes | rien |
| `shell/ui/ha-available.ts` | Détection et attente des éléments `ha-*` | rien |

`destinations.ts` est **la seule source de vérité** : la barre, le rail, le
titre de l'en-tête et le routeur la lisent tous. Aucune seconde table à tenir
synchronisée.

### 4.2 Les quatre familles

| Famille | Icône | Racine | Sous-écrans |
|---|---|---|---|
| Courses | `mdi:cart` | **Liste** | Scanner, Fiche, Panier, Session, Rangement, Ticket |
| Stock | `mdi:package-variant` | **Catalogue** | Journal, Manger |
| Cuisine | `mdi:silverware-fork-knife` | **Planning** | Recettes, Recette, Validation |
| Maison | `mdi:home-outline` | **Piles** | Équipements, Réglages |

Les quatre destinations sont **toujours rendues**, l'active est marquée. Le
comportement actuel — masquer le bouton de l'écran courant, ce qui décale tous
les autres à chaque navigation — disparaît.

Pastilles de compte : `Courses` porte le nombre de lignes de panier ou
d'articles à ranger, `Maison` le nombre de piles sous le seuil. C'est
l'information que portaient les libellés `Panier (3)` et `Ranger (4)`.

**Le Scanner cesse d'être l'écran d'accueil.** Il devient une action primaire
(bouton flottant) offerte sur toute la famille Courses. L'accueil devient la
Liste, qui a quelque chose à montrer.

### 4.3 Ce qui est conservé tel quel

Trois comportements existants passent dans la coquille sans changer de
sémantique :

- la confirmation « des articles rapportés seuls n'ont pas encore été rangés »
  avant de quitter le rangement (`panneau.ts`, `demanderNavigation`) ;
- la bannière de refus serveur (`erreurFile`), qui remonte dans l'en-tête ;
- le rappel de session de courses en cours.

## 5. Les routes d'URL

### 5.1 Mécanisme

Aucun changement côté Python. `ha-panel-custom` pose déjà une propriété
`route` sur l'élément du panneau — vérifié dans le chunk
`66102.e901fdb5d70b80d7.js` de `hass_frontend` en HA 2026.8.2 (`route:this.route`
au moment de l'appel de `_setProperties`). Tout `/home-stock/<quoi que ce soit>`
nous parvient sous la forme `{prefix: '/home-stock', path: '/list'}`.

Le panneau déclare donc `@property({attribute: false}) route` et réagit dans
`willUpdate`.

Naviguer = `history.pushState` puis un `CustomEvent('location-changed', {bubbles: true, composed: true})`
sur `window` — la convention du frontend HA. HA nous repasse ensuite `route`.
**Le bouton Retour du navigateur et le geste système d'Android fonctionnent
alors sans code de notre part.**

Une route inconnue retombe sur `/home-stock/list` en `replace`, pour ne pas
laisser d'entrée d'historique morte.

### 5.2 La table

```
/home-stock/list             Liste de courses          (racine Courses)
/home-stock/shopping         Session de courses
/home-stock/cart             Panier
/home-stock/put-away         Rangement
/home-stock/receipt/<id>     Ticket
/home-stock/scan             Scanner
/home-stock/item/<code>      Fiche article
/home-stock/catalog          Catalogue                 (racine Stock)
/home-stock/log              Journal
/home-stock/eat/<product>    Manger
/home-stock/planner          Planning                  (racine Cuisine)
/home-stock/recipes          Recettes
/home-stock/recipe/<id>      Recette
/home-stock/validate/<meal>  Validation de repas
/home-stock/batteries        Piles                     (racine Maison)
/home-stock/equipment        Équipements
/home-stock/settings         Réglages
```

En anglais, comme les commandes websocket (`home_stock/products/list`).

### 5.3 Ce qui se reconstruit, et ce qui ne peut pas

`/item/<code>` rejoue le `lookup` : une fiche rechargée ou partagée se
réaffiche. C'est un appel réseau à chaque ouverture d'URL, assumé.

`/put-away` **ne retrouvera pas** les articles autonomes gardés en mémoire par
le panneau (`enAttenteRangement`) : rien côté serveur ne les représente tant
qu'ils n'ont pas de lot. C'est déjà le cas à chaque rechargement aujourd'hui ;
les routes ne l'aggravent pas et ne le corrigent pas.

### 5.4 Hors périmètre : le contrôle C11

Les routes lèvent le blocage documenté dans `CLAUDE.md` (« le panneau n'a pas
de route d'URL par vue, on ne peut que l'ouvrir en entier »). Elles ne
rebranchent pas pour autant `script.afficher_recette_cuisine` ni
`script.afficher_repas_prevu` : ces scripts passent par `browser_mod`, qui est
`unavailable` sur la tablette cuisine depuis qu'elle affiche l'application
dédiée. Les réparer est un travail dans `tools/wallpanel-app`, pas ici. **Le
contrôle C11 de `check_grocy_migration` reste rouge à l'issue de ce lot.**

## 6. Le langage visuel

### 6.1 Les jetons

`shell/ui/tokens.ts` exporte un `CSSResult` lit. Chaque écran passe de
`static styles = css\`…\`` à `static styles = [tokens, css\`…\`]` : **une ligne
modifiée par écran**, et les dix-sept héritent de la même échelle d'espacement,
des mêmes rayons, de la même typographie et des mêmes couleurs.

Les jetons dérivent des variables HA, avec un repli explicite pour chacune —
c'est précisément l'absence de repli qui a produit le § 3 :

```
--hs-space-1 … --hs-space-6      échelle d'espacement (4 / 8 / 12 / 16 / 24 / 32)
--hs-radius-s / -m / -l          rayons
--hs-text                        var(--primary-text-color, #141414)
--hs-text-2                      var(--secondary-text-color, #5e5e5e)
--hs-surface                     var(--card-background-color, #fff)
--hs-surface-2                   var(--secondary-background-color, #e5e5e5)
--hs-divider                     var(--divider-color, #0000001f)
--hs-accent                      var(--primary-color, #009ac7)
--hs-on-accent                   #141414  /* défaut prudent, recalculé — cf. § 6.1 bis */
--hs-danger                      var(--error-color, #db4437)
--hs-on-danger                   #141414  /* défaut prudent, recalculé — cf. § 6.1 bis */
--hs-warning                     var(--warning-color, #ffa600)
--hs-on-warning                  #141414  /* défaut prudent, recalculé — cf. § 6.1 bis */
--hs-font                        var(--ha-font-family-body, Roboto, Noto, sans-serif)
--hs-touch                       62px
```

**Règle 1** : plus aucune variable HA lue directement dans un écran. Un écran
lit un jeton `--hs-*`, jamais `var(--divider-color)`. Ainsi une variable HA
absente ne peut plus annuler une déclaration.

### 6.1 bis — La couleur du texte sur un fond de marque se CALCULE

Mesuré sur les palettes réelles, et c'est le point qui invalide l'idée qu'un
thème « accorde » toujours son fond et son texte :

| Fond | Texte imposé par le thème | Contraste |
|---|---|---|
| HA défaut, `--primary-color` `#009ac7` | `--text-primary-color` `#ffffff` | **3,26:1** ❌ |
| HA défaut, `--error-color` `#db4437` | `#ffffff` | **4,29:1** ❌ |
| Graphite, `--primary-color` orange | navy | 7,41:1 ✅ |
| Graphite, `--error-color` rose pâle | navy | 6,11:1 ✅ |

**Home Assistant ne garantit pas la lisibilité de son propre texte-sur-primaire.**
`--hs-on-accent: var(--text-primary-color)` échoue donc sous le thème par
défaut, et aucune variable de thème ne donne la bonne réponse.

Trois issues envisagées :

1. **Aucun aplat de marque sous du texte** — tout en contours. Correct partout
   (17:1), mais un panneau sans un seul bouton plein ressemble précisément à
   l'inachevé qu'on cherche à corriger. Écartée.
2. **Choisir une couleur en dur** — c'est le défaut de départ. Écartée.
3. **Calculer** — retenue.

`src/shell/ui/on-color.ts` lit la couleur RÉSOLUE du fond, calcule sa
luminance, et pose `--hs-on-accent` / `--hs-on-danger` / `--hs-on-warning` sur
l'hôte, en clair ou en sombre selon celle qui contraste le mieux. Sous HA
défaut : sombre sur le cyan (6,4:1 au lieu de 3,26). Sous Graphite : navy sur
l'orange (7,41:1). Le panneau garde ses aplats **et** reste lisible sous
n'importe quel thème, y compris un thème que personne ici n'a encore installé.

**La sonde est nécessaire.** `getComputedStyle(el).getPropertyValue('--primary-color')`
ne rend PAS une couleur : la valeur calculée d'une propriété personnalisée est
son flux de jetons, donc littéralement `var(--ha-color-primary-40)` sous HA.
Il faut poser `color: var(--primary-color)` sur un élément sonde et lire son
`color` calculé, qui, lui, est toujours un `rgb(...)`.

**Conséquence pour les tests** : jsdom ne résout ni `var()` ni les couleurs
calculées. Les tests unitaires couvrent les fonctions pures (analyse d'une
couleur, choix de la meilleure des deux) ; le câblage DOM n'est vérifiable que
dans `verifier-rendu.mjs`, qui tourne dans un vrai Chromium. Le dire plutôt
que laisser croire que jsdom le couvre.

**Repli** : si la sonde ne rend rien d'exploitable (jsdom, thème absent), les
jetons gardent la valeur déclarée dans `tokens.ts`. Aucun écran ne casse.

**Règle 2 — jamais de couleur en dur, jamais une paire découplée.** Vérifié sur
l'installation : les deux comptes de la maison n'utilisent pas le même thème
(`Graphite Auto` pour l'un, `default` pour l'autre). Sous Graphite clair,
`--primary-color` est un **orange** `rgb(238, 147, 0)` et `--text-primary-color`
un **navy** `rgb(19, 21, 54)` — 7,41:1, correct. Mais `panneau.ts` écrit
aujourd'hui `background: var(--error-color, #b3261e); color: #fff` : le `#fff`
en dur **casse la paire que le thème avait faite**. Sous le thème HA par défaut,
la paire elle-même ne tient pas (blanc `#fff` sur `#009ac7` = **3,26:1**).

Donc : un fond `--hs-accent` impose son texte `--hs-on-accent`, un fond
`--hs-danger` impose `--hs-on-danger`, et aucun `#rrggbb` littéral n'apparaît
ailleurs que dans le repli d'un `var()` de la liste ci-dessus.

`--hs-touch` vaut 62 px (contrainte Fire 7), donc au-dessus des 48 px actuels :
les trois formats passent avec une seule valeur.

### 6.2 Les enveloppes

| Enveloppe | Si l'élément HA est défini | Sinon |
|---|---|---|
| `<hs-card>` | rend `<ha-card>` | un `div` aux mêmes jetons |
| `<hs-icon>` | rend `<ha-svg-icon .path>` | un `<svg>` avec le même `path` |
| `<hs-button>` | **toujours notre `<button>`** — voir ci-dessous | idem |

**Pourquoi `ha-button` est écarté.** Vérifié dans HA 2026.8.2 (chunk
`52345.8a897507db31c9f9.js`) : `ha-button` peint son fond sur un élément
`.button` **interne à son shadow DOM**, à partir de variables
`--wa-color-*` / `--button-color-*` pilotées par ses propres attributs
`appearance` et `variant` (défaut `variant = "brand"`). Une classe posée de
l'extérieur ne style que l'hôte, **derrière** ce bouton interne : nos variantes
`primary` / `neutral` / `danger` seraient invisibles dès que HA est chargé — un
bouton « danger » sans rien de dangereux à l'œil.

Deux issues : épouser l'API interne de `ha-button` (`appearance` + `variant`),
ou ne pas l'employer. La première nous lie à un contrat non public, qui vient
déjà de changer une fois (mwc → Web Awesome). La seconde ne coûte rien : notre
`<button>` tire ses couleurs des mêmes jetons HA, donc il a déjà l'air natif, et
son chemin est écrit, testé et correct.

`ha-card` reste, lui : c'est un conteneur qui style son propre `:host` et
accepte le style externe. `ha-svg-icon` reste : il est piloté par un `path` que
nous fournissons.

Le tracé `mdi` vient de `shell/ui/icons.ts` **dans les deux cas** (une quinzaine
de tracés, quelques centaines d'octets) : on ne dépend jamais du chargement de
l'iconset HA.

### 6.3 Pourquoi une enveloppe et pas l'élément HA directement

Vérifié dans `hass_frontend` en HA 2026.8.2 : `ha-card`, `ha-icon`,
`ha-textfield`, `loadCardHelpers` ne sont **pas** dans `app.*.js`. Ils vivent
dans des chunks chargés à la demande. Ils sont donc présents si l'utilisateur a
visité Lovelace, et absents si `/home-stock` est ouvert directement — ce que
fait la tablette cuisine. Un élément inconnu se rend en `display: inline` sans
la moindre erreur en console : l'écran casserait **silencieusement**.

`shell/ui/ha-available.ts` :

1. au démarrage, tente une fois `window.loadCardHelpers?.()` pour forcer le
   chunk Lovelace ;
2. expose `isDefined(nom)` synchrone, lu par les enveloppes au rendu ;
3. s'abonne à `customElements.whenDefined(nom)` et demande un nouveau rendu si
   l'élément arrive après coup.

## 7. Les trois écrans repris

Repris pour un défaut **structurel**, pas cosmétique. Les quatorze autres
héritent des jetons et de la coquille sans être réécrits.

### 7.1 Catalogue sur téléphone

Trois cents produits rendus en une page de 25 949 px de haut. Recherche
collante en tête et fenêtrage : seules les lignes visibles sont rendues. C'est
le seul des trois qui soit aussi un problème de performance.

### 7.2 Scanner

Aucun travail propre : il cesse d'être un écran (§ 4.2) et devient l'action
primaire de la famille Courses. L'écran vide disparaît de lui-même.

### 7.3 Planning

La grille reste bordée (elle l'est déjà, cf. § 3). Les actions par repas
passent en icônes dans la case (`hs-icon`) au lieu de deux boutons texte
empilés : sur sept colonnes × quatre créneaux, cinquante-six boutons texte,
c'est là qu'est le bruit.

## 8. Tests et vérification

### 8.1 Réparer le harnais — préalable

`THEME_CSS` ne définit pas seulement trop peu de variables : il en **invente**
la valeur. Son `--primary-color: #01579b` a été choisi pour passer le seuil de
contraste par construction (le commentaire de la ligne 120 le dit). Le
remplacer par « la bonne » palette recréerait le même mensonge sous un autre
nom, puisque aucun des deux comptes de la maison n'utilise le thème par défaut.

`THEME_CSS` devient donc `themeCss(palette)`, et le harnais connaît **trois
palettes réelles**, relevées dans `hass_frontend` et dans
`config/themes/graphite/` :

| Palette | `--primary-color` | `--text-primary-color` | Blanc sur primaire |
|---|---|---|---|
| `ha-clair` | `#009ac7` | `#ffffff` | 3,26:1 |
| `ha-sombre` | `#009ac7` | `#ffffff` | 3,26:1 |
| `graphite-clair` | `rgb(238,147,0)` | `rgb(19,21,54)` | 7,41:1 |

La suite complète tourne sous `ha-clair`. Un balayage supplémentaire — coquille
plus trois écrans représentatifs — tourne sous les deux autres, pour que ni le
mode sombre ni le thème réellement en service ne soient jamais mesurés.

**Ce changement seul doit faire apparaître des défauts de contraste jusqu'ici
masqués** — à commencer par tout texte blanc posé sur `--primary-color`, qui
tombe à 3,26:1 sous le thème HA par défaut. C'est attendu, et c'est le but : ils
seront traités à mesure, en appliquant la règle 2 du § 6.1. Un harnais réparé
qui ne signalerait rien serait le résultat suspect.

### 8.2 Le rendu de production doit être mesuré

En jsdom comme dans le harnais, aucun `ha-*` n'est défini : les tests
mesureraient **toujours le repli**, jamais le rendu réellement servi. Donc :

- des tests vitest qui enregistrent un faux `ha-card` / `ha-button` /
  `ha-svg-icon` et vérifient que l'enveloppe le préfère, et qu'un élément
  défini **après** le premier rendu déclenche bien un nouveau rendu ;
- dans `verifier-rendu.mjs`, un doublon des scénarios de coquille avec des
  `ha-*` minimaux définis, pour mesurer les deux chemins.

### 8.3 Nouveaux scénarios de rendu

Barre basse (412), rail bureau (1280 et 1920), en-tête avec retour et titre,
en-tête portant la bannière de refus, Catalogue fenêtré sur 412, Planning aux
actions en icônes.

Seuils : cible tactile **62 px**, contraste **4,5:1**, sur le thème réparé.

### 8.4 Non-régression

Les 547 tests vitest existants et les 2 215 tests pytest restent verts. Le
métier n'est pas touché ; les tests d'écran qui interrogent la barre de
navigation par le texte de ses boutons devront être adaptés à la nouvelle
coquille — c'est le seul point de casse attendu, et il est mécanique.

## 9. Contraintes dures

- **Chrome 100** (Fire 7, cuisine) : pas de `dvh`, pas de `:has()`, pas de
  conteneur-queries, pas d'imbrication CSS native.
- **Cibles ≥ 62 px**, contraste ≥ 4,5:1.
- **Aucun geste de navigation** : le retour est un bouton. Une action
  destructive demande deux appuis (armement puis confirmation), comme
  aujourd'hui.
- Le seuil `large` existant (`window.innerWidth >= 1000 && !narrow`,
  `panneau.ts` ligne 325) est réutilisé tel quel pour basculer barre basse ↔
  rail.

## 10. Découpage en lots

1. **Outillage et fondations** — harnais réparé (§ 8.1), `shell/ui/` (jetons,
   enveloppes, icônes, détection), les dix-sept écrans branchés sur les jetons.
2. **Coquille et routes** — `destinations.ts`, `router.ts`, `nav-bar.ts`,
   `header.ts` ; `panneau.ts` réduit à l'orchestration ; les routes d'URL.
3. **Les trois écrans** — Catalogue fenêtré, Scanner absorbé, Planning en
   icônes.

Chaque lot se termine sur `npx vitest run` vert, `node outils/verifier-rendu.mjs`
vert, et `npm run build` (qui déploie).

## 11. Hors périmètre, et pourquoi

- **Les quatorze autres écrans** : ils héritent des jetons et de la coquille.
  Les reprendre un par un est un autre chantier.
- **Les scripts `browser_mod` de la tablette cuisine** et le contrôle C11
  (§ 5.4).
- **La langue de l'interface** : elle reste française. Seuls le nouveau code et
  les routes sont en anglais.
- **Renommer les dix-sept écrans existants** en anglais : gros diff mécanique,
  547 tests à suivre, aucun gain fonctionnel.
- **La performance des flux métier** : écartée explicitement en brainstorming.
