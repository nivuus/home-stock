"""Executing a conversion: one transaction, an honest journal, no lost stock,
and no lost money."""
import sqlite3
from zoneinfo import ZoneInfo

import pytest

from custom_components.home_stock.application import StockManager
from custom_components.home_stock.domain.conversion import ConversionError
from custom_components.home_stock.storage import repositories as repo
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
    # Assert the row COUNT first: an empty result set also passes an `all(...)`
    # over nothing, so this used to pass even when the conversion wrote no
    # movement at all.
    assert len(rows) == 2
    assert all(r["kcal"] is None and r["cost"] is None for r in rows)


def test_nutrition_is_divided_by_the_weight_of_its_own_article(manager):
    # reference_quantity (400) deliberately differs from article 10's own net
    # weight (500): if the code rescaled by the reference instead of the
    # article's own weight, a reference that happened to match the weight
    # would let the bug through undetected.
    manager.convert_product_unit(product_id=1, to_unit="g", reference_quantity=400)

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
    # reference_quantity (400) again differs from article 10's own weight
    # (500), so the two articles' packagings can only agree with the test if
    # each is rescaled by its own factor, not by a shared reference.
    manager.convert_product_unit(product_id=1, to_unit="g", reference_quantity=400,
                                 packaging_name="Paquet")

    with manager.db.write() as conn:
        article_10 = conn.execute(
            "SELECT name, base_quantity, is_purchase_default FROM packaging "
            "WHERE scope = 'article' AND target_id = 10").fetchone()
        article_11 = conn.execute(
            "SELECT base_quantity FROM packaging "
            "WHERE scope = 'article' AND target_id = 11").fetchone()
    # Article 10 packages by its own 500 g net weight.
    assert (article_10["name"], article_10["base_quantity"],
            article_10["is_purchase_default"]) == ("Paquet", 500.0, 1)
    # Article 11 has no weight of its own, so it falls back to the 400 g
    # reference the human confirmed at conversion time.
    assert article_11["base_quantity"] == pytest.approx(400.0)


def test_an_article_with_no_weight_uses_the_reference(manager):
    _add(manager, 11, 3)

    manager.convert_product_unit(product_id=1, to_unit="g", reference_quantity=400)

    with manager.db.write() as conn:
        row = conn.execute("SELECT remaining FROM batch WHERE article_id = 11").fetchone()
    assert row["remaining"] == pytest.approx(1200.0)


def test_converting_preserves_the_value_of_the_stock_in_euros(manager):
    """A change of unit is a change of denomination, not a rewriting of
    history: 1.20 €/packet and 0.0024 €/g are the same fact said twice, so
    the stock's total value in euros must not move."""
    manager.add_stock(article_id=10, quantity=2, location_id=1, price_per_base_unit=1.20)

    before = manager.summary(expiration_alert_days=7, tz=ZoneInfo("UTC"))["stock_value"]
    assert before == pytest.approx(2.40)

    manager.convert_product_unit(product_id=1, to_unit="g", reference_quantity=500)

    after = manager.summary(expiration_alert_days=7, tz=ZoneInfo("UTC"))["stock_value"]
    assert after == pytest.approx(before)
    assert after == pytest.approx(2.40)


def test_a_consumption_after_conversion_charges_the_same_money(manager):
    manager.add_stock(article_id=10, quantity=2, location_id=1, price_per_base_unit=1.20)
    manager.convert_product_unit(product_id=1, to_unit="g", reference_quantity=500)

    movement_ids = manager.consume(product_id=1, quantity=100)   # 100 g of 1000 g

    with manager.db.write() as conn:
        row = conn.execute(
            "SELECT cost FROM movement WHERE id = ?", (movement_ids[0],)).fetchone()
    # 100 g at 0.0024 €/g (1.20 € per 500 g packet, rescaled) is 0.24 €, not
    # the 120.00 € a price left in €/piece would have written.
    assert row["cost"] == pytest.approx(0.24)


