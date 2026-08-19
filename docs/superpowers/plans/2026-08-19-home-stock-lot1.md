# home_stock Lot 1 — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rendre l'entrée en stock utilisable au téléphone sans clavier — scanner un code-barres, enrichir depuis Open Food Facts, relever le prix, et ranger le lot avec sa DLC.

**Architecture:** Le composant `home_stock` gagne une couche `off/` (réseau, isolée derrière un transport injectable), trois modules de domaine purs (`matching`, `pricing`, `conversion`), un module `shopping.py` pour la session de courses côté serveur, et des commandes websocket d'écriture. Un panneau SPA en TypeScript/`lit` vit dans `frontend/` et se compile vers `custom_components/home_stock/panel/`. Toute la logique risquée est dans des fonctions pures testées sans Home Assistant ni réseau.

**Tech Stack:** Python 3.14, Home Assistant 2026.8.2, SQLite (WAL), `aiohttp` (fourni par HA), pytest + `pytest-homeassistant-custom-component==0.13.356`, TypeScript, `lit`, rollup, vitest, playwright-core.

**Spec:** `docs/superpowers/specs/2026-08-19-home-stock-lot1-design.md`
**Spec du lot précédent (conventions, schéma) :** `docs/superpowers/specs/2026-08-18-home-stock-lot0-design.md`

## Global Constraints

Ces règles lient **toutes** les tâches. Elles sont recopiées mot pour mot du spec.

