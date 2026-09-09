"""The fourteen recipe and meal commands of lot 3.

A module of their own, and that is a FILE-LAYOUT decision, not a contract one:
the message types, the schemas and the helpers are exactly those of
`websocket_api`, which registers these commands alongside its own.

`websocket_api.py` is already 1 240 lines, and lot 5 adds eleven commands to
it in a parallel worktree. Putting lot 3's fourteen in a new module leaves the
exposed surface strictly identical and reduces the merge conflict to two lines.

Every command that WRITES accepts an `idempotency_key`. The panel's offline
queue stamps one on everything that goes through it, with no notion of "this
command does not take one" — that is what lot 1's incident cost: three
commands with strict schemas, refused on the very first offline retry.
"""
from __future__ import annotations

import sqlite3
from functools import partial
from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

from .const import MATCH_STATES, MEAL_SLOT_KEYS
from .domain.stock import InsufficientStock
from .validators import (
    bounded_int,
    bounded_text,
    finite_float,
    iso_date,
    parts_count,
)
from .websocket_api import (
    _read,
    _runtime,
    _send_domain_error,
    _send_integrity_error,
    _send_not_loaded,
)

# The key the offline queue stamps on everything. Optional in the schema and
# ignored by the read commands, because the queue does not know which is which.
_KEY = {vol.Optional("idempotency_key"): vol.Any(None, bounded_text)}

_SKIP_IDS = vol.All([bounded_int], vol.Length(max=200))


def _positive(value: Any) -> float:
    number = finite_float(value)
    if number <= 0:
        raise vol.Invalid(f"must be positive, got {number}")
    return number


def _not_negative(value: Any) -> float:
    number = finite_float(value)
    if number < 0:
        raise vol.Invalid(f"must not be negative, got {number}")
    return number


def _day(value: Any) -> str:
    """A food day in extended YYYY-MM-DD form, and only that form."""
    day = iso_date(value)
    if day is None:
        raise vol.Invalid("expected a date as YYYY-MM-DD")
    return day


async def _guarded(hass: HomeAssistant, connection, msg, work) -> Any:
    """Run `work` in the executor, turning domain refusals into French errors.

    Sentinel-based rather than exception-based on the way out: a command that
    failed must send exactly one error and no result, and returning a sentinel
    keeps that decision in one place instead of at every call site.
    """
    try:
        return await hass.async_add_executor_job(work)
    except (LookupError, ValueError, InsufficientStock) as err:
        _send_domain_error(connection, msg["id"], err)
    except sqlite3.IntegrityError as err:
        _send_integrity_error(connection, msg["id"], err)
    return _FAILED


_FAILED: Any = object()


# --- recipes ----------------------------------------------------------------

