# home_stock — Lot 6 : les quatre surfaces

*Conception validée le 2026-08-21. Domaine HA : `home_stock`. Home Assistant 2026.8.2.*

## 1. Objectif et livrable

Les cinq lots précédents ont construit un garde-manger complet et l'ont rendu
utilisable **dans un seul endroit** : le panneau `home_stock`, une SPA qu'on ouvre
sur le téléphone. Tout y est — le catalogue, le scan, la consommation, le journal,
les recettes, le planning, la liste de courses, les piles — et rien n'en sort.

Le lot 6 fait sortir `home_stock` de son panneau. Il ne construit aucune
fonctionnalité nouvelle : **il porte des fonctions existantes là où la maison les
regarde vraiment.** Trois endroits, et un seul déjà couvert :

- on cuisine **debout, devant la tablette de la cuisine**, les mains sales ;
- on demande **à voix haute** ce qu'il reste et ce qu'on mange ;
- on corrige un catalogue de 299 produits **assis devant un écran de 1280 px**,
  pas au pouce sur un téléphone.

**Livrable vérifiable** (feuille de route du lot 0, § 3) : *« Les quatre surfaces
annoncées. »* Concrètement, à la fin du lot :

1. la tablette de la cuisine affiche le repas suivant, ce qui périme et les courses
   **depuis `home_stock`**, plus une ligne de Grocy ;
2. sept phrases françaises marchent en vocal, dont deux qui écrivent ;
3. le panneau se comporte différemment au-delà de 1000 px sur les écrans qui le
   méritent, et le vérificateur de rendu le prouve dans un troisième format ;
4. la répartition Lovelace / SPA du lot 0 (§ 5.1) est révisée à la lumière de ce
   que six lots ont réellement produit.

Rien de tout cela n'est un « nice to have » : la deuxième raison du remplacement de
Grocy, écrite au lot 0, était *« l'interface est hors de HA : pas d'entités natives,
rien d'utilisable sur les tablettes murales ni dans l'application mobile »*. Tant
que le lot 6 n'est pas fait, `home_stock` est un Grocy mieux modélisé mais aussi mal
placé.

## 2. Périmètre

**Dans le lot :**

- le raccordement de `tools/wallpanel-app` à `home_stock` : bloc central du repas,
  ligne de synthèse, vue « Tâches », vue recette, commandes de la pièce cuisine ;
- le retrait des lectures Grocy de `wallpanel-app` (`src/grocy.ts` et ses appelants) ;
- les intents vocaux, livrés en **blueprint et en paquet `custom_sentences`**, jamais
  installés d'office ;
- les commandes websocket et les services que ces deux surfaces réclament et qui
  n'existent pas encore ;
- l'adaptation « écran large » du panneau, et les formats correspondants dans
  `outils/verifier-rendu.mjs` ;
- la révision de la répartition Lovelace / SPA, et ce qui reste à Lovelace ;
- la documentation d'exploitation des trois nouvelles surfaces.

**Hors du lot :**

- **la reprise des données Grocy et l'extinction du conteneur** — lot 7, sans
  exception. Le lot 6 débranche `wallpanel-app` de Grocy ; il ne touche ni au
  conteneur, ni aux données, ni à `/local/grocy-scanner.html` et
  `/local/grocy-recipes.html`, qui restent servis tant que le lot 7 n'a pas conclu ;
- les six *chores* Grocy (litière, fontaine, croquettes, poubelles), trou de la
  feuille de route repéré au lot 5 (§ 18) et à trancher au lot 7 ;
- toute nouvelle fonction métier. Si une surface réclame une donnée que le composant
  ne sait pas produire, la réponse par défaut est **la surface s'en passe**, pas
  « le composant apprend un calcul de plus ». Deux exceptions justifiées en § 12 ;
- l'application mobile HA et ses notifications : elle affiche déjà les entités et le
  panneau ; rien à écrire.

## 3. Décisions validées

| Sujet | Décision | Raison courte |
|---|---|---|
| Les quatre surfaces | Panneau · Tablettes · Voix · Vue dense PC | § 5 |
| Mode `wallpanel` pour le garde-manger | **Aucun mode nouveau** | Un mode est exclusif et confisque l'écran ; « il faut des courses » n'est pas un moment, c'est un état permanent (§ 8.1) |
| Canal tablette → `home_stock` | **Commandes websocket `home_stock/*` en direct**, via `Connexion.envoyerCommande` | Elles existent, aucune n'exige l'admin, et le mécanisme d'appariement par `id` est déjà écrit et testé (§ 7) |
| Écritures depuis la tablette | Websocket `home_stock/*` aussi, **jamais** un service pour les mêmes gestes | Une seule voie d'écriture par geste ; les services restent la porte du vocal et des automations (§ 7.4) |
| DLC sur la tablette | Ligne de synthèse, **jamais** une alerte plein écran | Le critère d'admission de `alertes.ts` exige « anormal ET traitable en quelques minutes » : une DLC dure des jours (§ 8.3) |
| Bloc central cuisine | Le bloc `repas` existant, réalimenté par `home_stock` | Il existe, il est mesuré, il tient le budget de 585 px (§ 8.2) |
| Liste de courses sur la tablette | `todo.home_stock_shopping` dans `listesTachesExtra`, cochage en deux appuis | Un remplacement de chaîne dans `pieces.ts`, zéro code neuf (§ 8.4) |
| Bloc cuisine au salon et au bureau | **Non**, sauf une ligne de synthèse DLC au salon | Pas de donnée en double *utile* ; le salon n'a pas de placard (§ 8.9) |
| Vocal — mécanisme | `intent_script` en YAML livré, adossé aux services `query_*` existants | Les services à réponse existent depuis les lots 0, 3 et 4 ; l'intent n'est qu'une phrase et un template (§ 9.2) |
| Vocal — écriture | **Deux verbes seulement** : ajouter à la liste, et déclarer un repas planifié mangé | Tout le reste est irréversible ou ambigu à la voix (§ 9.3) |
| Vue dense PC | **Une adaptation du panneau existant**, pas une page séparée | Le panneau porte déjà un état `large` (≥ 1000 px) et un écran « pensé pour le PC » (§ 10.2) |
| Formats du vérificateur | Ajout d'un **1920 × 1080**, les deux existants conservés | Le 1280 × 800 est un portable ; l'écran du bureau ne l'est pas (§ 10.3) |
| Blueprints | Livrés, jamais installés — comme au lot 2 et au lot 2bis | Convention de la maison ; l'utilisateur choisit son heure et son agent |
| Déploiement | `npm run build` de `wallpanel-app` lancé **une seule fois, en dernier** | Ce build écrit dans `config/www/wallpanel/` : c'est un déploiement en production (§ 6) |

## 4. État des lieux, relevé dans le code le 2026-08-21

Ce lot est le premier à travailler dans **deux dépôts**. Un état des lieux exact
n'est donc pas une politesse d'introduction : c'est ce qui évite d'écrire du neuf
là où il n'y a qu'un identifiant à remplacer.

### 4.1 Le panneau existe et couvre tout

`meal/frontend/src/panneau.ts` déclare **dix-sept écrans** : `scanner`, `fiche`,
`panier`, `rangement`, `session`, `catalogue`, `reglages`, `consommation`,
`journal`, `recettes`, `recette`, `planning`, `validation`, `piles`,
`equipements`, `liste`, `ticket`.

Il parle à HA par le websocket **du frontend hôte** (`this.hass.connection`), passe
toutes ses écritures par une file hors-ligne (`file-attente.ts`) qui estampille une
`idempotency_key`, et il porte déjà un état `large` (`window.innerWidth >= 1000`),
utilisé aujourd'hui par le seul écran `planning`. Le docstring de
`ecrans/catalogue.ts` dit en toutes lettres *« Pensé pour le PC — un champ de
recherche, une liste dense, l'édition d'un produit »*. **La quatrième surface n'est
donc pas à inventer : elle est commencée et jamais finie.**

### 4.2 Les tablettes sont déjà une surface de garde-manger — mais celle de Grocy

C'est le fait le plus important de ce lot, et il n'apparaît nulle part dans les
specs des lots 0 à 5. `tools/wallpanel-app` **contient déjà** une surface de
garde-manger complète, câblée sur Grocy :

| Point d'attache | Fichier | Ce qu'il fait aujourd'hui |
|---|---|---|
| `src/grocy.ts` | 8,3 ko | Client HTTP direct vers `http://192.168.0.1:9283` / `https://grocy.allanic.me` : plan de repas, sections, une recette à l'unité, ingrédients + stock |
| `blocDefaut: 'repas'` | `pieces.ts` | Le bloc central de la cuisine : le repas suivant du plan Grocy |
| `rendreRepasSuivant` | `rendu/defaut.ts` | Le rendu de ce bloc, gabarit `.mode-bloc` |
| mode `recette` | `modes.ts` | **Un mode principal à part entière**, prioritaire sur `minuteur`, ajouté le 2026-08-17 pour la cuisson |
| `src/recette.ts`, `rendu/recette.ts` | 4,5 + 34,8 ko | La vue cuisine : découpage en pages `div.page-recipes`, ingrédients, minuteurs `#Nom:secondes` |
| `src/repas.ts` | 7,6 ko | `resoudreRepasSuivant` : quel repas est « le suivant », avec les trois issues `ok` / `absente` / `muette` |
| Commande « Courses » | `pieces.ts` | `entite: 'todo.grocy_shopping_list'` |
| Commande « Recette » | `pieces.ts` | `entite: 'todo.grocy_meal_plan'`, `vue: '#recette'` |
| `extrasMaison` → « Scanner » | `pieces.ts` | Lien vers `/local/grocy-scanner.html` |
| `listesTachesExtra` | `pieces.ts` | `['todo.grocy_shopping_list']` — cochable en deux appuis |
| Consommation | `demarrage.ts` | `cx.appelerService('grocy', 'consume_product_from_stock' \| 'consume_recipe', …)` |

**Le lot 6 est donc majoritairement une migration, pas une création.** Cela change
tout au dimensionnement : la question n'est pas « comment afficher un garde-manger
sur 343 × 585 px » — elle est résolue, mesurée et testée — mais « comment remplacer
la source sans casser un budget de hauteur déjà au millimètre ».

Corollaire désagréable, et il faut le dire ici plutôt que le découvrir en cours de
route : **le lot 6 casse `wallpanel-app` s'il s'arrête à mi-chemin.** Laisser
`src/grocy.ts` et `home_stock` cohabiter donnerait deux plans de repas et deux
listes de courses sur la même dalle — précisément la règle « pas de donnée en
double sur la même tablette » que ce projet applique sans exception.

### 4.3 Le vocal n'a rien du tout

`grep -rn intent custom_components/` ne rend aucune ligne. Zéro `intent_script`,
zéro `custom_sentences`, zéro outil exposé à l'agent conversationnel. Ce qui existe
en revanche, et qui rend l'écriture des intents presque triviale :