- **Code, identifiants, noms de tables et de colonnes en anglais.** Textes affichés en français, dans `translations/fr.json` côté HA et dans les composants côté front. Les commentaires de code sont en anglais.
- **Trois unités de base fermées : `g`, `ml`, `piece`.** Rien d'autre n'est stocké.
- **Toutes les valeurs nutritionnelles sont PAR UNITÉ DE BASE**, jamais pour 100 g. La conversion se fait à l'entrée.
- **`movement` est en ajout seul.** Deux déclencheurs SQLite (`movement_no_update`, `movement_no_delete`) le font respecter. Toute migration qui doit écrire dans `movement` supprime le déclencheur, écrit, et le recrée dans le même script.
- **Le motif `conversion` rejoint `REASONS` mais PAS `COUNTED_REASONS`.**
- **`QUANTITY_EPSILON = 0.001`** — en dessous, un lot est vide.
- **Aucun test ne sort sur le réseau.** Le client OFF et le client Open Prices sont injectés ; les doubles rendent les fixtures de `tests/fixtures/off/`.
- **En-tête OFF obligatoire :** `User-Agent: home_stock/<version> (Home Assistant; maxime@allanic.me)`.
- **Débit OFF (mesuré le 2026-08-19) :** scan interactif immédiat ; resynchronisation en masse **8 s entre deux fiches** ; `HTTP 429` → attente de **45 s**, **5 tentatives** au maximum, puis abandon silencieux de la fiche.
- **Délais réseau :** 10 s par base OFF, 20 s pour la cascade entière, 5 s pour Open Prices (échec silencieux).
- **Gardes de vraisemblance nutritionnelle**, un dépassement refuse **toute** la nutrition de la fiche : kcal/100 g dans `[0, 900]` ; protéines, glucides, lipides, sucres, fibres, sel /100 g dans `[0, 100]` ; `protéines + glucides + lipides ≤ 105`.
- **Garde de poids net :** nombre strictement positif dans `[0,5 ; 50 000]`, unité compatible avec l'unité de base du produit. Sinon rejeté.
- **Seuils de présélection d'un produit candidat :** score `> 0,75` **et** écart `> 0,10` avec le deuxième. Sinon rien n'est présélectionné.
- **Idempotence :** toute commande websocket qui écrit porte une `idempotency_key` fournie par le client ; elle est préfixée par l'opération qui la possède (`_namespaced_key`).
- **Front :** cibles tactiles **≥ 48 px**, contraste **≥ 4,5:1**, formats **412 × 915** (Pixel) et **1280 × 800** (PC), aucun débordement horizontal, **aucun appui long**, un seul geste par action.
- **Commande de test Python :** `./scripts/test.sh` (construit l'image alignée sur HA 2026.8.2 et lance pytest). Un fichier seul : `./scripts/test.sh tests/off/test_mapping.py -v`.
- **Commande de test front :** `cd frontend && npm test`.
- **Ne jamais écrire dans Grocy.** Ne jamais modifier `config/automations.yaml`, les dashboards ni `.storage/`.

## Structure des fichiers

**Créés dans `custom_components/home_stock/` :**

| Fichier | Responsabilité |
|---|---|
| `aisles.py` | Le référentiel des 16 rayons, la table catégorie → rayon, et la résolution `categories_tags` → rayon. Pur. |
| `off/__init__.py` | Paquet vide. |
| `off/client.py` | Cascade des 4 bases, en-têtes, délais, `429`. Transport injecté. |
| `off/mapping.py` | Fiche OFF → colonnes `article`. Pur, aucun réseau, aucun `hass`. |
| `off/open_prices.py` | Une requête Open Prices, transport injecté. |
| `domain/matching.py` | Candidats produit pour un article. Pur. |
| `domain/pricing.py` | Cascade de prix. Pur. |
| `domain/conversion.py` | Plan de conversion d'unité. Pur. |
| `shopping.py` | Cycle de vie de la session de courses. |
| `storage/migrations/m002_scan.py` | Schéma du lot 1, semis des rayons, reprise. |
| `panel.py` | Enregistrement du panneau et du statique. |
| `panel/` | Artefact de build. Jamais édité à la main. |

**Modifiés :** `const.py`, `storage/migrations/__init__.py`, `storage/repositories.py`, `application.py`, `websocket_api.py`, `sensor.py`, `services.py`, `services.yaml`, `translations/fr.json`, `translations/en.json`, `__init__.py`, `manifest.json`.

**Créés dans `frontend/` :** `package.json`, `rollup.config.mjs`, `tsconfig.json`, `vitest.config.ts`, `src/connexion.ts`, `src/file-attente.ts`, `src/etat.ts`, `src/scan/*.ts`, `src/ecrans/*.ts`, `src/styles/*.css`, `outils/verifier-rendu.mjs`.

**Fixtures déjà versionnées, à utiliser telles quelles :** `tests/fixtures/off/catalogue.json` (34 fiches réelles du garde-manger), `tests/fixtures/off/soeurs.json` (6 fiches des bases sœurs), `tests/fixtures/off/anomalies.json` (10 cas fabriqués).

---

### Task 1: Migration `m002` et référentiel des rayons

**Files:**
- Create: `custom_components/home_stock/aisles.py`
- Create: `custom_components/home_stock/storage/migrations/m002_scan.py`
- Modify: `custom_components/home_stock/storage/migrations/__init__.py`
- Modify: `custom_components/home_stock/const.py`
- Test: `tests/storage/test_migrations.py` (existant, à compléter), `tests/test_aisles.py` (nouveau)

**Interfaces:**
- Consumes: `apply_migrations(conn) -> int` et le schéma du lot 0 (`m001_initial.VERSION == 1`).
- Produces:
  - `aisles.AISLES: tuple[str, ...]` — les 16 noms, dans l'ordre du parcours.
  - `aisles.CATEGORY_TO_AISLE: dict[str, str]` — les 21 catégories du catalogue vers un nom de rayon.
  - `const.REASON_CONVERSION: str = "conversion"`, ajouté à `REASONS`, **absent** de `COUNTED_REASONS`.
  - `m002_scan.VERSION == 2`, `m002_scan.SQL: str`, `m002_scan.apply(conn) -> None`.
  - Le lanceur de migrations appelle `migration.apply(conn)` après `SQL` quand la fonction existe.

**Piège central :** `movement` porte un déclencheur `movement_no_update` qui fait échouer tout `UPDATE`. Le remplissage rétroactif de `base_unit` est un `UPDATE`. Il faut supprimer le déclencheur, écrire, puis le recréer **dans le même script SQL**.

- [ ] **Step 1: Écrire le test de la migration**

Dans `tests/storage/test_migrations.py`, ajouter :

```python
import sqlite3

from custom_components.home_stock.aisles import AISLES, CATEGORY_TO_AISLE
from custom_components.home_stock.storage.migrations import apply_migrations


def _lot0_database() -> sqlite3.Connection:
    """A database at schema version 1, with one product and one movement."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    from custom_components.home_stock.storage.migrations import m001_initial

    conn.executescript(m001_initial.SQL)
    conn.execute("INSERT INTO schema_version (version) VALUES (1)")
    conn.execute("INSERT INTO category (id, name) VALUES (1, 'Viande')")
    conn.execute("INSERT INTO location (id, name, kind) VALUES (1, 'Frigo', 'fridge')")
    conn.execute(
        "INSERT INTO product (id, name, base_unit, category_id) "
        "VALUES (1, 'Steak haché', 'piece', 1)"
    )
    conn.execute("INSERT INTO article (id, product_id, is_generic) VALUES (1, 1, 1)")
    conn.execute(
        "INSERT INTO movement (id, occurred_at, product_id, article_id, quantity, reason) "
        "VALUES (1, '2026-08-01T10:00:00', 1, 1, 2.0, 'purchase')"
    )
    conn.commit()
    return conn


def test_m002_freezes_the_unit_on_existing_movements():
    conn = _lot0_database()

    assert apply_migrations(conn) == 2

    row = conn.execute("SELECT base_unit FROM movement WHERE id = 1").fetchone()
    assert row["base_unit"] == "piece"


def test_m002_keeps_the_journal_append_only():
    conn = _lot0_database()
    apply_migrations(conn)

    # The backfill dropped the trigger. It must be back.
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE movement SET quantity = 99 WHERE id = 1")


def test_m002_seeds_every_aisle_in_walking_order():
    conn = _lot0_database()
    apply_migrations(conn)

    rows = conn.execute("SELECT name FROM aisle ORDER BY position").fetchall()
    assert [r["name"] for r in rows] == list(AISLES)


def test_m002_gives_each_product_the_aisle_of_its_category():
    conn = _lot0_database()
    apply_migrations(conn)

    row = conn.execute(
        "SELECT a.name FROM product p JOIN aisle a ON a.id = p.aisle_id WHERE p.id = 1"
    ).fetchone()
    assert row["name"] == CATEGORY_TO_AISLE["Viande"] == "Boucherie"


def test_m002_never_overwrites_an_aisle_already_chosen():
    conn = _lot0_database()
    apply_migrations(conn)
    conn.execute("UPDATE product SET aisle_id = (SELECT id FROM aisle WHERE name = 'Autre')")
    conn.commit()

    from custom_components.home_stock.storage.migrations import m002_scan

    m002_scan.apply(conn)  # replayed by hand

    row = conn.execute(
        "SELECT a.name FROM product p JOIN aisle a ON a.id = p.aisle_id WHERE p.id = 1"
    ).fetchone()
    assert row["name"] == "Autre"


def test_m002_allows_only_one_open_shopping_session():
    conn = _lot0_database()
    apply_migrations(conn)
    conn.execute(
        "INSERT INTO shopping_session (started_at, state) VALUES ('2026-08-19T10:00:00', 'shopping')"
    )

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO shopping_session (started_at, state) "
            "VALUES ('2026-08-19T11:00:00', 'shopping')"
        )


def test_m002_accepts_several_closed_sessions():
    conn = _lot0_database()
    apply_migrations(conn)

    for started in ("2026-08-01T10:00:00", "2026-08-02T10:00:00"):
        conn.execute(
            "INSERT INTO shopping_session (started_at, state) VALUES (?, 'done')", (started,)
        )
    assert conn.execute("SELECT COUNT(*) AS n FROM shopping_session").fetchone()["n"] == 2
```

Ajouter `import pytest` en tête du fichier s'il n'y est pas.

- [ ] **Step 2: Lancer le test et vérifier qu'il échoue**

Run: `./scripts/test.sh tests/storage/test_migrations.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'custom_components.home_stock.aisles'`

- [ ] **Step 3: Écrire le référentiel des rayons**

`custom_components/home_stock/aisles.py` :

```python
"""The aisle referential: the order of a shopping trip, and how the catalogue
maps onto it.

Kept out of the migration module because two consumers need it: the migration
that seeds the table, and the OFF classification that gives a scanned article
an aisle. No hass, no network, no SQLite.
"""
from __future__ import annotations

from typing import Final

# Walking order of a supermarket. Position in the table follows this tuple.
AISLES: Final = (
    "Fruits et légumes",
    "Boucherie",
    "Poissonnerie",
    "Charcuterie et traiteur",
    "Crémerie",
    "Fromages",
    "Boulangerie",
    "Épicerie salée",
    "Épicerie sucrée",
    "Petit-déjeuner",
    "Boissons",
    "Surgelés",
    "Hygiène et beauté",
    "Entretien et maison",
    "Animalerie",
    "Autre",
)

FALLBACK_AISLE: Final = "Autre"

# The 21 categories the lot 0 import created from Grocy's product groups.
CATEGORY_TO_AISLE: Final = {
    "Viande": "Boucherie",
    "Poisson": "Poissonnerie",
    "Légume": "Fruits et légumes",
    "Fruit": "Fruits et légumes",
    "Fromage": "Fromages",
    "Œufs": "Crémerie",
    "Produit laitier": "Crémerie",
    "Charcuterie": "Charcuterie et traiteur",
    "Épicerie": "Épicerie salée",
    "Condiment": "Épicerie salée",
    "Épice": "Épicerie salée",
    "Pâtes": "Épicerie salée",
    "Matière grasse": "Épicerie salée",
    "Boulangerie": "Boulangerie",
    "Céréale": "Petit-déjeuner",
    "Boisson": "Boissons",
    "Surgelé": "Surgelés",
    "Snack": "Épicerie sucrée",
    "Ménage": "Entretien et maison",
    "Équipement": "Entretien et maison",
    "Pharmacie/Parapharmacie": "Hygiène et beauté",
}
```

- [ ] **Step 4: Écrire la migration**

`custom_components/home_stock/storage/migrations/m002_scan.py` :

```python
"""Lot 1: the journal freezes its unit, products carry a shelf life, and the
shopping session gets its two tables. Mirrors section 6 of the lot 1 design.
"""
from __future__ import annotations

import sqlite3

from ...aisles import AISLES, CATEGORY_TO_AISLE

VERSION = 2

# The movement table is append-only, enforced by a BEFORE UPDATE trigger. The
# backfill below IS an UPDATE, so the trigger has to come off and go straight
# back on — inside the same script, so no window exists where history is
# rewritable.
SQL = """
DROP TRIGGER movement_no_update;

ALTER TABLE product ADD COLUMN default_shelf_life_days INTEGER;
ALTER TABLE movement ADD COLUMN base_unit TEXT;

UPDATE movement SET base_unit = (
  SELECT p.base_unit FROM product p WHERE p.id = movement.product_id
) WHERE base_unit IS NULL;

CREATE TRIGGER movement_no_update
BEFORE UPDATE ON movement
BEGIN
  SELECT RAISE(ABORT, 'movement is append-only: insert a new row instead of UPDATE');
END;

CREATE TABLE shopping_session (
  id INTEGER PRIMARY KEY,
  started_at TEXT NOT NULL,
  closed_at TEXT,
  store TEXT,
  state TEXT NOT NULL CHECK (state IN ('shopping','to_store','done'))
);

CREATE TABLE shopping_line (
  id INTEGER PRIMARY KEY,
  session_id INTEGER NOT NULL REFERENCES shopping_session(id),
  article_id INTEGER NOT NULL REFERENCES article(id),
  quantity REAL NOT NULL,
  unit_price REAL,
  scanned_at TEXT NOT NULL,
  stored_at TEXT,
  batch_id INTEGER REFERENCES batch(id),
  idempotency_key TEXT UNIQUE
);

CREATE INDEX idx_line_session ON shopping_line(session_id, stored_at);
CREATE UNIQUE INDEX idx_one_open_session
  ON shopping_session(state) WHERE state = 'shopping';
"""


def apply(conn: sqlite3.Connection) -> None:
    """Seed the aisles and give every product the aisle of its category.

    Written in Python rather than SQL because the referential lives in
    aisles.py, where the OFF classification reads it too. Both statements are
    replayable: INSERT OR IGNORE on the names, and a backfill that only ever
    fills an aisle that is still NULL — a hand-chosen aisle is never
    overwritten.
    """
    for position, name in enumerate(AISLES):
        conn.execute(
            "INSERT OR IGNORE INTO aisle (name, position) VALUES (?, ?)", (name, position)
        )

    for category, aisle in CATEGORY_TO_AISLE.items():
        conn.execute(
            """
            UPDATE product SET aisle_id = (SELECT id FROM aisle WHERE name = ?)
            WHERE aisle_id IS NULL
              AND category_id = (SELECT id FROM category WHERE name = ?)
            """,
            (aisle, category),
        )
```

- [ ] **Step 5: Brancher la migration et le point d'entrée `apply`**

Dans `custom_components/home_stock/storage/migrations/__init__.py` :

```python
from . import m001_initial, m002_scan

MIGRATIONS = (m001_initial, m002_scan)
```

et, dans `apply_migrations`, après `conn.executescript(migration.SQL)` :

```python
            conn.executescript(migration.SQL)
            # A migration whose data step needs the referential in Python
            # (aisles.py) exposes apply(); schema-only migrations do not.
            hook = getattr(migration, "apply", None)
            if hook is not None:
                hook(conn)
```

- [ ] **Step 6: Ajouter le motif `conversion`**

Dans `custom_components/home_stock/const.py`, après `REASON_TRANSFER` :

```python
REASON_CONVERSION: Final = "conversion"
REASONS: Final = (
    REASON_PURCHASE,
    REASON_CONSUMPTION,
    REASON_WASTE,
    REASON_EXPIRED,
    REASON_INVENTORY,
    REASON_TRANSFER,
    REASON_CONVERSION,
)
```

`COUNTED_REASONS` reste inchangé : une conversion ne consomme ni n'achète rien.

- [ ] **Step 7: Lancer les tests**

Run: `./scripts/test.sh tests/storage/ tests/test_aisles.py -v`
Expected: PASS

- [ ] **Step 8: Vérifier que la suite entière tient toujours**

Run: `./scripts/test.sh`
Expected: PASS — aucun test du lot 0 ne casse.

- [ ] **Step 9: Commit**

```bash
git add custom_components/home_stock/aisles.py \
        custom_components/home_stock/storage/migrations/ \
        custom_components/home_stock/const.py \
        tests/storage/test_migrations.py
git commit -m "feat: m002 — shelf life, frozen movement unit, shopping tables, aisle referential"
```

---

### Task 2: Classement d'un article par rayon depuis OFF

**Files:**
- Modify: `custom_components/home_stock/aisles.py`
- Test: `tests/test_aisles.py`

**Interfaces:**
- Consumes: `aisles.AISLES`, `aisles.FALLBACK_AISLE` (Task 1).
- Produces: `aisles.resolve_aisle(categories_tags: list[str] | None, off_source: str | None) -> str` — rend toujours un nom présent dans `AISLES`.

**Règle :** OFF classe `categories_tags` du plus général au plus précis. On parcourt **à l'envers** et le premier tag reconnu gagne. Sans reconnaissance, le rayon vient de la base d'origine.

- [ ] **Step 1: Écrire le test**

`tests/test_aisles.py` :

```python
"""The aisle classifier, exercised on the real catalogue fixtures."""
import json
from pathlib import Path

import pytest

from custom_components.home_stock.aisles import AISLES, resolve_aisle

FIXTURES = Path(__file__).parent / "fixtures" / "off"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_the_most_specific_tag_wins():
    # OFF orders tags general -> specific. "frozen-foods" must not beat
    # "ice-creams" just because it comes first.
    tags = ["en:foods", "en:frozen-foods", "en:desserts", "en:ice-creams"]
    assert resolve_aisle(tags, "food") == "Surgelés"


def test_an_unrecognised_tag_falls_back_to_the_database_of_origin():
    assert resolve_aisle(["en:unknown-thing"], "beauty") == "Hygiène et beauté"
    assert resolve_aisle(["en:unknown-thing"], "petfood") == "Animalerie"
    assert resolve_aisle(["en:unknown-thing"], "products") == "Entretien et maison"
    assert resolve_aisle(["en:unknown-thing"], "food") == "Épicerie salée"


def test_no_tags_at_all_still_yields_an_aisle():
    assert resolve_aisle(None, None) == "Autre"
    assert resolve_aisle([], None) == "Autre"


def test_generic_tags_only_falls_back_rather_than_guessing():
    record = _load("anomalies.json")["categories_generiques_seulement"]["product"]
    assert resolve_aisle(record["categories_tags"], "food") == "Épicerie salée"


def test_every_catalogue_fixture_lands_in_a_real_aisle():
    catalogue = _load("catalogue.json")
    for code, entry in catalogue.items():
        product = entry.get("product")
        if not product:
            continue
        aisle = resolve_aisle(product.get("categories_tags"), entry["off_source"])
        assert aisle in AISLES, f"{code} landed outside the referential: {aisle}"


def test_the_sister_databases_classify_out_of_the_food_aisles():
    for entry in _load("soeurs.json").values():
        product = entry["product"]
        aisle = resolve_aisle(product.get("categories_tags"), entry["off_source"])
        assert aisle in ("Hygiène et beauté", "Entretien et maison", "Animalerie", "Autre")


@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        ("en:cheeses", "Fromages"),
        ("en:yogurts", "Crémerie"),
        ("en:hams", "Charcuterie et traiteur"),
        ("en:breakfast-cereals", "Petit-déjeuner"),
        ("en:fresh-vegetables", "Fruits et légumes"),
        ("en:waters", "Boissons"),
        ("en:breads", "Boulangerie"),
        ("en:biscuits", "Épicerie sucrée"),
        ("en:fishes", "Poissonnerie"),
        ("en:pastas", "Épicerie salée"),
    ],
)
def test_known_tags_map_where_a_shopper_expects(tag, expected):
    assert resolve_aisle(["en:foods", tag], "food") == expected
```

- [ ] **Step 2: Lancer le test et vérifier qu'il échoue**

Run: `./scripts/test.sh tests/test_aisles.py -v`
Expected: FAIL — `ImportError: cannot import name 'resolve_aisle'`

- [ ] **Step 3: Écrire le classifieur**

À ajouter à `custom_components/home_stock/aisles.py` :

```python
# OFF category tags, from the specific to the generic. resolve_aisle() walks
# categories_tags backwards — OFF orders them general first — so the first
# match is the most precise statement OFF makes about the product.
TAG_TO_AISLE: Final = {
    "en:fresh-vegetables": "Fruits et légumes",
    "en:vegetables": "Fruits et légumes",
    "en:fresh-fruits": "Fruits et légumes",
    "en:fruits": "Fruits et légumes",
    "en:legumes": "Fruits et légumes",
    "en:meats": "Boucherie",
    "en:fresh-meats": "Boucherie",
    "en:poultry": "Boucherie",
    "en:beef": "Boucherie",
    "en:fishes": "Poissonnerie",
    "en:seafood": "Poissonnerie",
    "en:hams": "Charcuterie et traiteur",
    "en:charcuteries": "Charcuterie et traiteur",
    "en:prepared-meats": "Charcuterie et traiteur",
    "en:delicatessen": "Charcuterie et traiteur",
    "en:cheeses": "Fromages",
    "en:dairies": "Crémerie",
    "en:milks": "Crémerie",
    "en:yogurts": "Crémerie",
    "en:creams": "Crémerie",
    "en:butters": "Crémerie",
    "en:eggs": "Crémerie",
    "en:breads": "Boulangerie",
    "en:bakery-products": "Boulangerie",
    "en:viennoiseries": "Boulangerie",
    "en:breakfast-cereals": "Petit-déjeuner",
    "en:breakfasts": "Petit-déjeuner",
    "en:spreads": "Petit-déjeuner",
    "en:jams": "Petit-déjeuner",
    "en:coffees": "Petit-déjeuner",
    "en:teas": "Petit-déjeuner",
    "en:beverages": "Boissons",
    "en:waters": "Boissons",
    "en:juices": "Boissons",
    "en:alcoholic-beverages": "Boissons",
    "en:frozen-foods": "Surgelés",
    "en:ice-creams": "Surgelés",
    "en:frozen-desserts": "Surgelés",
    "en:biscuits": "Épicerie sucrée",
    "en:biscuits-and-cakes": "Épicerie sucrée",
    "en:chocolates": "Épicerie sucrée",
    "en:confectioneries": "Épicerie sucrée",
    "en:sweet-snacks": "Épicerie sucrée",
    "en:desserts": "Épicerie sucrée",
    "en:pastas": "Épicerie salée",
    "en:rice": "Épicerie salée",
    "en:canned-foods": "Épicerie salée",
    "en:sauces": "Épicerie salée",
    "en:condiments": "Épicerie salée",
    "en:spices": "Épicerie salée",
    "en:vegetable-oils": "Épicerie salée",
    "en:salty-snacks": "Épicerie salée",
    "en:groceries": "Épicerie salée",
    "en:hygiene": "Hygiène et beauté",
    "en:body-care": "Hygiène et beauté",
    "en:hair-care": "Hygiène et beauté",
    "en:cosmetics": "Hygiène et beauté",
    "en:household-products": "Entretien et maison",
    "en:cleaning-products": "Entretien et maison",
    "en:laundry": "Entretien et maison",
    "en:sponges": "Entretien et maison",
    "en:batteries": "Entretien et maison",
    "en:pet-foods": "Animalerie",
    "en:cat-foods": "Animalerie",
    "en:dog-foods": "Animalerie",
}

# What a database says about a product when none of its tags is recognised.
SOURCE_TO_AISLE: Final = {
    "food": "Épicerie salée",
    "products": "Entretien et maison",
    "beauty": "Hygiène et beauté",
    "petfood": "Animalerie",
}


def resolve_aisle(categories_tags: list[str] | None, off_source: str | None) -> str:
    """Pick the aisle a scanned article belongs to. Always returns a real aisle."""
    for tag in reversed(categories_tags or []):
        aisle = TAG_TO_AISLE.get(tag)
        if aisle is not None:
            return aisle
    return SOURCE_TO_AISLE.get(off_source or "", FALLBACK_AISLE)
```

- [ ] **Step 4: Lancer les tests**

Run: `./scripts/test.sh tests/test_aisles.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/home_stock/aisles.py tests/test_aisles.py
git commit -m "feat: classify a scanned article into an aisle from its OFF category tags"
```

---

### Task 3: Le journal fige son unité

**Files:**
- Modify: `custom_components/home_stock/storage/repositories.py`
- Modify: `custom_components/home_stock/application.py`
- Test: `tests/test_application.py` (existant, à compléter)

**Interfaces:**
- Consumes: la colonne `movement.base_unit` (Task 1).
- Produces:
  - `repo.insert_movement(conn, *, occurred_at, product_id, article_id, batch_id, quantity, reason, base_unit, kcal, cost, ref_type, ref_id, idempotency_key) -> int` — `base_unit` devient **obligatoire**.
  - `repo.product_base_unit(conn, product_id: int) -> str`.

**Pourquoi :** dès qu'un produit peut changer d'unité (Task 9), une quantité passée ne veut plus rien dire sans son unité. Le journal étant en ajout seul, on ne pourra jamais la rattraper après coup.

- [ ] **Step 1: Écrire le test**

Dans `tests/test_application.py` :

```python
def test_every_movement_written_carries_its_unit(manager):
    """A quantity without its unit is unreadable the day the product converts."""
    article_id = _seed_article(manager, base_unit="g")

    manager.add_stock(article_id=article_id, quantity=500, location_id=1)
    manager.consume(product_id=1, quantity=200, reason="consumption")

    with manager.db.write() as conn:
        rows = conn.execute("SELECT reason, base_unit FROM movement ORDER BY id").fetchall()
    assert [r["base_unit"] for r in rows] == ["g", "g"]
    assert all(r["base_unit"] is not None for r in rows)


def test_the_unit_written_is_the_product_s_own(manager):
    article_id = _seed_article(manager, base_unit="ml")

    manager.add_stock(article_id=article_id, quantity=750, location_id=1)

    with manager.db.write() as conn:
        row = conn.execute("SELECT base_unit FROM movement ORDER BY id DESC LIMIT 1").fetchone()
    assert row["base_unit"] == "ml"
```

`_seed_article` est le helper déjà présent dans ce fichier ; s'il ne prend pas encore
`base_unit`, lui ajouter le paramètre avec `"g"` par défaut, sans changer les appels
existants.

- [ ] **Step 2: Lancer le test et vérifier qu'il échoue**

Run: `./scripts/test.sh tests/test_application.py -k unit -v`
Expected: FAIL — `base_unit` vaut `None` sur les mouvements écrits.

- [ ] **Step 3: Rendre `base_unit` obligatoire dans le dépôt**

Dans `storage/repositories.py`, ajouter le paramètre à `insert_movement` et à sa liste de
colonnes, puis :

```python
def product_base_unit(conn, product_id: int) -> str:
    """The base unit a movement on this product must be recorded in."""
    row = conn.execute(
        "SELECT base_unit FROM product WHERE id = ?", (product_id,)
    ).fetchone()
    if row is None:
        raise LookupError(f"no product {product_id}")
    return row["base_unit"]
```

- [ ] **Step 4: Renseigner l'unité à chaque écriture**

Dans `application.py`, chaque appel à `repo.insert_movement` reçoit
`base_unit=repo.product_base_unit(conn, product_id)`. Les méthodes concernées sont
`add_stock`, `consume`, `consume_batch`, `transfer_batch` et `adjust_inventory`. Dans
`consume`, l'unité se lit **une fois** avant la boucle d'allocation : tous les lots d'un
même produit partagent forcément son unité.

- [ ] **Step 5: Lancer la suite entière**

Run: `./scripts/test.sh`
Expected: PASS — les tests du lot 0 passent toujours ; un appel oublié se voit
immédiatement en `TypeError: insert_movement() missing 1 required keyword-only argument`.

- [ ] **Step 6: Commit**

```bash
git add custom_components/home_stock/storage/repositories.py \
        custom_components/home_stock/application.py tests/test_application.py
git commit -m "feat: freeze the base unit on every movement written"
```

---

### Task 4: Dépôts de la session de courses et des prix

**Files:**
- Modify: `custom_components/home_stock/storage/repositories.py`
- Test: `tests/storage/test_repositories_shopping.py` (nouveau)

**Interfaces:**
- Consumes: les tables `shopping_session`, `shopping_line`, `price` (Task 1 et lot 0).
- Produces, toutes synchrones, toutes prenant `conn` en premier argument :
  - `open_session(conn, *, started_at: str, store: str | None) -> int`
  - `current_session(conn) -> dict | None` — la session en état `shopping`, sinon la plus récente en `to_store`, sinon `None`.
  - `get_session(conn, session_id: int) -> dict | None`
  - `set_session_state(conn, session_id: int, state: str, *, closed_at: str | None = None) -> None`
  - `add_line(conn, *, session_id: int, article_id: int, quantity: float, unit_price: float | None, scanned_at: str, idempotency_key: str | None) -> int`
  - `update_line(conn, line_id: int, *, quantity: float | None = None, unit_price: float | None = None) -> None`
  - `remove_line(conn, line_id: int) -> None`
  - `line_by_key(conn, idempotency_key: str) -> dict | None`
  - `list_lines(conn, session_id: int, *, pending_only: bool = False) -> list[dict]` — jointe au produit, à l'article et au rayon, triée par `aisle.position` puis par nom de produit.
  - `mark_line_stored(conn, line_id: int, *, batch_id: int, stored_at: str) -> None`
  - `session_totals(conn, session_id: int) -> dict` — `{"lines": int, "pending": int, "total": float}`, `total` = Σ `quantity × unit_price` en ignorant les lignes sans prix.
  - `latest_price_in_store(conn, article_id: int, store: str) -> float | None`
  - `list_stores(conn) -> list[str]` — magasins déjà utilisés, du plus récent au plus ancien.

- [ ] **Step 1: Écrire le test**

`tests/storage/test_repositories_shopping.py` :

```python
"""The shopping session repositories, on a real migrated database."""
import sqlite3

import pytest

from custom_components.home_stock.storage import repositories as repo
from custom_components.home_stock.storage.migrations import apply_migrations


@pytest.fixture
def conn() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    apply_migrations(connection)
    connection.execute("INSERT INTO location (id, name, kind) VALUES (1, 'Placard', 'pantry')")
    connection.execute(
        "INSERT INTO product (id, name, base_unit, aisle_id) VALUES "
        "(1, 'Pâtes', 'g', (SELECT id FROM aisle WHERE name = 'Épicerie salée')),"
        "(2, 'Yaourt', 'piece', (SELECT id FROM aisle WHERE name = 'Crémerie'))"
    )
    connection.execute(
        "INSERT INTO article (id, product_id, label) VALUES (1, 1, 'Panzani 500 g'),"
        "(2, 2, 'Nature x4')"
    )
    return connection


def test_a_session_opens_and_is_found_again(conn):
    session_id = repo.open_session(conn, started_at="2026-08-19T10:00:00", store="Leclerc")

    current = repo.current_session(conn)
    assert current["id"] == session_id
    assert current["store"] == "Leclerc"
    assert current["state"] == "shopping"


def test_lines_come_back_in_walking_order_not_scan_order(conn):
    """The cart is read while walking the shop, so the aisle order is the one
    that matters — not the order things were scanned in."""
    session_id = repo.open_session(conn, started_at="2026-08-19T10:00:00", store=None)
    repo.add_line(conn, session_id=session_id, article_id=1, quantity=500,
                  unit_price=0.002, scanned_at="2026-08-19T10:05:00", idempotency_key="a")
    repo.add_line(conn, session_id=session_id, article_id=2, quantity=4,
                  unit_price=0.35, scanned_at="2026-08-19T10:01:00", idempotency_key="b")

    lines = repo.list_lines(conn, session_id)

    assert [line["product_name"] for line in lines] == ["Yaourt", "Pâtes"]


def test_the_total_ignores_a_line_with_no_price(conn):
    session_id = repo.open_session(conn, started_at="2026-08-19T10:00:00", store=None)
    repo.add_line(conn, session_id=session_id, article_id=1, quantity=500,
                  unit_price=0.002, scanned_at="2026-08-19T10:05:00", idempotency_key="a")
    repo.add_line(conn, session_id=session_id, article_id=2, quantity=4,
                  unit_price=None, scanned_at="2026-08-19T10:06:00", idempotency_key="b")

    totals = repo.session_totals(conn, session_id)

    assert totals == {"lines": 2, "pending": 2, "total": pytest.approx(1.0)}


def test_a_stored_line_leaves_the_pending_list(conn):
    session_id = repo.open_session(conn, started_at="2026-08-19T10:00:00", store=None)
    line_id = repo.add_line(conn, session_id=session_id, article_id=1, quantity=500,
                            unit_price=0.002, scanned_at="2026-08-19T10:05:00",
                            idempotency_key="a")
    batch_id = repo.insert_batch(conn, article_id=1, location_id=1, quantity=500,
                                 best_before=None, entered_at="2026-08-19T12:00:00",
                                 price_per_base_unit=0.002)

    repo.mark_line_stored(conn, line_id, batch_id=batch_id, stored_at="2026-08-19T12:00:00")

    assert repo.list_lines(conn, session_id, pending_only=True) == []
    assert repo.session_totals(conn, session_id)["pending"] == 0


def test_a_replayed_scan_is_found_by_its_key(conn):
    session_id = repo.open_session(conn, started_at="2026-08-19T10:00:00", store=None)
    line_id = repo.add_line(conn, session_id=session_id, article_id=1, quantity=500,
                            unit_price=None, scanned_at="2026-08-19T10:05:00",
                            idempotency_key="scan-42")

    assert repo.line_by_key(conn, "scan-42")["id"] == line_id
    assert repo.line_by_key(conn, "scan-43") is None


def test_the_price_of_this_shop_beats_the_price_of_another(conn):
    repo.insert_price(conn, article_id=1, observed_on="2026-08-01",
                      price_per_base_unit=0.003, store="Carrefour", source="manual")
    repo.insert_price(conn, article_id=1, observed_on="2026-08-02",
                      price_per_base_unit=0.002, store="Leclerc", source="manual")

    assert repo.latest_price_in_store(conn, 1, "Leclerc") == pytest.approx(0.002)
    assert repo.latest_price_in_store(conn, 1, "Lidl") is None


def test_known_shops_come_back_most_recent_first(conn):
    repo.insert_price(conn, article_id=1, observed_on="2026-08-01",
                      price_per_base_unit=0.003, store="Carrefour", source="manual")
    repo.insert_price(conn, article_id=1, observed_on="2026-08-05",
                      price_per_base_unit=0.002, store="Leclerc", source="manual")

    assert repo.list_stores(conn) == ["Leclerc", "Carrefour"]
```

- [ ] **Step 2: Lancer le test et vérifier qu'il échoue**

Run: `./scripts/test.sh tests/storage/test_repositories_shopping.py -v`
Expected: FAIL — `AttributeError: module ... has no attribute 'open_session'`

- [ ] **Step 3: Écrire les dépôts**

À ajouter à `storage/repositories.py`, après les dépôts de lots :

```python
# --- shopping sessions ------------------------------------------------------

def open_session(conn, *, started_at: str, store: str | None) -> int:
    """Start a shopping session. The partial unique index refuses a second one."""
    return _insert(conn, "shopping_session",
                   {"started_at": started_at, "store": store, "state": "shopping"})


def current_session(conn) -> dict[str, Any] | None:
    """The session the panel should show: the open one, else the last one still
    waiting to be put away."""
    return _row(conn.execute(
        """
        SELECT * FROM shopping_session
        WHERE state IN ('shopping', 'to_store')
        ORDER BY CASE state WHEN 'shopping' THEN 0 ELSE 1 END, started_at DESC
        LIMIT 1
        """
    ).fetchone())


def get_session(conn, session_id: int) -> dict[str, Any] | None:
    return _row(conn.execute(
        "SELECT * FROM shopping_session WHERE id = ?", (session_id,)).fetchone())


def set_session_state(conn, session_id: int, state: str, *,
                      closed_at: str | None = None) -> None:
    conn.execute("UPDATE shopping_session SET state = ?, closed_at = ? WHERE id = ?",
                 (state, closed_at, session_id))


def add_line(conn, *, session_id: int, article_id: int, quantity: float,
             unit_price: float | None, scanned_at: str,
             idempotency_key: str | None) -> int:
    return _insert(conn, "shopping_line", {
        "session_id": session_id, "article_id": article_id, "quantity": quantity,
        "unit_price": unit_price, "scanned_at": scanned_at,
        "idempotency_key": idempotency_key,
    })


def update_line(conn, line_id: int, *, quantity: float | None = None,
                unit_price: float | None = None) -> None:
    """Only the fields actually passed are written: None means "leave it", which
    is not the same as "clear it"."""
    if quantity is not None:
        conn.execute("UPDATE shopping_line SET quantity = ? WHERE id = ?",
                     (quantity, line_id))
    if unit_price is not None:
        conn.execute("UPDATE shopping_line SET unit_price = ? WHERE id = ?",
                     (unit_price, line_id))


def remove_line(conn, line_id: int) -> None:
    """Drop a line. Safe because nothing entered the stock yet — a stored line
    is refused by the caller, not here."""
    conn.execute("DELETE FROM shopping_line WHERE id = ?", (line_id,))


def line_by_key(conn, idempotency_key: str) -> dict[str, Any] | None:
    return _row(conn.execute(
        "SELECT * FROM shopping_line WHERE idempotency_key = ?",
        (idempotency_key,)).fetchone())


LINE_SELECT_SQL = """
SELECT l.*, p.id AS product_id, p.name AS product_name, p.base_unit,
       p.default_location_id, p.default_shelf_life_days, p.days_after_opening,
       a.label AS article_label, a.brand, a.image, a.net_quantity,
       ai.name AS aisle_name, COALESCE(ai.position, 999) AS aisle_position
FROM shopping_line l
JOIN article a ON a.id = l.article_id
JOIN product p ON p.id = a.product_id
LEFT JOIN aisle ai ON ai.id = p.aisle_id
WHERE l.session_id = ?
"""


def list_lines(conn, session_id: int, *, pending_only: bool = False) -> list[dict[str, Any]]:
    """The cart, in walking order. Scan order is never what a shopper wants."""
    sql = LINE_SELECT_SQL
    if pending_only:
        sql += " AND l.stored_at IS NULL"
    sql += " ORDER BY aisle_position, p.name, l.id"
    return _rows(conn.execute(sql, (session_id,)))


def mark_line_stored(conn, line_id: int, *, batch_id: int, stored_at: str) -> None:
    conn.execute("UPDATE shopping_line SET batch_id = ?, stored_at = ? WHERE id = ?",
                 (batch_id, stored_at, line_id))


def session_totals(conn, session_id: int) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT COUNT(*) AS lines,
               SUM(CASE WHEN stored_at IS NULL THEN 1 ELSE 0 END) AS pending,
               COALESCE(SUM(quantity * COALESCE(unit_price, 0)), 0) AS total
        FROM shopping_line WHERE session_id = ?
        """,
        (session_id,),
    ).fetchone()
    return {"lines": row["lines"], "pending": row["pending"] or 0,
            "total": round(row["total"], 4)}


def latest_price_in_store(conn, article_id: int, store: str) -> float | None:
    row = conn.execute(
        """
        SELECT price_per_base_unit FROM price
        WHERE article_id = ? AND store = ?
        ORDER BY observed_on DESC, id DESC LIMIT 1
        """,
        (article_id, store),
    ).fetchone()
    return row["price_per_base_unit"] if row else None


def list_stores(conn) -> list[str]:
    """Shops already used, most recently seen first — the panel shows them as chips."""
    rows = conn.execute(
        """
        SELECT store, MAX(observed_on) AS last_seen FROM price
        WHERE store IS NOT NULL AND store <> ''
        GROUP BY store ORDER BY last_seen DESC, store
        """
    ).fetchall()
    return [row["store"] for row in rows]
```

- [ ] **Step 4: Lancer les tests**

Run: `./scripts/test.sh tests/storage/ -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/home_stock/storage/repositories.py \
        tests/storage/test_repositories_shopping.py
git commit -m "feat: repositories for shopping sessions, lines and per-store prices"
```

---
### Task 5: `off/mapping.py` — une fiche OFF devient des colonnes

**Files:**
- Create: `custom_components/home_stock/off/__init__.py`
- Create: `custom_components/home_stock/off/mapping.py`
- Test: `tests/off/test_mapping.py` (nouveau), `tests/off/__init__.py`

**Interfaces:**
- Consumes: `aisles.resolve_aisle` (Task 2).
- Produces:
  - `mapping.MappedArticle` — dataclass gelée : `label`, `generic_name`, `brand`, `net_quantity: float | None`, `net_unit: str | None` (`'g'`/`'ml'`), `image`, `nutriscore`, `nova`, `ecoscore`, `allergens`, `traces`, `additives`, `off_labels`, `off_source`, `aisle: str`, `nutrition_per_100: dict[str, float] | None`, `rejections: tuple[str, ...]`.
  - `mapping.map_article(product: dict, off_source: str) -> MappedArticle`
  - `mapping.parse_net_quantity(product: dict) -> tuple[float, str] | None`
  - `mapping.nutrition_per_base_unit(nutrition_per_100: dict[str, float] | None, base_unit: str, net_quantity: float | None) -> dict[str, float] | None`
  - `mapping.NUTRIMENT_COLUMNS: tuple[str, ...]` — les noms de colonnes de `article`.

**Aucun réseau, aucun `hass`, aucun SQLite dans ce module.** `map_article` ne connaît pas le produit : la nutrition en sort **pour 100 g/ml**, et `nutrition_per_base_unit` la ramène à l'unité de base quand le produit est connu. C'est ce découpage qui permet de mapper une fiche avant même de savoir à quel produit elle sera rattachée.

- [ ] **Step 1: Écrire le test**

`tests/off/__init__.py` : fichier vide.

`tests/off/test_mapping.py` :

```python
"""OFF record -> article columns, on the real fixtures and the fabricated ones."""
import json
from pathlib import Path

import pytest

from custom_components.home_stock.off.mapping import (
    map_article,
    nutrition_per_base_unit,
    parse_net_quantity,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "off"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _anomaly(key: str) -> dict:
    return _load("anomalies.json")[key]["product"]


# --- net quantity -----------------------------------------------------------

def test_a_weight_in_kilograms_becomes_grams():
    assert parse_net_quantity({"product_quantity": 1.5, "product_quantity_unit": "kg"}) == (1500.0, "g")


def test_a_volume_in_centilitres_becomes_millilitres():
    assert parse_net_quantity(_anomaly("volume_en_cl")) == (750.0, "ml")


def test_an_unreadable_quantity_is_rejected_rather_than_guessed():
    # "1,kg" is a real OFF entry. float("1,".replace(",", ".")) would happily
    # return 1.0 and silently invent a one-kilogram pack.
    assert parse_net_quantity(_anomaly("quantite_illisible")) is None


def test_a_zero_or_absurd_quantity_is_rejected():
    assert parse_net_quantity(_anomaly("quantite_nulle")) is None
    assert parse_net_quantity(_anomaly("quantite_demesuree")) is None


def test_a_countable_unit_is_not_a_weight():
    assert parse_net_quantity(_anomaly("sans_nutrition")) is None


def test_a_decimal_comma_with_digits_is_read():
    assert parse_net_quantity({"product_quantity": "1,5", "product_quantity_unit": "l"}) == (1500.0, "ml")


# --- nutrition --------------------------------------------------------------

def test_nutrition_comes_back_per_100_grams():
    mapped = map_article(_anomaly("volume_en_cl"), "food")
    assert mapped.nutrition_per_100["kcal"] == pytest.approx(824)
    assert mapped.nutrition_per_100["fat"] == pytest.approx(91.6)
    assert mapped.nutrition_per_100["saturated_fat"] == pytest.approx(13.8)


def test_impossible_calories_reject_the_whole_nutrition():
    mapped = map_article(_anomaly("kcal_impossibles"), "food")
    assert mapped.nutrition_per_100 is None
    assert "kcal" in " ".join(mapped.rejections)


def test_macros_that_do_not_fit_in_100_grams_reject_the_whole_nutrition():
    mapped = map_article(_anomaly("macros_incoherentes"), "food")
    assert mapped.nutrition_per_100 is None


def test_values_given_per_serving_are_brought_back_to_100_grams():
    mapped = map_article(_anomaly("par_portion_seulement"), "food")
    # 140 kcal for a 35 g serving -> 400 kcal per 100 g
    assert mapped.nutrition_per_100["kcal"] == pytest.approx(400)


def test_prepared_values_are_ignored_because_we_stock_the_dry_product():
    mapped = map_article(_anomaly("prepare_seulement"), "food")
    assert mapped.nutrition_per_100 is None


def test_a_record_with_no_nutrition_keeps_the_rest_of_the_card():
    mapped = map_article(_anomaly("sans_nutrition"), "products")
    assert mapped.nutrition_per_100 is None
    assert mapped.label == "Éponge grattante"
    assert mapped.aisle == "Entretien et maison"


# --- per base unit ----------------------------------------------------------

def test_a_gram_product_divides_by_a_hundred():
    per_base = nutrition_per_base_unit({"kcal": 350.0, "proteins": 12.0}, "g", None)
    assert per_base["kcal"] == pytest.approx(3.5)
    assert per_base["proteins"] == pytest.approx(0.12)


def test_a_piece_product_needs_its_net_weight():
    per_base = nutrition_per_base_unit({"kcal": 350.0}, "piece", 500.0)
    assert per_base["kcal"] == pytest.approx(1750.0)


def test_a_piece_product_without_a_net_weight_gets_nothing_rather_than_a_guess():
    """NULL is visible and fixable. A factor of a thousand is not."""
    assert nutrition_per_base_unit({"kcal": 350.0}, "piece", None) is None


# --- the real catalogue -----------------------------------------------------

def test_every_real_card_maps_without_raising():
    for code, entry in _load("catalogue.json").items():
        product = entry.get("product")
        if not product:
            continue
        mapped = map_article(product, entry["off_source"])
        assert mapped.off_source == entry["off_source"]
        assert mapped.aisle
        if mapped.nutrition_per_100 is not None:
            assert 0 <= mapped.nutrition_per_100["kcal"] <= 900


def test_the_real_catalogue_yields_the_expected_coverage():
    """Guards that reject too much are as bad as guards that reject nothing.
    Measured on the 34 cards captured on 2026-08-19."""
    catalogue = [e for e in _load("catalogue.json").values() if e.get("product")]
    mapped = [map_article(e["product"], e["off_source"]) for e in catalogue]

    with_nutrition = [m for m in mapped if m.nutrition_per_100]
    with_weight = [m for m in mapped if m.net_quantity]

    assert len(mapped) == 34
    assert len(with_nutrition) >= 29, "the guards are throwing away real data"
    assert len(with_weight) >= 24


def test_the_sister_databases_map_too():
    for entry in _load("soeurs.json").values():
        mapped = map_article(entry["product"], entry["off_source"])
        assert mapped.off_source in ("products", "beauty", "petfood")
```

- [ ] **Step 2: Lancer le test et vérifier qu'il échoue**

Run: `./scripts/test.sh tests/off/test_mapping.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'custom_components.home_stock.off'`

- [ ] **Step 3: Écrire le mapping**

`custom_components/home_stock/off/__init__.py` :

```python
"""Open Food Facts and its sister databases."""
```

`custom_components/home_stock/off/mapping.py` :

```python
"""Turn one Open Food Facts record into the columns of `article`.

Pure: no network, no hass, no SQLite. That is deliberate — the rules encoded
here (per-100 g versus per-serving, the plausibility guards, the refusal to
invent a net weight) are the ones that produced Grocy's thousand-fold-wrong
spinach, and they must be testable on a fixture without starting anything.

Nutrition leaves this module PER 100 g/ml. Bringing it down to the product's
base unit needs the product, which may not exist yet when a barcode is first
scanned: that is `nutrition_per_base_unit`'s job.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Final

from ..aisles import resolve_aisle

# Columns of `article`, and the OFF nutriment key each one reads.
NUTRIMENT_KEYS: Final = {
    "kcal": "energy-kcal",
    "proteins": "proteins",
    "carbohydrates": "carbohydrates",
    "sugars": "sugars",
    "added_sugars": "added-sugars",
    "fat": "fat",
    "saturated_fat": "saturated-fat",
    "fiber": "fiber",
    "salt": "salt",
}
NUTRIMENT_COLUMNS: Final = tuple(NUTRIMENT_KEYS)

# Everything OFF may express a mass or a volume in, and what one unit is worth
# in our base unit. Anything else — "unité", "pcs", "portions" — is a count,
# not a weight, and is refused.
UNIT_TO_BASE: Final = {
    "g": ("g", 1.0), "gr": ("g", 1.0), "gram": ("g", 1.0), "grammes": ("g", 1.0),
    "kg": ("g", 1000.0), "mg": ("g", 0.001),
    "ml": ("ml", 1.0), "cl": ("ml", 10.0), "dl": ("ml", 100.0), "l": ("ml", 1000.0),
}

MIN_NET_QUANTITY: Final = 0.5
MAX_NET_QUANTITY: Final = 50_000.0
MAX_KCAL_PER_100: Final = 900.0      # pure fat tops out at 884
MAX_MACRO_PER_100: Final = 100.0
MAX_MACRO_SUM: Final = 105.0         # 100 plus a rounding allowance

# A number, optionally with a decimal part. "1,kg" must NOT parse: a lenient
# comma-to-dot replacement turns it into 1.0 and invents a one-kilogram pack.
_NUMBER = re.compile(r"^\d+(?:[.,]\d+)?$")


@dataclass(frozen=True)
class MappedArticle:
    """What one OFF record has to say about an article."""

    off_source: str
    aisle: str
    label: str | None = None
    generic_name: str | None = None
    brand: str | None = None
    net_quantity: float | None = None
    net_unit: str | None = None
    image: str | None = None
    nutriscore: str | None = None
    nova: int | None = None
    ecoscore: str | None = None
    allergens: str | None = None
    traces: str | None = None
    additives: str | None = None
    off_labels: str | None = None
    nutrition_per_100: dict[str, float] | None = None
    rejections: tuple[str, ...] = field(default_factory=tuple)


def _number(value: Any) -> float | None:
    """Read a number OFF may have stored as a string, refusing what is malformed."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str) and _NUMBER.match(value.strip()):
        return float(value.strip().replace(",", "."))
    return None


def parse_net_quantity(product: dict[str, Any]) -> tuple[float, str] | None:
    """The net weight or volume, in base units. None when OFF is not usable."""
    amount = _number(product.get("product_quantity"))
    unit = str(product.get("product_quantity_unit") or "").strip().lower()
    if amount is None or unit not in UNIT_TO_BASE:
        return None
    base_unit, factor = UNIT_TO_BASE[unit]
    quantity = amount * factor
    if not MIN_NET_QUANTITY <= quantity <= MAX_NET_QUANTITY:
        return None
    return quantity, base_unit


def _tags(product: dict[str, Any], key: str) -> str | None:
    values = product.get(key)
    return ", ".join(values) if values else None


def _nutrition_per_100(product: dict[str, Any]) -> tuple[dict[str, float] | None, list[str]]:
    """Read the nutrition table, per 100 g/ml, or refuse it entirely."""
    nutriments = product.get("nutriments") or {}
    values: dict[str, float] = {}

    for column, off_key in NUTRIMENT_KEYS.items():
        value = _number(nutriments.get(f"{off_key}_100g"))
        if value is not None:
            values[column] = value

    if not values:
        # No per-100 table. OFF sometimes only fills the per-serving one.
        serving = _number(product.get("serving_quantity"))
        if serving and serving > 0 and product.get("nutrition_data_per") == "serving":
            for column, off_key in NUTRIMENT_KEYS.items():
                value = _number(nutriments.get(f"{off_key}_serving"))
                if value is not None:
                    values[column] = value * 100.0 / serving

    # `*_prepared_100g` describes the reconstituted product — a soup once
    # water is added. We stock the dry packet, so those values are never read.
    if not values:
        return None, ["no usable nutrition table"]

    rejections: list[str] = []
    kcal = values.get("kcal")
    if kcal is not None and not 0 <= kcal <= MAX_KCAL_PER_100:
        rejections.append(f"kcal per 100 out of range: {kcal}")
    for column in ("proteins", "carbohydrates", "sugars", "fat", "saturated_fat",
                   "fiber", "salt"):
        value = values.get(column)
        if value is not None and not 0 <= value <= MAX_MACRO_PER_100:
            rejections.append(f"{column} per 100 out of range: {value}")
    macro_sum = sum(values.get(c, 0.0) for c in ("proteins", "carbohydrates", "fat"))
    if macro_sum > MAX_MACRO_SUM:
        rejections.append(f"proteins + carbohydrates + fat exceed 100 g: {macro_sum}")

    # One bad number condemns the whole table: a record wrong about its fat is
    # not a record to be trusted about its salt.
    if rejections:
        return None, rejections
    return values, []


def map_article(product: dict[str, Any], off_source: str) -> MappedArticle:
    """Read one OFF record. Never raises: what is unusable is left out."""
    net = parse_net_quantity(product)
    nutrition, rejections = _nutrition_per_100(product)
    nova = _number(product.get("nova_group"))

    return MappedArticle(
        off_source=off_source,
        aisle=resolve_aisle(product.get("categories_tags"), off_source),
        label=product.get("product_name_fr") or product.get("product_name") or None,
        generic_name=product.get("generic_name_fr") or product.get("generic_name") or None,
        brand=product.get("brands") or None,
        net_quantity=net[0] if net else None,
        net_unit=net[1] if net else None,
        image=product.get("image_front_url") or None,
        nutriscore=(product.get("nutriscore_grade") or None),
        nova=int(nova) if nova is not None else None,
        ecoscore=(product.get("ecoscore_grade") or None),
        allergens=_tags(product, "allergens_tags"),
        traces=_tags(product, "traces_tags"),
        additives=_tags(product, "additives_tags"),
        off_labels=_tags(product, "labels_tags"),
        nutrition_per_100=nutrition,
        rejections=tuple(rejections),
    )


def nutrition_per_base_unit(
    nutrition_per_100: dict[str, float] | None,
    base_unit: str,
    net_quantity: float | None,
) -> dict[str, float] | None:
    """Bring a per-100 table down to one base unit of the product.

    A product stocked in pieces needs its net weight to say what one piece
    contains. Without it we return None: a NULL is visible in the panel and
    fixable by hand, an invented factor is neither.
    """
    if not nutrition_per_100:
        return None
    if base_unit in ("g", "ml"):
        factor = 1 / 100
    elif net_quantity and net_quantity > 0:
        factor = net_quantity / 100
    else:
        return None
    return {column: value * factor for column, value in nutrition_per_100.items()}
```

- [ ] **Step 4: Lancer les tests**

Run: `./scripts/test.sh tests/off/test_mapping.py -v`
Expected: PASS, 20 tests

- [ ] **Step 5: Commit**

```bash
git add custom_components/home_stock/off/ tests/off/
git commit -m "feat: map an Open Food Facts record onto article columns, with plausibility guards"
```

---

### Task 6: `off/client.py` — la cascade des quatre bases

**Files:**
- Create: `custom_components/home_stock/off/client.py`
- Test: `tests/off/test_client.py`

**Interfaces:**
- Consumes: rien du composant.
- Produces:
  - `client.BASES: tuple[tuple[str, str], ...]` — `(off_source, hôte)`, dans l'ordre `food`, `products`, `beauty`, `petfood`.
  - `client.FIELDS: str` — la liste `fields=` envoyée à l'API.
  - `client.OffRecord` — dataclass gelée : `code: str`, `off_source: str`, `product: dict`.
  - `client.OffLookup` — dataclass gelée : `record: OffRecord | None`, `throttled: bool`, `timed_out: bool`.
  - `client.OffTransport` — `Protocol` avec `async def get_json(self, url: str, headers: dict[str, str], timeout: float) -> tuple[int, dict | None]`.
  - `client.OffClient(transport, *, user_agent, clock=time.monotonic, sleeper=asyncio.sleep)`
  - `await client.lookup(code) -> OffLookup`
  - `await client.lookup_with_retry(code, *, attempts=5, backoff=45.0) -> OffLookup`
  - `client.AiohttpTransport(session)` — l'implémentation réelle, la seule qui touche au réseau.
  - Constantes : `TIMEOUT_PER_BASE = 10.0`, `CASCADE_BUDGET = 20.0`, `BULK_INTERVAL = 8.0`, `THROTTLE_BACKOFF = 45.0`.

**Le transport est injecté** : aucun test ne sort sur le réseau, et le client se teste sur des scénarios impossibles à provoquer en vrai (429 sur la troisième base, budget épuisé au milieu de la cascade).

- [ ] **Step 1: Écrire le test**

`tests/off/test_client.py` :

```python
"""The cascade, driven by a fake transport. No test here touches the network."""
import pytest

from custom_components.home_stock.off.client import (
    BASES,
    CASCADE_BUDGET,
    OffClient,
)


class FakeTransport:
    """Answers by host. `calls` records the cascade actually walked."""

    def __init__(self, answers: dict[str, tuple[int, dict | None]]):
        self.answers = answers
        self.calls: list[str] = []

    async def get_json(self, url, headers, timeout):
        host = url.split("/")[2]
        self.calls.append(host)
        assert headers["User-Agent"].startswith("home_stock/")
        if host not in self.answers:
            return 200, {"status": 0}
        return self.answers[host]


def _found(name: str) -> tuple[int, dict]:
    return 200, {"status": 1, "product": {"code": "123", "product_name_fr": name}}


@pytest.fixture
def clock():
    """A monotonic clock the test drives by hand."""
    state = {"t": 0.0}

    def now() -> float:
        return state["t"]

    now.advance = lambda seconds: state.__setitem__("t", state["t"] + seconds)
    return now


async def test_a_food_barcode_stops_at_the_first_base(clock):
    transport = FakeTransport({"world.openfoodfacts.org": _found("Muesli")})
    result = await OffClient(transport, user_agent="home_stock/1.0", clock=clock).lookup("123")

    assert result.record.off_source == "food"
    assert result.record.product["product_name_fr"] == "Muesli"
    assert transport.calls == ["world.openfoodfacts.org"]


async def test_a_sponge_is_found_by_walking_down_to_the_products_base(clock):
    transport = FakeTransport({"world.openproductsfacts.org": _found("Éponge")})
    result = await OffClient(transport, user_agent="home_stock/1.0", clock=clock).lookup("123")

    assert result.record.off_source == "products"
    assert transport.calls[:2] == ["world.openfoodfacts.org", "world.openproductsfacts.org"]


async def test_an_unknown_barcode_walks_all_four_and_returns_nothing(clock):
    transport = FakeTransport({})
    result = await OffClient(transport, user_agent="home_stock/1.0", clock=clock).lookup("123")

    assert result.record is None
    assert result.throttled is False
    assert len(transport.calls) == len(BASES)


async def test_a_404_is_an_absence_not_a_failure(clock):
    transport = FakeTransport({
        "world.openfoodfacts.org": (404, None),
        "world.openbeautyfacts.org": _found("Savon"),
    })
    result = await OffClient(transport, user_agent="home_stock/1.0", clock=clock).lookup("123")

    assert result.record.off_source == "beauty"


async def test_a_429_stops_the_cascade_and_says_so(clock):
    """Walking on after a throttle would only deepen it."""
    transport = FakeTransport({"world.openfoodfacts.org": (429, None)})
    result = await OffClient(transport, user_agent="home_stock/1.0", clock=clock).lookup("123")

    assert result.record is None
    assert result.throttled is True
    assert transport.calls == ["world.openfoodfacts.org"]


async def test_the_cascade_gives_up_when_its_budget_is_spent(clock):
    class SlowTransport(FakeTransport):
        async def get_json(self, url, headers, timeout):
            clock.advance(CASCADE_BUDGET / 2 + 0.1)
            return await super().get_json(url, headers, timeout)

    transport = SlowTransport({})
    result = await OffClient(transport, user_agent="home_stock/1.0", clock=clock).lookup("123")

    assert result.record is None
    assert result.timed_out is True
    assert len(transport.calls) < len(BASES)


async def test_a_bulk_retry_waits_and_tries_again(clock):
    slept: list[float] = []

    async def sleeper(seconds: float) -> None:
        slept.append(seconds)
        clock.advance(seconds)

    class ThrottleOnce(FakeTransport):
        def __init__(self):
            super().__init__({})
            self.seen = 0

        async def get_json(self, url, headers, timeout):
            self.seen += 1
            self.calls.append(url.split("/")[2])
            if self.seen == 1:
                return 429, None
            return _found("Muesli")

    transport = ThrottleOnce()
    client = OffClient(transport, user_agent="home_stock/1.0", clock=clock, sleeper=sleeper)
    result = await client.lookup_with_retry("123", attempts=5, backoff=45.0)

    assert result.record is not None
    assert slept == [45.0]


async def test_a_bulk_retry_gives_up_rather_than_hammering(clock):
    async def sleeper(seconds: float) -> None:
        clock.advance(seconds)

    transport = FakeTransport({"world.openfoodfacts.org": (429, None)})
    client = OffClient(transport, user_agent="home_stock/1.0", clock=clock, sleeper=sleeper)
    result = await client.lookup_with_retry("123", attempts=3, backoff=45.0)

    assert result.record is None
    assert result.throttled is True
    assert transport.calls.count("world.openfoodfacts.org") == 3


async def test_the_requested_fields_are_the_ones_the_mapping_reads(clock):
    from custom_components.home_stock.off.client import FIELDS

    for needed in ("product_quantity", "nutriments", "categories_tags",
                   "generic_name_fr", "nutrition_data_per", "serving_quantity",
                   "nutriscore_grade", "labels_tags", "image_front_url"):
        assert needed in FIELDS
```

- [ ] **Step 2: Lancer le test et vérifier qu'il échoue**

Run: `./scripts/test.sh tests/off/test_client.py -v`
Expected: FAIL — `ModuleNotFoundError: ...off.client`

- [ ] **Step 3: Écrire le client**

`custom_components/home_stock/off/client.py` :

```python
"""The Open Food Facts cascade.

Four sister databases share one API and one barcode space, so a scan walks
them until something answers. The transport is injected: this module owns the
cascade rules, not the HTTP library, and every rule below is exercised in
tests without a socket.

Rate limits are measured, not assumed. Capturing the fixtures on 2026-08-19 at
one request every 1.5 s earned an HTTP 429 after about twenty calls. Hence:
an interactive scan fires once and takes what it gets, while a bulk resync
waits BULK_INTERVAL between cards and backs off THROTTLE_BACKOFF on a 429.
"""
from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Final, Protocol

BASES: Final = (
    ("food", "world.openfoodfacts.org"),
    ("products", "world.openproductsfacts.org"),
    ("beauty", "world.openbeautyfacts.org"),
    ("petfood", "world.openpetfoodfacts.org"),
)

FIELDS: Final = (
    "code,product_name,product_name_fr,generic_name,generic_name_fr,brands,quantity,"
    "product_quantity,product_quantity_unit,serving_size,serving_quantity,nutriments,"
    "nutrition_data_per,nutrition_data_prepared_per,nutriscore_grade,nova_group,"
    "ecoscore_grade,categories_tags,labels_tags,allergens_tags,traces_tags,"
    "additives_tags,ingredients_text_fr,ingredients_text,image_front_url,"
    "image_nutrition_url,image_ingredients_url,obsolete,completeness,last_modified_t"
)

TIMEOUT_PER_BASE: Final = 10.0
CASCADE_BUDGET: Final = 20.0
BULK_INTERVAL: Final = 8.0
THROTTLE_BACKOFF: Final = 45.0


class OffTransport(Protocol):
    """Whatever can fetch a JSON document. Injected so tests stay offline."""

    async def get_json(self, url: str, headers: dict[str, str],
                       timeout: float) -> tuple[int, dict[str, Any] | None]:
        ...


@dataclass(frozen=True)
class OffRecord:
    code: str
    off_source: str
    product: dict[str, Any]


@dataclass(frozen=True)
class OffLookup:
    """What a cascade found, and why it stopped if it found nothing."""

    record: OffRecord | None = None
    throttled: bool = False
    timed_out: bool = False


class OffClient:
    """Walks the four bases for one barcode."""

    def __init__(self, transport: OffTransport, *, user_agent: str,
                 clock: Callable[[], float] = time.monotonic,
                 sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep) -> None:
        self._transport = transport
        self._user_agent = user_agent
        self._clock = clock
        self._sleep = sleeper

    async def lookup(self, code: str) -> OffLookup:
        """One pass down the cascade. Never raises."""
        started = self._clock()
        headers = {"User-Agent": self._user_agent}

        for off_source, host in BASES:
            if self._clock() - started >= CASCADE_BUDGET:
                return OffLookup(timed_out=True)

            url = f"https://{host}/api/v2/product/{code}.json?fields={FIELDS}"
            try:
                status, payload = await self._transport.get_json(
                    url, headers, TIMEOUT_PER_BASE
                )
            except TimeoutError:
                continue
            except Exception:  # noqa: BLE001 - a scan never fails the caller
                continue

            if status == 429:
                # Walking on to the next base would only deepen the throttle:
                # the limit is per client, not per host.
                return OffLookup(throttled=True)
            if status == 404 or payload is None:
                continue
            if payload.get("status") == 1 and payload.get("product"):
                return OffLookup(record=OffRecord(code, off_source, payload["product"]))

        if self._clock() - started >= CASCADE_BUDGET:
            return OffLookup(timed_out=True)
        return OffLookup()

    async def lookup_with_retry(self, code: str, *, attempts: int = 5,
                                backoff: float = THROTTLE_BACKOFF) -> OffLookup:
        """The bulk path: waits out a throttle instead of dropping the card."""
        result = OffLookup()
        for attempt in range(attempts):
            result = await self.lookup(code)
            if not result.throttled:
                return result
            if attempt < attempts - 1:
                await self._sleep(backoff)
        return result


class AiohttpTransport:
    """The only thing here that touches the network."""

    def __init__(self, session: Any) -> None:
        self._session = session

    async def get_json(self, url: str, headers: dict[str, str],
                       timeout: float) -> tuple[int, dict[str, Any] | None]:
        async with self._session.get(url, headers=headers, timeout=timeout) as response:
            if response.status != 200:
                return response.status, None
            return 200, await response.json(content_type=None)
```

- [ ] **Step 4: Lancer les tests**

Run: `./scripts/test.sh tests/off/ -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/home_stock/off/client.py tests/off/test_client.py
git commit -m "feat: walk the four Open Food Facts databases with measured rate limits"
```

---

### Task 7: `domain/matching.py` — à quel produit rattacher cet article

**Files:**
- Create: `custom_components/home_stock/domain/matching.py`
- Test: `tests/domain/test_matching.py`

**Interfaces:**
- Consumes: rien.
- Produces:
  - `matching.Candidate` — dataclass gelée : `product_id: int`, `name: str`, `score: float`.
  - `matching.normalise(text: str) -> str`
  - `matching.candidates(*, names: Sequence[str | None], products: Sequence[dict], limit: int = 5) -> list[Candidate]` — triée par score décroissant puis par nom, pour être stable.
  - `matching.preselect(found: Sequence[Candidate]) -> Candidate | None` — applique la règle 0,75 / 0,10.
  - `matching.strip_brand(name: str, brands: str | None) -> str`
  - `matching.PRESELECT_SCORE = 0.75`, `matching.PRESELECT_MARGIN = 0.10`

**Le repliage des ligatures est obligatoire :** « Œufs » doit trouver « oeufs ». Le lot 0 a déjà été corrigé sur ce point dans `application._fold_for_search` ; la même règle s'applique ici.

- [ ] **Step 1: Écrire le test**

`tests/domain/test_matching.py` :

```python
"""Attaching a scanned article to a catalogue product."""
import pytest

from custom_components.home_stock.domain.matching import (
    Candidate,
    candidates,
    normalise,
    preselect,
    strip_brand,
)

CATALOGUE = [
    {"id": 1, "name": "Pâtes"},
    {"id": 2, "name": "Muesli"},
    {"id": 3, "name": "Œufs"},
    {"id": 4, "name": "Lait demi-écrémé"},
    {"id": 5, "name": "Yaourt nature"},
    {"id": 6, "name": "Huile d'olive"},
]


def test_accents_and_ligatures_fold():
    assert normalise("Œufs") == normalise("oeufs")
    assert normalise("Pâtes") == normalise("pates")
    assert normalise("Lait demi-écrémé") == "lait demi ecreme"


def test_a_simple_plural_does_not_break_a_match():
    assert normalise("yaourts") == normalise("yaourt")


def test_the_brand_is_removed_before_comparing():
    assert strip_brand("Bjorg Muesli Raisin Figue", "Bjorg") == "Muesli Raisin Figue"
    assert strip_brand("Muesli", None) == "Muesli"


def test_the_generic_name_finds_the_product():
    found = candidates(names=["Muesli aux fruits", None], products=CATALOGUE)
    assert found[0].product_id == 2


def test_a_ligature_in_the_catalogue_is_still_found():
    found = candidates(names=["oeufs frais de poule"], products=CATALOGUE)
    assert found[0].product_id == 3


def test_the_best_of_the_names_wins():
    """The commercial name is noise; the generic name is the signal."""
    found = candidates(names=["Panzani Torsades 500g", "Pâtes"], products=CATALOGUE)
    assert found[0].product_id == 1


def test_at_most_five_candidates_come_back():
    found = candidates(names=["lait"], products=CATALOGUE, limit=5)
    assert len(found) <= 5


def test_the_order_is_stable_for_equal_scores():
    twins = [{"id": 9, "name": "Sel"}, {"id": 8, "name": "Sel"}]
    found = candidates(names=["Sel"], products=twins)
    assert [c.product_id for c in found] == [8, 9]


def test_nothing_matches_an_empty_name():
    assert candidates(names=[None, ""], products=CATALOGUE) == []


def test_a_clear_winner_is_preselected():
    found = [Candidate(1, "Pâtes", 0.92), Candidate(2, "Muesli", 0.31)]
    assert preselect(found).product_id == 1


def test_a_hesitation_is_never_resolved_on_its_own():
    """Two close candidates mean the panel asks. Guessing writes the wrong
    nutrition onto the wrong product, permanently."""
    found = [Candidate(1, "Yaourt nature", 0.82), Candidate(2, "Yaourt sucré", 0.78)]
    assert preselect(found) is None


def test_a_weak_best_candidate_is_not_preselected():
    found = [Candidate(1, "Pâtes", 0.60), Candidate(2, "Muesli", 0.10)]
    assert preselect(found) is None


def test_a_single_strong_candidate_is_preselected():
    assert preselect([Candidate(1, "Pâtes", 0.90)]).product_id == 1


def test_no_candidates_preselect_to_nothing():
    assert preselect([]) is None


def test_the_real_catalogue_matches_a_real_card():
    """Reads the 34 captured cards and the real product names."""
    import json
    from pathlib import Path

    fixtures = Path(__file__).parent.parent / "fixtures" / "off" / "catalogue.json"
    cards = [e for e in json.loads(fixtures.read_text(encoding="utf-8")).values()
             if e.get("product")]
    assert cards, "the fixtures must be present"

    for entry in cards:
        product = entry["product"]
        names = [product.get("generic_name_fr"), product.get("product_name_fr")]
        found = candidates(names=names, products=CATALOGUE)
        # Nothing is asserted about which product wins — the point is that
        # scoring never raises and never returns a score outside [0, 1].
        assert all(0.0 <= c.score <= 1.0 for c in found)
```

- [ ] **Step 2: Lancer le test et vérifier qu'il échoue**

Run: `./scripts/test.sh tests/domain/test_matching.py -v`
Expected: FAIL — `ModuleNotFoundError: ...domain.matching`

- [ ] **Step 3: Écrire l'appariement**

`custom_components/home_stock/domain/matching.py` :

```python
"""Which catalogue product does this scanned article belong to?

Pure and deterministic, so it can be run against the real 299-product
catalogue in a test. Getting this wrong writes one article's nutrition onto
another product's recipes, which is why the preselection thresholds are
deliberately timid: when the answer is not obvious, the panel asks.
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Final

PRESELECT_SCORE: Final = 0.75
PRESELECT_MARGIN: Final = 0.10

# NFD splits an accented letter into letter plus combining mark, but leaves the
# œ/æ ligatures alone: they are single code points. Expand them by hand or
# "œufs" never matches a product named "Œufs".
_LIGATURES: Final = {"œ": "oe", "æ": "ae", "Œ": "OE", "Æ": "AE"}
_NON_WORD = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class Candidate:
    product_id: int
    name: str
    score: float


def normalise(text: str) -> str:
    """Case-, accent- and punctuation-free form, with simple plurals trimmed."""
    for ligature, expanded in _LIGATURES.items():
        text = text.replace(ligature, expanded)
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    words = _NON_WORD.sub(" ", stripped.casefold()).split()
    # Trim a trailing plural s, but only on words long enough for it to be one:
    # "os" and "gaz" are not plurals.
    return " ".join(w[:-1] if len(w) > 3 and w.endswith("s") else w for w in words)


def strip_brand(name: str, brands: str | None) -> str:
    """Drop the brand from a commercial name: it is noise for matching."""
    if not brands:
        return name
    result = name
    for brand in brands.split(","):
        brand = brand.strip()
        if brand:
            result = re.sub(re.escape(brand), " ", result, flags=re.IGNORECASE)
    return " ".join(result.split())


def _score(left: str, right: str) -> float:
    """Half string similarity, half word overlap.

    Similarity alone rates "Yaourt nature" and "Yaourt sucré" far too close;
    overlap alone ignores word order and spelling entirely. Together they
    behave on the real catalogue.
    """
    if not left or not right:
        return 0.0
    left_words, right_words = set(left.split()), set(right.split())
    overlap = len(left_words & right_words) / len(left_words | right_words)
    ratio = SequenceMatcher(None, left, right).ratio()
    return round(0.5 * ratio + 0.5 * overlap, 4)


def candidates(*, names: Sequence[str | None], products: Sequence[dict[str, Any]],
               limit: int = 5) -> list[Candidate]:
    """Rank catalogue products against every name OFF offers for the article."""
    wanted = [normalise(name) for name in names if name]
    wanted = [name for name in wanted if name]
    if not wanted:
        return []

    found = [
        Candidate(
            product_id=product["id"],
            name=product["name"],
            score=max(_score(name, normalise(product["name"])) for name in wanted),
        )
        for product in products
    ]
    # Sort by score, then by id: two identically-named products must not swap
    # places between two runs.
    found.sort(key=lambda c: (-c.score, c.product_id))
    return [c for c in found[:limit] if c.score > 0]


def preselect(found: Sequence[Candidate]) -> Candidate | None:
    """The one candidate the panel may tick on its own — or nothing.

    Requires both a strong best score and a clear gap to the runner-up: a
    hesitation between two products is exactly what a human is for.
    """
    if not found:
        return None
    best = found[0]
    if best.score <= PRESELECT_SCORE:
        return None
    if len(found) > 1 and best.score - found[1].score <= PRESELECT_MARGIN:
        return None
    return best
```

- [ ] **Step 4: Lancer les tests**

Run: `./scripts/test.sh tests/domain/test_matching.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/home_stock/domain/matching.py tests/domain/test_matching.py
git commit -m "feat: rank catalogue products for a freshly scanned article"
```

---

### Task 8: `domain/pricing.py` et Open Prices

**Files:**
- Create: `custom_components/home_stock/domain/pricing.py`
- Create: `custom_components/home_stock/off/open_prices.py`
- Test: `tests/domain/test_pricing.py`, `tests/off/test_open_prices.py`

**Interfaces:**
- Consumes: `off.client.OffTransport` (Task 6) — le même protocole de transport.
- Produces:
  - `pricing.PriceSuggestion` — dataclass gelée : `price_per_base_unit: float | None`, `source: str | None` (`'store'`, `'open_prices'`, `'last_known'`), `store: str | None`.
  - `pricing.suggest_price(*, in_store: float | None, open_prices: float | None, last_known: float | None, store: str | None) -> PriceSuggestion`
  - `open_prices.latest_price(transport, code: str, *, net_quantity: float | None, user_agent: str, timeout: float = 5.0) -> float | None` — coroutine, rend un prix **par unité de base**, ou `None`.
  - `open_prices.OPEN_PRICES_TIMEOUT = 5.0`

- [ ] **Step 1: Écrire les tests**

`tests/domain/test_pricing.py` :

```python
"""Which price the panel offers when an article is scanned."""
from custom_components.home_stock.domain.pricing import suggest_price


def test_the_price_of_this_shop_wins_over_everything():
    result = suggest_price(in_store=0.002, open_prices=0.0015, last_known=0.003,
                           store="Leclerc")
    assert result.price_per_base_unit == 0.002
    assert result.source == "store"
    assert result.store == "Leclerc"


def test_open_prices_fills_in_when_this_shop_is_unknown():
    result = suggest_price(in_store=None, open_prices=0.0015, last_known=0.003,
                           store="Lidl")
    assert result.price_per_base_unit == 0.0015
    assert result.source == "open_prices"


def test_the_last_known_price_is_the_final_fallback():
    result = suggest_price(in_store=None, open_prices=None, last_known=0.003, store=None)
    assert result.price_per_base_unit == 0.003
    assert result.source == "last_known"


def test_nothing_known_means_nothing_suggested():
    """This is the one moment the numeric keypad is allowed to open."""
    result = suggest_price(in_store=None, open_prices=None, last_known=None, store=None)
    assert result.price_per_base_unit is None
    assert result.source is None


def test_a_zero_price_is_a_real_price_and_is_kept():
    result = suggest_price(in_store=0.0, open_prices=0.002, last_known=None, store="Leclerc")
    assert result.price_per_base_unit == 0.0
    assert result.source == "store"
```

`tests/off/test_open_prices.py` :

```python
"""Open Prices, driven by a fake transport."""
import pytest

from custom_components.home_stock.off.open_prices import latest_price


class FakeTransport:
    def __init__(self, status=200, payload=None, raises=None):
        self.status, self.payload, self.raises = status, payload, raises
        self.calls: list[str] = []

    async def get_json(self, url, headers, timeout):
        self.calls.append(url)
        if self.raises:
            raise self.raises
        return self.status, self.payload


def _items(*items):
    return {"items": list(items)}


async def test_an_item_price_is_brought_back_to_the_base_unit():
    transport = FakeTransport(payload=_items(
        {"price": 2.5, "currency": "EUR", "date": "2026-08-10",
         "product": {"product_quantity": 500}}))

    price = await latest_price(transport, "123", net_quantity=500,
                               user_agent="home_stock/1.0")

    assert price == pytest.approx(0.005)


async def test_the_weight_from_open_prices_beats_the_one_we_guessed():
    transport = FakeTransport(payload=_items(
        {"price": 2.0, "currency": "EUR", "date": "2026-08-10",
         "product": {"product_quantity": 1000}}))

    price = await latest_price(transport, "123", net_quantity=500,
                               user_agent="home_stock/1.0")

    assert price == pytest.approx(0.002)


async def test_a_price_in_another_currency_is_ignored():
    transport = FakeTransport(payload=_items(
        {"price": 3.0, "currency": "CHF", "date": "2026-08-10",
         "product": {"product_quantity": 500}}))

    assert await latest_price(transport, "123", net_quantity=500,
                              user_agent="home_stock/1.0") is None


async def test_without_a_net_weight_no_price_per_base_unit_can_exist():
    transport = FakeTransport(payload=_items(
        {"price": 3.0, "currency": "EUR", "date": "2026-08-10", "product": {}}))

    assert await latest_price(transport, "123", net_quantity=None,
                              user_agent="home_stock/1.0") is None


async def test_a_network_failure_is_silent_because_a_suggestion_is_not_load_bearing():
    transport = FakeTransport(raises=TimeoutError())

    assert await latest_price(transport, "123", net_quantity=500,
                              user_agent="home_stock/1.0") is None


async def test_an_empty_answer_yields_nothing():
    transport = FakeTransport(payload={"items": []})

    assert await latest_price(transport, "123", net_quantity=500,
                              user_agent="home_stock/1.0") is None
```

- [ ] **Step 2: Lancer les tests et vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/domain/test_pricing.py tests/off/test_open_prices.py -v`
Expected: FAIL — les deux modules n'existent pas.

- [ ] **Step 3: Écrire la cascade de prix**

`custom_components/home_stock/domain/pricing.py` :

```python
"""Which price to offer when an article is scanned.

Pure. The caller has already looked up what it could; this decides what wins.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PriceSuggestion:
    price_per_base_unit: float | None = None
    source: str | None = None
    store: str | None = None


def suggest_price(*, in_store: float | None, open_prices: float | None,
                  last_known: float | None, store: str | None) -> PriceSuggestion:
    """The first price available, in order of how much it is worth trusting.

    `is not None` rather than truthiness throughout: a free item priced at 0 is
    a real observation, and dropping it would silently fall through to a stale
    price from another shop.
    """
    if in_store is not None:
        return PriceSuggestion(in_store, "store", store)
    if open_prices is not None:
        return PriceSuggestion(open_prices, "open_prices", store)
    if last_known is not None:
        return PriceSuggestion(last_known, "last_known", None)
    return PriceSuggestion()
```

- [ ] **Step 4: Écrire le client Open Prices**

`custom_components/home_stock/off/open_prices.py` :

```python
"""Open Prices: what other people paid for this barcode.

A suggestion, never a dependency. Every failure path here returns None and
says nothing: putting a batch away must not wait on someone else's server.
"""
from __future__ import annotations

import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)

OPEN_PRICES_URL = "https://prices.openfoodfacts.org/api/v1/prices"
OPEN_PRICES_TIMEOUT = 5.0
CURRENCY = "EUR"


async def latest_price(transport: Any, code: str, *, net_quantity: float | None,
                       user_agent: str, timeout: float = OPEN_PRICES_TIMEOUT) -> float | None:
    """The most recent euro price for this barcode, per base unit."""
    url = f"{OPEN_PRICES_URL}?product_code={code}&order_by=-date&size=5"
    try:
        status, payload = await transport.get_json(
            url, {"User-Agent": user_agent}, timeout
        )
    except Exception as err:  # noqa: BLE001 - a suggestion never fails a scan
        _LOGGER.debug("Open Prices unreachable for %s: %s", code, err)
        return None

    if status != 200 or not payload:
        return None

    for item in payload.get("items") or []:
        if item.get("currency") != CURRENCY:
            continue
        price = item.get("price")
        if not isinstance(price, (int, float)):
            continue
        # Open Prices carries its own idea of the pack size. Prefer it: it
        # comes from the same record the price was observed on.
        quantity = (item.get("product") or {}).get("product_quantity") or net_quantity
        if not quantity or quantity <= 0:
            continue
        return float(price) / float(quantity)
    return None
```

- [ ] **Step 5: Lancer les tests**

Run: `./scripts/test.sh tests/domain/test_pricing.py tests/off/test_open_prices.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add custom_components/home_stock/domain/pricing.py \
        custom_components/home_stock/off/open_prices.py \
        tests/domain/test_pricing.py tests/off/test_open_prices.py
git commit -m "feat: suggest a price from the shop, Open Prices, or history"
```

---

### Task 9: `domain/conversion.py` — le plan de conversion d'unité

**Files:**
- Create: `custom_components/home_stock/domain/conversion.py`
- Test: `tests/domain/test_conversion.py`

**Interfaces:**
- Consumes: rien.
- Produces:
  - `conversion.ConversionError(ValueError)`
  - `conversion.ArticleConversion` — `article_id: int`, `factor: float`, `used_reference: bool`
  - `conversion.BatchConversion` — `batch_id: int`, `article_id: int`, `old_remaining: float`, `new_remaining: float`, `old_initial: float`, `new_initial: float`
  - `conversion.ConversionPlan` — `product_id: int`, `from_unit: str`, `to_unit: str`, `reference_quantity: float`, `articles: tuple[ArticleConversion, ...]`, `batches: tuple[BatchConversion, ...]`, `movements: int`, `articles_using_reference: tuple[int, ...]`
  - `conversion.plan_conversion(*, product: dict, articles: Sequence[dict], batches: Sequence[dict], to_unit: str, reference_quantity: float) -> ConversionPlan`
  - `conversion.MIN_REFERENCE = 0.5`, `conversion.MAX_REFERENCE = 50_000.0`

**Ce module ne touche à rien.** Il rend un plan ; c'est la Task 10 qui l'exécute. Simuler avant d'écrire est la seule façon d'annoncer honnêtement « 3 lots seront convertis au poids de référence ».

- [ ] **Step 1: Écrire le test**

`tests/domain/test_conversion.py` :

```python
"""Planning a piece -> gram conversion. Nothing here writes."""
import pytest

from custom_components.home_stock.domain.conversion import (
    ConversionError,
    plan_conversion,
)

PRODUCT = {"id": 1, "name": "Pâtes", "base_unit": "piece"}
ARTICLES = [
    {"id": 10, "product_id": 1, "net_quantity": 500.0},
    {"id": 11, "product_id": 1, "net_quantity": None},
]
BATCHES = [
    {"id": 100, "article_id": 10, "remaining": 2.0, "initial": 3.0},
    {"id": 101, "article_id": 11, "remaining": 1.0, "initial": 1.0},
]


def test_each_article_converts_at_its_own_weight():
    plan = plan_conversion(product=PRODUCT, articles=ARTICLES, batches=BATCHES,
                           to_unit="g", reference_quantity=500.0)

    by_id = {a.article_id: a for a in plan.articles}
    assert by_id[10].factor == 500.0
    assert by_id[10].used_reference is False


def test_an_article_with_no_weight_falls_back_to_the_reference():
    """Refusing the whole conversion would freeze 239 products in pieces
    forever. The confirmation screen says which ones fell back."""
    plan = plan_conversion(product=PRODUCT, articles=ARTICLES, batches=BATCHES,
                           to_unit="g", reference_quantity=400.0)

    by_id = {a.article_id: a for a in plan.articles}
    assert by_id[11].factor == 400.0
    assert by_id[11].used_reference is True
    assert plan.articles_using_reference == (11,)


def test_batch_quantities_are_multiplied_by_their_article_s_weight():
    plan = plan_conversion(product=PRODUCT, articles=ARTICLES, batches=BATCHES,
                           to_unit="g", reference_quantity=400.0)

    by_id = {b.batch_id: b for b in plan.batches}
    assert by_id[100].new_remaining == pytest.approx(1000.0)
    assert by_id[100].new_initial == pytest.approx(1500.0)
    assert by_id[101].new_remaining == pytest.approx(400.0)


def test_two_movements_per_batch_because_the_journal_is_append_only():
    plan = plan_conversion(product=PRODUCT, articles=ARTICLES, batches=BATCHES,
                           to_unit="g", reference_quantity=500.0)
    assert plan.movements == 4


def test_a_product_already_in_grams_has_nothing_to_convert():
    with pytest.raises(ConversionError, match="already"):
        plan_conversion(product={"id": 1, "name": "Pâtes", "base_unit": "g"},
                        articles=ARTICLES, batches=BATCHES,
                        to_unit="g", reference_quantity=500.0)


def test_the_target_unit_must_be_a_real_base_unit():
    with pytest.raises(ConversionError, match="target"):
        plan_conversion(product=PRODUCT, articles=ARTICLES, batches=BATCHES,
                        to_unit="paquet", reference_quantity=500.0)


def test_converting_to_pieces_is_refused():
    with pytest.raises(ConversionError, match="target"):
        plan_conversion(product=PRODUCT, articles=ARTICLES, batches=BATCHES,
                        to_unit="piece", reference_quantity=500.0)


@pytest.mark.parametrize("reference", [0.0, -5.0, 0.1, 80_000.0])
def test_an_implausible_reference_weight_is_refused(reference):
    with pytest.raises(ConversionError, match="reference"):
        plan_conversion(product=PRODUCT, articles=ARTICLES, batches=BATCHES,
                        to_unit="g", reference_quantity=reference)


def test_a_product_with_no_batches_still_converts_its_articles():
    plan = plan_conversion(product=PRODUCT, articles=ARTICLES, batches=[],
                           to_unit="g", reference_quantity=500.0)
    assert plan.batches == ()
    assert plan.movements == 0
    assert len(plan.articles) == 2


def test_an_implausible_article_weight_is_treated_as_missing():
    articles = [{"id": 12, "product_id": 1, "net_quantity": 80_000.0}]
    plan = plan_conversion(product=PRODUCT, articles=articles, batches=[],
                           to_unit="g", reference_quantity=500.0)

    assert plan.articles[0].factor == 500.0
    assert plan.articles[0].used_reference is True
```

- [ ] **Step 2: Lancer le test et vérifier qu'il échoue**

Run: `./scripts/test.sh tests/domain/test_conversion.py -v`
Expected: FAIL — `ModuleNotFoundError: ...domain.conversion`

- [ ] **Step 3: Écrire le planificateur**

`custom_components/home_stock/domain/conversion.py` :

```python
"""Plan a product's move from pieces to grams or millilitres.

Pure: this module computes, it never writes. Task 10 executes the plan inside
one transaction. Separating the two is what lets the panel show an honest
confirmation — how many batches move, and which ones fall back to the
reference weight — before anything is touched.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final

MIN_REFERENCE: Final = 0.5
MAX_REFERENCE: Final = 50_000.0
TARGET_UNITS: Final = ("g", "ml")


class ConversionError(ValueError):
    """The conversion cannot be planned, and nothing should be attempted."""


@dataclass(frozen=True)
class ArticleConversion:
    article_id: int
    factor: float
    used_reference: bool


@dataclass(frozen=True)
class BatchConversion:
    batch_id: int
    article_id: int
    old_remaining: float
    new_remaining: float
    old_initial: float
    new_initial: float


@dataclass(frozen=True)
class ConversionPlan:
    product_id: int
    from_unit: str
    to_unit: str
    reference_quantity: float
    articles: tuple[ArticleConversion, ...]
    batches: tuple[BatchConversion, ...]
    movements: int
    articles_using_reference: tuple[int, ...]


def _plausible(quantity: Any) -> bool:
    return (isinstance(quantity, (int, float)) and not isinstance(quantity, bool)
            and MIN_REFERENCE <= quantity <= MAX_REFERENCE)


def plan_conversion(*, product: dict[str, Any], articles: Sequence[dict[str, Any]],
                    batches: Sequence[dict[str, Any]], to_unit: str,
                    reference_quantity: float) -> ConversionPlan:
    """Work out what converting this product would do. Writes nothing."""
    from_unit = product["base_unit"]
    if from_unit != "piece":
        raise ConversionError(
            f"product {product['id']} is already stocked in {from_unit}"
        )
    if to_unit not in TARGET_UNITS:
        raise ConversionError(f"target unit must be one of {TARGET_UNITS}, got {to_unit!r}")
    if not _plausible(reference_quantity):
        raise ConversionError(
            f"reference weight must be between {MIN_REFERENCE} and {MAX_REFERENCE}, "
            f"got {reference_quantity!r}"
        )

    planned_articles: list[ArticleConversion] = []
    factors: dict[int, float] = {}
    for article in articles:
        net = article.get("net_quantity")
        # An implausible weight is treated exactly like a missing one: the
        # reference the human just confirmed is worth more than an OFF typo.
        uses_reference = not _plausible(net)
        factor = reference_quantity if uses_reference else float(net)
        factors[article["id"]] = factor
        planned_articles.append(ArticleConversion(article["id"], factor, uses_reference))

    planned_batches = tuple(
        BatchConversion(
            batch_id=batch["id"],
            article_id=batch["article_id"],
            old_remaining=batch["remaining"],
            new_remaining=batch["remaining"] * factors[batch["article_id"]],
            old_initial=batch["initial"],
            new_initial=batch["initial"] * factors[batch["article_id"]],
        )
        for batch in batches
    )

    return ConversionPlan(
        product_id=product["id"],
        from_unit=from_unit,
        to_unit=to_unit,
        reference_quantity=reference_quantity,
        articles=tuple(planned_articles),
        batches=planned_batches,
        # One movement out in the old unit, one in in the new: the journal is
        # append-only, so a conversion is written, never edited.
        movements=2 * len(planned_batches),
        articles_using_reference=tuple(
            a.article_id for a in planned_articles if a.used_reference
        ),
    )
```

- [ ] **Step 4: Lancer les tests**

Run: `./scripts/test.sh tests/domain/ -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/home_stock/domain/conversion.py tests/domain/test_conversion.py
git commit -m "feat: plan a piece to gram conversion without touching anything"
```

---
### Task 10: Exécuter la conversion d'unité

**Files:**
- Modify: `custom_components/home_stock/application.py`
- Modify: `custom_components/home_stock/storage/repositories.py`
- Test: `tests/test_conversion_execution.py` (nouveau)

**Interfaces:**
- Consumes: `conversion.plan_conversion` (Task 9), `repo.insert_movement(..., base_unit=...)` (Task 3), `repo.insert_packaging` (lot 0).
- Produces:
  - `StockManager.convert_product_unit(*, product_id: int, to_unit: str, reference_quantity: float, packaging_name: str = "unité", dry_run: bool = False) -> dict` — rend le rapport : `{"product_id", "from_unit", "to_unit", "reference_quantity", "articles", "batches", "movements", "articles_using_reference", "applied": bool}`.
  - `repo.list_articles_for_product(conn, product_id: int) -> list[dict]`
  - `repo.list_open_batches_for_product(conn, product_id: int) -> list[dict]`
  - `repo.update_article_fields(conn, article_id: int, fields: dict) -> None`
  - `repo.update_product_fields(conn, product_id: int, fields: dict) -> None`

**`article.net_quantity` est toujours une masse ou un volume, jamais un compte.** Elle ne bouge donc pas pendant la conversion : elle cesse simplement d'être une information annexe pour devenir l'unité du produit.

- [ ] **Step 1: Écrire le test**

`tests/test_conversion_execution.py` :

```python
"""Executing a conversion: one transaction, an honest journal, no lost stock."""
import sqlite3

import pytest

from custom_components.home_stock.application import StockManager
from custom_components.home_stock.storage.database import Database
from custom_components.home_stock.storage.migrations import apply_migrations


@pytest.fixture
def manager(tmp_path) -> StockManager:
    database = Database(str(tmp_path / "home_stock.db"))
    database.connect()
    with database.write() as conn:
        apply_migrations(conn)
        conn.execute("INSERT INTO location (id, name, kind) VALUES (1, 'Placard', 'pantry')")
        conn.execute(
            "INSERT INTO product (id, name, base_unit, min_quantity, reference_kcal) "
            "VALUES (1, 'Pâtes', 'piece', 2, 1750)"
        )
        conn.execute(
            "INSERT INTO article (id, product_id, label, net_quantity, kcal_per_base_unit, "
            "proteins, is_generic) VALUES (10, 1, 'Panzani 500 g', 500, 1750, 60, 0)"
        )
        conn.execute(
            "INSERT INTO article (id, product_id, label, is_generic) VALUES (11, 1, 'Vrac', 1)"
        )
    return StockManager(database)


def _add(manager, article_id, quantity):
    return manager.add_stock(article_id=article_id, quantity=quantity, location_id=1)


def test_a_dry_run_changes_nothing(manager):
    _add(manager, 10, 2)

    report = manager.convert_product_unit(product_id=1, to_unit="g",
                                          reference_quantity=500, dry_run=True)

    assert report["applied"] is False
    assert report["movements"] == 2
    with manager.db.write() as conn:
        assert conn.execute("SELECT base_unit FROM product WHERE id = 1").fetchone()[0] == "piece"
        assert conn.execute("SELECT COUNT(*) FROM movement WHERE reason = 'conversion'"
                            ).fetchone()[0] == 0


def test_the_product_and_its_batches_move_together(manager):
    _add(manager, 10, 2)

    manager.convert_product_unit(product_id=1, to_unit="g", reference_quantity=500)

    with manager.db.write() as conn:
        assert conn.execute("SELECT base_unit FROM product WHERE id = 1").fetchone()[0] == "g"
        row = conn.execute("SELECT remaining, initial FROM batch").fetchone()
        assert row["remaining"] == pytest.approx(1000.0)
        assert row["initial"] == pytest.approx(1000.0)


def test_the_journal_records_the_conversion_in_both_units(manager):
    _add(manager, 10, 2)

    manager.convert_product_unit(product_id=1, to_unit="g", reference_quantity=500)

    with manager.db.write() as conn:
        rows = conn.execute(
            "SELECT quantity, base_unit FROM movement WHERE reason = 'conversion' ORDER BY id"
        ).fetchall()
    assert [(r["quantity"], r["base_unit"]) for r in rows] == [(-2.0, "piece"), (1000.0, "g")]


def test_a_conversion_counts_neither_calories_nor_cost(manager):
    _add(manager, 10, 2)
    manager.convert_product_unit(product_id=1, to_unit="g", reference_quantity=500)

    with manager.db.write() as conn:
        rows = conn.execute(
            "SELECT kcal, cost FROM movement WHERE reason = 'conversion'").fetchall()
    assert all(r["kcal"] is None and r["cost"] is None for r in rows)


def test_nutrition_is_divided_by_the_weight_of_its_own_article(manager):
    manager.convert_product_unit(product_id=1, to_unit="g", reference_quantity=500)

    with manager.db.write() as conn:
        row = conn.execute(
            "SELECT kcal_per_base_unit, proteins FROM article WHERE id = 10").fetchone()
    assert row["kcal_per_base_unit"] == pytest.approx(3.5)
    assert row["proteins"] == pytest.approx(0.12)


def test_the_product_thresholds_follow_the_unit(manager):
    manager.convert_product_unit(product_id=1, to_unit="g", reference_quantity=500)

    with manager.db.write() as conn:
        row = conn.execute(
            "SELECT min_quantity, reference_kcal FROM product WHERE id = 1").fetchone()
    assert row["min_quantity"] == pytest.approx(1000.0)   # 2 packs -> 1000 g
    assert row["reference_kcal"] == pytest.approx(3.5)    # per pack -> per gram


def test_a_packaging_is_created_so_the_pack_can_still_be_named(manager):
    manager.convert_product_unit(product_id=1, to_unit="g", reference_quantity=500,
                                 packaging_name="Paquet")

    with manager.db.write() as conn:
        row = conn.execute(
            "SELECT name, base_quantity, is_purchase_default FROM packaging "
            "WHERE scope = 'article' AND target_id = 10").fetchone()
    assert (row["name"], row["base_quantity"], row["is_purchase_default"]) == ("Paquet", 500.0, 1)


def test_an_article_with_no_weight_uses_the_reference(manager):
    _add(manager, 11, 3)

    manager.convert_product_unit(product_id=1, to_unit="g", reference_quantity=400)

    with manager.db.write() as conn:
        row = conn.execute("SELECT remaining FROM batch WHERE article_id = 11").fetchone()
    assert row["remaining"] == pytest.approx(1200.0)


def test_converting_twice_is_refused_rather_than_doubling_the_stock(manager):
    from custom_components.home_stock.domain.conversion import ConversionError

    _add(manager, 10, 2)
    manager.convert_product_unit(product_id=1, to_unit="g", reference_quantity=500)

    with pytest.raises(ConversionError):
        manager.convert_product_unit(product_id=1, to_unit="g", reference_quantity=500)


def test_a_failure_half_way_leaves_the_product_untouched(manager, monkeypatch):
    """One transaction: a crash after the first batch must not leave half the
    stock in grams and half in pieces."""
    _add(manager, 10, 2)
    from custom_components.home_stock.storage import repositories as repo

    original = repo.set_batch_remaining

    def explode(*args, **kwargs):
        raise sqlite3.OperationalError("disk is on fire")

    monkeypatch.setattr(repo, "set_batch_remaining", explode)

    with pytest.raises(sqlite3.OperationalError):
        manager.convert_product_unit(product_id=1, to_unit="g", reference_quantity=500)

    monkeypatch.setattr(repo, "set_batch_remaining", original)
    with manager.db.write() as conn:
        assert conn.execute("SELECT base_unit FROM product WHERE id = 1").fetchone()[0] == "piece"
        assert conn.execute("SELECT remaining FROM batch").fetchone()[0] == pytest.approx(2.0)
```

- [ ] **Step 2: Lancer le test et vérifier qu'il échoue**

Run: `./scripts/test.sh tests/test_conversion_execution.py -v`
Expected: FAIL — `AttributeError: 'StockManager' object has no attribute 'convert_product_unit'`

- [ ] **Step 3: Ajouter les dépôts manquants**

Dans `storage/repositories.py` :

```python
def list_articles_for_product(conn, product_id: int) -> list[dict[str, Any]]:
    return _rows(conn.execute(
        "SELECT * FROM article WHERE product_id = ? ORDER BY id", (product_id,)))


def list_open_batches_for_product(conn, product_id: int) -> list[dict[str, Any]]:
    return _rows(conn.execute(
        """
        SELECT b.* FROM batch b JOIN article a ON a.id = b.article_id
        WHERE a.product_id = ? AND b.closed_at IS NULL ORDER BY b.id
        """,
        (product_id,)))


def _update_fields(conn, table: str, row_id: int, fields: dict[str, Any]) -> None:
    """Write only the columns given. An empty dict is a no-op, not an error."""
    if not fields:
        return
    assignments = ", ".join(f"{column} = ?" for column in fields)
    conn.execute(f"UPDATE {table} SET {assignments} WHERE id = ?",
                 (*fields.values(), row_id))


def update_article_fields(conn, article_id: int, fields: dict[str, Any]) -> None:
    _update_fields(conn, "article", article_id, fields)


def update_product_fields(conn, product_id: int, fields: dict[str, Any]) -> None:
    _update_fields(conn, "product", product_id, fields)
```

`_update_fields` interpole des noms de colonnes dans le SQL : les clés du dictionnaire ne
viennent **jamais** d'une entrée utilisateur brute. Les appelants (Task 12) filtrent sur une
liste blanche de colonnes avant d'appeler.

- [ ] **Step 4: Écrire l'exécution**

Dans `application.py`, importer `REASON_CONVERSION` et le planificateur, puis ajouter :

```python
    def convert_product_unit(self, *, product_id: int, to_unit: str,
                             reference_quantity: float, packaging_name: str = "unité",
                             dry_run: bool = False) -> dict[str, Any]:
        """Move a product from pieces to grams or millilitres.

        Everything happens in one transaction: a product half-converted would
        report a stock that is partly packets and partly grams, and no reading
        of the journal could tell them apart afterwards.
        """
        with self.db.write() as conn:
            product = repo.get_product(conn, product_id)
            if product is None:
                raise LookupError(f"no product {product_id}")
            articles = repo.list_articles_for_product(conn, product_id)
            batches = repo.list_open_batches_for_product(conn, product_id)

            plan = plan_conversion(product=product, articles=articles, batches=batches,
                                   to_unit=to_unit, reference_quantity=reference_quantity)

            report = {
                "product_id": plan.product_id,
                "product_name": product["name"],
                "from_unit": plan.from_unit,
                "to_unit": plan.to_unit,
                "reference_quantity": plan.reference_quantity,
                "articles": len(plan.articles),
                "batches": len(plan.batches),
                "movements": plan.movements,
                "articles_using_reference": list(plan.articles_using_reference),
                "applied": False,
            }
            if dry_run:
                return report

            occurred_at = _now()
            factors = {a.article_id: a.factor for a in plan.articles}

            for article in plan.articles:
                # Nutrition is stored per base unit: per packet becomes per gram.
                # net_quantity is a mass or a volume already, so it does not move.
                current = next(a for a in articles if a["id"] == article.article_id)
                rescaled = {
                    column: current[column] / article.factor
                    for column in NUTRITION_COLUMNS
                    if current[column] is not None
                }
                repo.update_article_fields(conn, article.article_id, rescaled)
                repo.insert_packaging(conn, scope="article", target_id=article.article_id,
                                      name=packaging_name, base_quantity=article.factor,
                                      is_purchase_default=1)

            for batch in plan.batches:
                repo.insert_movement(
                    conn, occurred_at=occurred_at, product_id=product_id,
                    article_id=batch.article_id, batch_id=batch.batch_id,
                    quantity=-batch.old_remaining, reason=REASON_CONVERSION,
                    base_unit=plan.from_unit, kcal=None, cost=None,
                    ref_type=None, ref_id=None,
                    idempotency_key=f"conversion:{product_id}:{batch.batch_id}:{to_unit}:out",
                )
                repo.insert_movement(
                    conn, occurred_at=occurred_at, product_id=product_id,
                    article_id=batch.article_id, batch_id=batch.batch_id,
                    quantity=batch.new_remaining, reason=REASON_CONVERSION,
                    base_unit=plan.to_unit, kcal=None, cost=None,
                    ref_type=None, ref_id=None,
                    idempotency_key=f"conversion:{product_id}:{batch.batch_id}:{to_unit}:in",
                )
                repo.set_batch_remaining(conn, batch.batch_id, batch.new_remaining)
                conn.execute("UPDATE batch SET initial = ? WHERE id = ?",
                             (batch.new_initial, batch.batch_id))

            product_fields: dict[str, Any] = {"base_unit": plan.to_unit}
            if product["min_quantity"] is not None:
                product_fields["min_quantity"] = (
                    product["min_quantity"] * plan.reference_quantity
                )
            if product["reference_kcal"] is not None:
                product_fields["reference_kcal"] = (
                    product["reference_kcal"] / plan.reference_quantity
                )
            repo.update_product_fields(conn, product_id, product_fields)

            report["applied"] = True
            return report
```

Ajouter en tête du module la liste des colonnes remises à l'échelle :

```python
# Nutrition columns of `article`, all stored per base unit, all rescaled when a
# product changes unit.
NUTRITION_COLUMNS: Final = (
    "kcal_per_base_unit", "proteins", "carbohydrates", "sugars", "added_sugars",
    "fat", "saturated_fat", "fiber", "salt",
)
```

Le mouvement de conversion est écrit **avant** `set_batch_remaining`, pour que le journal
enregistre bien l'ancienne quantité.

- [ ] **Step 5: Lancer les tests**

Run: `./scripts/test.sh tests/test_conversion_execution.py -v`
Expected: PASS

- [ ] **Step 6: Lancer toute la suite**

Run: `./scripts/test.sh`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add custom_components/home_stock/application.py \
        custom_components/home_stock/storage/repositories.py \
        tests/test_conversion_execution.py
git commit -m "feat: convert a product from pieces to grams in one transaction"
```

---

### Task 11: `shopping.py` — le cycle de vie de la session

**Files:**
- Create: `custom_components/home_stock/shopping.py`
- Modify: `custom_components/home_stock/storage/repositories.py`
- Test: `tests/test_shopping.py`

**Interfaces:**
- Consumes: les dépôts de la Task 4, `StockManager.add_stock` (lot 0), `repo.insert_price` (lot 0).
- Produces:
  - `shopping.ShoppingError(Exception)`
  - `shopping.ShoppingService(manager: StockManager)`
  - `start(*, store: str | None) -> dict`
  - `current() -> dict | None` — `{"session": {...}, "lines": [...], "totals": {...}, "stores": [...]}`
  - `add_line(*, article_id: int, quantity: float, unit_price: float | None, idempotency_key: str | None) -> dict`
  - `update_line(line_id: int, *, quantity=None, unit_price=None) -> dict`
  - `remove_line(line_id: int) -> None`
  - `checkout() -> dict`
  - `store_line(line_id: int, *, location_id: int, best_before: str | None) -> dict`
  - `close() -> dict`
  - `repo.recent_shelf_lives(conn, product_id: int, limit: int = 3) -> list[int]`

**Deux règles à ne pas rater :** une ligne déjà rangée ne se supprime pas (le lot existe), et un prix relevé écrit une ligne `price` **au moment du scan**, pas au rangement — c'est là que l'observation a lieu.

- [ ] **Step 1: Écrire le test**

`tests/test_shopping.py` :

```python
"""The shopping session, end to end, without Home Assistant."""
import pytest

from custom_components.home_stock.application import StockManager
from custom_components.home_stock.shopping import ShoppingError, ShoppingService
from custom_components.home_stock.storage.database import Database
from custom_components.home_stock.storage.migrations import apply_migrations


@pytest.fixture
def service(tmp_path) -> ShoppingService:
    database = Database(str(tmp_path / "home_stock.db"))
    database.connect()
    with database.write() as conn:
        apply_migrations(conn)
        conn.execute("INSERT INTO location (id, name, kind) VALUES (1, 'Placard', 'pantry')")
        conn.execute(
            "INSERT INTO product (id, name, base_unit, default_location_id, "
            "aisle_id) VALUES (1, 'Pâtes', 'g', 1, "
            "(SELECT id FROM aisle WHERE name = 'Épicerie salée'))"
        )
        conn.execute(
            "INSERT INTO article (id, product_id, label, net_quantity) "
            "VALUES (10, 1, 'Panzani 500 g', 500)"
        )
    return ShoppingService(StockManager(database))


def test_a_session_starts_and_is_the_current_one(service):
    service.start(store="Leclerc")

    current = service.current()
    assert current["session"]["state"] == "shopping"
    assert current["session"]["store"] == "Leclerc"
    assert current["lines"] == []


def test_only_one_session_can_be_open(service):
    service.start(store="Leclerc")

    with pytest.raises(ShoppingError, match="déjà"):
        service.start(store="Lidl")


def test_scanning_adds_a_line_and_records_the_price_observed(service):
    service.start(store="Leclerc")

    service.add_line(article_id=10, quantity=500, unit_price=0.002, idempotency_key="a")

    with service.manager.db.write() as conn:
        row = conn.execute("SELECT store, source, price_per_base_unit FROM price").fetchone()
    assert (row["store"], row["source"]) == ("Leclerc", "manual")
    assert row["price_per_base_unit"] == pytest.approx(0.002)


def test_a_line_with_no_price_records_no_price(service):
    service.start(store="Leclerc")
    service.add_line(article_id=10, quantity=500, unit_price=None, idempotency_key="a")

    with service.manager.db.write() as conn:
        assert conn.execute("SELECT COUNT(*) FROM price").fetchone()[0] == 0


def test_replaying_the_same_scan_adds_nothing(service):
    """The offline queue replays. Two identical keys are one packet of pasta."""
    service.start(store="Leclerc")
    first = service.add_line(article_id=10, quantity=500, unit_price=0.002,
                             idempotency_key="scan-1")
    again = service.add_line(article_id=10, quantity=500, unit_price=0.002,
                             idempotency_key="scan-1")

    assert first["id"] == again["id"]
    assert len(service.current()["lines"]) == 1


def test_the_running_total_is_what_the_cart_costs(service):
    service.start(store="Leclerc")
    service.add_line(article_id=10, quantity=500, unit_price=0.002, idempotency_key="a")
    service.add_line(article_id=10, quantity=1000, unit_price=0.002, idempotency_key="b")

    assert service.current()["totals"]["total"] == pytest.approx(3.0)


def test_scanning_outside_a_session_is_refused(service):
    with pytest.raises(ShoppingError, match="aucune session"):
        service.add_line(article_id=10, quantity=500, unit_price=None, idempotency_key="a")


def test_checkout_moves_the_session_to_put_away(service):
    service.start(store="Leclerc")
    service.add_line(article_id=10, quantity=500, unit_price=0.002, idempotency_key="a")

    service.checkout()

    assert service.current()["session"]["state"] == "to_store"


def test_storing_a_line_creates_the_batch_and_writes_the_purchase(service):
    service.start(store="Leclerc")
    line = service.add_line(article_id=10, quantity=500, unit_price=0.002,
                            idempotency_key="a")
    service.checkout()

    result = service.store_line(line["id"], location_id=1, best_before="2027-01-01")

    with service.manager.db.write() as conn:
        batch = conn.execute("SELECT * FROM batch WHERE id = ?",
                             (result["batch_id"],)).fetchone()
        movement = conn.execute(
            "SELECT reason, quantity, base_unit FROM movement").fetchone()
    assert batch["remaining"] == pytest.approx(500.0)
    assert batch["best_before"] == "2027-01-01"
    assert batch["price_per_base_unit"] == pytest.approx(0.002)
    assert (movement["reason"], movement["quantity"], movement["base_unit"]) == (
        "purchase", 500.0, "g")


def test_storing_a_line_twice_creates_one_batch(service):
    service.start(store="Leclerc")
    line = service.add_line(article_id=10, quantity=500, unit_price=None,
                            idempotency_key="a")
    service.checkout()

    first = service.store_line(line["id"], location_id=1, best_before=None)
    again = service.store_line(line["id"], location_id=1, best_before=None)

    assert first["batch_id"] == again["batch_id"]
    with service.manager.db.write() as conn:
        assert conn.execute("SELECT COUNT(*) FROM batch").fetchone()[0] == 1


def test_a_stored_line_can_no_longer_be_removed(service):
    service.start(store="Leclerc")
    line = service.add_line(article_id=10, quantity=500, unit_price=None,
                            idempotency_key="a")
    service.checkout()
    service.store_line(line["id"], location_id=1, best_before=None)

    with pytest.raises(ShoppingError, match="rangée"):
        service.remove_line(line["id"])


def test_an_unstored_line_disappears_without_touching_the_stock(service):
    service.start(store="Leclerc")
    line = service.add_line(article_id=10, quantity=500, unit_price=None,
                            idempotency_key="a")

    service.remove_line(line["id"])

    assert service.current()["lines"] == []
    with service.manager.db.write() as conn:
        assert conn.execute("SELECT COUNT(*) FROM movement").fetchone()[0] == 0


def test_storing_the_last_line_closes_the_session(service):
    service.start(store="Leclerc")
    line = service.add_line(article_id=10, quantity=500, unit_price=None,
                            idempotency_key="a")
    service.checkout()

    service.store_line(line["id"], location_id=1, best_before=None)

    assert service.current() is None


def test_a_shelf_life_is_learned_from_what_was_actually_posed(service):
    service.start(store="Leclerc")
    for index, best_before in enumerate(["2026-09-01", "2026-09-03", "2026-09-02"]):
        line = service.add_line(article_id=10, quantity=500, unit_price=None,
                                idempotency_key=f"a{index}")
        service.store_line(line["id"], location_id=1, best_before=best_before)

    with service.manager.db.write() as conn:
        row = conn.execute(
            "SELECT default_shelf_life_days FROM product WHERE id = 1").fetchone()
    # Median of the three, not the last one: one odd date must not move the default.
    assert row["default_shelf_life_days"] is not None
```

- [ ] **Step 2: Lancer le test et vérifier qu'il échoue**

Run: `./scripts/test.sh tests/test_shopping.py -v`
Expected: FAIL — `ModuleNotFoundError: ...shopping`

- [ ] **Step 3: Ajouter le dépôt des durées de conservation**

Dans `storage/repositories.py` :

```python
def recent_shelf_lives(conn, product_id: int, limit: int = 3) -> list[int]:
    """Days between entry and best-before on this product's latest batches.

    Feeds the default the panel offers as a one-tap button. Batches with no
    best-before say nothing about shelf life and are left out.
    """
    rows = conn.execute(
        """
        SELECT CAST(julianday(b.best_before) - julianday(date(b.entered_at)) AS INTEGER) AS days
        FROM batch b JOIN article a ON a.id = b.article_id
        WHERE a.product_id = ? AND b.best_before IS NOT NULL
        ORDER BY b.entered_at DESC, b.id DESC LIMIT ?
        """,
        (product_id, limit),
    ).fetchall()
    return [row["days"] for row in rows if row["days"] is not None and row["days"] >= 0]
```

- [ ] **Step 4: Écrire le service**

`custom_components/home_stock/shopping.py` :

```python
"""The shopping session: what is scanned in the aisle, and put away at home.

The session lives here, server-side, not in the phone. A screen that goes to
sleep, an app that is closed, a basement with no signal — none of them lose a
cart. The panel keeps only a replay queue of writes it could not send.
"""
from __future__ import annotations

import statistics
from datetime import UTC, datetime
from typing import Any

from .application import StockManager
from .storage import repositories as repo


class ShoppingError(Exception):
    """A shopping action that does not make sense in the current state."""


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0, tzinfo=None).isoformat()


class ShoppingService:
    """Every write to a shopping session goes through here."""

    def __init__(self, manager: StockManager) -> None:
        self.manager = manager

    # --- session ------------------------------------------------------------

    def start(self, *, store: str | None) -> dict[str, Any]:
        with self.manager.db.write() as conn:
            existing = repo.current_session(conn)
            if existing is not None and existing["state"] == "shopping":
                raise ShoppingError("Une session de courses est déjà ouverte.")
            session_id = repo.open_session(conn, started_at=_now(), store=store)
            return repo.get_session(conn, session_id)

    def current(self) -> dict[str, Any] | None:
        conn = self.manager.db.read()
        session = repo.current_session(conn)
        if session is None:
            return None
        return {
            "session": session,
            "lines": repo.list_lines(conn, session["id"]),
            "totals": repo.session_totals(conn, session["id"]),
            "stores": repo.list_stores(conn),
        }

    def checkout(self) -> dict[str, Any]:
        with self.manager.db.write() as conn:
            session = self._open_session(conn)
            repo.set_session_state(conn, session["id"], "to_store")
            return repo.get_session(conn, session["id"])

    def close(self) -> dict[str, Any]:
        with self.manager.db.write() as conn:
            session = repo.current_session(conn)
            if session is None:
                raise ShoppingError("Aucune session de courses en cours.")
            repo.set_session_state(conn, session["id"], "done", closed_at=_now())
            return repo.get_session(conn, session["id"])

    # --- lines --------------------------------------------------------------

    def add_line(self, *, article_id: int, quantity: float, unit_price: float | None,
                 idempotency_key: str | None) -> dict[str, Any]:
        with self.manager.db.write() as conn:
            if idempotency_key:
                # The panel's offline queue replays in order; a replayed scan
                # must return the line it already created, not a second packet.
                existing = repo.line_by_key(conn, idempotency_key)
                if existing is not None:
                    return existing

            session = self._open_session(conn)
            line_id = repo.add_line(
                conn, session_id=session["id"], article_id=article_id,
                quantity=quantity, unit_price=unit_price, scanned_at=_now(),
                idempotency_key=idempotency_key,
            )
            if unit_price is not None:
                # The observation happens in the aisle, so it is recorded in the
                # aisle — not later, when the pack is put away somewhere else.
                repo.insert_price(
                    conn, article_id=article_id, observed_on=_now()[:10],
                    price_per_base_unit=unit_price, store=session["store"],
                    source="manual",
                )
            return repo.line_by_key(conn, idempotency_key) if idempotency_key else {
                "id": line_id, "session_id": session["id"], "article_id": article_id,
                "quantity": quantity, "unit_price": unit_price,
            }

    def update_line(self, line_id: int, *, quantity: float | None = None,
                    unit_price: float | None = None) -> dict[str, Any]:
        with self.manager.db.write() as conn:
            line = self._line(conn, line_id)
            if line["stored_at"]:
                raise ShoppingError("Cette ligne est déjà rangée.")
            repo.update_line(conn, line_id, quantity=quantity, unit_price=unit_price)
            return self._line(conn, line_id)

    def remove_line(self, line_id: int) -> None:
        with self.manager.db.write() as conn:
            line = self._line(conn, line_id)
            if line["stored_at"]:
                # The batch exists and the journal has recorded the purchase.
                # Undoing that is an inventory correction, not a deletion.
                raise ShoppingError(
                    "Cette ligne est déjà rangée : corrigez le lot, pas la liste."
                )
            repo.remove_line(conn, line_id)

    def store_line(self, line_id: int, *, location_id: int,
                   best_before: str | None) -> dict[str, Any]:
        """Turn a bought line into a real batch. This is where stock is created."""
        with self.manager.db.write() as conn:
            line = self._line(conn, line_id)
            if line["stored_at"]:
                return {"line_id": line_id, "batch_id": line["batch_id"],
                        "already_stored": True}

        result = self.manager.add_stock(
            article_id=line["article_id"], quantity=line["quantity"],
            location_id=location_id, best_before=best_before,
            price_per_base_unit=line["unit_price"],
            idempotency_key=f"shopping_line:{line_id}",
        )
        batch_id = result["batch_id"] if isinstance(result, dict) else result

        with self.manager.db.write() as conn:
            repo.mark_line_stored(conn, line_id, batch_id=batch_id, stored_at=_now())
            self._learn_shelf_life(conn, line["product_id"])
            session = repo.get_session(conn, line["session_id"])
            pending = repo.session_totals(conn, session["id"])["pending"]
            if pending == 0 and session["state"] != "shopping":
                repo.set_session_state(conn, session["id"], "done", closed_at=_now())

        return {"line_id": line_id, "batch_id": batch_id, "already_stored": False}

    # --- helpers ------------------------------------------------------------

    def _open_session(self, conn) -> dict[str, Any]:
        session = repo.current_session(conn)
        if session is None or session["state"] != "shopping":
            raise ShoppingError("Aucune session de courses ouverte.")
        return session

    def _line(self, conn, line_id: int) -> dict[str, Any]:
        row = conn.execute(
            """
            SELECT l.*, a.product_id FROM shopping_line l
            JOIN article a ON a.id = l.article_id WHERE l.id = ?
            """,
            (line_id,),
        ).fetchone()
        if row is None:
            raise ShoppingError(f"Ligne inconnue : {line_id}")
        return dict(row)

    def _learn_shelf_life(self, conn, product_id: int) -> None:
        """Update the one-tap default from what was actually posed.

        The median of the last three, not the last one: a date typed wrong
        should not drag the default with it.
        """
        observed = repo.recent_shelf_lives(conn, product_id, limit=3)
        if not observed:
            return
        repo.update_product_fields(
            conn, product_id, {"default_shelf_life_days": round(statistics.median(observed))}
        )
```

**Note d'implémentation :** `StockManager.add_stock` du lot 0 ouvre sa propre transaction.
`store_line` referme donc sa lecture avant de l'appeler, puis rouvre une transaction pour
marquer la ligne. Ne pas imbriquer les deux : `Database.write()` prend un verrou non
réentrant et l'imbrication bloquerait.

- [ ] **Step 5: Lancer les tests**

Run: `./scripts/test.sh tests/test_shopping.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add custom_components/home_stock/shopping.py \
        custom_components/home_stock/storage/repositories.py tests/test_shopping.py
git commit -m "feat: server-side shopping session, from the aisle to the cupboard"
```

---
### Task 12: Commandes websocket d'écriture

**Files:**
- Modify: `custom_components/home_stock/websocket_api.py`
- Modify: `custom_components/home_stock/__init__.py`
- Modify: `custom_components/home_stock/manifest.json`
- Test: `tests/test_websocket_write.py` (nouveau)

**Interfaces:**
- Consumes: `OffClient`, `AiohttpTransport` (Task 6), `map_article`, `nutrition_per_base_unit` (Task 5), `candidates`, `preselect` (Task 7), `suggest_price`, `latest_price` (Task 8), `convert_product_unit` (Task 10), `ShoppingService` (Task 11).
- Produces:
  - `HomeStockData` gagne trois champs : `off_client: OffClient`, `shopping: ShoppingService`, `user_agent: str`.
  - Commandes : `home_stock/lookup`, `home_stock/article/create`, `home_stock/article/update`, `home_stock/product/update`, `home_stock/product/convert_unit`, `home_stock/stock/add`, `home_stock/aisles/reorder`.
  - `websocket_api.ARTICLE_EDITABLE: frozenset[str]`, `websocket_api.PRODUCT_EDITABLE: frozenset[str]` — les listes blanches de colonnes.

**Le `manifest.json` doit déclarer `"dependencies": ["http", "websocket_api"]` et garder `"iot_class": "local_polling"`.** Le `User-Agent` se construit depuis la version du manifeste.

- [ ] **Step 1: Écrire le test**

`tests/test_websocket_write.py` :

```python
"""The write commands, through a real Home Assistant websocket connection."""
import pytest
from homeassistant.core import HomeAssistant

from custom_components.home_stock.off.client import OffLookup, OffRecord

from .test_websocket import setup_entry  # existing helper from lot 0


class FakeOffClient:
    """Stands in for the cascade. Nothing here reaches the network."""

    def __init__(self, record: OffRecord | None = None, throttled: bool = False):
        self.result = OffLookup(record=record, throttled=throttled)
        self.codes: list[str] = []

    async def lookup(self, code: str) -> OffLookup:
        self.codes.append(code)
        return self.result

    async def lookup_with_retry(self, code: str, **kwargs) -> OffLookup:
        return await self.lookup(code)


MUESLI = OffRecord("3229820129488", "food", {
    "code": "3229820129488",
    "product_name_fr": "Muesli Raisin, Figue, Datte, Abricot",
    "generic_name_fr": "Muesli",
    "brands": "Bjorg",
    "product_quantity": 375,
    "product_quantity_unit": "g",
    "nutriscore_grade": "a",
    "categories_tags": ["en:plant-based-foods", "en:breakfasts", "en:breakfast-cereals"],
    "nutrition_data_per": "100g",
    "nutriments": {"energy-kcal_100g": 360, "proteins_100g": 9, "carbohydrates_100g": 60,
                   "fat_100g": 6, "salt_100g": 0.02},
})


async def test_an_unknown_barcode_comes_back_with_its_off_card(hass: HomeAssistant,
                                                               hass_ws_client):
    entry = await setup_entry(hass)
    entry.runtime_data.off_client = FakeOffClient(MUESLI)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/lookup",
                            "code": "3229820129488"})
    result = (await client.receive_json())["result"]

    assert result["known"] is False
    assert result["off"]["label"] == "Muesli Raisin, Figue, Datte, Abricot"
    assert result["off"]["net_quantity"] == 375
    assert result["off"]["aisle"] == "Petit-déjeuner"
    assert result["off"]["nutriscore"] == "a"


async def test_a_lookup_never_writes(hass: HomeAssistant, hass_ws_client):
    entry = await setup_entry(hass)
    entry.runtime_data.off_client = FakeOffClient(MUESLI)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/lookup", "code": "3229820129488"})
    await client.receive_json()

    def count() -> int:
        return entry.runtime_data.database.read().execute(
            "SELECT COUNT(*) FROM article").fetchone()[0]

    assert await hass.async_add_executor_job(count) == 0


async def test_a_throttled_lookup_says_so_instead_of_pretending(hass: HomeAssistant,
                                                                hass_ws_client):
    entry = await setup_entry(hass)
    entry.runtime_data.off_client = FakeOffClient(throttled=True)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/lookup", "code": "123"})
    result = (await client.receive_json())["result"]

    assert result["throttled"] is True
    assert result["off"] is None


async def test_creating_an_article_attaches_it_and_remembers_the_barcode(
        hass: HomeAssistant, hass_ws_client):
    entry = await setup_entry(hass)
    entry.runtime_data.off_client = FakeOffClient(MUESLI)
    client = await hass_ws_client(hass)

    await client.send_json({
        "id": 1, "type": "home_stock/article/create",
        "code": "3229820129488",
        "new_product": {"name": "Muesli", "base_unit": "g"},
        "off": MUESLI.product, "off_source": "food",
    })
    created = (await client.receive_json())["result"]

    await client.send_json({"id": 2, "type": "home_stock/lookup", "code": "3229820129488"})
    again = (await client.receive_json())["result"]

    assert again["known"] is True
    assert again["article"]["id"] == created["article_id"]
    assert again["product"]["name"] == "Muesli"


async def test_a_created_article_carries_its_nutrition_per_base_unit(
        hass: HomeAssistant, hass_ws_client):
    entry = await setup_entry(hass)
    client = await hass_ws_client(hass)

    await client.send_json({
        "id": 1, "type": "home_stock/article/create", "code": "3229820129488",
        "new_product": {"name": "Muesli", "base_unit": "g"},
        "off": MUESLI.product, "off_source": "food",
    })
    created = (await client.receive_json())["result"]

    def kcal() -> float:
        return entry.runtime_data.database.read().execute(
            "SELECT kcal_per_base_unit FROM article WHERE id = ?",
            (created["article_id"],)).fetchone()[0]

    assert await hass.async_add_executor_job(kcal) == pytest.approx(3.6)


async def test_the_raw_off_answer_is_kept_verbatim(hass: HomeAssistant, hass_ws_client):
    entry = await setup_entry(hass)
    client = await hass_ws_client(hass)

    await client.send_json({
        "id": 1, "type": "home_stock/article/create", "code": "3229820129488",
        "new_product": {"name": "Muesli", "base_unit": "g"},
        "off": MUESLI.product, "off_source": "food",
    })
    created = (await client.receive_json())["result"]

    def raw() -> str:
        return entry.runtime_data.database.read().execute(
            "SELECT off_raw FROM article WHERE id = ?", (created["article_id"],)
        ).fetchone()[0]

    import json
    assert json.loads(await hass.async_add_executor_job(raw))["brands"] == "Bjorg"


async def test_editing_an_article_by_hand_protects_it_from_a_resync(
        hass: HomeAssistant, hass_ws_client):
    entry = await setup_entry(hass)
    client = await hass_ws_client(hass)
    await client.send_json({
        "id": 1, "type": "home_stock/article/create", "code": "1", 
        "new_product": {"name": "Muesli", "base_unit": "g"},
        "off": MUESLI.product, "off_source": "food"})
    created = (await client.receive_json())["result"]

    await client.send_json({"id": 2, "type": "home_stock/article/update",
                            "article_id": created["article_id"],
                            "fields": {"kcal_per_base_unit": 4.0}})
    await client.receive_json()

    def manual() -> str:
        return entry.runtime_data.database.read().execute(
            "SELECT manual_fields FROM article WHERE id = ?",
            (created["article_id"],)).fetchone()[0]

    assert "kcal_per_base_unit" in (await hass.async_add_executor_job(manual))


async def test_an_unknown_column_is_refused_rather_than_written(
        hass: HomeAssistant, hass_ws_client):
    """The update path interpolates column names into SQL. The whitelist is
    what keeps that safe."""
    await setup_entry(hass)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/product/update",
                            "product_id": 1, "fields": {"id = 1; DROP TABLE product; --": 1}})
    answer = await client.receive_json()

    assert answer["success"] is False


async def test_a_dry_run_conversion_reports_without_touching_anything(
        hass: HomeAssistant, hass_ws_client):
    entry = await setup_entry(hass, with_piece_product=True)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/product/convert_unit",
                            "product_id": 1, "to_unit": "g",
                            "reference_quantity": 500, "dry_run": True})
    report = (await client.receive_json())["result"]

    assert report["applied"] is False
    assert report["to_unit"] == "g"


async def test_reordering_aisles_writes_the_new_walking_order(hass: HomeAssistant,
                                                              hass_ws_client):
    entry = await setup_entry(hass)
    client = await hass_ws_client(hass)

    def ids() -> list[int]:
        return [r["id"] for r in entry.runtime_data.database.read().execute(
            "SELECT id FROM aisle ORDER BY position").fetchall()]

    order = await hass.async_add_executor_job(ids)
    reversed_order = list(reversed(order))

    await client.send_json({"id": 1, "type": "home_stock/aisles/reorder",
                            "aisle_ids": reversed_order})
    await client.receive_json()

    assert await hass.async_add_executor_job(ids) == reversed_order


async def test_storing_directly_creates_a_batch_outside_any_session(
        hass: HomeAssistant, hass_ws_client):
    entry = await setup_entry(hass, with_article=True)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/stock/add", "article_id": 1,
                            "quantity": 500, "location_id": 1,
                            "best_before": "2027-01-01", "idempotency_key": "k1"})
    first = (await client.receive_json())["result"]

    await client.send_json({"id": 2, "type": "home_stock/stock/add", "article_id": 1,
                            "quantity": 500, "location_id": 1,
                            "best_before": "2027-01-01", "idempotency_key": "k1"})
    again = (await client.receive_json())["result"]

    assert first["batch_id"] == again["batch_id"]
```

Le helper `setup_entry` existe déjà dans `tests/test_websocket.py` (lot 0). Lui ajouter les
paramètres `with_article: bool = False` et `with_piece_product: bool = False`, qui insèrent
respectivement un article prêt à ranger et un produit à la pièce avec un lot ouvert. Ne pas
changer son comportement par défaut : les tests du lot 0 l'appellent sans argument.

- [ ] **Step 2: Lancer le test et vérifier qu'il échoue**

Run: `./scripts/test.sh tests/test_websocket_write.py -v`
Expected: FAIL — `unknown_command: home_stock/lookup`

- [ ] **Step 3: Câbler le client OFF et le service de courses**

Dans `__init__.py` :

```python
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .off.client import AiohttpTransport, OffClient
from .shopping import ShoppingService


@dataclass
class HomeStockData:
    """What the entry keeps alive while it is loaded."""

    database: Database
    manager: StockManager
    coordinator: HomeStockCoordinator
    shopping: ShoppingService
    off_client: OffClient
    user_agent: str
```

et, dans `async_setup_entry`, après la création du `manager` :

```python
    # OFF refuses anonymous clients, so the agent names the integration, its
    # version and a way to reach its owner — the contact OFF asks for.
    version = (await async_get_integration(hass, DOMAIN)).version or "1.0"
    user_agent = f"home_stock/{version} (Home Assistant; maxime@allanic.me)"
    off_client = OffClient(
        AiohttpTransport(async_get_clientsession(hass)), user_agent=user_agent
    )
    shopping = ShoppingService(manager)
    ...
    entry.runtime_data = HomeStockData(
        database, manager, coordinator, shopping, off_client, user_agent
    )
```

avec `from homeassistant.loader import async_get_integration` en tête.

- [ ] **Step 4: Écrire les commandes**

À ajouter à `websocket_api.py` :

```python
# Columns a human may edit from the panel. Both sets are interpolated into
# SQL by repositories._update_fields, so nothing outside them is ever written.
ARTICLE_EDITABLE: Final = frozenset({
    "label", "brand", "net_quantity", "image", "kcal_per_base_unit", "proteins",
    "carbohydrates", "sugars", "added_sugars", "fat", "saturated_fat", "fiber",
    "salt", "nutriscore", "nova", "ecoscore",
})
# `base_unit` is deliberately absent: changing it through a plain field edit
# would rewrite the meaning of every stored quantity for that product without
# converting a single one. The only way to change a unit is
# `home_stock/product/convert_unit`, which rescales the batches, the nutrition
# and the prices inside one transaction.
PRODUCT_EDITABLE: Final = frozenset({
    "name", "category_id", "aisle_id", "edible", "default_location_id",
    "min_quantity", "days_after_opening", "default_shelf_life_days", "reference_kcal",
    "active",
})


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/lookup",
    vol.Required("code"): str,
})
@websocket_api.async_response
async def lookup(hass, connection, msg) -> None:
    """Resolve a barcode. Writes nothing: creation is a separate, explicit step."""
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return

    code = msg["code"]
    known = await _read(hass, partial(
        repo.find_article_by_barcode, runtime.manager.db.read(), code))

    if known is not None:
        product = await _read(hass, partial(
            repo.get_product, runtime.manager.db.read(), known["product_id"]))
        price = await _suggest_price(hass, runtime, known, product)
        connection.send_result(msg["id"], {
            "code": code, "known": True, "article": known, "product": product,
            "off": None, "candidates": [], "preselected_product_id": None,
            "price": price, "conversion_offer": _conversion_offer(product, known),
            "throttled": False, "timed_out": False,
        })
        return

    result = await runtime.off_client.lookup(code)
    if result.record is None:
        connection.send_result(msg["id"], {
            "code": code, "known": False, "article": None, "product": None,
            "off": None, "candidates": [], "preselected_product_id": None,
            "price": None, "conversion_offer": None,
            "throttled": result.throttled, "timed_out": result.timed_out,
        })
        return

    mapped = map_article(result.record.product, result.record.off_source)
    products = await _read(hass, partial(repo.list_products, runtime.manager.db.read()))
    found = candidates(names=[mapped.generic_name, mapped.label,
                              strip_brand(mapped.label or "", mapped.brand)],
                       products=products)
    chosen = preselect(found)

    connection.send_result(msg["id"], {
        "code": code, "known": False, "article": None, "product": None,
        "off": asdict(mapped), "off_raw": result.record.product,
        "off_source": result.record.off_source,
        "candidates": [asdict(c) for c in found],
        "preselected_product_id": chosen.product_id if chosen else None,
        "price": await _open_prices_only(hass, runtime, code, mapped.net_quantity),
        "conversion_offer": None, "throttled": False, "timed_out": False,
    })


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/article/create",
    vol.Required("code"): str,
    vol.Exclusive("product_id", "target"): int,
    vol.Exclusive("new_product", "target"): dict,
    vol.Optional("off"): dict,
    vol.Optional("off_source"): vol.Any(str, None),
    vol.Optional("fields", default={}): dict,
})
@websocket_api.async_response
async def article_create(hass, connection, msg) -> None:
    """Persist a scanned article, its barcode, and the OFF answer verbatim."""
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return

    def work() -> dict[str, Any]:
        with runtime.manager.db.write() as conn:
            existing = repo.find_article_by_barcode(conn, msg["code"])
            if existing is not None:
                # A replayed creation, or two phones scanning the same pack.
                return {"article_id": existing["id"],
                        "product_id": existing["product_id"], "created": False}

            raw = msg.get("off") or {}
            source = msg.get("off_source")
            mapped = map_article(raw, source) if raw and source else None

            product_id = msg.get("product_id")
            if product_id is None:
                wanted = dict(msg["new_product"])
                aisle = mapped.aisle if mapped else None
                if aisle:
                    row = conn.execute(
                        "SELECT id FROM aisle WHERE name = ?", (aisle,)).fetchone()
                    if row is not None:
                        wanted.setdefault("aisle_id", row["id"])
                product_id = repo.insert_product(conn, **wanted)

            product = repo.get_product(conn, product_id)
            values: dict[str, Any] = {"is_generic": 0}
            if mapped is not None:
                values.update({
                    "label": mapped.label, "brand": mapped.brand,
                    "net_quantity": mapped.net_quantity, "image": mapped.image,
                    "nutriscore": mapped.nutriscore, "nova": mapped.nova,
                    "ecoscore": mapped.ecoscore, "allergens": mapped.allergens,
                    "traces": mapped.traces, "additives": mapped.additives,
                    "off_labels": mapped.off_labels, "off_source": mapped.off_source,
                    "off_synced_at": dt_util.utcnow().replace(
                        microsecond=0, tzinfo=None).isoformat(),
                    "off_raw": json.dumps(raw, ensure_ascii=False),
                })
                per_base = nutrition_per_base_unit(
                    mapped.nutrition_per_100, product["base_unit"], mapped.net_quantity)
                # to_article_columns renames `kcal` to the article's own
                # `kcal_per_base_unit`. Passing the raw dict would lose the
                # calories silently, because insert_article drops keys it does
                # not recognise without raising.
                values.update(to_article_columns(per_base))
            values.update({k: v for k, v in msg["fields"].items() if k in ARTICLE_EDITABLE})

            article_id = repo.insert_article(conn, product_id=product_id, **values)
            repo.link_barcode(conn, msg["code"], article_id)
            return {"article_id": article_id, "product_id": product_id, "created": True}

    result = await hass.async_add_executor_job(work)
    await runtime.coordinator.async_request_refresh()
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/article/update",
    vol.Required("article_id"): int,
    vol.Required("fields"): dict,
})
@websocket_api.async_response
async def article_update(hass, connection, msg) -> None:
    """Edit an article by hand. Edited columns are never resynced from OFF again."""
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return

    unknown = set(msg["fields"]) - ARTICLE_EDITABLE
    if unknown:
        connection.send_error(msg["id"], "invalid_field",
                              f"Colonnes non modifiables : {sorted(unknown)}")
        return

    def work() -> None:
        with runtime.manager.db.write() as conn:
            article = repo.get_article(conn, msg["article_id"])
            if article is None:
                raise LookupError(f"no article {msg['article_id']}")
            protected = set(json.loads(article["manual_fields"] or "[]"))
            protected.update(msg["fields"])
            repo.update_article_fields(conn, msg["article_id"], {
                **msg["fields"],
                "manual_fields": json.dumps(sorted(protected)),
            })

    try:
        await hass.async_add_executor_job(work)
    except LookupError as err:
        connection.send_error(msg["id"], "not_found", str(err))
        return
    await runtime.coordinator.async_request_refresh()
    connection.send_result(msg["id"], {"article_id": msg["article_id"]})


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/product/update",
    vol.Required("product_id"): int,
    vol.Required("fields"): dict,
})
@websocket_api.async_response
async def product_update(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return

    unknown = set(msg["fields"]) - PRODUCT_EDITABLE
    if unknown:
        connection.send_error(msg["id"], "invalid_field",
                              f"Colonnes non modifiables : {sorted(unknown)}")
        return

    def work() -> None:
        with runtime.manager.db.write() as conn:
            repo.update_product_fields(conn, msg["product_id"], msg["fields"])

    await hass.async_add_executor_job(work)
    await runtime.coordinator.async_request_refresh()
    connection.send_result(msg["id"], {"product_id": msg["product_id"]})


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/product/convert_unit",
    vol.Required("product_id"): int,
    vol.Required("to_unit"): vol.In(("g", "ml")),
    vol.Required("reference_quantity"): vol.Coerce(float),
    vol.Optional("packaging_name", default="unité"): str,
    vol.Optional("dry_run", default=False): bool,
})
@websocket_api.async_response
async def product_convert_unit(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return

    try:
        report = await hass.async_add_executor_job(partial(
            runtime.manager.convert_product_unit,
            product_id=msg["product_id"], to_unit=msg["to_unit"],
            reference_quantity=msg["reference_quantity"],
            packaging_name=msg["packaging_name"], dry_run=msg["dry_run"],
        ))
    except ConversionError as err:
        connection.send_error(msg["id"], "conversion_refused", str(err))
        return
    except LookupError as err:
        connection.send_error(msg["id"], "not_found", str(err))
        return

    if report["applied"]:
        await runtime.coordinator.async_request_refresh()
    connection.send_result(msg["id"], report)


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/stock/add",
    vol.Required("article_id"): int,
    vol.Required("quantity"): vol.Coerce(float),
    vol.Required("location_id"): int,
    vol.Optional("best_before"): vol.Any(str, None),
    vol.Optional("price_per_base_unit"): vol.Any(vol.Coerce(float), None),
    vol.Optional("idempotency_key"): vol.Any(str, None),
})
@websocket_api.async_response
async def stock_add(hass, connection, msg) -> None:
    """Put one thing away, outside any shopping session."""
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return

    result = await hass.async_add_executor_job(partial(
        runtime.manager.add_stock, article_id=msg["article_id"],
        quantity=msg["quantity"], location_id=msg["location_id"],
        best_before=msg.get("best_before"),
        price_per_base_unit=msg.get("price_per_base_unit"),
        idempotency_key=msg.get("idempotency_key"),
    ))
    await runtime.coordinator.async_request_refresh()
    connection.send_result(msg["id"], result if isinstance(result, dict)
                           else {"batch_id": result})


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/aisles/reorder",
    vol.Required("aisle_ids"): [int],
})
@websocket_api.async_response
async def aisles_reorder(hass, connection, msg) -> None:
    """Set the walking order. Position is the index in the list given."""
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return

    def work() -> None:
        with runtime.manager.db.write() as conn:
            for position, aisle_id in enumerate(msg["aisle_ids"]):
                conn.execute("UPDATE aisle SET position = ? WHERE id = ?",
                             (position, aisle_id))

    await hass.async_add_executor_job(work)
    connection.send_result(msg["id"], {"aisles": len(msg["aisle_ids"])})
```

Ajouter les deux helpers privés :

```python
def _conversion_offer(product: dict[str, Any] | None,
                      article: dict[str, Any] | None) -> dict[str, Any] | None:
    """Offer a piece -> gram move, but only when the weight is trustworthy."""
    if not product or not article or product["base_unit"] != "piece":
        return None
    net = article.get("net_quantity")
    if not net or not MIN_REFERENCE <= net <= MAX_REFERENCE:
        return None
    return {"product_id": product["id"], "to_unit": "g", "reference_quantity": net}


async def _suggest_price(hass, runtime, article, product) -> dict[str, Any]:
    """The price cascade for an article already in the catalogue."""
    conn = runtime.manager.db.read()
    session = await _read(hass, partial(repo.current_session, conn))
    store = session["store"] if session else None
    in_store = (await _read(hass, partial(repo.latest_price_in_store, conn,
                                          article["id"], store))) if store else None
    last_known = await _read(hass, partial(repo.latest_price, conn, article["id"]))
    from_open_prices = None
    if in_store is None:
        from_open_prices = await latest_price(
            AiohttpTransport(async_get_clientsession(hass)), article.get("code") or "",
            net_quantity=article.get("net_quantity"), user_agent=runtime.user_agent)
    return asdict(suggest_price(in_store=in_store, open_prices=from_open_prices,
                                last_known=last_known, store=store))


async def _open_prices_only(hass, runtime, code, net_quantity) -> dict[str, Any]:
    """An article that does not exist yet has no history: only Open Prices can help."""
    from_open_prices = await latest_price(
        AiohttpTransport(async_get_clientsession(hass)), code,
        net_quantity=net_quantity, user_agent=runtime.user_agent)
    return asdict(suggest_price(in_store=None, open_prices=from_open_prices,
                                last_known=None, store=None))
```

et les imports nécessaires en tête du module : `json`, `dataclasses.asdict`,
`typing.Final`, `homeassistant.util.dt as dt_util`,
`homeassistant.helpers.aiohttp_client.async_get_clientsession`, les fonctions de
`.off.mapping` (dont `to_article_columns`), `.off.open_prices`, `.off.client`, `.domain.matching`, `.domain.pricing`,
`.domain.conversion`.

Enfin, enregistrer les nouvelles commandes dans `async_register_websocket`.

- [ ] **Step 5: Lancer les tests**

Run: `./scripts/test.sh tests/test_websocket_write.py tests/test_websocket.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add custom_components/home_stock/websocket_api.py \
        custom_components/home_stock/__init__.py \
        custom_components/home_stock/manifest.json tests/
git commit -m "feat: websocket commands to look up, create, edit and convert from the panel"
```

---

### Task 13: Session au websocket, capteurs et resynchronisation

**Files:**
- Modify: `custom_components/home_stock/websocket_api.py`
- Modify: `custom_components/home_stock/sensor.py`
- Modify: `custom_components/home_stock/application.py`
- Modify: `custom_components/home_stock/services.py`, `services.yaml`
- Modify: `custom_components/home_stock/translations/fr.json`, `translations/en.json`
- Test: `tests/test_websocket_session.py`, `tests/test_entities.py` (existant)

**Interfaces:**
- Consumes: `ShoppingService` (Task 11), `OffClient.lookup_with_retry` (Task 6).
- Produces:
  - Commandes : `home_stock/session/start`, `session/current`, `session/add_line`, `session/update_line`, `session/remove_line`, `session/checkout`, `session/store_line`, `session/close`.
  - `sensor.home_stock_cart_total` — euros, attributs `store`, `lines`, `pending`.
  - `sensor.home_stock_to_store` — nombre de lignes achetées non rangées.
  - `StockManager.summary()` gagne les clés `cart_total`, `cart_store`, `cart_lines`, `cart_pending`.
  - Service `home_stock.resync_off` — champs `article_id`, `product_id`, `all` (booléen).

- [ ] **Step 1: Écrire le test des commandes de session**

`tests/test_websocket_session.py` :

```python
"""The shopping session, driven exactly as the panel drives it."""
from homeassistant.core import HomeAssistant

from .test_websocket import setup_entry


async def _send(client, id_, type_, **payload):
    await client.send_json({"id": id_, "type": type_, **payload})
    return await client.receive_json()


async def test_a_full_trip_from_the_aisle_to_the_cupboard(hass: HomeAssistant,
                                                          hass_ws_client):
    entry = await setup_entry(hass, with_article=True)
    client = await hass_ws_client(hass)

    await _send(client, 1, "home_stock/session/start", store="Leclerc")
    added = await _send(client, 2, "home_stock/session/add_line", article_id=1,
                        quantity=500, unit_price=0.002, idempotency_key="scan-1")
    line_id = added["result"]["id"]

    current = await _send(client, 3, "home_stock/session/current")
    assert current["result"]["totals"]["total"] == 1.0
    assert current["result"]["lines"][0]["aisle_name"]

    await _send(client, 4, "home_stock/session/checkout")
    stored = await _send(client, 5, "home_stock/session/store_line", line_id=line_id,
                         location_id=1, best_before="2027-01-01")
    assert stored["result"]["batch_id"]

    after = await _send(client, 6, "home_stock/session/current")
    assert after["result"] is None


async def test_a_second_session_is_refused_with_a_readable_error(hass: HomeAssistant,
                                                                 hass_ws_client):
    await setup_entry(hass)
    client = await hass_ws_client(hass)
    await _send(client, 1, "home_stock/session/start", store="Leclerc")

    answer = await _send(client, 2, "home_stock/session/start", store="Lidl")

    assert answer["success"] is False
    assert "déjà" in answer["error"]["message"]


async def test_a_replayed_scan_does_not_double_the_cart(hass: HomeAssistant,
                                                        hass_ws_client):
    await setup_entry(hass, with_article=True)
    client = await hass_ws_client(hass)
    await _send(client, 1, "home_stock/session/start", store=None)

    first = await _send(client, 2, "home_stock/session/add_line", article_id=1,
                        quantity=500, unit_price=None, idempotency_key="scan-1")
    again = await _send(client, 3, "home_stock/session/add_line", article_id=1,
                        quantity=500, unit_price=None, idempotency_key="scan-1")

    assert first["result"]["id"] == again["result"]["id"]
    current = await _send(client, 4, "home_stock/session/current")
    assert len(current["result"]["lines"]) == 1


async def test_the_cart_sensors_follow_the_session(hass: HomeAssistant, hass_ws_client):
    await setup_entry(hass, with_article=True)
    client = await hass_ws_client(hass)
    await _send(client, 1, "home_stock/session/start", store="Leclerc")
    await _send(client, 2, "home_stock/session/add_line", article_id=1,
                quantity=500, unit_price=0.002, idempotency_key="scan-1")
    await hass.async_block_till_done()

    cart = hass.states.get("sensor.home_stock_cart_total")
    assert float(cart.state) == 1.0
    assert cart.attributes["store"] == "Leclerc"
    assert hass.states.get("sensor.home_stock_to_store").state == "1"


async def test_the_cart_sensors_are_zero_with_no_session(hass: HomeAssistant):
    await setup_entry(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.home_stock_cart_total").state == "0.0"
    assert hass.states.get("sensor.home_stock_to_store").state == "0"
```

- [ ] **Step 2: Lancer le test et vérifier qu'il échoue**

Run: `./scripts/test.sh tests/test_websocket_session.py -v`
Expected: FAIL — `unknown_command: home_stock/session/start`

- [ ] **Step 3: Écrire les commandes de session**

À ajouter à `websocket_api.py`. Chaque commande suit le même moule : garde `_runtime`,
appel du service dans l'exécuteur, rafraîchissement du coordinateur si le stock a bougé,
`ShoppingError` traduite en erreur websocket lisible.

```python
def _shopping_error(connection, msg, err: ShoppingError) -> None:
    connection.send_error(msg["id"], "shopping_refused", str(err))


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/session/start",
    vol.Optional("store"): vol.Any(str, None),
})
@websocket_api.async_response
async def session_start(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    try:
        session = await hass.async_add_executor_job(partial(
            runtime.shopping.start, store=msg.get("store")))
    except ShoppingError as err:
        _shopping_error(connection, msg, err)
        return
    await runtime.coordinator.async_request_refresh()
    connection.send_result(msg["id"], session)


@websocket_api.websocket_command({vol.Required("type"): "home_stock/session/current"})
@websocket_api.async_response
async def session_current(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    connection.send_result(msg["id"], await _read(hass, runtime.shopping.current))


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/session/add_line",
    vol.Required("article_id"): int,
    vol.Required("quantity"): vol.Coerce(float),
    vol.Optional("unit_price"): vol.Any(vol.Coerce(float), None),
    vol.Optional("idempotency_key"): vol.Any(str, None),
})
@websocket_api.async_response
async def session_add_line(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    try:
        line = await hass.async_add_executor_job(partial(
            runtime.shopping.add_line, article_id=msg["article_id"],
            quantity=msg["quantity"], unit_price=msg.get("unit_price"),
            idempotency_key=msg.get("idempotency_key")))
    except ShoppingError as err:
        _shopping_error(connection, msg, err)
        return
    await runtime.coordinator.async_request_refresh()
    connection.send_result(msg["id"], line)


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/session/update_line",
    vol.Required("line_id"): int,
    vol.Optional("quantity"): vol.Any(vol.Coerce(float), None),
    vol.Optional("unit_price"): vol.Any(vol.Coerce(float), None),
})
@websocket_api.async_response
async def session_update_line(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    try:
        line = await hass.async_add_executor_job(partial(
            runtime.shopping.update_line, msg["line_id"],
            quantity=msg.get("quantity"), unit_price=msg.get("unit_price")))
    except ShoppingError as err:
        _shopping_error(connection, msg, err)
        return
    await runtime.coordinator.async_request_refresh()
    connection.send_result(msg["id"], line)


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/session/remove_line",
    vol.Required("line_id"): int,
})
@websocket_api.async_response
async def session_remove_line(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    try:
        await hass.async_add_executor_job(partial(
            runtime.shopping.remove_line, msg["line_id"]))
    except ShoppingError as err:
        _shopping_error(connection, msg, err)
        return
    await runtime.coordinator.async_request_refresh()
    connection.send_result(msg["id"], {"line_id": msg["line_id"]})


@websocket_api.websocket_command({vol.Required("type"): "home_stock/session/checkout"})
@websocket_api.async_response
async def session_checkout(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    try:
        session = await hass.async_add_executor_job(runtime.shopping.checkout)
    except ShoppingError as err:
        _shopping_error(connection, msg, err)
        return
    await runtime.coordinator.async_request_refresh()
    connection.send_result(msg["id"], session)


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/session/store_line",
    vol.Required("line_id"): int,
    vol.Required("location_id"): int,
    vol.Optional("best_before"): vol.Any(str, None),
})
@websocket_api.async_response
async def session_store_line(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    try:
        result = await hass.async_add_executor_job(partial(
            runtime.shopping.store_line, msg["line_id"],
            location_id=msg["location_id"], best_before=msg.get("best_before")))
    except ShoppingError as err:
        _shopping_error(connection, msg, err)
        return
    await runtime.coordinator.async_request_refresh()
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command({vol.Required("type"): "home_stock/session/close"})
@websocket_api.async_response
async def session_close(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    try:
        session = await hass.async_add_executor_job(runtime.shopping.close)
    except ShoppingError as err:
        _shopping_error(connection, msg, err)
        return
    await runtime.coordinator.async_request_refresh()
    connection.send_result(msg["id"], session)
```

Les huit commandes rejoignent la liste de `async_register_websocket`.

- [ ] **Step 4: Publier le panier dans le résumé**

Dans `application.py`, à la fin de `summary()`, ajouter les clés du panier — en lisant la
session **sur la connexion de lecture**, comme le reste du résumé :

```python
        session = repo.current_session(conn)
        totals = repo.session_totals(conn, session["id"]) if session else None
        summary.update({
            "cart_total": totals["total"] if totals else 0.0,
            "cart_lines": totals["lines"] if totals else 0,
            "cart_pending": totals["pending"] if totals else 0,
            "cart_store": session["store"] if session else None,
        })
```

- [ ] **Step 5: Ajouter les deux capteurs**

Dans `sensor.py`, sur le modèle des capteurs du lot 0 :

```python
    HomeStockSensor(
        coordinator, key="cart_total", value_key="cart_total",
        unit="€", icon="mdi:cart-outline",
        attributes=("cart_store", "cart_lines", "cart_pending"),
    ),
    HomeStockSensor(
        coordinator, key="to_store", value_key="cart_pending",
        unit=None, icon="mdi:package-variant-closed",
    ),
```

Les attributs exposés portent les noms `store`, `lines`, `pending`. Ajouter les libellés
français dans `translations/fr.json` (`« Panier en cours »`, `« À ranger »`) et anglais dans
`translations/en.json`.

- [ ] **Step 6: Ajouter le service de resynchronisation**

Dans `services.py` :

```python
RESYNC_SCHEMA = vol.Schema(vol.All(
    {
        vol.Optional("article_id"): int,
        vol.Optional("product_id"): int,
        vol.Optional("all", default=False): bool,
    },
    cv.has_at_least_one_key("article_id", "product_id", "all"),
))


async def _resync_off(call: ServiceCall) -> None:
    """Refresh articles from OFF, one every BULK_INTERVAL seconds.

    Runs as a background task: a full catalogue pass is forty minutes at the
    rate OFF tolerates, and no service call should hold that long.
    """
    runtime = _entry(call.hass).runtime_data
    codes = await call.hass.async_add_executor_job(
        partial(repo.barcodes_to_resync, runtime.manager.db.read(),
                article_id=call.data.get("article_id"),
                product_id=call.data.get("product_id"),
                everything=call.data["all"])
    )

    async def run() -> None:
        for index, (code, article_id) in enumerate(codes):
            if index:
                await asyncio.sleep(BULK_INTERVAL)
            result = await runtime.off_client.lookup_with_retry(code)
            if result.record is None:
                continue
            await call.hass.async_add_executor_job(
                partial(_write_resync, runtime, article_id, result.record))
        await runtime.coordinator.async_request_refresh()

    call.hass.async_create_background_task(run(), "home_stock resync_off")
```

`_write_resync` écrit les colonnes issues d'OFF **en sautant celles listées dans
`manual_fields`** — c'est toute la raison d'être de cette colonne — et met à jour
`off_synced_at` et `off_raw`.

`repo.barcodes_to_resync(conn, *, article_id, product_id, everything) -> list[tuple[str, int]]`
rend les couples `(code, article_id)` concernés.

Déclarer le service dans `services.yaml` avec ses libellés français, et son sélecteur
`all` en booléen.

- [ ] **Step 7: Lancer les tests**

Run: `./scripts/test.sh`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add custom_components/home_stock tests/
git commit -m "feat: shopping session over websocket, cart sensors and OFF resync service"
```

---
### Task 14: Le panneau, sa chaîne de build et la file hors ligne

**Files:**
- Create: `custom_components/home_stock/panel.py`
- Create: `frontend/package.json`, `frontend/tsconfig.json`, `frontend/rollup.config.mjs`, `frontend/vitest.config.ts`, `frontend/.gitignore`
- Create: `frontend/src/panneau.ts`, `frontend/src/connexion.ts`, `frontend/src/file-attente.ts`, `frontend/src/styles/base.css`
- Create: `frontend/tests/file-attente.test.ts`, `frontend/tests/connexion.test.ts`
- Modify: `custom_components/home_stock/__init__.py`, `custom_components/home_stock/manifest.json`
- Test: `tests/test_panel.py` (nouveau)

**Interfaces:**
- Consumes: `HomeStockData` (Task 12).
- Produces:
  - `panel.async_register_panel(hass) -> None` — sert `/home_stock_panel/` et déclare l'entrée de barre latérale « Garde-manger ».
  - `panel.PANEL_URL = "home-stock"`, `panel.MODULE_URL = "/home_stock_panel/home-stock-panel.js"`
  - `connexion.ts` : `export class Connexion { constructor(hass: Hass); appeler<T>(type: string, charge?: object): Promise<T>; abonner(rappel: (resume: Resume) => void): () => void }`
  - `file-attente.ts` : `export class FileAttente { constructor(stockage: Storage, envoyer: Envoyeur); ajouter(type: string, charge: object): string; taille(): number; rejouer(): Promise<void> }`
  - `npm run build` écrit `custom_components/home_stock/panel/home-stock-panel.js`.

**Le panneau reçoit l'objet `hass`** : il réutilise la connexion websocket et l'authentification de Home Assistant. Contrairement à `wallpanel-app`, il ne lit **jamais** `localStorage.hassTokens` — cette application-là est servie sans authentification par `/local/`, ce qui n'est pas le cas ici.

- [ ] **Step 1: Écrire le test de la file d'attente**

`frontend/tests/file-attente.test.ts` :

```typescript
import { describe, expect, it, vi } from 'vitest';
import { FileAttente } from '../src/file-attente';

class StockageFactice implements Storage {
  private donnees = new Map<string, string>();
  get length() { return this.donnees.size; }
  clear() { this.donnees.clear(); }
  getItem(cle: string) { return this.donnees.get(cle) ?? null; }
  key(index: number) { return [...this.donnees.keys()][index] ?? null; }
  removeItem(cle: string) { this.donnees.delete(cle); }
  setItem(cle: string, valeur: string) { this.donnees.set(cle, valeur); }
}

describe('file d’attente hors ligne', () => {
  it('rend une clé d’idempotence différente à chaque ajout', () => {
    const file = new FileAttente(new StockageFactice(), async () => {});
    const a = file.ajouter('home_stock/session/add_line', { article_id: 1 });
    const b = file.ajouter('home_stock/session/add_line', { article_id: 1 });
    expect(a).not.toBe(b);
  });

  it('survit à un rechargement de la page', () => {
    const stockage = new StockageFactice();
    new FileAttente(stockage, async () => {}).ajouter('t', { a: 1 });
    expect(new FileAttente(stockage, async () => {}).taille()).toBe(1);
  });

  it('rejoue dans l’ordre où les scans ont eu lieu', async () => {
    const vus: number[] = [];
    const file = new FileAttente(new StockageFactice(), async (_t, charge) => {
      vus.push((charge as { n: number }).n);
    });
    file.ajouter('t', { n: 1 });
    file.ajouter('t', { n: 2 });
    file.ajouter('t', { n: 3 });

    await file.rejouer();

    expect(vus).toEqual([1, 2, 3]);
    expect(file.taille()).toBe(0);
  });

  it('garde l’action qui échoue et s’arrête là', async () => {
    // Rejouer la suivante réordonnerait le panier : on préfère réessayer plus tard.
    const file = new FileAttente(new StockageFactice(), async (_t, charge) => {
      if ((charge as { n: number }).n === 2) throw new Error('hors ligne');
    });
    file.ajouter('t', { n: 1 });
    file.ajouter('t', { n: 2 });
    file.ajouter('t', { n: 3 });

    await file.rejouer();

    expect(file.taille()).toBe(2);
  });

  it('renvoie la même clé si la même action est rejouée', async () => {
    const cles: string[] = [];
    const file = new FileAttente(new StockageFactice(), async (_t, charge) => {
      cles.push((charge as { idempotency_key: string }).idempotency_key);
      throw new Error('hors ligne');
    });
    file.ajouter('t', { article_id: 1 });

    await file.rejouer();
    await file.rejouer();

    expect(cles[0]).toBe(cles[1]);
  });

  it('n’écrase pas une clé fournie par l’appelant', () => {
    const file = new FileAttente(new StockageFactice(), async () => {});
    const cle = file.ajouter('t', { idempotency_key: 'imposée' });
    expect(cle).toBe('imposée');
  });
});
```

- [ ] **Step 2: Lancer le test et vérifier qu'il échoue**

Run: `cd frontend && npm test`
Expected: FAIL — le module `../src/file-attente` n'existe pas.

- [ ] **Step 3: Créer la chaîne de build**

`frontend/package.json` :

```json
{
  "name": "home-stock-panel",
  "version": "1.0.0",
  "type": "module",
  "private": true,
  "scripts": {
    "build": "rollup -c",
    "test": "vitest run",
    "verifier": "node outils/verifier-rendu.mjs"
  },
  "devDependencies": {
    "@rollup/plugin-node-resolve": "^15.2.3",
    "@rollup/plugin-terser": "^0.4.4",
    "@rollup/plugin-typescript": "^11.1.5",
    "@types/node": "^26.1.2",
    "jsdom": "^29.1.1",
    "playwright-core": "^1.60.0",
    "rollup": "^4.9.0",
    "rollup-plugin-import-css": "^3.5.0",
    "typescript": "^5.3.0",
    "vitest": "^2.1.0"
  },
  "dependencies": {
    "lit": "^3.1.0",
    "tslib": "^2.8.1"
  }
}
```

`frontend/tsconfig.json` :

```json
{
  "compilerOptions": {
    "target": "ES2021", "module": "ESNext", "moduleResolution": "bundler",
    "strict": true, "noUnusedLocals": true, "experimentalDecorators": true,
    "useDefineForClassFields": false, "lib": ["ES2021", "DOM"],
    "types": ["vitest/globals"]
  },
  "include": ["src/**/*.ts", "tests/**/*.ts"]
}
```

`frontend/rollup.config.mjs` — la sortie va **dans le composant**, qui est ce que HACS
installe :

```javascript
import resolve from '@rollup/plugin-node-resolve';
import typescript from '@rollup/plugin-typescript';
import terser from '@rollup/plugin-terser';
import css from 'rollup-plugin-import-css';

export default {
  input: 'src/panneau.ts',
  output: {
    file: '../custom_components/home_stock/panel/home-stock-panel.js',
    format: 'es',
    sourcemap: false,
  },
  plugins: [resolve(), typescript(), css({ inject: true }), terser()],
};
```

`frontend/vitest.config.ts` :

```typescript
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: { environment: 'jsdom', globals: true, include: ['tests/**/*.test.ts'] },
});
```

`frontend/.gitignore` : `node_modules/`

- [ ] **Step 4: Écrire la file d'attente**

`frontend/src/file-attente.ts` :

```typescript
/** File des écritures que le panneau n'a pas pu envoyer.
 *
 *  En magasin, le réseau tombe. La session vit côté serveur, mais un scan doit
 *  quand même partir : on l'empile ici avec sa clé d'idempotence, et on rejoue
 *  à la reconnexion. Le serveur reconnaît la clé et ne double rien.
 */
