# home_stock — Lot 0 : fondations du garde-manger

*Conception validée le 2026-08-18. Domaine HA : `home_stock`. Home Assistant 2026.8.2.*

## 1. Objectif

Remplacer Grocy par un composant natif Home Assistant qui gère les stocks de la
maison — alimentaire, ménager, équipements et piles — avec la nutrition et le prix
de chaque article, la planification de repas, la consommation par recette, et une
comptabilité kcal/€ par jour.

Trois griefs motivent le remplacement plutôt qu'une surcouche :

1. **L'interface est hors de HA.** Grocy est un site à part : pas d'entités natives,
   rien d'utilisable sur les tablettes murales ni dans l'application mobile.
2. **Le modèle de données se bat contre l'usage.** Unité de stock verrouillée par
   trigger dès le premier achat, quantité écrite deux fois (`amount` et
   `variable_amount`) sans garde-fou, copies fantômes `mealshadow`, produit et
   article confondus. Chacun de ces points a déjà produit un bug documenté dans
   `data/tools/grocy-off/README.md`.
3. **Des fonctions manquent** : aucune comptabilité kcal/jour ni prix/jour, aucun
   scan intégré à HA, aucune source de recettes.

Grocy reste en service pendant tout le développement. Il n'est éteint qu'au lot 7,
après reprise complète des données.

## 2. Décisions validées

| Sujet | Décision |
|---|---|
| Architecture | Composant HA unique + panneau SPA maison ; Lovelace partout où il ne handicape pas |
| Stockage | SQLite propre au composant (`config/home_stock.db`), migrations versionnées |
| Agrégats | Capteurs `total_increasing` + helpers `utility_meter` journaliers → statistiques long terme natives |
| Granularité | Lot, avec DLC et prix payé ; **sortie partielle** (200 g pris sur un paquet de 500 g) |
| Compta | kcal/jour et €/jour = **ce qui sort du stock** ce jour-là |
| Produit / article | Deux niveaux distincts : l'ingrédient culinaire et l'objet achetable identifié par son EAN |
| Scan | Caméra du Pixel via `BarcodeDetector`, dans une vue du panneau |
| Prix | Dernier prix connu → Open Prices → saisie manuelle → correction par photo du ticket |
| Recettes | API de recettes + traduction/adaptation par Gemini, appariement sur le catalogue |
| Nommage | Code, schéma et identifiants **en anglais** ; textes affichés en français (`translations/fr.json`) |

## 3. Découpage en lots

Le périmètre complet couvre huit lots. Chacun a son spec et son plan
d'implémentation ; ce document ne spécifie que le **lot 0**.

| Lot | Contenu | Livrable vérifiable |
|---|---|---|
| **0 — Fondations** | Schéma, catalogue, emplacements, rayons, lots de stock, journal, services, entités de synthèse, import du catalogue Grocy | Le stock réel est dans HA, consultable et modifiable |
| **1 — Scan & entrée** | Panneau SPA, scan caméra, enrichissement OFF (4 bases), création de lot, prix, mode magasin / mode rangement | Ranger 30 articles au téléphone sans clavier |
| **2 — Consommation & compta** | Sortie partielle FIFO, motifs, capteurs kcal/€ et macros par jour, alertes DLC | Graphes HA natifs jour/semaine/mois |
| **3 — Recettes & planning** | Source API + adaptation LLM, appariement ingrédient → produit, planning, validation = décrément | « Je valide le dîner » → le stock bouge juste |
| **4 — Liste de courses** | Manques + planning → liste, pointage au scan, coût du panier, ticket de caisse (Gemini), ordre des rayons par magasin et apprentissage du parcours | Une session de courses complète |
| **5 — Équipements & piles** | Piles (type, appareil, rechange), rechargeables (cycles, dernière charge), équipements (notice, garantie), consommables non alimentaires, reprise du raccord `maintenance.jinja` | `todo.maintenance` marche sans Grocy |
| **6 — Surfaces** | Bloc cuisine dans `wallpanel-app`, intents vocaux Bleuenn, vue dense PC | Les quatre surfaces annoncées |
| **7 — Migration & extinction** | Reprise du stock, de l'historique, des recettes et des images ; contrôles ; arrêt du container Grocy | Grocy éteint, rien de perdu |