| Service | Réponse | Depuis | Répond à |
|---|---|---|---|
| `home_stock.query_stock` | `ONLY` | lot 0 | « Il me reste des œufs ? » |
| `home_stock.query_meals` | `ONLY` | lot 3 | « Qu'est-ce qu'on mange ce soir ? » |
| `home_stock.query_shopping_list` | `ONLY` | lot 4 | « Qu'est-ce qu'il faut acheter ? » |
| `home_stock.add_to_shopping_list` | `OPTIONAL` | lot 4 | « Ajoute du lait à la liste » |
| `home_stock.validate_meal` | `OPTIONAL`, `dry_run: true` par défaut | lot 3 | « J'ai mangé le dîner » |
| `home_stock.maintenance_plan` | `ONLY` | lot 5 | le raccord `maintenance.jinja` |

Le lot 4 avait même écrit (§ 7.4) que `todo.add_item` sur
`todo.home_stock_shopping` fait marcher « Bleuenn, ajoute du beurre à la liste »
**sans une ligne de composant** — c'est vrai, et le § 9.2 explique pourquoi on
écrit quand même un intent par-dessus.

### 4.4 Ce que la maison route déjà vers Bleuenn

`conversation.personas_studio_home_manager` est la cible de **toutes** les alertes
des automations de la maison (`action: conversation.process`), et la valeur par
défaut des deux blueprints déjà livrés : `dlc_bleuenn.yaml` (lot 2, annonce des
dates limites à heure fixe) et `objectifs_bleuenn.yaml` (lot 2bis, dépassements
nutritionnels). Les deux sont **livrés, jamais installés** — convention posée au
lot 2 et reconduite ici sans discussion : le propriétaire choisit son heure et son
agent, et une intégration qui crée des automations dans le dos de son utilisateur
est une intégration qu'on désinstalle.

Ces deux blueprints sont la moitié **sortante** du vocal. Le lot 6 écrit la moitié
**entrante**.

### 4.5 Les entités disponibles, exhaustivement

C'est l'inventaire de ce qu'une surface peut lire sans écrire une ligne de Python.
Toutes portent le préfixe `home_stock_` (`entity.py` force l'`entity_id` en anglais).

| Domaine | Entités |
|---|---|
| `sensor` | `stock_value`, `batches`, `kcal_total`, `cost_total`, `cart_total`, `to_store`, `kcal_today`, `proteins_today`, `carbohydrates_today`, `sugars_today`, `added_sugars_today`, `fat_today`, `saturated_fat_today`, `fiber_today`, `salt_today`, `cost_today`, `cost_waste_total`, `next_meal`, `recipes`, `missing_ingredients`, `batteries_low`, `batteries_undeclared`, `warranty_next`, `shopping_list`, `list_estimate`, `receipts_pending` |
| `binary_sensor` | `expirations`, `shortages`, `nutrition_goals` |
| `todo` | `expirations`, `shopping` |
| `calendar` | `meals` |
| `event` | `expiration` |

Cinq d'entre elles portent dans leurs **attributs** exactement ce dont une tablette
a besoin, sans template Jinja — ce qui compte, parce que `wallpanel-app` parle
websocket et ne sait pas évaluer un template :

- `binary_sensor.home_stock_expirations` → `batches` (la liste complète des lots) ;
- `binary_sensor.home_stock_shortages` → `products` (les noms) ;
- `sensor.home_stock_next_meal` → `day`, `slot`, `recipe_id`, `missing_ingredients`,
  l'état étant le **nom du plat** ;
- `sensor.home_stock_shopping_list` → `items` (id, nom, quantité, rayon, coché),
  `by_origin`, `by_aisle` ;
- `sensor.home_stock_batteries_low` → la liste triée par pourcentage.

Le commentaire de `ShoppingListSensor` le dit déjà : *« Le libellé, la quantité et
l'état de chaque ligne : de quoi écrire une automation ou une annonce vocale sans
repasser par le websocket. »* Le lot 6 encaisse cette prévoyance.

## 5. Les quatre surfaces

Le lot 0 promettait « quatre surfaces » sans jamais les nommer. Elles le sont ici,
et chacune est définie autant par ce qu'elle **refuse** d'afficher que par ce
qu'elle montre. Une surface qui essaie de tout montrer est un cinquième panneau.

### 5.1 Le panneau — *« je manipule »*

**Support** : téléphone en main (412 × 915), et désormais l'écran du bureau (§ 10).
**État** : livré aux lots 1 à 5 ; le lot 6 ne le refait pas, il l'élargit.

Il montre **tout** : le scan, la fiche article, le rangement, le catalogue dense et
son édition, la saisie « 200 g pris sur ce lot », le journal et la correction d'un
mouvement, la session de courses, le panier, le ticket, les recettes, le planning, la
validation, les piles, les équipements. C'est la surface complète, par construction —
sa colonne « ne montre pas » est vide.

**Règle de démarcation** : tout geste qui a besoin d'un *choix* (quel lot, quelle
quantité, quel prix, quelle DLC) vit ici et **seulement** ici. Les trois autres
surfaces n'ont le droit de porter qu'un geste dont la réponse est déjà connue.

### 5.2 Les tablettes murales — *« je regarde en passant, j'agis d'un doigt »*

**Support** : Fire 7 sous Fully Kiosk, cadre 343 × 585 px, Chrome 100, doigt sale.
**État** : à raccorder. Détail complet au § 8.

| Montre | Ne montre pas | Pourquoi pas |
|---|---|---|
| Le repas suivant du planning (bloc central) | Le planning de la semaine | Sept jours ne tiennent pas ; le panneau et `calendar.home_stock_meals` sont là pour ça |
| Ce qui périme (ligne de synthèse, compte) | Le détail lot par lot, les DLC | Une ligne fait 1 texte ; le détail se coche dans la vue « Tâches » |
| La liste de courses, cochable (vue « Tâches ») | Les prix, l'estimation du panier | On ne fait pas ses courses depuis sa cuisine |
| La recette en cours, étape par étape (vue `#recette`) | Le catalogue, la fiche d'un produit | Aucune saisie de quantité sur une dalle qu'on touche avec un doigt de farine |
| Le nombre de piles faibles (ligne, si utile) | Le journal, les kcal, les € | Une comptabilité se lit assis (§ 8.8) |

### 5.3 La voix — *« j'ai les mains prises »*

**Support** : Bleuenn, `conversation.personas_studio_home_manager`, enceintes Google
de la cuisine, du salon, de la chambre et de la salle de bain.
**État** : à écrire. Détail au § 9.

| Répond | Refuse | Pourquoi |
|---|---|---|
| « Il me reste des œufs ? » | « Combien j'ai dépensé ce mois-ci ? » | Un nombre à quatre décimales ne s'écoute pas ; c'est un graphe |
| « Qu'est-ce qu'on mange ce soir ? » | « Range le lait au frigo » | Une entrée en stock demande cinq informations (article, quantité, prix, emplacement, DLC) |
| « Qu'est-ce qu'il faut acheter ? » | « Jette le yaourt » | Un `waste` est irréversible et se reconnaît mal à l'oreille |
| « Ajoute du lait à la liste » | « Enlève le lait de la liste » | Voir § 9.3 : la suppression vocale est refusée, pas oubliée |
| « J'ai mangé le dîner » | « J'ai mangé 180 g de gratin » | Le premier vise un repas planifié et connu ; le second est une saisie |

### 5.4 La vue dense PC — *« je répare »*

**Support** : le panneau, au-delà de 1000 px de large, sur l'écran du bureau.
**État** : commencé (état `large`, écran catalogue), à finir. Détail au § 10.

| Apporte | N'apporte pas |
|---|---|
| Des tableaux à plusieurs colonnes là où le téléphone empile | Un écran de plus : ce sont **les mêmes** écrans, en plus large |
| Le catalogue complet et l'édition en série | Une seconde application, un second bundle, un second vérificateur |
| Le journal sur douze mois et la correction d'un mouvement | Une fonction que le téléphone n'aurait pas |
| Les réglages : rayons, emplacements, magasins, objectifs | — |

**Ce qui les sépare tient en une phrase.** Le panneau *manipule*, les tablettes
*rappellent*, la voix *répond*, la vue dense *répare*. Une donnée qui apparaît sur
deux surfaces doit y répondre à deux verbes différents ; sinon c'est un doublon,
et il faut en retirer une.

## 6. Deux dépôts, une seule maison

C'est la contrainte structurante du lot, et elle n'existait dans aucun lot
précédent. `tools/wallpanel-app` **n'est pas dans le dépôt `meal`** : il vit dans
`/opt/nivuus/HomeAssistant/data/tools/wallpanel-app`, avec son propre `.git`, son
propre `package.json`, sa propre suite de tests et son propre vérificateur de rendu.

### 6.1 Qui change quoi

| Dépôt | Fichiers touchés | Nature |
|---|---|---|
| `meal` (Python) | `custom_components/home_stock/websocket_api.py`, `services.py`, `services.yaml`, `translations/fr.json`, `const.py` | Les commandes et services manquants (§ 12) |
| `meal` (front) | `frontend/src/panneau.ts`, `frontend/src/ecrans/*.ts`, `frontend/outils/verifier-rendu.mjs` | La vue dense (§ 10) |
| `meal` (livraison) | `blueprints/automation/home_stock/*.yaml`, `custom_sentences/fr/home_stock.yaml`, `docs/exploitation.md` | Le vocal (§ 9) et son mode d'emploi |
| `wallpanel-app` | `src/pieces.ts`, `src/modes.ts`, `src/demarrage.ts`, `src/cochage.ts`, `src/repas.ts`, `src/recette.ts`, `src/rendu/defaut.ts`, `src/rendu/recette.ts`, `src/connexion.ts` | Le raccordement (§ 8) |
| `wallpanel-app` | `src/grocy.ts` → **supprimé**, remplacé par `src/garde-manger.ts` | La bascule de source |
| `wallpanel-app` | `tests/*.test.ts` | La preuve |

**Deux commits, deux dépôts, deux historiques.** Aucun mécanisme ne les lie : rien
ne garantit qu'un `git bisect` dans `meal` retrouve l'état correspondant de
`wallpanel-app`. La seule protection possible est **l'ordre** (§ 6.3) et le fait que
la partie `meal` soit, à chaque étape, **rétro-compatible** : toute commande
websocket ajoutée au composant doit fonctionner avec l'ancien bundle de tablette
déployé, qui ne l'appelle simplement pas.

### 6.2 `npm run build` de `wallpanel-app` **déploie en production**

```json
"build": "npm run jetons && rollup -c && node scripts/versionner.mjs"
```

`rollup -c` écrit dans `config/www/wallpanel/` — le dossier que Home Assistant sert
aux trois tablettes — et `versionner.mjs` incrémente le `?v=` des trois pages HTML.
**Il n'y a aucune étape de validation entre ce build et les trois écrans de la
maison.** C'est la règle que `docs/exploitation.md` porte déjà pour le panneau
(« un build est un déploiement »), et elle vaut ici **en pire** : le panneau se
recharge quand on ouvre la page, la tablette de la cuisine tourne 24 h sur 24 et
sert d'horloge.

> `npm run build` de `wallpanel-app` est lancé **une seule fois, à la toute fin du
> lot**, après que tout le reste est vert. Jamais « pour voir ». Jamais deux fois.

La tâche qui le lance est donc **la dernière du plan**, elle ne fait que ça, et elle
est suivie du seul geste de contrôle autorisé :
`button.tablette_<piece>_vider_le_cache_du_navigateur`, puis
`button.tablette_<piece>_load_start_url`, puis lecture de
`image.tablette_<piece>_capture_d_ecran`.

