"""The two recipe-line gestures through the integration's real entry points:
the websocket API the panel speaks, and the Home Assistant services.

The scene is Maxime's breakfast (recipe 193) in small: the recipe asks 320 g
of krisprolls with 100 g in stock, plus garlic (none in stock) and water.
Today the meal cannot be marked done (`blocking: ["short"]`); after the trial
— 50 g of krisprolls, garlic and water out — it can.
"""
import pytest
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.service import async_get_all_descriptions

from custom_components.home_stock.const import DOMAIN
from custom_components.home_stock.storage import repositories as repo

NEXT = "sensor.home_stock_next_meal"


@pytest.fixture(autouse=True)
async def _paris(hass):
    await hass.config.async_set_time_zone("Europe/Paris")


def _today():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from custom_components.home_stock.domain.foodday import food_day_of
    return food_day_of(datetime.now(ZoneInfo("UTC")),
                       ZoneInfo("Europe/Paris")).isoformat()


@pytest.fixture
async def kitchen(hass, setup_entry):
    entry = await setup_entry()
    manager = entry.runtime_data.manager
    today = await hass.async_add_executor_job(_today)

    def _seed():
        with manager.db.write() as conn:
            repo.insert_location(conn, name="Placard", kind="pantry")
            krisprolls = repo.insert_product(conn, name="Krisprolls", base_unit="g")
            ail = repo.insert_product(conn, name="Ail", base_unit="g")
            article = repo.insert_article(conn, product_id=krisprolls, label="Krisprolls",
                                          net_quantity=225, kcal_per_base_unit=4.0)
            repo.insert_batch(conn, article_id=article, location_id=1, quantity=100,
                              entered_at="2026-10-01T10:00:00")
            recipe = repo.insert_recipe(conn, name="Petit-déj", source="manual",
                                        created_at="2026-10-01T08:00:00", servings=1)
            ids = {"recipe": recipe}
            for position, (key, raw, product, amount, state) in enumerate((
                    ("krisprolls", "320 g krisprolls", krisprolls, 320.0, "confirmed"),
                    ("ail", "1 gousse d'ail", ail, 5.0, "auto"),
                    ("eau", "eau", None, None, "ignored")), start=1):
                ids[key] = repo.insert_ingredient(
                    conn, recipe_id=recipe, position=position, raw_text=raw,
                    product_id=product, amount=amount, match_state=state)
            conn.execute("INSERT INTO recipe_step (recipe_id, position, title)"
                         " VALUES (?, 1, 'Tartiner')", (recipe,))
        ids["meal"] = manager.plan_meal(day=today, slot_key="breakfast",
                                        recipe_id=recipe)["meal_id"]
        return ids

    ids = await hass.async_add_executor_job(_seed)
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()
    return entry, ids


async def _ask(client, payload):
    await client.send_json_auto_id(payload)
    return await client.receive_json()


async def _call(hass, service, data):
    return await hass.services.async_call(DOMAIN, service, data, blocking=True,
                                          return_response=True)


async def _recipe(client, recipe_id):
    answer = await _ask(client, {"type": "home_stock/recipe/get", "recipe_id": recipe_id})
    assert answer["success"], answer
    return answer["result"]


async def _preview(client, meal_id):
    answer = await _ask(client, {"type": "home_stock/meal/preview", "meal_id": meal_id})
    assert answer["success"], answer
    return answer["result"]


def _without(recipe, ingredient_id, *, amount=None):
    """The recipe as it should read after one gesture on one line."""
    expected = dict(recipe)
    lines = []
    for line in recipe["ingredients"]:
        if line["id"] != ingredient_id:
            lines.append(line)
        elif amount is not None:
            lines.append({**line, "amount": amount})
    expected["ingredients"] = lines
    return expected


def _strip_display(recipe):
    """`display_amount` is derived from `amount`: compared on its own."""
    return {**recipe, "ingredients": [
        {k: v for k, v in line.items() if k != "display_amount"}
        for line in recipe["ingredients"]]}


async def test_websocket_update_changes_one_line_and_answers_it(hass, hass_ws_client, kitchen):
    _, ids = kitchen
    client = await hass_ws_client(hass)
    before = await _recipe(client, ids["recipe"])

    answer = await _ask(client, {"type": "home_stock/recipe/ingredient/update",
                                 "recipe_id": ids["recipe"],
                                 "ingredient_id": ids["krisprolls"], "quantity": 50})

    assert answer["success"], answer
    assert answer["result"]["ingredient"]["id"] == ids["krisprolls"]
    assert answer["result"]["ingredient"]["amount"] == 50.0
    after = await _recipe(client, ids["recipe"])
    assert _strip_display(after) == _strip_display(
        _without(before, ids["krisprolls"], amount=50.0))


