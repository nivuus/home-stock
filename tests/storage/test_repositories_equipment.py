"""Les dépôts des quatre tables du lot 5 : piles, événements, équipements et
consommables.

Même forme que `test_repositories_journal.py` : une base migrée, une
connexion en écriture, et des lignes posées à la main pour contrôler
exactement ce qu'on mesure.
"""
import sqlite3

import pytest

from custom_components.home_stock.storage.database import Database
from custom_components.home_stock.storage.migrations import apply_migrations
from custom_components.home_stock.storage.repositories import (
    battery_by_anchor, get_battery, insert_battery, insert_battery_event,
    insert_equipment, insert_product, link_consumable, list_batteries,
    list_battery_events, list_consumables, set_battery_reading, spare_stock,
    warranty_rows,
)


@pytest.fixture
def conn(tmp_path):
    db = Database(str(tmp_path / "home_stock.db"))
    db.connect()
    with db.write() as connection:
        apply_migrations(connection)
    with db.write() as connection:
        connection.execute(
            "INSERT INTO location (name, kind) VALUES ('Placard', 'cupboard')")
    with db.write() as connection:
        yield connection
    db.close()


def _seed_batch(conn, product_id, *, quantity):
    """Un article générique et un lot ouvert : le chemin par lequel une
    rechange arrive au placard, exactement comme un produit alimentaire."""
    article_id = conn.execute(
        "INSERT INTO article (product_id, is_generic) VALUES (?, 1)",
        (product_id,)).lastrowid
    conn.execute(
        "INSERT INTO batch (article_id, location_id, remaining, initial,"
        " entered_at) VALUES (?, 1, ?, ?, '2026-08-01T10:00:00')",
        (article_id, quantity, quantity))
    return article_id


def test_a_battery_round_trips_with_its_defaults(conn):
    battery_id = insert_battery(conn, label="Velux (CH)", kind="primary")
    row = get_battery(conn, battery_id)
    assert row["cell_count"] == 1
    assert row["low_percent"] == 20.0 and row["keep_percent"] == 25.0
    assert row["tracked"] is None          # découvert, pas décidé
    assert row["active"] == 1


def test_list_batteries_carries_the_spare_label_and_its_stock(conn):
    product_id = insert_product(conn, name="CR2032", base_unit="piece", edible=0)
    _seed_batch(conn, product_id, quantity=3)
    insert_battery(conn, label="Velux (CH)", kind="primary", product_id=product_id)
    row = list_batteries(conn)[0]
    assert row["spare_label"] == "CR2032"
    assert spare_stock(conn, [product_id])[product_id] == 3.0


def test_spare_stock_is_zero_not_missing_for_a_product_without_a_batch(conn):
    """« aucune en stock » et « on ne sait pas » ne sont pas la même phrase, et
    c'est la première que la tâche doit dire."""
    product_id = insert_product(conn, name="9 V", base_unit="piece", edible=0)
    assert spare_stock(conn, [product_id]) == {product_id: 0.0}


def test_spare_stock_of_nothing_is_an_empty_mapping_not_a_full_scan(conn):
    assert spare_stock(conn, []) == {}


def test_set_battery_reading_writes_both_columns(conn):
    battery_id = insert_battery(conn, label="X", kind="primary")
    set_battery_reading(conn, battery_id, percent=18.0, at="2026-08-21T06:00:00")
    row = get_battery(conn, battery_id)
    assert row["last_percent"] == 18.0
    assert row["last_reading_at"] == "2026-08-21T06:00:00"


def test_battery_by_anchor_finds_nothing_for_an_unknown_uuid(conn):
    assert battery_by_anchor(conn, "9c03f558eabb5b7691b37e0a43558e9f") is None


def test_battery_by_anchor_finds_the_declared_one(conn):
    battery_id = insert_battery(conn, label="X", kind="primary",
                                entity_registry_id="uuid-1")
    assert battery_by_anchor(conn, "uuid-1")["id"] == battery_id


def test_battery_events_come_back_newest_first(conn):
    battery_id = insert_battery(conn, label="X", kind="primary")
    insert_battery_event(conn, battery_id=battery_id, occurred_at="2026-01-01T00:00:00",
                         kind="install")
    insert_battery_event(conn, battery_id=battery_id, occurred_at="2026-06-01T00:00:00",
                         kind="replacement")
    assert [e["kind"] for e in list_battery_events(conn, battery_id)] == \
        ["replacement", "install"]


def test_an_event_key_is_unique(conn):
    battery_id = insert_battery(conn, label="X", kind="primary")
    insert_battery_event(conn, battery_id=battery_id, occurred_at="2026-01-01T00:00:00",
                         kind="install", idempotency_key="k")
    with pytest.raises(sqlite3.IntegrityError):
        insert_battery_event(conn, battery_id=battery_id,
                             occurred_at="2026-01-02T00:00:00",
                             kind="install", idempotency_key="k")


def test_warranty_rows_computes_the_end_date_and_never_stores_it(conn):
    insert_equipment(conn, name="Purificateur", purchased_on="2024-03-15",
                     warranty_months=24)
    row = warranty_rows(conn)[0]
    assert row["warranty_ends_on"] == "2026-03-15"
    assert "warranty_ends_on" not in {c["name"] for c in
                                      conn.execute("PRAGMA table_info(equipment)")}


def test_warranty_rows_handles_the_end_of_month(conn):
    """31 janvier + 1 mois n'existe pas. La réponse retenue est le dernier jour
    du mois d'arrivée — jamais un débordement sur mars."""
    insert_equipment(conn, name="A", purchased_on="2024-01-31", warranty_months=1)
    assert warranty_rows(conn)[0]["warranty_ends_on"] == "2024-02-29"


def test_warranty_rows_skips_what_it_cannot_compute(conn):
    insert_equipment(conn, name="Poêle")                       # ni date ni durée
    insert_equipment(conn, name="B", purchased_on="2024-01-01")  # pas de durée
    assert warranty_rows(conn) == []


def test_warranty_rows_are_sorted_by_deadline(conn):
    insert_equipment(conn, name="Tard", purchased_on="2025-01-01", warranty_months=24)
    insert_equipment(conn, name="Tôt", purchased_on="2024-01-01", warranty_months=12)
    assert [r["name"] for r in warranty_rows(conn)] == ["Tôt", "Tard"]


def test_a_consumable_link_carries_its_thresholds(conn):
    equipment_id = insert_equipment(conn, name="Purificateur")
    product_id = insert_product(conn, name="Filtre HEPA MB4", base_unit="piece", edible=0)
    link_consumable(conn, equipment_id=equipment_id, product_id=product_id,
                    role="filter", label="filtre HEPA", low_value=15.0,
                    keep_value=20.0, unit="percent")
    row = list_consumables(conn, equipment_id)[0]
    assert row["role"] == "filter" and row["unit"] == "percent"
    assert row["product_name"] == "Filtre HEPA MB4"
