"""The delete surfaces: websocket commands and admin services.

Two products in every fixture: Riz (never served, erasable), Lait (with
history, hidden on delete) — plus Pâtes, with open stock, which blocks.
"""
from __future__ import annotations

import itertools

import pytest
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError, Unauthorized

NOW = "2026-09-28T10:00:00"


def _seed(conn) -> dict[str, int]:
    ids = {"placard": conn.execute(
        "INSERT INTO location (name, kind) VALUES ('Placard', 'pantry')").lastrowid}
    for key, name in (("riz", "Riz"), ("lait", "Lait"), ("pates", "Pâtes")):
        ids[key] = conn.execute(
            "INSERT INTO product (name, base_unit) VALUES (?, 'g')",
            (name,)).lastrowid
        ids[f"{key}_article"] = conn.execute(
            "INSERT INTO article (product_id) VALUES (?)", (ids[key],)).lastrowid
    # Lait: a batch long gone. Pâtes: a batch still in the cupboard.
    for key, closed in (("lait", NOW), ("pates", None)):
        conn.execute(
            "INSERT INTO batch (article_id, location_id, remaining, initial,"
            " entered_at, closed_at) VALUES (?, ?, ?, 1000, ?, ?)",
            (ids[f"{key}_article"], ids["placard"], 0 if closed else 100, NOW, closed))
    return ids


@pytest.fixture
async def seeded(hass: HomeAssistant, setup_entry):
    entry = await setup_entry()
    db = entry.runtime_data.manager.db

    def work():
        with db.write() as conn:
            return _seed(conn)

    ids = await hass.async_add_executor_job(work)
    await entry.runtime_data.coordinator.async_request_refresh()
    await hass.async_block_till_done()
    return entry, ids


def _dump(entry):
    return list(entry.runtime_data.manager.db.read().iterdump())


_IDS = itertools.count(1)


async def _ws(client, **payload):
    await client.send_json({"id": next(_IDS), **payload})
    return await client.receive_json()


async def _call(hass, service, data, *, user=None):
    return await hass.services.async_call(
        "home_stock", service, data, blocking=True, return_response=True,
        context=Context(user_id=user.id) if user else None)


# --- websocket ---------------------------------------------------------------

async def test_an_admin_deletes_and_hides_through_the_websocket(
        hass: HomeAssistant, seeded, hass_ws_client):
    _, ids = seeded
    client = await hass_ws_client(hass)

    erased = await _ws(client, type="home_stock/product/delete", product_id=ids["riz"])
    hidden = await _ws(client, type="home_stock/product/delete", product_id=ids["lait"])
    article = await _ws(client, type="home_stock/article/delete",
                        article_id=ids["lait_article"])

    assert erased["result"] == {"outcome": "deleted"}
    assert hidden["result"] == {"outcome": "hidden"}
    assert article["result"] == {"outcome": "hidden"}


@pytest.mark.parametrize(("command", "key"), [
    ("home_stock/product/delete", "riz"),
    ("home_stock/article/delete", "riz_article"),
])
async def test_the_tablet_user_is_refused_by_the_websocket(
        hass: HomeAssistant, seeded, hass_ws_client, hass_read_only_access_token,
        command, key):
    entry, ids = seeded
    before = _dump(entry)
    client = await hass_ws_client(hass, hass_read_only_access_token)

    field = "product_id" if command.endswith("product/delete") else "article_id"
    answer = await _ws(client, type=command, **{field: ids[key]})

    assert answer["success"] is False
    assert answer["error"]["code"] == "unauthorized"
    assert _dump(entry) == before


async def test_a_blocked_delete_answers_delete_blocked_in_french(
        hass: HomeAssistant, seeded, hass_ws_client):
    entry, ids = seeded
    before = _dump(entry)
    client = await hass_ws_client(hass)

    answer = await _ws(client, type="home_stock/product/delete", product_id=ids["pates"])

    assert answer["error"] == {"code": "delete_blocked",
                               "message": "Encore 1 lot en stock (Placard)"}
    assert _dump(entry) == before


async def test_an_unknown_id_is_not_found_on_the_websocket(
        hass: HomeAssistant, seeded, hass_ws_client):
    client = await hass_ws_client(hass)
    answer = await _ws(client, type="home_stock/article/delete", article_id=999)
    assert answer["error"] == {"code": "not_found", "message": "Article 999 inconnu."}