async def test_websocket_delete_removes_one_line(hass, hass_ws_client, kitchen):
    _, ids = kitchen
    client = await hass_ws_client(hass)
    before = await _recipe(client, ids["recipe"])

    answer = await _ask(client, {"type": "home_stock/recipe/ingredient/delete",
                                 "ingredient_id": ids["ail"]})

    assert answer["success"], answer
    assert answer["result"]["removed"]["id"] == ids["ail"]
    assert await _recipe(client, ids["recipe"]) == _without(before, ids["ail"])


async def test_the_services_do_the_same_and_answer_it(hass, hass_ws_client, kitchen):
    _, ids = kitchen
    client = await hass_ws_client(hass)
    before = await _recipe(client, ids["recipe"])

    changed = await _call(hass, "set_recipe_ingredient_quantity",
                          {"ingredient_id": ids["krisprolls"], "quantity": 50,
                           "recipe_id": ids["recipe"]})
    removed = await _call(hass, "remove_recipe_ingredient", {"ingredient_id": ids["eau"]})

    assert changed["ingredient"]["amount"] == 50.0
    assert removed["removed"]["raw_text"] == "eau"
    expected = _without(_without(before, ids["krisprolls"], amount=50.0), ids["eau"])
    assert _strip_display(await _recipe(client, ids["recipe"])) == _strip_display(expected)


@pytest.mark.parametrize(("command", "service", "extra"), [
    ("home_stock/recipe/ingredient/update", "set_recipe_ingredient_quantity",
     {"quantity": 50}),
    ("home_stock/recipe/ingredient/delete", "remove_recipe_ingredient", {}),
])
async def test_an_unknown_line_is_refused_in_french_on_both_surfaces(
        hass, hass_ws_client, kitchen, command, service, extra):
    _, ids = kitchen
    client = await hass_ws_client(hass)
    before = await _recipe(client, ids["recipe"])

    answer = await _ask(client, {"type": command, "ingredient_id": 999999, **extra})
    assert answer["success"] is False
    assert answer["error"] == {"code": "not_found",
                               "message": "Ligne d'ingrédient 999999 introuvable."}
    with pytest.raises(ServiceValidationError,
                       match=r"^Ligne d'ingrédient 999999 introuvable\.$"):
        await _call(hass, service, {"ingredient_id": 999999, **extra})
    assert await _recipe(client, ids["recipe"]) == before


@pytest.mark.parametrize(("payload", "code", "message"), [
    ({"quantity": 0}, "invalid_value", "La quantité doit être positive (reçu : 0)."),
    ({"quantity": -1}, "invalid_value", "La quantité doit être positive (reçu : -1)."),
    ({"quantity": "abc"}, "invalid_format", "Un nombre est attendu (reçu : 'abc')."),
    ({"quantity": 100001}, "invalid_value",
     "Quantité trop grande : 100001 (au plus 100000)."),
    ({}, "invalid_format", "Champ obligatoire manquant : quantity."),
    ({"quantity": 50, "ingredient_id": "abc"}, "invalid_format",
     "Un nombre entier est attendu (reçu : 'abc')."),
    ({"quantity": True}, "invalid_format", "Un nombre est attendu (reçu : vrai)."),
    ({"quantity": 50, "foo": 1}, "invalid_format", "Champ inconnu : foo."),
])
async def test_an_impossible_field_is_refused_in_french_on_both_surfaces(
        hass, hass_ws_client, kitchen, payload, code, message):
    """The text is the proof, not only the code: Home Assistant's own schema
    check would refuse these too, in voluptuous' English."""
    _, ids = kitchen
    client = await hass_ws_client(hass)
    before = await _recipe(client, ids["recipe"])
    payload = {"ingredient_id": ids["krisprolls"], **payload}

    answer = await _ask(client, {"type": "home_stock/recipe/ingredient/update", **payload})
    assert answer["success"] is False
    assert answer["error"] == {"code": code, "message": message}
    with pytest.raises(ServiceValidationError) as raised:
        await _call(hass, "set_recipe_ingredient_quantity", payload)
    assert str(raised.value) == message
    assert await _recipe(client, ids["recipe"]) == before


