import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.home_stock.const import DOMAIN
from custom_components.home_stock.storage import repositories as repo


@pytest.fixture
async def client(hass, hass_ws_client):
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    manager = entry.runtime_data.manager

    def _seed() -> None:
        with manager.db.write() as conn:
            location_id = repo.insert_location(conn, name="Placard", kind="pantry")
            product_id = repo.insert_product(conn, name="Pâtes", base_unit="g")
            article_id = repo.insert_article(conn, product_id=product_id)
        manager.add_stock(article_id=article_id, quantity=500,
                          location_id=location_id, occurred_at="2026-08-18T10:00:00")

    await hass.async_add_executor_job(_seed)
    return await hass_ws_client(hass)


async def test_products_list(client):
    await client.send_json_auto_id({"type": "home_stock/products/list"})
    message = await client.receive_json()
    assert message["success"] is True
    assert message["result"]["products"][0]["name"] == "Pâtes"


async def test_batches_list_returns_one_row_per_batch(client):
    await client.send_json_auto_id({"type": "home_stock/batches/list"})
    message = await client.receive_json()
    assert message["result"]["batches"][0]["remaining"] == 500
    assert message["result"]["batches"][0]["location_name"] == "Placard"


async def test_locations_list(client):
    await client.send_json_auto_id({"type": "home_stock/locations/list"})
    message = await client.receive_json()
    assert [l["name"] for l in message["result"]["locations"]] == ["Placard"]


async def test_aisles_list_is_empty_until_lot_1(client):
    # The aisle table exists from lot 0; Grocy has no aisles, and Open Food Facts
    # categories seed them at lot 1.
    await client.send_json_auto_id({"type": "home_stock/aisles/list"})
    message = await client.receive_json()
    assert message["result"]["aisles"] == []


async def test_product_get_returns_one_product(hass, client):
    await client.send_json_auto_id({"type": "home_stock/products/list"})
    listed = await client.receive_json()
    product_id = listed["result"]["products"][0]["id"]

    await client.send_json_auto_id(
        {"type": "home_stock/product/get", "product_id": product_id}
    )
    message = await client.receive_json()
    assert message["result"]["product"]["name"] == "Pâtes"


async def test_product_get_reports_an_unknown_id(client):
    await client.send_json_auto_id({"type": "home_stock/product/get", "product_id": 999})
    message = await client.receive_json()
    assert message["success"] is False
    assert message["error"]["code"] == "not_found"


async def test_subscribe_pushes_the_summary(hass, client):
    await client.send_json_auto_id({"type": "home_stock/subscribe"})
    subscription = await client.receive_json()
    assert subscription["success"] is True
    # The first push carries the current summary, without waiting for a change.
    event = await client.receive_json()
    assert event["event"]["batch_count"] == 1
