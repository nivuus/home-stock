from zoneinfo import ZoneInfo

import pytest

from custom_components.home_stock.application import PartsError, StockManager
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


def _seed_article(manager, *, base_unit: str = "g",
                  kcal_per_base_unit: float | None = None,
                  proteins: float | None = None) -> tuple[int, int]:
    """Seed one location, one product and one article. Returns (article_id, product_id).

    In a fresh test database this lands location, product and article all on
    id 1, which is what callers hardcoding product_id=1/location_id=1 rely on.
    """
    with manager.db.write() as conn:
        repo.insert_location(conn, name="Placard", kind="pantry")
        product_id = repo.insert_product(conn, name="Article", base_unit=base_unit)
        article_id = repo.insert_article(
            conn, product_id=product_id,
            kcal_per_base_unit=kcal_per_base_unit, proteins=proteins,
        )
        return article_id, product_id


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


def test_the_same_key_used_by_two_services_does_not_cross_match(manager, pasta):
    """idempotency_key is one UNIQUE column shared by every service: without a
    namespace per operation, add_stock replaying a key first used by consume
    would find consume's movement and hand back ITS batch_id."""
    manager.add_stock(article_id=pasta["article_id"], quantity=500,
                      location_id=pasta["location_id"], occurred_at="2026-08-18T09:00:00")
    manager.consume(product_id=pasta["product_id"], quantity=100,
                    occurred_at="2026-08-18T19:00:00", idempotency_key="shared-key")
    # Same literal key, different service: must do its own work, not resolve
    # to whatever consume() wrote under that key.
    new_batch_id = manager.add_stock(
        article_id=pasta["article_id"], quantity=50, location_id=pasta["location_id"],
        occurred_at="2026-08-19T09:00:00", idempotency_key="shared-key",
    )
    with manager.db.write() as conn:
        batch = conn.execute("SELECT * FROM batch WHERE id = ?", (new_batch_id,)).fetchone()
        purchase_count = conn.execute(
            "SELECT COUNT(*) AS n FROM movement WHERE reason = 'purchase'"
        ).fetchone()["n"]
    assert batch["initial"] == 50
    assert purchase_count == 2


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


def test_query_stock_ignores_case_and_accents(manager, pasta):
    """services.yaml promises matching "sans tenir compte de la casse ni des
    accents" — this is the voice path ("il reste des pâtes ?")."""
    manager.add_stock(article_id=pasta["article_id"], quantity=300,
                      location_id=pasta["location_id"], occurred_at="2026-08-01T10:00:00")
    assert [e["product_name"] for e in manager.query_stock(name="pates")] == ["Pâtes"]
    assert [e["product_name"] for e in manager.query_stock(name="PÂTES")] == ["Pâtes"]


def test_query_stock_matches_the_oe_ligature(manager):
    """NFD decomposition alone does not split œ/æ: "il reste des œufs ?" must
    still match a product literally named "Œufs"."""
    with manager.db.write() as conn:
        location_id = repo.insert_location(conn, name="Frigo", kind="fridge")
        product_id = repo.insert_product(conn, name="Œufs", base_unit="piece")
        article_id = repo.insert_article(conn, product_id=product_id)
    manager.add_stock(article_id=article_id, quantity=6, location_id=location_id,
                      occurred_at="2026-08-01T10:00:00")
    assert [e["product_name"] for e in manager.query_stock(name="oeufs")] == ["Œufs"]


def test_summary_reports_value_expirations_and_shortages(manager, pasta):
    manager.add_stock(article_id=pasta["article_id"], quantity=100,
                      location_id=pasta["location_id"], best_before="2026-08-19",
                      price_per_base_unit=0.004, occurred_at="2026-08-18T10:00:00")
    summary = manager.summary(expiration_alert_days=3, tz=ZoneInfo("UTC"), today="2026-08-18")
    assert summary["stock_value"] == pytest.approx(0.4)
    assert summary["batch_count"] == 1
    assert len(summary["expiring"]) == 1
    # 100 g in stock against a 200 g threshold.
    assert [s["product_name"] for s in summary["shortages"]] == ["Pâtes"]


