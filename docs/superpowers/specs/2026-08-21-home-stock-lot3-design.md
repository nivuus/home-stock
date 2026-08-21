# home_stock — Lot 3 : recettes, planning et validation d'un repas

> Spec du lot 3. Le découpage en huit lots est fixé par
> `2026-08-18-home-stock-lot0-design.md` § 3 ; le panneau, la file d'attente
> hors-ligne, l'appariement et la conversion d'unité viennent de
> `2026-08-19-home-stock-lot1-design.md` ; la sortie de stock, les parts, la
> journée alimentaire et le gel des neuf nutriments viennent de
> `2026-08-20-home-stock-lot2-design.md`.

## 1. Objectif et livrable

Décider ce qu'on mange, le poser sur un jour, puis le valider — et que le stock
bouge exactement de ce qui a été cuisiné, sans rien avoir à ressaisir.

Livrable vérifiable, celui annoncé au lot 0 :

> « Je valide le dîner » → le stock bouge juste.

Concrètement : ouvrir une recette du planning sur le téléphone, la suivre page
par page en cuisine, appuyer sur « J'ai cuisiné », et constater que les six
ingrédients ont quitté leurs lots dans l'ordre FIFO, que le plat existe en stock
avec sa date limite et ses calories, et que la part mangée ce soir apparaît dans
le journal de la journée — les deux parts restantes toujours au frigo.

## 2. Périmètre

**Dans le lot :** les tables des recettes, de leurs étapes et de leurs
ingrédients ; les mesures culinaires ; l'appariement d'un ingrédient sur un
produit du catalogue et les alias appris ; la source de recettes en ligne et son
adaptation par un agent conversationnel de la maison ; le planning et l'entité
`calendar` native ; la simulation puis la validation d'un repas ; le motif
`cooked` et les restes cuisinés comme lot en stock ; les nutriments portés par
le lot ; trois écrans de panneau ; les commandes websocket et les services
associés ; la migration `m004`.

**Hors du lot :** la liste de courses issue du planning et la correction d'un
mouvement déjà écrit (lot 4) ; les piles et équipements (lot 5) ; les tablettes
murales, la vue dense PC et le vocal Bleuenn (lot 6) ; la reprise des 87
recettes Grocy, de leurs 420 lignes d'ingrédients et de leurs images (lot 7).
Le § 18 dit précisément ce que le lot 3 doit poser pour que le lot 7 ne soit
qu'une jointure.

## 3. Décisions validées

