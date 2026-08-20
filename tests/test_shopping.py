"""The shopping session, end to end, without Home Assistant."""
import pytest

from custom_components.home_stock import application as application_module
from custom_components.home_stock import shopping as shopping_module
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


def test_a_shelf_life_is_learned_from_what_was_actually_posed(service, monkeypatch):
    """The median of the last three, not the last one — pinned independently
    of the day this test happens to run.

    entered_at (read back by recent_shelf_lives) comes from
    application._now(), used inside StockManager.add_stock; scanned_at and
    stored_at come from shopping._now(). Both module-level clocks are frozen
    here — patching only one would leave the batch's entered_at floating on
    the real date, and the fix round exists precisely because that happened.
    """
    frozen_now = "2026-01-01T10:00:00"
    monkeypatch.setattr(shopping_module, "_now", lambda: frozen_now)
    monkeypatch.setattr(application_module, "_now", lambda: frozen_now)

    service.start(store="Leclerc")
    # entered_at is pinned to 2026-01-01. Offsets to best_before are the same
    # {13, 15, 14} days as the original test, stored out of date order so the
    # *last* line posed does not carry the middle offset.
    for index, best_before in enumerate(["2026-01-14", "2026-01-16", "2026-01-15"]):
        line = service.add_line(article_id=10, quantity=500, unit_price=None,
                                idempotency_key=f"a{index}")
        service.store_line(line["id"], location_id=1, best_before=best_before)

    with service.manager.db.write() as conn:
        row = conn.execute(
            "SELECT default_shelf_life_days FROM product WHERE id = 1").fetchone()
    # Median of {13, 15, 14} sorted -> {13, 14, 15} is 14 (2026-01-15, the
    # middle date entered) — not 15 (2026-01-16, the last one stored). This
    # literal is hand-computed, not re-derived with the production code's own
    # julianday/median arithmetic: doing that would only prove the code
    # agrees with itself.
    assert row["default_shelf_life_days"] == 14


def test_storing_a_priced_line_writes_exactly_one_price_row(service):
    """The observation happens once, in the aisle, with its shop.

    Regression for the fix round: add_stock used to insert a second,
    unconditional price row at put-away time, stamped with store=None,
    silently doubling every priced line in the price history that feeds the
    suggestion cascade. Asserting the count, not just presence, is the point.
    """
    service.start(store="Leclerc")
    line = service.add_line(article_id=10, quantity=500, unit_price=0.002,
                            idempotency_key="a")
    service.checkout()

    service.store_line(line["id"], location_id=1, best_before=None)

    with service.manager.db.write() as conn:
        rows = conn.execute("SELECT store, source FROM price").fetchall()
    assert len(rows) == 1
    assert (rows[0]["store"], rows[0]["source"]) == ("Leclerc", "manual")


def test_update_line_refuses_a_stored_line_and_writes_only_the_given_field(service):
    service.start(store="Leclerc")
    line = service.add_line(article_id=10, quantity=500, unit_price=0.002,
                            idempotency_key="a")

    updated = service.update_line(line["id"], quantity=750)

    assert updated["quantity"] == pytest.approx(750)
    assert updated["unit_price"] == pytest.approx(0.002)  # untouched by the update

    service.checkout()
    service.store_line(line["id"], location_id=1, best_before=None)

    with pytest.raises(ShoppingError, match="rangée"):
        service.update_line(line["id"], quantity=1000)


def test_close_moves_an_open_session_to_done_and_stamps_closed_at(service):
    service.start(store="Leclerc")

    result = service.close()

    assert result["state"] == "done"
    assert result["closed_at"] is not None
    assert service.current() is None


def test_close_without_a_session_is_refused(service):
    with pytest.raises(ShoppingError):
        service.close()
