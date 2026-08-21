import sqlite3

import pytest

from custom_components.home_stock.aisles import AISLES, CATEGORY_TO_AISLE
from custom_components.home_stock.storage.database import Database
from custom_components.home_stock.storage.migrations import (
    CURRENT_VERSION,
    MIGRATIONS,
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


def _seed_one_battery_event(conn) -> None:
    conn.execute("INSERT INTO battery (label, kind) VALUES ('Pile porte', 'primary')")
    conn.execute(
        "INSERT INTO battery_event (battery_id, occurred_at, kind) "
        "VALUES (1, '2026-08-20T10:00:00', 'install')")
    conn.commit()


def _seed_equipment_and_product(conn) -> None:
    conn.execute("INSERT INTO equipment (name) VALUES ('Aspirateur')")
    conn.execute("INSERT INTO product (name, base_unit) VALUES ('Sac aspirateur', 'piece')")
    conn.commit()


def test_migration_versions_are_contiguous_from_one():
    """Le lot 3 (`m004_recipes`) s'implémente en parallèle dans un autre
    worktree : tant que les deux n'ont pas fusionné, `MIGRATIONS` a un trou en
    4 et ce test ne peut pas exiger la suite stricte 1..N. Il vérifie à la
    place ce qui reste vrai des deux côtés du merge : les VERSION sont
    uniques, strictement croissantes, la première vaut 1, et CURRENT_VERSION
    est la dernière. Un DÉPASSEMENT, lui, reste fatal et muet dans tous les
    cas : `apply_migrations()` n'applique que les migrations dont la VERSION
    dépasse MAX(version), donc une base passée en 5 sans avoir vu m004 ne la
    verrait plus jamais, et l'intégration démarrerait sur un schéma amputé,
    sans une ligne de log."""
    versions = [m.VERSION for m in MIGRATIONS]
    assert len(set(versions)) == len(versions)
    assert versions == sorted(versions)
    assert versions[0] == 1
    assert CURRENT_VERSION == versions[-1]
    # À RESSERRER AU MERGE DU LOT 3 : une fois `m004_recipes` inséré dans
    # MIGRATIONS, remplacer les quatre assertions ci-dessus par la forme
    # stricte, qui est celle que ce test doit avoir en fin de compte :
    #     assert versions == list(range(1, len(versions) + 1))
    # Le trou 4 n'existe que le temps où les lots 3 et 5 vivent dans deux
    # worktrees séparés. `apply_migrations()` n'applique que les migrations
    # dont la VERSION dépasse MAX(version) : une base passée en 5 sans avoir
    # vu m004 ne la verrait PLUS JAMAIS, sans une ligne de log.


def test_migration_modules_are_named_after_their_version():
    """m003_consumption.VERSION == 3. Un module renuméroté à moitié (VERSION
    changée, fichier non renommé) est exactement le genre d'erreur que le
    merge des lots 3 et 5 peut produire."""
    for module in MIGRATIONS:
        assert module.__name__.rsplit(".", 1)[-1].startswith(f"m{module.VERSION:03d}_")


def test_m005_creates_the_four_tables(tmp_path):
    conn = _migrated(tmp_path)
    tables = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"battery", "battery_event", "equipment", "equipment_consumable"} <= tables
    columns = {r["name"] for r in conn.execute("PRAGMA table_info(battery)")}
    assert {"entity_registry_id", "device_id", "kind", "product_id", "cell_count",
            "tracked", "exclusion_reason", "low_percent", "keep_percent",
            "last_percent", "last_reading_at", "external_ref"} <= columns


def test_m005_adds_no_column_to_the_catalogue(tmp_path):
    """Le critère qui prouve que la réutilisation du catalogue en est une : si
    une pile avait eu besoin d'une colonne dans `product`, c'est que ce n'était
    pas un produit."""
    (tmp_path / "avant").mkdir()
    (tmp_path / "apres").mkdir()
    before = _migrated_to(tmp_path / "avant", version=4)
    after = _migrated(tmp_path / "apres")
    for table in ("product", "article", "batch"):
        assert ({r["name"] for r in before.execute(f"PRAGMA table_info({table})")}
                == {r["name"] for r in after.execute(f"PRAGMA table_info({table})")})


def test_m005_battery_event_is_append_only(tmp_path):
    conn = _migrated(tmp_path)
    _seed_one_battery_event(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE battery_event SET note = 'x' WHERE id = 1")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM battery_event WHERE id = 1")


def test_m005_refuses_an_unknown_kind(tmp_path):
    conn = _migrated(tmp_path)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO battery (label, kind) VALUES ('X', 'nimh')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO battery (label, kind, cell_count) "
                     "VALUES ('X', 'primary', 0)")


def test_m005_refuses_two_batteries_on_the_same_anchor(tmp_path):
    """L'ancre est unique — mais seulement quand elle existe : deux piles sans
    ancre (une poêle à pile, une pile déclarée avant d'être branchée) doivent
    coexister. C'est ce que l'index UNIQUE PARTIEL achète."""
    conn = _migrated(tmp_path)
    conn.execute("INSERT INTO battery (label, kind, entity_registry_id) "
                 "VALUES ('A', 'primary', 'abc')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO battery (label, kind, entity_registry_id) "
                     "VALUES ('B', 'primary', 'abc')")
    conn.execute("INSERT INTO battery (label, kind) VALUES ('C', 'primary')")
    conn.execute("INSERT INTO battery (label, kind) VALUES ('D', 'primary')")


def test_m005_refuses_two_identical_consumable_links(tmp_path):
    conn = _migrated(tmp_path)
    _seed_equipment_and_product(conn)
    conn.execute("INSERT INTO equipment_consumable (equipment_id, product_id, role) "
                 "VALUES (1, 1, 'filter')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO equipment_consumable (equipment_id, product_id, role) "
                     "VALUES (1, 1, 'filter')")


def test_m005_is_replayable(tmp_path):
    """Rejouer `apply_migrations` sur une base déjà en version 5 ne doit rien
    changer et rien lever."""
    conn = _migrated(tmp_path)
    assert apply_migrations(conn) == 5
    assert apply_migrations(conn) == 5


def test_m005_applies_on_a_copy_of_the_lot2_database(tmp_path):
    """Pas sur une base vide : sur une base qui a déjà des produits, des lots
    et des mouvements — c'est celle-là qui existe dans la maison."""
    conn = _migrated_to(tmp_path, version=4)
    _seed_one_movement(conn)
    assert apply_migrations(conn) == 5
    assert conn.execute("SELECT COUNT(*) AS n FROM movement").fetchone()["n"] == 1