| Question | Réponse retenue |
|---|---|
| Ingrédient → catalogue | Sur le **produit** (l'ingrédient culinaire), jamais sur l'`article` (l'EAN) |
| Quantité d'un ingrédient | **Un seul nombre écrit**, `amount`, plus la mesure dans laquelle il est dit. La quantité en unité de base est *calculée*, jamais stockée |
| Source en ligne | **TheMealDB**, sans compte, transport injecté, jamais bloquante |
| Adaptation / traduction | Un **agent conversationnel de Home Assistant** désigné dans les options, pas une clé d'API dans le composant |
| Planning | Entité **`calendar` native**, en création / déplacement / suppression, plus les commandes websocket du panneau |
| Valider un repas | **Cuisiner puis manger** : les ingrédients sortent en `cooked`, le plat entre en `cooked`, la part du soir sort en `consumption` |
| Restes | Un **lot en stock** sous un produit « Reste — ⟨recette⟩ », avec sa DLC et ses neuf nutriments portés **par le lot** |
| Réversibilité | Aucune au lot 3 : simulation obligatoire avant écriture, transaction unique, clé d'idempotence. La correction est au lot 4 |

Le premier choix mérite d'être posé tout de suite, parce qu'il cadre le reste.
Une recette cite « de la moutarde », pas « Moutarde Savora 265 g ». Le lot 0 a
séparé le `product` (l'ingrédient culinaire) de l'`article` (l'objet acheté avec
son code-barres) précisément pour ça : c'est le produit que la recette
référence, et c'est le FIFO qui choisit ensuite dans quel article — donc dans
quel pot ouvert — la moutarde est prise. Une recette liée à un EAN serait fausse
le jour où le format change, ce qui arrive plusieurs fois par an.

## 4. Amendements aux specs précédents

Trois points changent. Ils sont normatifs.

**A1 — Le tableau des motifs du lot 0 (§ 7.5) gagne `cooked`.** Le lot 1 y avait
déjà ajouté `conversion` (sortie dans l'ancienne unité, entrée dans la
nouvelle, rien qui compte). `cooked` suit exactement le même modèle : une sortie
par ingrédient, une entrée pour le plat, **et rien qui compte** ni en
kilocalories ni en euros. Cuisiner n'est pas manger ; c'est un changement de
forme, comme une conversion d'unité en est un. `cooked` rejoint `REASONS` dans
`const.py` mais **pas** `CONSUME_REASONS` — la constante que le lot 2 appelait
`COUNTED_REASONS` et qui porte ce nom dans le code depuis.

**A2 — Les neuf nutriments et le prix peuvent vivre sur le lot, pas seulement
sur l'article.** Un plat cuisiné n'a pas de fiche Open Food Facts et deux
cuissons de la même recette n'ont pas la même valeur : le gratin de dimanche a
été fait avec la crème entière, celui de mercredi avec la demi-écrémée. Écrire
ces valeurs sur l'article partagé les écraserait d'une cuisson à l'autre, y
compris pendant qu'un lot de la cuisson précédente attend encore au frigo. La
table `batch` reçoit donc les neuf colonnes ; la cascade de résolution devient
`COALESCE(b.…, a.…, p.reference_kcal)` pour les kcal et `COALESCE(b.…, a.…)`
pour les huit macros, dans les deux constantes SQL déjà nommées une seule fois
(`repo.KCAL_RATE_SQL`, `repo.MACRO_RATE_SQL`). Tout ce qui existe reste à
`NULL` et se lit exactement comme avant.

**A3 — `application.add_stock()` accepte un motif et une nutrition.** Il écrit
`purchase` en dur depuis le lot 0. Il prend désormais `reason` (défaut
`purchase`, inchangé pour tous les appelants existants) et un dictionnaire de
taux à figer sur le lot. C'est le seul chemin d'entrée en stock du composant ;
en ouvrir un second pour les plats cuisinés reviendrait à entretenir deux
comportements d'entrée, ce qui est précisément le genre de dette que le lot 0
a refusé sur la sortie.

## 5. Architecture

Aucune couche nouvelle. Les règles vivent dans le domaine pur, la lecture dans
les dépôts, l'orchestration dans `application.py`, la surface dans le websocket
et les services.

| Fichier | Rôle |
|---|---|
| `domain/recipes.py` | **Nouveau.** Mise à l'échelle, résolution d'une quantité d'ingrédient en unité de base, plan de décrément. Pur |
| `domain/matching.py` | Réutilisé tel quel, avec ses seuils. Aucune modification |
| `domain/units.py` | Réutilisé : `to_base_quantity`, `format_quantity` |
| `recipes/source.py` | **Nouveau.** Client TheMealDB. Transport injecté, aucun `hass` |
| `recipes/mapping.py` | **Nouveau.** Fiche TheMealDB → lignes de recette. Aucun réseau, aucun `hass` |
| `recipes/adapt.py` | **Nouveau.** Invite, appel à l'agent conversationnel, lecture défensive de sa réponse |
| `storage/migrations/m004_recipes.py` | **Nouveau.** Tables, colonnes, données de départ |
| `storage/repositories.py` | Dépôts des recettes, des ingrédients, des repas ; cascade nutritionnelle étendue |
| `application.py` | `plan_meal`, `preview_meal`, `validate_meal`, `cancel_meal`, `match_ingredient` |
| `calendar.py` | **Nouveau.** `calendar.home_stock_meals` |
| `sensor.py` | Trois capteurs de plus |
| `websocket_api.py` | Quatorze commandes de plus |
| `frontend/src/ecrans/recettes.ts` · `recette.ts` · `planning.ts` | **Nouveaux.** Liste, vue cuisine, semaine |

`domain/recipes.py`, `recipes/mapping.py` et `recipes/adapt.py` (pour tout ce
qui n'est pas l'appel lui-même) ne connaissent ni `hass`, ni le réseau, ni
SQLite. C'est la discipline des lots précédents et elle sert ici la même chose :
la mise à l'échelle d'une recette et la conversion « 2 cs d'huile » → « 30 ml »
sont exactement les calculs que Grocy a ratés, et ils se testent sans démarrer
quoi que ce soit.

Le front garde ses identifiants et ses commentaires **en français**, le Python
les siens **en anglais**, comme aux trois lots précédents.

## 6. Migration `m004`

Le lot 2 s'est arrêté à `m003` (`storage/migrations/__init__.py` :
`MIGRATIONS = (m001_initial, m002_scan, m003_consumption)`). `m004` est donc la
quatrième, `VERSION = 4`.

Aucune manipulation de trigger : rien ici ne fait d'`UPDATE` sur `movement`.
Toutes les colonnes ajoutées sont nullables, toutes les tables sont nouvelles,
et le remplissage de départ (`apply`) est rejouable — même discipline que le
remplissage des rayons de `m002` et celui des portions de `m003`.

```sql
-- Pas d'unicité sur le nom : deux « Salade de pâtes » sont légitimes. L'unicité
-- qui compte est celle de la SOURCE, et c'est elle qui rend l'import rejouable
-- (même raison que product.external_ref au lot 0).
CREATE TABLE recipe (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  servings INTEGER NOT NULL DEFAULT 1 CHECK (servings >= 1),
  total_minutes INTEGER,
  utensils TEXT,
  summary TEXT,                    -- l'accroche de couverture
  image_url TEXT,
  source TEXT NOT NULL CHECK (source IN ('manual','themealdb','grocy')),
  source_ref TEXT,                 -- idMeal, id Grocy
  source_url TEXT,
  language TEXT NOT NULL DEFAULT 'fr',
  adapted_at TEXT,                 -- quand l'agent a traduit/adapté, NULL sinon
  needs_review INTEGER NOT NULL DEFAULT 0,
  leftover_product_id INTEGER REFERENCES product(id),
  leftover_shelf_life_days INTEGER,
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  external_ref TEXT
);
CREATE UNIQUE INDEX idx_recipe_source
  ON recipe(source, source_ref) WHERE source_ref IS NOT NULL;

-- Une page de la vue cuisine : un titre, une image, et ses puces.
CREATE TABLE recipe_step (
  id INTEGER PRIMARY KEY,
  recipe_id INTEGER NOT NULL REFERENCES recipe(id),
  position INTEGER NOT NULL,
  title TEXT,
  image_url TEXT,
  UNIQUE (recipe_id, position)
);

-- Une puce. Au plus UN minuteur, et son libellé et sa durée vont ensemble ou
-- pas du tout — un bouton « Cuisson » sans durée n'est pas un bouton.
CREATE TABLE recipe_instruction (
  id INTEGER PRIMARY KEY,
  step_id INTEGER NOT NULL REFERENCES recipe_step(id),
  position INTEGER NOT NULL,
  text TEXT NOT NULL,
  timer_label TEXT,
  timer_seconds INTEGER CHECK (timer_seconds IS NULL OR timer_seconds > 0),
  UNIQUE (step_id, position),
  CHECK ((timer_label IS NULL) = (timer_seconds IS NULL))
);

-- Une ligne d'ingrédient. `amount` est le SEUL nombre écrit ; voir § 9.
CREATE TABLE recipe_ingredient (
  id INTEGER PRIMARY KEY,
  recipe_id INTEGER NOT NULL REFERENCES recipe(id),
  position INTEGER NOT NULL,
  product_id INTEGER REFERENCES product(id),
  amount REAL,
  packaging_id INTEGER REFERENCES packaging(id),      -- « 1 tranche », propre au produit
  measure_id INTEGER REFERENCES culinary_measure(id), -- « 1 cs », universelle
  raw_text TEXT NOT NULL,          -- ce que la source disait. PROVENANCE, jamais un calcul
  group_name TEXT,                 -- ingredient_group de Grocy (« Pour la sauce »)
  optional INTEGER NOT NULL DEFAULT 0,
  match_state TEXT NOT NULL DEFAULT 'unmatched'
    CHECK (match_state IN ('unmatched','auto','confirmed','ignored')),
  match_score REAL,
  external_ref TEXT,
  UNIQUE (recipe_id, position),
  -- Une quantité se dit dans UNE mesure, jamais deux.
  CHECK (packaging_id IS NULL OR measure_id IS NULL),
  -- Un état d'appariement autre que 'unmatched' suppose un produit.
  CHECK (match_state = 'unmatched' OR product_id IS NOT NULL)
);

-- Les mesures de cuisine, valables pour tous les produits. Un `packaging`
-- propre au produit l'emporte toujours (§ 9).
CREATE TABLE culinary_measure (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  base_unit TEXT NOT NULL CHECK (base_unit IN ('g','ml','piece')),
  base_quantity REAL NOT NULL CHECK (base_quantity > 0),
  UNIQUE (name, base_unit)
);

-- Ce qu'un humain a tranché une fois pour toutes : « coriandre fraîche »,
-- c'est le produit « Coriandre ». Jamais écrit par l'appariement automatique.
CREATE TABLE ingredient_alias (
  id INTEGER PRIMARY KEY,
  normalised TEXT NOT NULL UNIQUE, -- forme rendue par matching.normalise()
  product_id INTEGER NOT NULL REFERENCES product(id),
  created_at TEXT NOT NULL
);

-- Les créneaux du planning. Repris tels quels des meal_plan_sections de Grocy,
-- horaires compris : c'est ce que le calendrier utilise pour poser un début.
CREATE TABLE meal_slot (
  id INTEGER PRIMARY KEY,
  key TEXT NOT NULL UNIQUE CHECK (key IN ('breakfast','lunch','dinner','snack')),
  position INTEGER NOT NULL,
  default_time TEXT NOT NULL,      -- 'HH:MM' local
  duration_minutes INTEGER NOT NULL DEFAULT 45,
  external_ref TEXT
);

-- Un repas posé sur un jour. La table est MUTABLE — ce n'est pas le journal.
CREATE TABLE meal (
  id INTEGER PRIMARY KEY,
  uid TEXT NOT NULL UNIQUE,        -- l'uid de l'événement de calendrier
  day TEXT NOT NULL,               -- journée ALIMENTAIRE (AAAA-MM-JJ), § 12
  slot_key TEXT NOT NULL REFERENCES meal_slot(key),
  position INTEGER NOT NULL DEFAULT 0,
  recipe_id INTEGER REFERENCES recipe(id),
  product_id INTEGER REFERENCES product(id),
  amount REAL,
  packaging_id INTEGER REFERENCES packaging(id),
  note TEXT,
  servings REAL NOT NULL DEFAULT 1 CHECK (servings > 0),
  portions_eaten REAL,             -- combien de parts mangées à la validation
  parts_total INTEGER, parts_mine INTEGER,
  state TEXT NOT NULL DEFAULT 'planned'
    CHECK (state IN ('planned','done','skipped')),
  validated_at TEXT,
  skipped_ingredient_ids TEXT,     -- JSON. Provenance, jamais de la comptabilité
  created_at TEXT NOT NULL,
  external_ref TEXT,
  -- Un repas est une recette, OU un produit, OU une note. Jamais deux.
  CHECK ((recipe_id IS NOT NULL) + (product_id IS NOT NULL) + (note IS NOT NULL) = 1)
);
CREATE INDEX idx_meal_day ON meal(day, slot_key, position);
CREATE INDEX idx_ingredient_recipe ON recipe_ingredient(recipe_id, position);

-- Amendement A2 : un lot peut porter sa propre nutrition.
ALTER TABLE batch ADD COLUMN kcal_per_base_unit REAL;
ALTER TABLE batch ADD COLUMN proteins REAL;
ALTER TABLE batch ADD COLUMN carbohydrates REAL;
ALTER TABLE batch ADD COLUMN sugars REAL;
ALTER TABLE batch ADD COLUMN added_sugars REAL;
ALTER TABLE batch ADD COLUMN fat REAL;
ALTER TABLE batch ADD COLUMN saturated_fat REAL;
ALTER TABLE batch ADD COLUMN fiber REAL;
ALTER TABLE batch ADD COLUMN salt REAL;
```

`apply(conn)` sème, **seulement si la table est vide** (donc rejouable) :

- les quatre créneaux, aux horaires de Grocy : `breakfast` 07:30, `lunch` 12:30,
  `dinner` 20:00, plus `snack` 16:00 qui n'existait pas et qu'on ajoute parce
  qu'un en-cas se déclare comme le reste ;
- les mesures culinaires : **cuillère à soupe 15 ml, cuillère à café 5 ml, verre
  200 ml, pincée 1 g**. Le lot 0 citait « cs = 13 ml » en exemple ; 15 ml est la
  valeur normalisée française, et le chiffre exact importe peu puisqu'un
  `packaging` propre au produit l'emporte dès qu'il existe ;
- la catégorie « Plats cuisinés », qui accueillera les produits de restes.

Les créneaux portent un `external_ref` dès le semis (`1`, `2`, `3` pour les
trois sections Grocy, `NULL` pour `snack`) : c'est la jointure du lot 7, posée
maintenant plutôt que devinée par correspondance de nom plus tard.

## 7. Recette, étapes, ingrédients

La forme retenue est **exactement** celle que les 87 recettes Grocy ont déjà :
une couverture (image, durée, ustensiles, accroche), un bloc Ingrédients, puis
une page par étape avec son image, son titre et sa liste numérotée de puces,
chaque puce pouvant porter un minuteur. C'est le modèle de la recette 1
« Burger poulet maison » décrit dans `data/tools/grocy-off/README.md`. On ne le
réinvente pas : il fonctionne, l'application des tablettes le rend déjà, et le
reprendre tel quel est ce qui rend le lot 7 mécanique.

Deux différences, toutes deux volontaires :

1. **Ce n'est plus du HTML.** Grocy stocke une description HTML unique dans
   laquelle `decouperPages` va chercher les `<div class="page-recipes">` de
   premier niveau, avec les précautions d'échappement que la mise en page a dû
   apprendre (`&#x27;` redécodé par Grocy, script non idempotent). Ici les
   étapes et les puces sont **des lignes**, l'affichage les compose : plus de
   HTML à parser, donc plus de parseur à rendre rejouable.
2. **Les minuteurs sont des colonnes.** `#Nom:secondes` est chez Grocy un
   marqueur *dans* le texte, relu par une expression régulière à chaque
   affichage. Ici `timer_label` et `timer_seconds` sont des colonnes et le texte
   n'en porte plus la trace — une seule vérité, que personne ne casse en
   corrigeant une faute de frappe dans la phrase.

`recipe.summary`, `total_minutes` et `utensils` reprennent la ligne méta
`⏱ / 🔥 / 🍳` de la couverture. `needs_review = 1` marque les recettes dont les
étapes ont été rédigées ou traduites plutôt que relevées — la distinction que le
README de `grocy-off` tient à la main pour les 17 recettes réécrites le
2026-08-18 devient ici une colonne.

## 8. Appariement ingrédient → produit

Rien de nouveau à écrire : `domain/matching.py` existe depuis le lot 1, est pur,
déterministe, et a été calibré sur les 299 produits réels du catalogue. Le lot 3
l'appelle, avec ses seuils inchangés (`PRESELECT_SCORE = 0.75`,
`PRESELECT_MARGIN = 0.10`). Un seuil qui diffère entre deux écrans est un seuil
que personne ne comprend.

**Ordre de résolution d'une ligne d'ingrédient :**

1. **Alias.** `matching.normalise(texte)` interrogé dans `ingredient_alias`.
   Touché → `match_state = 'confirmed'`, `match_score = 1.0`. C'est le chemin
   qui rend le travail décroissant : chaque arbitrage humain vaut pour toujours.
2. **Appariement.** `candidates(names=[…], products=…)` reçoit, dans cet ordre,
   le nom d'ingrédient isolé par l'adaptation (§ 11), le `raw_text` amputé de sa
   quantité, et le `raw_text` brut. Le meilleur des trois l'emporte, exactement
   comme le lot 1 essaie `generic_name_fr`, `product_name_fr` et
   `product_name_fr` sans la marque.
3. **`preselect()`.** S'il rend un candidat → `match_state = 'auto'`, avec son
   score. Sinon → `match_state = 'unmatched'`, et les cinq candidats sont
   conservés pour être proposés à l'écran.

**Un `auto` n'écrit jamais d'alias.** Seul un appui humain
(`recipe/ingredient/match`) fait passer une ligne en `confirmed` et crée
l'alias. Sans cette règle, un appariement automatique faux deviendrait permanent
et contaminerait toutes les recettes suivantes — c'est exactement le
ré-appariement par nom qui a produit 35 doublons dans Grocy en avril 2026.

**`ignored` est un état de plein droit.** « Sel », « poivre », « eau » n'ont pas
vocation à être suivis en stock. Une ligne `ignored` s'affiche dans la recette,
ne décrémente rien, et ne réapparaît jamais dans les manques. Sans cet état, le
même arbitrage serait à reprendre à chaque recette.

**Ce qui reste à la main, et c'est assumé :** une ligne `unmatched` ou une ligne
dont la quantité est inutilisable (§ 9) bloque le décrément de *cette ligne*,
jamais le repas. L'écran de validation la montre comme « à sortir à la main » et
la validation continue sans elle. Refuser un dîner entier parce qu'une gousse
d'ail n'est pas appariée serait une leçon de morale, pas un outil.

## 9. Unités et quantités : une seule écriture

Le grief n° 2 contre Grocy est écrit noir sur blanc dans le lot 0 : la quantité
écrite deux fois, `amount` + `qu_id` d'un côté (la valeur MACHINE, celle que
`grocy.consume_*` décrémente), `variable_amount` de l'autre (la valeur LISIBLE,
celle que la tablette affiche), sans aucun garde-fou entre les deux. Le défaut
concret : 42 lignes portaient l'unité de conditionnement (`1.5 Bouteille`
d'huile d'olive) alors que le nombre était déjà en centilitres. Le bouton [×] de
la tablette retirait une bouteille et demie de stock à chaque burger.