def test_summary_breaks_the_stock_value_down_per_location(manager, pasta):
    """Design §8.1: sensor.home_stock_stock_value carries the value per
    location as an attribute, not just the grand total."""
    freezer_id = None
    with manager.db.write() as conn:
        freezer_id = repo.insert_location(conn, name="Congélateur", kind="freezer")
    manager.add_stock(article_id=pasta["article_id"], quantity=100,
                      location_id=pasta["location_id"], price_per_base_unit=0.004,
                      occurred_at="2026-08-18T10:00:00")
    manager.add_stock(article_id=pasta["article_id"], quantity=50,
                      location_id=freezer_id, price_per_base_unit=0.004,
                      occurred_at="2026-08-18T11:00:00")
    summary = manager.summary(expiration_alert_days=3, tz=ZoneInfo("UTC"), today="2026-08-18")
    assert summary["stock_value"] == pytest.approx(0.6)
    assert summary["stock_value_by_location"] == {
        "Placard": pytest.approx(0.4), "Congélateur": pytest.approx(0.2),
    }


# --- fix-review follow-up tests -------------------------------------------


def test_kcal_falls_back_to_the_product_reference_when_the_article_has_none(manager):
    """Generic/produce articles often carry no rate of their own (spec 7.4):
    kcal must fall back to product.reference_kcal, on both entry and exit."""
    with manager.db.write() as conn:
        location_id = repo.insert_location(conn, name="Frigo", kind="fridge")
        product_id = repo.insert_product(conn, name="Pomme", base_unit="g",
                                         reference_kcal=0.52)
        article_id = repo.insert_article(conn, product_id=product_id, label="Générique")
    manager.add_stock(article_id=article_id, quantity=200, location_id=location_id,
                      occurred_at="2026-08-18T10:00:00")
    manager.consume(product_id=product_id, quantity=100,
                    occurred_at="2026-08-18T19:00:00")
    with manager.db.write() as conn:
        purchase = conn.execute(
            "SELECT kcal FROM movement WHERE reason = 'purchase'").fetchone()
        consumption = conn.execute(
            "SELECT kcal FROM movement WHERE reason = 'consumption'").fetchone()
    assert purchase["kcal"] == pytest.approx(200 * 0.52)
    assert consumption["kcal"] == pytest.approx(100 * 0.52)


def test_summary_reports_a_shortage_when_stock_reaches_zero(manager, pasta):
    """A product with no open batch left (stock_rows sees nothing) must still
    show up as a shortage: this is the moment the alert matters most."""
    manager.add_stock(article_id=pasta["article_id"], quantity=100,
                      location_id=pasta["location_id"], occurred_at="2026-08-18T10:00:00")
    manager.consume(product_id=pasta["product_id"], quantity=100,
                    occurred_at="2026-08-18T19:00:00")
    summary = manager.summary(expiration_alert_days=3, tz=ZoneInfo("UTC"), today="2026-08-19")
    assert summary["batch_count"] == 0
    assert [s["product_name"] for s in summary["shortages"]] == ["Pâtes"]


def test_idempotency_replay_does_not_match_on_like_wildcards(manager, pasta):
    """'_' and '%' are SQL LIKE wildcards. An idempotency key containing one
    must be matched literally on replay, not as a pattern."""
    manager.add_stock(article_id=pasta["article_id"], quantity=100,
                      location_id=pasta["location_id"], best_before="2026-08-20",
                      occurred_at="2026-08-01T10:00:00")
    manager.add_stock(article_id=pasta["article_id"], quantity=100,
                      location_id=pasta["location_id"], best_before="2026-09-20",
                      occurred_at="2026-08-10T10:00:00")
    # Spans both batches, so it writes movements keyed "dinnerX1" and
    # "dinnerX1#1". Without LIKE escaping, the pattern built below for
    # "dinner_1" ("dinner_1#%") would also match "dinnerX1#1", since '_' is a
    # wildcard for "any single character".
    unrelated = manager.consume(product_id=pasta["product_id"], quantity=150,
                                occurred_at="2026-08-18T18:00:00",
                                idempotency_key="dinnerX1")
    assert len(unrelated) == 2
    # Drain the leftover so the next consumption lands on a single fresh batch.
    manager.consume(product_id=pasta["product_id"], quantity=50,
                    occurred_at="2026-08-18T18:30:00")

    manager.add_stock(article_id=pasta["article_id"], quantity=500,
                      location_id=pasta["location_id"], occurred_at="2026-08-18T09:00:00")
    first = manager.consume(product_id=pasta["product_id"], quantity=200,
                            occurred_at="2026-08-18T19:00:00", idempotency_key="dinner_1")
    replay = manager.consume(product_id=pasta["product_id"], quantity=200,
                             occurred_at="2026-08-18T19:00:00", idempotency_key="dinner_1")
    assert replay == first
    assert unrelated[1] not in replay