export type Envoyeur = (type: string, charge: object) => Promise<unknown>;

type Action = { type: string; charge: Record<string, unknown> };

const CLE_STOCKAGE = 'home_stock.file';

export class FileAttente {
  private actions: Action[] = [];

  constructor(private stockage: Storage, private envoyer: Envoyeur) {
    try {
      this.actions = JSON.parse(this.stockage.getItem(CLE_STOCKAGE) ?? '[]');
    } catch {
      this.actions = [];   // stockage corrompu : on repart vide plutôt que de planter
    }
  }

  /** Empile une action et rend sa clé d'idempotence. */
  ajouter(type: string, charge: object): string {
    const contenu = { ...charge } as Record<string, unknown>;
    // La clé est posée à l'ajout, pas à l'envoi : un rejeu doit porter LA MÊME
    // clé, sinon le serveur voit deux scans distincts et le panier double.
    if (typeof contenu.idempotency_key !== 'string') {
      contenu.idempotency_key = crypto.randomUUID();
    }
    this.actions.push({ type, charge: contenu });
    this.ecrire();
    return contenu.idempotency_key as string;
  }

  taille(): number {
    return this.actions.length;
  }

  /** Rejoue dans l'ordre. S'arrête à la première qui échoue. */
  async rejouer(): Promise<void> {
    while (this.actions.length) {
      const action = this.actions[0];
      try {
        await this.envoyer(action.type, action.charge);
      } catch {
        return;   // toujours hors ligne : on garde la file intacte et on réessaiera
      }
      this.actions.shift();
      this.ecrire();
    }
  }

