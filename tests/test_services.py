import pytest
import voluptuous as vol
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.home_stock.const import DOMAIN
from custom_components.home_stock.storage import repositories as repo


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
