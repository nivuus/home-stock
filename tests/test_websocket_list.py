"""La liste, le magasin et la correction, pilotés comme le panneau les pilote."""
import pytest
from homeassistant.core import HomeAssistant

from custom_components.home_stock.storage import repositories as repo


async def _send(client, id_, type_, **payload):
    await client.send_json({"id": id_, "type": type_, **payload})
    return await client.receive_json()


async def _seed(hass, entry):
    """Deux produits sous leur seuil, dans deux rayons différents."""
    manager = entry.runtime_data.manager

    def _write() -> dict:
        with manager.db.write() as conn:
            aisles = {row["name"]: row["id"] for row in repo.list_aisles(conn)}
            milk = repo.insert_product(conn, name="Lait", base_unit="ml",
                                       min_quantity=2000,
                                       aisle_id=aisles["Crémerie"])
            pasta = repo.insert_product(conn, name="Pâtes", base_unit="g",
                                        min_quantity=500,
                                        aisle_id=aisles["Épicerie salée"])
            for product_id in (milk, pasta):
                repo.insert_article(conn, product_id=product_id, is_generic=1)
            return {"milk": milk, "pasta": pasta, "aisles": aisles}

    return await hass.async_add_executor_job(_write)


# --- la liste ---------------------------------------------------------------

async def test_list_items_is_sorted_for_the_given_store(hass: HomeAssistant,
                                                        setup_entry, hass_ws_client):
    entry = await setup_entry(with_article=True)
    ids = await _seed(hass, entry)
    manager = entry.runtime_data.manager

    def _route() -> int:
        with manager.db.write() as conn:
            store_id = repo.upsert_store(conn, name="Leclerc")
            repo.set_store_aisle(conn, store_id=store_id,
                                 aisle_id=ids["aisles"]["Épicerie salée"],
                                 position=1, source="manual")
            repo.set_store_aisle(conn, store_id=store_id,
                                 aisle_id=ids["aisles"]["Crémerie"],
                                 position=2, source="manual")
            return store_id

    store_id = await hass.async_add_executor_job(_route)
    client = await hass_ws_client(hass)
    await _send(client, 1, "home_stock/list/refresh")

    answer = await _send(client, 2, "home_stock/list/items", store_id=store_id)

    names = [row["product_name"] for row in answer["result"]["items"]]
    assert names == ["Pâtes", "Lait"]
    assert answer["result"]["store_id"] == store_id


