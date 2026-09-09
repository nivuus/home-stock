"""Home Assistant services. Every write refreshes the coordinator on success."""
from __future__ import annotations

import json
import logging
from functools import partial
from typing import Any, Final

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .application import PartsError
from .const import (
    BATTERY_EVENT_KINDS,
    CONF_SHOPPING_LIST_HORIZON_DAYS,
    CONSUME_REASONS,
    DEFAULT_SHOPPING_LIST_HORIZON_DAYS,
    DOMAIN,
    MEAL_SLOT_KEYS,
    REASON_CONSUMPTION,
)
from .domain.stock import InsufficientStock
from .domain.units import UnitError
from .import_grocy import import_catalog
from .import_grocy_equipment import import_grocy_equipment
from .import_grocy_recipes import import_recipes
from .import_grocy_stock import import_stock
from .migration_check import check_migration
from .messages import french_message
from .off.client import BULK_INTERVAL, OffRecord
from .off.ingest import build_article_values
from .storage import repositories as repo
from .validators import (
    acknowledgement_list, bounded_int, bounded_text, finite_float,
    grocy_database_path, iso_date, list_quantity, non_negative_float,
    parts_count, picture_dir, preview,
)

_LOGGER = logging.getLogger(__name__)

# Home Assistant's own cv.positive_int is vol.All(vol.Coerce(int),
# vol.Range(min=0)): it truncates a float silently, accepts a bare JSON
# `true` as 1, and never bounds the top end, so a JSON number like 2**70
# sails through and only fails later, uncaught, when sqlite3 raises
# OverflowError at bind time — the exact hole closed on the websocket
# commands' ids. `_id` keeps cv.positive_int's own range (>= 0) but swaps
# its coercion leg for `bounded_int`, which refuses all three instead.
_id: Final = vol.All(bounded_int, vol.Range(min=0))

# --- lot 7 : la bascule ------------------------------------------------------
# Les trois schémas lisent les validateurs de validators.py, jamais cv.string
# nu sur un chemin. La commande websocket home_stock/migration/check lit
# EXACTEMENT MIGRATION_CHECK_SCHEMA : aucune des deux surfaces n'a le droit
# d'être la plus faible, et une divergence s'ouvre toujours du côté qu'on n'a
# pas testé.
MIGRATION_IMPORT_SCHEMA: Final = vol.Schema({
    vol.Optional("database_path", default="grocy_import.db"): grocy_database_path,
    vol.Optional("apply", default=False): cv.boolean,
})
MIGRATION_RECIPES_SCHEMA: Final = vol.Schema({
    vol.Optional("database_path", default="grocy_import.db"): grocy_database_path,
    vol.Optional("picture_dir", default="media/home_stock"): picture_dir,
    vol.Optional("apply", default=False): cv.boolean,
})
MIGRATION_CHECK_SCHEMA: Final = vol.Schema({
    vol.Optional("database_path", default="grocy_import.db"): grocy_database_path,
    vol.Optional("archive", default=True): cv.boolean,
    vol.Optional("acknowledged", default=list): acknowledgement_list,
})


def _check_migration_for(hass: HomeAssistant, data: dict[str, Any]):
    """Run the checks from wherever they are called — service or websocket.

    Both surfaces call THIS function, so the answer cannot diverge. The paths
    are resolved with `hass.config.path()`: the component never reads outside
    `config/`, which is exactly why copying grocy.db in there is a gesture of
    the procedure.
    """
    entry = _entry(hass)
    return check_migration(
        entry.runtime_data.manager.db,
        hass.config.path(data["database_path"]),
        acknowledged=data["acknowledged"],
        archive=data["archive"],
        picture_dir=hass.config.path("media/home_stock"),
        config_dir=hass.config.path(""),
        archive_dir=hass.config.path(""),
    )


def _iso_datetime(value: Any) -> str:
    """An ISO timestamp whose DATE part is a real calendar date.

    `iso_date` guards the ten leading characters — the part that reaches
    `installed_on` and every `occurred_at[:10]` comparison — and the rest is
    kept as given. A "02/05/2024" typed into a script must be refused here,
    not discovered later by a coordinator refresh that then takes every
    entity unavailable.
    """
    text = bounded_text(value)
    if text is None:
        raise vol.Invalid("expected a timestamp")
    iso_date(text[:10])
    return text