@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/recipes/list",
    vol.Optional("search"): vol.Any(None, bounded_text),
    vol.Optional("only_reviewable", default=False): bool,
})
@websocket_api.async_response
async def recipes_list(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    recipes = await _read(hass, partial(
        runtime.manager.list_recipes, search=msg.get("search"),
        only_reviewable=msg["only_reviewable"]))
    connection.send_result(msg["id"], {"recipes": recipes})


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/recipe/get",
    vol.Required("recipe_id"): bounded_int,
})
@websocket_api.async_response
async def recipe_get(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    view = await _guarded(hass, connection, msg, partial(
        runtime.manager.get_recipe_view, msg["recipe_id"]))
    if view is not _FAILED:
        connection.send_result(msg["id"], view)


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/recipe/create",
    vol.Required("name"): bounded_text,
    vol.Optional("servings", default=1): bounded_int,
    vol.Optional("steps", default=[]): list,
    vol.Optional("ingredients", default=[]): list,
    **_KEY,
})
@websocket_api.async_response
async def recipe_create(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    recipe_id = await _guarded(hass, connection, msg, partial(
        runtime.manager.create_recipe, name=msg["name"],
        servings=msg["servings"], steps=msg["steps"],
        ingredients=msg["ingredients"]))
    if recipe_id is not _FAILED:
        connection.send_result(msg["id"], {"recipe_id": recipe_id})


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/recipe/update",
    vol.Required("recipe_id"): bounded_int,
    vol.Required("fields"): dict,
    **_KEY,
})
@websocket_api.async_response
async def recipe_update(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    result = await _guarded(hass, connection, msg, partial(
        runtime.manager.update_recipe, msg["recipe_id"], msg["fields"]))
    if result is not _FAILED:
        connection.send_result(msg["id"], {})


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/recipe/delete",
    vol.Required("recipe_id"): bounded_int,
    **_KEY,
})
@websocket_api.async_response
async def recipe_delete(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    result = await _guarded(hass, connection, msg, partial(
        runtime.manager.delete_recipe, msg["recipe_id"]))
    if result is not _FAILED:
        connection.send_result(msg["id"], {})


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/recipe/ingredient/match",
    vol.Required("ingredient_id"): bounded_int,
    vol.Optional("product_id"): vol.Any(None, bounded_int),
    vol.Required("state"): vol.In(MATCH_STATES),
    vol.Optional("create_alias", default=False): bool,
    **_KEY,
})
@websocket_api.async_response
async def recipe_ingredient_match(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    line = await _guarded(hass, connection, msg, partial(
        runtime.manager.match_ingredient, msg["ingredient_id"],
        product_id=msg.get("product_id"), state=msg["state"],
        create_alias=msg["create_alias"]))
    if line is not _FAILED:
        connection.send_result(msg["id"], {"ingredient": line})


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/recipe/search_external",
    vol.Optional("query"): vol.Any(None, bounded_text),
    vol.Optional("ingredient"): vol.Any(None, bounded_text),
})
@websocket_api.async_response
async def recipe_search_external(hass, connection, msg) -> None:
    """Search the online source. Writes absolutely nothing.

    A source that is down answers an empty list and a message, never an error:
    nothing here is allowed to delay a dinner, and no existing recipe is
    affected either way.
    """
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    source = runtime.recipe_source
    if source is None:
        connection.send_result(msg["id"], {"hits": [], "reachable": False})
        return
    if msg.get("ingredient"):
        hits = await source.by_ingredient(msg["ingredient"])
    else:
        hits = await source.search(msg.get("query") or "")
    connection.send_result(msg["id"], {
        "hits": [
            {"source_ref": hit.source_ref, "name": hit.name,
             "image_url": hit.image_url, "category": hit.category,
             "area": hit.area}
            for hit in hits
        ],
        "reachable": True,
    })


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/recipe/import_external",
    vol.Required("source_ref"): bounded_text,
    **_KEY,
})
@websocket_api.async_response
async def recipe_import_external(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    result = await async_import_recipe(hass, runtime, msg["source_ref"])
    if result is None:
        connection.send_error(msg["id"], "not_found",
                              "Cette recette est introuvable à la source.")
        return
    connection.send_result(msg["id"], result)


async def async_import_recipe(hass: HomeAssistant, runtime,
                              source_ref: str) -> dict[str, Any] | None:
    """Look up, map, adapt, write — the ONE orchestration both surfaces use.

    Shared with `home_stock.import_recipe` rather than written twice: the
    websocket and the service must not be able to drift into importing the
    same card differently.
    """
    from .const import CONF_RECIPE_AGENT
    from .recipes.adapt import adapt
    from .recipes.mapping import map_meal

    source = runtime.recipe_source
    if source is None:
        return None
    payload = await source.lookup(source_ref)
    recipe = map_meal(payload) if payload else None
    if recipe is None:
        return None

    entries = hass.config_entries.async_loaded_entries("home_stock")
    agent_id = entries[0].options.get(CONF_RECIPE_AGENT) if entries else None
    adapted = await adapt(hass, agent_id=agent_id, recipe=recipe)

    recipe_id, _created = await hass.async_add_executor_job(
        partial(runtime.manager.write_source_recipe, recipe, adapted=adapted))
    return {"recipe_id": recipe_id, "adapted": adapted is not None}


# --- meals ------------------------------------------------------------------

@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/meals/list",
    vol.Required("start"): _day,
    vol.Required("end"): _day,
})
@websocket_api.async_response
async def meals_list(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    meals = await _guarded(hass, connection, msg, partial(
        runtime.manager.list_meals, msg["start"], msg["end"]))
    if meals is not _FAILED:
        connection.send_result(msg["id"], {"meals": meals})


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/meal/plan",
    vol.Required("day"): _day,
    vol.Required("slot_key"): vol.In(MEAL_SLOT_KEYS),
    vol.Optional("recipe_id"): vol.Any(None, bounded_int),
    vol.Optional("product_id"): vol.Any(None, bounded_int),
    vol.Optional("amount"): vol.Any(None, _positive),
    vol.Optional("note"): vol.Any(None, bounded_text),
    vol.Optional("servings", default=1.0): _positive,
    **_KEY,
})
@websocket_api.async_response
async def meal_plan(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    posted = await _guarded(hass, connection, msg, partial(
        runtime.manager.plan_meal, day=msg["day"], slot_key=msg["slot_key"],
        recipe_id=msg.get("recipe_id"), product_id=msg.get("product_id"),
        amount=msg.get("amount"), note=msg.get("note"),
        servings=msg["servings"]))
    if posted is not _FAILED:
        connection.send_result(msg["id"], posted)


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/meal/move",
    vol.Required("meal_id"): bounded_int,
    vol.Required("day"): _day,
    vol.Required("slot_key"): vol.In(MEAL_SLOT_KEYS),
    vol.Optional("position"): vol.Any(None, bounded_int),
    **_KEY,
})
@websocket_api.async_response
async def meal_move(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    result = await _guarded(hass, connection, msg, partial(
        runtime.manager.move_meal, msg["meal_id"], day=msg["day"],
        slot_key=msg["slot_key"], position=msg.get("position")))
    if result is not _FAILED:
        connection.send_result(msg["id"], {})


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/meal/cancel",
    vol.Required("meal_id"): bounded_int,
    **_KEY,
})
@websocket_api.async_response
async def meal_cancel(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    outcome = await _guarded(hass, connection, msg, partial(
        runtime.manager.cancel_meal, msg["meal_id"]))
    if outcome is not _FAILED:
        connection.send_result(msg["id"], {"outcome": outcome})


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/meal/preview",
    vol.Required("meal_id"): bounded_int,
    vol.Optional("servings"): vol.Any(None, _positive),
    vol.Optional("skip_ingredient_ids", default=[]): _SKIP_IDS,
})
@websocket_api.async_response
async def meal_preview(hass, connection, msg) -> None:
    """The decrement plan. Writes absolutely nothing."""
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    preview = await _guarded(hass, connection, msg, partial(
        runtime.manager.preview_meal, msg["meal_id"],
        servings=msg.get("servings"),
        skip_ingredient_ids=msg["skip_ingredient_ids"]))
    if preview is not _FAILED:
        connection.send_result(msg["id"], preview)


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/meal/validate",
    vol.Required("meal_id"): bounded_int,
    vol.Required("portions_eaten"): _not_negative,
    vol.Optional("servings"): vol.Any(None, _positive),
    vol.Optional("parts_total"): vol.Any(None, parts_count),
    vol.Optional("parts_mine"): vol.Any(None, parts_count),
    vol.Optional("skip_ingredient_ids", default=[]): _SKIP_IDS,
    **_KEY,
})
@websocket_api.async_response
async def meal_validate(hass, connection, msg) -> None:
    """Cook, then eat. Not reversible at lot 3, and the screen says so."""
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    result = await _guarded(hass, connection, msg, partial(
        runtime.manager.validate_meal, msg["meal_id"],
        portions_eaten=msg["portions_eaten"], servings=msg.get("servings"),
        parts_total=msg.get("parts_total"), parts_mine=msg.get("parts_mine"),
        skip_ingredient_ids=msg["skip_ingredient_ids"], dry_run=False))
    if result is not _FAILED:
        connection.send_result(msg["id"], result)
        await runtime.coordinator.async_request_refresh()


def async_register_recipe_commands(hass: HomeAssistant) -> None:
    """Register lot 3's fourteen commands."""
    for command in (recipes_list, recipe_get, recipe_create, recipe_update,
                    recipe_delete, recipe_ingredient_match,
                    recipe_search_external, recipe_import_external,
                    meals_list, meal_plan, meal_move, meal_cancel,
                    meal_preview, meal_validate):
        websocket_api.async_register_command(hass, command)