**Le lot 3 n'écrit qu'un seul nombre.** Une ligne d'ingrédient porte :

- `amount` — le nombre, tel qu'il est dit ;
- **au plus une** mesure : `packaging_id` (propre au produit ou à l'article :
  « 1 tranche = 30 g ») **ou** `measure_id` (universelle : « 1 cs = 15 ml »).
  Aucune des deux → `amount` est directement en unité de base du produit.

La quantité en unité de base est **calculée**, à la lecture, par la fonction qui
existe déjà :

```python
base = to_base_quantity(amount, mesure.base_quantity if mesure else None)
```

Le libellé affiché — « 2 cs », « 150 g », « ½ oignon » — est **calculé lui
aussi**, depuis les deux mêmes valeurs. Il n'existe nulle part en base. Les
deux lectures que Grocy tenait à la main en écrivant deux fois deviennent deux
rendus d'une seule écriture. C'est la règle du lot 0 § 6.1 appliquée aux
recettes : *les conditionnements sont une couche d'affichage, jamais de
stockage*.

`raw_text` est conservé — « ½ tomate en rondelles », « 2 tbsp olive oil » — et
son statut est le même que celui d'`article.off_raw` : **provenance, jamais
calcul**. Aucun code de décrément ne le lit, aucun affichage de quantité ne
s'en sert. Il sert à comprendre d'où vient une ligne quand elle est fausse, et à
relancer un appariement.