Deux dépendances repérées d'avance :

- **Le catalogue Grocy arrive au lot 0**, pas au lot 7 : développer sur une base vide
  produit un système qui marche en démonstration et casse sur 299 produits réels.
- **`config/custom_templates/maintenance.jinja` lit `todo.grocy_batteries`** pour
  enrichir les tâches de pile (« 18 % — 1x CR2032 »). Il casse le jour où Grocy
  s'éteint : c'est un travail du lot 5, pas une découverte du lot 7.

## 4. Périmètre du lot 0

**Dans le lot :** schéma et migrations ; catalogue produits et articles ;
emplacements et rayons ; codes-barres ; conditionnements ; prix ; lots de stock ;
journal des mouvements ; règles d'entrée et de sortie (dont la sortie partielle
FIFO) ; services HA ; entités de synthèse ; commandes websocket de lecture ;
import rejouable du catalogue Grocy ; stockage de la réponse OFF brute.

**Hors du lot :** le panneau SPA et le scan (lot 1), l'appel réseau à OFF (lot 1 —
le lot 0 pose seulement la table qui l'accueille), les capteurs par jour (lot 2),
tout ce qui touche aux recettes, aux courses, aux piles.

À la fin du lot 0, le stock se manipule par services HA et se lit dans une vue
Lovelace. C'est volontairement austère : le lot 0 doit prouver le modèle, pas
l'ergonomie.

## 5. Architecture

### 5.1 Répartition Lovelace / SPA

Le composant expose de vraies entités HA d'abord. La SPA n'existe que là où
Lovelace échoue.

| Lovelace natif | SPA |
|---|---|
| Alertes DLC, ruptures (`binary_sensor`, `todo`) | Scan caméra en rafale |
| Liste de courses cochable (`todo`) | Saisie « 200 g sur ce lot » |
| kcal/jour, €/jour (`statistics-graph`) | Catalogue dense, édition d'un produit |
| Planning de la semaine (`calendar`) | Vue cuisine d'une recette |
| Boutons de validation (`button`, scripts) | Rangement des courses |

### 5.2 Modules

```
config/custom_components/home_stock/
├── manifest.json, const.py, __init__.py, config_flow.py
├── storage/
│   ├── database.py        # connexion sqlite3, WAL, exécution sérialisée en executor
│   ├── schema.py          # DDL de référence
│   ├── migrations/        # 001_initial.py, 002_…  — versionnées, testées
│   └── repositories.py    # un dépôt par agrégat (products, batches, movements…)
├── domain/                # AUCUNE dépendance à hass — testable en pytest pur
│   ├── units.py           # unités de base, conditionnements, conversions
│   ├── stock.py           # entrée, sortie FIFO, sortie partielle, transfert
│   └── nutrition.py       # kcal et coût d'un mouvement
├── coordinator.py
├── sensor.py, binary_sensor.py, todo.py
├── services.py, services.yaml
├── websocket_api.py       # la seule porte de la SPA
├── http.py                # images d'articles (binaire) uniquement
├── import_grocy.py        # import de catalogue, rejouable, hors démarrage
├── translations/fr.json, translations/en.json
└── panel/                 # ARTEFACT DE BUILD — jamais édité à la main
```

Le front vit dans `data/tools/home-stock-app/` : TypeScript, `lit`, rollup,
`vitest`, et un `verifier-rendu.mjs` réglé sur les formats téléphone. Même stack
et même outillage que `wallpanel-app`, dont on reprend les scripts.
`npm run build` écrit dans `custom_components/home_stock/panel/`.

