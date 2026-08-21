# home_stock — Lot 7 : migration & extinction

*Conception du 2026-08-21. Domaine HA : `home_stock`. Home Assistant 2026.8.2.
Dernier lot de la feuille de route posée au lot 0.*

## 1. Objectif et livrable

Reprendre ce qui reste chez Grocy — le stock, les recettes, les images, le
planning —, prouver par des contrôles chiffrés que rien n'est perdu, puis
**livrer au propriétaire la procédure d'extinction du conteneur**.

Livrable vérifiable du lot 0 : « Grocy éteint, rien de perdu ». Il se décompose
en trois preuves, dans cet ordre :

1. Le stock de `home_stock` est **identique au gramme près** à celui de Grocy,
   lot par lot, écarts assumés listés et signés.
2. Les 87 recettes, leurs 414 lignes d'ingrédients et leurs 117 images qui
   meurent avec le conteneur sont chez nous, et une recette s'ouvre sur la
   tablette **avec Grocy arrêté**.
3. Plus aucune entité, aucun template, aucune automation, aucune page de
   `www/` ne lit Grocy — inventaire fait, pas supposé.

> **Le composant n'arrête jamais Grocy.** Arrêter un conteneur de la maison est
> un geste humain. Le lot 7 **livre** la séquence (§ 18) ; il ne l'exécute pas.
> Même discipline que le raccord `maintenance.jinja` du lot 5, livré dans
> `docs/raccord/` et jamais appliqué — et que les blueprints du lot 2, livrés et
> jamais importés. L'intégration livre, elle n'installe pas.

## 2. Ce que le lot 7 hérite réellement, au 2026-08-21

Trois faits mesurés, qui commandent tout le reste. Ils ne sont pas des
hypothèses : ils sortent d'une lecture de la base de production.

### 2.1 La base de `home_stock` en production est au **schéma 2**

`/opt/nivuus/HomeAssistant/config/home_stock.db` (4 Ko + un WAL de 412 Ko non
consolidé, dernière écriture le 2026-08-19 à 10 h 33) contient :

| | |
|---|---|
| `schema_version` | **2** (lot 1) |
| `product` | **299**, tous avec un `external_ref` Grocy |
| `article` | 299 (génériques) |
| `barcode` / `price` | 35 / 1 |
| `location` / `category` / `aisle` | 4 / 21 / 16 |
| `batch` | **1** (essai du 19 août, `closed_at` renseigné) |
| `movement` | **3** (essai : un `purchase`, un `consumption`, un `inventory`) |

Autrement dit : **les lots 2 à 6 sont écrits, testés, et jamais déployés.** Le
jour de la bascule, cette base franchit `m003` → `m008` d'un seul coup, sur des
données réelles. C'est le premier risque du lot, antérieur à toute reprise de
données (§ 18, étape 4). Les 4 lignes d'essai du 19 août **restent** : le
journal est en ajout seul, un `DELETE` y est refusé par trigger, et elles ne
coûtent rien.

### 2.2 Grocy est **encore utilisé**, aujourd'hui

Le produit **#350 « Sorbet Fraise » a été créé le 2026-08-21 à 18 h 54**, avec
son lot en stock — soit deux jours après l'import du catalogue du lot 0, et
trois heures avant l'écriture de ce document. Le catalogue de `home_stock`
compte 299 produits, celui de Grocy 300 actifs : l'écart, c'est lui.

La reprise vise donc une cible **mobile**, d'où deux règles : **l'import du
catalogue du lot 0 est rejoué en tête de bascule** (il est rejouable par
construction, c'est exactement ce pour quoi il l'a été), et **le gel de Grocy
est un geste de la séquence** (§ 18, étape 2), pas une supposition.

### 2.3 Les 299 `external_ref` font de la reprise une jointure

Sur les 108 lots de `stock`, **107 se résolvent par `external_ref`** vers un
produit de `home_stock`, avec une unité convertible et une unité de base
identique à celle déjà choisie à l'import du catalogue. Le seul échec est le
Sorbet Fraise du § 2.2, que le rejeu de l'import fait disparaître.

Sur les **414 lignes de `recipes_pos`** des 87 recettes `normal` : **0 ligne
sans produit, 0 ligne pointant un produit inactif ou supprimé, 0 ligne dont
l'unité diffère de l'unité de stock de son produit.** L'appariement
ingrédient → produit du lot 3, qui devine et qui score, **n'est pas sollicité
une seule fois** : chaque ligne connaît son produit par son identifiant.

C'est la promesse du lot 0 (« ce qui fera du lot 7 une simple jointure au lieu
d'un ré-appariement par nom ») tenue, et mesurée.

## 3. Volumétrie relevée chez Grocy

Relevé le **2026-08-21 à 21 h 40**, sur une **copie en lecture seule** de
`/opt/nivuus/Grocy/config/data/grocy.db` (5,42 Mo). Aucune écriture, jamais, sur
le fichier de production — règle du lot 0, jamais assouplie.

Un plan de migration sans volumétrie est une fiction. Voici la base entière.