**Quand la quantité est refusée.** Si la mesure de la source ne se ramène pas à
l'unité de base du produit, la ligne garde `amount = NULL` :

| Cas | Décision |
|---|---|
| Masse ou volume convertible (`g`, `kg`, `mg`, `ml`, `cl`, `dl`, `l`) vers la même dimension | Converti, `measure_id` à `NULL`, `amount` en unité de base |
| Mesure culinaire connue, produit en `ml` ou en `g` | `measure_id` renseigné, `amount` tel quel |
| Mesure culinaire, produit en `piece` | **Refusé.** Un yaourt ne se dose pas à la cuillère |
| Masse donnée pour un produit suivi en `piece` | **Refusé** — le lot 1 refuse déjà d'inventer un diviseur (§ 7.4, § 11), et pour la même raison : un poids par pièce deviné écrit un chiffre faux dans un journal en ajout seul |
| Volume donné pour un produit suivi en `g`, ou l'inverse | **Refusé** |
| Rien de chiffré (« un filet d'huile », « selon le goût ») | `amount` à `NULL`, la ligne s'affiche et ne décrémente rien |

Une ligne sans `amount` est parfaitement légitime. Elle apparaît dans la
recette, dans le bloc Ingrédients, et dans l'écran de validation sous « à sortir
à la main ». `NULL` veut dire inconnu, jamais zéro — la règle du lot 0 § 7.4,
qui vaut ici aussi.

**Mise à l'échelle.** Un repas porte `servings` ; la recette porte le sien. Le
facteur est `meal.servings / recipe.servings`, appliqué à la quantité **en unité
de base**, jamais à `amount` (multiplier « 1 cs » par 1,5 donne « 1,5 cs », ce
qui n'est ni faux ni utile ; multiplier 15 ml par 1,5 donne 22,5 ml, ce qui se
décrémente). Le facteur ne touche évidemment pas les lignes sans quantité.

**Les demis.** Grocy affichait « ½ ». Ici `amount` vaut `0.5` et le rendu d'un
produit en `piece` écrit « ½ » pour 0,5, « ¼ » pour 0,25, « ⅓ » pour ~0,333 —
côté panneau, dans `nombres.ts` qui fait déjà le formatage français. Un seul
nombre en base, plusieurs façons de le lire.

## 10. La source des recettes

**TheMealDB**, `https://www.themealdb.com/api/json/v1/{key}/`. Retenue pour
trois raisons et une seule vraiment décisive :

1. **Aucun compte, aucune clé à obtenir.** La clé publique de test vaut `1` ;
   une clé de soutien se pose dans les options si le débit devient un problème.
   Une source qui exige une inscription est une source qui casse le jour où le
   quota gratuit change de politique, et il n'y a personne pour surveiller ça.
2. Sa forme (`strIngredient1..20` + `strMeasure1..20`) se projette directement
   sur `recipe_ingredient` : un nom, une mesure, une ligne.
3. `filter.php?i=<ingrédient>` répond à la seule question qu'un garde-manger
   permet de poser et qu'un livre de cuisine ne permet pas : *qu'est-ce que je
   peux faire avec ça*.

Les trois routes utilisées : `search.php?s=`, `filter.php?i=`, `lookup.php?i=`.

**Le contrat réseau est celui du lot 1, mot pour mot.** Le transport est
injecté — le protocole `OffTransport` de `off/client.py` (`get_json(url,
headers, timeout)`) convient tel quel, et `AiohttpTransport` est déjà tenu une
seule fois dans `HomeStockData.transport` : un test qui remplace ce champ ferme
d'un coup toutes les sorties réseau, celle-ci comprise. Timeout 10 s, **une
seule tentative, aucune reprise**. Un import en lot respecte un intervalle,
comme `BULK_INTERVAL` le fait pour Open Food Facts.

**Rien ne bloque si le réseau est coupé.** C'est la règle posée au lot 1 et elle
tient ici sans effort : la source en ligne ne sert qu'à *découvrir* des
recettes. Les recettes déjà en base, le planning, la vue cuisine et la
validation d'un repas ne font aucun appel réseau — la recette du soir est en
SQLite, les ingrédients pointent sur des produits locaux, le décrément est une
transaction locale. TheMealDB injoignable produit une recherche vide et un
message ; il ne retarde pas un dîner.

**Les images restent chez la source** (`strMealThumb`) : `recipe.image_url`
stocke l'URL, le panneau la charge. Ne pas la rapatrier est une dette assumée et
inscrite au § 20 — avec sa conséquence : une recette perd sa photo si la source
disparaît. Pour les 87 recettes Grocy, la question est différente et le lot 7
devra la trancher avant l'extinction : les images sont servies **sans clé
d'API** par `https://grocy.allanic.me/api/files/recipepictures/<nom en base64>`,
donc elles meurent avec le conteneur. Elles doivent être copiées, pas
référencées.

## 11. L'adaptation par un agent conversationnel

TheMealDB est en anglais, ses mesures sont approximatives (« 1 tbsp », « a
handful »), et ses instructions sont un pavé de texte sans découpage. Il faut
traduire, découper en étapes, isoler les noms d'ingrédients et normaliser les
mesures. C'est un travail de modèle de langue.

**Décision : le composant n'embarque aucune clé d'API.** L'adaptation passe par
un **agent conversationnel de Home Assistant**, désigné dans les options de
l'entrée de configuration :

| Option | Défaut | Effet |
|---|---|---|
| `recipe_agent` | *(vide)* | `entity` selector sur le domaine `conversation`. Vide → aucune adaptation |
| `recipe_source_key` | `1` | Clé TheMealDB |

Quatre raisons, dans l'ordre où elles pèsent :

1. **Aucun second magasin de secrets.** La clé Gemini vit déjà dans l'entrée de
   configuration de l'intégration Google Generative AI, chiffrée avec le reste
   du `.storage` de Home Assistant. En redemander une à `home_stock` créerait un
   second endroit à protéger, à sauvegarder et à faire tourner.
2. **La maison a déjà ce qu'il faut.** Les backends `Gemini Flash` et
   `Gemini Pro` sont configurés et servent déjà `conversation.personas_studio_home_manager`.
3. **Le composant part sur HACS.** Le lot 2 a posé la règle en refusant de coder
   Bleuenn en dur dans le composant (le blueprint DLC est livré, jamais
   installé) : `home_stock` ne code pas un fournisseur de LLM en dur non plus.
4. **La clé `GEMINI_KEY` de `data/tools/grocy-off/.env` est une clé
   d'outillage**, utilisée par `recettes_images.py` pour générer les images de
   couverture avec `gemini-3.1-flash-image`. Elle appartient au dépôt d'outils,
   n'est pas versionnée (le `.env` ne l'est pas), et **n'est recopiée nulle
   part** — ni dans ce document, ni dans le composant. Le propriétaire la
   reporte lui-même dans l'intégration Google Generative AI s'il veut ce
   backend ; le composant ne la lit jamais.

**Le mécanisme.** `recipes/adapt.py` construit une invite en français qui
demande **un objet JSON et rien d'autre**, appelle `conversation.process` sur
l'agent choisi, et lit sa réponse défensivement :

- la réponse est cherchée d'abord telle quelle, puis dans le premier bloc
  délimité par des accolades équilibrées — un agent conversationnel a le droit
  d'ajouter « Voici la recette adaptée : » devant, c'est même son métier ;
- le résultat est validé champ par champ avec les mêmes helpers que le reste du
  composant (`bounded_text`, `finite_float`, `bounded_int`) : un modèle qui rend
  `servings: "quatre"` ou un titre de 40 000 caractères n'écrit rien ;