La séparation `domain/` sans `hass` est délibérée : la logique qui a fait souffrir
Grocy (unités, quantités, FIFO) doit être testable sans démarrer Home Assistant.

## 6. Modèle de données

### 6.1 Les six décisions structurantes

1. **Trois unités de base, fermées : `g`, `ml`, `piece`.** Un produit en a une.
   Plus de référentiel où « Pot », « Paquet » et « cl » cohabitent — ce mélange a
   fait retirer une bouteille et demie d'huile d'olive à chaque burger dans Grocy.
   Changer l'unité de base reste possible : c'est une conversion explicite du stock
   existant, pas un trigger qui refuse.
2. **Les conditionnements sont une couche d'affichage, jamais de stockage.**
   « Paquet = 500 g », « cs = 13 ml ». On saisit et on lit en conditionnements, on
   stocke et on calcule en unité de base. Une seule vérité, deux lectures — au lieu
   des deux écritures à tenir synchrones de Grocy.
3. **Produit ≠ article.** Le `product` est l'ingrédient culinaire (« Moutarde ») :
   c'est lui que cite une recette. L'`article` est l'objet achetable identifié par
   son EAN, avec sa marque, son poids net et **sa propre nutrition**. « Moutarde
   Savora 265 g » et « 385 g » sont deux articles d'un même produit.
4. **Le lot porte son prix et sa DLC.** Un lot est ce qui est entré en une fois. La
   sortie prend le lot le plus proche de périmer, partiellement si besoin.
5. **Le journal est en ajout seul et il est la seule source de la compta.** Chaque
   mouvement fige ses kcal et son coût. Aucun agrégat n'est stocké. Une correction
   d'inventaire est un nouveau mouvement, jamais une réécriture du passé.
6. **La donnée externe est séparée de la donnée saisie.** La nutrition vient d'OFF
   dans ses propres colonnes, la réponse brute est conservée telle quelle, et une
   valeur corrigée à la main n'est jamais réécrite par une resynchronisation.

### 6.2 Schéma

Identifiants en anglais. Quantités en `REAL` dans l'unité de base. Prix en `REAL`,
en euros par unité de base.

