"""A hidden product or article stays out of the lists, the matching and the
suggestions — but the scan still finds it, flagged, so buying it again never
creates a duplicate.

Two products everywhere: Riz (hidden) and Lait (visible).
"""
from __future__ import annotations

import json
from datetime import date

import pytest
from homeassistant.core import HomeAssistant

from custom_components.home_stock.application import resolve_ingredient_match
from custom_components.home_stock.storage import repositories as repo

TODAY = date(2026, 9, 28)
NOW = "2026-09-28T10:00:00"


def _seed(conn) -> dict[str, int]:
    """Riz and Lait, both under their threshold, each with an article and a
    barcode; Riz is hidden."""
    ids = {"placard": repo.insert_location(conn, name="Placard", kind="pantry")}
    for key, name, code in (("riz", "Riz", "111"), ("lait", "Lait", "222")):
        product = repo.insert_product(conn, name=name, base_unit="g", min_quantity=500)
        article = repo.insert_article(conn, product_id=product, is_generic=1)
        repo.link_barcode(conn, code, article)
        ids[key], ids[f"{key}_article"] = product, article
    conn.execute("UPDATE product SET active = 0 WHERE id = ?", (ids["riz"],))
    return ids


@pytest.fixture
def seeded(manager):
    with manager.db.write() as conn:
        return _seed(conn)


# --- lists, alerts, suggestions ----------------------------------------------

def test_low_stock_alerts_skip_a_hidden_product(manager, seeded):
    names = {row["product_id"] for row in repo.shortage_rows(manager.db.read())}
    assert names == {seeded["lait"]}


def test_a_shortage_of_a_hidden_product_is_never_suggested(manager, seeded):
    manager.reconcile_shopping_list(today=TODAY)
    assert {row["product_id"] for row in manager.shopping_list()} == {seeded["lait"]}


def test_a_recurring_purchase_of_a_hidden_product_is_never_suggested(manager, seeded):
    with manager.db.write() as conn:
        conn.execute("UPDATE product SET min_quantity = NULL")
        for key in ("riz", "lait"):
            conn.execute(
                "INSERT INTO shopping_recurring (product_id, every_days) VALUES (?, 7)",
                (seeded[key],))
    manager.reconcile_shopping_list(today=TODAY)
    assert {row["product_id"] for row in manager.shopping_list()} == {seeded["lait"]}


def test_a_planned_meal_never_asks_to_buy_a_hidden_product(manager, seeded):
    with manager.db.write() as conn:
        conn.execute("UPDATE product SET min_quantity = NULL")
        recipe = repo.insert_recipe(conn, name="Riz au lait", source="manual",
                                    created_at=NOW)
        for position, key in ((1, "riz"), (2, "lait")):
            repo.insert_ingredient(conn, recipe_id=recipe, position=position,
                                   raw_text=key, product_id=seeded[key], amount=100,
                                   match_state="confirmed")
        repo.insert_meal(conn, uid="m1", day="2026-09-29", slot_key="dinner",
                         created_at=NOW, recipe_id=recipe)
    manager.reconcile_shopping_list(today=TODAY)
    assert {row["product_id"] for row in manager.shopping_list()} == {seeded["lait"]}


def test_the_price_estimate_skips_a_hidden_article(manager, seeded):
    """Lait has two articles: the usual one (generic) is hidden, the other
    visible. The estimate must price the visible one."""
    with manager.db.write() as conn:
        other = repo.insert_article(conn, product_id=seeded["lait"])
        conn.execute("UPDATE article SET active = 0 WHERE id = ?",
                     (seeded["lait_article"],))
        repo.insert_price(conn, article_id=seeded["lait_article"],
                          observed_on="2026-09-01", price_per_base_unit=0.01,
                          source="manual")
        repo.insert_price(conn, article_id=other, observed_on="2026-09-01",
                          price_per_base_unit=0.02, source="manual")
        repo.insert_list_item(conn, added_at=NOW, product_id=seeded["lait"],
                              quantity=100)
    rows = repo.list_estimate_rows(manager.db.read())
    assert [(r["article_id"], r["estimate"]) for r in rows] == [(other, 2.0)]


# --- ingredient matching -----------------------------------------------------

def test_ingredient_matching_never_proposes_a_hidden_product(manager, seeded):
    with manager.db.write() as conn:
        products = repo.list_products(conn)
        state, product_id, _, found = resolve_ingredient_match(
            conn, raw_text="riz", ingredient_name=None, products=products)
    assert product_id != seeded["riz"]
    assert seeded["riz"] not in {c.product_id for c in found}


def test_an_alias_to_a_hidden_product_no_longer_decides(manager, seeded):
    with manager.db.write() as conn:
        repo.upsert_alias(conn, normalised="riz", product_id=seeded["riz"],
                          created_at=NOW)
        repo.upsert_alias(conn, normalised="lait", product_id=seeded["lait"],
                          created_at=NOW)
        products = repo.list_products(conn)
        hidden = resolve_ingredient_match(
            conn, raw_text="riz", ingredient_name=None, products=products)
        visible = resolve_ingredient_match(
            conn, raw_text="lait", ingredient_name=None, products=products)
    assert hidden[:2] != ("confirmed", seeded["riz"])
    assert visible[:2] == ("confirmed", seeded["lait"])


