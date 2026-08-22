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
        # Le rendez-vous ne rafraîchit pas lui-même : il *demande* un
        # rafraîchissement, que l'anti-rebond du coordinateur exécute en
        # tâche de FOND. `async_block_till_done()` ne les attend pas, d'où
        # un test qui réussissait ou échouait au hasard de l'ordonnancement.
        await hass.async_block_till_done(wait_background_tasks=True)

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


# --- Lot 2bis : les objectifs suivent la même frontière de 4 h ---------------

async def _entry_with_goals(hass, setup_entry, goals):
    """L'entrée standard, dont les options portent des plafonds."""
    entry = await setup_entry(with_article=True)
    hass.config_entries.async_update_entry(entry, options={"nutrition_goals": goals})
    await hass.async_block_till_done()
    return entry


async def test_the_goals_food_day_is_the_one_the_summary_computed(hass, setup_entry):
    """Le coordinateur ne calcule aucune date locale de son côté : il relit
    celle que `food_day_bounds()` a déjà rendue."""
    await hass.config.async_set_time_zone("Europe/Paris")
    with freeze_time("2026-08-21T03:59:00+02:00"):
        entry = await _entry_with_goals(hass, setup_entry, {"salt": 6.0})
        coordinator = entry.runtime_data.coordinator
        await coordinator.async_refresh()
        veille = coordinator.data["goals"]["food_day"]
        assert veille == coordinator.data["today"]["food_day"] == "2026-08-20"

    with freeze_time("2026-08-21T04:01:00+02:00"):
        await coordinator.async_refresh()
        assert coordinator.data["goals"]["food_day"] == "2026-08-21"
        assert coordinator.data["goals"]["food_day"] == coordinator.data["today"]["food_day"]


async def test_a_breach_of_yesterday_is_gone_after_the_four_o_clock_rendezvous(
        hass, setup_entry):
    """Sans le rendez-vous de 4 h, le dépassement de la veille resterait `on`
    toute la matinée."""
    await hass.config.async_set_time_zone("Europe/Paris")
    with freeze_time("2026-08-20T20:00:00+02:00"):
        # 6 g : la journée (8,4 g) dépasse, la moyenne des sept journées
        # closes (8,4 / 7 = 1,2 g) ne dépasse pas — le retour à `off` prouve
        # donc bien le passage de la journée, et non l'oubli de la semaine.
        entry = await _entry_with_goals(hass, setup_entry, {"salt": 6.0})
        coordinator = entry.runtime_data.coordinator
        manager = entry.runtime_data.manager

        def _seed() -> None:
            with manager.db.write() as conn:
                conn.execute("UPDATE article SET salt = 0.084 WHERE id = 1")
            manager.add_stock(article_id=1, quantity=500.0, location_id=1)
            manager.consume(product_id=1, quantity=100.0)

        await hass.async_add_executor_job(_seed)
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert hass.states.get("binary_sensor.home_stock_nutrition_goals").state == "on"

    with freeze_time("2026-08-21T04:00:01+02:00"):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
        # Le rendez-vous ne rafraîchit pas lui-même : il *demande* un
        # rafraîchissement, que l'anti-rebond du coordinateur exécute en
        # tâche de FOND. `async_block_till_done()` ne les attend pas, d'où
        # un test qui réussissait ou échouait au hasard de l'ordonnancement.
        await hass.async_block_till_done(wait_background_tasks=True)

    assert coordinator.data["goals"]["count"] == 0
    assert hass.states.get("binary_sensor.home_stock_nutrition_goals").state == "off"