async def test_list_items_falls_back_to_the_open_session_store(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    """Puis au DERNIER magasin utilisé, puis à l'ordre par défaut. Les
    trois niveaux, dans cet ordre."""
    entry = await setup_entry(with_article=True)
    await _seed(hass, entry)
    client = await hass_ws_client(hass)
    await _send(client, 1, "home_stock/list/refresh")

    # 3. Aucun magasin nulle part : l'ordre par défaut.
    default = await _send(client, 2, "home_stock/list/items")
    assert default["result"]["store_id"] is None

    # 2. Un magasin déjà visité, aucune session ouverte.
    await _send(client, 3, "home_stock/session/start", store="Leclerc")
    await _send(client, 4, "home_stock/session/close")
    last = await _send(client, 5, "home_stock/list/items")
    assert last["result"]["store_id"] is not None

    # 1. Une session ouverte gagne sur le dernier utilisé.
    await _send(client, 6, "home_stock/session/start", store="Lidl")
    current = await _send(client, 7, "home_stock/list/items")
    assert current["result"]["store_name"] == "Lidl"


async def test_adding_a_free_text_line_works_without_a_product(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    await setup_entry(with_article=True)
    client = await hass_ws_client(hass)
    answer = await _send(client, 1, "home_stock/list/add",
                         free_text="Piles télécommande salon")
    assert answer["success"] is True
    assert answer["result"]["items"][0]["free_text"] == "Piles télécommande salon"


async def test_adding_a_line_that_names_nothing_is_refused_in_french(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    await setup_entry(with_article=True)
    client = await hass_ws_client(hass)
    refused = await _send(client, 1, "home_stock/list/add")
    assert refused["success"] is False
    assert "produit" in refused["error"]["message"].lower()


async def test_check_and_uncheck_are_symmetric(hass: HomeAssistant, setup_entry,
                                               hass_ws_client):
    await setup_entry(with_article=True)
    client = await hass_ws_client(hass)
    added = await _send(client, 1, "home_stock/list/add", free_text="Pain")
    item_id = added["result"]["items"][0]["id"]

    checked = await _send(client, 2, "home_stock/list/check", item_id=item_id)
    assert checked["result"]["items"][0]["checked_at"] is not None
    unchecked = await _send(client, 3, "home_stock/list/uncheck", item_id=item_id)
    assert unchecked["result"]["items"][0]["checked_at"] is None


async def test_checking_without_an_open_session_is_allowed(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    """On coche une liste chez soi aussi."""
    await setup_entry(with_article=True)
    client = await hass_ws_client(hass)
    added = await _send(client, 1, "home_stock/list/add", free_text="Pain")
    answer = await _send(client, 2, "home_stock/list/check",
                         item_id=added["result"]["items"][0]["id"])
    assert answer["success"] is True


async def test_remove_is_a_timestamp(hass: HomeAssistant, setup_entry,
                                     hass_ws_client):
    entry = await setup_entry(with_article=True)
    client = await hass_ws_client(hass)
    added = await _send(client, 1, "home_stock/list/add", free_text="Pain")
    item_id = added["result"]["items"][0]["id"]

    removed = await _send(client, 2, "home_stock/list/remove", item_id=item_id)

    assert removed["result"]["items"] == []
    row = repo.get_list_item(entry.runtime_data.manager.db.read(), item_id)
    assert row["removed_at"] is not None


async def test_refresh_returns_the_counts(hass: HomeAssistant, setup_entry,
                                          hass_ws_client):
    entry = await setup_entry(with_article=True)
    await _seed(hass, entry)
    client = await hass_ws_client(hass)
    answer = await _send(client, 1, "home_stock/list/refresh")
    assert answer["result"]["created"] == 2
    assert answer["result"]["open"] == 2


# --- les récurrences --------------------------------------------------------

@pytest.mark.parametrize("days, accepted", [(0, False), (1, True),
                                            (365, True), (366, False)])
async def test_recurring_save_bounds_every_days(hass: HomeAssistant, setup_entry,
                                                hass_ws_client, days, accepted):
    """0 refusé, 1 accepté, 365 accepté, 366 refusé. Les quatre bornes."""
    await setup_entry(with_article=True)
    client = await hass_ws_client(hass)
    answer = await _send(client, 1, "home_stock/recurring/save",
                         free_text="Café", every_days=days)
    assert answer["success"] is accepted


async def test_recurring_lines_round_trip(hass: HomeAssistant, setup_entry,
                                          hass_ws_client):
    await setup_entry(with_article=True)
    client = await hass_ws_client(hass)
    saved = await _send(client, 1, "home_stock/recurring/save",
                        free_text="Sacs poubelle", every_days=30, quantity=1)
    recurring_id = saved["result"]["recurring"][0]["id"]

    listed = await _send(client, 2, "home_stock/recurring/list")
    assert listed["result"]["recurring"][0]["every_days"] == 30

    deleted = await _send(client, 3, "home_stock/recurring/delete",
                          recurring_id=recurring_id)
    assert deleted["result"]["recurring"] == []


# --- les magasins -----------------------------------------------------------

async def test_stores_list_carries_id_and_observed_sessions(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    await setup_entry(with_article=True)
    client = await hass_ws_client(hass)
    await _send(client, 1, "home_stock/session/start", store="Leclerc")
    await _send(client, 2, "home_stock/session/close")

    answer = await _send(client, 3, "home_stock/stores/list")

    [store] = answer["result"]["stores"]
    assert store["name"] == "Leclerc"
    assert store["id"] and store["observed_sessions"] == 1


async def test_a_store_can_be_renamed_and_deactivated(hass: HomeAssistant,
                                                      setup_entry, hass_ws_client):
    await setup_entry(with_article=True)
    client = await hass_ws_client(hass)
    saved = await _send(client, 1, "home_stock/store/save", name="Leclerc")
    store_id = saved["result"]["stores"][0]["id"]

    renamed = await _send(client, 2, "home_stock/store/save", store_id=store_id,
                          name="E.Leclerc")
    assert renamed["result"]["stores"][0]["name"] == "E.Leclerc"

    hidden = await _send(client, 3, "home_stock/store/save", store_id=store_id,
                         name="E.Leclerc", active=0)
    assert hidden["result"]["stores"] == []


async def test_merging_during_an_open_session_is_refused_in_french(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    await setup_entry(with_article=True)
    client = await hass_ws_client(hass)
    other = await _send(client, 1, "home_stock/store/save", name="E.Leclerc")
    merge_id = other["result"]["stores"][0]["id"]
    started = await _send(client, 2, "home_stock/session/start", store="Leclerc")

    refused = await _send(client, 3, "home_stock/store/merge",
                          keep_id=started["result"]["store_id"], merge_id=merge_id)

    assert refused["success"] is False
    assert "en cours" in refused["error"]["message"]


async def test_merging_two_closed_stores_goes_through(hass: HomeAssistant,
                                                      setup_entry, hass_ws_client):
    await setup_entry(with_article=True)
    client = await hass_ws_client(hass)
    await _send(client, 1, "home_stock/store/save", name="Leclerc")
    saved = await _send(client, 2, "home_stock/store/save", name="E.Leclerc")
    by_name = {row["name"]: row["id"] for row in saved["result"]["stores"]}

    merged = await _send(client, 3, "home_stock/store/merge",
                         keep_id=by_name["Leclerc"],
                         merge_id=by_name["E.Leclerc"])

    assert merged["success"] is True
    assert len(merged["result"]["stores"]) == 1


async def test_reorder_aisles_pins_and_says_it_pinned(hass: HomeAssistant,
                                                      setup_entry, hass_ws_client):
    entry = await setup_entry(with_article=True)
    ids = await _seed(hass, entry)
    client = await hass_ws_client(hass)
    saved = await _send(client, 1, "home_stock/store/save", name="Leclerc")
    store_id = saved["result"]["stores"][0]["id"]

    answer = await _send(client, 2, "home_stock/store/reorder_aisles",
                         store_id=store_id,
                         aisle_ids=[ids["aisles"]["Épicerie salée"],
                                    ids["aisles"]["Crémerie"]])

    aisles = answer["result"]["aisles"]
    assert [row["aisle_name"] for row in aisles][:2] == ["Épicerie salée", "Crémerie"]
    assert all(row["source"] == "manual" for row in aisles[:2])


async def test_store_aisles_reports_how_far_the_learning_got(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    """« 2 sessions sur 3 » : les réglages le DISENT plutôt que d'afficher
    un ordre par défaut sans expliquer pourquoi."""
    await setup_entry(with_article=True)
    client = await hass_ws_client(hass)
    for turn in (1, 2):
        await _send(client, turn * 10, "home_stock/session/start", store="Leclerc")
        await _send(client, turn * 10 + 1, "home_stock/session/close")
    stores = await _send(client, 30, "home_stock/stores/list")
    store_id = stores["result"]["stores"][0]["id"]

    answer = await _send(client, 31, "home_stock/store/aisles", store_id=store_id)

    assert answer["result"]["observed_sessions"] == 2
    assert answer["result"]["required_sessions"] == 3
    assert answer["result"]["reliable"] is False


# --- la correction ----------------------------------------------------------

async def _one_movement(hass, entry):
    manager = entry.runtime_data.manager

    def _write() -> dict:
        with manager.db.write() as conn:
            location_id = repo.insert_location(conn, name="Frigo", kind="fridge")
        batch_id = manager.add_stock(article_id=1, quantity=1000,
                                     location_id=location_id,
                                     price_per_base_unit=0.002,
                                     occurred_at="2026-08-14T10:00:00")
        movement_id = manager.consume_batch(batch_id, quantity=200.0,
                                            occurred_at="2026-08-14T18:00:00")
        return {"batch_id": batch_id, "movement_id": movement_id}

    return await hass.async_add_executor_job(_write)


async def test_correcting_a_movement_returns_the_correction_row(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    entry = await setup_entry(with_article=True)
    ids = await _one_movement(hass, entry)
    client = await hass_ws_client(hass)

    answer = await _send(client, 1, "home_stock/movement/correct",
                         movement_id=ids["movement_id"])

    assert answer["result"]["correction_id"]
    assert answer["result"]["restored"] is True


async def test_correcting_twice_answers_a_french_refusal_not_unknown_error(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    entry = await setup_entry(with_article=True)
    ids = await _one_movement(hass, entry)
    client = await hass_ws_client(hass)
    first = await _send(client, 1, "home_stock/movement/correct",
                        movement_id=ids["movement_id"])

    refused = await _send(client, 2, "home_stock/movement/correct",
                          movement_id=first["result"]["correction_id"])

    assert refused["success"] is False
    assert refused["error"]["message"] == (
        "Cette ligne est déjà une correction : corriger une correction, "
        "c'est refaire la saisie.")


async def test_correction_preview_says_what_it_will_do(hass: HomeAssistant,
                                                       setup_entry, hass_ws_client):
    entry = await setup_entry(with_article=True)
    ids = await _one_movement(hass, entry)
    client = await hass_ws_client(hass)

    answer = await _send(client, 1, "home_stock/movement/correction_preview",
                         movement_id=ids["movement_id"])

    result = answer["result"]
    assert result["quantity"] == pytest.approx(200.0)
    assert result["correctable"] is True
    assert result["batch_id"] == ids["batch_id"]


async def test_correcting_a_meal_that_was_never_validated_is_refused_in_french(
        hass: HomeAssistant, setup_entry, hass_ws_client):
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
    client = await hass_ws_client(hass)

    refused = await _send(client, 1, "home_stock/meal/correct", meal_id=meal_id)

    assert refused["success"] is False
    assert refused["error"]["message"] == (
        "Ce repas n'a pas été validé : il n'y a rien à annuler.")


# --- les extensions et la file hors ligne -----------------------------------

async def test_session_start_accepts_a_store_id(hass: HomeAssistant, setup_entry,
                                                hass_ws_client):
    await setup_entry(with_article=True)
    client = await hass_ws_client(hass)
    saved = await _send(client, 1, "home_stock/store/save", name="Leclerc")
    store_id = saved["result"]["stores"][0]["id"]

    started = await _send(client, 2, "home_stock/session/start", store_id=store_id)

    assert started["result"]["store_id"] == store_id
    assert started["result"]["store"] == "Leclerc"


async def test_every_new_write_command_accepts_an_idempotency_key(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    """Le contrat de la file hors ligne : une écriture faite dans un magasin
    est une écriture faite là où le réseau est le plus mauvais."""
    entry = await setup_entry(with_article=True)
    ids = await _one_movement(hass, entry)
    client = await hass_ws_client(hass)
    added = await _send(client, 1, "home_stock/list/add", free_text="Pain",
                        idempotency_key="a")
    item_id = added["result"]["items"][0]["id"]
    saved = await _send(client, 2, "home_stock/store/save", name="Leclerc",
                        idempotency_key="b")
    store_id = saved["result"]["stores"][0]["id"]

    for number, (command, payload) in enumerate([
            ("home_stock/list/check", {"item_id": item_id}),
            ("home_stock/list/uncheck", {"item_id": item_id}),
            ("home_stock/list/remove", {"item_id": item_id}),
            ("home_stock/list/refresh", {}),
            ("home_stock/recurring/save", {"free_text": "Café", "every_days": 21}),
            ("home_stock/store/reorder_aisles",
             {"store_id": store_id, "aisle_ids": []}),
            ("home_stock/movement/correct", {"movement_id": ids["movement_id"]}),
    ], start=10):
        answer = await _send(client, number, command,
                             idempotency_key=f"clef-{number}", **payload)
        assert answer["success"] is True, command
