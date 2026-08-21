"""The eleven battery and equipment commands, in their own module.

`websocket_api.py` is already 1 240 lines and lot 3 adds fourteen commands to
it in a parallel worktree. Two lots lengthening the same file at once is a
merge conflict on nearly every hunk, so lot 5 adds exactly TWO lines there —
an import and a call — and everything else lives here.

The shared helpers (`_runtime`, `_read`, `_send_domain_error`,
`_send_integrity_error`, `_send_not_loaded`, `_validate_fields`) are IMPORTED
from `websocket_api`, never copied: two copies of an error translator are two
vocabularies six months from now.
"""
from __future__ import annotations

import sqlite3
from functools import partial
from typing import Any, Final

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

from .const import BATTERY_EVENT_KINDS, BATTERY_KINDS, BATTERY_VERBS, CONSUMABLE_ROLES
from .coordinator import resolve_battery_anchors, undeclared_battery_sensors
from .domain.stock import InsufficientStock
from .domain.units import UnitError
from .validators import (
    bounded_int, bounded_text, cell_count, iso_date, media_path, percent_threshold,
    tracked_flag,
)
from .websocket_api import (
    _read,
    _runtime,
    _send_domain_error,
    _send_integrity_error,
    _send_not_loaded,
    _validate_fields,
)

_id: Final = vol.All(bounded_int, vol.Range(min=0))


def _label(value: Any) -> str:
    """A battery's displayed label: trimmed, capped, never empty.

    It is the second half of every summary (`«{verbe} — {libellé}»`), so an
    empty one would produce "Pile à changer — " in todo.maintenance and match
    nothing on the next reconciliation.
    """
    text = bounded_text(value)
    if text is None or not text.strip():
        raise vol.Invalid("a battery needs a label")
    return text.strip()


# The columns `battery/update` may touch, each with the validator that guards
# it. Anything not in here is refused by name before it can reach SQL —
# `_update_fields` interpolates the column name straight into the statement.
BATTERY_UPDATE_FIELDS: Final = {
    "label": _label,
    "kind": vol.In(BATTERY_KINDS),
    "entity_registry_id": bounded_text,
    "device_id": bounded_text,
    "equipment_id": _id,
    "product_id": _id,
    "cell_count": cell_count,
    "tracked": tracked_flag,
    "exclusion_reason": bounded_text,
    "low_percent": percent_threshold,
    "keep_percent": percent_threshold,
    "installed_on": iso_date,
    "expected_life_days": bounded_int,
    "note": bounded_text,
    "active": bounded_int,
}

EQUIPMENT_UPDATE_FIELDS: Final = {
    "name": _label,
    "device_id": bounded_text,
    "location_id": _id,
    "brand": bounded_text,
    "model": bounded_text,
    "serial": bounded_text,
    "purchased_on": iso_date,
    "purchase_price": vol.All(vol.Coerce(float), vol.Range(min=0)),
    "warranty_months": bounded_int,
    "receipt_media_id": media_path,
    "manual_url": bounded_text,
    "manual_media_id": media_path,
    "note": bounded_text,
    "active": bounded_int,
}

_WRITE_ERRORS = (InsufficientStock, LookupError, UnitError, ValueError,
                 OverflowError, vol.Invalid)


def _battery_view(row: dict[str, Any]) -> dict[str, Any]:
    """One declared place, as the panel reads it."""
    spare = row.get("spare")
    return {
        "id": row["id"],
        "label": row["label"],
        "kind": row["kind"],
        "verb": BATTERY_VERBS[row["kind"]],
        "tracked": row["tracked"],
        "exclusion_reason": row["exclusion_reason"],
        "entity_id": row.get("entity_id"),
        "state": row.get("state"),
        "orphaned": row.get("orphaned", False),
        "device_name": row.get("device_name"),
        "model": row.get("model"),
        "equipment_id": row["equipment_id"],
        "cell_count": row["cell_count"],
        "low_percent": row["low_percent"],
        "keep_percent": row["keep_percent"],
        "last_percent": row["last_percent"],
        "last_reading_at": row["last_reading_at"],
        "installed_on": row["installed_on"],
        "note": row["note"],
        "spare_label": spare["label"] if spare else None,
        "spare_in_stock": spare["in_stock"] if spare else None,
    }