```sql
CREATE TABLE location (            -- placard, frigo, congélateur, cellier…
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  kind TEXT NOT NULL,              -- 'pantry' | 'fridge' | 'freezer' | 'other'
  position INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE aisle (               -- rayon, dans l'ordre du parcours en magasin
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  position INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE category (            -- classement culinaire (ex-groupes Grocy)
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE
);

CREATE TABLE product (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  base_unit TEXT NOT NULL CHECK (base_unit IN ('g','ml','piece')),
  category_id INTEGER REFERENCES category(id),
  aisle_id INTEGER REFERENCES aisle(id),
  edible INTEGER NOT NULL DEFAULT 1,
  default_location_id INTEGER REFERENCES location(id),
  min_quantity REAL,               -- seuil de réapprovisionnement, unité de base
  days_after_opening INTEGER,      -- DLC secondaire une fois ouvert
  reference_kcal REAL,             -- kcal par unité de base, pour le frais sans EAN
  active INTEGER NOT NULL DEFAULT 1,
  external_ref TEXT,               -- id Grocy, pour un import rejouable
  UNIQUE (name)
);

CREATE TABLE article (
  id INTEGER PRIMARY KEY,
  product_id INTEGER NOT NULL REFERENCES product(id),
  brand TEXT,
  label TEXT,                      -- libellé OFF ou saisi
  net_quantity REAL,               -- poids/volume net, unité de base
  image TEXT,
  -- Toutes les valeurs nutritionnelles sont PAR UNITÉ DE BASE (kcal/g, g de
  -- protéines par g…). L'affichage les ramène à 100 g. Une seule convention dans
  -- toute la base : c'est l'ambiguïté « par 100 g ou par unité de stock ? » qui a
  -- produit les valeurs 1000× fausses des épinards hachés dans Grocy.
  kcal_per_base_unit REAL,
  proteins REAL, carbohydrates REAL, sugars REAL, added_sugars REAL,
  fat REAL, saturated_fat REAL, fiber REAL, salt REAL,
  nutriscore TEXT, nova INTEGER, ecoscore TEXT,
  allergens TEXT, traces TEXT, additives TEXT, off_labels TEXT,
  off_source TEXT,                 -- 'food' | 'beauty' | 'products' | 'petfood'
  off_synced_at TEXT,
  off_raw TEXT,                    -- réponse OFF brute (JSON), telle quelle
  manual_fields TEXT,              -- colonnes saisies à la main, à ne jamais écraser
  is_generic INTEGER NOT NULL DEFAULT 0,
  external_ref TEXT
);

CREATE TABLE barcode (
  code TEXT PRIMARY KEY,
  article_id INTEGER NOT NULL REFERENCES article(id)
);

CREATE TABLE packaging (
  id INTEGER PRIMARY KEY,
  scope TEXT NOT NULL CHECK (scope IN ('product','article')),
  target_id INTEGER NOT NULL,
  name TEXT NOT NULL,              -- 'Paquet', 'cs', 'tranche'
  base_quantity REAL NOT NULL,     -- en unité de base
  is_purchase_default INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE price (
  id INTEGER PRIMARY KEY,
  article_id INTEGER NOT NULL REFERENCES article(id),
  observed_on TEXT NOT NULL,
  price_per_base_unit REAL NOT NULL,
  store TEXT,
  source TEXT NOT NULL             -- 'manual' | 'receipt' | 'open_prices' | 'import'
);

CREATE TABLE batch (
  id INTEGER PRIMARY KEY,
  article_id INTEGER NOT NULL REFERENCES article(id),
  location_id INTEGER NOT NULL REFERENCES location(id),
  remaining REAL NOT NULL,
  initial REAL NOT NULL,
  best_before TEXT,
  entered_at TEXT NOT NULL,
  opened_at TEXT,
  price_per_base_unit REAL,
  session_id INTEGER,              -- session de courses (lot 4)
  closed_at TEXT
);

CREATE TABLE movement (            -- AJOUT SEUL. Jamais d'UPDATE, jamais de DELETE.
  id INTEGER PRIMARY KEY,
  occurred_at TEXT NOT NULL,
  product_id INTEGER NOT NULL REFERENCES product(id),
  article_id INTEGER NOT NULL REFERENCES article(id),
  batch_id INTEGER REFERENCES batch(id),
  quantity REAL NOT NULL,          -- signée : + entrée, − sortie
  reason TEXT NOT NULL,
  kcal REAL, cost REAL,            -- figés au moment du mouvement
  ref_type TEXT, ref_id INTEGER,   -- 'recipe' | 'meal' | 'session' (lots ultérieurs)
  idempotency_key TEXT UNIQUE      -- rejeu d'un service : aucun mouvement en double
);

CREATE INDEX idx_batch_pick ON batch(article_id, closed_at, best_before, entered_at);
CREATE INDEX idx_movement_day ON movement(occurred_at);
CREATE TABLE schema_version (version INTEGER NOT NULL);
```

Les tables des recettes, du planning, des courses, des piles et des équipements
arrivent avec leur lot. Les clés qui les relieront (`movement.ref_type/ref_id`,
`batch.session_id`) sont posées dès maintenant : le journal étant en ajout seul, il
ne doit pas être réécrit plus tard.

### 6.3 L'article générique

Le frais et le vrac n'ont pas d'EAN — 13 produits chez toi (tomates, citron, chèvre
à la coupe). Chaque produit possède donc un **article générique** (`is_generic = 1`,
sans code-barres), portant les valeurs de référence saisies à la main. Un lot pointe
ainsi toujours vers un article : aucun cas particulier dans le code de sortie, de
calcul de kcal ou de coût.

## 7. Règles métier

### 7.1 Choix du lot à sortir