### 6.3 `verifier-rendu.mjs` **ne déploie pas** — c'est là que tout se vérifie

```
node outils/verifier-rendu.mjs            # construit le bundle EN MÉMOIRE depuis src/
node outils/verifier-rendu.mjs --deploye  # mesure le bundle réellement en place
```

Il construit en mémoire depuis `src/` et ouvre les pages dans un Chromium au format
exact de la dalle ; il échoue sur débordement du cadre 343 × 585, cible tactile sous
62 px, contraste sous 5:1, texte tronqué. **C'est le seul outil du lot capable de
dire « ça tient » sans rien mettre en production**, donc c'est là que se joue toute
la mise au point du § 8.

Deux mesureurs l'accompagnent et ne déploient pas non plus : `mesurer-salve.mjs`
(coût des douze premières secondes) et `mesurer-rendus.mjs` (régime établi). Ils ne
sont pas décoratifs : avant la coalescence des redessins, ce projet mesurait **1712
recalculs de style à chaque connexion websocket**, de quoi faire tuer Fully par
Android sur une page qui *rendait juste*. **Obligation du lot** : les deux sont
exécutés sur la cuisine avant le build final, et leurs chiffres comparés à ceux
d'avant le lot.

### 6.4 L'ordre imposé

1. `meal` : commandes websocket, services, entités — avec leurs tests Python.
2. `meal` : vue dense + `verifier-rendu.mjs` (formats ajoutés), tests front.
3. `meal` : `npm run build` du panneau (déploie le bundle du composant — règle du
   lot 1, une fois, en fin de la partie `meal`).
4. `wallpanel-app` : `src/`, `npm test`, `node outils/verifier-rendu.mjs`, les deux
   `mesurer-*`. **Aucun build.**
5. `meal` : blueprints et `custom_sentences`, documentation.
6. `wallpanel-app` : `npm run build` — **une fois**, puis cache + capture d'écran.

L'étape 1 précède l'étape 4 pour une raison mécanique : le vérificateur de
`wallpanel-app` ouvre les pages **contre l'instance Home Assistant réelle** de la
maison, avec une session issue du jeton de `data/.mcp.json`. Si les commandes
websocket n'existent pas encore côté composant, il mesure un écran vide et déclare
que tout va bien.

> **Interdits du lot, repris du lot 1 et jamais assouplis :** aucun
> `docker compose`, aucun redémarrage, aucun rechargement de l'intégration, aucune
> écriture dans `/opt/nivuus/HomeAssistant/config/` autre que celle du build final
> de `wallpanel-app`, aucune modification de Grocy (lecture seule jusqu'au lot 7).

## 7. Le canal : par où la tablette parle à `home_stock`

C'est **la** question technique du lot. La réponse est courte et elle est bonne :
**les commandes websocket `home_stock/*` sont utilisables telles quelles depuis
`wallpanel-app`.** Voici pourquoi, point par point, parce que trois choses devaient
être vraies en même temps et le sont.

### 7.1 La connexion est une vraie session Home Assistant

`wallpanel-app/src/connexion.ts` lit `hassTokens` dans le `localStorage` — la page
est servie par HA sur la même origine (`/local/wallpanel/cuisine.html`), donc elle
partage le stockage du frontend — puis ouvre `/api/websocket` et s'authentifie avec
ce jeton, celui d'un **utilisateur Home Assistant authentifié**. Elle le rafraîchit
toutes les 25 minutes (`doitRafraichir`, marge de 5 min sur 30), parce qu'un écran
mural qui ne le fait pas meurt en silence au bout d'une demi-heure.

Conséquence : **une commande `home_stock/*` envoyée depuis la tablette arrive au
serveur exactement comme si elle venait du panneau.** Même transport, même
authentification, même `connection.user`.

### 7.2 Aucune commande `home_stock` n'exige l'administrateur

Vérifié sur les quatre fichiers de commandes (`websocket_api.py`,
`websocket_recipes.py`, `websocket_receipts.py`, `websocket_batteries.py`) : **zéro
occurrence de `@websocket_api.require_admin`.** Toutes sont enregistrées en
`@websocket_api.websocket_command` + `@websocket_api.async_response` (ou `@callback`
pour `subscribe`), donc accessibles à tout utilisateur authentifié.

Ce n'est pas un oubli : `docs/exploitation.md` porte depuis le lot 1 une section
« Qui peut écrire dans le journal : tout utilisateur authentifié », et l'en-tête de
`websocket_api.py` dit *« The panel reuses the Home Assistant connection, so there
is no separate authentication »*. L'installation n'a d'ailleurs qu'une personne
(`person.maxime_allanic`). **Le lot 6 hérite de ce choix, il ne le rouvre pas** —
mais il l'inscrit noir sur blanc, parce que ce choix vient de rendre la surface
tablette possible sans une ligne de code serveur.

### 7.3 Le mécanisme d'appariement existe déjà, écrit et testé

`Connexion.envoyerCommande` (tâche 14 de `wallpanel-app`) :

```ts
envoyerCommande(payload: Record<string, unknown>): Promise<unknown> {
  return new Promise((resolve, reject) => {
    if (!this.ws) { reject(new Error('websocket indisponible')); return; }
    const id = this.id++;
    this.enAttenteCommandes.set(id, { resolve, reject });
    this.ws.send(JSON.stringify({ id, ...payload }));
  });
}
```

C'est **une commande websocket arbitraire, appariée par `id`**. Elle a été écrite
pour `todo/item/list` et elle accepte n'importe quel `type`. Le `onmessage` vérifie
`enAttenteCommandes` **en premier**, avant le traitement générique
`type === 'result' && Array.isArray(m.result)` qui sert à `get_states` — les deux
mécanismes sont mutuellement exclusifs, la docstring le démontre déjà.

Autrement dit : `home_stock/list/items`, `home_stock/journal/day`,
`home_stock/meals/list` ou `home_stock/stock/consume` sont **envoyables aujourd'hui,
sans modifier `connexion.ts`**. Le lot 6 n'ajoute à ce fichier qu'une chose (§ 7.6).

### 7.4 La règle de partage : websocket pour ce qui est riche, entités pour ce qui est simple

Le fait que tout soit possible ne veut pas dire que tout doit passer par le même
tuyau. Trois voies existent, et chacune a un domaine :

| Voie | Quand | Exemples dans ce lot |
|---|---|---|
| **État d'entité** (`get_states` + `subscribe_events`, déjà en place) | La donnée tient dans un état ou un attribut, et la tablette la relit à chaque changement gratuitement | `sensor.home_stock_next_meal` et ses attributs, `binary_sensor.home_stock_expirations.batches`, `sensor.home_stock_shopping_list.items`, `sensor.home_stock_batteries_low` |
| **Commande websocket `home_stock/*`** | La donnée est structurée, volumineuse ou paramétrée ; ou l'écriture demande plus d'un bit | `home_stock/recipe/get`, `home_stock/meal/preview`, `home_stock/meal/validate`, `home_stock/stock/consume` |
| **Service HA** (`call_service`) | Le geste est déjà exprimé par une entité standard, ou vient d'une automation / du vocal | `todo.update_item` sur `todo.home_stock_shopping` |

**Décision : la tablette lit d'abord les états, écrit par websocket `home_stock/*`.**

Lire par état plutôt que par commande n'est pas de l'élégance, c'est de l'économie.
`Etat.notifier` coalesce déjà les redessins ; une souscription `state_changed`
existe depuis le premier jour ; ajouter une lecture périodique
`home_stock/list/items` toutes les 15 minutes reproduirait exactement le défaut que
`src/grocy.ts` a mis trois mois à corriger (3,8 Mo × 96 par jour sur une dalle à
130 Mo de libre). **La donnée qui tient dans un attribut se lit dans l'attribut.**

Écrire par websocket plutôt que par service tient à un point précis : les commandes
`home_stock/*` **répondent**. `home_stock/list/check` renvoie la vue de liste
complète après le cochage ; `home_stock/meal/validate` renvoie ce qui a été
décrémenté. Un `call_service` de `wallpanel-app` (`appelerService`) est **un envoi
sans réponse** : il ne sait pas si le serveur a refusé. Sur un écran où l'on coche
en deux appuis et où l'on retire la ligne de façon optimiste, savoir que l'écriture
a échoué n'est pas un luxe.

L'exception assumée est `todo.update_item` : voir § 8.4.

### 7.5 Ce qui n'a **pas** été retenu, et pourquoi

| Piste | Rejetée parce que |
|---|---|
| Un client HTTP direct vers l'API REST de `home_stock` | Il n'y en a pas, et il n'en faut pas : `home_stock` n'expose aucune vue HTTP. C'est précisément ce qui a rendu `src/grocy.ts` fragile (contenu mixte HTTP/HTTPS, deux bases d'URL selon le protocole, aucun `ETag`) |
| Des capteurs template dans `config/custom_templates/` pour pré-mâcher les données | `wallpanel.jinja` est **périmé** (CLAUDE.md) et n'alimente plus que des capteurs inutilisés. Recréer un template pour la tablette serait ressusciter une couche morte, et ajouter un troisième endroit où une règle métier vit |
| Une carte Lovelace `todo-list` sur un dashboard `wallpanel_cuisine` | Les dashboards `.storage/lovelace.wallpanel_*` sont **périmés** : les modifier n'a **aucun effet** sur les tablettes. Le lot 4 (§ 18) écrivait « la tablette de la cuisine affiche la liste avec la carte `todo-list` native » — **c'est faux, et ce lot corrige l'erreur** (§ 11.3) |
| Exposer les commandes `home_stock/*` en `require_admin` pour la sûreté | Ce serait casser la tablette pour un gain nul sur une installation à un utilisateur, et rompre avec le choix documenté du lot 1 |
| Un second `Connexion` propre au garde-manger | Une deuxième socket sur une Fire 7, avec sa propre reconnexion et son propre `setInterval` : exactement le garde-fou anti-fuite (`silenceArme`) que ce fichier a dû ajouter après coup |

### 7.6 La souscription : pas au lot 6

`home_stock/subscribe` répond une fois puis **pousse un événement à chaque
rafraîchissement du coordinateur**. `envoyerCommande` résout sa promesse au premier
`result` et **oublie l'`id`** : les événements suivants ne seraient vus par personne.
Le supporter demanderait un `souscrire(payload, rappel)` dans `connexion.ts`.

**Décision : pas de souscription.** Le § 8 démontre que les données affichées par la
tablette vivent toutes dans un état ou un attribut d'entité, donc arrivent déjà par
`subscribe_events` — sans une ligne de plus dans `connexion.ts`, sans seconde source
de vérité, et sans le risque mesuré au § 6.3. `home_stock/subscribe` reste ce qu'il
est : la voie du panneau, qui affiche bien plus. **La tablette est un client de plus,
pas un client privilégié** — si elle réclame un mécanisme que le panneau n'a pas,
c'est en général qu'elle affiche quelque chose qu'elle ne devrait pas.

## 8. Le bloc cuisine dans `wallpanel-app`

### 8.1 Pas de mode de plus — et c'est la décision la plus importante de la section

