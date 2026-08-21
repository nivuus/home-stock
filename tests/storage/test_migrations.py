import itertools
import sqlite3

import pytest

from custom_components.home_stock.aisles import AISLES, CATEGORY_TO_AISLE
from custom_components.home_stock.storage import migrations
from custom_components.home_stock.storage.database import Database
from custom_components.home_stock.storage.migrations import (
    CURRENT_VERSION,
    MIGRATIONS,
    apply_migrations,
)
from custom_components.home_stock.storage.migrations import m004_recipes as m004


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
    db = _fresh(tmp_path)
    with db.write() as conn:
        apply_migrations(conn)
    with pytest.raises(sqlite3.IntegrityError):
        with db.write() as conn:
            conn.execute("INSERT INTO product (name, base_unit) VALUES ('X', 'Paquet')")
    db.close()


def test_movement_is_append_only(tmp_path):
    """The journal must be structural, not just a comment: an UPDATE (and a
    DELETE) on `movement` must raise, never silently rewrite history."""
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
        conn.execute(
            "INSERT INTO movement (occurred_at, product_id, article_id, quantity,"
            " reason) VALUES ('2026-08-18T10:00:00', 1, 1, 5, 'purchase')"
        )
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        with db.write() as conn:
            conn.execute("UPDATE movement SET quantity = 99 WHERE id = 1")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        with db.write() as conn:
            conn.execute("DELETE FROM movement WHERE id = 1")
    db.close()


def _lot0_database() -> sqlite3.Connection:
    """A database at schema version 1, with one product and one movement."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    from custom_components.home_stock.storage.migrations import m001_initial

    conn.executescript(m001_initial.SQL)
    # schema_version is only created lazily by apply_migrations()'s
    # _current_version(); this fixture bypasses apply_migrations to build a
    # database frozen at version 1, so it has to create the table itself.
    conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
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

    assert apply_migrations(conn) == CURRENT_VERSION

    row = conn.execute("SELECT base_unit FROM movement WHERE id = 1").fetchone()
    assert row["base_unit"] == "piece"


def test_m002_keeps_the_journal_append_only():
    conn = _lot0_database()
    apply_migrations(conn)

    # The backfill dropped the trigger. It must be back.
    with pytest.raises((sqlite3.IntegrityError, sqlite3.OperationalError)):
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

    with pytest.raises((sqlite3.IntegrityError, sqlite3.OperationalError)):
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


def test_a_movement_whose_product_vanished_keeps_an_unknown_unit():
    """The m002 backfill cannot know the unit of a movement whose product_id
    no longer resolves to a product: it leaves base_unit at NULL rather than
    guessing. This case is unreachable in production (movement.product_id is
    a foreign key, and Database.connect() runs PRAGMA foreign_keys=ON), so
    this test forces it by disabling foreign keys on the fixture connection
    — the only way to get such a row into the table at all."""
    conn = _lot0_database()
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute(
        "INSERT INTO movement (id, occurred_at, product_id, article_id, quantity, reason) "
        "VALUES (2, '2026-08-02T10:00:00', 999, 1, 1.0, 'purchase')"
    )
    conn.commit()

    apply_migrations(conn)

    rows = {
        row["id"]: row["base_unit"]
        for row in conn.execute("SELECT id, base_unit FROM movement")
    }
    assert rows[1] == "piece"  # normal row: still correctly filled
    assert rows[2] is None  # product 999 does not exist: honestly unknown


def _open(tmp_path) -> sqlite3.Connection:
    """A raw connection to a fresh database file, pragmas included — the
    same ones Database.connect() applies in production."""
    conn = sqlite3.connect(str(tmp_path / "home_stock.db"))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _migrated(tmp_path) -> sqlite3.Connection:
    """A raw connection, migrated to CURRENT_VERSION."""
    conn = _open(tmp_path)
    apply_migrations(conn)
    return conn


def _migrated_to(tmp_path, *, version: int):
    """A database stopped at a given version, to observe what the next
    one does with content already present."""
    conn = _open(tmp_path)                    # opening helper already defined above
    for migration in MIGRATIONS:
        if migration.VERSION > version:
            break
        conn.executescript(migration.SQL)
        hook = getattr(migration, "apply", None)
        if hook is not None:
            hook(conn)
    conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
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


def test_m003_adds_the_journal_columns(tmp_path):
    conn = _migrated(tmp_path)                       # helper already defined earlier in this file
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(movement)")}
    assert {"parts_total", "parts_mine", "proteins", "carbohydrates", "sugars",
            "added_sugars", "fat", "saturated_fat", "fiber", "salt"} <= columns
    assert "serving_quantity" in {r["name"] for r in conn.execute("PRAGMA table_info(article)")}
    assert "expiry_announced_stage" in {r["name"] for r in conn.execute("PRAGMA table_info(batch)")}


def test_m003_keeps_the_movement_triggers(tmp_path):
    """m003 does not touch the triggers — but a movement must still stay
    unmodifiable after it, or the migration broke append-only with
    nothing else around to say so."""
    conn = _migrated(tmp_path)
    _seed_one_movement(conn)                          # helper to add, see Step 7
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE movement SET quantity = 999 WHERE id = 1")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM movement WHERE id = 1")


def test_m003_backfills_serving_quantity_from_off_raw(tmp_path):
    conn = _migrated_to(tmp_path, version=2)          # helper to add, see Step 7
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
        ('{"serving_quantity": "500"}',))     # bigger than the pack: rejected
    conn.execute("INSERT INTO article (product_id, off_raw) VALUES (1, '{tronqu')")
    conn.commit()

    apply_migrations(conn)

    servings = [row["serving_quantity"] for row in
                conn.execute("SELECT serving_quantity FROM article ORDER BY id")]
    assert servings == [100.0, None, None, None]


def test_m003_is_replayable(tmp_path):
    """Replaying the migration on an already-migrated database must change
    nothing — and especially must not overwrite a hand-corrected serving."""
    conn = _migrated(tmp_path)
    conn.execute("INSERT INTO product (name, base_unit) VALUES ('Yaourt', 'g')")
    conn.execute(
        "INSERT INTO article (product_id, net_quantity, off_raw, serving_quantity)"
        " VALUES (1, 125, ?, 60)", ('{"serving_quantity": "100"}',))
    conn.commit()

    apply_migrations(conn)

    assert conn.execute("SELECT serving_quantity FROM article").fetchone()[0] == 60.0


def test_m003_apply_never_overwrites_a_serving_already_set(tmp_path):
    """apply_migrations() locks by version: once the base sits at
    CURRENT_VERSION, m003's own apply() hook is never invoked again, so
    test_m003_is_replayable's second apply_migrations() call is a total
    no-op and cannot exercise the `serving_quantity IS NULL` guard in
    m003_consumption.apply(). Calling m003_consumption.apply(conn) directly
    is the only path that bypasses the version lock — same trick
    test_m002_never_overwrites_an_aisle_already_chosen already uses for
    m002's own hook."""
    conn = _migrated(tmp_path)
    conn.execute("INSERT INTO product (name, base_unit) VALUES ('Yaourt', 'g')")
    conn.execute(
        "INSERT INTO article (product_id, net_quantity, off_raw, serving_quantity)"
        " VALUES (1, 125, ?, 60)", ('{"serving_quantity": "100"}',))
    conn.commit()

    from custom_components.home_stock.storage.migrations import m003_consumption

    m003_consumption.apply(conn)  # replayed by hand, bypassing the version lock

    assert conn.execute("SELECT serving_quantity FROM article").fetchone()[0] == 60.0


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