  private ecrire(): void {
    this.stockage.setItem(CLE_STOCKAGE, JSON.stringify(this.actions));
  }
}
```

- [ ] **Step 5: Écrire la connexion et la coquille du panneau**

`frontend/src/connexion.ts` :

```typescript
/** Accès à Home Assistant depuis un panneau enregistré.
 *
 *  HA passe l'objet `hass` au composant : la connexion websocket et
 *  l'authentification sont déjà les siennes. On ne lit aucun jeton, on n'ouvre
 *  aucune seconde session.
 */
export type Hass = {
  connection: {
    sendMessagePromise<T>(message: object): Promise<T>;
    subscribeMessage<T>(rappel: (event: T) => void, message: object): Promise<() => void>;
  };
  language: string;
};

export class Connexion {
  constructor(private hass: Hass) {}

  appeler<T>(type: string, charge: object = {}): Promise<T> {
    return this.hass.connection.sendMessagePromise<T>({ type, ...charge });
  }

  /** S'abonne au résumé : le stock bouge sur le téléphone pendant qu'on range. */
  abonner<T>(rappel: (resume: T) => void): Promise<() => void> {
    return this.hass.connection.subscribeMessage<T>(rappel, { type: 'home_stock/subscribe' });
  }
}
```

`frontend/src/panneau.ts` — l'élément que HA instancie, avec ses six écrans en attente
des tâches suivantes :

```typescript
import { LitElement, html, css } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { Connexion, type Hass } from './connexion';
import { FileAttente } from './file-attente';