async def test_a_line_can_be_named_by_its_product_on_both_surfaces(
        hass, hass_ws_client, kitchen):
    """The breakfast trial without one id: what `todo.update_item` allows
    (an item's name or its UID), for a line of one recipe."""
    _, ids = kitchen
    client = await hass_ws_client(hass)
    recipe = ids["recipe"]
    before = await _recipe(client, recipe)

    changed = await _ask(client, {"type": "home_stock/recipe/ingredient/update",
                                  "recipe_id": recipe, "product": "krisprolls",
                                  "quantity": 50})
    removed = await _call(hass, "remove_recipe_ingredient",
                          {"recipe_id": recipe, "product": "AIL"})
    water = await _ask(client, {"type": "home_stock/recipe/ingredient/delete",
                                "recipe_id": recipe, "product": "eau"})

    assert changed["result"]["ingredient"]["id"] == ids["krisprolls"]
    assert removed["removed"]["id"] == ids["ail"]
    assert water["result"]["removed"]["id"] == ids["eau"]
    expected = _without(_without(_without(before, ids["krisprolls"], amount=50.0),
                                 ids["ail"]), ids["eau"])
    assert _strip_display(await _recipe(client, recipe)) == _strip_display(expected)


@pytest.mark.parametrize(("command", "service", "extra"), [
    ("home_stock/recipe/ingredient/update", "set_recipe_ingredient_quantity",
     {"quantity": 50}),
    ("home_stock/recipe/ingredient/delete", "remove_recipe_ingredient", {}),
])
@pytest.mark.parametrize(("payload", "code", "message"), [
    ({"recipe_id": "RECIPE", "product": "Beurre"}, "not_found",
     "Aucune ligne « Beurre » dans la recette RECIPE."),
    ({"product": "Ail"}, "invalid_format",
     "Indique la ligne : ingredient_id, ou recipe_id et product."),
    ({"recipe_id": 999999, "product": "Ail"}, "not_found", "Recette 999999 introuvable."),
    ({"recipe_id": "RECIPE", "product": 42}, "invalid_format",
     "Un texte est attendu (reçu : 42)."),
    ({"recipe_id": "RECIPE", "product": "Ail", "foo": 1}, "invalid_format",
     "Champ inconnu : foo."),
])
async def test_a_line_that_cannot_be_named_is_refused_in_french_on_both_surfaces(
        hass, hass_ws_client, kitchen, command, service, extra, payload, code, message):
    _, ids = kitchen
    client = await hass_ws_client(hass)
    before = await _recipe(client, ids["recipe"])
    recipe = str(ids["recipe"])
    payload = {key: ids["recipe"] if value == "RECIPE" else value
               for key, value in {**payload, **extra}.items()}
    message = message.replace("RECIPE", recipe)

    answer = await _ask(client, {"type": command, **payload})
    assert answer["success"] is False
    assert answer["error"] == {"code": code, "message": message}
    with pytest.raises(ServiceValidationError) as raised:
        await _call(hass, service, payload)
    assert str(raised.value) == message
    assert await _recipe(client, ids["recipe"]) == before


async def test_the_lines_of_a_recipe_can_be_read_with_their_ids(hass, kitchen):
    """What a script or an automation needs before either gesture."""
    _, ids = kitchen
    answer = await _call(hass, "get_recipe_ingredients", {"recipe_id": ids["recipe"]})
    assert answer == {"recipe_id": ids["recipe"], "ingredients": [
        {"ingredient_id": ids["krisprolls"], "position": 1, "product_id": answer[
            "ingredients"][0]["product_id"], "product": "Krisprolls", "amount": 320.0,
         "unit": "g", "raw_text": "320 g krisprolls", "match_state": "confirmed"},
        {"ingredient_id": ids["ail"], "position": 2, "product_id": answer[
            "ingredients"][1]["product_id"], "product": "Ail", "amount": 5.0,
         "unit": "g", "raw_text": "1 gousse d'ail", "match_state": "auto"},
        {"ingredient_id": ids["eau"], "position": 3, "product_id": None,
         "product": None, "amount": None, "unit": None, "raw_text": "eau",
         "match_state": "ignored"},
    ]}
    with pytest.raises(ServiceValidationError, match=r"^Recette 999999 introuvable\.$"):
        await _call(hass, "get_recipe_ingredients", {"recipe_id": 999999})