def test_idempotency_key_survives_a_replay_across_two_batches(manager, pasta):
    """The trickiest rule: a consumption spanning two batches writes
    "key" and "key#1". A replay must return both, and write nothing new."""
    manager.add_stock(article_id=pasta["article_id"], quantity=300,
                      location_id=pasta["location_id"], best_before="2026-08-20",
                      price_per_base_unit=0.004, occurred_at="2026-08-01T10:00:00")
    manager.add_stock(article_id=pasta["article_id"], quantity=500,
                      location_id=pasta["location_id"], best_before="2026-09-20",
                      price_per_base_unit=0.005, occurred_at="2026-08-10T10:00:00")
    first = manager.consume(product_id=pasta["product_id"], quantity=700,
                            occurred_at="2026-08-18T19:00:00", idempotency_key="dinner-2")
    assert len(first) == 2
    with manager.db.write() as conn:
        before = conn.execute("SELECT COUNT(*) AS n FROM movement").fetchone()["n"]
    replay = manager.consume(product_id=pasta["product_id"], quantity=700,
                             occurred_at="2026-08-18T19:00:00", idempotency_key="dinner-2")
    assert replay == first
    with manager.db.write() as conn:
        after = conn.execute("SELECT COUNT(*) AS n FROM movement").fetchone()["n"]
    assert after == before


def test_add_stock_replay_returns_the_same_batch_without_duplicating(manager, pasta):
    first = manager.add_stock(article_id=pasta["article_id"], quantity=500,
                              location_id=pasta["location_id"],
                              occurred_at="2026-08-18T10:00:00",
                              idempotency_key="delivery-1")
    replay = manager.add_stock(article_id=pasta["article_id"], quantity=500,
                               location_id=pasta["location_id"],
                               occurred_at="2026-08-18T10:00:00",
                               idempotency_key="delivery-1")
    assert replay == first
    with manager.db.write() as conn:
        batches = conn.execute("SELECT COUNT(*) AS n FROM batch").fetchone()["n"]
        movements = conn.execute("SELECT COUNT(*) AS n FROM movement").fetchone()["n"]
    assert batches == 1
    assert movements == 1


def test_summary_excludes_unpriced_batches_from_stock_value(manager, pasta):
    manager.add_stock(article_id=pasta["article_id"], quantity=100,
                      location_id=pasta["location_id"], price_per_base_unit=0.004,
                      occurred_at="2026-08-18T10:00:00")
    manager.add_stock(article_id=pasta["article_id"], quantity=50,
                      location_id=pasta["location_id"], occurred_at="2026-08-18T11:00:00")
    summary = manager.summary(expiration_alert_days=3, tz=ZoneInfo("UTC"), today="2026-08-18")
    assert summary["stock_value"] == pytest.approx(0.4)   # only the priced batch
    assert summary["batch_count"] == 2
    assert summary["unpriced_batches"] == 1


def test_export_journal_returns_the_full_movement_history(manager, pasta):
    manager.add_stock(article_id=pasta["article_id"], quantity=500,
                      location_id=pasta["location_id"], price_per_base_unit=0.004,
                      occurred_at="2026-08-18T10:00:00")
    manager.consume(product_id=pasta["product_id"], quantity=200,
                    occurred_at="2026-08-18T19:00:00")
    journal = manager.export_journal()
    assert [entry["reason"] for entry in journal] == ["purchase", "consumption"]
    assert journal[0]["quantity"] == 500
    assert journal[1]["quantity"] == -200