@websocket_api.websocket_command({vol.Required("type"): "home_stock/batteries/list"})
@websocket_api.async_response
async def batteries_list(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    rows = await _read(hass, runtime.manager.list_batteries)
    resolved = resolve_battery_anchors(hass, rows)
    connection.send_result(msg["id"],
                           {"batteries": [_battery_view(row) for row in resolved]})


@websocket_api.websocket_command({vol.Required("type"): "home_stock/batteries/discover"})
@websocket_api.async_response
async def batteries_discover(hass, connection, msg) -> None:
    """Battery sensors with no `battery` row. WRITES NOTHING.

    A command called "discover" must not create anything: otherwise merely
    opening the Piles screen would seed the database with 28 rows nobody
    asked for.
    """
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    rows = await _read(hass, runtime.manager.list_batteries)
    known = {row["entity_registry_id"] for row in rows if row["entity_registry_id"]}
    connection.send_result(
        msg["id"], {"sensors": undeclared_battery_sensors(hass, known)})


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/battery/declare",
    vol.Required("label"): _label,
    vol.Required("kind"): vol.In(BATTERY_KINDS),
    vol.Optional("entity_registry_id"): bounded_text,
    vol.Optional("device_id"): bounded_text,
    vol.Optional("equipment_id"): _id,
    vol.Optional("product_id"): _id,
    vol.Optional("cell_count"): cell_count,
    vol.Optional("tracked"): tracked_flag,
    vol.Optional("exclusion_reason"): bounded_text,
    vol.Optional("low_percent"): percent_threshold,
    vol.Optional("keep_percent"): percent_threshold,
    vol.Optional("installed_on"): iso_date,
    vol.Optional("note"): bounded_text,
    vol.Optional("idempotency_key"): bounded_text,
})
@websocket_api.async_response
async def battery_declare(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    optional = {key: msg[key] for key in (
        "entity_registry_id", "device_id", "equipment_id", "product_id",
        "cell_count", "tracked", "exclusion_reason", "low_percent",
        "keep_percent", "installed_on", "note", "idempotency_key") if key in msg}
    try:
        battery_id = await _read(hass, partial(
            runtime.manager.declare_battery, label=msg["label"], kind=msg["kind"],
            **optional))
    except _WRITE_ERRORS as err:
        _send_domain_error(connection, msg["id"], err)
        return
    except sqlite3.IntegrityError as err:
        _send_integrity_error(connection, msg["id"], err)
        return
    await runtime.coordinator.async_request_refresh()
    connection.send_result(msg["id"], {"battery_id": battery_id})


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/battery/update",
    vol.Required("battery_id"): _id,
    vol.Required("fields"): dict,
    vol.Optional("idempotency_key"): bounded_text,
})
@websocket_api.async_response
async def battery_update(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    fields = _validate_fields(BATTERY_UPDATE_FIELDS, msg["fields"],
                              connection, msg["id"])
    if fields is None:
        return
    try:
        await _read(hass, partial(runtime.manager.update_battery,
                                  msg["battery_id"], fields))
    except _WRITE_ERRORS as err:
        _send_domain_error(connection, msg["id"], err)
        return
    except sqlite3.IntegrityError as err:
        _send_integrity_error(connection, msg["id"], err)
        return
    await runtime.coordinator.async_request_refresh()
    connection.send_result(msg["id"], {"battery_id": msg["battery_id"]})


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/battery/event",
    vol.Required("battery_id"): _id,
    vol.Required("kind"): vol.In(BATTERY_EVENT_KINDS),
    vol.Optional("occurred_at"): bounded_text,
    vol.Optional("consume_spare"): bool,
    vol.Optional("note"): bounded_text,
    vol.Optional("idempotency_key"): bounded_text,
})
@websocket_api.async_response
async def battery_event(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    try:
        result = await _read(hass, partial(
            runtime.manager.record_battery_event, msg["battery_id"],
            kind=msg["kind"], occurred_at=msg.get("occurred_at"),
            consume_spare=msg.get("consume_spare"), note=msg.get("note"),
            idempotency_key=msg.get("idempotency_key")))
    except _WRITE_ERRORS as err:
        _send_domain_error(connection, msg["id"], err)
        return
    except sqlite3.IntegrityError as err:
        _send_integrity_error(connection, msg["id"], err)
        return
    await runtime.coordinator.async_request_refresh()
    # `spare_refused` travels back rather than being swallowed: losing it
    # would let someone believe there is still a CR2032 in the drawer.
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command({vol.Required("type"): "home_stock/equipment/list"})
@websocket_api.async_response
async def equipment_list(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    rows = await _read(hass, runtime.manager.list_equipment)
    connection.send_result(msg["id"], {"equipment": rows})


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/equipment/get",
    vol.Required("equipment_id"): _id,
})
@websocket_api.async_response
async def equipment_get(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    try:
        sheet = await _read(hass, partial(runtime.manager.get_equipment,
                                          msg["equipment_id"]))
    except _WRITE_ERRORS as err:
        _send_domain_error(connection, msg["id"], err)
        return
    connection.send_result(msg["id"], {"equipment": sheet})


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/equipment/create",
    vol.Required("name"): _label,
    vol.Optional("device_id"): bounded_text,
    vol.Optional("location_id"): _id,
    vol.Optional("brand"): bounded_text,
    vol.Optional("model"): bounded_text,
    vol.Optional("serial"): bounded_text,
    vol.Optional("purchased_on"): iso_date,
    vol.Optional("purchase_price"): vol.All(vol.Coerce(float), vol.Range(min=0)),
    vol.Optional("warranty_months"): bounded_int,
    vol.Optional("manual_url"): bounded_text,
    vol.Optional("manual_media_id"): media_path,
    vol.Optional("receipt_media_id"): media_path,
    vol.Optional("note"): bounded_text,
    vol.Optional("idempotency_key"): bounded_text,
})
@websocket_api.async_response
async def equipment_create(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    optional = {key: msg[key] for key in (
        "device_id", "location_id", "brand", "model", "serial", "purchased_on",
        "purchase_price", "warranty_months", "manual_url", "manual_media_id",
        "receipt_media_id", "note", "idempotency_key") if key in msg}
    try:
        equipment_id = await _read(hass, partial(
            runtime.manager.create_equipment, name=msg["name"], **optional))
    except _WRITE_ERRORS as err:
        _send_domain_error(connection, msg["id"], err)
        return
    except sqlite3.IntegrityError as err:
        _send_integrity_error(connection, msg["id"], err, name=msg["name"])
        return
    await runtime.coordinator.async_request_refresh()
    connection.send_result(msg["id"], {"equipment_id": equipment_id})


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/equipment/update",
    vol.Required("equipment_id"): _id,
    vol.Required("fields"): dict,
    vol.Optional("idempotency_key"): bounded_text,
})
@websocket_api.async_response
async def equipment_update(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    fields = _validate_fields(EQUIPMENT_UPDATE_FIELDS, msg["fields"],
                              connection, msg["id"])
    if fields is None:
        return
    try:
        await _read(hass, partial(runtime.manager.update_equipment,
                                  msg["equipment_id"], fields))
    except _WRITE_ERRORS as err:
        _send_domain_error(connection, msg["id"], err)
        return
    except sqlite3.IntegrityError as err:
        _send_integrity_error(connection, msg["id"], err)
        return
    await runtime.coordinator.async_request_refresh()
    connection.send_result(msg["id"], {"equipment_id": msg["equipment_id"]})


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/equipment/consumable/link",
    vol.Required("equipment_id"): _id,
    vol.Required("product_id"): _id,
    vol.Required("role"): vol.In(CONSUMABLE_ROLES),
    vol.Optional("label"): bounded_text,
    vol.Optional("entity_registry_id"): bounded_text,
    vol.Optional("low_value"): vol.Coerce(float),
    vol.Optional("keep_value"): vol.Coerce(float),
    vol.Optional("unit"): bounded_text,
    vol.Optional("expected_life_days"): bounded_int,
    vol.Optional("installed_on"): iso_date,
    vol.Optional("idempotency_key"): bounded_text,
})
@websocket_api.async_response
async def consumable_link(hass, connection, msg) -> None:
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    optional = {key: msg[key] for key in (
        "label", "entity_registry_id", "low_value", "keep_value", "unit",
        "expected_life_days", "installed_on") if key in msg}
    try:
        consumable_id = await _read(hass, partial(
            runtime.manager.link_consumable, equipment_id=msg["equipment_id"],
            product_id=msg["product_id"], role=msg["role"], **optional))
    except _WRITE_ERRORS as err:
        _send_domain_error(connection, msg["id"], err)
        return
    except sqlite3.IntegrityError as err:
        _send_integrity_error(connection, msg["id"], err)
        return
    await runtime.coordinator.async_request_refresh()
    connection.send_result(msg["id"], {"consumable_id": consumable_id})


@websocket_api.websocket_command({
    vol.Required("type"): "home_stock/equipment/consumable/unlink",
    vol.Required("consumable_id"): _id,
    vol.Optional("idempotency_key"): bounded_text,
})
@websocket_api.async_response
async def consumable_unlink(hass, connection, msg) -> None:
    """Unlink, never delete: the filter stays in the catalogue with its stock
    and its price history."""
    runtime = _runtime(hass)
    if runtime is None:
        _send_not_loaded(connection, msg)
        return
    try:
        await _read(hass, partial(runtime.manager.unlink_consumable,
                                  msg["consumable_id"]))
    except _WRITE_ERRORS as err:
        _send_domain_error(connection, msg["id"], err)
        return
    await runtime.coordinator.async_request_refresh()
    connection.send_result(msg["id"], {"consumable_id": msg["consumable_id"]})


def async_register_battery_commands(hass: HomeAssistant) -> None:
    for command in (batteries_list, batteries_discover, battery_declare,
                    battery_update, battery_event, equipment_list, equipment_get,
                    equipment_create, equipment_update, consumable_link,
                    consumable_unlink):
        websocket_api.async_register_command(hass, command)