ADD_STOCK_SCHEMA = vol.All(
    vol.Schema({
        vol.Exclusive("article_id", "article"): _id,
        vol.Exclusive("barcode", "article"): cv.string,
        vol.Required("quantity"): finite_float,
        vol.Required("location_id"): _id,
        vol.Optional("best_before"): iso_date,
        vol.Optional("price_per_base_unit"): non_negative_float,
        vol.Optional("packaging_base_quantity"): finite_float,
        vol.Optional("idempotency_key"): bounded_text,
    }),
    # vol.Exclusive above only forbids giving both; without at least one, the
    # service reaches services.add_stock() with neither, tries to resolve
    # `None` as a barcode and answers the confusing "Code-barres None inconnu".
    cv.has_at_least_one_key("article_id", "barcode"),
)
CONSUME_SCHEMA = vol.Schema({
    vol.Required("product_id"): _id,
    vol.Required("quantity"): finite_float,
    vol.Optional("reason", default=REASON_CONSUMPTION): vol.In(CONSUME_REASONS),
    vol.Optional("batch_id"): _id,
    # parts_count, not `_id`: a number of plates is neither an identifier nor
    # a float that may truncate, and the websocket surface refuses exactly the
    # same values. Neither surface may be the weaker one.
    vol.Optional("parts_total"): parts_count,
    vol.Optional("parts_mine"): parts_count,
    vol.Optional("idempotency_key"): bounded_text,
})
BATCH_SCHEMA = vol.Schema({vol.Required("batch_id"): _id})
TRANSFER_SCHEMA = BATCH_SCHEMA.extend({vol.Required("location_id"): _id})
INVENTORY_SCHEMA = vol.Schema({
    vol.Required("article_id"): _id,
    vol.Required("location_id"): _id,
    vol.Required("counted_quantity"): finite_float,
})
QUERY_SCHEMA = vol.Schema({vol.Optional("name"): cv.string})
def _at_least_one_resync_target(value: dict[str, Any]) -> dict[str, Any]:
    """"all" must be affirmatively true to count as a target: `has_at_least_
    one_key` alone would let `{"all": False}` — the field's own unchecked
    state in the UI, with no article_id or product_id either — through as
    if something had been chosen, and silently resync nothing. That is
    exactly the no-op this check exists to refuse, in French rather than
    voluptuous's own generic English.
    """
    if value.get("article_id") is None and value.get("product_id") is None \
            and not value.get("all"):
        raise vol.Invalid(
            "Choisissez un article, un produit ou tout le catalogue à resynchroniser.")
    return value


RESYNC_SCHEMA = vol.Schema(vol.All(
    {
        # All three exclusive: a call naming two of them (an id AND the
        # catalogue box ticked) is refused instead of one silently winning
        # a forty-minute pass the caller may not have meant to start.
        vol.Exclusive("article_id", "resync_target"): _id,
        vol.Exclusive("product_id", "resync_target"): _id,
        vol.Exclusive("all", "resync_target"): cv.boolean,
    },
    _at_least_one_resync_target,
))


# --- lot 3 : recettes, planning, repas -------------------------------------
#
# The rule that governs these five: NEITHER surface may be the weaker one.
# What the websocket refuses, the service refuses too. A service call comes
# from an automation or from voice, and it is every bit as capable of writing
# four portions out of three into an append-only journal.
#
# So the same shared validators are used here as in `websocket_recipes`:
# `finite_float` then a strict bound for servings and portions, `parts_count`
# for the parts, `iso_date` for the day, a `vol.In` on the slot constant.


def _positive_float(value: Any) -> float:
    number = finite_float(value)
    if number <= 0:
        raise vol.Invalid(f"Le nombre doit être supérieur à zéro (reçu : {number}).")
    return number


def _not_negative_float(value: Any) -> float:
    number = finite_float(value)
    if number < 0:
        raise vol.Invalid(f"Le nombre ne peut pas être négatif (reçu : {number}).")
    return number


def _meal_day(value: Any) -> str:
    day = iso_date(value)
    if day is None:
        raise vol.Invalid("Date attendue au format AAAA-MM-JJ.")
    return day


PLAN_MEAL_SCHEMA = vol.Schema({
    vol.Required("day"): _meal_day,
    vol.Required("slot_key"): vol.In(MEAL_SLOT_KEYS),
    vol.Optional("recipe_id"): _id,
    vol.Optional("product_id"): _id,
    vol.Optional("amount"): _positive_float,
    vol.Optional("note"): bounded_text,
    vol.Optional("servings", default=1.0): _positive_float,
})

VALIDATE_MEAL_SCHEMA = vol.Schema({
    vol.Required("meal_id"): _id,
    vol.Required("portions_eaten"): _not_negative_float,
    vol.Optional("servings"): _positive_float,
    vol.Optional("parts_total"): parts_count,
    vol.Optional("parts_mine"): parts_count,
    vol.Optional("skip_ingredient_ids", default=[]): vol.All([_id],
                                                             vol.Length(max=200)),
    # Simulated by DEFAULT, like import_grocy_catalog since lot 0: a service
    # that decrements a stock must not do so on the first exploratory call
    # from the developer tools.
    vol.Optional("dry_run", default=True): cv.boolean,
})

IMPORT_RECIPE_SCHEMA = vol.Schema({
    vol.Optional("source_ref"): bounded_text,
    vol.Optional("query"): bounded_text,
})

ADAPT_RECIPE_SCHEMA = vol.Schema({vol.Required("recipe_id"): _id})

QUERY_MEALS_SCHEMA = vol.Schema({
    vol.Required("start"): _meal_day,
    vol.Required("end"): _meal_day,
    # Lot 6 : la porte du vocal. `vol.In(MEAL_SLOT_KEYS)` et non une liste
    # recopiée — le vocabulaire des créneaux a UN seul propriétaire, `const.py`.
    vol.Optional("slot_key"): vol.In(MEAL_SLOT_KEYS),
})


# --- lot 5 : piles et équipements -------------------------------------------

