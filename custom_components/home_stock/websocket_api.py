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
from homeassistant.util import dt as dt_util

from .const import BASE_UNITS, DOMAIN
from .domain.conversion import ConversionError, MAX_REFERENCE, MIN_REFERENCE
from .domain.matching import candidates, preselect, strip_brand
from .domain.pricing import suggest_price
from .domain.units import UnitError
from .off.mapping import (
    MAX_NET_QUANTITY,
    MIN_NET_QUANTITY,
    map_article,
    nutrition_per_base_unit,
    to_article_columns,
)
from .off.open_prices import latest_price
from .shopping import ShoppingError
from .storage import repositories as repo
from .validators import MAX_TEXT_LENGTH, bounded_int, bounded_text, finite_float, iso_date, preview

# Same wording as services._entry()'s HomeAssistantError, for the same condition.
NOT_LOADED_MESSAGE = "Le garde-manger n'est pas configuré."

# --- value validators ------------------------------------------------------
#
# SQLite is dynamically typed: repositories._update_fields interpolates a
# column name and binds whatever value it is given, so both the column NAME
# and its VALUE must be checked before anything reaches SQL. A whitelist of
# names alone is not enough — see test_product_update_refuses_a_non_numeric_
# min_quantity, which used to reach the shortage sensor as a silently
# uncomparable string.
#
# finite_float/bounded_int/bounded_text/iso_date/preview all live in
# .validators, not here: services.py needs the exact same guarantees (a
# service call is just as capable of writing Inf, an out-of-range id, or an
# unparseable best_before into the database as a websocket command is), and
# the older surface must not be the weaker one. Aliased under their old
# private names so none of this module's call sites needed to change.
_finite_float = finite_float
_bounded_int = bounded_int
_bounded_text = bounded_text
_iso_date = iso_date
_preview = preview


def _non_empty_text(value: Any) -> str:
    """A product name: trimmed, capped, and refused if that leaves nothing
    — `name: ""` (or all-whitespace) satisfies the `NOT NULL` column but
    names nothing a person could find again."""
    if not isinstance(value, str):
        raise vol.Invalid(f"expected a string, got {_preview(value)}")
    trimmed = value.strip()
    if not trimmed:
        raise vol.Invalid("expected a non-empty name")
    if len(trimmed) > MAX_TEXT_LENGTH:
        raise vol.Invalid(
            f"text too long: {len(trimmed)} characters (max {MAX_TEXT_LENGTH})")
    return trimmed


_TRUE_STRINGS: Final = frozenset({"1", "true", "yes", "on"})
_FALSE_STRINGS: Final = frozenset({"0", "false", "no", "off"})