def test_consume_accepts_a_waste_reason(manager, pasta):
    manager.add_stock(article_id=pasta["article_id"], quantity=500,
                      location_id=pasta["location_id"], price_per_base_unit=0.004,
                      occurred_at="2026-08-18T10:00:00")
    movement_ids = manager.consume(product_id=pasta["product_id"], quantity=50,
                                   reason="waste", occurred_at="2026-08-18T19:00:00")
    with manager.db.write() as conn:
        movement = conn.execute("SELECT * FROM movement WHERE id = ?",
                                (movement_ids[0],)).fetchone()
    assert movement["reason"] == "waste"
    assert movement["quantity"] == -50


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


def test_consume_batch_also_falls_back_to_the_product_kcal_reference(manager):
    """Same rule as consume() (spec 7.4): a generic article with no rate of its
    own must still record kcal, taken from product.reference_kcal."""
    with manager.db.write() as conn:
        location_id = repo.insert_location(conn, name="Frigo", kind="fridge")
        product_id = repo.insert_product(conn, name="Pomme", base_unit="g",
                                         reference_kcal=0.52)
        article_id = repo.insert_article(conn, product_id=product_id, label="Générique")
    batch_id = manager.add_stock(article_id=article_id, quantity=200,
                                 location_id=location_id,
                                 occurred_at="2026-08-18T10:00:00")
    manager.consume_batch(batch_id, occurred_at="2026-08-18T19:00:00")
    with manager.db.write() as conn:
        consumption = conn.execute(
            "SELECT kcal FROM movement WHERE reason = 'consumption'").fetchone()
    assert consumption["kcal"] == pytest.approx(200 * 0.52)


def test_consume_batch_refuses_to_over_consume(manager, pasta):
    batch_id = manager.add_stock(article_id=pasta["article_id"], quantity=200,
                                 location_id=pasta["location_id"],
                                 occurred_at="2026-08-01T10:00:00")
    with pytest.raises(InsufficientStock):
        manager.consume_batch(batch_id, quantity=250, occurred_at="2026-08-18T19:00:00")


def test_consume_batch_refuses_an_unknown_batch(manager):
    with pytest.raises(ValueError, match="unknown or closed batch"):
        manager.consume_batch(999999, occurred_at="2026-08-18T19:00:00")


def test_consume_batch_refuses_a_batch_of_another_product(manager, pasta):
    """product_id, when given, is checked against the batch's own article —
    the pair is refused rather than trusting either side of it (lot 2: the
    panel always sends both, targeting the batch FIFO would pick)."""
    batch_id = manager.add_stock(article_id=pasta["article_id"], quantity=200,
                                 location_id=pasta["location_id"],
                                 occurred_at="2026-08-18T10:00:00")
    with manager.db.write() as conn:
        other_product_id = repo.insert_product(conn, name="Riz", base_unit="g")

    with pytest.raises(ValueError, match="does not belong to product"):
        manager.consume_batch(batch_id, product_id=other_product_id,
                              occurred_at="2026-08-18T19:00:00")

    # Refused before any write: the batch is untouched and no movement exists.
    with manager.db.write() as conn:
        batch = conn.execute("SELECT * FROM batch WHERE id = ?", (batch_id,)).fetchone()
        movement = conn.execute(
            "SELECT * FROM movement WHERE reason = 'consumption'").fetchone()
    assert batch["remaining"] == 200
    assert movement is None


def test_summary_totals_keep_waste_and_expired_out_of_kcal_and_cost(manager, pasta):
    """Lot 2, amendment A2: kcal_total and cost_total now count consumption
    only, and cost_waste_total picks up waste and expiry instead, so that
    cost_total + cost_waste_total gives back the former, single total."""
    batch_id = manager.add_stock(article_id=pasta["article_id"], quantity=500,
                                 location_id=pasta["location_id"], price_per_base_unit=0.004,
                                 occurred_at="2026-08-01T10:00:00")
    manager.consume(product_id=pasta["product_id"], quantity=100, reason="waste",
                    occurred_at="2026-08-02T10:00:00")
    manager.consume_batch(batch_id, quantity=50, reason="expired",
                          occurred_at="2026-08-03T10:00:00")
    summary = manager.summary(expiration_alert_days=3, tz=ZoneInfo("UTC"), today="2026-08-18")
    # 100 g waste + 50 g expired, at 3.5 kcal/g and 0.004 EUR/g each — none of
    # it eaten, so kcal_total stays at zero and the money moves to
    # cost_waste_total instead of cost_total.
    assert summary["kcal_total"] == 0.0
    assert summary["cost_total"] == 0.0
    assert summary["cost_waste_total"] == pytest.approx(150 * 0.004, rel=1e-3)