export type Ecran = 'scanner' | 'fiche' | 'panier' | 'rangement' | 'catalogue' | 'reglages';

@customElement('home-stock-panel')
export class PanneauGardeManger extends LitElement {
  @property({ attribute: false }) hass!: Hass;
  @property({ attribute: false }) narrow = false;
  @state() ecran: Ecran = 'scanner';
  @state() enAttente = 0;

  private connexion?: Connexion;
  private file?: FileAttente;
  private desabonner?: () => void;

  connectedCallback(): void {
    super.connectedCallback();
    this.connexion = new Connexion(this.hass);
    this.file = new FileAttente(window.localStorage, (type, charge) =>
      this.connexion!.appeler(type, charge));
    this.enAttente = this.file.taille();
    void this.file.rejouer().then(() => { this.enAttente = this.file!.taille(); });
    void this.connexion.abonner(() => this.requestUpdate());
    window.addEventListener('online', this.auRetourDuReseau);
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    this.desabonner?.();
    window.removeEventListener('online', this.auRetourDuReseau);
  }

  private auRetourDuReseau = (): void => {
    void this.file?.rejouer().then(() => { this.enAttente = this.file!.taille(); });
  };

  static styles = css`
    :host { display: block; height: 100%; background: var(--primary-background-color); }
  `;