# `extra_items` and `extra_keep` are validated on the SHAPE OF THE CONTAINER
# only, never item by item. A service that refused a malformed item would make
# the air-purifier's filter task vanish the first time the macro's item shape
# changed; `merge_plan` copies what it does not understand instead. What IS
# refused is a container that is not a list at all — that means the wiring
# itself is broken, and the wiring must then disarm the closing pass, which
# `continue_on_error: true` plus an undefined `stock` already do.
def _plain_list(value: Any) -> list:
    """A real list. NOT `cv.ensure_list`, which wraps a bare string into a
    one-element list — so `extra_items: "pas une liste"` would sail through as
    `["pas une liste"]` and be copied verbatim into todo.maintenance as an
    item nobody can act on."""
    if not isinstance(value, list):
        raise vol.Invalid(f"expected a list, got {preview(value)}")
    return value


MAINTENANCE_PLAN_SCHEMA = vol.Schema({
    vol.Optional("extra_items"): _plain_list,
    vol.Optional("extra_keep"): _plain_list,
})

IMPORT_EQUIPMENT_SCHEMA = vol.Schema({
    vol.Required("database_path"): cv.string,
    vol.Optional("apply", default=False): cv.boolean,
})

# --- lot 4 : liste de courses, ticket, correction ---------------------------
#
# Les bornes vivent dans `validators.py`, une seule fois, et le websocket lit
# les mêmes : aucune des deux surfaces n'a le droit d'être la plus faible.

ADD_TO_LIST_SCHEMA = vol.Schema({
    vol.Optional("product_id"): _id,
    vol.Optional("free_text"): bounded_text,
    vol.Optional("quantity"): list_quantity,
    vol.Optional("note"): bounded_text,
})

REFRESH_LIST_SCHEMA = vol.Schema({
    vol.Optional("horizon_days"): vol.All(bounded_int, vol.Range(min=1, max=60)),
})

QUERY_LIST_SCHEMA = vol.Schema({
    vol.Optional("store_id"): _id,
})

READ_RECEIPT_SCHEMA = vol.Schema({
    vol.Optional("receipt_id"): _id,
})

CORRECT_MOVEMENT_SCHEMA = vol.Schema({
    vol.Required("movement_id"): _id,
})

CORRECT_MEAL_SCHEMA = vol.Schema({
    vol.Required("meal_id"): _id,
})

BATTERY_EVENT_SCHEMA = vol.Schema({
    vol.Required("battery_id"): _id,
    vol.Required("kind"): vol.In(BATTERY_EVENT_KINDS),
    vol.Optional("occurred_at"): _iso_datetime,
    vol.Optional("consume_spare"): cv.boolean,
    vol.Optional("note"): bounded_text,
    vol.Optional("idempotency_key"): bounded_text,
})


def _entry(hass: HomeAssistant):
    """The single loaded entry. Raises if the integration is not set up."""
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        raise HomeAssistantError("Le garde-manger n'est pas configuré.")
    return entries[0]


async def _run(hass: HomeAssistant, work) -> Any:
    """Run a manager call in the executor, translating domain errors.

    The translation is `messages.french_message`, the very same vocabulary
    the websocket surface uses (websocket_api._send_domain_error): one
    English exception must not become two different French sentences
    depending on whether the panel or a script asked. Re-raising `str(error)`
    here used to leak the English original ("unknown article 5") into a
    notification and a voice answer.

    `vol.Invalid` is in the list for that same rule. The schemas run before
    the handler, but the invariants that bind two fields together
    (`check_battery_fields`, `check_battery_event`) are enforced INSIDE the
    manager, where they can see the stored row — so they raise here, not at
    schema time. Without this, "a primary battery cannot be charged" reached
    a script as a raw English `voluptuous.error.Invalid` while the websocket
    surface answered a French sentence: exactly the asymmetry this lot forbids.

    `LookupError` is caught alongside the `ValueError` family for the same
    reason: `repo.product_base_unit` raises it for an unknown product id
    (StockManager.consume's FIFO path calls it directly with the caller's
    own `product_id`, before any existence check), and the websocket surface
    already catches it (`websocket_api._send_domain_error`'s callers list it
    explicitly). Missing it here meant a well-formed but nonexistent
    `product_id` — a deleted product an automation still references — raised
    a bare Python `LookupError` straight into the Home Assistant log instead
    of a French refusal: the exact weaker-surface asymmetry this lot's rule
    forbids.
    """
    try:
        return await hass.async_add_executor_job(work)
    except (InsufficientStock, LookupError, PartsError, UnitError, ValueError,
            vol.Invalid) as error:
        raise HomeAssistantError(french_message(error)) from error
    except OverflowError as error:
        # Backstop, not the primary defence: ADD_STOCK_SCHEMA/CONSUME_SCHEMA/
        # etc. already validate every numeric field through bounded_int/
        # finite_float before a call ever reaches here. Caught anyway so a
        # gap in that validation answers a French refusal instead of
        # "Unknown error".
        raise HomeAssistantError("Valeur numérique hors limites.") from error


# Written unconditionally by _write_resync: a human can protect a value,
# never the fact that a sync happened at all or what it answered.
_NEVER_PROTECTED: Final = frozenset({"off_synced_at", "off_raw"})