def _seed_one_batch(conn) -> None:
    conn.execute("INSERT INTO location (name, kind) VALUES ('Placard', 'cupboard')")
    conn.execute("INSERT INTO product (name, base_unit) VALUES ('Riz', 'g')")
    conn.execute("INSERT INTO article (product_id) VALUES (1)")
    conn.execute(
        "INSERT INTO batch (article_id, location_id, remaining, initial, entered_at)"
        " VALUES (1, 1, 500, 500, '2026-08-20T10:00:00')")
    conn.commit()


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


def _ensure_recipe(conn) -> int:
    """The first recipe in the database, created on demand."""
    row = conn.execute("SELECT id FROM recipe LIMIT 1").fetchone()
    if row is not None:
        return row["id"]
    conn.execute(
        "INSERT INTO recipe (name, source, created_at) VALUES (?, ?, ?)",
        ("Recette de test", "manual", "2026-08-20T10:00:00"))
    return conn.execute("SELECT id FROM recipe ORDER BY id DESC LIMIT 1").fetchone()["id"]


def _ensure_product(conn) -> int:
    """The first product in the database, created on demand."""
    row = conn.execute("SELECT id FROM product LIMIT 1").fetchone()
    if row is not None:
        return row["id"]
    conn.execute("INSERT INTO product (name, base_unit) VALUES ('Farine', 'g')")
    return conn.execute("SELECT id FROM product ORDER BY id DESC LIMIT 1").fetchone()["id"]


def _ensure_packaging(conn, product_id: int) -> int:
    """The first packaging in the database, created on demand."""
    row = conn.execute("SELECT id FROM packaging LIMIT 1").fetchone()
    if row is not None:
        return row["id"]
    conn.execute(
        "INSERT INTO packaging (scope, target_id, name, base_quantity)"
        " VALUES ('product', ?, 'Sachet', 500)", (product_id,))
    return conn.execute("SELECT id FROM packaging ORDER BY id DESC LIMIT 1").fetchone()["id"]