- **toute anomalie fait échouer l'adaptation entière, jamais à moitié.** La
  recette est alors écrite telle quelle depuis la source, `language = 'en'`,
  `needs_review = 1`, `adapted_at = NULL`.

**Rien ne bloque.** Agent absent, agent en panne, quota épuisé, réponse
illisible : la recette existe quand même, en anglais, marquée à relire, et le
service `home_stock.adapt_recipe` la reprendra plus tard. C'est le même contrat
que le lot 1 a écrit pour Open Food Facts injoignable — l'article est créé avec
ce qu'on a, `resync_off` le complétera.

**L'adaptation ne touche jamais une recette `confirmed`.** Un ingrédient dont
l'appariement a été validé à la main, une étape corrigée par le propriétaire :
la ré-adaptation ne les réécrit pas, exactement comme `article.manual_fields`
protège une valeur saisie d'une resynchronisation OFF.

## 12. Le planning et l'entité `calendar`

Le lot 0 annonçait « Planning de la semaine (`calendar`) » dans la colonne
Lovelace de sa répartition (§ 5.1). C'est tenu : `calendar.home_stock_meals`
est une vraie entité, la carte native de Home Assistant l'affiche, et le
planning se manipule depuis les deux surfaces.

**`meal.day` est une journée ALIMENTAIRE, pas une date civile.** C'est la
frontière de 4 h posée au lot 2 (`domain/foodday.py`). Un dîner qui se prolonge
et se valide à 01:00 est imputé à la veille, comme l'est déjà son mouvement de
consommation. Sans cette règle, le repas et le mouvement qu'il produit
tomberaient dans deux journées différentes, et le journal du panneau ne
retrouverait pas le repas qui a fait monter sa barre.

**Ce que l'entité expose.**

- `async_get_events(start, end)` rend un `CalendarEvent` par repas. `summary` :
  le nom de la recette, celui du produit, ou la note. `start` : le jour du repas
  à `meal_slot.default_time`, dans le fuseau de Home Assistant. `end` :
  `+ duration_minutes`. `uid` : `meal.uid`. `description` : la liste des
  ingrédients et ce qui manque.
- La propriété `event` rend le prochain repas non validé, ou celui en cours.
- `supported_features = CREATE_EVENT | DELETE_EVENT | UPDATE_EVENT`. Pas de
  `RRULE` : un menu de la semaine n'est pas un événement récurrent, et
  l'annoncer récurrent promettrait un comportement qu'on ne veut pas écrire.

**Poser un repas.** `async_create_event` reçoit un `summary` et un début. Le
créneau se déduit de l'heure : celui dont `default_time` est le plus proche. Le
`summary` est passé à `matching.candidates()` contre les recettes ; au-delà du
seuil de présélection, le repas pointe la recette, sinon c'est un repas `note`.
Un repas posé depuis la carte Lovelace est donc un repas complet, décrémentable,
et pas une chaîne de caractères sans suite.

**Déplacer un repas.** `async_update_event` change `day`, `slot_key` et
`position`. Le glisser-déposer de la carte native marche, et
`home_stock/meal/move` fait la même chose depuis le panneau. Un repas `done` ne
se déplace pas : ses mouvements portent une date que rien ne peut plus changer,
et déplacer la ligne les décorrélerait silencieusement. Le refus est explicite.

**Annuler un repas.** `async_delete_event` supprime la ligne si `state =
'planned'`. Un repas `done` n'est pas supprimé mais passé à `skipped` — la
suppression détruirait la référence `movement.ref_type = 'meal'` que le journal
porte déjà et qui, elle, est en ajout seul. Un repas dont l'heure est passée
sans validation reste `planned` : le composant ne décide pas tout seul qu'un
repas n'a pas eu lieu.

## 13. Valider un repas : cuisiner, puis manger

C'est le cœur du lot. La séquence est en **deux temps distincts**, et cette
séparation est ce qui rend la comptabilité juste.

### 13.1 Simuler d'abord

`home_stock/meal/preview` — et `home_stock.validate_meal` avec `dry_run: true`,
qui est la valeur par défaut — **n'écrit rien** et rend, par ligne
d'ingrédient : le produit apparié, `needed` (quantité en unité de base, mise à
l'échelle), `available`, `batches` (les lots que le FIFO prendrait et combien
dans chacun) et `status` parmi `ok`, `short`, `unmatched`, `unquantified`,
`ignored`. Plus le récapitulatif du plat produit : parts, DLC proposée, coût et
neuf nutriments estimés, et la liste de ce qui sera sorti à la main.

La simulation appelle `domain/stock.allocate()` — la même fonction que la sortie
réelle, pas une seconde implémentation. Une simulation qui ne partage pas son
code avec l'exécution est une simulation qui ment un jour.

### 13.2 Écrire ensuite, en une transaction

`dry_run: false`, dans **une seule transaction SQLite** : elle passe entièrement
ou pas du tout. Trois écritures, dans cet ordre.

**1. Les ingrédients sortent, motif `cooked`.** Un `consume()` par ligne, donc
allocation FIFO selon la règle du lot 0 § 7.1 (lot ouvert d'abord, puis DLC la
plus proche, puis entrée la plus ancienne), donc **un mouvement par lot
traversé**, chacun figeant son prix, ses kcal et ses huit macros.
`ref_type = 'meal'`, `ref_id = meal.id` — les deux colonnes que le lot 0 a
posées « pour les lots ultérieurs » trouvent ici leur premier usage. Clé :
`meal:<id>:ing:<recipe_ingredient_id>`.

**2. Le plat entre, motif `cooked`.** Un lot sur le produit de restes de la
recette (§ 14) : quantité = parts produites, `best_before` = jour +
`leftover_shelf_life_days`, emplacement = le frigo, prix et neuf nutriments
calculés au § 14. Clé : `meal:<id>:dish`.

**3. La part du soir sort, motif `consumption`.** Un `consume_batch()` sur le lot
qu'on vient de créer, quantité = `portions_eaten`, avec les
`parts_total`/`parts_mine` du repas : le partage entre assiettes du lot 2
s'applique au repas entier d'un coup. Clé : `meal:<id>:eaten`. Quand
`portions_eaten` égale le nombre de parts, la poussière flottante (lot 0 § 7.2)
referme le lot dans la même transaction — il n'y a pas de reste, et rien de
spécial n'a été écrit pour ça.

### 13.3 Pourquoi `cooked` ne compte pas

Si les ingrédients sortaient en `consumption`, leurs kcal seraient portées au
jour de la cuisson **et** celles du plat au jour où on le mange : le même repas
compté deux fois. `cooked` **déplace la valeur** des ingrédients vers le plat,
sans que rien ne soit ni acheté ni mangé. Il ne touche donc ni `kcal_today` et
les macros, ni `cost_today` / `cost_total`, ni `cost_waste_total` — il n'est pas
dans `CONSUME_REASONS`. Et `sensor.home_stock_stock_value` est inchangé au
total : la valeur quitte les ingrédients et entre dans le plat.

D'où une conséquence qui vaut d'être dite : **un plat au frigo garde sa valeur
dans le stock**, et cette valeur est dépensée le jour où il est mangé. C'est la
définition de la compta du lot 0 — « ce qui sort du stock ce jour-là » —
appliquée sans double comptage.

### 13.4 Ce qui manque, et ce qui ne se convertit pas

| Situation | Comportement |
|---|---|
| Ligne `unmatched` ou sans quantité | Ignorée du décrément, listée dans `skipped_ingredient_ids`, signalée à l'écran comme « à sortir à la main » |
| Ligne `ignored` (sel, eau) | Ignorée, sans signalement |
| Stock insuffisant | La ligne est proposée **réduite au disponible** dans la simulation. Le propriétaire accepte, ou la retire. Sans arbitrage, la validation est refusée : servir 200 g quand on en demande 500 sans le dire écrit un chiffre faux |
| Aucun lot du tout | La ligne bascule automatiquement en « à sortir à la main » |
| Conversion impossible | Traitée comme « sans quantité » : jamais de diviseur deviné |
| Rejeu de la validation | Les clés d'idempotence rendent les mêmes `movement_ids`, aucun second décrément |