def _write_resync(runtime, article_id: int, record: OffRecord) -> None:
    """Refresh one article from a freshly fetched OFF record.

    Every column a human corrected (`article.manual_fields`) is left
    untouched — that is the entire reason that column exists: a resync must
    never silently overwrite what a person already fixed by hand, even when
    OFF now disagrees with them.

    When `manual_fields` itself cannot be read (malformed JSON, or valid
    JSON that is not a list — a hand-edited row, a bug elsewhere), we
    cannot tell what a human protected. The safe reading is "everything is
    protected": this article's write is skipped entirely, with a warning
    naming it, rather than risk overwriting a correction we cannot
    identify. `run()` below still moves on to the next card either way —
    one unreadable row must not be why a forty-minute pass never reaches
    the other 298 products.
    """
    with runtime.manager.db.write() as conn:
        article = repo.get_article(conn, article_id)
        if article is None:
            # The article was deleted (or never existed) between the
            # barcode list being read and this card's turn coming up in the
            # BULK_INTERVAL-spaced walk — nothing left to refresh.
            return
        product = repo.get_product(conn, article["product_id"])
        if product is None:
            return

        try:
            raw_manual = json.loads(article["manual_fields"] or "[]")
            if not isinstance(raw_manual, list):
                raise ValueError("manual_fields is not a JSON list")
            protected = set(raw_manual)
        except (TypeError, ValueError):
            _LOGGER.warning(
                "home_stock: article %s has an unreadable manual_fields "
                "value (%r); skipping its OFF resync rather than risk "
                "overwriting a human correction we cannot identify",
                article_id, article["manual_fields"],
            )
            return

        # build_article_values (off/ingest.py) is the same mapping
        # article/create's own scan-time ingestion uses: the value-dropping
        # and off_raw size ceiling apply here exactly as they do there, and
        # it never hands back a None for a column OFF simply did not answer
        # this time — see its own docstring for why a resync must be able
        # to fill a gap or correct a value, but never erase one.
        ingest = build_article_values(
            record.product, record.off_source, product["base_unit"],
            synced_at=dt_util.utcnow().replace(microsecond=0, tzinfo=None).isoformat())
        values = dict(ingest.values)
        # A human can protect a value, never the fact that a resync ran:
        # off_synced_at/off_raw are excluded from the pop below even if a
        # hand-edited (or corrupted) manual_fields value happened to name
        # them — the panel itself can never put them there (it validates
        # against ARTICLE_EDITABLE, which does not include either), but
        # this function must not trust that path is the only way in.
        for column in protected - _NEVER_PROTECTED:
            values.pop(column, None)

        repo.update_article_fields(conn, article_id, values)