def test_every_movement_written_carries_its_unit(manager):
    """A quantity without its unit is unreadable the day the product converts."""
    article_id, product_id = _seed_article(manager, base_unit="g")

    manager.add_stock(article_id=article_id, quantity=500, location_id=1)
    manager.consume(product_id=product_id, quantity=200, reason="consumption")

    with manager.db.write() as conn:
        rows = conn.execute("SELECT reason, base_unit FROM movement ORDER BY id").fetchall()
    assert [r["base_unit"] for r in rows] == ["g", "g"]
    assert all(r["base_unit"] is not None for r in rows)


def test_the_unit_written_is_the_product_s_own(manager):
    article_id, _product_id = _seed_article(manager, base_unit="ml")

    manager.add_stock(article_id=article_id, quantity=750, location_id=1)

    with manager.db.write() as conn:
        row = conn.execute("SELECT base_unit FROM movement ORDER BY id DESC LIMIT 1").fetchone()
    assert row["base_unit"] == "ml"


def test_add_stock_freezes_the_macros_of_the_moment(manager):
    """The purchase movement must freeze macros too: add_stock is the third of
    the three call sites this lot wires (add_stock, consume, consume_batch),
    and only this one had no test reading `movement.proteins` back."""
    article_id, _product_id = _seed_article(manager, base_unit="g",
                                            kcal_per_base_unit=1.2, proteins=0.05)

    manager.add_stock(article_id=article_id, quantity=500.0, location_id=1)

    with manager.db.write() as conn:
        conn.execute("UPDATE article SET proteins = 99.0 WHERE id = ?", (article_id,))

    row = manager.db.read().execute(
        "SELECT proteins FROM movement WHERE reason = 'purchase'").fetchone()
    assert row["proteins"] == pytest.approx(25.0)


def test_add_stock_of_an_article_without_macros_writes_nulls(manager):
    article_id, _product_id = _seed_article(manager, base_unit="g",
                                            kcal_per_base_unit=None, proteins=None)

    manager.add_stock(article_id=article_id, quantity=500.0, location_id=1)

    row = manager.db.read().execute(
        "SELECT proteins FROM movement WHERE reason = 'purchase'").fetchone()
    assert row["proteins"] is None


def test_consuming_freezes_the_macros_of_the_moment(manager):
    """The test that actually matters: resyncing the article AFTER the fact
    must not change the movement already written. That is the whole point
    of these columns, not an implementation detail."""
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
    article_id, _product_id = _seed_article(manager, base_unit="g",
                                            kcal_per_base_unit=1.2, proteins=0.05)
    batch_id = manager.add_stock(article_id=article_id, quantity=500.0, location_id=1)

    manager.consume_batch(batch_id, quantity=100.0)

    row = manager.db.read().execute(
        "SELECT proteins FROM movement WHERE reason = 'consumption'").fetchone()
    assert row["proteins"] == pytest.approx(5.0)


def test_parts_are_written_on_a_consumption(manager):
    article_id, product_id = _seed_article(manager, base_unit="g", kcal_per_base_unit=1.2)
    manager.add_stock(article_id=article_id, quantity=800.0, location_id=1)

    manager.consume(product_id=product_id, quantity=400.0, parts_total=4, parts_mine=1)

    row = manager.db.read().execute(
        "SELECT parts_total, parts_mine, kcal FROM movement"
        " WHERE reason = 'consumption'").fetchone()
    assert (row["parts_total"], row["parts_mine"]) == (4, 1)
    # The FROZEN kcal stays that of everything taken out of stock: the
    # division by the parts happens at read time, never at write time —
    # otherwise the quantity and the kcal of the same movement would no
    # longer agree with each other.
    assert row["kcal"] == pytest.approx(480.0)


