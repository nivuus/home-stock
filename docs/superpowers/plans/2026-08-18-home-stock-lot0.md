# home_stock — Lot 0 : plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Poser les fondations du composant `home_stock` — schéma SQLite, catalogue produits/articles, lots de stock, journal en ajout seul, services et entités HA, import du catalogue Grocy — de sorte que le stock réel de la maison soit manipulable depuis Home Assistant.

**Architecture:** Un composant HA unique. Une couche `domain/` sans aucune dépendance à `hass`, testable en pytest pur, qui porte les règles qui ont fait souffrir Grocy (unités, FIFO, sortie partielle, kcal figées). Une couche `storage/` en `sqlite3` synchrone, migrations versionnées. Une couche `application.py` qui compose les deux. La couche HA (entités, services, websocket) appelle l'application dans l'executor.

**Tech Stack:** Python 3.14 (image HA), sqlite3 en WAL, Home Assistant 2026.8.2, pytest + `pytest-homeassistant-custom-component==0.13.356`, Docker pour le harnais de test.

**Spec:** `docs/superpowers/specs/2026-08-18-home-stock-lot0-design.md` — à lire avant la tâche 1, et à rouvrir à chaque tâche.

## Global Constraints

- **Home Assistant 2026.8.2** exactement (image `ghcr.io/home-assistant/home-assistant:2026.8.2`, Python 3.14.6). Ne jamais utiliser le tag `stable` dans le harnais : il bouge.
- **`pytest-homeassistant-custom-component==0.13.356`** — c'est la seule version qui épingle `homeassistant==2026.8.2`.
- **Code, identifiants, noms de tables, commentaires : en anglais.** Textes affichés : en français, via `translations/fr.json`. Décision §14 du spec.
- **Unités de base fermées : `g`, `ml`, `piece`.** Aucune autre valeur n'est acceptée nulle part.
- **Les valeurs nutritionnelles sont stockées par unité de base** (kcal/g), jamais pour 100 g. L'affichage seul ramène à 100.
- **`movement` est en ajout seul** : jamais d'`UPDATE`, jamais de `DELETE`. Une correction est un nouveau mouvement de motif `inventory`.
- **`NULL` ≠ 0** pour `kcal` et `cost` : `NULL` signifie « inconnu », 0 signifie « mesuré à zéro ».
- **Aucune entité par produit.** Les entités sont des synthèses.
- **Un seul fichier de base** : `config/home_stock.db`, chemin non configurable.
- **TDD strict** : le test échoue d'abord, pour la bonne raison, avant toute implémentation.
- **Commit à chaque fin de tâche**, message en anglais, format Conventional Commits.
- **Le dépôt reste installable par HACS** : `custom_components/home_stock/` à la racine, `hacs.json` et `README.md` présents, `manifest.json` complet. Pendant le développement, le composant est **monté** dans HA (tâche 13) et **jamais installé par HACS** : HACS copie les fichiers, le montage les partage, et les deux ensemble font charger une copie pendant qu'on édite l'autre.

## File Structure

Dépôt : `/opt/nivuus/HomeAssistant/data/meal/` (à initialiser en git à la tâche 1).

| Fichier | Responsabilité |
|---|---|
| `custom_components/home_stock/const.py` | Domaine, motifs de mouvement, unités, valeurs par défaut |
| `custom_components/home_stock/domain/units.py` | Unités de base, conversions conditionnement ↔ base, formatage |
| `custom_components/home_stock/domain/stock.py` | Ordre de prélèvement des lots, allocation FIFO, poussière flottante, stock insuffisant |
| `custom_components/home_stock/domain/nutrition.py` | kcal et coût d'un mouvement, motifs comptés dans les totaux du jour |
| `custom_components/home_stock/storage/database.py` | Connexion sqlite3, WAL, écritures sérialisées, transactions |
| `custom_components/home_stock/storage/migrations/001_initial.py` | DDL de départ (§6.2 du spec) |
| `custom_components/home_stock/storage/migrations/__init__.py` | Découverte et application des migrations, table `schema_version` |
| `custom_components/home_stock/storage/repositories.py` | Lecture/écriture par agrégat, sans logique métier |
| `custom_components/home_stock/application.py` | `StockManager` : compose domain + storage, écrit les mouvements |
| `custom_components/home_stock/__init__.py` | Mise en place de l'entrée, plateformes, services, websocket |
| `custom_components/home_stock/config_flow.py` | Entrée unique + options (`expiration_alert_days`) |
| `custom_components/home_stock/coordinator.py` | Rafraîchissement des synthèses |
| `custom_components/home_stock/entity.py` | Classe de base des entités : appareil, identifiants, `entity_id` anglais |
| `custom_components/home_stock/sensor.py`, `binary_sensor.py`, `todo.py` | Entités de synthèse |
| `custom_components/home_stock/services.py`, `services.yaml` | Services HA, dont `query_stock` à réponse |
| `custom_components/home_stock/websocket_api.py` | Commandes de lecture pour la future SPA |
| `custom_components/home_stock/import_grocy.py` | Import du catalogue Grocy + rapport de contrôle |
| `custom_components/home_stock/translations/fr.json`, `en.json` | Textes affichés |
| `tests/` | Miroir de l'arborescence ci-dessus |
| `Dockerfile.test`, `scripts/test.sh`, `pytest.ini`, `tests/conftest.py` | Harnais |
| `hacs.json`, `README.md` | Rendent le dépôt installable par HACS |

`application.py` n'apparaît pas dans l'arborescence du spec (§5.2) : c'est la couche qui compose `domain/` et `storage/`, sans laquelle l'un des deux devrait connaître l'autre. Ajout assumé.

---

### Task 1: Dépôt, harnais de test, squelette du composant

**Files:**
- Create: `/opt/nivuus/HomeAssistant/data/meal/.gitignore`
- Create: `Dockerfile.test`, `scripts/test.sh`, `pytest.ini`, `tests/conftest.py`
- Create: `hacs.json`, `README.md`
- Create: `custom_components/home_stock/const.py`, `custom_components/home_stock/__init__.py`, `custom_components/home_stock/manifest.json`
- Test: `tests/test_harness.py`

**Interfaces:**
- Consumes: rien.
- Produits: `scripts/test.sh` (lance toute la suite dans Docker) ; `custom_components.home_stock.const.DOMAIN == "home_stock"`, `BASE_UNITS`, `REASONS`, `DEFAULT_EXPIRATION_ALERT_DAYS`.

- [ ] **Step 1: Initialiser le dépôt**

```bash
cd /opt/nivuus/HomeAssistant/data/meal
git init
git config user.email "maxime@allanic.me"
git config user.name "Maxime Allanic"
mkdir -p custom_components/home_stock/{domain,storage/migrations,translations} tests scripts
cat > .gitignore <<'EOF'
__pycache__/
*.pyc
.pytest_cache/
*.db
*.db-shm
*.db-wal
node_modules/
EOF
git add -A && git commit -m "chore: initialise home_stock repository"
```

- [ ] **Step 2: Écrire le harnais Docker**

`Dockerfile.test` :

```dockerfile
FROM ghcr.io/home-assistant/home-assistant:2026.8.2
RUN pip install --no-cache-dir --break-system-packages \
      pytest-homeassistant-custom-component==0.13.356 \
 || pip install --no-cache-dir pytest-homeassistant-custom-component==0.13.356
WORKDIR /src
```

`scripts/test.sh` :

```bash
#!/usr/bin/env bash
# Lance la suite de tests dans une image alignée sur HA 2026.8.2.
set -euo pipefail
cd "$(dirname "$0")/.."
docker build -q -f Dockerfile.test -t home-stock-test . > /dev/null
exec docker run --rm --entrypoint python -v "$PWD:/src" -w /src home-stock-test -m pytest "$@"
```

`pytest.ini` :

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
```

`tests/conftest.py` :

```python
"""Shared fixtures. The custom integration must be enabled for every test."""
import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Let Home Assistant load custom_components/home_stock during tests."""
    yield
```

```bash
chmod +x scripts/test.sh
```

- [ ] **Step 3: Écrire le test qui échoue**

`tests/test_harness.py` :

```python
"""The harness itself is worth one test: everything else depends on it."""
from custom_components.home_stock.const import (
    BASE_UNITS,
    DEFAULT_EXPIRATION_ALERT_DAYS,
    DOMAIN,
    REASONS,
)


def test_constants_are_exposed():
    assert DOMAIN == "home_stock"
    assert BASE_UNITS == ("g", "ml", "piece")
    assert "consumption" in REASONS
    assert DEFAULT_EXPIRATION_ALERT_DAYS == 3
```

- [ ] **Step 4: Lancer le test, vérifier qu'il échoue**

Run: `./scripts/test.sh tests/test_harness.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'custom_components.home_stock.const'`

Si `docker build` échoue sur `pip install`, c'est que l'image HA refuse l'installation hors venv : la seconde forme de la commande (sans `--break-system-packages`) prend le relais grâce au `||`. Si les deux échouent, remplacer la ligne par `RUN python -m venv /venv && /venv/bin/pip install …` et adapter `--entrypoint /venv/bin/python`.

- [ ] **Step 5: Écrire les constantes**

`custom_components/home_stock/const.py` :

```python
"""Constants shared across the integration."""
from typing import Final

DOMAIN: Final = "home_stock"

BASE_UNITS: Final = ("g", "ml", "piece")

# Movement reasons. See spec section 7.5 for the sign and accounting rules.
REASON_PURCHASE: Final = "purchase"
REASON_CONSUMPTION: Final = "consumption"
REASON_WASTE: Final = "waste"
REASON_EXPIRED: Final = "expired"
REASON_INVENTORY: Final = "inventory"
REASON_TRANSFER: Final = "transfer"
REASONS: Final = (
    REASON_PURCHASE,
    REASON_CONSUMPTION,
    REASON_WASTE,
    REASON_EXPIRED,
    REASON_INVENTORY,
    REASON_TRANSFER,
)

# Reasons that count towards the daily kcal and cost totals (spec 7.5).
COUNTED_REASONS: Final = frozenset({REASON_CONSUMPTION, REASON_WASTE, REASON_EXPIRED})

DATABASE_FILENAME: Final = "home_stock.db"
DEFAULT_EXPIRATION_ALERT_DAYS: Final = 3
CONF_EXPIRATION_ALERT_DAYS: Final = "expiration_alert_days"

# Below this many base units, a batch is empty: floating point dust (spec 7.2).
QUANTITY_EPSILON: Final = 0.001
```

`custom_components/home_stock/__init__.py` : fichier vide pour l'instant (la mise en place arrive à la tâche 8).

`custom_components/home_stock/manifest.json` :

```json
{
  "domain": "home_stock",
  "name": "Garde-manger",
  "codeowners": ["@<compte-github>"],
  "config_flow": true,
  "dependencies": ["http"],
  "documentation": "https://github.com/<compte-github>/home-stock",
  "issue_tracker": "https://github.com/<compte-github>/home-stock/issues",
  "iot_class": "local_push",
  "integration_type": "service",
  "requirements": [],
  "version": "0.1.0"
}
```

Remplacer `<compte-github>` par le vrai compte **avant de commiter** : HACS refuse une
intégration dont `documentation` ou `issue_tracker` ne répond pas, et `codeowners`
doit être un compte existant.

Créer aussi les `__init__.py` vides de `domain/` et `storage/` et `tests/__init__.py` absent (pytest n'en a pas besoin).

- [ ] **Step 6: Lancer le test, vérifier qu'il passe**

Run: `./scripts/test.sh tests/test_harness.py -v`
Expected: PASS

- [ ] **Step 7: Rendre le dépôt installable par HACS**

`hacs.json` à la racine :

```json
{
  "name": "Garde-manger",
  "homeassistant": "2026.8.2",
  "render_readme": true
}
```

`README.md` à la racine — HACS l'affiche comme description de l'intégration :

```markdown
# Garde-manger (`home_stock`)

Gestion des stocks de la maison dans Home Assistant : placards, frigo,
congélateur, alimentaire comme ménager. Chaque lot porte sa date limite et son
prix payé ; le journal des mouvements alimente la comptabilité kcal et euros par
jour.

## Installation

HACS → Intégrations → dépôt personnalisé → cette URL, catégorie « Integration ».
Puis Paramètres → Appareils et services → Ajouter une intégration → Garde-manger.

## État

Lot 0 : fondations (schéma, catalogue, lots, journal, services). Le scan de
codes-barres et l'interface arrivent au lot 1.
```

`hacs.json` n'est vérifié par personne à ce stade — mais il coûte deux minutes
maintenant et évite de restructurer le dépôt plus tard.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: add test harness pinned to HA 2026.8.2 and shared constants"
```

---

### Task 2: Unités de base et conditionnements

**Files:**
- Create: `custom_components/home_stock/domain/units.py`
- Test: `tests/domain/test_units.py`

**Interfaces:**
- Consumes: `const.BASE_UNITS`.
- Produces:
  - `class UnitError(ValueError)`
  - `validate_base_unit(unit: str) -> str`
  - `to_base_quantity(amount: float, packaging_base_quantity: float | None = None) -> float`
  - `format_quantity(quantity: float, base_unit: str) -> str` — sortie française (« 1,5 kg », « 200 g », « 3 pièces »)

- [ ] **Step 1: Écrire les tests qui échouent**

`tests/domain/test_units.py` :

```python
import pytest

from custom_components.home_stock.domain.units import (
    UnitError,
    format_quantity,
    to_base_quantity,
    validate_base_unit,
)


def test_validate_base_unit_accepts_the_three_units():
    assert validate_base_unit("g") == "g"
    assert validate_base_unit("ml") == "ml"
    assert validate_base_unit("piece") == "piece"


def test_validate_base_unit_rejects_everything_else():
    # "Paquet" as a stock unit is exactly what this model refuses.
    with pytest.raises(UnitError):
        validate_base_unit("Paquet")
    with pytest.raises(UnitError):
        validate_base_unit("kg")


def test_to_base_quantity_without_packaging_is_the_identity():
    assert to_base_quantity(200) == 200


def test_to_base_quantity_multiplies_by_the_packaging():
    # Two 500 g packs are 1000 g.
    assert to_base_quantity(2, 500) == 1000


def test_to_base_quantity_rejects_a_non_positive_packaging():
    with pytest.raises(UnitError):
        to_base_quantity(2, 0)


def test_to_base_quantity_rejects_a_negative_amount():
    with pytest.raises(UnitError):
        to_base_quantity(-1)


def test_format_quantity_uses_french_notation():
    assert format_quantity(1500, "g") == "1,5 kg"
    assert format_quantity(200, "g") == "200 g"
    assert format_quantity(1200, "ml") == "1,2 l"
    assert format_quantity(250, "ml") == "250 ml"
    assert format_quantity(1, "piece") == "1 pièce"
    assert format_quantity(3, "piece") == "3 pièces"
```

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `./scripts/test.sh tests/domain/test_units.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'custom_components.home_stock.domain.units'`

- [ ] **Step 3: Implémenter**

`custom_components/home_stock/domain/units.py` :

```python
"""Base units and packaging conversions.

A product has exactly one base unit, forever. Packagings ("Paquet = 500 g",
"cs = 13 ml") are a display layer: we read and enter in packagings, we store and
compute in base units. Grocy stored both and had to keep them in sync; it did not.
"""
from __future__ import annotations

from ..const import BASE_UNITS


class UnitError(ValueError):
    """Raised when a unit or a quantity cannot be used."""


def validate_base_unit(unit: str) -> str:
    """Return the unit if it is one of the three base units, raise otherwise."""
    if unit not in BASE_UNITS:
        raise UnitError(f"{unit!r} is not a base unit; expected one of {BASE_UNITS}")
    return unit


def to_base_quantity(amount: float, packaging_base_quantity: float | None = None) -> float:
    """Convert an amount, optionally expressed in packagings, into base units."""
    if amount < 0:
        raise UnitError(f"quantity must not be negative, got {amount}")
    if packaging_base_quantity is None:
        return float(amount)
    if packaging_base_quantity <= 0:
        raise UnitError(
            f"packaging quantity must be positive, got {packaging_base_quantity}"
        )
    return float(amount) * float(packaging_base_quantity)


def _french_number(value: float) -> str:
    """Render a number the French way: no trailing zeros, comma as separator."""
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")


def format_quantity(quantity: float, base_unit: str) -> str:
    """Render a quantity for display, in French."""
    validate_base_unit(base_unit)
    if base_unit == "piece":
        plural = "s" if quantity >= 2 else ""
        return f"{_french_number(quantity)} pièce{plural}"
    if base_unit == "g":
        if quantity >= 1000:
            return f"{_french_number(quantity / 1000)} kg"
        return f"{_french_number(quantity)} g"
    if quantity >= 1000:
        return f"{_french_number(quantity / 1000)} l"
    return f"{_french_number(quantity)} ml"
```

- [ ] **Step 4: Lancer, vérifier le succès**

Run: `./scripts/test.sh tests/domain/test_units.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add custom_components/home_stock/domain/units.py tests/domain/test_units.py
git commit -m "feat(domain): add base units and packaging conversions"
```

---

### Task 3: Base SQLite, migrations versionnées

**Files:**
- Create: `custom_components/home_stock/storage/database.py`
- Create: `custom_components/home_stock/storage/migrations/__init__.py`
- Create: `custom_components/home_stock/storage/migrations/m001_initial.py`
- Test: `tests/storage/test_database.py`, `tests/storage/test_migrations.py`

**Interfaces:**
- Consumes: rien du domaine.
- Produces:
  - `class Database` avec `connect()`, `close()`, `write()` (context manager transactionnel), `read()` (connexion en lecture), attribut `path`
  - `apply_migrations(conn: sqlite3.Connection) -> int` — retourne la version finale
  - `CURRENT_VERSION: int`

- [ ] **Step 1: Écrire les tests qui échouent**

`tests/storage/test_database.py` :

```python
import sqlite3

import pytest

from custom_components.home_stock.storage.database import Database


@pytest.fixture
def db(tmp_path):
    database = Database(str(tmp_path / "home_stock.db"))
    database.connect()
    yield database
    database.close()


def test_connect_enables_wal_and_foreign_keys(db):
    conn = db.read()
    assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_write_commits_on_success(db):
    with db.write() as conn:
        conn.execute("CREATE TABLE t (v INTEGER)")
        conn.execute("INSERT INTO t VALUES (1)")
    assert db.read().execute("SELECT v FROM t").fetchone()[0] == 1


def test_write_rolls_back_on_error(db):
    with db.write() as conn:
        conn.execute("CREATE TABLE t (v INTEGER)")
    with pytest.raises(sqlite3.IntegrityError):
        with db.write() as conn:
            conn.execute("INSERT INTO t VALUES (1)")
            conn.execute("INSERT INTO t VALUES (NULL), (2)")
            conn.execute("CREATE TABLE t (v INTEGER)")  # raises
    # Nothing from the failed transaction survived.
    assert db.read().execute("SELECT COUNT(*) FROM t").fetchone()[0] == 0


def test_rows_are_dict_like(db):
    with db.write() as conn:
        conn.execute("CREATE TABLE t (v INTEGER)")
        conn.execute("INSERT INTO t VALUES (7)")
    row = db.read().execute("SELECT v FROM t").fetchone()
    assert row["v"] == 7
```

`tests/storage/test_migrations.py` :

```python
from custom_components.home_stock.storage.database import Database
from custom_components.home_stock.storage.migrations import (
    CURRENT_VERSION,
    apply_migrations,
)


def _fresh(tmp_path):
    database = Database(str(tmp_path / "home_stock.db"))
    database.connect()
    return database


def test_apply_migrations_on_an_empty_database(tmp_path):
    db = _fresh(tmp_path)
    with db.write() as conn:
        assert apply_migrations(conn) == CURRENT_VERSION
    tables = {
        row["name"]
        for row in db.read().execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {
        "location",
        "aisle",
        "category",
        "product",
        "article",
        "barcode",
        "packaging",
        "price",
        "batch",
        "movement",
        "schema_version",
    } <= tables
    db.close()


def test_apply_migrations_is_idempotent(tmp_path):
    db = _fresh(tmp_path)
    with db.write() as conn:
        apply_migrations(conn)
    with db.write() as conn:
        assert apply_migrations(conn) == CURRENT_VERSION
    version = db.read().execute("SELECT version FROM schema_version").fetchall()
    assert len(version) == 1
    db.close()


def test_movement_rejects_a_duplicate_idempotency_key(tmp_path):
    import sqlite3

    import pytest

    db = _fresh(tmp_path)
    with db.write() as conn:
        apply_migrations(conn)
        conn.execute("INSERT INTO location (id, name, kind) VALUES (1, 'Placard', 'pantry')")
        conn.execute(
            "INSERT INTO product (id, name, base_unit) VALUES (1, 'Moutarde', 'g')"
        )
        conn.execute(
            "INSERT INTO article (id, product_id, is_generic) VALUES (1, 1, 1)"
        )
    with db.write() as conn:
        conn.execute(
            "INSERT INTO movement (occurred_at, product_id, article_id, quantity,"
            " reason, idempotency_key) VALUES ('2026-08-18T10:00:00', 1, 1, 5,"
            " 'purchase', 'abc')"
        )
    with pytest.raises(sqlite3.IntegrityError):
        with db.write() as conn:
            conn.execute(
                "INSERT INTO movement (occurred_at, product_id, article_id, quantity,"
                " reason, idempotency_key) VALUES ('2026-08-18T11:00:00', 1, 1, 5,"
                " 'purchase', 'abc')"
            )
    db.close()


def test_product_base_unit_is_constrained(tmp_path):
    import sqlite3

    import pytest

    db = _fresh(tmp_path)
    with db.write() as conn:
        apply_migrations(conn)
    with pytest.raises(sqlite3.IntegrityError):
        with db.write() as conn:
            conn.execute("INSERT INTO product (name, base_unit) VALUES ('X', 'Paquet')")
    db.close()
```

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `./scripts/test.sh tests/storage -v`
Expected: FAIL — `ModuleNotFoundError: ... storage.database`

- [ ] **Step 3: Implémenter la connexion**

`custom_components/home_stock/storage/database.py` :

```python
"""SQLite access: one writer, serialised, WAL enabled.