```
ORDER BY (opened_at IS NULL),      -- finir un paquet déjà ouvert d'abord
         (best_before IS NULL),    -- puis le plus proche de périmer
         best_before,
         entered_at
```

Finir ce qui est ouvert passe avant la DLC : c'est le comportement attendu en
cuisine, et ça évite d'ouvrir un second paquet quand le premier suffit.

Une sortie traverse autant de lots que nécessaire et produit **un mouvement par
lot** — c'est ce qui permet à chaque mouvement de porter le prix réellement payé
pour cette fraction.

### 7.2 Poussière flottante

Un lot dont `remaining` descend sous **0,001 unité de base** est considéré comme
vide : `remaining` est mis à 0 et `closed_at` est renseigné. Sans cette règle, les
arrondis binaires laissent des lots à 10⁻¹⁴ g qui polluent le FIFO à vie.

### 7.3 Sortie supérieure au stock

Une sortie qui dépasse la quantité disponible est **refusée**, avec le disponible
dans le message d'erreur — jamais servie partiellement et jamais autorisée à passer
le stock en négatif. Un stock négatif est toujours le symptôme d'une entrée
manquante, et le corriger tard coûte plus cher que le refuser tôt.

La seule façon de constater « il y en avait moins que prévu » est
`home_stock.adjust_inventory`, dont c'est précisément le rôle : il écrit un
mouvement de motif `inventory`, qui ne compte ni en kcal ni en euros.

### 7.4 kcal et coût

Au moment du mouvement, et seulement à ce moment :

```
kcal = |quantity| × article.kcal_per_base_unit      (à défaut product.reference_kcal)
cost = |quantity| × batch.price_per_base_unit
```

Les deux sont **figés dans la ligne**. Changer le prix ou la fiche OFF d'un article
plus tard ne réécrit jamais le passé. Si la donnée manque, la colonne reste `NULL` —
jamais zéro : zéro voudrait dire « mesuré à zéro », `NULL` veut dire « inconnu ».
Les capteurs affichent explicitement la part inconnue.

Les valeurs sont conservées non arrondies ; l'arrondi est fait à l'affichage. On ne
somme jamais des valeurs déjà arrondies.

### 7.5 Motifs de mouvement

| Motif | Signe | Compte dans kcal/€ du jour |
|---|---|---|
| `purchase` | + | non (alimente le budget courses) |
| `consumption` | − | **oui** |
| `waste` | − | **oui**, et compté séparément comme gaspillage |
| `expired` | − | **oui**, idem |
| `inventory` | ± | non — c'est une correction, pas une consommation |
| `transfer` | ± | non — deux lignes de somme nulle, changement d'emplacement |

Le gaspillage compte dans le total du jour parce que la question posée est « ce qui
est sorti du stock », mais il reste distingué : un capteur dédié permet de le voir.

### 7.6 Ouverture d'un lot

Ouvrir un lot renseigne `opened_at` et, si le produit a `days_after_opening`,
avance `best_before` à `opened_at + N jours` quand cette date est plus proche. Aucun
mouvement n'est créé : rien n'a été consommé.

## 8. Surface Home Assistant

**Aucune entité par produit.** 299 produits feraient 299 entités et noieraient le
registre. Les entités sont des synthèses ; le détail passe par les services et la
SPA. Une seule entrée de configuration, un seul appareil « Garde-manger ».

### 8.0 Entrée de configuration

Instance unique, créée par un `config_flow` sans saisie (aucun identifiant à
fournir : tout est local). Options modifiables ensuite :

| Option | Défaut | Effet |
|---|---|---|
| `expiration_alert_days` | 3 | Seuil de `binary_sensor.home_stock_expirations` et du `todo` associé |

Le chemin du fichier de base n'est **pas** configurable : `config/home_stock.db`,
pour que les sauvegardes HA l'emportent sans réglage.

