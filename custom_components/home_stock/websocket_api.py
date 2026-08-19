"""Read and write commands for the panel. The panel reuses the Home Assistant
connection, so there is no separate authentication and it can subscribe to
changes."""
from __future__ import annotations

import json
from dataclasses import asdict
from functools import partial
from typing import Any, Final

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .domain.conversion import ConversionError, MAX_REFERENCE, MIN_REFERENCE
from .domain.matching import candidates, preselect, strip_brand
from .domain.pricing import suggest_price
from .off.client import AiohttpTransport
from .off.mapping import map_article, nutrition_per_base_unit, to_article_columns
from .off.open_prices import latest_price
from .storage import repositories as repo

# Same wording as services._entry()'s HomeAssistantError, for the same condition.
NOT_LOADED_MESSAGE = "Le garde-manger n'est pas configuré."

# Columns a human may edit from the panel. Both sets are interpolated into
# SQL by repositories._update_fields, so nothing outside them is ever written.
ARTICLE_EDITABLE: Final = frozenset({
    "label", "brand", "net_quantity", "image", "kcal_per_base_unit", "proteins",
    "carbohydrates", "sugars", "added_sugars", "fat", "saturated_fat", "fiber",
    "salt", "nutriscore", "nova", "ecoscore",
})
# base_unit is deliberately absent: a plain field edit that changed a unit
# would rewrite the meaning of every stored quantity (batches, prices,
# nutrition) with nothing converted. The only path to a unit change is
# home_stock/product/convert_unit, which rescales everything atomically.
PRODUCT_EDITABLE: Final = frozenset({
    "name", "category_id", "aisle_id", "edible", "default_location_id",
    "min_quantity", "days_after_opening", "default_shelf_life_days", "reference_kcal",
    "active",
})


def _runtime(hass: HomeAssistant):
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    return entries[0].runtime_data if entries else None


