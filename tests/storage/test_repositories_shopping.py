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
