"""Change the quantity of a recipe line, take the line out, or put one back:
the websocket commands and the services — plus the read service that lists
the lines with the ids those gestures take.

Both surfaces are thin: the rules live in `recipe_lines.py`, and both read
the same field validators, so they refuse and accept exactly the same inputs.
The fields are checked inside the handlers, not by the schema Home Assistant
runs before them: its refusal is voluptuous' English ("... for dictionary
value @ data['quantity']"), while a refusal raised here goes through
`messages.french_error` and reaches Maxime in French on both surfaces.
After a write the coordinator is refreshed at once: the next-meal sensor
counts what the recipe asks for, and must not show the old quantity until
the next polling interval.

Kept out of `websocket_recipes.py` and `services.py` (the latter already far
past this project's line limit). Registered once from `__init__.py`.
"""
from __future__ import annotations

from functools import partial
from typing import Any, Final

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.websocket_api.decorators import (
    async_response,
    websocket_command,
)
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import ServiceValidationError

from . import recipe_lines
from .const import DOMAIN
from .messages import french_error
from .validators import bounded_int, bounded_text

SERVICE_SET_QUANTITY: Final = "set_recipe_ingredient_quantity"
SERVICE_REMOVE: Final = "remove_recipe_ingredient"
SERVICE_ADD: Final = "add_recipe_ingredient"
SERVICE_LIST: Final = "get_recipe_ingredients"
WS_UPDATE: Final = "home_stock/recipe/ingredient/update"
WS_DELETE: Final = "home_stock/recipe/ingredient/delete"
WS_ADD: Final = "home_stock/recipe/ingredient/add"

_ID: Final = vol.All(bounded_int, vol.Range(min=1))
# A line is named by `ingredient_id`, or by `recipe_id` + `product` (the
# readable name of its product): `recipe_lines.designated_line` decides.
# With an id, `recipe_id` is a guard: a line of another recipe is refused.
_LINE: Final[dict[Any, Any]] = {
    vol.Optional("ingredient_id"): _ID,
    vol.Optional("recipe_id"): _ID,
    vol.Optional("product"): bounded_text,
}
SET_QUANTITY_FIELDS: Final[dict[Any, Any]] = {
    **_LINE, vol.Required("quantity"): recipe_lines.ingredient_quantity}
REMOVE_FIELDS: Final[dict[Any, Any]] = dict(_LINE)
LIST_FIELDS: Final[dict[Any, Any]] = {vol.Required("recipe_id"): _ID}
# Putting a line back: the product by its name (or only a text), the
# quantity in its base unit, and the place it had if it is still free.
ADD_FIELDS: Final[dict[Any, Any]] = {
    vol.Required("recipe_id"): _ID,
    vol.Optional("product"): bounded_text,
    vol.Optional("quantity"): recipe_lines.ingredient_quantity,
    vol.Optional("raw_text"): bounded_text,
    vol.Optional("position"): vol.All(
        bounded_int, vol.Range(min=1, msg="position must be at least 1")),
}

NOT_LOADED: Final = "Le garde-manger n'est pas configuré."


# Keys of a websocket message that are the protocol's, not the command's.
_ENVELOPE: Final = ("id", "type")


def _loose(fields: dict[Any, Any]) -> dict[Any, Any]:
    """The schema Home Assistant runs: any key, any value, none required.

    Even an unknown key passes it — its refusal would be English — and is
    refused by `_checked` instead.
    """
    return {**{vol.Optional(str(key)): object for key in fields}, vol.Extra: object}


def _checked(fields: dict[Any, Any], data: dict[str, Any]) -> dict[str, Any]:
    """The fields validated, or a ValueError `french_error` translates."""
    given = {key: value for key, value in data.items() if key not in _ENVELOPE}
    try:
        return dict(vol.Schema(fields)(given))
    except vol.MultipleInvalid as err:
        first = err.errors[0]
        if first.error_message == "required key not provided":
            raise ValueError(f"missing field {first.path[-1]}") from err
        if first.error_message == "extra keys not allowed":
            raise ValueError(f"unknown field {first.path[-1]}") from err
        raise ValueError(first.error_message) from err


def _runtime(hass: HomeAssistant) -> Any:
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    return entries[0].runtime_data if entries else None


