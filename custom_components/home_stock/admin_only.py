"""Which surfaces only an administrator may call — the one table.

The wall tablet runs as a standard user and must not be able to erase the
catalogue or rewrite it in bulk: imports, the migration check (it can write
archives), the catalogue-wide resync, and hard deletes. A call without any
user (an automation, a script) keeps working, as with Home Assistant's own
admin services.

Every surface listed here is registered through `register_service` or
`register_command`, which read this table; nothing else decides.

Kept out: `home_stock/store/merge` and `home_stock/migration/check` are
offered by the panel's Settings screen to whoever opens it, so restricting
them is a decision for the owner, not a hardening.
"""
from __future__ import annotations

from typing import Any, Final

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, SupportsResponse
from homeassistant.helpers.service import async_register_admin_service

from .const import DOMAIN

ADMIN_SERVICES: Final = frozenset({
    "delete_product",
    "delete_article",
    "import_grocy_catalog",
    "import_grocy_stock",
    "import_grocy_recipes",
    "import_grocy_equipment",
    "check_grocy_migration",
    "resync_off",
})

ADMIN_COMMANDS: Final = frozenset({
    "home_stock/product/delete",
    "home_stock/article/delete",
    "home_stock/recipe/delete",
})


def register_service(hass: HomeAssistant, service: str, handler, *, schema,
                     supports_response: SupportsResponse = SupportsResponse.NONE
                     ) -> None:
    """Register a home_stock service, admin-only when the table says so."""
    if service in ADMIN_SERVICES:
        async_register_admin_service(
            hass, DOMAIN, service, handler, schema=schema,
            supports_response=supports_response)
    else:
        hass.services.async_register(
            DOMAIN, service, handler, schema=schema,
            supports_response=supports_response)


def register_command(hass: HomeAssistant, handler: Any) -> None:
    """Register a websocket command, admin-only when the table says so."""
    # websocket_command stores the type on the handler; require_admin keeps
    # it (functools.wraps copies the attributes).
    if handler._ws_command in ADMIN_COMMANDS:
        handler = websocket_api.require_admin(handler)
    websocket_api.async_register_command(hass, handler)
