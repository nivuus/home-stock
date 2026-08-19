"""Read and write commands for the panel. The panel reuses the Home Assistant
connection, so there is no separate authentication and it can subscribe to
changes."""
from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import asdict
from functools import partial
from typing import Any, Callable, Final

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .domain.conversion import ConversionError, MAX_REFERENCE, MIN_REFERENCE
from .domain.matching import candidates, preselect, strip_brand
from .domain.pricing import suggest_price
from .domain.units import UnitError
from .off.mapping import map_article, nutrition_per_base_unit, to_article_columns
from .off.open_prices import latest_price
from .storage import repositories as repo

# Same wording as services._entry()'s HomeAssistantError, for the same condition.
NOT_LOADED_MESSAGE = "Le garde-manger n'est pas configuré."

_GRADE: Final = vol.In(("a", "b", "c", "d", "e"))
_TEXT: Final = vol.Any(str, None)
_REQUIRED_TEXT: Final = vol.Schema(str)
_FLOAT: Final = vol.Any(vol.Coerce(float), None)
_INT: Final = vol.Any(vol.Coerce(int), None)

# Columns a human may edit from the panel, mapped to the shape a value must
# have to be written. Both the column names AND the values reach SQL through
# repositories._update_fields, which interpolates the column name and binds
# the value as-is: SQLite is dynamically typed, so an unvalidated value lands
# in any column and rots there silently (a string in a REAL column disables
# whatever compares against it, with no error anywhere — see
# test_product_update_refuses_a_non_numeric_min_quantity for the shortage
# sensor this breaks). Every value below is validated against its schema
# before any write is attempted.
ARTICLE_EDITABLE: Final[dict[str, Callable[[Any], Any]]] = {
    "label": _TEXT,
    "brand": _TEXT,
    "net_quantity": _FLOAT,
    "image": _TEXT,
    "kcal_per_base_unit": _FLOAT,
    "proteins": _FLOAT,
    "carbohydrates": _FLOAT,
    "sugars": _FLOAT,
    "added_sugars": _FLOAT,
    "fat": _FLOAT,
    "saturated_fat": _FLOAT,
    "fiber": _FLOAT,
    "salt": _FLOAT,
    "nutriscore": vol.Any(_GRADE, None),
    "nova": _INT,
    "ecoscore": _TEXT,
}
# base_unit is deliberately absent: a plain field edit that changed a unit
# would rewrite the meaning of every stored quantity (batches, prices,
# nutrition) with nothing converted. The only path to a unit change is
# home_stock/product/convert_unit, which rescales everything atomically.
PRODUCT_EDITABLE: Final[dict[str, Callable[[Any], Any]]] = {
    "name": _REQUIRED_TEXT,
    "category_id": _INT,
    "aisle_id": _INT,
    "edible": cv.boolean,
    "default_location_id": _INT,
    "min_quantity": _FLOAT,
    "days_after_opening": _INT,
    "default_shelf_life_days": _INT,
    "reference_kcal": _FLOAT,
    "active": cv.boolean,
}

# English message the domain/application layer raised, matched and turned
# into the French sentence the panel actually shows. The domain is right to
# raise in English (the code is English); this is the seam where it becomes
# what a person reads — the same seam services._run already is for the
# voice/service path, so the vocabulary below matches its wording rather
# than inventing a second one.
_DOMAIN_ERROR_PATTERNS: Final[tuple[tuple[re.Pattern[str], str, Callable[[re.Match], str]], ...]] = (
    (re.compile(r"^unknown article (\d+)$"), "not_found",
     lambda m: f"Article {m.group(1)} inconnu."),
    (re.compile(r"^no article (\d+)$"), "not_found",
     lambda m: f"Article {m.group(1)} inconnu."),
    (re.compile(r"^no product (\d+)$"), "not_found",
     lambda m: f"Produit {m.group(1)} inconnu."),
    (re.compile(r"^unknown or closed batch (\d+)$"), "not_found",
     lambda m: f"Lot {m.group(1)} inconnu ou déjà clôturé."),
    (re.compile(r"^unknown batch (\d+)$"), "not_found",
     lambda m: f"Lot {m.group(1)} inconnu."),
    (re.compile(r"^quantity must not be negative, got (.+)$"), "invalid_value",
     lambda m: f"La quantité ne peut pas être négative (reçu : {m.group(1)})."),
    (re.compile(r"^packaging quantity must be positive, got (.+)$"), "invalid_value",
     lambda m: f"Le conditionnement doit être positif (reçu : {m.group(1)})."),
)


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


