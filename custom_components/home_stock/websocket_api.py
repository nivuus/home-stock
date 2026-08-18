"""Read commands for the panel. The panel reuses the Home Assistant connection,
so there is no separate authentication and it can subscribe to changes."""
from __future__ import annotations

from functools import partial
from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .storage import repositories as repo


def _runtime(hass: HomeAssistant):
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    return entries[0].runtime_data if entries else None


async def _read(hass: HomeAssistant, work) -> Any:
    return await hass.async_add_executor_job(work)


@websocket_api.websocket_command({vol.Required("type"): "home_stock/products/list"})
@websocket_api.async_response
async def products_list(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    products = await _read(hass, partial(repo.list_products, runtime.manager.db.read()))
    connection.send_result(msg["id"], {"products": products})


@websocket_api.websocket_command({vol.Required("type"): "home_stock/locations/list"})
@websocket_api.async_response
async def locations_list(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    locations = await _read(hass, partial(repo.list_locations, runtime.manager.db.read()))
    connection.send_result(msg["id"], {"locations": locations})


@websocket_api.websocket_command({vol.Required("type"): "home_stock/aisles/list"})
@websocket_api.async_response
async def aisles_list(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    aisles = await _read(hass, partial(repo.list_aisles, runtime.manager.db.read()))
    connection.send_result(msg["id"], {"aisles": aisles})


@websocket_api.websocket_command({vol.Required("type"): "home_stock/batches/list"})
@websocket_api.async_response
async def batches_list(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    batches = await _read(hass, partial(repo.stock_rows, runtime.manager.db.read()))
    connection.send_result(msg["id"], {"batches": batches})


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/product/get",
    vol.Required("product_id"): int,
})
@websocket_api.async_response
async def product_get(hass, connection, msg) -> None:
    runtime = _runtime(hass)
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
    movements = await _read(hass, partial(
        repo.list_movements, runtime.manager.db.read(), msg.get("since")
    ))
    connection.send_result(msg["id"], {"movements": movements})


@websocket_api.websocket_command({vol.Required("type"): "home_stock/subscribe"})
@websocket_api.async_response
async def subscribe(hass, connection, msg) -> None:
    """Push the summary now, and again on every coordinator refresh."""
    runtime = _runtime(hass)
    coordinator = runtime.coordinator

    @callback
    def _forward() -> None:
        connection.send_event(msg["id"], coordinator.data)

    connection.subscriptions[msg["id"]] = coordinator.async_add_listener(_forward)
    connection.send_result(msg["id"])
    # `coordinator.data` can be stale: a caller that wrote through the manager
    # directly (bypassing the services, which refresh the coordinator after
    # every write) would otherwise have its first push show the old summary.
    # `async_refresh()` re-reads the database and, since `always_update`
    # defaults to True, always calls the listeners once it is done — so this
    # both delivers a guaranteed-current first push and drives `_forward()`,
    # with no separate manual call needed.
    await coordinator.async_refresh()


def async_register_websocket(hass: HomeAssistant) -> None:
    """Register the read commands once."""
    for command in (products_list, product_get, locations_list, aisles_list,
                    batches_list, movements_list, subscribe):
        websocket_api.async_register_command(hass, command)