### 13.5 Réversibilité : il n'y en a pas, et c'est dit

`movement` refuse l'`UPDATE` et le `DELETE` — deux triggers le garantissent
depuis `m001`. **Une validation n'est donc pas annulable au lot 3.** Ce qui la
remplace :

- la **simulation est obligatoire** avant l'écriture, et l'écran de validation
  demande deux appuis (armement puis confirmation), comme toute action
  destructive du panneau ;
- la transaction est **unique** : jamais un demi-repas ;
- la clé d'idempotence rend le rejeu **sans effet**, y compris depuis la file
  hors-ligne ;
- `meal.state` peut retomber à `planned` (la table est mutable), mais les
  mouvements restent — et le panneau le dit en toutes lettres plutôt que de
  laisser croire à une annulation.

Annuler pour de bon demande un motif `correction` et des mouvements de
compensation. Le lot 2 l'a déjà différé au lot 4, groupé avec la correction de
prix. On ne l'anticipe pas ici : deux mécanismes de correction écrits séparément
divergeraient.

## 14. Les restes cuisinés

Le lot 2 a laissé ceci en points différés : *« Restes cuisinés comme objet en
stock : lot 3 »*. Voici la forme retenue.

**Un produit de restes par recette**, créé paresseusement à la première
validation : nom « Reste — ⟨recette⟩ », `base_unit = 'piece'` (une pièce = une
part), catégorie « Plats cuisinés », `default_location_id` = le premier
emplacement de `kind = 'fridge'`. `product.name` est `UNIQUE` depuis `m001` : en
cas de collision, l'identifiant de recette est suffixé.
`recipe.leftover_product_id` retient le lien, donc une seconde cuisson réutilise
le même produit. Un **article générique** (`is_generic = 1`, sans code-barres)
l'accompagne — mécanisme du lot 0 § 6.3, repris sans exception : un lot pointe
toujours vers un article, donc aucun cas particulier dans le code de sortie, de
kcal ou de coût.

**Mais les valeurs sont sur le LOT, pas sur l'article** (amendement A2). Deux
cuissons de la même recette n'ont ni les mêmes nutriments ni le même coût ;
écrire sur l'article partagé écraserait la cuisson précédente pendant que ses
parts sont encore au frigo. Pour chacune des dix valeurs (neuf nutriments plus
le coût) :

```
valeur_par_part = Σ(valeur figée sur les mouvements `cooked` sortants) / parts_produites
```

Les mouvements viennent d'être écrits dans la même transaction et portent déjà
leurs valeurs figées (lot 2, A3) : on somme ce qui a réellement quitté le stock,
pas ce que la recette prévoyait.

**Règle du `NULL`, valeur par valeur.** Si *un seul* mouvement ingrédient porte
`NULL` sur une valeur, le plat porte `NULL` pour cette valeur-là — jamais une
somme partielle présentée comme un total. Chaque nutriment est traité
indépendamment : les kcal sont souvent connues quand les fibres ne le sont pas,
et refuser les neuf parce qu'une manque perdrait de l'information vraie. C'est
la règle du lot 0 § 7.4, et `kcal_today` continue de compter dans son attribut
`unvalued_movements` les sorties non chiffrées qui en résultent.

**DLC :** `LEFTOVER_SHELF_LIFE_DAYS = 3` jours, réglable par recette
(`recipe.leftover_shelf_life_days`) — trois jours au réfrigérateur est la
recommandation courante pour un plat cuisiné ; une soupe congelée le dit sur sa
fiche.

**Effet de bord voulu :** les restes entrent dans
`binary_sensor.home_stock_expirations`, `todo.home_stock_expirations` et
`event.home_stock_expiration`. Le blueprint DLC du lot 2 annoncera donc « le
gratin de dimanche périme demain » sans une ligne de code de plus — c'est le
principal intérêt de traiter un reste comme n'importe quel autre lot.

**Ce qu'ils ne font pas :** pas de `min_quantity`, donc jamais de rupture ; pas
de rayon, donc « Autre » si quelque chose les mettait un jour sur une liste de
courses — ce que le lot 4 devra explicitement empêcher.

## 15. Surface Home Assistant

### 15.1 Commandes websocket

| Commande | Entrée | Sortie |
|---|---|---|
| `home_stock/recipes/list` | `search?`, `only_reviewable?` | Recettes, avec le compte d'ingrédients non appariés |
| `home_stock/recipe/get` | `recipe_id` | Recette, étapes, puces, ingrédients résolus et candidats |
| `home_stock/recipe/create` | Recette complète | `{recipe_id}` |
| `home_stock/recipe/update` | `recipe_id`, `fields` | — |
| `home_stock/recipe/delete` | `recipe_id` | Refusée si un repas `done` la référence |
| `home_stock/recipe/ingredient/match` | `ingredient_id`, `product_id?`, `state`, `create_alias?` | La ligne mise à jour |
| `home_stock/recipe/search_external` | `query?`, `ingredient?` | Fiches de la source. **N'écrit rien** |
| `home_stock/recipe/import_external` | `source_ref` | `{recipe_id, adapted}` |
| `home_stock/meals/list` | `start`, `end` (journées alimentaires) | Repas, avec leurs manques |
| `home_stock/meal/plan` | `day`, `slot_key`, `recipe_id`\|`product_id`+`amount`\|`note`, `servings?` | `{meal_id, uid}` |
| `home_stock/meal/move` | `meal_id`, `day`, `slot_key`, `position?` | — |
| `home_stock/meal/cancel` | `meal_id` | — |
| `home_stock/meal/preview` | `meal_id`, `servings?` | Le plan de décrément (§ 13.1). **N'écrit rien** |
| `home_stock/meal/validate` | `meal_id`, `portions_eaten`, `parts_total?`, `parts_mine?`, `skip_ingredient_ids?`, `idempotency_key` | `{movement_ids, batch_id}` |

Toute commande qui écrit porte une `idempotency_key` fournie par le panneau,
comme depuis le lot 1 : c'est ce qui rend la file hors-ligne rejouable sans
doublon, et `tests/test_offline_queue_contract.py` dérive la liste des commandes
mises en file depuis le source TypeScript — une commande dont le schéma refuse
la clé fait échouer ce test le jour où elle est écrite.