> **Retiré le 2026-08-18, pendant l'implémentation** : l'option `default_currency` (EUR,
> « affichage seulement ») figurait ici. Aucun code ne la lit — les capteurs portent l'unité
> `EUR` en dur — et une option qui ne change rien promet dans l'interface un comportement qui
> n'existe pas. Le foyer est en France ; le jour où une seconde devise sera nécessaire, il
> faudra de toute façon un taux de change, donc bien plus que cette option.

### 8.1 Entités du lot 0

| Entité | Rôle |
|---|---|
| `sensor.home_stock_stock_value` | Valeur du stock en €, attribut par emplacement |
| `sensor.home_stock_batches` | Nombre de lots, dont ouverts |
| `binary_sensor.home_stock_expirations` | Au moins un lot périme sous `expiration_alert_days` jours |
| `binary_sensor.home_stock_shortages` | Au moins un produit sous son seuil |
| `todo.home_stock_expirations` | Les lots concernés, cochables (« mangé », « jeté ») |
| `sensor.home_stock_kcal_total`, `sensor.home_stock_cost_total` | Compteurs `total_increasing` ; les `utility_meter` journaliers du lot 2 s'y branchent |

Les `entity_id` suivent l'anglais, les noms affichés viennent de
`translations/fr.json`.

Le lot 1 ajoutera `event.home_stock_scan`, qui émet à chaque scan et permet
d'écrire des automations HA sur le scan sans toucher au composant.

**Ambiguïté levée sur `todo.home_stock_expirations`** : une case cochée ne porte
qu'une information binaire, elle ne peut pas distinguer « mangé » de « jeté ».
Cocher vaut donc **consommé** (motif `consumption`). Jeter passe par
`home_stock.consume` avec le motif `waste`, ou par la SPA au lot 1.

### 8.2 Services

Tous journalisés, tous idempotents au sens où un rejeu ne crée pas de mouvement en
double lorsqu'un `idempotency_key` est fourni.

- `home_stock.add_stock` — article ou code-barres, quantité (unité de base ou
  conditionnement), emplacement, DLC, prix. **Au lot 0, un code-barres inconnu est
  refusé** : créer un article à partir d'un EAN suppose l'interrogation d'OFF, qui
  arrive au lot 1.
- `home_stock.consume` — produit ou article, quantité, motif, lot précis facultatif.
  Traverse les lots selon §7.1.
- `home_stock.open_batch`
- `home_stock.transfer_batch` — congélateur → frigo.
- `home_stock.adjust_inventory` — quantité réelle constatée → mouvement de correction.
- `home_stock.query_stock` — **service à réponse** (`SupportsResponse.ONLY`) : c'est
  lui qui répondra à « il reste des œufs ? », côté vocal comme côté template, sans
  créer d'entité.
- `home_stock.export_journal` — export JSON du journal.
- `home_stock.import_grocy_catalog` — voir §10, simulation par défaut.

### 8.3 Websocket

Le panneau reçoit l'objet `hass` : il réutilise la connexion et l'authentification
de HA, et **s'abonne** aux changements — le stock se met à jour sur le téléphone
pendant qu'on range, sans polling.

Commandes du lot 0 : `home_stock/products/list`, `home_stock/product/get`,
`home_stock/batches/list`, `home_stock/movements/list`,
`home_stock/locations/list`, `home_stock/aisles/list`, plus l'abonnement
`home_stock/subscribe`. Les commandes d'écriture arrivent au lot 1, avec la SPA.

Une seule vue HTTP subsiste, pour les images d'articles (binaire).

Conséquence de conception pour le mode magasin (lot 1) : la session de courses vivra
**côté serveur**. L'application fermée, l'écran éteint ou le réseau perdu en
sous-sol ne perdent rien.

## 9. Ingestion Open Food Facts

Le lot 0 pose les colonnes et la table ; les appels réseau sont au lot 1. La liste
ci-dessous fixe ce qu'on ingère, mesuré sur les 38 fiches réellement en cache dans
`data/tools/grocy-off/cache_off.json`.

