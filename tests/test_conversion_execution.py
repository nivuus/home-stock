"""Executing a conversion: one transaction, an honest journal, no lost stock."""
import sqlite3

import pytest

from custom_components.home_stock.application import StockManager
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
    assert all(r["kcal"] is None and r["cost"] is None for r in rows)


def test_nutrition_is_divided_by_the_weight_of_its_own_article(manager):
    manager.convert_product_unit(product_id=1, to_unit="g", reference_quantity=500)

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
    manager.convert_product_unit(product_id=1, to_unit="g", reference_quantity=500,
                                 packaging_name="Paquet")

    with manager.db.write() as conn:
        row = conn.execute(
            "SELECT name, base_quantity, is_purchase_default FROM packaging "
            "WHERE scope = 'article' AND target_id = 10").fetchone()
    assert (row["name"], row["base_quantity"], row["is_purchase_default"]) == ("Paquet", 500.0, 1)


def test_an_article_with_no_weight_uses_the_reference(manager):
    _add(manager, 11, 3)

    manager.convert_product_unit(product_id=1, to_unit="g", reference_quantity=400)

    with manager.db.write() as conn:
        row = conn.execute("SELECT remaining FROM batch WHERE article_id = 11").fetchone()
    assert row["remaining"] == pytest.approx(1200.0)


def test_converting_twice_is_refused_rather_than_doubling_the_stock(manager):
    from custom_components.home_stock.domain.conversion import ConversionError

    _add(manager, 10, 2)
    manager.convert_product_unit(product_id=1, to_unit="g", reference_quantity=500)

    with pytest.raises(ConversionError):
        manager.convert_product_unit(product_id=1, to_unit="g", reference_quantity=500)


def test_a_failure_half_way_leaves_the_product_untouched(manager, monkeypatch):
    """One transaction: a crash after the first batch must not leave half the
    stock in grams and half in pieces."""
    _add(manager, 10, 2)
    from custom_components.home_stock.storage import repositories as repo

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
