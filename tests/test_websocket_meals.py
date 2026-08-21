"""Les commandes repas, vues du panneau. Aucune surface n'est la plus faible."""
import pytest

from custom_components.home_stock.storage import repositories as repo


async def _ask(client, payload):
    await client.send_json_auto_id(payload)
    return await client.receive_json()


async def _kitchen(hass, entry, *, amount=300.0, available=900.0):
    """Une recette d'une ligne, du stock, et un frigo. Rend l'id de recette."""
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
                                   amount=amount, match_state="auto")
            article_id = repo.insert_article(conn, product_id=product_id)
            repo.insert_batch(conn, article_id=article_id, location_id=1,
                              quantity=available, entered_at="2026-08-01T10:00:00")
        return recipe_id

    return await hass.async_add_executor_job(_seed)


# --- poser ------------------------------------------------------------------

async def test_meal_plan_returns_the_meal_id_and_the_uid(hass, hass_ws_client,
                                                         setup_entry):
    await setup_entry()
    client = await hass_ws_client(hass)
    answer = await _ask(client, {"type": "home_stock/meal/plan",
                                 "day": "2026-08-21", "slot_key": "dinner",
                                 "note": "Restaurant"})
    assert answer["success"]
    assert answer["result"]["meal_id"]
    assert answer["result"]["uid"].startswith("home-stock-meal-")


@pytest.mark.parametrize("servings", [0, -1, "deux"])
async def test_meal_plan_refuses_a_bad_servings(hass, hass_ws_client, setup_entry,
                                                servings):
    await setup_entry()
    client = await hass_ws_client(hass)
    answer = await _ask(client, {"type": "home_stock/meal/plan",
                                 "day": "2026-08-21", "slot_key": "dinner",
                                 "note": "x", "servings": servings})
    assert not answer["success"]


async def test_meal_plan_refuses_an_unknown_slot(hass, hass_ws_client, setup_entry):
    await setup_entry()
    client = await hass_ws_client(hass)
    answer = await _ask(client, {"type": "home_stock/meal/plan",
                                 "day": "2026-08-21", "slot_key": "brunch",
                                 "note": "x"})
    assert not answer["success"]


@pytest.mark.parametrize("day", ["2026-8-1", "20260801", "hier", "2026-W01-1", ""])
async def test_meal_plan_refuses_a_malformed_day(hass, hass_ws_client, setup_entry,
                                                 day):
    """La forme étendue AAAA-MM-JJ et rien d'autre, comme au lot 1."""
    await setup_entry()
    client = await hass_ws_client(hass)
    answer = await _ask(client, {"type": "home_stock/meal/plan",
                                 "day": day, "slot_key": "dinner", "note": "x"})
    assert not answer["success"]


async def test_meal_plan_refuses_two_natures_at_once(hass, hass_ws_client,
                                                     setup_entry):
    entry = await setup_entry()
    recipe_id = await _kitchen(hass, entry)
    client = await hass_ws_client(hass)
    answer = await _ask(client, {"type": "home_stock/meal/plan",
                                 "day": "2026-08-21", "slot_key": "dinner",
                                 "recipe_id": recipe_id, "note": "x"})
    assert not answer["success"]


# --- lire, déplacer, annuler ------------------------------------------------

async def test_meals_list_bounds_are_validated_as_iso_dates(hass, hass_ws_client,
                                                            setup_entry):
    await setup_entry()
    client = await hass_ws_client(hass)
    answer = await _ask(client, {"type": "home_stock/meals/list",
                                 "start": "hier", "end": "2026-08-21"})
    assert not answer["success"]


async def test_meals_list_returns_the_meals_of_the_range(hass, hass_ws_client,
                                                         setup_entry):
    await setup_entry()
    client = await hass_ws_client(hass)
    await _ask(client, {"type": "home_stock/meal/plan", "day": "2026-08-21",
                        "slot_key": "dinner", "note": "Restaurant"})
    answer = await _ask(client, {"type": "home_stock/meals/list",
                                 "start": "2026-08-21", "end": "2026-08-21"})
    assert [m["note"] for m in answer["result"]["meals"]] == ["Restaurant"]


async def test_meal_move_refuses_a_done_meal(hass, hass_ws_client, setup_entry):
    entry = await setup_entry()
    manager = entry.runtime_data.manager
    client = await hass_ws_client(hass)
    posted = await _ask(client, {"type": "home_stock/meal/plan",
                                 "day": "2026-08-21", "slot_key": "dinner",
                                 "note": "x"})
    meal_id = posted["result"]["meal_id"]

    def _done():
        with manager.db.write() as conn:
            repo.update_meal_fields(conn, meal_id, {"state": "done"})

    await hass.async_add_executor_job(_done)
    answer = await _ask(client, {"type": "home_stock/meal/move",
                                 "meal_id": meal_id, "day": "2026-08-23",
                                 "slot_key": "lunch"})
    assert not answer["success"]