| Donnée | Couverture (/38) | Usage |
|---|---|---|
| Macros complètes (protéines, glucides, sucres, sucres ajoutés, lipides, saturés, sel, fibres) | 29–31 | Compta par jour au-delà des kcal (lot 2) |
| `product_quantity` + `_unit` | 27 | **Poids net → `article.net_quantity`**, donc conversion paquet → grammes |
| `serving_size`, `serving_quantity`, `energy-kcal_serving` | 14 | Création automatique d'un `packaging` « portion » |
| `categories_tags` | 33 | Amorçage automatique du rayon et de la catégorie |
| `labels_tags` | 33 | Filtres (bio, végétarien, sans huile de palme) |
| `ingredients_text_fr`, `ingredients` structurés | 33 | Détail, et rattachement d'un article au bon produit |
| `additives_tags`, `traces_tags` | ~30 | Additifs et traces, aujourd'hui perdus |
| `generic_name_fr` | — | **Appariement article → produit existant** |
| `nutriments_estimated` | 16 | Valeurs déduites des ingrédients quand la table manque |
| `obsolete`, `completeness`, `last_modified_t` | — | Confiance à accorder à la fiche, et quand la rafraîchir |
| `image_nutrition_url`, `image_ingredients_url` | 34 | Vérifier une valeur sans aller chercher l'emballage |
| `packagings`, `packaging_tags` | ~25 | Matériau et recyclabilité — différé, mais la colonne brute le conserve |

**Quatre bases sœurs, même API, même code-barres**, interrogées en cascade jusqu'à
trouver : Open Food Facts, **Open Products Facts** (éponges, sacs, piles),
**Open Beauty Facts** (savon, shampooing, lessive), **Open Pet Food Facts** (les
croquettes de Soraya). C'est ce qui étend le scan aux 11 produits non alimentaires
qui n'ont aujourd'hui aucune chance d'être enrichis. La base d'origine est
mémorisée dans `article.off_source`.

**On stocke la réponse brute** dans `article.off_raw`. Ajouter un champ six mois
plus tard devient une relecture locale, pas 300 requêtes à une API qui impose un
délai de six secondes entre deux fiches inconnues.

**Deux pièges à traiter explicitement :**

- `nutrition_data_per` vaut parfois `serving` et non `100g` ; `nutrition_data_prepared_per`
  concerne ce qui se reconstitue (soupes, purées). Lire les valeurs sans vérifier ces
  champs se trompe d'un facteur 2 à 4.
- OFF est collaboratif : Nutri-Score absent sur 10 des 38 fiches, quantités mal
  saisies (« 1,kg » déjà rencontré). Toute valeur importée reste écrasable à la main,
  et une saisie manuelle n'est jamais réécrite par une resynchronisation — c'est le
  rôle de `article.manual_fields`.

## 10. Import du catalogue Grocy

Import **à sens unique, rejouable, hors démarrage de HA** : un service
d'administration, en simulation par défaut, dans l'esprit de l'outillage
`grocy-off` existant. Il lit une copie de `grocy.db` en lecture seule.

**Entre au lot 0 :** les 299 produits actifs, les emplacements, les groupes →
catégories, les 38 codes-barres, les champs personnalisés OFF (Nutri-Score, NOVA,
Eco-Score, marque, allergènes) et les calories.
**Reste au lot 7 :** le stock, l'historique, les recettes, le planning.

**Règle de conversion des unités** — le point délicat :

- unité de masse ou de volume Grocy (`g`, `kg`, `cl`, `l`) → `base_unit` `g` ou `ml`,
  conversion directe ;
- unité de conditionnement (`Paquet`, `Pot`, `Pièce`) → `base_unit = 'piece'`, **plus**
  une ligne `packaging` portant le poids net quand OFF ou le nom du produit le
  donnent. Ce qui est réellement compté (œufs, brocolis) reste compté : on n'invente
  pas de grammage.