`src/modes.ts` définit un **mode principal exclusif** (`alerte`, `recette`,
`minuteur`, `menage`, `cinema`, `media`, `aeration`, `voiture`, `defaut`). Un mode
occupe le bloc central **et fixe le nombre de commandes affichées** (`combien()` :
0 pour `minuteur`, 2 pour `media`/`cinema`/`voiture`, 4 sinon). Un mode de plus n'est
donc pas une ligne d'énumération : c'est une place de plus dans une file de priorité,
et une chance de plus qu'un autre mode ne s'affiche jamais.

**Décision : le garde-manger n'obtient aucun mode principal nouveau.** Trois raisons.

**1. Un mode répond à un moment, pas à un état.** Tous les modes existants ont une
fin naturelle : le minuteur sonne, l'aspirateur s'arrête, la musique se termine, la
fenêtre se referme. « Il y a trois choses à acheter » n'a pas de fin — c'est l'état
ordinaire d'une maison, et un tel mode mangerait le bloc central de la cuisine pour
toujours. Le même argument a déjà été tranché dans `alertes.ts`, où la fenêtre
ouverte a été **retirée** du rang d'alerte parce qu'elle « peut durer des heures ».

**2. Le mode qu'il fallait existe déjà.** `recette` a été ajouté le 2026-08-17,
prioritaire sur `minuteur` (« pendant une cuisson, l'écran doit pouvoir ramener à
l'étape en cours »). C'est exactement le moment du garde-manger qui mérite le bloc
central : le lot 6 **réalimente ce mode** au lieu d'en créer un deuxième à côté.

**3. Le bloc par défaut existe aussi.** `blocDefaut: 'repas'` rend
`rendreRepasSuivant` dans le gabarit standard sans coûter une commande — mesuré
(500 → 574 px, tâche 19).

| Élément | Type | Nouveau ? |
|---|---|---|
| Repas suivant | bloc par défaut (`blocDefaut: 'repas'`) | non — resourcé |
| Recette en cours | mode `recette` existant | non — resourcé |
| DLC | ligne de synthèse | oui, une entrée de **données** |
| Liste de courses | vue « Tâches » (`listesTachesExtra`) | non — resourcé |
| Ruptures, piles faibles, compta | rien (§ 8.8) | — |

**Zéro ligne ajoutée à `modes.ts`** : `recetteEnCours` est un booléen qui ne dit pas
d'où vient la recette.

### 8.2 Le bloc central : le repas suivant, lu dans un attribut

Aujourd'hui, `demarrage.ts` charge le plan Grocy toutes les 15 minutes, résout « le
repas suivant » (`resoudreRepasSuivant`, `src/repas.ts`, avec ses trois issues
`ok` / `absente` / `muette`), lit la recette à l'unité et rend `rendreRepasSuivant`.
Après le lot 6, **tout ce calcul disparaît côté tablette** : `home_stock` l'a déjà
fait et l'a publié.

| Ce que la tablette affiche | Source |
|---|---|
| Le plat | `sensor.home_stock_next_meal` — l'**état** est `recipe_name or product_name or note` |
| L'étiquette (« Dîner », « Demain midi ») | attributs `day` + `slot` |
| Ouvrable en vue `#recette` ? | attribut `recipe_id` non nul |
| Un avertissement discret | attribut `missing_ingredients` |

Le gain est mesurable : **−3,8 Mo/jour** de trafic HTTP (l'ancienne lecture du plan
Grocy), **−1 client HTTP** (`src/grocy.ts`, 8,3 ko, et ses deux bases d'URL selon le
protocole), et **−1 chemin de panne** — « Grocy muet » et sa règle « surtout ne pas
passer au repas suivant » disparaissent, remplacés par `Etat.estUtilisable`, le
mécanisme de masquage générique déjà en place pour toute entité `unavailable`.

`src/repas.ts` survit sous forme réduite : le choix de l'étiquette reste une
décision d'affichage. Ce qui meurt, c'est le parcours du plan.

**Le repli reste en place.** `rendreEntretien` (tâche 17) remplace le bloc repas par
les tâches d'entretien quand aucun repas n'est planifié — 185 px de fond nu mesurés
sur la capture de 21 h 07, parce qu'« un plan de repas vide est l'état ORDINAIRE de
cette installation ». `home_stock` ne le remplira pas par magie, et `masquerEntretien`
continue de retirer la ligne de synthèse correspondante pour ne pas afficher deux
fois le même compte.

### 8.3 La ligne de synthèse : une seule, et pas une alerte

`EntreeSynthese` porte sa propre condition. Une seule entrée est ajoutée à la cuisine
(et une au salon, § 8.9) :

```ts
{ entite: 'todo.home_stock_expirations', operateur: '>', valeur: 0,
  texte: '{etat} produit{s} à consommer', perso: true },
```

**Pourquoi `todo.` et pas `binary_sensor.`.** L'état d'une entité `todo` est le
**nombre d'éléments non cochés** ; `binary_sensor.home_stock_expirations` ne vaut que
`on`/`off` et ne pourrait produire qu'un texte sans compte — or le compte est ce
qu'on lit de loin. Bonus mécanique décisif : `listesTachesPiece` (`cochage.ts`)
collecte **automatiquement** toute entrée de `synthese` dont l'entité commence par
`todo.` Déclarer cette ligne suffit donc à faire apparaître les lots qui périment
**dans la vue « Tâches », cochables en deux appuis**, sans une ligne de plus. Et
cocher y veut dire **mangé** (`consume_batch`), ce qui est le geste juste devant un
frigo.

**Pourquoi pas une alerte.** `alertes.ts` pose un critère d'admission cumulatif :
*anormale* **et** *traitable en quelques minutes depuis la maison*. Une DLC échoue aux
deux. Le fichier raconte ce que coûte l'erreur : la batterie de la e208 a
« confisqué les trois écrans une journée entière » pour avoir enfreint le second
critère. **Le garde-manger ne produit aucune alerte plein écran.**

**Pourquoi une seule.** La cuisine a déjà quatre entrées de synthèse et la ligne n'en
affiche qu'un nombre borné. Une sixième ferait tomber l'une des existantes selon
l'ordre de déclaration — une information qui disparaît en silence, le pire des
comportements.

### 8.4 La liste de courses : `listesTachesExtra`, et rien d'autre

Un remplacement de chaîne :

```ts
listesTachesExtra: ['todo.home_stock_shopping'],   // était todo.grocy_shopping_list
```

plus une entrée dans la table de libellés de `cochage.ts` :

```ts
const LIBELLES_LISTE: Record<string, string> = {
  'todo.maintenance': 'Entretien',
  'todo.travail': 'Travail',
  'todo.home_stock_shopping': 'Courses',
};
```

C'est **tout**. Le raisonnement de l'arbitrage d'origine tient mot pour mot pour
`home_stock` : la liste de courses n'est pas un écart à signaler (donc pas dans
`synthese`), mais elle se coche naturellement (donc dans la vue « Tâches »). Le
planning, lui, reste consultable par la commande « Recette » et n'est pas une liste
d'actions discrètes ; les piles ne se cochent pas.

**Comment le cochage écrit.** `cochage.ts` arme, `rendu/taches.ts` confirme au second
appui, et `demarrage.ts` appelle aujourd'hui `todo.update_item`. **Décision : on
garde `todo.update_item`**, seule exception à la règle du § 7.4, pour trois raisons :

1. c'est déjà écrit, testé (`tests/cochage.test.ts`, `tests/taches.test.ts`) et
   partagé avec `todo.maintenance` et `todo.travail` — deux listes qui ne sont pas
   `home_stock` et ne le seront jamais ;
2. `ShoppingTodoList.async_update_todo_item` fait exactement la bonne chose : cocher
   vaut « je l'ai », jamais « c'est en stock » (lot 4, § 7.5), et un `uid` périmé
   est un no-op explicite, pas une erreur ;
3. écrire un chemin `home_stock/list/check` en parallèle donnerait **deux façons de
   cocher la même ligne** sur la même dalle, avec deux traitements d'erreur.

La lecture, elle, reste `Connexion.listerTaches` (`todo/item/list`), commande
standard qui marche déjà sur `todo.home_stock_shopping` sans une ligne de plus.

### 8.5 Les commandes de la pièce cuisine

Quatre aujourd'hui, quatre demain. **Aucune rangée ajoutée** : la cuisine est à
574 px sur un budget de 585.

| Libellé | Avant | Après |
|---|---|---|
| Courses | `todo.grocy_shopping_list`, tuile informative | `todo.home_stock_shopping`, **`vue: '#taches'`** |
| Recette | `todo.grocy_meal_plan`, `vue: '#recette'` | `sensor.home_stock_next_meal`, `vue: '#recette'` |
| Aspirer ici · Purificateur | inchangés | inchangés |

Les deux entités changées gardent leur rôle d'**indicateur de disponibilité** :
muettes, elles font masquer la tuile par le filtre générique de `rendu/corps.ts`.
L'ajout de `vue: '#taches'` est le seul enrichissement fonctionnel — aujourd'hui la
tuile affiche un compte sur lequel on ne peut rien faire, et la vue « Tâches » ne
s'atteint qu'en touchant la ligne de synthèse. Ça ne coûte rien (navigation interne,
jamais un appel HA) et ça supprime un cul-de-sac.

**`extrasMaison`** : « Scanner » pointe vers `/local/grocy-scanner.html` et devient
un lien vers `/home-stock` (le panneau s'ouvre sur son écran `scanner`). Deux
réserves, à trancher à la mesure plutôt qu'ici : le panneau est pensé pour
412 × 915 et sera à l'étroit sur 343 px — acceptable pour un lien de secours, c'était
déjà le statut du scanner Grocy, et **le panneau ne devient pas une surface
tablette** ; et la caméra d'une Fire 7 lit mal un code-barres. Si la mesure le
confirme, ce bouton **disparaît** plutôt que de promettre un scan qui échoue.

### 8.6 La vue `#recette` : de Grocy à `home_stock`

C'est le plus gros morceau de code du raccordement (`src/recette.ts` 4,5 ko,
`src/rendu/recette.ts` 34,8 ko, `tests/rendu-recette.test.ts` 33,6 ko).

Aujourd'hui, `decouperPages` découpe la **description HTML** d'une recette Grocy en
pages `div.page-recipes` — une convention imposée à la main sur les 87 recettes de
l'installation — avec des minuteurs encodés `#Nom:secondes` dans le texte.
`home_stock` a un **modèle structuré** : `home_stock/recipe/get` rend la recette,
ses étapes et ses ingrédients déjà appariés au catalogue.

| Décision | Choix | Raison |
|---|---|---|
| Source | `home_stock/recipe/get` par `envoyerCommande`, à l'ouverture de la vue | Lecture ponctuelle, jamais périodique — la leçon de `src/grocy.ts` |
| Ingrédients et stock | Dans la même réponse | Un aller-retour au lieu de quatre (`recipes_pos`, `products`, `quantity_units`, `stock`) |
| Découpage en pages | **Conservé**, alimenté par les étapes structurées | Le rendu tient le budget de hauteur et il est testé ; seule son **entrée** change |
| Minuteurs `#Nom:secondes` | **Conservés** | Ils vivent dans le texte de l'étape, le mécanisme marche |
| « Terminer » | `home_stock/meal/validate` | § 8.7 |

**Ce qui disparaît** : `cx.appelerService('grocy', 'consume_product_from_stock', …)`
et `cx.appelerService('grocy', 'consume_recipe', …)` (`demarrage.ts`, l. 968 et 980).