def _send_not_loaded(connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Answer a proper error instead of letting `runtime.manager` raise a bare
    AttributeError, which Home Assistant would report to the client as an
    opaque "Unknown error" while logging a full traceback."""
    connection.send_error(msg["id"], "not_loaded", NOT_LOADED_MESSAGE)


async def _read(hass: HomeAssistant, work) -> Any:
    return await hass.async_add_executor_job(work)


@websocket_api.websocket_command({vol.Required("type"): "home_stock/products/list"})
@websocket_api.async_response
async def products_list(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    products = await _read(hass, partial(repo.list_products, runtime.manager.db.read()))
    connection.send_result(msg["id"], {"products": products})


@websocket_api.websocket_command({vol.Required("type"): "home_stock/locations/list"})
@websocket_api.async_response
async def locations_list(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    locations = await _read(hass, partial(repo.list_locations, runtime.manager.db.read()))
    connection.send_result(msg["id"], {"locations": locations})


@websocket_api.websocket_command({vol.Required("type"): "home_stock/aisles/list"})
@websocket_api.async_response
async def aisles_list(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    aisles = await _read(hass, partial(repo.list_aisles, runtime.manager.db.read()))
    connection.send_result(msg["id"], {"aisles": aisles})


@websocket_api.websocket_command({vol.Required("type"): "home_stock/batches/list"})
@websocket_api.async_response
async def batches_list(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    batches = await _read(hass, partial(repo.stock_rows, runtime.manager.db.read()))
    connection.send_result(msg["id"], {"batches": batches})


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/product/get",
    vol.Required("product_id"): int,
})
@websocket_api.async_response
async def product_get(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    product = await _read(hass, partial(
        repo.get_product, runtime.manager.db.read(), msg["product_id"]
    ))
    if product is None:
        connection.send_error(msg["id"], "not_found",
                              f"produit {msg['product_id']} inconnu")
        return
    connection.send_result(msg["id"], {"product": product})


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/movements/list",
    vol.Optional("since"): str,
})
@websocket_api.async_response
async def movements_list(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    movements = await _read(hass, partial(
        repo.list_movements, runtime.manager.db.read(), msg.get("since")
    ))
    connection.send_result(msg["id"], {"movements": movements})


@websocket_api.websocket_command({vol.Required("type"): "home_stock/subscribe"})
@callback
def subscribe(hass, connection, msg) -> None:
    """Push the summary now, and again on every coordinator refresh."""
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    coordinator = runtime.coordinator

    @callback
    def _forward() -> None:
        connection.send_event(msg["id"], coordinator.data)

    connection.subscriptions[msg["id"]] = coordinator.async_add_listener(_forward)
    connection.send_result(msg["id"])
    # Guaranteed first push: whatever the coordinator already holds, sent
    # straight to this connection. Immediate and free — no database read, no
    # dependency on `always_update` triggering `async_update_listeners()` for
    # every registered listener, and no risk of a refresh error trying to
    # answer this msg["id"] a second time after send_result already did.
    connection.send_event(msg["id"], coordinator.data)
    # Both production write paths (the services and the todo entity) already
    # await a coordinator refresh before returning, so the push above is
    # normally already current. This only closes the narrow gap a write
    # outside those paths leaves open within the debounce window below —
    # request one, without awaiting it: `async_request_refresh` is debounced,
    # so several panels subscribing at once coalesce into a single database
    # read instead of one full read (and one rebroadcast to every other
    # already-connected client) per new subscriber, unlike `async_refresh()`.
    hass.async_create_task(coordinator.async_request_refresh(),
                           "home_stock subscribe refresh")


# --- write commands -----------------------------------------------------


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/lookup",
    vol.Required("code"): str,
})
@websocket_api.async_response
async def lookup(hass, connection, msg) -> None:
    """Resolve a barcode. Writes nothing: creation is a separate, explicit step."""
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return

    code = msg["code"]
    known = await _read(hass, partial(
        repo.find_article_by_barcode, runtime.manager.db.read(), code))

    if known is not None:
        product = await _read(hass, partial(
            repo.get_product, runtime.manager.db.read(), known["product_id"]))
        price = await _suggest_price(hass, runtime, known, product, code)
        connection.send_result(msg["id"], {
            "code": code, "known": True, "article": known, "product": product,
            "off": None, "candidates": [], "preselected_product_id": None,
            "price": price, "conversion_offer": _conversion_offer(product, known),
            "throttled": False, "timed_out": False,
        })
        return

    result = await runtime.off_client.lookup(code)
    if result.record is None:
        connection.send_result(msg["id"], {
            "code": code, "known": False, "article": None, "product": None,
            "off": None, "candidates": [], "preselected_product_id": None,
            "price": None, "conversion_offer": None,
            "throttled": result.throttled, "timed_out": result.timed_out,
        })
        return

    mapped = map_article(result.record.product, result.record.off_source)
    products = await _read(hass, partial(repo.list_products, runtime.manager.db.read()))
    found = candidates(names=[mapped.generic_name, mapped.label,
                              strip_brand(mapped.label or "", mapped.brand)],
                       products=products)
    chosen = preselect(found)

    connection.send_result(msg["id"], {
        "code": code, "known": False, "article": None, "product": None,
        "off": asdict(mapped), "off_raw": result.record.product,
        "off_source": result.record.off_source,
        "candidates": [asdict(c) for c in found],
        "preselected_product_id": chosen.product_id if chosen else None,
        "price": await _open_prices_only(hass, runtime, code, mapped.net_quantity),
        "conversion_offer": None, "throttled": False, "timed_out": False,
    })


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/article/create",
    vol.Required("code"): str,
    vol.Exclusive("product_id", "target"): int,
    vol.Exclusive("new_product", "target"): dict,
    vol.Optional("off"): dict,
    vol.Optional("off_source"): vol.Any(str, None),
    vol.Optional("fields", default={}): dict,
})
@websocket_api.async_response
async def article_create(hass, connection, msg) -> None:
    """Persist a scanned article, its barcode, and the OFF answer verbatim."""
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return

    def work() -> dict[str, Any]:
        with runtime.manager.db.write() as conn:
            existing = repo.find_article_by_barcode(conn, msg["code"])
            if existing is not None:
                # A replayed creation, or two phones scanning the same pack.
                return {"article_id": existing["id"],
                        "product_id": existing["product_id"], "created": False}

            raw = msg.get("off") or {}
            source = msg.get("off_source")
            mapped = map_article(raw, source) if raw and source else None

            product_id = msg.get("product_id")
            if product_id is None:
                wanted = dict(msg["new_product"])
                aisle = mapped.aisle if mapped else None
                if aisle:
                    row = conn.execute(
                        "SELECT id FROM aisle WHERE name = ?", (aisle,)).fetchone()
                    if row is not None:
                        wanted.setdefault("aisle_id", row["id"])
                product_id = repo.insert_product(conn, **wanted)

            product = repo.get_product(conn, product_id)
            values: dict[str, Any] = {"is_generic": 0}
            if mapped is not None:
                values.update({
                    "label": mapped.label, "brand": mapped.brand,
                    "net_quantity": mapped.net_quantity, "image": mapped.image,
                    "nutriscore": mapped.nutriscore, "nova": mapped.nova,
                    "ecoscore": mapped.ecoscore, "allergens": mapped.allergens,
                    "traces": mapped.traces, "additives": mapped.additives,
                    "off_labels": mapped.off_labels, "off_source": mapped.off_source,
                    "off_synced_at": dt_util.utcnow().replace(
                        microsecond=0, tzinfo=None).isoformat(),
                    "off_raw": json.dumps(raw, ensure_ascii=False),
                })
                per_base = nutrition_per_base_unit(
                    mapped.nutrition_per_100, product["base_unit"], mapped.net_quantity)
                # to_article_columns renames `kcal` to the article's own
                # `kcal_per_base_unit`. Passing the raw dict would lose the
                # calories silently, because insert_article drops keys it does
                # not recognise without raising.
                values.update(to_article_columns(per_base))
            values.update({k: v for k, v in msg["fields"].items() if k in ARTICLE_EDITABLE})

            article_id = repo.insert_article(conn, product_id=product_id, **values)
            repo.link_barcode(conn, msg["code"], article_id)
            return {"article_id": article_id, "product_id": product_id, "created": True}

    result = await hass.async_add_executor_job(work)
    await runtime.coordinator.async_request_refresh()
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/article/update",
    vol.Required("article_id"): int,
    vol.Required("fields"): dict,
})
@websocket_api.async_response
async def article_update(hass, connection, msg) -> None:
    """Edit an article by hand. Edited columns are never resynced from OFF again."""
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return

    unknown = set(msg["fields"]) - ARTICLE_EDITABLE
    if unknown:
        connection.send_error(msg["id"], "invalid_field",
                              f"Colonnes non modifiables : {sorted(unknown)}")
        return

    def work() -> None:
        with runtime.manager.db.write() as conn:
            article = repo.get_article(conn, msg["article_id"])
            if article is None:
                raise LookupError(f"no article {msg['article_id']}")
            protected = set(json.loads(article["manual_fields"] or "[]"))
            protected.update(msg["fields"])
            repo.update_article_fields(conn, msg["article_id"], {
                **msg["fields"],
                "manual_fields": json.dumps(sorted(protected)),
            })

    try:
        await hass.async_add_executor_job(work)
    except LookupError as err:
        connection.send_error(msg["id"], "not_found", str(err))
        return
    await runtime.coordinator.async_request_refresh()
    connection.send_result(msg["id"], {"article_id": msg["article_id"]})


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/product/update",
    vol.Required("product_id"): int,
    vol.Required("fields"): dict,
})
@websocket_api.async_response
async def product_update(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return

    unknown = set(msg["fields"]) - PRODUCT_EDITABLE
    if unknown:
        connection.send_error(msg["id"], "invalid_field",
                              f"Colonnes non modifiables : {sorted(unknown)}")
        return

    def work() -> None:
        with runtime.manager.db.write() as conn:
            repo.update_product_fields(conn, msg["product_id"], msg["fields"])

    await hass.async_add_executor_job(work)
    await runtime.coordinator.async_request_refresh()
    connection.send_result(msg["id"], {"product_id": msg["product_id"]})


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/product/convert_unit",
    vol.Required("product_id"): int,
    vol.Required("to_unit"): vol.In(("g", "ml")),
    vol.Required("reference_quantity"): vol.Coerce(float),
    vol.Optional("packaging_name", default="unité"): str,
    vol.Optional("dry_run", default=False): bool,
})
@websocket_api.async_response
async def product_convert_unit(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return

    try:
        report = await hass.async_add_executor_job(partial(
            runtime.manager.convert_product_unit,
            product_id=msg["product_id"], to_unit=msg["to_unit"],
            reference_quantity=msg["reference_quantity"],
            packaging_name=msg["packaging_name"], dry_run=msg["dry_run"],
        ))
    except ConversionError as err:
        connection.send_error(msg["id"], "conversion_refused", str(err))
        return
    except LookupError as err:
        connection.send_error(msg["id"], "not_found", str(err))
        return

    if report["applied"]:
        await runtime.coordinator.async_request_refresh()
    connection.send_result(msg["id"], report)


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/stock/add",
    vol.Required("article_id"): int,
    vol.Required("quantity"): vol.Coerce(float),
    vol.Required("location_id"): int,
    vol.Optional("best_before"): vol.Any(str, None),
    vol.Optional("price_per_base_unit"): vol.Any(vol.Coerce(float), None),
    vol.Optional("idempotency_key"): vol.Any(str, None),
})
@websocket_api.async_response
async def stock_add(hass, connection, msg) -> None:
    """Put one thing away, outside any shopping session."""
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return

    result = await hass.async_add_executor_job(partial(
        runtime.manager.add_stock, article_id=msg["article_id"],
        quantity=msg["quantity"], location_id=msg["location_id"],
        best_before=msg.get("best_before"),
        price_per_base_unit=msg.get("price_per_base_unit"),
        idempotency_key=msg.get("idempotency_key"),
    ))
    await runtime.coordinator.async_request_refresh()
    connection.send_result(msg["id"], {"batch_id": result})


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/aisles/reorder",
    vol.Required("aisle_ids"): [int],
})
@websocket_api.async_response
async def aisles_reorder(hass, connection, msg) -> None:
    """Set the walking order. Position is the index in the list given."""
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return

    def work() -> None:
        with runtime.manager.db.write() as conn:
            for position, aisle_id in enumerate(msg["aisle_ids"]):
                conn.execute("UPDATE aisle SET position = ? WHERE id = ?",
                             (position, aisle_id))

    await hass.async_add_executor_job(work)
    connection.send_result(msg["id"], {"aisles": len(msg["aisle_ids"])})


def _conversion_offer(product: dict[str, Any] | None,
                      article: dict[str, Any] | None) -> dict[str, Any] | None:
    """Offer a piece -> gram move, but only when the weight is trustworthy."""
    if not product or not article or product["base_unit"] != "piece":
        return None
    net = article.get("net_quantity")
    if not net or not MIN_REFERENCE <= net <= MAX_REFERENCE:
        return None
    return {"product_id": product["id"], "to_unit": "g", "reference_quantity": net}


async def _suggest_price(hass, runtime, article, product, code) -> dict[str, Any]:
    """The price cascade for an article already in the catalogue.

    `code` is passed explicitly rather than read off `article`:
    repo.find_article_by_barcode's `SELECT a.*` never returns a `code`
    column, so reading `article.get("code")` would silently skip Open
    Prices for every known article.
    """
    conn = runtime.manager.db.read()
    session = await _read(hass, partial(repo.current_session, conn))
    store = session["store"] if session else None
    in_store = (await _read(hass, partial(repo.latest_price_in_store, conn,
                                          article["id"], store))) if store else None
    last_known = await _read(hass, partial(repo.latest_price, conn, article["id"]))
    from_open_prices = None
    if in_store is None:
        from_open_prices = await latest_price(
            AiohttpTransport(async_get_clientsession(hass)), code,
            net_quantity=article.get("net_quantity"), user_agent=runtime.user_agent)
    return asdict(suggest_price(in_store=in_store, open_prices=from_open_prices,
                                last_known=last_known, store=store))


async def _open_prices_only(hass, runtime, code, net_quantity) -> dict[str, Any]:
    """An article that does not exist yet has no history: only Open Prices can help."""
    from_open_prices = await latest_price(
        AiohttpTransport(async_get_clientsession(hass)), code,
        net_quantity=net_quantity, user_agent=runtime.user_agent)
    return asdict(suggest_price(in_store=None, open_prices=from_open_prices,
                                last_known=None, store=None))


def async_register_websocket(hass: HomeAssistant) -> None:
    """Register the read and write commands once."""
    for command in (products_list, product_get, locations_list, aisles_list,
                    batches_list, movements_list, subscribe, lookup,
                    article_create, article_update, product_update,
                    product_convert_unit, stock_add, aisles_reorder):
        websocket_api.async_register_command(hass, command)
