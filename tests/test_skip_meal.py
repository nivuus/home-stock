"""The `home_stock.skip_meal` service, called the way a Lovelace card calls it.

Every test goes through Home Assistant's real service registry (or its REST
API, or the websocket the panel uses) on a real, freshly created database:
nothing here is mocked. The clock is frozen only where "today" matters.
"""
from pathlib import Path

import pytest
import voluptuous as vol
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.service import async_get_all_descriptions
from homeassistant.setup import async_setup_component

from custom_components.home_stock.const import DOMAIN
from custom_components.home_stock.skip_meal import current_food_day
from custom_components.home_stock.storage import repositories as repo

SERVICES_YAML = (Path(__file__).parent.parent / "custom_components" / "home_stock"
                 / "services.yaml")

# 18:00 UTC is 11:00 in US/Pacific, the test instance's time zone: well
# inside the food day of 2026-08-21, far from its 4 a.m. boundary.
NOON_ON_THE_21ST = "2026-08-21T18:00:00+00:00"
TODAY = "2026-08-21"


async def _kitchen(hass, entry):
    """One one-line recipe, a fridge and 900 g of stock. Returns the recipe id."""
    manager = entry.runtime_data.manager

    def _seed():
        with manager.db.write() as conn:
            repo.insert_location(conn, name="Frigo", kind="fridge")
            product_id = repo.insert_product(conn, name="Courgette", base_unit="g")
            recipe_id = repo.insert_recipe(conn, name="Gratin", source="manual",
                                           created_at="2026-08-21T10:00:00",
                                           servings=1)
            repo.insert_ingredient(conn, recipe_id=recipe_id, position=1,
                                   raw_text="courgette", product_id=product_id,
                                   amount=300.0, match_state="auto")
            article_id = repo.insert_article(conn, product_id=product_id)
            repo.insert_batch(conn, article_id=article_id, location_id=1,
                              quantity=900.0, entered_at="2026-08-01T10:00:00")
        return recipe_id

    return await hass.async_add_executor_job(_seed)


async def _plan(hass, entry, recipe_id, *, day=TODAY, slot_key="dinner"):
    manager = entry.runtime_data.manager
    posted = await hass.async_add_executor_job(
        lambda: manager.plan_meal(day=day, slot_key=slot_key, recipe_id=recipe_id))
    return posted["meal_id"]


async def _validate(hass, meal_id):
    await hass.services.async_call(
        DOMAIN, "validate_meal",
        {"meal_id": meal_id, "portions_eaten": 1, "dry_run": False},
        blocking=True)


async def _state(hass, entry, meal_id):
    manager = entry.runtime_data.manager
    meal = await hass.async_add_executor_job(
        lambda: repo.get_meal(manager.db.read(), meal_id))
    return None if meal is None else meal["state"]


async def _ledger(hass, entry):
    """What a skip must never change: the journal and the stock it books."""
    manager = entry.runtime_data.manager

    def _read():
        conn = manager.db.read()
        movements = conn.execute("SELECT COUNT(*) c FROM movement").fetchone()["c"]
        batches = conn.execute(
            "SELECT COUNT(*) n, TOTAL(remaining) total FROM batch").fetchone()
        return movements, batches["n"], batches["total"]

    return await hass.async_add_executor_job(_read)


async def _skip(hass, data=None):
    return await hass.services.async_call(
        DOMAIN, "skip_meal", data or {}, blocking=True, return_response=True)


# --- registration and description -----------------------------------------

async def test_skip_meal_is_registered_with_its_french_description(hass, setup_entry):
    await setup_entry()
    assert hass.services.has_service(DOMAIN, "skip_meal")

    # The real descriptions loader: it reads services.yaml the way the
    # frontend's action editor does.
    descriptions = await async_get_all_descriptions(hass)
    described = descriptions[DOMAIN]["skip_meal"]
    assert described["name"] == "Ignorer un repas"
    assert described["description"].startswith("Marque un repas comme ignoré")
    assert described["fields"]["meal_id"]["name"] == "Repas"
    assert "prochain repas planifié" in described["fields"]["meal_id"]["description"]
    # The loader read the WHOLE file, not only this entry.
    assert descriptions[DOMAIN]["create_product"]["name"] == "Créer un produit"


def test_services_yaml_has_no_flow_style_list():
    flow_lists = [
        (number, line) for number, line in
        enumerate(SERVICES_YAML.read_text(encoding="utf-8").splitlines(), 1)
        if ": [" in line or line.lstrip().startswith("- [")
    ]
    assert flow_lists == []


async def test_skip_meal_is_listed_by_the_rest_api(hass, hass_client, setup_entry):
    await setup_entry()
    assert await async_setup_component(hass, "api", {})
    client = await hass_client()

    response = await client.get("/api/services")

    assert response.status == 200
    domains = {item["domain"]: item["services"] for item in await response.json()}
    assert "skip_meal" in domains[DOMAIN]


