# home_stock — Lot 3 : recettes, planning et validation d'un repas — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Décider ce qu'on mange, le poser sur un jour, puis le valider — et que le stock bouge exactement de ce qui a été cuisiné, sans rien avoir à ressaisir. « Je valide le dîner » → les six ingrédients quittent leurs lots en FIFO, le plat existe en stock avec sa DLC et ses calories, la part mangée apparaît dans le journal du jour, les deux parts restantes attendent au frigo.

**Architecture:** Aucune couche nouvelle. Un domaine pur reçoit la mise à l'échelle, la résolution d'une quantité d'ingrédient en unité de base et le plan de décrément ; les dépôts lisent ; `application.py` orchestre une transaction unique ; le websocket et les services exposent. La source en ligne et l'agent conversationnel sont deux dépendances injectées qui n'ont le droit de bloquer personne. Le lot devient réel par trois écrans de panneau et une entité `calendar` native.

**Tech Stack:** Python 3.13 / Home Assistant 2026.8.2 / SQLite (WAL, écrivain unique) / `pytest-homeassistant-custom-component` — TypeScript / `lit` / rollup / vitest / playwright-core.

**Spec:** `docs/superpowers/specs/2026-08-21-home-stock-lot3-design.md`

**Base de départ :** `master`, propre, **623 tests Python** (`./scripts/test.sh`) et **247 tests front** (`npm test` depuis `frontend/`) au vert. Toute tâche qui laisse un de ces deux chiffres en baisse est une tâche qui n'est pas finie.

---

## Global Constraints

Ces règles lient **toutes** les tâches. Elles sont recopiées telles quelles depuis la spec et des trois lots précédents.