def async_register_services(hass: HomeAssistant) -> None:
    """Register once; a reload of the entry must not register twice."""
    if hass.services.has_service(DOMAIN, "add_stock"):
        return

    async def add_stock(call: ServiceCall) -> None:
        entry = _entry(hass)
        manager = entry.runtime_data.manager
        article_id = call.data.get("article_id")
        if article_id is None:
            code = call.data.get("barcode")
            article = await hass.async_add_executor_job(
                partial(repo.find_article_by_barcode, manager.db.read(), code)
            )
            if article is None:
                raise HomeAssistantError(
                    f"Code-barres {code} inconnu. La création d'un article à partir"
                    " d'un code-barres arrive avec le scan (lot 1)."
                )
            article_id = article["id"]
        await _run(hass, partial(
            manager.add_stock,
            article_id=article_id,
            quantity=call.data["quantity"],
            location_id=call.data["location_id"],
            best_before=call.data.get("best_before"),
            price_per_base_unit=call.data.get("price_per_base_unit"),
            packaging_base_quantity=call.data.get("packaging_base_quantity"),
            idempotency_key=call.data.get("idempotency_key"),
        ))
        await entry.runtime_data.coordinator.async_request_refresh()

    async def consume(call: ServiceCall) -> None:
        entry = _entry(hass)
        manager = entry.runtime_data.manager
        parts_total = call.data.get("parts_total")
        parts_mine = call.data.get("parts_mine")
        batch_id = call.data.get("batch_id")
        if batch_id is not None:
            # product_id is still passed for the consistency check: a batch
            # belonging to the wrong product must be refused, not silently
            # consumed — the same guard the websocket surface relies on.
            work = partial(
                manager.consume_batch, batch_id,
                product_id=call.data["product_id"],
                quantity=call.data["quantity"],
                reason=call.data["reason"],
                parts_total=parts_total, parts_mine=parts_mine,
                idempotency_key=call.data.get("idempotency_key"),
            )
        else:
            work = partial(
                manager.consume,
                product_id=call.data["product_id"],
                quantity=call.data["quantity"],
                reason=call.data["reason"],
                parts_total=parts_total, parts_mine=parts_mine,
                idempotency_key=call.data.get("idempotency_key"),
            )
        await _run(hass, work)
        await entry.runtime_data.coordinator.async_request_refresh()

    async def open_batch(call: ServiceCall) -> None:
        entry = _entry(hass)
        await _run(hass, partial(entry.runtime_data.manager.open_batch,
                                 call.data["batch_id"]))
        await entry.runtime_data.coordinator.async_request_refresh()

    async def transfer_batch(call: ServiceCall) -> None:
        entry = _entry(hass)
        await _run(hass, partial(entry.runtime_data.manager.transfer_batch,
                                 call.data["batch_id"], call.data["location_id"]))
        await entry.runtime_data.coordinator.async_request_refresh()

    async def adjust_inventory(call: ServiceCall) -> None:
        entry = _entry(hass)
        await _run(hass, partial(
            entry.runtime_data.manager.adjust_inventory,
            article_id=call.data["article_id"],
            location_id=call.data["location_id"],
            counted_quantity=call.data["counted_quantity"],
        ))
        await entry.runtime_data.coordinator.async_request_refresh()

    async def query_stock(call: ServiceCall) -> ServiceResponse:
        entry = _entry(hass)
        products = await _run(hass, partial(
            entry.runtime_data.manager.query_stock, name=call.data.get("name")
        ))
        return {"products": products}

    async def export_journal(call: ServiceCall) -> ServiceResponse:
        entry = _entry(hass)
        movements = await _run(hass, entry.runtime_data.manager.export_journal)
        return {"movements": movements}

    async def import_grocy_catalog(call: ServiceCall) -> ServiceResponse:
        entry = _entry(hass)
        path = hass.config.path(call.data["path"])
        apply = call.data["apply"]
        report = await _run(hass, partial(
            import_catalog, entry.runtime_data.manager.db, path, apply=apply,
        ))
        # A dry run (apply=False) never writes: refreshing the coordinator would
        # only waste a read, like query_stock/export_journal never do either.
        if apply:
            await entry.runtime_data.coordinator.async_request_refresh()
        return report.as_dict()

    # --- lot 7 : la bascule ------------------------------------------------
    # Même forme que import_grocy_catalog, et même asymétrie assumée : les
    # deux IMPORTS n'ont pas de jumeau websocket. Un import de masse se lance
    # depuis Outils de développement, UNE fois, en lisant son rapport en
    # entier. Le CONTRÔLE, lui, se relance vingt fois pendant la bascule, une
    # main dans le placard et l'autre sur le téléphone : il lui faut le
    # panneau, et il a donc sa commande websocket.

    async def import_grocy_stock_service(call: ServiceCall) -> ServiceResponse:
        entry = _entry(hass)
        path = hass.config.path(call.data["database_path"])
        apply = call.data["apply"]
        report = await _run(hass, partial(
            import_stock, entry.runtime_data.manager.db, path, apply=apply))
        if apply:
            await entry.runtime_data.coordinator.async_request_refresh()
        return report.as_dict()

    async def import_grocy_recipes_service(call: ServiceCall) -> ServiceResponse:
        entry = _entry(hass)
        path = hass.config.path(call.data["database_path"])
        dossier = hass.config.path(call.data["picture_dir"])
        apply = call.data["apply"]
        report = await _run(hass, partial(
            import_recipes, entry.runtime_data.manager.db, path,
            picture_dir=dossier, apply=apply))
        if apply:
            await entry.runtime_data.coordinator.async_request_refresh()
        return report.as_dict()

    async def check_grocy_migration_service(call: ServiceCall) -> ServiceResponse:
        report = await _run(hass, partial(
            _check_migration_for, hass, call.data))
        return report.as_dict()

    async def resync_off(call: ServiceCall) -> None:
        """Refresh articles from OFF, one every BULK_INTERVAL seconds.

        Runs as a background task: a full catalogue pass is roughly forty
        minutes at the rate OFF tolerates (BULK_INTERVAL between cards), and
        no service call should hold that long — the call itself only reads
        which barcodes are concerned and returns. Refuses to start a second
        pass on top of a running one: Open Food Facts' own rate limit is
        measured per client, not per request, so two passes at once would
        double the request rate against it.

        The slot is claimed by setting `resync_in_progress` synchronously,
        with no `await` between the check and the claim: two automations
        firing at the same moment both reach this handler, and cooperative
        asyncio only guarantees exclusivity across a stretch of code with no
        suspension point in it. Claiming it only after the barcode-list read
        below (an earlier version of this fix did exactly that) leaves a
        window where both calls read `False` before either writes `True` —
        both start a pass, and the field then only names the second, making
        the first invisible to the guard for the rest of its forty minutes.

        Tied to the config entry (`entry.async_create_background_task`, not
        `hass.async_create_background_task`) so unloading the entry mid-pass
        cancels it instead of leaving it writing to a database that is about
        to close.
        """
        entry = _entry(hass)
        runtime = entry.runtime_data
        if runtime.resync_in_progress:
            raise HomeAssistantError(
                "Une resynchronisation Open Food Facts est déjà en cours.")
        runtime.resync_in_progress = True

        try:
            codes = await hass.async_add_executor_job(partial(
                repo.barcodes_to_resync, runtime.manager.db.read(),
                article_id=call.data.get("article_id"),
                product_id=call.data.get("product_id"),
                everything=call.data.get("all", False),
            ))
        except Exception:
            # Claimed the slot above but never actually started a pass:
            # release it again so a transient read failure does not lock
            # resync_off out forever.
            runtime.resync_in_progress = False
            raise

        async def run() -> None:
            try:
                for index, (code, article_id) in enumerate(codes):
                    if index:
                        await runtime.resync_sleeper(BULK_INTERVAL)
                    try:
                        result = await runtime.off_client.lookup_with_retry(code)
                        if result.record is None:
                            continue
                        await hass.async_add_executor_job(partial(
                            _write_resync, runtime, article_id, result.record))
                    except Exception:  # noqa: BLE001 - deliberately catches
                        # everything: a single bad card (a malformed OFF
                        # answer, a transient database error from a mid-pass
                        # reload, a bug this review round did not
                        # anticipate) must not be why the other ~298
                        # products in the catalogue never get their turn.
                        # Logged with the barcode so the failure is
                        # findable, not silent.
                        _LOGGER.exception(
                            "home_stock: resync_off failed for barcode %s (article %s)",
                            code, article_id)
                await runtime.coordinator.async_request_refresh()
            finally:
                # Runs on normal completion, on a per-card exception already
                # caught above, and on cancellation (the entry unloading
                # mid-pass) alike: the slot must never stay claimed after
                # the pass that claimed it is actually gone.
                runtime.resync_in_progress = False

        entry.async_create_background_task(hass, run(), "home_stock resync_off")

    async def maintenance_plan(call: ServiceCall) -> ServiceResponse:
        """The plan `maintenance_sync_taches` reconciles todo.maintenance from.

        Never raises when the database is unwell: `StockManager.maintenance_plan`
        answers `complete: False` instead, and the automation's `peut_fermer`
        flag reads that. The only thing that makes THIS raise is a
        badly-SHAPED argument, because that means the wiring is broken.
        """
        coordinator = _entry(hass).runtime_data.coordinator
        return await coordinator.async_maintenance_plan(
            extra_items=call.data.get("extra_items"),
            extra_keep=call.data.get("extra_keep"))

    async def import_grocy_equipment_service(call: ServiceCall) -> ServiceResponse:
        """Copy Grocy's batteries and equipment over. Dry run by default.

        The registry sweep and the states both have to be read on the event
        loop, so they are gathered here and handed to a pure function that
        knows nothing about `hass` — which is also what makes the whole import
        testable without starting Home Assistant.
        """
        runtime = _entry(hass).runtime_data
        registry = er.async_get(hass)
        registry_rows = [
            {"entity_registry_id": entry.id, "entity_id": entry.entity_id,
             "device_id": entry.device_id, "name": entry.name or entry.original_name,
             "model": None}
            for entry in registry.entities.values()
            if entry.domain == "sensor"
            and (entry.device_class or entry.original_device_class) == "battery"
        ]
        states = [
            {"entity_id": state.entity_id, "state": state.state,
             "attributes": dict(state.attributes)}
            for state in hass.states.async_all("sensor")
        ]
        report = await _run(hass, partial(
            import_grocy_equipment, runtime.manager.db, call.data["database_path"],
            hass_states=states, registry_rows=registry_rows,
            apply=call.data["apply"]))
        if call.data["apply"]:
            await runtime.coordinator.async_request_refresh()
        return report.as_dict()

    async def record_battery_event(call: ServiceCall) -> None:
        runtime = _entry(hass).runtime_data
        await _run(hass, partial(
            runtime.manager.record_battery_event, call.data["battery_id"],
            kind=call.data["kind"], occurred_at=call.data.get("occurred_at"),
            consume_spare=call.data.get("consume_spare"),
            note=call.data.get("note"),
            idempotency_key=call.data.get("idempotency_key")))
        await runtime.coordinator.async_request_refresh()

    hass.services.async_register(DOMAIN, "add_stock", add_stock, schema=ADD_STOCK_SCHEMA)
    hass.services.async_register(DOMAIN, "consume", consume, schema=CONSUME_SCHEMA)
    hass.services.async_register(DOMAIN, "open_batch", open_batch, schema=BATCH_SCHEMA)
    hass.services.async_register(DOMAIN, "transfer_batch", transfer_batch,
                                 schema=TRANSFER_SCHEMA)
    hass.services.async_register(DOMAIN, "adjust_inventory", adjust_inventory,
                                 schema=INVENTORY_SCHEMA)
    hass.services.async_register(DOMAIN, "query_stock", query_stock, schema=QUERY_SCHEMA,
                                 supports_response=SupportsResponse.ONLY)
    hass.services.async_register(DOMAIN, "export_journal", export_journal,
                                 schema=vol.Schema({}),
                                 supports_response=SupportsResponse.ONLY)
    hass.services.async_register(
        DOMAIN, "import_grocy_catalog", import_grocy_catalog,
        schema=vol.Schema({
            vol.Optional("path", default="grocy_import.db"): cv.string,
            vol.Optional("apply", default=False): cv.boolean,
        }),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN, "import_grocy_stock", import_grocy_stock_service,
        schema=MIGRATION_IMPORT_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN, "import_grocy_recipes", import_grocy_recipes_service,
        schema=MIGRATION_RECIPES_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN, "check_grocy_migration", check_grocy_migration_service,
        schema=MIGRATION_CHECK_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    # --- lot 3 -------------------------------------------------------------

    async def plan_meal(call: ServiceCall) -> None:
        """Put a meal on a day, from YAML or from voice."""
        runtime = _entry(hass).runtime_data
        await _run(hass, partial(
            runtime.manager.plan_meal, day=call.data["day"],
            slot_key=call.data["slot_key"], recipe_id=call.data.get("recipe_id"),
            product_id=call.data.get("product_id"), amount=call.data.get("amount"),
            note=call.data.get("note"), servings=call.data["servings"]))
        await runtime.coordinator.async_request_refresh()

    async def validate_meal(call: ServiceCall) -> ServiceResponse:
        """Cook then eat — but SIMULATE unless `dry_run: false` is passed."""
        runtime = _entry(hass).runtime_data
        result = await _run(hass, partial(
            runtime.manager.validate_meal, call.data["meal_id"],
            portions_eaten=call.data["portions_eaten"],
            servings=call.data.get("servings"),
            parts_total=call.data.get("parts_total"),
            parts_mine=call.data.get("parts_mine"),
            skip_ingredient_ids=call.data["skip_ingredient_ids"],
            dry_run=call.data["dry_run"]))
        if not call.data["dry_run"]:
            await runtime.coordinator.async_request_refresh()
        return result

    async def import_recipe(call: ServiceCall) -> ServiceResponse:
        """Import one card, named by reference or found by a search.

        Calls the SAME orchestration the websocket does
        (`websocket_recipes.async_import_recipe`), so the two surfaces cannot
        drift into importing the same card differently. The only difference is
        upstream: this one may resolve a free-text search into a reference
        first, which the panel does in two steps of its own.
        """
        from .websocket_recipes import async_import_recipe

        runtime = _entry(hass).runtime_data
        source_ref = call.data.get("source_ref")
        if not source_ref:
            source = runtime.recipe_source
            hits = await source.search(call.data.get("query") or "") if source else []
            if not hits:
                return {"imported": False,
                        "message": "Aucune recette trouvée à la source."}
            source_ref = hits[0].source_ref
        result = await async_import_recipe(hass, runtime, source_ref)
        if result is None:
            return {"imported": False,
                    "message": "Cette recette est introuvable à la source."}
        await runtime.coordinator.async_request_refresh()
        return {"imported": True, **result}

    async def adapt_recipe(call: ServiceCall) -> None:
        """Re-run the adaptation of a recipe imported without an agent."""
        from .websocket_recipes import async_import_recipe

        runtime = _entry(hass).runtime_data
        recipe = await _run(hass, partial(
            repo.get_recipe, runtime.manager.db.read(), call.data["recipe_id"]))
        if recipe is None:
            raise HomeAssistantError(
                f"Recette {call.data['recipe_id']} introuvable.")
        if not recipe["source_ref"]:
            raise HomeAssistantError(
                "Cette recette n'a pas été importée : il n'y a rien à réadapter.")
        await async_import_recipe(hass, runtime, recipe["source_ref"])
        await runtime.coordinator.async_request_refresh()

    async def query_meals(call: ServiceCall) -> ServiceResponse:
        """What is planned over a range. The counterpart of query_stock.

        A response service rather than an entity: this is what will answer
        "what are we eating tonight?" at lot 6, without creating one entity
        per meal — the same reasoning lot 0 applied to query_stock.
        """
        runtime = _entry(hass).runtime_data
        meals = await _run(hass, partial(
            runtime.manager.list_meals, call.data["start"], call.data["end"]))
        # Filtré ici et non dans le dépôt : `list_meals` rend déjà la plage, et
        # une variante de requête SQL ouvrirait une SECONDE façon de lire un
        # planning pour quelques dizaines de lignes.
        slot = call.data.get("slot_key")
        if slot is not None:
            meals = [m for m in meals if m["slot_key"] == slot]
        return {"meals": meals}

    hass.services.async_register(DOMAIN, "resync_off", resync_off, schema=RESYNC_SCHEMA)
    hass.services.async_register(DOMAIN, "plan_meal", plan_meal,
                                 schema=PLAN_MEAL_SCHEMA)
    hass.services.async_register(DOMAIN, "validate_meal", validate_meal,
                                 schema=VALIDATE_MEAL_SCHEMA,
                                 supports_response=SupportsResponse.OPTIONAL)
    hass.services.async_register(DOMAIN, "import_recipe", import_recipe,
                                 schema=IMPORT_RECIPE_SCHEMA,
                                 supports_response=SupportsResponse.OPTIONAL)
    hass.services.async_register(DOMAIN, "adapt_recipe", adapt_recipe,
                                 schema=ADAPT_RECIPE_SCHEMA)
    hass.services.async_register(DOMAIN, "query_meals", query_meals,
                                 schema=QUERY_MEALS_SCHEMA,
                                 supports_response=SupportsResponse.ONLY)
    hass.services.async_register(DOMAIN, "maintenance_plan", maintenance_plan,
                                 schema=MAINTENANCE_PLAN_SCHEMA,
                                 supports_response=SupportsResponse.ONLY)
    hass.services.async_register(DOMAIN, "record_battery_event", record_battery_event,
                                 schema=BATTERY_EVENT_SCHEMA)
    hass.services.async_register(DOMAIN, "import_grocy_equipment",
                                 import_grocy_equipment_service,
                                 schema=IMPORT_EQUIPMENT_SCHEMA,
                                 supports_response=SupportsResponse.ONLY)

    # --- lot 4 -------------------------------------------------------------
    # Enregistrés EN FIN, comme les entrées de `services.yaml` : ce fichier
    # est allongé par un autre lot en parallèle.

    async def add_to_shopping_list(call: ServiceCall) -> ServiceResponse:
        """La porte du vocal : « Bleuenn, ajoute du beurre à la liste ».

        Une charge minimale — juste un texte — doit passer. Exiger un
        `product_id` ici reviendrait à demander à quelqu'un qui parle de
        connaître l'identifiant d'une ligne de catalogue.
        """
        runtime = _entry(hass).runtime_data
        if call.data.get("product_id") is None and not call.data.get("free_text"):
            raise HomeAssistantError(french_message(
                ValueError("a shopping list line needs a product or a text")))
        result = await _run(hass, partial(
            runtime.manager.add_to_shopping_list,
            product_id=call.data.get("product_id"),
            free_text=call.data.get("free_text"),
            quantity=call.data.get("quantity"),
            note=call.data.get("note")))
        await runtime.coordinator.async_request_refresh()
        return result

    async def refresh_shopping_list(call: ServiceCall) -> None:
        runtime = _entry(hass).runtime_data
        horizon = call.data.get(
            "horizon_days",
            _entry(hass).options.get(CONF_SHOPPING_LIST_HORIZON_DAYS,
                                     DEFAULT_SHOPPING_LIST_HORIZON_DAYS))
        await _run(hass, partial(runtime.manager.reconcile_shopping_list,
                                 today=dt_util.now().date(), horizon_days=horizon))
        await runtime.coordinator.async_request_refresh()

    async def query_shopping_list(call: ServiceCall) -> ServiceResponse:
        """« Qu'est-ce qu'il faut acheter ? », sans créer d'entité.

        `SupportsResponse.ONLY`, comme `query_stock` : une entité par ligne de
        liste serait une entité par produit sous son seuil, qui va et vient.
        """
        runtime = _entry(hass).runtime_data
        rows = await _run(hass, partial(runtime.manager.shopping_list,
                                        store_id=call.data.get("store_id"),
                                        include_checked=False))
        by_aisle: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            aisle = row.get("aisle_name") or "Sans rayon"
            by_aisle.setdefault(aisle, []).append({
                "id": row["id"],
                "name": row["product_name"] or row["free_text"],
                "quantity": row["quantity"],
                "base_unit": row["base_unit"],
                "reasons": [claim["detail"] for claim in row.get("claims") or ()
                            if claim.get("detail")],
            })
        estimate = await _run(hass, runtime.manager.list_estimate)
        return {"items": by_aisle, "count": len(rows), "estimate": estimate}

    async def read_receipt(call: ServiceCall) -> ServiceResponse:
        """Relance la lecture d'un ticket — celui qu'on nomme, ou le dernier
        en échec. Sans argument, c'est le geste qu'on fait le lendemain matin
        quand le réseau du parking était mauvais."""
        runtime = _entry(hass).runtime_data
        receipt_id = call.data.get("receipt_id")
        if receipt_id is None:
            pending = await _run(hass, partial(
                repo.pending_receipts, runtime.manager.db.read()))
            if not pending:
                raise HomeAssistantError("Aucun ticket en attente de lecture.")
            receipt_id = int(pending[0]["id"])
        row = await _run(hass, partial(repo.get_receipt,
                                       runtime.manager.db.read(), receipt_id))
        if row is None:
            raise HomeAssistantError(
                french_message(LookupError(f"unknown receipt {receipt_id}")))
        from .websocket_receipts import _perform_read
        await _perform_read(hass, runtime, receipt_id)
        await runtime.coordinator.async_request_refresh()
        after = await _run(hass, partial(repo.get_receipt,
                                         runtime.manager.db.read(), receipt_id))
        return {"receipt_id": receipt_id, "state": after["state"],
                "error": after["error"], "lines": len(after["lines"])}

    async def correct_movement(call: ServiceCall) -> ServiceResponse:
        runtime = _entry(hass).runtime_data
        result = await _run(hass, partial(runtime.manager.correct_movement,
                                          call.data["movement_id"]))
        await runtime.coordinator.async_request_refresh()
        return result

    async def correct_meal(call: ServiceCall) -> ServiceResponse:
        runtime = _entry(hass).runtime_data
        result = await _run(hass, partial(runtime.manager.correct_meal,
                                          call.data["meal_id"]))
        await runtime.coordinator.async_request_refresh()
        return result

    hass.services.async_register(DOMAIN, "add_to_shopping_list",
                                 add_to_shopping_list, schema=ADD_TO_LIST_SCHEMA,
                                 supports_response=SupportsResponse.OPTIONAL)
    hass.services.async_register(DOMAIN, "refresh_shopping_list",
                                 refresh_shopping_list, schema=REFRESH_LIST_SCHEMA)
    hass.services.async_register(DOMAIN, "query_shopping_list",
                                 query_shopping_list, schema=QUERY_LIST_SCHEMA,
                                 supports_response=SupportsResponse.ONLY)
    hass.services.async_register(DOMAIN, "read_receipt", read_receipt,
                                 schema=READ_RECEIPT_SCHEMA,
                                 supports_response=SupportsResponse.OPTIONAL)
    hass.services.async_register(DOMAIN, "correct_movement", correct_movement,
                                 schema=CORRECT_MOVEMENT_SCHEMA,
                                 supports_response=SupportsResponse.OPTIONAL)
    hass.services.async_register(DOMAIN, "correct_meal", correct_meal,
                                 schema=CORRECT_MEAL_SCHEMA,
                                 supports_response=SupportsResponse.OPTIONAL)
