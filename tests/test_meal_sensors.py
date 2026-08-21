"""Les trois capteurs du lot 3, et les restes dans les alertes qui existaient."""
import pytest

from custom_components.home_stock.storage import repositories as repo

NEXT = "sensor.home_stock_next_meal"
RECIPES = "sensor.home_stock_recipes"
MISSING = "sensor.home_stock_missing_ingredients"


@pytest.fixture(autouse=True)
async def _paris(hass):
    await hass.config.async_set_time_zone("Europe/Paris")


async def _refresh(hass, entry):
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()


async def _write(hass, entry, fn):
    manager = entry.runtime_data.manager

    def _run():
        with manager.db.write() as conn:
            return fn(conn, manager)

    return await hass.async_add_executor_job(_run)


# --- les trois capteurs -----------------------------------------------------

async def test_the_three_sensors_exist(hass, setup_entry):
    await setup_entry()
    for entity_id in (NEXT, RECIPES, MISSING):
        assert hass.states.get(entity_id) is not None, entity_id


async def test_next_meal_is_empty_without_any_meal(hass, setup_entry):
    """Sans repas, l'état est vide — jamais « 0 », qui se lirait comme un repas
    nommé zéro."""
    await setup_entry()
    state = hass.states.get(NEXT)
    assert state.state in ("unknown", "None", "")
    assert state.attributes["missing_ingredients"] == 0


async def test_next_meal_names_the_next_planned_meal(hass, setup_entry):
    entry = await setup_entry()
    manager = entry.runtime_data.manager
    today = await hass.async_add_executor_job(_today)
    await hass.async_add_executor_job(
        lambda: manager.plan_meal(day=today, slot_key="dinner", note="Restaurant"))
    await _refresh(hass, entry)
    state = hass.states.get(NEXT)
    assert state.state == "Restaurant"
    assert state.attributes["day"] == today
    assert state.attributes["slot"] == "dinner"


async def test_next_meal_skips_a_done_meal(hass, setup_entry):
    entry = await setup_entry()
    manager = entry.runtime_data.manager
    today = await hass.async_add_executor_job(_today)

    def _seed():
        posted = manager.plan_meal(day=today, slot_key="lunch", note="Mangé")
        manager.plan_meal(day=today, slot_key="dinner", note="À venir")
        with manager.db.write() as conn:
            repo.update_meal_fields(conn, posted["meal_id"], {"state": "done"})

    await hass.async_add_executor_job(_seed)
    await _refresh(hass, entry)
    assert hass.states.get(NEXT).state == "À venir"


async def test_recipes_counts_only_the_active_ones(hass, setup_entry):
    entry = await setup_entry()
    manager = entry.runtime_data.manager

    def _seed():
        manager.create_recipe(name="Kapsalon")
        manager.create_recipe(name="À relire", needs_review=1)
        inactive = manager.create_recipe(name="Ancienne")
        manager.update_recipe(inactive, {"active": 0})

    await hass.async_add_executor_job(_seed)
    await _refresh(hass, entry)
    state = hass.states.get(RECIPES)
    assert state.state == "2"
    assert state.attributes["reviewable"] == 1


async def test_recipes_counts_the_unmatched_ingredients(hass, setup_entry):
    entry = await setup_entry()
    manager = entry.runtime_data.manager
    await hass.async_add_executor_job(
        lambda: manager.create_recipe(name="Kapsalon", ingredients=[
            {"raw_text": "sumac"}, {"raw_text": "za'atar"}]))
    await _refresh(hass, entry)
    assert hass.states.get(RECIPES).attributes["unmatched_ingredients"] == 2


async def test_missing_ingredients_counts_and_lists_the_products(hass, setup_entry):
    entry = await setup_entry()
    manager = entry.runtime_data.manager
    today = await hass.async_add_executor_job(_today)

    def _seed():
        with manager.db.write() as conn:
            product_id = repo.insert_product(conn, name="Oignon", base_unit="g")
            recipe_id = repo.insert_recipe(conn, name="Gratin", source="manual",
                                           created_at="2026-08-21T10:00:00",
                                           servings=1)
            repo.insert_ingredient(conn, recipe_id=recipe_id, position=1,
                                   raw_text="oignon", product_id=product_id,
                                   amount=500.0, match_state="auto")
        manager.plan_meal(day=today, slot_key="dinner", recipe_id=recipe_id)

    await hass.async_add_executor_job(_seed)
    await _refresh(hass, entry)
    state = hass.states.get(MISSING)
    assert state.state == "1"
    assert [p["product_name"] for p in state.attributes["products"]] == ["Oignon"]
    assert hass.states.get(NEXT).attributes["missing_ingredients"] == 1