Si `recipe/get` ne rend pas les étapes sous une forme directement utilisable par
`decouperPages`, **c'est la tablette qui s'adapte**. Le lot 6 n'ajoute aucune
commande websocket dont le seul but serait de pré-mâcher un rendu.

### 8.7 Agir depuis la tablette : trois gestes, deux appuis chacun

`cochage.ts` pose la règle : jamais d'appui long, toute action destructive s'arme puis
se confirme, **un seul emplacement armé à la fois**.

| Geste | Où | Écriture |
|---|---|---|
| Cocher une ligne de courses | vue « Tâches » | `todo.update_item` (§ 8.4) |
| Cocher un lot qui périme = « mangé » | vue « Tâches » | `todo.update_item` → `consume_batch`, gratuitement |
| « Terminer » le repas en cours | vue `#recette` | `home_stock/meal/validate` |

**Trois gestes, pas quatre.** Sont explicitement refusés : *déclarer un repas hors
planning* (il faut choisir un produit et une quantité — c'est l'écran « manger » du
panneau) ; *jeter* (`reason: waste` — irréversible, et un doigt qui glisse coûte une
contrepassation) ; *ajouter une ligne de courses* (pas de clavier ; c'est le rôle du
vocal et du panneau).

**`meal/validate` n'est pas réversible, et l'écran doit le dire.** Le lot 3 l'écrit :
*« Cook, then eat. Not reversible at lot 3, and the screen says so. »* Le lot 4 a
ajouté `meal/correct`, mais depuis le journal du panneau, pas au mur. Le second appui
porte donc un libellé explicite, pas un « Toucher pour confirmer » générique :
**« Terminer — le stock sera décrémenté »**. Trois défenses en profondeur, toutes
déjà écrites : `home_stock/meal/preview` **n'écrit rien** et rend le plan de
décrément à l'armement ; `envoyerCommande` rend une promesse, donc un refus
(`InsufficientStock`) est traduit en français par `messages.py` et affichable ; et le
garde `estHorsLigne` s'applique comme à toute autre écriture.

**Décision sur le hors-ligne : la tablette n'a pas de file.** Le panneau en a une
parce qu'on scanne dans un magasin sans réseau ; une tablette murale est à trois
mètres du routeur, qui est le serveur HA. Un geste refusé hors ligne est **refusé
visiblement**, jamais mis en attente : rejouer une validation de repas une heure plus
tard, sans témoin, décrémenterait un stock à l'aveugle. Les commandes portent quand
même une `idempotency_key` — toutes l'acceptent — parce qu'une reconnexion websocket
peut faire douter d'un envoi.

### 8.8 Ce qui n'est **pas** sur la tablette, et pourquoi

| Donnée | Raison du refus |
|---|---|
| Les ruptures (`binary_sensor.home_stock_shortages`) | Une rupture alimente déjà la liste de courses (lot 4, § 7.1) : l'afficher **et** afficher la liste, c'est la même information deux fois sur la même dalle |
| Les kcal et les € du jour | Une comptabilité se lit assise et se compare. `kcal_today` monte toute la journée : l'écran mentirait à midi |
| Les objectifs nutritionnels dépassés | Déjà annoncés par Bleuenn. Un dépassement au mur, à l'heure du dîner, est un reproche |
| Le planning de la semaine | Sept jours ne tiennent pas dans 343 px sans passer sous 62 px de cible |
| L'estimation du panier, les tickets à traiter | On ne fait pas ses courses depuis sa cuisine ; un ticket se rapproche sur écran large |
| Les piles faibles | **Changement d'avis assumé** : le lot 5 (§ 17) suggérait une ligne « n piles faibles » *si elle se révèle utile*. Elle ne l'est pas — `todo.maintenance` contient déjà les piles à changer et la ligne « {n} tâches d'entretien » les compte sur les trois tablettes |
| Les équipements et les garanties | Une fin de garantie se traite avec une facture sous les yeux |

Cette colonne est plus longue que celle de ce qui s'affiche, et c'est normal : sur
343 × 585 px, la conception consiste à refuser.

### 8.9 Par pièce : la cuisine oui, le salon un peu, le bureau non

| Pièce | Bloc repas | Ligne DLC | Liste de courses | Vue recette |
|---|---|---|---|---|
| **Cuisine** | oui (resourcé) | **oui** | oui (vue « Tâches ») | oui (resourcé) |
| **Salon** | non | **oui** | non | non |
| **Bureau** | non | non | non | non |

**Cuisine** : c'est là qu'on cuisine, qu'on ouvre le frigo et qu'on écrit la liste.

**Salon** : la tablette du salon est à l'entrée — c'est pour ça que « Porte » y est
épinglée. Une ligne « 3 produits à consommer » y est utile au moment précis où on part
faire les courses ou où on rentre. C'est **une ligne, sur une autre tablette** : la
règle « pas de donnée en double » s'applique *par tablette*, et la répétition entre
tablettes est explicitement permise. Rien d'autre n'y va : le salon n'a ni placard ni
plaque, et sa vue « Tâches » n'a pas à porter une liste qu'on ne coche pas d'un canapé.

**Bureau** : rien. Le garde-manger n'a aucun geste à y offrir. C'est le refus le plus
facile du lot, et il faut le noter comme tel : un lot « surfaces » a une pente
naturelle vers « mettons-le partout ».

### 8.10 Le budget de hauteur, chiffré

La contrainte est dure : **343 × 585 px, marge nulle, la hauteur totale ne bouge pas
selon qu'une alerte ou un média est actif — on remplace un bloc, on n'en ajoute
jamais un.**

| Élément | Effet sur la hauteur | Pourquoi |
|---|---|---|
| Bloc repas resourcé | **0** | Même gabarit `.mode-bloc`, même `.v.deux-lignes` |
| Ligne de synthèse DLC | **0** | La ligne existe ; un texte de plus dans sa rotation |
| `listesTachesExtra` | **0** sur l'accueil | Vue « Tâches », budget propre : 6×64 + 5×8 + 112 = 536 ≤ 585 |
| Commandes de la pièce | **0** | Quatre avant, quatre après |
| `vue: '#taches'`, `lien` de « Scanner », libellé du 2ᵉ appui | **0** | Des attributs, pas des pixels |

**Total : zéro pixel ajouté** — la preuve que la décision du § 8.1 était la bonne.
`node outils/verifier-rendu.mjs` doit le confirmer sans qu'une constante de mise en
page ait bougé ; s'il échoue, la réponse est de **retirer** quelque chose, jamais
d'agrandir le cadre.

**Un point de vigilance mesurable :** la vue « Tâches » de la cuisine passera de deux
listes à trois (`todo.maintenance`, `todo.home_stock_expirations`,
`todo.home_stock_shopping`). `repartirTaches` réserve déjà la dernière ligne à un
« +N tâches » — le débordement est structurellement impossible — mais cette ligne
deviendra **fréquente** au lieu d'exceptionnelle. L'ordre de `listesTachesPiece`
devient donc une décision : entretien, puis DLC, puis courses. **Une DLC passe avant
une course** : l'une a une échéance, l'autre non.

## 9. Les intents vocaux de Bleuenn

### 9.1 Sept phrases, et pas une de plus

Le foyer compte **une personne**. Le catalogue vocal n'a donc pas à couvrir un
système : il doit couvrir les sept choses qu'on dit vraiment, les mains dans la
farine ou la tête dans le frigo.

| # | Phrase (et ses variantes) | Écrit ? | Sert |
|---|---|---|---|
| 1 | « Il me reste des œufs ? » · « Est-ce qu'il y a du lait ? » · « Combien il reste de café ? » | non | `home_stock.query_stock` |
| 2 | « Qu'est-ce qu'on mange ce soir ? » · « C'est quoi le dîner ? » · « Qu'est-ce qui est prévu demain midi ? » | non | `home_stock.query_meals` |
| 3 | « Qu'est-ce qu'il faut acheter ? » · « Qu'est-ce qu'il y a sur la liste ? » | non | `home_stock.query_shopping_list` |
| 4 | « Ajoute du lait à la liste » · « Note du beurre » · « Ajoute deux baguettes à la liste » | **oui** | `home_stock.add_to_shopping_list` |
| 5 | « Qu'est-ce qui périme ? » · « Qu'est-ce qui est bientôt périmé ? » | non | attribut `batches` de `binary_sensor.home_stock_expirations` |
| 6 | « J'ai mangé le dîner » · « J'ai fini le déjeuner » | **oui**, avec confirmation | `home_stock.validate_meal` |
| 7 | « Qu'est-ce que j'ai mangé aujourd'hui ? » | non | `sensor.home_stock_kcal_today` et son attribut |

Cinq lectures, deux écritures — et une seule des deux écritures est irréversible.
C'est le bon rapport pour une surface qui n'a **aucun moyen d'annuler** : il n'y a
pas de « Ctrl-Z » à la voix, et une phrase mal comprise ne se rattrape que par une
autre phrase.

