"""Delete a product or an article: the websocket commands and the services.

Both surfaces are thin: the rules live in `deletion.py`. Both are ADMIN ONLY
— the wall tablet runs as a standard user and must not be able to erase the
catalogue — and both read the same field validator, so they refuse and accept
exactly the same inputs.

Kept out of `websocket_api.py` and `services.py`, which are already far past
this project's line limit. Registered once from `__init__.py`.
"""
from __future__ import annotations

from functools import partial
from typing import Any, Final

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.service import async_register_admin_service

from . import deletion
from .const import DOMAIN
from .messages import french_error
from .validators import bounded_int

SERVICE_DELETE_PRODUCT: Final = "delete_product"
SERVICE_DELETE_ARTICLE: Final = "delete_article"
DELETE_BLOCKED: Final = "delete_blocked"

_ID: Final = vol.All(bounded_int, vol.Range(min=1))
DELETE_PRODUCT_FIELDS: Final = {vol.Required("product_id"): _ID}
DELETE_ARTICLE_FIELDS: Final = {vol.Required("article_id"): _ID}

# (websocket type, service, id key, rule) — one table, both surfaces.
_TARGETS: Final = (
    ("home_stock/product/delete", SERVICE_DELETE_PRODUCT, "product_id",
     deletion.delete_product),
    ("home_stock/article/delete", SERVICE_DELETE_ARTICLE, "article_id",
     deletion.delete_article),
)


def _runtime(hass: HomeAssistant):
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    return entries[0].runtime_data if entries else None


async def _delete(hass: HomeAssistant, runtime, rule, element_id: int) -> dict[str, Any]:
    """Run the rule, then refresh the sensors: a hidden product must leave
    the shortage alert now, not at the next polling interval."""
    outcome = await hass.async_add_executor_job(rule, runtime.manager.db, element_id)
    await runtime.coordinator.async_request_refresh()
    return {"outcome": outcome}


def _websocket_command(command: str, key: str, rule):
    @websocket_api.websocket_command({
        vol.Required("type"): command,
        **(DELETE_PRODUCT_FIELDS if key == "product_id" else DELETE_ARTICLE_FIELDS),
    })
    @websocket_api.require_admin
    @websocket_api.async_response
    async def handler(hass, connection, msg) -> None:
        runtime = _runtime(hass)
        if runtime is None:
            connection.send_error(msg["id"], "not_loaded",
                                  "Le garde-manger n'est pas configuré.")
            return
        try:
            result = await _delete(hass, runtime, rule, msg[key])
        except deletion.DeleteBlocked as err:
            connection.send_error(msg["id"], DELETE_BLOCKED, str(err))
            return
        except LookupError as err:
            connection.send_error(msg["id"], *french_error(err))
            return
        connection.send_result(msg["id"], result)

    return handler


async def _service(hass: HomeAssistant, key: str, rule,
                   call: ServiceCall) -> ServiceResponse:
    runtime = _runtime(hass)
    if runtime is None:
        raise HomeAssistantError("Le garde-manger n'est pas configuré.")
    try:
        return await _delete(hass, runtime, rule, call.data[key])
    except deletion.DeleteBlocked as err:
        raise HomeAssistantError(str(err)) from err
    except LookupError as err:
        raise HomeAssistantError(french_error(err)[1]) from err


def async_register_delete_surfaces(hass: HomeAssistant) -> None:
    """Register the two websocket commands and the two admin services once;
    a reload of the entry must not register twice."""
    for command, service, key, rule in _TARGETS:
        if hass.services.has_service(DOMAIN, service):
            continue
        websocket_api.async_register_command(
            hass, _websocket_command(command, key, rule))
        schema = DELETE_PRODUCT_FIELDS if key == "product_id" else DELETE_ARTICLE_FIELDS
        async_register_admin_service(
            hass, DOMAIN, service, partial(_service, hass, key, rule),
            schema=vol.Schema(schema),
            # It acts AND answers what it did: OPTIONAL, per the developer
            # docs (ONLY is for services that perform no action).
            supports_response=SupportsResponse.OPTIONAL,
        )
