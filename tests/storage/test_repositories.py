import pytest

from custom_components.home_stock.storage import repositories as repo
from custom_components.home_stock.storage.database import Database
from custom_components.home_stock.storage.migrations import apply_migrations


@pytest.fixture
def conn(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.connect()
    with db.write() as c:
        apply_migrations(c)
    with db.write() as c:
        yield c
    db.close()


def test_product_round_trip(conn):
    product_id = repo.insert_product(conn, name="Moutarde", base_unit="g")
    product = repo.get_product(conn, product_id)
    assert product["name"] == "Moutarde"
    assert product["base_unit"] == "g"
    assert product["active"] == 1


def test_find_product_by_name(conn):
    repo.insert_product(conn, name="Moutarde", base_unit="g")
    assert repo.find_product_by_name(conn, "Moutarde")["name"] == "Moutarde"
    assert repo.find_product_by_name(conn, "Ketchup") is None


def test_barcode_resolves_to_an_article(conn):
    product_id = repo.insert_product(conn, name="Moutarde", base_unit="g")
    small = repo.insert_article(conn, product_id=product_id, label="Savora 265 g",
                                net_quantity=265, kcal_per_base_unit=1.2)
    large = repo.insert_article(conn, product_id=product_id, label="Savora 385 g",
                                net_quantity=385, kcal_per_base_unit=1.2)
    repo.link_barcode(conn, "3011360002105", small)
    repo.link_barcode(conn, "3011360002204", large)
    found = repo.find_article_by_barcode(conn, "3011360002204")
    assert found["id"] == large
    assert found["net_quantity"] == 385
    assert repo.find_article_by_barcode(conn, "0000000000000") is None


def test_latest_price_is_the_most_recent(conn):
    product_id = repo.insert_product(conn, name="Moutarde", base_unit="g")
    article_id = repo.insert_article(conn, product_id=product_id)
    repo.insert_price(conn, article_id=article_id, observed_on="2026-01-01",
                      price_per_base_unit=0.004, source="manual")
    repo.insert_price(conn, article_id=article_id, observed_on="2026-08-01",
                      price_per_base_unit=0.005, source="receipt")
    assert repo.latest_price(conn, article_id) == 0.005


def test_latest_price_is_none_without_history(conn):
    product_id = repo.insert_product(conn, name="Sel", base_unit="g")
    article_id = repo.insert_article(conn, product_id=product_id)
    assert repo.latest_price(conn, article_id) is None


def test_list_batches_excludes_closed_ones(conn):
    location_id = repo.insert_location(conn, name="Placard", kind="pantry")
    product_id = repo.insert_product(conn, name="Pâtes", base_unit="g")
    article_id = repo.insert_article(conn, product_id=product_id)
    open_batch = repo.insert_batch(conn, article_id=article_id, location_id=location_id,
                                   quantity=500, entered_at="2026-08-01T10:00:00")
    closed = repo.insert_batch(conn, article_id=article_id, location_id=location_id,
                               quantity=500, entered_at="2026-07-01T10:00:00")
    repo.set_batch_remaining(conn, closed, 0, closed_at="2026-08-10T10:00:00")
    batches = repo.list_batches_for_product(conn, product_id)
    assert [b["id"] for b in batches] == [open_batch]


def test_movement_idempotency(conn):
    product_id = repo.insert_product(conn, name="Pâtes", base_unit="g")
    article_id = repo.insert_article(conn, product_id=product_id)
    repo.insert_movement(conn, occurred_at="2026-08-18T10:00:00", product_id=product_id,
                         article_id=article_id, quantity=-200, reason="consumption",
                         base_unit="g", kcal=700.0, cost=0.6, idempotency_key="k1")
    assert repo.movement_exists(conn, "k1") is True
    assert repo.movement_exists(conn, "k2") is False


def test_stock_rows_join_names(conn):
    location_id = repo.insert_location(conn, name="Frigo", kind="fridge")
    product_id = repo.insert_product(conn, name="Lait", base_unit="ml")
    article_id = repo.insert_article(conn, product_id=product_id, label="Lactel 1 l")
    repo.insert_batch(conn, article_id=article_id, location_id=location_id,
                      quantity=1000, entered_at="2026-08-01T10:00:00",
                      best_before="2026-08-25", price_per_base_unit=0.0012)
    row = repo.stock_rows(conn)[0]
    assert row["product_name"] == "Lait"
    assert row["location_name"] == "Frigo"
    assert row["base_unit"] == "ml"
    assert row["remaining"] == 1000


def test_stock_rows_kcal_falls_back_to_the_product_reference(conn):
    """home_stock/batches/list (the future panel) is served straight from this
    query: without the same COALESCE as list_batches_for_product (spec 7.4),
    it would show no calories for exactly the generic/produce articles the
    fallback exists for."""
    location_id = repo.insert_location(conn, name="Frigo", kind="fridge")
    product_id = repo.insert_product(conn, name="Pomme", base_unit="g",
                                     reference_kcal=0.52)
    article_id = repo.insert_article(conn, product_id=product_id, label="Générique")
    repo.insert_batch(conn, article_id=article_id, location_id=location_id,
                      quantity=200, entered_at="2026-08-01T10:00:00")
    row = repo.stock_rows(conn)[0]
    assert row["kcal_per_base_unit"] == pytest.approx(0.52)


def test_resolve_kcal_rate_falls_back_to_the_product_reference(conn):
    product_id = repo.insert_product(conn, name="Pomme", base_unit="g",
                                     reference_kcal=0.52)
    article_id = repo.insert_article(conn, product_id=product_id, label="Générique")
    article = repo.get_article(conn, article_id)
    assert repo.resolve_kcal_rate(conn, article) == pytest.approx(0.52)

    with_own_rate = repo.insert_article(conn, product_id=product_id,
                                        kcal_per_base_unit=1.1)
    assert repo.resolve_kcal_rate(conn, repo.get_article(conn, with_own_rate)) == 1.1
