from datetime import date, timedelta

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.home_stock.const import DOMAIN
from custom_components.home_stock.storage import repositories as repo


@pytest.fixture
async def loaded(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_entities_are_created_empty(hass, loaded):
    assert hass.states.get("sensor.home_stock_stock_value").state == "0.0"
    assert hass.states.get("sensor.home_stock_batches").state == "0"
    assert hass.states.get("binary_sensor.home_stock_expirations").state == "off"
    assert hass.states.get("binary_sensor.home_stock_shortages").state == "off"


async def test_entities_reflect_the_stock(hass, loaded):
    manager = loaded.runtime_data.manager

    def _seed() -> None:
        with manager.db.write() as conn:
            location_id = repo.insert_location(conn, name="Frigo", kind="fridge")
            product_id = repo.insert_product(conn, name="Lait", base_unit="ml",
                                             min_quantity=2000)
            article_id = repo.insert_article(conn, product_id=product_id,
                                             kcal_per_base_unit=0.46)
        manager.add_stock(article_id=article_id, quantity=1000,
                          location_id=location_id, best_before="2026-08-19",
                          price_per_base_unit=0.0012,
                          occurred_at="2026-08-18T10:00:00")

    await hass.async_add_executor_job(_seed)
    await loaded.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get("sensor.home_stock_batches").state == "1"
    assert float(hass.states.get("sensor.home_stock_stock_value").state) == 1.2
    assert hass.states.get("binary_sensor.home_stock_shortages").state == "on"
    shortages = hass.states.get("binary_sensor.home_stock_shortages")
    assert shortages.attributes["products"] == ["Lait"]


async def test_the_cumulative_counters_only_count_what_left_the_stock(hass, loaded):
    manager = loaded.runtime_data.manager

    def _seed() -> None:
        with manager.db.write() as conn:
            location_id = repo.insert_location(conn, name="Placard", kind="pantry")
            product_id = repo.insert_product(conn, name="Pâtes", base_unit="g")
            article_id = repo.insert_article(conn, product_id=product_id,
                                             kcal_per_base_unit=3.5)
        manager.add_stock(article_id=article_id, quantity=500,
                          location_id=location_id, price_per_base_unit=0.004,
                          occurred_at="2026-08-18T10:00:00")
        manager.consume(product_id=product_id, quantity=200,
                        occurred_at="2026-08-18T19:00:00")

    await hass.async_add_executor_job(_seed)
    await loaded.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    # The purchase of 500 g must not count: only the 200 g that left the stock.
    assert float(hass.states.get("sensor.home_stock_kcal_total").state) == 700.0
    assert float(hass.states.get("sensor.home_stock_cost_total").state) == 0.8


async def test_the_todo_list_holds_the_expiring_batches(hass, loaded):
    manager = loaded.runtime_data.manager

    def _seed() -> int:
        with manager.db.write() as conn:
            location_id = repo.insert_location(conn, name="Frigo", kind="fridge")
            product_id = repo.insert_product(conn, name="Yaourt", base_unit="piece")
            article_id = repo.insert_article(conn, product_id=product_id)
        # A date relative to today: a hard-coded one would stop expiring one day.
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        return manager.add_stock(article_id=article_id, quantity=4,
                                 location_id=location_id, best_before=tomorrow,
                                 occurred_at="2026-08-18T10:00:00")

    await hass.async_add_executor_job(_seed)
    await loaded.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    items = await hass.services.async_call(
        "todo", "get_items", {"entity_id": "todo.home_stock_expirations"},
        blocking=True, return_response=True,
    )
    listed = items["todo.home_stock_expirations"]["items"]
    assert len(listed) == 1
    assert "Yaourt" in listed[0]["summary"]