async def test_meal_cancel_deletes_a_planned_and_skips_a_done(hass, hass_ws_client,
                                                              setup_entry):
    entry = await setup_entry()
    manager = entry.runtime_data.manager
    client = await hass_ws_client(hass)

    planned = await _ask(client, {"type": "home_stock/meal/plan",
                                  "day": "2026-08-21", "slot_key": "dinner",
                                  "note": "prévu"})
    answer = await _ask(client, {"type": "home_stock/meal/cancel",
                                 "meal_id": planned["result"]["meal_id"]})
    assert answer["result"]["outcome"] == "deleted"

    done = await _ask(client, {"type": "home_stock/meal/plan",
                               "day": "2026-08-22", "slot_key": "dinner",
                               "note": "validé"})
    meal_id = done["result"]["meal_id"]

    def _done():
        with manager.db.write() as conn:
            repo.update_meal_fields(conn, meal_id, {"state": "done"})

    await hass.async_add_executor_job(_done)
    answer = await _ask(client, {"type": "home_stock/meal/cancel",
                                 "meal_id": meal_id})
    assert answer["result"]["outcome"] == "skipped"


# --- simuler et valider -----------------------------------------------------

async def test_meal_preview_writes_nothing(hass, hass_ws_client, setup_entry):
    entry = await setup_entry()
    recipe_id = await _kitchen(hass, entry)
    manager = entry.runtime_data.manager
    client = await hass_ws_client(hass)
    posted = await _ask(client, {"type": "home_stock/meal/plan",
                                 "day": "2026-08-21", "slot_key": "dinner",
                                 "recipe_id": recipe_id, "servings": 3})

    answer = await _ask(client, {"type": "home_stock/meal/preview",
                                 "meal_id": posted["result"]["meal_id"]})
    assert answer["success"]
    assert answer["result"]["factor"] == 3.0
    assert [l["status"] for l in answer["result"]["lines"]] == ["ok"]

    movements = await hass.async_add_executor_job(
        lambda: manager.db.read().execute(
            "SELECT COUNT(*) c FROM movement").fetchone()["c"])
    assert movements == 0


async def test_meal_validate_writes_the_movements_and_returns_them(
        hass, hass_ws_client, setup_entry):
    entry = await setup_entry()
    recipe_id = await _kitchen(hass, entry)
    client = await hass_ws_client(hass)
    posted = await _ask(client, {"type": "home_stock/meal/plan",
                                 "day": "2026-08-21", "slot_key": "dinner",
                                 "recipe_id": recipe_id, "servings": 3})
    answer = await _ask(client, {"type": "home_stock/meal/validate",
                                 "meal_id": posted["result"]["meal_id"],
                                 "portions_eaten": 1,
                                 "idempotency_key": "panneau-1"})
    assert answer["success"]
    assert len(answer["result"]["movement_ids"]) == 3
    assert answer["result"]["batch_id"]


async def test_meal_validate_is_idempotent_on_replay(hass, hass_ws_client,
                                                     setup_entry):
    """Le garde-fou est la famille `meal:<id>:…`, pas la clé du panneau : deux
    clés différentes pour le même repas ne décrémentent pas deux fois."""
    entry = await setup_entry()
    recipe_id = await _kitchen(hass, entry)
    manager = entry.runtime_data.manager
    client = await hass_ws_client(hass)
    posted = await _ask(client, {"type": "home_stock/meal/plan",
                                 "day": "2026-08-21", "slot_key": "dinner",
                                 "recipe_id": recipe_id, "servings": 3})
    meal_id = posted["result"]["meal_id"]

    first = await _ask(client, {"type": "home_stock/meal/validate",
                                "meal_id": meal_id, "portions_eaten": 1,
                                "idempotency_key": "panneau-1"})

    def _replan():
        with manager.db.write() as conn:
            repo.update_meal_fields(conn, meal_id, {"state": "planned"})

    await hass.async_add_executor_job(_replan)
    second = await _ask(client, {"type": "home_stock/meal/validate",
                                 "meal_id": meal_id, "portions_eaten": 1,
                                 "idempotency_key": "panneau-DIFFERENTE"})
    assert second["success"]
    assert second["result"]["movement_ids"] == first["result"]["movement_ids"]

    count = await hass.async_add_executor_job(
        lambda: manager.db.read().execute(
            "SELECT COUNT(*) c FROM movement").fetchone()["c"])
    assert count == 3


