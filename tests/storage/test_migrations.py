import sqlite3

import pytest

from custom_components.home_stock.aisles import AISLES, CATEGORY_TO_AISLE
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

    assert apply_migrations(conn) == 2

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
