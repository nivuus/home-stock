import sqlite3

import pytest

from custom_components.home_stock.import_grocy import import_catalog
from custom_components.home_stock.storage import repositories as repo
from custom_components.home_stock.storage.database import Database
from custom_components.home_stock.storage.migrations import apply_migrations


@pytest.fixture
def grocy(tmp_path):
    """A miniature Grocy database with the columns the import reads."""
    path = tmp_path / "grocy.db"
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE quantity_units (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE locations (id INTEGER PRIMARY KEY, name TEXT, is_freezer INTEGER);
        CREATE TABLE product_groups (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE products (
            id INTEGER PRIMARY KEY, name TEXT, active INTEGER, product_group_id INTEGER,
            location_id INTEGER, qu_id_stock INTEGER, min_stock_amount REAL,
            calories REAL, default_best_before_days_after_open INTEGER,
            picture_file_name TEXT);
        CREATE TABLE product_barcodes (
            id INTEGER PRIMARY KEY, product_id INTEGER, barcode TEXT, qu_id INTEGER,
            amount REAL, last_price REAL);
        CREATE TABLE userfields (id INTEGER PRIMARY KEY, entity TEXT, name TEXT);
        CREATE TABLE userfield_values (
            id INTEGER PRIMARY KEY, field_id INTEGER, object_id INTEGER, value TEXT);
    """)
    conn.executemany("INSERT INTO quantity_units VALUES (?, ?)",
                     [(4, "g"), (5, "kg"), (6, "cl"), (2, "Pièce"), (14, "cs")])
    conn.executemany("INSERT INTO locations VALUES (?, ?, ?)",
                     [(2, "Frigo", 0), (3, "Congélateur", 1), (4, "Placard", 0)])
    conn.executemany("INSERT INTO product_groups VALUES (?, ?)",
                     [(1, "Pâtes"), (2, "Produit laitier")])
    conn.executemany(
        "INSERT INTO products VALUES (?,?,?,?,?,?,?,?,?,?)",
        [
            # grams: taken as is
            (1, "Pâtes", 1, 1, 4, 4, 200, 3.5, 0, None),
            # kilograms: quantities x1000, calories /1000
            (2, "Farine", 1, 1, 4, 5, 1, 3640.0, 0, None),
            # centilitres: quantities x10, calories /10
            (3, "Lait", 1, 2, 2, 6, 100, 4.6, 3, None),
            # a container unit stays counted
            (4, "Œufs", 1, 2, 2, 2, 6, 78.0, 0, None),
            # inactive: a disabled duplicate, not imported
            (5, "Pâtes (doublon)", 0, 1, 4, 4, None, None, 0, None),
        ],
    )
    conn.executemany("INSERT INTO product_barcodes VALUES (?,?,?,?,?,?)",
                     [(1, 1, "3038350201553", 4, 500, 2.0),
                      (2, 3, "3033490004743", 6, 100, 1.2)])
    conn.executemany("INSERT INTO userfields VALUES (?,?,?)",
                     [(1, "products", "nutriscore"), (4, "products", "marque")])
    conn.executemany("INSERT INTO userfield_values VALUES (?,?,?,?)",
                     [(1, 1, 1, "A"), (2, 4, 1, "Panzani")])
    conn.commit()
    conn.close()
    return str(path)


@pytest.fixture
def db(tmp_path):
    database = Database(str(tmp_path / "home_stock.db"))
    database.connect()
    with database.write() as conn:
        apply_migrations(conn)
    yield database
    database.close()


def test_dry_run_writes_nothing(db, grocy):
    report = import_catalog(db, grocy, apply=False)
    assert report.products == 4
    assert repo.list_products(db.read()) == []


def test_import_creates_products_locations_and_categories(db, grocy):
    report = import_catalog(db, grocy, apply=True)
    assert report.products == 4
    assert report.skipped == 1          # the disabled duplicate
    assert report.locations == 3
    assert report.categories == 2
    names = [p["name"] for p in repo.list_products(db.read())]
    assert names == ["Farine", "Lait", "Pâtes", "Œufs"]


def test_units_are_converted_with_their_factor(db, grocy):
    import_catalog(db, grocy, apply=True)
    products = {p["name"]: p for p in repo.list_products(db.read())}
    assert products["Pâtes"]["base_unit"] == "g"
    assert products["Pâtes"]["min_quantity"] == 200
    assert products["Farine"]["base_unit"] == "g"
    assert products["Farine"]["min_quantity"] == 1000      # 1 kg
    assert products["Lait"]["base_unit"] == "ml"
    assert products["Lait"]["min_quantity"] == 1000        # 100 cl
    assert products["Œufs"]["base_unit"] == "piece"
    assert products["Œufs"]["min_quantity"] == 6


def test_calories_follow_the_same_factor(db, grocy):
    import_catalog(db, grocy, apply=True)
    conn = db.read()
    rows = {
        row["name"]: row["kcal_per_base_unit"]
        for row in conn.execute(
            "SELECT p.name, a.kcal_per_base_unit FROM article a"
            " JOIN product p ON p.id = a.product_id")
    }
    assert rows["Pâtes"] == pytest.approx(3.5)     # per gram
    assert rows["Farine"] == pytest.approx(3.64)   # 3640 per kg
    assert rows["Lait"] == pytest.approx(0.46)     # 4.6 per cl
    assert rows["Œufs"] == pytest.approx(78.0)     # per egg


def test_every_product_gets_a_generic_article(db, grocy):
    import_catalog(db, grocy, apply=True)
    count = db.read().execute(
        "SELECT COUNT(*) AS n FROM article WHERE is_generic = 1").fetchone()
    assert count["n"] == 4


def test_custom_fields_land_on_the_article(db, grocy):
    import_catalog(db, grocy, apply=True)
    row = db.read().execute(
        "SELECT a.nutriscore, a.brand FROM article a JOIN product p ON p.id = a.product_id"
        " WHERE p.name = 'Pâtes'").fetchone()
    assert row["nutriscore"] == "A"
    assert row["brand"] == "Panzani"


def test_barcodes_and_prices_are_imported(db, grocy):
    report = import_catalog(db, grocy, apply=True)
    assert report.barcodes == 2
    article = repo.find_article_by_barcode(db.read(), "3038350201553")
    assert article is not None
    # 2 € for 500 g is 0.004 €/g.
    assert repo.latest_price(db.read(), article["id"]) == pytest.approx(0.004)


def test_days_after_opening_are_kept(db, grocy):
    import_catalog(db, grocy, apply=True)
    row = db.read().execute(
        "SELECT days_after_opening FROM product WHERE name = 'Lait'").fetchone()
    assert row["days_after_opening"] == 3


def test_running_twice_changes_nothing(db, grocy):
    import_catalog(db, grocy, apply=True)
    second = import_catalog(db, grocy, apply=True)
    assert second.products == 0
    assert len(repo.list_products(db.read())) == 4


def test_a_dosage_unit_as_stock_unit_is_an_anomaly(db, grocy):
    conn = sqlite3.connect(grocy)
    conn.execute("UPDATE products SET qu_id_stock = 14 WHERE id = 1")   # 'cs'
    conn.commit()
    conn.close()
    report = import_catalog(db, grocy, apply=False)
    assert report.ok is False
    assert any("cs" in anomaly for anomaly in report.anomalies)


def test_an_impossible_calorie_value_is_an_anomaly(db, grocy):
    conn = sqlite3.connect(grocy)
    # 50 kcal per gram: no food does that (fat tops out around 9).
    conn.execute("UPDATE products SET calories = 50 WHERE id = 1")
    conn.commit()
    conn.close()
    report = import_catalog(db, grocy, apply=False)
    assert report.ok is False
    assert any("Pâtes" in anomaly for anomaly in report.anomalies)


def test_a_clean_import_has_no_anomalies(db, grocy):
    report = import_catalog(db, grocy, apply=True)
    assert report.ok is True


def test_an_unknown_unit_is_an_anomaly(db, grocy):
    conn = sqlite3.connect(grocy)
    conn.execute("INSERT INTO quantity_units VALUES (99, 'Rouleau')")
    conn.execute("UPDATE products SET qu_id_stock = 99 WHERE id = 1")
    conn.commit()
    conn.close()
    report = import_catalog(db, grocy, apply=False)
    assert report.ok is False
    assert any(
        "Rouleau" in anomaly and "inconnue" in anomaly for anomaly in report.anomalies
    )


def test_a_duplicate_product_name_is_an_anomaly_not_a_crash(db, grocy):
    # The April 2026 scenario: a product already exists under that name — here
    # because it was hand-created in home_stock, not because it was imported
    # before (it carries no external_ref).
    with db.write() as conn:
        repo.insert_product(conn, name="Farine", base_unit="g")

    report = import_catalog(db, grocy, apply=True)   # must not raise

    assert report.ok is False
    assert any("Farine" in anomaly for anomaly in report.anomalies)
    # the rest of the import still went through
    assert report.products == 3   # Lait, Pâtes, Œufs — Farine collided
    names = [p["name"] for p in repo.list_products(db.read())]
    assert names.count("Farine") == 1


def test_a_duplicate_barcode_within_the_same_run_is_an_anomaly(db, grocy):
    conn = sqlite3.connect(grocy)
    # Lait grabs Pâtes' barcode by mistake.
    conn.execute(
        "INSERT INTO product_barcodes VALUES (3, 3, '3038350201553', 6, 100, 1.2)")
    conn.commit()
    conn.close()

    report = import_catalog(db, grocy, apply=True)

    assert report.ok is False
    assert any("3038350201553" in anomaly for anomaly in report.anomalies)
    assert report.barcodes == 2   # Pâtes' own + Lait's own, not the collision
    # the first claimant keeps it
    article = repo.find_article_by_barcode(db.read(), "3038350201553")
    assert article is not None
    product = repo.get_product(db.read(), article["product_id"])
    assert product["name"] == "Pâtes"


def test_a_non_convertible_price_is_an_anomaly(db, grocy):
    conn = sqlite3.connect(grocy)
    # Œufs is stocked by the piece, but this barcode is priced by the gram:
    # converting literally would record a price per egg as a price per gram —
    # the same class of bug as the real "Houmous bio Pascalou 160g" case,
    # where the pack (Pièce) and the stock unit (g) don't resolve to the same
    # base unit.
    conn.execute(
        "INSERT INTO product_barcodes VALUES (3, 4, '2222222222222', 4, 1, 3.0)")
    conn.commit()
    conn.close()

    report = import_catalog(db, grocy, apply=True)

    assert report.ok is False
    assert any("2222222222222" in anomaly for anomaly in report.anomalies)
    # the barcode itself still links — only the price is refused
    article = repo.find_article_by_barcode(db.read(), "2222222222222")
    assert article is not None
    assert repo.latest_price(db.read(), article["id"]) is None


def test_a_product_without_a_category_is_an_anomaly_but_still_imports(db, grocy):
    # category_id is nullable and the product still lands: this is a visibility
    # check, not a data integrity gate (design §10's control gate lists it
    # among the counts that must reach zero).
    conn = sqlite3.connect(grocy)
    conn.execute("UPDATE products SET product_group_id = NULL WHERE id = 1")  # Pâtes
    conn.commit()
    conn.close()

    report = import_catalog(db, grocy, apply=True)

    assert report.ok is False
    assert any("Pâtes" in a and "catégorie" in a for a in report.anomalies)
    product = repo.find_product_by_name(db.read(), "Pâtes")
    assert product is not None
    assert product["category_id"] is None


def test_a_barcode_added_after_the_first_import_is_picked_up_by_a_replay(db, grocy):
    import_catalog(db, grocy, apply=True)

    conn = sqlite3.connect(grocy)
    # Farine (kg, base unit g) gets a barcode in Grocy after the fact.
    conn.execute(
        "INSERT INTO product_barcodes VALUES (3, 2, '4444444444444', 4, 1000, 2.5)")
    conn.commit()
    conn.close()

    second = import_catalog(db, grocy, apply=True)

    assert second.ok is True
    assert second.products == 0        # no product re-created
    assert second.barcodes == 1        # only the new one
    assert second.prices == 1
    assert len(repo.list_products(db.read())) == 4
    article = repo.find_article_by_barcode(db.read(), "4444444444444")
    assert article is not None
    product = repo.get_product(db.read(), article["product_id"])
    assert product["name"] == "Farine"
    assert repo.latest_price(db.read(), article["id"]) == pytest.approx(0.0025)
