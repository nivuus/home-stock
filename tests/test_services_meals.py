"""Les cinq services du lot 3, et la parité avec le websocket.

La règle qui gouverne ce fichier : aucune des deux surfaces n'a le droit d'être
la plus faible. Ce que le websocket refuse, le service le refuse aussi — un
appel de service part d'une automation ou du vocal, et il est tout aussi
capable d'écrire quatre parts sur trois dans un journal en ajout seul.
"""
import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import service as service_helper

from custom_components.home_stock.const import DOMAIN
from custom_components.home_stock.recipes.source import SourceHit
from custom_components.home_stock.storage import repositories as repo

CARD = {
    "idMeal": "52772", "strMeal": "Teriyaki Chicken Casserole",
    "strMealThumb": "https://img/x.jpg", "strSource": "https://src/x",
    "strInstructions": "Preheat oven.",
    "strIngredient1": "soy sauce", "strMeasure1": "3/4 cup",
}


class _Source:
    def __init__(self, *, hits=(), card=None):
        self._hits = list(hits)
        self._card = card

    async def search(self, query):
        return list(self._hits)

    async def by_ingredient(self, ingredient):
        return list(self._hits)

    async def lookup(self, source_ref):
        return self._card


async def _kitchen(hass, entry, *, amount=300.0, available=900.0):
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


async def _plan(hass, entry, recipe_id, servings=3.0):
    manager = entry.runtime_data.manager
    posted = await hass.async_add_executor_job(
        lambda: manager.plan_meal(day="2026-08-21", slot_key="dinner",
                                  recipe_id=recipe_id, servings=servings))
    return posted["meal_id"]


async def _count(hass, entry, table):
    manager = entry.runtime_data.manager
    return await hass.async_add_executor_job(
        lambda: manager.db.read().execute(
            f"SELECT COUNT(*) c FROM {table}").fetchone()["c"])


# --- les cinq services ------------------------------------------------------

async def test_plan_meal_service_creates_the_meal(hass, setup_entry):
    entry = await setup_entry()
    await hass.services.async_call(
        DOMAIN, "plan_meal",
        {"day": "2026-08-21", "slot_key": "dinner", "note": "Restaurant"},
        blocking=True)
    manager = entry.runtime_data.manager
    meals = await hass.async_add_executor_job(
        manager.list_meals, "2026-08-21", "2026-08-21")
    assert [m["note"] for m in meals] == ["Restaurant"]


async def test_validate_meal_is_a_dry_run_by_default_and_writes_nothing(hass,
                                                                        setup_entry):
    """Un service qui décrémente un stock ne doit pas le faire au premier appel
    exploratoire depuis les Outils de développement."""
    entry = await setup_entry()
    recipe_id = await _kitchen(hass, entry)
    meal_id = await _plan(hass, entry, recipe_id)

    answer = await hass.services.async_call(
        DOMAIN, "validate_meal", {"meal_id": meal_id, "portions_eaten": 1},
        blocking=True, return_response=True)

    assert answer["lines"]
    assert "movement_ids" not in answer
    assert await _count(hass, entry, "movement") == 0


async def test_validate_meal_writes_when_dry_run_is_false(hass, setup_entry):
    entry = await setup_entry()
    recipe_id = await _kitchen(hass, entry)
    meal_id = await _plan(hass, entry, recipe_id)

    answer = await hass.services.async_call(
        DOMAIN, "validate_meal",
        {"meal_id": meal_id, "portions_eaten": 1, "dry_run": False},
        blocking=True, return_response=True)

    assert len(answer["movement_ids"]) == 3
    assert await _count(hass, entry, "movement") == 3


async def test_import_recipe_by_source_ref(hass, setup_entry):
    entry = await setup_entry()
    entry.runtime_data.recipe_source = _Source(card=CARD)
    answer = await hass.services.async_call(
        DOMAIN, "import_recipe", {"source_ref": "52772"},
        blocking=True, return_response=True)
    assert answer["imported"] is True
    assert answer["recipe_id"]
    assert await _count(hass, entry, "recipe") == 1


async def test_import_recipe_by_search_takes_the_first_hit(hass, setup_entry):
    entry = await setup_entry()
    entry.runtime_data.recipe_source = _Source(
        hits=[SourceHit(source_ref="52772", name="Teriyaki", image_url=None,
                        category=None, area=None)],
        card=CARD)
    answer = await hass.services.async_call(
        DOMAIN, "import_recipe", {"query": "teriyaki"},
        blocking=True, return_response=True)
    assert answer["imported"] is True


async def test_import_recipe_with_the_source_down_reports_it_without_raising(
        hass, setup_entry):
    """Rien ici n'a le droit de retarder un dîner, ni de lever."""
    entry = await setup_entry()
    entry.runtime_data.recipe_source = _Source(hits=[], card=None)
    answer = await hass.services.async_call(
        DOMAIN, "import_recipe", {"query": "introuvable"},
        blocking=True, return_response=True)
    assert answer["imported"] is False
    assert answer["message"]
    assert await _count(hass, entry, "recipe") == 0


