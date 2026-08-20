# home_stock — Lot 2 : consommation et comptabilité par jour — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Déclarer ce qu'on mange en un ou deux appuis depuis le panneau, et lire ce que ça fait par jour, par semaine et par mois — en kilocalories, en nutriments et en euros.

**Architecture:** Le journal des mouvements, déjà append-only, gagne les huit macros et deux colonnes de parts ; tout se fige à l'écriture. Une journée alimentaire court de 4 h à 4 h, calculée par un module de domaine pur qui reçoit son fuseau au lieu d'aller le chercher. Les capteurs publient la journée courante, le panneau dessine les séries depuis SQLite — les statistiques natives de Home Assistant découpent à minuit et ne peuvent pas honorer la frontière de 4 h.

**Tech Stack:** Python 3.13 / Home Assistant 2026.8.2 / SQLite (WAL, écrivain unique) / `pytest-homeassistant-custom-component` — TypeScript / `lit` / rollup / vitest / playwright-core.

**Spec:** `docs/superpowers/specs/2026-08-20-home-stock-lot2-design.md`

## Global Constraints

Ces règles lient **toutes** les tâches. Elles sont recopiées telles quelles depuis la spec.

- **Nommage.** Code, schéma et identifiants Python **en anglais** ; textes affichés **en français**. Le front garde ses identifiants et ses commentaires **en français**, comme aux lots 0 et 1.
- **`FOOD_DAY_START_HOUR = 4`.** Une journée alimentaire court de 4 h locales à 4 h locales.
- **Parts.** Bornes validées aux deux surfaces : `1 ≤ parts_total ≤ 24` et `0 ≤ parts_mine ≤ parts_total`. Écrites **uniquement** pour `reason == "consumption"`, `NULL` partout ailleurs. `NULL` vaut 1/1.
- **Les euros ne sont jamais divisés par les parts.** Seuls les kilocalories et les huit macros portent le facteur personnel.
- **`NULL` reste distinct de `0.0`.** Un article sans table nutritionnelle produit `NULL`, jamais `0.0`.
- **Jamais d'arrondi** à l'écriture d'un mouvement.
- **Aucune des deux surfaces n'a le droit d'être la plus faible** : ce que le websocket refuse, le service le refuse aussi, et réciproquement.
- **Bornes de portion** : `]0 ; 5000]`, et jamais supérieure au poids net de l'article quand il est connu. Uniquement pour un produit suivi en `g` ou en `ml`.
- **Capteurs éteints par défaut** : `carbohydrates_today`, `added_sugars_today`, `fat_today`, `saturated_fat_today`, `fiber_today`. Allumés : `kcal_today`, `proteins_today`, `sugars_today`, `salt_today`, `cost_today`, `cost_waste_total`.
- **Rien ne touche l'instance vivante.** Pas de `docker compose restart`, pas de rechargement de l'intégration, pas de lecture du jeton dans `.mcp.json`, aucune écriture dans `/opt/nivuus/HomeAssistant/config/home_stock.db`. La vérification s'arrête à ce qui s'observe sans déranger la maison. Règle posée au lot 1 après un redémarrage non demandé du Home Assistant du foyer.
- **`npm run build` est interdit** avant la dernière tâche. `custom_components/home_stock/` est **bind-monté** dans le conteneur Home Assistant (`docker-compose.yml` ligne 20) : le bundle construit est servi tel quel. Une seule construction, à la toute fin, quand tout le reste est vert.
- **Commandes de test.** Python : `./scripts/test.sh` depuis la racine du dépôt (image Docker alignée sur HA 2026.8.2 — le Python de l'hôte ne peut pas charger le plugin). Front : `npm test` puis `node outils/verifier-rendu.mjs`, **depuis `frontend/`**.
- **Grocy est en lecture seule.** Aucune écriture, jamais.

---

## Structure des fichiers

**Python — créés**

| Fichier | Responsabilité |
|---|---|
| `custom_components/home_stock/domain/foodday.py` | Frontières de la journée alimentaire et seaux de série. Pur : pas de `hass`, pas de SQLite. |
| `custom_components/home_stock/storage/migrations/m003_consumption.py` | Colonnes du lot 2 et reprise des portions depuis `off_raw`. |
| `custom_components/home_stock/event.py` | `event.home_stock_expiration`. |
| `blueprints/automation/home_stock/dlc_bleuenn.yaml` | Blueprint livré, jamais installé par le composant. |

**Python — modifiés**

| Fichier | Ce qui change |
|---|---|
| `const.py` | `MACRO_COLUMNS`, `FOOD_DAY_START_HOUR`, `MAX_PARTS` |
| `domain/nutrition.py` | `movement_values` rend les neuf nutriments |
| `domain/stock.py` | `BatchView`/`Allocation` transportent les macros |
| `off/mapping.py` | `plausible_serving`, `serving_from_raw` |
| `off/ingest.py` | `serving_quantity` à l'ingestion |
| `storage/migrations/__init__.py` | `m003` dans `MIGRATIONS` |
| `storage/repositories.py` | Macros et parts à l'insertion, agrégats du jour, séries, portion apprise, étape d'annonce |
| `application.py` | Parts, clé sur `consume_batch`, `summary()` scindé, totaux du jour |
| `coordinator.py` | Fuseau, journée alimentaire, rendez-vous de 4 h |
| `sensor.py` | Onze capteurs |
| `websocket_api.py` | `stock/consume`, `journal/day`, `journal/series`, `product/get` étendu |
| `services.py`, `services.yaml` | `consume` gagne les parts et `batch_id` |
| `validators.py` | `parts_count` |
| `translations/fr.json` | Noms français des nouvelles entités |
| `docs/exploitation.md` | Journée de 4 h, rupture des compteurs, import du blueprint |

**Front — créés**

| Fichier | Responsabilité |
|---|---|
| `frontend/src/portion.ts` | Les raccourcis de quantité. Pur, comme `dlc.ts`. |
| `frontend/src/ecrans/consommation.ts` | L'écran « manger ». |
| `frontend/src/ecrans/journal.ts` | La journée et les barres. |

**Front — modifiés**

| Fichier | Ce qui change |
|---|---|
| `frontend/src/file-attente.ts` | Passage de relais par clé (dette du lot 1) |
| `frontend/src/panneau.ts` | Deux écrans de plus dans `Ecran` et dans la navigation |
| `frontend/outils/verifier-rendu.mjs` | Deux scénarios de plus |

---

## Task 1: Migration `m003` et reprise des portions

**Files:**
- Create: `custom_components/home_stock/storage/migrations/m003_consumption.py`
- Modify: `custom_components/home_stock/storage/migrations/__init__.py`
- Modify: `custom_components/home_stock/off/mapping.py`
- Modify: `custom_components/home_stock/const.py`
- Test: `tests/storage/test_migrations.py`, `tests/off/test_mapping.py`

**Interfaces:**
- Consomme : `_number(value)` de `off/mapping.py` ; le hook `apply(conn)` du lanceur de migrations, déjà en place depuis `m002`.
- Produit :
  - `const.MACRO_COLUMNS: tuple[str, ...]` — les huit macros, dans l'ordre du schéma.
  - `const.MAX_SERVING: float = 5000.0`
  - `off.mapping.plausible_serving(value: Any, *, base_unit: str, net_quantity: float | None) -> float | None`
  - `off.mapping.serving_from_raw(raw: str | None, *, base_unit: str, net_quantity: float | None) -> float | None`
  - Colonnes : `movement.parts_total`, `movement.parts_mine`, `movement.{proteins,carbohydrates,sugars,added_sugars,fat,saturated_fat,fiber,salt}`, `article.serving_quantity`, `batch.expiry_announced_stage`.
  - `off.ingest.ARTICLE_OFF_SCHEMA` gagne la clé `serving_quantity`.

- [ ] **Step 1: Écrire les tests de `plausible_serving`**

Dans `tests/off/test_mapping.py`, à la fin du fichier :

```python
from custom_components.home_stock.off.mapping import plausible_serving, serving_from_raw


def test_plausible_serving_accepts_a_number_and_a_numeric_string():
    assert plausible_serving(30, base_unit="g", net_quantity=500) == 30.0
    assert plausible_serving("30", base_unit="g", net_quantity=500) == 30.0
    assert plausible_serving("12,5", base_unit="ml", net_quantity=1000) == 12.5


def test_plausible_serving_refuses_a_piece_product():
    # Une portion d'un produit suivi à la pièce vaut une pièce : la colonne
    # n'a rien à dire, et un chiffre en grammes y serait un piège.
    assert plausible_serving(30, base_unit="piece", net_quantity=None) is None


def test_plausible_serving_refuses_zero_and_the_absurd():
    assert plausible_serving(0, base_unit="g", net_quantity=500) is None
    assert plausible_serving(-5, base_unit="g", net_quantity=500) is None
    assert plausible_serving(5000.1, base_unit="g", net_quantity=None) is None
    assert plausible_serving(5000, base_unit="g", net_quantity=None) == 5000.0


def test_plausible_serving_refuses_a_serving_bigger_than_the_pack():
    assert plausible_serving(300, base_unit="g", net_quantity=250) is None
    # Exactement le paquet reste plausible : une conserve individuelle.
    assert plausible_serving(250, base_unit="g", net_quantity=250) == 250.0


def test_plausible_serving_refuses_malformed_text():
    for value in ("", "1,", "trente", None, True, [30]):
        assert plausible_serving(value, base_unit="g", net_quantity=None) is None


def test_serving_from_raw_reads_the_stored_record():
    raw = '{"serving_quantity": "30", "product_name": "Yaourt"}'
    assert serving_from_raw(raw, base_unit="g", net_quantity=125) == 30.0


def test_serving_from_raw_survives_anything_unusable():
    for raw in (None, "", "{tronqu", "[1, 2]", '"une chaine"', "{}"):
        assert serving_from_raw(raw, base_unit="g", net_quantity=None) is None
```

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/off/test_mapping.py -q`
Expected: FAIL — `ImportError: cannot import name 'plausible_serving'`

- [ ] **Step 3: Écrire `plausible_serving` et `serving_from_raw`**

Dans `custom_components/home_stock/const.py`, à côté des autres constantes :

```python
# Les huit macros de `article`, telles que le schéma les nomme. `kcal` n'y est
# pas : elle s'appelle `kcal_per_base_unit` sur `article` et `kcal` sur
# `movement`, et elle est la seule à avoir une roue de secours au niveau
# produit (`product.reference_kcal`).
MACRO_COLUMNS: Final = (
    "proteins", "carbohydrates", "sugars", "added_sugars",
    "fat", "saturated_fat", "fiber", "salt",
)

# Une portion au-delà de cette valeur n'est pas une portion : c'est une erreur
# de saisie dans une base collaborative (une palette annoncée en grammes).
MAX_SERVING: Final = 5000.0
```

Dans `custom_components/home_stock/off/mapping.py`, ajouter `json` aux imports, `MAX_SERVING` à l'import depuis `..const`, puis à la fin du fichier :

```python
def plausible_serving(value: Any, *, base_unit: str,
                      net_quantity: float | None) -> float | None:
    """La portion d'Open Food Facts, ou rien.

    Trois refus, dans cet ordre : un produit suivi à la pièce (une portion y
    vaut une pièce, un nombre de grammes n'y veut rien dire), une valeur
    illisible ou hors de `]0 ; MAX_SERVING]`, et une portion plus grosse que
    le paquet lui-même — Open Food Facts est collaboratif, et « 300 g » sur
    un pot de 250 g est une faute de frappe, pas une portion.
    """
    if base_unit not in ("g", "ml"):
        return None
    number = _number(value)
    if number is None or not 0 < number <= MAX_SERVING:
        return None
    if net_quantity is not None and number > net_quantity:
        return None
    return number


def serving_from_raw(raw: str | None, *, base_unit: str,
                     net_quantity: float | None) -> float | None:
    """La portion lue dans la fiche brute déjà stockée (`article.off_raw`).

    Tout ce qui n'est pas un objet JSON exploitable rend `None` sans lever :
    cette lecture sert un confort d'affichage, jamais une donnée dont dépend
    le stock, et elle tourne à l'intérieur d'une migration qu'un `off_raw`
    tronqué ne doit pas faire échouer.
    """
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    return plausible_serving(payload.get("serving_quantity"),
                             base_unit=base_unit, net_quantity=net_quantity)
```

- [ ] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/off/test_mapping.py -q`
Expected: PASS

- [ ] **Step 5: Écrire les tests de la migration**

Dans `tests/storage/test_migrations.py`, à la fin. Lire d'abord le haut du fichier pour reprendre les helpers déjà présents (ouverture d'une base, application des migrations) plutôt que d'en écrire d'autres.

```python
def test_m003_adds_the_journal_columns(tmp_path):
    conn = _migrated(tmp_path)                       # helper déjà présent dans ce fichier
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(movement)")}
    assert {"parts_total", "parts_mine", "proteins", "carbohydrates", "sugars",
            "added_sugars", "fat", "saturated_fat", "fiber", "salt"} <= columns
    assert "serving_quantity" in {r["name"] for r in conn.execute("PRAGMA table_info(article)")}
    assert "expiry_announced_stage" in {r["name"] for r in conn.execute("PRAGMA table_info(batch)")}


def test_m003_keeps_the_movement_triggers(tmp_path):
    """m003 ne touche pas aux triggers — mais un mouvement doit rester
    inmodifiable après elle, sinon la migration a cassé l'append-only sans
    que rien d'autre ne le dise."""
    conn = _migrated(tmp_path)
    _seed_one_movement(conn)                          # helper à ajouter, voir Step 7
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE movement SET quantity = 999 WHERE id = 1")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM movement WHERE id = 1")


def test_m003_backfills_serving_quantity_from_off_raw(tmp_path):
    conn = _migrated_to(tmp_path, version=2)          # helper à ajouter, voir Step 7
    conn.execute("INSERT INTO location (name, kind) VALUES ('Placard', 'cupboard')")
    conn.execute("INSERT INTO product (name, base_unit) VALUES ('Yaourt', 'g')")
    conn.execute("INSERT INTO product (name, base_unit) VALUES ('Pomme', 'piece')")
    conn.execute(
        "INSERT INTO article (product_id, net_quantity, off_raw) VALUES (1, 125, ?)",
        ('{"serving_quantity": "100"}',))
    conn.execute(
        "INSERT INTO article (product_id, net_quantity, off_raw) VALUES (2, 150, ?)",
        ('{"serving_quantity": "100"}',))
    conn.execute(
        "INSERT INTO article (product_id, net_quantity, off_raw) VALUES (1, 125, ?)",
        ('{"serving_quantity": "500"}',))     # plus gros que le paquet : refusé
    conn.execute("INSERT INTO article (product_id, off_raw) VALUES (1, '{tronqu')")
    conn.commit()

    apply_migrations(conn)

    servings = [row["serving_quantity"] for row in
                conn.execute("SELECT serving_quantity FROM article ORDER BY id")]
    assert servings == [100.0, None, None, None]


def test_m003_is_replayable(tmp_path):
    """Rejouer la migration sur une base déjà migrée ne doit rien changer —
    et surtout ne pas écraser une portion corrigée à la main."""
    conn = _migrated(tmp_path)
    conn.execute("INSERT INTO product (name, base_unit) VALUES ('Yaourt', 'g')")
    conn.execute(
        "INSERT INTO article (product_id, net_quantity, off_raw, serving_quantity)"
        " VALUES (1, 125, ?, 60)", ('{"serving_quantity": "100"}',))
    conn.commit()

    apply_migrations(conn)

    assert conn.execute("SELECT serving_quantity FROM article").fetchone()[0] == 60.0
```

- [ ] **Step 6: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/storage/test_migrations.py -q`
Expected: FAIL — les colonnes n'existent pas.

- [ ] **Step 7: Écrire la migration**

Créer `custom_components/home_stock/storage/migrations/m003_consumption.py` :

```python
"""Lot 2: the journal freezes nine nutrients and who ate, articles learn their
serving, batches remember what has already been announced. Mirrors section 6 of
the lot 2 design.

No trigger dance here, unlike m002: nothing in this migration UPDATEs the
movement table. Every column it adds is nullable, so the rows already written
keep their meaning without being rewritten — NULL parts read as 1/1, NULL
nutrients read as unknown, which is exactly what the history of lots 0 and 1
(and of the Grocy import) actually is.
"""
from __future__ import annotations

import sqlite3

from ...off.mapping import serving_from_raw

VERSION = 3

SQL = """
ALTER TABLE movement ADD COLUMN parts_total INTEGER;
ALTER TABLE movement ADD COLUMN parts_mine INTEGER;

ALTER TABLE movement ADD COLUMN proteins REAL;
ALTER TABLE movement ADD COLUMN carbohydrates REAL;
ALTER TABLE movement ADD COLUMN sugars REAL;
ALTER TABLE movement ADD COLUMN added_sugars REAL;
ALTER TABLE movement ADD COLUMN fat REAL;
ALTER TABLE movement ADD COLUMN saturated_fat REAL;
ALTER TABLE movement ADD COLUMN fiber REAL;
ALTER TABLE movement ADD COLUMN salt REAL;

ALTER TABLE article ADD COLUMN serving_quantity REAL;
ALTER TABLE batch ADD COLUMN expiry_announced_stage TEXT;

-- The daily aggregates all filter on a reason and a date range; the lot 0
-- index (occurred_at alone) leaves the reason to a scan.
CREATE INDEX IF NOT EXISTS idx_movement_reason_day ON movement(reason, occurred_at);
"""


def apply(conn: sqlite3.Connection) -> None:
    """Fill `article.serving_quantity` from the OFF records already stored.

    The record is already in `article.off_raw` (lot 1 stores it): asking the
    network again for something sitting in our own database would be absurd.

    Replayable by construction: only an article whose serving is still NULL is
    touched, so a hand-corrected serving is never overwritten — same discipline
    as m002's aisle backfill.
    """
    rows = conn.execute(
        "SELECT a.id, a.off_raw, a.net_quantity, p.base_unit"
        " FROM article a JOIN product p ON p.id = a.product_id"
        " WHERE a.off_raw IS NOT NULL AND a.serving_quantity IS NULL"
    ).fetchall()
    for row in rows:
        serving = serving_from_raw(row["off_raw"], base_unit=row["base_unit"],
                                   net_quantity=row["net_quantity"])
        if serving is not None:
            conn.execute("UPDATE article SET serving_quantity = ? WHERE id = ?",
                         (serving, row["id"]))
```

Dans `custom_components/home_stock/storage/migrations/__init__.py` :

```python
from . import m001_initial, m002_scan, m003_consumption

MIGRATIONS = (m001_initial, m002_scan, m003_consumption)
```

Ajouter dans `tests/storage/test_migrations.py` les deux helpers utilisés ci-dessus, s'ils n'existent pas déjà sous un autre nom :

```python
def _migrated_to(tmp_path, *, version: int):
    """Une base arrêtée à une version donnée, pour observer ce que la
    suivante fait d'un contenu déjà présent."""
    conn = _open(tmp_path)                    # helper d'ouverture déjà présent
    for migration in MIGRATIONS:
        if migration.VERSION > version:
            break
        conn.executescript(migration.SQL)
        hook = getattr(migration, "apply", None)
        if hook is not None:
            hook(conn)
    conn.execute("DELETE FROM schema_version")
    conn.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
    return conn


def _seed_one_movement(conn) -> None:
    conn.execute("INSERT INTO location (name, kind) VALUES ('Placard', 'cupboard')")
    conn.execute("INSERT INTO product (name, base_unit) VALUES ('Yaourt', 'g')")
    conn.execute("INSERT INTO article (product_id) VALUES (1)")
    conn.execute(
        "INSERT INTO movement (occurred_at, product_id, article_id, quantity,"
        " reason, base_unit) VALUES ('2026-08-20T10:00:00', 1, 1, -125,"
        " 'consumption', 'g')")
    conn.commit()
```

- [ ] **Step 8: Remplir `serving_quantity` à l'ingestion**

La migration ne sert que les articles **déjà** enrichis. Un article scanné
demain doit obtenir sa portion sans attendre une migration qui ne repassera
jamais — c'est la moitié du § 10 de la spec, et l'oublier laisserait la colonne
vide pour toujours sur une base neuve.

Ajouter à `tests/off/test_ingest.py` :

```python
def test_build_article_values_reads_the_serving():
    ingest = build_article_values(
        {"product_name": "Yaourt", "product_quantity": "125",
         "product_quantity_unit": "g", "serving_quantity": "100"},
        "food", "g", synced_at="2026-08-20T10:00:00")
    assert ingest.values["serving_quantity"] == 100.0


def test_build_article_values_drops_an_implausible_serving():
    ingest = build_article_values(
        {"product_name": "Yaourt", "product_quantity": "125",
         "product_quantity_unit": "g", "serving_quantity": "500"},
        "food", "g", synced_at="2026-08-20T10:00:00")
    assert "serving_quantity" not in ingest.values


def test_a_piece_product_never_gets_a_serving():
    ingest = build_article_values(
        {"product_name": "Pomme", "serving_quantity": "150"},
        "food", "piece", synced_at="2026-08-20T10:00:00")
    assert "serving_quantity" not in ingest.values
```

Puis, dans `off/ingest.py` :

- ajouter `"serving_quantity": _NON_NEGATIVE_FLOAT` a `ARTICLE_OFF_SCHEMA` — la
  colonne devient du meme coup corrigeable a la main par `article/update`, qui
  partage ce dictionnaire, ce qui est exactement ce qu'on veut le jour ou une
  fiche annonce une portion absurde ;
- dans `build_article_values`, apres le calcul de `per_base` :

```python
    # La portion vient de la MEME fonction que le remplissage retroactif de
    # m003 : deux copies de ces bornes divergeraient, et la divergence ne se
    # verrait nulle part.
    values["serving_quantity"] = plausible_serving(
        product.get("serving_quantity"), base_unit=base_unit,
        net_quantity=mapped.net_quantity)