- **Nommage.** Code, schéma et identifiants Python **en anglais** ; textes affichés **en français**. Le front garde ses identifiants et ses commentaires **en français**, comme aux lots 0, 1 et 2. Les `entity_id` sont en anglais, les noms affichés vivent dans `translations/fr.json`.
- **Rien ne touche l'instance vivante.** Pas de `docker compose` (hors `scripts/test.sh`, qui construit une image de test et ne parle à aucun conteneur de la maison), pas de rechargement de l'intégration, pas de lecture du jeton dans `.mcp.json`, aucune écriture dans `/opt/nivuus/HomeAssistant/config/`. Règle posée au lot 1 après un redémarrage non demandé du Home Assistant du foyer.
- **Grocy est en lecture seule**, et uniquement sur une **copie** de `grocy.db` — jamais celle en production. Le lot 3 n'importe rien de Grocy (c'est le lot 7) : la seule lecture autorisée sert à fabriquer les fixtures d'appariement de la tâche 7, une fois, depuis une copie.
- **`npm run build` est interdit avant la dernière tâche.** `custom_components/home_stock/` est **bind-monté** dans le conteneur Home Assistant : le bundle construit est servi tel quel. Une seule construction, à la toute fin, quand tout le reste est vert. Un vérificateur ne déploie pas ; un build, si.
- **Commandes de test.** Python : `./scripts/test.sh` depuis la racine du dépôt (image Docker alignée sur HA 2026.8.2 — le Python de l'hôte ne peut pas charger le plugin). Front : `npm test` puis `node outils/verifier-rendu.mjs`, **depuis `frontend/`**.
- **Aucune des deux surfaces n'a le droit d'être la plus faible.** Ce que le websocket refuse, le service le refuse aussi, et réciproquement. Concrètement : `servings` et `portions_eaten` par `finite_float` puis borne stricte `> 0` ; `parts_total`/`parts_mine` par `parts_count` (`1 ≤ total ≤ 24`, `0 ≤ mine ≤ total`) ; `day` par `iso_date` (forme étendue `AAAA-MM-JJ` seulement) ; `slot_key` par un `vol.In` sur la constante ; tous les identifiants par `bounded_int` ; tous les textes par `bounded_text`.
- **Aucun appel réseau ne doit bloquer.** Ni TheMealDB, ni l'agent conversationnel. Source injoignable → recherche vide et message. Agent absent, en panne, hors quota ou illisible → la recette existe quand même, `language = 'en'`, `needs_review = 1`, `adapted_at = NULL`. **Jamais d'adaptation à moitié écrite.** La recette du soir, le planning, la vue cuisine et la validation ne font **aucun** appel réseau.
- **`cooked` ne compte pas.** Il rejoint `REASONS` mais **pas** `CONSUME_REASONS` (la constante que la spec §A1 appelle par erreur `COUNTED_REASONS` ; son nom réel dans le code depuis le lot 2 est `CONSUME_REASONS`). Cuisiner déplace la valeur des ingrédients vers le plat : ni `kcal_today`, ni les macros, ni `cost_today`, ni `cost_waste_total`, et `sensor.home_stock_stock_value` est inchangé au total.
- **`NULL` reste distinct de `0.0`,** valeur par valeur. Un seul mouvement ingrédient à `NULL` sur un nutriment rend `NULL` **ce nutriment-là** sur le plat, jamais les huit autres.
- **La quantité en unité de base n'est jamais stockée.** `amount` est le seul nombre écrit, plus **au plus une** mesure (`packaging_id` **ou** `measure_id`). Le libellé affiché est calculé lui aussi. `raw_text` est de la **provenance, jamais un calcul** — aucun code de décrément ne le lit.
- **Aucun diviseur deviné.** Une conversion impossible se traite comme une quantité absente, jamais comme une estimation.
- **Simulation obligatoire, transaction unique, clé d'idempotence.** Une validation n'est pas annulable au lot 3 ; c'est dit à l'écran plutôt que contourné.
- **`meal.day` est une journée ALIMENTAIRE** (frontière de 4 h, `domain/foodday.py`), pas une date civile.
- **Deux appuis pour toute action destructive du panneau** : armement puis confirmation. Aucun geste de navigation, aucun appui long.
- **Contraintes de rendu** : 412 × 915 et 1280 × 800, cibles ≥ **48 px**, contraste ≥ **4,5:1**, aucun débordement horizontal, aucun texte tronqué. Ce sont les seuils que `frontend/outils/verifier-rendu.mjs` applique déjà (`CIBLE_MIN_PX = 48`, `CONTRASTE_MIN = 4.5`). Ne jamais désactiver un contrôle pour faire passer un écran.
- **Jamais deux `db.write()` imbriqués.** `Database._lock` est un `threading.Lock` simple, non réentrant : imbriquer deux transactions **bloque le processus pour toujours**. C'est la contrainte structurante de la tâche 11.

---

## Fusion avec le lot 5 — fichiers à fort risque de conflit

Le lot 3 et le lot 5 sont implémentés **en parallèle, dans deux worktrees git séparés**, puis fusionnés dans `master`. Les fichiers ci-dessous seront touchés par les deux. La consigne est la même partout et elle n'a qu'une exception, signalée : **ajouter en fin de liste, ne jamais réordonner, ne jamais renuméroter ce que l'autre lot a posé.**

| Fichier | Consigne de fusion |
|---|---|
| `storage/migrations/__init__.py` | **La seule exception.** Le lot 3 prend `m004` / `VERSION = 4`. Le lot 5 vise `m006` en réservant `m005` au lot 4. Au merge, **relire le fichier et prendre le premier numéro libre**, pas le numéro écrit dans la spec : une base passée en version 6 ne verrait jamais `m004` ni `m005` (`apply_migrations` n'applique que `VERSION > MAX(version)`), qui seraient sautées **silencieusement**. Le test de contiguïté de la tâche 1 est ce qui rend cette règle exécutoire : le lot qui fusionne en second **renumérote sa migration** jusqu'à ce que le test repasse. Ajouter le module en **fin** du tuple `MIGRATIONS`. |
| `const.py` | Ajouter les constantes du lot **en fin de fichier**, dans un bloc commenté au nom du lot. Ne pas réordonner `REASONS` : `cooked` s'ajoute **après** `REASON_CONVERSION`, et les tests qui épinglent l'ordre resteront vrais. |
| `translations/fr.json` et `en.json` | Ajouter les clés à l'intérieur de `entity.<plateforme>`, sans toucher aux clés existantes. Un conflit ici est textuel et se résout à la main en gardant **les deux** blocs. Le lot 3 ajoute une plateforme (`calendar`) que le lot 5 n'a pas. |
| `services.yaml` | Ajouter les blocs de service **en fin de fichier**. Aucun réordonnancement. |
| `services.py` | Les nouveaux handlers sont des closures **en fin** de `async_register_services`, et les `async_register` correspondants **en fin** du bloc d'enregistrement. Les schémas module-level s'ajoutent **après** `RESYNC_SCHEMA`. |
| `websocket_api.py` | **Le lot 3 n'y ajoute que deux lignes** : un `from .websocket_recipes import async_register_recipe_commands` et l'appel de cette fonction en fin de `async_register_websocket`. Les quatorze commandes vivent dans un module neuf (voir la décision en tête de la tâche 15). Le lot 5 est invité à faire pareil ; s'il ne le fait pas, le conflit se limite au tuple de `async_register_websocket`, où l'on garde **les deux** listes. |
| `sensor.py` | Les nouvelles classes s'ajoutent **en fin de fichier**, et leurs instances **en fin** de la liste passée à `async_add_entities`. |
| `coordinator.py` | Le lot 3 ajoute **une** clé à `coordinator.data` (`"meals"`) via un unique travail d'exécuteur. Ne pas réécrire `_async_update_data` : y insérer sa lecture, en gardant celle de l'autre lot. |
| `application.py` | Les nouvelles méthodes de `StockManager` s'ajoutent **en fin de classe**. Les helpers internes extraits par la tâche 11 (`_consume_within`, `_add_stock_within`) sont un **refactor** de méthodes existantes : c'est le seul endroit où le lot 3 modifie du code partagé, et c'est à relire à deux yeux au merge. |
| `storage/repositories.py` | Nouvelles fonctions **en fin de fichier**, dans une section commentée. Exception : `KCAL_RATE_SQL` et `MACRO_RATE_SQL` sont modifiés en place par la tâche 2 — deux lignes, à garder telles que le lot 3 les écrit. |
| `frontend/src/panneau.ts` | `Ecran` gagne ses valeurs **en fin d'union** ; les branches de `rendreEcran()` s'ajoutent **avant** le `return` du scanner ; les boutons de navigation **en fin** de barre. |
| `docs/exploitation.md` | Une section `## Lot 3 — …` **à la fin du fichier**, après la section du lot 2. Aucune retouche des sections précédentes. |
| `tests/storage/test_migrations.py`, `tests/test_offline_queue_contract.py` | Ajouts en fin de fichier / en fin de l'ensemble `EXPECTED_QUEUED_COMMAND_TYPES`. |

---

## Structure des fichiers

**Python — créés**

| Fichier | Responsabilité |
|---|---|
| `custom_components/home_stock/domain/recipes.py` | Mise à l'échelle, résolution d'une quantité d'ingrédient en unité de base, plan de décrément, valeurs par part. Pur : pas de `hass`, pas de réseau, pas de SQLite. |
| `custom_components/home_stock/recipes/__init__.py` | Paquet. |
| `custom_components/home_stock/recipes/source.py` | Client TheMealDB. Transport injecté, aucun `hass`, ne lève jamais. |
| `custom_components/home_stock/recipes/mapping.py` | Fiche TheMealDB → lignes de recette. Aucun réseau, aucun `hass`. |
| `custom_components/home_stock/recipes/adapt.py` | Invite, appel à l'agent conversationnel, lecture défensive de sa réponse. |
| `custom_components/home_stock/storage/migrations/m004_recipes.py` | Huit tables, neuf colonnes sur `batch`, semis rejouable. |
| `custom_components/home_stock/calendar.py` | `calendar.home_stock_meals`. |
| `custom_components/home_stock/websocket_recipes.py` | Les quatorze commandes du lot, enregistrées par `websocket_api`. |

**Python — modifiés**

| Fichier | Ce qui change |
|---|---|
| `const.py` | `REASON_COOKED`, `MEAL_SLOT_KEYS`, `MEAL_STATES`, `MATCH_STATES`, `RECIPE_SOURCES`, `LEFTOVER_*`, `CONF_RECIPE_AGENT`, `CONF_RECIPE_SOURCE_KEY`, bornes du lot |
| `domain/units.py` | `UNIT_TO_BASE` remonte ici (une seule table d'unités dans le dépôt) ; `convertible_amount()` |
| `off/mapping.py` | Importe `UNIT_TO_BASE` depuis le domaine au lieu de le définir |
| `storage/migrations/__init__.py` | `m004` en fin de `MIGRATIONS` |
| `storage/repositories.py` | Cascade `COALESCE(b, a, p)` ; dépôts des recettes, des ingrédients, des mesures, des alias, des créneaux et des repas |
| `application.py` | `_consume_within` / `_add_stock_within` extraits ; `match_ingredient`, `plan_meal`, `move_meal`, `cancel_meal`, `preview_meal`, `validate_meal`, `meal_summary`, CRUD des recettes |
| `coordinator.py` | `coordinator.data["meals"]` |
| `sensor.py` | `next_meal`, `recipes`, `missing_ingredients` |
| `config_flow.py` | Options `recipe_agent` (sélecteur d'entité `conversation`) et `recipe_source_key` |
| `__init__.py` | `Platform.CALENDAR` dans `PLATFORMS` ; `meal_transport` et `recipe_source` dans `HomeStockData` |
| `websocket_api.py` | Deux lignes : import et appel de `async_register_recipe_commands` |
| `services.py`, `services.yaml` | `plan_meal`, `validate_meal`, `import_recipe`, `adapt_recipe`, `query_meals` |
| `messages.py` | Les motifs d'erreur du lot |
| `translations/fr.json`, `en.json` | `calendar.meals`, `sensor.next_meal`, `sensor.recipes`, `sensor.missing_ingredients`, les deux options |
| `docs/exploitation.md` | Section « Lot 3 » |

**Front — créés**

| Fichier | Responsabilité |
|---|---|
| `frontend/src/minuteur.ts` | Le décompte d'un minuteur de recette. Pur, comme `dlc.ts` et `portion.ts`. |
| `frontend/src/ecrans/recettes.ts` | La liste, la recherche locale, « Chercher ailleurs ». |
| `frontend/src/ecrans/recette.ts` | La vue cuisine : couverture, Ingrédients, une page par étape. |
| `frontend/src/ecrans/validation.ts` | L'écran de validation d'un repas. |
| `frontend/src/ecrans/planning.ts` | La semaine (1280) et la journée (412). |

**Front — modifiés**

| Fichier | Ce qui change |
|---|---|
| `frontend/src/nombres.ts` | `formaterFraction`, `formaterQuantiteRecette` |
| `frontend/src/panneau.ts` | Quatre écrans de plus dans `Ecran` et dans la navigation |
| `frontend/outils/verifier-rendu.mjs` | Quatre scénarios de plus, aux deux formats |

---

## Task 1: Migration `m004`, contiguïté des `VERSION`, et les constantes du lot

**Files:**
- Create: `custom_components/home_stock/storage/migrations/m004_recipes.py`
- Modify: `custom_components/home_stock/storage/migrations/__init__.py`
- Modify: `custom_components/home_stock/const.py`
- Test: `tests/storage/test_migrations.py`

**Interfaces:**
- Consomme : le hook `apply(conn)` du lanceur de migrations, en place depuis `m002`.
- Produit :
  - `m004_recipes.VERSION = 4`, `m004_recipes.SQL`, `m004_recipes.apply(conn)`.
  - Huit tables : `recipe`, `recipe_step`, `recipe_instruction`, `recipe_ingredient`, `culinary_measure`, `ingredient_alias`, `meal_slot`, `meal`. Deux index (`idx_meal_day`, `idx_ingredient_recipe`) et un index unique partiel (`idx_recipe_source`).
  - Neuf colonnes nullables sur `batch` : `kcal_per_base_unit` et les huit macros.
  - Dans `const.py`, en fin de fichier :

```python
# --- lot 3 : recettes, planning, repas --------------------------------------
REASON_COOKED: Final = "cooked"          # à ajouter À LA FIN de REASONS, jamais ailleurs
MEAL_SLOT_KEYS: Final = ("breakfast", "lunch", "dinner", "snack")
MEAL_STATES: Final = ("planned", "done", "skipped")
MATCH_STATES: Final = ("unmatched", "auto", "confirmed", "ignored")
RECIPE_SOURCES: Final = ("manual", "themealdb", "grocy")
LEFTOVER_SHELF_LIFE_DAYS: Final = 3
LEFTOVER_CATEGORY_NAME: Final = "Plats cuisinés"
LEFTOVER_NAME_PREFIX: Final = "Reste — "
MAX_SERVINGS: Final = 100.0              # au-delà, c'est une saisie, pas un dîner
MAX_RECIPE_STEPS: Final = 40
MAX_RECIPE_INGREDIENTS: Final = 60
MEAL_HORIZON_DAYS: Final = 7             # la fenêtre de sensor.missing_ingredients
CONF_RECIPE_AGENT: Final = "recipe_agent"
CONF_RECIPE_SOURCE_KEY: Final = "recipe_source_key"
DEFAULT_RECIPE_SOURCE_KEY: Final = "1"
```

**Décision de plan — la contiguïté est un test, pas une consigne.** `apply_migrations()` n'applique que les migrations dont la `VERSION` dépasse `MAX(version)` de `schema_version`. Un trou est sans conséquence ; un **dépassement** est fatal et silencieux. Le test de contiguïté ajouté ici est ce qui empêche le lot 5 (qui vise `m006`) d'atterrir sur `master` avant le lot 4 sans renuméroter. Il manque aujourd'hui ; le lot 3 le pose parce qu'il est le premier des deux à écrire une migration.

- [x] **Step 1: Écrire les tests de la migration et de la contiguïté**

Dans `tests/storage/test_migrations.py`, à la fin du fichier. **Lire d'abord le haut du fichier** et reprendre le helper d'ouverture/migration déjà présent (noté `_migrated(tmp_path)` ci-dessous) plutôt que d'en écrire un autre.

```python
from custom_components.home_stock.storage import migrations


def test_migration_versions_are_contiguous_from_one():
    """Un dépassement de version saute une migration DÉFINITIVEMENT et sans
    bruit : `apply_migrations` ne redescend jamais. Ce test est le garde-fou
    du merge parallèle des lots 3 et 5 — le second à fusionner renumérote."""
    versions = [module.VERSION for module in migrations.MIGRATIONS]
    assert versions == list(range(1, len(versions) + 1))
    assert migrations.CURRENT_VERSION == versions[-1]


def test_m004_creates_the_eight_tables(tmp_path):
    conn = _migrated(tmp_path)
    tables = {row["name"] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"recipe", "recipe_step", "recipe_instruction", "recipe_ingredient",
            "culinary_measure", "ingredient_alias", "meal_slot", "meal"} <= tables


def test_m004_adds_the_nutrition_columns_to_batch(tmp_path):
    conn = _migrated(tmp_path)
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(batch)")}
    assert {"kcal_per_base_unit", "proteins", "carbohydrates", "sugars",
            "added_sugars", "fat", "saturated_fat", "fiber", "salt"} <= columns


def test_m004_leaves_the_existing_batches_null(tmp_path):
    """Amendement A2 : tout ce qui existe reste à NULL et se lit comme avant."""
    conn = _migrated(tmp_path)
    _seed_one_batch(conn)                       # helper local, à écrire si absent
    row = conn.execute("SELECT kcal_per_base_unit, proteins FROM batch").fetchone()
    assert row["kcal_per_base_unit"] is None and row["proteins"] is None


def test_m004_seeds_the_four_slots_with_their_grocy_refs(tmp_path):
    conn = _migrated(tmp_path)
    rows = {r["key"]: dict(r) for r in conn.execute("SELECT * FROM meal_slot")}
    assert set(rows) == {"breakfast", "lunch", "dinner", "snack"}
    assert rows["breakfast"]["default_time"] == "07:30"
    assert rows["lunch"]["default_time"] == "12:30"
    assert rows["dinner"]["default_time"] == "20:00"
    assert rows["snack"]["default_time"] == "16:00"
    # La jointure du lot 7, posée maintenant plutôt que devinée par nom.
    assert [rows[k]["external_ref"] for k in ("breakfast", "lunch", "dinner")] == ["1", "2", "3"]
    assert rows["snack"]["external_ref"] is None


def test_m004_seeds_the_culinary_measures(tmp_path):
    conn = _migrated(tmp_path)
    measures = {r["name"]: (r["base_unit"], r["base_quantity"])
                for r in conn.execute("SELECT * FROM culinary_measure")}
    assert measures == {
        "cuillère à soupe": ("ml", 15.0), "cuillère à café": ("ml", 5.0),
        "verre": ("ml", 200.0), "pincée": ("g", 1.0),
    }


def test_m004_seeds_the_leftover_category(tmp_path):
    conn = _migrated(tmp_path)
    assert conn.execute("SELECT 1 FROM category WHERE name = ?",
                        ("Plats cuisinés",)).fetchone() is not None


def test_m004_apply_is_replayable(tmp_path):
    """Même discipline que les rayons de m002 et les portions de m003."""
    conn = _migrated(tmp_path)
    m004.apply(conn); m004.apply(conn)
    assert conn.execute("SELECT COUNT(*) c FROM meal_slot").fetchone()["c"] == 4
    assert conn.execute("SELECT COUNT(*) c FROM culinary_measure").fetchone()["c"] == 4
    assert conn.execute("SELECT COUNT(*) c FROM category WHERE name = ?",
                        ("Plats cuisinés",)).fetchone()["c"] == 1
```

Puis les contraintes de schéma, qui sont la moitié de l'intérêt de cette migration — chacune prouve un refus :

```python
@pytest.mark.parametrize("values, why", [
    ({"packaging_id": 1, "measure_id": 1}, "une quantité se dit dans UNE mesure"),
    ({"match_state": "auto", "product_id": None}, "un appariement suppose un produit"),
])
def test_m004_recipe_ingredient_refuses_the_impossible(tmp_path, values, why):
    conn = _migrated(tmp_path)
    with pytest.raises(sqlite3.IntegrityError):
        _insert_ingredient(conn, **values)


def test_m004_instruction_refuses_a_half_timer(tmp_path):
    """Un bouton « Cuisson » sans durée n'est pas un bouton."""
    conn = _migrated(tmp_path)
    with pytest.raises(sqlite3.IntegrityError):
        _insert_instruction(conn, timer_label="Cuisson", timer_seconds=None)
    with pytest.raises(sqlite3.IntegrityError):
        _insert_instruction(conn, timer_label=None, timer_seconds=600)
    _insert_instruction(conn, timer_label="Cuisson", timer_seconds=600)   # les deux : accepté


def test_m004_meal_refuses_two_natures_and_accepts_exactly_one(tmp_path):
    conn = _migrated(tmp_path)
    with pytest.raises(sqlite3.IntegrityError):
        _insert_meal(conn, recipe_id=1, product_id=1)
    with pytest.raises(sqlite3.IntegrityError):
        _insert_meal(conn)                       # ni recette, ni produit, ni note
    _insert_meal(conn, note="Restaurant")


def test_m004_recipe_source_is_unique_but_only_when_there_is_a_ref(tmp_path):
    """L'unicité qui compte est celle de la SOURCE : c'est elle qui rend
    l'import rejouable. Deux « Salade de pâtes » manuelles restent légitimes."""
    conn = _migrated(tmp_path)
    _insert_recipe(conn, name="Kapsalon", source="themealdb", source_ref="52942")
    with pytest.raises(sqlite3.IntegrityError):
        _insert_recipe(conn, name="Autre", source="themealdb", source_ref="52942")
    _insert_recipe(conn, name="Salade de pâtes", source="manual", source_ref=None)
    _insert_recipe(conn, name="Salade de pâtes", source="manual", source_ref=None)


def test_m004_servings_and_timer_bounds(tmp_path):
    conn = _migrated(tmp_path)
    with pytest.raises(sqlite3.IntegrityError):
        _insert_recipe(conn, name="Zéro", servings=0)
    with pytest.raises(sqlite3.IntegrityError):
        _insert_instruction(conn, timer_label="Repos", timer_seconds=0)
```

- [x] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/storage/test_migrations.py -q`
Expected: FAIL — `ImportError` sur `m004_recipes`, puis `no such table: recipe`.

- [x] **Step 3: Écrire `m004_recipes.py`**

Recopier le DDL de la spec § 6 **tel quel** — il a été relu, ses `CHECK` sont des décisions et non de la décoration. Le module suit le contrat des trois précédents : docstring de tête, `VERSION = 4`, `SQL = """…"""` passé à `executescript`, puis `apply(conn)` pour ce qui demande du Python.

```python
"""Lot 3 : recettes, étapes, ingrédients, mesures, alias, créneaux, repas.

Aucune manipulation de trigger : rien ici ne fait d'UPDATE sur `movement`.
Toutes les colonnes ajoutées sont nullables, toutes les tables sont neuves,
et `apply` ne sème que dans une table vide — donc rejouable, comme les rayons
de m002 et les portions de m003.
"""
VERSION = 4

SQL = """ ... le DDL de la spec § 6, verbatim ... """

SLOTS = (("breakfast", 1, "07:30", 45, "1"), ("lunch", 2, "12:30", 45, "2"),
         ("dinner", 3, "20:00", 45, "3"), ("snack", 4, "16:00", 20, None))

# 15 ml est la valeur normalisée française. Le chiffre exact importe peu :
# un `packaging` propre au produit l'emporte dès qu'il existe (spec § 9).
MEASURES = (("cuillère à soupe", "ml", 15.0), ("cuillère à café", "ml", 5.0),
            ("verre", "ml", 200.0), ("pincée", "g", 1.0))


def apply(conn) -> None:
    if not conn.execute("SELECT 1 FROM meal_slot LIMIT 1").fetchone():
        conn.executemany(
            "INSERT INTO meal_slot (key, position, default_time, duration_minutes,"
            " external_ref) VALUES (?, ?, ?, ?, ?)", SLOTS)
    if not conn.execute("SELECT 1 FROM culinary_measure LIMIT 1").fetchone():
        conn.executemany(
            "INSERT INTO culinary_measure (name, base_unit, base_quantity)"
            " VALUES (?, ?, ?)", MEASURES)
    conn.execute("INSERT OR IGNORE INTO category (name) VALUES (?)",
                 ("Plats cuisinés",))
```

Dans `storage/migrations/__init__.py` : ajouter `m004_recipes` à l'import **et en fin** du tuple `MIGRATIONS`.

Dans `const.py` : ajouter le bloc du lot en fin de fichier, et `REASON_COOKED` **à la fin** de `REASONS` — jamais au milieu.

- [x] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/storage/test_migrations.py -q`
Expected: PASS

- [x] **Step 5: Lancer toute la suite Python**

Run: `./scripts/test.sh -q`
Expected: PASS — aucune régression. Un test du lot 0 épingle `REASONS` : s'il échoue, c'est que `cooked` a été inséré au milieu.

- [x] **Step 6: Commit**

```bash
git add custom_components/home_stock/storage/migrations custom_components/home_stock/const.py tests/storage/test_migrations.py
git commit -m "feat: m004 creates the recipe, meal and measure tables"
```

---

## Task 2: La nutrition peut vivre sur le lot (amendement A2)

**Files:**
- Modify: `custom_components/home_stock/storage/repositories.py`
- Modify: `custom_components/home_stock/application.py`
- Test: `tests/storage/test_repositories.py`

**Interfaces:**
- Produit :
  - `repo.KCAL_RATE_SQL = "COALESCE(b.kcal_per_base_unit, a.kcal_per_base_unit, p.reference_kcal)"`
  - `repo.MACRO_RATE_SQL` = les huit `COALESCE(b.<col>, a.<col>) AS <col>`
  - `repo.insert_batch(...)` gagne `nutrition: Mapping[str, float | None] | None = None`
  - `repo.resolve_kcal_rate(conn, article, batch=None)` — le pendant Python, pour les appelants qui tiennent déjà leurs lignes en main
  - `repo.batch_macro_rates(batch, article) -> dict[str, float | None]`

**⚠️ Le piège de cette tâche, et c'est un vrai.** `list_batches_for_product` fait aujourd'hui :

```sql
SELECT b.*, COALESCE(a.kcal_per_base_unit, p.reference_kcal) AS kcal_per_base_unit,
       a.proteins, a.carbohydrates, …
```

Dès que `batch` porte ces neuf colonnes, `b.*` les ramène **aussi**, et la ligne rendue contient deux colonnes du même nom. `dict(sqlite3.Row)` garde alors la **première** — c'est-à-dire la colonne brute de `batch`, `NULL` pour tout le stock existant — et non le `COALESCE`. Résultat : toutes les kcal et toutes les macros du stock passent silencieusement à `NULL` le jour où la migration s'applique. **`SELECT b.*` doit donc être remplacé par une liste explicite de colonnes** dans les deux requêtes concernées. C'est le seul changement de cette tâche qui n'est pas une addition.

- [x] **Step 1: Écrire les tests**

Dans `tests/storage/test_repositories.py`, à la fin :

```python
def test_the_cascade_reads_the_article_when_the_batch_says_nothing(conn):
    """Tout ce qui existe se lit exactement comme avant."""
    batch_id = _batch(conn, article_kcal=2.5)
    row = repo.list_batches_for_product(conn, 1)[0]
    assert row["kcal_per_base_unit"] == 2.5


def test_the_cascade_falls_back_to_the_product(conn):
    batch_id = _batch(conn, article_kcal=None, product_reference_kcal=0.52)
    assert repo.list_batches_for_product(conn, 1)[0]["kcal_per_base_unit"] == 0.52


def test_the_batch_wins_over_the_article_and_the_product(conn):
    """Deux cuissons de la même recette n'ont pas la même valeur : l'article
    est partagé, le lot ne l'est pas."""
    _batch(conn, article_kcal=2.5, product_reference_kcal=0.52,
           nutrition={"kcal_per_base_unit": 180.0, "proteins": 9.0})
    row = repo.list_batches_for_product(conn, 1)[0]
    assert row["kcal_per_base_unit"] == 180.0
    assert row["proteins"] == 9.0


def test_a_batch_null_macro_still_reads_the_article(conn):
    """La cascade est par COLONNE, pas par ligne."""
    _batch(conn, nutrition={"kcal_per_base_unit": 180.0},   # proteins non renseigné
           article_macros={"proteins": 0.09})
    row = repo.list_batches_for_product(conn, 1)[0]
    assert row["kcal_per_base_unit"] == 180.0 and row["proteins"] == 0.09


def test_the_batch_star_no_longer_shadows_the_cascade(conn):
    """Régression : `SELECT b.*` ramenait deux colonnes du même nom, et
    dict(sqlite3.Row) gardait la première — donc le NULL du lot."""
    _batch(conn, article_kcal=2.5)                # rien sur le lot
    row = repo.list_batches_for_product(conn, 1)[0]
    assert row["kcal_per_base_unit"] == 2.5
    assert list(row).count("kcal_per_base_unit") == 1


def test_stock_rows_reads_the_same_cascade(conn):
    _batch(conn, nutrition={"kcal_per_base_unit": 180.0})
    assert repo.stock_rows(conn)[0]["kcal_per_base_unit"] == 180.0


def test_insert_batch_freezes_the_nutrition_it_is_given(conn):
    batch_id = repo.insert_batch(conn, article_id=1, location_id=1, quantity=3.0,
                                 entered_at="2026-08-21T18:00:00",
                                 nutrition={"kcal_per_base_unit": 180.0, "salt": 0.9})
    row = conn.execute("SELECT * FROM batch WHERE id = ?", (batch_id,)).fetchone()
    assert row["kcal_per_base_unit"] == 180.0 and row["salt"] == 0.9
    assert row["fiber"] is None      # ce qui n'est pas dit reste inconnu, pas zéro


def test_insert_batch_without_nutrition_is_unchanged(conn):
    batch_id = repo.insert_batch(conn, article_id=1, location_id=1, quantity=3.0,
                                 entered_at="2026-08-21T18:00:00")
    row = conn.execute("SELECT * FROM batch WHERE id = ?", (batch_id,)).fetchone()
    assert all(row[column] is None for column in NUTRITION_COLUMNS)
```

- [x] **Step 2: Lancer, vérifier l'échec**

Run: `./scripts/test.sh tests/storage/test_repositories.py -q`
Expected: FAIL — `insert_batch() got an unexpected keyword argument 'nutrition'`.

- [x] **Step 3: Étendre la cascade et l'insertion**

Dans `repositories.py` : les deux constantes, la liste explicite de colonnes à la place de `b.*` dans `list_batches_for_product` **et** dans `stock_rows` si elle sélectionne `b.*`, l'argument `nutrition` de `insert_batch` (filtré sur `NUTRITION_COLUMNS`, importé de `application`… non : **déplacer `NUTRITION_COLUMNS` de `application.py` vers `const.py`** pour que `repositories` puisse l'utiliser sans importer la couche du dessus — `application` continue de le réexporter pour ne casser aucun appelant).

`resolve_kcal_rate(conn, article, batch=None)` : le lot d'abord, l'article ensuite, le produit en dernier. `batch_macro_rates(batch, article)` : `{col: batch[col] if batch and batch[col] is not None else article[col]}`.

Dans `application.py`, `consume_batch` lit déjà sa ligne de lot jointe : lui faire prendre les taux du lot en priorité (`repo.macro_rates` reçoit une ligne déjà cascadée par `list_batches_for_product`, donc rien à changer si la requête est bien corrigée — **le vérifier par le test ci-dessous plutôt que par lecture**).

- [x] **Step 4: Lancer, vérifier le vert, puis la suite entière**

```bash
./scripts/test.sh tests/storage/test_repositories.py -q
./scripts/test.sh -q
```
Expected: PASS des deux. La suite entière est obligatoire ici : cette tâche touche la lecture de **tout** le stock.

- [x] **Step 5: Commit**

```bash
git add custom_components/home_stock/storage/repositories.py custom_components/home_stock/const.py custom_components/home_stock/application.py tests/storage/test_repositories.py
git commit -m "feat: a batch may carry its own nutrition, and the cascade reads it first"
```

---

## Task 3: `add_stock` accepte un motif et une nutrition (amendement A3)

**Files:**
- Modify: `custom_components/home_stock/application.py`
- Test: `tests/test_application.py`

**Interfaces:**
- Produit : `StockManager.add_stock(..., reason: str = REASON_PURCHASE, nutrition: Mapping[str, float | None] | None = None) -> int`.

**Pourquoi ici et pas un second chemin.** `add_stock` est le seul chemin d'entrée en stock du composant. En ouvrir un second pour les plats cuisinés reviendrait à entretenir deux comportements d'entrée — exactement la dette que le lot 0 a refusée sur la sortie. Les deux nouveaux arguments ont des défauts qui laissent **tous** les appelants existants strictement inchangés.

- [x] **Step 1: Écrire les tests**

Dans `tests/test_application.py` :

```python
def test_add_stock_still_writes_purchase_by_default(manager):
    manager.add_stock(article_id=1, quantity=500.0, location_id=1)
    assert _one(manager, "SELECT reason FROM movement")["reason"] == "purchase"


def test_add_stock_can_write_another_reason(manager):
    manager.add_stock(article_id=1, quantity=3.0, location_id=1, reason="cooked")
    assert _one(manager, "SELECT reason FROM movement")["reason"] == "cooked"


def test_add_stock_freezes_the_nutrition_on_the_batch(manager):
    batch_id = manager.add_stock(article_id=1, quantity=3.0, location_id=1,
                                 reason="cooked",
                                 nutrition={"kcal_per_base_unit": 180.0, "proteins": 9.0})
    row = _one(manager, "SELECT * FROM batch WHERE id = ?", (batch_id,))
    assert (row["kcal_per_base_unit"], row["proteins"]) == (180.0, 9.0)


def test_the_entry_movement_uses_the_frozen_nutrition_not_the_article(manager):
    """Le mouvement d'entrée du plat vaut ce que le plat vaut, pas ce que
    l'article générique dirait."""
    batch_id = manager.add_stock(article_id=1, quantity=3.0, location_id=1,
                                 reason="cooked", nutrition={"kcal_per_base_unit": 180.0})
    assert _one(manager, "SELECT kcal FROM movement WHERE batch_id = ?",
                (batch_id,))["kcal"] == 540.0


def test_cooked_is_a_reason_but_never_a_counted_one(manager):
    from custom_components.home_stock.const import CONSUME_REASONS, REASONS
    assert "cooked" in REASONS and "cooked" not in CONSUME_REASONS


def test_add_stock_stays_idempotent_with_the_new_arguments(manager):
    first = manager.add_stock(article_id=1, quantity=3.0, location_id=1,
                              reason="cooked", idempotency_key="k",
                              nutrition={"kcal_per_base_unit": 180.0})
    second = manager.add_stock(article_id=1, quantity=3.0, location_id=1,
                               reason="cooked", idempotency_key="k",
                               nutrition={"kcal_per_base_unit": 180.0})
    assert first == second
    assert _count(manager, "SELECT COUNT(*) c FROM movement") == 1
```

- [x] **Step 2: Lancer, vérifier l'échec**

Run: `./scripts/test.sh tests/test_application.py -q`
Expected: FAIL — `add_stock() got an unexpected keyword argument 'reason'`.

- [x] **Step 3: Étendre `add_stock`**

Deux arguments nommés en fin de signature ; `nutrition` filtré sur `NUTRITION_COLUMNS` et passé à `repo.insert_batch` ; les valeurs du mouvement d'entrée calculées depuis la nutrition figée quand elle existe, sinon depuis `repo.resolve_kcal_rate` / `repo.macro_rates(article)` comme aujourd'hui. Documenter dans la docstring que `reason` par défaut vaut `purchase` **et pourquoi** on n'a pas ouvert un second chemin.

- [x] **Step 4: Lancer, vérifier le vert**

Run: `./scripts/test.sh tests/test_application.py -q && ./scripts/test.sh -q`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add custom_components/home_stock/application.py tests/test_application.py
git commit -m "feat: add_stock takes a reason and a nutrition to freeze on the batch"
```

---

## Task 4: Une seule table d'unités, dans le domaine

**Files:**
- Modify: `custom_components/home_stock/domain/units.py`
- Modify: `custom_components/home_stock/off/mapping.py`
- Test: `tests/domain/test_units.py`, `tests/off/test_mapping.py`

**Interfaces:**
- Produit :
  - `units.UNIT_TO_BASE: dict[str, tuple[str, float]]` — déplacé depuis `off/mapping.py`, **inchangé** (`g`, `gr`, `gram`, `grammes`, `kg`, `mg`, `ml`, `cl`, `dl`, `l`).
  - `units.convertible_amount(amount: float, unit: str | None, product_base_unit: str) -> float | None` — la quantité en unité de base, ou `None` si la dimension ne correspond pas.
- `off/mapping.py` fait `from ..domain.units import UNIT_TO_BASE` et cesse de définir la table. **Rien d'autre ne change** : le nom reste importable depuis `off.mapping` pour les appelants existants.

**Pourquoi déplacer plutôt que dupliquer.** `domain/recipes.py` doit ramener « 2 tbsp » et « 250 g » à l'unité de base d'un produit, et il n'a pas le droit d'importer `off/` — le domaine ne connaît ni le réseau ni les fournisseurs de données. Recopier la table donnerait deux vérités sur ce que vaut un décilitre, et la seconde dériverait. Le domaine est l'endroit où elle aurait dû naître.

- [x] **Step 1: Écrire les tests**

Dans `tests/domain/test_units.py` :

```python
from custom_components.home_stock.domain.units import UNIT_TO_BASE, convertible_amount


def test_a_mass_converts_to_grams():
    assert convertible_amount(1.5, "kg", "g") == 1500.0
    assert convertible_amount(250, "g", "g") == 250.0
    assert convertible_amount(500, "mg", "g") == 0.5


def test_a_volume_converts_to_millilitres():
    assert convertible_amount(2, "cl", "ml") == 20.0
    assert convertible_amount(1, "l", "ml") == 1000.0


def test_a_mass_given_for_a_volume_product_is_refused():
    """Jamais de densité devinée : 100 g de miel ne font pas 100 ml."""
    assert convertible_amount(100, "g", "ml") is None
    assert convertible_amount(100, "ml", "g") is None


def test_anything_given_for_a_piece_product_is_refused():
    """Le lot 1 refuse déjà d'inventer un diviseur (§ 7.4) ; même raison."""
    assert convertible_amount(100, "g", "piece") is None


def test_an_unknown_unit_is_refused_not_guessed():
    for unit in ("unité", "pcs", "portions", "handful", "", None, "G "):
        assert convertible_amount(1, unit, "g") is None


def test_no_unit_at_all_means_the_number_is_already_in_the_base_unit():
    assert convertible_amount(150, None, "g") is None   # explicitement refusé ici :
    # c'est l'APPELANT (domain/recipes) qui décide qu'une ligne sans mesure est
    # déjà en unité de base. Cette fonction ne convertit que ce qu'on lui nomme.


def test_the_table_did_not_move_a_single_value():
    assert UNIT_TO_BASE["cl"] == ("ml", 10.0)
    assert UNIT_TO_BASE["mg"] == ("g", 0.001)
    assert len(UNIT_TO_BASE) == 10
```

Dans `tests/off/test_mapping.py`, un test de non-régression du déplacement :

```python
def test_off_mapping_still_exposes_the_unit_table():
    """Le déplacement ne doit rien casser chez les appelants du lot 1."""
    from custom_components.home_stock.domain.units import UNIT_TO_BASE as source
    from custom_components.home_stock.off.mapping import UNIT_TO_BASE as reexport
    assert reexport is source
```

- [x] **Step 2: Lancer, vérifier l'échec**

Run: `./scripts/test.sh tests/domain/test_units.py tests/off/test_mapping.py -q`
Expected: FAIL — `ImportError: cannot import name 'UNIT_TO_BASE' from …domain.units`.

- [x] **Step 3: Déplacer la table et écrire `convertible_amount`**

`convertible_amount` : `unit` non `str` ou absent de `UNIT_TO_BASE` → `None` ; dimension rendue par la table différente de `product_base_unit` → `None` ; sinon `amount * facteur`. Aucun `strip()`, aucun `lower()` : la normalisation du texte de la source est le travail de `recipes/mapping.py`, pas du domaine — une fonction qui devine deux fois ne dit plus où la devinette a eu lieu.

- [x] **Step 4: Lancer, vérifier le vert**

Run: `./scripts/test.sh tests/domain tests/off -q && ./scripts/test.sh -q`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add custom_components/home_stock/domain/units.py custom_components/home_stock/off/mapping.py tests/domain/test_units.py tests/off/test_mapping.py
git commit -m "refactor: the unit table lives in the domain, where recipes can reach it"
```

---

## Task 5: `domain/recipes.py` — l'échelle, la quantité, le plan, les valeurs par part

**Files:**
- Create: `custom_components/home_stock/domain/recipes.py`
- Test: `tests/domain/test_recipes.py` (créer)

**Interfaces:**
- Consomme : `units.convertible_amount`, `units.to_base_quantity`, `units.format_quantity`, `stock.allocate`, `stock.BatchView`, `stock.InsufficientStock`, `const.MACRO_COLUMNS`, `const.NUTRITION_COLUMNS`.
- Produit :

```python
STATUSES: Final = ("ok", "short", "unmatched", "unquantified", "ignored")

@dataclass(frozen=True)
class Measure:
    id: int | None
    name: str
    base_unit: str          # 'g' | 'ml' | 'piece'
    base_quantity: float

@dataclass(frozen=True)
class IngredientLine:
    """Une ligne de recette, telle que le dépôt la rend — déjà jointe."""
    id: int
    position: int
    product_id: int | None
    product_base_unit: str | None
    amount: float | None
    packaging_base_quantity: float | None
    packaging_name: str | None
    measure: Measure | None
    raw_text: str
    match_state: str
    optional: bool

@dataclass(frozen=True)
class IngredientNeed:
    line: IngredientLine
    status: str                       # dans STATUSES
    needed: float | None              # en unité de base, DÉJÀ mis à l'échelle
    available: float
    allocations: tuple[Allocation, ...]

def scale_factor(meal_servings: float, recipe_servings: int) -> float
def base_amount(line: IngredientLine, factor: float = 1.0) -> float | None
def display_amount(line: IngredientLine) -> str          # français, jamais stocké
def plan_decrement(lines, batches_by_product, *, factor: float,
                   skipped_ids: Collection[int] = ()) -> tuple[IngredientNeed, ...]
def per_part_values(frozen: Sequence[Mapping[str, float | None]],
                    parts: float) -> dict[str, float | None]
```

**Décisions de plan, tranchées ici :**

1. `base_amount` applique le facteur **à la quantité en unité de base**, jamais à `amount` : `1 cs × 1,5` donne « 1,5 cs », ce qui n'est ni faux ni utile ; `15 ml × 1,5` donne 22,5 ml, ce qui se décrémente.
2. Ordre de résolution d'une quantité : `packaging_base_quantity` s'il existe (`to_base_quantity`), sinon `measure` si sa `base_unit` **égale** celle du produit, sinon `amount` tel quel — le nombre est déjà en unité de base. Une mesure dont la dimension diffère de celle du produit rend `None` : c'est le refus de la ligne « mesure culinaire, produit en `piece` » et de « volume donné pour un produit en `g` ».
3. `plan_decrement` ne lève **jamais** `InsufficientStock`. Elle le voit venir : quand le besoin dépasse le disponible, elle rend `status="short"`, `allocations` réduites au disponible, et laisse l'arbitrage à l'appelant. C'est la simulation, et une simulation qui lève ne montre rien.
4. `per_part_values` traite **chaque clé indépendamment** : si un seul élément de `frozen` porte `None` sur une clé, le résultat porte `None` **pour cette clé**. Sinon, somme ÷ `parts`. Aucun arrondi.

- [x] **Step 1: Écrire les tests**

Créer `tests/domain/test_recipes.py`. Le module est pur : aucun `hass`, aucun SQLite, aucun réseau. Il se teste en `pytest` nu.

```python
"""La mise à l'échelle et la conversion « 2 cs d'huile » → « 30 ml ».

Ce sont exactement les deux calculs que Grocy a ratés, et ils se testent sans
démarrer quoi que ce soit.
"""
from custom_components.home_stock.domain.recipes import (
    IngredientLine, Measure, base_amount, display_amount, per_part_values,
    plan_decrement, scale_factor,
)

CS = Measure(id=1, name="cuillère à soupe", base_unit="ml", base_quantity=15.0)
PINCEE = Measure(id=4, name="pincée", base_unit="g", base_quantity=1.0)


def _line(**kwargs):
    base = dict(id=1, position=1, product_id=1, product_base_unit="g", amount=None,
                packaging_base_quantity=None, packaging_name=None, measure=None,
                raw_text="", match_state="auto", optional=False)
    return IngredientLine(**{**base, **kwargs})


# --- l'échelle -------------------------------------------------------------

def test_the_factor_is_the_ratio_of_servings():
    assert scale_factor(3, 2) == 1.5
    assert scale_factor(1, 1) == 1.0


def test_a_line_without_a_quantity_is_untouched_by_the_factor():
    assert base_amount(_line(amount=None), factor=1.5) is None


def test_a_non_integer_factor_scales_the_base_quantity_not_the_spoon():
    """15 ml × 1,5 = 22,5 ml se décrémente ; « 1,5 cs » ne se décrémente pas."""
    line = _line(product_base_unit="ml", amount=1, measure=CS)
    assert base_amount(line, factor=1.5) == 22.5


# --- le tableau du § 9, refus compris --------------------------------------

def test_a_number_without_any_measure_is_already_in_the_base_unit():
    assert base_amount(_line(amount=150)) == 150.0


def test_a_product_packaging_wins_over_everything():
    line = _line(amount=2, packaging_base_quantity=30.0, packaging_name="tranche")
    assert base_amount(line) == 60.0


def test_a_culinary_measure_applies_when_the_dimension_matches():
    assert base_amount(_line(product_base_unit="ml", amount=2, measure=CS)) == 30.0
    assert base_amount(_line(product_base_unit="g", amount=1, measure=PINCEE)) == 1.0


def test_a_spoon_of_a_piece_product_is_refused():
    """Un yaourt ne se dose pas à la cuillère."""
    assert base_amount(_line(product_base_unit="piece", amount=2, measure=CS)) is None


def test_a_volume_measure_for_a_gram_product_is_refused():
    assert base_amount(_line(product_base_unit="g", amount=2, measure=CS)) is None


def test_a_line_with_no_product_has_no_base_quantity():
    assert base_amount(_line(product_id=None, product_base_unit=None, amount=2)) is None


def test_half_stays_half_and_never_becomes_zero():
    assert base_amount(_line(product_base_unit="piece", amount=0.5)) == 0.5


# --- le libellé, calculé, jamais stocké ------------------------------------

@pytest.mark.parametrize("line, expected", [
    (_line(product_base_unit="ml", amount=2, measure=CS), "2 cuillères à soupe"),
    (_line(product_base_unit="ml", amount=1, measure=CS), "1 cuillère à soupe"),
    (_line(amount=150), "150 g"),
    (_line(amount=2, packaging_base_quantity=30.0, packaging_name="tranche"), "2 tranches"),
    (_line(amount=None, raw_text="un filet d'huile"), "un filet d'huile"),
])
def test_the_label_is_computed_from_the_single_written_number(line, expected):
    assert display_amount(line) == expected


# --- le plan de décrément ---------------------------------------------------

def test_a_plan_spanning_two_batches_lists_both():
    needs = plan_decrement([_line(amount=700)], {1: [_batch(1, 500), _batch(2, 400)]},
                           factor=1.0)
    assert needs[0].status == "ok"
    assert [a.quantity for a in needs[0].allocations] == [500.0, 200.0]


def test_a_short_stock_is_reported_reduced_never_raised():
    needs = plan_decrement([_line(amount=500)], {1: [_batch(1, 200)]}, factor=1.0)
    assert needs[0].status == "short"
    assert needs[0].available == 200.0
    assert sum(a.quantity for a in needs[0].allocations) == 200.0


def test_no_batch_at_all_falls_back_to_by_hand():
    needs = plan_decrement([_line(amount=500)], {}, factor=1.0)
    assert needs[0].status == "short" and needs[0].allocations == ()
    assert needs[0].available == 0.0


@pytest.mark.parametrize("line, status", [
    (_line(product_id=None, match_state="unmatched", amount=2), "unmatched"),
    (_line(match_state="ignored", amount=2), "ignored"),
    (_line(amount=None), "unquantified"),
    (_line(product_base_unit="piece", amount=2, measure=CS), "unquantified"),
])
def test_the_statuses_the_validation_screen_shows(line, status):
    assert plan_decrement([line], {1: [_batch(1, 500)]}, factor=1.0)[0].status == status


def test_a_skipped_line_is_not_planned():
    needs = plan_decrement([_line(id=7, amount=500)], {1: [_batch(1, 500)]},
                           factor=1.0, skipped_ids={7})
    assert needs[0].status == "unmatched" and needs[0].allocations == ()


def test_two_lines_on_the_same_product_share_the_same_stock():
    """Deux lignes d'oignon dans une recette ne prennent pas deux fois le même
    lot en entier : le plan alloue en séquence, pas en parallèle."""
    lines = [_line(id=1, amount=300), _line(id=2, amount=300)]
    needs = plan_decrement(lines, {1: [_batch(1, 500)]}, factor=1.0)
    assert needs[0].status == "ok" and needs[1].status == "short"
    assert needs[1].available == 200.0


# --- les valeurs par part ---------------------------------------------------

def test_per_part_divides_the_frozen_sums():
    frozen = [{"kcal": 600.0, "proteins": 30.0}, {"kcal": 300.0, "proteins": 6.0}]
    assert per_part_values(frozen, 3) == {"kcal": 300.0, "proteins": 12.0}


def test_one_missing_nutrient_nulls_that_nutrient_and_not_the_other_eight():
    frozen = [{"kcal": 600.0, "proteins": None}, {"kcal": 300.0, "proteins": 6.0}]
    result = per_part_values(frozen, 3)
    assert result["proteins"] is None
    assert result["kcal"] == 300.0


def test_an_empty_plan_gives_null_everywhere_never_zero():
    assert per_part_values([], 3)["kcal"] is None


def test_zero_parts_is_refused_rather_than_dividing():
    with pytest.raises(ValueError):
        per_part_values([{"kcal": 1.0}], 0)
```

- [x] **Step 2: Lancer, vérifier l'échec**

Run: `./scripts/test.sh tests/domain/test_recipes.py -q`
Expected: FAIL — `ModuleNotFoundError: …domain.recipes`

- [x] **Step 3: Écrire `domain/recipes.py`**

Pur, docstrings en anglais, messages d'erreur en français (ils traversent `messages.py`). `plan_decrement` alloue en séquence sur une **copie mutable** du disponible par produit, pour que deux lignes du même produit ne se servent pas deux fois du même lot. `display_amount` pluralise en français (`≥ 2` → pluriel), replie sur `format_quantity` quand il n'y a ni mesure ni conditionnement, et sur `raw_text` quand il n'y a pas de quantité du tout.

- [x] **Step 4: Lancer, vérifier le vert**

Run: `./scripts/test.sh tests/domain/test_recipes.py -q`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add custom_components/home_stock/domain/recipes.py tests/domain/test_recipes.py
git commit -m "feat: the pure recipe rules — scaling, base quantity, decrement plan"
```

---

## Task 6: Les dépôts des recettes, des mesures, des alias et des repas

**Files:**
- Modify: `custom_components/home_stock/storage/repositories.py`
- Test: `tests/storage/test_repositories_recipes.py` (créer)

**Interfaces:** une section commentée **en fin de fichier**, `conn` en premier argument positionnel partout, aucune transaction ouverte ici — le caller la possède.

```python
# recettes
def insert_recipe(conn, *, name: str, source: str, created_at: str, **fields) -> int
def get_recipe(conn, recipe_id: int) -> dict | None
def find_recipe_by_source(conn, source: str, source_ref: str) -> dict | None
def list_recipes(conn, *, search: str | None = None,
                 only_reviewable: bool = False) -> list[dict]   # + unmatched_count
def update_recipe_fields(conn, recipe_id: int, fields: Mapping) -> None
def delete_recipe(conn, recipe_id: int) -> None                  # étapes, puces, lignes
def recipe_is_referenced_by_a_done_meal(conn, recipe_id: int) -> bool

# étapes et puces
def insert_step(conn, *, recipe_id, position, title=None, image_url=None) -> int
def insert_instruction(conn, *, step_id, position, text,
                       timer_label=None, timer_seconds=None) -> int
def list_steps(conn, recipe_id: int) -> list[dict]               # puces incluses

# ingrédients, mesures, alias
def insert_ingredient(conn, *, recipe_id, position, raw_text, **fields) -> int
def list_ingredients(conn, recipe_id: int) -> list[dict]         # joint product, packaging, measure
def update_ingredient_match(conn, ingredient_id, *, product_id, state, score) -> None
def list_measures(conn) -> list[dict]
def find_alias(conn, normalised: str) -> dict | None
def upsert_alias(conn, *, normalised, product_id, created_at) -> None

# créneaux et repas
def list_slots(conn) -> list[dict]
def get_slot(conn, key: str) -> dict | None
def insert_meal(conn, *, uid, day, slot_key, created_at, **fields) -> int
def get_meal(conn, meal_id: int) -> dict | None
def get_meal_by_uid(conn, uid: str) -> dict | None
def list_meals(conn, start: str, end: str) -> list[dict]         # joint recipe/product/slot
def next_meal(conn, day: str) -> dict | None                      # premier 'planned' >= day
def update_meal_fields(conn, meal_id: int, fields: Mapping) -> None
def delete_meal(conn, meal_id: int) -> None
def next_meal_position(conn, day: str, slot_key: str) -> int
def missing_products_between(conn, start: str, end: str) -> list[dict]
```

**Décision de plan — `list_ingredients` fait la jointure une fois.** Elle rend, par ligne, tout ce dont `domain.recipes.IngredientLine` a besoin : `product_base_unit`, `packaging_base_quantity`, `packaging_name`, et les quatre colonnes de la mesure préfixées `measure_*`. La construction de l'`IngredientLine` reste dans `application.py`, mais la requête est écrite une seule fois — c'est ce qui évite qu'un écran lise la mesure autrement qu'un autre.

- [x] **Step 1: Écrire les tests**

Créer `tests/storage/test_repositories_recipes.py`. Reprendre le helper de base migrée déjà utilisé par `tests/storage/test_repositories.py`.

```python
def test_a_recipe_round_trips_with_its_steps_and_bullets(conn): ...
def test_list_recipes_counts_the_unmatched_ingredients(conn):
    """Le badge « n non appariés » de l'écran Recettes vient d'ici, pas d'un
    comptage refait côté panneau."""
def test_list_recipes_filters_on_review_and_on_search(conn): ...
def test_list_recipes_search_is_accent_and_case_insensitive(conn): ...
def test_find_recipe_by_source_is_what_makes_an_import_replayable(conn): ...
def test_delete_recipe_removes_its_steps_bullets_and_ingredients(conn): ...
def test_a_recipe_referenced_by_a_done_meal_is_detected(conn):
    """La suppression sera refusée par-dessus (§ 17) ; le dépôt se contente de
    dire la vérité."""
def test_list_ingredients_joins_the_product_the_packaging_and_the_measure(conn): ...
def test_list_ingredients_keeps_a_line_whose_product_is_null(conn): ...
def test_upsert_alias_is_idempotent_and_moves_an_existing_alias(conn): ...
def test_list_meals_returns_the_slot_order_then_the_position(conn):
    """Le planning affiche petit-déjeuner, déjeuner, dîner, en-cas — dans cet
    ordre, y compris pour un repas ajouté après coup."""
def test_next_meal_ignores_a_done_and_a_skipped_one(conn): ...
def test_next_meal_position_appends_rather_than_colliding(conn): ...
def test_missing_products_between_lists_a_product_without_enough_stock(conn): ...
def test_missing_products_between_ignores_unmatched_and_ignored_lines(conn):
    """On ne réclame pas d'acheter ce qu'on n'a pas su identifier ; ce serait
    une liste de courses fausse, et c'est le lot 4 qui la construira."""
def test_missing_products_between_scales_by_the_meal_servings(conn): ...
```

- [x] **Step 2: Lancer, vérifier l'échec**
Run: `./scripts/test.sh tests/storage/test_repositories_recipes.py -q` → FAIL (`AttributeError: … insert_recipe`).

- [x] **Step 3: Écrire les dépôts**
Section commentée en fin de `repositories.py`. Réutiliser `_insert`, `_update_fields`, `_row`, `_rows`. Les listes blanches de champs (`RECIPE_FIELDS`, `INGREDIENT_FIELDS`, `MEAL_FIELDS`) suivent le motif de `PRODUCT_FIELDS` / `ARTICLE_FIELDS` : un nom de colonne interpolé dans du SQL ne se prend jamais dans une charge utile brute.

- [x] **Step 4: Vert, puis suite entière**
Run: `./scripts/test.sh tests/storage -q && ./scripts/test.sh -q` → PASS

- [x] **Step 5: Commit**
```bash
git add custom_components/home_stock/storage/repositories.py tests/storage/test_repositories_recipes.py
git commit -m "feat: repositories for recipes, ingredients, measures, aliases and meals"
```

---

## Task 7: L'appariement d'un ingrédient sur un produit, et les alias appris

**Files:**
- Modify: `custom_components/home_stock/application.py`
- Create: `tests/fixtures/recipes/ingredients.json`, `tests/fixtures/recipes/products.json`
- Test: `tests/test_ingredient_matching.py` (créer)

**Interfaces:**
- Consomme : `matching.normalise`, `matching.candidates`, `matching.preselect`, `matching.PRESELECT_SCORE`, `matching.PRESELECT_MARGIN` — **avec leurs seuils inchangés**. Aucune modification de `domain/matching.py` : un seuil qui diffère entre deux écrans est un seuil que personne ne comprend.
- Produit :

```python
def resolve_ingredient_match(conn, *, raw_text: str, ingredient_name: str | None,
                             products: Sequence[dict]) -> tuple[str, int | None, float | None, list[Candidate]]
    # rend (match_state, product_id, match_score, candidats_a_proposer)

class StockManager:
    def match_ingredient(self, ingredient_id: int, *, product_id: int | None,
                         state: str, create_alias: bool = False) -> dict
```

**Ordre de résolution, normatif (spec § 8) :**

1. **Alias.** `matching.normalise(texte)` cherché dans `ingredient_alias`. Touché → `('confirmed', product_id, 1.0, [])`.
2. **Appariement.** `candidates(names=[nom_isolé, raw_text_sans_quantité, raw_text], products=…)`. Le meilleur des trois l'emporte — exactement comme le lot 1 essaie `generic_name_fr`, `product_name_fr` et le nom sans la marque.
3. **`preselect()`.** Un candidat → `('auto', id, score, [])`. Sinon → `('unmatched', None, None, les cinq candidats)`.

**Deux règles qui ne se négocient pas :**
- **Un `auto` n'écrit jamais d'alias.** Seul `match_ingredient` avec `create_alias=True` en crée un. Sans cette règle, un appariement automatique faux deviendrait permanent et contaminerait toutes les recettes suivantes — c'est le ré-appariement par nom qui a produit 35 doublons dans Grocy en avril 2026.
- **`ignored` est un état de plein droit.** Sel, poivre, eau. Une ligne `ignored` s'affiche, ne décrémente rien, et ne réapparaît jamais dans les manques.

- [x] **Step 1: Fabriquer les fixtures**

`tests/fixtures/recipes/products.json` : les 299 produits réels (id, `name`), extraits **d'une copie** de la base ou du catalogue déjà utilisé par `tests/fixtures/off/catalogue.json`. `tests/fixtures/recipes/ingredients.json` : les 420 `raw_text` réels de `recipes_pos`, extraits **d'une copie** de `grocy.db`, en lecture seule, une fois. Aucun script de génération n'est versionné et rien n'est écrit ailleurs que dans ces deux fichiers. Si la copie n'est pas disponible au moment de l'implémentation, **réduire l'échantillon plutôt que d'inventer des lignes** : un taux mesuré sur 60 lignes vraies vaut mieux qu'un taux mesuré sur 420 lignes imaginaires, et le test le dit dans son message.

- [x] **Step 2: Écrire les tests**

```python
"""L'appariement rejoué sur les lignes réelles, avec les seuils du lot 1."""

def test_a_confirmed_alias_beats_a_higher_scoring_preselect(conn):
    """Chaque arbitrage humain vaut pour toujours, y compris contre un score
    supérieur : c'est ce qui rend le travail décroissant."""

def test_an_auto_match_never_writes_an_alias(conn): ...
def test_confirming_by_hand_writes_the_alias_once(conn): ...
def test_confirming_a_second_product_moves_the_alias(conn): ...
def test_marking_a_line_ignored_needs_no_product(conn): ...
def test_marking_a_line_auto_without_a_product_is_refused(conn):
    """La contrainte de schéma le refuse déjà ; la couche du dessus doit le
    refuser AVANT, avec une phrase française."""

@pytest.mark.parametrize("raw_text, expected_product", [
    ("coriandre fraîche", "Coriandre"),
    ("2 cs d'huile d'olive", "Huile d'olive"),
    ("3 œufs", "Œufs"),
])
def test_the_named_cases_that_must_work(conn, raw_text, expected_product): ...

@pytest.mark.parametrize("raw_text", ["sel", "poivre du moulin", "eau", "un peu de tout"])
def test_the_cases_that_must_stay_unmatched_rather_than_be_guessed(conn, raw_text):
    """Deviner ici, c'est écrire un décrément faux dans un journal en ajout
    seul. `unmatched` est un résultat, pas un échec."""

def test_the_automatic_match_rate_on_the_real_lines(conn):
    """Mesure, et épingle un plancher. Ce test n'a pas vocation à monter tout
    seul : s'il baisse, c'est que les seuils ou la normalisation ont bougé."""
    rate = _replay_all(conn)
    assert rate >= 0.45, f"taux d'appariement automatique tombé à {rate:.0%}"

def test_the_replay_is_deterministic(conn):
    """Deux passes sur les mêmes fixtures donnent exactement le même verdict
    ligne par ligne — sinon aucune mesure n'a de sens."""
```

**Note pour l'implémenteur :** le plancher de `test_the_automatic_match_rate_on_the_real_lines` s'écrit **après** la première mesure, arrondi vers le bas au multiple de 5 %. Ne pas inventer 0,45 s'il mesure 0,72 ; ne pas non plus baisser le plancher pour faire passer une régression.

- [x] **Step 3: Lancer, vérifier l'échec** — `./scripts/test.sh tests/test_ingredient_matching.py -q`

- [x] **Step 4: Écrire la résolution et `match_ingredient`**

`resolve_ingredient_match` est une fonction module-level de `application.py` (elle prend `conn`, elle n'ouvre rien). `match_ingredient` ouvre une transaction, valide `state` contre `MATCH_STATES`, refuse `state != 'unmatched'` sans `product_id` avec une phrase française, écrit la ligne, et n'écrit l'alias que si `create_alias` **et** `state == 'confirmed'`.

- [x] **Step 5: Vert** — `./scripts/test.sh tests/test_ingredient_matching.py -q && ./scripts/test.sh -q`

- [x] **Step 6: Commit**
```bash
git add custom_components/home_stock/application.py tests/fixtures/recipes tests/test_ingredient_matching.py
git commit -m "feat: ingredient matching with learned aliases, on the real 420 lines"
```

---

## Task 8: Le client TheMealDB

**Files:**
- Create: `custom_components/home_stock/recipes/__init__.py`, `custom_components/home_stock/recipes/source.py`
- Create: `tests/recipes/__init__.py`, `tests/fixtures/recipes/themealdb_lookup.json`, `tests/fixtures/recipes/themealdb_search.json`
- Test: `tests/recipes/test_source.py` (créer)

**Interfaces:**
- Consomme : le protocole `OffTransport` de `off/client.py` — `get_json(url, headers, timeout) -> tuple[int, dict | None]`. **Réutilisé tel quel, sans le renommer** : un test qui remplace `HomeStockData.transport` ferme d'un coup toutes les sorties réseau du composant, celle-ci comprise.
- Produit :

```python
BASE_URL: Final = "https://www.themealdb.com/api/json/v1/{key}/"
TIMEOUT: Final = 10.0
BULK_INTERVAL: Final = 8.0          # même intervalle que l'ingestion OFF

@dataclass(frozen=True)
class SourceHit:
    source_ref: str                 # idMeal
    name: str
    image_url: str | None
    category: str | None
    area: str | None

class MealDbClient:
    def __init__(self, transport, *, key: str = "1", user_agent: str,
                 clock=time.monotonic, sleeper=asyncio.sleep) -> None
    async def search(self, query: str) -> list[SourceHit]         # search.php?s=
    async def by_ingredient(self, ingredient: str) -> list[SourceHit]  # filter.php?i=
    async def lookup(self, source_ref: str) -> dict | None        # lookup.php?i=
```

**Le contrat réseau est celui du lot 1, mot pour mot.** Transport injecté, **timeout 10 s, une seule tentative, aucune reprise**. **Aucune méthode ne lève jamais** : elle rend une liste vide ou `None`, et l'appelant affiche un message. Un import en lot respecte `BULK_INTERVAL`, comme l'ingestion Open Food Facts.

- [x] **Step 1: Capturer les fixtures**

Deux fichiers, capturés une fois puis versionnés : la réponse de `lookup.php?i=52772` (une fiche complète, avec ses `strIngredient1..20` et `strMeasure1..20` dont la plupart sont vides) et celle de `search.php?s=chicken`. Les capturer **hors du composant**, à la main ; le dépôt ne versionne pas de script d'appel.

- [x] **Step 2: Écrire les tests**

Créer `tests/recipes/test_source.py`. Le double de transport suit `_InertTransport` de `conftest.py` : `async def get_json(self, url, headers, timeout)`.

```python
class _Transport:
    """Un transport scripté. Il enregistre ce qu'on lui demande — c'est ce qui
    prouve qu'on n'a essayé qu'UNE fois."""
    def __init__(self, *reponses): ...
    async def get_json(self, url, headers, timeout): ...


async def test_lookup_reads_the_captured_card(): ...
async def test_search_maps_the_summary_fields(): ...
async def test_by_ingredient_asks_the_filter_route():
    """`filter.php?i=` répond à la seule question qu'un garde-manger permet de
    poser : qu'est-ce que je peux faire avec ça."""

async def test_the_key_from_the_options_lands_in_the_url(): ...
async def test_a_timeout_gives_an_empty_result_and_never_raises(): ...
async def test_a_404_gives_an_empty_result(): ...
async def test_a_500_gives_an_empty_result(): ...
async def test_truncated_json_gives_an_empty_result(): ...
async def test_a_payload_that_is_not_a_dict_gives_an_empty_result(): ...
async def test_meals_null_is_an_empty_search_not_an_error():
    """TheMealDB rend `{"meals": null}` quand il ne trouve rien. C'est une
    recherche vide, pas une panne."""

async def test_only_one_attempt_is_ever_made():
    """Aucune reprise : une source de découverte qui rejoue trois fois retarde
    un dîner pour rien."""
    transport = _Transport(TimeoutError())
    assert await client.search("x") == []
    assert transport.calls == 1

async def test_the_bulk_interval_is_respected_between_two_lookups():
    """Même dispositif que BULK_INTERVAL pour Open Food Facts : horloge et
    dormeur injectés, aucune attente réelle dans les tests."""

async def test_the_user_agent_is_sent(): ...


@pytest.mark.network
async def test_the_real_contract_has_not_moved():
    """Désactivé par défaut, comme le test réseau du lot 1 pour OFF. Il ne
    tourne qu'à la main : `./scripts/test.sh -m network`."""
```

Déclarer le marqueur dans `pytest.ini` (`markers = network: touche le réseau réel`) et l'exclure par défaut (`addopts = -m "not network"`) — **en vérifiant d'abord** qu'ajouter `addopts` ne casse aucune invocation existante de `scripts/test.sh`.

- [x] **Step 3: Lancer, vérifier l'échec** — `./scripts/test.sh tests/recipes/test_source.py -q`

- [x] **Step 4: Écrire `recipes/source.py`**

Motif recopié de `off/client.py` : budget de temps, `except Exception: return []` autour de l'appel de transport, statut non-200 → vide, charge non-`dict` → vide, `meals` absent ou `null` → vide. Aucun `hass`, aucun import de `homeassistant`.

- [x] **Step 5: Vert** — `./scripts/test.sh tests/recipes -q`

- [x] **Step 6: Commit**
```bash
git add custom_components/home_stock/recipes tests/recipes tests/fixtures/recipes pytest.ini
git commit -m "feat: a TheMealDB client that never blocks and never retries"
```

---

## Task 9: De la fiche TheMealDB aux lignes de recette

**Files:**
- Create: `custom_components/home_stock/recipes/mapping.py`
- Modify: `custom_components/home_stock/application.py`
- Test: `tests/recipes/test_mapping.py` (créer), `tests/test_recipes_write.py` (créer)

**Interfaces:**
- Produit, dans `recipes/mapping.py` (pur : aucun réseau, aucun `hass`, aucun SQLite) :

```python
@dataclass(frozen=True)
class SourceIngredient:
    position: int
    name: str
    raw_text: str          # « 2 tbsp olive oil », reconstruit mesure + nom
    amount: float | None
    unit: str | None       # tel que la source l'écrit, non converti

@dataclass(frozen=True)
class SourceRecipe:
    name: str
    source_ref: str
    image_url: str | None
    source_url: str | None
    instructions: str      # le pavé, non découpé — l'adaptation s'en charge
    ingredients: tuple[SourceIngredient, ...]

def parse_measure(text: str | None) -> tuple[float | None, str | None]
def map_meal(payload: Mapping[str, Any]) -> SourceRecipe | None
```

- Produit, dans `application.py` :

```python
class StockManager:
    def create_recipe(self, *, name, servings=1, source="manual", steps=(),
                      ingredients=(), **fields) -> int
    def get_recipe_view(self, recipe_id: int) -> dict     # recette + étapes + puces + lignes résolues + candidats
    def list_recipes(self, *, search=None, only_reviewable=False) -> list[dict]
    def update_recipe(self, recipe_id: int, fields: Mapping) -> None
    def delete_recipe(self, recipe_id: int) -> None       # refusée si un repas 'done' la référence
    def write_source_recipe(self, recipe: SourceRecipe, *,
                            adapted: AdaptedRecipe | None = None) -> tuple[int, bool]
```

**Décisions de plan :**
- `parse_measure` lit le début du texte : un nombre (entier, décimal, fraction unicode `½ ¼ ⅓ ¾`, fraction ASCII `1/2`, intervalle `1-2` → la borne basse), puis une unité. Tout ce qui n'est pas reconnu laisse `(None, None)` et le texte entier part dans `raw_text`. **Aucune devinette** : « a handful » n'a ni nombre ni unité.
- `write_source_recipe` est **rejouable** : `find_recipe_by_source` d'abord, et un second import de la même `source_ref` met à jour la recette au lieu d'en créer une deuxième — c'est ce que garantit `idx_recipe_source`.
- **La ré-écriture ne touche jamais une ligne `confirmed`**, ni une étape corrigée à la main. Même règle que `article.manual_fields` protégeant une valeur saisie d'une resynchronisation OFF.
- Une ligne dont la mesure ne se ramène pas à l'unité de base du produit garde `amount = NULL` et son `raw_text`. Le mapping **n'écrit jamais** de `measure_id` d'une dimension incompatible : il consulte `units.convertible_amount` d'abord, puis les mesures culinaires, et renonce sinon.

- [x] **Step 1: Écrire les tests du mapping**

```python
@pytest.mark.parametrize("text, expected", [
    ("2 tbsp", (2.0, "tbsp")), ("1/2 cup", (0.5, "cup")), ("½ tsp", (0.5, "tsp")),
    ("250g", (250.0, "g")), ("1.5 kg", (1.5, "kg")), ("1-2 cloves", (1.0, "cloves")),
    ("a handful", (None, None)), ("", (None, None)), (None, (None, None)),
    ("to taste", (None, None)), ("2", (2.0, None)),
])
def test_parse_measure(text, expected):
    assert parse_measure(text) == expected


def test_map_meal_pairs_the_twenty_slots(): ...
def test_map_meal_skips_an_empty_ingredient_in_the_middle():
    """TheMealDB laisse des trous : strIngredient7 vide entre deux pleins.
    Les positions se renumérotent, elles ne se décalent pas."""
def test_map_meal_keeps_an_ingredient_whose_measure_is_empty():
    """Un nom sans mesure est une ligne parfaitement légitime (§ 9)."""
def test_map_meal_refuses_a_card_without_a_name_or_an_id(): ...
def test_map_meal_refuses_a_payload_that_is_not_a_dict(): ...
def test_map_meal_caps_the_number_of_ingredients(): ...
def test_the_raw_text_is_the_source_verbatim_and_nothing_computed():
    """`raw_text` a le statut d'`article.off_raw` : provenance, jamais calcul."""
```

- [x] **Step 2: Écrire les tests d'écriture** dans `tests/test_recipes_write.py`

```python
def test_a_source_recipe_lands_with_its_ingredients(manager): ...
def test_importing_the_same_source_ref_twice_updates_and_does_not_duplicate(manager): ...
def test_a_reimport_never_overwrites_a_confirmed_ingredient(manager): ...
def test_a_reimport_never_overwrites_a_manually_edited_step(manager): ...
def test_an_unconvertible_measure_lands_as_a_null_amount(manager):
    """« 1 tbsp » sur un produit suivi à la pièce : la ligne existe, s'affiche,
    et ne décrémente rien. NULL veut dire inconnu, jamais zéro."""
def test_a_convertible_mass_lands_converted_with_no_measure_id(manager):
    """250 g sur un produit en g : amount = 250, measure_id NULL."""
def test_a_culinary_measure_lands_as_amount_plus_measure_id(manager):
    """2 cs d'huile : amount = 2, measure_id = celui de la cuillère à soupe.
    La quantité en unité de base reste CALCULÉE."""
def test_deleting_a_recipe_referenced_by_a_done_meal_is_refused(manager):
    with pytest.raises(ValueError):
        manager.delete_recipe(recipe_id)
def test_deactivating_is_the_path_instead(manager): ...
def test_get_recipe_view_returns_the_five_candidates_for_an_unmatched_line(manager): ...
def test_create_recipe_refuses_more_steps_than_MAX_RECIPE_STEPS(manager): ...
def test_create_recipe_writes_nothing_when_one_ingredient_is_invalid(manager):
    """Transaction unique : jamais une demi-recette."""
```

- [x] **Step 3: Lancer, vérifier l'échec, écrire, revérifier**

```bash
./scripts/test.sh tests/recipes/test_mapping.py tests/test_recipes_write.py -q   # FAIL puis PASS
```

- [x] **Step 4: Commit**
```bash
git add custom_components/home_stock/recipes/mapping.py custom_components/home_stock/application.py tests/recipes/test_mapping.py tests/test_recipes_write.py
git commit -m "feat: map a TheMealDB card onto recipe rows, replayably"
```

---

## Task 10: L'adaptation par un agent conversationnel, et les deux options

**Files:**
- Create: `custom_components/home_stock/recipes/adapt.py`
- Modify: `custom_components/home_stock/config_flow.py`, `custom_components/home_stock/const.py`, `custom_components/home_stock/__init__.py`, `custom_components/home_stock/translations/{fr,en}.json`
- Test: `tests/recipes/test_adapt.py` (créer), `tests/test_config_flow.py`

**Interfaces:**

```python
MAX_PROMPT_INSTRUCTIONS: Final = 8000     # au-delà, on tronque la source, pas la réponse

@dataclass(frozen=True)
class AdaptedRecipe:
    name: str
    summary: str | None
    total_minutes: int | None
    utensils: str | None
    servings: int
    steps: tuple[AdaptedStep, ...]         # titre + puces + minuteur éventuel
    ingredient_names: tuple[str, ...]      # un nom isolé par position source
    ingredient_amounts: tuple[tuple[float | None, str | None], ...]

def build_prompt(recipe: SourceRecipe) -> str          # en français, demande UN objet JSON
def extract_json(text: str) -> dict | None             # premier bloc à accolades ÉQUILIBRÉES
def validate_adaptation(payload: Any, *, source: SourceRecipe) -> AdaptedRecipe | None

async def adapt(hass, *, agent_id: str | None, recipe: SourceRecipe) -> AdaptedRecipe | None
```

- Options, dans `config_flow.py` (ajoutées au schéma existant, **après** `expiration_alert_days`) :

| Option | Défaut | Sélecteur |
|---|---|---|
| `recipe_agent` | *(vide)* | `EntitySelector(EntitySelectorConfig(domain="conversation"))`, enveloppé dans `vol.Optional` |
| `recipe_source_key` | `"1"` | `TextSelector`, borné par `bounded_text` |

- `HomeStockData` gagne `recipe_source: MealDbClient`, construit dans `async_setup_entry` avec `transport` et la clé des options. Un rechargement de l'entrée le reconstruit (le listener existe déjà).

**Décision de plan — l'appel passe par le service, pas par un import de `conversation`.** `hass.services.async_call("conversation", "process", {"text": …, "agent_id": …}, blocking=True, return_response=True)`. Trois raisons : le composant ne dépend pas du module `conversation` de Home Assistant à l'import (donc `manifest.json` reste inchangé et l'intégration démarre sans lui), l'agent est désigné par `entity_id` exactement comme le sélecteur le rend, et un test remplace le service par un double sans monter d'intégration `conversation`.

**Décision de plan — la lecture est défensive de bout en bout.** Un agent conversationnel a le droit d'écrire « Voici la recette adaptée : » devant son JSON, c'est même son métier. `extract_json` cherche d'abord la charge telle quelle, puis le premier bloc délimité par des **accolades équilibrées** (compteur, pas d'expression régulière — une regex non gloutonne coupe au premier `}` interne). Chaque champ passe par `bounded_text` / `finite_float` / `bounded_int`. **Toute anomalie fait échouer l'adaptation entière** ; la recette est alors écrite telle quelle depuis la source, `language = 'en'`, `needs_review = 1`, `adapted_at = NULL`.

- [x] **Step 1: Écrire les tests**

```python
# --- l'invite ---------------------------------------------------------------
def test_the_prompt_is_french_and_asks_for_json_and_nothing_else(): ...
def test_the_prompt_carries_every_ingredient_position(): ...
def test_a_very_long_instruction_block_is_truncated_in_the_prompt(): ...

# --- l'extraction -----------------------------------------------------------
def test_pure_json_is_read(): ...
def test_json_wrapped_in_prose_is_read():
    assert extract_json('Voici la recette adaptée :\n{"name": "x"}\nBon appétit !')["name"] == "x"
def test_json_inside_a_fenced_block_is_read(): ...
def test_nested_braces_do_not_cut_the_block_short():
    """Une regex non gloutonne couperait au premier `}` interne."""
def test_unbalanced_braces_give_nothing(): ...
def test_truncated_json_gives_nothing(): ...
def test_a_json_array_at_the_top_level_gives_nothing(): ...

# --- la validation ----------------------------------------------------------
def test_servings_as_a_word_fails_the_whole_adaptation():
    assert validate_adaptation({"servings": "quatre", ...}, source=SOURCE) is None
def test_a_forty_thousand_character_title_fails_the_whole_adaptation(): ...
def test_a_negative_timer_fails_the_whole_adaptation(): ...
def test_a_timer_label_without_a_duration_fails_the_whole_adaptation(): ...
def test_more_ingredient_names_than_the_source_had_fails(): ...
def test_a_valid_answer_maps_cleanly(): ...

# --- l'appel, et ses cinq échecs -------------------------------------------
async def test_no_agent_configured_means_no_adaptation_and_no_call(hass): ...
async def test_an_agent_that_raises_leaves_the_recipe_in_english(hass): ...
async def test_an_agent_that_times_out_leaves_the_recipe_in_english(hass): ...
async def test_an_unreadable_answer_leaves_the_recipe_in_english(hass): ...
async def test_an_out_of_bounds_field_leaves_the_recipe_in_english(hass): ...

@pytest.mark.parametrize("failure", ["absent", "raises", "timeout", "unreadable", "out_of_bounds"])
async def test_in_every_failure_the_recipe_exists_marked_for_review(hass, setup_entry, failure):
    """Rien n'est à moitié écrit : ni une étape orpheline, ni un titre traduit
    sur des puces anglaises."""
    recipe = await _import_with(hass, failure)
    assert recipe["needs_review"] == 1
    assert recipe["language"] == "en" and recipe["adapted_at"] is None
    assert _step_count(recipe) in (0, _source_step_count())

async def test_adaptation_never_rewrites_a_confirmed_ingredient(hass): ...
async def test_the_adapt_recipe_service_can_pick_it_up_later(hass): ...
```

Et dans `tests/test_config_flow.py` :

```python
async def test_the_options_flow_offers_the_conversation_agent_and_the_source_key(hass): ...
async def test_an_empty_agent_is_a_valid_choice(hass):
    """Vide = aucune adaptation. C'est un réglage, pas une erreur."""
async def test_the_source_key_defaults_to_one(hass): ...
async def test_changing_an_option_reloads_the_entry(hass): ...
```

- [x] **Step 2: Lancer, vérifier l'échec** — `./scripts/test.sh tests/recipes/test_adapt.py tests/test_config_flow.py -q`

- [x] **Step 3: Écrire `recipes/adapt.py`, les options et le câblage**

Le composant **n'embarque aucune clé d'API** et n'en lit aucune : ni `GEMINI_KEY`, ni le `.env` de `data/tools/grocy-off`, ni rien d'autre. C'est une règle, pas une préférence — le composant part sur HACS.

Ajouter les deux libellés dans `options.step.init.data` de `translations/fr.json` **et** `en.json`.

- [x] **Step 4: Vert** — `./scripts/test.sh tests/recipes tests/test_config_flow.py -q && ./scripts/test.sh -q`

- [x] **Step 5: Commit**
```bash
git add custom_components/home_stock/recipes/adapt.py custom_components/home_stock/config_flow.py custom_components/home_stock/const.py custom_components/home_stock/__init__.py custom_components/home_stock/translations tests/recipes/test_adapt.py tests/test_config_flow.py
git commit -m "feat: adapt an imported recipe through a Home Assistant conversation agent"
```

---

## Task 11: Poser, déplacer, annuler un repas

**Files:**
- Modify: `custom_components/home_stock/application.py`
- Test: `tests/test_meals_plan.py` (créer)

**Interfaces:**

```python
class StockManager:
    def plan_meal(self, *, day: str, slot_key: str, recipe_id=None, product_id=None,
                  amount=None, packaging_id=None, note=None, servings: float = 1.0,
                  position: int | None = None, uid: str | None = None,
                  created_at: str | None = None) -> dict     # {"meal_id", "uid"}
    def move_meal(self, meal_id: int, *, day: str, slot_key: str,
                  position: int | None = None) -> None
    def cancel_meal(self, meal_id: int) -> str               # "deleted" | "skipped"
    def list_meals(self, start: str, end: str) -> list[dict]
    def meal_summary(self, *, tz: ZoneInfo, now: datetime | None = None,
                     horizon_days: int = MEAL_HORIZON_DAYS) -> dict
```

**Décisions de plan :**
- **`uid` est un UUID, généré au dépôt**, préfixé `home-stock-meal-` pour être reconnaissable dans un client de calendrier. Il est **injectable** (`uid=`) pour que les tests soient déterministes ; en production personne ne le passe.
- **`day` est une journée alimentaire.** `plan_meal` valide la forme `AAAA-MM-JJ` (`iso_date`) et rien d'autre : c'est une date que l'appelant a déjà décidée, pas un instant à convertir.
- **Un repas `done` ne se déplace pas.** Ses mouvements portent une date figée ; déplacer la ligne les décorrélerait silencieusement. Le refus est explicite et français.
- **`cancel_meal` supprime un `planned` et passe un `done` à `skipped`.** Supprimer un `done` détruirait la référence `movement.ref_type = 'meal'` que le journal porte déjà et qui, elle, est en ajout seul.
- **Un repas dont l'heure est passée reste `planned`.** Le composant ne décide pas tout seul qu'un repas n'a pas eu lieu.
- `meal_summary` rend `{"next": {...} | None, "recipes": {...}, "missing": [...]}` : c'est ce que le coordinateur publiera (tâche 15).

- [x] **Step 1: Écrire les tests**

```python
def test_a_recipe_meal_lands_with_a_uid(manager): ...
def test_a_product_meal_and_a_note_meal_are_both_legitimate(manager): ...
def test_a_meal_that_is_two_things_at_once_is_refused(manager):
    """La contrainte de schéma le dit ; la couche du dessus doit le dire AVANT,
    avec une phrase française."""
def test_a_meal_that_is_nothing_at_all_is_refused(manager): ...
@pytest.mark.parametrize("servings", [0, -1, float("inf")])
def test_servings_must_be_strictly_positive(manager, servings): ...
def test_an_unknown_slot_is_refused(manager): ...
def test_a_malformed_day_is_refused(manager):
    for day in ("2026-8-1", "20260801", "2026-13-01", "hier", ""):
        with pytest.raises(...): manager.plan_meal(day=day, slot_key="dinner", note="x")
def test_two_meals_in_the_same_slot_get_distinct_positions(manager): ...
def test_moving_a_planned_meal_changes_day_slot_and_position(manager): ...
def test_moving_a_done_meal_is_refused(manager):
    """Ses mouvements portent une date que rien ne peut plus changer."""
def test_cancelling_a_planned_meal_deletes_the_row(manager): ...
def test_cancelling_a_done_meal_marks_it_skipped_and_keeps_the_row(manager): ...
def test_a_meal_whose_time_has_passed_stays_planned(manager): ...
def test_list_meals_bounds_are_food_days_inclusive_start_exclusive_end(manager): ...
def test_meal_summary_names_the_next_unvalidated_meal(manager): ...
def test_meal_summary_counts_the_missing_products_over_seven_days(manager): ...
def test_meal_summary_is_empty_without_any_meal_and_never_raises(manager): ...
```

- [x] **Step 2: Lancer, vérifier l'échec** — `./scripts/test.sh tests/test_meals_plan.py -q`

- [x] **Step 3: Écrire les méthodes**

Une transaction par méthode. Les messages français passent par les motifs de `messages.py` que la tâche 17 ajoutera : ici, lever `ValueError` avec un texte **anglais stable** (`unknown slot 'brunch'`, `meal 3 is already done`) et laisser la traduction à `messages.py`, exactement comme le lot 0 l'a fait pour `unknown article 7`.

- [x] **Step 4: Vert** — `./scripts/test.sh tests/test_meals_plan.py -q && ./scripts/test.sh -q`

- [x] **Step 5: Commit**
```bash
git add custom_components/home_stock/application.py tests/test_meals_plan.py
git commit -m "feat: plan, move and cancel a meal — a done meal never moves"
```

---

## Task 12: Simuler un repas, sans rien écrire

**Files:**
- Modify: `custom_components/home_stock/application.py`
- Test: `tests/test_meal_preview.py` (créer)

**Interfaces:**

```python
class StockManager:
    def preview_meal(self, meal_id: int, *, servings: float | None = None,
                     skip_ingredient_ids: Collection[int] = (),
                     portions_eaten: float | None = None,
                     parts_total: int | None = None,
                     parts_mine: int | None = None,
                     today: str | None = None) -> dict
```

Ce qu'elle rend :

```python
{
  "meal_id": 12, "day": "2026-08-21", "slot_key": "dinner",
  "recipe": {"id": 4, "name": "Gratin de courgettes", "servings": 2},
  "servings": 3.0, "factor": 1.5,
  "lines": [
    {"ingredient_id": 41, "label": "300 g de courgettes", "product_id": 8,
     "product_name": "Courgette", "status": "ok", "needed": 450.0,
     "available": 900.0, "base_unit": "g",
     "batches": [{"batch_id": 3, "quantity": 450.0, "best_before": "2026-08-24"}]},
    ...
  ],
  "by_hand": [ ... ],              # unmatched + unquantified, à sortir à la main
  "dish": {"product_name": "Reste — Gratin de courgettes", "parts": 3.0,
           "best_before": "2026-08-24", "cost": 4.12,
           "kcal": 540.0, "proteins": 21.0, ..., "unvalued": 1},
  "blocking": ["short"],           # vide si la validation peut partir
}
```

**Décisions de plan :**
- **La simulation appelle `domain/recipes.plan_decrement`, qui appelle `domain/stock.allocate` — la même fonction que la sortie réelle.** Une simulation qui ne partage pas son code avec l'exécution est une simulation qui ment un jour. Il n'existe **aucune** seconde implémentation du FIFO dans ce lot.
- `preview_meal` **n'ouvre aucune transaction en écriture** : elle lit sur `db.read()`. Elle ne crée donc **pas** le produit de restes ; le récapitulatif du plat nomme le produit **futur** sans l'écrire.
- Les valeurs du plat (coût et neuf nutriments) sont estimées ici avec les **mêmes taux figés** que la validation utilisera : ceux portés par les lots que le FIFO vise, via `per_part_values`. Un chiffre montré avant l'écriture doit être celui qui sera écrit, sinon il n'a pas d'intérêt.
- `blocking` porte les raisons pour lesquelles `validate_meal` refuserait aujourd'hui. **Une ligne `short` bloque** tant qu'elle n'a pas été soit acceptée (le panneau renvoie la quantité réduite), soit retirée (`skip_ingredient_ids`) : servir 200 g quand on en demande 500 sans le dire écrit un chiffre faux.
- **Une ligne `unmatched`, `unquantified` ou `ignored` ne bloque jamais rien.** Refuser un dîner entier parce qu'une gousse d'ail n'est pas appariée serait une leçon de morale, pas un outil.

- [x] **Step 1: Écrire les tests**

```python
def test_a_preview_writes_absolutely_nothing(manager):
    before = _snapshot(manager)           # movement, batch, product, article, meal
    manager.preview_meal(meal_id)
    assert _snapshot(manager) == before

def test_the_lines_carry_the_batches_the_fifo_would_take(manager): ...
def test_the_scaling_applies_to_the_base_quantity(manager):
    """Un repas à 3 parts sur une recette à 2 : facteur 1,5 sur les millilitres,
    jamais sur les cuillères."""
def test_a_line_across_two_batches_lists_both_with_their_shares(manager): ...
def test_a_short_line_is_offered_reduced_and_reported_blocking(manager): ...
def test_a_line_with_no_batch_at_all_falls_back_to_by_hand(manager): ...
def test_an_unmatched_line_lands_in_by_hand_and_blocks_nothing(manager): ...
def test_an_unquantified_line_lands_in_by_hand_and_blocks_nothing(manager): ...
def test_an_ignored_line_is_silent_and_appears_nowhere(manager):
    """Sel, poivre, eau : ignorés, sans signalement. Sans cet état, le même
    arbitrage serait à reprendre à chaque recette."""
def test_skipping_a_line_clears_the_block(manager): ...
def test_the_dish_summary_carries_the_parts_and_the_default_shelf_life(manager): ...
def test_a_recipe_shelf_life_overrides_the_default_three_days(manager): ...
def test_the_dish_nutrients_are_the_frozen_rates_not_the_recipe_s_wish(manager): ...
def test_one_missing_nutrient_nulls_that_one_and_counts_it_in_unvalued(manager): ...
def test_preview_of_a_note_meal_has_no_lines_and_no_dish(manager): ...
def test_preview_of_a_product_meal_plans_one_line(manager): ...
def test_preview_of_a_done_meal_is_refused(manager): ...
def test_preview_of_an_unknown_meal_raises_a_lookup_error(manager): ...
def test_the_preview_uses_the_same_allocation_function_as_the_write(manager, monkeypatch):
    """Épingle le partage de code : si quelqu'un écrit un second FIFO un jour,
    ce test tombe."""
    calls = []
    monkeypatch.setattr(stock, "allocate", _counting(stock.allocate, calls))
    manager.preview_meal(meal_id)
    assert calls, "la simulation doit passer par domain.stock.allocate"
```

- [x] **Step 2: Lancer, vérifier l'échec** — `./scripts/test.sh tests/test_meal_preview.py -q`

- [x] **Step 3: Écrire `preview_meal`**

- [x] **Step 4: Vert** — `./scripts/test.sh tests/test_meal_preview.py -q`

- [x] **Step 5: Commit**
```bash
git add custom_components/home_stock/application.py tests/test_meal_preview.py
git commit -m "feat: simulate a meal without writing, on the very same FIFO"
```

---

## Task 13: Valider un repas — cuisiner, puis manger, en une transaction

**C'est le cœur du lot.** Rien de ce qui suit ne se coupe en deux.

**Files:**
- Modify: `custom_components/home_stock/application.py`
- Test: `tests/test_meal_validate.py` (créer), `tests/test_leftovers.py` (créer)

**Interfaces:**

```python
class StockManager:
    def validate_meal(self, meal_id: int, *, portions_eaten: float,
                      servings: float | None = None,
                      parts_total: int | None = None, parts_mine: int | None = None,
                      skip_ingredient_ids: Collection[int] = (),
                      dry_run: bool = True,
                      occurred_at: str | None = None) -> dict
        # dry_run=True  -> le dict de preview_meal, rien d'écrit
        # dry_run=False -> {**preview, "movement_ids": [...], "batch_id": 42}

    # extraits, PAS de nouvelles capacités : le corps de `consume` / `add_stock`
    # sorti de son `with self.db.write()`, pour que la validation puisse les
    # appeler DANS sa propre transaction.
    def _consume_within(self, conn, *, product_id, quantity, reason, moment,
                        base_unit=None, parts_total=None, parts_mine=None,
                        ref_type=None, ref_id=None, key=None) -> list[int]
    def _consume_batch_within(self, conn, batch_id, *, quantity, reason, moment,
                              parts_total=None, parts_mine=None,
                              ref_type=None, ref_id=None, key=None) -> int
    def _add_stock_within(self, conn, *, article_id, quantity, location_id,
                          moment, best_before=None, price_per_base_unit=None,
                          reason=REASON_PURCHASE, nutrition=None,
                          ref_type=None, ref_id=None, key=None) -> int
    def _ensure_leftover_product(self, conn, recipe: Mapping) -> tuple[int, int]
```

**⚠️ Le refactor obligatoire, et pourquoi il l'est.** `add_stock`, `consume` et `consume_batch` ouvrent chacun leur `with self.db.write()`. `Database._lock` est un `threading.Lock` **non réentrant** : appeler l'un depuis l'autre **bloque le processus définitivement**, sans exception ni message. La validation doit écrire trois choses dans **une** transaction ; il faut donc extraire le corps de chacune en une méthode qui **reçoit `conn`** et n'ouvre rien. Les trois méthodes publiques deviennent des enveloppes de quatre lignes : ouvrir, vérifier l'idempotence, déléguer. **Aucun changement de comportement** — c'est ce que prouve la suite existante, qui doit rester verte sans une seule retouche.

**La séquence, dans cet ordre exact :**

**1. Les ingrédients sortent, motif `cooked`.** Un décrément par ligne planifiée, donc allocation FIFO selon la règle du lot 0 § 7.1 (lot entamé d'abord, puis DLC la plus proche, puis entrée la plus ancienne), donc **un mouvement par lot traversé**, chacun figeant son prix, ses kcal et ses huit macros. `ref_type = 'meal'`, `ref_id = meal.id`. Clé : `meal:<id>:ing:<recipe_ingredient_id>`, puis `#1`, `#2` pour les lots suivants — la convention de `consume`.

**2. Le plat entre, motif `cooked`.** Un lot sur le produit de restes de la recette : quantité = parts produites, `best_before` = jour + `leftover_shelf_life_days`, emplacement = le premier `location.kind = 'fridge'`, prix et neuf nutriments calculés par `per_part_values` **depuis les mouvements qu'on vient d'écrire**. Clé : `meal:<id>:dish`.

**3. La part du soir sort, motif `consumption`.** Un décrément sur le lot qu'on vient de créer, quantité = `portions_eaten`, avec `parts_total` / `parts_mine`. Clé : `meal:<id>:eaten`. Quand `portions_eaten` égale le nombre de parts, la poussière flottante (lot 0 § 7.2) referme le lot **dans la même transaction** — il n'y a pas de reste, et rien de spécial n'a été écrit pour ça.

**Décision de plan — la clé du panneau ne remplace pas les clés déterministes.** `home_stock/meal/validate` porte une `idempotency_key` (la file hors-ligne la pose sur tout). Elle est acceptée et validée, mais **le garde-fou est la famille `meal:<id>:…`**, dérivée de l'identifiant du repas : deux clés de panneau différentes pour le même repas ne doivent pas décrémenter deux fois. Un rejeu relit les mouvements par préfixe de clé et rend les mêmes `movement_ids`.

- [x] **Step 1: Écrire les tests du refactor d'abord**

Ils ne portent pas sur du code neuf : ils épinglent le comportement **avant** de déplacer quoi que ce soit.

```python
def test_consume_and_add_stock_still_behave_identically_after_the_extraction(manager):
    """Filet de sécurité du refactor. Écrit AVANT de toucher les trois méthodes."""

def test_two_writes_in_one_transaction_do_not_deadlock(manager):
    """Preuve directe : Database._lock n'est pas réentrant. Sans les méthodes
    `_within`, ce test ne finirait jamais."""
    with manager.db.write() as conn:
        manager._add_stock_within(conn, article_id=1, quantity=3.0, location_id=1,
                                  moment="2026-08-21T20:00:00")
        manager._consume_within(conn, product_id=1, quantity=1.0,
                                reason="cooked", moment="2026-08-21T20:00:00")
```

- [x] **Step 2: Écrire les tests de validation**

```python
# --- la simulation par défaut ----------------------------------------------
def test_dry_run_is_the_default_and_writes_nothing(manager):
    before = _snapshot(manager)
    manager.validate_meal(meal_id, portions_eaten=1)
    assert _snapshot(manager) == before

# --- les trois écritures ----------------------------------------------------
def test_the_ingredients_leave_in_fifo_with_one_movement_per_batch(manager): ...
def test_every_ingredient_movement_carries_ref_type_meal_and_ref_id(manager):
    """Les deux colonnes que le lot 0 a posées « pour les lots ultérieurs »
    trouvent ici leur premier usage."""
def test_the_dish_enters_with_the_right_number_of_parts(manager): ...
def test_the_dish_best_before_is_the_day_plus_three(manager): ...
def test_the_dish_lands_in_the_first_fridge_location(manager): ...
def test_the_eaten_part_leaves_as_consumption_with_its_parts(manager): ...
def test_eating_every_part_closes_the_batch_in_the_same_transaction(manager):
    """La poussière flottante du lot 0 § 7.2 : rien de spécial n'a été écrit."""

# --- ce que `cooked` ne fait pas -------------------------------------------
def test_cooked_never_reaches_kcal_today(manager): ...
def test_cooked_never_reaches_cost_today_nor_cost_waste_total(manager): ...
def test_cooking_leaves_the_total_stock_value_unchanged(manager):
    """La valeur quitte les ingrédients et entre dans le plat. C'est la
    définition même de `cooked` : un changement de forme."""
    before = manager.summary(...)["stock_value"]
    manager.validate_meal(meal_id, portions_eaten=0, dry_run=False)
    assert manager.summary(...)["stock_value"] == pytest.approx(before)
def test_only_the_eaten_part_moves_kcal_today(manager): ...
def test_a_dish_left_in_the_fridge_keeps_its_value_in_the_stock(manager): ...

# --- les nutriments, valeur par valeur -------------------------------------
def test_one_null_nutrient_on_one_ingredient_nulls_that_one_and_not_the_eight(manager): ...
def test_the_unvalued_counter_sees_the_resulting_unpriced_movement(manager): ...

# --- ce qui manque ----------------------------------------------------------
def test_an_unmatched_line_is_listed_in_skipped_ingredient_ids(manager): ...
def test_skipped_ingredient_ids_is_provenance_and_never_arithmetic(manager):
    """Rien ne le relit pour calculer quoi que ce soit."""
def test_a_short_line_without_arbitration_refuses_the_whole_validation(manager): ...
def test_a_short_line_accepted_reduced_goes_through(manager): ...
def test_an_ignored_line_decrements_nothing_and_is_not_reported(manager): ...

# --- l'idempotence et l'atomicité ------------------------------------------
def test_replaying_the_validation_returns_the_same_movement_ids(manager): ...
def test_replaying_with_a_different_panel_key_still_writes_nothing_new(manager):
    """Le garde-fou est `meal:<id>:…`, pas la clé du panneau."""
def test_validating_a_done_meal_is_refused_with_a_french_message(manager): ...
def test_a_failure_halfway_leaves_no_movement_and_no_batch(manager, monkeypatch):
    """Transaction unique : jamais un demi-repas. On fait échouer l'écriture du
    plat et on vérifie que les sorties d'ingrédients ont été annulées elles
    aussi."""
    _snapshot_before = _snapshot(manager)
    monkeypatch.setattr(repo, "insert_batch", _boom)
    with pytest.raises(RuntimeError):
        manager.validate_meal(meal_id, portions_eaten=1, dry_run=False)
    assert _snapshot(manager) == _snapshot_before

# --- les bornes, aux deux bouts --------------------------------------------
@pytest.mark.parametrize("portions", [0, -1, float("nan"), float("inf")])
def test_portions_eaten_must_be_finite_and_positive(manager, portions): ...
def test_portions_eaten_above_the_parts_produced_is_refused(manager):
    """On ne mange pas quatre parts d'un plat qui en fait trois."""
def test_parts_mine_above_parts_total_is_refused(manager): ...
def test_parts_total_above_twenty_four_is_refused(manager): ...

# --- la journée alimentaire -------------------------------------------------
def test_a_dinner_validated_at_one_in_the_morning_lands_on_the_evening(manager):
    """Le repas et le mouvement qu'il produit tombent dans la MÊME journée
    alimentaire — sinon le journal du panneau ne retrouve pas le repas qui a
    fait monter sa barre."""
```

- [x] **Step 3: Écrire les tests des restes** dans `tests/test_leftovers.py`

```python
def test_the_leftover_product_is_created_once_for_two_cookings(manager):
    """`recipe.leftover_product_id` retient le lien : une seconde cuisson
    réutilise le même produit et le même article générique."""
def test_the_leftover_product_is_a_piece_product_in_the_cooked_category(manager): ...
def test_a_generic_article_accompanies_it(manager):
    """Un lot pointe toujours vers un article : aucun cas particulier dans le
    code de sortie, de kcal ou de coût."""
def test_a_name_collision_is_suffixed_with_the_recipe_id(manager):
    """product.name est UNIQUE depuis m001."""
def test_the_values_land_on_the_batch_not_on_the_shared_article(manager):
    """Deux cuissons de la même recette n'ont ni les mêmes nutriments ni le même
    coût ; écrire sur l'article écraserait la cuisson précédente pendant que ses
    parts attendent encore au frigo."""
    _cook(manager, cream="entière"); _cook(manager, cream="demi-écrémée")
    kcals = [r["kcal_per_base_unit"] for r in _batches(manager)]
    assert kcals[0] != kcals[1]
    assert _article(manager)["kcal_per_base_unit"] is None
def test_the_default_shelf_life_is_three_days(manager): ...
def test_a_recipe_can_override_the_shelf_life(manager): ...
def test_a_leftover_batch_shows_up_in_expiry_candidates(manager):
    """Effet de bord voulu : le blueprint DLC du lot 2 annoncera « le gratin de
    dimanche périme demain » sans une ligne de code de plus."""
def test_a_leftover_batch_shows_up_in_the_expirations_todo_and_binary_sensor(hass, setup_entry): ...
def test_a_leftover_product_has_no_min_quantity_and_never_reports_a_shortage(manager): ...
def test_a_leftover_product_falls_back_to_the_other_aisle(manager):
    """Pas de rayon : « Autre » si quelque chose les mettait un jour sur une
    liste de courses — ce que le lot 4 devra explicitement empêcher."""
```

- [x] **Step 4: Lancer, vérifier l'échec**

Run: `./scripts/test.sh tests/test_meal_validate.py tests/test_leftovers.py -q`
Expected: FAIL

- [x] **Step 5: Extraire les trois `_within`, puis écrire `validate_meal`**

Faire le refactor **en premier** et relancer la suite entière avant d'écrire une seule ligne de `validate_meal` : c'est le seul moment où l'on saura qu'une régression vient du déplacement et non du code neuf.

Run intermédiaire : `./scripts/test.sh -q` → PASS obligatoire avant de continuer.

- [x] **Step 6: Vert**

```bash
./scripts/test.sh tests/test_meal_validate.py tests/test_leftovers.py -q
./scripts/test.sh -q
```
Expected: PASS des deux.

- [x] **Step 7: Commit**
```bash
git add custom_components/home_stock/application.py tests/test_meal_validate.py tests/test_leftovers.py
git commit -m "feat: validate a meal — cook then eat, in one transaction"
```

---

## Task 14: L'entité `calendar`

**Files:**
- Create: `custom_components/home_stock/calendar.py`
- Modify: `custom_components/home_stock/__init__.py` (`Platform.CALENDAR`), `translations/{fr,en}.json`
- Test: `tests/test_calendar.py` (créer)

**Interfaces:**
- Consomme : `manager.list_meals`, `plan_meal`, `move_meal`, `cancel_meal`, `repo.list_slots` ; `matching.candidates` / `preselect` pour apparier un `summary`.
- Produit : `calendar.home_stock_meals`, clé de traduction `meals`, `_attr_supported_features = CREATE_EVENT | DELETE_EVENT | UPDATE_EVENT`.

**Ce que l'entité expose :**
- `async_get_events(hass, start, end)` → un `CalendarEvent` par repas. `summary` : nom de la recette, du produit, ou la note. `start` : le jour à `meal_slot.default_time`, **dans le fuseau de Home Assistant**. `end` : `+ duration_minutes`. `uid` : `meal.uid`. `description` : la liste des ingrédients et ce qui manque.
- `event` → le prochain repas non validé, ou celui en cours.
- **Pas de `RRULE`.** Un menu de la semaine n'est pas un événement récurrent, et l'annoncer récurrent promettrait un comportement qu'on ne veut pas écrire.

**Poser un repas depuis la carte native.** `async_create_event` reçoit un `summary` et un début. Le créneau se déduit de l'heure : celui dont `default_time` est le plus proche. Le `summary` passe à `matching.candidates()` contre les **recettes** ; au-delà du seuil de présélection, le repas pointe la recette, sinon c'est un repas `note`. Un repas posé depuis Lovelace est donc un repas complet et décrémentable, pas une chaîne de caractères sans suite.

- [x] **Step 1: Écrire les tests**

```python
async def test_the_calendar_entity_exists_with_a_french_name(hass, setup_entry): ...
async def test_get_events_returns_one_event_per_meal(hass, setup_entry): ...
async def test_an_event_starts_at_the_slot_default_time_in_the_local_zone(hass, setup_entry):
    await dt_util.async_set_time_zone(hass, "Europe/Paris")
    # dinner = 20:00 locales = 18:00 UTC en été
async def test_an_event_ends_after_the_slot_duration(hass, setup_entry): ...
async def test_the_uid_is_the_meal_uid(hass, setup_entry): ...
async def test_the_description_lists_the_ingredients_and_what_is_missing(hass, setup_entry): ...
async def test_a_note_meal_has_the_note_as_summary(hass, setup_entry): ...
async def test_the_event_property_is_the_next_unvalidated_meal(hass, setup_entry): ...
async def test_a_done_meal_is_not_the_next_one(hass, setup_entry): ...
async def test_the_entity_supports_create_update_and_delete(hass, setup_entry): ...
async def test_no_rrule_is_ever_produced(hass, setup_entry): ...

async def test_creating_an_event_matches_a_recipe_by_summary(hass, setup_entry): ...
async def test_creating_an_event_whose_summary_matches_nothing_makes_a_note_meal(hass, setup_entry):
    """Pas un échec : « Restaurant » est un repas parfaitement légitime."""
async def test_the_slot_is_the_nearest_default_time(hass, setup_entry):
    for hour, slot in ((8, "breakfast"), (13, "lunch"), (16, "snack"), (21, "dinner")):
        ...
async def test_an_event_created_at_one_in_the_morning_lands_on_the_previous_food_day(hass, setup_entry): ...
async def test_updating_an_event_moves_the_meal(hass, setup_entry): ...
async def test_updating_a_done_meal_is_refused(hass, setup_entry):
    with pytest.raises(HomeAssistantError):
        ...
async def test_deleting_a_planned_meal_removes_it(hass, setup_entry): ...
async def test_deleting_a_done_meal_marks_it_skipped_and_keeps_its_movements(hass, setup_entry):
    """La suppression détruirait la référence `movement.ref_type = 'meal'` que
    le journal porte déjà et qui, elle, est en ajout seul."""
async def test_deleting_an_unknown_uid_raises_rather_than_passing_silently(hass, setup_entry): ...
```

- [x] **Step 2: Lancer, vérifier l'échec** — `./scripts/test.sh tests/test_calendar.py -q`

- [x] **Step 3: Écrire `calendar.py`**

Sous-classer `HomeStockEntity, CalendarEntity`, `super().__init__(coordinator, "meals", ENTITY_ID_FORMAT)`. Toutes les lectures SQLite passent par `hass.async_add_executor_job`. Ajouter `Platform.CALENDAR` à `PLATFORMS` **en fin de liste** et la clé `entity.calendar.meals.name` (« Repas ») dans les deux fichiers de traduction.

- [x] **Step 4: Vert** — `./scripts/test.sh tests/test_calendar.py -q && ./scripts/test.sh -q`

- [x] **Step 5: Commit**
```bash
git add custom_components/home_stock/calendar.py custom_components/home_stock/__init__.py custom_components/home_stock/translations tests/test_calendar.py
git commit -m "feat: calendar.home_stock_meals, creatable, movable and deletable"
```

---

## Task 15: Les trois capteurs, et les restes dans les alertes existantes

**Files:**
- Modify: `custom_components/home_stock/coordinator.py`, `custom_components/home_stock/sensor.py`, `translations/{fr,en}.json`
- Test: `tests/test_entities.py`, `tests/test_meal_sensors.py` (créer)

**Interfaces:**
- `coordinator.data["meals"]` = `manager.meal_summary(tz=…, now=…)` (tâche 11), lu dans **le même** travail d'exécuteur que `summary()` — deux allers-retours vers l'exécuteur pour un rafraîchissement qui a lieu toutes les 15 minutes seraient deux fois trop.

| Entité | État | Attributs |
|---|---|---|
| `sensor.home_stock_next_meal` | Le nom du prochain repas, `None` s'il n'y en a pas | `day`, `slot`, `recipe_id`, `missing_ingredients` |
| `sensor.home_stock_recipes` | Nombre de recettes actives | `reviewable`, `unmatched_ingredients` |
| `sensor.home_stock_missing_ingredients` | Nombre de produits manquants sur sept jours | `products` (la liste) |

**Décision reprise de la spec, et elle vaut d'être répétée dans le code :** `missing_ingredients` est **un compteur, pas une liste cochable**. Une entité `todo` serait déjà la liste de courses, qui est le lot 4 — y cocher signifierait « acheté », donc une session, un prix, un rangement. **Aucune entité `event` pour la validation d'un repas** non plus : une validation est un geste humain qui vient d'avoir lieu sur l'écran, pas un fait que rien n'observe.

- [x] **Step 1: Écrire les tests**

```python
async def test_the_three_sensors_exist_with_french_names(hass, setup_entry): ...
async def test_next_meal_names_the_next_planned_meal(hass, setup_entry): ...
async def test_next_meal_is_unknown_without_any_meal(hass, setup_entry):
    """Sans repas, l'état est vide — jamais « 0 », qui se lirait comme un repas
    nommé zéro."""
async def test_next_meal_carries_the_number_of_missing_ingredients(hass, setup_entry): ...
async def test_next_meal_skips_a_done_meal(hass, setup_entry): ...
async def test_recipes_counts_only_the_active_ones(hass, setup_entry): ...
async def test_recipes_attributes_count_reviewable_and_unmatched(hass, setup_entry): ...
async def test_missing_ingredients_counts_the_seven_day_window(hass, setup_entry): ...
async def test_missing_ingredients_lists_the_products_in_its_attribute(hass, setup_entry): ...
async def test_missing_ingredients_ignores_unmatched_and_ignored_lines(hass, setup_entry): ...
async def test_the_sensors_survive_a_refresh_with_an_empty_database(hass, setup_entry): ...
async def test_no_event_entity_was_created_for_meal_validation(hass, setup_entry):
    """Décision de la spec § 15.3, épinglée : une automation qui veut réagir a
    déjà `calendar.home_stock_meals` et `sensor.home_stock_next_meal`."""
    assert hass.states.get("event.home_stock_meal") is None

# --- les restes entrent dans ce qui existait déjà --------------------------
async def test_a_leftover_batch_turns_on_the_expirations_binary_sensor(hass, setup_entry): ...
async def test_a_leftover_batch_appears_in_the_expirations_todo(hass, setup_entry): ...
async def test_a_leftover_batch_fires_the_expiration_event(hass, setup_entry):
    """Zéro ligne de code pour ça : c'est le principal intérêt de traiter un
    reste comme n'importe quel autre lot."""
```

- [x] **Step 2 → 4: Échec, écriture, vert**

```bash
./scripts/test.sh tests/test_meal_sensors.py tests/test_entities.py -q    # FAIL puis PASS
./scripts/test.sh -q
```

- [x] **Step 5: Commit**
```bash
git add custom_components/home_stock/coordinator.py custom_components/home_stock/sensor.py custom_components/home_stock/translations tests/test_meal_sensors.py tests/test_entities.py
git commit -m "feat: next meal, recipe and missing-ingredient sensors"
```

---

## Task 16: Les quatorze commandes websocket

**Files:**
- Create: `custom_components/home_stock/websocket_recipes.py`
- Modify: `custom_components/home_stock/websocket_api.py` (deux lignes)
- Test: `tests/test_websocket_recipes.py`, `tests/test_websocket_meals.py` (créer), `tests/test_offline_queue_contract.py`

**Décision de plan — un module séparé, et pourquoi.** La spec § 5 annonce « `websocket_api.py` : quatorze commandes de plus ». `websocket_api.py` fait déjà 1 240 lignes, et le lot 5 y ajoutera onze commandes **en parallèle, dans un autre worktree**. Écrire les quatorze du lot 3 dans un module neuf enregistré par `async_register_websocket` laisse la surface exposée **strictement identique** (mêmes types de message, mêmes schémas, mêmes helpers importés depuis `websocket_api`) et réduit le conflit de fusion à deux lignes. C'est une décision de disposition de fichiers, pas de contrat.

**Interfaces:**

| Commande | Entrée | Sortie |
|---|---|---|
| `home_stock/recipes/list` | `search?`, `only_reviewable?` | Recettes + compte d'ingrédients non appariés |
| `home_stock/recipe/get` | `recipe_id` | Recette, étapes, puces, lignes résolues et candidats |
| `home_stock/recipe/create` | Recette complète, `idempotency_key?` | `{recipe_id}` |
| `home_stock/recipe/update` | `recipe_id`, `fields`, `idempotency_key?` | — |
| `home_stock/recipe/delete` | `recipe_id`, `idempotency_key?` | Refusée si un repas `done` la référence |
| `home_stock/recipe/ingredient/match` | `ingredient_id`, `product_id?`, `state`, `create_alias?`, `idempotency_key?` | La ligne mise à jour |
| `home_stock/recipe/search_external` | `query?`, `ingredient?` | Fiches de la source. **N'écrit rien** |
| `home_stock/recipe/import_external` | `source_ref`, `idempotency_key?` | `{recipe_id, adapted}` |
| `home_stock/meals/list` | `start`, `end` | Repas, avec leurs manques |
| `home_stock/meal/plan` | `day`, `slot_key`, `recipe_id`\|`product_id`+`amount`\|`note`, `servings?`, `idempotency_key?` | `{meal_id, uid}` |
| `home_stock/meal/move` | `meal_id`, `day`, `slot_key`, `position?`, `idempotency_key?` | — |
| `home_stock/meal/cancel` | `meal_id`, `idempotency_key?` | — |
| `home_stock/meal/preview` | `meal_id`, `servings?`, `skip_ingredient_ids?` | Le plan. **N'écrit rien** |
| `home_stock/meal/validate` | `meal_id`, `portions_eaten`, `parts_total?`, `parts_mine?`, `skip_ingredient_ids?`, `idempotency_key` | `{movement_ids, batch_id}` |

**Toute commande qui écrit accepte une `idempotency_key`** — la file hors-ligne la pose sur **tout** ce qui passe par elle, sans notion de « cette commande n'en prend pas ». C'est ce qu'a coûté l'incident du lot 1 : trois commandes à schéma strict, refusées au premier rejeu hors ligne.

- [x] **Step 1: Écrire les tests**

Deux fichiers, motif de `tests/test_websocket_consume.py` (`setup_entry`, `hass_ws_client`, `send_json_auto_id`).

```python
# tests/test_websocket_recipes.py
async def test_recipes_list_returns_the_unmatched_count(...): ...
async def test_recipes_list_filters_on_search_and_on_review(...): ...
async def test_recipe_get_returns_steps_bullets_and_candidates(...): ...
async def test_recipe_get_on_an_unknown_id_answers_not_found(...): ...
async def test_recipe_create_then_update_then_delete(...): ...
async def test_recipe_delete_is_refused_when_a_done_meal_references_it(...): ...
async def test_ingredient_match_confirms_and_creates_the_alias(...): ...
async def test_ingredient_match_refuses_auto_without_a_product(...): ...
async def test_search_external_writes_absolutely_nothing(hass, setup_entry, ...):
    before = _snapshot(...)
    ... ; assert _snapshot(...) == before
async def test_search_external_with_the_source_down_answers_empty_not_an_error(...):
    """Recherche vide et message explicite. Aucune recette existante n'est
    affectée, et rien ne retarde un dîner."""
async def test_import_external_reports_whether_the_adaptation_happened(...): ...
async def test_import_external_without_an_agent_still_creates_the_recipe(...): ...

# tests/test_websocket_meals.py
async def test_meal_plan_returns_the_meal_id_and_the_uid(...): ...
@pytest.mark.parametrize("servings", [0, -1, "deux"])
async def test_meal_plan_refuses_a_bad_servings(..., servings): ...
async def test_meal_plan_refuses_an_unknown_slot(...): ...
async def test_meal_plan_refuses_a_malformed_day(...):
    for day in ("2026-8-1", "20260801", "hier"): ...
async def test_meals_list_bounds_are_validated_as_iso_dates(...): ...
async def test_meal_move_refuses_a_done_meal(...): ...
async def test_meal_cancel_deletes_a_planned_and_skips_a_done(...): ...
async def test_meal_preview_writes_nothing(...): ...
async def test_meal_validate_writes_the_three_movements_and_returns_them(...): ...
async def test_meal_validate_is_idempotent_on_replay(...): ...
async def test_meal_validate_refuses_more_parts_eaten_than_served(...): ...
async def test_meal_validate_refuses_a_meal_already_done(...): ...
async def test_every_write_command_accepts_an_idempotency_key(...): ...
async def test_an_insufficient_stock_answers_a_french_message(...): ...
```

Et dans `tests/test_offline_queue_contract.py`, **les trois gestes** :
1. `EXPECTED_QUEUED_COMMAND_TYPES` gagne les commandes réellement mises en file par le front (tâches 18 à 21) : `home_stock/recipe/ingredient/match`, `home_stock/recipe/update`, `home_stock/meal/plan`, `home_stock/meal/move`, `home_stock/meal/cancel`, `home_stock/meal/validate`.
2. Un bloc `_send(...)` + `tested.add(...)` par commande, dans un ordre qui respecte le cycle de vie (créer la recette et le repas avant de le valider).
3. L'assertion finale `tested == discovered == EXPECTED_QUEUED_COMMAND_TYPES` reste vraie.

⚠️ Le scanner ne voit que les **littéraux** passés à `.ajouter(` / `.ecrire(`. Une commande construite par concaténation serait invisible et le contrat serait vert à tort.

- [x] **Step 2 → 4: Échec, écriture, vert**

```bash
./scripts/test.sh tests/test_websocket_recipes.py tests/test_websocket_meals.py -q  # FAIL puis PASS
./scripts/test.sh tests/test_offline_queue_contract.py -q
```

Note : le contrat ne passera **complètement** qu'après la tâche 21 (le front doit avoir écrit ses littéraux). Jusque-là, écrire les entrées de `EXPECTED_QUEUED_COMMAND_TYPES` **en même temps** que les littéraux front, tâche par tâche, plutôt que toutes ici — sinon le premier test du contrat (`… finds exactly the commands …`) tombe et reste rouge pendant quatre tâches.

- [x] **Step 5: Commit**
```bash
git add custom_components/home_stock/websocket_recipes.py custom_components/home_stock/websocket_api.py tests/test_websocket_recipes.py tests/test_websocket_meals.py
git commit -m "feat: fourteen websocket commands for recipes, meals and validation"
```

---

## Task 17: Les cinq services, et les messages français

**Files:**
- Modify: `custom_components/home_stock/services.py`, `services.yaml`, `messages.py`
- Test: `tests/test_services_meals.py` (créer), `tests/test_messages.py`

**Interfaces:**

| Service | Réponse | Rôle |
|---|---|---|
| `home_stock.plan_meal` | — | Poser un repas, en YAML ou en vocal |
| `home_stock.validate_meal` | `OPTIONAL` | **`dry_run: true` par défaut** : rend le plan sans rien écrire |
| `home_stock.import_recipe` | `OPTIONAL` | Une référence de source, ou une recherche |
| `home_stock.adapt_recipe` | — | Relance l'adaptation d'une recette importée sans agent |
| `home_stock.query_meals` | `ONLY` | Ce qui est prévu sur une plage. Le pendant de `query_stock` |

**La règle qui gouverne cette tâche :** aucune des deux surfaces n'a le droit d'être la plus faible. Ce que le websocket refuse à la tâche 16, le service doit le refuser ici — un appel de service part d'une automation ou du vocal, et il est tout aussi capable d'écrire quatre parts sur trois dans un journal en ajout seul.

`validate_meal` en simulation par défaut suit `import_grocy_catalog`, qui simule par défaut depuis le lot 0 : un service qui décrémente un stock ne doit pas le faire au premier appel exploratoire depuis les Outils de développement.

`query_meals` est un service à réponse et non une entité : c'est lui qui répondra à « qu'est-ce qu'on mange ce soir ? » au lot 6, sans créer une entité par repas.

**Nouveaux motifs dans `messages.py`** (à ajouter en fin de `DOMAIN_ERROR_PATTERNS`, jamais au milieu — l'ordre est significatif, le premier motif qui matche gagne) :

| Motif (regex, anglais stable) | Code | Phrase française |
|---|---|---|
| `^no recipe (\d+)$` | `not_found` | « Recette introuvable. » |
| `^no meal (\d+)$` | `not_found` | « Repas introuvable. » |
| `^unknown slot '(.+)'$` | `invalid_value` | « Créneau inconnu : … » |
| `^meal (\d+) is already done$` | `invalid_value` | « Ce repas a déjà été validé. » |
| `^meal (\d+) cannot be moved once done$` | `invalid_value` | « Un repas validé ne se déplace pas : ses mouvements portent une date figée. » |
| `^recipe (\d+) is referenced by a validated meal$` | `invalid_value` | « Cette recette a servi à un repas validé : désactivez-la plutôt que de la supprimer. » |
| `^ingredient (\d+) needs a product for state '(.+)'$` | `invalid_field` | « Choisissez un produit avant de confirmer cet ingrédient. » |
| `^(\d+) ingredient\(s\) short of stock$` | `insufficient_stock` | « Il manque du stock pour … ingrédient(s) : ajustez ou retirez ces lignes. » |
| `^portions_eaten must not exceed the (.+) parts produced$` | `invalid_value` | « On ne mange pas plus de parts que le plat n'en fait. » |
| `^servings must be positive, got (.+)$` | `invalid_value` | « Le nombre de parts doit être supérieur à zéro. » |

Un message non reconnu retombe sur la phrase générique plutôt que d'exposer un `repr` Python à quelqu'un qui a les mains dans la farine.

- [x] **Step 1: Écrire les tests**

```python
# tests/test_services_meals.py
async def test_plan_meal_service_creates_the_meal(hass, ...): ...
async def test_validate_meal_is_a_dry_run_by_default_and_writes_nothing(hass, ...):
    before = _snapshot(...)
    answer = await hass.services.async_call(DOMAIN, "validate_meal",
        {"meal_id": 1, "portions_eaten": 1}, blocking=True, return_response=True)
    assert _snapshot(...) == before
    assert answer["lines"]
async def test_validate_meal_writes_when_dry_run_is_false(hass, ...): ...
async def test_import_recipe_by_source_ref(hass, ...): ...
async def test_import_recipe_by_search_takes_the_first_hit(hass, ...): ...
async def test_import_recipe_with_the_source_down_reports_it_without_raising(hass, ...): ...
async def test_adapt_recipe_picks_up_a_recipe_imported_without_an_agent(hass, ...): ...
async def test_query_meals_returns_the_range(hass, ...): ...
async def test_query_meals_is_response_only_and_writes_nothing(hass, ...): ...

# la parité, surface par surface — le cœur de la tâche
@pytest.mark.parametrize("payload", [
    {"portions_eaten": 0}, {"portions_eaten": -1},
    {"portions_eaten": 1, "parts_total": 2, "parts_mine": 3},
    {"portions_eaten": 1, "parts_total": 25, "parts_mine": 1},
    {"portions_eaten": 1, "parts_total": 1.5, "parts_mine": 1},
])
async def test_the_service_refuses_exactly_what_the_websocket_refuses(hass, payload): ...

@pytest.mark.parametrize("payload", [
    {"day": "2026-8-1"}, {"slot_key": "brunch"}, {"servings": 0},
    {"recipe_id": 1, "note": "x"},        # deux natures à la fois
])
async def test_plan_meal_service_refuses_exactly_what_the_websocket_refuses(hass, payload): ...

async def test_every_new_service_has_a_french_name_and_description(hass, ...):
    """`async_get_all_descriptions`, comme le lot 0 le fait déjà pour les neuf
    services existants — sélecteurs compris."""

# tests/test_messages.py
@pytest.mark.parametrize("text, code", [...])
def test_the_new_domain_errors_become_french(text, code): ...
def test_an_unrecognised_error_falls_back_to_the_generic_sentence(): ...
def test_no_new_pattern_shadows_an_older_one():
    """L'ordre compte : le premier motif qui matche gagne. Rejoue tous les
    messages déjà couverts et vérifie que leur code n'a pas changé."""
```

- [x] **Step 2 → 4: Échec, écriture, vert**

```bash
./scripts/test.sh tests/test_services_meals.py tests/test_messages.py -q   # FAIL puis PASS
./scripts/test.sh -q
```

- [x] **Step 5: Commit**
```bash
git add custom_components/home_stock/services.py custom_components/home_stock/services.yaml custom_components/home_stock/messages.py tests/test_services_meals.py tests/test_messages.py
git commit -m "feat: five meal services, no weaker than the websocket surface"
```

---

## Task 18: Les fractions, le minuteur, et l'écran Recettes

**Files:**
- Modify: `frontend/src/nombres.ts`
- Create: `frontend/src/minuteur.ts`, `frontend/src/ecrans/recettes.ts`
- Test: `frontend/tests/nombres.test.ts` (créer), `frontend/tests/minuteur.test.ts` (créer), `frontend/tests/recettes.test.ts` (créer)

**Interfaces:**

```ts
// nombres.ts — s'ajoute à analyserNombre / formaterNombre, qui ne bougent pas
export function formaterFraction(valeur: number): string;
export function formaterQuantiteRecette(
  quantite: number | null, unite: 'g' | 'ml' | 'piece',
  mesure: string | null, conditionnement: string | null): string;

// minuteur.ts — pur, comme dlc.ts et portion.ts
export type EtatMinuteur = { restant: number; enMarche: boolean; termine: boolean };
export function demarrer(secondes: number, maintenant: number): EtatMinuteur;
export function avancer(etat: EtatMinuteur, ecoule: number): EtatMinuteur;
export function remettreAZero(secondes: number): EtatMinuteur;
export function formaterDuree(secondes: number): string;   // « 12:30 », « 1:05:00 »

// ecrans/recettes.ts
@customElement('home-stock-recettes') export class EcranRecettes extends LitElement
// propriétés : .connexion, .file, .enAttente ; événement : `recette-ouverte` (detail: {recipe_id})
```

**Décision de plan — les demis se lisent, ils ne se stockent pas.** `amount` vaut `0.5` en base ; le rendu écrit « ½ » pour 0,5, « ¼ » pour 0,25, « ⅓ » pour ~0,333 et « ¾ » pour 0,75, **et seulement pour un produit suivi à la pièce**. Une demi-cuillère à soupe s'écrit « 0,5 cuillère à soupe » : personne ne dit « ½ cuillère à soupe d'huile » en cuisine, et une fraction sur une masse (« ½ g ») serait ridicule. Un seul nombre en base, plusieurs façons de le lire.

**Décision de plan — le minuteur est un module pur, décompté dans le panneau.** Aucune entité `timer` de Home Assistant n'est créée : une recette de quatre étapes en produirait quatre, et elles lui survivraient. Le module ne touche ni `setInterval` ni `Date.now()` — il reçoit le temps, ce qui rend le décompte testable sans horloge factice globale.

- [x] **Step 1: Écrire les tests purs**

```ts
// nombres.test.ts
it.each([[0.5, '½'], [0.25, '¼'], [0.75, '¾'], [1/3, '⅓'], [2/3, '⅔']])(
  'écrit %s en fraction', (v, attendu) => expect(formaterFraction(v)).toBe(attendu));
it('laisse un entier tel quel', () => expect(formaterFraction(2)).toBe('2'));
it('écrit 1,5 en « 1 ½ »', () => expect(formaterFraction(1.5)).toBe('1 ½'));
it('replie sur la virgule quand aucune fraction ne colle',
   () => expect(formaterFraction(0.4)).toBe('0,4'));
it('n’écrit jamais « 0 » pour une quantité inconnue',
   () => expect(formaterQuantiteRecette(null, 'g', null, null)).toBe(''));
it('n’utilise les fractions que pour les pièces', () => {
  expect(formaterQuantiteRecette(0.5, 'piece', null, 'oignon')).toBe('½ oignon');
  expect(formaterQuantiteRecette(0.5, 'g', null, null)).toBe('0,5 g');
});
it('accorde le pluriel de la mesure',
   () => expect(formaterQuantiteRecette(2, 'ml', 'cuillère à soupe', null))
     .toBe('2 cuillères à soupe'));

// minuteur.test.ts
it('décompte sans jamais passer sous zéro', ...);
it('se déclare terminé exactement à zéro', ...);
it('remis à zéro, il repart de la durée d’origine et n’est pas en marche', ...);
it.each([[90, '1:30'], [3661, '1:01:01'], [0, '0:00']])(
  'formate %s secondes en %s', ...);
it('ne dépend d’aucune horloge globale', ...);
```

- [x] **Step 2: Écrire les tests de l'écran Recettes**

Motif du dépôt : `monter()` local, `element.connexion = { appeler: vi.fn(...) }`, `await element.updateComplete` **deux fois**, sélecteurs en français.

```ts
it('liste les recettes rendues par le serveur', ...);
it('affiche le badge « à relire » sur une recette needs_review', ...);
it('affiche « n non appariés » quand il en reste', ...);
it('n’affiche aucun badge quand tout est apparié', ...);
it('filtre localement sur la saisie, sans rappeler le serveur', ...);
it('émet « recette-ouverte » avec l’identifiant au clic sur une ligne', ...);
it('appelle recipe/search_external au clic sur « Chercher ailleurs »', ...);
it('affiche un message explicite quand la source ne répond rien', ...);
it('désactive « Chercher ailleurs » hors ligne', async () => {
  // La recherche en ligne est le SEUL bouton désactivé hors ligne : tout le
  // reste de l’écran fonctionne sur ce qui est déjà en base.
});
it('importe une fiche et signale si l’adaptation a eu lieu', ...);
it('affiche « aucune recette » plutôt qu’une liste vide muette', ...);
```

- [x] **Step 3: Lancer, vérifier l'échec**

Run (depuis `frontend/`) : `npm test -- tests/nombres.test.ts tests/minuteur.test.ts tests/recettes.test.ts`
Expected: FAIL

- [x] **Step 4: Écrire les trois modules**

Gabarit : `journal.ts` pour la structure d'écran (types exportés décrivant la réponse serveur, constantes en tête, `connectedCallback` qui charge, méthodes `rendreX()` privées, `static styles` à la fin, `min-height: 48px` sur tout ce qui est cliquable, `@media (max-width: 700px)`).

`recettes.ts` écrit par la file : le littéral `'home_stock/recipe/update'` doit apparaître **dans** un `.ajouter(` ou `.ecrire(`, sinon le contrat Python est aveugle. Ajouter la même chaîne à `EXPECTED_QUEUED_COMMAND_TYPES` **dans cette tâche**.

- [x] **Step 5: Vert**

Run (depuis `frontend/`) : `npm test`
Expected: PASS, et le compte total au-dessus de 247.

Run: `./scripts/test.sh tests/test_offline_queue_contract.py -q` → PASS

- [x] **Step 6: Commit**
```bash
git add frontend/src/nombres.ts frontend/src/minuteur.ts frontend/src/ecrans/recettes.ts frontend/tests tests/test_offline_queue_contract.py
git commit -m "feat: French fractions, a pure timer, and the recipe list screen"
```

---

## Task 19: La vue cuisine

**Files:**
- Create: `frontend/src/ecrans/recette.ts`
- Test: `frontend/tests/recette.test.ts` (créer)

**Interfaces:** `<home-stock-recette>`, propriétés `.connexion`, `.file`, `.recipeId`, `.mealId` (optionnel) ; événements `valider-repas` (detail `{meal_id}`) et `recette-fermee`.

**Ce que l'écran est.** On y est debout, les mains sales, à un mètre de l'écran. Une couverture (image, ligne méta `⏱ / 🔥 / 🍳`, accroche), un bloc **Ingrédients**, puis **une page par étape** : image en tête, titre, liste numérotée de puces, plein écran, gros texte.

**Cinq règles, toutes contraignantes :**
1. **Navigation au bouton uniquement**, précédent / suivant. Aucun geste, aucun appui long — la contrainte des tablettes de la maison vaut ici aussi.
2. **Le bloc Ingrédients s'atteint en un appui depuis n'importe quelle étape et revient où on en était.** Perdre sa place au milieu d'une pâte est la raison pour laquelle on revient au papier.
3. **Les minuteurs sont des boutons dessinés depuis `timer_label` / `timer_seconds`**, décomptés dans le panneau via `minuteur.ts`. Aucune entité Home Assistant.
4. **`navigator.wakeLock`, quand l'API existe**, est demandé à l'ouverture et relâché à la sortie. Son absence n'est jamais une erreur : `jsdom` ne l'a pas, la WebView Fire non plus.
5. **Aucun appel réseau.** La recette vient de `recipe/get`, une fois. Hors ligne, une recette déjà chargée reste lisible — le Wi-Fi de la cuisine n'est pas meilleur que celui d'un rayon de supermarché.

- [ ] **Step 1: Écrire les tests**

```ts
const RECETTE = { recipe: {...}, steps: [ /* 3 étapes, dont une avec 2 puces et un minuteur */ ],
                  ingredients: [ /* dont une ligne sans quantité et une unmatched */ ] };

it('affiche la couverture avant la première étape', ...);
it('affiche la ligne méta durée / ustensiles / accroche', ...);
it('découpe en autant de pages qu’il y a d’étapes', ...);
it('avance et recule au bouton, et jamais au-delà des bornes', async () => {
  // « Précédent » sur la couverture et « Suivant » sur la dernière étape sont
  // absents ou désactivés — jamais un clic qui ne fait rien.
});
it('n’installe aucun écouteur de geste', () => {
  // Preuve directe : aucun addEventListener 'touchstart'/'touchmove'/'pointerdown'
});
it('ouvre le bloc Ingrédients depuis l’étape 2 et y revient à la fermeture', ...);
it('affiche une ligne sans quantité avec son texte d’origine', ...);
it('marque une ligne non appariée comme « à sortir à la main »', ...);
it('n’affiche pas de « 0 » pour une quantité inconnue', ...);
it('dessine un bouton de minuteur depuis timer_label et timer_seconds', ...);
it('démarre le minuteur au clic et décompte', ...);
it('remet le minuteur à zéro au second bouton', ...);
it('ne crée aucun minuteur quand la puce n’en porte pas', ...);
it('demande le wakeLock à l’ouverture et le relâche à la sortie', ...);
it('survit à l’absence totale de navigator.wakeLock', async () => {
  // jsdom ne l’a pas : c’est le cas nominal du test, pas un cas limite.
});
it('n’appelle recipe/get qu’une seule fois', ...);
it('reste lisible quand la connexion échoue après le chargement', ...);
it('propose « J’ai cuisiné » seulement quand un mealId est fourni', ...);
it('émet « valider-repas » avec le meal_id depuis la dernière étape', ...);
```

- [ ] **Step 2 → 4: Échec, écriture, vert**

Run (depuis `frontend/`) : `npm test -- tests/recette.test.ts` → FAIL puis PASS, puis `npm test` complet.

- [ ] **Step 5: Commit**
```bash
git add frontend/src/ecrans/recette.ts frontend/tests/recette.test.ts
git commit -m "feat: the kitchen view — one page per step, buttons only, no gestures"
```

---

## Task 20: L'écran de validation

**Files:**
- Create: `frontend/src/ecrans/validation.ts`
- Test: `frontend/tests/validation.test.ts` (créer)

**Interfaces:** `<home-stock-validation>`, propriétés `.connexion`, `.file`, `.mealId` ; événement `repas-valide`.

**Ce que l'écran montre :** une ligne par ingrédient avec son statut (`ok`, `short`, `unmatched`, `unquantified`, `ignored`), le récapitulatif du plat (parts, DLC, coût, kilocalories), le sélecteur de parts mangées, et le partage optionnel **repris tel quel** de l'écran « manger » du lot 2 (`.partage-bascule`, `.parts-total`, `.parts-moi`, `PARTS_MAX = 24`, mêmes messages de refus). On ne réécrit pas un second sélecteur de parts : deux sélecteurs divergent.

**Confirmation en deux appuis.** Une validation écrit dans un journal en ajout seul : c'est destructif au sens du panneau, donc c'est le même geste que le cochage d'une tâche sur les tablettes. Armement, puis confirmation, en boutons, dans l'écran. Jamais de `window.confirm`.

**L'écran dit qu'il n'y a pas de retour en arrière.** En toutes lettres, avant l'appui de confirmation, plutôt que de laisser croire à une annulation possible.

- [ ] **Step 1: Écrire les tests**

```ts
it('affiche une ligne par ingrédient avec son statut', ...);
it.each(['ok', 'short', 'unmatched', 'unquantified'])(
  'donne un libellé français au statut %s', ...);
it('n’affiche pas les lignes ignorées', () => {
  // Sel, poivre, eau : ignorés SANS signalement (§ 13.4).
});
it('groupe les lignes non décrémentables sous « à sortir à la main »', ...);
it('retire une ligne au clic et la renvoie en simulation', ...);
it('rappelle meal/preview après chaque retrait, jamais meal/validate', ...);
it('bloque la validation tant qu’une ligne « short » n’est pas arbitrée', ...);
it('débloque la validation quand la ligne short est acceptée réduite', ...);
it('affiche le récapitulatif du plat : parts, DLC, coût, kcal', ...);
it('affiche un tiret plutôt que « 0 » pour un nutriment inconnu', ...);
it('reprend le sélecteur de parts du lot 2 à l’identique', ...);
it('accepte la virgule décimale dans les parts mangées', () => {
  // analyserNombre gère déjà virgule ET point : ne pas réécrire un parseur.
});
it('refuse localement plus de parts mangées que le plat n’en fait', ...);
it('refuse localement parts_moi > parts_total', ...);
it('demande deux appuis : le premier arme, le second envoie', async () => {
  await premierAppui(); expect(envoi).not.toHaveBeenCalled();
  await secondAppui();  expect(envoi).toHaveBeenCalledOnce();
});
it('un appui sur « Annuler » désarme sans rien envoyer', ...);
it('dit en toutes lettres qu’une validation ne s’annule pas', ...);
it('envoie meal/validate par la file, avec une clé d’idempotence', ...);
it('émet « repas-valide » quand l’envoi est parti', ...);
it('affiche « en attente » quand la file garde l’action hors ligne', ...);
it('n’envoie rien deux fois si on double-clique la confirmation', ...);
```

- [ ] **Step 2 → 4: Échec, écriture, vert**

Ajouter `'home_stock/meal/validate'` à `EXPECTED_QUEUED_COMMAND_TYPES` **dans cette tâche**, en même temps que le littéral côté front.

```bash
cd frontend && npm test -- tests/validation.test.ts   # FAIL puis PASS
cd frontend && npm test
./scripts/test.sh tests/test_offline_queue_contract.py -q
```

- [ ] **Step 5: Commit**
```bash
git add frontend/src/ecrans/validation.ts frontend/tests/validation.test.ts tests/test_offline_queue_contract.py
git commit -m "feat: the validation screen — two taps, and it says there is no undo"
```

---

## Task 21: Le planning, et la navigation qui rend tout ça atteignable

**Files:**
- Create: `frontend/src/ecrans/planning.ts`
- Modify: `frontend/src/panneau.ts`
- Test: `frontend/tests/planning.test.ts` (créer), `frontend/tests/panneau.test.ts`

**⚠️ Cette tâche est celle qui rend les trois écrans précédents atteignables.** Sans elle, les tâches 18 à 20 livrent des composants que rien n'ouvre — exactement le défaut qui a échappé aux dix-sept revues du lot 1, où `session/start` n'était appelé par personne et emportait avec lui le panier, deux capteurs et tout le parcours en magasin. **Les points d'entrée font partie du livrable.**

**Interfaces:**
- `Ecran` gagne `'recettes' | 'recette' | 'planning' | 'validation'`.
- La barre de navigation gagne **deux** boutons : « Recettes » et « Planning ». `recette` et `validation` n'en ont pas : la première s'ouvre depuis la liste ou le planning, la seconde depuis la dernière étape ou depuis le planning — exactement comme `consommation` et `fiche` au lot 2.
- Le panneau retient `recetteOuverte: number | null` et `repasAValider: number | null`, posés par les événements `recette-ouverte`, `valider-repas`, `repas-valide`.
- **Toute navigation passe par `demanderNavigation`**, jamais par `this.ecran = …`, pour que le garde-fou « rangement en attente » du lot 1 s'applique à ces cibles comme aux autres.

**Le planning :** sept colonnes × quatre créneaux en 1280 × 800, **une journée à la fois** en 412 × 915 avec précédent / suivant. **Pas de grille de sept colonnes réduite** : elle produirait des cibles sous 48 px et `verifier-rendu.mjs` la refuserait, à juste titre.

- [ ] **Step 1: Écrire les tests du planning**

```ts
it('affiche sept colonnes et quatre créneaux en large', ...);
it('affiche une seule journée en étroit, avec précédent et suivant', ...);
it('nomme les créneaux en français dans l’ordre du planning', ...);
it('affiche un repas de recette, un repas de produit et une note', ...);
it('marque visuellement un repas validé', ...);
it('signale les ingrédients manquants sur un repas planifié', ...);
it('pose un repas par meal/plan avec le jour et le créneau cliqués', ...);
it('déplace un repas par meal/move', ...);
it('refuse de déplacer un repas validé, et le dit', ...);
it('annule un repas planifié en deux appuis', ...);
it('ouvre la recette au clic sur un repas de recette', ...);
it('ouvre la validation au clic sur « Valider »', ...);
it('n’ouvre pas la validation sur un repas déjà validé', ...);
it('affiche un jour vide sans planter', ...);
```

- [ ] **Step 2: Écrire les tests de navigation** dans `frontend/tests/panneau.test.ts`

```ts
it('affiche les boutons Recettes et Planning dans la barre', ...);
it('ouvre l’écran Recettes au clic sur son bouton', ...);
it('ouvre la vue cuisine sur « recette-ouverte » et retient l’identifiant', ...);
it('ouvre la validation sur « valider-repas »', ...);
it('revient au planning après « repas-valide »', ...);
it('n’affiche aucun bouton pour la vue cuisine ni pour la validation', ...);
it('applique le garde-fou du rangement en attente aux quatre nouvelles cibles',
   async () => {
     // Depuis « rangement » avec des lignes en attente, cliquer « Planning »
     // arme la confirmation au lieu de naviguer.
   });
it('n’ouvre pas la vue cuisine sans recetteOuverte', ...);
```

- [ ] **Step 3: Lancer, vérifier l'échec**

Run (depuis `frontend/`) : `npm test -- tests/planning.test.ts tests/panneau.test.ts`

- [ ] **Step 4: Écrire l'écran et la navigation**

Six endroits, tous obligatoires : le type `Ecran`, les quatre `import './ecrans/…'`, les quatre branches de `rendreEcran()`, les deux boutons de `rendreNavigation()`, la liste `enfants` de `reglerAttente()` dans `verifier-rendu.mjs` (tâche 22), et les scénarios (tâche 22).

Ajouter `'home_stock/meal/plan'`, `'home_stock/meal/move'`, `'home_stock/meal/cancel'` et `'home_stock/recipe/ingredient/match'` à `EXPECTED_QUEUED_COMMAND_TYPES`, en même temps que leurs littéraux.

- [ ] **Step 5: Vert**

```bash
cd frontend && npm test
./scripts/test.sh tests/test_offline_queue_contract.py -q
```
Expected: PASS des deux. Le contrat de la file d'attente doit maintenant être **complet** : `tested == discovered == EXPECTED_QUEUED_COMMAND_TYPES`.

- [ ] **Step 6: Commit**
```bash
git add frontend/src/ecrans/planning.ts frontend/src/panneau.ts frontend/tests tests/test_offline_queue_contract.py
git commit -m "feat: the planning screen, and the navigation that makes lot 3 reachable"
```

---

## Task 22: Vérification de rendu, documentation, et construction du bundle

**Files:**
- Modify: `frontend/outils/verifier-rendu.mjs`
- Modify: `docs/exploitation.md`
- Modify: `custom_components/home_stock/panel/home-stock-panel.js` (produit par le build)

**C'est la seule tâche autorisée à lancer `npm run build`.** Le répertoire est bind-monté dans Home Assistant : le bundle construit est servi tel quel. Une seule construction, à la fin, quand tout le reste est vert.

- [ ] **Step 1: Compléter le vérificateur**

Deux gestes préalables, sans lesquels les scénarios mentiraient :
- ajouter les quatre nouveaux tags à la liste en dur de `reglerAttente()` (`home-stock-recettes`, `home-stock-recette`, `home-stock-validation`, `home-stock-planning`) — sans quoi le vérificateur mesure une page pas encore peinte ;
- vérifier que l'action `dispatch-evenement` existe bien (posée au lot 2) et l'utiliser pour atteindre `recette` et `validation`, qui n'ont pas de bouton de navigation.

Puis quatre scénarios dans `SCENARIOS` :

```js
  {
    nom: 'Recettes (liste dense, badges à relire et non appariés)',
    fixture: { reponses: { 'home_stock/session/current': null,
                           'home_stock/recipes/list': RECETTES_DENSES } },
    actions: [{ type: 'click-nav', texte: 'Recettes' }],
    ecranAttendu: 'home-stock-recettes',
  },
  {
    nom: 'Recette (étape avec minuteur, vue cuisine)',
    fixture: { reponses: { 'home_stock/session/current': null,
                           'home_stock/recipe/get': RECETTE_LONGUE } },
    actions: [
      { type: 'dispatch-evenement', nom: 'recette-ouverte', detail: { recipe_id: 4 } },
      { type: 'click-in-child', enfant: 'home-stock-recette', selector: '.suivant' },
    ],
    ecranAttendu: 'home-stock-recette',
    elementAttendu: { enfant: 'home-stock-recette', selector: '.minuteur' },
  },
  {
    nom: 'Planning (semaine chargée)',
    fixture: { reponses: { 'home_stock/session/current': null,
                           'home_stock/meals/list': SEMAINE_CHARGEE } },
    actions: [{ type: 'click-nav', texte: 'Planning' }],
    ecranAttendu: 'home-stock-planning',
  },
  {
    nom: 'Validation (un ingrédient manquant, partage ouvert)',
    fixture: { reponses: { 'home_stock/session/current': null,
                           'home_stock/meal/preview': PREVIEW_AVEC_MANQUE } },
    actions: [
      { type: 'dispatch-evenement', nom: 'valider-repas', detail: { meal_id: 12 } },
      { type: 'click-in-child', enfant: 'home-stock-validation', selector: '.partage-bascule' },
    ],
    ecranAttendu: 'home-stock-validation',
  },
```

Définir les fixtures avec des données **réalistes**, pas symboliques : `RECETTES_DENSES` avec **quarante** recettes dont des noms longs et des badges ; `RECETTE_LONGUE` avec **six** étapes, une image, cinq puces sur l'étape visée et un minuteur ; `SEMAINE_CHARGEE` avec **sept jours × quatre créneaux** partiellement remplis, dont un jour à trois repas et un repas validé ; `PREVIEW_AVEC_MANQUE` avec huit lignes dont une `short`, une `unmatched` et une `unquantified`. Une liste à trois entrées ne prouve rien sur le débordement.

Ajouter un scénario à `SCENARIOS_MINIFIES` : la vue cuisine sur le bundle minifié — c'est l'écran qui dépend le plus de noms de classes CSS, et `terser` est passé par là.

- [ ] **Step 2: Lancer le vérificateur**

Run (depuis `frontend/`) : `node outils/verifier-rendu.mjs`
Expected: aucun défaut sur les **deux** formats — aucun débordement, aucune cible sous 48 px, aucun contraste sous 4,5:1, aucun texte tronqué, et l'écran attendu réellement atteint.

Corriger les styles jusqu'à ce que ce soit vrai. **Ne jamais désactiver un contrôle.** Le point de rupture attendu est le planning : si les sept colonnes ne tiennent pas en 1280, c'est la grille qui change, pas le seuil.

- [ ] **Step 3: Mettre à jour la documentation d'exploitation**

Dans `docs/exploitation.md`, une section `## Lot 3 — recettes, planning et validation d'un repas` **à la fin du fichier**, en français et sans jargon :

- **Trois écrans de plus** : Recettes (liste et recherche), la vue cuisine (une page par étape, boutons seulement, l'écran ne s'éteint pas), et Planning (la semaine sur PC, la journée sur téléphone). La validation s'ouvre depuis la dernière étape ou depuis le planning.
- **Valider un repas, c'est deux choses d'un coup** : les ingrédients quittent le stock, et le plat y entre sous un produit « Reste — ⟨recette⟩ », avec une date limite à **trois jours** et ses calories. Ce que vous mangez le soir même en ressort ; les parts restantes attendent au frigo et **comptent le jour où vous les mangerez**, pas le jour de la cuisson.
- **Cuisiner ne fait monter aucun compteur.** Ni les calories du jour, ni les euros du jour. La valeur passe des ingrédients au plat, et la valeur totale du garde-manger ne bouge pas. C'est voulu : sinon le même repas serait compté deux fois.
- **Une validation ne s'annule pas.** Le journal est en ajout seul. C'est pour ça que l'écran simule d'abord et demande deux appuis. La correction viendra au lot 4.
- **Les restes déclenchent les alertes de date limite existantes** — le capteur, la liste de tâches et l'annonce vocale si le blueprint du lot 2 est installé. Rien à configurer.
- **Deux nouveaux réglages** dans Paramètres → Appareils et services → Garde-manger → Configurer : l'**agent conversationnel** qui traduit et découpe les recettes importées (laisser vide = pas de traduction, les recettes arrivent en anglais et marquées « à relire »), et la **clé TheMealDB** (laisser `1`, la clé publique, tant que le débit suffit). **Le composant ne stocke aucune clé d'IA** : il réutilise l'agent que Home Assistant a déjà.
- **Le planning est aussi un calendrier** : `calendar.home_stock_meals` s'affiche dans une carte Calendrier native, et on peut y poser un repas en tapant simplement son nom — il est apparié à une recette quand c'en est une.
- **La journée d'un repas est une journée alimentaire**, de 4 h à 4 h, comme le journal du lot 2. Un dîner validé à une heure du matin compte pour la soirée qu'on finit.
- **Les images de recettes importées restent chez la source** : une recette perd sa photo si TheMealDB disparaît. Dette assumée, à reprendre au lot 7 avec les images Grocy.
- **Ce que le lot 3 ne fait pas** : pas de liste de courses depuis le planning, pas de correction d'un repas validé, pas encore les 87 recettes de Grocy.

- [ ] **Step 4: Construire le bundle**

Run (depuis `frontend/`) : `npm run build`

Puis vérifier ce qui a été écrit :

```bash
git -C /opt/nivuus/HomeAssistant/data/meal status --porcelain custom_components/home_stock/panel/
```
Un seul fichier doit avoir changé.

- [ ] **Step 5: Vérifier le bundle réellement en place**

Run (depuis `frontend/`) : `node outils/verifier-rendu.mjs --deploye`
Expected: mêmes scénarios verts, cette fois sur le bundle construit et minifié.

- [ ] **Step 6: Lancer les deux suites une dernière fois**

```bash
./scripts/test.sh -q
cd /opt/nivuus/HomeAssistant/data/meal/frontend && npm test && node outils/verifier-rendu.mjs
```
Expected: tout vert, et les deux compteurs **au-dessus** de 623 et 247.

- [ ] **Step 7: Commit**

```bash
git add frontend/outils/verifier-rendu.mjs docs/exploitation.md custom_components/home_stock/panel/home-stock-panel.js
git commit -m "chore: render checks for the four new screens, docs, and the built panel"
```

---

## Ce que ce plan ne fait pas

Rappel, pour qu'aucune tâche n'aille les chercher :

- **Corriger un repas validé.** Le journal est en ajout seul ; annuler demande un motif `correction` et des mouvements de compensation. Groupé au lot 4 avec la correction de prix, déjà différée par le lot 2. Deux mécanismes de correction écrits séparément divergeraient.
- **La liste de courses depuis le planning.** `sensor.home_stock_missing_ingredients` porte l'information ; en faire une liste cochable suppose la session d'achat du lot 4, où cocher signifie « acheté » — donc un prix, un magasin et un rangement.
- **Empêcher un produit de restes d'atterrir sur une liste de courses.** C'est au lot 4 de le faire ; le lot 3 se contente de ne leur donner ni `min_quantity` ni rayon.
- **Reprendre les 87 recettes Grocy, leurs 420 lignes et leurs 41 images.** Lot 7. Le § 18 de la spec dit ce qu'il faut ; le faire maintenant importerait dans un modèle qu'on est encore en train de valider. Les seules données Grocy touchées ici sont les fixtures d'appariement de la tâche 7, lues **une fois, sur une copie**.
- **Rapatrier les images de recettes en local.** Lot 7, en même temps que les images d'articles — la question se pose une fois, pour les deux, au moment où Grocy s'éteint.
- **Les recettes imbriquées** (`recipes_nestings`) : 5 186 lignes chez Grocy, presque toutes issues des copies fantômes, aucun usage réel dans le foyer.
- **« Que cuisiner avec ce qui périme ».** Tout est en place (`expiry_candidates`, `recipe_ingredient.product_id`), rien ne presse.
- **Afficher les nutriments d'une recette avant cuisson.** Calculables, mais faux tant que l'appariement n'est pas complet — et un chiffre affiché avant d'être fiable ne se corrige plus dans la tête de celui qui l'a lu.
- **La récurrence (`RRULE`) au calendrier.** Un menu de la semaine n'est pas un événement récurrent.
- **Générer des images de recettes.** Ça reste dans l'outillage (`recettes_images.py`, `GEMINI_KEY` du `.env`) ; ce n'est pas le métier du composant, et le composant ne lit jamais cette clé.
- **La mise à l'échelle par convive nommé.** Les parts comptent des assiettes, pas des noms. Décision reprise du lot 2.
- **Écrire quoi que ce soit vers Grocy.** L'import est à sens unique, décision du lot 0.
- **Les tablettes murales, la vue dense PC et le vocal Bleuenn.** Lot 6.
- **Déployer.** Redémarrer Home Assistant, ouvrir la fenêtre des options pour désigner l'agent conversationnel et lancer le premier import restent le geste du propriétaire. Aucune tâche de ce plan ne touche l'instance vivante.
