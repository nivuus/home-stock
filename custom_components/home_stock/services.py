"""Home Assistant services. Every write refreshes the coordinator on success."""
from __future__ import annotations

from functools import partial
from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, REASON_CONSUMPTION, REASON_EXPIRED, REASON_WASTE
from .domain.stock import InsufficientStock
from .domain.units import UnitError
from .import_grocy import import_catalog
from .storage import repositories as repo

# Reasons a "consume" call may legitimately carry — the same three the
# services.yaml selector offers. The other three reasons (purchase, inventory,
# transfer) are written exclusively by add_stock/adjust_inventory/transfer_batch;
# letting them through here would tag a negative-quantity movement with a
# reason that COUNTED_REASONS does not track, silently under-counting the
# kcal/cost totals for stock that really did leave the pantry.
CONSUME_REASONS = (REASON_CONSUMPTION, REASON_WASTE, REASON_EXPIRED)

ADD_STOCK_SCHEMA = vol.Schema({
    vol.Exclusive("article_id", "article"): cv.positive_int,
    vol.Exclusive("barcode", "article"): cv.string,
    vol.Required("quantity"): vol.Coerce(float),
    vol.Required("location_id"): cv.positive_int,
    vol.Optional("best_before"): cv.string,
    vol.Optional("price_per_base_unit"): vol.Coerce(float),
    vol.Optional("packaging_base_quantity"): vol.Coerce(float),
    vol.Optional("idempotency_key"): cv.string,
})
CONSUME_SCHEMA = vol.Schema({
    vol.Required("product_id"): cv.positive_int,
    vol.Required("quantity"): vol.Coerce(float),
    vol.Optional("reason", default=REASON_CONSUMPTION): vol.In(CONSUME_REASONS),
    vol.Optional("idempotency_key"): cv.string,
})
BATCH_SCHEMA = vol.Schema({vol.Required("batch_id"): cv.positive_int})
TRANSFER_SCHEMA = BATCH_SCHEMA.extend({vol.Required("location_id"): cv.positive_int})
INVENTORY_SCHEMA = vol.Schema({
    vol.Required("article_id"): cv.positive_int,
    vol.Required("location_id"): cv.positive_int,
    vol.Required("counted_quantity"): vol.Coerce(float),
})
QUERY_SCHEMA = vol.Schema({vol.Optional("name"): cv.string})


def _entry(hass: HomeAssistant):
    """The single loaded entry. Raises if the integration is not set up."""
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        raise HomeAssistantError("Le garde-manger n'est pas configuré.")
    return entries[0]


async def _run(hass: HomeAssistant, work) -> Any:
    """Run a manager call in the executor, translating domain errors."""
    try:
        return await hass.async_add_executor_job(work)
    except InsufficientStock as error:
        raise HomeAssistantError(
            f"Stock insuffisant : {error.requested} demandé, {error.available} disponible."
        ) from error
    except (UnitError, ValueError) as error:
        raise HomeAssistantError(str(error)) from error


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
