from datetime import date, timedelta

import pytest
from homeassistant.components.todo import DATA_COMPONENT, TodoItem, TodoItemStatus
from homeassistant.exceptions import HomeAssistantError
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
    stock_value = hass.states.get("sensor.home_stock_stock_value")
    assert float(stock_value.state) == 1.2
    assert stock_value.attributes["by_location"] == {"Frigo": pytest.approx(1.2)}
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


def _seed_expiring_yaourt(manager, *, price_per_base_unit=None):
    """A closure ready for hass.async_add_executor_job: seeds one expiring
    batch and returns its batch id."""
    def _seed() -> int:
        with manager.db.write() as conn:
            location_id = repo.insert_location(conn, name="Frigo", kind="fridge")
            product_id = repo.insert_product(conn, name="Yaourt", base_unit="piece")
            article_id = repo.insert_article(conn, product_id=product_id)
        # A date relative to today: a hard-coded one would stop expiring one day.
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        return manager.add_stock(article_id=article_id, quantity=4,
                                 location_id=location_id, best_before=tomorrow,
                                 price_per_base_unit=price_per_base_unit,
                                 occurred_at="2026-08-18T10:00:00")
    return _seed


async def test_checking_an_item_consumes_the_whole_batch(hass, loaded):
    manager = loaded.runtime_data.manager
    seed = _seed_expiring_yaourt(manager, price_per_base_unit=0.3)
    batch_id = await hass.async_add_executor_job(seed)
    await loaded.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    await hass.services.async_call(
        "todo", "update_item",
        {"entity_id": "todo.home_stock_expirations", "item": str(batch_id),
         "status": "completed"},
        blocking=True,
    )
    await hass.async_block_till_done()

    def _check():
        with manager.db.write() as conn:
            batch = conn.execute("SELECT * FROM batch WHERE id = ?", (batch_id,)).fetchone()
            movement = conn.execute(
                "SELECT * FROM movement WHERE batch_id = ? AND reason = 'consumption'",
                (batch_id,),
            ).fetchone()
        return batch, movement

    batch, movement = await hass.async_add_executor_job(_check)
    assert batch["remaining"] == 0
    assert movement is not None


async def test_an_uncompleted_update_does_nothing(hass, loaded):
    manager = loaded.runtime_data.manager
    seed = _seed_expiring_yaourt(manager)
    batch_id = await hass.async_add_executor_job(seed)
    await loaded.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    await hass.services.async_call(
        "todo", "update_item",
        {"entity_id": "todo.home_stock_expirations", "item": str(batch_id),
         "status": "needs_action"},
        blocking=True,
    )
    await hass.async_block_till_done()

    def _check():
        with manager.db.write() as conn:
            batch = conn.execute("SELECT * FROM batch WHERE id = ?", (batch_id,)).fetchone()
            count = conn.execute(
                "SELECT COUNT(*) AS n FROM movement WHERE reason = 'consumption'"
            ).fetchone()["n"]
        return batch, count

    batch, count = await hass.async_add_executor_job(_check)
    assert batch["remaining"] == 4
    assert count == 0


async def test_a_stale_uid_is_a_no_op_not_an_error(hass, loaded):
    """The coordinator refreshes every 15 minutes: a batch consumed elsewhere
    in between is still checkable in the stale list. Ticking it must not blow
    up — the user's intent ("this is finished") is already true."""
    manager = loaded.runtime_data.manager
    seed = _seed_expiring_yaourt(manager)
    batch_id = await hass.async_add_executor_job(seed)
    await loaded.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    # Consumed directly, bypassing the coordinator: its cached data (and hence
    # entity.todo_items) still lists this batch as expiring.
    await hass.async_add_executor_job(manager.consume_batch, batch_id)

    # Must not raise: the frontend would otherwise show "Unknown error" for an
    # action whose intent was already satisfied.
    await hass.services.async_call(
        "todo", "update_item",
        {"entity_id": "todo.home_stock_expirations", "item": str(batch_id),
         "status": "completed"},
        blocking=True,
    )
    await hass.async_block_till_done()


async def test_a_non_numeric_uid_raises_a_home_assistant_error(hass, loaded):
    """Unlike a stale batch id, this can only come from a genuine programming
    error and must surface to the frontend, not vanish as a bare ValueError."""
    entity = hass.data[DATA_COMPONENT].get_entity("todo.home_stock_expirations")
    with pytest.raises(HomeAssistantError, match="not-a-number"):
        await entity.async_update_todo_item(
            TodoItem(uid="not-a-number", status=TodoItemStatus.COMPLETED)
        )