# --- a planned meal ---------------------------------------------------------

async def test_a_planned_meal_becomes_skipped_without_any_stock_movement(
        hass, setup_entry):
    entry = await setup_entry()
    meal_id = await _plan(hass, entry, await _kitchen(hass, entry))
    before = await _ledger(hass, entry)

    answer = await _skip(hass, {"meal_id": meal_id})

    assert answer == {"meal_id": meal_id, "day": TODAY, "slot_key": "dinner",
                      "outcome": "skipped"}
    assert await _state(hass, entry, meal_id) == "skipped"
    assert await _ledger(hass, entry) == before


async def test_without_meal_id_the_next_planned_meal_of_today_is_skipped(
        hass, setup_entry, freezer):
    freezer.move_to(NOON_ON_THE_21ST)
    entry = await setup_entry()
    recipe_id = await _kitchen(hass, entry)
    dinner = await _plan(hass, entry, recipe_id, slot_key="dinner")
    lunch = await _plan(hass, entry, recipe_id, slot_key="lunch")
    before = await _ledger(hass, entry)
    assert current_food_day(hass) == TODAY

    answer = await _skip(hass)

    assert answer["meal_id"] == lunch
    assert await _state(hass, entry, lunch) == "skipped"
    assert await _state(hass, entry, dinner) == "planned"
    assert await _ledger(hass, entry) == before

    # Pressed again, the button moves on to the next meal of the day.
    assert (await _skip(hass))["meal_id"] == dinner
    assert await _state(hass, entry, dinner) == "skipped"


async def test_without_meal_id_nothing_planned_today_is_refused_in_french(
        hass, setup_entry, freezer):
    freezer.move_to(NOON_ON_THE_21ST)
    entry = await setup_entry()
    tomorrow = await _plan(hass, entry, await _kitchen(hass, entry),
                           day="2026-08-22")

    with pytest.raises(ServiceValidationError,
                       match=r"Aucun repas planifié à ignorer aujourd'hui \(2026-08-21\)"):
        await _skip(hass)

    assert await _state(hass, entry, tomorrow) == "planned"


async def test_a_meal_already_skipped_is_left_as_it_is(hass, setup_entry):
    entry = await setup_entry()
    meal_id = await _plan(hass, entry, await _kitchen(hass, entry))
    await _skip(hass, {"meal_id": meal_id})

    answer = await _skip(hass, {"meal_id": meal_id})

    assert answer["outcome"] == "already_skipped"
    assert await _state(hass, entry, meal_id) == "skipped"


# --- a validated meal: exactly what meal/cancel does ------------------------

async def test_a_done_meal_gets_what_meal_cancel_gives_it(
        hass, hass_ws_client, setup_entry):
    entry = await setup_entry()
    recipe_id = await _kitchen(hass, entry)
    by_service = await _plan(hass, entry, recipe_id, slot_key="lunch")
    by_websocket = await _plan(hass, entry, recipe_id, slot_key="dinner")
    await _validate(hass, by_service)
    await _validate(hass, by_websocket)
    assert await _state(hass, entry, by_service) == "done"
    assert await _state(hass, entry, by_websocket) == "done"
    before = await _ledger(hass, entry)
    assert before[0] > 0  # the two validations did write to the journal

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "home_stock/meal/cancel",
                                    "meal_id": by_websocket})
    from_websocket = await client.receive_json()
    from_service = await _skip(hass, {"meal_id": by_service})

    assert from_websocket["result"] == {"outcome": "skipped"}
    assert from_service["outcome"] == "skipped"
    assert await _state(hass, entry, by_service) == "skipped"
    assert await _state(hass, entry, by_websocket) == "skipped"
    assert await _ledger(hass, entry) == before


# --- refusals ---------------------------------------------------------------

async def test_an_unknown_meal_is_refused_in_french(hass, setup_entry):
    await setup_entry()
    with pytest.raises(HomeAssistantError, match=r"^Repas 999 introuvable\.$"):
        await _skip(hass, {"meal_id": 999})


@pytest.mark.parametrize("meal_id", [1.5, True, "abc"])
async def test_a_meal_id_that_is_not_a_whole_number_is_refused(
        hass, setup_entry, meal_id):
    await setup_entry()
    with pytest.raises(vol.Invalid, match="expected a whole number"):
        await _skip(hass, {"meal_id": meal_id})


async def test_the_call_works_without_asking_for_a_response(hass, setup_entry):
    entry = await setup_entry()
    meal_id = await _plan(hass, entry, await _kitchen(hass, entry))

    # A dashboard button calls the service this way: no response requested.
    await hass.services.async_call(DOMAIN, "skip_meal", {"meal_id": meal_id},
                                   blocking=True)

    assert await _state(hass, entry, meal_id) == "skipped"