def _strict_boolean(value: Any) -> bool:
    """Stricter than `cv.boolean`, which treats any non-zero number as true
    — `edible: 5` must not be silently accepted as "yes". The panel always
    sends a real JSON boolean; the string forms below exist only as English
    tolerance for a hand-typed call (a service, a test, curl against the
    websocket), not because the panel ever sends one. Only an actual bool,
    one of those strings, or exactly 0/1 are recognised; everything else is
    refused."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in _TRUE_STRINGS:
            return True
        if lowered in _FALSE_STRINGS:
            return False
    elif isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    raise vol.Invalid(f"expected a boolean, got {_preview(value)}")


_GRADE: Final = vol.In(("a", "b", "c", "d", "e"))
_BASE_UNIT: Final = vol.In(BASE_UNITS)
_TEXT: Final = _bounded_text                                         # free, nullable text, capped
# A quantity cannot be negative: a person never means "-5 g" or "-5 kcal".
_NON_NEGATIVE_FLOAT: Final = vol.Any(vol.All(_finite_float, vol.Range(min=0)), None)
_NON_NEGATIVE_INT: Final = vol.Any(vol.All(_bounded_int, vol.Range(min=0)), None)
# category_id/aisle_id/default_location_id reference an INTEGER PRIMARY KEY,
# which SQLite starts at 1: 0 or a negative id can never be a real row.
_POSITIVE_ID: Final = vol.Any(vol.All(_bounded_int, vol.Range(min=1)), None)
# The four Nutri-Score/NOVA classification groups OFF actually uses.
_NOVA: Final = vol.Any(vol.All(_bounded_int, vol.In((1, 2, 3, 4))), None)
# Same plausibility window OFF's own mapping uses for a net weight
# (off/mapping.py's MIN_NET_QUANTITY/MAX_NET_QUANTITY): a manually typed
# net_quantity is the same kind of value and deserves the same guard.
_NET_QUANTITY: Final = vol.Any(
    vol.All(_finite_float, vol.Range(min=MIN_NET_QUANTITY, max=MAX_NET_QUANTITY)), None)


# A real Open Food Facts record is a few kilobytes; 256 kB is generous
# headroom without letting one scan grow the database without bound.
MAX_OFF_RAW_BYTES: Final = 256 * 1024

# Columns a human may edit from the panel, mapped to the shape a value must
# have to be written. Every value is validated against its schema before any
# write is attempted — see the module docstring above this section.
ARTICLE_EDITABLE: Final[dict[str, Callable[[Any], Any]]] = {
    "label": _TEXT,
    "brand": _TEXT,
    "net_quantity": _NET_QUANTITY,
    "image": _TEXT,
    "kcal_per_base_unit": _NON_NEGATIVE_FLOAT,
    "proteins": _NON_NEGATIVE_FLOAT,
    "carbohydrates": _NON_NEGATIVE_FLOAT,
    "sugars": _NON_NEGATIVE_FLOAT,
    "added_sugars": _NON_NEGATIVE_FLOAT,
    "fat": _NON_NEGATIVE_FLOAT,
    "saturated_fat": _NON_NEGATIVE_FLOAT,
    "fiber": _NON_NEGATIVE_FLOAT,
    "salt": _NON_NEGATIVE_FLOAT,
    "nutriscore": vol.Any(_GRADE, None),
    "nova": _NOVA,
    "ecoscore": _TEXT,
}
# base_unit is deliberately absent: a plain field edit that changed a unit
# would rewrite the meaning of every stored quantity (batches, prices,
# nutrition) with nothing converted. The only path to a unit change is
# home_stock/product/convert_unit, which rescales everything atomically.
PRODUCT_EDITABLE: Final[dict[str, Callable[[Any], Any]]] = {
    "name": _non_empty_text,
    "category_id": _POSITIVE_ID,
    "aisle_id": _POSITIVE_ID,
    "edible": _strict_boolean,
    "default_location_id": _POSITIVE_ID,
    "min_quantity": _NON_NEGATIVE_FLOAT,
    "days_after_opening": _NON_NEGATIVE_INT,
    "default_shelf_life_days": _NON_NEGATIVE_INT,
    "reference_kcal": _NON_NEGATIVE_FLOAT,
    "active": _strict_boolean,
}
# The schema a brand-new product must satisfy: everything PRODUCT_EDITABLE
# already validates, plus base_unit — which an *edit* deliberately excludes
# (see the comment above) but a *creation* has to supply, since a product
# cannot exist without one. A new product must not be creatable in a state
# an edit of that same product would refuse.
NEW_PRODUCT_SCHEMA: Final[dict[str, Callable[[Any], Any]]] = {
    **PRODUCT_EDITABLE,
    "base_unit": _BASE_UNIT,
}
NEW_PRODUCT_REQUIRED: Final = ("name", "base_unit")

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
                f"Valeur invalide pour « {column} » : {_preview(value)}")
            return None
    return validated


def _validate_new_product(new_product: dict[str, Any],
                          connection: websocket_api.ActiveConnection,
                          msg_id: int) -> dict[str, Any] | None:
    """A brand-new product must not be creatable in a state an edit of that
    same product would refuse: reuses NEW_PRODUCT_SCHEMA's validators (the
    same ones PRODUCT_EDITABLE uses, plus base_unit), then on top of that
    requires the columns a creation cannot default (name, base_unit) —
    `insert_product`'s keyword-only signature raises a bare TypeError
    without them, which article_create also now catches as a backstop, but
    refusing here first is what turns that into a proper French error.
    """
    missing = [key for key in NEW_PRODUCT_REQUIRED if key not in new_product]
    if missing:
        connection.send_error(
            msg_id, "invalid_field",
            f"Champs requis pour un nouveau produit : {sorted(missing)}")
        return None
    return _validate_fields(NEW_PRODUCT_SCHEMA, new_product, connection, msg_id)


def _drop_invalid_off_values(schema: dict[str, Callable[[Any], Any]],
                             values: dict[str, Any]) -> list[str]:
    """Validate OFF-derived entries of `values` against `schema`, IN PLACE,
    dropping whichever fail instead of refusing the whole write.

    Deliberately not the same policy `_validate_fields` applies to what a
    person typed: a client-supplied field is refused because the person can
    fix what they typed, but an Open Food Facts contributor's typo is not
    something the person scanning a barcode can fix, and refusing the whole
    scan over one bad field (a Nova group of 99, a Nutri-Score of "zzz")
    would make the scanner useless exactly when it is most needed. Off/
    mapping.py already guards the two fields most likely to be implausible
    (nova, nutriscore) at the source; this is the general backstop for
    whatever it does not — today, chiefly free text with no length bound of
    its own (label, brand, image).

    Returns the column names dropped, so the caller can tell the panel what
    happened instead of leaving a silently missing value to explain itself.
    """
    dropped: list[str] = []
    for column in list(values):
        if column not in schema:
            continue
        try:
            values[column] = schema[column](values[column])
        except vol.Invalid:
            del values[column]
            dropped.append(column)
    return dropped


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
    vol.Required("product_id"): _bounded_int,
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
    vol.Required("code"): _non_empty_text,
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
    vol.Required("code"): _non_empty_text,
    vol.Exclusive("product_id", "target"): _bounded_int,
    vol.Exclusive("new_product", "target"): dict,
    vol.Optional("off"): dict,
    vol.Optional("off_source"): _bounded_text,
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

    new_product = None
    if msg.get("product_id") is None:
        new_product = _validate_new_product(msg["new_product"], connection, msg["id"])
        if new_product is None:
            return

    raw = msg.get("off") or {}
    # Serialised once, up front: work() reuses this string verbatim rather
    # than re-encoding raw a second time inside the executor job.
    off_raw_json = json.dumps(raw, ensure_ascii=False) if raw else None
    if off_raw_json is not None and len(off_raw_json.encode("utf-8")) > MAX_OFF_RAW_BYTES:
        # A real OFF record is a few kilobytes; refusing outright here (not
        # dropping, as _drop_invalid_off_values does for a single bad field)
        # is the only sane response to a blob this size — there is no
        # meaningful way to store "most of" a JSON document.
        connection.send_error(
            msg["id"], "invalid_field", "Réponse Open Food Facts trop volumineuse.")
        return

    def work() -> dict[str, Any]:
        with runtime.manager.db.write() as conn:
            existing = repo.find_article_by_barcode(conn, msg["code"])
            if existing is not None:
                # A replayed creation, or two phones scanning the same pack.
                return {"article_id": existing["id"],
                        "product_id": existing["product_id"], "created": False,
                        "off_dropped_fields": []}

            source = msg.get("off_source")
            mapped = map_article(raw, source) if raw and source else None

            product_id = msg.get("product_id")
            if product_id is None:
                wanted = dict(new_product)
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
            dropped_off_fields: list[str] = []
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
                    "off_raw": off_raw_json,
                })
                per_base = nutrition_per_base_unit(
                    mapped.nutrition_per_100, product["base_unit"], mapped.net_quantity)
                # to_article_columns renames `kcal` to the article's own
                # `kcal_per_base_unit`. Passing the raw dict would lose the
                # calories silently, because insert_article drops keys it does
                # not recognise without raising.
                values.update(to_article_columns(per_base))
                # OFF is a stranger's database entry, not something the
                # person scanning can fix: an implausible value (a Nova
                # group off/mapping.py did not already catch, a label with
                # no length bound of its own) is dropped, not refused — the
                # article is still created with everything else. Run before
                # `fields` is merged in, so a client-supplied correction is
                # never subject to this policy; it already went through
                # _validate_fields, which refuses instead.
                dropped_off_fields = _drop_invalid_off_values(ARTICLE_EDITABLE, values)
                # off/mapping.py neutralises an implausible nova/nutriscore
                # before this function ever sees it, so the drop above never
                # has a bad value left to catch for those two columns —
                # merge in what map_article already recorded in its own
                # `rejections`, so the panel finds out about those too, not
                # just the ones caught here.
                for name in mapped.rejections:
                    if name in ARTICLE_EDITABLE and name not in dropped_off_fields:
                        dropped_off_fields.append(name)
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
            return {"article_id": article_id, "product_id": product_id, "created": True,
                    "off_dropped_fields": dropped_off_fields}

    try:
        result = await hass.async_add_executor_job(work)
    except sqlite3.IntegrityError as err:
        name = (msg.get("new_product") or {}).get("name")
        _send_integrity_error(connection, msg["id"], err, name=name)
        return
    except (LookupError, UnitError, ValueError, TypeError, OverflowError) as err:
        # TypeError is a backstop, not the primary defence: _validate_new_
        # product already requires name/base_unit before work() ever runs,
        # so insert_product's keyword-only signature should never actually
        # raise one here. OverflowError is the same kind of backstop for a
        # number sqlite3 refuses to bind — _bounded_int/_finite_float and
        # off/mapping.py's own nova/nutriscore bounds should already have
        # caught it upstream. Caught anyway so a gap in either answers a
        # French (if generic) refusal instead of "Unknown error".
        _send_domain_error(connection, msg["id"], err)
        return

    await runtime.coordinator.async_request_refresh()
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/article/update",
    vol.Required("article_id"): _bounded_int,
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
    except (LookupError, OverflowError) as err:
        # OverflowError is a backstop: _bounded_int already bounds
        # article_id at the schema level, so this should be unreachable —
        # caught anyway so a gap there answers a French refusal instead of
        # "Unknown error".
        _send_domain_error(connection, msg["id"], err)
        return
    await runtime.coordinator.async_request_refresh()
    connection.send_result(msg["id"], {"article_id": msg["article_id"]})


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/product/update",
    vol.Required("product_id"): _bounded_int,
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
    except (LookupError, OverflowError) as err:
        # OverflowError is a backstop: _bounded_int already bounds
        # product_id/category_id/aisle_id/etc. at the schema level, so this
        # should be unreachable — caught anyway so a gap there answers a
        # French refusal instead of "Unknown error".
        _send_domain_error(connection, msg["id"], err)
        return
    except sqlite3.IntegrityError as err:
        _send_integrity_error(connection, msg["id"], err)
        return
    await runtime.coordinator.async_request_refresh()
    connection.send_result(msg["id"], {"product_id": msg["product_id"]})


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/product/convert_unit",
    vol.Required("product_id"): _bounded_int,
    vol.Required("to_unit"): vol.In(("g", "ml")),
    vol.Required("reference_quantity"): _finite_float,
    vol.Optional("packaging_name", default="unité"): _non_empty_text,
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
    except OverflowError as err:
        # Backstop: _bounded_int already bounds product_id/reference_
        # quantity at the schema level, so this should be unreachable.
        _send_domain_error(connection, msg["id"], err)
        return

    report["already_converted"] = False
    if report["applied"]:
        await runtime.coordinator.async_request_refresh()
    connection.send_result(msg["id"], report)


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/stock/add",
    vol.Required("article_id"): _bounded_int,
    vol.Required("quantity"): _finite_float,
    vol.Required("location_id"): _bounded_int,
    vol.Optional("best_before"): _iso_date,
    vol.Optional("price_per_base_unit"): vol.Any(_finite_float, None),
    vol.Optional("idempotency_key"): _bounded_text,
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
    except (LookupError, UnitError, ValueError, OverflowError) as err:
        # OverflowError is a backstop: _bounded_int/_finite_float already
        # bound article_id/location_id/quantity/price_per_base_unit at the
        # schema level, so this should be unreachable.
        _send_domain_error(connection, msg["id"], err)
        return
    except sqlite3.IntegrityError as err:
        _send_integrity_error(connection, msg["id"], err)
        return

    await runtime.coordinator.async_request_refresh()
    connection.send_result(msg["id"], {"batch_id": result})


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/aisles/reorder",
    vol.Required("aisle_ids"): [_bounded_int],
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
    except OverflowError as err:
        # Backstop: _bounded_int already bounds every id in aisle_ids at the
        # schema level, so this should be unreachable.
        _send_domain_error(connection, msg["id"], err)
        return
    connection.send_result(msg["id"], {"aisles": len(msg["aisle_ids"])})


def _shopping_error(connection: websocket_api.ActiveConnection, msg: dict[str, Any],
                    err: ShoppingError) -> None:
    """ShoppingError's own message is already the French sentence to show —
    unlike _send_domain_error's targets, nothing here needs translating: the
    application layer raises it directly for a person to read (see
    shopping.py). Sent through the same `connection.send_error` seam as
    _send_domain_error/_send_integrity_error so a ShoppingError reaches the
    panel exactly like every other refusal, never as "Unknown error"."""
    connection.send_error(msg["id"], "shopping_refused", str(err))


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/session/start",
    vol.Optional("store"): _bounded_text,
})
@websocket_api.async_response
async def session_start(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    try:
        session = await hass.async_add_executor_job(partial(
            runtime.shopping.start, store=msg.get("store")))
    except ShoppingError as err:
        _shopping_error(connection, msg, err)
        return
    await runtime.coordinator.async_request_refresh()
    connection.send_result(msg["id"], session)


@websocket_api.websocket_command({vol.Required("type"): "home_stock/session/current"})
@websocket_api.async_response
async def session_current(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    connection.send_result(msg["id"], await _read(hass, runtime.shopping.current))


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/session/add_line",
    vol.Required("article_id"): _bounded_int,
    vol.Required("quantity"): _finite_float,
    vol.Optional("unit_price"): vol.Any(_finite_float, None),
    vol.Optional("idempotency_key"): _bounded_text,
})
@websocket_api.async_response
async def session_add_line(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    try:
        line = await hass.async_add_executor_job(partial(
            runtime.shopping.add_line, article_id=msg["article_id"],
            quantity=msg["quantity"], unit_price=msg.get("unit_price"),
            idempotency_key=msg.get("idempotency_key")))
    except ShoppingError as err:
        _shopping_error(connection, msg, err)
        return
    await runtime.coordinator.async_request_refresh()
    connection.send_result(msg["id"], line)


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/session/update_line",
    vol.Required("line_id"): _bounded_int,
    vol.Optional("quantity"): vol.Any(_finite_float, None),
    vol.Optional("unit_price"): vol.Any(_finite_float, None),
})
@websocket_api.async_response
async def session_update_line(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    try:
        line = await hass.async_add_executor_job(partial(
            runtime.shopping.update_line, msg["line_id"],
            quantity=msg.get("quantity"), unit_price=msg.get("unit_price")))
    except ShoppingError as err:
        _shopping_error(connection, msg, err)
        return
    await runtime.coordinator.async_request_refresh()
    connection.send_result(msg["id"], line)


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/session/remove_line",
    vol.Required("line_id"): _bounded_int,
})
@websocket_api.async_response
async def session_remove_line(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    try:
        await hass.async_add_executor_job(partial(
            runtime.shopping.remove_line, msg["line_id"]))
    except ShoppingError as err:
        _shopping_error(connection, msg, err)
        return
    await runtime.coordinator.async_request_refresh()
    connection.send_result(msg["id"], {"line_id": msg["line_id"]})


@websocket_api.websocket_command({vol.Required("type"): "home_stock/session/checkout"})
@websocket_api.async_response
async def session_checkout(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    try:
        session = await hass.async_add_executor_job(runtime.shopping.checkout)
    except ShoppingError as err:
        _shopping_error(connection, msg, err)
        return
    await runtime.coordinator.async_request_refresh()
    connection.send_result(msg["id"], session)


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/session/store_line",
    vol.Required("line_id"): _bounded_int,
    vol.Required("location_id"): _bounded_int,
    vol.Optional("best_before"): _iso_date,
})
@websocket_api.async_response
async def session_store_line(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    try:
        result = await hass.async_add_executor_job(partial(
            runtime.shopping.store_line, msg["line_id"],
            location_id=msg["location_id"], best_before=msg.get("best_before")))
    except ShoppingError as err:
        _shopping_error(connection, msg, err)
        return
    await runtime.coordinator.async_request_refresh()
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command({vol.Required("type"): "home_stock/session/close"})
@websocket_api.async_response
async def session_close(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    try:
        session = await hass.async_add_executor_job(runtime.shopping.close)
    except ShoppingError as err:
        _shopping_error(connection, msg, err)
        return
    await runtime.coordinator.async_request_refresh()
    connection.send_result(msg["id"], session)


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
                    product_convert_unit, stock_add, aisles_reorder,
                    session_start, session_current, session_add_line,
                    session_update_line, session_remove_line, session_checkout,
                    session_store_line, session_close):
        websocket_api.async_register_command(hass, command)
