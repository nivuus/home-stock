"""The four o'clock boundary turns the food day over on its own."""
from datetime import timedelta

from freezegun import freeze_time
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed


async def test_the_day_resets_at_four_without_any_activity(hass, setup_entry):
    """Without this rendezvous, the sensor would keep yesterday's total
    until the next stock withdrawal came along to correct it."""
    await hass.config.async_set_time_zone("Europe/Paris")
    with freeze_time("2026-08-20T20:00:00+02:00"):
        entry = await setup_entry(with_article=True)
        coordinator = entry.runtime_data.coordinator
        manager = entry.runtime_data.manager
        await hass.async_add_executor_job(
            lambda: manager.add_stock(article_id=1, quantity=500.0, location_id=1))
        await hass.async_add_executor_job(
            lambda: manager.consume(product_id=1, quantity=100.0))
        await coordinator.async_refresh()
        assert coordinator.data["today"]["food_day"] == "2026-08-20"

    with freeze_time("2026-08-21T04:00:01+02:00"):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
        await hass.async_block_till_done()

    assert coordinator.data["today"]["food_day"] == "2026-08-21"
    assert coordinator.data["today"]["kcal"] == 0.0


async def test_the_rendezvous_is_cancelled_when_the_entry_unloads(hass, setup_entry):
    """A rendezvous left behind would call back into a coordinator that
    nobody owns any more."""
    entry = await setup_entry()
    coordinator = entry.runtime_data.coordinator
    assert coordinator.food_day_rollover_pending
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert not coordinator.food_day_rollover_pending