def test_price_history_keeps_the_next_purchase_suggesting_the_same_money(manager):
    """price rows (not just the batch's own price_per_base_unit) feed the
    purchase-suggestion cascade (repo.latest_price / latest_price_in_store):
    left in the old unit, the next scan would suggest 500x the real price.
    Each article rescales by its OWN factor, not a single product-wide one —
    pinned here with two articles whose factors differ."""
    with manager.db.write() as conn:
        repo.insert_price(conn, article_id=10, observed_on="2026-08-01",
                          price_per_base_unit=1.20, source="manual")
        repo.insert_price(conn, article_id=11, observed_on="2026-08-01",
                          price_per_base_unit=2.00, source="manual")

    # reference_quantity (400) differs from article 10's own net weight
    # (500): article 10 rescales by 500 (its own weight), article 11 by 400
    # (the reference it falls back to, having no weight of its own).
    manager.convert_product_unit(product_id=1, to_unit="g", reference_quantity=400)

    with manager.db.write() as conn:
        price_10 = conn.execute(
            "SELECT price_per_base_unit FROM price WHERE article_id = 10").fetchone()[0]
        price_11 = conn.execute(
            "SELECT price_per_base_unit FROM price WHERE article_id = 11").fetchone()[0]

    assert price_10 == pytest.approx(0.0024)       # 1.20 / 500, article 10's own weight
    assert price_10 != pytest.approx(1.20 / 400)   # not a single product-wide factor
    assert price_11 == pytest.approx(0.005)        # 2.00 / 400, the reference fallback


def test_converting_twice_is_refused_rather_than_doubling_the_stock(manager):
    _add(manager, 10, 2)
    manager.convert_product_unit(product_id=1, to_unit="g", reference_quantity=500)

    with pytest.raises(ConversionError):
        manager.convert_product_unit(product_id=1, to_unit="g", reference_quantity=500)


def test_a_conversion_is_refused_while_shopping_is_pending(manager):
    """shopping_line.quantity is stored in the product's base unit as a
    promise about a quantity not yet turned into a batch. Converting under a
    pending line would silently reinterpret it the moment it is put away."""
    with manager.db.write() as conn:
        session_id = repo.open_session(conn, started_at="2026-08-19T10:00:00", store=None)
        repo.add_line(conn, session_id=session_id, article_id=10, quantity=2,
                      unit_price=None, scanned_at="2026-08-19T10:05:00",
                      idempotency_key=None)

    with pytest.raises(ConversionError):
        manager.convert_product_unit(product_id=1, to_unit="g", reference_quantity=500)

    # Refused before any write: nothing moved.
    with manager.db.write() as conn:
        assert conn.execute("SELECT base_unit FROM product WHERE id = 1").fetchone()[0] == "piece"


def test_a_failure_half_way_leaves_the_product_untouched(manager, monkeypatch):
    """One transaction: a crash after the first batch must not leave half the
    stock in grams and half in pieces — nor leave standing the writes that DID
    run before the crash (nutrition rescale, packaging, price rescale,
    conversion movements), which is what a real rollback, and only a real
    rollback, undoes."""
    _add(manager, 10, 2)

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
        # The article-nutrition loop runs entirely before the batch loop that
        # crashes, so these writes DID happen inside the transaction. Only a
        # real rollback — not merely the crash stopping later writes — makes
        # them false again.
        article = conn.execute(
            "SELECT kcal_per_base_unit, proteins FROM article WHERE id = 10").fetchone()
        assert article["kcal_per_base_unit"] == pytest.approx(1750)
        assert article["proteins"] == pytest.approx(60)
        assert conn.execute("SELECT COUNT(*) FROM packaging").fetchone()[0] == 0
        assert conn.execute(
            "SELECT COUNT(*) FROM movement WHERE reason = 'conversion'"
        ).fetchone()[0] == 0
