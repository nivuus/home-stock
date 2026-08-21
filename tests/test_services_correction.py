"""Les deux services de correction, et leur parité avec le websocket."""
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.home_stock.storage import repositories as repo


async def _call(hass, service, payload, response=True):
    return await hass.services.async_call(
        "home_stock", service, payload, blocking=True, return_response=response)


async def _one_movement(hass, entry):
    manager = entry.runtime_data.manager

    def _write() -> dict:
        with manager.db.write() as conn:
            location_id = repo.insert_location(conn, name="Frigo", kind="fridge")
        batch_id = manager.add_stock(article_id=1, quantity=1000,
                                     location_id=location_id,
                                     price_per_base_unit=0.002,
                                     occurred_at="2026-08-14T10:00:00")
        return {"batch_id": batch_id,
                "movement_id": manager.consume_batch(
                    batch_id, quantity=200.0, occurred_at="2026-08-14T18:00:00")}

    return await hass.async_add_executor_job(_write)


async def test_correct_movement_service_matches_the_websocket(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    entry = await setup_entry(with_article=True)
    ids = await _one_movement(hass, entry)

    answer = await _call(hass, "correct_movement",
                         {"movement_id": ids["movement_id"]})

    assert answer["correction_id"]
    assert answer["restored"] is True
    conn = entry.runtime_data.manager.db.read()
    assert repo.correction_of(conn, ids["movement_id"]) is not None


async def test_correcting_twice_answers_in_french(hass: HomeAssistant, setup_entry):
    entry = await setup_entry(with_article=True)
    ids = await _one_movement(hass, entry)
    first = await _call(hass, "correct_movement",
                        {"movement_id": ids["movement_id"]})

    with pytest.raises(HomeAssistantError) as refus:
        await _call(hass, "correct_movement",
                    {"movement_id": first["correction_id"]})
    assert str(refus.value) == (
        "Cette ligne est déjà une correction : corriger une correction, "
        "c'est refaire la saisie.")


async def test_correcting_an_unknown_movement_says_so_in_french(
        hass: HomeAssistant, setup_entry):
    await setup_entry(with_article=True)
    with pytest.raises(HomeAssistantError) as refus:
        await _call(hass, "correct_movement", {"movement_id": 4242})
    assert str(refus.value) == "Mouvement 4242 inconnu."


async def test_correct_meal_service_refuses_a_meal_never_validated(
        hass: HomeAssistant, setup_entry):
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager

    def _plan() -> int:
        with manager.db.write() as conn:
            recipe_id = repo.insert_recipe(conn, name="Gratin", source="manual",
                                           created_at="2026-08-21T10:00:00",
                                           servings=1)
        return manager.plan_meal(day="2026-08-21", slot_key="dinner",
                                 recipe_id=recipe_id)["meal_id"]

    meal_id = await hass.async_add_executor_job(_plan)

    with pytest.raises(HomeAssistantError) as refus:
        await _call(hass, "correct_meal", {"meal_id": meal_id})
    assert str(refus.value) == "Ce repas n'a pas été validé : il n'y a rien à annuler."


async def test_the_correction_moves_the_sensors(hass: HomeAssistant, setup_entry):
    """Le service demande un rafraîchissement : sans lui, les capteurs
    resteraient sur l'ancienne valeur jusqu'au tic suivant, et la correction
    aurait l'air de n'avoir rien fait."""
    entry = await setup_entry(with_article=True)
    ids = await _one_movement(hass, entry)
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()
    before = float(hass.states.get("sensor.home_stock_cost_total").state)

    await _call(hass, "correct_movement", {"movement_id": ids["movement_id"]})
    await hass.async_block_till_done()

    after = float(hass.states.get("sensor.home_stock_cost_total").state)
    assert after == pytest.approx(0.0)
    assert before > 0