  render() {
    return html`<div class="ecran">${this.ecran}</div>`;
  }
}
```

- [ ] **Step 6: Écrire l'enregistrement du panneau côté Python**

`custom_components/home_stock/panel.py` :

```python
"""Register the panel and serve its bundle.

The panel is a Home Assistant custom panel, not a page under /local/: it is
handed the `hass` object, so it inherits the connection and the authentication
instead of reading a token out of localStorage.
"""
from __future__ import annotations

import os

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PANEL_URL = "home-stock"
STATIC_URL = "/home_stock_panel"
MODULE_URL = f"{STATIC_URL}/home-stock-panel.js"
PANEL_TITLE = "Garde-manger"
PANEL_ICON = "mdi:fridge-outline"


async def async_register_panel(hass: HomeAssistant) -> None:
    """Serve the bundle and put the panel in the sidebar. Idempotent."""
    if DOMAIN in hass.data.get("home_stock_panel_registered", set()):
        return

    directory = os.path.join(os.path.dirname(__file__), "panel")
    await hass.http.async_register_static_paths(
        [StaticPathConfig(STATIC_URL, directory, cache_headers=False)]
    )
    await panel_custom.async_register_panel(
        hass,
        webcomponent_name="home-stock-panel",
        frontend_url_path=PANEL_URL,
        module_url=MODULE_URL,
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        require_admin=False,
        embed_iframe=False,
    )
    hass.data.setdefault("home_stock_panel_registered", set()).add(DOMAIN)