```

Le filtre `values = {... if value is not None}` deja present juste apres retire
la cle quand la portion est refusee : rien a ecrire de plus.

- [ ] **Step 9: Lancer toute la suite de stockage et d'ingestion**

Run: `./scripts/test.sh tests/storage tests/off -q`
Expected: PASS

- [ ] **Step 10: Vérifier que le test a des dents (mutation)**

Retirer temporairement la ligne `if net_quantity is not None and number > net_quantity:` (et son `return None`) de `plausible_serving`, relancer `./scripts/test.sh tests/off tests/storage/test_migrations.py -q` : **trois** tests doivent tomber — `test_plausible_serving_refuses_a_serving_bigger_than_the_pack`, `test_m003_backfills_serving_quantity_from_off_raw` et `test_build_article_values_drops_an_implausible_serving`. Remettre la ligne.

- [ ] **Step 11: Commit**

```bash
git add custom_components/home_stock/storage/migrations/ custom_components/home_stock/off/ tests/
git commit -m "feat: m003 freezes room for nutrients, parts and servings"
```

---

## Task 2: La journée alimentaire

**Files:**
- Create: `custom_components/home_stock/domain/foodday.py`
- Modify: `custom_components/home_stock/const.py`
- Test: `tests/domain/test_foodday.py`

**Interfaces:**
- Consomme : `const.FOOD_DAY_START_HOUR`.
- Produit :
  - `food_day_bounds(moment: datetime, tz: ZoneInfo) -> tuple[str, str]` — bornes ISO **UTC naïf**, `[début, fin[`.
  - `food_day_of(moment: datetime, tz: ZoneInfo) -> date`
  - `bounds_of_food_day(day: date, tz: ZoneInfo) -> tuple[str, str]`
  - `bucket_bounds(granularity: str, count: int, now: datetime, tz: ZoneInfo) -> list[Bucket]` avec `Bucket = namedtuple("Bucket", "label start end")`, `label` étant la date ISO du premier jour du seau.
  - `GRANULARITIES: tuple[str, ...] = ("day", "week", "month")`

**Pourquoi ce module est pur.** `application.py` ne connaît pas `hass`. Le fuseau lui est passé en argument, jamais lu depuis Home Assistant ici — c'est ce qui rend les deux changements d'heure testables sans démarrer quoi que ce soit.

- [ ] **Step 1: Écrire les tests**

Créer `tests/domain/test_foodday.py` :

```python
"""La journée alimentaire court de 4 h à 4 h, heure locale.

`occurred_at` est stocké en UTC naïf (décision du lot 0) : toutes les bornes
rendues par ce module sont donc en UTC naïf elles aussi, pour que la
comparaison SQL reste une comparaison de chaînes ISO.
"""
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest

from custom_components.home_stock.domain.foodday import (
    bucket_bounds, bounds_of_food_day, food_day_bounds, food_day_of,
)

PARIS = ZoneInfo("Europe/Paris")


def _paris(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=PARIS)


def test_a_meal_at_three_in_the_morning_belongs_to_the_day_before():
    assert food_day_of(_paris("2026-08-20T03:30:00"), PARIS) == date(2026, 8, 19)


def test_a_meal_at_four_starts_the_new_day():
    assert food_day_of(_paris("2026-08-20T04:00:00"), PARIS) == date(2026, 8, 20)
    assert food_day_of(_paris("2026-08-20T03:59:59"), PARIS) == date(2026, 8, 19)


def test_bounds_are_utc_naive_iso():
    start, end = food_day_bounds(_paris("2026-08-20T12:00:00"), PARIS)
    # Été : Paris est à UTC+2, donc 4 h locales valent 2 h UTC.
    assert start == "2026-08-20T02:00:00"
    assert end == "2026-08-21T02:00:00"


def test_bounds_in_winter_shift_with_the_offset():
    start, end = food_day_bounds(_paris("2026-01-15T12:00:00"), PARIS)
    assert start == "2026-01-15T03:00:00"
    assert end == "2026-01-16T03:00:00"


def test_the_spring_forward_day_is_twenty_three_hours_long():
    """29 mars 2026 : Paris passe de 02:00 à 03:00. 4 h existe une seule fois
    ce jour-là, mais la journée alimentaire ne dure que 23 heures."""
    start, end = bounds_of_food_day(date(2026, 3, 29), PARIS)
    assert start == "2026-03-29T03:00:00"    # 4 h locales = UTC+1 ce matin-là
    assert end == "2026-03-30T02:00:00"      # 4 h locales = UTC+2 le lendemain
    duration = datetime.fromisoformat(end) - datetime.fromisoformat(start)
    assert duration.total_seconds() == 23 * 3600


def test_the_autumn_day_is_twenty_five_hours_long():
    """25 octobre 2026 : Paris repasse de 03:00 à 02:00."""
    start, end = bounds_of_food_day(date(2026, 10, 25), PARIS)
    assert start == "2026-10-25T02:00:00"
    assert end == "2026-10-26T03:00:00"
    duration = datetime.fromisoformat(end) - datetime.fromisoformat(start)
    assert duration.total_seconds() == 25 * 3600


def test_a_movement_stored_in_utc_lands_in_the_right_day_across_the_change():
    """Le vrai piège : un repas à 03:30 locales le lendemain du changement.
    Stocké en UTC naïf, il doit tomber dans la journée de la veille."""
    stored = "2026-10-26T02:30:00"        # 03:30 à Paris, UTC+1 ce jour-là
    start, end = bounds_of_food_day(date(2026, 10, 25), PARIS)
    assert start <= stored < end


def test_buckets_by_day_are_contiguous_and_ordered():
    now = _paris("2026-08-20T12:00:00")
    buckets = bucket_bounds("day", 3, now, PARIS)
    assert [b.label for b in buckets] == ["2026-08-18", "2026-08-19", "2026-08-20"]
    assert buckets[0].end == buckets[1].start
    assert buckets[1].end == buckets[2].start


def test_buckets_by_week_start_on_monday():
    now = _paris("2026-08-20T12:00:00")           # un jeudi
    buckets = bucket_bounds("week", 2, now, PARIS)
    assert [b.label for b in buckets] == ["2026-08-10", "2026-08-17"]


def test_buckets_by_month_start_on_the_first():
    now = _paris("2026-08-20T12:00:00")
    buckets = bucket_bounds("month", 3, now, PARIS)
    assert [b.label for b in buckets] == ["2026-06-01", "2026-07-01", "2026-08-01"]


def test_a_month_bucket_starts_at_four_in_the_morning_too():
    buckets = bucket_bounds("month", 1, _paris("2026-08-20T12:00:00"), PARIS)
    assert buckets[0].start == "2026-08-01T02:00:00"


def test_an_unknown_granularity_is_refused():
    with pytest.raises(ValueError):
        bucket_bounds("fortnight", 3, _paris("2026-08-20T12:00:00"), PARIS)


def test_a_count_below_one_is_refused():
    with pytest.raises(ValueError):
        bucket_bounds("day", 0, _paris("2026-08-20T12:00:00"), PARIS)


def test_an_aware_utc_moment_is_accepted_as_well():
    """Le coordinateur passe `dt_util.utcnow()`, qui porte UTC."""
    assert food_day_of(datetime(2026, 8, 20, 1, 0, tzinfo=UTC), PARIS) == date(2026, 8, 19)
```

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `./scripts/test.sh tests/domain/test_foodday.py -q`
Expected: FAIL — `ModuleNotFoundError: custom_components.home_stock.domain.foodday`

- [ ] **Step 3: Écrire le module**

Dans `const.py` :

```python
# A food day runs from 04:00 local to 04:00 local: what you eat at one in the
# morning belongs to the evening you are still finishing, not to the calendar
# day that just started.
FOOD_DAY_START_HOUR: Final = 4
```

Créer `custom_components/home_stock/domain/foodday.py` :

```python
"""Where a food day starts, and how a series is bucketed.

Pure: no hass, no SQLite. The timezone is passed in, never looked up here —
that is what makes both daylight-saving changes testable without starting
anything.

Every bound this module returns is a **naive UTC ISO string**, because that is
what `movement.occurred_at` holds (lot 0). Comparing two ISO strings in SQLite
is then exact, and needs no timezone database on SQLite's side — which is just
as well, since SQLite has none.
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import NamedTuple
from zoneinfo import ZoneInfo

from ..const import FOOD_DAY_START_HOUR

GRANULARITIES = ("day", "week", "month")


class Bucket(NamedTuple):
    """One bar of a series: its label, and the half-open range it covers."""

    label: str      # ISO date of the bucket's first food day
    start: str      # naive UTC ISO, inclusive
    end: str        # naive UTC ISO, exclusive


def _to_naive_utc(moment: datetime) -> str:
    return moment.astimezone(UTC).replace(tzinfo=None, microsecond=0).isoformat()


def _start_of(day: date, tz: ZoneInfo) -> datetime:
    """04:00 local on that date. Neither ambiguous nor missing in any zone
    that shifts at 02:00 or 03:00, which is every European one; elsewhere
    `fold=0` picks the first occurrence, deterministically."""
    return datetime(day.year, day.month, day.day, FOOD_DAY_START_HOUR, tzinfo=tz)


def food_day_of(moment: datetime, tz: ZoneInfo) -> date:
    """The date this moment is booked against."""
    local = moment.astimezone(tz)
    if local.hour < FOOD_DAY_START_HOUR:
        return (local - timedelta(days=1)).date()
    return local.date()


def bounds_of_food_day(day: date, tz: ZoneInfo) -> tuple[str, str]:
    """[start, end[ of one food day, in naive UTC ISO.

    The two bounds are computed from two different local dates, each with its
    own UTC offset: that is precisely why a spring day comes out 23 hours long
    and an autumn one 25, instead of a hard-coded 24 that would leak an hour
    of meals into the neighbouring day twice a year.
    """
    return (_to_naive_utc(_start_of(day, tz)),
            _to_naive_utc(_start_of(day + timedelta(days=1), tz)))


def food_day_bounds(moment: datetime, tz: ZoneInfo) -> tuple[str, str]:
    """[start, end[ of the food day containing `moment`."""
    return bounds_of_food_day(food_day_of(moment, tz), tz)


def _first_day_of_bucket(day: date, granularity: str) -> date:
    if granularity == "day":
        return day
    if granularity == "week":
        return day - timedelta(days=day.weekday())
    return day.replace(day=1)


def _previous_bucket(day: date, granularity: str) -> date:
    if granularity == "day":
        return day - timedelta(days=1)
    if granularity == "week":
        return day - timedelta(days=7)
    return (day - timedelta(days=1)).replace(day=1)


def _next_bucket(day: date, granularity: str) -> date:
    if granularity == "day":
        return day + timedelta(days=1)
    if granularity == "week":
        return day + timedelta(days=7)
    # Day 28 exists in every month, so +4 days always lands in the next one.
    return (day.replace(day=28) + timedelta(days=4)).replace(day=1)


def bucket_bounds(granularity: str, count: int, now: datetime,
                  tz: ZoneInfo) -> list[Bucket]:
    """The `count` most recent buckets, oldest first, current one last."""
    if granularity not in GRANULARITIES:
        raise ValueError(f"unknown granularity {granularity!r}")
    if count < 1:
        raise ValueError(f"count must be at least 1, got {count}")

    first = _first_day_of_bucket(food_day_of(now, tz), granularity)
    starts = [first]
    for _ in range(count - 1):
        starts.append(_previous_bucket(starts[-1], granularity))
    starts.reverse()

    return [
        Bucket(label=start.isoformat(),
               start=_to_naive_utc(_start_of(start, tz)),
               end=_to_naive_utc(_start_of(_next_bucket(start, granularity), tz)))
        for start in starts
    ]
```

- [ ] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `./scripts/test.sh tests/domain/test_foodday.py -q`
Expected: PASS

- [ ] **Step 5: Vérifier que les tests ont des dents (mutation)**

Remplacer dans `bounds_of_food_day` le second appel par `_to_naive_utc(_start_of(day, tz)) + timedelta(hours=24)` — c'est-à-dire coder 24 h en dur. Le faire proprement :

```python
    start = _start_of(day, tz)
    return (_to_naive_utc(start), _to_naive_utc(start + timedelta(hours=24)))
```

Relancer `./scripts/test.sh tests/domain/test_foodday.py -q` : `test_the_spring_forward_day_is_twenty_three_hours_long` **et** `test_the_autumn_day_is_twenty_five_hours_long` doivent tomber. Si un seul tombe, le second test ne couvre pas ce qu'il prétend. Remettre le code correct.

- [ ] **Step 6: Commit**

```bash
git add custom_components/home_stock/domain/foodday.py custom_components/home_stock/const.py tests/domain/test_foodday.py
git commit -m "feat: a food day runs from 04:00 to 04:00, daylight saving included"
```

---

## Task 3: Les neuf nutriments dans le domaine

**Files:**
- Modify: `custom_components/home_stock/domain/nutrition.py`
- Modify: `custom_components/home_stock/domain/stock.py`
- Test: `tests/domain/test_nutrition.py`, `tests/domain/test_stock.py`

**Interfaces:**
- Consomme : `const.MACRO_COLUMNS` (tâche 1).
- Produit :
  - `MovementValues(kcal: float | None, cost: float | None, macros: Mapping[str, float | None])`
  - `movement_values(quantity, kcal_per_base_unit, price_per_base_unit, macro_rates=None) -> MovementValues`
  - `BatchView(..., macros: Mapping[str, float | None] = {})` et `Allocation(..., macros: Mapping[str, float | None] = {})`

**Pourquoi un dictionnaire et non huit champs.** Huit champs de plus sur deux dataclasses gelées, plus huit arguments sur `movement_values`, rendraient chaque appel illisible et chaque test existant à réécrire. Un `Mapping` avec une valeur par défaut vide laisse les constructions déjà écrites valides, et `MACRO_COLUMNS` reste l'unique définition de la liste.

- [ ] **Step 1: Écrire les tests de `movement_values`**

Ajouter à `tests/domain/test_nutrition.py` :

```python
from custom_components.home_stock.const import MACRO_COLUMNS
from custom_components.home_stock.domain.nutrition import movement_values


def test_macros_scale_with_the_quantity():
    values = movement_values(
        200.0, 1.2, 0.004,
        macro_rates={"proteins": 0.05, "salt": 0.001},
    )
    assert values.kcal == pytest.approx(240.0)
    assert values.cost == pytest.approx(0.8)
    assert values.macros["proteins"] == pytest.approx(10.0)
    assert values.macros["salt"] == pytest.approx(0.2)


def test_an_unknown_macro_stays_none_and_never_becomes_zero():
    values = movement_values(200.0, None, None, macro_rates={"proteins": None})
    assert values.kcal is None
    assert values.cost is None
    assert values.macros["proteins"] is None


def test_a_macro_measured_at_zero_stays_zero():
    """Un aliment sans sel a bien 0 g de sel : ce n'est pas une valeur
    manquante, et l'écraser en `None` perdrait une mesure réelle."""
    values = movement_values(200.0, None, None, macro_rates={"salt": 0.0})
    assert values.macros["salt"] == 0.0


def test_macros_are_keyed_by_every_column_even_when_the_rates_are_partial():
    """Le dictionnaire rendu couvre TOUJOURS les huit colonnes : l'appelant
    l'écrit directement dans `movement`, et une clé absente y deviendrait une
    colonne muette au lieu d'un NULL explicite."""
    values = movement_values(100.0, None, None, macro_rates={"proteins": 0.1})
    assert set(values.macros) == set(MACRO_COLUMNS)
    assert values.macros["fiber"] is None


def test_no_macro_rates_at_all_still_yields_eight_nulls():
    values = movement_values(100.0, None, None)
    assert set(values.macros) == set(MACRO_COLUMNS)
    assert all(value is None for value in values.macros.values())


def test_macros_use_the_magnitude_like_kcal_does():
    """Une sortie porte une quantité négative ; ses nutriments sont positifs."""
    values = movement_values(-200.0, 1.2, None, macro_rates={"proteins": 0.05})
    assert values.macros["proteins"] == pytest.approx(10.0)


def test_macros_are_never_rounded():
    values = movement_values(3.0, None, None, macro_rates={"proteins": 0.1})
    assert values.macros["proteins"] == 3.0 * 0.1     # 0.30000000000000004
```

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `./scripts/test.sh tests/domain/test_nutrition.py -q`
Expected: FAIL — `movement_values() got an unexpected keyword argument 'macro_rates'`

- [ ] **Step 3: Écrire l'implémentation**

Remplacer le contenu de `custom_components/home_stock/domain/nutrition.py` sous les imports :

```python
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from ..const import MACRO_COLUMNS


@dataclass(frozen=True)
class MovementValues:
    """Values frozen on a movement. None means unknown, 0.0 means measured at zero."""

    kcal: float | None
    cost: float | None
    macros: Mapping[str, float | None] = field(default_factory=dict)


def movement_values(
    quantity: float,
    kcal_per_base_unit: float | None,
    price_per_base_unit: float | None,
    macro_rates: Mapping[str, float | None] | None = None,
) -> MovementValues:
    """Compute the kcal, cost and macros of a movement. Never rounds.

    `macros` always carries all eight keys, even when the rates given are
    partial or absent: the caller writes this mapping straight into the
    movement row, and a missing key there would leave a column unwritten
    instead of an explicit NULL — the two look identical in SQLite until you
    try to tell "no data" from "never asked".
    """
    magnitude = abs(float(quantity))
    rates = macro_rates or {}
    return MovementValues(
        kcal=None if kcal_per_base_unit is None else magnitude * kcal_per_base_unit,
        cost=None if price_per_base_unit is None else magnitude * price_per_base_unit,
        macros={
            column: (None if rates.get(column) is None else magnitude * rates[column])
            for column in MACRO_COLUMNS
        },
    )
```

- [ ] **Step 4: Lancer, vérifier le succès**

Run: `./scripts/test.sh tests/domain/test_nutrition.py -q`
Expected: PASS

- [ ] **Step 5: Écrire le test du transport par les allocations**

Ajouter à `tests/domain/test_stock.py` :

```python
def test_an_allocation_carries_the_macros_of_its_batch():
    batch = BatchView(
        id=1, remaining=500.0, best_before=None,
        entered_at=datetime(2026, 8, 1), opened_at=None,
        price_per_base_unit=0.004, kcal_per_base_unit=1.2,
        macros={"proteins": 0.05, "salt": 0.001},
    )
    [allocation] = allocate([batch], 200.0)
    assert allocation.macros == {"proteins": 0.05, "salt": 0.001}


def test_a_batch_view_without_macros_still_works():
    """Toutes les constructions du lot 0 et du lot 1 en sont dépourvues."""
    batch = BatchView(
        id=1, remaining=500.0, best_before=None,
        entered_at=datetime(2026, 8, 1), opened_at=None,
        price_per_base_unit=None, kcal_per_base_unit=None,
    )
    [allocation] = allocate([batch], 200.0)
    assert allocation.macros == {}
```

- [ ] **Step 6: Lancer, vérifier l'échec**

Run: `./scripts/test.sh tests/domain/test_stock.py -q`
Expected: FAIL — `BatchView.__init__() got an unexpected keyword argument 'macros'`

- [ ] **Step 7: Faire transiter les macros**

Dans `custom_components/home_stock/domain/stock.py`, ajouter `from collections.abc import Mapping` et `field` à l'import `dataclasses`, puis un champ à chacune des deux dataclasses :

```python
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
    # The eight macros of the article behind this batch, per base unit. Empty
    # by default so every construction written before lot 2 stays valid; the
    # movement it produces then freezes eight NULLs, which is the truth.
    macros: Mapping[str, float | None] = field(default_factory=dict)
```

Idem sur `Allocation` (même champ, même commentaire abrégé), et dans `allocate()` ajouter `macros=candidate.macros,` à la construction de l'`Allocation`.

- [ ] **Step 8: Lancer toute la suite du domaine**

Run: `./scripts/test.sh tests/domain -q`
Expected: PASS

- [ ] **Step 9: Vérifier que le test a des dents (mutation)**

Dans `movement_values`, remplacer `None if rates.get(column) is None else magnitude * rates[column]` par `magnitude * (rates.get(column) or 0.0)`. Relancer `./scripts/test.sh tests/domain/test_nutrition.py -q` : `test_an_unknown_macro_stays_none_and_never_becomes_zero` doit tomber. C'est exactement le mensonge que la spec interdit (un repas inconnu compté comme zéro). Remettre le code correct.

- [ ] **Step 10: Commit**

```bash
git add custom_components/home_stock/domain/ tests/domain/
git commit -m "feat: a movement values nine nutrients, not one"
```

---

## Task 4: Geler les neuf nutriments dans le journal

**Files:**
- Modify: `custom_components/home_stock/storage/repositories.py`
- Modify: `custom_components/home_stock/application.py`
- Test: `tests/storage/test_repositories.py`, `tests/test_application.py`

**Interfaces:**
- Consomme : `movement_values(..., macro_rates=...)` et `BatchView.macros` (tâche 3) ; les colonnes de `m003` (tâche 1).
- Produit :
  - `repo.MACRO_RATE_SQL: str` — la liste `a.proteins, a.carbohydrates, …` préfixée pour un `SELECT`.
  - `repo.macro_rates(row: Mapping) -> dict[str, float | None]` — extrait les huit taux d'une ligne déjà lue.
  - `repo.insert_movement(..., macros: Mapping[str, float | None] | None = None, parts_total: int | None = None, parts_mine: int | None = None)`
  - `repo.list_batches_for_product` et la requête de `consume_batch` rapportent les huit taux.

- [ ] **Step 1: Écrire le test d'insertion**

Ajouter à `tests/storage/test_repositories.py` :

```python
def test_insert_movement_freezes_the_eight_macros(seeded_conn):
    movement_id = repo.insert_movement(
        seeded_conn, occurred_at="2026-08-20T10:00:00", product_id=1, article_id=1,
        quantity=-200.0, reason="consumption", base_unit="g", kcal=240.0, cost=0.8,
        macros={"proteins": 10.0, "salt": 0.2},
    )
    row = seeded_conn.execute(
        "SELECT * FROM movement WHERE id = ?", (movement_id,)).fetchone()
    assert row["proteins"] == 10.0
    assert row["salt"] == 0.2
    # Une macro absente du dictionnaire reste NULL, pas 0.
    assert row["fiber"] is None


def test_insert_movement_without_macros_writes_eight_nulls(seeded_conn):
    movement_id = repo.insert_movement(
        seeded_conn, occurred_at="2026-08-20T10:00:00", product_id=1, article_id=1,
        quantity=-200.0, reason="consumption", base_unit="g")
    row = seeded_conn.execute(
        "SELECT * FROM movement WHERE id = ?", (movement_id,)).fetchone()
    assert all(row[column] is None for column in MACRO_COLUMNS)


def test_macro_rates_reads_the_eight_columns_of_a_row():
    row = {"proteins": 0.05, "carbohydrates": None, "sugars": 0.01,
           "added_sugars": None, "fat": 0.02, "saturated_fat": None,
           "fiber": 0.0, "salt": 0.001, "kcal_per_base_unit": 1.2}
    rates = repo.macro_rates(row)
    assert set(rates) == set(MACRO_COLUMNS)
    assert rates["proteins"] == 0.05
    assert rates["carbohydrates"] is None
    assert rates["fiber"] == 0.0       # mesuré à zéro, pas manquant
    assert "kcal_per_base_unit" not in rates


def test_list_batches_for_product_reports_the_macro_rates(seeded_conn):
    seeded_conn.execute("UPDATE article SET proteins = 0.05, salt = 0.001 WHERE id = 1")
    [row] = repo.list_batches_for_product(seeded_conn, 1)
    assert row["proteins"] == 0.05
    assert row["salt"] == 0.001
```

Le fichier importe déjà `repo` ; ajouter `from custom_components.home_stock.const import MACRO_COLUMNS` en tête. Si la fixture `seeded_conn` n'existe pas sous ce nom, reprendre celle que ce fichier utilise déjà pour ses tests de `insert_movement` : une base migrée avec un emplacement, un produit `g`, un article et un lot ouvert.

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `./scripts/test.sh tests/storage/test_repositories.py -q`
Expected: FAIL — `insert_movement() got an unexpected keyword argument 'macros'`

- [ ] **Step 3: Écrire les dépôts**

Dans `custom_components/home_stock/storage/repositories.py`, sous `KCAL_RATE_SQL` :

```python
# The eight macro rates, read straight off the article. Unlike the kcal rate
# above, there is NO product-level fallback: `product.reference_kcal` exists
# because a generic article (loose apples) still has a known calorie count,
# but nobody maintains a reference protein content per product. No value on
# the article means no value, and the movement freezes NULL.
MACRO_RATE_SQL = ", ".join(f"a.{column}" for column in MACRO_COLUMNS)


def macro_rates(row: Mapping[str, Any]) -> dict[str, float | None]:
    """The eight macro rates of an already-read row, keyed by column name."""
    return {column: row[column] for column in MACRO_COLUMNS}
```

Ajouter `from collections.abc import Mapping` et `MACRO_COLUMNS` aux imports du module.

Étendre `insert_movement` :

```python
def insert_movement(conn, *, occurred_at: str, product_id: int, article_id: int,
                    quantity: float, reason: str, base_unit: str,
                    batch_id: int | None = None,
                    kcal: float | None = None, cost: float | None = None,
                    macros: Mapping[str, float | None] | None = None,
                    parts_total: int | None = None, parts_mine: int | None = None,
                    ref_type: str | None = None, ref_id: int | None = None,
                    idempotency_key: str | None = None) -> int:
    values: dict[str, Any] = {
        "occurred_at": occurred_at, "product_id": product_id, "article_id": article_id,
        "batch_id": batch_id, "quantity": quantity, "reason": reason,
        "base_unit": base_unit, "kcal": kcal,
        "cost": cost, "ref_type": ref_type, "ref_id": ref_id,
        "parts_total": parts_total, "parts_mine": parts_mine,
        "idempotency_key": idempotency_key,
    }
    # Always all eight columns, so an absent rate lands as an explicit NULL
    # rather than as a column this INSERT simply never mentioned.
    given = macros or {}
    values.update({column: given.get(column) for column in MACRO_COLUMNS})
    return _insert(conn, "movement", values)
```

Dans `list_batches_for_product`, ajouter les taux au `SELECT` :

```python
    return _rows(conn.execute(
        f"SELECT b.*, {KCAL_RATE_SQL} AS kcal_per_base_unit, {MACRO_RATE_SQL},"
        "       a.product_id FROM batch b"
        " JOIN article a ON a.id = b.article_id"
        " JOIN product p ON p.id = a.product_id"
        " WHERE a.product_id = ? AND b.closed_at IS NULL",
        (product_id,),
    ))
```

- [ ] **Step 4: Lancer, vérifier le succès**

Run: `./scripts/test.sh tests/storage/test_repositories.py -q`
Expected: PASS

- [ ] **Step 5: Écrire le test bout en bout du gel**

Ajouter à `tests/test_application.py` :

```python
def test_consuming_freezes_the_macros_of_the_moment(manager):
    """Le test qui compte vraiment : resynchroniser l'article APRÈS coup ne
    doit rien changer au mouvement déjà écrit. C'est la raison d'être des
    colonnes, pas un détail d'implémentation."""
    article_id, product_id = _seed_article(manager, base_unit="g",
                                           kcal_per_base_unit=1.2, proteins=0.05)
    manager.add_stock(article_id=article_id, quantity=500.0, location_id=1)

    manager.consume(product_id=product_id, quantity=200.0)

    with manager.db.write() as conn:
        conn.execute("UPDATE article SET proteins = 99.0 WHERE id = ?", (article_id,))

    row = manager.db.read().execute(
        "SELECT proteins, kcal FROM movement WHERE reason = 'consumption'").fetchone()
    assert row["proteins"] == pytest.approx(10.0)
    assert row["kcal"] == pytest.approx(240.0)


def test_consuming_an_article_without_macros_writes_nulls(manager):
    article_id, product_id = _seed_article(manager, base_unit="g",
                                           kcal_per_base_unit=None, proteins=None)
    manager.add_stock(article_id=article_id, quantity=500.0, location_id=1)

    manager.consume(product_id=product_id, quantity=200.0)

    row = manager.db.read().execute(
        "SELECT kcal, proteins FROM movement WHERE reason = 'consumption'").fetchone()
    assert row["kcal"] is None
    assert row["proteins"] is None


def test_consume_batch_freezes_the_macros_too(manager):
    article_id, product_id = _seed_article(manager, base_unit="g",
                                           kcal_per_base_unit=1.2, proteins=0.05)
    batch_id = manager.add_stock(article_id=article_id, quantity=500.0, location_id=1)

    manager.consume_batch(batch_id, quantity=100.0)

    row = manager.db.read().execute(
        "SELECT proteins FROM movement WHERE reason = 'consumption'").fetchone()
    assert row["proteins"] == pytest.approx(5.0)
```

`_seed_article` est le helper de ce fichier ; lui ajouter les paramètres nutritionnels nécessaires (`proteins=None` par défaut) plutôt que d'en créer un second.

- [ ] **Step 6: Lancer, vérifier l'échec**

Run: `./scripts/test.sh tests/test_application.py -q`
Expected: FAIL — `movement.proteins` vaut `None` alors que 10.0 est attendu.

- [ ] **Step 7: Câbler les trois appelants**

Dans `custom_components/home_stock/application.py` :

`add_stock` (autour de la ligne 131) — l'article est déjà lu en main :

```python
            values = movement_values(amount, kcal_rate, price_per_base_unit,
                                     macro_rates=repo.macro_rates(article))
```
puis passer `macros=values.macros` à `repo.insert_movement`.

`consume` (autour de la ligne 175) :

```python
                values = movement_values(allocation.quantity,
                                         allocation.kcal_per_base_unit,
                                         allocation.price_per_base_unit,
                                         macro_rates=allocation.macros)
```
et `macros=values.macros` sur l'`insert_movement` qui suit. La construction des `BatchView` juste au-dessus devient :

```python
            batches = [_as_batch_view(row)
                       for row in repo.list_batches_for_product(conn, product_id)]
```
inchangée — c'est `_as_batch_view` qui gagne `macros=repo.macro_rates(row)`.

`consume_batch` (autour de la ligne 220) : ajouter `{repo.MACRO_RATE_SQL},` au `SELECT` de la requête, puis

```python
            values = movement_values(taken, row["kcal_per_base_unit"],
                                     row["price_per_base_unit"],
                                     macro_rates=repo.macro_rates(row))
```
et `macros=values.macros` sur l'`insert_movement`.

Enfin `_as_batch_view` :

```python
def _as_batch_view(row: dict[str, Any]) -> BatchView:
    return BatchView(
        ...,                                   # champs déjà présents, inchangés
        macros=repo.macro_rates(row),
    )
```

- [ ] **Step 8: Lancer toute la suite Python**

Run: `./scripts/test.sh -q`
Expected: PASS

- [ ] **Step 9: Vérifier que le test a des dents (mutation)**

Retirer `macro_rates=allocation.macros` de l'appel dans `consume`. Relancer `./scripts/test.sh tests/test_application.py -q` : `test_consuming_freezes_the_macros_of_the_moment` doit tomber. Remettre.

- [ ] **Step 10: Commit**

```bash
git add custom_components/home_stock/storage/repositories.py custom_components/home_stock/application.py tests/
git commit -m "feat: every movement freezes its nine nutrients"
```

---

## Task 5: Les parts

**Files:**
- Modify: `custom_components/home_stock/application.py`
- Modify: `custom_components/home_stock/validators.py`
- Modify: `custom_components/home_stock/const.py`
- Test: `tests/test_application.py`, `tests/test_validators.py`

**Interfaces:**
- Consomme : `repo.insert_movement(..., parts_total=…, parts_mine=…)` (tâche 4).
- Produit :
  - `const.MAX_PARTS: int = 24`
  - `validators.parts_count(value) -> int` — entier de 0 à `MAX_PARTS`, refuse tout le reste.
  - `application.PartsError(ValueError)` — parts incohérentes ou posées sur un mauvais motif.
  - `StockManager.consume(..., parts_total: int | None = None, parts_mine: int | None = None)`
  - `StockManager.consume_batch(..., parts_total=…, parts_mine=…, idempotency_key: str | None = None)`

- [ ] **Step 1: Écrire les tests**

Ajouter à `tests/test_application.py` :

```python
def test_parts_are_written_on_a_consumption(manager):
    article_id, product_id = _seed_article(manager, base_unit="g", kcal_per_base_unit=1.2)
    manager.add_stock(article_id=article_id, quantity=800.0, location_id=1)

    manager.consume(product_id=product_id, quantity=400.0, parts_total=4, parts_mine=1)

    row = manager.db.read().execute(
        "SELECT parts_total, parts_mine, kcal FROM movement"
        " WHERE reason = 'consumption'").fetchone()
    assert (row["parts_total"], row["parts_mine"]) == (4, 1)
    # Les kcal FIGÉES restent celles de tout ce qui est sorti : la division
    # par les parts est faite à la lecture, jamais à l'écriture — sinon la
    # quantité et les calories du même mouvement ne se correspondraient plus.
    assert row["kcal"] == pytest.approx(480.0)


def test_parts_default_to_nothing_at_all(manager):
    """Sans parts, les colonnes restent NULL — et NULL vaut 1/1 à la
    lecture. Écrire 1/1 en dur salirait tout l'historique d'avant le lot 2
    d'une donnée qui n'a jamais été saisie."""
    article_id, product_id = _seed_article(manager, base_unit="g")
    manager.add_stock(article_id=article_id, quantity=800.0, location_id=1)

    manager.consume(product_id=product_id, quantity=100.0)

    row = manager.db.read().execute(
        "SELECT parts_total, parts_mine FROM movement"
        " WHERE reason = 'consumption'").fetchone()
    assert row["parts_total"] is None and row["parts_mine"] is None


def test_parts_mine_may_be_zero(manager):
    """« J'ai servi mes invités, je n'en ai pas mangé » : le stock part, le
    journal alimentaire n'en porte rien."""
    article_id, product_id = _seed_article(manager, base_unit="g")
    manager.add_stock(article_id=article_id, quantity=800.0, location_id=1)

    manager.consume(product_id=product_id, quantity=400.0, parts_total=4, parts_mine=0)

    row = manager.db.read().execute(
        "SELECT parts_mine FROM movement WHERE reason = 'consumption'").fetchone()
    assert row["parts_mine"] == 0


def test_more_parts_eaten_than_served_is_refused(manager):
    article_id, product_id = _seed_article(manager, base_unit="g")
    manager.add_stock(article_id=article_id, quantity=800.0, location_id=1)

    with pytest.raises(PartsError):
        manager.consume(product_id=product_id, quantity=100.0,
                        parts_total=2, parts_mine=3)

    assert manager.db.read().execute("SELECT COUNT(*) FROM movement"
                                     " WHERE reason = 'consumption'").fetchone()[0] == 0


def test_zero_parts_served_is_refused(manager):
    article_id, product_id = _seed_article(manager, base_unit="g")
    manager.add_stock(article_id=article_id, quantity=800.0, location_id=1)
    with pytest.raises(PartsError):
        manager.consume(product_id=product_id, quantity=100.0,
                        parts_total=0, parts_mine=0)


def test_parts_on_waste_are_refused(manager):
    """Personne ne partage une poubelle : accepter des parts ici écrirait une
    donnée qui n'a aucun sens, et que le calcul du jour ignore de toute façon."""
    article_id, product_id = _seed_article(manager, base_unit="g")
    manager.add_stock(article_id=article_id, quantity=800.0, location_id=1)
    with pytest.raises(PartsError):
        manager.consume(product_id=product_id, quantity=100.0, reason="waste",
                        parts_total=2, parts_mine=1)


def test_only_one_part_given_is_refused(manager):
    """Donner l'un sans l'autre est une saisie incomplète, pas un défaut."""
    article_id, product_id = _seed_article(manager, base_unit="g")
    manager.add_stock(article_id=article_id, quantity=800.0, location_id=1)
    with pytest.raises(PartsError):
        manager.consume(product_id=product_id, quantity=100.0, parts_total=4)
    with pytest.raises(PartsError):
        manager.consume(product_id=product_id, quantity=100.0, parts_mine=1)


def test_parts_spread_over_several_batches_land_on_every_movement(manager):
    """Une consommation qui traverse deux lots écrit deux mouvements : les
    deux portent les mêmes parts, sinon la moitié du repas serait comptée
    pour la maison entière."""
    article_id, product_id = _seed_article(manager, base_unit="g")
    manager.add_stock(article_id=article_id, quantity=100.0, location_id=1)
    manager.add_stock(article_id=article_id, quantity=100.0, location_id=1)

    manager.consume(product_id=product_id, quantity=150.0, parts_total=3, parts_mine=1)

    rows = manager.db.read().execute(
        "SELECT parts_total, parts_mine FROM movement"
        " WHERE reason = 'consumption'").fetchall()
    assert len(rows) == 2
    assert all((r["parts_total"], r["parts_mine"]) == (3, 1) for r in rows)


def test_consume_batch_accepts_parts_and_an_idempotency_key(manager):
    article_id, product_id = _seed_article(manager, base_unit="g")
    batch_id = manager.add_stock(article_id=article_id, quantity=800.0, location_id=1)

    first = manager.consume_batch(batch_id, quantity=100.0, parts_total=2,
                                  parts_mine=1, idempotency_key="abc")
    second = manager.consume_batch(batch_id, quantity=100.0, parts_total=2,
                                   parts_mine=1, idempotency_key="abc")

    assert first == second
    assert manager.db.read().execute(
        "SELECT COUNT(*) FROM movement WHERE reason = 'consumption'").fetchone()[0] == 1
```

Ajouter `from custom_components.home_stock.application import PartsError` en tête du fichier.

Créer `tests/test_validators.py` s'il n'existe pas, et y ajouter :

```python
import pytest
import voluptuous as vol

from custom_components.home_stock.validators import parts_count


def test_parts_count_accepts_a_plain_integer():
    assert parts_count(4) == 4
    assert parts_count(0) == 0


def test_parts_count_refuses_a_float_a_bool_and_text():
    for value in (1.5, True, "2", None, [2]):
        with pytest.raises(vol.Invalid):
            parts_count(value)


def test_parts_count_refuses_out_of_range():
    with pytest.raises(vol.Invalid):
        parts_count(-1)
    with pytest.raises(vol.Invalid):
        parts_count(25)
    assert parts_count(24) == 24
```

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `./scripts/test.sh tests/test_application.py tests/test_validators.py -q`
Expected: FAIL — `ImportError: cannot import name 'PartsError'`

- [ ] **Step 3: Écrire le validateur**

Dans `const.py` :

```python
# Twenty-four plates is already a party; past that it is a typo, and the
# number ends up dividing someone's calories by a hundred.
MAX_PARTS: Final = 24
```

Dans `validators.py`, à côté de `bounded_int` :

```python
def parts_count(value: Any) -> int:
    """A number of plates: a real integer between 0 and MAX_PARTS.

    Stricter than `bounded_int` on purpose. A float would silently truncate
    (2.9 plates becoming 2 changes the divisor of someone's calories), and a
    bool is an integer in Python — `parts_mine: true` must not be read as one
    plate.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise vol.Invalid(f"expected a whole number of parts, got {preview(value)}")
    if not 0 <= value <= MAX_PARTS:
        raise vol.Invalid(f"parts must be between 0 and {MAX_PARTS}, got {value}")
    return value
```

Importer `MAX_PARTS` depuis `.const` en tête de `validators.py`.

- [ ] **Step 4: Écrire les parts dans l'application**

Dans `application.py`, sous les imports :

```python
class PartsError(ValueError):
    """Parts that cannot be true, or parts on a movement that cannot have any."""


def _checked_parts(reason: str, parts_total: int | None,
                   parts_mine: int | None) -> tuple[int | None, int | None]:
    """Validate the pair, or refuse the whole call.

    Both or neither: given one alone, the caller believes it recorded a share
    it did not, and the movement would read as 1/1 forever after.
    """
    if parts_total is None and parts_mine is None:
        return None, None
    if parts_total is None or parts_mine is None:
        raise PartsError("parts_total and parts_mine go together")
    if reason != REASON_CONSUMPTION:
        raise PartsError(f"a {reason} movement cannot be shared")
    if not 1 <= parts_total <= MAX_PARTS:
        raise PartsError(f"parts_total must be between 1 and {MAX_PARTS}")
    if not 0 <= parts_mine <= parts_total:
        raise PartsError("parts_mine must be between 0 and parts_total")
    return parts_total, parts_mine
```

`consume` : ajouter les deux paramètres à la signature, appeler `_checked_parts` **avant** d'ouvrir la transaction d'écriture (une saisie incohérente ne doit pas prendre le verrou d'écriture), et passer `parts_total=…, parts_mine=…` à chaque `repo.insert_movement` de la boucle.

`consume_batch` : mêmes deux paramètres, plus `idempotency_key: str | None = None`. Reprendre le motif exact déjà écrit dans `consume` pour la clé — `_namespaced_key("consume_batch", idempotency_key)`, court-circuit `repo.movement_exists`, et la clé posée sur l'unique mouvement écrit. `consume_batch` n'écrit qu'un mouvement : pas de suffixe `#1` à gérer.

Ajouter `MAX_PARTS` à l'import depuis `.const`.

- [ ] **Step 5: Lancer, vérifier le succès**

Run: `./scripts/test.sh -q`
Expected: PASS

- [ ] **Step 6: Vérifier que les tests ont des dents (mutation)**

Remplacer dans `_checked_parts` la ligne `if not 0 <= parts_mine <= parts_total:` par `if parts_mine < 0:`. Relancer : `test_more_parts_eaten_than_served_is_refused` doit tomber. Remettre.

- [ ] **Step 7: Commit**

```bash
git add custom_components/home_stock/ tests/
git commit -m "feat: a consumption records how many plates, and how many were mine"
```

---

## Task 6: Les agrégats et les séries, côté dépôts

**Files:**
- Modify: `custom_components/home_stock/storage/repositories.py`
- Test: `tests/storage/test_repositories_journal.py` (créer)

**Interfaces:**
- Consomme : les colonnes de `m003` (tâche 1).
- Produit :
  - `repo.SHARE_SQL: str`
  - `repo.totals_between(conn, start: str | None = None, end: str | None = None) -> dict[str, Any]` — clés : les neuf nutriments, `cost`, `waste_cost`, `unvalued`.
  - `repo.journal_entries(conn, start: str, end: str) -> list[dict[str, Any]]`
  - `repo.counted_movements(conn, since: str) -> list[dict[str, Any]]` — la matière brute des séries.
  - `repo.learned_portion(conn, product_id: int) -> float | None`

**⚠️ Le piège de ce lot.** `parts_total` et `parts_mine` sont des colonnes **INTEGER**. En SQLite, `1 / 4` sur deux entiers vaut **0** : sans `CAST(... AS REAL)`, une part sur quatre annulerait purement et simplement la journée, et le capteur afficherait 0 kcal en silence. C'est pour ça que `SHARE_SQL` existe une seule fois et que le test ci-dessous utilise `parts_mine = 1, parts_total = 4` plutôt que 1/2.

- [ ] **Step 1: Écrire les tests**

Créer `tests/storage/test_repositories_journal.py` :

```python
"""Les agrégats que lisent les capteurs et le panneau."""
import pytest

from custom_components.home_stock.storage import repositories as repo

JOUR = ("2026-08-20T02:00:00", "2026-08-21T02:00:00")


def _movement(conn, **kwargs):
    defaults = dict(occurred_at="2026-08-20T10:00:00", product_id=1, article_id=1,
                    quantity=-200.0, reason="consumption", base_unit="g")
    return repo.insert_movement(conn, **{**defaults, **kwargs})


def test_a_share_of_one_quarter_is_not_swallowed_by_integer_division(journal_conn):
    """Le piège du lot : en SQLite, 1/4 sur deux INTEGER vaut 0."""
    _movement(journal_conn, kcal=480.0, parts_total=4, parts_mine=1)
    totals = repo.totals_between(journal_conn, *JOUR)
    assert totals["kcal"] == pytest.approx(120.0)


def test_null_parts_count_as_the_whole_thing(journal_conn):
    _movement(journal_conn, kcal=240.0)
    assert repo.totals_between(journal_conn, *JOUR)["kcal"] == pytest.approx(240.0)


def test_zero_parts_mine_contributes_nothing(journal_conn):
    _movement(journal_conn, kcal=480.0, parts_total=4, parts_mine=0)
    assert repo.totals_between(journal_conn, *JOUR)["kcal"] == 0.0


def test_waste_never_reaches_the_calories(journal_conn):
    _movement(journal_conn, kcal=500.0, cost=1.5, reason="waste")
    _movement(journal_conn, kcal=300.0, cost=0.9, reason="expired")
    _movement(journal_conn, kcal=240.0, cost=0.8, reason="consumption")
    totals = repo.totals_between(journal_conn, *JOUR)
    assert totals["kcal"] == pytest.approx(240.0)
    assert totals["cost"] == pytest.approx(0.8)
    assert totals["waste_cost"] == pytest.approx(2.4)


def test_money_is_never_divided_by_the_parts(journal_conn):
    """La règle explicite de la spec : le paquet a coûté ce qu'il a coûté."""
    _movement(journal_conn, kcal=480.0, cost=2.0, parts_total=4, parts_mine=1)
    totals = repo.totals_between(journal_conn, *JOUR)
    assert totals["cost"] == pytest.approx(2.0)
    assert totals["kcal"] == pytest.approx(120.0)


def test_a_purchase_is_never_counted(journal_conn):
    _movement(journal_conn, kcal=1000.0, cost=5.0, reason="purchase", quantity=800.0)
    totals = repo.totals_between(journal_conn, *JOUR)
    assert totals["kcal"] == 0.0 and totals["cost"] == 0.0 and totals["waste_cost"] == 0.0


def test_the_eight_macros_are_aggregated_too(journal_conn):
    _movement(journal_conn, kcal=480.0, parts_total=2, parts_mine=1,
              macros={"proteins": 20.0, "salt": 1.0})
    totals = repo.totals_between(journal_conn, *JOUR)
    assert totals["proteins"] == pytest.approx(10.0)
    assert totals["salt"] == pytest.approx(0.5)
    assert totals["fiber"] == 0.0        # rien de mesuré : la somme est vide


def test_unvalued_counts_the_consumptions_without_calories(journal_conn):
    _movement(journal_conn, kcal=240.0)
    _movement(journal_conn, kcal=None)
    _movement(journal_conn, kcal=None, reason="waste")     # pas une consommation
    assert repo.totals_between(journal_conn, *JOUR)["unvalued"] == 1


def test_bounds_are_half_open(journal_conn):
    _movement(journal_conn, occurred_at="2026-08-20T02:00:00", kcal=10.0)   # inclus
    _movement(journal_conn, occurred_at="2026-08-21T02:00:00", kcal=99.0)   # exclu
    _movement(journal_conn, occurred_at="2026-08-20T01:59:59", kcal=99.0)   # exclu
    assert repo.totals_between(journal_conn, *JOUR)["kcal"] == pytest.approx(10.0)


def test_without_bounds_the_totals_are_cumulative(journal_conn):
    _movement(journal_conn, occurred_at="2024-01-01T10:00:00", kcal=100.0)
    _movement(journal_conn, occurred_at="2026-08-20T10:00:00", kcal=240.0)
    assert repo.totals_between(journal_conn)["kcal"] == pytest.approx(340.0)


def test_journal_entries_carry_what_the_panel_shows(journal_conn):
    _movement(journal_conn, occurred_at="2026-08-20T12:00:00", kcal=240.0,
              parts_total=2, parts_mine=1)
    _movement(journal_conn, occurred_at="2026-08-20T09:00:00", kcal=100.0)
    entries = repo.journal_entries(journal_conn, *JOUR)
    assert [e["occurred_at"] for e in entries] == [
        "2026-08-20T09:00:00", "2026-08-20T12:00:00"]
    assert entries[0]["product_name"] == "Yaourt"
    assert entries[1]["parts_mine"] == 1
    assert entries[0]["base_unit"] == "g"


def test_journal_entries_show_what_was_thrown_away_too(journal_conn):
    _movement(journal_conn, reason="waste", kcal=500.0)
    _movement(journal_conn, reason="purchase", quantity=800.0)
    reasons = [e["reason"] for e in repo.journal_entries(journal_conn, *JOUR)]
    assert reasons == ["waste"]


def test_learned_portion_is_the_median_of_the_last_three(journal_conn):
    for quantity in (-100.0, -300.0, -150.0, -140.0, -160.0):
        _movement(journal_conn, quantity=quantity)
    # Les trois DERNIÈRES sont 150, 140, 160 : médiane 150.
    assert repo.learned_portion(journal_conn, 1) == pytest.approx(150.0)


def test_learned_portion_needs_three_consumptions(journal_conn):
    _movement(journal_conn, quantity=-100.0)
    _movement(journal_conn, quantity=-120.0)
    assert repo.learned_portion(journal_conn, 1) is None


def test_learned_portion_ignores_waste_and_purchases(journal_conn):
    _movement(journal_conn, quantity=-100.0)
    _movement(journal_conn, quantity=-100.0)
    _movement(journal_conn, quantity=-999.0, reason="waste")
    _movement(journal_conn, quantity=800.0, reason="purchase")
    assert repo.learned_portion(journal_conn, 1) is None


def test_counted_movements_reports_the_raw_rows_for_a_series(journal_conn):
    _movement(journal_conn, occurred_at="2026-08-19T10:00:00", kcal=100.0)
    _movement(journal_conn, occurred_at="2026-08-20T10:00:00", kcal=240.0,
              parts_total=2, parts_mine=1)
    _movement(journal_conn, occurred_at="2026-08-20T11:00:00", reason="purchase",
              quantity=800.0, cost=5.0)
    rows = repo.counted_movements(journal_conn, "2026-08-19T02:00:00")
    assert len(rows) == 2
    assert rows[0]["occurred_at"] == "2026-08-19T10:00:00"
    assert rows[1]["parts_total"] == 2
```

Ajouter la fixture au fichier :

```python
@pytest.fixture
def journal_conn(tmp_path):
    """Une base migrée avec un produit, un article et rien d'autre : ces
    tests écrivent leurs mouvements à la main pour contrôler exactement les
    horodatages, les motifs et les parts."""
    from custom_components.home_stock.storage.database import Database
    db = Database(tmp_path / "home_stock.db")
    with db.write() as conn:
        conn.execute("INSERT INTO location (name, kind) VALUES ('Placard', 'cupboard')")
        conn.execute("INSERT INTO product (name, base_unit) VALUES ('Yaourt', 'g')")
        conn.execute("INSERT INTO article (product_id) VALUES (1)")
    with db.write() as conn:
        yield conn
```

Si `Database` ne s'ouvre pas ainsi, reprendre exactement le motif d'ouverture de `tests/storage/test_repositories.py`.

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `./scripts/test.sh tests/storage/test_repositories_journal.py -q`
Expected: FAIL — `module 'repositories' has no attribute 'totals_between'`

- [ ] **Step 3: Écrire les dépôts**

Dans `repositories.py` :

```python
# The personal share of a movement. The CAST is not decoration: parts_mine and
# parts_total are INTEGER columns, and SQLite's `1 / 4` on two integers is 0 —
# without it, one plate out of four would silently zero the whole day and the
# sensor would read 0 kcal with no error anywhere.
SHARE_SQL = "(CAST(COALESCE(parts_mine, 1) AS REAL) / COALESCE(parts_total, 1))"

# Only a consumption feeds the personal diary. Waste and expiry leave the
# stock and cost money, but nobody ate them (spec 7).
_PERSONAL_SUMS = ", ".join(
    [f"COALESCE(SUM(CASE WHEN reason = '{REASON_CONSUMPTION}'"
     f" THEN kcal * {SHARE_SQL} END), 0) AS kcal"]
    + [f"COALESCE(SUM(CASE WHEN reason = '{REASON_CONSUMPTION}'"
       f" THEN {column} * {SHARE_SQL} END), 0) AS {column}"
       for column in MACRO_COLUMNS]
)

_WASTE_REASONS_SQL = f"('{REASON_WASTE}', '{REASON_EXPIRED}')"


def totals_between(conn, start: str | None = None,
                   end: str | None = None) -> dict[str, Any]:
    """Nutrients, money and coverage over a half-open range, or over everything.

    Money is NEVER divided by the parts: the pack cost what it cost, whether
    it was eaten alone or shared four ways (spec 7). Only the nine nutrients
    carry the personal share.
    """
    where, params = "", []
    if start is not None and end is not None:
        where = " WHERE occurred_at >= ? AND occurred_at < ?"
        params = [start, end]
    row = conn.execute(
        f"SELECT {_PERSONAL_SUMS},"
        f" COALESCE(SUM(CASE WHEN reason = '{REASON_CONSUMPTION}' THEN cost END), 0)"
        "   AS cost,"
        f" COALESCE(SUM(CASE WHEN reason IN {_WASTE_REASONS_SQL} THEN cost END), 0)"
        "   AS waste_cost,"
        f" COALESCE(SUM(CASE WHEN reason = '{REASON_CONSUMPTION}' AND kcal IS NULL"
        "   THEN 1 END), 0) AS unvalued"
        f" FROM movement{where}",
        tuple(params),
    ).fetchone()
    return dict(row)


def journal_entries(conn, start: str, end: str) -> list[dict[str, Any]]:
    """What left the stock during a food day, oldest first."""
    return _rows(conn.execute(
        "SELECT m.id, m.occurred_at, m.quantity, m.reason, m.base_unit, m.kcal,"
        "       m.cost, m.parts_total, m.parts_mine, p.name AS product_name"
        " FROM movement m JOIN product p ON p.id = m.product_id"
        f" WHERE m.reason IN ('{REASON_CONSUMPTION}', '{REASON_WASTE}',"
        f"                    '{REASON_EXPIRED}')"
        "   AND m.occurred_at >= ? AND m.occurred_at < ?"
        " ORDER BY m.occurred_at, m.id",
        (start, end),
    ))


def counted_movements(conn, since: str) -> list[dict[str, Any]]:
    """The raw rows a series is bucketed from, in Python.

    Bucketing here rather than in SQL is not laziness: SQLite ships no
    timezone database, so a GROUP BY on a locally-shifted date would be wrong
    twice a year — precisely on the two days the food-day boundary is
    interesting. The volume makes this free: a household writes some fifteen
    movements a day, so twelve months is on the order of 5 000 rows.
    """
    return _rows(conn.execute(
        "SELECT occurred_at, reason, kcal, cost, parts_total, parts_mine,"
        f"       {', '.join(MACRO_COLUMNS)}"
        " FROM movement"
        f" WHERE reason IN ('{REASON_CONSUMPTION}', '{REASON_WASTE}',"
        f"                  '{REASON_EXPIRED}')"
        "   AND occurred_at >= ? ORDER BY occurred_at, id",
        (since,),
    ))


def learned_portion(conn, product_id: int) -> float | None:
    """The median of the last three consumptions of this product, or nothing.

    Under three, there is no habit yet — and proposing a number drawn from a
    single meal would train the button to be wrong. Same discipline as lot 1's
    learned shelf life.
    """
    rows = conn.execute(
        "SELECT ABS(quantity) AS quantity FROM movement"
        f" WHERE product_id = ? AND reason = '{REASON_CONSUMPTION}'"
        " ORDER BY id DESC LIMIT 3",
        (product_id,),
    ).fetchall()
    if len(rows) < 3:
        return None
    return float(sorted(row["quantity"] for row in rows)[1])
```

Ajouter `REASON_EXPIRED`, `REASON_WASTE`, `REASON_CONSUMPTION` et `MACRO_COLUMNS` aux imports depuis `..const` si l'un manque.

- [ ] **Step 4: Lancer, vérifier le succès**

Run: `./scripts/test.sh tests/storage -q`
Expected: PASS

- [ ] **Step 5: Vérifier que le test a des dents (mutation)**

Retirer le `CAST(... AS REAL)` de `SHARE_SQL` (le laisser en `COALESCE(parts_mine, 1) / COALESCE(parts_total, 1)`). Relancer : `test_a_share_of_one_quarter_is_not_swallowed_by_integer_division` doit tomber, et `test_the_eight_macros_are_aggregated_too` aussi. Remettre le `CAST`.

- [ ] **Step 6: Commit**

```bash
git add custom_components/home_stock/storage/repositories.py tests/storage/test_repositories_journal.py
git commit -m "feat: daily totals, journal entries and the learned portion"
```

---

## Task 7: `summary()` scindé, et les séries

**Files:**
- Modify: `custom_components/home_stock/application.py`
- Test: `tests/test_application_journal.py` (créer)

**Interfaces:**
- Consomme : `foodday.food_day_bounds`, `foodday.bucket_bounds`, `foodday.bounds_of_food_day` (tâche 2) ; `repo.totals_between`, `repo.journal_entries`, `repo.counted_movements` (tâche 6).
- Produit :
  - `StockManager.summary(*, expiration_alert_days: int, tz: ZoneInfo, now: datetime | None = None, today: str | None = None)` — clés ajoutées : `kcal_total`, `cost_total` (sens changé), `cost_waste_total`, `today` (dict des neuf nutriments + `cost` + `unvalued` + `food_day` + `waste_cost`).
  - `StockManager.journal_day(day: date | None, tz: ZoneInfo, now=None) -> dict`
  - `StockManager.journal_series(granularity: str, count: int, tz: ZoneInfo, now=None) -> dict`

- [ ] **Step 1: Écrire les tests**

Créer `tests/test_application_journal.py` :

```python
"""La journée alimentaire vue depuis l'application."""
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest

PARIS = ZoneInfo("Europe/Paris")
MIDI = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)


def test_the_day_totals_only_hold_today(manager):
    article_id, product_id = _seed_article(manager, base_unit="g", kcal_per_base_unit=1.2)
    manager.add_stock(article_id=article_id, quantity=1000.0, location_id=1)
    # Hier 20 h locales = 18:00 UTC la veille.
    manager.consume(product_id=product_id, quantity=100.0,
                    occurred_at="2026-08-19T18:00:00")
    manager.consume(product_id=product_id, quantity=200.0,
                    occurred_at="2026-08-20T10:00:00")

    summary = manager.summary(expiration_alert_days=3, tz=PARIS, now=MIDI)

    assert summary["today"]["kcal"] == pytest.approx(240.0)
    assert summary["today"]["food_day"] == "2026-08-20"


def test_a_meal_at_two_in_the_morning_belongs_to_yesterday(manager):
    article_id, product_id = _seed_article(manager, base_unit="g", kcal_per_base_unit=1.2)
    manager.add_stock(article_id=article_id, quantity=1000.0, location_id=1)
    # 02:00 heure de Paris le 20 août = 00:00 UTC : encore la journée du 19.
    manager.consume(product_id=product_id, quantity=100.0,
                    occurred_at="2026-08-20T00:00:00")

    summary = manager.summary(expiration_alert_days=3, tz=PARIS, now=MIDI)
    assert summary["today"]["kcal"] == 0.0


def test_kcal_total_no_longer_counts_what_was_thrown_away(manager):
    article_id, product_id = _seed_article(manager, base_unit="g", kcal_per_base_unit=1.2)
    manager.add_stock(article_id=article_id, quantity=1000.0, location_id=1)
    manager.consume(product_id=product_id, quantity=100.0)
    manager.consume(product_id=product_id, quantity=200.0, reason="waste")

    summary = manager.summary(expiration_alert_days=3, tz=PARIS, now=MIDI)
    assert summary["kcal_total"] == pytest.approx(120.0)


def test_waste_has_its_own_euro_counter(manager):
    article_id, product_id = _seed_article(manager, base_unit="g", kcal_per_base_unit=1.2)
    manager.add_stock(article_id=article_id, quantity=1000.0, location_id=1,
                      price_per_base_unit=0.01)
    manager.consume(product_id=product_id, quantity=100.0)
    manager.consume(product_id=product_id, quantity=200.0, reason="expired")

    summary = manager.summary(expiration_alert_days=3, tz=PARIS, now=MIDI)
    assert summary["cost_total"] == pytest.approx(1.0)
    assert summary["cost_waste_total"] == pytest.approx(2.0)


def test_the_day_reports_how_much_it_could_not_value(manager):
    article_id, product_id = _seed_article(manager, base_unit="g", kcal_per_base_unit=None)
    manager.add_stock(article_id=article_id, quantity=1000.0, location_id=1)
    manager.consume(product_id=product_id, quantity=100.0,
                    occurred_at="2026-08-20T10:00:00")

    summary = manager.summary(expiration_alert_days=3, tz=PARIS, now=MIDI)
    assert summary["today"]["unvalued"] == 1


def test_journal_day_lists_the_entries_of_that_day(manager):
    article_id, product_id = _seed_article(manager, base_unit="g", kcal_per_base_unit=1.2)
    manager.add_stock(article_id=article_id, quantity=1000.0, location_id=1)
    manager.consume(product_id=product_id, quantity=200.0,
                    occurred_at="2026-08-20T10:00:00")

    day = manager.journal_day(date(2026, 8, 20), tz=PARIS, now=MIDI)
    assert day["food_day"] == "2026-08-20"
    assert day["start"] == "2026-08-20T02:00:00"
    assert len(day["entries"]) == 1
    assert day["entries"][0]["product_name"]
    assert day["totals"]["kcal"] == pytest.approx(240.0)


def test_journal_day_defaults_to_the_current_food_day(manager):
    day = manager.journal_day(None, tz=PARIS, now=MIDI)
    assert day["food_day"] == "2026-08-20"


def test_journal_series_buckets_by_day(manager):
    article_id, product_id = _seed_article(manager, base_unit="g", kcal_per_base_unit=1.2)
    manager.add_stock(article_id=article_id, quantity=2000.0, location_id=1)
    manager.consume(product_id=product_id, quantity=100.0,
                    occurred_at="2026-08-19T10:00:00")
    manager.consume(product_id=product_id, quantity=200.0,
                    occurred_at="2026-08-20T10:00:00")

    series = manager.journal_series("day", 3, tz=PARIS, now=MIDI)
    assert [b["label"] for b in series["buckets"]] == ["2026-08-18", "2026-08-19", "2026-08-20"]
    assert [b["kcal"] for b in series["buckets"]] == [0.0, pytest.approx(120.0),
                                                      pytest.approx(240.0)]


def test_journal_series_applies_the_parts_like_the_day_does(manager):
    article_id, product_id = _seed_article(manager, base_unit="g", kcal_per_base_unit=1.2)
    manager.add_stock(article_id=article_id, quantity=2000.0, location_id=1)
    manager.consume(product_id=product_id, quantity=400.0, parts_total=4, parts_mine=1,
                    occurred_at="2026-08-20T10:00:00")

    series = manager.journal_series("day", 1, tz=PARIS, now=MIDI)
    assert series["buckets"][0]["kcal"] == pytest.approx(120.0)


def test_journal_series_keeps_waste_out_of_the_calories_but_in_the_euros(manager):
    article_id, product_id = _seed_article(manager, base_unit="g", kcal_per_base_unit=1.2)
    manager.add_stock(article_id=article_id, quantity=2000.0, location_id=1,
                      price_per_base_unit=0.01)
    manager.consume(product_id=product_id, quantity=200.0, reason="waste",
                    occurred_at="2026-08-20T10:00:00")

    bucket = manager.journal_series("day", 1, tz=PARIS, now=MIDI)["buckets"][0]
    assert bucket["kcal"] == 0.0
    assert bucket["cost"] == 0.0
    assert bucket["waste_cost"] == pytest.approx(2.0)


def test_journal_series_refuses_an_unknown_granularity(manager):
    with pytest.raises(ValueError):
        manager.journal_series("fortnight", 3, tz=PARIS, now=MIDI)
```

Reprendre `manager` et `_seed_article` de `tests/test_application.py` en les important, ou déplacer les deux dans `tests/conftest.py` si c'est plus propre — ne pas en écrire une seconde version.

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `./scripts/test.sh tests/test_application_journal.py -q`
Expected: FAIL — `summary() got an unexpected keyword argument 'tz'`

- [ ] **Step 3: Écrire l'application**

Dans `application.py`, importer :

```python
from zoneinfo import ZoneInfo

from .const import MACRO_COLUMNS
from .domain.foodday import bounds_of_food_day, bucket_bounds, food_day_bounds, food_day_of
```

Ajouter le regroupement des seaux :

```python
# The keys a bucket and a day both carry. One definition, so a series and a
# day can never disagree about what "kcal" means.
_TOTAL_KEYS: Final = ("kcal", *MACRO_COLUMNS, "cost", "waste_cost", "unvalued")


def _empty_totals() -> dict[str, float]:
    return {key: 0.0 for key in _TOTAL_KEYS}


def _accumulate(totals: dict[str, float], row: dict[str, Any]) -> None:
    """Add one movement to a bucket, applying the same rules as the SQL in
    repo.totals_between — personal share on the nutrients, never on the money."""
    reason = row["reason"]
    if reason == REASON_CONSUMPTION:
        share = ((row["parts_mine"] if row["parts_mine"] is not None else 1)
                 / (row["parts_total"] if row["parts_total"] is not None else 1))
        for key in ("kcal", *MACRO_COLUMNS):
            value = row[key]
            if value is not None:
                totals[key] += value * share
        if row["kcal"] is None:
            totals["unvalued"] += 1
        if row["cost"] is not None:
            totals["cost"] += row["cost"]
    elif row["cost"] is not None:
        totals["waste_cost"] += row["cost"]
```

> Note pour l'implémenteur : `_accumulate` et `repo.totals_between` calculent la même chose de deux façons. C'est délibéré — un jour tient dans une requête, une série de douze mois tient dans une boucle — mais **les deux doivent rester d'accord**. Le test `test_journal_series_applies_the_parts_like_the_day_does` existe pour ça ; si vous changez l'une, relisez l'autre.

Méthodes de `StockManager` :

```python
    def journal_day(self, day: date | None, *, tz: ZoneInfo,
                    now: datetime | None = None) -> dict[str, Any]:
        """One food day: its bounds, its entries, its totals."""
        reference = day or food_day_of(now or datetime.now(UTC), tz)
        start, end = bounds_of_food_day(reference, tz)
        conn = self.db.read()
        return {
            "food_day": reference.isoformat(),
            "start": start,
            "end": end,
            "entries": repo.journal_entries(conn, start, end),
            "totals": repo.totals_between(conn, start, end),
        }

    def journal_series(self, granularity: str, count: int, *, tz: ZoneInfo,
                       now: datetime | None = None) -> dict[str, Any]:
        """The last `count` buckets, oldest first. Raises ValueError on a
        granularity or a count the domain refuses."""
        buckets = bucket_bounds(granularity, count, now or datetime.now(UTC), tz)
        rows = repo.counted_movements(self.db.read(), buckets[0].start)
        filled = []
        for bucket in buckets:
            totals = _empty_totals()
            for row in rows:
                if bucket.start <= row["occurred_at"] < bucket.end:
                    _accumulate(totals, row)
            filled.append({"label": bucket.label, **totals})
        return {"granularity": granularity, "buckets": filled}
```

Dans `summary()` : ajouter les paramètres `tz: ZoneInfo` et `now: datetime | None = None`.

> **`today` reste, `now` s'ajoute.** `summary()` porte déjà un paramètre
> `today: str | None` que le lot 0 utilise pour la fenêtre de péremption, et
> plusieurs tests existants s'en servent. Ne pas le remplacer : la péremption
> raisonne en dates civiles, la journée alimentaire en instants. Les deux
> cohabitent, et `now` ne sert qu'aux bornes de la journée.

Remplacer l'appel à `repo.counted_totals` par

```python
        cumulative = repo.totals_between(conn)
        day_start, day_end = food_day_bounds(now or datetime.now(UTC), tz)
        today_totals = repo.totals_between(conn, day_start, day_end)
```

et dans le dictionnaire rendu :

```python
            # Lot 2, amendement A2 : ces deux compteurs ne totalisent plus que
            # la consommation. Le gaspillage a le sien, cost_waste_total, pour
            # que cost_total + cost_waste_total redonne l'ancien total.
            "kcal_total": round(cumulative["kcal"], 1),
            "cost_total": round(cumulative["cost"], 2),
            "cost_waste_total": round(cumulative["waste_cost"], 2),
            "today": {
                "food_day": food_day_of(now or datetime.now(UTC), tz).isoformat(),
                "kcal": round(today_totals["kcal"], 1),
                **{column: round(today_totals[column], 3) for column in MACRO_COLUMNS},
                "cost": round(today_totals["cost"], 2),
                "waste_cost": round(today_totals["waste_cost"], 2),
                "unvalued": int(today_totals["unvalued"]),
            },
```

`repo.counted_totals` n'a plus d'appelant : le supprimer, ainsi que son test, plutôt que de laisser deux définitions du même total dériver.

- [ ] **Step 4: Lancer toute la suite**

Run: `./scripts/test.sh -q`
Expected: PASS — corriger les appelants de `summary()` dans les tests existants, qui doivent maintenant passer `tz`.

- [ ] **Step 5: Vérifier que le test a des dents (mutation)**

Dans `_accumulate`, remplacer la garde `if reason == REASON_CONSUMPTION:` par `if reason in (REASON_CONSUMPTION, REASON_WASTE, REASON_EXPIRED):`. Relancer `./scripts/test.sh tests/test_application_journal.py -q` : `test_journal_series_keeps_waste_out_of_the_calories_but_in_the_euros` doit tomber. Remettre.

- [ ] **Step 6: Commit**

```bash
git add custom_components/home_stock/application.py custom_components/home_stock/storage/repositories.py tests/
git commit -m "feat: the day, the series, and eaten split from wasted"
```

---

## Task 8: Le coordinateur et le rendez-vous de 4 h

**Files:**
- Modify: `custom_components/home_stock/coordinator.py`
- Test: `tests/test_coordinator_foodday.py` (créer)

**Interfaces:**
- Consomme : `StockManager.summary(..., tz=…)` (tâche 7) ; `foodday.food_day_bounds` (tâche 2).
- Produit : `coordinator.data["today"]` toujours à jour, y compris un jour sans aucune activité.

**Pourquoi un rendez-vous.** Le coordinateur bat toutes les 15 minutes ; sans rendez-vous posé à la frontière, une journée sans sortie de stock afficherait le total de la veille pendant des heures — et le premier rafraîchissement après 4 h le corrigerait sans que personne comprenne pourquoi le chiffre a sauté.

- [ ] **Step 1: Écrire les tests**

Créer `tests/test_coordinator_foodday.py` :

```python
"""Le passage de 4 h remet la journée à zéro tout seul."""
from datetime import timedelta

from freezegun import freeze_time
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed


async def test_the_day_resets_at_four_without_any_activity(hass, setup_entry):
    """Sans ce rendez-vous, le capteur garderait le total de la veille jusqu'à
    la prochaine sortie de stock."""
    await dt_util.async_set_time_zone(hass, "Europe/Paris")
    with freeze_time("2026-08-20T20:00:00+02:00"):
        entry = await setup_entry(with_article=True)
        coordinator = entry.runtime_data.coordinator
        manager = entry.runtime_data.manager
        await hass.async_add_executor_job(
            lambda: manager.add_stock(article_id=1, quantity=500.0, location_id=1))
        await hass.async_add_executor_job(
            lambda: manager.consume(product_id=1, quantity=100.0))
        await coordinator.async_refresh()
        assert coordinator.data["today"]["food_day"] == "2026-08-20"

    with freeze_time("2026-08-21T04:00:01+02:00"):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
        await hass.async_block_till_done()

    assert coordinator.data["today"]["food_day"] == "2026-08-21"
    assert coordinator.data["today"]["kcal"] == 0.0


async def test_the_rendezvous_is_cancelled_when_the_entry_unloads(hass, setup_entry):
    """Un rendez-vous laissé derrière rappelle un coordinateur détruit."""
    entry = await setup_entry()
    coordinator = entry.runtime_data.coordinator
    assert coordinator._food_day_unsub is not None
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert coordinator._food_day_unsub is None
```

Si `freezegun` n'est pas déjà une dépendance de test, ne pas l'ajouter : réécrire les deux tests en injectant `now` — le coordinateur lit l'heure par `dt_util.utcnow()`, que `pytest-homeassistant-custom-component` sait déjà déplacer via `async_fire_time_changed`. Vérifier d'abord : `grep -r freezegun Dockerfile.test requirements*.txt`.

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `./scripts/test.sh tests/test_coordinator_foodday.py -q`
Expected: FAIL — `AttributeError: 'HomeStockCoordinator' object has no attribute '_food_day_unsub'`

- [ ] **Step 3: Écrire le coordinateur**

```python
from datetime import UTC, datetime, timedelta

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util import dt as dt_util

from .domain.foodday import food_day_bounds


class HomeStockCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass, entry, manager) -> None:
        super().__init__(...)                      # inchangé
        self.manager = manager
        self._food_day_unsub: CALLBACK_TYPE | None = None

    async def _async_update_data(self) -> dict[str, Any]:
        days = self.config_entry.options.get(
            CONF_EXPIRATION_ALERT_DAYS, DEFAULT_EXPIRATION_ALERT_DAYS
        )
        data = await self.hass.async_add_executor_job(
            partial(self.manager.summary, expiration_alert_days=days,
                    tz=dt_util.DEFAULT_TIME_ZONE)
        )
        self._schedule_food_day_rollover()
        return data

    @callback
    def _schedule_food_day_rollover(self) -> None:
        """Wake up at the next 04:00, so a day with no activity still turns.

        Rescheduled after every refresh rather than once at setup: the house's
        timezone can change, and a daylight-saving shift moves the next
        boundary by an hour without anything else telling us.
        """
        if self._food_day_unsub is not None:
            self._food_day_unsub()
        _, end = food_day_bounds(dt_util.utcnow(), dt_util.DEFAULT_TIME_ZONE)
        when = datetime.fromisoformat(end).replace(tzinfo=UTC) + timedelta(seconds=1)
        self._food_day_unsub = async_track_point_in_utc_time(
            self.hass, self._on_food_day_rollover, when)

    @callback
    def _on_food_day_rollover(self, _now: datetime) -> None:
        self._food_day_unsub = None
        self.hass.async_create_task(self.async_request_refresh())

    async def async_shutdown(self) -> None:
        """Drop the rendezvous with the entry: a timer left behind would call
        back into a coordinator nobody owns any more."""
        if self._food_day_unsub is not None:
            self._food_day_unsub()
            self._food_day_unsub = None
        await super().async_shutdown()
```

> La seconde de marge sur `when` n'est pas de la superstition : la borne rendue est l'instant **exclu** de la journée qui finit. Se réveiller exactement dessus laisse `food_day_of` sur la frontière, et un arrondi à la seconde près déciderait du jour affiché.

Vérifier que `async_shutdown` est bien appelé au déchargement de l'entrée ; sinon, ajouter l'appel dans `async_unload_entry` de `__init__.py`.

- [ ] **Step 4: Lancer, vérifier le succès**

Run: `./scripts/test.sh -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/home_stock/coordinator.py custom_components/home_stock/__init__.py tests/test_coordinator_foodday.py
git commit -m "feat: the food day turns at four, even on a quiet day"
```

---

## Task 9: Les onze capteurs

**Files:**
- Modify: `custom_components/home_stock/sensor.py`
- Modify: `custom_components/home_stock/translations/fr.json`
- Test: `tests/test_entities.py`

**Interfaces:**
- Consomme : `coordinator.data["today"]`, `coordinator.data["cost_waste_total"]` (tâche 7).
- Produit : les entités listées ci-dessous.

| Clé | Unité | `state_class` | Activé |
|---|---|---|---|
| `kcal_today` | `kcal` | `TOTAL` + `last_reset` | oui |
| `proteins_today`, `sugars_today`, `salt_today` | `g` | `TOTAL` + `last_reset` | oui |
| `cost_today` | `EUR` | `TOTAL` + `last_reset` | oui |
| `carbohydrates_today`, `added_sugars_today`, `fat_today`, `saturated_fat_today`, `fiber_today` | `g` | `TOTAL` + `last_reset` | **non** |
| `cost_waste_total` | `EUR` | `TOTAL_INCREASING` | oui |

- [ ] **Step 1: Écrire les tests**

Ajouter à `tests/test_entities.py` :

```python
async def test_the_four_daily_nutrients_are_on_by_default(hass, setup_entry):
    await setup_entry()
    for key in ("kcal_today", "proteins_today", "sugars_today", "salt_today",
                "cost_today", "cost_waste_total"):
        assert hass.states.get(f"sensor.home_stock_{key}") is not None, key


async def test_the_five_rarer_nutrients_are_created_but_disabled(hass, setup_entry):
    """Ils existent dans le registre et s'allument d'un clic — mais ils ne
    remplissent pas la barre latérale de colonnes souvent creuses."""
    entry = await setup_entry()
    registry = er.async_get(hass)
    for key in ("carbohydrates_today", "added_sugars_today", "fat_today",
                "saturated_fat_today", "fiber_today"):
        entity_id = f"sensor.home_stock_{key}"
        assert hass.states.get(entity_id) is None, key
        record = registry.async_get(entity_id)
        assert record is not None and record.disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_kcal_today_reports_the_day_and_its_gaps(hass, setup_entry):
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager
    await hass.async_add_executor_job(
        lambda: manager.add_stock(article_id=1, quantity=500.0, location_id=1))
    await hass.async_add_executor_job(
        lambda: manager.consume(product_id=1, quantity=100.0))
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get("sensor.home_stock_kcal_today")
    assert state.attributes["unvalued_movements"] == 0
    assert state.attributes["food_day"] == entry.runtime_data.coordinator.data["today"]["food_day"]
    assert state.attributes["last_reset"] is not None


async def test_the_daily_sensors_declare_a_last_reset(hass, setup_entry):
    """`TOTAL` sans `last_reset`, une chute de 1 800 à 0 serait lue comme un
    débordement de compteur et gonflerait les statistiques."""
    entry = await setup_entry()
    state = hass.states.get("sensor.home_stock_cost_today")
    assert state.attributes["state_class"] == "total"
    assert state.attributes["last_reset"].startswith(
        entry.runtime_data.coordinator.data["today"]["food_day"][:4])
```

Importer `from homeassistant.helpers import entity_registry as er` en tête si absent.

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `./scripts/test.sh tests/test_entities.py -q`
Expected: FAIL — `sensor.home_stock_kcal_today` n'existe pas.

- [ ] **Step 3: Écrire les capteurs**

Dans `sensor.py` :

```python
# The nine daily nutrient sensors: key, the key inside coordinator.data["today"],
# its unit, and whether it is worth a slot in the sidebar out of the box. The
# five disabled ones exist in the registry and turn on with one click; their
# long-term history starts then, which is the announced price (spec 11).
DAILY_NUTRIENTS: Final = (
    ("kcal_today", "kcal", "kcal", True),
    ("proteins_today", "proteins", "g", True),
    ("sugars_today", "sugars", "g", True),
    ("salt_today", "salt", "g", True),
    ("carbohydrates_today", "carbohydrates", "g", False),
    ("added_sugars_today", "added_sugars", "g", False),
    ("fat_today", "fat", "g", False),
    ("saturated_fat_today", "saturated_fat", "g", False),
    ("fiber_today", "fiber", "g", False),
)


class DailyTotalSensor(HomeStockEntity, SensorEntity):
    """One nutrient (or the money) over the current food day, 04:00 to 04:00.

    Declared TOTAL with an explicit `last_reset` rather than TOTAL_INCREASING:
    this counter really does drop back to zero every morning, and saying so is
    what stops Home Assistant reading that drop as a meter rollover.

    Its native daily statistic is still cut at midnight — Home Assistant has no
    other bucket. The panel is the authority for the 04:00 day (spec 4, A1).
    """

    _attr_state_class = SensorStateClass.TOTAL

    def __init__(self, coordinator: HomeStockCoordinator, key: str,
                 field: str, unit: str, *, enabled: bool = True) -> None:
        super().__init__(coordinator, key, ENTITY_ID_FORMAT)
        self._field = field
        self._attr_native_unit_of_measurement = unit
        self._attr_entity_registry_enabled_default = enabled

    @property
    def native_value(self) -> float:
        return self.coordinator.data["today"][self._field]

    @property
    def last_reset(self) -> datetime:
        """04:00 local of the current food day, as an aware datetime."""
        start, _ = food_day_bounds(dt_util.utcnow(), dt_util.DEFAULT_TIME_ZONE)
        return datetime.fromisoformat(start).replace(tzinfo=UTC)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "food_day": self.coordinator.data["today"]["food_day"],
            # A day at 1 800 kcal with three unvalued outings is not the same
            # information as a complete one (spec 8).
            "unvalued_movements": self.coordinator.data["today"]["unvalued"],
        }


class CostWasteTotalSensor(HomeStockEntity, SensorEntity):
    """Cumulative cost of what was thrown away or expired.

    Split out of cost_total at lot 2: what you waste is a figure worth seeing,
    not one to drown in what you ate (spec 4, A2).
    """

    _attr_native_unit_of_measurement = "EUR"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator: HomeStockCoordinator) -> None:
        super().__init__(coordinator, "cost_waste_total", ENTITY_ID_FORMAT)

    @property
    def native_value(self) -> float:
        return self.coordinator.data["cost_waste_total"]
```

Dans `async_setup_entry`, ajouter à la liste :

```python
        *(DailyTotalSensor(coordinator, key, field, unit, enabled=enabled)
          for key, field, unit, enabled in DAILY_NUTRIENTS),
        DailyTotalSensor(coordinator, "cost_today", "cost", "EUR"),
        CostWasteTotalSensor(coordinator),
```

Mettre à jour le docstring de `KcalTotalSensor` : la mention d'un `utility_meter` au lot 2 est caduque, remplacer par « ne compte que la consommation, pondérée par la part mangée (lot 2, amendement A2) ».

Dans `translations/fr.json`, sous `entity.sensor` :

```json
"kcal_today": { "name": "Kilocalories du jour" },
"proteins_today": { "name": "Protéines du jour" },
"carbohydrates_today": { "name": "Glucides du jour" },
"sugars_today": { "name": "Sucres du jour" },
"added_sugars_today": { "name": "Sucres ajoutés du jour" },
"fat_today": { "name": "Matières grasses du jour" },
"saturated_fat_today": { "name": "Graisses saturées du jour" },
"fiber_today": { "name": "Fibres du jour" },
"salt_today": { "name": "Sel du jour" },
"cost_today": { "name": "Dépense alimentaire du jour" },
"cost_waste_total": { "name": "Coût du gaspillage" }
```

- [ ] **Step 4: Lancer toute la suite**

Run: `./scripts/test.sh -q`
Expected: PASS

- [ ] **Step 5: Vérifier que le test a des dents (mutation)**

Passer `enabled=True` pour `fiber_today` dans `DAILY_NUTRIENTS`. Relancer : `test_the_five_rarer_nutrients_are_created_but_disabled` doit tomber. Remettre `False`.

- [ ] **Step 6: Commit**

```bash
git add custom_components/home_stock/sensor.py custom_components/home_stock/translations/fr.json tests/test_entities.py
git commit -m "feat: eleven sensors for the food day and for what was wasted"
```

---

## Task 10: L'entité `event` et le blueprint

**Files:**
- Create: `custom_components/home_stock/event.py`
- Create: `blueprints/automation/home_stock/dlc_bleuenn.yaml`
- Modify: `custom_components/home_stock/storage/repositories.py`
- Modify: `custom_components/home_stock/application.py`
- Modify: `custom_components/home_stock/__init__.py` (ajouter `Platform.EVENT`)
- Modify: `custom_components/home_stock/translations/fr.json`
- Test: `tests/test_event_expiration.py` (créer)

**Interfaces:**
- Produit :
  - `repo.expiry_candidates(conn, limit: str) -> list[dict]`
  - `repo.mark_expiry_announced(conn, batch_id: int, stage: str) -> None`
  - `StockManager.claim_expiry_announcements(*, expiration_alert_days: int, today: str | None = None) -> list[tuple[str, list[dict]]]`
  - `event.home_stock_expiration`, types `approaching` et `expired`.

**Pourquoi l'entité réclame elle-même.** Le premier rafraîchissement du coordinateur a lieu **avant** que les plateformes ne soient montées : si c'était lui qui marquait les lots, une installation neuve marquerait tout son arriéré comme annoncé sans que personne n'ait rien entendu. C'est donc l'entité, une fois vivante, qui réclame — et le marquage n'a lieu que quand une annonce part vraiment.

- [ ] **Step 1: Écrire les tests**

Créer `tests/test_event_expiration.py` :

```python
"""L'annonce des péremptions : une fois, et une seule."""
import pytest


async def test_a_batch_entering_the_window_is_announced_once(hass, setup_entry):
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager
    await hass.async_add_executor_job(lambda: manager.add_stock(
        article_id=1, quantity=500.0, location_id=1, best_before="2026-08-21"))
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get("event.home_stock_expiration")
    assert state.attributes["event_type"] == "approaching"
    assert state.attributes["count"] == 1
    first_fired = state.state

    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    # Rien de neuf : l'état ne bouge pas, on ne réannonce pas les mêmes yaourts.
    assert hass.states.get("event.home_stock_expiration").state == first_fired


async def test_the_stage_survives_a_restart(hass, setup_entry):
    """L'étape est en base, pas en mémoire : sinon chaque redémarrage de Home
    Assistant réannoncerait tout le frigo."""
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager
    await hass.async_add_executor_job(lambda: manager.add_stock(
        article_id=1, quantity=500.0, location_id=1, best_before="2026-08-21"))

    claimed = await hass.async_add_executor_job(
        lambda: manager.claim_expiry_announcements(expiration_alert_days=3,
                                                   today="2026-08-20"))
    assert [stage for stage, _ in claimed] == ["approaching"]

    again = await hass.async_add_executor_job(
        lambda: manager.claim_expiry_announcements(expiration_alert_days=3,
                                                   today="2026-08-20"))
    assert again == []


async def test_the_second_stage_is_announced_when_the_date_passes(hass, setup_entry):
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager
    await hass.async_add_executor_job(lambda: manager.add_stock(
        article_id=1, quantity=500.0, location_id=1, best_before="2026-08-21"))

    await hass.async_add_executor_job(
        lambda: manager.claim_expiry_announcements(expiration_alert_days=3,
                                                   today="2026-08-20"))
    claimed = await hass.async_add_executor_job(
        lambda: manager.claim_expiry_announcements(expiration_alert_days=3,
                                                   today="2026-08-22"))
    assert [stage for stage, _ in claimed] == ["expired"]


async def test_the_stage_never_goes_backwards(hass, setup_entry):
    """Une date limite ne redevient pas proche après être passée — et une
    horloge qui recule (fuseau corrigé, sauvegarde restaurée) ne doit pas
    faire réannoncer."""
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager
    await hass.async_add_executor_job(lambda: manager.add_stock(
        article_id=1, quantity=500.0, location_id=1, best_before="2026-08-21"))

    await hass.async_add_executor_job(
        lambda: manager.claim_expiry_announcements(expiration_alert_days=3,
                                                   today="2026-08-22"))
    claimed = await hass.async_add_executor_job(
        lambda: manager.claim_expiry_announcements(expiration_alert_days=3,
                                                   today="2026-08-20"))
    assert claimed == []


async def test_several_batches_are_announced_in_one_event(hass, setup_entry):
    """Une phrase « trois choses périment », pas trois phrases — et surtout
    pas trois états écrits dans la même seconde."""
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager
    for _ in range(3):
        await hass.async_add_executor_job(lambda: manager.add_stock(
            article_id=1, quantity=100.0, location_id=1, best_before="2026-08-21"))

    claimed = await hass.async_add_executor_job(
        lambda: manager.claim_expiry_announcements(expiration_alert_days=3650,
                                                   today="2026-08-20"))
    assert len(claimed) == 1
    stage, batches = claimed[0]
    assert stage == "approaching" and len(batches) == 3
    assert batches[0]["product_name"]
    assert batches[0]["display"]


async def test_a_batch_with_no_date_is_never_announced(hass, setup_entry):
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager
    await hass.async_add_executor_job(lambda: manager.add_stock(
        article_id=1, quantity=500.0, location_id=1))
    claimed = await hass.async_add_executor_job(
        lambda: manager.claim_expiry_announcements(expiration_alert_days=3650,
                                                   today="2026-08-20"))
    assert claimed == []
```

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `./scripts/test.sh tests/test_event_expiration.py -q`
Expected: FAIL — `'StockManager' object has no attribute 'claim_expiry_announcements'`

- [ ] **Step 3: Écrire les dépôts et l'application**

Dans `repositories.py` :

```python
def expiry_candidates(conn, limit: str) -> list[dict[str, Any]]:
    """Open batches with a date on or before `limit`, and what has already
    been announced about each one."""
    return _rows(conn.execute(
        "SELECT b.id, b.best_before, b.remaining, b.expiry_announced_stage,"
        "       p.name AS product_name, p.base_unit"
        " FROM batch b"
        " JOIN article a ON a.id = b.article_id"
        " JOIN product p ON p.id = a.product_id"
        " WHERE b.closed_at IS NULL AND b.best_before IS NOT NULL"
        "   AND b.best_before <= ?"
        " ORDER BY b.best_before, b.id",
        (limit,),
    ))


def mark_expiry_announced(conn, batch_id: int, stage: str) -> None:
    conn.execute("UPDATE batch SET expiry_announced_stage = ? WHERE id = ?",
                 (stage, batch_id))
```

Dans `application.py` :

```python
# The two stages of an expiry announcement, in the only order they may occur.
EXPIRY_STAGES: Final = ("approaching", "expired")


    def claim_expiry_announcements(
        self, *, expiration_alert_days: int, today: str | None = None,
    ) -> list[tuple[str, list[dict[str, Any]]]]:
        """What has just crossed a threshold, marked as announced on the way out.

        Claiming and marking happen in ONE write transaction: an announcement
        read but not marked would be repeated at the next refresh, which is
        the exact failure this method exists to prevent.

        A stage never goes backwards. A batch already announced as `expired`
        stays there even if the clock moves back — a corrected timezone or a
        restored backup must not re-announce the whole fridge.
        """
        reference = date.fromisoformat(today) if today else datetime.now(UTC).date()
        limit = (reference + timedelta(days=expiration_alert_days)).isoformat()
        claimed: dict[str, list[dict[str, Any]]] = {stage: [] for stage in EXPIRY_STAGES}
        with self.db.write() as conn:
            for row in repo.expiry_candidates(conn, limit):
                stage = ("expired" if date.fromisoformat(row["best_before"]) < reference
                         else "approaching")
                already = row["expiry_announced_stage"]
                if already is not None and (
                        already == stage
                        or EXPIRY_STAGES.index(already) > EXPIRY_STAGES.index(stage)):
                    continue
                repo.mark_expiry_announced(conn, row["id"], stage)
                claimed[stage].append({
                    "batch_id": row["id"],
                    "product_name": row["product_name"],
                    "best_before": row["best_before"],
                    "display": format_quantity(row["remaining"], row["base_unit"]),
                })
        return [(stage, batches) for stage, batches in claimed.items() if batches]
```

- [ ] **Step 4: Écrire l'entité**

Créer `custom_components/home_stock/event.py` :

```python
"""One event entity for expiry announcements.

Grouped: one event per stage per refresh, carrying the list of batches. Firing
once per batch would put several state writes in the same second — and would
make a voice assistant say three sentences where one ("three things are going
off") is what a person wants.
"""
from __future__ import annotations

from functools import partial

from homeassistant.components.event import ENTITY_ID_FORMAT, EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeStockConfigEntry
from .application import EXPIRY_STAGES
from .const import CONF_EXPIRATION_ALERT_DAYS, DEFAULT_EXPIRATION_ALERT_DAYS
from .coordinator import HomeStockCoordinator
from .entity import HomeStockEntity


class ExpirationEventEntity(HomeStockEntity, EventEntity):
    _attr_event_types = list(EXPIRY_STAGES)

    def __init__(self, coordinator: HomeStockCoordinator) -> None:
        super().__init__(coordinator, "expiration", ENTITY_ID_FORMAT)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # The coordinator's first refresh happens before the platforms are set
        # up: claiming there would mark a fresh install's whole backlog as
        # announced with nobody listening. The entity claims, once it exists.
        await self._announce()

    @callback
    def _handle_coordinator_update(self) -> None:
        self.hass.async_create_task(self._announce())

    async def _announce(self) -> None:
        days = self.coordinator.config_entry.options.get(
            CONF_EXPIRATION_ALERT_DAYS, DEFAULT_EXPIRATION_ALERT_DAYS)
        claimed = await self.hass.async_add_executor_job(partial(
            self.coordinator.manager.claim_expiry_announcements,
            expiration_alert_days=days))
        for stage, batches in claimed:
            self._trigger_event(stage, {"count": len(batches), "batches": batches})
            self.async_write_ha_state()


async def async_setup_entry(hass: HomeAssistant, entry: HomeStockConfigEntry,
                            async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities([ExpirationEventEntity(entry.runtime_data.coordinator)])
```

Ajouter `Platform.EVENT` à la liste `PLATFORMS` de `__init__.py`, et dans `translations/fr.json`, sous `entity` :

```json
"event": { "expiration": { "name": "Péremption" } }
```

- [ ] **Step 5: Lancer, vérifier le succès**

Run: `./scripts/test.sh tests/test_event_expiration.py -q`
Expected: PASS

- [ ] **Step 6: Écrire le blueprint**

Créer `blueprints/automation/home_stock/dlc_bleuenn.yaml` :

```yaml
blueprint:
  name: Garde-manger — annonce des dates limites
  description: >-
    Chaque jour à l'heure choisie, fait annoncer par l'assistant conversationnel
    ce qui approche de sa date limite.

    Déclencheur horaire volontaire : le composant constate un basculement au
    moment où son coordinateur se rafraîchit, parfois à trois heures du matin.
    Ce qu'un foyer veut, c'est « chaque soir, dis-moi ce qui périme ».
    L'entité `event.home_stock_expiration` reste disponible pour qui préfère
    écrire une automation qui réagit à l'instant même.

    À importer une fois ; ce fichier n'est jamais installé par l'intégration.
  domain: automation
  input:
    heure:
      name: Heure de l'annonce
      default: "18:00:00"
      selector:
        time:
    agent:
      name: Agent conversationnel
      default: conversation.personas_studio_home_manager
      selector:
        entity:
          domain: conversation
    capteur:
      name: Capteur de péremptions
      default: binary_sensor.home_stock_expirations
      selector:
        entity:
          domain: binary_sensor

triggers:
  - trigger: time
    at: !input heure

conditions:
  - condition: state
    entity_id: !input capteur
    state: "on"

actions:
  - action: conversation.process
    data:
      agent_id: !input agent
      text: >-
        {% set lots = state_attr(nom_capteur, 'batches') or [] %}
        Dans le garde-manger, {{ lots | count }}
        {{ 'article approche de sa date limite' if lots | count == 1
           else 'articles approchent de leur date limite' }} :
        {{ lots | map(attribute='product_name') | join(', ') }}.
    variables:
      nom_capteur: !input capteur
```

> Le `variables:` sert à rendre `!input capteur` lisible depuis le modèle Jinja : un `!input` ne s'interpole pas à l'intérieur d'un template, il doit passer par une variable. Vérifier ce point en chargeant le blueprint dans le conteneur de test, **jamais** dans l'instance du foyer.

- [ ] **Step 7: Vérifier le blueprint sans toucher à la maison**

Run: `./scripts/test.sh tests/test_event_expiration.py -q -k blueprint` après avoir ajouté :

```python
def test_the_blueprint_is_valid_yaml_and_declares_its_inputs():
    import yaml
    from pathlib import Path
    path = Path(__file__).resolve().parent.parent / "blueprints" / "automation" \
        / "home_stock" / "dlc_bleuenn.yaml"
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert document["blueprint"]["domain"] == "automation"
    assert set(document["blueprint"]["input"]) == {"heure", "agent", "capteur"}
    assert document["triggers"][0]["trigger"] == "time"
```

Ce test ne charge pas Home Assistant : il vérifie que le fichier est bien formé et complet. Le comportement réel se vérifiera à l'import, qui est le geste du propriétaire.

- [ ] **Step 8: Lancer toute la suite**

Run: `./scripts/test.sh -q`
Expected: PASS

- [ ] **Step 9: Vérifier que le test a des dents (mutation)**

Dans `claim_expiry_announcements`, supprimer l'appel à `repo.mark_expiry_announced`. Relancer : `test_the_stage_survives_a_restart` doit tomber. Remettre.

- [ ] **Step 10: Commit**

```bash
git add custom_components/home_stock/ blueprints/ tests/test_event_expiration.py
git commit -m "feat: expiry announcements fire once, and a blueprint carries them to Bleuenn"
```

---

## Task 11: Les commandes websocket

**Files:**
- Modify: `custom_components/home_stock/websocket_api.py`
- Test: `tests/test_websocket_consume.py` (créer), `tests/test_offline_queue_contract.py`

**Interfaces:**
- Consomme : `StockManager.consume/consume_batch` avec parts (tâche 5) ; `journal_day` / `journal_series` (tâche 7) ; `repo.learned_portion` (tâche 6).
- Produit :

| Commande | Entrée | Sortie |
|---|---|---|
| `home_stock/stock/consume` | `product_id`, `quantity`, `reason?`, `batch_id?`, `parts_total?`, `parts_mine?`, `idempotency_key?` | `{movement_ids}` |
| `home_stock/journal/day` | `date?` | `{food_day, start, end, entries, totals}` |
| `home_stock/journal/series` | `granularity`, `count` | `{granularity, buckets}` |
| `home_stock/product/get` | *étendu* | gagne `suggested_portion`, `portion_source`, `serving_quantity`, `next_batch` |

**Décision de plan.** La spec §14.1 dit « `product/get` étendu ». L'écran « manger » a besoin, en un aller-retour, du lot que le FIFO va viser : `next_batch` est donc ajouté à cette même réponse plutôt qu'inventé en commande séparée. `portion_source` (`"learned"` \| `"serving"` \| `null`) accompagne la portion pour que le bouton puisse dire d'où vient son chiffre.

- [ ] **Step 1: Écrire les tests**

Créer `tests/test_websocket_consume.py`. Reprendre le motif d'un fichier existant (`tests/test_websocket_write.py`) pour la fixture de connexion websocket.

```python
"""Sortie de stock et journal, vus du panneau."""
import pytest


async def test_consume_takes_from_the_fifo_batch(hass, hass_ws_client, setup_entry):
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager
    await hass.async_add_executor_job(
        lambda: manager.add_stock(article_id=1, quantity=500.0, location_id=1))
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({
        "type": "home_stock/stock/consume", "product_id": 1, "quantity": 200.0})
    answer = await client.receive_json()

    assert answer["success"]
    assert len(answer["result"]["movement_ids"]) == 1


async def test_consume_records_the_parts(hass, hass_ws_client, setup_entry):
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager
    await hass.async_add_executor_job(
        lambda: manager.add_stock(article_id=1, quantity=500.0, location_id=1))
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({
        "type": "home_stock/stock/consume", "product_id": 1, "quantity": 400.0,
        "parts_total": 4, "parts_mine": 1})
    assert (await client.receive_json())["success"]

    row = await hass.async_add_executor_job(lambda: manager.db.read().execute(
        "SELECT parts_total, parts_mine FROM movement"
        " WHERE reason = 'consumption'").fetchone())
    assert (row["parts_total"], row["parts_mine"]) == (4, 1)


async def test_consume_refuses_more_parts_eaten_than_served(hass, hass_ws_client,
                                                            setup_entry):
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager
    await hass.async_add_executor_job(
        lambda: manager.add_stock(article_id=1, quantity=500.0, location_id=1))
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({
        "type": "home_stock/stock/consume", "product_id": 1, "quantity": 100.0,
        "parts_total": 2, "parts_mine": 3})
    answer = await client.receive_json()

    assert not answer["success"]
    # Un message montrable tel quel à quelqu'un debout dans sa cuisine.
    assert answer["error"]["code"] in ("invalid_field", "invalid_value")


async def test_consume_refuses_a_batch_of_another_product(hass, hass_ws_client,
                                                          setup_entry):
    """Le couple incohérent est refusé plutôt que d'accorder sa confiance à
    l'un des deux."""
    entry = await setup_entry(with_article=True, with_piece_product=True)
    manager = entry.runtime_data.manager
    batch_id = await hass.async_add_executor_job(
        lambda: manager.add_stock(article_id=1, quantity=500.0, location_id=1))
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({
        "type": "home_stock/stock/consume", "product_id": 2, "quantity": 1.0,
        "batch_id": batch_id})
    answer = await client.receive_json()
    assert not answer["success"]


async def test_consume_is_idempotent(hass, hass_ws_client, setup_entry):
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager
    await hass.async_add_executor_job(
        lambda: manager.add_stock(article_id=1, quantity=500.0, location_id=1))
    client = await hass_ws_client(hass)

    for _ in range(2):
        await client.send_json_auto_id({
            "type": "home_stock/stock/consume", "product_id": 1, "quantity": 100.0,
            "idempotency_key": "abc"})
        assert (await client.receive_json())["success"]

    count = await hass.async_add_executor_job(lambda: manager.db.read().execute(
        "SELECT COUNT(*) FROM movement WHERE reason = 'consumption'").fetchone()[0])
    assert count == 1


async def test_consume_refuses_an_insufficient_stock_in_french(hass, hass_ws_client,
                                                               setup_entry):
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager
    await hass.async_add_executor_job(
        lambda: manager.add_stock(article_id=1, quantity=50.0, location_id=1))
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({
        "type": "home_stock/stock/consume", "product_id": 1, "quantity": 500.0})
    answer = await client.receive_json()
    assert not answer["success"]
    assert not answer["error"]["message"].isascii() or "stock" in answer["error"]["message"]


async def test_journal_day_answers_the_current_food_day(hass, hass_ws_client,
                                                        setup_entry):
    await setup_entry()
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "home_stock/journal/day"})
    answer = await client.receive_json()
    assert answer["success"]
    assert set(answer["result"]) >= {"food_day", "start", "end", "entries", "totals"}


async def test_journal_series_refuses_an_unknown_granularity(hass, hass_ws_client,
                                                             setup_entry):
    await setup_entry()
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({
        "type": "home_stock/journal/series", "granularity": "fortnight", "count": 3})
    assert not (await client.receive_json())["success"]


async def test_journal_series_bounds_the_count(hass, hass_ws_client, setup_entry):
    """Douze mois de barres, pas dix mille : la commande borne, elle ne fait
    pas confiance au client."""
    await setup_entry()
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({
        "type": "home_stock/journal/series", "granularity": "day", "count": 5000})
    assert not (await client.receive_json())["success"]


async def test_product_get_carries_the_portion_and_the_next_batch(hass, hass_ws_client,
                                                                  setup_entry):
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager
    await hass.async_add_executor_job(
        lambda: manager.add_stock(article_id=1, quantity=500.0, location_id=1))
    await hass.async_add_executor_job(lambda: manager.db.write().__enter__().execute(
        "UPDATE article SET serving_quantity = 125 WHERE id = 1"))
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "home_stock/product/get", "product_id": 1})
    result = (await client.receive_json())["result"]

    assert result["suggested_portion"] == 125.0
    assert result["portion_source"] == "serving"
    assert result["next_batch"]["remaining"] == 500.0


