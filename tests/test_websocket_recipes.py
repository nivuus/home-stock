"""Les commandes recettes, vues du panneau."""

from custom_components.home_stock.recipes.source import SourceHit
from custom_components.home_stock.storage import repositories as repo


class _Source:
    """Une source scriptée. `None` partout = source injoignable."""

    def __init__(self, *, hits=(), card=None):
        self._hits = list(hits)
        self._card = card
        self.calls = 0

    async def search(self, query):
        self.calls += 1
        return list(self._hits)

    async def by_ingredient(self, ingredient):
        self.calls += 1
        return list(self._hits)

    async def lookup(self, source_ref):
        self.calls += 1
        return self._card


CARD = {
    "idMeal": "52772", "strMeal": "Teriyaki Chicken Casserole",
    "strMealThumb": "https://img/x.jpg", "strSource": "https://src/x",
    "strInstructions": "Preheat oven.",
    "strIngredient1": "soy sauce", "strMeasure1": "3/4 cup",
}


async def _recipe(hass, entry, **kwargs):
    manager = entry.runtime_data.manager
    return await hass.async_add_executor_job(
        lambda: manager.create_recipe(**kwargs))


async def _ask(client, payload):
    await client.send_json_auto_id(payload)
    return await client.receive_json()


# --- lire -------------------------------------------------------------------

async def test_recipes_list_returns_the_unmatched_count(hass, hass_ws_client,
                                                        setup_entry):
    entry = await setup_entry()
    await _recipe(hass, entry, name="Kapsalon",
                  ingredients=[{"raw_text": "sumac"}, {"raw_text": "za'atar"}])
    client = await hass_ws_client(hass)
    answer = await _ask(client, {"type": "home_stock/recipes/list"})
    assert answer["success"]
    [recipe] = answer["result"]["recipes"]
    assert recipe["unmatched_count"] == 2


async def test_recipes_list_filters_on_search_and_on_review(hass, hass_ws_client,
                                                            setup_entry):
    entry = await setup_entry()
    await _recipe(hass, entry, name="Kapsalon", needs_review=1)
    await _recipe(hass, entry, name="Tartiflette")
    client = await hass_ws_client(hass)

    answer = await _ask(client, {"type": "home_stock/recipes/list",
                                 "only_reviewable": True})
    assert [r["name"] for r in answer["result"]["recipes"]] == ["Kapsalon"]

    answer = await _ask(client, {"type": "home_stock/recipes/list",
                                 "search": "tarti"})
    assert [r["name"] for r in answer["result"]["recipes"]] == ["Tartiflette"]


async def test_recipe_get_returns_steps_bullets_and_candidates(hass, hass_ws_client,
                                                               setup_entry):
    entry = await setup_entry()
    manager = entry.runtime_data.manager

    def _seed():
        with manager.db.write() as conn:
            repo.insert_product(conn, name="Crème fraîche", base_unit="ml")
        return manager.create_recipe(
            name="Kapsalon",
            steps=[{"title": "Cuire", "instructions": [
                {"text": "Chauffer", "timer_label": "Cuisson",
                 "timer_seconds": 600}]}],
            ingredients=[{"raw_text": "coriandre fraîche"}])

    recipe_id = await hass.async_add_executor_job(_seed)
    client = await hass_ws_client(hass)
    answer = await _ask(client, {"type": "home_stock/recipe/get",
                                 "recipe_id": recipe_id})
    assert answer["success"]
    result = answer["result"]
    assert result["recipe"]["name"] == "Kapsalon"
    assert result["steps"][0]["instructions"][0]["timer_seconds"] == 600
    assert [c["name"] for c in result["ingredients"][0]["candidates"]] == [
        "Crème fraîche"]


async def test_recipe_get_on_an_unknown_id_answers_an_error(hass, hass_ws_client,
                                                            setup_entry):
    await setup_entry()
    client = await hass_ws_client(hass)
    answer = await _ask(client, {"type": "home_stock/recipe/get", "recipe_id": 999})
    assert not answer["success"]