def _ensure_step(conn) -> int:
    """The first recipe_step in the database, created on demand."""
    row = conn.execute("SELECT id FROM recipe_step LIMIT 1").fetchone()
    if row is not None:
        return row["id"]
    recipe_id = _ensure_recipe(conn)
    conn.execute("INSERT INTO recipe_step (recipe_id, position) VALUES (?, 1)", (recipe_id,))
    return conn.execute("SELECT id FROM recipe_step ORDER BY id DESC LIMIT 1").fetchone()["id"]


def _insert_ingredient(conn, **overrides) -> None:
    recipe_id = _ensure_recipe(conn)
    product_id = _ensure_product(conn)
    _ensure_packaging(conn, product_id)
    values = {
        "recipe_id": recipe_id,
        "position": 1,
        "product_id": product_id,
        "amount": 1.0,
        "packaging_id": None,
        "measure_id": None,
        "raw_text": "1 pincée de sel",
        "group_name": None,
        "optional": 0,
        "match_state": "unmatched",
        "match_score": None,
        "external_ref": None,
    }
    values.update(overrides)
    conn.execute(
        "INSERT INTO recipe_ingredient (recipe_id, position, product_id, amount,"
        " packaging_id, measure_id, raw_text, group_name, optional, match_state,"
        " match_score, external_ref) VALUES (:recipe_id, :position, :product_id,"
        " :amount, :packaging_id, :measure_id, :raw_text, :group_name, :optional,"
        " :match_state, :match_score, :external_ref)", values)
    conn.commit()


def _insert_instruction(conn, *, timer_label=None, timer_seconds=None, text="Mélanger") -> None:
    step_id = _ensure_step(conn)
    position = conn.execute(
        "SELECT COALESCE(MAX(position), 0) + 1 AS p FROM recipe_instruction"
        " WHERE step_id = ?", (step_id,)).fetchone()["p"]
    conn.execute(
        "INSERT INTO recipe_instruction (step_id, position, text, timer_label,"
        " timer_seconds) VALUES (?, ?, ?, ?, ?)",
        (step_id, position, text, timer_label, timer_seconds))
    conn.commit()


_meal_uids = itertools.count()


def _insert_meal(conn, **overrides) -> None:
    _ensure_recipe(conn)
    _ensure_product(conn)
    values = {
        "uid": f"meal-test-{next(_meal_uids)}",
        "day": "2026-08-20",
        "slot_key": "lunch",
        "position": 0,
        "recipe_id": None,
        "product_id": None,
        "amount": None,
        "packaging_id": None,
        "note": None,
        "servings": 1,
        "portions_eaten": None,
        "parts_total": None,
        "parts_mine": None,
        "state": "planned",
        "validated_at": None,
        "skipped_ingredient_ids": None,
        "created_at": "2026-08-20T10:00:00",
        "external_ref": None,
    }
    values.update(overrides)
    conn.execute(
        "INSERT INTO meal (uid, day, slot_key, position, recipe_id, product_id,"
        " amount, packaging_id, note, servings, portions_eaten, parts_total,"
        " parts_mine, state, validated_at, skipped_ingredient_ids, created_at,"
        " external_ref) VALUES (:uid, :day, :slot_key, :position, :recipe_id,"
        " :product_id, :amount, :packaging_id, :note, :servings, :portions_eaten,"
        " :parts_total, :parts_mine, :state, :validated_at,"
        " :skipped_ingredient_ids, :created_at, :external_ref)", values)
    conn.commit()


def _insert_recipe(conn, *, name, source="manual", source_ref=None, servings=1) -> None:
    conn.execute(
        "INSERT INTO recipe (name, servings, source, source_ref, created_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (name, servings, source, source_ref, "2026-08-20T10:00:00"))
    conn.commit()


@pytest.mark.parametrize("values, why", [
    ({"packaging_id": 1, "measure_id": 1}, "une quantité se dit dans UNE mesure"),
    ({"match_state": "auto", "product_id": None}, "un appariement suppose un produit"),
    ({"match_state": "confirmed", "product_id": None}, "confirmer, c'est désigner"),
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


def test_m004_lets_an_ignored_line_have_no_product(tmp_path):
    """« Ignoré » est un état de plein droit : sel, poivre, eau du robinet.

    On ignore précisément une ligne qu'on ne veut pas suivre — exiger de lui
    apparier un produit pour pouvoir l'ignorer serait se mordre la queue.
    """
    conn = _migrated(tmp_path)
    _insert_ingredient(conn, position=1, match_state="ignored", product_id=None)
    _insert_ingredient(conn, position=2, match_state="unmatched", product_id=None)