def test_parts_default_to_nothing_at_all(manager):
    """Without parts, the columns stay NULL — and NULL means 1/1 at read
    time. Writing 1/1 in stone would taint the whole history predating lot 2
    with data that was never actually entered."""
    article_id, product_id = _seed_article(manager, base_unit="g")
    manager.add_stock(article_id=article_id, quantity=800.0, location_id=1)

    manager.consume(product_id=product_id, quantity=100.0)

    row = manager.db.read().execute(
        "SELECT parts_total, parts_mine FROM movement"
        " WHERE reason = 'consumption'").fetchone()
    assert row["parts_total"] is None and row["parts_mine"] is None


def test_parts_mine_may_be_zero(manager):
    """"I served my guests, I didn't eat any of it": the stock leaves, the
    food journal carries none of it."""
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


def test_too_many_parts_served_is_refused(manager):
    """The symmetric case of test_zero_parts_served_is_refused: past
    MAX_PARTS, `parts_total` is not a shared meal any more, it is a typo."""
    article_id, product_id = _seed_article(manager, base_unit="g")
    manager.add_stock(article_id=article_id, quantity=800.0, location_id=1)
    with pytest.raises(PartsError):
        manager.consume(product_id=product_id, quantity=100.0,
                        parts_total=25, parts_mine=1)

    assert manager.db.read().execute("SELECT COUNT(*) FROM movement"
                                     " WHERE reason = 'consumption'").fetchone()[0] == 0


def test_parts_on_waste_are_refused(manager):
    """Nobody shares a bin: accepting parts here would write data that makes
    no sense, and that the day's totals ignore anyway."""
    article_id, product_id = _seed_article(manager, base_unit="g")
    manager.add_stock(article_id=article_id, quantity=800.0, location_id=1)
    with pytest.raises(PartsError):
        manager.consume(product_id=product_id, quantity=100.0, reason="waste",
                        parts_total=2, parts_mine=1)


def test_only_one_part_given_is_refused(manager):
    """Giving one without the other is an incomplete entry, not a default."""
    article_id, product_id = _seed_article(manager, base_unit="g")
    manager.add_stock(article_id=article_id, quantity=800.0, location_id=1)
    with pytest.raises(PartsError):
        manager.consume(product_id=product_id, quantity=100.0, parts_total=4)
    with pytest.raises(PartsError):
        manager.consume(product_id=product_id, quantity=100.0, parts_mine=1)


def test_parts_spread_over_several_batches_land_on_every_movement(manager):
    """A consumption spanning two batches writes two movements: both carry
    the same parts, otherwise half the meal would be counted for the whole
    household."""
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


# --- lot 3 (amendement A2) : manger un plat compte les valeurs DU PLAT -------

def test_consume_batch_counts_the_batch_nutrition_over_the_article(manager, pasta):
    """Ce que le plan demandait de vérifier par un test plutôt qu'à la lecture.

    L'article « Panzani 500 g » titre 3,5 kcal/g. Le lot, lui, est une part de
    lasagnes cuisinée : il porte ses propres 1,8 kcal/g. Manger ce lot doit
    inscrire 1,8 dans le mouvement — sinon une assiette de restes serait
    comptée au tarif de ses pâtes crues.
    """
    with manager.db.write() as conn:
        batch_id = repo.insert_batch(
            conn, article_id=pasta["article_id"], location_id=pasta["location_id"],
            quantity=300.0, entered_at="2026-08-21T18:00:00",
            nutrition={"kcal_per_base_unit": 1.8, "proteins": 0.09})

    manager.consume_batch(batch_id, quantity=100.0)

    row = manager.db.read().execute(
        "SELECT kcal, proteins FROM movement WHERE batch_id = ?", (batch_id,)
    ).fetchone()
    assert row["kcal"] == pytest.approx(180.0)      # 100 g x 1,8 — pas 350
    assert row["proteins"] == pytest.approx(9.0)


def test_consume_batch_still_reads_the_article_when_the_batch_is_silent(manager, pasta):
    """La cascade ne casse rien : un lot ordinaire compte comme avant."""
    with manager.db.write() as conn:
        batch_id = repo.insert_batch(
            conn, article_id=pasta["article_id"], location_id=pasta["location_id"],
            quantity=300.0, entered_at="2026-08-21T18:00:00")

    manager.consume_batch(batch_id, quantity=100.0)

    row = manager.db.read().execute(
        "SELECT kcal FROM movement WHERE batch_id = ?", (batch_id,)).fetchone()
    assert row["kcal"] == pytest.approx(350.0)      # 100 g x 3,5