Les calories Grocy sont déjà exprimées **par unité de stock**. Comme l'unité de
base reprend systématiquement l'unité de stock (`g`/`ml` pour les masses et volumes,
`piece` pour les conditionnements), elles deviennent `kcal_per_base_unit` **sans
aucune reconversion**. C'est la contrepartie de la règle ci-dessus : ne jamais
convertir un conditionnement en grammes à l'import, c'est aussi ne jamais avoir à
diviser des calories par un poids net supposé.

`product.external_ref` et `article.external_ref` gardent l'id Grocy. C'est ce qui
rend l'import rejouable **et** qui fera du lot 7 une simple jointure au lieu d'un
ré-appariement par nom — ce ré-appariement est précisément ce qui a produit 35
doublons en avril 2026.

Les 35 doublons déjà désactivés dans Grocy ne sont pas importés.

**Contrôle de sortie, obligatoire.** L'import n'est réputé réussi que si le rapport
est vide : 0 produit sans nom, sans catégorie, sans unité de base ; 0 nom en
double ; 0 kcal aberrante (> 9 kcal/g pour un produit en `g`) ; 0 code-barres
attribué à deux articles. Même esprit que `verifier_catalogue.py`.

## 11. Tests

- **`domain/` en pytest pur**, écrit en TDD. Les cas qui font mal : sortie partielle
  traversant plusieurs lots, lot ouvert prioritaire, poussière flottante,
  conversion conditionnement → unité de base, kcal et coût figés, motif sans effet
  sur la compta, quantité insuffisante en stock.
- **Couche HA** avec `pytest-homeassistant-custom-component` : services, service à
  réponse, commandes websocket, entités.
- **Migrations** : rejeu depuis une base vide et depuis chaque version publiée.
- **Import Grocy** : jeu de données réel réduit, et vérification que deux passages
  successifs ne créent rien de nouveau.
- **Front** (lot 1) : `vitest` + `verifier-rendu.mjs` réglé sur les formats téléphone.

## 12. Erreurs et exploitation

- **Rien n'échoue silencieusement.** Une écriture refusée est remontée et visible ;
  jamais avalée.
- **Rien ne bloque le scan** (lot 1) : OFF injoignable → l'article est créé avec le
  minimum, marqué à enrichir, repris par une tâche de fond. Un scan hors réseau
  reste en file locale et se rejoue.
- **Base** : `home_stock.db` en WAL, une seule connexion en écriture sérialisée dans
  l'executor. Le fichier vit dans `config/`, donc les sauvegardes HA l'emportent.
- **Filet supplémentaire** : `home_stock.export_journal` produit un JSON du journal.
  Le journal étant en ajout seul, il suffit à tout reconstruire.
- **Volumétrie** : ~300 produits, quelques milliers de mouvements par an. Aucun
  enjeu de performance ; les index posés suffisent largement.

## 13. Points différés, et pourquoi

| Sujet | Lot | Raison |
|---|---|---|
| Ordre des rayons par magasin, apprentissage du parcours | 4 | Inutile tant qu'il n'y a pas de sessions de courses réelles à observer |
| Matériau d'emballage et tri des déchets | ultérieur | Gratuit à conserver (`off_raw`), sans usage identifié aujourd'hui |
| Portions et suivi par personne | — | Foyer d'une personne (`person.maxime_allanic`) ; ajouter un convive multiplierait les portions, pas le modèle |
| Écriture vers Grocy | jamais | L'import est à sens unique ; Grocy n'est jamais mis à jour par `home_stock` |

## 14. Tranché

Les `entity_id` sont en **anglais** (`sensor.home_stock_stock_value`) avec un nom
affiché en français via `translations/fr.json` — la convention Home Assistant. Le
reste de la maison nomme ses entités en français ; l'écart est assumé et limité à
ce composant, dont le code est en anglais de bout en bout.

*Validé le 2026-08-18.*