def _validate_fields(schema: dict[str, Callable[[Any], Any]], fields: dict[str, Any],
                     connection: websocket_api.ActiveConnection,
                     msg_id: int) -> dict[str, Any] | None:
    """Check `fields` against `schema`: an unknown column and a bad value are
    both refused before anything reaches SQL. Returns the validated (and
    coerced) fields, or None after sending an `invalid_field` error — the
    caller must return as soon as it gets None back.
    """
    unknown = set(fields) - set(schema)
    if unknown:
        connection.send_error(msg_id, "invalid_field",
                              f"Colonnes non modifiables : {sorted(unknown)}")
        return None
    validated: dict[str, Any] = {}
    for column, value in fields.items():
        try:
            validated[column] = schema[column](value)
        except vol.Invalid:
            connection.send_error(
                msg_id, "invalid_field",
                f"Valeur invalide pour « {column} » : {value!r}")
            return None
    return validated


def _send_domain_error(connection: websocket_api.ActiveConnection, msg_id: int,
                       err: Exception) -> None:
    """Translate a LookupError/UnitError/ValueError from the domain or
    application layer into a French websocket error."""
    text = str(err)
    for pattern, code, formatter in _DOMAIN_ERROR_PATTERNS:
        match = pattern.match(text)
        if match:
            connection.send_error(msg_id, code, formatter(match))
            return
    connection.send_error(msg_id, "invalid_value", "Valeur invalide.")