async def test_the_breakfast_trial_recomputes_preview_sensor_and_lets_it_be_done(
        hass, hass_ws_client, kitchen):
    """Recipe 193 in small: 320 g → 50 g, garlic and water out, then « terminé »."""
    _, ids = kitchen
    client = await hass_ws_client(hass)
    preview = await _preview(client, ids["meal"])
    assert preview["blocking"] == ["short"]
    assert preview["dish"]["kcal"] == 400.0  # only the 100 g in stock
    assert hass.states.get(NEXT).attributes["missing_ingredients"] == 2

    await _ask(client, {"type": "home_stock/recipe/ingredient/update",
                        "ingredient_id": ids["krisprolls"], "quantity": 50})
    await hass.async_block_till_done()
    preview = await _preview(client, ids["meal"])
    assert [(line["needed"], line["status"]) for line in preview["lines"]
            if line["ingredient_id"] == ids["krisprolls"]] == [(50.0, "ok")]
    assert preview["dish"]["kcal"] == 200.0  # 50 g at 4 kcal/g
    assert hass.states.get(NEXT).attributes["missing_ingredients"] == 1  # garlic

    await _call(hass, "remove_recipe_ingredient", {"ingredient_id": ids["ail"]})
    await _call(hass, "remove_recipe_ingredient", {"ingredient_id": ids["eau"]})
    await hass.async_block_till_done()
    assert hass.states.get(NEXT).attributes["missing_ingredients"] == 0
    preview = await _preview(client, ids["meal"])
    assert [line["ingredient_id"] for line in preview["lines"]] == [ids["krisprolls"]]
    assert preview["blocking"] == []

    done = await _ask(client, {"type": "home_stock/meal/validate", "meal_id": ids["meal"],
                               "portions_eaten": 1})
    assert done["success"], done


async def test_the_services_are_described_in_french_and_none_is_lost(hass, kitchen):
    described = (await async_get_all_descriptions(hass))[DOMAIN]
    assert described["set_recipe_ingredient_quantity"]["name"] == (
        "Changer la quantité d'un ingrédient de recette")
    assert set(described["set_recipe_ingredient_quantity"]["fields"]) == {
        "ingredient_id", "quantity", "recipe_id", "product"}
    assert described["remove_recipe_ingredient"]["name"] == (
        "Retirer un ingrédient de recette")
    # Its fields are YAML aliases of the first gesture's: the real loader
    # must resolve them, descriptions included.
    remove_fields = described["remove_recipe_ingredient"]["fields"]
    assert set(remove_fields) == {"ingredient_id", "recipe_id", "product"}
    assert remove_fields["product"]["name"] == "Produit"
    assert remove_fields["product"]["description"].startswith("À la place de l'identifiant")
    assert described["set_recipe_ingredient_quantity"]["response"] == {"optional": True}
    assert described["get_recipe_ingredients"]["name"] == "Lister les ingrédients d'une recette"
    assert set(described["get_recipe_ingredients"]["fields"]) == {"recipe_id"}
    assert described["get_recipe_ingredients"]["response"] == {"optional": False}
    assert described["add_recipe_ingredient"]["name"] == (
        "Remettre un ingrédient dans une recette")
    assert set(described["add_recipe_ingredient"]["fields"]) == {
        "recipe_id", "product", "quantity", "raw_text", "position"}
    # A line put back is not the line removed: the description says what is lost.
    lost = described["add_recipe_ingredient"]["description"]
    for word in ("identifiant", "conditionnement", "mesure", "groupe", "facultative",
                 "rapprochement"):
        assert word in lost, word
    # One malformed entry makes the loader drop the WHOLE file: every
    # service registered must still read a non-empty description.
    registered = hass.services.async_services_for_domain(DOMAIN)
    assert set(registered) <= set(described)
    for service in registered:
        assert described[service].get("description"), service


async def test_the_changelog_script_example_runs_as_written(hass, hass_ws_client, kitchen):
    """The YAML of CHANGELOG.md, chaining the three services through
    `response_variable`, run by Home Assistant's own script integration."""
    import re
    from pathlib import Path

    import yaml
    from homeassistant.setup import async_setup_component

    _, ids = kitchen
    text = (Path(__file__).parent.parent / "CHANGELOG.md").read_text(encoding="utf-8")
    example = re.search(r"```yaml\n(.+?)```", text, re.S).group(1)
    scripts = yaml.safe_load(
        example.replace("recipe_id: 193", f"recipe_id: {ids['recipe']}"))
    assert await async_setup_component(hass, "persistent_notification", {})
    assert await async_setup_component(hass, "script", {"script": scripts})

    await hass.services.async_call("script", "petit_dej_193", blocking=True)
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)
    lines = (await _recipe(client, ids["recipe"]))["ingredients"]
    assert [(line["id"], line["amount"]) for line in lines] == [(ids["krisprolls"], 50.0)]
    notes = await _ask(client, {"type": "persistent_notification/get"})
    assert [note["message"] for note in notes["result"]] == [
        "Krisprolls : 50.0 g ; retiré : eau."]