async def test_the_learned_portion_beats_the_open_food_facts_one(hass, hass_ws_client,
                                                                 setup_entry):
    """Ce que tu manges vraiment vaut mieux que ce que le fabricant appelle
    une portion."""
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager
    await hass.async_add_executor_job(
        lambda: manager.add_stock(article_id=1, quantity=2000.0, location_id=1))
    for _ in range(3):
        await hass.async_add_executor_job(
            lambda: manager.consume(product_id=1, quantity=80.0))
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "home_stock/product/get", "product_id": 1})
    result = (await client.receive_json())["result"]
    assert result["suggested_portion"] == 80.0
    assert result["portion_source"] == "learned"
```

Dans `tests/test_offline_queue_contract.py`, ajouter `"home_stock/stock/consume"` à `EXPECTED_QUEUED_COMMAND_TYPES`.

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `./scripts/test.sh tests/test_websocket_consume.py -q`
Expected: FAIL — commande `home_stock/stock/consume` inconnue.

- [ ] **Step 3: Écrire les commandes**

Dans `websocket_api.py`, d'abord les imports que ces commandes exigent et qui
n'y sont pas encore — `from datetime import date`, `from .domain.stock import
InsufficientStock, sort_batches`, `from .application import PartsError,
_as_batch_view` :

```python
from .application import PartsError
from .domain.foodday import GRANULARITIES
from .validators import parts_count

