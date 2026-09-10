"""Lot 2: product_id stable, barcode optional, create_product validation.

Covers R5 (product_id distinct from a barcode), R7 (persistence across a
restart) and R10 (a barcode-less product is a normal product everywhere it
is read).
"""
import pytest

from custom_components.home_stock.aisles import AISLES
from custom_components.home_stock.const import BASE_UNITS
from custom_components.home_stock.storage import products as store
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


def _an_aisle(conn) -> str:
    return repo.list_aisles(conn)[0]["name"]


def test_create_product_defaults_no_barcode(conn):
    rayon = _an_aisle(conn)
    product = store.create_product(conn, name="Mangue", rayon=rayon)
    assert product["product_id"].startswith(store.PRODUCT_ID_PREFIX)
    assert product["barcode"] is None
    assert product["unit"] == store.DEFAULT_BASE_UNIT
    assert product["name"] == "Mangue"
    assert product["rayon"] == rayon


def test_create_product_strips_name(conn):
    rayon = _an_aisle(conn)
    product = store.create_product(conn, name="  Kimchi ", rayon=rayon)
    assert product["name"] == "Kimchi"


def test_create_product_rejects_blank_name(conn):
    rayon = _an_aisle(conn)
    with pytest.raises(store.EmptyName):
        store.create_product(conn, name="   ", rayon=rayon)
    assert store.list_products(conn) == []


def test_create_product_rejects_duplicate_name(conn):
    rayon = _an_aisle(conn)
    store.create_product(conn, name="Mangue", rayon=rayon)
    with pytest.raises(store.DuplicateName) as excinfo:
        store.create_product(conn, name="Mangue", rayon=rayon)
    assert excinfo.value.name == "Mangue"
    assert len(store.list_products(conn)) == 1


def test_create_product_rejects_duplicate_barcode(conn):
    rayon = _an_aisle(conn)
    store.create_product(conn, name="A", rayon=rayon, barcode="123")
    with pytest.raises(store.DuplicateBarcode) as excinfo:
        store.create_product(conn, name="B", rayon=rayon, barcode="123")
    assert excinfo.value.barcode == "123"
    assert len(store.list_products(conn)) == 1


def test_create_product_empty_barcode_is_none(conn):
    rayon = _an_aisle(conn)
    product = store.create_product(conn, name="A", rayon=rayon, barcode="")
    assert product["barcode"] is None


def test_create_product_rejects_unknown_rayon(conn):
    with pytest.raises(store.InvalidRayon) as excinfo:
        store.create_product(conn, name="A", rayon="nope")
    assert excinfo.value.value == "nope"
    assert sorted(excinfo.value.allowed) == sorted(AISLES)


def test_create_product_rejects_unknown_unit(conn):
    rayon = _an_aisle(conn)
    with pytest.raises(store.InvalidUnit) as excinfo:
        store.create_product(conn, name="A", rayon=rayon, unit="litre")
    assert excinfo.value.value == "litre"
    assert list(excinfo.value.allowed) == list(BASE_UNITS)


def test_get_product_survives_a_restart(tmp_path):
    """Create through one Database instance, close it (as Home Assistant
    would on shutdown), then re-open a fresh instance on the same file: the
    record must still be there, under the same product_id (R7)."""
    db_path = str(tmp_path / "restart.db")

    db = Database(db_path)
    db.connect()
    with db.write() as conn:
        apply_migrations(conn)
    with db.write() as conn:
        rayon = _an_aisle(conn)
        created = store.create_product(conn, name="Piment", rayon=rayon)
    db.close()

    reopened = Database(db_path)
    reopened.connect()
    with reopened.write() as conn:
        reloaded = store.get_product(conn, created["product_id"])
    reopened.close()

    assert reloaded["product_id"] == created["product_id"]
    assert reloaded["name"] == "Piment"
    assert reloaded["rayon"] == created["rayon"]


def test_get_product_returns_none_for_an_unparseable_id(conn):
    assert store.get_product(conn, "not-a-product-id") is None
    assert store.get_product(conn, "hs_") is None
    assert store.get_product(conn, "hs_99999") is None


def test_find_by_barcode_locates_the_product(conn):
    rayon = _an_aisle(conn)
    created = store.create_product(conn, name="Yaourt", rayon=rayon, barcode="42")
    found = store.find_by_barcode(conn, "42")
    assert found["product_id"] == created["product_id"]
    assert store.find_by_barcode(conn, "0000") is None


def test_list_products_includes_barcode_less_products(conn):
    rayon = _an_aisle(conn)
    store.create_product(conn, name="Sans code", rayon=rayon)
    listed = store.list_products(conn)
    assert len(listed) == 1
    assert listed[0]["barcode"] is None
    assert listed[0]["product_id"].startswith(store.PRODUCT_ID_PREFIX)


def test_legacy_product_without_articles_is_still_readable(conn):
    """A product inserted the old way (before this lot, no article at all)
    still gets a product_id and a barcode of None: no migration step is
    needed because `product.id` was already independent of any barcode."""
    aisle_id = repo.list_aisles(conn)[0]["id"]
    legacy_id = repo.insert_product(conn, name="Legacy", base_unit="g", aisle_id=aisle_id)

    dressed = store.get_product(conn, store.format_product_id(legacy_id))

    assert dressed["barcode"] is None
    assert dressed["product_id"] == f"hs_{legacy_id}"
