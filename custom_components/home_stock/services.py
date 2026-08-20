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
from homeassistant.util import dt as dt_util

from .const import DOMAIN, REASON_CONSUMPTION, REASON_EXPIRED, REASON_WASTE
from .domain.stock import InsufficientStock
from .domain.units import UnitError
from .import_grocy import import_catalog
from .messages import french_message
from .off.client import BULK_INTERVAL, OffRecord
from .off.ingest import build_article_values
from .storage import repositories as repo
from .validators import (
    bounded_int, bounded_text, finite_float, iso_date, non_negative_float,
)

_LOGGER = logging.getLogger(__name__)

# Reasons a "consume" call may legitimately carry — the same three the
# services.yaml selector offers. The other three reasons (purchase, inventory,
# transfer) are written exclusively by add_stock/adjust_inventory/transfer_batch;
# letting them through here would tag a negative-quantity movement with a
# reason that repo.totals_between/journal_entries/counted_movements do not
# track, silently under-counting the kcal, cost or cost_waste totals for
# stock that really did leave the pantry.
CONSUME_REASONS = (REASON_CONSUMPTION, REASON_WASTE, REASON_EXPIRED)

# Home Assistant's own cv.positive_int is vol.All(vol.Coerce(int),
# vol.Range(min=0)): it truncates a float silently, accepts a bare JSON
# `true` as 1, and never bounds the top end, so a JSON number like 2**70
# sails through and only fails later, uncaught, when sqlite3 raises
# OverflowError at bind time — the exact hole closed on the websocket
# commands' ids. `_id` keeps cv.positive_int's own range (>= 0) but swaps
# its coercion leg for `bounded_int`, which refuses all three instead.
_id: Final = vol.All(bounded_int, vol.Range(min=0))

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
    """
    try:
        return await hass.async_add_executor_job(work)
    except InsufficientStock as error:
        raise HomeAssistantError(
            f"Stock insuffisant : {error.requested} demandé, {error.available} disponible."
        ) from error
    except (UnitError, ValueError) as error:
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
        await _run(hass, partial(
            entry.runtime_data.manager.consume,
            product_id=call.data["product_id"],
            quantity=call.data["quantity"],
            reason=call.data["reason"],
            idempotency_key=call.data.get("idempotency_key"),
        ))
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
    hass.services.async_register(DOMAIN, "resync_off", resync_off, schema=RESYNC_SCHEMA)
