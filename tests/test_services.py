import sqlite3
from unittest.mock import AsyncMock

import pytest
import voluptuous as vol
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.home_stock.const import DOMAIN
from custom_components.home_stock.storage import repositories as repo


def _write_empty_grocy(path: str) -> None:
    """A structurally valid but empty grocy.db — enough for the import to run
    end to end without needing real catalogue data, to exercise the service
    itself (schema, response shape, refresh gating) rather than import_catalog's
    own logic, which tests/test_import_grocy.py already covers.
    """
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
    conn.commit()
    conn.close()


@pytest.fixture
async def seeded(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    manager = entry.runtime_data.manager

    def _seed() -> dict[str, int]:
        with manager.db.write() as conn:
            location_id = repo.insert_location(conn, name="Placard", kind="pantry")
            product_id = repo.insert_product(conn, name="Pâtes", base_unit="g")
            article_id = repo.insert_article(conn, product_id=product_id,
                                             kcal_per_base_unit=3.5)
            repo.link_barcode(conn, "3038350201553", article_id)
        return {"location_id": location_id, "product_id": product_id,
                "article_id": article_id}

    ids = await hass.async_add_executor_job(_seed)
    return entry, ids


async def test_add_stock_accepts_a_barcode(hass, seeded):
    entry, ids = seeded
    await hass.services.async_call(DOMAIN, "add_stock", {
        "barcode": "3038350201553", "quantity": 500,
        "location_id": ids["location_id"], "price_per_base_unit": 0.004,
    }, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.home_stock_batches").state == "1"


async def test_add_stock_rejects_an_unknown_barcode(hass, seeded):
    entry, ids = seeded
    # Creating an article from an EAN needs Open Food Facts: that is lot 1.
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(DOMAIN, "add_stock", {
            "barcode": "0000000000000", "quantity": 1,
            "location_id": ids["location_id"],
        }, blocking=True)


async def test_consume_reports_insufficient_stock_as_a_home_assistant_error(hass, seeded):
    entry, ids = seeded
    await hass.services.async_call(DOMAIN, "add_stock", {
        "article_id": ids["article_id"], "quantity": 100,
        "location_id": ids["location_id"],
    }, blocking=True)
    with pytest.raises(HomeAssistantError, match="Stock insuffisant"):
        await hass.services.async_call(DOMAIN, "consume", {
            "product_id": ids["product_id"], "quantity": 500,
        }, blocking=True)


async def test_consume_rejects_a_reason_not_meant_for_consumption(hass, seeded):
    entry, ids = seeded
    # "purchase"/"inventory"/"transfer" are written by other services; letting
    # consume() carry them would silently escape COUNTED_REASONS and
    # under-count the kcal/cost totals for stock that really left the pantry.
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(DOMAIN, "consume", {
            "product_id": ids["product_id"], "quantity": 1, "reason": "purchase",
        }, blocking=True)


async def test_query_stock_returns_a_response(hass, seeded):
    entry, ids = seeded
    await hass.services.async_call(DOMAIN, "add_stock", {
        "article_id": ids["article_id"], "quantity": 500,
        "location_id": ids["location_id"],
    }, blocking=True)
    response = await hass.services.async_call(
        DOMAIN, "query_stock", {"name": "pât"}, blocking=True, return_response=True
    )
    assert response["products"][0]["display"] == "500 g"


async def test_export_journal_returns_the_movements(hass, seeded):
    entry, ids = seeded
    await hass.services.async_call(DOMAIN, "add_stock", {
        "article_id": ids["article_id"], "quantity": 500,
        "location_id": ids["location_id"],
    }, blocking=True)
    response = await hass.services.async_call(
        DOMAIN, "export_journal", {}, blocking=True, return_response=True
    )
    assert [m["reason"] for m in response["movements"]] == ["purchase"]


async def test_the_state_refreshes_right_after_a_write(hass, seeded):
    entry, ids = seeded
    await hass.services.async_call(DOMAIN, "add_stock", {
        "article_id": ids["article_id"], "quantity": 500,
        "location_id": ids["location_id"],
    }, blocking=True)
    await hass.async_block_till_done()
    # No waiting for the 15-minute poll: a write refreshes immediately.
    assert hass.states.get("sensor.home_stock_batches").state == "1"


async def test_import_grocy_catalog_is_response_only(hass, seeded):
    entry, ids = seeded
    _write_empty_grocy(hass.config.path("grocy_import.db"))
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "import_grocy_catalog", {"path": "grocy_import.db"}, blocking=True,
        )


async def test_import_grocy_catalog_schema_defaults(hass, seeded):
    entry, ids = seeded
    # The default path ("grocy_import.db") is relative to the config directory.
    _write_empty_grocy(hass.config.path("grocy_import.db"))
    response = await hass.services.async_call(
        DOMAIN, "import_grocy_catalog", {}, blocking=True, return_response=True,
    )
    assert response == {
        "products": 0, "articles": 0, "barcodes": 0, "prices": 0,
        "categories": 0, "locations": 0, "skipped": 0, "anomalies": [], "ok": True,
    }


async def test_import_grocy_catalog_dry_run_does_not_refresh_the_coordinator(hass, seeded):
    entry, ids = seeded
    _write_empty_grocy(hass.config.path("grocy_import.db"))
    entry.runtime_data.coordinator.async_request_refresh = AsyncMock()
    await hass.services.async_call(
        DOMAIN, "import_grocy_catalog", {"path": "grocy_import.db"},
        blocking=True, return_response=True,
    )
    entry.runtime_data.coordinator.async_request_refresh.assert_not_called()


async def test_import_grocy_catalog_apply_refreshes_the_coordinator(hass, seeded):
    entry, ids = seeded
    _write_empty_grocy(hass.config.path("grocy_import.db"))
    entry.runtime_data.coordinator.async_request_refresh = AsyncMock()
    await hass.services.async_call(
        DOMAIN, "import_grocy_catalog", {"path": "grocy_import.db", "apply": True},
        blocking=True, return_response=True,
    )
    entry.runtime_data.coordinator.async_request_refresh.assert_called_once()