# --- the websocket surface ---------------------------------------------------

async def _entry_with(hass, setup_entry):
    entry = await setup_entry()
    manager = entry.runtime_data.manager

    def work():
        with manager.db.write() as conn:
            return _seed(conn)

    return entry, await hass.async_add_executor_job(work)


async def test_products_list_hides_hidden_products_unless_asked(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    _, ids = await _entry_with(hass, setup_entry)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/products/list"})
    default = (await client.receive_json())["result"]["products"]
    await client.send_json({"id": 2, "type": "home_stock/products/list",
                            "include_hidden": True})
    everything = (await client.receive_json())["result"]["products"]

    assert [p["id"] for p in default] == [ids["lait"]]
    assert {p["id"] for p in everything} == {ids["riz"], ids["lait"]}


@pytest.mark.parametrize(("code", "article_active", "product_active"), [
    ("111", False, False),     # Riz: product hidden, article untouched
    ("222", True, True),       # Lait: visible
])
async def test_the_scan_finds_a_hidden_article_and_flags_it(
        hass: HomeAssistant, setup_entry, hass_ws_client,
        code, article_active, product_active):
    await _entry_with(hass, setup_entry)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/lookup", "code": code})
    result = (await client.receive_json())["result"]

    assert result["known"] is True
    assert result["article"]["active"] is article_active
    assert result["product"]["active"] is product_active


async def test_the_scan_flags_a_hidden_article_of_a_visible_product(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    entry, ids = await _entry_with(hass, setup_entry)
    await hass.async_add_executor_job(_run, entry, "UPDATE article SET active = 0"
                                      " WHERE id = ?", (ids["lait_article"],))
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/lookup", "code": "222"})
    result = (await client.receive_json())["result"]

    assert result["article"]["active"] is False
    assert result["product"]["active"] is True


def _run(entry, sql, args=()):
    with entry.runtime_data.manager.db.write() as conn:
        conn.execute(sql, args)


def _row(entry, sql, args=()):
    return dict(entry.runtime_data.manager.db.read().execute(sql, args).fetchone())


async def test_restoring_an_article_of_a_hidden_product_restores_both(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    entry, ids = await _entry_with(hass, setup_entry)
    await hass.async_add_executor_job(_run, entry, "UPDATE article SET active = 0"
                                      " WHERE id = ?", (ids["riz_article"],))
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/article/update",
                            "article_id": ids["riz_article"], "fields": {"active": 1}})
    assert (await client.receive_json())["success"] is True

    article = await hass.async_add_executor_job(
        _row, entry, "SELECT active, manual_fields FROM article WHERE id = ?",
        (ids["riz_article"],))
    product = await hass.async_add_executor_job(
        _row, entry, "SELECT active FROM product WHERE id = ?", (ids["riz"],))
    assert article["active"] == 1 and product["active"] == 1
    # Visibility is not an Open Food Facts field: nothing to protect from resync.
    assert "active" not in json.loads(article["manual_fields"] or "[]")


async def test_article_update_hides_an_article_alongside_other_fields(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    entry, ids = await _entry_with(hass, setup_entry)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/article/update",
                            "article_id": ids["lait_article"],
                            "fields": {"active": False, "label": "Lait 1 L"}})
    assert (await client.receive_json())["success"] is True

    article = await hass.async_add_executor_job(
        _row, entry, "SELECT active, label, manual_fields FROM article WHERE id = ?",
        (ids["lait_article"],))
    product = await hass.async_add_executor_job(
        _row, entry, "SELECT active FROM product WHERE id = ?", (ids["lait"],))
    assert (article["active"], article["label"]) == (0, "Lait 1 L")
    assert json.loads(article["manual_fields"]) == ["label"]
    assert product["active"] == 1


async def test_article_update_refuses_a_bad_active_value(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    entry, ids = await _entry_with(hass, setup_entry)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/article/update",
                            "article_id": ids["lait_article"], "fields": {"active": 5}})
    answer = await client.receive_json()
    assert answer["success"] is False
    assert answer["error"]["code"] == "invalid_field"


# --- re-creating a hidden product by name -------------------------------------

async def test_creating_a_product_named_like_a_hidden_one_says_it_is_hidden(
        hass: HomeAssistant, setup_entry):
    from homeassistant.exceptions import ServiceValidationError

    from custom_components.home_stock.aisles import AISLES

    await _entry_with(hass, setup_entry)
    with pytest.raises(ServiceValidationError, match="masqué"):
        await hass.services.async_call(
            "home_stock", "create_product", {"name": "Riz", "rayon": AISLES[0]},
            blocking=True, return_response=True)
    # A visible namesake keeps the plain message.
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            "home_stock", "create_product", {"name": "Lait", "rayon": AISLES[0]},
            blocking=True, return_response=True)
    assert "masqué" not in str(err.value)


async def test_scanning_into_a_new_product_named_like_a_hidden_one_says_so(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    await _entry_with(hass, setup_entry)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/article/create",
                            "code": "999",
                            "new_product": {"name": "Riz", "base_unit": "g"}})
    answer = await client.receive_json()

    assert answer["error"]["code"] == "already_exists"
    assert "masqué" in answer["error"]["message"]