# --- écrire -----------------------------------------------------------------

async def test_recipe_create_then_update_then_delete(hass, hass_ws_client,
                                                     setup_entry):
    await setup_entry()
    client = await hass_ws_client(hass)

    answer = await _ask(client, {"type": "home_stock/recipe/create",
                                 "name": "Kapsalon", "servings": 4})
    assert answer["success"]
    recipe_id = answer["result"]["recipe_id"]

    answer = await _ask(client, {"type": "home_stock/recipe/update",
                                 "recipe_id": recipe_id,
                                 "fields": {"name": "Kapsalon revisité"}})
    assert answer["success"]

    answer = await _ask(client, {"type": "home_stock/recipe/delete",
                                 "recipe_id": recipe_id})
    assert answer["success"]

    answer = await _ask(client, {"type": "home_stock/recipes/list"})
    assert answer["result"]["recipes"] == []


async def test_recipe_delete_is_refused_when_a_done_meal_references_it(
        hass, hass_ws_client, setup_entry):
    entry = await setup_entry()
    manager = entry.runtime_data.manager
    recipe_id = await _recipe(hass, entry, name="Kapsalon")

    def _done():
        with manager.db.write() as conn:
            repo.insert_meal(conn, uid="u1", day="2026-08-20", slot_key="dinner",
                             created_at="2026-08-20T18:00:00",
                             recipe_id=recipe_id, state="done")

    await hass.async_add_executor_job(_done)
    client = await hass_ws_client(hass)
    answer = await _ask(client, {"type": "home_stock/recipe/delete",
                                 "recipe_id": recipe_id})
    assert not answer["success"]


async def test_ingredient_match_confirms_and_creates_the_alias(hass, hass_ws_client,
                                                               setup_entry):
    entry = await setup_entry()
    manager = entry.runtime_data.manager

    def _seed():
        with manager.db.write() as conn:
            product_id = repo.insert_product(conn, name="Coriandre", base_unit="g")
        recipe_id = manager.create_recipe(
            name="R", ingredients=[{"raw_text": "coriandre fraîche"}])
        line = repo.list_ingredients(manager.db.read(), recipe_id)[0]
        return product_id, line["id"]

    product_id, ingredient_id = await hass.async_add_executor_job(_seed)
    client = await hass_ws_client(hass)
    answer = await _ask(client, {
        "type": "home_stock/recipe/ingredient/match",
        "ingredient_id": ingredient_id, "product_id": product_id,
        "state": "confirmed", "create_alias": True})
    assert answer["success"]
    assert answer["result"]["ingredient"]["match_state"] == "confirmed"

    alias = await hass.async_add_executor_job(
        lambda: repo.find_alias(manager.db.read(), "coriandre fraiche"))
    assert alias["product_id"] == product_id


async def test_ingredient_match_refuses_auto_without_a_product(hass, hass_ws_client,
                                                               setup_entry):
    entry = await setup_entry()
    manager = entry.runtime_data.manager
    recipe_id = await _recipe(hass, entry, name="R",
                              ingredients=[{"raw_text": "sel"}])
    ingredient_id = (await hass.async_add_executor_job(
        lambda: repo.list_ingredients(manager.db.read(), recipe_id)))[0]["id"]
    client = await hass_ws_client(hass)
    answer = await _ask(client, {
        "type": "home_stock/recipe/ingredient/match",
        "ingredient_id": ingredient_id, "state": "auto"})
    assert not answer["success"]


async def test_an_unknown_match_state_is_refused_by_the_schema(hass, hass_ws_client,
                                                               setup_entry):
    await setup_entry()
    client = await hass_ws_client(hass)
    answer = await _ask(client, {
        "type": "home_stock/recipe/ingredient/match",
        "ingredient_id": 1, "state": "peut-être"})
    assert not answer["success"]


# --- la source en ligne -----------------------------------------------------