async def test_missing_ingredients_ignores_unmatched_and_ignored_lines(hass, setup_entry):
    """On ne réclame pas d'acheter ce qu'on n'a pas su identifier."""
    entry = await setup_entry()
    manager = entry.runtime_data.manager
    today = await hass.async_add_executor_job(_today)

    def _seed():
        with manager.db.write() as conn:
            recipe_id = repo.insert_recipe(conn, name="Gratin", source="manual",
                                           created_at="2026-08-21T10:00:00",
                                           servings=1)
            repo.insert_ingredient(conn, recipe_id=recipe_id, position=1,
                                   raw_text="sumac")
        manager.plan_meal(day=today, slot_key="dinner", recipe_id=recipe_id)

    await hass.async_add_executor_job(_seed)
    await _refresh(hass, entry)
    assert hass.states.get(MISSING).state == "0"


async def test_the_sensors_survive_a_refresh_with_an_empty_database(hass, setup_entry):
    entry = await setup_entry()
    await _refresh(hass, entry)
    assert hass.states.get(RECIPES).state == "0"
    assert hass.states.get(MISSING).state == "0"


async def test_no_event_entity_was_created_for_meal_validation(hass, setup_entry):
    """Décision de la spec § 15.3, épinglée : une automation qui veut réagir a
    déjà `calendar.home_stock_meals` et `sensor.home_stock_next_meal`. Une
    validation est un geste humain qui vient d'avoir lieu sur l'écran, pas un
    fait que rien n'observe."""
    await setup_entry()
    assert hass.states.get("event.home_stock_meal") is None
    assert hass.states.get("event.home_stock_meal_validated") is None


async def test_missing_ingredients_is_a_counter_not_a_todo_list(hass, setup_entry):
    """Une entité `todo` serait déjà la liste de courses, qui est le lot 4."""
    await setup_entry()
    assert hass.states.get("todo.home_stock_missing_ingredients") is None
    assert hass.states.get(MISSING) is not None


def _today():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from custom_components.home_stock.domain.foodday import food_day_of
    return food_day_of(datetime.now(ZoneInfo("UTC")),
                       ZoneInfo("Europe/Paris")).isoformat()


# --- les restes entrent dans ce qui existait déjà --------------------------

async def _cook_a_dish_expiring_soon(hass, entry):
    """Cuisine un plat dont la DLC tombe dans deux jours. Rend son nom."""
    manager = entry.runtime_data.manager
    today = await hass.async_add_executor_job(_today)

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
        meal = manager.plan_meal(day=today, slot_key="dinner",
                                 recipe_id=recipe_id, servings=3.0)
        manager.validate_meal(meal["meal_id"], portions_eaten=0, dry_run=False)

    await hass.async_add_executor_job(_seed)
    return "Reste — Gratin"


async def test_a_leftover_batch_turns_on_the_expirations_binary_sensor(hass, setup_entry):
    """Zéro ligne de code pour ça : c'est le principal intérêt de traiter un
    reste comme n'importe quel autre lot."""
    entry = await setup_entry()
    await _cook_a_dish_expiring_soon(hass, entry)
    await _refresh(hass, entry)
    assert hass.states.get("binary_sensor.home_stock_expirations").state == "on"


async def test_a_leftover_batch_appears_in_the_expirations_todo(hass, setup_entry):
    entry = await setup_entry()
    name = await _cook_a_dish_expiring_soon(hass, entry)
    await _refresh(hass, entry)
    items = await hass.services.async_call(
        "todo", "get_items",
        {"entity_id": "todo.home_stock_expirations"},
        blocking=True, return_response=True)
    summaries = [item["summary"]
                 for item in items["todo.home_stock_expirations"]["items"]]
    assert any(name in summary for summary in summaries)


async def test_a_leftover_batch_fires_the_expiration_event(hass, setup_entry):
    entry = await setup_entry()
    await _cook_a_dish_expiring_soon(hass, entry)
    await _refresh(hass, entry)
    state = hass.states.get("event.home_stock_expiration")
    assert state.attributes["event_type"] == "approaching"
    assert state.attributes["count"] >= 1