def _shape(recipe):
    """A recipe as its lines read, whatever their ids: what putting back restores."""
    return ({k: v for k, v in recipe.items() if k != "ingredients"},
            [(line["position"], line["product_id"], line["amount"], line["raw_text"])
             for line in recipe["ingredients"]])


async def test_a_removed_line_can_be_put_back_on_both_surfaces(hass, hass_ws_client, kitchen):
    """Maxime, 10/10: « Remettre une ligne avant que ça sorte »."""
    _, ids = kitchen
    client = await hass_ws_client(hass)
    recipe = ids["recipe"]
    before = await _recipe(client, recipe)

    gone = (await _call(hass, "remove_recipe_ingredient",
                        {"recipe_id": recipe, "product": "Ail"}))["removed"]
    water = (await _ask(client, {"type": "home_stock/recipe/ingredient/delete",
                                 "ingredient_id": ids["eau"]}))["result"]["removed"]
    back = await _ask(client, {"type": "home_stock/recipe/ingredient/add",
                               "recipe_id": recipe, "product": "ail", "quantity": gone["amount"],
                               "raw_text": gone["raw_text"], "position": gone["position"]})
    again = await _call(hass, "add_recipe_ingredient",
                        {"recipe_id": recipe, "raw_text": water["raw_text"],
                         "position": water["position"]})

    assert back["success"], back
    assert back["result"]["ingredient"]["match_state"] == "confirmed"
    assert again["ingredient"]["match_state"] == "ignored"
    assert _shape(await _recipe(client, recipe)) == _shape(before)
    # Without a position the line goes last, after the others.
    last = await _call(hass, "add_recipe_ingredient",
                       {"recipe_id": recipe, "product": "Krisprolls", "quantity": 10})
    assert last["ingredient"]["position"] == 4


@pytest.mark.parametrize(("payload", "code", "message"), [
    ({"recipe_id": "R", "product": "Beurre"}, "not_found", "Produit « Beurre » introuvable."),
    ({"recipe_id": "R"}, "invalid_format",
     "Indique le produit de la ligne, ou son texte (raw_text)."),
    ({"recipe_id": "R", "raw_text": "sel", "quantity": 2}, "invalid_format",
     "Une quantité demande un produit : une ligne sans produit n'est qu'un texte."),
    ({"recipe_id": "R", "product": "Ail", "quantity": 0}, "invalid_value",
     "La quantité doit être positive (reçu : 0)."),
    ({"recipe_id": "R", "product": "Ail", "position": 1}, "invalid_value",
     "La position 1 est déjà prise dans la recette R."),
    ({"recipe_id": "R", "product": "Ail", "position": 0}, "invalid_format",
     "Une position commence à 1."),
    ({"recipe_id": 999999, "product": "Ail"}, "not_found", "Recette 999999 introuvable."),
    ({"recipe_id": "R", "product": "Ail", "foo": 1}, "invalid_format", "Champ inconnu : foo."),
    ({"product": "Ail"}, "invalid_format", "Champ obligatoire manquant : recipe_id."),
])
async def test_a_line_that_cannot_be_put_back_is_refused_in_french_on_both_surfaces(
        hass, hass_ws_client, kitchen, payload, code, message):
    _, ids = kitchen
    client = await hass_ws_client(hass)
    before = await _recipe(client, ids["recipe"])
    payload = {key: ids["recipe"] if value == "R" else value for key, value in payload.items()}
    message = message.replace("recette R", f"recette {ids['recipe']}")

    answer = await _ask(client, {"type": "home_stock/recipe/ingredient/add", **payload})
    assert answer["success"] is False
    assert answer["error"] == {"code": code, "message": message}
    with pytest.raises(ServiceValidationError) as raised:
        await _call(hass, "add_recipe_ingredient", payload)
    assert str(raised.value) == message
    assert await _recipe(client, ids["recipe"]) == before


def test_the_changelog_names_what_a_line_put_back_loses():
    """A put-back line is not the removed one: the 1.7.0 entry says so."""
    from pathlib import Path

    text = (Path(__file__).parent.parent / "CHANGELOG.md").read_text(encoding="utf-8")
    entry = text.split("## [1.7.0]", 1)[1].split("\n## [", 1)[0]
    limits = entry.split("### Limites connues", 1)[1]
    for field in ("ingredient_id", "conditionnement", "mesure", "group_name",
                  "optional", "external_ref", "match_score"):
        assert field in limits, field