Validation par les helpers partagés de `validators.py`, et la règle du lot 1
reprise mot pour mot au lot 2 tient ici : **aucune des deux surfaces n'a le droit
d'être la plus faible.** Ce que le websocket refuse, le service le refuse aussi,
et réciproquement. Concrètement, pour ce lot : `servings` et `portions_eaten`
passent par `finite_float` puis une borne stricte `> 0` ; `parts_total` et
`parts_mine` par `parts_count` (donc `1 ≤ total ≤ 24`, `0 ≤ mine ≤ total`) ;
`day` par `iso_date` (forme étendue `AAAA-MM-JJ` uniquement, pour les mêmes
raisons qu'au lot 1) ; `slot_key` par un `vol.In` sur la constante ; tous les
identifiants par `bounded_int` ; tous les textes par `bounded_text`.

### 15.2 Services

| Service | Réponse | Rôle |
|---|---|---|
| `home_stock.plan_meal` | — | Poser un repas, en YAML ou en vocal |
| `home_stock.validate_meal` | `OPTIONAL` | `dry_run: true` **par défaut** : rend le plan sans rien écrire |
| `home_stock.import_recipe` | `OPTIONAL` | Une référence de source, ou une recherche |
| `home_stock.adapt_recipe` | — | Relance l'adaptation d'une recette importée sans agent |
| `home_stock.query_meals` | `ONLY` | Ce qui est prévu sur une plage. Le pendant de `query_stock` |

`validate_meal` en simulation par défaut est délibéré et suit `import_grocy_catalog`,
qui simule par défaut depuis le lot 0 : un service qui décrémente un stock ne
doit pas le faire au premier appel exploratoire depuis les Outils de
développement.

`query_meals` est un service à réponse (`SupportsResponse.ONLY`) et non une
entité : c'est lui qui répondra à « qu'est-ce qu'on mange ce soir ? » au lot 6,
sans créer d'entité par repas — même raisonnement qu'au lot 0 pour
`query_stock`, et même raison de fond : 299 produits ne font pas 299 entités,
et un planning ne fait pas une entité par jour.

Libellés et descriptions en français dans `services.yaml`, sélecteurs compris.

### 15.3 Entités

| Entité | Rôle |
|---|---|
| `calendar.home_stock_meals` | Le planning (§ 12) |
| `sensor.home_stock_next_meal` | Le nom du prochain repas. Attributs : jour, créneau, recette, nombre d'ingrédients manquants |
| `sensor.home_stock_recipes` | Nombre de recettes actives. Attributs : à relire, ingrédients non appariés |
| `sensor.home_stock_missing_ingredients` | Nombre de produits manquants pour les sept prochains jours. Attribut : la liste |

`sensor.home_stock_missing_ingredients` est **un compteur, pas une liste
cochable**. Une entité `todo` serait déjà la liste de courses, qui est le lot 4 :
cocher y signifie « acheté », donc une session, un prix, un rangement — tout un
mécanisme qui n'existe pas encore. Le capteur porte l'information ; le lot 4 la
transformera en liste.

Aucune entité `event` pour la validation d'un repas. Une automation qui veut
réagir a déjà l'état de `calendar.home_stock_meals` et celui de
`sensor.home_stock_next_meal`. Le lot 2 a créé `event.home_stock_expiration`
parce qu'un basculement de DLC est un fait que rien n'observe autrement ; une
validation, elle, est un geste humain qui vient d'avoir lieu sur l'écran.

`entity_id` en anglais, noms affichés dans `translations/fr.json` — la
convention de nommage du lot 0 § 14, sans exception.

## 16. Le panneau

Trois écrans de plus, sur le même moteur : `lit`, rollup, sources dans
`frontend/src/`, build vers `custom_components/home_stock/panel/`. `Ecran` gagne
`'recettes'`, `'recette'` et `'planning'` ; la barre de navigation les expose ;
le garde-fou du lot 1 sur le rangement en attente s'applique à ces cibles comme
aux autres.

| Écran | Ce qu'on y fait |
|---|---|
| Recettes | Recherche locale, liste dense, badge « à relire » et « n non appariés ». Un bouton « Chercher ailleurs » interroge la source, hors ligne il est simplement désactivé |
| Recette | La vue cuisine : couverture, bloc Ingrédients, puis **une page par étape** |
| Planning | La semaine. Poser, déplacer, annuler, valider |

**La vue cuisine** est l'écran annoncé dès le lot 0 comme relevant de la SPA et
non de Lovelace, et la raison n'a pas changé : on y est debout, les mains sales,
à un mètre de l'écran. Une page par étape, plein écran, gros texte, image en
tête. Navigation **au bouton uniquement**, précédent / suivant : aucun geste,
aucun appui long — la contrainte des tablettes de la maison vaut ici aussi. Le
bloc Ingrédients s'atteint en un appui depuis n'importe quelle étape et revient
où on en était. Les minuteurs sont des boutons dessinés depuis `timer_label` /
`timer_seconds` et décomptés **dans le panneau** : aucune entité `timer` de Home
Assistant n'est créée — une recette de quatre étapes en produirait quatre, et
elles lui survivraient. `navigator.wakeLock`, quand l'API existe, est demandé à
l'ouverture et relâché à la sortie : un écran qui s'éteint pendant qu'on pétrit
est une raison de revenir au papier.

**L'écran de validation** — atteint depuis la dernière étape ou depuis le
planning — montre une ligne par ingrédient avec son statut (§ 13.1), le
récapitulatif du plat, le sélecteur de parts mangées et le partage optionnel
repris tel quel de l'écran « manger » du lot 2. Confirmation **en deux appuis** :
une validation écrit dans un journal en ajout seul, c'est destructif au sens du
panneau, donc c'est le même geste que le cochage d'une tâche sur les tablettes.

**L'écran planning** affiche sept colonnes × quatre créneaux en 1280 × 800, et
**une journée à la fois** en 412 × 915 avec précédent/suivant. Pas de grille de
sept colonnes réduite : elle produirait des cibles sous 48 px et
`outils/verifier-rendu.mjs` la refuserait, à juste titre.

**Contraintes de rendu** inchangées depuis le lot 1 : 412 × 915 et 1280 × 800,
cibles ≥ 48 px, contraste ≥ 4,5:1, aucun débordement horizontal, aucun texte
tronqué. Quatre scénarios de plus, chacun vérifiant d'abord qu'il a bien atteint
son écran : liste de recettes, étape avec minuteur, planning chargé, validation
avec un ingrédient manquant.

**Hors ligne**, toutes les écritures passent par la file du lot 1, clé
d'idempotence comprise, et une recette déjà chargée reste lisible sans réseau.
C'est la situation normale : le Wi-Fi de la cuisine n'est pas meilleur que celui
d'un rayon de supermarché.

## 17. Erreurs

| Situation | Comportement |
|---|---|
| TheMealDB injoignable | Recherche vide, message explicite. Aucune recette existante n'est affectée |
| Agent conversationnel absent ou muet | Recette écrite telle quelle, `needs_review = 1`, `adapted_at` vide |
| Réponse de l'agent illisible | Idem. **Jamais d'adaptation partielle** |
| Ingrédient non apparié | Ligne affichée, jamais décrémentée, listée dans `skipped_ingredient_ids` |
| Quantité inconvertible | Traitée comme absente. Aucun diviseur deviné |
| Stock insuffisant | `InsufficientStock`, message français disant ce qui reste ; la simulation le montre avant l'écriture |
| Validation rejouée | Clés d'idempotence : mêmes `movement_ids`, aucun second décrément |
| Validation d'un repas déjà `done` | Refusée, message explicite |
| Déplacement d'un repas `done` | Refusé : ses mouvements portent une date figée |
| Suppression d'une recette référencée par un repas `done` | Refusée. `active = 0` est le chemin |
| Collision de nom sur un produit de restes | Suffixé par l'identifiant de recette |
| Nutriment manquant sur un ingrédient | `NULL` sur le plat pour ce nutriment-là seulement |

Les messages passent par `messages.py`, qui traduit une exception du domaine en
un couple (code, phrase française). Les motifs nouveaux de ce lot y sont
ajoutés ; un message non reconnu retombe sur la phrase générique plutôt que
d'exposer un `repr` Python à quelqu'un qui a les mains dans la farine.

## 18. Ce que le lot 3 pose pour que le lot 7 ne soit qu'une jointure

Le lot 7 devra reprendre 87 recettes `normal`, leurs 420 lignes d'ingrédients,
92 entrées de planning, 4 sections et 41 images. Ce lot-ci pose tout ce qu'il
faut pour que ce soit un `INSERT … SELECT` guidé, et pas un ré-appariement.

| Grocy | home_stock | Comment |
|---|---|---|
| `recipes.id` | `recipe.external_ref` + `recipe.source_ref` (`source = 'grocy'`) | Import rejouable, index unique partiel |
| `recipes.base_servings` | `recipe.servings` | Direct. 63 recettes sur 87 sont à 1 |
| `recipes.description` (HTML) | `recipe_step` + `recipe_instruction` | Découpe sur les `<div class="page-recipes">` de premier niveau, `<h3>Étape N — …</h3>` pour le titre, `<ol><li>` pour les puces |
| `#Nom:secondes` dans une puce | `timer_label` + `timer_seconds` | Extrait à l'import, retiré du texte |
| `recipes_pos.id` | `recipe_ingredient.external_ref` | — |
| `recipes_pos.product_id` | `recipe_ingredient.product_id` | **Par `product.external_ref`**, jamais par nom. C'est le ré-appariement par nom qui a produit 35 doublons en avril 2026 |
| `recipes_pos.amount` + `qu_id` | `amount` + `packaging_id`/`measure_id` | La table de correspondance des unités de l'import du lot 0 sert ici aussi |
| `recipes_pos.variable_amount` | `recipe_ingredient.raw_text` | **Provenance uniquement.** Jamais réimporté comme seconde quantité — c'est le grief n° 2, il ne revient pas par la porte de derrière |
| `recipes_pos.ingredient_group` | `group_name` | Direct |
| `meal_plan_sections` | `meal_slot.external_ref` | Semé par `m004` avec les refs `1`, `2`, `3` |
| `meal_plan` (type `recipe`, `note`) | `meal` | `day`, `recipe_id`, `recipe_servings`, `note`, `done` → `state` |
| Images `recipepictures/<base64>` | À copier | Servies sans clé d'API, elles meurent avec le conteneur |

Deux filtres à écrire dans le lot 7 et déjà connus, donc inscrits ici :

- **`WHERE type = 'normal'` sur `recipes`.** La base contient aussi 15
  `mealplan-week`, 65 `mealplan-day`, 90 `mealplan-shadow` et 15 de type `1` :
  ce sont les copies fantômes que le README de `grocy-off` décrit, 296 lignes de
  `recipes_pos` en plus des vraies. Les importer créerait 185 recettes fantômes.
- **`recipes_nestings` n'est pas importée.** 5 186 lignes, presque toutes
  générées par les copies fantômes. Les recettes imbriquées sont différées (§ 20).

## 19. Tests

Suites existantes vertes, plus ce qui suit. `./scripts/test.sh` pour le Python
(image alignée sur HA 2026.8.2), `npm test` et `node outils/verifier-rendu.mjs`
depuis `frontend/` pour le front.

**Python, en `pytest` pur, sans Home Assistant ni réseau — le gros du lot.**

- `domain/recipes.py` : mise à l'échelle (facteur non entier, ligne sans
  quantité non touchée) ; résolution d'une quantité en unité de base pour chaque
  ligne du tableau du § 9, **refus compris** ; plan traversant plusieurs lots ;
  plan sur un stock insuffisant.