async def test_adapt_recipe_picks_up_a_recipe_imported_without_an_agent(hass,
                                                                        setup_entry):
    entry = await setup_entry()
    entry.runtime_data.recipe_source = _Source(card=CARD)
    imported = await hass.services.async_call(
        DOMAIN, "import_recipe", {"source_ref": "52772"},
        blocking=True, return_response=True)

    await hass.services.async_call(
        DOMAIN, "adapt_recipe", {"recipe_id": imported["recipe_id"]}, blocking=True)
    assert await _count(hass, entry, "recipe") == 1


async def test_adapt_recipe_refuses_a_recipe_that_was_never_imported(hass,
                                                                     setup_entry):
    entry = await setup_entry()
    manager = entry.runtime_data.manager
    recipe_id = await hass.async_add_executor_job(
        lambda: manager.create_recipe(name="Faite à la main"))
    with pytest.raises(HomeAssistantError, match="importée"):
        await hass.services.async_call(
            DOMAIN, "adapt_recipe", {"recipe_id": recipe_id}, blocking=True)


async def test_query_meals_returns_the_range_and_writes_nothing(hass, setup_entry):
    entry = await setup_entry()
    await hass.services.async_call(
        DOMAIN, "plan_meal",
        {"day": "2026-08-21", "slot_key": "dinner", "note": "Restaurant"},
        blocking=True)
    before = await _count(hass, entry, "movement")
    answer = await hass.services.async_call(
        DOMAIN, "query_meals", {"start": "2026-08-21", "end": "2026-08-21"},
        blocking=True, return_response=True)
    assert [m["note"] for m in answer["meals"]] == ["Restaurant"]
    assert await _count(hass, entry, "movement") == before


# --- la parité, surface par surface — le cœur de la tâche ------------------

@pytest.mark.parametrize("payload", [
    {"portions_eaten": -1},
    {"portions_eaten": "une"},
    {"portions_eaten": 1, "parts_total": 2, "parts_mine": 3},
    {"portions_eaten": 1, "parts_total": 25, "parts_mine": 1},
    {"portions_eaten": 1, "parts_total": 1.5, "parts_mine": 1},
    {"portions_eaten": 4},                 # plus de parts que le plat n'en fait
])
async def test_validate_meal_refuses_exactly_what_the_websocket_refuses(
        hass, setup_entry, payload):
    entry = await setup_entry()
    recipe_id = await _kitchen(hass, entry)
    meal_id = await _plan(hass, entry, recipe_id)
    with pytest.raises(Exception):
        await hass.services.async_call(
            DOMAIN, "validate_meal",
            {"meal_id": meal_id, "dry_run": False, **payload},
            blocking=True, return_response=True)
    assert await _count(hass, entry, "movement") == 0


@pytest.mark.parametrize("payload", [
    {"day": "2026-8-1", "slot_key": "dinner", "note": "x"},
    {"day": "20260801", "slot_key": "dinner", "note": "x"},
    {"day": "2026-W01-1", "slot_key": "dinner", "note": "x"},
    {"day": "2026-08-21", "slot_key": "brunch", "note": "x"},
    {"day": "2026-08-21", "slot_key": "dinner", "note": "x", "servings": 0},
    {"day": "2026-08-21", "slot_key": "dinner", "note": "x", "servings": -1},
    {"day": "2026-08-21", "slot_key": "dinner"},          # aucune nature
    {"day": "2026-08-21", "slot_key": "dinner", "recipe_id": 1, "note": "x"},
])
async def test_plan_meal_refuses_exactly_what_the_websocket_refuses(
        hass, setup_entry, payload):
    entry = await setup_entry()
    with pytest.raises(Exception):
        await hass.services.async_call(DOMAIN, "plan_meal", payload, blocking=True)
    assert await _count(hass, entry, "meal") == 0


@pytest.mark.parametrize("bounds", [
    {"start": "hier", "end": "2026-08-21"},
    {"start": "2026-08-21", "end": "20260822"},
])
async def test_query_meals_validates_its_bounds_like_the_websocket(hass, setup_entry,
                                                                   bounds):
    await setup_entry()
    with pytest.raises(Exception):
        await hass.services.async_call(DOMAIN, "query_meals", bounds,
                                       blocking=True, return_response=True)


# --- les libellés -----------------------------------------------------------

async def test_every_new_service_has_a_french_name_and_description(hass, setup_entry):
    await setup_entry()
    descriptions = await service_helper.async_get_all_descriptions(hass)
    for name in ("plan_meal", "validate_meal", "import_recipe", "adapt_recipe",
                 "query_meals"):
        described = descriptions[DOMAIN][name]
        assert described["name"], name
        assert described["description"], name
        for field, spec in described.get("fields", {}).items():
            assert spec.get("name"), f"{name}.{field}"
            assert "selector" in spec, f"{name}.{field}"