| Table Grocy | Lignes | Ce qu'il en reste au lot 7 |
|---|---:|---|
| `products` | **335** (300 actifs, 35 désactivés) | 299 déjà repris ; **1 nouveau** (#350, § 2.2) |
| `product_barcodes` | 41 | 35 repris ; le rejeu prend le reste |
| `product_groups` | 21 | repris (catégories) |
| `quantity_units` | 14 | référentiel, jamais repris tel quel |
| `quantity_unit_conversions` | **30** | **14 deviennent des `packaging`** (§ 13) |
| `locations` | 4 | repris ; **l'id 1 a été supprimé du référentiel** (§ 8.5) |
| `stock` | **108** lots, 87 produits distincts | **repris** (§ 8) |
| `stock_log` | **1 123** | **archivé, pas réinjecté** (§ 9) |
| `recipes` | **268** | **102 reprises** (87 `normal` + 15 de type `1`), 166 fantômes écartées (§ 10.1) |
| `recipes_pos` | **710** | **510 reprises**, 200 orphelines écartées |
| `recipes_nestings` | **5 651** | abandonnée (§ 4) |
| `meal_plan` | **108** (88 recettes, 20 notes) | **42 reprises** — l'avenir seulement (§ 12) |
| `meal_plan_sections` | 4 | 3 déjà semées par `m004` ; la 4ᵉ est la ligne `-1` (§ 12) |
| `shopping_list` | 25 (16 cochées) | **9 reprises** (§ 13.2) |
| `shopping_lists` | 1 | sans objet — `home_stock` n'a qu'une liste |
| `batteries` | 26 | **déjà couvert par le lot 5** |
| `battery_charge_cycles` | **0** | rien |
| `equipment` | 34 | **déjà couvert par le lot 5** |
| `chores` / `chores_log` | 6 / **39** | **abandonnées** (§ 14) |
| `tasks` / `task_categories` | 0 / 0 | rien |
| `shopping_locations` | **0** | rien — aucun magasin n'a jamais été saisi |
| `userfields` / `userfield_values` | 7 / 198 | déjà repris au lot 0 (Nutri-Score, NOVA, Eco-Score, marque, allergènes) |
| `users` / `sessions` / `api_keys` | 1 / 2 / 2 | rien. Les clés meurent avec le service |
| `cache__*` | 3 tables | caches de triggers Grocy. Rien |

### 3.1 Les fichiers

Grocy stocke ses images **hors base**, dans `config/data/storage/` :

| Dossier | Fichiers | Poids | Référencés |
|---|---:|---:|---|
| `recipepictures/` | **56** | 3,9 Mo | **55**, tous depuis le HTML des descriptions. Un orphelin : `test.jpg` |
| `productpictures/` | 38 | 1,2 Mo | **33** distincts (les 5 autres sont des vignettes `__downscaledto64x64` produites par Grocy), dont **29 sur des produits actifs** |

Réconciliation faite dans les deux sens : **0 référence sans fichier**, un seul
fichier sans référence. C'est propre.

### 3.2 Les images des recettes sont de trois familles, et une seule meurt

Les 3,80 Mo de descriptions HTML des 87 recettes `normal` (la plus grosse fait
240 079 octets à elle seule) contiennent **229 balises `<img>`** :

| Famille | Références | Distinctes | Meurt avec le conteneur ? |
|---|---:|---:|---|
| `data:image/jpeg;base64,…` **dans le HTML** | 62 | 62 | **Oui** — 3,48 Mo de base64, dans 27 recettes |
| `https://grocy.allanic.me/api/files/recipepictures/<base64>` | 55 | 55 | **Oui** — servi par le conteneur |
| `https://images.unsplash.com/photo-…` | 112 | 46 | **Non** — CDN public |

**`recipes.picture_file_name` est NULL sur les 87 recettes.** Aucune n'a de
couverture au sens de Grocy : les images vivent **uniquement** dans le HTML.
Toute reprise d'image est donc une réécriture de HTML, jamais une copie de
colonne. C'est la contrainte structurante du § 11.

### 3.3 Ce que valent vraiment le stock et l'historique

Deux chiffres qui commandent les § 8 et § 9, et qu'il faut avoir vus avant de
lire quoi que ce soit d'autre.

**Le stock.** `SUM(amount × price)` sur les 108 lots donne **8 140,35 €**. Ce
n'est pas la valeur d'un garde-manger, c'est un symptôme. **7 lots sur les 64
qui portent un prix pèsent 8 089 € ; les 57 autres pèsent 51 €.**

| Lot | Produit | Quantité | Prix Grocy | « Valeur » |
|---|---|---|---|---:|
| #419 | Petits pois | 1 487 g | 2,45 €/g | **3 643 €** |
| #256, #257 | Sel | 1 000 **Pot** ×2 | 1,79 €/Pot | **1 790 € ×2** |
| #255 | Blé précuit 500g | 370 g | 1,59 €/g | **588 €** |
| #264 | Ail sémoule 90g | 89,99 **Boîte** | 1,65 €/Boîte | **148 €** |
| #241 | Paprika moulu | 5,98 Pièce | 13,80 €/Pièce | **83 €** |
| #250 | Petits pois | 12 g | 3,89 €/g | **47 €** |

Deux défauts distincts s'y superposent : le prix saisi est celui du **paquet
entier** alors que la colonne veut un prix **par unité de stock** (« 2,45 € le
gramme de petits pois »), et la quantité elle-même est parfois dans la mauvaise
unité (« 1 000 pots de sel » : ce sont des grammes, dans un produit stocké en
`Pot`). Le § 8.4 en tire une règle, pas une excuse.

**L'historique.** Les 387 sorties non annulées de `stock_log` donnent, en
appliquant les calories du catalogue, **2 804 847 kcal sur 35 journées** —
soit 80 138 kcal/jour en moyenne. La journée du **2026-08-17 pèse à elle seule
2 556 904 kcal**. Six journées sur trente-cinq tombent dans une fourchette
plausible (1 200–3 500 kcal). Et 37 journées portent une consommation sur les
**187 jours** de la période : **20 % de couverture**. Le § 9 en tire la seule
conclusion possible.

## 4. Périmètre : repris, déjà couvert, abandonné

Chaque ligne est tranchée, avec sa raison. Un abandon non justifié est une perte
déguisée.

| Donnée Grocy | Décision | Pourquoi |
|---|---|---|
| Catalogue (produits, articles, codes-barres, catégories, emplacements, champs OFF) | **Déjà couvert** (lot 0) — **rejoué** en tête de bascule | Rejouable par `external_ref`. Le rejeu rattrape ce qui a été créé depuis (§ 2.2) |
| `stock` — 108 lots, DLC, prix, ouverture, emplacement | **Repris** (§ 8) | C'est la donnée qui doit être juste au gramme près le jour de la bascule |
| `stock_log` — 1 123 lignes | **Archivé, non réinjecté** (§ 9) | Faux d'un facteur 34 en kcal, couvert à 20 % en jours, et il ferait sauter trois compteurs `TOTAL`. Preuve au § 3.3 |
| Prix historiques (`stock_log.price`, `cache__products_average_price`) | **Abandonnés** | Même défaut d'unité que le stock (§ 3.3). Le prix se réapprend à la première session de courses (lot 4) et par Open Prices (lot 1) |
| Recettes `normal` (87) et de type `1` (15) | **Reprises** (§ 10) | 102 recettes, 510 lignes d'ingrédients. La correction du § 10.1 est un amendement au lot 3 |
| Recettes `mealplan-day` / `-week` / `-shadow` (166) | **Abandonnées** | Copies générées par trois triggers Grocy (§ 10.1). Les importer créerait 166 recettes fantômes |
| `recipes_nestings` — 5 651 lignes | **Abandonnée** | Générée par les mêmes triggers. Les recettes imbriquées sont différées depuis le lot 3, § 20, sans usage constaté |
| Images de recettes | **117 rapatriées, 112 laissées à leur source** (§ 11) | Le critère est « est-ce que ça meurt avec le conteneur ? ». Unsplash ne meurt pas |
| Images de produits (33 fichiers) | **Rapatriées** (§ 11) | Même mécanisme, même geste, une seule fois pour les deux — dette ouverte par le lot 0 (« vue HTTP pour les images d'articles », jamais écrite) |
| `meal_plan` — 42 entrées à venir | **Reprises** (§ 12) | Le planning de la semaine ne doit pas disparaître le jour de la bascule |
| `meal_plan` — 66 entrées passées | **Abandonnées** (§ 12) | Un plan passé n'est ni un repas mangé ni un repas à cuisiner. Les importer `done` mentirait (aucun mouvement derrière), les importer `planned` peuplerait le calendrier de 66 fantômes |
| `shopping_list` — 9 lignes ouvertes | **Reprises** (§ 13.2) | Ce sont des courses à faire demain |
| `shopping_list` — 16 lignes cochées | **Abandonnées** | Une ligne cochée est une course faite. Elle n'a pas d'après |
| `quantity_unit_conversions` — 14 utiles | **Reprises en `packaging`** (§ 13.1) | Dette explicitement ouverte au lot 0 : « `repo.insert_packaging` existe déjà et l'attend » |
| `batteries` (26), `equipment` (34) | **Déjà couvert** (lot 5, `import_grocy_equipment`) | Le lot 7 **ne le refait pas**. Il vérifie seulement que l'import a eu lieu (§ 16, contrôle C7) |
| `battery_charge_cycles` | **Rien** | 0 ligne |
| `chores` (6) / `chores_log` (39) | **Abandonnées** (§ 14) | Tâches périodiques, hors modèle de `todo.maintenance` qui est conditionnel. 39 pointages pour 6 tâches quotidiennes sur 187 jours : **3,5 % de suivi**. Le trou de feuille de route repéré au lot 5 § 18 se referme sur un abandon assumé, pas sur un développement |
| `tasks`, `task_categories`, `shopping_locations`, `userobjects`, `userentities` | **Rien** | 0 ligne dans chacune |
| `users`, `sessions`, `api_keys` | **Rien** | Comptes et clés d'un service qu'on éteint |
| `cache__*` (3 tables) | **Rien** | Caches alimentés par les triggers Grocy |

**Hors du lot, explicitement :** toute écriture vers Grocy (décision du lot 0,
« jamais ») ; toute modification de `wallpanel-app` (le lot 6 l'a débranché) ;
tout nouvel écran du panneau au-delà du bloc de contrôle des Réglages (§ 15.3) ;
l'arrêt du conteneur, qui est un geste humain.

## 5. Décisions structurantes

| Sujet | Décision |
|---|---|
| Ordre de bascule | **Catalogue rejoué → piles/équipements → stock → recettes+images → planning+liste → contrôles → extinction.** Jamais l'inverse : chaque étape suppose la précédente |
| Cible mobile | **Grocy est gelé à la main** avant la reprise du stock (§ 18, étape 2). Aucun contrôle d'égalité n'a de sens sur une base qu'on écrit encore |
| Historique | **Non réinjecté.** Archivé sous forme d'un export daté, à côté de la sauvegarde de `grocy.db` |
| Lots sans prix plausible | **Lot importé, prix laissé à `NULL`.** `NULL` veut dire « inconnu », jamais zéro (règle du lot 0, § 7.4) |
| Lots sans DLC | **Importés avec `best_before = NULL`.** Le FIFO du lot 0 sait déjà les classer (`best_before IS NULL` en second critère) |
| Lot sans produit correspondant | **Refusé, et l'import échoue.** Après le rejeu du catalogue, ce cas ne doit plus exister : s'il existe, quelque chose a bougé pendant la bascule |
| Quantité en `variable_amount` | **Jamais réimportée comme quantité.** Provenance seulement (`raw_text`), règle du lot 3, § 18. C'est le grief n° 2 : il ne revient pas par la porte de derrière |
| Ligne d'ingrédient à unité divergente | **`amount = NULL` + anomalie nommée dans le rapport.** 25 lignes concernées, toutes de type `1` (§ 10.4) |
| Images | **Sous `media/`, jamais sous `www/`, et le composant n'écrit aucune vue HTTP** (§ 11) |
| Contrôles | **Un contrôle qui ne mesure rien échoue.** Chaque contrôle porte un plancher : zéro lot, zéro recette, zéro image lue = rouge (§ 16) |
| Extinction | **Procédure écrite, jamais exécutée par le code** |
| Migration | **`m008`, `VERSION = 8`** : une colonne, un index (§ 6) |

## 6. `m008` — une colonne, un index, et rien d'autre

Le schéma des lots 0 à 6 accueille tout ce que le lot 7 apporte, à une exception
près : **`batch` est la seule table du schéma qui n'ait pas d'`external_ref`.**

`product`, `article`, `recipe`, `recipe_ingredient`, `meal`, `battery`,
`equipment` en ont un, tous pour la même raison, écrite au lot 0 : « id Grocy,
pour un import rejouable ». Un import de stock non rejouable serait le seul de
la chaîne, et il serait le plus dangereux : c'est celui qu'on relance après
avoir corrigé un prix.

```python
# storage/migrations/m008_migration.py
VERSION = 8

SQL = """
-- L'id Grocy du lot. Même rôle exactement que product.external_ref au lot 0 :
-- c'est ce qui rend l'import du stock rejouable, donc ce qui permet de le
-- lancer en simulation, de corriger la source, et de le relancer.
ALTER TABLE batch ADD COLUMN external_ref TEXT;

-- Partiel, comme idx_recipe_source : un lot créé au scan n'a pas de référence
-- externe, et cent lots sans référence ne doivent pas se gêner.
CREATE UNIQUE INDEX idx_batch_external_ref
  ON batch(external_ref) WHERE external_ref IS NOT NULL;
"""
```

Pas d'`apply()` : il n'y a rien à rétro-remplir. Le seul lot existant en
production est l'essai du 19 août, qui ne vient pas de Grocy.

**Ce qui a été envisagé et refusé** :

- **`batch.note`**, pour les 25 lots qui portent une note de provenance chez
  Grocy. Ces notes sont la **preuve** du défaut du § 8.4 et doivent être lues
  pendant la bascule — le rapport d'import les cite mot pour mot. Après
  arbitrage, plus personne ne les lira. Une colonne que rien ne lit est ce que
  le lot 0 a refusé pour `default_currency` ; même décision.
- **Une table `archive_movement`** pour l'historique de Grocy. Elle serait
  écrite une fois et lue jamais (§ 9.3). L'archive est un fichier.
- **`recipe_step.external_ref`**. Une étape n'est pas une ligne Grocy : elle est
  découpée d'un HTML. Sa clé naturelle est `(recipe_id, position)`, déjà UNIQUE.

Le test strict de contiguïté (`test_migration_versions_are_contiguous_from_one`)
impose la suite `[1..8]` : le fichier s'appelle `m008_migration.py` et porte
`VERSION = 8`, les deux dans le même commit. `CURRENT_VERSION` suit.

## 7. Modules

```
custom_components/home_stock/
├── import_grocy.py             # lot 0, INCHANGÉ — rejoué en tête de bascule
├── import_grocy_equipment.py   # lot 5, INCHANGÉ
├── import_grocy_stock.py       # NOUVEAU — stock, liste, conversions → packaging
├── import_grocy_recipes.py     # NOUVEAU — recettes, étapes, ingrédients, planning
├── grocy/
│   ├── __init__.py
│   ├── units.py                # la table de correspondance, extraite d'import_grocy.py
│   ├── html.py                 # découpe du HTML des recettes — pur, sans hass
│   └── pictures.py             # rapatriement des images vers media/
├── migration_check.py          # NOUVEAU — les contrôles de bascule (§ 16)
└── storage/migrations/m008_migration.py
```

`grocy/units.py` **n'est pas une copie** : `MASS_UNITS`, `VOLUME_UNITS`,
`CONTAINER_UNITS`, `DOSAGE_UNITS` et `_base_unit()` sortent d'`import_grocy.py`
et y sont réimportés. Trois imports qui convertiraient les unités chacun à sa
façon finiraient par diverger — et une divergence de conversion d'unité, c'est
une bouteille et demie d'huile d'olive par burger.

`grocy/html.py` est **pur** : une chaîne de HTML en entrée, des pages, des
titres, des puces et des minuteurs en sortie. C'est la partie qui casse, donc
celle qui se teste en `pytest` nu sur les 102 descriptions réelles.

**Piège du dépôt, rappelé une fois :** `Database._lock` n'est pas réentrant.
Deux `db.write()` imbriqués figent sans lever. Les imports du lot 7 prennent
**une seule** transaction chacun et appellent des fonctions `_within(conn, …)`
en dessous, comme `application.py` le fait déjà. Aucun helper de ce lot n'ouvre
sa propre transaction.

## 8. La reprise du stock

C'est la donnée qui doit être **juste au gramme près** le jour de la bascule.
Tout le reste peut se rattraper le lendemain ; un lot manquant se découvre trois
semaines plus tard, quand on cherche un paquet qui n'existe plus.

### 8.1 La requête, et rien de plus

```sql
-- Lue sur la COPIE de grocy.db, en lecture seule (mode=ro), jamais sur la
-- production. Aucun alias `b` : le dépôt interdit `SELECT b.*` par un test qui
-- scanne le littéral, et la meilleure façon de ne pas l'écrire est de ne pas
-- avoir de table aliasée `b`.
SELECT  s.id            AS grocy_stock_id,
        s.product_id    AS grocy_product_id,
        s.amount        AS grocy_amount,
        s.best_before_date,
        s.purchased_date,
        s.row_created_timestamp,
        s.price         AS grocy_price,
        s.open,
        s.opened_date,
        s.location_id   AS grocy_location_id,
        s.note,
        prod.qu_id_stock,
        prod.location_id AS product_default_location
FROM stock AS s
JOIN products AS prod ON prod.id = s.product_id
ORDER BY s.id
```

Côté `home_stock`, la jointure est une résolution par identifiant :

```sql
SELECT p.id AS product_id, p.base_unit, p.external_ref,
       gen.id AS generic_article_id
FROM product AS p
JOIN article AS gen ON gen.product_id = p.id AND gen.is_generic = 1
WHERE p.external_ref IS NOT NULL
```

Un lot dont le `grocy_product_id` n'apparaît pas dans cette table **arrête
l'import**. C'est le seul cas d'arrêt dur du § 8 : après le rejeu du catalogue
il ne doit plus exister, et s'il existe, c'est que quelqu'un a écrit dans Grocy
pendant la bascule — auquel cas rien de ce qui suit n'a de valeur.

Mesuré aujourd'hui : **107 lots sur 108** se résolvent. Le 108ᵉ est le Sorbet
Fraise du § 2.2, que le rejeu fait entrer.

### 8.2 La quantité

`quantity_base = grocy_amount × facteur(unité de stock du produit)`, avec la
**même** table de correspondance que le lot 0 (`grocy/units.py`) — `g`/`kg` → `g`,
`ml`/`cl`/`l` → `ml`, unités de conditionnement → `piece`, facteur 1.

C'est la contrepartie exacte de la règle du lot 0 : « ne jamais convertir un
conditionnement en grammes à l'import, c'est aussi ne jamais avoir à diviser des
calories par un poids net supposé ». Le lot 7 hérite de cette cohérence : parce
que `product.base_unit` a été choisi **à partir de** `qu_id_stock`, la quantité
d'un lot se convertit par le même facteur, et `reference_kcal` (déjà en
kcal/unité de base) reste juste sans reconversion.

**Aucun cas n'échoue** : sur les 107 lots résolus, 0 unité inconnue, 0
divergence entre l'unité du lot et l'unité de base du produit.

Deux cas particuliers, tous deux déjà prévus par le domaine du lot 0 :

- **Poussière flottante.** Le lot #537 (« Fromage fouetté ») porte
  `amount = 5,55 × 10⁻¹⁷`. La règle du lot 0, § 7.2 s'applique **à l'import** :
  sous 0,001 unité de base, le lot entre avec `remaining = 0` et un `closed_at`.
  Il n'est pas ignoré — un lot ignoré serait un écart de comptage au contrôle C1.
- **Pièces fractionnaires.** 18 lots portent une quantité non entière dans une
  unité `piece` : 0,08 concombre, 12,875 œufs, 5,98 paprika. **Aucun arrondi.**
  Un demi-concombre existe, et le lot 0 stocke des `REAL` précisément pour ça.
  L'arrondi est un geste d'affichage, jamais de stockage.

### 8.3 La DLC

| Cas Grocy | Lots | `batch.best_before` |
|---|---:|---|
| Date réelle | 98 | telle quelle, `AAAA-MM-JJ` |
| `2999-12-31` | **10** | **`NULL`** |
| Absente | 0 | — |

`2999-12-31` est la sentinelle « ne périme jamais » de Grocy. La recopier
donnerait dix lots qui périment dans neuf cent soixante-treize ans, en tête de
tous les tris décroissants et en queue de tous les tris croissants. `NULL` est
la façon dont `home_stock` dit « pas de DLC », et le FIFO du lot 0 la classe
déjà (`(best_before IS NULL)` en second critère du `ORDER BY`).

**Six lots ont une DLC déjà dépassée** au 2026-08-21. Ils sont importés tels
quels : ce sont de vrais produits périmés dans un vrai placard, et
`binary_sensor.home_stock_expirations` doit s'allumer dessus le premier jour.
Les masquer serait mentir au propriétaire sur l'état de son frigo.

### 8.4 Le prix — la décision la plus lourde du lot

Rappel du § 3.3 : **7 lots sur 64 portent 8 089 € des 8 140 € du stock.** Les 57
autres pèsent 51 €.

Le relevé des notes de ces sept lots ferme le dossier :

| Lot | Produit du lot | `note` Grocy | Date d'achat |
|---|---|---|---|
| #241 | Paprika moulu | « Ticket Carrefour 21/04/2026 — **Lait bio UHT 6x1L** » | 2026-04-21 |
| #250 | Petits pois | « Ticket Carrefour 21/04/2026 — **Œufs ×12** (CORRIGÉ) » | 2026-04-21 |
| #255 | Blé précuit 500g | « Ticket Carrefour 21/04/2026 — Blé précuit 500g » | 2026-04-21 |
| #256 | Sel | « Ticket Carrefour 21/04/2026 — **Fromage blanc 1kg** (CORRIGÉ) » | 2026-04-21 |
| #257 | Sel | « Ticket Carrefour 21/04/2026 — **Fromage blanc 1kg** (achat 2, CORRIGÉ) » | 2026-04-21 |
| #264 | Ail sémoule 90g | « Ticket Carrefour 21/04/2026 — Ail semoule 90g » | 2026-04-21 |
| #419 | Petits pois | *(aucune)* | 2026-06-08 |

**Six des sept datent du 21 avril 2026**, et quatre portent le nom d'un **autre
produit** que celui auquel le lot est attaché. C'est la même date, et
vraisemblablement le même import de ticket, que celui qui a créé les 35 doublons
d'avril 2026 documentés dans `grocy-off/README.md`. Ce ne sont pas des prix
maladroits : ce sont des lignes de ticket accrochées au mauvais produit, avec le
prix du paquet écrit dans une colonne qui attend un prix par unité de stock, et
la quantité en grammes écrite dans un produit stocké au pot.

**Décision.** Un lot dont `grocy_amount × grocy_price` dépasse **20 €** entre en
stock **avec `price_per_base_unit = NULL`**, et l'import remonte une anomalie
nommée qui cite le produit, la quantité, le prix, la valeur calculée et la note.

**Pourquoi 20 €** : la frontière est un fossé, pas une ligne. Le lot le plus
cher retenu vaut 13,80 € (une brique de lait), le premier écarté en vaut 47.

**Pourquoi `NULL` et pas une correction** : corriger supposerait de deviner
laquelle des trois valeurs est fausse — produit, quantité ou prix — et les notes
montrent que c'est parfois les trois. Règle du lot 0, § 7.4 : « jamais zéro :
zéro voudrait dire *mesuré à zéro*, `NULL` veut dire *inconnu* ». Un prix
inconnu est visible — `sensor.home_stock_stock_value` publie
`unpriced_batches`.

**Ce que ça coûte, chiffré** : `stock_value` annoncera **≈ 51 €** sur 57 lots
valorisés et 50 sans prix. Un chiffre petit et vrai plutôt qu'énorme et faux ;
les prix se remplissent d'eux-mêmes en trois sessions de courses.

**Les 7 lots restent en stock.** Seul leur prix est écarté. Leur *quantité* est
également suspecte (« 1 000 Pot » de sel), mais un lot supprimé est un paquet
qui disparaît du placard sans que personne le voie partir. Le contrôle C4 (§ 16)
les liste nommément et exige un **acquittement explicite** avant l'extinction :
c'est au propriétaire d'aller regarder ses deux pots de sel.

### 8.5 L'emplacement

`batch.location_id` est `NOT NULL`. Chez Grocy, **29 lots sur 108 n'ont pas
d'emplacement résoluble** : 27 avec `location_id IS NULL`, et 2 qui pointent
l'**emplacement id 1, supprimé du référentiel** — exactement le même défaut que
l'unité de stock id 1 supprimée que `debloquer_unites.py` a dû réparer en août.

Cascade, dans cet ordre :

1. l'emplacement du lot Grocy, s'il se résout par son nom ;
2. sinon `product.default_location_id` — **couvre 27 des 29** ;
3. sinon l'emplacement nommé **« Autre »** — **couvre les 2 derniers**
   (« Moutarde Burger Complet » et « Beurre Oméga-3 », tous deux sur l'ancien
   id 1), et chacun est remonté en anomalie non bloquante.

Aucun lot n'est refusé pour cette raison : un paquet mal rangé reste un paquet
qu'on possède.

> **Défaut hérité du lot 0, corrigé ici.** L'import du catalogue mappe
> `location.kind` sur `'freezer' if row["is_freezer"] else 'pantry'`. Grocy n'a
> pas de drapeau « réfrigérateur » : **« Frigo » est donc enregistré en
> `pantry`** dans la base de production. La colonne n'est lue par aucun code
> aujourd'hui, mais c'est une donnée fausse, et elle le restera d'autant plus
> longtemps que rien ne la lit. L'import du stock la corrige **par nom exact**
> (`Frigo` → `fridge`), une seule ligne, et le rapporte. Aucun autre nom n'est
> deviné.

### 8.6 L'ouverture

`stock.open = 1` → `batch.opened_at`. Un seul lot est concerné. `opened_date`
est vide même sur celui-là : `opened_at` prend alors `entered_at`, ce qui rend
vrai « ce paquet est ouvert » sans inventer une date d'ouverture précise.

**Aucun recalcul de `best_before` à l'import.** La règle du lot 0, § 7.6 (avancer
la DLC de `days_after_opening` jours) s'applique **au geste d'ouverture**, pas à
la constatation qu'un paquet est déjà ouvert depuis six mois. L'appliquer ici
donnerait une DLC calculée depuis une date d'entrée, ce qui est faux dans les
deux sens.

### 8.7 Le mouvement d'entrée — et pourquoi il ne fait sauter aucun compteur

Chaque lot importé écrit **un** mouvement :

```python
repo.insert_movement(
    conn,
    occurred_at=entered_at,               # purchased_date, sinon row_created_timestamp
    product_id=product_id,
    article_id=generic_article_id,
    batch_id=batch_id,
    quantity=+quantity_base,
    reason=REASON_PURCHASE,
    base_unit=base_unit,
    kcal=None, cost=None,                 # § ci-dessous
    idempotency_key=f"grocy:stock:{grocy_stock_id}",
)
```

**Pourquoi un mouvement.** Le lot 0, § 12 pose que « le journal étant en ajout
seul, il suffit à tout reconstruire ». Cent sept lots apparus sans une ligne de
journal casseraient cet invariant : la base ne saurait plus dire d'où vient son
stock. `home_stock.export_journal` cesserait d'être un filet.

**Pourquoi ça ne fausse rien.** `repo.totals_between()` — source unique de
`kcal_total`, `cost_total` et `cost_waste_total` — ne somme que
`reason = 'consumption'` (et les motifs de gaspillage pour `waste_cost`). Un
`purchase` n'y entre jamais : les 107 mouvements d'entrée sont **rigoureusement
neutres** sur les trois cumuls et sur les onze capteurs du jour. Vérifié dans le
code, pas supposé — c'est le même mécanisme qui interdit la réinjection de
l'historique au § 9.

`kcal` et `cost` restent `NULL` : aucun capteur ne les lit sur une entrée, et un
chiffre que personne ne lit finit par être cru.

`idempotency_key` porte la contrainte `UNIQUE` de la table `movement` : un
second passage de l'import lève `sqlite3.IntegrityError` sur le premier lot déjà
importé, ce qui est exactement le comportement voulu — il se rattrape par le
`external_ref` du § 6, testé avant l'insertion.

### 8.8 Rejouabilité

L'import est **en simulation par défaut** (`apply: false`), comme
`import_grocy_catalog` depuis le lot 0 et `import_grocy_equipment` depuis le
lot 5. En simulation, il parcourt tout, calcule tout, remonte toutes les
anomalies, puis `rollback()`.

Un lot déjà importé se reconnaît à `batch.external_ref = 'grocy:stock:<id>'` et
est **sauté**, pas réécrit : `remaining` a pu bouger depuis (on a mangé), et un
import qui remettrait `remaining = initial` défferait une consommation réelle
sans laisser de trace. Deux passages successifs ne changent donc rien — la même
propriété que le lot 0 exige de son import de catalogue, et qu'un test épingle.

## 9. L'historique : ce qu'on en fait, et surtout ce qu'on n'en fait pas

### 9.1 La décision

**Les 1 123 lignes de `stock_log` ne sont pas réinjectées dans `movement`.**
Elles sont **archivées** (§ 9.3).

Ce n'est pas une facilité. C'est la seule option qui ne produise pas des graphes
faux, et voici les quatre raisons, dans l'ordre où elles tuent l'idée.

### 9.2 Pourquoi

**1. Les valeurs sont fausses d'un facteur trente.** Les 387 sorties non
annulées, multipliées par les calories du catalogue (déjà par unité de stock,
donc directement utilisables), donnent **2 804 847 kcal sur 35 journées** :

| | |
|---|---:|
| Médiane | 867 kcal/jour |
| Moyenne | 80 138 kcal/jour |
| Maximum, le **2026-08-17** | **2 556 904 kcal** |
| Journées dans une fourchette plausible (1 200–3 500) | **6 sur 35** |

Les mêmes défauts d'unité qu'au § 8.4 sont dans le journal : « 1 000 Pot » de
sel consommés comptent mille pots. Corriger ces lignes demanderait le même
arbitrage produit par produit qu'au § 8.4, mais sur 387 lignes au lieu de 7, et
sur des paquets qu'on ne peut plus aller regarder dans le placard puisqu'ils
sont mangés.

**2. La couverture est de 20 %.** 37 journées portent une consommation sur les
**187 jours** écoulés depuis le 2026-02-16 : un graphe montrerait 150 journées à
zéro. « Zéro kcal » se lit « n'a rien mangé », pas « n'a rien saisi » — c'est
l'ambiguïté que le lot 2 a passé un lot entier à éviter avec
`unvalued_movements`.

**3. L'heure est celle de la saisie, pas celle du repas.** Répartition horaire
des 391 sorties : **131 à 10 h**, 56 à 19 h, 55 à 20 h, 49 à 12 h. Une saisie en
rafale à dix heures du matin n'est pas un petit déjeuner de 131 aliments. Or
`used_date` est une **date sans heure** et la journée alimentaire du lot 2 court
de **4 h à 4 h** : imputer une sortie sans heure à une journée demanderait une
convention, qui serait une invention invisible dans les graphes.

**4. Trois compteurs sauteraient d'un bloc.** `kcal_total`, `cost_total` et
`cost_waste_total` lisent `repo.totals_between(conn)` **sans bornes** : la somme
de tout le journal. Injecter 353 sorties chiffrées les ferait monter de
**2,8 millions de kcal en un rafraîchissement de coordinateur**. Depuis le lot 4
ils sont `state_class: TOTAL` : Home Assistant enregistrerait honnêtement la
marche d'escalier dans ses statistiques long terme, pour toujours, sans moyen de
la distinguer d'une vraie consommation. Et le journal étant en **ajout seul**,
la reprendre demanderait 353 contrepassations — un `DELETE` est refusé par
trigger.

Le coût ne serait même pas calculable : **188 des 353 sorties n'ont aucun prix**
(53 %).

**Ce qu'on abandonne, nommément** : 387 sorties, 475 entrées, 174 corrections
d'inventaire et 11 ouvertures, du 2026-02-16 au 2026-08-21. La comptabilité
kcal/€ de `home_stock` commence donc **le jour de la bascule**, et le
`docs/exploitation.md` le dit en toutes lettres pour que personne ne cherche
pourquoi les graphes sont vides avant.

### 9.3 Ce qu'on garde quand même

Rien n'est jeté ; ce n'est simplement pas versé dans la comptabilité.

1. **`grocy.db` en entier**, sauvegardé et conservé (§ 19).
2. **Un export daté**, produit par le service de contrôle :
   `config/home_stock_grocy_archive_<AAAA-MM-JJ>.json` — les 1 123 lignes de
   `stock_log` jointes à leur nom de produit (les six `undone = 1` avec leur
   drapeau : une annulation fait partie de l'histoire), les 25 notes de lots du
   § 8.4, les 39 pointages de `chores_log`, les 66 entrées de planning passées.

JSON et pas SQLite : l'archive doit se lire dans dix ans, sur une machine qui
n'aura plus le schéma de Grocy 4.6 en tête. Écrite **dans `config/`**, donc
emportée par les sauvegardes natives de Home Assistant.

## 10. La reprise des recettes

### 10.1 Amendement au lot 3, § 18 : **il y a 102 recettes, pas 87**

Le lot 3 écrit :

> La base contient aussi 15 `mealplan-week`, 65 `mealplan-day`, 90
> `mealplan-shadow` **et 15 de type `1`** : ce sont les copies fantômes que le
> README de `grocy-off` décrit.

**Les 15 recettes de type `1` ne sont pas des copies fantômes.** Ce sont de
vraies recettes, créées **le 2026-06-27 entre 18 h 45 et 18 h 55** par un outil
qui a écrit `type = 1` au lieu de `type = 'normal'` :

> Salade de lentilles fraîche · Bowl protéiné fromage blanc · Taboulé quinoa
> été · Wrap houmous légumes crus · Omelette courgette légère · Salade pois
> chiches méditerranéenne · Gaspacho andalou · Bowl pois chiches rôtis
> cumin-courgette · Salade lentilles-herbes de Provence · Courgettes crues
> râpées parmesan-menthe · Omelette aux herbes et chèvre · Salade
> pêches-roquette-chèvre · Salade grecque classique · Riz sauté
> courgette-tomates-herbes · Bowl riz-edamame-œufs soja

Elles portent **96 lignes d'ingrédients**, toutes avec un produit et un
`variable_amount`, et **10 entrées de planning** les référencent. Un
`WHERE type = 'normal'` strict, tel que le lot 3 le prescrit, perdrait
**15 recettes et 96 lignes en silence** — exactement le genre de perte que ce
lot existe pour empêcher.

Le filtre correct est donc :

```sql
WHERE r.type IN ('normal', '1')
```

et il laisse dehors les **166 vraies copies fantômes** : 86 `mealplan-shadow`,
65 `mealplan-day`, 15 `mealplan-week`, toutes à identifiant **négatif** et
toutes générées par les triggers `create_internal_recipe`,
`update_internal_recipe` et `remove_internal_recipe` de la table `meal_plan`.

Deux conséquences mécaniques, à écrire dans les tests :

- **200 lignes de `recipes_pos` sont orphelines** : leur `recipe_id` ne
  correspond à aucune ligne de `recipes`. Ce sont les résidus des recettes du
  jour et de la semaine supprimées par les triggers. Un `LEFT JOIN` les
  ramènerait ; le `JOIN` du filtre ci-dessus les écarte.
- **`recipes_nestings` compte 5 651 lignes**, presque toutes produites par ces
  mêmes triggers. Abandonnée, décision reprise du lot 3, § 20.

**Décompte final : 102 recettes, 510 lignes d'ingrédients.**

### 10.2 La correspondance, ligne à ligne

| Grocy | `home_stock` | Comment |
|---|---|---|
| `recipes.id` | `recipe.source = 'grocy'`, `recipe.source_ref = <id>`, `recipe.external_ref = <id>` | `idx_recipe_source` (unique partiel) rend l'import rejouable |
| `recipes.name` | `recipe.name` | Direct |
| `recipes.base_servings` | `recipe.servings` | Direct. **63 des 87 `normal` valent 1** ; bornes 1 à 8 ; toutes entières, la contrainte `CHECK (servings >= 1)` passe |
| `recipes.description` (HTML) | `recipe.summary`, `total_minutes`, `utensils`, `recipe_step`, `recipe_instruction` | § 10.3 |
| `recipes.picture_file_name` | — | **NULL sur les 102.** Les images sont dans le HTML (§ 11) |
| `recipes_pos.id` | `recipe_ingredient.external_ref` | — |
| `recipes_pos.product_id` | `recipe_ingredient.product_id` | **Par `product.external_ref`**, jamais par nom |
| `recipes_pos.amount` + `qu_id` | `recipe_ingredient.amount` | § 10.4 |
| `recipes_pos.variable_amount` | `recipe_ingredient.raw_text` | **Provenance uniquement**, jamais une seconde quantité |
| `recipes_pos.ingredient_group` | `recipe_ingredient.group_name` | **Vide sur les 510 lignes.** La colonne reste `NULL` ; la ligne du lot 3, § 18 est sans objet |
| `recipes_pos.not_check_stock_fulfillment` | — | 4 lignes. Aucune colonne équivalente ; sans effet sur la validation d'un repas, qui vérifie le stock de toute façon. Non repris, mentionné au rapport |
| — | `recipe.language` | `'fr'`, défaut de la colonne |
| — | `recipe.needs_review` | **`1` sur les 17 recettes réécrites** (41, 43-50, 96-103) dont `grocy-off/README.md` dit que « les étapes, les titres, les durées de minuteur et les ustensiles sont **inventés** ». C'est précisément ce que `needs_review` veut dire |
| — | `recipe.created_at` | `recipes.row_created_timestamp` |
| — | `recipe.adapted_at` | `NULL`. Aucun agent n'a adapté ces recettes |

### 10.3 Découper le HTML — la structure réelle, mesurée

Le lot 3, § 18 annonce une découpe « sur les `<div class="page-recipes">` de
premier niveau, `<h3>Étape N — …</h3>` pour le titre, `<ol><li>` pour les
puces ». C'est juste, à une nuance près qui casse une expression régulière
naïve : **les balises portent des attributs de style**. Il n'y a pas un seul
`<h3>` nu dans la base ; il y a 234 `<h3 style="color:#333;">`.

Structure mesurée sur les **87 recettes `normal`** :

| | |
|---:|---|
| **323** | `<div class="page-recipes">` de premier niveau, de 3 à 8 par recette |
| **87** | pages « Ingrédients » (`<h3 …>Ingrédients</h3>` + `<ul>`) — une par recette, exactement |
| **147** | pages d'étape (`<h3 …>Étape N — …</h3>` + `<ol>`) |
| **89** | pages de couverture ou intercalaires |
| **229** | pages portant une `<img>` |
| **415** | `<li>` dans les `<ul>` d'ingrédients (pour 414 lignes de `recipes_pos` : la page Ingrédients est bien un miroir) |
| **468** | `<li>` dans les `<ol>` d'instruction |
| **87** | lignes méta `⏱ … 🔥 … 🍳 …` sur la couverture — une par recette |

Les **15 recettes de type `1`** n'ont **aucune de ces structures** : leur
description est un `<ol><li>…</li></ol>` nu, sans page, sans image, sans bloc
Ingrédients, sans ligne méta. Le découpeur doit donc traiter les deux formes :

```python
# grocy/html.py — pur, sans hass, sans réseau, sans SQLite.
def decouper(description: str) -> list[Page]:
    """Les pages d'une description Grocy.

    Une description SANS `page-recipes` (les 15 recettes de type `1`) rend UNE
    page portant tout le `<ol>`. Rendre zéro page serait une perte silencieuse,
    et c'est la forme que prend une perte silencieuse : un `findall` qui ne
    trouve rien et une boucle qui ne tourne pas.
    """
```

Ce que chaque morceau devient :

| Morceau du HTML | Destination | Règle |
|---|---|---|
| `⏱ 15 min` de la ligne méta | `recipe.total_minutes` | Entier, minutes. Absent → `NULL` |
| `🍳 Poêle + grille-pain` | `recipe.utensils` | Texte, tel quel |
| `🔥 ~450 kcal` | — | **Non repris.** C'est une valeur *calculée* par `recettes_miseenpage.py` depuis le catalogue ; la recalculer chez nous à l'affichage vaut mieux que graver un chiffre daté. Le lot 3, § 20 a déjà différé « nutriments d'une recette avant cuisson » |
| `<p style="color:#555;">…</p>` de la couverture | `recipe.summary` | L'accroche |
| Première `<img>` de la couverture | `recipe.image_url` | § 11 |
| Page « Ingrédients » | — | **Ignorée.** Elle est un rendu de `recipes_pos`, jamais une source. Le README de `grocy-off` le dit : « Le bloc Ingrédients ne s'écrit jamais à la main ». La réimporter serait la deuxième écriture d'une même quantité, encore |
| `<h3 …>Étape N — Titre</h3>` | `recipe_step.title` | Le `N` sert à l'ordre, le titre est ce qui suit le tiret cadratin |
| `<img>` d'une page d'étape | `recipe_step.image_url` | § 11 |
| `<li>` d'un `<ol>` | `recipe_instruction.text` | Balises internes (`<strong>`) **retirées**, texte conservé : « saisir **4 min par face** » devient « saisir 4 min par face ». Le panneau met en forme, la base stocke du texte |
| `#Étiquette:secondes` | `timer_label` + `timer_seconds` | § 10.5 |

**Piège d'entités HTML.** `grocy-off/README.md` le documente pour l'écriture,
il vaut aussi pour la lecture : « Grocy redécode `&#x27;` en `'` à
l'enregistrement ». Le découpeur passe tout texte extrait par
`html.unescape()` **une seule fois** ; un second passage transformerait un
`&amp;lt;` légitime en `<`.

### 10.4 Les quantités — et la 42ᵉ ligne d'huile d'olive, qui n'a jamais été corrigée

Sur les **414 lignes des 87 recettes `normal`** : `0` ligne sans produit, `0`
ligne pointant un produit inactif, **`0` ligne dont `qu_id` diffère du
`qu_id_stock` de son produit**. La conversion est donc la même qu'au § 8.2, avec
le même facteur, et `packaging_id` comme `measure_id` restent `NULL` : il n'y a
rien à exprimer dans une autre mesure.

Sur les **96 lignes des 15 recettes de type `1`**, c'est une autre histoire :

| Défaut | Lignes |
|---|---:|
| `qu_id` ≠ `qu_id_stock` du produit | **23** |
| Produit **inactif** (« Riz basmati (doublon) ») | **2** |

Les 23 lignes sont **le défaut que le README de `grocy-off` décrit** — « 42
lignes portaient l'unité de conditionnement (`1.5 Bouteille` d'huile d'olive)
alors que le nombre était déjà en cl » — jamais corrigé sur ces quinze recettes,
parce que `recettes_ingredients.py` filtre sur `type = 'normal'`. **Treize
disent « 1 Bouteille » d'huile d'olive quand `variable_amount` dit « 1 cs »** :
importées telles quelles, elles retireraient 750 ml d'huile du stock pour une
cuillère à soupe, à chaque repas validé. Le grief n° 2 du lot 0, encore vivant,
dans la donnée.

**Décision.** Une ligne dont `qu_id` diffère du `qu_id_stock` de son produit
entre avec :

```
amount        = NULL          -- la quantité est inconnue, pas nulle
product_id    = <résolu>      -- le produit, lui, est certain
match_state   = 'unmatched'
raw_text      = variable_amount   -- « 1 cs », lisible, provenance
```

et est **citée nommément** dans le rapport, avec sa recette, son produit, la
quantité Grocy, les deux unités et le `variable_amount`. Le `CHECK` de `m004`
l'autorise : seuls `auto` et `confirmed` exigent un `product_id`, `unmatched`
peut en porter un.

**On ne lit pas `variable_amount` pour retrouver la quantité.** « 1 cs » se
résoudrait pourtant contre `culinary_measure` (semée par `m004`). Refusé :
règle du lot 3, § 18 — `variable_amount` est de la **provenance**, « jamais
réimporté comme seconde quantité, il ne revient pas par la porte de derrière ».
Vingt-cinq lignes se corrigent à la main en dix minutes sur l'écran
d'appariement du lot 3 ; un analyseur se corrigerait pendant des années.

Les 2 lignes sur « Riz basmati (doublon) » n'ont **pas** de produit : le doublon
est désactivé chez Grocy et n'a donc pas été importé au lot 0. Elles entrent
avec `product_id = NULL`, `amount = NULL`, `match_state = 'unmatched'`,
`raw_text` conservé, et le rapport nomme le produit actif qui leur correspond
(« Riz Basmati »). C'est un appariement que seul un humain peut signer.

**`match_state` des 485 autres lignes : `'confirmed'`.** Le lot 3 réserve
`'auto'` à un appariement deviné et scoré. Ici rien n'est deviné : le produit
vient d'un identifiant. `match_score` reste `NULL` — il n'y a pas de score, et
écrire `1.0` laisserait croire qu'un algorithme a été très sûr de lui.

**`raw_text` est `NOT NULL`**, et **56 lignes n'ont pas de `variable_amount`**.
Pour celles-là il est composé mécaniquement — `f"{amount:g} {unité}"`, « 500 g »,
« 2 Pièce » : le même nombre dans la même unité, ce que la source disait.

### 10.5 Les minuteurs — 116, dont 8 qui ne rentrent pas dans le modèle

`recipe_instruction` (`m004`) porte **au plus un** minuteur par puce, et sa
contrainte est stricte : `CHECK ((timer_label IS NULL) = (timer_seconds IS NULL))`.

Relevé sur les 553 puces d'instruction (468 dans les 87 `normal`, 85 dans les 15
de type `1`) :

| | |
|---:|---|
| **116** | minuteurs `#Étiquette:secondes`, tous dans les recettes `normal` |
| 445 | puces sans minuteur |
| 100 | puces à un minuteur |
| **8** | puces à **deux** minuteurs |
| 25 s / 3 600 s | durée minimale / maximale |

**Deux pièges de forme**, tous deux vérifiés sur la base :

1. **L'étiquette contient des espaces.** Le lot 3 et le README écrivent
   `#Nom:secondes` ; la réalité est `#Repos poulet:600`, `#Cabillaud face 1:180`,
   `#Airfryer légumes:1050`. Un motif `#(\S+):(\d+)` coupe l'étiquette au premier
   espace et perd la moitié du libellé.
2. **Les couleurs CSS ressemblent à des minuteurs.** Les 102 descriptions
   contiennent **443 caractères `#`, dont 327 sont des couleurs**
   (`color:#333;`, `#555`, `#888`). Un motif trop lâche transforme
   `style="color:#888;font-size:12px"` en un minuteur intitulé « 888;font-size »
   de 12 secondes — c'est arrivé pendant l'analyse de cette spec, sur la
   première expression essayée. Le motif retenu interdit `#`, `:`, `;`, `<` et
   `>` dans l'étiquette :

```python
TIMER = re.compile(r"#([^#:;<>]{1,40}?):(\d{1,5})\b")
```

**Les 8 puces à deux minuteurs** sont toutes des cuissons à deux faces —
recette 1 : « Poêle à feu vif, saisir 4 min par face. `#Poulet face 1:240`
`#Poulet face 2:240` », et de même pour le cabillaud (×2), les crêpes, le steak,
la dinde et deux fois le poulet.

**Décision : la puce est scindée en deux instructions.** La première garde le
texte de la phrase et son premier minuteur ; la seconde porte le **libellé du
second minuteur comme texte** (« Poulet face 2 ») et ce minuteur. Rien n'est
inventé — le texte de la seconde puce est une chaîne qui existe déjà dans la
source — et **aucun minuteur n'est perdu**. Les 8 cas sont listés dans le
rapport, par recette et par libellé, pour être relus.

Les trois options écartées, et pourquoi :

| Option | Refusée parce que |
|---|---|
| Garder le premier minuteur, laisser le second dans le texte | Perte silencieuse de 8 minuteurs. C'est précisément ce que ce lot refuse |
| Ajouter une table `recipe_timer` en `m008` | Change le contrat de la vue cuisine du lot 3 (`timer_label`/`timer_seconds` sur la puce), donc le front, ses tests et son vérificateur — pour 8 puces sur 553 |
| Fusionner les deux durées en une (480 s) | Faux : on retourne le poulet entre les deux |

Le motif exigeant les deux, une puce à libellé sans durée (ou l'inverse) ne
peut pas naître : le `CHECK` de `m004` tient sans effort.

### 10.6 Ce que ça donne

| | Total |
|---|---:|
| `recipe` | **102** |
| `recipe_step` | **338** (323 pages moins 87 blocs Ingrédients, plus une page par recette de type `1`, plus les couvertures qui portent une image d'étape) |
| `recipe_instruction` | **561** (553 puces, plus les 8 dédoublements du § 10.5) |
| `recipe_ingredient` | **510**, dont **25 en `unmatched`** à arbitrer |
| Minuteurs | **116** |

## 11. Les images — la question se pose une fois, pour les deux

Le lot 0 avait prévu « une vue HTTP pour les images d'articles » ; elle n'a
jamais été écrite. Le lot 3, § 20 a différé le rapatriement des images de
recettes en notant que « la question se pose une fois, pour les deux, au moment
où Grocy s'éteint ». Nous y sommes.

### 11.1 Le composant n'écrit aucune vue HTTP

Depuis le lot 4, la règle est posée et le code la respecte : le téléversement
d'un ticket passe par `/api/media_source/local_source/upload`, **fourni par Home
Assistant**, et `frontend/src/connexion.ts` le commente en toutes lettres — « Le
composant n'écrit AUCUNE vue HTTP : celle-ci est fournie par Home Assistant,
plafonne à 20 Mo, refuse ce qui n'est pas une image, et exige un compte
administrateur ». Le lot 5 ajoute la moitié manquante : `receipt_media_id` est un
« chemin sous `media/`, jamais sous `www/` ».

**Décision : les images vont sous `media/`, et le lot 7 n'écrit pas de vue
HTTP.**

```
config/media/home_stock/recipes/<nom de fichier>
config/media/home_stock/articles/<code-barres>.jpg
```

`recipe.image_url`, `recipe_step.image_url` et `article.image` stockent un
identifiant `media-source://media_source/local/…` — le même vocabulaire que
`receipt.media_content_id`. Le panneau le résout par la commande websocket
**native** `media_source/resolve_media`, qui rend un chemin signé : aucune vue
de plus, aucun jeton manipulé à la main, et une image de recette n'est pas
lisible par le premier navigateur du réseau.

Écartées : **`config/www/`** (servi *sans authentification* à tout le réseau —
le lot 5 a tranché « jamais sous `www/` ») ; **une vue HTTP du composant** (le
`http.py` du lot 0 : écrire, authentifier et tester ce que Home Assistant
fournit déjà, et dont personne n'a eu besoin en six lots) ; **les data-URI en
base** (3,48 Mo de base64 relus à chaque ouverture — le README de `grocy-off` a
fait marche arrière là-dessus) ; **laisser les URL Grocy** (c'est tout le
problème).

### 11.2 Qui copie quoi, et qui ne copie rien

| Famille | Références | Décision | Qui fait le geste |
|---|---:|---|---|
| `data:image/jpeg;base64,…` dans le HTML | **62** (3,48 Mo, dans 27 recettes) | **Décodées et écrites en fichiers** sous `media/home_stock/recipes/` | L'import : la donnée est dans la base qu'il lit déjà |
| `grocy.allanic.me/api/files/recipepictures/<base64>` | **55** | **Fichiers copiés** puis URL réécrites | **Le propriétaire**, par un `cp` de la séquence (§ 18, étape 3) |
| `productpictures/` | **33** (29 sur des produits actifs) | **Fichiers copiés**, `article.image` renseigné | Idem |
| `images.unsplash.com/photo-…` | **112** (46 distinctes) | **Laissées telles quelles** | Personne |

**Pourquoi Unsplash reste dehors.** Le critère est « est-ce que ça meurt avec le
conteneur ? ». Unsplash n'en dépend pas. C'est la dette que le lot 3 a déjà
assumée pour `strMealThumb` de TheMealDB ; la traiter autrement ici créerait
deux règles pour un même problème. Inscrite au § 21 avec son chiffre : 46
images, 112 emplacements.

**Pourquoi le propriétaire copie les fichiers.** Le conteneur Home Assistant ne
monte que `config/` et `media/` : il **ne voit pas**
`/opt/nivuus/Grocy/config/data/storage/`. C'est déjà pour cette raison que
`exploitation.md` fait copier `grocy.db` dans `config/`. Deux `cp` de plus, et
le composant reste dans sa boîte.

### 11.3 La réécriture des URL

Le nom de fichier se lit dans l'URL Grocy : c'est du **base64 du nom**, sans
clé d'API. `cmVjZXR0ZS00MS0wLmpwZw==` → `recette-41-0.jpg`. Le décodage est fait
par l'import, jamais recopié à la main, et un nom qui ne se décode pas est une
anomalie nommée, jamais un fichier ignoré.

Réconciliation exigée **avant** l'écriture, dans les deux sens :

- **toute référence doit avoir son fichier** — 0 manquante aujourd'hui ;
- tout fichier sans référence est signalé sans bloquer — 1 aujourd'hui,
  `test.jpg`, qui n'est pas copié.

Les 62 data-URI sont écrites sous un nom déterministe,
`recette-<id>-inline-<n>.jpg`, où `n` est le rang de l'image dans la
description. Déterministe pour que le rejeu réécrive le même fichier au lieu
d'en accumuler un nouveau par passage — la même exigence que l'idempotence du
§ 8.8, appliquée au système de fichiers.

Poids final sous `media/home_stock/` : **≈ 6,5 Mo** (3,9 Mo de
`recipepictures`, ≈ 2,6 Mo de data-URI décodées, 1,2 Mo de `productpictures`).
Cela entre dans les sauvegardes natives de Home Assistant, comme le reste.

## 12. Le planning : l'avenir, et rien que l'avenir

`meal_plan` compte **108 entrées** du 2026-03-20 au 2026-08-31 : 88 recettes et
20 notes. **42 sont à venir** (jour ≥ le jour de la bascule).

**Décision : seules les 42 entrées à venir sont reprises.** Les 66 passées sont
abandonnées, pour une raison qui n'admet pas de milieu :

- les importer avec `state = 'done'` affirmerait des repas validés — or valider
  un repas, au lot 3, **écrit des mouvements**. Il n'y en aurait aucun derrière :
  un repas `done` sans mouvement est un mensonge dans une base dont le journal
  est la seule source de vérité ;
- les importer `planned` peuplerait le calendrier de 66 repas à cuisiner dans le
  passé, et `sensor.home_stock_next_meal` irait les chercher.

Le contenu de ces 66 entrées part dans l'archive du § 9.3.

Cette décision **referme d'elle-même** le seul problème de correspondance du
planning. `meal_plan_sections` contient une quatrième ligne, **`id = -1`, sans
nom** : c'est le « sans section » de Grocy, et `m004` ne l'a pas semée (les
créneaux portent les `external_ref` `1`, `2`, `3`, plus `snack` sans référence).
**30 entrées de planning l'utilisent — et les 30 sont dans le passé.** Les 42
entrées à venir se répartissent proprement :

| Section Grocy | `meal_slot.key` | Entrées à venir |
|---|---|---:|
| 1 — Petit-déjeuner | `breakfast` | 12 (11 recettes, 1 note) |
| 2 — Déjeuner | `lunch` | 19 (18 recettes, 1 note) |
| 3 — Dîner | `dinner` | 11 recettes |
| −1 — sans section | — | **0** |

La correspondance :

| Grocy | `home_stock` |
|---|---|
| `meal_plan.day` | `meal.day` — même date ; c'est déjà une journée alimentaire au sens du lot 2 pour un repas planifié |
| `meal_plan.section_id` | `meal.slot_key`, par `meal_slot.external_ref` |
| `meal_plan.recipe_id` | `meal.recipe_id`, par `recipe.source_ref` |
| `meal_plan.recipe_servings` | `meal.servings` — **valeurs non entières présentes** (0,15 ; 0,2 ; 0,25 sur 10 entrées). `meal.servings` est un `REAL` avec `CHECK (servings > 0)` : elles passent telles quelles |
| `meal_plan.note` | `meal.note` |
| `meal_plan.done` | **ignoré** — voir ci-dessus |
| `meal_plan.type = 'product'` | sans objet : **0 ligne** dans la base |
| — | `meal.state = 'planned'` pour les 42 |
| — | `meal.uid = f"grocy-meal-{id}@home_stock"` — `UNIQUE`, donc l'idempotence du planning est gratuite |
| — | `meal.external_ref = <id Grocy>` |

Les 42 entrées référencent **23 recettes distinctes, toutes `normal`** : aucune
ne pointe une copie fantôme, aucune ne pointe une recette de type `1`. Une
entrée pointant une recette absente **arrête l'import du planning** — le
planning se réimporte en dix secondes, une entrée orpheline se découvre au dîner.

## 13. Conversions, liste de courses

### 13.1 14 conversions deviennent des `packaging` — une dette du lot 0 qui se referme

Le lot 0 a délibérément renoncé à créer des `packaging` à l'import :

> **Reporté au lot 1** : cette règle prévoyait aussi de créer une ligne
> `packaging` portant le poids net « quand OFF ou le nom du produit le
> donnent ». L'import ne le fait pas, et c'est délibéré. […] Le poids net
> viendra d'Open Food Facts au lot 1, via `product_quantity`, qui est une mesure
> et non une devinette. `repo.insert_packaging` existe déjà et l'attend.

`quantity_unit_conversions` contient **30 lignes**, soit **15 paires**
aller-retour saisies **à la main** par le propriétaire. Ce ne sont pas des
devinettes : ce sont des mesures, exactement au même titre que
`product_quantity` d'Open Food Facts.

| Produits | Conversion Grocy | `packaging` |
|---|---|---|
| Huile d'olive, Vinaigre blanc, Vin blanc (cuisson) | 1 Bouteille = 75 cl | « Bouteille » = **750 ml** |
| Jus de mangue passion, Lait demi-écrémé | 1 Bouteille = 100 cl | 1 000 ml |
| Ketchup / Vinaigrette Sésame-Soja | 1 Bouteille = 50 / 36 cl | 500 / 360 ml |
| Sauce Soja sucrée, Jus de citron, Vinaigre de riz | 1 Bouteille = 25 cl | 250 ml |
| Crème de soja / Sauce nuoc mam / Sauce Worcestershire | 1 Brique ou Bouteille = 20 / 20 / 15 cl | 200 / 200 / 150 ml |
| Houmous bio Pascalou 160g | 1 Pièce = 160 g | « Pièce » = **160 g** |
| ~~Yaourt aux fruits~~ | 1 Lot = 1 Pot | **écartée** : `Lot` et `Pot` deviennent tous deux `piece`, facteur 1, no-op |

Règle : on ne retient que le sens **conditionnement → unité de base du produit**
(le sens inverse est le même fait écrit deux fois), et seulement quand l'unité
d'arrivée se convertit vers `product.base_unit`. `scope = 'product'`,
`target_id = product.id`, `is_purchase_default = 1`. Une ligne déjà présente
(même `scope`, même cible, même nom) n'est **pas** réécrite : le lot 1 a pu en
créer depuis Open Food Facts, et une mesure d'emballage vaut mieux qu'une
conversion de 2026.

Ces 14 lignes sont un vrai gain : à partir d'elles, `home_stock` sait qu'une
bouteille d'huile fait 750 ml, donc que « 1 cs » n'en est pas une — ce qui est
la moitié du § 10.4.

### 13.2 Les 9 lignes de courses ouvertes

25 lignes dans `shopping_list`, **16 cochées** (`done = 1`) et **9 ouvertes**.
Les 16 cochées sont des courses faites : abandonnées.

Les 9 ouvertes entrent dans `shopping_list_item` (lot 4) avec, pour chacune, une
`shopping_list_claim` d'origine **`manual`** — leur origine réelle est
inconnaissable, et `manual` est la seule des quatre qui ne prétende rien.

```
product_id  ← product.external_ref
quantity    ← amount × facteur(unité de la ligne)
note        ← shopping_list.note            (3 des 9 en ont une)
added_at    ← shopping_list.row_created_timestamp
```

Les 9 produits sont actifs, aucun doublon de produit — l'index unique
`idx_list_open_product` (au plus une ligne ouverte par produit) passe sans
arbitrage. Une seule ligne a une unité de liste différente de l'unité de stock
(« Cerneaux de noix », `Sachet` contre `Paquet`) : les deux deviennent `piece`,
facteur 1, aucune conversion. Les trois notes sont des prescriptions
médicamenteuses ; elles voyagent telles quelles, dans une colonne qui est faite
pour ça.

Aucune `shopping_session`, aucun `store` : `shopping_locations` est **vide**
chez Grocy. Rien à reprendre, et donc rien pour amorcer l'ordre des rayons du
lot 4 — il s'apprendra à la première vraie session.

## 14. Piles, équipements, corvées

### 14.1 Déjà couvert par le lot 5 — le lot 7 vérifie, il ne refait pas

`import_grocy_equipment` (lot 5) reprend `batteries` (**26**) et `equipment`
(**34**), et fait davantage : il rejoue une dernière fois les heuristiques du
bloc 3 de `maintenance.jinja` pour que la première réconciliation après la
bascule produise **exactement** les mêmes résumés que la dernière d'avant.

Le lot 7 n'y touche pas. Il ajoute **un contrôle** (C7, § 16) : `battery` et
`equipment` non vides, et `summary_diff` vide. Un import d'équipements non fait
avant l'application du raccord ferait **disparaître** les tâches de pile au lieu
de les déplacer — c'est écrit dans `docs/raccord/README.md`, étape 2, et c'est
la seule dépendance d'ordre du lot 5 vers le lot 7.

`battery_charge_cycles` est vide (0 ligne) : rien à reprendre, et
`battery_event` restera donc sans historique de charge. Assumé.

### 14.2 Les 6 corvées — le trou de la feuille de route se referme sur un abandon

Le lot 5, § 18 le posait ainsi :

> **Les 6 *chores* Grocy** (litière, fontaine, croquettes, poubelles) — à
> trancher au lot 7. […] **C'est un trou de la feuille de route, pas un choix.**

Voici le choix. **Elles ne sont pas reprises.**

| | |
|---|---|
| Les six | Nettoyer la litière · Nettoyer la fontaine à eau · Nettoyer le distributeur de croquettes · Remplir les croquettes · Vider les poubelles · Vider complètement la litière |
| Périodicité | `daily`, toutes les six |
| Pointages en six mois | **39** |
| Attendu si suivies | 6 × 187 = 1 122 |
| **Taux de suivi** | **3,5 %** |

Trois raisons :

1. **Elles ne sont pas utilisées.** 3,5 % de suivi sur six mois se mesure.
   Reconstruire un mécanisme périodique pour ça, c'est travailler pour un usage
   qui n'existe pas.
2. **Elles ne sont pas du garde-manger.** Une litière n'a ni produit, ni lot, ni
   DLC, ni prix : rien dans les huit migrations ne l'accueille, et l'y forcer
   déformerait le modèle.
3. **`todo.maintenance` est conditionnel, pas périodique.** Toute sa mécanique —
   `items`/`keep`, l'hystérésis, « jamais de fermeture sur un capteur
   indisponible » — repose sur une **condition mesurée**. Une corvée quotidienne
   a un calendrier, pas une condition.

**Le chemin de repli, si le propriétaire les veut**, tient en trois lignes et
n'appartient pas à `home_stock` : une liste `local_todo` et une automation
quotidienne qui y remet les six lignes. Il est **écrit dans
`docs/exploitation.md`**, pas dans le composant. Les 39 pointages partent dans
l'archive du § 9.3.

## 15. Surface Home Assistant

### 15.1 Trois services de plus

Tous **en simulation par défaut**, tous à réponse (`SupportsResponse.ONLY`),
tous journalisés, comme `import_grocy_catalog` depuis le lot 0.

| Service | Paramètres | Rend |
|---|---|---|
| `home_stock.import_grocy_stock` | `database_path` (défaut `grocy_import.db`), `apply` (défaut `false`) | lots, mouvements, `packaging`, lignes de courses, anomalies, `ok` |
| `home_stock.import_grocy_recipes` | `database_path`, `picture_dir` (défaut `media/home_stock`), `apply` | recettes, étapes, instructions, ingrédients, images écrites, repas, anomalies, `ok` |
| `home_stock.check_grocy_migration` | `database_path`, `archive` (défaut `true`) | les onze contrôles du § 16, `blocking`, `ok` |

Les chemins sont résolus par `hass.config.path()` — le composant ne lit **jamais
en dehors de `config/`**, et c'est ce qui rend la copie de `grocy.db` dans
`config/` obligatoire (elle l'est déjà pour l'import du catalogue).

Les validateurs (`database_path` non vide et sans `..`, `picture_dir` sous
`media/`) vivent dans `validators.py`, **une seule fois**.

### 15.2 Une commande websocket, et une seule

`home_stock/migration/check` — même schéma, même code, même réponse que
`home_stock.check_grocy_migration`. Les deux surfaces lisent **la même** constante
de schéma : aucune des deux n'a le droit d'être la plus faible, règle du lot 4
reprise telle quelle, et `test_surface_parity.py` la tient.

**Les deux imports n'ont pas de jumeau websocket**, et c'est un choix inscrit,
pas un oubli — même asymétrie que `import_grocy_catalog`,
`import_grocy_equipment` et `resync_off` : un import de masse se lance depuis
Outils de développement, une fois, en lisant son rapport en entier. Le
**contrôle**, lui, se relance vingt fois pendant la bascule, une main dans le
placard et l'autre sur le téléphone : il lui faut le panneau.

### 15.3 Un bloc dans l'écran Réglages, pas un écran de plus

`frontend/src/ecrans/reglages.ts` existe et appelle déjà un service
(`home_stock.resync_off`). Il gagne un bloc **« Bascule »** : un bouton
« Contrôler », les onze lignes du § 16 avec leur écart, et les anomalies
bloquantes en rouge. Rien d'autre — pas de bouton « Importer », pas de bouton
« Éteindre Grocy ». Le panneau **montre** l'état de la bascule ; il ne la
conduit pas.

Contraintes de rendu inchangées : 412 px de large, cibles ≥ 44 px, contraste
≥ 5:1, vérifiées par `node outils/verifier-rendu.mjs`.

### 15.4 Aucune entité nouvelle

La bascule est un événement, pas un état. Un `binary_sensor.home_stock_migration_ok`
resterait `on` pour toujours après le premier passage et n'apprendrait plus rien
à personne. Le rapport est une réponse de service.

## 16. Les contrôles de bascule — le cœur du lot

> **La leçon du lot 6, citée pour qu'elle ne se reperde pas.** Son vérificateur
> ouvrait les pages contre l'instance réelle ; les commandes websocket
> n'existaient pas encore, « il mesure un écran vide et déclare que tout va
> bien ». **Un contrôle qui passe à vide est pire que pas de contrôle** : il
> transforme une absence de donnée en preuve de succès.

Chaque contrôle ci-dessous porte donc **un plancher** : un seuil en dessous
duquel il échoue *parce qu'il n'a rien mesuré*, indépendamment de tout écart.
Un contrôle qui compare 0 à 0 est **rouge**, jamais vert.

### 16.1 Les onze contrôles, dans l'ordre

`home_stock.check_grocy_migration` lit **les deux bases** et rend, pour chacun :
le compte Grocy, le compte `home_stock`, l'écart, le verdict, et la liste
nommée des écarts (plafonnée à 50 entrées, le reste dans l'archive).

| # | Contrôle | Plancher — échoue si | Écart bloquant |
|---|---|---|---|
| **C0** | **Schéma et gel.** `schema_version = 8` ; `grocy.db` copié depuis moins de 2 h ; le conteneur Grocy n'a **rien écrit** depuis la copie (comparaison du `MAX(row_created_timestamp)` de `stock`, `stock_log`, `products`, `meal_plan`) | version < 8, ou copie absente | **Oui.** Une écriture après la copie invalide tous les autres contrôles |
| **C1** | **Lots.** Un `batch` par ligne de `stock`, apparié par `external_ref` | `stock` Grocy vide, ou `batch` importés = 0 | **Oui**, tout écart |
| **C2** | **Quantités.** Pour chaque lot : `batch.remaining` = `amount × facteur`, à **10⁻⁶ unité de base** près | idem C1 | **Oui**, tout écart |
| **C3** | **DLC.** `best_before` égale la date Grocy, sauf les 10 sentinelles `2999-12-31` attendues à `NULL` | 0 lot daté | **Oui** si un écart n'est pas une sentinelle |
| **C4** | **Prix.** Les lots à `price_per_base_unit IS NULL` sont **exactement** les 50 attendus (43 sans prix chez Grocy + les 7 écartés du § 8.4), chacun nommé avec sa note | 0 lot valorisé | **Oui** tant que les 7 du § 8.4 ne sont pas **acquittés** explicitement |
| **C5** | **Journal.** Un `movement` `purchase` par `batch` importé, `idempotency_key = grocy:stock:<id>` ; et `SUM(quantity)` par produit = stock du produit | `movement` importés = 0 | **Oui** |
| **C6** | **Compteurs.** `kcal_total`, `cost_total` et `cost_waste_total` **n'ont pas bougé** entre avant et après l'import du stock | les trois lus à `unknown` | **Oui.** C'est la preuve mécanique du § 8.7 |
| **C7** | **Piles et équipements** (lot 5). `battery` et `equipment` non vides, `summary_diff` vide | `battery` = 0 **ou** `equipment` = 0 | **Oui** — sans quoi le raccord ferme 14 tâches |
| **C8** | **Recettes.** 102 `recipe`, 510 `recipe_ingredient`, 561 `recipe_instruction`, 116 minuteurs ; **0 recette au `source_ref` négatif** (une fantôme aurait passé le filtre) | `recipe` importées = 0 | **Oui** sur les comptes ; **non** sur les 25 `unmatched` du § 10.4, qui sont listées et **acquittées** |
| **C9** | **Images.** Chaque `image_url` sous `media/` **désigne un fichier qui existe et qui pèse > 0 octet** ; 117 fichiers attendus ; 0 URL `grocy.allanic.me` **résiduelle** dans `recipe`, `recipe_step` ou `article` | fichiers trouvés = 0 | **Oui** |
| **C10** | **Planning et liste.** 42 `meal` à venir, 23 recettes distinctes atteignables, 9 `shopping_list_item` ouverts ; 0 `meal` pointant une recette absente | `meal` = 0 | **Oui** |
| **C11** | **Résidus Grocy dans la maison.** L'inventaire du § 17, relu à chaud : entités `grocy.*` encore lues par une automation, un script ou un template ; `todo.grocy_batteries` encore cité par `maintenance.jinja` ou par `maintenance_sync_taches` | — | **Oui** tant que le raccord du lot 5 n'est pas appliqué |

### 16.2 Ce que « bloquant » veut dire

Un écart bloquant **interdit l'extinction**, pas l'import. Le rapport rend
`blocking: [...]` et `ok: false` ; `docs/exploitation.md` dit en une phrase : on
n'arrête pas le conteneur tant que `ok` est faux.

Deux contrôles ont un acquittement explicite — C4 (les 7 lots au prix écarté) et
C8 (les 25 lignes d'ingrédient sans quantité). Ce sont les seuls écarts que la
machine ne peut pas trancher : il faut aller regarder deux pots de sel et lire
treize lignes d'huile d'olive. L'acquittement est un paramètre du service
(`acknowledged: [<ids>]`), et il est **nominatif** : acquitter « tout » n'existe
pas, parce qu'un bouton « tout va bien » finit toujours par être pressé sans
regarder.

### 16.3 Les contrôles qui échouent à vide, en pratique

Trois cas réels qu'un contrôle naïf laisserait passer :

1. **La copie de `grocy.db` a été oubliée** : sans plancher, C1 compare 0 lot à
   0 lot et affiche « écart : 0 ». C0 échoue d'abord, sur la fraîcheur.
2. **L'import est resté en simulation** : C1 trouve 0 `batch` et échoue, au lieu
   de « 0 écart sur 0 lot ».
3. **Les images sont dans le mauvais dossier** : les `image_url` sont écrites,
   la base est cohérente avec elle-même, tout est vert — jusqu'à ce que C9 aille
   `stat()` chaque fichier. Un contrôle qui ne sort pas de la base ne prouve
   rien sur des fichiers.

## 17. Ce qui casse le jour où Grocy s'éteint

Inventaire **cherché**, pas supposé : `grep -ril grocy` sur
`/opt/nivuus/HomeAssistant/config/` et `data/tools/` (en lecture seule), plus le
registre d'entités, la crontab root et la configuration du reverse proxy.

### 17.1 Ce qui casse vraiment, et doit être traité AVANT

| Quoi | Où | Traitement |
|---|---|---|
| **`maintenance.jinja` bloc 3 « Piles »** lit `states.sensor` et l'automation `maintenance_sync_taches` enrichit chaque tâche depuis **`todo.grocy_batteries`** (`automations.yaml`, lignes 4304-4321) | `config/custom_templates/maintenance.jinja` (**142 lignes — le bloc 3 est toujours là**) et `config/automations.yaml` | **Appliquer le raccord du lot 5**, livré dans `docs/raccord/` et **jamais appliqué**. Sa procédure fait autorité, dans son ordre : import des piles d'abord, `.jinja` ensuite, automation en dernier. Le raccord fait 88 lignes contre 142 |
| **`script.afficher_recette_cuisine`** ouvre `/local/grocy-recipes.html` dans un iframe `browser_mod` sur la tablette cuisine | `config/scripts.yaml`, l. 293-331 | La page reste servie (fichier statique), **mais elle interroge l'API de Grocy** : elle affichera une erreur. Le lot 6 a migré la vue recette dans `wallpanel-app` ; le script doit pointer la vue du panneau ou disparaître. **Geste du propriétaire**, décrit dans `exploitation.md` |
| **`script.afficher_repas_prevu`** lit `state_attr('sensor.grocy_meal_plan', 'meals')` | `config/scripts.yaml`, l. 407-435 | L'attribut devient `None` : le script tombe dans sa branche « pas de recette » et n'affiche rien. Dégradation silencieuse — donc à traiter. `sensor.home_stock_next_meal` (lot 6) porte déjà `meal_id` |
| **`automation.grocy_rappel_liste_de_courses_au_depart`** lit `todo.grocy_shopping_list` au départ de la maison | `config/automations.yaml`, l. 3672-3699 | L'entité passe `unavailable`, `int(0)` la lit `0`, l'automation **ne se déclenche plus jamais** — sans erreur. À rebrancher sur `todo.home_stock_shopping` ou à supprimer |
| **Les 55 images de recettes** servies par `grocy.allanic.me` | HTML des descriptions | Traité par le § 11. C'est la raison d'être du rapatriement |
| **Le cron root de 5 h 40**, `grocy-off/sync.sh`, écrit dans `/var/log/grocy-off.log` | crontab root | Échouera chaque nuit contre un port fermé. **À commenter**, § 18 étape 11 |

### 17.2 Ce qui devient inerte, sans rien casser

| Quoi | Devient |
|---|---|
| **21 entités de la plateforme `grocy`** — 7 `binary_sensor`, 6 `sensor` (+1 désactivée), 6 `todo`, 1 `calendar` | `unavailable`. Aucune n'est lue par autre chose que ce qui est listé au § 17.1 |
| **`custom_components/grocy/`** (HACS) | Lèvera à chaque tentative de connexion. L'entrée de configuration se supprime, § 18 étape 12 |
| **`update.grocy_custom_component_update`**, `switch.grocy_custom_component_pre_release` (HACS) | Suivent le dépôt HACS, pas le conteneur |
| **`update.nivuus_docker_grocy`** (MQTT, Docker Marketplace) | Signalera un conteneur arrêté. Normal |
| **`/local/grocy-scanner.html`** et **`/local/grocy-recipes.html`** | Toujours servis par Home Assistant, mais vides de données. Le lot 6 a débranché toutes les tablettes ; **plus aucune surface n'y renvoie** sauf le script du § 17.1 |
| **Les 2 routes Pomerium** `https://grocy.allanic.me` → `127.0.0.1:9283` (l'une publique sur `/api/`, l'autre authentifiée) | 502. À retirer, § 18 étape 13 |

### 17.3 Ce qui était déjà mort avant ce lot

- **`data/tools/wallpanel/rooms.py`** — le générateur du dashboard Lovelace des
  tablettes, périmé depuis le 2026-08-02. Il cite `todo.grocy_shopping_list`,
  `todo.grocy_chores`, `todo.grocy_meal_plan`, `todo.grocy_stock` et
  `binary_sensor.grocy_overdue_chores`. **Le modifier n'a aucun effet** :
  `CLAUDE.md` le dit, les tablettes lisent `wallpanel-app`. Aucun geste.
- **`.storage/lovelace.wallpanel_cuisine`** — 16 références Grocy dans un
  dashboard périmé, conservé comme filet. Les autres dashboards en comptent
  **zéro**. Aucun geste.
- **`data/tools/wallpanel-app/src/`** — **zéro** occurrence, et deux tests le
  tiennent (`pieces.test.ts` : « aucune chaîne `grocy` ne subsiste dans `src/` » ;
  `navigation.test.ts` : « n'appelle plus aucun service grocy »). Le lot 6 a fait
  son travail.
- Les 8 sauvegardes `automations.yaml.backup-*` et `scripts.yaml.backup-*` qui
  citent Grocy : des sauvegardes. Aucun geste.

## 18. La séquence d'extinction

**Une liste de gestes numérotés, pour le propriétaire.** Le composant n'en
exécute aucun. Elle est reprise telle quelle dans `docs/exploitation.md`.

Compter **une soirée**, sans interruption ; les étapes 1 à 10 doivent tenir dans
une même session, parce que l'étape 2 gèle Grocy et que rien ne doit être rangé
entre-temps.

1. **Sauvegarder.** Une sauvegarde native Home Assistant complète (Paramètres →
   Système → Sauvegardes), puis :
   ```bash
   D=$(date +%Y%m%d)
   cp /opt/nivuus/Grocy/config/data/grocy.db  ~/grocy-extinction-$D.db
   tar czf ~/grocy-storage-$D.tar.gz -C /opt/nivuus/Grocy/config/data storage
   cp /opt/nivuus/Grocy/config/data/config.php ~/grocy-config-$D.php
   ```
2. **Geler Grocy.** Ne plus rien y saisir à partir de maintenant. Rappel du
   § 2.2 : un produit y a été créé le 2026-08-21 à 18 h 54. Tant que quelqu'un
   range une course dans Grocy, aucun contrôle d'égalité ne veut rien dire.
3. **Copier la source dans `config/`** — le conteneur Home Assistant ne voit pas
   `/opt/nivuus/Grocy` :
   ```bash
   cd /opt/nivuus/HomeAssistant/config
   cp /opt/nivuus/Grocy/config/data/grocy.db ./grocy_import.db
   mkdir -p media/home_stock/recipes media/home_stock/articles
   cp /opt/nivuus/Grocy/config/data/storage/recipepictures/*.jpg   media/home_stock/recipes/
   cp /opt/nivuus/Grocy/config/data/storage/productpictures/*.jpg  media/home_stock/articles/
   rm -f media/home_stock/recipes/test.jpg          # le seul orphelin (§ 3.1)
   rm -f media/home_stock/articles/*__downscaledto64x64.jpg
   ```
4. **Déployer les lots 2 à 6.** La base de production est au schéma **2** (§ 2.1) :
   `m003` → `m008` s'appliquent au redémarrage de l'intégration. Vérifier ensuite
   `websocket_call → repairs/list_issues` à **0**, et
   `home_stock/migration/check` → C0 doit voir `schema_version = 8`.
5. **Supprimer les statistiques des trois cumuls**, une fois pour toutes :
   Outils de développement → Statistiques → `sensor.home_stock_kcal_total`,
   `cost_total`, `cost_waste_total` → supprimer. C'est le geste que
   `docs/exploitation.md` décrit déjà (« Statistiques à supprimer une fois »),
   rendu obligatoire ici par le passage en `state_class: total` du lot 4.
6. **Rejouer l'import du catalogue.**
   `home_stock.import_grocy_catalog` avec `apply: false`, lire le rapport,
   exiger `ok: true` et `anomalies: []`, puis `apply: true`. Il rattrape ce qui a
   été créé dans Grocy depuis le 19 août — au moins le produit #350.
7. **Importer les piles et les équipements** (lot 5), même protocole :
   `home_stock.import_grocy_equipment`, `apply: false`, `summary_diff` **vide**,
   puis `apply: true`.
8. **Appliquer le raccord `maintenance.jinja`** — la procédure de
   `docs/raccord/README.md`, dans son ordre, sans en sauter une étape. C'est
   elle qui débranche `todo.grocy_batteries`.
9. **Importer le stock.** `home_stock.import_grocy_stock`, `apply: false`. Lire
   **toutes** les anomalies, en particulier les 7 lots du § 8.4 avec leurs notes.
   Puis `apply: true`.
10. **Importer les recettes, les images et le planning.**
    `home_stock.import_grocy_recipes`, `apply: false` puis `apply: true`.
11. **Contrôler.** `home_stock.check_grocy_migration` (ou le bloc « Bascule » de
    l'écran Réglages). Acquitter nommément les 7 lots et les 25 lignes
    d'ingrédient. **Ne pas continuer tant que `ok` n'est pas `true`.**
12. **Preuve sur pièce, Grocy encore allumé** : ouvrir une recette sur la
    tablette de la cuisine, vérifier que **l'image s'affiche**, puis
    `docker stop grocy` **temporairement** et la rouvrir. Si elle s'affiche
    encore, le § 11 a tenu. `docker start grocy` ensuite — on n'éteint pas
    encore.
13. **Débrancher ce qui reste** (§ 17.1) : `script.afficher_recette_cuisine`,
    `script.afficher_repas_prevu`, `automation.grocy_rappel_liste_de_courses_au_depart`.
    `automation.reload`, `script.reload`, puis `repairs/list_issues` à 0.
14. **Commenter le cron de 5 h 40** dans la crontab root
    (`grocy-off/sync.sh`) — sinon il échoue chaque nuit dans
    `/var/log/grocy-off.log`.
15. **Arrêter Grocy, sans le supprimer :**
    ```bash
    cd /opt/nivuus/Grocy && docker compose stop      # PAS `down -v`
    ```
    Retirer le label `com.centurylinklabs.watchtower.enable: true` du
    `docker-compose.yml` pour que Watchtower ne le relance pas, et **ne pas
    supprimer `/opt/nivuus/Grocy/config/`** avant le délai du § 19.
16. **Retirer les deux routes `grocy.allanic.me`** de
    `/opt/nivuus/Pomerium/config.yaml` (une sauvegarde datée d'abord, comme les
    quatre déjà présentes), puis recharger Pomerium.
17. **Supprimer l'entrée de configuration `grocy`** dans Home Assistant
    (Paramètres → Appareils et services), ce qui retire les 21 entités du
    registre, puis **désinstaller le dépôt HACS**. `repairs/list_issues` à 0.
18. **Ranger la maison** : supprimer `config/grocy_import.db` (l'intrant, pas un
    fichier d'exploitation — règle du lot 0), et retirer
    `/local/grocy-scanner.html` et `/local/grocy-recipes.html` de `config/www/`.

## 19. Le retour arrière

La question n'est pas « si », elle est « après combien de temps ». Un écart se
découvre le jour où on cherche un paquet, c'est-à-dire des semaines plus tard.

### 19.1 Ce qu'on garde, et combien de temps

| Quoi | Où | Durée |
|---|---|---|
| `grocy-extinction-<date>.db` | hors `config/`, dans le dossier personnel | **12 mois**, minimum |
| `grocy-storage-<date>.tar.gz` (les 94 fichiers d'images) | idem | 12 mois |
| `grocy-config-<date>.php` | idem | 12 mois |
| `/opt/nivuus/Grocy/config/` **intact**, conteneur seulement arrêté | en place | **3 mois** |
| `home_stock_grocy_archive_<date>.json` (§ 9.3) | `config/` | **toujours** — il est petit et emporté par les sauvegardes HA |
| Sauvegarde native Home Assistant d'avant l'étape 4 | Sauvegardes HA | selon la rétention configurée, **≥ 1 mois** |

Trois mois pour le conteneur arrêté : le temps d'un cycle complet de courses, de
recettes de saison et de piles à changer. Un an pour la base : le temps qu'une
question du type « combien coûtait ce produit l'an dernier ? » ait encore une
réponse.

### 19.2 Si un écart bloquant apparaît APRÈS l'arrêt

**Grocy n'est jamais rallumé pour être réutilisé.** Il est rallumé pour être
**lu**, et le sens de la migration ne s'inverse jamais — décision du lot 0,
« Écriture vers Grocy : jamais ».

Trois situations, trois réponses, par ordre de gravité :

1. **Il manque une donnée** (un lot, une recette, une image). Ne pas rallumer :
   la sauvegarde suffit.
   ```bash
   cp ~/grocy-extinction-<date>.db /opt/nivuus/HomeAssistant/config/grocy_import.db
   ```
   puis relancer l'import concerné, en simulation d'abord. Les imports sont
   rejouables (§ 8.8) : ce qui est déjà là n'est pas réécrit, ce qui manque
   entre. C'est exactement pour ça que `batch.external_ref` existe (§ 6).
2. **Une donnée est fausse et on veut comparer les deux bases.**
   ```bash
   cd /opt/nivuus/Grocy && docker compose start
   ```
   Consulter, comparer, **ne rien saisir**, puis `docker compose stop`. La
   séquence a retiré les routes Pomerium à l'étape 16 : l'accès se fait par
   `http://127.0.0.1:9283` depuis le serveur, ce qui est une garantie de plus
   qu'on ne rangera pas une course dedans par habitude.
3. **`home_stock` est inexploitable.** Ordre de redémarrage, strict :
   restaurer la sauvegarde native Home Assistant d'avant l'étape 4 (elle
   contient `home_stock.db` **au schéma 2** et les `.yaml` d'avant le raccord) ;
   redémarrer Home Assistant ; puis `docker compose start` sur Grocy ; puis
   reposer `maintenance.jinja.avant-lot5` et `automations.yaml.avant-lot5`
   (sauvegardés à l'étape 1 du raccord) et recharger modèles et automations.
   **Grocy en dernier des services, ses fichiers de configuration en dernier des
   fichiers** : reposer le `.jinja` avant que Grocy réponde ferait, pendant
   quelques minutes, une réconciliation où le bloc 3 et le service `home_stock`
   produiraient chacun leur résumé — le doublon que le raccord décrit.

### 19.3 Ce qui ne revient pas en arrière

Deux choses, et il faut les avoir dites avant, pas après :

- **Les statistiques long terme supprimées à l'étape 5.** Irréversible, et
  `docs/exploitation.md` le dit déjà. Rien n'est perdu pour autant : le journal
  SQLite porte toute l'histoire et les graphes du panneau se recalculent depuis
  lui.
- **Les mouvements écrits par les imports.** `movement` est en ajout seul, avec
  deux triggers qui refusent `UPDATE` et `DELETE`. Un import de stock appliqué
  ne s'annule pas ; il se **corrige** par des contrepassations (lot 4). C'est la
  raison pour laquelle l'étape 9 exige de lire les anomalies **avant**
  `apply: true`, et pas après.

## 20. Tests

Suites existantes vertes, plus ce qui suit. `./scripts/test.sh` pour le Python
(**1 914** aujourd'hui, image alignée sur HA 2026.8.2), `npm test` (**536**) et
`node outils/verifier-rendu.mjs` (**70 exécutions**) depuis `frontend/`.

**`pytest` pur, sans Home Assistant, sans réseau — le gros du lot.**

- `grocy/units.py` : un test compare l'**identité** des tables avec celles
  d'`import_grocy.py`, pas leurs valeurs, pour qu'une copie ne puisse pas naître.
- `grocy/html.py`, sur les **102 descriptions réelles** versionnées dans
  `tests/fixtures/grocy/` : 323 pages découpées ; une description **sans**
  `page-recipes` rend **une** page et non zéro ; `<h3 style="…">` reconnu ;
  `&#x27;` déséchappé une seule fois ; `<strong>` retiré du texte.
- Minuteurs : `#Repos poulet:600` → `('Repos poulet', 600)` ;
  **`style="color:#888;font-size:12px"` ne rend aucun minuteur** ; les 8 puces à
  deux minuteurs rendent **deux** instructions ; 116 minuteurs sur les fixtures,
  pas 115.
- Stock : conversion des 108 lots ; poussière flottante (5,55·10⁻¹⁷ → 0 +
  `closed_at`) ; pièces fractionnaires **non arrondies** ; `2999-12-31` → `NULL` ;
  les 7 lots > 20 € entrent **avec `price NULL`** et leur note au rapport ;
  cascade d'emplacement dans ses trois cas (27, 2, 0) ; `Frigo` → `fridge`.
- Rejeu : deux passages ne créent rien, et le second ne touche pas un
  `remaining` diminué entre-temps par une consommation réelle.
- **Le contrôle échoue à vide** — trois tests, un par cas du § 16.3, chacun
  exigeant `ok: false`. **Ce sont les tests les plus importants du lot** : ceux
  qui empêchent la panne du lot 6 de se rejouer.
- `m008` : colonne créée, migration rejouable, index unique partiel, contiguïté
  `[1..8]`.
- Neutralité comptable : après import des 107 lots, `totals_between(conn)` rend
  les **mêmes** kcal, coût et coût de gaspillage qu'avant. C'est C6.

**Couche HA** : les trois services en simulation n'écrivent rien ; `apply: true`
rafraîchit le coordinateur ; un `database_path` hors `config/` est refusé aux
**deux** surfaces avec le même message ; `home_stock/migration/check` et
`home_stock.check_grocy_migration` rendent le **même** objet
(`test_surface_parity.py`).

**Front** : `reglages.test.ts` (le bloc Bascule affiche les onze lignes, met en
rouge les bloquantes, n'offre **aucun** bouton d'import ni d'extinction) ;
`verifier-rendu.mjs`, un scénario de plus aux deux formats.

**Interdits, repris du lot 1 et jamais assouplis** : aucun `docker compose`,
aucun redémarrage, aucun rechargement de l'intégration, aucune lecture du jeton
de `.mcp.json`, aucune écriture dans `/opt/nivuus/HomeAssistant/config/`, aucun
`npm run build` pendant la conception. **Grocy est en lecture seule, et seule une
copie de `grocy.db` est lue** — la volumétrie de ce document a été relevée
exactement ainsi.

## 21. Points différés

| Sujet | Quand | Raison |
|---|---|---|
| **Les 112 images Unsplash** (46 distinctes) | jamais, sauf panne | Elles ne meurent pas avec le conteneur. Même dette assumée que `strMealThumb` au lot 3. Le jour où elles tomberont, elles tomberont toutes ensemble et se remplaceront par `recettes_images.py` |
| **Réinjecter l'historique** de `stock_log` | jamais | § 9. Il faudrait d'abord corriger 387 lignes de quantités sur des paquets déjà mangés |
| **Les prix historiques** | jamais | Même défaut d'unité. Ils se réapprennent en trois sessions de courses |
| **Analyser `variable_amount`** pour retrouver les 23 quantités | jamais | Règle du lot 3, § 18. Vingt-cinq lignes à la main valent mieux qu'un analyseur à vie |
| **Une seconde minuterie par puce** (`recipe_timer`) | ultérieur | 8 puces sur 553. Le dédoublement du § 10.5 ne perd rien ; une table changerait le contrat de la vue cuisine |
| **`recipes_nestings`** — recettes imbriquées | ultérieur | 5 651 lignes, presque toutes générées par les triggers de `meal_plan`. Aucun usage réel constaté, décision reprise du lot 3, § 20 |
| **Les 6 corvées** | hors composant | § 14.2. Chemin de repli (`local_todo` + automation quotidienne) écrit dans `docs/exploitation.md`, pas dans le code |
| **Une vue HTTP d'images dans le composant** (le `http.py` du lot 0) | jamais | § 11.1. `media_source` de Home Assistant fait le travail, avec l'authentification en prime |
| **Un écran « Bascule » à part entière** | jamais | Un bloc dans Réglages suffit pour un événement qui n'arrive qu'une fois |
| **`batch.note`** | jamais | § 6. Les 25 notes sont dans le rapport d'import et dans l'archive ; une colonne que rien ne lit finit par être crue |
| **Le poids net des 239 produits en `piece`** | lot 1, en cours | Vient d'Open Food Facts (`product_quantity`) et des 14 `packaging` du § 13.1. La devinette par le nom reste refusée |
| **Écriture vers Grocy** | jamais | Décision du lot 0, rappelée au § 19.2 |

## 22. Amendements aux specs précédentes

Ce sont des **amendements** : les documents d'origine ne sont pas réécrits.

| Spec | Ligne fausse | Correction |
|---|---|---|
| Lot 3, § 18 | « 15 de type `1` : ce sont les copies fantômes » | **Faux.** Ce sont 15 vraies recettes créées le 2026-06-27, avec 96 lignes d'ingrédients et 10 entrées de planning. Le filtre est `type IN ('normal','1')` (§ 10.1) |
| Lot 3, § 18 | « 87 recettes, 420 lignes d'ingrédients, 92 entrées de planning, 41 images » | **102 recettes, 510 lignes, 108 entrées de planning (42 reprises), 117 images à rapatrier** (§ 3, § 10) |
| Lot 3, § 18 | « `<h3>Étape N — …</h3>` pour le titre » | Les balises portent des attributs : `<h3 style="color:#333;">`. Il n'existe **aucun** `<h3>` nu dans la base (§ 10.3) |
| Lot 3, § 18 | « `recipes_pos.ingredient_group` → `group_name`, direct » | Sans objet : la colonne est **vide sur les 510 lignes** |
| Lot 3, § 18 et `grocy-off/README.md` | « `#Nom:secondes` » | L'étiquette contient des espaces (`#Repos poulet:600`), et 327 des 443 `#` de la base sont des **couleurs CSS** (§ 10.5) |
| Lot 3, § 18 | « Images `recipepictures/<base64>` : à copier » | Vrai, mais incomplet : **`recipes.picture_file_name` est NULL sur les 102 recettes**. Les images ne sont que dans le HTML, et 62 d'entre elles sont des data-URI (§ 3.2) |
| Lot 0, § 5.2 | « `http.py` — images d'articles (binaire) uniquement » | **Jamais écrit, et abandonné.** Les images passent par `media_source` (§ 11.1) |
| Lot 0, § 10 | « les 299 produits actifs » | **300 au 2026-08-21**, et le nombre bouge tant que Grocy n'est pas gelé (§ 2.2) |
| Lot 0, § 10 | L'import de catalogue mappe `location.kind` sur `is_freezer` | « Frigo » est donc enregistré en `pantry`. Corrigé par nom exact à l'import du stock (§ 8.5) |
| Lot 5, § 18 | « Les 6 *chores* : à trancher au lot 7 » | **Tranché : abandonnées** (§ 14.2), 3,5 % de suivi mesuré sur six mois |

*Conception du 2026-08-21.*