- Appariement : rejoué sur un jeu de fixtures dérivé des **420 lignes réelles**
  de `recipes_pos` et des 299 produits, versionné dans `tests/fixtures/recipes/`.
  On mesure le taux d'appariement automatique, et on épingle les cas nommés qui
  doivent marcher (« coriandre fraîche », « huile d'olive », « œufs ») comme ceux
  qui doivent rester `unmatched` plutôt que d'être devinés. Un alias confirmé
  l'emporte sur un `preselect` de score supérieur.
- Source : client TheMealDB sur fixtures capturées, transport double — timeout,
  404, JSON tronqué, `strIngredient` vide au milieu de la liste, mesure vide.
  Un test marqué `network`, désactivé par défaut, vérifie que le contrat n'a pas
  bougé — même dispositif qu'au lot 1 pour Open Food Facts.
- Adaptation : agent absent, agent qui lève, JSON pur, JSON entouré de prose,
  JSON tronqué, JSON aux champs hors bornes. Dans les cinq cas d'échec la
  recette existe, `needs_review = 1`, **rien n'est à moitié écrit**, et un champ
  `confirmed` n'est jamais réécrit.
- `m004` : tables créées, migration rejouable, semis idempotent, colonnes de
  `batch` à `NULL` sur l'existant, cascade `COALESCE(b, a, p)` dans ses trois cas.
- Validation : sortie FIFO avec un mouvement par lot ; plat entré au bon nombre
  de parts ; part mangée en `consumption` ; `cooked` **absent** de `kcal_today`,
  `cost_today` et `cost_waste_total` ; valeur totale du stock inchangée par la
  cuisson ; un nutriment `NULL` sur un ingrédient rend `NULL` ce nutriment-là et
  **pas les huit autres** ; rejeu rendant les mêmes `movement_ids` ; échec au
  milieu laissant la base intacte, aucun mouvement, aucun lot.
- Restes : produit et article créés une seule fois pour deux cuissons, collision
  de nom suffixée, DLC par défaut et par recette, lot présent dans
  `expiry_candidates`.
- Calendrier : `async_get_events` sur une plage, création par `summary` appariée
  puis non appariée, déplacement, refus de déplacer un `done`, suppression d'un
  `planned`, `skipped` sur un `done`.
- Websocket et services : chaque commande d'écriture refuse ce que son service
  jumeau refuse et l'inverse ; `dry_run` par défaut n'écrit rien ; `servings = 0`
  et `slot_key` inconnu refusés aux deux surfaces ; contrat de la file
  hors-ligne mis à jour.

**Front.** `recette.test.ts` (découpe en pages, navigation au bouton, minuteur
qui démarre et se remet à zéro, retour du bloc Ingrédients à l'étape courante) ;
`planning.test.ts` (semaine et jour, déplacement, refus sur un repas validé) ;
`validation.test.ts` (statuts par ligne, retrait d'une ligne, deux appuis,
virgule décimale sur les parts) ; `verifier-rendu.mjs`, quatre scénarios de plus
aux deux formats.

**Interdit, et c'est la règle depuis le lot 1 :** rien ne touche l'instance
vivante. Pas de redémarrage du conteneur, pas de rechargement de l'intégration,
pas de lecture du jeton, pas d'écriture dans `/opt/nivuus/HomeAssistant/config/`.
Grocy est en lecture seule, et seule une **copie** de `grocy.db` est lue —
jamais celle en production.

## 20. Points différés

| Sujet | Lot | Raison |
|---|---|---|
| **Corriger un repas validé** (motif `correction`) | 4 | Le journal est en ajout seul ; annuler demande des mouvements de compensation. Déjà groupé au lot 4 avec la correction de prix par le lot 2 |
| **Liste de courses depuis le planning** | 4 | `sensor.home_stock_missing_ingredients` porte déjà l'information ; en faire une liste cochable suppose la session d'achat du lot 4 |
| **Reprise des 87 recettes Grocy et de leurs images** | 7 | Le § 18 dit ce qu'il faut ; le faire maintenant importerait dans un modèle qu'on est encore en train de valider |
| **Rapatriement local des images de recettes** | 7 | Le lot 0 prévoyait une vue HTTP pour les images d'articles ; elle n'a jamais été écrite. La question se pose une fois, pour les deux, au moment où Grocy s'éteint |
| **Recettes imbriquées** (`recipes_nestings`) | ultérieur | 5 186 lignes chez Grocy, presque toutes issues des copies fantômes. Aucun usage réel constaté dans le foyer |
| **« Que cuisiner avec ce qui périme »** | ultérieur | Demande un score de recette contre l'état du stock. Tout est en place (`expiry_candidates`, `recipe_ingredient.product_id`), rien ne presse |
| **Nutriments d'une recette avant cuisson** | ultérieur | Calculables, mais faux tant que l'appariement n'est pas complet ; un chiffre affiché avant d'être fiable ne se corrige plus dans la tête de celui qui l'a lu |
| **Récurrence (`RRULE`) au calendrier** | — | Un menu de la semaine n'est pas un événement récurrent |
| **Génération d'images de recettes** | — | Reste dans l'outillage (`recettes_images.py`, `GEMINI_KEY` du `.env`) ; ce n'est pas le métier du composant |
| **Mise à l'échelle par convive nommé** | — | Le foyer suit une personne (`person.maxime_allanic`). Les parts comptent des assiettes, pas des noms — décision reprise du lot 2 |
| **Écriture vers Grocy** | jamais | L'import est à sens unique, décision du lot 0 |

*Validé le 2026-08-21.*