def _send_integrity_error(connection: websocket_api.ActiveConnection, msg_id: int,
                          err: sqlite3.IntegrityError, *, name: str | None = None) -> None:
    """Translate a UNIQUE/FOREIGN KEY violation into French.

    `name` is passed when the caller already knows what value collided (the
    product name typed on article/create), so the message can say what to do
    about it instead of just naming the SQL constraint.
    """
    text = str(err)
    if "UNIQUE constraint failed: product.name" in text:
        if name:
            connection.send_error(
                msg_id, "already_exists",
                f"Un produit nommé « {name} » existe déjà : rattachez ce scan à ce "
                "produit plutôt que d'en créer un nouveau.")
        else:
            connection.send_error(msg_id, "already_exists",
                                  "Un produit portant ce nom existe déjà.")
        return
    if "FOREIGN KEY constraint failed" in text:
        connection.send_error(
            msg_id, "invalid_field",
            "Référence invalide (rayon, catégorie ou emplacement inconnu).")
        return
    connection.send_error(msg_id, "invalid_field", "Écriture refusée : donnée invalide.")


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
        price = await _suggest_price(hass, runtime, known, code)
        connection.send_result(msg["id"], {
            "code": code, "known": True, "article": known, "product": product,
            "off": None, "off_raw": None, "off_source": None,
            "candidates": [], "preselected_product_id": None,
            "price": price, "conversion_offer": _conversion_offer(product, known),
            "throttled": False, "timed_out": False,
        })
        return

    result = await runtime.off_client.lookup(code)
    if result.record is None:
        connection.send_result(msg["id"], {
            "code": code, "known": False, "article": None, "product": None,
            "off": None, "off_raw": None, "off_source": None,
            "candidates": [], "preselected_product_id": None,
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

    if msg.get("product_id") is None and "new_product" not in msg:
        connection.send_error(
            msg["id"], "invalid_field",
            "Indiquez product_id (produit existant) ou new_product (nouveau produit).")
        return

    fields = _validate_fields(ARTICLE_EDITABLE, msg["fields"], connection, msg["id"])
    if fields is None:
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
            if product is None:
                raise LookupError(f"no product {product_id}")
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
            values.update(fields)
            if fields:
                # A correction typed on the creation screen must survive the
                # article's first OFF resync exactly like one typed later
                # through article/update — manual_fields is what protects it.
                # Without this, a kcal typed here would be silently
                # overwritten the first time the article is resynced.
                values["manual_fields"] = json.dumps(sorted(fields))

            article_id = repo.insert_article(conn, product_id=product_id, **values)
            repo.link_barcode(conn, msg["code"], article_id)
            return {"article_id": article_id, "product_id": product_id, "created": True}

    try:
        result = await hass.async_add_executor_job(work)
    except sqlite3.IntegrityError as err:
        name = (msg.get("new_product") or {}).get("name")
        _send_integrity_error(connection, msg["id"], err, name=name)
        return
    except (LookupError, UnitError, ValueError) as err:
        _send_domain_error(connection, msg["id"], err)
        return

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

    fields = _validate_fields(ARTICLE_EDITABLE, msg["fields"], connection, msg["id"])
    if fields is None:
        return

    def work() -> None:
        with runtime.manager.db.write() as conn:
            article = repo.get_article(conn, msg["article_id"])
            if article is None:
                raise LookupError(f"no article {msg['article_id']}")
            protected = set(json.loads(article["manual_fields"] or "[]"))
            protected.update(fields)
            repo.update_article_fields(conn, msg["article_id"], {
                **fields,
                "manual_fields": json.dumps(sorted(protected)),
            })

    try:
        await hass.async_add_executor_job(work)
    except LookupError as err:
        _send_domain_error(connection, msg["id"], err)
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

    fields = _validate_fields(PRODUCT_EDITABLE, msg["fields"], connection, msg["id"])
    if fields is None:
        return

    def work() -> None:
        with runtime.manager.db.write() as conn:
            product = repo.get_product(conn, msg["product_id"])
            if product is None:
                raise LookupError(f"no product {msg['product_id']}")
            repo.update_product_fields(conn, msg["product_id"], fields)

    try:
        await hass.async_add_executor_job(work)
    except LookupError as err:
        _send_domain_error(connection, msg["id"], err)
        return
    except sqlite3.IntegrityError as err:
        _send_integrity_error(connection, msg["id"], err)
        return
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

    product = await _read(hass, partial(
        repo.get_product, runtime.manager.db.read(), msg["product_id"]))
    if product is None:
        connection.send_error(msg["id"], "not_found",
                              f"produit {msg['product_id']} inconnu")
        return

    if product["base_unit"] == msg["to_unit"]:
        # The caller asked for an end state the product already has. This is
        # exactly what a replayed queue looks like after the first call
        # already succeeded (the panel lost the connection before the ack) —
        # answering "refused" here would be indistinguishable from a
        # conversion that never happened, so this is a normal, unapplied
        # result instead: asking for a unit a product already has is
        # success, not refusal.
        connection.send_result(msg["id"], {
            "product_id": product["id"], "product_name": product["name"],
            "from_unit": product["base_unit"], "to_unit": msg["to_unit"],
            "reference_quantity": msg["reference_quantity"], "articles": 0,
            "batches": 0, "movements": 0, "articles_using_reference": [],
            "applied": False, "already_converted": True,
        })
        return

    try:
        report = await hass.async_add_executor_job(partial(
            runtime.manager.convert_product_unit,
            product_id=msg["product_id"], to_unit=msg["to_unit"],
            reference_quantity=msg["reference_quantity"],
            packaging_name=msg["packaging_name"], dry_run=msg["dry_run"],
        ))
    except ConversionError as err:
        connection.send_error(msg["id"], "conversion_refused",
                              _translate_conversion_error(err, product))
        return
    except LookupError as err:
        connection.send_error(msg["id"], "not_found",
                              f"produit {msg['product_id']} inconnu")
        return

    report["already_converted"] = False
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

    try:
        result = await hass.async_add_executor_job(partial(
            runtime.manager.add_stock, article_id=msg["article_id"],
            quantity=msg["quantity"], location_id=msg["location_id"],
            best_before=msg.get("best_before"),
            price_per_base_unit=msg.get("price_per_base_unit"),
            idempotency_key=msg.get("idempotency_key"),
        ))
    except (LookupError, UnitError, ValueError) as err:
        _send_domain_error(connection, msg["id"], err)
        return
    except sqlite3.IntegrityError as err:
        _send_integrity_error(connection, msg["id"], err)
        return

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
            existing = {row["id"] for row in conn.execute("SELECT id FROM aisle").fetchall()}
            unknown = [a for a in msg["aisle_ids"] if a not in existing]
            if unknown:
                # Raised (and caught) here, in French directly: this check is
                # local to the websocket boundary, never crosses into the
                # domain layer, so there is no English original to translate.
                raise LookupError(f"Rayon(s) inconnu(s) : {sorted(unknown)}")
            for position, aisle_id in enumerate(msg["aisle_ids"]):
                conn.execute("UPDATE aisle SET position = ? WHERE id = ?",
                             (position, aisle_id))

    try:
        await hass.async_add_executor_job(work)
    except LookupError as err:
        connection.send_error(msg["id"], "not_found", str(err))
        return
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


def _translate_conversion_error(err: ConversionError, product: dict[str, Any]) -> str:
    """A French sentence for a ConversionError. `application.convert_product_unit`'s
    own pending-shopping-lines refusal is already French — passed through
    unchanged; everything else comes from `domain.conversion.plan_conversion`,
    in English, and is translated here."""
    text = str(err)
    if "ligne(s) de courses" in text:
        return text
    if "is already stocked in" in text:
        return (f"Ce produit est suivi en « {product['base_unit']} » : seule la "
                "conversion d'un produit suivi « à la pièce » est prise en charge.")
    if "target unit must be one of" in text:
        return "L'unité cible doit être « g » ou « ml »."
    if "reference weight must be between" in text:
        return (f"Le poids de référence doit être compris entre {MIN_REFERENCE} "
                f"et {MAX_REFERENCE}.")
    return "Conversion refusée : configuration invalide."


async def _suggest_price(hass, runtime, article, code) -> dict[str, Any]:
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
            runtime.transport, code,
            net_quantity=article.get("net_quantity"), user_agent=runtime.user_agent)
    return asdict(suggest_price(in_store=in_store, open_prices=from_open_prices,
                                last_known=last_known, store=store))


async def _open_prices_only(hass, runtime, code, net_quantity) -> dict[str, Any]:
    """An article that does not exist yet has no history: only Open Prices can help."""
    from_open_prices = await latest_price(
        runtime.transport, code,
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