# --- lot 3 (amendement A3) : add_stock reste le seul chemin d'entrée ---------

def _one(manager, sql, params=()):
    return manager.db.read().execute(sql, params).fetchone()


def test_add_stock_still_writes_purchase_by_default(manager):
    article_id, _ = _seed_article(manager)
    manager.add_stock(article_id=article_id, quantity=500.0, location_id=1)
    assert _one(manager, "SELECT reason FROM movement")["reason"] == "purchase"


def test_add_stock_can_write_another_reason(manager):
    article_id, _ = _seed_article(manager)
    manager.add_stock(article_id=article_id, quantity=3.0, location_id=1,
                      reason="cooked")
    assert _one(manager, "SELECT reason FROM movement")["reason"] == "cooked"


def test_add_stock_freezes_the_nutrition_on_the_batch(manager):
    article_id, _ = _seed_article(manager)
    batch_id = manager.add_stock(
        article_id=article_id, quantity=3.0, location_id=1, reason="cooked",
        nutrition={"kcal_per_base_unit": 180.0, "proteins": 9.0})
    row = _one(manager, "SELECT * FROM batch WHERE id = ?", (batch_id,))
    assert (row["kcal_per_base_unit"], row["proteins"]) == (180.0, 9.0)
    assert row["fiber"] is None          # non dit reste inconnu, pas zéro


def test_the_entry_movement_uses_the_frozen_nutrition_not_the_article(manager):
    """Le mouvement d'entrée du plat vaut ce que le plat vaut, pas ce que
    l'article générique dirait."""
    article_id, _ = _seed_article(manager, kcal_per_base_unit=3.5)
    batch_id = manager.add_stock(
        article_id=article_id, quantity=3.0, location_id=1, reason="cooked",
        nutrition={"kcal_per_base_unit": 180.0})
    assert _one(manager, "SELECT kcal FROM movement WHERE batch_id = ?",
                (batch_id,))["kcal"] == pytest.approx(540.0)


def test_a_frozen_null_macro_still_reads_the_article(manager):
    """La cascade de la tâche 2 vaut aussi à l'entrée : le plat sait ses
    calories, il ne sait pas ses protéines, l'article les connaît."""
    article_id, _ = _seed_article(manager, kcal_per_base_unit=3.5, proteins=0.09)
    batch_id = manager.add_stock(
        article_id=article_id, quantity=3.0, location_id=1, reason="cooked",
        nutrition={"kcal_per_base_unit": 180.0})
    row = _one(manager, "SELECT kcal, proteins FROM movement WHERE batch_id = ?",
               (batch_id,))
    assert row["kcal"] == pytest.approx(540.0)
    assert row["proteins"] == pytest.approx(0.27)      # 3 x 0,09, pris sur l'article


def test_cooked_is_a_reason_but_never_a_counted_one():
    from custom_components.home_stock.const import CONSUME_REASONS, REASONS
    assert "cooked" in REASONS
    assert "cooked" not in CONSUME_REASONS


def test_add_stock_stays_idempotent_with_the_new_arguments(manager):
    article_id, _ = _seed_article(manager)
    first = manager.add_stock(article_id=article_id, quantity=3.0, location_id=1,
                              reason="cooked", idempotency_key="k",
                              nutrition={"kcal_per_base_unit": 180.0})
    second = manager.add_stock(article_id=article_id, quantity=3.0, location_id=1,
                               reason="cooked", idempotency_key="k",
                               nutrition={"kcal_per_base_unit": 180.0})
    assert first == second
    assert _one(manager, "SELECT COUNT(*) c FROM movement")["c"] == 1


def test_add_stock_refuses_a_reason_it_does_not_know(manager):
    """Un motif inconnu atteindrait `movement.reason`, que le CHECK du schéma
    refuse — autant le dire ici, avec le nom du motif fautif."""
    article_id, _ = _seed_article(manager)
    with pytest.raises(ValueError, match="grignotage"):
        manager.add_stock(article_id=article_id, quantity=3.0, location_id=1,
                          reason="grignotage")
