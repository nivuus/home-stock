import pytest

from custom_components.home_stock.aisles import AISLES
from custom_components.home_stock.storage import repositories as repo


@pytest.fixture
async def entry(setup_entry):
    return await setup_entry()


@pytest.fixture
async def seeded(entry, hass):
    """One product, one 500 g batch. Returns the entry with fresh coordinator data."""
    manager = entry.runtime_data.manager

    def _seed() -> None:
        with manager.db.write() as conn:
            location_id = repo.insert_location(conn, name="Placard", kind="pantry")
            product_id = repo.insert_product(conn, name="Pâtes", base_unit="g")
            article_id = repo.insert_article(conn, product_id=product_id)
        manager.add_stock(article_id=article_id, quantity=500,
                          location_id=location_id, occurred_at="2026-08-18T10:00:00")

    await hass.async_add_executor_job(_seed)
    # Mirror what both production write paths (the services, the todo entity)
    # do: refresh the coordinator after writing. Without this, this fixture's
    # direct manager write — bypassing both of those paths — would leave
    # coordinator.data stale, which is not representative of what a panel
    # sees today.
    await entry.runtime_data.coordinator.async_request_refresh()
    return entry


@pytest.fixture
async def client(seeded, hass, hass_ws_client):
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


async def test_aisles_list_is_seeded_in_walking_order(client):
    # The aisle table exists from lot 0, empty; migration m002 (lot 1, task 1)
    # seeds it from the referential in aisles.py.
    await client.send_json_auto_id({"type": "home_stock/aisles/list"})
    message = await client.receive_json()
    assert [a["name"] for a in message["result"]["aisles"]] == list(AISLES)


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


async def test_movements_list_returns_them_in_order_and_respects_since(
        hass, setup_entry, hass_ws_client):
    entry = await setup_entry()
    manager = entry.runtime_data.manager

    def _seed() -> None:
        with manager.db.write() as conn:
            location_id = repo.insert_location(conn, name="Placard", kind="pantry")
            product_id = repo.insert_product(conn, name="Pâtes", base_unit="g")
            article_id = repo.insert_article(conn, product_id=product_id)
        manager.add_stock(article_id=article_id, quantity=500, location_id=location_id,
                          occurred_at="2026-08-18T09:00:00")
        manager.consume(product_id=product_id, quantity=100,
                        occurred_at="2026-08-18T10:00:00")

    await hass.async_add_executor_job(_seed)
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "home_stock/movements/list"})
    message = await client.receive_json()
    movements = message["result"]["movements"]
    assert [m["reason"] for m in movements] == ["purchase", "consumption"]
    assert movements[0]["occurred_at"] < movements[1]["occurred_at"]

    await client.send_json_auto_id({
        "type": "home_stock/movements/list", "since": "2026-08-18T10:00:00",
    })
    filtered = await client.receive_json()
    assert [m["reason"] for m in filtered["result"]["movements"]] == ["consumption"]


async def test_subscribe_pushes_the_summary(hass, client):
    await client.send_json_auto_id({"type": "home_stock/subscribe"})
    subscription = await client.receive_json()
    assert subscription["success"] is True
    # The first push carries the current summary, without waiting for a change.
    event = await client.receive_json()
    assert event["event"]["batch_count"] == 1


async def test_subscribe_pushes_even_when_always_update_is_false(seeded, hass, hass_ws_client):
    # The first push must not depend on always_update triggering
    # async_update_listeners(): it is sent directly to this connection,
    # independently of that coordinator setting.
    seeded.runtime_data.coordinator.always_update = False
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "home_stock/subscribe"})
    subscription = await client.receive_json()
    assert subscription["success"] is True
    event = await client.receive_json()
    assert event["event"]["batch_count"] == 1


async def test_a_command_reports_not_loaded_once_the_entry_is_unloaded(hass, seeded, client):
    await hass.config_entries.async_unload(seeded.entry_id)
    await hass.async_block_till_done()

    await client.send_json_auto_id({"type": "home_stock/products/list"})
    message = await client.receive_json()
    assert message["success"] is False
    assert message["error"]["code"] == "not_loaded"