Home Assistant calls into this module from the executor. All writes go through a
single lock so two services can never interleave a transaction.
"""
from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager


class Database:
    """A single SQLite file, with serialised writes."""

    def __init__(self, path: str) -> None:
        self.path = path
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.Lock()

    def connect(self) -> None:
        """Open the file and apply the pragmas we depend on."""
        conn = sqlite3.connect(self.path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        self._conn = conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def read(self) -> sqlite3.Connection:
        """Return the connection for read-only queries."""
        if self._conn is None:
            raise RuntimeError("database is not connected")
        return self._conn

    @contextmanager
    def write(self) -> Iterator[sqlite3.Connection]:
        """Run a transaction. Commits on success, rolls back on any exception."""
        if self._conn is None:
            raise RuntimeError("database is not connected")
        with self._lock:
            try:
                yield self._conn
            except Exception:
                self._conn.rollback()
                raise
            else:
                self._conn.commit()
```

- [ ] **Step 4: Implémenter le DDL et les migrations**

`custom_components/home_stock/storage/migrations/m001_initial.py` — copier **mot pour mot** le schéma de la section 6.2 du spec, y compris les commentaires :

```python
"""Initial schema. Mirrors section 6.2 of the design document."""

VERSION = 1

SQL = """
CREATE TABLE location (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  kind TEXT NOT NULL,
  position INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE aisle (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  position INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE category (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE
);

CREATE TABLE product (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  base_unit TEXT NOT NULL CHECK (base_unit IN ('g','ml','piece')),
  category_id INTEGER REFERENCES category(id),
  aisle_id INTEGER REFERENCES aisle(id),
  edible INTEGER NOT NULL DEFAULT 1,
  default_location_id INTEGER REFERENCES location(id),
  min_quantity REAL,
  days_after_opening INTEGER,
  reference_kcal REAL,
  active INTEGER NOT NULL DEFAULT 1,
  external_ref TEXT
);

-- All nutrition values are PER BASE UNIT (kcal per g, g of protein per g...).
-- Display divides by 100. One convention everywhere: the "per 100 g or per stock
-- unit?" ambiguity is what produced the 1000x wrong spinach values in Grocy.
CREATE TABLE article (
  id INTEGER PRIMARY KEY,
  product_id INTEGER NOT NULL REFERENCES product(id),
  brand TEXT,
  label TEXT,
  net_quantity REAL,
  image TEXT,
  kcal_per_base_unit REAL,
  proteins REAL, carbohydrates REAL, sugars REAL, added_sugars REAL,
  fat REAL, saturated_fat REAL, fiber REAL, salt REAL,
  nutriscore TEXT, nova INTEGER, ecoscore TEXT,
  allergens TEXT, traces TEXT, additives TEXT, off_labels TEXT,
  off_source TEXT,
  off_synced_at TEXT,
  off_raw TEXT,
  manual_fields TEXT,
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
  name TEXT NOT NULL,
  base_quantity REAL NOT NULL,
  is_purchase_default INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE price (
  id INTEGER PRIMARY KEY,
  article_id INTEGER NOT NULL REFERENCES article(id),
  observed_on TEXT NOT NULL,
  price_per_base_unit REAL NOT NULL,
  store TEXT,
  source TEXT NOT NULL
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
  session_id INTEGER,
  closed_at TEXT
);

-- APPEND ONLY. Never UPDATE, never DELETE. A correction is a new movement.
CREATE TABLE movement (
  id INTEGER PRIMARY KEY,
  occurred_at TEXT NOT NULL,
  product_id INTEGER NOT NULL REFERENCES product(id),
  article_id INTEGER NOT NULL REFERENCES article(id),
  batch_id INTEGER REFERENCES batch(id),
  quantity REAL NOT NULL,
  reason TEXT NOT NULL,
  kcal REAL, cost REAL,
  ref_type TEXT, ref_id INTEGER,
  idempotency_key TEXT UNIQUE
);

CREATE INDEX idx_batch_pick ON batch(article_id, closed_at, best_before, entered_at);
CREATE INDEX idx_movement_day ON movement(occurred_at);
"""
```

`custom_components/home_stock/storage/migrations/__init__.py` :

```python
"""Versioned migrations. Each module exposes VERSION and SQL."""
from __future__ import annotations

import sqlite3

from . import m001_initial

MIGRATIONS = (m001_initial,)
CURRENT_VERSION = MIGRATIONS[-1].VERSION


def _current_version(conn: sqlite3.Connection) -> int:
    conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
    row = conn.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()
    return row["v"] or 0


def apply_migrations(conn: sqlite3.Connection) -> int:
    """Bring the database up to CURRENT_VERSION. Returns the version reached."""
    version = _current_version(conn)
    for migration in MIGRATIONS:
        if migration.VERSION > version:
            conn.executescript(migration.SQL)
            conn.execute("DELETE FROM schema_version")
            conn.execute(
                "INSERT INTO schema_version (version) VALUES (?)", (migration.VERSION,)
            )
            version = migration.VERSION
    return version
```

Attention : `executescript` valide implicitement la transaction en cours. C'est acceptable ici parce que la migration est la seule écriture de son transaction ; ne pas mélanger `apply_migrations` avec d'autres écritures dans le même `with db.write()`.

- [ ] **Step 5: Lancer, vérifier le succès**

Run: `./scripts/test.sh tests/storage -v`
Expected: PASS (8 tests)

- [ ] **Step 6: Commit**

```bash
git add custom_components/home_stock/storage tests/storage
git commit -m "feat(storage): add SQLite access layer and versioned migrations"
```

---

### Task 4: Dépôts — lecture et écriture par agrégat

**Files:**
- Create: `custom_components/home_stock/storage/repositories.py`
- Test: `tests/storage/test_repositories.py`

**Interfaces:**
- Consumes: `Database.write()`, `Database.read()`, `apply_migrations`.
- Produces (toutes prennent une `sqlite3.Connection` en premier argument) :
  - `insert_location(conn, *, name, kind, position=0) -> int`, `list_locations(conn) -> list[dict]`
  - `insert_category(conn, name) -> int`, `insert_aisle(conn, *, name, position=0) -> int`
  - `insert_product(conn, *, name, base_unit, **fields) -> int`, `get_product(conn, product_id) -> dict | None`, `find_product_by_name(conn, name) -> dict | None`, `list_products(conn, active_only=True) -> list[dict]`
  - `insert_article(conn, *, product_id, **fields) -> int`, `get_article(conn, article_id) -> dict | None`, `find_article_by_barcode(conn, code) -> dict | None`, `link_barcode(conn, code, article_id) -> None`
  - `insert_packaging(conn, *, scope, target_id, name, base_quantity, is_purchase_default=False) -> int`
  - `insert_price(conn, *, article_id, observed_on, price_per_base_unit, source, store=None) -> int`, `latest_price(conn, article_id) -> float | None`
  - `insert_batch(conn, *, article_id, location_id, quantity, entered_at, best_before=None, price_per_base_unit=None) -> int`
  - `list_batches_for_product(conn, product_id) -> list[dict]`, `set_batch_remaining(conn, batch_id, remaining, closed_at=None) -> None`, `set_batch_opened(conn, batch_id, opened_at, best_before) -> None`, `set_batch_location(conn, batch_id, location_id) -> None`
  - `insert_movement(conn, *, occurred_at, product_id, article_id, quantity, reason, batch_id=None, kcal=None, cost=None, ref_type=None, ref_id=None, idempotency_key=None) -> int`
  - `movement_exists(conn, idempotency_key) -> bool`
  - `stock_rows(conn) -> list[dict]` — un enregistrement par lot ouvert, avec produit, article et emplacement joints

- [ ] **Step 1: Écrire les tests qui échouent**

`tests/storage/test_repositories.py` :

```python
import pytest

from custom_components.home_stock.storage import repositories as repo
from custom_components.home_stock.storage.database import Database
from custom_components.home_stock.storage.migrations import apply_migrations


@pytest.fixture
def conn(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.connect()
    with db.write() as c:
        apply_migrations(c)
    with db.write() as c:
        yield c
    db.close()


def test_product_round_trip(conn):
    product_id = repo.insert_product(conn, name="Moutarde", base_unit="g")
    product = repo.get_product(conn, product_id)
    assert product["name"] == "Moutarde"
    assert product["base_unit"] == "g"
    assert product["active"] == 1


def test_find_product_by_name(conn):
    repo.insert_product(conn, name="Moutarde", base_unit="g")
    assert repo.find_product_by_name(conn, "Moutarde")["name"] == "Moutarde"
    assert repo.find_product_by_name(conn, "Ketchup") is None


def test_barcode_resolves_to_an_article(conn):
    product_id = repo.insert_product(conn, name="Moutarde", base_unit="g")
    small = repo.insert_article(conn, product_id=product_id, label="Savora 265 g",
                                net_quantity=265, kcal_per_base_unit=1.2)
    large = repo.insert_article(conn, product_id=product_id, label="Savora 385 g",
                                net_quantity=385, kcal_per_base_unit=1.2)
    repo.link_barcode(conn, "3011360002105", small)
    repo.link_barcode(conn, "3011360002204", large)
    found = repo.find_article_by_barcode(conn, "3011360002204")
    assert found["id"] == large
    assert found["net_quantity"] == 385
    assert repo.find_article_by_barcode(conn, "0000000000000") is None


def test_latest_price_is_the_most_recent(conn):
    product_id = repo.insert_product(conn, name="Moutarde", base_unit="g")
    article_id = repo.insert_article(conn, product_id=product_id)
    repo.insert_price(conn, article_id=article_id, observed_on="2026-01-01",
                      price_per_base_unit=0.004, source="manual")
    repo.insert_price(conn, article_id=article_id, observed_on="2026-08-01",
                      price_per_base_unit=0.005, source="receipt")
    assert repo.latest_price(conn, article_id) == 0.005


def test_latest_price_is_none_without_history(conn):
    product_id = repo.insert_product(conn, name="Sel", base_unit="g")
    article_id = repo.insert_article(conn, product_id=product_id)
    assert repo.latest_price(conn, article_id) is None


def test_list_batches_excludes_closed_ones(conn):
    location_id = repo.insert_location(conn, name="Placard", kind="pantry")
    product_id = repo.insert_product(conn, name="Pâtes", base_unit="g")
    article_id = repo.insert_article(conn, product_id=product_id)
    open_batch = repo.insert_batch(conn, article_id=article_id, location_id=location_id,
                                   quantity=500, entered_at="2026-08-01T10:00:00")
    closed = repo.insert_batch(conn, article_id=article_id, location_id=location_id,
                               quantity=500, entered_at="2026-07-01T10:00:00")
    repo.set_batch_remaining(conn, closed, 0, closed_at="2026-08-10T10:00:00")
    batches = repo.list_batches_for_product(conn, product_id)
    assert [b["id"] for b in batches] == [open_batch]


def test_movement_idempotency(conn):
    product_id = repo.insert_product(conn, name="Pâtes", base_unit="g")
    article_id = repo.insert_article(conn, product_id=product_id)
    repo.insert_movement(conn, occurred_at="2026-08-18T10:00:00", product_id=product_id,
                         article_id=article_id, quantity=-200, reason="consumption",
                         kcal=700.0, cost=0.6, idempotency_key="k1")
    assert repo.movement_exists(conn, "k1") is True
    assert repo.movement_exists(conn, "k2") is False


def test_stock_rows_join_names(conn):
    location_id = repo.insert_location(conn, name="Frigo", kind="fridge")
    product_id = repo.insert_product(conn, name="Lait", base_unit="ml")
    article_id = repo.insert_article(conn, product_id=product_id, label="Lactel 1 l")
    repo.insert_batch(conn, article_id=article_id, location_id=location_id,
                      quantity=1000, entered_at="2026-08-01T10:00:00",
                      best_before="2026-08-25", price_per_base_unit=0.0012)
    row = repo.stock_rows(conn)[0]
    assert row["product_name"] == "Lait"
    assert row["location_name"] == "Frigo"
    assert row["base_unit"] == "ml"
    assert row["remaining"] == 1000
```

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `./scripts/test.sh tests/storage/test_repositories.py -v`
Expected: FAIL — `ModuleNotFoundError: ... storage.repositories`

- [ ] **Step 3: Implémenter**

`custom_components/home_stock/storage/repositories.py` :

```python
"""Reads and writes, one function per operation. No business logic lives here.

Every function takes an open connection: the caller owns the transaction, so a
service can write a batch and its movement atomically.
"""
from __future__ import annotations

import sqlite3
from typing import Any

PRODUCT_FIELDS = (
    "category_id", "aisle_id", "edible", "default_location_id", "min_quantity",
    "days_after_opening", "reference_kcal", "active", "external_ref",
)
ARTICLE_FIELDS = (
    "brand", "label", "net_quantity", "image", "kcal_per_base_unit", "proteins",
    "carbohydrates", "sugars", "added_sugars", "fat", "saturated_fat", "fiber",
    "salt", "nutriscore", "nova", "ecoscore", "allergens", "traces", "additives",
    "off_labels", "off_source", "off_synced_at", "off_raw", "manual_fields",
    "is_generic", "external_ref",
)


def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def _rows(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
    return [dict(row) for row in cursor.fetchall()]


def _insert(conn: sqlite3.Connection, table: str, values: dict[str, Any]) -> int:
    columns = ", ".join(values)
    marks = ", ".join("?" for _ in values)
    cursor = conn.execute(
        f"INSERT INTO {table} ({columns}) VALUES ({marks})", tuple(values.values())
    )
    return int(cursor.lastrowid)


# --- locations, aisles, categories -----------------------------------------

def insert_location(conn, *, name: str, kind: str, position: int = 0) -> int:
    return _insert(conn, "location", {"name": name, "kind": kind, "position": position})


def list_locations(conn) -> list[dict[str, Any]]:
    return _rows(conn.execute("SELECT * FROM location ORDER BY position, name"))


def insert_category(conn, name: str) -> int:
    return _insert(conn, "category", {"name": name})


def insert_aisle(conn, *, name: str, position: int = 0) -> int:
    return _insert(conn, "aisle", {"name": name, "position": position})


# --- products ---------------------------------------------------------------

def insert_product(conn, *, name: str, base_unit: str, **fields: Any) -> int:
    values: dict[str, Any] = {"name": name, "base_unit": base_unit}
    values.update({k: v for k, v in fields.items() if k in PRODUCT_FIELDS})
    return _insert(conn, "product", values)


def get_product(conn, product_id: int) -> dict[str, Any] | None:
    return _row(conn.execute("SELECT * FROM product WHERE id = ?", (product_id,)).fetchone())


def find_product_by_name(conn, name: str) -> dict[str, Any] | None:
    return _row(conn.execute("SELECT * FROM product WHERE name = ?", (name,)).fetchone())


def list_products(conn, active_only: bool = True) -> list[dict[str, Any]]:
    sql = "SELECT * FROM product"
    if active_only:
        sql += " WHERE active = 1"
    return _rows(conn.execute(sql + " ORDER BY name"))


# --- articles and barcodes --------------------------------------------------

def insert_article(conn, *, product_id: int, **fields: Any) -> int:
    values: dict[str, Any] = {"product_id": product_id}
    values.update({k: v for k, v in fields.items() if k in ARTICLE_FIELDS})
    return _insert(conn, "article", values)


def get_article(conn, article_id: int) -> dict[str, Any] | None:
    return _row(conn.execute("SELECT * FROM article WHERE id = ?", (article_id,)).fetchone())


def find_article_by_barcode(conn, code: str) -> dict[str, Any] | None:
    return _row(
        conn.execute(
            "SELECT a.* FROM article a JOIN barcode b ON b.article_id = a.id"
            " WHERE b.code = ?",
            (code,),
        ).fetchone()
    )


def link_barcode(conn, code: str, article_id: int) -> None:
    conn.execute("INSERT INTO barcode (code, article_id) VALUES (?, ?)", (code, article_id))


# --- packagings and prices --------------------------------------------------

def insert_packaging(conn, *, scope: str, target_id: int, name: str,
                     base_quantity: float, is_purchase_default: bool = False) -> int:
    return _insert(conn, "packaging", {
        "scope": scope, "target_id": target_id, "name": name,
        "base_quantity": base_quantity,
        "is_purchase_default": 1 if is_purchase_default else 0,
    })


def insert_price(conn, *, article_id: int, observed_on: str,
                 price_per_base_unit: float, source: str, store: str | None = None) -> int:
    return _insert(conn, "price", {
        "article_id": article_id, "observed_on": observed_on,
        "price_per_base_unit": price_per_base_unit, "source": source, "store": store,
    })


def latest_price(conn, article_id: int) -> float | None:
    row = conn.execute(
        "SELECT price_per_base_unit FROM price WHERE article_id = ?"
        " ORDER BY observed_on DESC, id DESC LIMIT 1",
        (article_id,),
    ).fetchone()
    return None if row is None else float(row["price_per_base_unit"])


# --- batches ----------------------------------------------------------------

def insert_batch(conn, *, article_id: int, location_id: int, quantity: float,
                 entered_at: str, best_before: str | None = None,
                 price_per_base_unit: float | None = None) -> int:
    return _insert(conn, "batch", {
        "article_id": article_id, "location_id": location_id,
        "remaining": quantity, "initial": quantity, "entered_at": entered_at,
        "best_before": best_before, "price_per_base_unit": price_per_base_unit,
    })


def list_batches_for_product(conn, product_id: int) -> list[dict[str, Any]]:
    """Open batches only, newest information joined from the article."""
    return _rows(conn.execute(
        "SELECT b.*, a.kcal_per_base_unit, a.product_id FROM batch b"
        " JOIN article a ON a.id = b.article_id"
        " WHERE a.product_id = ? AND b.closed_at IS NULL",
        (product_id,),
    ))


def set_batch_remaining(conn, batch_id: int, remaining: float,
                        closed_at: str | None = None) -> None:
    conn.execute(
        "UPDATE batch SET remaining = ?, closed_at = ? WHERE id = ?",
        (remaining, closed_at, batch_id),
    )


def set_batch_opened(conn, batch_id: int, opened_at: str, best_before: str | None) -> None:
    conn.execute(
        "UPDATE batch SET opened_at = ?, best_before = ? WHERE id = ?",
        (opened_at, best_before, batch_id),
    )


def set_batch_location(conn, batch_id: int, location_id: int) -> None:
    conn.execute("UPDATE batch SET location_id = ? WHERE id = ?", (location_id, batch_id))


# --- movements --------------------------------------------------------------

def insert_movement(conn, *, occurred_at: str, product_id: int, article_id: int,
                    quantity: float, reason: str, batch_id: int | None = None,
                    kcal: float | None = None, cost: float | None = None,
                    ref_type: str | None = None, ref_id: int | None = None,
                    idempotency_key: str | None = None) -> int:
    return _insert(conn, "movement", {
        "occurred_at": occurred_at, "product_id": product_id, "article_id": article_id,
        "batch_id": batch_id, "quantity": quantity, "reason": reason, "kcal": kcal,
        "cost": cost, "ref_type": ref_type, "ref_id": ref_id,
        "idempotency_key": idempotency_key,
    })


def movement_exists(conn, idempotency_key: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM movement WHERE idempotency_key = ? LIMIT 1", (idempotency_key,)
    ).fetchone()
    return row is not None


def list_movements(conn, since: str | None = None) -> list[dict[str, Any]]:
    sql = "SELECT * FROM movement"
    params: tuple[Any, ...] = ()
    if since is not None:
        sql += " WHERE occurred_at >= ?"
        params = (since,)
    return _rows(conn.execute(sql + " ORDER BY occurred_at, id", params))


# --- read models ------------------------------------------------------------

def stock_rows(conn) -> list[dict[str, Any]]:
    """One row per open batch, with the names needed for display."""
    return _rows(conn.execute(
        "SELECT b.id, b.remaining, b.best_before, b.entered_at, b.opened_at,"
        "       b.price_per_base_unit, p.id AS product_id, p.name AS product_name,"
        "       p.base_unit, p.min_quantity, a.id AS article_id, a.label AS article_label,"
        "       a.kcal_per_base_unit, l.id AS location_id, l.name AS location_name"
        " FROM batch b"
        " JOIN article a ON a.id = b.article_id"
        " JOIN product p ON p.id = a.product_id"
        " JOIN location l ON l.id = b.location_id"
        " WHERE b.closed_at IS NULL"
        " ORDER BY p.name, b.best_before"
    ))
```

- [ ] **Step 4: Lancer, vérifier le succès**

Run: `./scripts/test.sh tests/storage/test_repositories.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add custom_components/home_stock/storage/repositories.py tests/storage/test_repositories.py
git commit -m "feat(storage): add repositories for products, articles, batches and movements"
```

---

### Task 5: Prélèvement FIFO et sortie partielle

C'est la tâche centrale du lot : la règle §7.1 du spec, la poussière flottante §7.2 et le refus de sortie excédentaire §7.3.

**Files:**
- Create: `custom_components/home_stock/domain/stock.py`
- Test: `tests/domain/test_stock.py`

**Interfaces:**
- Consumes: `const.QUANTITY_EPSILON`.
- Produces:
  - `@dataclass(frozen=True) class BatchView` — `id: int`, `remaining: float`, `best_before: date | None`, `entered_at: datetime`, `opened_at: datetime | None`, `price_per_base_unit: float | None`, `kcal_per_base_unit: float | None`
  - `@dataclass(frozen=True) class Allocation` — `batch_id: int`, `quantity: float` (positive), `price_per_base_unit: float | None`, `kcal_per_base_unit: float | None`, `remaining_after: float`, `closes_batch: bool`
  - `class InsufficientStock(Exception)` — attributs `requested`, `available`
  - `sort_batches(batches: Sequence[BatchView]) -> list[BatchView]`
  - `allocate(batches: Sequence[BatchView], quantity: float) -> list[Allocation]`
  - `is_empty(remaining: float) -> bool`

- [ ] **Step 1: Écrire les tests qui échouent**

`tests/domain/test_stock.py` :

```python
from datetime import date, datetime

import pytest

from custom_components.home_stock.domain.stock import (
    Allocation,
    BatchView,
    InsufficientStock,
    allocate,
    is_empty,
    sort_batches,
)


def batch(id_, remaining, best_before=None, entered="2026-08-01", opened=None,
          price=None, kcal=None):
    return BatchView(
        id=id_,
        remaining=remaining,
        best_before=date.fromisoformat(best_before) if best_before else None,
        entered_at=datetime.fromisoformat(f"{entered}T10:00:00"),
        opened_at=datetime.fromisoformat(f"{opened}T10:00:00") if opened else None,
        price_per_base_unit=price,
        kcal_per_base_unit=kcal,
    )


def test_an_opened_batch_comes_first_even_with_a_later_date():
    # Finishing what is already open beats the closest expiry: that is how a
    # kitchen works, and it avoids opening a second pack for nothing.
    closed_soon = batch(1, 500, best_before="2026-08-20")
    opened_later = batch(2, 300, best_before="2026-09-30", opened="2026-08-10")
    assert [b.id for b in sort_batches([closed_soon, opened_later])] == [2, 1]


def test_batches_without_a_date_come_last():
    dated = batch(1, 500, best_before="2026-12-01")
    undated = batch(2, 500)
    assert [b.id for b in sort_batches([undated, dated])] == [1, 2]


def test_equal_dates_fall_back_to_entry_order():
    first = batch(1, 500, best_before="2026-09-01", entered="2026-07-01")
    second = batch(2, 500, best_before="2026-09-01", entered="2026-08-01")
    assert [b.id for b in sort_batches([second, first])] == [1, 2]


def test_partial_consumption_of_a_single_batch():
    # 200 g taken from a 500 g pack: 300 g left, the batch stays open.
    allocations = allocate([batch(1, 500, price=0.004, kcal=3.5)], 200)
    assert allocations == [
        Allocation(batch_id=1, quantity=200, price_per_base_unit=0.004,
                   kcal_per_base_unit=3.5, remaining_after=300, closes_batch=False)
    ]


def test_consumption_spans_several_batches():
    allocations = allocate(
        [batch(1, 300, best_before="2026-08-20", price=0.004),
         batch(2, 500, best_before="2026-09-20", price=0.005)],
        700,
    )
    assert [(a.batch_id, a.quantity, a.closes_batch) for a in allocations] == [
        (1, 300, True),
        (2, 400, False),
    ]
    # Each fraction keeps the price actually paid for it.
    assert allocations[0].price_per_base_unit == 0.004
    assert allocations[1].price_per_base_unit == 0.005


def test_a_batch_emptied_below_the_epsilon_is_closed():
    allocations = allocate([batch(1, 500.0000001)], 500)
    assert allocations[0].closes_batch is True
    assert allocations[0].remaining_after == 0


def test_consuming_more_than_available_is_refused():
    with pytest.raises(InsufficientStock) as error:
        allocate([batch(1, 300), batch(2, 100)], 500)
    assert error.value.requested == 500
    assert error.value.available == 400


def test_consuming_from_an_empty_stock_is_refused():
    with pytest.raises(InsufficientStock):
        allocate([], 1)


def test_allocate_refuses_a_non_positive_quantity():
    with pytest.raises(ValueError):
        allocate([batch(1, 100)], 0)


def test_is_empty_uses_the_epsilon():
    assert is_empty(0.0005) is True
    assert is_empty(0.01) is False
```

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `./scripts/test.sh tests/domain/test_stock.py -v`
Expected: FAIL — `ModuleNotFoundError: ... domain.stock`

- [ ] **Step 3: Implémenter**

`custom_components/home_stock/domain/stock.py` :

```python
"""Which batch is taken, and how much of it.

Pure functions over value objects: no database, no Home Assistant. The rules here
are the ones Grocy got wrong, so they are tested on their own.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime

from ..const import QUANTITY_EPSILON


@dataclass(frozen=True)
class BatchView:
    """A batch, as the allocation rules need to see it."""

    id: int
    remaining: float
    best_before: date | None
    entered_at: datetime
    opened_at: datetime | None
    price_per_base_unit: float | None
    kcal_per_base_unit: float | None


@dataclass(frozen=True)
class Allocation:
    """How much is taken from one batch, and what that fraction is worth."""

    batch_id: int
    quantity: float
    price_per_base_unit: float | None
    kcal_per_base_unit: float | None
    remaining_after: float
    closes_batch: bool


class InsufficientStock(Exception):
    """Raised instead of letting the stock go negative."""

    def __init__(self, requested: float, available: float) -> None:
        super().__init__(f"requested {requested}, only {available} available")
        self.requested = requested
        self.available = available


def is_empty(remaining: float) -> bool:
    """Below the epsilon a batch is empty: binary rounding leaves 1e-14 g behind."""
    return remaining < QUANTITY_EPSILON


def sort_batches(batches: Sequence[BatchView]) -> list[BatchView]:
    """Opened first, then closest expiry, then oldest entry (spec 7.1)."""
    return sorted(
        batches,
        key=lambda b: (
            b.opened_at is None,
            b.best_before is None,
            b.best_before or date.max,
            b.entered_at,
        ),
    )


def allocate(batches: Sequence[BatchView], quantity: float) -> list[Allocation]:
    """Spread a consumption over the batches, in order. Never partial, never negative."""
    if quantity <= 0:
        raise ValueError(f"quantity must be positive, got {quantity}")
    available = sum(b.remaining for b in batches)
    if quantity > available + QUANTITY_EPSILON:
        raise InsufficientStock(requested=quantity, available=available)

    allocations: list[Allocation] = []
    left = quantity
    for candidate in sort_batches(batches):
        if left <= 0:
            break
        taken = min(candidate.remaining, left)
        remaining_after = candidate.remaining - taken
        closes = is_empty(remaining_after)
        allocations.append(
            Allocation(
                batch_id=candidate.id,
                quantity=taken,
                price_per_base_unit=candidate.price_per_base_unit,
                kcal_per_base_unit=candidate.kcal_per_base_unit,
                remaining_after=0.0 if closes else remaining_after,
                closes_batch=closes,
            )
        )
        left -= taken
    return allocations
```

- [ ] **Step 4: Lancer, vérifier le succès**

Run: `./scripts/test.sh tests/domain/test_stock.py -v`
Expected: PASS (10 tests)

- [ ] **Step 5: Commit**

```bash
git add custom_components/home_stock/domain/stock.py tests/domain/test_stock.py
git commit -m "feat(domain): allocate consumption across batches, FIFO with partials"
```

---

### Task 6: kcal et coût d'un mouvement

**Files:**
- Create: `custom_components/home_stock/domain/nutrition.py`
- Test: `tests/domain/test_nutrition.py`

**Interfaces:**
- Consumes: `const.COUNTED_REASONS`.
- Produces:
  - `@dataclass(frozen=True) class MovementValues` — `kcal: float | None`, `cost: float | None`
  - `movement_values(quantity: float, kcal_per_base_unit: float | None, price_per_base_unit: float | None) -> MovementValues`
  - `counts_in_daily_totals(reason: str) -> bool`

- [ ] **Step 1: Écrire les tests qui échouent**

`tests/domain/test_nutrition.py` :

```python
import pytest

from custom_components.home_stock.domain.nutrition import (
    MovementValues,
    counts_in_daily_totals,
    movement_values,
)


def test_values_are_the_quantity_times_the_rates():
    # 200 g at 3.5 kcal/g and 0.004 €/g.
    values = movement_values(200, 3.5, 0.004)
    assert values.kcal == pytest.approx(700.0)
    assert values.cost == pytest.approx(0.8)


def test_a_negative_quantity_yields_positive_values():
    # A movement of -200 g still costs 0.8 €; the sign lives on the quantity.
    values = movement_values(-200, 3.5, 0.004)
    assert values.kcal == pytest.approx(700.0)
    assert values.cost == pytest.approx(0.8)


def test_unknown_rates_give_none_not_zero():
    # None means "unknown". Zero would mean "measured at zero" and would silently
    # understate the daily total.
    assert movement_values(200, None, None) == MovementValues(kcal=None, cost=None)
    assert movement_values(200, 3.5, None).cost is None
    assert movement_values(200, None, 0.004).kcal is None


def test_a_zero_rate_is_kept_as_zero():
    values = movement_values(200, 0.0, 0.0)
    assert values.kcal == 0.0
    assert values.cost == 0.0


def test_values_are_not_rounded():
    # Rounding happens at display time only; summing rounded values drifts.
    values = movement_values(3, 1 / 3, None)
    assert values.kcal == pytest.approx(1.0, abs=1e-12)


def test_which_reasons_count_in_the_daily_totals():
    assert counts_in_daily_totals("consumption") is True
    assert counts_in_daily_totals("waste") is True
    assert counts_in_daily_totals("expired") is True
    assert counts_in_daily_totals("purchase") is False
    assert counts_in_daily_totals("inventory") is False
    assert counts_in_daily_totals("transfer") is False
```

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `./scripts/test.sh tests/domain/test_nutrition.py -v`
Expected: FAIL — `ModuleNotFoundError: ... domain.nutrition`

- [ ] **Step 3: Implémenter**

`custom_components/home_stock/domain/nutrition.py` :

```python
"""What a movement is worth, in kilocalories and in euros.

Both are frozen into the movement row when it happens: changing an article's price
or its Open Food Facts record later must never rewrite the past.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..const import COUNTED_REASONS


@dataclass(frozen=True)
class MovementValues:
    """Values frozen on a movement. None means unknown, 0.0 means measured at zero."""

    kcal: float | None
    cost: float | None


def movement_values(
    quantity: float,
    kcal_per_base_unit: float | None,
    price_per_base_unit: float | None,
) -> MovementValues:
    """Compute the kcal and cost of a movement. Never rounds."""
    magnitude = abs(float(quantity))
    return MovementValues(
        kcal=None if kcal_per_base_unit is None else magnitude * kcal_per_base_unit,
        cost=None if price_per_base_unit is None else magnitude * price_per_base_unit,
    )


def counts_in_daily_totals(reason: str) -> bool:
    """Whether a movement counts towards the daily kcal and cost (spec 7.5)."""
    return reason in COUNTED_REASONS
```

- [ ] **Step 4: Lancer, vérifier le succès**

Run: `./scripts/test.sh tests/domain/test_nutrition.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add custom_components/home_stock/domain/nutrition.py tests/domain/test_nutrition.py
git commit -m "feat(domain): freeze kcal and cost on movements"
```

---

### Task 7: `StockManager` — la couche applicative

**Files:**
- Create: `custom_components/home_stock/application.py`
- Test: `tests/test_application.py`

**Interfaces:**
- Consumes: `Database`, `repositories`, `domain.stock`, `domain.nutrition`, `domain.units`.
- Produces `class StockManager(db: Database)` :
  - `add_stock(*, article_id, quantity, location_id, best_before=None, price_per_base_unit=None, packaging_base_quantity=None, occurred_at=None, idempotency_key=None) -> int` (id du lot)
  - `consume(*, product_id, quantity, reason="consumption", occurred_at=None, idempotency_key=None) -> list[int]` (ids des mouvements)
  - `open_batch(batch_id, *, occurred_at=None) -> None`
  - `transfer_batch(batch_id, location_id, *, occurred_at=None) -> int` (id du mouvement)
  - `adjust_inventory(*, article_id, location_id, counted_quantity, occurred_at=None) -> int | None`
  - `query_stock(*, name=None) -> list[dict]`
  - `summary(*, expiration_alert_days) -> dict`
  - `export_journal() -> list[dict]`

Un transfert écrit **un** mouvement de quantité nulle portant l'emplacement d'arrivée en référence (`ref_type="location"`). Deux lignes de somme nulle ne porteraient aucune information : la table `movement` n'a pas de colonne d'emplacement.

- [ ] **Step 1: Écrire les tests qui échouent**

`tests/test_application.py` :

```python
import pytest

from custom_components.home_stock.application import StockManager
from custom_components.home_stock.domain.stock import InsufficientStock
from custom_components.home_stock.storage import repositories as repo
from custom_components.home_stock.storage.database import Database
from custom_components.home_stock.storage.migrations import apply_migrations


@pytest.fixture
def manager(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.connect()
    with db.write() as conn:
        apply_migrations(conn)
    yield StockManager(db)
    db.close()


@pytest.fixture
def pasta(manager):
    """A 'Pâtes' product in grams, one article at 3.5 kcal/g, and a pantry."""
    with manager.db.write() as conn:
        location_id = repo.insert_location(conn, name="Placard", kind="pantry")
        product_id = repo.insert_product(conn, name="Pâtes", base_unit="g",
                                         min_quantity=200)
        article_id = repo.insert_article(conn, product_id=product_id,
                                         label="Panzani 500 g", net_quantity=500,
                                         kcal_per_base_unit=3.5)
    return {"location_id": location_id, "product_id": product_id, "article_id": article_id}


def test_add_stock_creates_a_batch_and_a_purchase_movement(manager, pasta):
    batch_id = manager.add_stock(
        article_id=pasta["article_id"], quantity=500, location_id=pasta["location_id"],
        best_before="2027-01-01", price_per_base_unit=0.004,
        occurred_at="2026-08-18T10:00:00",
    )
    with manager.db.write() as conn:
        batch = conn.execute("SELECT * FROM batch WHERE id = ?", (batch_id,)).fetchone()
        movements = repo.list_movements(conn)
    assert batch["remaining"] == 500
    assert batch["initial"] == 500
    assert batch["price_per_base_unit"] == 0.004
    assert len(movements) == 1
    assert movements[0]["reason"] == "purchase"
    assert movements[0]["quantity"] == 500
    assert movements[0]["cost"] == pytest.approx(2.0)


def test_add_stock_converts_a_packaging(manager, pasta):
    batch_id = manager.add_stock(
        article_id=pasta["article_id"], quantity=2, packaging_base_quantity=500,
        location_id=pasta["location_id"], occurred_at="2026-08-18T10:00:00",
    )
    with manager.db.write() as conn:
        batch = conn.execute("SELECT remaining FROM batch WHERE id = ?", (batch_id,)).fetchone()
    assert batch["remaining"] == 1000


def test_add_stock_records_the_price_in_the_history(manager, pasta):
    manager.add_stock(article_id=pasta["article_id"], quantity=500,
                      location_id=pasta["location_id"], price_per_base_unit=0.004,
                      occurred_at="2026-08-18T10:00:00")
    with manager.db.write() as conn:
        assert repo.latest_price(conn, pasta["article_id"]) == 0.004


def test_consume_takes_200_g_from_a_500_g_pack(manager, pasta):
    batch_id = manager.add_stock(article_id=pasta["article_id"], quantity=500,
                                 location_id=pasta["location_id"],
                                 price_per_base_unit=0.004,
                                 occurred_at="2026-08-18T10:00:00")
    movement_ids = manager.consume(product_id=pasta["product_id"], quantity=200,
                                   occurred_at="2026-08-18T19:00:00")
    with manager.db.write() as conn:
        batch = conn.execute("SELECT * FROM batch WHERE id = ?", (batch_id,)).fetchone()
        movement = conn.execute("SELECT * FROM movement WHERE id = ?",
                                (movement_ids[0],)).fetchone()
    assert batch["remaining"] == 300
    assert batch["closed_at"] is None
    assert movement["quantity"] == -200
    assert movement["kcal"] == pytest.approx(700.0)
    assert movement["cost"] == pytest.approx(0.8)


def test_consume_spanning_two_batches_writes_one_movement_each(manager, pasta):
    manager.add_stock(article_id=pasta["article_id"], quantity=300,
                      location_id=pasta["location_id"], best_before="2026-08-20",
                      price_per_base_unit=0.004, occurred_at="2026-08-01T10:00:00")
    manager.add_stock(article_id=pasta["article_id"], quantity=500,
                      location_id=pasta["location_id"], best_before="2026-09-20",
                      price_per_base_unit=0.005, occurred_at="2026-08-10T10:00:00")
    movement_ids = manager.consume(product_id=pasta["product_id"], quantity=700,
                                   occurred_at="2026-08-18T19:00:00")
    assert len(movement_ids) == 2
    with manager.db.write() as conn:
        rows = conn.execute(
            "SELECT quantity, cost FROM movement WHERE reason = 'consumption'"
            " ORDER BY id").fetchall()
        closed = conn.execute(
            "SELECT COUNT(*) AS n FROM batch WHERE closed_at IS NOT NULL").fetchone()
    assert [r["quantity"] for r in rows] == [-300, -400]
    assert rows[0]["cost"] == pytest.approx(1.2)   # 300 g at 0.004
    assert rows[1]["cost"] == pytest.approx(2.0)   # 400 g at 0.005
    assert closed["n"] == 1


def test_consume_refuses_to_go_negative(manager, pasta):
    manager.add_stock(article_id=pasta["article_id"], quantity=100,
                      location_id=pasta["location_id"], occurred_at="2026-08-18T10:00:00")
    with pytest.raises(InsufficientStock):
        manager.consume(product_id=pasta["product_id"], quantity=500,
                        occurred_at="2026-08-18T19:00:00")
    with manager.db.write() as conn:
        assert conn.execute("SELECT remaining FROM batch").fetchone()["remaining"] == 100


def test_an_idempotency_key_prevents_a_replayed_consumption(manager, pasta):
    manager.add_stock(article_id=pasta["article_id"], quantity=500,
                      location_id=pasta["location_id"], occurred_at="2026-08-18T10:00:00")
    first = manager.consume(product_id=pasta["product_id"], quantity=200,
                            occurred_at="2026-08-18T19:00:00", idempotency_key="dinner-1")
    second = manager.consume(product_id=pasta["product_id"], quantity=200,
                             occurred_at="2026-08-18T19:00:00", idempotency_key="dinner-1")
    assert second == first
    with manager.db.write() as conn:
        assert conn.execute("SELECT remaining FROM batch").fetchone()["remaining"] == 300


def test_opening_a_batch_shortens_its_date(manager, pasta):
    with manager.db.write() as conn:
        conn.execute("UPDATE product SET days_after_opening = 3 WHERE id = ?",
                     (pasta["product_id"],))
    batch_id = manager.add_stock(article_id=pasta["article_id"], quantity=500,
                                 location_id=pasta["location_id"],
                                 best_before="2027-01-01",
                                 occurred_at="2026-08-18T10:00:00")
    manager.open_batch(batch_id, occurred_at="2026-08-18T19:00:00")
    with manager.db.write() as conn:
        batch = conn.execute("SELECT * FROM batch WHERE id = ?", (batch_id,)).fetchone()
        movements = repo.list_movements(conn)
    assert batch["opened_at"] == "2026-08-18T19:00:00"
    assert batch["best_before"] == "2026-08-21"
    # Opening consumes nothing, so it writes no movement beyond the purchase.
    assert [m["reason"] for m in movements] == ["purchase"]


def test_opening_never_pushes_a_date_further_away(manager, pasta):
    with manager.db.write() as conn:
        conn.execute("UPDATE product SET days_after_opening = 30 WHERE id = ?",
                     (pasta["product_id"],))
    batch_id = manager.add_stock(article_id=pasta["article_id"], quantity=500,
                                 location_id=pasta["location_id"],
                                 best_before="2026-08-20",
                                 occurred_at="2026-08-18T10:00:00")
    manager.open_batch(batch_id, occurred_at="2026-08-18T19:00:00")
    with manager.db.write() as conn:
        batch = conn.execute("SELECT best_before FROM batch WHERE id = ?",
                             (batch_id,)).fetchone()
    assert batch["best_before"] == "2026-08-20"


def test_transfer_moves_the_batch_and_records_a_zero_movement(manager, pasta):
    with manager.db.write() as conn:
        freezer_id = repo.insert_location(conn, name="Congélateur", kind="freezer")
    batch_id = manager.add_stock(article_id=pasta["article_id"], quantity=500,
                                 location_id=pasta["location_id"],
                                 occurred_at="2026-08-18T10:00:00")
    manager.transfer_batch(batch_id, freezer_id, occurred_at="2026-08-18T20:00:00")
    with manager.db.write() as conn:
        batch = conn.execute("SELECT location_id FROM batch WHERE id = ?",
                             (batch_id,)).fetchone()
        movement = conn.execute(
            "SELECT * FROM movement WHERE reason = 'transfer'").fetchone()
    assert batch["location_id"] == freezer_id
    assert movement["quantity"] == 0
    assert movement["ref_type"] == "location"
    assert movement["ref_id"] == freezer_id
    assert movement["kcal"] is None and movement["cost"] is None


def test_inventory_adjustment_downwards(manager, pasta):
    manager.add_stock(article_id=pasta["article_id"], quantity=500,
                      location_id=pasta["location_id"], price_per_base_unit=0.004,
                      occurred_at="2026-08-18T10:00:00")
    manager.adjust_inventory(article_id=pasta["article_id"],
                             location_id=pasta["location_id"], counted_quantity=420,
                             occurred_at="2026-08-19T09:00:00")
    with manager.db.write() as conn:
        batch = conn.execute("SELECT remaining FROM batch").fetchone()
        movement = conn.execute(
            "SELECT * FROM movement WHERE reason = 'inventory'").fetchone()
    assert batch["remaining"] == 420
    assert movement["quantity"] == -80
    # An inventory correction is not a consumption: it costs nothing and feeds no total.
    assert movement["kcal"] is None
    assert movement["cost"] is None


def test_inventory_adjustment_upwards_creates_a_batch(manager, pasta):
    manager.add_stock(article_id=pasta["article_id"], quantity=100,
                      location_id=pasta["location_id"], occurred_at="2026-08-18T10:00:00")
    manager.adjust_inventory(article_id=pasta["article_id"],
                             location_id=pasta["location_id"], counted_quantity=300,
                             occurred_at="2026-08-19T09:00:00")
    with manager.db.write() as conn:
        total = conn.execute(
            "SELECT SUM(remaining) AS s FROM batch WHERE closed_at IS NULL").fetchone()
    assert total["s"] == 300


def test_inventory_adjustment_with_nothing_to_do(manager, pasta):
    manager.add_stock(article_id=pasta["article_id"], quantity=100,
                      location_id=pasta["location_id"], occurred_at="2026-08-18T10:00:00")
    assert manager.adjust_inventory(article_id=pasta["article_id"],
                                    location_id=pasta["location_id"],
                                    counted_quantity=100,
                                    occurred_at="2026-08-19T09:00:00") is None


def test_query_stock_aggregates_per_product(manager, pasta):
    manager.add_stock(article_id=pasta["article_id"], quantity=300,
                      location_id=pasta["location_id"], occurred_at="2026-08-01T10:00:00")
    manager.add_stock(article_id=pasta["article_id"], quantity=200,
                      location_id=pasta["location_id"], occurred_at="2026-08-05T10:00:00")
    rows = manager.query_stock(name="pât")
    assert len(rows) == 1
    assert rows[0]["quantity"] == 500
    assert rows[0]["display"] == "500 g"


def test_summary_reports_value_expirations_and_shortages(manager, pasta):
    manager.add_stock(article_id=pasta["article_id"], quantity=100,
                      location_id=pasta["location_id"], best_before="2026-08-19",
                      price_per_base_unit=0.004, occurred_at="2026-08-18T10:00:00")
    summary = manager.summary(expiration_alert_days=3, today="2026-08-18")
    assert summary["stock_value"] == pytest.approx(0.4)
    assert summary["batch_count"] == 1
    assert len(summary["expiring"]) == 1
    # 100 g in stock against a 200 g threshold.
    assert [s["product_name"] for s in summary["shortages"]] == ["Pâtes"]
```

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `./scripts/test.sh tests/test_application.py -v`
Expected: FAIL — `ModuleNotFoundError: ... application`

- [ ] **Step 3: Implémenter**

`custom_components/home_stock/application.py` :

```python
"""The application layer: composes the domain rules with the repositories.

Everything here is synchronous. Home Assistant calls it from the executor.
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from .const import (
    REASON_CONSUMPTION,
    REASON_INVENTORY,
    REASON_PURCHASE,
    REASON_TRANSFER,
)
from .domain.nutrition import movement_values
from .domain.stock import BatchView, allocate, is_empty
from .domain.units import format_quantity, to_base_quantity
from .storage import repositories as repo
from .storage.database import Database


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0, tzinfo=None).isoformat()


def _as_batch_view(row: dict[str, Any]) -> BatchView:
    return BatchView(
        id=row["id"],
        remaining=row["remaining"],
        best_before=date.fromisoformat(row["best_before"]) if row["best_before"] else None,
        entered_at=datetime.fromisoformat(row["entered_at"]),
        opened_at=datetime.fromisoformat(row["opened_at"]) if row["opened_at"] else None,
        price_per_base_unit=row["price_per_base_unit"],
        kcal_per_base_unit=row["kcal_per_base_unit"],
    )


class StockManager:
    """Every write to the stock goes through here."""

    def __init__(self, db: Database) -> None:
        self.db = db

    # --- writes -------------------------------------------------------------

    def add_stock(self, *, article_id: int, quantity: float, location_id: int,
                  best_before: str | None = None,
                  price_per_base_unit: float | None = None,
                  packaging_base_quantity: float | None = None,
                  occurred_at: str | None = None,
                  idempotency_key: str | None = None) -> int:
        """Create a batch and its purchase movement. Returns the batch id."""
        moment = occurred_at or _now()
        amount = to_base_quantity(quantity, packaging_base_quantity)
        with self.db.write() as conn:
            if idempotency_key and repo.movement_exists(conn, idempotency_key):
                row = conn.execute(
                    "SELECT batch_id FROM movement WHERE idempotency_key = ?",
                    (idempotency_key,),
                ).fetchone()
                return int(row["batch_id"])
            article = repo.get_article(conn, article_id)
            if article is None:
                raise ValueError(f"unknown article {article_id}")
            batch_id = repo.insert_batch(
                conn, article_id=article_id, location_id=location_id, quantity=amount,
                entered_at=moment, best_before=best_before,
                price_per_base_unit=price_per_base_unit,
            )
            values = movement_values(amount, article["kcal_per_base_unit"],
                                     price_per_base_unit)
            repo.insert_movement(
                conn, occurred_at=moment, product_id=article["product_id"],
                article_id=article_id, batch_id=batch_id, quantity=amount,
                reason=REASON_PURCHASE, kcal=values.kcal, cost=values.cost,
                idempotency_key=idempotency_key,
            )
            if price_per_base_unit is not None:
                repo.insert_price(
                    conn, article_id=article_id, observed_on=moment[:10],
                    price_per_base_unit=price_per_base_unit, source="manual",
                )
            return batch_id

    def consume(self, *, product_id: int, quantity: float,
                reason: str = REASON_CONSUMPTION, occurred_at: str | None = None,
                idempotency_key: str | None = None) -> list[int]:
        """Take a quantity out of stock, across as many batches as needed."""
        moment = occurred_at or _now()
        with self.db.write() as conn:
            if idempotency_key and repo.movement_exists(conn, idempotency_key):
                # Replayed call: return the movements the first call wrote.
                rows = conn.execute(
                    "SELECT id FROM movement WHERE idempotency_key = ?"
                    " OR idempotency_key LIKE ? ORDER BY id",
                    (idempotency_key, f"{idempotency_key}#%"),
                ).fetchall()
                return [int(row["id"]) for row in rows]
            batches = [_as_batch_view(row)
                       for row in repo.list_batches_for_product(conn, product_id)]
            allocations = allocate(batches, quantity)   # raises InsufficientStock
            movement_ids: list[int] = []
            for index, allocation in enumerate(allocations):
                article_row = conn.execute(
                    "SELECT article_id FROM batch WHERE id = ?", (allocation.batch_id,)
                ).fetchone()
                values = movement_values(allocation.quantity,
                                         allocation.kcal_per_base_unit,
                                         allocation.price_per_base_unit)
                # One consumption can span several batches, but the key is UNIQUE:
                # the first movement carries it, the next ones carry "key#1", "key#2".
                key = None
                if idempotency_key:
                    key = idempotency_key if index == 0 else f"{idempotency_key}#{index}"
                movement_ids.append(repo.insert_movement(
                    conn, occurred_at=moment, product_id=product_id,
                    article_id=article_row["article_id"], batch_id=allocation.batch_id,
                    quantity=-allocation.quantity, reason=reason, kcal=values.kcal,
                    cost=values.cost, idempotency_key=key,
                ))
                repo.set_batch_remaining(
                    conn, allocation.batch_id, allocation.remaining_after,
                    closed_at=moment if allocation.closes_batch else None,
                )
            return movement_ids

    def open_batch(self, batch_id: int, *, occurred_at: str | None = None) -> None:
        """Mark a batch open and, if the product says so, bring its date closer."""
        moment = occurred_at or _now()
        with self.db.write() as conn:
            row = conn.execute(
                "SELECT b.best_before, p.days_after_opening FROM batch b"
                " JOIN article a ON a.id = b.article_id"
                " JOIN product p ON p.id = a.product_id WHERE b.id = ?",
                (batch_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"unknown batch {batch_id}")
            best_before = row["best_before"]
            if row["days_after_opening"]:
                shortened = (
                    datetime.fromisoformat(moment).date()
                    + timedelta(days=int(row["days_after_opening"]))
                ).isoformat()
                if best_before is None or shortened < best_before:
                    best_before = shortened
            repo.set_batch_opened(conn, batch_id, moment, best_before)

    def transfer_batch(self, batch_id: int, location_id: int, *,
                       occurred_at: str | None = None) -> int:
        """Move a batch to another location. Nothing is consumed."""
        moment = occurred_at or _now()
        with self.db.write() as conn:
            row = conn.execute(
                "SELECT b.article_id, a.product_id FROM batch b"
                " JOIN article a ON a.id = b.article_id WHERE b.id = ?",
                (batch_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"unknown batch {batch_id}")
            repo.set_batch_location(conn, batch_id, location_id)
            return repo.insert_movement(
                conn, occurred_at=moment, product_id=row["product_id"],
                article_id=row["article_id"], batch_id=batch_id, quantity=0,
                reason=REASON_TRANSFER, ref_type="location", ref_id=location_id,
            )

    def adjust_inventory(self, *, article_id: int, location_id: int,
                         counted_quantity: float,
                         occurred_at: str | None = None) -> int | None:
        """Record what was actually counted. Returns the movement id, or None."""
        moment = occurred_at or _now()
        with self.db.write() as conn:
            article = repo.get_article(conn, article_id)
            if article is None:
                raise ValueError(f"unknown article {article_id}")
            rows = conn.execute(
                "SELECT * FROM batch WHERE article_id = ? AND location_id = ?"
                " AND closed_at IS NULL", (article_id, location_id),
            ).fetchall()
            current = sum(row["remaining"] for row in rows)
            delta = counted_quantity - current
            if abs(delta) < 0.001:
                return None
            if delta < 0:
                views = [
                    BatchView(
                        id=row["id"], remaining=row["remaining"],
                        best_before=date.fromisoformat(row["best_before"])
                        if row["best_before"] else None,
                        entered_at=datetime.fromisoformat(row["entered_at"]),
                        opened_at=datetime.fromisoformat(row["opened_at"])
                        if row["opened_at"] else None,
                        price_per_base_unit=row["price_per_base_unit"],
                        kcal_per_base_unit=article["kcal_per_base_unit"],
                    )
                    for row in rows
                ]
                for allocation in allocate(views, -delta):
                    repo.set_batch_remaining(
                        conn, allocation.batch_id, allocation.remaining_after,
                        closed_at=moment if allocation.closes_batch else None,
                    )
                batch_id = None
            else:
                batch_id = repo.insert_batch(
                    conn, article_id=article_id, location_id=location_id,
                    quantity=delta, entered_at=moment,
                )
            # kcal and cost stay NULL: a correction is not a consumption (spec 7.5).
            return repo.insert_movement(
                conn, occurred_at=moment, product_id=article["product_id"],
                article_id=article_id, batch_id=batch_id, quantity=delta,
                reason=REASON_INVENTORY,
            )

    # --- reads --------------------------------------------------------------

    def query_stock(self, *, name: str | None = None) -> list[dict[str, Any]]:
        """What is in stock, aggregated per product. Feeds the voice answer."""
        rows = repo.stock_rows(self.db.read())
        grouped: dict[int, dict[str, Any]] = {}
        for row in rows:
            entry = grouped.setdefault(row["product_id"], {
                "product_id": row["product_id"], "product_name": row["product_name"],
                "base_unit": row["base_unit"], "quantity": 0.0, "batches": 0,
            })
            entry["quantity"] += row["remaining"]
            entry["batches"] += 1
        result = list(grouped.values())
        if name:
            needle = name.casefold()
            result = [e for e in result if needle in e["product_name"].casefold()]
        for entry in result:
            entry["display"] = format_quantity(entry["quantity"], entry["base_unit"])
        return sorted(result, key=lambda e: e["product_name"])

    def summary(self, *, expiration_alert_days: int,
                today: str | None = None) -> dict[str, Any]:
        """The numbers the entities publish."""
        reference = date.fromisoformat(today) if today else datetime.now(UTC).date()
        limit = reference + timedelta(days=expiration_alert_days)
        rows = repo.stock_rows(self.db.read())

        value = 0.0
        unpriced = 0
        expiring: list[dict[str, Any]] = []
        per_product: dict[int, dict[str, Any]] = {}
        for row in rows:
            if row["price_per_base_unit"] is None:
                unpriced += 1
            else:
                value += row["remaining"] * row["price_per_base_unit"]
            if row["best_before"] and date.fromisoformat(row["best_before"]) <= limit:
                expiring.append({
                    "batch_id": row["id"], "product_name": row["product_name"],
                    "best_before": row["best_before"],
                    "display": format_quantity(row["remaining"], row["base_unit"]),
                })
            entry = per_product.setdefault(row["product_id"], {
                "product_name": row["product_name"], "quantity": 0.0,
                "min_quantity": row["min_quantity"], "base_unit": row["base_unit"],
            })
            entry["quantity"] += row["remaining"]

        shortages = [
            {"product_name": entry["product_name"],
             "display": format_quantity(entry["quantity"], entry["base_unit"])}
            for entry in per_product.values()
            if entry["min_quantity"] and entry["quantity"] < entry["min_quantity"]
        ]
        return {
            "stock_value": round(value, 2),
            "unpriced_batches": unpriced,
            "batch_count": len(rows),
            "open_batch_count": sum(1 for row in rows if row["opened_at"]),
            "expiring": sorted(expiring, key=lambda e: e["best_before"]),
            "shortages": sorted(shortages, key=lambda e: e["product_name"]),
        }

    def export_journal(self) -> list[dict[str, Any]]:
        """The whole append-only journal. It is enough to rebuild everything."""
        return repo.list_movements(self.db.read())
```

- [ ] **Step 4: Lancer, vérifier le succès**

Run: `./scripts/test.sh tests/test_application.py -v`
Expected: PASS (15 tests)

Si `test_an_idempotency_key_prevents_a_replayed_consumption` échoue, c'est la clé sur plusieurs mouvements : la contrainte `UNIQUE` n'autorise la clé que sur **un** mouvement, les suivants portent `clé#1`, `clé#2`. Ne pas contourner en supprimant la contrainte — c'est elle qui rend le rejeu inoffensif.

- [ ] **Step 5: Lancer TOUTE la suite**

Run: `./scripts/test.sh -v`
Expected: PASS — aucune régression sur les tâches 1 à 6.

- [ ] **Step 6: Commit**

```bash
git add custom_components/home_stock/application.py tests/test_application.py
git commit -m "feat: add StockManager, the application layer over domain and storage"
```

---

### Task 8: Mise en place Home Assistant — entrée, coordinateur, options

**Files:**
- Modify: `custom_components/home_stock/__init__.py`
- Create: `custom_components/home_stock/coordinator.py`, `custom_components/home_stock/config_flow.py`
- Create: `custom_components/home_stock/translations/fr.json`, `custom_components/home_stock/translations/en.json`
- Test: `tests/test_init.py`, `tests/test_config_flow.py`

**Interfaces:**
- Consumes: `StockManager`, `Database`, `apply_migrations`, `const`.
- Produces:
  - `@dataclass class HomeStockData` — `database: Database`, `manager: StockManager`, `coordinator: HomeStockCoordinator`
  - `type HomeStockConfigEntry = ConfigEntry[HomeStockData]`
  - `class HomeStockCoordinator(DataUpdateCoordinator[dict])` — `.manager`, données = le dictionnaire de `StockManager.summary()`
  - `PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.TODO]`

- [ ] **Step 1: Écrire les tests qui échouent**

`tests/test_init.py` :

```python
from pathlib import Path

from homeassistant.config_entries import ConfigEntryState
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.home_stock.const import DOMAIN


async def test_setup_creates_the_database_and_loads(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={}, title="Garde-manger")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert Path(hass.config.path("home_stock.db")).exists()
    assert entry.runtime_data.coordinator.data["batch_count"] == 0


async def test_unload_closes_the_database(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
```

`tests/test_config_flow.py` :

```python
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.home_stock.const import (
    CONF_EXPIRATION_ALERT_DAYS,
    DEFAULT_EXPIRATION_ALERT_DAYS,
    DOMAIN,
)


async def test_user_flow_creates_the_entry(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Garde-manger"


async def test_only_one_entry_is_allowed(hass):
    MockConfigEntry(domain=DOMAIN, data={}).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_options_flow_sets_the_alert_threshold(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_EXPIRATION_ALERT_DAYS: 7}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_EXPIRATION_ALERT_DAYS] == 7
    assert DEFAULT_EXPIRATION_ALERT_DAYS == 3
```

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `./scripts/test.sh tests/test_init.py tests/test_config_flow.py -v`
Expected: FAIL — l'entrée ne se charge pas (`async_setup_entry` absent).

- [ ] **Step 3: Implémenter le coordinateur**

`custom_components/home_stock/coordinator.py` :

```python
"""Refreshes the summary the entities publish."""
from __future__ import annotations

import logging
from datetime import timedelta
from functools import partial
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .application import StockManager
from .const import CONF_EXPIRATION_ALERT_DAYS, DEFAULT_EXPIRATION_ALERT_DAYS, DOMAIN

_LOGGER = logging.getLogger(__name__)


class HomeStockCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Reads the summary from SQLite, in the executor."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry,
                 manager: StockManager) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=15),
            config_entry=entry,
        )
        self.manager = manager

    async def _async_update_data(self) -> dict[str, Any]:
        days = self.config_entry.options.get(
            CONF_EXPIRATION_ALERT_DAYS, DEFAULT_EXPIRATION_ALERT_DAYS
        )
        return await self.hass.async_add_executor_job(
            partial(self.manager.summary, expiration_alert_days=days)
        )
```

Les services d'écriture appellent `await coordinator.async_request_refresh()` après chaque succès : le polling toutes les 15 minutes n'est qu'un filet, l'affichage doit bouger immédiatement.

- [ ] **Step 4: Implémenter la mise en place**

`custom_components/home_stock/__init__.py` :

```python
"""The Garde-manger integration."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .application import StockManager
from .const import DATABASE_FILENAME
from .coordinator import HomeStockCoordinator
from .storage.database import Database
from .storage.migrations import apply_migrations

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.TODO]


@dataclass
class HomeStockData:
    """What the entry keeps alive while it is loaded."""

    database: Database
    manager: StockManager
    coordinator: HomeStockCoordinator


type HomeStockConfigEntry = ConfigEntry[HomeStockData]


async def async_setup_entry(hass: HomeAssistant, entry: HomeStockConfigEntry) -> bool:
    """Open the database, migrate it, and start the coordinator."""
    database = Database(hass.config.path(DATABASE_FILENAME))

    def _open() -> None:
        database.connect()
        with database.write() as conn:
            apply_migrations(conn)

    await hass.async_add_executor_job(_open)

    manager = StockManager(database)
    coordinator = HomeStockCoordinator(hass, entry, manager)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = HomeStockData(database, manager, coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def _async_reload_entry(hass: HomeAssistant, entry: HomeStockConfigEntry) -> None:
    """Options changed: reload so the new threshold is applied."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: HomeStockConfigEntry) -> bool:
    """Close the database when the entry goes away."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await hass.async_add_executor_job(entry.runtime_data.database.close)
    return unloaded
```

`custom_components/home_stock/config_flow.py` :

```python
"""One entry, no credentials: everything is local."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_EXPIRATION_ALERT_DAYS, DEFAULT_EXPIRATION_ALERT_DAYS, DOMAIN


class HomeStockConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create the single entry."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        return self.async_create_entry(title="Garde-manger", data={})

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return HomeStockOptionsFlow()


class HomeStockOptionsFlow(OptionsFlow):
    """How many days before a date counts as expiring."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = self.config_entry.options.get(
            CONF_EXPIRATION_ALERT_DAYS, DEFAULT_EXPIRATION_ALERT_DAYS
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_EXPIRATION_ALERT_DAYS, default=current):
                    vol.All(vol.Coerce(int), vol.Range(min=0, max=60)),
            }),
        )
```

`custom_components/home_stock/translations/fr.json` :

```json
{
  "config": {
    "step": {
      "user": {
        "title": "Garde-manger",
        "description": "Rien à configurer : la base est créée dans le dossier de configuration."
      }
    },
    "abort": {
      "single_instance_allowed": "Le garde-manger est déjà configuré."
    }
  },
  "options": {
    "step": {
      "init": {
        "title": "Options du garde-manger",
        "data": {
          "expiration_alert_days": "Alerter combien de jours avant la date limite"
        }
      }
    }
  },
  "entity": {
    "sensor": {
      "stock_value": { "name": "Valeur du stock" },
      "batches": { "name": "Lots en stock" },
      "kcal_total": { "name": "Kilocalories sorties du stock" },
      "cost_total": { "name": "Coût des sorties de stock" }
    },
    "binary_sensor": {
      "expirations": { "name": "Péremptions proches" },
      "shortages": { "name": "Ruptures" }
    },
    "todo": {
      "expirations": { "name": "À consommer" }
    }
  }
}
```

`custom_components/home_stock/translations/en.json` :

```json
{
  "config": {
    "step": {
      "user": {
        "title": "Pantry",
        "description": "Nothing to configure: the database is created in the configuration folder."
      }
    },
    "abort": {
      "single_instance_allowed": "The pantry is already set up."
    }
  },
  "options": {
    "step": {
      "init": {
        "title": "Pantry options",
        "data": {
          "expiration_alert_days": "How many days before the best-before date to alert"
        }
      }
    }
  },
  "entity": {
    "sensor": {
      "stock_value": { "name": "Stock value" },
      "batches": { "name": "Batches in stock" },
      "kcal_total": { "name": "Kilocalories out of stock" },
      "cost_total": { "name": "Cost of stock consumed" }
    },
    "binary_sensor": {
      "expirations": { "name": "Expiring soon" },
      "shortages": { "name": "Shortages" }
    },
    "todo": {
      "expirations": { "name": "To eat" }
    }
  }
}
```

- [ ] **Step 5: Lancer, vérifier**

Run: `./scripts/test.sh tests/test_init.py tests/test_config_flow.py -v`
Expected: les tests de `config_flow` passent ; `test_init` échoue encore tant que les plateformes de la tâche 9 n'existent pas. Si c'est le cas, retirer temporairement les plateformes de `PLATFORMS` **n'est pas** la solution : passer à l'étape 6, qui crée des modules de plateforme vides.

- [ ] **Step 6: Créer les modules de plateforme minimaux**

Trois fichiers, chacun avec une fonction de mise en place qui n'ajoute encore aucune
entité. Les entités arrivent à la tâche 9 ; ici on rend seulement le chargement possible.

```python
# custom_components/home_stock/sensor.py (idem binary_sensor.py, todo.py)
"""Sensors. Entities are added in the next task."""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeStockConfigEntry


async def async_setup_entry(hass: HomeAssistant, entry: HomeStockConfigEntry,
                            async_add_entities: AddEntitiesCallback) -> None:
    """No entity yet."""
    return
```

- [ ] **Step 7: Lancer, vérifier le succès**

Run: `./scripts/test.sh tests/test_init.py tests/test_config_flow.py -v`
Expected: PASS (5 tests)

- [ ] **Step 8: Commit**

```bash
git add custom_components/home_stock tests/test_init.py tests/test_config_flow.py
git commit -m "feat: set up the config entry, coordinator and options flow"
```

---

### Task 9: Entités de synthèse

**Files:**
- Modify: `custom_components/home_stock/application.py` (ajout de `consume_batch`, totaux dans `summary`)
- Modify: `custom_components/home_stock/storage/repositories.py` (ajout de `counted_totals`)
- Create: `custom_components/home_stock/entity.py`
- Modify: `custom_components/home_stock/sensor.py`, `binary_sensor.py`, `todo.py`
- Test: `tests/test_entities.py`, `tests/test_application.py` (ajout)

**Interfaces:**
- Consumes: `HomeStockCoordinator.data` — clés `stock_value`, `unpriced_batches`, `batch_count`, `open_batch_count`, `expiring`, `shortages`.
- Produces:
  - `StockManager.consume_batch(batch_id, *, quantity=None, reason="consumption", occurred_at=None) -> int`
  - `repositories.counted_totals(conn) -> dict` — `{"kcal": float, "cost": float}` sur les motifs comptés
  - `summary()` gagne les clés `kcal_total` et `cost_total`
  - `sensor.home_stock_stock_value`, `sensor.home_stock_batches`
  - `sensor.home_stock_kcal_total`, `sensor.home_stock_cost_total` — `total_increasing`, ce sont eux que les `utility_meter` journaliers du lot 2 découperont
  - `binary_sensor.home_stock_expirations`, `binary_sensor.home_stock_shortages`
  - `todo.home_stock_expirations` — cocher un élément consomme le lot entier

- [ ] **Step 1: Test de `consume_batch`, qui échoue**

Ajouter à `tests/test_application.py` :

```python
def test_consume_batch_empties_one_precise_batch(manager, pasta):
    old = manager.add_stock(article_id=pasta["article_id"], quantity=300,
                            location_id=pasta["location_id"], best_before="2026-08-20",
                            price_per_base_unit=0.004, occurred_at="2026-08-01T10:00:00")
    recent = manager.add_stock(article_id=pasta["article_id"], quantity=500,
                               location_id=pasta["location_id"], best_before="2026-09-20",
                               occurred_at="2026-08-10T10:00:00")
    # The todo list checks off a batch by its id, not by FIFO order.
    manager.consume_batch(recent, occurred_at="2026-08-18T19:00:00")
    with manager.db.write() as conn:
        rows = {r["id"]: r for r in conn.execute("SELECT * FROM batch").fetchall()}
    assert rows[recent]["remaining"] == 0
    assert rows[recent]["closed_at"] == "2026-08-18T19:00:00"
    assert rows[old]["remaining"] == 300


def test_consume_batch_can_take_a_part_and_a_reason(manager, pasta):
    batch_id = manager.add_stock(article_id=pasta["article_id"], quantity=500,
                                 location_id=pasta["location_id"],
                                 occurred_at="2026-08-01T10:00:00")
    manager.consume_batch(batch_id, quantity=120, reason="waste",
                          occurred_at="2026-08-18T19:00:00")
    with manager.db.write() as conn:
        batch = conn.execute("SELECT * FROM batch WHERE id = ?", (batch_id,)).fetchone()
        movement = conn.execute("SELECT * FROM movement WHERE reason = 'waste'").fetchone()
    assert batch["remaining"] == 380
    assert movement["quantity"] == -120
```

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `./scripts/test.sh tests/test_application.py -k consume_batch -v`
Expected: FAIL — `AttributeError: 'StockManager' object has no attribute 'consume_batch'`

- [ ] **Step 3: Implémenter `consume_batch`**

Ajouter à `custom_components/home_stock/application.py`, dans `StockManager` :

```python
    def consume_batch(self, batch_id: int, *, quantity: float | None = None,
                      reason: str = REASON_CONSUMPTION,
                      occurred_at: str | None = None) -> int:
        """Take from one precise batch. Without a quantity, empties it.

        The expiry list checks off a batch, not a product: FIFO must not apply.
        """
        moment = occurred_at or _now()
        with self.db.write() as conn:
            row = conn.execute(
                "SELECT b.*, a.product_id, a.kcal_per_base_unit FROM batch b"
                " JOIN article a ON a.id = b.article_id"
                " WHERE b.id = ? AND b.closed_at IS NULL",
                (batch_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"unknown or closed batch {batch_id}")
            taken = row["remaining"] if quantity is None else float(quantity)
            if taken > row["remaining"] + 0.001:
                raise InsufficientStock(requested=taken, available=row["remaining"])
            remaining_after = row["remaining"] - taken
            closes = is_empty(remaining_after)
            values = movement_values(taken, row["kcal_per_base_unit"],
                                     row["price_per_base_unit"])
            movement_id = repo.insert_movement(
                conn, occurred_at=moment, product_id=row["product_id"],
                article_id=row["article_id"], batch_id=batch_id, quantity=-taken,
                reason=reason, kcal=values.kcal, cost=values.cost,
            )
            repo.set_batch_remaining(conn, batch_id, 0.0 if closes else remaining_after,
                                     closed_at=moment if closes else None)
            return movement_id
```

Ajouter `InsufficientStock` à l'import depuis `.domain.stock`.

- [ ] **Step 3 bis: Ajouter les totaux cumulés**

Dans `storage/repositories.py` :

```python
def counted_totals(conn) -> dict[str, float]:
    """Cumulative kcal and cost of everything that left the stock.

    Purchases, inventory corrections and transfers are excluded: only the reasons
    listed in COUNTED_REASONS feed the daily totals (spec 7.5).
    """
    marks = ", ".join("?" for _ in COUNTED_REASONS)
    row = conn.execute(
        f"SELECT COALESCE(SUM(kcal), 0) AS kcal, COALESCE(SUM(cost), 0) AS cost"
        f" FROM movement WHERE reason IN ({marks})",
        tuple(sorted(COUNTED_REASONS)),
    ).fetchone()
    return {"kcal": float(row["kcal"]), "cost": float(row["cost"])}
```

avec `from ..const import COUNTED_REASONS` en tête du fichier.

Dans `application.py`, à la fin de `summary()`, avant le `return` :

```python
        totals = repo.counted_totals(self.db.read())
```

et deux clés supplémentaires dans le dictionnaire retourné :

```python
            "kcal_total": round(totals["kcal"], 1),
            "cost_total": round(totals["cost"], 2),
```

Ces deux compteurs ne décroissent jamais — le journal est en ajout seul — d'où
`total_increasing` côté capteur, et des statistiques long terme propres.

- [ ] **Step 4: Écrire les tests d'entités, qui échouent**

`tests/test_entities.py` :

```python
from datetime import date, timedelta

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.home_stock.const import DOMAIN
from custom_components.home_stock.storage import repositories as repo


@pytest.fixture
async def loaded(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_entities_are_created_empty(hass, loaded):
    assert hass.states.get("sensor.home_stock_stock_value").state == "0.0"
    assert hass.states.get("sensor.home_stock_batches").state == "0"
    assert hass.states.get("binary_sensor.home_stock_expirations").state == "off"
    assert hass.states.get("binary_sensor.home_stock_shortages").state == "off"


async def test_entities_reflect_the_stock(hass, loaded):
    manager = loaded.runtime_data.manager

    def _seed() -> None:
        with manager.db.write() as conn:
            location_id = repo.insert_location(conn, name="Frigo", kind="fridge")
            product_id = repo.insert_product(conn, name="Lait", base_unit="ml",
                                             min_quantity=2000)
            article_id = repo.insert_article(conn, product_id=product_id,
                                             kcal_per_base_unit=0.46)
        manager.add_stock(article_id=article_id, quantity=1000,
                          location_id=location_id, best_before="2026-08-19",
                          price_per_base_unit=0.0012,
                          occurred_at="2026-08-18T10:00:00")

    await hass.async_add_executor_job(_seed)
    await loaded.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get("sensor.home_stock_batches").state == "1"
    assert float(hass.states.get("sensor.home_stock_stock_value").state) == 1.2
    assert hass.states.get("binary_sensor.home_stock_shortages").state == "on"
    shortages = hass.states.get("binary_sensor.home_stock_shortages")
    assert shortages.attributes["products"] == ["Lait"]


async def test_the_cumulative_counters_only_count_what_left_the_stock(hass, loaded):
    manager = loaded.runtime_data.manager

    def _seed() -> None:
        with manager.db.write() as conn:
            location_id = repo.insert_location(conn, name="Placard", kind="pantry")
            product_id = repo.insert_product(conn, name="Pâtes", base_unit="g")
            article_id = repo.insert_article(conn, product_id=product_id,
                                             kcal_per_base_unit=3.5)
        manager.add_stock(article_id=article_id, quantity=500,
                          location_id=location_id, price_per_base_unit=0.004,
                          occurred_at="2026-08-18T10:00:00")
        manager.consume(product_id=product_id, quantity=200,
                        occurred_at="2026-08-18T19:00:00")

    await hass.async_add_executor_job(_seed)
    await loaded.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    # The purchase of 500 g must not count: only the 200 g that left the stock.
    assert float(hass.states.get("sensor.home_stock_kcal_total").state) == 700.0
    assert float(hass.states.get("sensor.home_stock_cost_total").state) == 0.8


async def test_the_todo_list_holds_the_expiring_batches(hass, loaded):
    manager = loaded.runtime_data.manager

    def _seed() -> int:
        with manager.db.write() as conn:
            location_id = repo.insert_location(conn, name="Frigo", kind="fridge")
            product_id = repo.insert_product(conn, name="Yaourt", base_unit="piece")
            article_id = repo.insert_article(conn, product_id=product_id)
        # A date relative to today: a hard-coded one would stop expiring one day.
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        return manager.add_stock(article_id=article_id, quantity=4,
                                 location_id=location_id, best_before=tomorrow,
                                 occurred_at="2026-08-18T10:00:00")

    await hass.async_add_executor_job(_seed)
    await loaded.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    items = await hass.services.async_call(
        "todo", "get_items", {"entity_id": "todo.home_stock_expirations"},
        blocking=True, return_response=True,
    )
    listed = items["todo.home_stock_expirations"]["items"]
    assert len(listed) == 1
    assert "Yaourt" in listed[0]["summary"]
```

- [ ] **Step 5: Lancer, vérifier l'échec**

Run: `./scripts/test.sh tests/test_entities.py -v`
Expected: FAIL — `AttributeError: 'NoneType' object has no attribute 'state'`

- [ ] **Step 6: Implémenter les entités**

`custom_components/home_stock/entity.py` :

```python
"""Base class for every entity: one device, English ids, French display names."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HomeStockCoordinator


class HomeStockEntity(CoordinatorEntity[HomeStockCoordinator]):
    """Everything hangs off one device, named in French by the translations."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: HomeStockCoordinator, key: str,
                 entity_id_format: str) -> None:
        super().__init__(coordinator)
        self._attr_translation_key = key
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{key}"
        # Spec section 14: entity ids in English. Left to Home Assistant they would
        # be built from the French device and entity names.
        self.entity_id = entity_id_format.format(f"{DOMAIN}_{key}")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name="Garde-manger",
            manufacturer="Maison",
        )


```

`custom_components/home_stock/sensor.py` :

```python
"""Summary sensors. There is deliberately no entity per product."""
from __future__ import annotations

from homeassistant.components.sensor import (
    ENTITY_ID_FORMAT,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeStockConfigEntry
from .coordinator import HomeStockCoordinator
from .entity import HomeStockEntity


class StockValueSensor(HomeStockEntity, SensorEntity):
    _attr_native_unit_of_measurement = "EUR"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: HomeStockCoordinator) -> None:
        super().__init__(coordinator, "stock_value", ENTITY_ID_FORMAT)

    @property
    def native_value(self) -> float:
        return self.coordinator.data["stock_value"]

    @property
    def extra_state_attributes(self) -> dict[str, int]:
        # Batches without a price are excluded from the value: say how many.
        return {"unpriced_batches": self.coordinator.data["unpriced_batches"]}


class BatchesSensor(HomeStockEntity, SensorEntity):
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: HomeStockCoordinator) -> None:
        super().__init__(coordinator, "batches", ENTITY_ID_FORMAT)

    @property
    def native_value(self) -> int:
        return self.coordinator.data["batch_count"]

    @property
    def extra_state_attributes(self) -> dict[str, int]:
        return {"open": self.coordinator.data["open_batch_count"]}


class KcalTotalSensor(HomeStockEntity, SensorEntity):
    """Cumulative kcal that left the stock. The lot 2 utility_meter slices it per day."""

    _attr_native_unit_of_measurement = "kcal"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator: HomeStockCoordinator) -> None:
        super().__init__(coordinator, "kcal_total", ENTITY_ID_FORMAT)

    @property
    def native_value(self) -> float:
        return self.coordinator.data["kcal_total"]


class CostTotalSensor(HomeStockEntity, SensorEntity):
    """Cumulative cost of what left the stock, purchases excluded."""

    _attr_native_unit_of_measurement = "EUR"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator: HomeStockCoordinator) -> None:
        super().__init__(coordinator, "cost_total", ENTITY_ID_FORMAT)

    @property
    def native_value(self) -> float:
        return self.coordinator.data["cost_total"]


async def async_setup_entry(hass: HomeAssistant, entry: HomeStockConfigEntry,
                            async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data.coordinator
    async_add_entities([
        StockValueSensor(coordinator),
        BatchesSensor(coordinator),
        KcalTotalSensor(coordinator),
        CostTotalSensor(coordinator),
    ])
```

`custom_components/home_stock/binary_sensor.py` :

```python
"""Two alerts: something expires soon, something ran short."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    ENTITY_ID_FORMAT,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeStockConfigEntry
from .coordinator import HomeStockCoordinator
from .entity import HomeStockEntity


class ExpirationsBinarySensor(HomeStockEntity, BinarySensorEntity):
    def __init__(self, coordinator: HomeStockCoordinator) -> None:
        super().__init__(coordinator, "expirations", ENTITY_ID_FORMAT)

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data["expiring"])

    @property
    def extra_state_attributes(self) -> dict[str, list]:
        return {"batches": self.coordinator.data["expiring"]}


class ShortagesBinarySensor(HomeStockEntity, BinarySensorEntity):
    def __init__(self, coordinator: HomeStockCoordinator) -> None:
        super().__init__(coordinator, "shortages", ENTITY_ID_FORMAT)

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data["shortages"])

    @property
    def extra_state_attributes(self) -> dict[str, list[str]]:
        return {"products": [s["product_name"] for s in self.coordinator.data["shortages"]]}


async def async_setup_entry(hass: HomeAssistant, entry: HomeStockConfigEntry,
                            async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data.coordinator
    async_add_entities([ExpirationsBinarySensor(coordinator),
                        ShortagesBinarySensor(coordinator)])
```

`custom_components/home_stock/todo.py` :

```python
"""The expiring batches, as a checkable list.

Checking an item means EATEN: a checkbox carries one bit and cannot tell "eaten"
from "thrown away". Throwing away goes through home_stock.consume with the waste
reason (spec 8.1).
"""
from __future__ import annotations

from functools import partial

from homeassistant.components.todo import (
    ENTITY_ID_FORMAT,
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeStockConfigEntry
from .coordinator import HomeStockCoordinator
from .entity import HomeStockEntity


class ExpirationsTodoList(HomeStockEntity, TodoListEntity):
    _attr_supported_features = TodoListEntityFeature.UPDATE_TODO_ITEM

    def __init__(self, coordinator: HomeStockCoordinator) -> None:
        super().__init__(coordinator, "expirations", ENTITY_ID_FORMAT)

    @property
    def todo_items(self) -> list[TodoItem]:
        return [
            TodoItem(
                uid=str(batch["batch_id"]),
                summary=f"{batch['product_name']} — {batch['display']}",
                due=None,
                description=f"Date limite {batch['best_before']}",
                status=TodoItemStatus.NEEDS_ACTION,
            )
            for batch in self.coordinator.data["expiring"]
        ]

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """A checked item is a consumed batch."""
        if item.status is not TodoItemStatus.COMPLETED or item.uid is None:
            return
        manager = self.coordinator.manager
        await self.hass.async_add_executor_job(
            partial(manager.consume_batch, int(item.uid))
        )
        await self.coordinator.async_request_refresh()


async def async_setup_entry(hass: HomeAssistant, entry: HomeStockConfigEntry,
                            async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities([ExpirationsTodoList(entry.runtime_data.coordinator)])
```

- [ ] **Step 7: Lancer, vérifier le succès**

Run: `./scripts/test.sh tests/test_entities.py tests/test_application.py -v`
Expected: PASS

Les `entity_id` sont imposés dans le constructeur (`self.entity_id = ...`) et non
laissés à Home Assistant : avec `_attr_has_entity_name`, HA les composerait à partir
du nom **français** de l'appareil et de l'entité (`sensor.garde_manger_valeur_du_stock`),
ce que le spec §14 exclut. Le nom affiché reste français, seul l'identifiant est
anglais.

- [ ] **Step 8: Commit**

```bash
git add custom_components/home_stock tests/test_entities.py tests/test_application.py
git commit -m "feat: publish summary sensors, alerts and the expiring-batch todo list"
```

---

### Task 10: Services Home Assistant

**Files:**
- Create: `custom_components/home_stock/services.py`, `custom_components/home_stock/services.yaml`
- Modify: `custom_components/home_stock/__init__.py` (appel d'enregistrement)
- Test: `tests/test_services.py`

**Interfaces:**
- Consumes: `StockManager`, `HomeStockCoordinator`.
- Produces `async_register_services(hass: HomeAssistant) -> None`, qui enregistre :
  `home_stock.add_stock`, `consume`, `open_batch`, `transfer_batch`, `adjust_inventory`,
  `query_stock` (`SupportsResponse.ONLY`), `export_journal` (`SupportsResponse.ONLY`).

- [ ] **Step 1: Écrire les tests qui échouent**

`tests/test_services.py` :

```python
import pytest
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.home_stock.const import DOMAIN
from custom_components.home_stock.storage import repositories as repo


@pytest.fixture
async def seeded(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    manager = entry.runtime_data.manager

    def _seed() -> dict[str, int]:
        with manager.db.write() as conn:
            location_id = repo.insert_location(conn, name="Placard", kind="pantry")
            product_id = repo.insert_product(conn, name="Pâtes", base_unit="g")
            article_id = repo.insert_article(conn, product_id=product_id,
                                             kcal_per_base_unit=3.5)
            repo.link_barcode(conn, "3038350201553", article_id)
        return {"location_id": location_id, "product_id": product_id,
                "article_id": article_id}

    ids = await hass.async_add_executor_job(_seed)
    return entry, ids


async def test_add_stock_accepts_a_barcode(hass, seeded):
    entry, ids = seeded
    await hass.services.async_call(DOMAIN, "add_stock", {
        "barcode": "3038350201553", "quantity": 500,
        "location_id": ids["location_id"], "price_per_base_unit": 0.004,
    }, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.home_stock_batches").state == "1"


async def test_add_stock_rejects_an_unknown_barcode(hass, seeded):
    entry, ids = seeded
    # Creating an article from an EAN needs Open Food Facts: that is lot 1.
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(DOMAIN, "add_stock", {
            "barcode": "0000000000000", "quantity": 1,
            "location_id": ids["location_id"],
        }, blocking=True)


async def test_consume_reports_insufficient_stock_as_a_home_assistant_error(hass, seeded):
    entry, ids = seeded
    await hass.services.async_call(DOMAIN, "add_stock", {
        "article_id": ids["article_id"], "quantity": 100,
        "location_id": ids["location_id"],
    }, blocking=True)
    with pytest.raises(HomeAssistantError, match="Stock insuffisant"):
        await hass.services.async_call(DOMAIN, "consume", {
            "product_id": ids["product_id"], "quantity": 500,
        }, blocking=True)


async def test_query_stock_returns_a_response(hass, seeded):
    entry, ids = seeded
    await hass.services.async_call(DOMAIN, "add_stock", {
        "article_id": ids["article_id"], "quantity": 500,
        "location_id": ids["location_id"],
    }, blocking=True)
    response = await hass.services.async_call(
        DOMAIN, "query_stock", {"name": "pât"}, blocking=True, return_response=True
    )
    assert response["products"][0]["display"] == "500 g"


async def test_export_journal_returns_the_movements(hass, seeded):
    entry, ids = seeded
    await hass.services.async_call(DOMAIN, "add_stock", {
        "article_id": ids["article_id"], "quantity": 500,
        "location_id": ids["location_id"],
    }, blocking=True)
    response = await hass.services.async_call(
        DOMAIN, "export_journal", {}, blocking=True, return_response=True
    )
    assert [m["reason"] for m in response["movements"]] == ["purchase"]


async def test_the_state_refreshes_right_after_a_write(hass, seeded):
    entry, ids = seeded
    await hass.services.async_call(DOMAIN, "add_stock", {
        "article_id": ids["article_id"], "quantity": 500,
        "location_id": ids["location_id"],
    }, blocking=True)
    await hass.async_block_till_done()
    # No waiting for the 15-minute poll: a write refreshes immediately.
    assert hass.states.get("sensor.home_stock_batches").state == "1"
```

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `./scripts/test.sh tests/test_services.py -v`
Expected: FAIL — `ServiceNotFound: home_stock.add_stock`

- [ ] **Step 3: Implémenter les services**

`custom_components/home_stock/services.py` :

```python
"""Home Assistant services. Every write refreshes the coordinator on success."""
from __future__ import annotations

from functools import partial
from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, REASON_CONSUMPTION, REASONS
from .domain.stock import InsufficientStock
from .domain.units import UnitError
from .storage import repositories as repo

ADD_STOCK_SCHEMA = vol.Schema({
    vol.Exclusive("article_id", "article"): cv.positive_int,
    vol.Exclusive("barcode", "article"): cv.string,
    vol.Required("quantity"): vol.Coerce(float),
    vol.Required("location_id"): cv.positive_int,
    vol.Optional("best_before"): cv.string,
    vol.Optional("price_per_base_unit"): vol.Coerce(float),
    vol.Optional("packaging_base_quantity"): vol.Coerce(float),
    vol.Optional("idempotency_key"): cv.string,
})
CONSUME_SCHEMA = vol.Schema({
    vol.Required("product_id"): cv.positive_int,
    vol.Required("quantity"): vol.Coerce(float),
    vol.Optional("reason", default=REASON_CONSUMPTION): vol.In(REASONS),
    vol.Optional("idempotency_key"): cv.string,
})
BATCH_SCHEMA = vol.Schema({vol.Required("batch_id"): cv.positive_int})
TRANSFER_SCHEMA = BATCH_SCHEMA.extend({vol.Required("location_id"): cv.positive_int})
INVENTORY_SCHEMA = vol.Schema({
    vol.Required("article_id"): cv.positive_int,
    vol.Required("location_id"): cv.positive_int,
    vol.Required("counted_quantity"): vol.Coerce(float),
})
QUERY_SCHEMA = vol.Schema({vol.Optional("name"): cv.string})


def _entry(hass: HomeAssistant):
    """The single loaded entry. Raises if the integration is not set up."""
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        raise HomeAssistantError("Le garde-manger n'est pas configuré.")
    return entries[0]


async def _run(hass: HomeAssistant, work) -> Any:
    """Run a manager call in the executor, translating domain errors."""
    try:
        return await hass.async_add_executor_job(work)
    except InsufficientStock as error:
        raise HomeAssistantError(
            f"Stock insuffisant : {error.requested} demandé, {error.available} disponible."
        ) from error
    except (UnitError, ValueError) as error:
        raise HomeAssistantError(str(error)) from error


def async_register_services(hass: HomeAssistant) -> None:
    """Register once; a reload of the entry must not register twice."""
    if hass.services.has_service(DOMAIN, "add_stock"):
        return

    async def add_stock(call: ServiceCall) -> None:
        entry = _entry(hass)
        manager = entry.runtime_data.manager
        article_id = call.data.get("article_id")
        if article_id is None:
            code = call.data.get("barcode")
            article = await hass.async_add_executor_job(
                partial(repo.find_article_by_barcode, manager.db.read(), code)
            )
            if article is None:
                raise HomeAssistantError(
                    f"Code-barres {code} inconnu. La création d'un article à partir"
                    " d'un code-barres arrive avec le scan (lot 1)."
                )
            article_id = article["id"]
        await _run(hass, partial(
            manager.add_stock,
            article_id=article_id,
            quantity=call.data["quantity"],
            location_id=call.data["location_id"],
            best_before=call.data.get("best_before"),
            price_per_base_unit=call.data.get("price_per_base_unit"),
            packaging_base_quantity=call.data.get("packaging_base_quantity"),
            idempotency_key=call.data.get("idempotency_key"),
        ))
        await entry.runtime_data.coordinator.async_request_refresh()

    async def consume(call: ServiceCall) -> None:
        entry = _entry(hass)
        await _run(hass, partial(
            entry.runtime_data.manager.consume,
            product_id=call.data["product_id"],
            quantity=call.data["quantity"],
            reason=call.data["reason"],
            idempotency_key=call.data.get("idempotency_key"),
        ))
        await entry.runtime_data.coordinator.async_request_refresh()

    async def open_batch(call: ServiceCall) -> None:
        entry = _entry(hass)
        await _run(hass, partial(entry.runtime_data.manager.open_batch,
                                 call.data["batch_id"]))
        await entry.runtime_data.coordinator.async_request_refresh()

    async def transfer_batch(call: ServiceCall) -> None:
        entry = _entry(hass)
        await _run(hass, partial(entry.runtime_data.manager.transfer_batch,
                                 call.data["batch_id"], call.data["location_id"]))
        await entry.runtime_data.coordinator.async_request_refresh()

    async def adjust_inventory(call: ServiceCall) -> None:
        entry = _entry(hass)
        await _run(hass, partial(
            entry.runtime_data.manager.adjust_inventory,
            article_id=call.data["article_id"],
            location_id=call.data["location_id"],
            counted_quantity=call.data["counted_quantity"],
        ))
        await entry.runtime_data.coordinator.async_request_refresh()

    async def query_stock(call: ServiceCall) -> ServiceResponse:
        entry = _entry(hass)
        products = await _run(hass, partial(
            entry.runtime_data.manager.query_stock, name=call.data.get("name")
        ))
        return {"products": products}

    async def export_journal(call: ServiceCall) -> ServiceResponse:
        entry = _entry(hass)
        movements = await _run(hass, entry.runtime_data.manager.export_journal)
        return {"movements": movements}

    hass.services.async_register(DOMAIN, "add_stock", add_stock, schema=ADD_STOCK_SCHEMA)
    hass.services.async_register(DOMAIN, "consume", consume, schema=CONSUME_SCHEMA)
    hass.services.async_register(DOMAIN, "open_batch", open_batch, schema=BATCH_SCHEMA)
    hass.services.async_register(DOMAIN, "transfer_batch", transfer_batch,
                                 schema=TRANSFER_SCHEMA)
    hass.services.async_register(DOMAIN, "adjust_inventory", adjust_inventory,
                                 schema=INVENTORY_SCHEMA)
    hass.services.async_register(DOMAIN, "query_stock", query_stock, schema=QUERY_SCHEMA,
                                 supports_response=SupportsResponse.ONLY)
    hass.services.async_register(DOMAIN, "export_journal", export_journal,
                                 schema=vol.Schema({}),
                                 supports_response=SupportsResponse.ONLY)
```

Ajouter dans `async_setup_entry`, juste avant `return True` :

```python
    async_register_services(hass)
```

et l'import `from .services import async_register_services`.

- [ ] **Step 4: Écrire `services.yaml`**

Un bloc par service, avec `name`, `description` et `selector` en français — c'est ce
que l'interface « Actions » de HA affiche. Les sept blocs, en entier :

```yaml
add_stock:
  name: Ajouter au stock
  description: Crée un lot et son mouvement d'achat.
  fields:
    article_id:
      name: Article
      description: Identifiant de l'article. Alternative au code-barres.
      selector: { number: { min: 1, mode: box } }
    barcode:
      name: Code-barres
      description: EAN d'un article déjà connu. Alternative à l'identifiant.
      selector: { text: }
    quantity:
      name: Quantité
      description: Dans l'unité de base du produit, ou en conditionnements.
      required: true
      selector: { number: { min: 0, step: 0.001, mode: box } }
    location_id:
      name: Emplacement
      required: true
      selector: { number: { min: 1, mode: box } }
    best_before:
      name: Date limite
      selector: { date: }
    price_per_base_unit:
      name: Prix par unité de base
      description: En euros. 0,004 €/g pour un paquet de 500 g à 2 €.
      selector: { number: { min: 0, step: 0.0001, mode: box } }
    packaging_base_quantity:
      name: Taille du conditionnement
      description: Si la quantité est en paquets, le nombre d'unités de base par paquet.
      selector: { number: { min: 0, step: 0.001, mode: box } }
    idempotency_key:
      name: Clé d'idempotence
      description: Rejouer l'appel avec la même clé n'écrit rien de nouveau.
      selector: { text: }

consume:
  name: Consommer
  description: Sort une quantité du stock, en traversant les lots du plus urgent au moins urgent.
  fields:
    product_id:
      name: Produit
      required: true
      selector: { number: { min: 1, mode: box } }
    quantity:
      name: Quantité
      required: true
      selector: { number: { min: 0, step: 0.001, mode: box } }
    reason:
      name: Motif
      default: consumption
      selector:
        select:
          options:
            - { value: consumption, label: Consommé }
            - { value: waste, label: Jeté }
            - { value: expired, label: Périmé }
    idempotency_key:
      name: Clé d'idempotence
      selector: { text: }

open_batch:
  name: Ouvrir un lot
  description: >-
    Marque un lot comme entamé. Si le produit a une durée après ouverture, la date
    limite est avancée. Rien n'est consommé.
  fields:
    batch_id:
      name: Lot
      required: true
      selector: { number: { min: 1, mode: box } }

transfer_batch:
  name: Déplacer un lot
  description: Change l'emplacement d'un lot, par exemple du congélateur au frigo.
  fields:
    batch_id:
      name: Lot
      required: true
      selector: { number: { min: 1, mode: box } }
    location_id:
      name: Emplacement d'arrivée
      required: true
      selector: { number: { min: 1, mode: box } }

adjust_inventory:
  name: Corriger l'inventaire
  description: >-
    Enregistre la quantité réellement comptée pour un article à un emplacement.
    L'écart est journalisé comme correction : il ne compte ni en kilocalories ni en euros.
  fields:
    article_id:
      name: Article
      required: true
      selector: { number: { min: 1, mode: box } }
    location_id:
      name: Emplacement
      required: true
      selector: { number: { min: 1, mode: box } }
    counted_quantity:
      name: Quantité comptée
      description: Dans l'unité de base du produit.
      required: true
      selector: { number: { min: 0, step: 0.001, mode: box } }

query_stock:
  name: Interroger le stock
  description: Renvoie ce qui est en stock, agrégé par produit. Ne modifie rien.
  fields:
    name:
      name: Filtre sur le nom
      description: Fragment de nom, sans tenir compte de la casse ni des accents.
      selector: { text: }

export_journal:
  name: Exporter le journal
  description: >-
    Renvoie tous les mouvements. Le journal étant en ajout seul, il suffit à
    reconstruire l'état du stock.
```

- [ ] **Step 5: Lancer, vérifier le succès**

Run: `./scripts/test.sh tests/test_services.py -v`
Expected: PASS (6 tests)

- [ ] **Step 6: Commit**

```bash
git add custom_components/home_stock tests/test_services.py
git commit -m "feat: expose stock operations as Home Assistant services"
```

---

### Task 11: Commandes websocket pour la future interface

**Files:**
- Create: `custom_components/home_stock/websocket_api.py`
- Modify: `custom_components/home_stock/__init__.py`
- Test: `tests/test_websocket.py`

**Interfaces:**
- Produces `async_register_websocket(hass: HomeAssistant) -> None`, qui enregistre les six commandes du spec §8.3 :
  `home_stock/products/list`, `home_stock/product/get`, `home_stock/batches/list`,
  `home_stock/movements/list`, `home_stock/locations/list`, `home_stock/aisles/list`,
  plus l'abonnement `home_stock/subscribe`.
- Modifie aussi `storage/repositories.py` : ajout de `list_aisles(conn) -> list[dict]`,
  symétrique de `list_locations`.

Ce sont des lectures seules : les écritures passent par les services tant que la SPA
n'existe pas (lot 1).

- [ ] **Step 1: Écrire les tests qui échouent**

`tests/test_websocket.py` :

```python
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.home_stock.const import DOMAIN
from custom_components.home_stock.storage import repositories as repo


@pytest.fixture
async def client(hass, hass_ws_client):
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    manager = entry.runtime_data.manager

    def _seed() -> None:
        with manager.db.write() as conn:
            location_id = repo.insert_location(conn, name="Placard", kind="pantry")
            product_id = repo.insert_product(conn, name="Pâtes", base_unit="g")
            article_id = repo.insert_article(conn, product_id=product_id)
        manager.add_stock(article_id=article_id, quantity=500,
                          location_id=location_id, occurred_at="2026-08-18T10:00:00")

    await hass.async_add_executor_job(_seed)
    return await hass_ws_client(hass)


async def test_products_list(client):
    await client.send_json_auto_id({"type": "home_stock/products/list"})
    message = await client.receive_json()
    assert message["success"] is True
    assert message["result"]["products"][0]["name"] == "Pâtes"


async def test_batches_list_returns_one_row_per_batch(client):
    await client.send_json_auto_id({"type": "home_stock/batches/list"})
    message = await client.receive_json()
    assert message["result"]["batches"][0]["remaining"] == 500
    assert message["result"]["batches"][0]["location_name"] == "Placard"


async def test_locations_list(client):
    await client.send_json_auto_id({"type": "home_stock/locations/list"})
    message = await client.receive_json()
    assert [l["name"] for l in message["result"]["locations"]] == ["Placard"]


async def test_aisles_list_is_empty_until_lot_1(client):
    # The aisle table exists from lot 0; Grocy has no aisles, and Open Food Facts
    # categories seed them at lot 1.
    await client.send_json_auto_id({"type": "home_stock/aisles/list"})
    message = await client.receive_json()
    assert message["result"]["aisles"] == []


async def test_product_get_returns_one_product(hass, client):
    await client.send_json_auto_id({"type": "home_stock/products/list"})
    listed = await client.receive_json()
    product_id = listed["result"]["products"][0]["id"]

    await client.send_json_auto_id(
        {"type": "home_stock/product/get", "product_id": product_id}
    )
    message = await client.receive_json()
    assert message["result"]["product"]["name"] == "Pâtes"


async def test_product_get_reports_an_unknown_id(client):
    await client.send_json_auto_id({"type": "home_stock/product/get", "product_id": 999})
    message = await client.receive_json()
    assert message["success"] is False
    assert message["error"]["code"] == "not_found"


async def test_subscribe_pushes_the_summary(hass, client):
    await client.send_json_auto_id({"type": "home_stock/subscribe"})
    subscription = await client.receive_json()
    assert subscription["success"] is True
    # The first push carries the current summary, without waiting for a change.
    event = await client.receive_json()
    assert event["event"]["batch_count"] == 1
```

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `./scripts/test.sh tests/test_websocket.py -v`
Expected: FAIL — `unknown_command`

- [ ] **Step 3: Implémenter**

Ajouter d'abord à `storage/repositories.py`, juste après `list_locations` :

```python
def list_aisles(conn) -> list[dict[str, Any]]:
    """Aisles in walking order. Empty until Open Food Facts seeds them (lot 1)."""
    return _rows(conn.execute("SELECT * FROM aisle ORDER BY position, name"))
```

Puis `custom_components/home_stock/websocket_api.py` :

```python
"""Read commands for the panel. The panel reuses the Home Assistant connection,
so there is no separate authentication and it can subscribe to changes."""
from __future__ import annotations

from functools import partial
from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .storage import repositories as repo


def _runtime(hass: HomeAssistant):
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    return entries[0].runtime_data if entries else None


async def _read(hass: HomeAssistant, work) -> Any:
    return await hass.async_add_executor_job(work)


@websocket_api.websocket_command({vol.Required("type"): "home_stock/products/list"})
@websocket_api.async_response
async def products_list(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    products = await _read(hass, partial(repo.list_products, runtime.manager.db.read()))
    connection.send_result(msg["id"], {"products": products})


@websocket_api.websocket_command({vol.Required("type"): "home_stock/locations/list"})
@websocket_api.async_response
async def locations_list(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    locations = await _read(hass, partial(repo.list_locations, runtime.manager.db.read()))
    connection.send_result(msg["id"], {"locations": locations})


@websocket_api.websocket_command({vol.Required("type"): "home_stock/aisles/list"})
@websocket_api.async_response
async def aisles_list(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    aisles = await _read(hass, partial(repo.list_aisles, runtime.manager.db.read()))
    connection.send_result(msg["id"], {"aisles": aisles})


@websocket_api.websocket_command({vol.Required("type"): "home_stock/batches/list"})
@websocket_api.async_response
async def batches_list(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    batches = await _read(hass, partial(repo.stock_rows, runtime.manager.db.read()))
    connection.send_result(msg["id"], {"batches": batches})


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/product/get",
    vol.Required("product_id"): int,
})
@websocket_api.async_response
async def product_get(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    product = await _read(hass, partial(
        repo.get_product, runtime.manager.db.read(), msg["product_id"]
    ))
    if product is None:
        connection.send_error(msg["id"], "not_found",
                              f"produit {msg['product_id']} inconnu")
        return
    connection.send_result(msg["id"], {"product": product})


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/movements/list",
    vol.Optional("since"): str,
})
@websocket_api.async_response
async def movements_list(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    movements = await _read(hass, partial(
        repo.list_movements, runtime.manager.db.read(), msg.get("since")
    ))
    connection.send_result(msg["id"], {"movements": movements})


@websocket_api.websocket_command({vol.Required("type"): "home_stock/subscribe"})
@callback
def subscribe(hass, connection, msg) -> None:
    """Push the summary now, and again on every coordinator refresh."""
    runtime = _runtime(hass)
    coordinator = runtime.coordinator

    @callback
    def _forward() -> None:
        connection.send_event(msg["id"], coordinator.data)

    connection.subscriptions[msg["id"]] = coordinator.async_add_listener(_forward)
    connection.send_result(msg["id"])
    _forward()


def async_register_websocket(hass: HomeAssistant) -> None:
    """Register the read commands once."""
    for command in (products_list, product_get, locations_list, aisles_list,
                    batches_list, movements_list, subscribe):
        websocket_api.async_register_command(hass, command)
```

Ajouter dans `async_setup_entry`, à côté de `async_register_services(hass)` :

```python
    async_register_websocket(hass)
```

Home Assistant journalise un avertissement si une commande est enregistrée deux fois ;
comme l'entrée est unique et que le rechargement passe par `async_unload_entry`, le
cas ne se présente qu'en test. Si le journal en montre, entourer l'appel du même garde
que les services.

- [ ] **Step 4: Lancer, vérifier le succès**

Run: `./scripts/test.sh tests/test_websocket.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add custom_components/home_stock/websocket_api.py custom_components/home_stock/__init__.py tests/test_websocket.py
git commit -m "feat: add read-only websocket commands for the future panel"
```

---

### Task 12: Import du catalogue Grocy

**Files:**
- Create: `custom_components/home_stock/import_grocy.py`
- Modify: `custom_components/home_stock/services.py` (service `import_grocy_catalog`), `services.yaml`
- Test: `tests/test_import_grocy.py`

**Interfaces:**
- Produces :
  - `@dataclass class ImportReport` — `products: int`, `articles: int`, `barcodes: int`, `prices: int`, `categories: int`, `locations: int`, `skipped: int`, `anomalies: list[str]`, et `ok: bool` (vrai si `anomalies` est vide)
  - `import_catalog(db: Database, grocy_path: str, *, apply: bool = False) -> ImportReport`
  - Service `home_stock.import_grocy_catalog` — champs `path` (chemin **relatif au dossier de configuration**) et `apply` (défaut `false`), `SupportsResponse.ONLY`

**Le conteneur HA ne voit pas `/opt/nivuus/Grocy`** : ses volumes sont `config/` et `media/`. Copier la base avant :

```bash
cp /opt/nivuus/Grocy/config/data/grocy.db /opt/nivuus/HomeAssistant/config/grocy_import.db
```

La copie est lue en `mode=ro`, jamais écrite, et se supprime après l'import.

**Table de correspondance des unités** (relevée dans la base réelle le 2026-08-18) :

| Unité Grocy | Unité de base | Facteur |
|---|---|---|
| `g` | `g` | 1 |
| `kg` | `g` | 1000 |
| `cl` | `ml` | 10 |
| `Pièce`, `Paquet`, `Pot`, `Bouteille`, `Barquette`, `Brique`, `Boîte`, `Sachet`, `Lot` | `piece` | 1 |
| `cs`, `cc` | — | aucune : unités de dosage, jamais unités de stock. Rencontrées comme unité de stock → anomalie |

Les calories Grocy sont par unité de stock : `kcal_per_base_unit = calories / facteur`.
`min_stock_amount` est multiplié par le facteur. Aucun `packaging` n'est créé à
l'import : le poids net d'un « Paquet » vient d'Open Food Facts, donc du lot 1.

- [ ] **Step 1: Écrire les tests qui échouent**

`tests/test_import_grocy.py` :

```python
import sqlite3

import pytest

from custom_components.home_stock.import_grocy import import_catalog
from custom_components.home_stock.storage import repositories as repo
from custom_components.home_stock.storage.database import Database
from custom_components.home_stock.storage.migrations import apply_migrations


@pytest.fixture
def grocy(tmp_path):
    """A miniature Grocy database with the columns the import reads."""
    path = tmp_path / "grocy.db"
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE quantity_units (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE locations (id INTEGER PRIMARY KEY, name TEXT, is_freezer INTEGER);
        CREATE TABLE product_groups (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE products (
            id INTEGER PRIMARY KEY, name TEXT, active INTEGER, product_group_id INTEGER,
            location_id INTEGER, qu_id_stock INTEGER, min_stock_amount REAL,
            calories REAL, default_best_before_days_after_open INTEGER,
            picture_file_name TEXT);
        CREATE TABLE product_barcodes (
            id INTEGER PRIMARY KEY, product_id INTEGER, barcode TEXT, qu_id INTEGER,
            amount REAL, last_price REAL);
        CREATE TABLE userfields (id INTEGER PRIMARY KEY, entity TEXT, name TEXT);
        CREATE TABLE userfield_values (
            id INTEGER PRIMARY KEY, field_id INTEGER, object_id INTEGER, value TEXT);
    """)
    conn.executemany("INSERT INTO quantity_units VALUES (?, ?)",
                     [(4, "g"), (5, "kg"), (6, "cl"), (2, "Pièce"), (14, "cs")])
    conn.executemany("INSERT INTO locations VALUES (?, ?, ?)",
                     [(2, "Frigo", 0), (3, "Congélateur", 1), (4, "Placard", 0)])
    conn.executemany("INSERT INTO product_groups VALUES (?, ?)",
                     [(1, "Pâtes"), (2, "Produit laitier")])
    conn.executemany(
        "INSERT INTO products VALUES (?,?,?,?,?,?,?,?,?,?)",
        [
            # grams: taken as is
            (1, "Pâtes", 1, 1, 4, 4, 200, 3.5, 0, None),
            # kilograms: quantities x1000, calories /1000
            (2, "Farine", 1, 1, 4, 5, 1, 3640.0, 0, None),
            # centilitres: quantities x10, calories /10
            (3, "Lait", 1, 2, 2, 6, 100, 4.6, 3, None),
            # a container unit stays counted
            (4, "Œufs", 1, 2, 2, 2, 6, 78.0, 0, None),
            # inactive: a disabled duplicate, not imported
            (5, "Pâtes (doublon)", 0, 1, 4, 4, None, None, 0, None),
        ],
    )
    conn.executemany("INSERT INTO product_barcodes VALUES (?,?,?,?,?,?)",
                     [(1, 1, "3038350201553", 4, 500, 2.0),
                      (2, 3, "3033490004743", 6, 100, 1.2)])
    conn.executemany("INSERT INTO userfields VALUES (?,?,?)",
                     [(1, "products", "nutriscore"), (4, "products", "marque")])
    conn.executemany("INSERT INTO userfield_values VALUES (?,?,?,?)",
                     [(1, 1, 1, "A"), (2, 4, 1, "Panzani")])
    conn.commit()
    conn.close()
    return str(path)


@pytest.fixture
def db(tmp_path):
    database = Database(str(tmp_path / "home_stock.db"))
    database.connect()
    with database.write() as conn:
        apply_migrations(conn)
    yield database
    database.close()


def test_dry_run_writes_nothing(db, grocy):
    report = import_catalog(db, grocy, apply=False)
    assert report.products == 4
    assert repo.list_products(db.read()) == []


def test_import_creates_products_locations_and_categories(db, grocy):
    report = import_catalog(db, grocy, apply=True)
    assert report.products == 4
    assert report.skipped == 1          # the disabled duplicate
    assert report.locations == 3
    assert report.categories == 2
    names = [p["name"] for p in repo.list_products(db.read())]
    assert names == ["Farine", "Lait", "Pâtes", "Œufs"]


def test_units_are_converted_with_their_factor(db, grocy):
    import_catalog(db, grocy, apply=True)
    products = {p["name"]: p for p in repo.list_products(db.read())}
    assert products["Pâtes"]["base_unit"] == "g"
    assert products["Pâtes"]["min_quantity"] == 200
    assert products["Farine"]["base_unit"] == "g"
    assert products["Farine"]["min_quantity"] == 1000      # 1 kg
    assert products["Lait"]["base_unit"] == "ml"
    assert products["Lait"]["min_quantity"] == 1000        # 100 cl
    assert products["Œufs"]["base_unit"] == "piece"
    assert products["Œufs"]["min_quantity"] == 6


def test_calories_follow_the_same_factor(db, grocy):
    import_catalog(db, grocy, apply=True)
    conn = db.read()
    rows = {
        row["name"]: row["kcal_per_base_unit"]
        for row in conn.execute(
            "SELECT p.name, a.kcal_per_base_unit FROM article a"
            " JOIN product p ON p.id = a.product_id")
    }
    assert rows["Pâtes"] == pytest.approx(3.5)     # per gram
    assert rows["Farine"] == pytest.approx(3.64)   # 3640 per kg
    assert rows["Lait"] == pytest.approx(0.46)     # 4.6 per cl
    assert rows["Œufs"] == pytest.approx(78.0)     # per egg


def test_every_product_gets_a_generic_article(db, grocy):
    import_catalog(db, grocy, apply=True)
    count = db.read().execute(
        "SELECT COUNT(*) AS n FROM article WHERE is_generic = 1").fetchone()
    assert count["n"] == 4


def test_custom_fields_land_on_the_article(db, grocy):
    import_catalog(db, grocy, apply=True)
    row = db.read().execute(
        "SELECT a.nutriscore, a.brand FROM article a JOIN product p ON p.id = a.product_id"
        " WHERE p.name = 'Pâtes'").fetchone()
    assert row["nutriscore"] == "A"
    assert row["brand"] == "Panzani"


def test_barcodes_and_prices_are_imported(db, grocy):
    report = import_catalog(db, grocy, apply=True)
    assert report.barcodes == 2
    article = repo.find_article_by_barcode(db.read(), "3038350201553")
    assert article is not None
    # 2 € for 500 g is 0.004 €/g.
    assert repo.latest_price(db.read(), article["id"]) == pytest.approx(0.004)


def test_days_after_opening_are_kept(db, grocy):
    import_catalog(db, grocy, apply=True)
    row = db.read().execute(
        "SELECT days_after_opening FROM product WHERE name = 'Lait'").fetchone()
    assert row["days_after_opening"] == 3


def test_running_twice_changes_nothing(db, grocy):
    import_catalog(db, grocy, apply=True)
    second = import_catalog(db, grocy, apply=True)
    assert second.products == 0
    assert len(repo.list_products(db.read())) == 4


def test_a_dosage_unit_as_stock_unit_is_an_anomaly(db, grocy):
    conn = sqlite3.connect(grocy)
    conn.execute("UPDATE products SET qu_id_stock = 14 WHERE id = 1")   # 'cs'
    conn.commit()
    conn.close()
    report = import_catalog(db, grocy, apply=False)
    assert report.ok is False
    assert any("cs" in anomaly for anomaly in report.anomalies)


def test_an_impossible_calorie_value_is_an_anomaly(db, grocy):
    conn = sqlite3.connect(grocy)
    # 50 kcal per gram: no food does that (fat tops out around 9).
    conn.execute("UPDATE products SET calories = 50 WHERE id = 1")
    conn.commit()
    conn.close()
    report = import_catalog(db, grocy, apply=False)
    assert report.ok is False
    assert any("Pâtes" in anomaly for anomaly in report.anomalies)
```

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `./scripts/test.sh tests/test_import_grocy.py -v`
Expected: FAIL — `ModuleNotFoundError: ... import_grocy`

- [ ] **Step 3: Implémenter**

`custom_components/home_stock/import_grocy.py` :

```python
"""One-way, replayable import of the Grocy catalogue.

Reads a read-only copy of grocy.db. Stock, history and recipes stay in Grocy: they
come over in lot 7. Every product and article keeps its Grocy id in external_ref,
so a second run changes nothing and lot 7 becomes a join instead of a name match —
name matching is what created 35 duplicates in April 2026.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Any

from .storage import repositories as repo
from .storage.database import Database

MASS_UNITS = {"g": 1.0, "kg": 1000.0}
VOLUME_UNITS = {"ml": 1.0, "cl": 10.0, "l": 1000.0}
CONTAINER_UNITS = {
    "Pièce", "Paquet", "Pot", "Bouteille", "Barquette", "Brique", "Boîte",
    "Sachet", "Lot",
}
DOSAGE_UNITS = {"cs", "cc"}
MAX_KCAL_PER_GRAM = 9.5   # pure fat is 9; above that the value is wrong


@dataclass
class ImportReport:
    """What was written, and what must be looked at by hand."""

    products: int = 0
    articles: int = 0
    barcodes: int = 0
    prices: int = 0
    categories: int = 0
    locations: int = 0
    skipped: int = 0
    anomalies: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.anomalies

    def as_dict(self) -> dict[str, Any]:
        return {
            "products": self.products, "articles": self.articles,
            "barcodes": self.barcodes, "prices": self.prices,
            "categories": self.categories, "locations": self.locations,
            "skipped": self.skipped, "anomalies": self.anomalies, "ok": self.ok,
        }


def _base_unit(unit_name: str) -> tuple[str, float] | None:
    if unit_name in MASS_UNITS:
        return "g", MASS_UNITS[unit_name]
    if unit_name in VOLUME_UNITS:
        return "ml", VOLUME_UNITS[unit_name]
    if unit_name in CONTAINER_UNITS:
        return "piece", 1.0
    return None


def _open_grocy(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def import_catalog(db: Database, grocy_path: str, *, apply: bool = False) -> ImportReport:
    """Copy the Grocy catalogue over. Without apply=True, nothing is written."""
    report = ImportReport()
    grocy = _open_grocy(grocy_path)
    try:
        units = {row["id"]: row["name"] for row in grocy.execute("SELECT * FROM quantity_units")}
        groups = {row["id"]: row["name"] for row in grocy.execute("SELECT * FROM product_groups")}
        fields = {
            row["id"]: row["name"]
            for row in grocy.execute("SELECT * FROM userfields WHERE entity = 'products'")
        }
        values: dict[int, dict[str, str]] = {}
        for row in grocy.execute("SELECT * FROM userfield_values"):
            name = fields.get(row["field_id"])
            if name:
                values.setdefault(row["object_id"], {})[name] = row["value"]

        with db.write() as conn:
            known = {
                row["external_ref"]
                for row in conn.execute(
                    "SELECT external_ref FROM product WHERE external_ref IS NOT NULL")
            }

            location_ids: dict[int, int] = {}
            for row in grocy.execute("SELECT * FROM locations"):
                existing = conn.execute(
                    "SELECT id FROM location WHERE name = ?", (row["name"],)).fetchone()
                if existing:
                    location_ids[row["id"]] = existing["id"]
                    continue
                report.locations += 1
                if apply:
                    location_ids[row["id"]] = repo.insert_location(
                        conn, name=row["name"],
                        kind="freezer" if row["is_freezer"] else "pantry",
                    )

            category_ids: dict[int, int] = {}
            for row in grocy.execute("SELECT * FROM product_groups"):
                existing = conn.execute(
                    "SELECT id FROM category WHERE name = ?", (row["name"],)).fetchone()
                if existing:
                    category_ids[row["id"]] = existing["id"]
                    continue
                report.categories += 1
                if apply:
                    category_ids[row["id"]] = repo.insert_category(conn, row["name"])

            article_ids: dict[int, int] = {}
            for row in grocy.execute("SELECT * FROM products ORDER BY name"):
                if not row["active"]:
                    report.skipped += 1
                    continue
                if str(row["id"]) in known:
                    continue
                unit_name = units.get(row["qu_id_stock"], "?")
                if unit_name in DOSAGE_UNITS:
                    report.anomalies.append(
                        f"{row['name']} : unité de stock « {unit_name} » est une unité"
                        " de dosage, pas une unité de stock"
                    )
                    continue
                mapped = _base_unit(unit_name)
                if mapped is None:
                    report.anomalies.append(
                        f"{row['name']} : unité de stock « {unit_name} » inconnue")
                    continue
                base_unit, factor = mapped

                kcal = None if row["calories"] is None else row["calories"] / factor
                if kcal is not None and base_unit == "g" and kcal > MAX_KCAL_PER_GRAM:
                    report.anomalies.append(
                        f"{row['name']} : {kcal:.1f} kcal/g est impossible")
                    continue
                if not row["name"]:
                    report.anomalies.append(f"produit Grocy {row['id']} sans nom")
                    continue

                report.products += 1
                report.articles += 1
                if not apply:
                    continue

                product_id = repo.insert_product(
                    conn,
                    name=row["name"],
                    base_unit=base_unit,
                    category_id=category_ids.get(row["product_group_id"]),
                    default_location_id=location_ids.get(row["location_id"]),
                    min_quantity=None if row["min_stock_amount"] is None
                    else row["min_stock_amount"] * factor,
                    days_after_opening=row["default_best_before_days_after_open"] or None,
                    reference_kcal=kcal,
                    external_ref=str(row["id"]),
                )
                custom = values.get(row["id"], {})
                article_ids[row["id"]] = repo.insert_article(
                    conn,
                    product_id=product_id,
                    is_generic=1,
                    kcal_per_base_unit=kcal,
                    brand=custom.get("marque"),
                    nutriscore=custom.get("nutriscore"),
                    nova=int(custom["nova"]) if custom.get("nova", "").isdigit() else None,
                    ecoscore=custom.get("ecoscore"),
                    allergens=custom.get("allergenes"),
                    external_ref=str(row["id"]),
                )

            for row in grocy.execute("SELECT * FROM product_barcodes"):
                article_id = article_ids.get(row["product_id"])
                if article_id is None:
                    continue
                report.barcodes += 1
                if not apply:
                    continue
                existing = conn.execute(
                    "SELECT 1 FROM barcode WHERE code = ?", (row["barcode"],)).fetchone()
                if existing:
                    report.anomalies.append(
                        f"code-barres {row['barcode']} déjà attribué")
                    continue
                repo.link_barcode(conn, row["barcode"], article_id)

                # last_price is per purchase unit: convert only when it is unambiguous.
                price_unit = _base_unit(units.get(row["qu_id"], "?"))
                if row["last_price"] and row["amount"] and price_unit:
                    per_base = row["last_price"] / (row["amount"] * price_unit[1])
                    repo.insert_price(
                        conn, article_id=article_id, observed_on="2026-08-18",
                        price_per_base_unit=per_base, source="import",
                    )
                    report.prices += 1
                elif row["last_price"]:
                    report.anomalies.append(
                        f"prix de {row['barcode']} non convertible (unité ou quantité"
                        " d'achat manquante)"
                    )

            if not apply:
                conn.rollback()
    finally:
        grocy.close()
    return report
```

Attention à la dernière ligne : en simulation, le `rollback()` explicite annule les
écritures faites par les emplacements et catégories déjà insérés dans la transaction.
Le `with db.write()` committerait sinon.

- [ ] **Step 4: Lancer, vérifier le succès**

Run: `./scripts/test.sh tests/test_import_grocy.py -v`
Expected: PASS (11 tests)

- [ ] **Step 5: Ajouter le service**

Dans `services.py`, à l'intérieur de `async_register_services` :

```python
    async def import_grocy_catalog(call: ServiceCall) -> ServiceResponse:
        entry = _entry(hass)
        path = hass.config.path(call.data["path"])
        report = await _run(hass, partial(
            import_catalog, entry.runtime_data.manager.db, path,
            apply=call.data["apply"],
        ))
        await entry.runtime_data.coordinator.async_request_refresh()
        return report.as_dict()

    hass.services.async_register(
        DOMAIN, "import_grocy_catalog", import_grocy_catalog,
        schema=vol.Schema({
            vol.Optional("path", default="grocy_import.db"): cv.string,
            vol.Optional("apply", default=False): cv.boolean,
        }),
        supports_response=SupportsResponse.ONLY,
    )
```

avec `from .import_grocy import import_catalog` en tête de fichier, et le bloc
correspondant dans `services.yaml` :

```yaml
import_grocy_catalog:
  name: Importer le catalogue Grocy
  description: >-
    Copie les produits, emplacements, groupes, codes-barres et calories depuis une
    copie de grocy.db placée dans le dossier de configuration. Simulation par défaut.
  fields:
    path:
      name: Fichier
      description: Chemin relatif au dossier de configuration.
      default: grocy_import.db
      selector: { text: }
    apply:
      name: Appliquer
      description: Sans cela, rien n'est écrit — seul le rapport est produit.
      default: false
      selector: { boolean: }
```

- [ ] **Step 6: Lancer toute la suite**

Run: `./scripts/test.sh -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add custom_components/home_stock tests/test_import_grocy.py
git commit -m "feat: import the Grocy catalogue, replayable and reported"
```

---

### Task 13: Déploiement réel et vue Lovelace

Cette tâche ne s'exécute pas dans Docker : elle touche l'instance HA de la maison.

**Files:**
- Modify: `/opt/nivuus/HomeAssistant/docker-compose.yml`
- Create: `/opt/nivuus/HomeAssistant/config/lovelace_garde_manger.yaml` (vue à coller dans un dashboard)
- Create: `docs/exploitation.md` dans le dépôt

**Interfaces:** aucune nouvelle — c'est la mise en service.

- [ ] **Step 1: Monter le composant dans le conteneur**

Ajouter au bloc `volumes:` du service `homeassistant`, à côté des montages existants
(`home_agent`, `ha_ai_learner`, `docker_marketplace`) :

```yaml
      - /opt/nivuus/HomeAssistant/data/meal/custom_components/home_stock:/config/custom_components/home_stock
```

Puis :

```bash
cd /opt/nivuus/HomeAssistant
docker compose up -d homeassistant
docker compose logs -f homeassistant | grep -i home_stock
```

Ne **pas** installer le composant par HACS : HACS copierait les fichiers dans
`config/custom_components/`, et HA chargerait la copie pendant qu'on édite le montage.

- [ ] **Step 2: Ajouter l'intégration**

Paramètres → Appareils et services → Ajouter une intégration → « Garde-manger ».
Vérifier ensuite que les cinq entités existent et sont à zéro :

```bash
docker compose exec homeassistant \
  python -c "print(open('/config/home_stock.db').read(1))" 2>/dev/null || true
ls -la /opt/nivuus/HomeAssistant/config/home_stock.db
```

- [ ] **Step 3: Importer le catalogue en simulation**

```bash
cp /opt/nivuus/Grocy/config/data/grocy.db /opt/nivuus/HomeAssistant/config/grocy_import.db
```

Outils de développement → Actions → `home_stock.import_grocy_catalog`, avec
`apply: false`. Lire le rapport : **`ok` doit être `true`**. S'il contient des
anomalies, les corriger dans Grocy (ou dans la table de correspondance des unités)
et relancer. Ne jamais appliquer un import dont le rapport n'est pas vide.

- [ ] **Step 4: Appliquer l'import**

Même action avec `apply: true`. Attendu sur la base réelle du 2026-08-18 :
299 produits, 299 articles génériques, 4 emplacements, 21 catégories, 39 codes-barres,
35 produits ignorés (les doublons désactivés). Contrôler que `sensor.home_stock_batches`
reste à 0 : le lot 0 n'importe pas le stock, seulement le catalogue.

```bash
rm /opt/nivuus/HomeAssistant/config/grocy_import.db
```

- [ ] **Step 5: Écrire la vue Lovelace**

`config/lovelace_garde_manger.yaml`, à coller dans un dashboard (mode YAML) :

```yaml
title: Garde-manger
cards:
  - type: entities
    title: État
    entities:
      - entity: sensor.home_stock_stock_value
      - entity: sensor.home_stock_batches
      - entity: binary_sensor.home_stock_expirations
      - entity: binary_sensor.home_stock_shortages
  - type: todo-list
    entity: todo.home_stock_expirations
  - type: markdown
    title: Ruptures
    content: >-
      {% set produits = state_attr('binary_sensor.home_stock_shortages', 'products') %}
      {% if produits %}{% for p in produits %}- {{ p }}
      {% endfor %}{% else %}Rien à racheter.{% endif %}
```

Les graphes kcal/jour et €/jour arrivent au lot 2 : les capteurs `total_increasing`
et les `utility_meter` journaliers n'existent pas encore.

- [ ] **Step 6: Vérifier de bout en bout, à la main**

Dans Outils de développement → Actions, avec un vrai produit du catalogue :

1. `home_stock.add_stock` — un lot de 500 g avec une date et un prix ;
2. vérifier `sensor.home_stock_batches` = 1 et la valeur du stock ;
3. `home_stock.consume` — 200 g ; vérifier qu'il reste 300 g via `home_stock.query_stock` ;
4. `home_stock.consume` — 1000 g ; vérifier que HA affiche « Stock insuffisant » et que
   rien n'a bougé ;
5. `home_stock.export_journal` — trois mouvements, dont deux consommations refusées
   n'apparaissent PAS.

- [ ] **Step 7: Écrire `docs/exploitation.md`**

Y consigner : la commande de montage, le fait que HACS et le montage s'excluent, la
procédure d'import (copie, simulation, application, suppression), l'emplacement de la
base (`config/home_stock.db`, emportée par les sauvegardes HA), et la commande de
tests (`./scripts/test.sh`).

- [ ] **Step 8: Commit**

```bash
git add docs/exploitation.md
git commit -m "docs: add operations notes for the home_stock deployment"
```

---

## Ce que le lot 0 ne fait pas

À dire explicitement pour que personne ne le cherche : pas de scan, pas d'appel à Open
Food Facts, pas d'interface, pas de capteur par jour, pas de recette, pas de liste de
courses, pas de piles. Le stock se manipule par les actions de Home Assistant et se lit
dans une vue Lovelace austère. C'est le lot 1 qui rend l'ensemble utilisable au
quotidien.

Le stock, l'historique et les recettes restent dans Grocy jusqu'au lot 7. Grocy
continue de tourner : rien de ce plan ne l'arrête ni ne l'écrit.