async def test_the_shortage_sensor_forgets_a_hidden_product_at_once(
        hass: HomeAssistant, seeded, hass_ws_client):
    """Lait and Pâtes go under a threshold. Hide Lait: only Pâtes is still
    short, and the sensor says so without waiting for the polling interval.

    A product under its threshold lands on the shopping list by itself, and
    an open list line blocks the delete: the line is removed by hand first,
    which the reconciliation respects."""
    entry, ids = seeded
    coordinator = entry.runtime_data.coordinator

    def threshold():
        with entry.runtime_data.manager.db.write() as conn:
            conn.execute("UPDATE product SET min_quantity = 500000"
                         " WHERE id IN (?, ?)", (ids["lait"], ids["pates"]))

    def remove_lait_line():
        with entry.runtime_data.manager.db.write() as conn:
            conn.execute("UPDATE shopping_list_item SET removed_at = ?"
                         " WHERE product_id = ?", (NOW, ids["lait"]))

    await hass.async_add_executor_job(threshold)
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    await hass.async_add_executor_job(remove_lait_line)
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    shortages = hass.states.get("binary_sensor.home_stock_shortages")
    assert shortages.attributes["products"] == ["Lait", "Pâtes"]

    client = await hass_ws_client(hass)
    answer = await _ws(client, type="home_stock/product/delete", product_id=ids["lait"])
    assert answer["result"] == {"outcome": "hidden"}
    await hass.async_block_till_done()

    shortages = hass.states.get("binary_sensor.home_stock_shortages")
    assert shortages.attributes["products"] == ["Pâtes"]


# --- services ----------------------------------------------------------------

async def test_an_admin_deletes_through_the_service(
        hass: HomeAssistant, seeded, hass_admin_user):
    _, ids = seeded
    assert await _call(hass, "delete_product", {"product_id": ids["lait"]},
                       user=hass_admin_user) == {"outcome": "hidden"}
    assert await _call(hass, "delete_article", {"article_id": ids["riz_article"]},
                       user=hass_admin_user) == {"outcome": "deleted"}


@pytest.mark.parametrize(("service", "field", "key"), [
    ("delete_product", "product_id", "riz"),
    ("delete_article", "article_id", "riz_article"),
])
async def test_the_tablet_user_is_refused_by_the_service(
        hass: HomeAssistant, seeded, hass_read_only_user, service, field, key):
    entry, ids = seeded
    before = _dump(entry)
    with pytest.raises(Unauthorized):
        await _call(hass, service, {field: ids[key]}, user=hass_read_only_user)
    assert _dump(entry) == before


async def test_a_blocked_delete_says_the_same_thing_on_the_service(
        hass: HomeAssistant, seeded, hass_admin_user):
    entry, ids = seeded
    before = _dump(entry)
    with pytest.raises(HomeAssistantError, match=r"^Encore 1 lot en stock \(Placard\)$"):
        await _call(hass, "delete_product", {"product_id": ids["pates"]},
                    user=hass_admin_user)
    assert _dump(entry) == before


async def test_the_services_are_described(hass: HomeAssistant, seeded):
    from homeassistant.helpers.service import async_get_all_descriptions

    described = (await async_get_all_descriptions(hass))["home_stock"]
    assert set(described["delete_product"]["fields"]) == {"product_id"}
    assert set(described["delete_article"]["fields"]) == {"article_id"}
    assert described["delete_product"]["response"] == {"optional": True}


# --- parity: fresh state per surface, same verdict ---------------------------

@pytest.mark.parametrize(("service", "command", "field", "key", "expected"), [
    ("delete_product", "home_stock/product/delete", "product_id", "pates", "refusé"),
    ("delete_article", "home_stock/article/delete", "article_id", "pates_article",
     "refusé"),
    ("delete_product", "home_stock/product/delete", "product_id", "riz", "accepté"),
    ("delete_article", "home_stock/article/delete", "article_id", "lait_article",
     "accepté"),
])
@pytest.mark.parametrize("surface", ["websocket", "service"])
async def test_both_surfaces_give_the_same_verdict_on_the_same_state(
        hass: HomeAssistant, seeded, hass_ws_client, surface,
        service, command, field, key, expected):
    _, ids = seeded
    if surface == "websocket":
        answer = await _ws(await hass_ws_client(hass), type=command,
                           **{field: ids[key]})
        verdict = "accepté" if answer["success"] else "refusé"
    else:
        try:
            await _call(hass, service, {field: ids[key]})
            verdict = "accepté"
        except HomeAssistantError:
            verdict = "refusé"
    assert verdict == expected


@pytest.mark.parametrize("bad", [0, -3, True, 1.5, 2**70])
async def test_an_impossible_id_is_refused_by_the_schema(
        hass: HomeAssistant, seeded, hass_ws_client, bad):
    """Refused before any read: an id no row can carry is a malformed
    request, not an unknown product."""
    client = await hass_ws_client(hass)
    answer = await _ws(client, type="home_stock/product/delete", product_id=bad)
    assert answer["error"]["code"] == "invalid_format"
