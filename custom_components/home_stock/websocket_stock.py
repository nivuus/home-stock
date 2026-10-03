"""home_stock/stock/add and home_stock/stock/consume, in their own module.

Moved out of `websocket_api.py` unchanged (nivuus/home-stock#9: that module is
over 1800 lines and its lot sections are the seams to split it along). Both
commands are still registered by `websocket_api.async_register_websocket`, at
the same place in its list, so the command contract does not move.

The shared helpers and value validators are IMPORTED from `websocket_api`,
never copied, like `websocket_batteries` does: one error translator, one set
of bounds.
"""
from __future__ import annotations

import sqlite3
from functools import partial

import voluptuous as vol
from homeassistant.components import websocket_api

from .application import PartsError
from .const import CONSUME_REASONS, REASON_CONSUMPTION
from .domain.stock import InsufficientStock
from .domain.units import UnitError
from .occurred_at import past_moment
from .websocket_api import (
    _NON_NEGATIVE_FLOAT,
    _NON_NEGATIVE_ID,
    _PARTS,
    _bounded_int,
    _bounded_text,
    _finite_float,
    _iso_date,
    _runtime,
    _send_domain_error,
    _send_integrity_error,
    _send_not_loaded,
)


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/stock/add",
    vol.Required("article_id"): _bounded_int,
    vol.Required("quantity"): _finite_float,
    vol.Required("location_id"): _bounded_int,
    vol.Optional("best_before"): _iso_date,
    vol.Optional("price_per_base_unit"): _NON_NEGATIVE_FLOAT,
    vol.Optional("idempotency_key"): _bounded_text,
    # When it was really put away: offset ISO 8601, past, stored as naive UTC.
    vol.Optional("occurred_at"): past_moment,
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
            occurred_at=msg.get("occurred_at"),
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
    vol.Required("type"): "home_stock/stock/consume",
    # _NON_NEGATIVE_ID, not the bare _bounded_int used elsewhere in this
    # file for an id that is range-checked further down (e.g. product/get's
    # own product_id): no real row ever has a negative id, and the services
    # surface (services.CONSUME_SCHEMA's own `_id`) already refused one.
    # Neither surface may be the weaker one (correction round 1).
    vol.Required("product_id"): _NON_NEGATIVE_ID,
    vol.Required("quantity"): _finite_float,
    vol.Optional("reason", default=REASON_CONSUMPTION): vol.In(CONSUME_REASONS),
    vol.Optional("batch_id"): _NON_NEGATIVE_ID,
    vol.Optional("parts_total"): _PARTS,
    vol.Optional("parts_mine"): _PARTS,
    vol.Optional("idempotency_key"): _bounded_text,
    # When it was really eaten or thrown away: offset ISO 8601, past, stored
    # as naive UTC — the food day and its kcal follow this, not the call.
    vol.Optional("occurred_at"): past_moment,
})
@websocket_api.async_response
async def stock_consume(hass, connection, msg) -> None:
    """Declare that something was eaten, thrown away, or found expired.

    With a batch_id, that precise batch is taken from — the panel's "manger"
    screen always targets the batch FIFO would pick, and says so. Without one,
    the consumption walks the batches in FIFO order and may span several.
    product_id stays required either way: the pair is checked rather than one
    of the two being trusted.
    """
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return

    parts = (msg.get("parts_total"), msg.get("parts_mine"))
    try:
        if "batch_id" in msg:
            result = await hass.async_add_executor_job(partial(
                runtime.manager.consume_batch, msg["batch_id"],
                product_id=msg["product_id"], quantity=msg["quantity"],
                reason=msg["reason"], parts_total=parts[0], parts_mine=parts[1],
                occurred_at=msg.get("occurred_at"),
                idempotency_key=msg.get("idempotency_key")))
            movement_ids = [result]
        else:
            movement_ids = await hass.async_add_executor_job(partial(
                runtime.manager.consume, product_id=msg["product_id"],
                quantity=msg["quantity"], reason=msg["reason"],
                parts_total=parts[0], parts_mine=parts[1],
                occurred_at=msg.get("occurred_at"),
                idempotency_key=msg.get("idempotency_key")))
    except (LookupError, PartsError, InsufficientStock, UnitError, ValueError,
            OverflowError) as err:
        _send_domain_error(connection, msg["id"], err)
        return
    except sqlite3.IntegrityError as err:
        _send_integrity_error(connection, msg["id"], err)
        return

    await runtime.coordinator.async_request_refresh()
    connection.send_result(msg["id"], {"movement_ids": movement_ids})