async def test_meal_validate_refuses_more_parts_eaten_than_served(
        hass, hass_ws_client, setup_entry):
    entry = await setup_entry()
    recipe_id = await _kitchen(hass, entry)
    client = await hass_ws_client(hass)
    posted = await _ask(client, {"type": "home_stock/meal/plan",
                                 "day": "2026-08-21", "slot_key": "dinner",
                                 "recipe_id": recipe_id, "servings": 3})
    answer = await _ask(client, {"type": "home_stock/meal/validate",
                                 "meal_id": posted["result"]["meal_id"],
                                 "portions_eaten": 4})
    assert not answer["success"]


async def test_meal_validate_refuses_an_insufficient_stock_in_french(
        hass, hass_ws_client, setup_entry):
    entry = await setup_entry()
    recipe_id = await _kitchen(hass, entry, amount=500.0, available=200.0)
    client = await hass_ws_client(hass)
    posted = await _ask(client, {"type": "home_stock/meal/plan",
                                 "day": "2026-08-21", "slot_key": "dinner",
                                 "recipe_id": recipe_id, "servings": 1})
    answer = await _ask(client, {"type": "home_stock/meal/validate",
                                 "meal_id": posted["result"]["meal_id"],
                                 "portions_eaten": 1})
    assert not answer["success"]
    assert answer["error"]["message"]


@pytest.mark.parametrize("payload", [
    {"parts_total": 25, "parts_mine": 1},
    {"parts_total": 2, "parts_mine": 3},
])
async def test_meal_validate_refuses_inconsistent_parts(hass, hass_ws_client,
                                                        setup_entry, payload):
    entry = await setup_entry()
    recipe_id = await _kitchen(hass, entry)
    client = await hass_ws_client(hass)
    posted = await _ask(client, {"type": "home_stock/meal/plan",
                                 "day": "2026-08-21", "slot_key": "dinner",
                                 "recipe_id": recipe_id, "servings": 3})
    answer = await _ask(client, {"type": "home_stock/meal/validate",
                                 "meal_id": posted["result"]["meal_id"],
                                 "portions_eaten": 1, **payload})
    assert not answer["success"]


@pytest.mark.parametrize("portions", [-1, "une"])
async def test_meal_validate_refuses_a_bad_portions_eaten(hass, hass_ws_client,
                                                          setup_entry, portions):
    entry = await setup_entry()
    recipe_id = await _kitchen(hass, entry)
    client = await hass_ws_client(hass)
    posted = await _ask(client, {"type": "home_stock/meal/plan",
                                 "day": "2026-08-21", "slot_key": "dinner",
                                 "recipe_id": recipe_id, "servings": 3})
    answer = await _ask(client, {"type": "home_stock/meal/validate",
                                 "meal_id": posted["result"]["meal_id"],
                                 "portions_eaten": portions})
    assert not answer["success"]


# --- la file hors-ligne pose sa clé sur TOUT -------------------------------

async def test_every_write_command_accepts_an_idempotency_key(hass, hass_ws_client,
                                                              setup_entry):
    """L'incident du lot 1 : trois commandes à schéma strict, refusées au
    premier rejeu hors ligne. La file ne sait pas quelles commandes en
    prennent une — elle en pose une sur tout."""
    entry = await setup_entry()
    recipe_id = await _kitchen(hass, entry)
    manager = entry.runtime_data.manager
    client = await hass_ws_client(hass)

    posted = await _ask(client, {"type": "home_stock/meal/plan",
                                 "day": "2026-08-21", "slot_key": "dinner",
                                 "recipe_id": recipe_id, "servings": 3,
                                 "idempotency_key": "k1"})
    assert posted["success"]
    meal_id = posted["result"]["meal_id"]

    line = (await hass.async_add_executor_job(
        lambda: repo.list_ingredients(manager.db.read(), recipe_id)))[0]

    for payload in (
        {"type": "home_stock/recipe/create", "name": "R", "idempotency_key": "k2"},
        {"type": "home_stock/recipe/update", "recipe_id": recipe_id,
         "fields": {"name": "R2"}, "idempotency_key": "k3"},
        {"type": "home_stock/recipe/ingredient/match",
         "ingredient_id": line["id"], "state": "ignored", "idempotency_key": "k4"},
        {"type": "home_stock/meal/move", "meal_id": meal_id, "day": "2026-08-22",
         "slot_key": "lunch", "idempotency_key": "k5"},
        {"type": "home_stock/meal/validate", "meal_id": meal_id,
         "portions_eaten": 0, "idempotency_key": "k6"},
        {"type": "home_stock/meal/cancel", "meal_id": meal_id,
         "idempotency_key": "k7"},
    ):
        answer = await _ask(client, payload)
        assert answer["success"], payload["type"]