def _set_quantity(runtime: Any, data: dict[str, Any]) -> dict[str, Any]:
    db = runtime.manager.db
    line = recipe_lines.set_ingredient_quantity(
        db, recipe_lines.designated_line(db, data), data["quantity"],
        recipe_id=data.get("recipe_id"))
    return {"ingredient": line}


def _remove(runtime: Any, data: dict[str, Any]) -> dict[str, Any]:
    db = runtime.manager.db
    line = recipe_lines.remove_ingredient(
        db, recipe_lines.designated_line(db, data), recipe_id=data.get("recipe_id"))
    return {"removed": line}


def _add(runtime: Any, data: dict[str, Any]) -> dict[str, Any]:
    line = recipe_lines.add_ingredient(
        runtime.manager.db, data["recipe_id"], product=data.get("product"),
        quantity=data.get("quantity"), raw_text=data.get("raw_text"),
        position=data.get("position"))
    return {"ingredient": line}


def _list(runtime: Any, data: dict[str, Any]) -> dict[str, Any]:
    lines = recipe_lines.list_lines(runtime.manager.db, data["recipe_id"])
    return {"recipe_id": data["recipe_id"], "ingredients": lines}


async def _apply(hass: HomeAssistant, runtime: Any, rule: Any,
                 data: dict[str, Any], *, writes: bool = True) -> dict[str, Any]:
    """Run the rule off the event loop, then refresh the sensors after a write.

    `async_refresh`, not `async_request_refresh`: the request goes through a
    debouncer that runs the first call at once but delays the next ones by
    its cooldown — and the breakfast trial is three gestures in a row, after
    which the next-meal sensor must already be right.
    """
    result: dict[str, Any] = await hass.async_add_executor_job(rule, runtime, data)
    if writes:
        await runtime.coordinator.async_refresh()
    return result


# (websocket type, service, fields, rule) — one table, both surfaces.
_SURFACES: Final = (
    (WS_UPDATE, SERVICE_SET_QUANTITY, SET_QUANTITY_FIELDS, _set_quantity),
    (WS_DELETE, SERVICE_REMOVE, REMOVE_FIELDS, _remove),
    (WS_ADD, SERVICE_ADD, ADD_FIELDS, _add),
)


def _websocket_command(command: str, fields: dict[Any, Any], rule: Any) -> Any:
    @websocket_command({vol.Required("type"): command, **_loose(fields)})
    @async_response
    async def handler(hass: HomeAssistant, connection: Any,
                      msg: dict[str, Any]) -> None:
        runtime = _runtime(hass)
        if runtime is None:
            connection.send_error(msg["id"], "not_loaded", NOT_LOADED)
            return
        try:
            result = await _apply(hass, runtime, rule, _checked(fields, msg))
        except ValueError as err:
            connection.send_error(msg["id"], *french_error(err))
            return
        connection.send_result(msg["id"], result)

    return handler


async def _service(hass: HomeAssistant, rule: Any, fields: dict[Any, Any],
                   writes: bool, call: ServiceCall) -> ServiceResponse:
    runtime = _runtime(hass)
    if runtime is None:
        raise ServiceValidationError(NOT_LOADED)
    try:
        result = await _apply(hass, runtime, rule, _checked(fields, dict(call.data)),
                              writes=writes)
    except ValueError as err:
        raise ServiceValidationError(french_error(err)[1]) from err
    return result if call.return_response else None


def async_register_recipe_line_surfaces(hass: HomeAssistant) -> None:
    """Register the three websocket commands and the four services once;
    a reload of the entry must not register twice."""
    for command, service, fields, rule in _SURFACES:
        if hass.services.has_service(DOMAIN, service):
            continue
        websocket_api.async_register_command(
            hass, _websocket_command(command, fields, rule))
        hass.services.async_register(
            DOMAIN, service, partial(_service, hass, rule, fields, True),
            schema=vol.Schema(_loose(fields)),
            # It acts AND answers what it did: OPTIONAL, per the developer
            # docs (ONLY is for services that perform no action).
            supports_response=SupportsResponse.OPTIONAL,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_LIST):
        # Read-only: its websocket twin is the existing `recipe/get`.
        hass.services.async_register(
            DOMAIN, SERVICE_LIST, partial(_service, hass, _list, LIST_FIELDS, False),
            schema=vol.Schema(_loose(LIST_FIELDS)),
            supports_response=SupportsResponse.ONLY,
        )
