"""sensor.home_stock_kcal_today after a meal is validated, through the real
surfaces: the panel's `home_stock/meal/validate` command, the
`home_stock.validate_meal` service the « terminé » script calls, and
`home_stock/stock/consume` for the leftover eaten later.
"""
import pytest

from custom_components.home_stock.const import DOMAIN
from custom_components.home_stock.storage import repositories as repo

KCAL_TODAY = "sensor.home_stock_kcal_today"
# 80 g of crispbread at 4.2 kcal/g (420 kcal/100 g) and one egg at 78 kcal.
CRISPBREAD_KCAL = 80 * 4.2
EGG_KCAL = 78.0


async def _ask(client, payload):
    await client.send_json_auto_id(payload)
    return await client.receive_json()


async def _breakfast(hass, entry, *, servings=1.0, egg_kcal=EGG_KCAL,
                     crispbread_kcal_per_g=4.2):
    """A two-line breakfast recipe, its stock, a fridge, and the meal planned
    for today. Returns the meal id."""
    manager = entry.runtime_data.manager

    def _seed():
        with manager.db.write() as conn:
            fridge = repo.insert_location(conn, name="Frigo", kind="fridge")
            recipe_id = repo.insert_recipe(conn, name="Petit-déjeuner",
                                           source="manual",
                                           created_at="2026-10-01T08:00:00",
                                           servings=1)
            lines = (("Krisprolls", "g", crispbread_kcal_per_g, 80.0, 225.0),
                     ("Œuf", "piece", egg_kcal, 1.0, 6.0))
            for position, (name, unit, rate, amount, stock) in enumerate(lines, 1):
                product_id = repo.insert_product(conn, name=name, base_unit=unit,
                                                 reference_kcal=rate)
                repo.insert_ingredient(conn, recipe_id=recipe_id,
                                       position=position, raw_text=name,
                                       product_id=product_id, amount=amount,
                                       match_state="auto")
                article_id = repo.insert_article(conn, product_id=product_id)
                repo.insert_batch(conn, article_id=article_id,
                                  location_id=fridge, quantity=stock,
                                  entered_at="2026-10-01T10:00:00")
        return recipe_id

    recipe_id = await hass.async_add_executor_job(_seed)
    today = entry.runtime_data.coordinator.data["today"]["food_day"]
    return await hass.async_add_executor_job(
        lambda: manager.plan_meal(day=today, slot_key="breakfast",
                                  recipe_id=recipe_id, servings=servings)["meal_id"])


async def _kcal_today(hass, entry):
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()
    state = hass.states.get(KCAL_TODAY)
    return float(state.state), state.attributes["unvalued_movements"]


async def test_the_panel_validation_adds_the_whole_meal(hass, hass_ws_client,
                                                        setup_entry):
    entry = await setup_entry()
    meal_id = await _breakfast(hass, entry)
    before, _ = await _kcal_today(hass, entry)
    client = await hass_ws_client(hass)
    answer = await _ask(client, {"type": "home_stock/meal/validate",
                                 "meal_id": meal_id, "portions_eaten": 1})
    assert answer["success"], answer
    after, unvalued = await _kcal_today(hass, entry)
    assert after - before == pytest.approx(CRISPBREAD_KCAL + EGG_KCAL, abs=0.05)
    assert unvalued == 0


async def test_the_service_validation_takes_the_leftover_off(hass, setup_entry):
    entry = await setup_entry()
    meal_id = await _breakfast(hass, entry, servings=2.0)
    before, _ = await _kcal_today(hass, entry)
    result = await hass.services.async_call(
        DOMAIN, "validate_meal",
        {"meal_id": meal_id, "portions_eaten": 1, "dry_run": False},
        blocking=True, return_response=True)
    after, _ = await _kcal_today(hass, entry)
    whole = 2 * (CRISPBREAD_KCAL + EGG_KCAL)
    assert after - before == pytest.approx(whole / 2, abs=0.05)
    assert result["dish"]["kcal"] == pytest.approx(whole / 2)


async def test_the_leftover_eaten_later_adds_its_own_kcal_once(
        hass, hass_ws_client, setup_entry):
    entry = await setup_entry()
    meal_id = await _breakfast(hass, entry, servings=2.0)
    client = await hass_ws_client(hass)
    validated = await _ask(client, {"type": "home_stock/meal/validate",
                                    "meal_id": meal_id, "portions_eaten": 1})
    middle, _ = await _kcal_today(hass, entry)
    manager = entry.runtime_data.manager
    leftover_product = await hass.async_add_executor_job(
        lambda: manager.db.read().execute(
            "SELECT a.product_id FROM batch b JOIN article a ON a.id = b.article_id"
            " WHERE b.id = ?", (validated["result"]["batch_id"],)
        ).fetchone()["product_id"])
    answer = await _ask(client, {"type": "home_stock/stock/consume",
                                 "product_id": leftover_product, "quantity": 1})
    assert answer["success"], answer
    after, unvalued = await _kcal_today(hass, entry)
    whole = 2 * (CRISPBREAD_KCAL + EGG_KCAL)
    assert after - middle == pytest.approx(whole / 2, abs=0.05)
    assert after == pytest.approx(whole, abs=0.05)
    assert unvalued == 0


async def test_an_unvalued_ingredient_no_longer_zeroes_the_meal(
        hass, hass_ws_client, setup_entry):
    """The 03/10 defect, through the real command: one ingredient with no
    kcal made the whole meal count zero and one `unvalued_movements`."""
    entry = await setup_entry()
    meal_id = await _breakfast(hass, entry, egg_kcal=None)
    client = await hass_ws_client(hass)
    answer = await _ask(client, {"type": "home_stock/meal/validate",
                                 "meal_id": meal_id, "portions_eaten": 1})
    assert answer["success"], answer
    after, unvalued = await _kcal_today(hass, entry)
    assert after == pytest.approx(CRISPBREAD_KCAL, abs=0.05)
    assert unvalued == 0


async def test_a_meal_without_any_kcal_adds_zero_and_is_reported(
        hass, hass_ws_client, setup_entry):
    entry = await setup_entry()
    meal_id = await _breakfast(hass, entry, egg_kcal=None,
                               crispbread_kcal_per_g=None)
    client = await hass_ws_client(hass)
    answer = await _ask(client, {"type": "home_stock/meal/validate",
                                 "meal_id": meal_id, "portions_eaten": 1})
    assert answer["success"], answer
    after, unvalued = await _kcal_today(hass, entry)
    assert after == 0
    assert unvalued == 1


async def test_a_simulated_service_call_moves_nothing(hass, setup_entry):
    entry = await setup_entry()
    meal_id = await _breakfast(hass, entry)
    before, _ = await _kcal_today(hass, entry)
    await hass.services.async_call(
        DOMAIN, "validate_meal", {"meal_id": meal_id, "portions_eaten": 1},
        blocking=True, return_response=True)
    after, _ = await _kcal_today(hass, entry)
    assert after == before == 0