_PARTS: Final = parts_count
# Twelve months of monthly bars, fourteen days of daily ones: past that the
# panel is not drawing a graph, it is fetching a year of journal to throw away.
MAX_SERIES_COUNT: Final = 60


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/stock/consume",
    vol.Required("product_id"): _bounded_int,
    vol.Required("quantity"): _finite_float,
    vol.Optional("reason", default=REASON_CONSUMPTION): vol.In(CONSUME_REASONS),
    vol.Optional("batch_id"): _bounded_int,
    vol.Optional("parts_total"): _PARTS,
    vol.Optional("parts_mine"): _PARTS,
    vol.Optional("idempotency_key"): _bounded_text,
})
@websocket_api.async_response
async def stock_consume(hass, connection, msg) -> None:
    """Declare that something was eaten, thrown away, or found expired.

    With a batch_id, that precise batch is taken from — the panel's "manger"
    screen always targets the batch FIFO would pick, and says so. Without one,
    the consumption walks the batches in FIFO order and may span several.
    product_id stays required either way: the pair is checked rather than one
    of the two being trusted.
    """
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return

    parts = (msg.get("parts_total"), msg.get("parts_mine"))
    try:
        if "batch_id" in msg:
            result = await hass.async_add_executor_job(partial(
                runtime.manager.consume_batch, msg["batch_id"],
                product_id=msg["product_id"], quantity=msg["quantity"],
                reason=msg["reason"], parts_total=parts[0], parts_mine=parts[1],
                idempotency_key=msg.get("idempotency_key")))
            movement_ids = [result]
        else:
            movement_ids = await hass.async_add_executor_job(partial(
                runtime.manager.consume, product_id=msg["product_id"],
                quantity=msg["quantity"], reason=msg["reason"],
                parts_total=parts[0], parts_mine=parts[1],
                idempotency_key=msg.get("idempotency_key")))
    except (LookupError, PartsError, InsufficientStock, UnitError, ValueError,
            OverflowError) as err:
        _send_domain_error(connection, msg["id"], err)
        return
    except sqlite3.IntegrityError as err:
        _send_integrity_error(connection, msg["id"], err)
        return

    await runtime.coordinator.async_request_refresh()
    connection.send_result(msg["id"], {"movement_ids": movement_ids})


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/journal/day",
    vol.Optional("date"): _iso_date,
})
@websocket_api.async_response
async def journal_day(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    day = date.fromisoformat(msg["date"]) if msg.get("date") else None
    result = await _read(hass, partial(
        runtime.manager.journal_day, day, tz=dt_util.DEFAULT_TIME_ZONE))
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/journal/series",
    vol.Required("granularity"): vol.In(GRANULARITIES),
    vol.Required("count"): vol.All(_bounded_int, vol.Range(min=1, max=MAX_SERIES_COUNT)),
})
@websocket_api.async_response
async def journal_series(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    result = await _read(hass, partial(
        runtime.manager.journal_series, msg["granularity"], msg["count"],
        tz=dt_util.DEFAULT_TIME_ZONE))
    connection.send_result(msg["id"], result)
```

`_read` prend un callable synchrone ; si sa signature ne l'accepte pas tel quel, utiliser `hass.async_add_executor_job` comme le font les commandes d'écriture.

Étendre `product_get` : après avoir lu le produit,

```python
    conn = runtime.manager.db.read()
    learned = await _read(hass, partial(repo.learned_portion, conn, msg["product_id"]))
    batches = await _read(hass, partial(repo.list_batches_for_product, conn,
                                        msg["product_id"]))
    next_batch = next(iter(sort_batches([_as_batch_view(row) for row in batches])), None)
    serving = None
    if next_batch is not None:
        serving = next(row["serving_quantity"] for row in batches
                       if row["id"] == next_batch.id)
    suggested, source = ((learned, "learned") if learned is not None
                         else (serving, "serving") if serving is not None
                         else (None, None))
    connection.send_result(msg["id"], {
        "product": product,
        "suggested_portion": suggested,
        "portion_source": source,
        "serving_quantity": serving,
        "next_batch": None if next_batch is None else {
            "id": next_batch.id, "remaining": next_batch.remaining,
            "best_before": next_batch.best_before.isoformat()
                           if next_batch.best_before else None,
        },
    })
```

`sort_batches` et `_as_batch_view` viennent de `domain.stock` et de `application` : les importer, plutôt que de retrier ici selon d'autres règles que le FIFO réel. `_as_batch_view` est aujourd'hui privé au module `application` — le renommer `as_batch_view` et corriger ses trois appels internes, plutôt que d'importer un nom souligné depuis un autre module. `list_batches_for_product` doit rapporter `a.serving_quantity` — l'ajouter à son `SELECT`.

**`CONSUME_REASONS` déménage.** Le tuple des trois motifs qu'une sortie peut porter vit aujourd'hui dans `services.py`. Le websocket en a besoin pour le même schéma : le déplacer dans `const.py`, à côté de `REASONS` et de `COUNTED_REASONS`, et l'importer des deux côtés. Importer depuis `services.py` mettrait la surface la plus récente à la merci de la plus ancienne.

`consume_batch` gagne un paramètre `product_id: int | None = None` : quand il est fourni, la méthode refuse (`ValueError`) un lot dont l'article n'appartient pas à ce produit.

Enregistrer les trois commandes dans `async_register_websocket`.

- [ ] **Step 4: Lancer toute la suite**

Run: `./scripts/test.sh -q`
Expected: PASS

- [ ] **Step 5: Vérifier que les tests ont des dents (mutation)**

Retirer `vol.Range(min=1, max=MAX_SERIES_COUNT)` du schéma de `journal/series`. Relancer : `test_journal_series_bounds_the_count` doit tomber. Remettre.

- [ ] **Step 6: Commit**

```bash
git add custom_components/home_stock/websocket_api.py custom_components/home_stock/storage/repositories.py tests/
git commit -m "feat: consume, read a day, read a series, from the panel"
```

---

## Task 12: Les services

**Files:**
- Modify: `custom_components/home_stock/services.py`
- Modify: `custom_components/home_stock/services.yaml`
- Test: `tests/test_services.py`

**Interface :** `home_stock.consume` gagne `batch_id`, `parts_total`, `parts_mine`.

**La règle qui gouverne cette tâche :** aucune des deux surfaces n'a le droit d'être la plus faible. Ce que le websocket refuse à la tâche 11, le service doit le refuser ici — un appel de service part d'une automation ou du vocal, et il est tout aussi capable d'écrire trois parts sur deux dans le journal append-only.

- [ ] **Step 1: Écrire les tests**

Ajouter à `tests/test_services.py` :

```python
async def test_the_consume_service_records_the_parts(hass, setup_entry):
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager
    await hass.async_add_executor_job(
        lambda: manager.add_stock(article_id=1, quantity=800.0, location_id=1))

    await hass.services.async_call(DOMAIN, "consume", {
        "product_id": 1, "quantity": 400.0, "parts_total": 4, "parts_mine": 1,
    }, blocking=True)

    row = await hass.async_add_executor_job(lambda: manager.db.read().execute(
        "SELECT parts_total, parts_mine FROM movement"
        " WHERE reason = 'consumption'").fetchone())
    assert (row["parts_total"], row["parts_mine"]) == (4, 1)


async def test_the_consume_service_refuses_impossible_parts(hass, setup_entry):
    """La même règle que le websocket, sur la surface la plus ancienne."""
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager
    await hass.async_add_executor_job(
        lambda: manager.add_stock(article_id=1, quantity=800.0, location_id=1))

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(DOMAIN, "consume", {
            "product_id": 1, "quantity": 100.0, "parts_total": 2, "parts_mine": 3,
        }, blocking=True)


@pytest.mark.parametrize("value", [1.5, "2", -1, 25])
async def test_the_consume_service_refuses_a_parts_value_the_schema_rejects(
        hass, setup_entry, value):
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager
    await hass.async_add_executor_job(
        lambda: manager.add_stock(article_id=1, quantity=800.0, location_id=1))

    with pytest.raises((vol.Invalid, HomeAssistantError)):
        await hass.services.async_call(DOMAIN, "consume", {
            "product_id": 1, "quantity": 100.0, "parts_total": value, "parts_mine": 1,
        }, blocking=True)


async def test_the_consume_service_can_target_one_batch(hass, setup_entry):
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager
    old = await hass.async_add_executor_job(
        lambda: manager.add_stock(article_id=1, quantity=100.0, location_id=1))
    recent = await hass.async_add_executor_job(
        lambda: manager.add_stock(article_id=1, quantity=100.0, location_id=1))

    await hass.services.async_call(DOMAIN, "consume", {
        "product_id": 1, "quantity": 50.0, "batch_id": recent,
    }, blocking=True)

    remaining = await hass.async_add_executor_job(lambda: dict(
        manager.db.read().execute("SELECT id, remaining FROM batch ORDER BY id")
        .fetchall()[1]))
    assert remaining["remaining"] == 50.0
```

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `./scripts/test.sh tests/test_services.py -q`
Expected: FAIL — `extra keys not allowed @ data['parts_total']`

- [ ] **Step 3: Étendre le service**

Dans `services.py` :

```python
CONSUME_SCHEMA = vol.Schema({
    vol.Required("product_id"): _id,
    vol.Required("quantity"): finite_float,
    vol.Optional("reason", default=REASON_CONSUMPTION): vol.In(CONSUME_REASONS),
    vol.Optional("batch_id"): _id,
    # parts_count, not `_id`: a number of plates is neither an identifier nor
    # a float that may truncate, and the websocket surface refuses exactly the
    # same values. Neither surface may be the weaker one.
    vol.Optional("parts_total"): parts_count,
    vol.Optional("parts_mine"): parts_count,
    vol.Optional("idempotency_key"): bounded_text,
})
```

Importer `parts_count` et `PartsError`, router `batch_id` vers `consume_batch` (avec `product_id` pour le contrôle de cohérence) et le cas général vers `consume`, et ajouter `PartsError` aux exceptions que `_run` traduit en `HomeAssistantError` française via `messages.french_message`.

Dans `services.yaml`, sous `consume:` :

```yaml
    batch_id:
      name: Lot
      description: Prendre dans ce lot précis plutôt que de suivre l'ordre FIFO.
      selector: { number: { min: 1, mode: box } }
    parts_total:
      name: Parts servies
      description: Nombre d'assiettes servies au total. À donner avec « parts mangées ».
      selector: { number: { min: 1, max: 24, mode: box } }
    parts_mine:
      name: Parts mangées
      description: Combien de ces assiettes sont les tiennes. Zéro est valide.
      selector: { number: { min: 0, max: 24, mode: box } }
```

Vérifier dans `messages.py` que `PartsError` obtient une phrase française : sinon l'ajouter, du genre « Les parts sont incohérentes : on ne mange pas plus de parts qu'il n'en a été servi. »

- [ ] **Step 4: Lancer toute la suite**

Run: `./scripts/test.sh -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/home_stock/services.py custom_components/home_stock/services.yaml custom_components/home_stock/messages.py tests/test_services.py
git commit -m "feat: the consume service learns parts and a target batch"
```

---

## Task 13: Les raccourcis de quantité, et la dette de la file d'attente

**Files:**
- Create: `frontend/src/portion.ts`
- Create: `frontend/src/nombres.ts`
- Modify: `frontend/src/file-attente.ts`
- Modify: `frontend/src/ecrans/catalogue.ts`, `panier.ts`, `rangement.ts`, `session.ts`
- Test: `frontend/tests/portion.test.ts` (créer), `frontend/tests/file-attente.test.ts`

**Interfaces:**
- Produit :
  - `nombres.ts` : `analyserNombre(saisie: string): ResultatNombre` (déplacé depuis `ecrans/catalogue.ts`), `formaterNombre(valeur: number): string`.
  - `portion.ts` : `raccourcisQuantite(restant: number, unite: UniteBase, portion: number | null): Raccourci[]` avec `Raccourci = { libelle: string; quantite: number }`.
  - `file-attente.ts` : `ajouter(type, charge): SuiviAction` avec `SuiviAction = { cle: string; sort: Promise<ResultatAction> }` et `ResultatAction = 'envoyee' | 'refusee' | 'en-attente'`. `resultatDe` et `viderResultats` **disparaissent**.

**Pourquoi la file change ici.** `file-attente.ts` porte depuis le lot 1 un commentaire qui nomme la correction et la reporte à ce lot : « la vraie correction n'est pas un verrou de plus : c'est un passage de relais **par clé** ». La course actuelle fait qu'un écran croit son action encore en file alors que le serveur l'a reçue. L'écran « manger » de la tâche 14 s'appuie sur ce retour pour savoir s'il peut se refermer : la dette se solde avant, pas après.

- [ ] **Step 1: Écrire les tests des raccourcis**

Créer `frontend/tests/portion.test.ts` :

```ts
import { describe, expect, it } from 'vitest';
import { raccourcisQuantite } from '../src/portion';

describe('raccourcisQuantite', () => {
  it('arme « 1 » pour un produit à la pièce', () => {
    const raccourcis = raccourcisQuantite(3, 'piece', null);
    expect(raccourcis[0]).toEqual({ libelle: '1 pièce', quantite: 1 });
  });

  it('ne propose jamais plus que ce qui reste', () => {
    const raccourcis = raccourcisQuantite(1, 'piece', null);
    expect(raccourcis.every((r) => r.quantite <= 1)).toBe(true);
  });

  it('propose la portion apprise en tête quand elle existe', () => {
    const [premier] = raccourcisQuantite(500, 'g', 125);
    expect(premier).toEqual({ libelle: '1 portion (125 g)', quantite: 125 });
  });

  it('n’invente pas de portion quand on n’en connaît aucune', () => {
    const libelles = raccourcisQuantite(500, 'g', null).map((r) => r.libelle);
    expect(libelles).toEqual(['La moitié (250 g)', 'Tout le reste (500 g)']);
  });

  it('n’affiche pas deux boutons identiques', () => {
    // Une portion qui vaut exactement la moitié du reste.
    const raccourcis = raccourcisQuantite(250, 'g', 125);
    const quantites = raccourcis.map((r) => r.quantite);
    expect(new Set(quantites).size).toBe(quantites.length);
  });

  it('écarte une portion plus grosse que ce qui reste', () => {
    const libelles = raccourcisQuantite(100, 'g', 125).map((r) => r.libelle);
    expect(libelles.some((l) => l.startsWith('1 portion'))).toBe(false);
  });

  it('affiche les millilitres et les litres comme le reste du panneau', () => {
    const [, dernier] = raccourcisQuantite(1500, 'ml', null);
    expect(dernier.libelle).toBe('Tout le reste (1,5 l)');
  });

  it('rend une liste vide quand il ne reste rien', () => {
    expect(raccourcisQuantite(0, 'g', 125)).toEqual([]);
  });
});
```

- [ ] **Step 2: Lancer, vérifier l'échec**

Run (depuis `frontend/`) : `npm test -- portion`
Expected: FAIL — `Cannot find module '../src/portion'`

- [ ] **Step 3: Écrire `nombres.ts` et `portion.ts`**

Créer `frontend/src/nombres.ts` en y **déplaçant** `ResultatNombre` et `analyserNombre` depuis `ecrans/catalogue.ts` (avec leur commentaire d'origine, qui raconte l'incident de la virgule), et en ajoutant :

```ts
/** Un nombre tel qu'on l'écrit en français, sans zéro décimal inutile. */
export function formaterNombre(valeur: number): string {
  return (Math.round(valeur * 100) / 100).toString().replace('.', ',');
}
```

Mettre à jour l'import dans `ecrans/catalogue.ts` et dans `frontend/tests/catalogue.test.ts`.

Créer `frontend/src/portion.ts` :

```ts
/** Les boutons de quantité de l'écran « manger ».
 *
 *  Pur, comme `dlc.ts` : déclarer un repas doit tenir en un appui, et ce qui
 *  décide du libellé de ces boutons se teste sans monter d'écran.
 *
 *  Aucun bouton ne propose plus que ce qui reste dans le lot visé : une
 *  quantité au-delà déborderait sur le lot suivant, ce qui est légitime au
 *  pavé numérique mais n'a rien à faire dans un raccourci qui prétend dire
 *  « tout le reste ».
 */
import { formaterNombre } from './nombres';
import type { UniteBase } from './ecrans/fiche';

export type Raccourci = { libelle: string; quantite: number };

function afficher(quantite: number, unite: UniteBase): string {
  if (unite === 'piece') return `${formaterNombre(quantite)} pièce${quantite >= 2 ? 's' : ''}`;
  if (unite === 'g') {
    return quantite >= 1000 ? `${formaterNombre(quantite / 1000)} kg` : `${formaterNombre(quantite)} g`;
  }
  return quantite >= 1000 ? `${formaterNombre(quantite / 1000)} l` : `${formaterNombre(quantite)} ml`;
}

export function raccourcisQuantite(restant: number, unite: UniteBase,
                                   portion: number | null): Raccourci[] {
  if (restant <= 0) return [];

  const proposes: Raccourci[] = [];
  if (unite === 'piece') {
    proposes.push({ libelle: afficher(1, unite), quantite: 1 });
  } else if (portion !== null && portion > 0 && portion <= restant) {
    proposes.push({ libelle: `1 portion (${afficher(portion, unite)})`, quantite: portion });
  }
  if (unite !== 'piece') {
    proposes.push({ libelle: `La moitié (${afficher(restant / 2, unite)})`, quantite: restant / 2 });
  }
  proposes.push({ libelle: `Tout le reste (${afficher(restant, unite)})`, quantite: restant });

  // Une portion qui vaut exactement la moitié, ou un lot qui n'a plus qu'une
  // pièce : deux boutons identiques valent moins que zéro.
  const vues = new Set<number>();
  return proposes.filter((r) => r.quantite <= restant && !vues.has(r.quantite) && vues.add(r.quantite));
}
```

- [ ] **Step 4: Lancer, vérifier le succès**

Run: `npm test -- portion`
Expected: PASS

- [ ] **Step 5: Écrire les tests du passage de relais**

Ajouter à `frontend/tests/file-attente.test.ts` :

```ts
it('rend un sort par action, sans table partagée', async () => {
  const file = new FileAttente(stockage, async () => undefined);
  const premier = file.ajouter('home_stock/stock/consume', { product_id: 1 });
  const second = file.ajouter('home_stock/stock/consume', { product_id: 2 });
  await file.rejouer();
  expect(await premier.sort).toBe('envoyee');
  expect(await second.sort).toBe('envoyee');
});

it('un rejeu générique concurrent n’emporte plus le sort d’un écran', async () => {
  // La course exacte que le lot 1 avait laissée ouverte : le rejeu du panneau
  // démarre avant l'écriture d'un écran, et son `.then` effaçait la table
  // partagée avant que l'écran n'ait lu SON résultat.
  const file = new FileAttente(stockage, async () => undefined);
  const generique = file.rejouer();
  const suivi = file.ajouter('home_stock/stock/consume', { product_id: 1 });
  await Promise.all([generique, file.rejouer()]);
  expect(await suivi.sort).toBe('envoyee');
});

it('résout « en-attente » quand le transport est tombé, sans vider la file', async () => {
  const file = new FileAttente(stockage, async () => { throw new Error('hors ligne'); });
  const suivi = file.ajouter('home_stock/stock/consume', { product_id: 1 });
  await file.rejouer();
  expect(await suivi.sort).toBe('en-attente');
  expect(file.taille()).toBe(1);
});

it('résout « refusee » sur un refus du serveur et retire l’action', async () => {
  const file = new FileAttente(stockage, async () => {
    throw { code: 'invalid_field', message: 'Les parts sont incohérentes.' };
  });
  const suivi = file.ajouter('home_stock/stock/consume', { product_id: 1 });
  await file.rejouer();
  expect(await suivi.sort).toBe('refusee');
  expect(file.taille()).toBe(0);
});

it('une action restaurée du stockage local n’attend personne', async () => {
  stockage.setItem('home_stock.file', JSON.stringify(
    [{ type: 'home_stock/stock/add', charge: { idempotency_key: 'x' } }]));
  const file = new FileAttente(stockage, async () => undefined);
  await expect(file.rejouer()).resolves.toBeUndefined();
  expect(file.taille()).toBe(0);
});
```

- [ ] **Step 6: Lancer, vérifier l'échec**

Run: `npm test -- file-attente`
Expected: FAIL — `premier.sort is not a function` / `ajouter` rend une chaîne.

- [ ] **Step 7: Réécrire le passage de relais**

Dans `frontend/src/file-attente.ts` :

- `type Action = { type: string; charge: Record<string, unknown>; resoudre?: (sort: ResultatAction) => void }` — le résolveur n'est **pas** sérialisé dans le stockage local (`ecrire()` ne persiste que `type` et `charge`).
- `ajouter` construit la promesse, garde son `resolve` sur l'entrée, et rend `{ cle, sort }`.
- `boucle()` appelle `action.resoudre?.('envoyee')` ou `('refusee')` au lieu d'écrire dans `resultats`.
- Sur une panne de transport, avant le `return`, résoudre **toutes** les entrées encore en file avec `'en-attente'` puis effacer leurs résolveurs : l'action reste en file et repartira, mais son appelant a sa réponse tout de suite au lieu d'attendre indéfiniment.
- Supprimer `resultats`, `resultatDe` et `viderResultats`, ainsi que leur long commentaire de dette — remplacé par une phrase disant que la course est fermée et comment.

Mettre à jour les cinq `ecrire()` des écrans :

```ts
  private ecrire(type: string, charge: Record<string, unknown>): Promise<boolean> {
    if (!this.file) return Promise.resolve(false);
    const suivi = this.file.ajouter(type, charge);
    this.avertirFile();
    void this.file.rejouer().then(() => this.avertirFile());
    return suivi.sort.then((sort) => sort === 'envoyee');
  }
```

Et dans `panneau.ts`, retirer l'appel à `viderResultats()` : il n'a plus d'objet.

- [ ] **Step 8: Lancer toute la suite front**

Run: `npm test`
Expected: PASS — 12 fichiers de tests plus les nouveaux.

- [ ] **Step 9: Vérifier que le test a des dents (mutation)**

Supprimer la résolution `'en-attente'` sur la panne de transport. Relancer : `résout « en-attente » quand le transport est tombé` doit tomber — et le faire **par expiration de délai**, ce qui est exactement le symptôme qu'aurait l'écran « manger » (bouton bloqué à jamais). Remettre.

- [ ] **Step 10: Commit**

```bash
git add frontend/src frontend/tests
git commit -m "feat: quantity shortcuts, and the queue hands each action its own fate"
```

---

## Task 14: L'écran « manger »

**Files:**
- Create: `frontend/src/ecrans/consommation.ts`
- Test: `frontend/tests/consommation.test.ts` (créer)

**Interfaces:**
- Consomme : `raccourcisQuantite` (tâche 13), `analyserNombre` (tâche 13), `home_stock/product/get` étendu et `home_stock/stock/consume` (tâche 11), `FileAttente.ajouter` (tâche 13).
- Produit : `<home-stock-consommation>`, propriétés `connexion`, `file`, `productId`, et l'événement `consommation-enregistree` que le panneau écoute pour revenir au scanner.

- [ ] **Step 1: Écrire les tests**

Créer `frontend/tests/consommation.test.ts`. Reprendre le montage utilisé par `frontend/tests/fiche.test.ts` (jsdom, `await element.updateComplete`, fausse `connexion`).

```ts
import { beforeEach, describe, expect, it, vi } from 'vitest';
import '../src/ecrans/consommation';

const PRODUIT_G = {
  product: { id: 1, name: 'Riz', base_unit: 'g' },
  suggested_portion: 80, portion_source: 'learned', serving_quantity: null,
  next_batch: { id: 7, remaining: 500, best_before: '2026-09-01' },
};

const PRODUIT_PIECE = {
  product: { id: 2, name: 'Yaourt', base_unit: 'piece' },
  suggested_portion: null, portion_source: null, serving_quantity: null,
  next_batch: { id: 8, remaining: 4, best_before: null },
};

function monter(reponse: unknown, envoyer = vi.fn(async () => undefined)) {
  const element = document.createElement('home-stock-consommation') as any;
  element.connexion = { envoyer: vi.fn(async () => reponse) };
  element.file = { ajouter: (type: string, charge: any) => ({
    cle: 'k', sort: Promise.resolve(envoyer(type, charge) ? 'envoyee' : 'envoyee') }),
    rejouer: async () => undefined };
  element.productId = 1;
  document.body.append(element);
  return element;
}

describe('<home-stock-consommation>', () => {
  beforeEach(() => { document.body.innerHTML = ''; });

  it('arme « 1 pièce » pour un produit à la pièce', async () => {
    const element = monter(PRODUIT_PIECE);
    await element.updateComplete;
    await element.updateComplete;
    expect(element.quantite).toBe(1);
  });

  it('propose la portion apprise pour un produit au gramme', async () => {
    const element = monter(PRODUIT_G);
    await element.updateComplete;
    await element.updateComplete;
    const libelles = [...element.shadowRoot.querySelectorAll('.raccourci')]
      .map((b: Element) => b.textContent?.trim());
    expect(libelles[0]).toContain('1 portion (80 g)');
  });

  it('envoie la quantité, le motif et rien d’autre par défaut', async () => {
    const envoi = vi.fn();
    const element = monter(PRODUIT_G);
    element.file = { ajouter: (type: string, charge: any) => {
      envoi(type, charge); return { cle: 'k', sort: Promise.resolve('envoyee') }; },
      rejouer: async () => undefined };
    await element.updateComplete;
    element.quantite = 80;
    await element.enregistrer();
    expect(envoi).toHaveBeenCalledWith('home_stock/stock/consume', expect.objectContaining({
      product_id: 1, batch_id: 7, quantity: 80, reason: 'consumption',
    }));
    // Pas de parts quand on n'a rien partagé : NULL en base, pas 1/1.
    expect(envoi.mock.calls[0][1]).not.toHaveProperty('parts_total');
  });

  it('envoie les deux parts quand on partage', async () => {
    const envoi = vi.fn();
    const element = monter(PRODUIT_G);
    element.file = { ajouter: (type: string, charge: any) => {
      envoi(type, charge); return { cle: 'k', sort: Promise.resolve('envoyee') }; },
      rejouer: async () => undefined };
    await element.updateComplete;
    element.quantite = 400;
    element.partage = true;
    element.partsTotal = 4;
    element.partsMoi = 1;
    await element.enregistrer();
    expect(envoi.mock.calls[0][1]).toMatchObject({ parts_total: 4, parts_mine: 1 });
  });

  it('escamote les parts dès qu’on choisit « jeté »', async () => {
    const element = monter(PRODUIT_G);
    await element.updateComplete;
    element.partage = true;
    element.motif = 'waste';
    await element.updateComplete;
    expect(element.shadowRoot.querySelector('.parts')).toBeNull();
  });

  it('n’envoie jamais de parts sur un motif « jeté »', async () => {
    const envoi = vi.fn();
    const element = monter(PRODUIT_G);
    element.file = { ajouter: (type: string, charge: any) => {
      envoi(type, charge); return { cle: 'k', sort: Promise.resolve('envoyee') }; },
      rejouer: async () => undefined };
    await element.updateComplete;
    element.quantite = 100;
    element.partage = true;
    element.partsTotal = 4;
    element.partsMoi = 1;
    element.motif = 'waste';
    await element.enregistrer();
    expect(envoi.mock.calls[0][1]).not.toHaveProperty('parts_total');
  });

  it('accepte la virgule décimale au pavé', async () => {
    const element = monter(PRODUIT_G);
    await element.updateComplete;
    element.saisirQuantite('12,5');
    expect(element.quantite).toBe(12.5);
    expect(element.erreur).toBeNull();
  });

  it('refuse un texte qui n’est pas un nombre plutôt que d’envoyer NaN', async () => {
    const envoi = vi.fn();
    const element = monter(PRODUIT_G);
    element.file = { ajouter: (type: string, charge: any) => {
      envoi(type, charge); return { cle: 'k', sort: Promise.resolve('envoyee') }; },
      rejouer: async () => undefined };
    await element.updateComplete;
    element.saisirQuantite('deux cuillères');
    await element.enregistrer();
    expect(envoi).not.toHaveBeenCalled();
    expect(element.erreur).toContain('nombre');
  });

  it('refuse une quantité nulle ou négative', async () => {
    const element = monter(PRODUIT_G);
    await element.updateComplete;
    element.saisirQuantite('0');
    await element.enregistrer();
    expect(element.erreur).not.toBeNull();
  });

  it('refuse de manger plus de parts qu’il n’en a été servi, sans aller au serveur', async () => {
    const envoi = vi.fn();
    const element = monter(PRODUIT_G);
    element.file = { ajouter: (type: string, charge: any) => {
      envoi(type, charge); return { cle: 'k', sort: Promise.resolve('envoyee') }; },
      rejouer: async () => undefined };
    await element.updateComplete;
    element.quantite = 100;
    element.partage = true;
    element.partsTotal = 2;
    element.partsMoi = 3;
    await element.enregistrer();
    expect(envoi).not.toHaveBeenCalled();
  });

  it('dit qu’il ne reste rien plutôt que de proposer une quantité', async () => {
    const element = monter({ ...PRODUIT_G, next_batch: null });
    await element.updateComplete;
    await element.updateComplete;
    expect(element.shadowRoot.textContent).toContain('Plus rien en stock');
    expect(element.shadowRoot.querySelectorAll('.raccourci').length).toBe(0);
  });

  it('reste ouvert quand l’envoi n’est pas parti', async () => {
    const element = monter(PRODUIT_G);
    element.file = { ajouter: () => ({ cle: 'k', sort: Promise.resolve('en-attente') }),
      rejouer: async () => undefined };
    await element.updateComplete;
    element.quantite = 80;
    await element.enregistrer();
    expect(element.enAttenteEnvoi).toBe(true);
  });
});
```

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `npm test -- consommation`
Expected: FAIL — le module n'existe pas.

- [ ] **Step 3: Écrire l'écran**

Créer `frontend/src/ecrans/consommation.ts`. Structure imposée :

```ts
/** L'écran « manger » : ce qui sort du stock, et pour qui.
 *
 *  Il vise TOUJOURS le lot que le FIFO prendrait — le plus ancien lot ouvert
 *  du produit — et le dit. Les raccourcis sont calculés sur le reste de CE
 *  lot ; le pavé numérique, lui, accepte davantage, et la sortie déborde
 *  alors sur les lots suivants comme le fait le service.
 *
 *  Les parts ne sont envoyées que sur le motif « mangé », et seulement si on
 *  a explicitement partagé : sans partage, les colonnes restent NULL en base,
 *  ce qui vaut 1/1 à la lecture. Écrire 1/1 en dur salirait le journal d'une
 *  donnée qui n'a jamais été saisie.
 */
import { LitElement, html, css, nothing } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import type { Connexion } from '../connexion';
import type { FileAttente } from '../file-attente';
import type { UniteBase } from './fiche';
import { analyserNombre } from '../nombres';
import { raccourcisQuantite } from '../portion';

export type Motif = 'consumption' | 'waste' | 'expired';

const LIBELLE_MOTIF: Record<Motif, string> = {
  consumption: 'Mangé', waste: 'Jeté', expired: 'Périmé',
};

@customElement('home-stock-consommation')
export class EcranConsommation extends LitElement {
  @property({ attribute: false }) connexion?: Connexion;
  @property({ attribute: false }) file?: FileAttente;
  @property({ type: Number }) productId: number | null = null;

  @state() produit: { id: number; name: string; base_unit: UniteBase } | null = null;
  @state() lot: { id: number; remaining: number; best_before: string | null } | null = null;
  @state() portion: number | null = null;
  @state() quantite: number | null = null;
  @state() motif: Motif = 'consumption';
  @state() partage = false;
  @state() partsTotal = 2;
  @state() partsMoi = 1;
  @state() erreur: string | null = null;
  @state() enCours = false;
  @state() enAttenteEnvoi = false;
  ...
}
```

Méthodes à écrire, dans cet ordre :

```ts
  /** Charge le produit, son lot FIFO et sa portion en un aller-retour. */
  private async charger(): Promise<void> {
    if (!this.connexion || this.productId === null) return;
    const reponse = await this.connexion.envoyer('home_stock/product/get',
                                                 { product_id: this.productId }) as any;
    this.produit = reponse.produit ?? reponse.product;
    this.lot = reponse.next_batch;
    this.portion = reponse.suggested_portion;
    // Un produit à la pièce a « 1 » déjà armé : un appui suffit, et c'est le
    // cas de 239 des 299 produits du catalogue.
    this.quantite = this.produit?.base_unit === 'piece' && this.lot ? 1 : null;
  }

  /** Le pavé numérique. La virgule est acceptée comme le point : un incident
   *  réel du lot 1 a montré qu'une virgule suffisait à effacer un champ en
   *  silence, ici elle effacerait un repas. */
  saisirQuantite(saisie: string): void {
    const resultat = analyserNombre(saisie);
    if (!resultat.ok) {
      this.erreur = 'Quantité : ce n’est pas un nombre.';
      this.quantite = null;
      return;
    }
    this.erreur = null;
    this.quantite = resultat.valeur;
  }

  /** Ce qui part au serveur. Refuse tout ce que le serveur refuserait, mais
   *  sans aller le lui demander : debout dans une cuisine, un aller-retour
   *  pour apprendre qu'on a tapé trois parts sur deux est un aller-retour de
   *  trop. */
  async enregistrer(): Promise<void> {
    if (this.enCours || !this.file || !this.lot || this.produit === null) return;
    if (this.quantite === null || !(this.quantite > 0)) {
      this.erreur = 'Quantité : donne un nombre supérieur à zéro.';
      return;
    }
    const partage = this.partage && this.motif === 'consumption';
    if (partage && !(this.partsTotal >= 1 && this.partsMoi >= 0
                     && this.partsMoi <= this.partsTotal)) {
      this.erreur = 'On ne mange pas plus de parts qu’il n’en a été servi.';
      return;
    }
    this.erreur = null;
    this.enCours = true;
    this.enAttenteEnvoi = false;
    const charge: Record<string, unknown> = {
      product_id: this.produit.id, batch_id: this.lot.id,
      quantity: this.quantite, reason: this.motif,
    };
    if (partage) {
      charge.parts_total = this.partsTotal;
      charge.parts_mine = this.partsMoi;
    }
    const suivi = this.file.ajouter('home_stock/stock/consume', charge);
    this.avertirFile();
    void this.file.rejouer().then(() => this.avertirFile());
    const sort = await suivi.sort;
    this.enCours = false;
    if (sort === 'envoyee') {
      this.dispatchEvent(new CustomEvent('consommation-enregistree',
                                         { bubbles: true, composed: true }));
    } else {
      // Refusé (le panneau l'affiche en français) ou encore en file (hors
      // ligne) : l'écran reste ouvert, rien n'est perdu.
      this.enAttenteEnvoi = true;
    }
  }
```

Le rendu, dans l'ordre vertical : le nom du produit et ce qui reste du lot visé (avec sa date limite quand il y en a une) ; les boutons de raccourci (`class="raccourci"`) ; le pavé ; les trois motifs ; le bloc `class="parts"` — rendu **uniquement** si `this.motif === 'consumption'` — avec la bascule « je partage » puis deux compteurs ; le bouton d'enregistrement ; l'erreur et l'attente d'envoi. Quand `this.lot` est `null`, rendre « Plus rien en stock » et rien d'autre.

Reprendre les styles de `ecrans/fiche.ts` : mêmes tailles de bouton, mêmes couleurs, aucun hex qui ne s'y trouve déjà.

- [ ] **Step 4: Lancer, vérifier le succès**

Run: `npm test -- consommation`
Expected: PASS

- [ ] **Step 5: Vérifier que le test a des dents (mutation)**

Remplacer `const partage = this.partage && this.motif === 'consumption';` par `const partage = this.partage;`. Relancer : `n’envoie jamais de parts sur un motif « jeté »` doit tomber. Remettre.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/ecrans/consommation.ts frontend/tests/consommation.test.ts
git commit -m "feat: the eat screen, one tap for a piece"
```

---

## Task 15: L'écran « journal » et la navigation

**Files:**
- Create: `frontend/src/ecrans/journal.ts`
- Modify: `frontend/src/panneau.ts`
- Test: `frontend/tests/journal.test.ts` (créer), `frontend/tests/panneau.test.ts`

**Interfaces:**
- Consomme : `home_stock/journal/day`, `home_stock/journal/series` (tâche 11).
- Produit : `<home-stock-journal>` ; `Ecran` gagne `'consommation'` et `'journal'`.

- [ ] **Step 1: Écrire les tests**

Créer `frontend/tests/journal.test.ts` :

```ts
import { beforeEach, describe, expect, it, vi } from 'vitest';
import '../src/ecrans/journal';

const JOUR = {
  food_day: '2026-08-20', start: '2026-08-20T02:00:00', end: '2026-08-21T02:00:00',
  entries: [
    { id: 1, occurred_at: '2026-08-20T08:30:00', product_name: 'Café',
      quantity: -20, base_unit: 'g', reason: 'consumption', kcal: 8,
      parts_total: null, parts_mine: null },
    { id: 2, occurred_at: '2026-08-20T12:15:00', product_name: 'Riz',
      quantity: -400, base_unit: 'g', reason: 'consumption', kcal: 1360,
      parts_total: 4, parts_mine: 1 },
    { id: 3, occurred_at: '2026-08-20T19:00:00', product_name: 'Salade',
      quantity: -150, base_unit: 'g', reason: 'waste', kcal: 30,
      parts_total: null, parts_mine: null },
  ],
  totals: { kcal: 348, cost: 2.4, waste_cost: 0.9, unvalued: 0,
            proteins: 12, salt: 1.2 },
};

const SERIE = { granularity: 'day', buckets: [
  { label: '2026-08-18', kcal: 1800, cost: 9.4, waste_cost: 0 },
  { label: '2026-08-19', kcal: 2100, cost: 11.0, waste_cost: 1.2 },
  { label: '2026-08-20', kcal: 348, cost: 2.4, waste_cost: 0.9 },
]};

function monter() {
  const element = document.createElement('home-stock-journal') as any;
  element.connexion = { envoyer: vi.fn(async (type: string) =>
    type === 'home_stock/journal/day' ? JOUR : SERIE) };
  document.body.append(element);
  return element;
}

describe('<home-stock-journal>', () => {
  beforeEach(() => { document.body.innerHTML = ''; });

  it('liste les entrées de la journée dans l’ordre', async () => {
    const element = monter();
    await element.updateComplete; await element.updateComplete;
    const noms = [...element.shadowRoot.querySelectorAll('.entree-nom')]
      .map((n: Element) => n.textContent?.trim());
    expect(noms).toEqual(['Café', 'Riz', 'Salade']);
  });

  it('affiche la part quand elle n’est pas 1/1, et rien sinon', async () => {
    const element = monter();
    await element.updateComplete; await element.updateComplete;
    const parts = [...element.shadowRoot.querySelectorAll('.entree')]
      .map((e: Element) => e.querySelector('.entree-parts')?.textContent?.trim() ?? '');
    expect(parts[0]).toBe('');
    expect(parts[1]).toContain('1');
    expect(parts[1]).toContain('4');
  });

  it('distingue visiblement ce qui a été jeté', async () => {
    const element = monter();
    await element.updateComplete; await element.updateComplete;
    const entrees = element.shadowRoot.querySelectorAll('.entree');
    expect(entrees[2].classList.contains('jete')).toBe(true);
  });

  it('affiche le total du jour', async () => {
    const element = monter();
    await element.updateComplete; await element.updateComplete;
    expect(element.shadowRoot.querySelector('.total-kcal').textContent).toContain('348');
  });

  it('signale les sorties non chiffrées, et se tait quand il n’y en a pas', async () => {
    const element = monter();
    await element.updateComplete; await element.updateComplete;
    expect(element.shadowRoot.querySelector('.non-chiffre')).toBeNull();

    element.jour = { ...JOUR, totals: { ...JOUR.totals, unvalued: 3 } };
    await element.updateComplete;
    expect(element.shadowRoot.querySelector('.non-chiffre').textContent).toContain('3');
  });

  it('dessine une barre par seau, la plus haute à l’échelle', async () => {
    const element = monter();
    await element.updateComplete; await element.updateComplete;
    const barres = element.shadowRoot.querySelectorAll('.barre');
    expect(barres.length).toBe(3);
    // 2100 est le maximum : sa barre est pleine hauteur.
    expect(Number(barres[1].getAttribute('data-part'))).toBe(1);
  });

  it('ne divise jamais par zéro quand tous les seaux sont vides', async () => {
    const element = monter();
    await element.updateComplete;
    element.serie = { granularity: 'day', buckets: [
      { label: '2026-08-20', kcal: 0, cost: 0, waste_cost: 0 }] };
    await element.updateComplete;
    const barre = element.shadowRoot.querySelector('.barre');
    expect(Number(barre.getAttribute('data-part'))).toBe(0);
  });

  it('demande la bonne granularité quand on change de vue', async () => {
    const element = monter();
    await element.updateComplete; await element.updateComplete;
    await element.choisirGranularite('month');
    expect(element.connexion.envoyer).toHaveBeenCalledWith(
      'home_stock/journal/series', { granularity: 'month', count: 12 });
  });

  it('ouvre le jour d’une barre quand on la touche', async () => {
    const element = monter();
    await element.updateComplete; await element.updateComplete;
    await element.ouvrirSeau('2026-08-19');
    expect(element.connexion.envoyer).toHaveBeenCalledWith(
      'home_stock/journal/day', { date: '2026-08-19' });
  });

  it('affiche une journée vide sans se plaindre', async () => {
    const element = monter();
    await element.updateComplete;
    element.jour = { ...JOUR, entries: [],
                     totals: { kcal: 0, cost: 0, waste_cost: 0, unvalued: 0 } };
    await element.updateComplete;
    expect(element.shadowRoot.textContent).toContain('Rien de déclaré');
  });
});
```

Ajouter à `frontend/tests/panneau.test.ts` :

```ts
it('expose les deux nouveaux écrans dans la navigation', async () => {
  const panneau = await monterPanneau();       // helper déjà présent dans ce fichier
  const libelles = [...panneau.shadowRoot.querySelectorAll('.nav-bouton')]
    .map((b: Element) => b.textContent?.trim());
  expect(libelles).toContain('Journal');
});

it('revient au scanner quand une consommation est enregistrée', async () => {
  const panneau = await monterPanneau();
  panneau.ecran = 'consommation';
  await panneau.updateComplete;
  panneau.shadowRoot.querySelector('home-stock-consommation')
    ?.dispatchEvent(new CustomEvent('consommation-enregistree',
                                    { bubbles: true, composed: true }));
  await panneau.updateComplete;
  expect(panneau.ecran).toBe('scanner');
});
```

- [ ] **Step 2: Lancer, vérifier l'échec**

Run: `npm test -- journal panneau`
Expected: FAIL

- [ ] **Step 3: Écrire l'écran et la navigation**

Créer `frontend/src/ecrans/journal.ts`. Points imposés :

- État : `jour`, `serie`, `granularite: 'day' | 'week' | 'month'` (défaut `'day'`), `enCours`.
- `NOMBRE_DE_SEAUX = { day: 14, week: 12, month: 12 }`.
- `choisirGranularite(g)` recharge la série avec le compte correspondant.
- `ouvrirSeau(label)` recharge la journée à cette date — pour `week` et `month`, le label est le **premier jour** du seau, ce que la commande `journal/day` accepte tel quel.
- Les barres, exactement :

```ts
  /** La hauteur relative d'une barre.
   *
   *  La garde sur `maximum > 0` n'est pas décorative : une semaine sans rien
   *  de déclaré donnerait `0 / 0`, donc `NaN`, donc une hauteur CSS invalide
   *  — et des barres invisibles sans la moindre erreur nulle part.
   */
  private partDeLaBarre(kcal: number, maximum: number): number {
    return maximum > 0 ? kcal / maximum : 0;
  }

  private rendreBarres() {
    const seaux = this.serie?.buckets ?? [];
    const maximum = Math.max(0, ...seaux.map((b) => b.kcal));
    return html`
      <div class="barres">
        ${seaux.map((seau) => {
          const part = this.partDeLaBarre(seau.kcal, maximum);
          return html`
            <button class="barre" data-part=${part}
                    style=${`height: ${Math.round(part * 100)}%`}
                    title=${`${seau.label} — ${Math.round(seau.kcal)} kcal`}
                    @click=${() => this.ouvrirSeau(seau.label)}></button>`;
        })}
      </div>`;
  }
```
- Une entrée dont le motif n'est pas `consumption` porte la classe `jete`.
- La part ne s'affiche (`.entree-parts`) que si `parts_total` n'est ni `null` ni égal à `parts_mine`.
- Aucune dépendance nouvelle : les barres sont des `div`, pas une bibliothèque de graphes.

Dans `panneau.ts` :

```ts
export type Ecran = 'scanner' | 'fiche' | 'panier' | 'rangement' | 'session'
  | 'catalogue' | 'reglages' | 'consommation' | 'journal';
```

Ajouter les deux imports, les deux branches de rendu, un bouton « Journal » dans la navigation, et l'écoute de `consommation-enregistree` qui ramène à `'scanner'`. Le garde-fou existant du rangement (confirmation à deux appuis quand des lignes attendent) s'applique à ces deux cibles sans modification.

- [ ] **Step 4: Lancer toute la suite front**

Run: `npm test`
Expected: PASS

- [ ] **Step 5: Vérifier que le test a des dents (mutation)**

Retirer la garde `maximum > 0` du calcul de `data-part`. Relancer : `ne divise jamais par zéro quand tous les seaux sont vides` doit tomber. Remettre.

- [ ] **Step 6: Commit**

```bash
git add frontend/src frontend/tests
git commit -m "feat: the journal screen, with bars the panel draws itself"
```

---

## Task 16: Vérification de rendu, documentation, et construction du bundle

**Files:**
- Modify: `frontend/outils/verifier-rendu.mjs`
- Modify: `docs/exploitation.md`
- Modify: `custom_components/home_stock/panel/home-stock-panel.js` (produit par le build)
- Test: le vérificateur lui-même

**C'est la seule tâche autorisée à lancer `npm run build`.** Le répertoire est bind-monté dans Home Assistant : le bundle construit est servi tel quel. Une seule construction, à la fin, quand tout le reste est vert.

- [ ] **Step 1: Ajouter les deux scénarios**

Dans `frontend/outils/verifier-rendu.mjs`, ajouter à `SCENARIOS` :

```js
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
    actions: [
      { type: 'click-nav', texte: 'Manger' },
      { type: 'click', selecteur: '.partage-bascule' },
    ],
    ecranAttendu: 'home-stock-consommation',
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
    actions: [{ type: 'click-nav', texte: 'Journal' }],
    ecranAttendu: 'home-stock-journal',
  },
```

Définir `JOURNEE_CHARGEE` avec **douze** entrées — dont une jetée, une avec des parts 1/4, et une sans kcal — et `SERIE_QUATORZE_JOURS` avec quatorze seaux dont un à zéro et un maximum net. Une journée à trois lignes ne prouve rien sur le débordement : c'est une journée réaliste qui doit tenir dans le cadre.

Ajouter un scénario à `SCENARIOS_MINIFIES` : l'écran « manger » sur le bundle minifié, pour vérifier que `terser` n'a rien cassé dans les noms de motif.

- [ ] **Step 2: Lancer le vérificateur**

Run (depuis `frontend/`) : `node outils/verifier-rendu.mjs`
Expected: tous les scénarios sans défaut — aucun débordement, aucun contraste sous 5:1, aucun texte tronqué, et l'écran attendu réellement atteint.

Corriger les styles jusqu'à ce que ce soit vrai. Ne pas désactiver un contrôle.

- [ ] **Step 3: Mettre à jour la documentation d'exploitation**

Dans `docs/exploitation.md`, ajouter une section « La journée alimentaire » disant, en français et sans jargon :

- la journée court de **4 h à 4 h** ; ce qui est mangé à une heure du matin compte pour la soirée qu'on est en train de finir ;
- les graphes jour / semaine / mois sont **dans le panneau**, pas dans une carte Lovelace : les statistiques natives de Home Assistant découpent à minuit et n'acceptent aucun décalage. Le panneau les calcule sur le journal, donc ils survivent à la purge du `recorder` (dix jours par défaut) ;
- `sensor.home_stock_kcal_total` et `cost_total` **ont changé de sens** au lot 2 : ils ne comptent plus que la consommation, et le gaspillage a son propre `cost_waste_total`. Un compteur `total_increasing` dont la valeur baisse est lu par Home Assistant comme une remise à zéro, et les statistiques déjà enregistrées gardent l'ancienne définition. Rupture assumée, une fois ;
- cinq capteurs de nutriments sont **créés éteints** ; les allumer dans le registre démarre leur historique à ce moment-là, pas avant ;
- pour être annoncé à voix haute, importer `blueprints/automation/home_stock/dlc_bleuenn.yaml` (Paramètres → Automatisations → Blueprints → Importer), choisir l'heure et l'agent. Le composant ne crée aucune automation tout seul ;
- `article.serving_quantity` se remplit au fil des scans et de la resynchronisation Open Food Facts. **Mesuré le 2026-08-20 : aucun des 299 articles n'a de fiche brute stockée**, la migration ne trouvera donc rien le jour où elle passera.

- [ ] **Step 4: Construire le bundle**

Run (depuis `frontend/`) : `npm run build`

Puis vérifier ce qui a été écrit :

```bash
git -C /opt/nivuus/HomeAssistant/data/meal status --porcelain custom_components/home_stock/panel/
```

Un seul fichier doit avoir changé.

- [ ] **Step 5: Vérifier le bundle réellement en place**

Run (depuis `frontend/`) : `node outils/verifier-rendu.mjs --deploye`
Expected: mêmes scénarios verts, cette fois sur le bundle construit.

- [ ] **Step 6: Lancer les deux suites une dernière fois**

```bash
./scripts/test.sh -q
cd /opt/nivuus/HomeAssistant/data/meal/frontend && npm test && node outils/verifier-rendu.mjs
```
Expected: tout vert.

- [ ] **Step 7: Commit**

```bash
git add frontend/outils/verifier-rendu.mjs docs/exploitation.md custom_components/home_stock/panel/home-stock-panel.js
git commit -m "chore: render checks for the two new screens, docs, and the built panel"
```

---

## Ce que ce plan ne fait pas

Rappel, pour qu'aucune tâche n'aille les chercher :

- **Corriger un mouvement déjà écrit** — le journal est append-only ; la correction demandera un motif `correction` et une migration, groupée avec la correction de prix au lot 4.
- **Les restes cuisinés comme objet en stock** — lot 3, avec les recettes.
- **Les objectifs nutritionnels** et leurs alertes de dépassement.
- **Une portion saisie à la main** par produit — la médiane apprise d'abord ; si elle déçoit à l'usage, la colonne viendra ensuite.
- **Nommer les convives** — les parts comptent des assiettes. Le foyer ne suit qu'une personne.
- **Déployer.** Redémarrer Home Assistant et lancer la première resynchronisation Open Food Facts restent le geste du propriétaire.