**Ce qui est délibérément absent, et que quelqu'un demandera :** « range le lait au
frigo » (cinq informations manquent — article, quantité, prix, emplacement, DLC :
c'est le lot 1, au scan) ; « j'ai mangé une part de gratin » (il faut un produit *et*
une quantité — « une part » n'a de sens que dans un repas planifié, cas déjà couvert
par la phrase 6) ; « jette le yaourt » et « enlève le lait de la liste » (§ 9.3) ;
« combien j'ai dépensé cette semaine ? » (un chiffre isolé sans comparaison n'apprend
rien : `sensor.home_stock_cost_today` a des statistiques long terme et un graphe) ;
« planifie un gratin pour jeudi » (différée, § 15 — choisir parmi 87 recettes à la
voix demande une désambiguïsation multi-tours qu'aucun `intent_script` ne porte).

### 9.2 Le mécanisme : `intent_script` + `custom_sentences`, livrés en paquet

| Voie | Verdict |
|---|---|
| **Intents natifs HA** (`intent_script` + phrases dans `custom_sentences/fr/`) | **Retenue** |
| Outils exposés à l'agent conversationnel (le LLM appelle les services) | Rejetée comme mécanisme **principal** |
| Une plateforme `conversation` propre à `home_stock` | Rejetée : un agent de plus dans une maison qui en a déjà un, et qu'il faudrait sélectionner à la place de Bleuenn |

**Pourquoi les intents natifs.** Un agent conversationnel HA essaie d'abord les
intents locaux et ne passe au LLM que s'il n'en reconnaît aucun. Trois conséquences
directes : « Il me reste des œufs ? » répond **hors ligne**, en quelques dizaines de
millisecondes, sans aller-retour vers Gemini et sans qu'un modèle puisse halluciner
un stock ; une phrase d'écriture est **déterministe** — le même énoncé produit
toujours le même appel de service, alors qu'un LLM qui choisit ses outils peut
décider un jour d'appeler `add_stock` au lieu de `add_to_shopping_list`, ce qui est
inacceptable sur un service qui écrit ; et les phrases restent **en français, dans un
fichier lisible**, versionnées avec le composant. Le LLM garde son rôle : tout ce que
les sept intents ne reconnaissent pas lui revient. **C'est un repli, pas le
mécanisme.**

**Où ça vit** (convention du lot 2, jamais enfreinte depuis) :

```
meal/blueprints/automation/home_stock/courses_bleuenn.yaml   (lot 6)
meal/custom_sentences/fr/home_stock.yaml                     (lot 6)
```

`custom_sentences/fr/home_stock.yaml` est **livré dans le dépôt, jamais copié par
l'intégration**. `docs/exploitation.md` explique le geste : copier le fichier dans
`config/custom_sentences/fr/`, coller les blocs `intent_script` dans
`configuration.yaml`, recharger. **`home_stock` ne modifie jamais la configuration de
la maison** — même contrat que les blueprints, et il vaut ici pour une raison de
plus : `intent_script` est une clé de `configuration.yaml`, un fichier que le
propriétaire tient à la main.

Forme retenue, sur l'exemple 1 :

```yaml
# custom_sentences/fr/home_stock.yaml
language: fr
intents:
  HomeStockQueryStock:
    data:
      - sentences:
          - "(il me reste|est-ce qu'il (me )?reste|il y a) (du|de la|des|de l') {product}"
          - "combien (il me reste|il reste|j'ai) (de|du|de la|des|d') {product}"
lists:
  product:
    wildcard: true
```

Le corps `intent_script` appelle le service à réponse et met en phrase. Deux règles
de rédaction, tirées du blueprint DLC du lot 2 : **jamais une liste brute** (« il te
reste six œufs et un litre de lait », avec l'accord de nombre en Jinja, comme
`dlc_bleuenn.yaml` le fait déjà) ; et **une phrase quand il n'y a rien** — « il ne
reste plus d'œufs » est une réponse, le silence est une panne.

**Nommage :** identifiants d'intent, listes et slots **en anglais**
(`HomeStockQueryStock`, `{product}`), comme tout le code depuis le lot 0. Seules les
phrases et les réponses sont en français.

### 9.3 Où passe la limite de ce qui s'écrit à la voix

Le journal de `home_stock` est **en ajout seul**. Le lot 4 a introduit la correction
(`home_stock/movement/correct`, `home_stock/meal/correct`), mais une correction n'est
pas une annulation : c'est une **contrepassation**, un second mouvement qui neutralise
le premier. Le journal garde les deux. Une erreur vocale n'est donc jamais effacée —
elle est réparée, visiblement, depuis le panneau.

**La règle du lot :**

> Une phrase peut écrire si, et seulement si, (a) son effet est **borné** — elle ne
> peut pas décrémenter plus que ce qu'elle nomme —, et (b) sa réparation est
> **possible sans le panneau ou sans urgence**.

Application :

| Geste | Écrit à la voix ? | Justification |
|---|---|---|
| Ajouter une ligne de courses | **oui, sans confirmation** | Effet borné (une ligne), réparation triviale (on décoche, ou on ne l'achète pas). C'est aussi le seul geste où le vocal bat toutes les autres surfaces : les mains dans l'évier |
| Valider un repas planifié | **oui, avec confirmation obligatoire** | Effet borné (les ingrédients de **ce** repas, déjà connus), mais irréversible sans passer par le journal. Bleuenn annonce ce qui va être décrémenté et attend un « oui » |
| Consommer un produit au hasard | **non** | Non borné : « j'ai mangé du riz » ne dit pas combien, et le FIFO décrémenterait un lot arbitraire |
| Jeter (`waste`) | **non** | Irréversible **et** comptabilisé dans `sensor.home_stock_cost_waste_total`, un chiffre qu'on regarde sur douze mois. Une erreur y reste visible un an |
| Retirer une ligne de courses | **non** | Un `removed_at`, pas un `DELETE` : la réconciliation « doit se souvenir qu'on n'en veut pas » (lot 4, § 7.4). Un retrait dit par erreur **empêche la ligne de revenir**, silencieusement, à chaque réconciliation. C'est le pire cas de tout le lot : une erreur qui se répare mal parce qu'elle ne se voit pas |
| Modifier un seuil, un produit, un prix | **non** | Aucune raison de le faire debout |

**La confirmation de la phrase 6, concrètement.** `home_stock.validate_meal` simule
par défaut (`dry_run: true`, décision du lot 3 — « un service qui décrémente un stock
ne doit pas le faire au premier appel exploratoire »). L'intent l'exploite tel quel :

1. premier tour — `validate_meal` avec `dry_run: true` → Bleuenn énonce le plan de
   décrément (« je retire 200 g de pommes de terre, 150 g de crème et deux œufs, je
   confirme ? ») ;
2. second tour — sur « oui », `validate_meal` avec `dry_run: false`.

C'est exactement le « deux appuis » de la tablette, transposé à l'oral. **Le
`dry_run` par défaut du lot 3 a été écrit pour les Outils de développement ; il vient
de payer une seconde fois.**

### 9.4 Le sens sortant : ce que Bleuenn dit sans qu'on lui demande

Trois annonces, toutes en blueprint, toutes optionnelles, toutes déclenchées par
l'heure et non par un basculement d'état — le coordinateur se rafraîchit parfois à
trois heures du matin.

| Blueprint | Lot | Sur quoi |
|---|---|---|
| `dlc_bleuenn.yaml` | 2 | `binary_sensor.home_stock_expirations` + attribut `batches` |
| `objectifs_bleuenn.yaml` | 2bis | `binary_sensor.home_stock_nutrition_goals` |
| `courses_bleuenn.yaml` | **6** | `sensor.home_stock_shopping_list` + attribut `items` |

Le troisième est le seul ajout du lot, et il ne mérite un blueprint que pour une
raison : il n'existe **aucune** autre façon de rappeler la liste au moment où on
part. Il annonce les lignes non cochées groupées par rayon, plafonnées à ce qui se
retient à l'oreille (« sept articles, dont trois au rayon frais »), avec le détail
seulement si la liste est courte.

Le lot 5 (§ 18) laissait « alerte de fin de garantie annoncée à la voix » au lot 6.
**Refusée** : une fin de garantie se traite avec une facture sous les yeux, pas en
écoutant une enceinte. Le capteur reste disponible pour qui veut l'automation.

## 10. La vue dense PC

### 10.1 Ce qu'elle apporte que le téléphone ne peut pas

Quatre choses, une seule cause — **la largeur**.

| Apport | Pourquoi le téléphone ne peut pas |
|---|---|
| **Le tableau** | Sur 412 px, une ligne de catalogue empile nom, unité, seuil, catégorie. Trouver un doublon parmi trois cents produits suppose de voir trente lignes d'un coup |
| **L'édition en série** | Corriger trente seuils au pouce est une soirée ; un formulaire large permet de rester dans la liste |
| **La profondeur d'historique** | Douze barres mensuelles (`journal/series`, `MAX_SERIES_COUNT = 60`) font 30 px chacune sur 412 px |
| **La correction d'un mouvement** (lot 4, § 12.6) | Chercher une ligne dans un journal, lire sa contrepartie, confirmer. Personne ne fait ça debout |

### 10.2 Où elle vit : dans le panneau, pas à côté

**Décision : la vue dense est le panneau existant, au-delà de 1000 px.** Pas une page
séparée, pas un second bundle, pas un second point d'entrée.

1. **Le mécanisme existe déjà** : `@state() large` (`innerWidth >= 1000`), mis à jour
   sur `resize`, **mesuré et non déduit d'un agent utilisateur**, déjà utilisé par le
   planning pour choisir entre la semaine et la journée.
2. **Un écran est déjà écrit pour le PC** : `ecrans/catalogue.ts`.
3. **Un second bundle doublerait tout** — rollup, vérificateur, file hors-ligne,
   connexion, 26 fichiers de tests — pour zéro fonction nouvelle.
4. **Les données sont les mêmes** : mêmes commandes, mêmes écrans, mêmes règles de
   validation. Deux frontends sur un même modèle finissent par diverger sur une
   règle, exactement l'argument qui a fait écrire `test_surface_parity.py`.
5. **HA fournit déjà `narrow`** au panneau, aujourd'hui inutilisé : le frontend hôte
   sait s'il est étroit, on n'a pas à le redécouvrir.

### 10.3 Ce qui change, écran par écran

Pas tous. Un écran qui n'a rien à gagner à la largeur ne doit **rien** changer : une
mise en page conditionnelle est une seconde mise en page à tester.

| Écran | Sur ≥ 1000 px | Pourquoi |
|---|---|---|
| `catalogue` | Tableau à colonnes, édition en ligne sans quitter la liste | Le cœur de la vue dense |
| `journal` | Douze barres mensuelles + le détail du jour côte à côte | Aujourd'hui, il faut naviguer entre les deux |
| `liste` | Rayons en colonnes plutôt qu'empilés | Une liste de courses est courte mais large (nom, quantité, rayon, origine) |
| `reglages` | Rayons, emplacements et magasins en trois colonnes | Trois listes réordonnables, aujourd'hui empilées |
| `ticket` | Photo à gauche, lignes rapprochées à droite | Le rapprochement se fait **en comparant** ; empilés, on scrolle entre les deux |
| `equipements`, `piles` | Tableau | Même argument que le catalogue, sur moins de lignes |
| `planning` | **déjà fait** (`large`) | — |
| `scanner`, `fiche`, `panier`, `rangement`, `session` | **inchangés** | Écrans de magasin, conçus pour une main. Les élargir n'apporte rien et coûterait six variantes à vérifier |
| `recettes`, `recette`, `validation`, `consommation` | **inchangés** | La vue cuisine est une vue debout ; l'élargir la dégraderait |

Sept écrans adaptés, dix inchangés. **La vue dense n'est pas « le panneau en grand » :
c'est le panneau qui cesse d'être étroit là où l'étroitesse coûtait quelque chose.**

### 10.4 Les formats du vérificateur de rendu

`meal/frontend/outils/verifier-rendu.mjs` mesure aujourd'hui **deux** formats —
412 × 915 (le Pixel qui scanne en rayon) et 1280 × 800 (le bureau) — avec les seuils
WCAG AA (48 px de cible, 4,5:1 de contraste), plus souples que le mur parce que ce
panneau se tient en main ou se pilote à la souris.

**Ajout du lot 6 : un troisième format, 1920 × 1080.** Le 1280 × 800 est **à peine
au-dessus** du seuil de 1000 px : c'est le cas où la mise en page dense est la plus
serrée, donc celui qui détecte un débordement. Le 1920 × 1080 est le cas le plus
lâche, donc celui qui détecte l'inverse — un tableau qui laisse 700 px de vide, un
texte qui s'étire sur une ligne illisible. Les deux défauts existent, et aucun des
deux formats actuels ne les voit tous les deux.

**Effet sur le compte d'exécutions.** Le vérificateur en fait **47** aujourd'hui
(22 scénarios × 2 formats + 3 scénarios sur bundle minifié). Après le lot 6 :
22 × **3** = 66, + 3 minifiés = **69**, + un scénario propre à la vue dense
(« Catalogue large : tableau, édition en ligne, trois cents produits », en
1920 × 1080 seulement) — les six autres écrans adaptés étant déjà couverts par des
scénarios existants, qui les mesureront désormais dans trois formats. **Cible : 70
exécutions.** Le chiffre exact est une conséquence du plan, mais il doit **monter** :
un lot qui le laisse à 47 n'a pas ajouté de format.

Deux garde-fous existants restent en vigueur : l'auto-vérification (le script casse
volontairement cinq choses et vérifie qu'il les détecte — sans quoi « aucun défaut »
ne prouve rien) et le contrôle que chaque scénario a bien **atteint** l'écran attendu
avant de le mesurer.

## 11. Ce qui reste à Lovelace — révision de la répartition du lot 0

Le lot 0 (§ 5.1) avait posé cette table. Six lots plus tard, elle est en partie
fausse, et il vaut mieux le dire que la laisser guider quelqu'un.

| Lot 0 disait — **Lovelace natif** | Vrai en 2026-08-21 ? |
|---|---|
| Alertes DLC, ruptures (`binary_sensor`, `todo`) | **Oui**, et enrichi : le vocal (§ 9) et la ligne de synthèse des tablettes (§ 8.3) s'en servent aussi |
| Liste de courses cochable (`todo`) | **Oui pour Lovelace et le mobile**, **faux pour les tablettes murales** (§ 11.3) |
| kcal/jour, €/jour (`statistics-graph`) | **Oui**, et c'est la seule surface qui les montre. Le panneau a son propre journal (lot 2), qui répond à une autre question — « qu'est-ce que j'ai mangé », pas « comment ça évolue » |
| Planning de la semaine (`calendar`) | **Oui**, `calendar.home_stock_meals` est une vraie entité. Le panneau a un écran `planning` qui **édite** ; la carte Lovelace **consulte** |
| Boutons de validation (`button`, scripts) | **Non, et abandonné.** Aucune entité `button` n'a jamais été créée. Valider un repas demande des portions et des ingrédients à ignorer : c'est un écran, jamais un bouton |

| Lot 0 disait — **SPA** | Vrai ? |
|---|---|
| Scan caméra en rafale | Oui (lot 1) |
| Saisie « 200 g sur ce lot » | Oui (lot 2) |
| Catalogue dense, édition d'un produit | Oui — et **c'est devenu la vue dense PC** (§ 10) |
| Vue cuisine d'une recette | Oui (lot 3) — **et elle a un jumeau sur la tablette** (§ 8.6), ce que le lot 0 n'avait pas prévu |
| Rangement des courses | Oui (lot 1) |

### 11.1 Ce qui a bougé, et pourquoi

1. **Les tablettes murales ne sont pas Lovelace.** Le lot 0 a écrit sa répartition
   sans connaître `wallpanel-app`, et les lots 4 et 5 ont répété l'erreur (lot 4,
   § 18 : *« la tablette de la cuisine affiche la liste avec la carte `todo-list`
   native »*). **C'est faux** : les dashboards `.storage/lovelace.wallpanel_*` sont
   périmés depuis le 2026-08-02 et les modifier n'a aucun effet. La colonne
   « Lovelace » du lot 0 vaut pour le téléphone, l'ordinateur et l'application
   mobile — pas pour les murs.