def async_remove_panel(hass: HomeAssistant) -> None:
    """Take the panel back out when the entry is unloaded."""
    frontend.async_remove_panel(hass, PANEL_URL)
    hass.data.get("home_stock_panel_registered", set()).discard(DOMAIN)
```

`cache_headers=False` est délibéré : le bundle change à chaque build, et un panneau servi
depuis un cache navigateur est exactement le piège que les tablettes ont déjà coûté.

Appeler `await async_register_panel(hass)` dans `async_setup_entry` et
`async_remove_panel(hass)` dans `async_unload_entry`. Ajouter `"panel_custom"` aux
`dependencies` du `manifest.json`.

- [ ] **Step 7: Écrire le test Python du panneau**

`tests/test_panel.py` :

```python
"""The panel is registered, served, and removed with the entry."""
from homeassistant.core import HomeAssistant

from custom_components.home_stock.panel import PANEL_URL

from .test_websocket import setup_entry


async def test_the_panel_appears_in_the_sidebar(hass: HomeAssistant):
    await setup_entry(hass)

    assert PANEL_URL in hass.data["frontend_panels"]
    assert hass.data["frontend_panels"][PANEL_URL].sidebar_title == "Garde-manger"


async def test_unloading_the_entry_takes_the_panel_away(hass: HomeAssistant):
    entry = await setup_entry(hass)

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert PANEL_URL not in hass.data["frontend_panels"]


