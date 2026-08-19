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

# Same wording as services._entry()'s HomeAssistantError, for the same condition.
NOT_LOADED_MESSAGE = "Le garde-manger n'est pas configuré."


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


def async_register_websocket(hass: HomeAssistant) -> None:
    """Register the read commands once."""
    for command in (products_list, product_get, locations_list, aisles_list,
                    batches_list, movements_list, subscribe):
        websocket_api.async_register_command(hass, command)