2. **Une troisième colonne existait sans être nommée** : la voix n'apparaît nulle
   part dans la table du lot 0, alors que `query_stock` y était déjà spécifié pour
   elle.
3. **La quatrième surface est une largeur, pas un support.** Le lot 0 opposait
   Lovelace et SPA ; le vrai clivage est *à quoi sert le geste* (§ 5).

### 11.2 La répartition qui vaut à partir du lot 6

| Surface | Techno | Ce qui y vit |
|---|---|---|
| **Lovelace** (téléphone, PC, app mobile) | cartes natives | `todo.home_stock_shopping` et `todo.home_stock_expirations` en `todo-list` · `binary_sensor.*` en badges · `statistics-graph` sur `kcal_today`/`cost_today` · `calendar.home_stock_meals` |
| **Panneau** | SPA `home_stock` | Les dix-sept écrans (§ 4.1), en étroit et en large |
| **Tablettes murales** | `wallpanel-app` | Bloc repas · ligne DLC · vue « Tâches » · vue recette (§ 8) |
| **Voix** | `intent_script` + `custom_sentences` | Sept phrases (§ 9) |

**Aucune carte Lovelace n'est livrée par `home_stock`.** Ni au lot 0, ni ici. Les
entités sont là ; le dashboard appartient au propriétaire, comme les automations.

### 11.3 La correction à porter dans les specs précédents

| Spec | Ligne fausse | Correction |
|---|---|---|
| Lot 0, § 5.1 | « Liste de courses cochable (`todo`) » en colonne Lovelace | Vrai sauf pour les tablettes murales, qui ne lisent aucun dashboard |
| Lot 4, § 18 | « La tablette de la cuisine affiche la liste avec la carte `todo-list` native » | Faux. Elle l'affiche via `listesTachesExtra` dans `wallpanel-app` (§ 8.4) |
| Lot 5, § 17 | « Une ligne *n* piles faibles si elle se révèle utile » | Elle ne l'est pas : doublon avec « {n} tâches d'entretien » (§ 8.8) |

Ces trois corrections sont **des amendements de spec, pas du code**. Elles vivent
ici et sont reportées dans `docs/exploitation.md` ; les documents d'origine ne sont
pas réécrits, conformément à l'usage des lots précédents (« Amendements aux specs
précédents »).

## 12. Surface Home Assistant

C'est la section la plus courte du lot, et c'est un bon signe : **cinq lots de
travail sur le composant ont rendu la sixième surface presque gratuite.**

### 12.1 Commandes websocket — aucune nouvelle

Les quatre commandes dont la tablette a besoin existent toutes, et aucune n'exige
l'administrateur (§ 7.2) :

| Commande | Usage lot 6 | Lot d'origine |
|---|---|---|
| `home_stock/recipe/get` | La vue `#recette` | 3 |
| `home_stock/meal/preview` | L'armement de « Terminer » (n'écrit rien) | 3 |
| `home_stock/meal/validate` | La confirmation de « Terminer » | 3 |
| `home_stock/journal/day` | *(non utilisé — la tablette ne montre pas la compta, § 8.8)* | 2 |

`home_stock/subscribe` reste réservé au panneau (§ 7.6).

### 12.2 Services — un champ optionnel

| Service | Changement | Raison |
|---|---|---|
| `home_stock.query_meals` | `slot_key` **optionnel** (`vol.In(MEAL_SLOT_KEYS)`) | « Qu'est-ce qu'on mange **ce soir** ? » suppose de savoir quel créneau est « ce soir ». `MEAL_SLOT_KEYS` vit dans `const.py` ; le refaire en Jinja dans un `intent_script` mettrait la même règle à deux endroits, et c'est exactement le défaut que `maintenance.jinja` a déjà payé (la regex dupliquée, cf. CLAUDE.md) |

Rien d'autre. `query_stock`, `query_shopping_list`, `add_to_shopping_list` et
`validate_meal` répondent aux six autres phrases sans une ligne de plus.

### 12.3 Entités — un attribut

| Entité | Changement | Raison |
|---|---|---|
| `sensor.home_stock_next_meal` | attribut **`meal_id`** ajouté | La tablette affiche le repas suivant (§ 8.2) puis doit pouvoir le **valider** (§ 8.7) ; sans `meal_id`, elle devrait rappeler `home_stock/meals/list` juste pour retrouver l'identifiant de ce qu'elle affiche déjà. Le vocal a le même besoin (§ 9.3) |

L'attribut est déjà calculé : `NextMealSensor._meal` tient le dictionnaire complet du
repas et n'en publie que quatre champs. C'est une ligne.

### 12.4 La parité des deux surfaces, sans exception

Règle du lot 1, répétée à chaque lot depuis, matérialisée par
`tests/test_surface_parity.py` : *« Aucune des deux surfaces n'a le droit d'être la
plus faible. Ce que le websocket refuse, le service le refuse, et réciproquement. »*

Le lot 6 ajoute un paramètre à un service et un attribut à une entité. La parité s'y
applique quand même :

| Cas | Websocket | Service | Attendu |
|---|---|---|---|
| `slot_key` inconnu (`"gouter"`) | `home_stock/meals/list` **n'a pas de `slot_key`** → sans objet | `query_meals` refuse (`vol.In`) | Refus côté service |
| `slot_key` valide (`"dinner"`) | — | accepté | Accepté |

Le premier cas est le seul point d'asymétrie du lot, et il est **assumé et
documenté** : `home_stock/meals/list` rend la plage complète, le filtrage par créneau
est un service de commodité pour le vocal. Ajouter `slot_key` au websocket serait
ajouter un filtre que le panneau n'utilise pas, donc du code jamais exercé. Une
ligne de `test_surface_parity.py` acte cette asymétrie **explicitement**, pour qu'elle
soit un choix relu et non un oubli découvert.

**Ce que le lot 6 n'ajoute pas, et il faut s'en réjouir** : aucune migration de
schéma, aucune table, aucun motif de mouvement, aucun capteur. Un lot de surfaces qui
touche au modèle de données est un lot qui a mal lu ce qui existait.

## 13. Erreurs et exploitation

### 13.1 Ce qui casse, et ce que la maison voit

| Panne | Effet visible | Comportement voulu |
|---|---|---|
| `home_stock` non chargé (entrée absente, base verrouillée) | Les entités passent `unavailable` | `Etat.estUtilisable` masque le bloc repas, la ligne DLC et la commande « Recette ». **L'écran vit**, avec ses lumières et ses minuteurs. Mécanisme générique, aucune règle propre au garde-manger |
| Websocket coupé (Wi-Fi, redémarrage HA) | `surSilence` affiche l'état hors ligne | Déjà en place. Le garde `estHorsLigne` refuse toute écriture — **visiblement**, jamais en file (§ 8.7) |
| `meal/validate` refusé (stock insuffisant) | Message français rendu par `messages.py` | `envoyerCommande` rejette, la vue affiche le refus et **ne retire rien** de l'écran |
| Un `uid` de tâche périmé | Rien | `todo.update_item` traite un `uid` inconnu en no-op explicite (lot 0 pour les DLC, lot 4 pour les courses) |
| Un intent qui ne trouve rien | Une phrase, jamais un silence | « Il ne reste plus d'œufs » est une réponse. § 9.2 |
| Bleuenn hors ligne (Gemini injoignable) | Les sept intents **continuent de marcher** | C'est le bénéfice des intents natifs : ils ne passent pas par le LLM (§ 9.2) |
| Le bundle de tablette est en avance sur le composant | Commande websocket inconnue → refus | Ne peut arriver que si l'ordre du § 6.4 est enfreint |
| Le composant est en avance sur le bundle | Rien | Cas normal entre l'étape 1 et l'étape 6 : la tablette n'appelle simplement pas ce qu'elle ne connaît pas |

### 13.2 Ce qui va dans `docs/exploitation.md`

Une section « Lot 6 — les quatre surfaces », dans le ton des précédentes : ce que le
propriétaire doit faire de ses mains, et ce qui se répare.

1. **Installer les phrases vocales.** Copier `custom_sentences/fr/home_stock.yaml`
   dans `config/custom_sentences/fr/`, coller le bloc `intent_script` dans
   `configuration.yaml`, recharger. La liste des sept phrases, en clair, avec leurs
   variantes — c'est le document qu'on relit quand une phrase ne marche pas.
2. **Le blueprint `courses_bleuenn.yaml`** : à importer, avec son heure et son agent.
3. **Ce que la tablette de la cuisine montre maintenant**, et ce qu'elle ne montre
   pas — la table du § 8.8, parce que « pourquoi les kcal ne sont pas au mur ? » est
   une question qui reviendra.