async def test_search_external_writes_absolutely_nothing(hass, hass_ws_client,
                                                         setup_entry):
    entry = await setup_entry()
    entry.runtime_data.recipe_source = _Source(hits=[
        SourceHit(source_ref="52772", name="Teriyaki", image_url=None,
                  category="Chicken", area="Japanese")])
    manager = entry.runtime_data.manager
    before = await hass.async_add_executor_job(
        lambda: manager.db.read().execute(
            "SELECT COUNT(*) c FROM recipe").fetchone()["c"])

    client = await hass_ws_client(hass)
    answer = await _ask(client, {"type": "home_stock/recipe/search_external",
                                 "query": "teriyaki"})
    assert answer["success"]
    assert [h["source_ref"] for h in answer["result"]["hits"]] == ["52772"]

    after = await hass.async_add_executor_job(
        lambda: manager.db.read().execute(
            "SELECT COUNT(*) c FROM recipe").fetchone()["c"])
    assert after == before == 0


async def test_search_external_with_the_source_down_answers_empty_not_an_error(
        hass, hass_ws_client, setup_entry):
    """Recherche vide et message explicite. Rien ne retarde un dîner."""
    entry = await setup_entry()
    entry.runtime_data.recipe_source = _Source(hits=[])
    client = await hass_ws_client(hass)
    answer = await _ask(client, {"type": "home_stock/recipe/search_external",
                                 "query": "teriyaki"})
    assert answer["success"]
    assert answer["result"]["hits"] == []


async def test_search_external_by_ingredient_uses_the_filter_route(
        hass, hass_ws_client, setup_entry):
    entry = await setup_entry()
    source = _Source(hits=[
        SourceHit(source_ref="1", name="Poulet", image_url=None,
                  category=None, area=None)])
    entry.runtime_data.recipe_source = source
    client = await hass_ws_client(hass)
    answer = await _ask(client, {"type": "home_stock/recipe/search_external",
                                 "ingredient": "chicken"})
    assert answer["success"] and source.calls == 1


async def test_import_external_creates_the_recipe_without_an_agent(
        hass, hass_ws_client, setup_entry):
    """Aucun agent configuré : la recette existe quand même, en anglais et
    marquée à relire."""
    entry = await setup_entry()
    entry.runtime_data.recipe_source = _Source(card=CARD)
    client = await hass_ws_client(hass)
    answer = await _ask(client, {"type": "home_stock/recipe/import_external",
                                 "source_ref": "52772"})
    assert answer["success"]
    assert answer["result"]["adapted"] is False

    manager = entry.runtime_data.manager
    recipe = await hass.async_add_executor_job(
        lambda: repo.get_recipe(manager.db.read(), answer["result"]["recipe_id"]))
    assert recipe["language"] == "en" and recipe["needs_review"] == 1


async def test_import_external_of_an_unknown_ref_answers_not_found(
        hass, hass_ws_client, setup_entry):
    entry = await setup_entry()
    entry.runtime_data.recipe_source = _Source(card=None)
    client = await hass_ws_client(hass)
    answer = await _ask(client, {"type": "home_stock/recipe/import_external",
                                 "source_ref": "00000"})
    assert not answer["success"]
    assert answer["error"]["code"] == "not_found"


async def test_import_external_twice_does_not_duplicate(hass, hass_ws_client,
                                                        setup_entry):
    entry = await setup_entry()
    entry.runtime_data.recipe_source = _Source(card=CARD)
    client = await hass_ws_client(hass)
    first = await _ask(client, {"type": "home_stock/recipe/import_external",
                                "source_ref": "52772"})
    second = await _ask(client, {"type": "home_stock/recipe/import_external",
                                 "source_ref": "52772"})
    assert first["result"]["recipe_id"] == second["result"]["recipe_id"]

    manager = entry.runtime_data.manager
    count = await hass.async_add_executor_job(
        lambda: manager.db.read().execute(
            "SELECT COUNT(*) c FROM recipe").fetchone()["c"])
    assert count == 1
