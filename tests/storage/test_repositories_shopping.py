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


def test_current_session_prefers_the_oldest_queued_trip(conn):
    """Among sessions waiting to be put away, the older one is the backlog to
    clear first — its chilled items have been out of a fridge the longest —
    even if a quicker, later trip was already checked out. An open shopping
    session still always wins over any of them."""
    older_id = repo.open_session(conn, started_at="2026-08-19T09:00:00", store=None)
    repo.set_session_state(conn, older_id, "to_store", closed_at="2026-08-19T09:30:00")

    newer_id = repo.open_session(conn, started_at="2026-08-19T10:00:00", store=None)
    repo.set_session_state(conn, newer_id, "to_store", closed_at="2026-08-19T10:15:00")

    current = repo.current_session(conn)
    assert current["id"] == older_id

    shopping_id = repo.open_session(conn, started_at="2026-08-19T11:00:00", store=None)

    current = repo.current_session(conn)
    assert current["id"] == shopping_id


def test_get_session_returns_none_for_an_unknown_id(conn):
    session_id = repo.open_session(conn, started_at="2026-08-19T10:00:00", store=None)

    assert repo.get_session(conn, session_id)["id"] == session_id
    assert repo.get_session(conn, session_id + 999) is None


def test_set_session_state_never_wipes_closed_at_as_a_side_effect(conn):
    session_id = repo.open_session(conn, started_at="2026-08-19T10:00:00", store=None)

    repo.set_session_state(conn, session_id, "to_store")
    assert repo.get_session(conn, session_id)["closed_at"] is None

    repo.set_session_state(conn, session_id, "done", closed_at="2026-08-19T12:00:00")
    assert repo.get_session(conn, session_id)["closed_at"] == "2026-08-19T12:00:00"

    # Regression test: a later state write with no closed_at must not erase
    # the timestamp already recorded above.
    repo.set_session_state(conn, session_id, "done")
    assert repo.get_session(conn, session_id)["closed_at"] == "2026-08-19T12:00:00"


def test_update_line_only_writes_the_field_actually_passed(conn):
    session_id = repo.open_session(conn, started_at="2026-08-19T10:00:00", store=None)
    line_id = repo.add_line(conn, session_id=session_id, article_id=1, quantity=500,
                            unit_price=0.002, scanned_at="2026-08-19T10:05:00",
                            idempotency_key="a")

    repo.update_line(conn, line_id, quantity=600)
    line = repo.list_lines(conn, session_id)[0]
    assert line["quantity"] == 600
    assert line["unit_price"] == pytest.approx(0.002)

    repo.update_line(conn, line_id, unit_price=0.0025)
    line = repo.list_lines(conn, session_id)[0]
    assert line["quantity"] == 600
    assert line["unit_price"] == pytest.approx(0.0025)


def test_remove_line_drops_only_that_line(conn):
    session_id = repo.open_session(conn, started_at="2026-08-19T10:00:00", store=None)
    line_id = repo.add_line(conn, session_id=session_id, article_id=1, quantity=500,
                            unit_price=0.002, scanned_at="2026-08-19T10:05:00",
                            idempotency_key="a")
    other_id = repo.add_line(conn, session_id=session_id, article_id=2, quantity=4,
                             unit_price=0.35, scanned_at="2026-08-19T10:06:00",
                             idempotency_key="b")

    repo.remove_line(conn, line_id)

    remaining = repo.list_lines(conn, session_id)
    assert [line["id"] for line in remaining] == [other_id]


def test_session_totals_on_an_empty_session(conn):
    session_id = repo.open_session(conn, started_at="2026-08-19T10:00:00", store=None)

    totals = repo.session_totals(conn, session_id)

    assert totals == {"lines": 0, "pending": 0, "total": 0.0}
    assert totals["pending"] is not None


def test_list_stores_ignores_prices_with_no_store(conn):
    repo.insert_price(conn, article_id=1, observed_on="2026-08-01",
                      price_per_base_unit=0.003, store="Carrefour", source="manual")
    repo.insert_price(conn, article_id=1, observed_on="2026-08-02",
                      price_per_base_unit=0.002, store="Leclerc", source="manual")
    repo.insert_price(conn, article_id=1, observed_on="2026-08-03",
                      price_per_base_unit=0.0021, store=None, source="manual")
    repo.insert_price(conn, article_id=1, observed_on="2026-08-04",
                      price_per_base_unit=0.0022, store="", source="manual")

    assert sorted(repo.list_stores(conn)) == ["Carrefour", "Leclerc"]


def test_latest_price_in_store_breaks_a_same_day_tie_by_insertion_order(conn):
    repo.insert_price(conn, article_id=1, observed_on="2026-08-02",
                      price_per_base_unit=0.002, store="Leclerc", source="manual")
    repo.insert_price(conn, article_id=1, observed_on="2026-08-02",
                      price_per_base_unit=0.0025, store="Leclerc", source="manual")

    assert repo.latest_price_in_store(conn, 1, "Leclerc") == pytest.approx(0.0025)


def test_lines_come_back_in_walking_order_not_scan_order(conn):
    """The cart is read while walking the shop, so the aisle order is the one
    that matters — not the order things were scanned in.

    The timestamps are deliberately in the opposite order of the expected
    result (Pâtes scanned first, Yaourt scanned second) so that an
    implementation that wrongly sorted by scan time would fail this test
    instead of passing it by accident.
    """
    session_id = repo.open_session(conn, started_at="2026-08-19T10:00:00", store=None)
    repo.add_line(conn, session_id=session_id, article_id=1, quantity=500,
                  unit_price=0.002, scanned_at="2026-08-19T10:01:00", idempotency_key="a")
    repo.add_line(conn, session_id=session_id, article_id=2, quantity=4,
                  unit_price=0.35, scanned_at="2026-08-19T10:05:00", idempotency_key="b")

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


# --- amendement A3 : la cascade ne se nourrit pas de ses suppositions -------

def _observe(conn, *, source, price, day, store="Leclerc"):
    return repo.insert_price(conn, article_id=1, observed_on=day,
                             price_per_base_unit=price, source=source, store=store)


def test_an_open_prices_observation_never_reaches_rank_one(conn):
    """LE test de la dette : deux lignes dans le même magasin, l'une
    `open_prices` plus récente, l'autre `manual` plus ancienne.
    `latest_price_in_store` rend la MANUELLE."""
    _observe(conn, source="manual", price=0.004, day="2026-08-01")
    _observe(conn, source="open_prices", price=0.009, day="2026-08-20")
    assert repo.latest_price_in_store(conn, 1, "Leclerc") == pytest.approx(0.004)


@pytest.mark.parametrize("source", ["receipt", "import", "manual"])
def test_a_receipt_and_an_import_observation_do_reach_rank_one(conn, source):
    """`receipt` et `import` sont des observations : le ticket et la reprise
    Grocy disent ce qui a réellement été payé."""
    _observe(conn, source=source, price=0.007, day="2026-08-20")
    assert repo.latest_price_in_store(conn, 1, "Leclerc") == pytest.approx(0.007)


@pytest.mark.parametrize("source", ["open_prices", "last_known", "store"])
def test_a_store_with_only_suggested_prices_answers_nothing(conn, source):
    """Et la cascade retombe alors sur Open Prices puis sur le dernier prix
    connu — comportement du lot 1, préservé."""
    _observe(conn, source=source, price=0.009, day="2026-08-20")
    assert repo.latest_price_in_store(conn, 1, "Leclerc") is None