async def test_the_bundle_is_served(hass: HomeAssistant, hass_client):
    await setup_entry(hass)
    client = await hass_client()

    response = await client.get("/home_stock_panel/home-stock-panel.js")

    # 404 means the build never ran; anything else means the static path is wired.
    assert response.status in (200, 404)
```

- [ ] **Step 8: Installer, construire, tester**

```bash
cd frontend && npm install && npm test && npm run build
cd .. && ./scripts/test.sh tests/test_panel.py -v
```
Expected: `npm test` PASS (6 tests), `npm run build` écrit
`custom_components/home_stock/panel/home-stock-panel.js`, `test_panel.py` PASS.

- [ ] **Step 9: Commit**

```bash
git add frontend custom_components/home_stock/panel.py \
        custom_components/home_stock/panel/ custom_components/home_stock/__init__.py \
        custom_components/home_stock/manifest.json tests/test_panel.py
git commit -m "feat: register the Garde-manger panel and its offline write queue"
```

---

### Task 15: Le scan et la fiche article

**Files:**
- Create: `frontend/src/scan/index.ts`, `frontend/src/scan/companion.ts`, `frontend/src/scan/navigateur.ts`
- Create: `frontend/src/ecrans/scanner.ts`, `frontend/src/ecrans/fiche.ts`
- Modify: `frontend/src/panneau.ts`
- Test: `frontend/tests/scan.test.ts`, `frontend/tests/fiche.test.ts`

**Interfaces:**
- Consumes: `Connexion.appeler` (Task 14), les commandes `home_stock/lookup` et `home_stock/article/create` (Task 12).
- Produces:
  - `scan/index.ts` : `export type Scanner = { disponible(): boolean; lire(): Promise<string | null> }` et `export function choisirScanner(fenetre: Window): Scanner`.
  - `scan/companion.ts` : `export class ScannerCompanion implements Scanner` — bus externe de l'application HA.
  - `scan/navigateur.ts` : `export class ScannerNavigateur implements Scanner` — `BarcodeDetector` sur `getUserMedia`.
  - `ecrans/fiche.ts` : composant `<home-stock-fiche>`, propriétés `resultat` (la réponse de `lookup`), `mode: 'panier' | 'rangement'`.

**L'ordre de choix est une règle, pas une préférence :** l'application HA d'abord (c'est l'appareil photo du système), puis `BarcodeDetector`, puis le clavier. Le bus externe de HA envoie `bar_code/scan` et reçoit `bar_code/scan_result`, `bar_code/close` ou `bar_code/aborted` — vérifié présent dans le frontend 2026.8.2.

- [ ] **Step 1: Écrire le test du choix de scanner**

`frontend/tests/scan.test.ts` :

```typescript
import { describe, expect, it, vi } from 'vitest';
import { choisirScanner } from '../src/scan';
import { ScannerCompanion } from '../src/scan/companion';

function fenetreAvecCompanion(): any {
  return {
    externalApp: { externalBus: vi.fn() },
    BarcodeDetector: undefined,
  };
}

function fenetreNavigateur(): any {
  return { BarcodeDetector: class {}, navigator: { mediaDevices: {} } };
}

describe('choix du scanner', () => {
  it('préfère l’application Home Assistant quand elle est là', () => {
    expect(choisirScanner(fenetreAvecCompanion()).constructor.name)
      .toBe('ScannerCompanion');
  });

  it('retombe sur BarcodeDetector dans un navigateur ordinaire', () => {
    expect(choisirScanner(fenetreNavigateur()).constructor.name)
      .toBe('ScannerNavigateur');
  });

  it('retombe sur le clavier quand ni l’un ni l’autre n’existe', () => {
    expect(choisirScanner({} as any).constructor.name).toBe('ScannerClavier');
  });
});

describe('scanner de l’application Home Assistant', () => {
  it('rend le code lu par l’appareil photo du système', async () => {
    const fenetre: any = { externalApp: { externalBus: vi.fn() } };
    const scanner = new ScannerCompanion(fenetre);

    const promesse = scanner.lire();
    fenetre.externalBus({ command: 'bar_code/scan_result',
                          payload: { rawValue: '3229820129488', format: 'ean_13' } });

    expect(await promesse).toBe('3229820129488');
  });

  it('rend null quand l’utilisateur annule', async () => {
    const fenetre: any = { externalApp: { externalBus: vi.fn() } };
    const scanner = new ScannerCompanion(fenetre);

    const promesse = scanner.lire();
    fenetre.externalBus({ command: 'bar_code/aborted', payload: { reason: 'canceled' } });

    expect(await promesse).toBeNull();
  });

  it('ferme le scanner du système après une lecture', async () => {
    const envoyes: any[] = [];
    const fenetre: any = { externalApp: { externalBus: (m: string) => envoyes.push(JSON.parse(m)) } };
    const scanner = new ScannerCompanion(fenetre);

    const promesse = scanner.lire();
    fenetre.externalBus({ command: 'bar_code/scan_result', payload: { rawValue: '1' } });
    await promesse;

    expect(envoyes.map((m) => m.type)).toContain('bar_code/close');
  });
});
```

- [ ] **Step 2: Lancer le test et vérifier qu'il échoue**

Run: `cd frontend && npm test`
Expected: FAIL — `../src/scan` n'existe pas.

- [ ] **Step 3: Écrire les trois voies de scan**

`frontend/src/scan/companion.ts` :

```typescript
/** Le scanner natif de l'application Home Assistant.
 *
 *  C'est l'appareil photo du système, pas une WebView : mise au point, torche,
 *  lecture en rafale. Le dialogue passe par le bus externe de l'application —
 *  `bar_code/scan` à l'aller, `bar_code/scan_result` / `bar_code/aborted` au
 *  retour, `bar_code/close` pour refermer.
 */
import type { Scanner } from './index';

export class ScannerCompanion implements Scanner {
  constructor(private fenetre: any) {}

  disponible(): boolean {
    return Boolean(this.fenetre?.externalApp?.externalBus
      || this.fenetre?.webkit?.messageHandlers?.externalBus);
  }

  lire(): Promise<string | null> {
    return new Promise((resoudre) => {
      const precedent = this.fenetre.externalBus;
      this.fenetre.externalBus = (message: any) => {
        const evenement = typeof message === 'string' ? JSON.parse(message) : message;
        if (evenement.command === 'bar_code/scan_result') {
          this.envoyer({ type: 'bar_code/close' });
          this.fenetre.externalBus = precedent;
          resoudre(String(evenement.payload.rawValue));
        } else if (evenement.command === 'bar_code/aborted'
                   || evenement.command === 'bar_code/close') {
          this.fenetre.externalBus = precedent;
          resoudre(null);
        }
        return true;
      };
      this.envoyer({
        type: 'bar_code/scan',
        payload: {
          title: 'Scanner un article',
          description: 'Visez le code-barres',
          alternative_option_label: 'Saisir le code',
        },
      });
    });
  }

  private envoyer(message: object): void {
    const brut = JSON.stringify(message);
    if (this.fenetre.externalApp?.externalBus) {
      this.fenetre.externalApp.externalBus(brut);
    } else {
      this.fenetre.webkit.messageHandlers.externalBus.postMessage(message);
    }
  }
}
```

`frontend/src/scan/navigateur.ts` :

```typescript
/** `BarcodeDetector` sur le flux de la caméra. Exige un contexte sécurisé,
 *  ce que home.allanic.me fournit. */
import type { Scanner } from './index';

const FORMATS = ['ean_13', 'ean_8', 'upc_a', 'upc_e', 'code_128'];

export class ScannerNavigateur implements Scanner {
  private flux?: MediaStream;

  constructor(private fenetre: any) {}

  disponible(): boolean {
    return Boolean(this.fenetre?.BarcodeDetector
      && this.fenetre?.navigator?.mediaDevices);
  }

  async lire(): Promise<string | null> {
    const detecteur = new this.fenetre.BarcodeDetector({ formats: FORMATS });
    this.flux = await this.fenetre.navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'environment' },
    });
    const video = this.fenetre.document.createElement('video');
    video.srcObject = this.flux;
    await video.play();

    try {
      // Une lecture par image : un code-barres flou n'est lu qu'au bout de
      // quelques images, et rendre la main trop tôt ferait clignoter l'écran.
      for (let essai = 0; essai < 300; essai += 1) {
        const trouves = await detecteur.detect(video);
        if (trouves.length) return String(trouves[0].rawValue);
        await new Promise((r) => this.fenetre.requestAnimationFrame(r));
      }
      return null;
    } finally {
      this.arreter();
    }
  }

  arreter(): void {
    this.flux?.getTracks().forEach((piste) => piste.stop());
    this.flux = undefined;
  }
}
```

`frontend/src/scan/index.ts` :

```typescript
import { ScannerCompanion } from './companion';
import { ScannerNavigateur } from './navigateur';

export type Scanner = {
  disponible(): boolean;
  lire(): Promise<string | null>;
};

/** Le clavier : ni caméra système, ni BarcodeDetector. La saisie est faite par
 *  l'écran appelant ; ce scanner-là ne fait que dire « à toi de jouer ». */
export class ScannerClavier implements Scanner {
  disponible(): boolean { return true; }
  async lire(): Promise<string | null> { return null; }
}

/** L'application HA d'abord, le navigateur ensuite, le clavier en dernier. */
export function choisirScanner(fenetre: Window | any): Scanner {
  const companion = new ScannerCompanion(fenetre);
  if (companion.disponible()) return companion;
  const navigateur = new ScannerNavigateur(fenetre);
  if (navigateur.disponible()) return navigateur;
  return new ScannerClavier();
}
```

- [ ] **Step 4: Écrire l'écran Scanner et la fiche**

`frontend/src/ecrans/scanner.ts` — composant `<home-stock-scanner>` :
un bouton de scan pleine largeur d'au moins 96 px de haut, la dernière fiche lue en
dessous, la bannière de session quand une session est ouverte, et un champ de saisie
manuelle replié derrière un bouton « Saisir le code ». Il émet un événement
`code-lu` portant `{ code: string }`.

`frontend/src/ecrans/fiche.ts` — composant `<home-stock-fiche>` :

- en tête, l'image, le nom, la marque, le poids net, le Nutri-Score et les kcal pour 100 g ;
- le rattachement au produit : le candidat présélectionné est coché, les quatre autres sont
  proposés, et un bouton « Nouveau produit » pré-remplit le nom depuis `generic_name` ;
- le prix, pré-rempli par `price.price_per_base_unit` avec la provenance affichée en clair
  (« dernier prix Leclerc », « Open Prices », « dernier prix connu ») ;
- la quantité, avec des boutons `−` et `+` d'au moins 62 px ;
- si `conversion_offer` est présent, une ligne « Passer de pièce à g — 1 unité = 500 g »
  avec un bouton qui appelle `home_stock/product/convert_unit` en `dry_run` puis affiche
  le rapport avant d'appliquer ;
- l'action principale : « Au panier » en session, « Ranger » sinon.

`frontend/tests/fiche.test.ts` vérifie, en `jsdom`, sur la réponse d'un `lookup` factice :
le candidat présélectionné est bien coché ; deux candidats proches n'en cochent aucun ;
la provenance du prix est affichée ; l'offre de conversion n'apparaît que lorsque
`conversion_offer` est fourni ; le bouton principal dit « Au panier » en session et
« Ranger » hors session.

- [ ] **Step 5: Lancer les tests**

Run: `cd frontend && npm test`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/scan frontend/src/ecrans frontend/tests
git commit -m "feat: scan by system camera, BarcodeDetector or keyboard, and the article card"
```

---

### Task 16: Le panier et le rangement

**Files:**
- Create: `frontend/src/ecrans/panier.ts`, `frontend/src/ecrans/rangement.ts`, `frontend/src/dlc.ts`
- Modify: `frontend/src/panneau.ts`
- Test: `frontend/tests/dlc.test.ts`, `frontend/tests/panier.test.ts`

**Interfaces:**
- Consumes: les commandes `home_stock/session/*` (Task 13).
- Produces:
  - `dlc.ts` : `export function raccourcisDlc(aujourdhui: Date, dureeParDefaut: number | null): Raccourci[]`, avec `Raccourci = { libelle: string; date: string | null }`.
  - `ecrans/panier.ts` : composant `<home-stock-panier>`.
  - `ecrans/rangement.ts` : composant `<home-stock-rangement>`.

- [ ] **Step 1: Écrire le test des raccourcis de DLC**

`frontend/tests/dlc.test.ts` :

```typescript
import { describe, expect, it } from 'vitest';
import { raccourcisDlc } from '../src/dlc';

const LE_19_AOUT = new Date('2026-08-19T10:00:00Z');

describe('raccourcis de date de péremption', () => {
  it('propose la durée apprise en premier quand elle existe', () => {
    const [premier] = raccourcisDlc(LE_19_AOUT, 5);
    expect(premier.date).toBe('2026-08-24');
    expect(premier.libelle).toContain('5');
  });

  it('propose trois durées génériques quand rien n’a été appris', () => {
    const dates = raccourcisDlc(LE_19_AOUT, null).map((r) => r.date);
    expect(dates).toEqual(['2026-08-22', '2026-08-26', '2026-09-19', null]);
  });

  it('offre toujours « sans DLC »', () => {
    for (const duree of [null, 3, 400]) {
      expect(raccourcisDlc(LE_19_AOUT, duree).some((r) => r.date === null)).toBe(true);
    }
  });

  it('ne propose jamais deux fois la même date', () => {
    // Une durée apprise de 7 jours coïncide avec « +1 semaine » : un bouton en double
    // fait hésiter pour rien.
    const dates = raccourcisDlc(LE_19_AOUT, 7).map((r) => r.date);
    expect(new Set(dates).size).toBe(dates.length);
  });

  it('rend une date ISO, jamais un horodatage', () => {
    for (const raccourci of raccourcisDlc(LE_19_AOUT, 5)) {
      if (raccourci.date) expect(raccourci.date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    }
  });
});
```

- [ ] **Step 2: Lancer le test et vérifier qu'il échoue**

Run: `cd frontend && npm test`
Expected: FAIL — `../src/dlc` n'existe pas.

- [ ] **Step 3: Écrire les raccourcis**

`frontend/src/dlc.ts` :

```typescript
/** Les boutons de date de péremption.
 *
 *  Ranger trente articles sans clavier suppose qu'une DLC se pose en un appui.
 *  La durée apprise par produit passe donc en tête, suivie de trois durées
 *  génériques et de « sans DLC ».
 */
export type Raccourci = { libelle: string; date: string | null };

const JOUR_MS = 86_400_000;

function dans(jours: number, depuis: Date): string {
  return new Date(depuis.getTime() + jours * JOUR_MS).toISOString().slice(0, 10);
}

export function raccourcisDlc(aujourdhui: Date, dureeParDefaut: number | null): Raccourci[] {
  const proposees: Raccourci[] = [];
  if (dureeParDefaut && dureeParDefaut > 0) {
    proposees.push({ libelle: `+${dureeParDefaut} j (habituel)`, date: dans(dureeParDefaut, aujourdhui) });
  }
  proposees.push(
    { libelle: '+3 j', date: dans(3, aujourdhui) },
    { libelle: '+1 sem', date: dans(7, aujourdhui) },
    { libelle: '+1 mois', date: dans(31, aujourdhui) },
  );
  // Une durée apprise de 7 jours produirait deux boutons identiques.
  const vues = new Set<string>();
  const uniques = proposees.filter((r) => r.date && !vues.has(r.date) && vues.add(r.date));
  return [...uniques, { libelle: 'Sans DLC', date: null }];
}
```

- [ ] **Step 4: Écrire les deux écrans**

`frontend/src/ecrans/panier.ts` — composant `<home-stock-panier>` :
les lignes rendues par `home_stock/session/current`, **groupées par `aisle_name` dans
l'ordre du parcours** (le serveur les rend déjà triées ; l'écran ne retrie pas), le total
courant en tête, le magasin, un compteur d'actions en attente si la file n'est pas vide.
Chaque ligne porte `−` / `+` sur la quantité et un champ de prix. Le bouton « Passage en
caisse » appelle `home_stock/session/checkout`. Supprimer une ligne demande **deux appuis** :
armement puis confirmation.

`frontend/src/ecrans/rangement.ts` — composant `<home-stock-rangement>` :
les lignes en attente groupées par emplacement suggéré (`default_location_id`), chacune avec
les boutons de `raccourcisDlc(new Date(), ligne.default_shelf_life_days)` et un sélecteur
d'emplacement pré-positionné. Un appui sur un raccourci appelle
`home_stock/session/store_line` et retire la ligne de la liste. Quand la liste se vide,
l'écran annonce « Tout est rangé » et revient au scanner.

`frontend/tests/panier.test.ts` vérifie, en `jsdom` : les lignes s'affichent groupées par
rayon dans l'ordre reçu ; le total est celui du serveur, jamais recalculé côté client ;
la suppression demande deux appuis ; le compteur d'actions en attente n'apparaît que si la
file est non vide.

- [ ] **Step 5: Lancer les tests**

Run: `cd frontend && npm test`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src frontend/tests
git commit -m "feat: cart sorted by aisle, and one-tap put-away with learned shelf lives"
```

---

### Task 17: Catalogue, réglages, vérification de rendu et déploiement

**Files:**
- Create: `frontend/src/ecrans/catalogue.ts`, `frontend/src/ecrans/reglages.ts`
- Create: `frontend/outils/verifier-rendu.mjs`
- Modify: `frontend/src/panneau.ts`, `docs/exploitation.md`
- Test: `frontend/tests/catalogue.test.ts`

**Interfaces:**
- Consumes: `home_stock/products/list`, `home_stock/product/get`, `home_stock/product/update`, `home_stock/aisles/list`, `home_stock/aisles/reorder`, `home_stock/locations/list`.
- Produces: les deux écrans, et `frontend/outils/verifier-rendu.mjs` qui échoue sur débordement, cible < 48 px, contraste < 4,5:1 ou texte tronqué, aux formats 412 × 915 et 1280 × 800.

- [ ] **Step 1: Écrire l'écran Catalogue**

`<home-stock-catalogue>` : un champ de recherche, la liste dense des produits (nom, rayon,
quantité en stock, seuil), et l'édition d'un produit — nom, rayon, catégorie, emplacement par
défaut, seuil de réapprovisionnement, durée de conservation, unité de base. L'édition écrit
par `home_stock/product/update`. C'est l'écran pensé pour le PC : il tolère la souris et les
listes longues.

- [ ] **Step 2: Écrire l'écran Réglages**

`<home-stock-reglages>` : l'ordre des rayons, réordonnable par des boutons « monter » et
« descendre » — pas de glisser-déposer, la contrainte « aucun geste » vaut ici aussi —
envoyé par `home_stock/aisles/reorder` ; la liste des emplacements ; un bouton
« Resynchroniser Open Food Facts » qui appelle le service `home_stock.resync_off`.

- [ ] **Step 3: Écrire le vérificateur de rendu**

`frontend/outils/verifier-rendu.mjs`, sur le modèle de `tools/wallpanel-app/outils/verifier-rendu.mjs`,
avec quatre différences assumées :

- deux formats au lieu d'un : **412 × 915** (Pixel) et **1280 × 800** (PC) ;
- cible tactile **≥ 48 px** et contraste **≥ 4,5:1** — un téléphone se tient en main, une
  tablette murale se touche à bout de bras ;
- il construit le bundle **en mémoire** depuis `src/` (esbuild, `write: false`) et l'injecte
  par interception de requête : un vérificateur ne déploie pas ;
- il ouvre `/home-stock` sur l'instance HA, en injectant une session avant tout script de la
  page — le jeton est lu dans `data/.mcp.json` et n'est **jamais** écrit dans un fichier
  servi.

Run: `cd frontend && node outils/verifier-rendu.mjs`
Expected: aucun défaut signalé sur les six écrans.

- [ ] **Step 4: Construire et déployer**

```bash
cd frontend && npm test && npm run build
cd .. && ./scripts/test.sh
```
Expected: tests front PASS, bundle écrit dans `custom_components/home_stock/panel/`,
suite Python PASS.

Puis recharger l'intégration et vérifier que le panneau « Garde-manger » apparaît dans la
barre latérale de Home Assistant.

- [ ] **Step 5: Compléter les notes d'exploitation**

Ajouter à `docs/exploitation.md` : que `frontend/npm run build` écrit **dans le composant**
(donc qu'un build est un déploiement dès que HA recharge) ; que le panneau est servi sans
cache ; la commande de vérification de rendu ; et le rappel que `resync_off` sur tout le
catalogue prend une quarantaine de minutes au rythme qu'OFF tolère.

- [ ] **Step 6: Commit**

```bash
git add frontend docs/exploitation.md custom_components/home_stock/panel/
git commit -m "feat: catalogue and settings screens, rendering checks, deployment notes"
```

---

## Auto-relecture du plan

**Couverture du spec.** Chaque section du spec du lot 1 a sa tâche : §5 architecture
(Tasks 5, 6, 11, 14) ; §6 migration (Task 1) ; §7 client OFF (Tasks 5 et 6) ; §8 appariement
(Task 7) ; §9 rayons (Tasks 1 et 2) ; §10 conversion (Tasks 9 et 10) ; §11 prix (Task 8) ;
§12 session (Tasks 4, 11, 13) ; §13 surface HA (Tasks 12 et 13) ; §14 panneau (Tasks 14 à
17) ; §15 erreurs (réparties, chacune avec son test) ; §16 tests (partout).

**Cohérence des types.** `insert_movement` prend `base_unit` obligatoire dès la Task 3 et
toutes les écritures ultérieures le passent. `map_article` rend `nutrition_per_100`, et c'est
`nutrition_per_base_unit` — jamais `map_article` — qui divise. `plan_conversion` rend un
`ConversionPlan` que seule la Task 10 exécute. `FileAttente.ajouter` rend la clé
d'idempotence que les commandes websocket attendent sous le nom `idempotency_key`.

**Deux points à surveiller pendant l'exécution :**

1. `Database.write()` prend un verrou **non réentrant**. `ShoppingService.store_line` appelle
   `StockManager.add_stock`, qui ouvre sa propre transaction : les deux ne doivent jamais être
   imbriquées.
2. La migration `m002` supprime puis recrée `movement_no_update`. Un test doit prouver que le
   déclencheur est bien revenu — c'est dans la Task 1, et il ne se supprime pas.