4. **La procédure de déploiement de `wallpanel-app`**, avec l'avertissement en
   première ligne : `npm run build` **déploie**. Puis vider le cache, recharger l'URL,
   regarder la capture d'écran — et se fier à l'heure de l'horloge affichée, pas à
   `frame_timestamp`.
5. **Le retour arrière**, en une phrase : `git revert` dans `wallpanel-app`, puis
   `npm run build`. Il n'y a pas d'autre chemin — les dashboards `.storage` de secours
   sont périmés et ne servent à rien.
6. **Le rappel du lot 7** : Grocy tourne toujours. `/local/grocy-scanner.html` et
   `/local/grocy-recipes.html` restent servis ; plus aucune tablette n'y renvoie.

## 14. Stratégie de test

Deux dépôts, deux suites, deux vérificateurs. **Aucune des deux n'est facultative**,
et elles ne se remplacent pas : celle de `meal` prouve que le composant est correct,
celle de `wallpanel-app` prouve que la dalle tient.

### 14.1 Dépôt `meal` — Python

`./scripts/test.sh` — **1877 tests** aujourd'hui, dans une image alignée sur
HA 2026.8.2 (`docker build` puis `docker run --rm`, jamais l'instance vivante).

| Fichier | Ce qui s'ajoute |
|---|---|
| `test_meal_sensors.py` | `sensor.home_stock_next_meal` publie `meal_id` ; il vaut `None` quand aucun repas n'est prévu (jamais `0`, même argument que l'état vide) |
| `test_services_meals.py` | `query_meals` accepte `slot_key`, le filtre, refuse une valeur hors `MEAL_SLOT_KEYS`, et se comporte comme avant sans le paramètre |
| `test_surface_parity.py` | L'asymétrie `slot_key` est **inscrite** comme choix (§ 12.4), pas découverte |
| `test_entities.py` | Les états de `todo.home_stock_expirations` et `todo.home_stock_shopping` sont bien des **comptes** — c'est ce dont dépend la ligne de synthèse de la tablette (§ 8.3). Aujourd'hui implicite, désormais tenu par un test |

**Ce qui ne se teste pas ici** : les phrases vocales. Un `intent_script` vit dans
`configuration.yaml`, hors du dépôt. Ce qui **se teste**, c'est que les services
qu'il appelle rendent une réponse dont la forme est stable — et c'est déjà couvert
par `test_services*.py`. La spec exige en revanche que les sept phrases soient
**listées dans `docs/exploitation.md` avec leur réponse attendue**, pour être
rejouables à la main en trois minutes.

### 14.2 Dépôt `meal` — front du panneau

`npm test` depuis `meal/frontend` — **499 tests**, vitest, jsdom.

| Fichier | Ce qui s'ajoute |
|---|---|
| `catalogue.test.ts` | Le rendu large : tableau à colonnes, édition en ligne |
| `journal.test.ts` | Barres et détail côte à côte au-delà de 1000 px |
| `liste.test.ts`, `reglages.test.ts`, `ticket.test.ts` | Idem, une assertion de structure par écran |
| `panneau.test.ts` | `large` bascule sur `resize` et **ne casse aucun écran étroit** |

`node outils/verifier-rendu.mjs` — **47 exécutions** aujourd'hui, cible **70**
(§ 10.4). Attention au piège de lecture : l'outil compte des **exécutions**, pas des
scénarios — chaque scénario tourne dans chaque format. Passer de deux à trois formats
fait donc +50 % sans qu'un seul scénario ait été écrit.

### 14.3 Dépôt `wallpanel-app` — l'autre base de code

**C'est le point que ce lot doit traiter explicitement, parce qu'il n'a aucun
précédent dans les cinq lots précédents.** `wallpanel-app` a :

- sa propre suite : `npm test` (vitest, **40 fichiers** dans `tests/`, dont
  `aides.ts` et `setup-animate.ts` qui sont des utilitaires — le README parle de 33,
  chiffre à rafraîchir) ;
- son propre vérificateur : `node outils/verifier-rendu.mjs`, format 343 × 585,
  seuils 62 px / 5:1, **qui ne déploie pas** ;
- ses propres mesureurs : `mesurer-salve.mjs`, `mesurer-rendus.mjs`.

Toutes ces commandes se lancent **depuis `tools/wallpanel-app`**, jamais depuis la
racine.

| Fichier de test | Ce qui s'ajoute |
|---|---|
| `pieces.test.ts` | La cuisine déclare `todo.home_stock_shopping` et plus aucune entité `grocy.*` ; **aucune chaîne `grocy` ne subsiste dans `src/`** — une assertion sur tout le répertoire, seul moyen d'attraper un reliquat dans un fichier oublié |
| `cochage.test.ts`, `taches.test.ts` | `listesTachesPiece` rend trois listes en cuisine, dans l'ordre voulu (DLC avant courses) ; `libelleListe` connaît la nouvelle entité ; `repartirTaches` fait apparaître « +N » au bon seuil, **sans qu'une tâche disparaisse en silence** |
| `defaut.test.ts`, `repas.test.ts` | `rendreRepasSuivant` alimenté par l'attribut d'un capteur ; capteur `unavailable` → `undefined` → repli entretien. Les trois issues `ok`/`absente`/`muette` disparaissent avec Grocy |
| `recette.test.ts`, `rendu-recette.test.ts` | Les pages alimentées par les étapes structurées de `home_stock/recipe/get`, plus par du HTML découpé |
| `connexion.test.ts` | **Inchangé** — et c'est la preuve du § 7.3 : le canal n'a pas eu besoin d'évoluer |
| `demarrage.test.ts` | Plus aucun `appelerService('grocy', …)` ; « Terminer » envoie `home_stock/meal/validate` ; un refus serveur n'efface rien à l'écran |
| `orchestration.test.ts`, `pannes.test.ts` | Composant `unavailable` : l'écran vit, sans bloc et sans ligne |

**Ce qu'aucun test unitaire ne prouvera** : que ça tient dans 343 × 585 px. jsdom ne
calcule aucune mise en page. Seul `verifier-rendu.mjs` le dit, et il faut le lancer
sur la cuisine à chaque étape, pas une fois à la fin.

### 14.4 L'ordre des preuves, et la seule fenêtre de déploiement

| # | Commande | Dépôt | Déploie ? |
|---|---|---|---|
| 1 | `./scripts/test.sh` | `meal` | non |
| 2 | `npm test` | `meal/frontend` | non |
| 3 | `node outils/verifier-rendu.mjs` | `meal/frontend` | non |
| 4 | `npm run build` | `meal/frontend` | **oui** — écrit le bundle du composant (règle du lot 1 : une fois, en fin de partie `meal`) |
| 5 | `npm test` | `wallpanel-app` | non |
| 6 | `node outils/verifier-rendu.mjs` | `wallpanel-app` | non |
| 7 | `node outils/mesurer-salve.mjs cuisine --src` | `wallpanel-app` | non |
| 8 | `node outils/mesurer-rendus.mjs cuisine 300` | `wallpanel-app` | non |
| 9 | `npm run build` | `wallpanel-app` | **OUI — LES TROIS TABLETTES** |
| 10 | `verifier-rendu.mjs --deploye`, vider le cache, capture | `wallpanel-app` | non |

**L'étape 9 est la seule fenêtre de déploiement du mur, et elle est irréversible sans
un second build.** Tout ce qui peut être vérifié avant elle **doit** l'être avant
elle. Un plan d'implémentation qui place un `npm run build` de `wallpanel-app`
ailleurs qu'en avant-dernière position est un plan à refuser.

> **Interdits, rappelés une dernière fois :** aucun `docker compose`, aucun
> redémarrage de Home Assistant, aucun rechargement de l'intégration, aucune lecture
> du jeton hors de ce que `verifier-rendu.mjs` fait déjà de lui-même, aucune écriture
> dans `/opt/nivuus/HomeAssistant/config/` en dehors des étapes 4 et 9, aucune
> modification de Grocy.

## 15. Points différés

| Sujet | Lot | Raison |
|---|---|---|
| **La reprise des données Grocy et l'extinction du conteneur** | 7 | Périmètre explicite du lot 7 depuis le lot 0. Le lot 6 débranche les *surfaces* de Grocy ; les *données* y restent |
| **Les six *chores* Grocy** (litière, fontaine, croquettes, poubelles) | 7 | Trou de la feuille de route repéré au lot 5 (§ 18). Ce sont des tâches **périodiques**, et `todo.maintenance` est piloté par des conditions. Le lot 6 ne les touche pas : elles ne sont sur aucune des quatre surfaces aujourd'hui |
| **« Planifie un gratin pour jeudi » à la voix** | ultérieur | `home_stock.plan_meal` existe, mais choisir parmi 87 recettes à l'oral demande une désambiguïsation multi-tours qu'un `intent_script` ne porte pas. À rouvrir le jour où l'agent expose des outils avec confirmation |
| **Déclarer une consommation libre à la voix** | — | Non borné par construction (§ 9.3). L'écran « manger » du panneau reste le chemin |
| **Une souscription `home_stock/subscribe` depuis la tablette** | ultérieur | Inutile tant que la tablette n'affiche que des données d'attributs (§ 7.6). À rouvrir si — et seulement si — une donnée future n'existe que là |
| **Une file hors-ligne sur la tablette** | — | Une tablette murale est à trois mètres du routeur, qui est le serveur HA. Rejouer une validation de repas sans témoin est pire que la refuser (§ 8.7) |
| **Le scan depuis la tablette** | — | La caméra d'une Fire 7 lit mal un code-barres. Le bouton « Scanner » ouvre le panneau ; s'il déçoit à la mesure, il disparaît (§ 8.5) |
| **Une ligne « n piles faibles » sur les tablettes** | — | Refusée : doublon avec « {n} tâches d'entretien », qui les compte déjà. Renverse la suggestion du lot 5, § 17 |
| **L'alerte de fin de garantie à la voix** | — | Refusée : une garantie se traite avec une facture sous les yeux. Le capteur reste disponible pour qui veut l'automation (renverse le lot 5, § 18) |
| **Les kcal, les € et les objectifs sur les tablettes** | — | Une comptabilité se lit assise ; un dépassement au mur à l'heure du dîner est un reproche (§ 8.8) |
| **Un bloc garde-manger au bureau** | — | Aucun geste à y offrir. La retenue est le travail principal d'un lot « surfaces » |
| **La vue dense sur `scanner`/`fiche`/`panier`/`rangement`/`session`** | — | Écrans de magasin, conçus pour une main. Six variantes de plus à vérifier pour zéro gain |
| **Des cartes Lovelace livrées par `home_stock`** | — | Jamais. Les entités sont là, le dashboard appartient au propriétaire — même contrat que les blueprints |
| **Fusionner `wallpanel-app` et le panneau** | — | Deux cadres (343 × 585 et 412 × 915), deux moteurs (Chrome 100 et un navigateur à jour), deux jeux de seuils (62 px / 5:1 et 48 px / 4,5:1), deux authentifications. Ce sont deux applications, et ce lot confirme qu'elles doivent le rester : elles partagent un **modèle**, pas un rendu |

*Rédigé le 2026-08-21.*
