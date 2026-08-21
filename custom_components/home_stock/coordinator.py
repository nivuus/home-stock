"""Refreshes the summary the entities publish."""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from functools import partial
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .application import StockManager
from .const import (
    CONF_EXPIRATION_ALERT_DAYS,
    CONF_GOALS,
    CONF_SHOPPING_LIST_HORIZON_DAYS,
    DEFAULT_EXPIRATION_ALERT_DAYS,
    DEFAULT_SHOPPING_LIST_HORIZON_DAYS,
    DOMAIN,
)
from .domain import goals as goals_domain
from .domain.foodday import food_day_bounds
from .storage import repositories as repo

_LOGGER = logging.getLogger(__name__)


async def async_resolve_time_zone(hass: HomeAssistant) -> ZoneInfo:
    """Home Assistant's own configured time zone, resolved asynchronously.

    Every caller that bounds a food day needs the same guard: a coordinator
    refresh must not fail every 15 minutes just because the configured zone
    string turned out unresolvable — `async_get_time_zone` can still return
    `None` for that — so this falls back to UTC (loudly) instead of raising.
    A hard error on a bad zone string belongs in HA's own config validation,
    long before this ever runs.

    Shared by the coordinator and by the websocket journal commands: a food
    day must not be bounded by two different guesses depending on which of
    the two asked.
    """
    tz = await dt_util.async_get_time_zone(hass.config.time_zone)
    if tz is None:
        _LOGGER.warning(
            "Could not resolve configured time zone %r; the food day "
            "falls back to UTC until this is fixed",
            hass.config.time_zone,
        )
        tz = ZoneInfo("UTC")
    return tz


def _numeric_percent(state: str | None) -> float | None:
    """A usable reading, or None for anything that is not one.

    `unavailable`, `unknown`, an empty string, a word, NaN: none of them is a
    measurement, and none of them may move `last_reading_at`.
    """
    if state is None:
        return None
    try:
        percent = float(state)
    except (TypeError, ValueError):
        return None
    return None if percent != percent else percent


def resolve_battery_anchors(hass: HomeAssistant, rows) -> list[dict[str, Any]]:
    """Attach the live entity_id, device name and model to each declared row.

    The `entity_id` is NEVER stored: it is resolved from the registry id on
    every refresh, so renaming an entity in two clicks breaks nothing — the
    exact defect CLAUDE.md holds against today's Grocy wiring, which looks an
    entity_id up inside a free-text description. The anchor is the registry
    entry's `id`, a UUID the interface does not even show; `unique_id` is not
    used as a key because it is only unique per platform.

    `orphaned` is not `tracked = 0`. An orphaned battery is still tracked: it
    feeds `keep`, it is counted, and its task is never closed. An integration
    migration (ZHA to Z2M, on 2026-07-14) orphans several at once, and that is
    precisely the day when closing would be most wrong.
    """
    registry = er.async_get(hass)
    devices = dr.async_get(hass)
    resolved: list[dict[str, Any]] = []
    for row in rows:
        anchor = row.get("entity_registry_id")
        # `registry.entities` is keyed by entity_id; `get_entry` is the
        # lookup by registry id, which is what the anchor is.
        entry = registry.entities.get_entry(anchor) if anchor else None
        entity_id = entry.entity_id if entry is not None else None
        device_id = (entry.device_id if entry is not None else None) or row.get("device_id")
        device = devices.async_get(device_id) if device_id else None
        state = hass.states.get(entity_id) if entity_id else None
        resolved.append({
            **row,
            "entity_id": entity_id,
            "state": state.state if state is not None else None,
            "device_name": device.name_by_user or device.name if device else None,
            "model": device.model if device else None,
            # Declared with an anchor that resolves to nothing: the entry is
            # gone. No anchor at all is not an orphan — it is a battery
            # nobody has wired to an entity, which is perfectly ordinary.
            "orphaned": bool(anchor) and entry is None,
        })
    return resolved


def undeclared_battery_sensors(hass: HomeAssistant,
                               known_registry_ids) -> list[dict[str, Any]]:
    """Every `device_class: battery` sensor with no `battery` row behind it.

    Counts, never creates: the coordinator declares nothing on its own. The
    declaration is a gesture, made at the panel or by the import — otherwise
    merely opening the Piles screen would seed the database with 28 rows.
    """
    registry = er.async_get(hass)
    devices = dr.async_get(hass)
    found: list[dict[str, Any]] = []
    for entry in registry.entities.values():
        if entry.domain != "sensor" or entry.id in known_registry_ids:
            continue
        device_class = entry.device_class or entry.original_device_class
        if device_class != "battery":
            continue
        device = devices.async_get(entry.device_id) if entry.device_id else None
        state = hass.states.get(entry.entity_id)
        found.append({
            "entity_registry_id": entry.id,
            "entity_id": entry.entity_id,
            "device_id": entry.device_id,
            "device_name": device.name_by_user or device.name if device else None,
            "model": device.model if device else None,
            "state": state.state if state is not None else None,
        })
    found.sort(key=lambda row: row["entity_id"])
    return found


class HomeStockCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Reads the summary from SQLite, in the executor."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry,
                 manager: StockManager) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=15),
            config_entry=entry,
        )
        self.manager = manager
        # The rendezvous that wakes the coordinator at the next 04:00 food-day
        # boundary, even on a day with no stock movement at all. See
        # _schedule_food_day_rollover.
        self._food_day_unsub: CALLBACK_TYPE | None = None

    @property
    def food_day_rollover_pending(self) -> bool:
        """Whether a rendezvous is currently scheduled for the next food-day
        boundary.

        Part of the coordinator's public contract (not an implementation
        detail): tests use it to prove the rendezvous is cancelled when the
        config entry unloads, so a timer never fires into a coordinator
        nobody owns any more.
        """
        return self._food_day_unsub is not None

    async def _async_update_data(self) -> dict[str, Any]:
        days = self.config_entry.options.get(
            CONF_EXPIRATION_ALERT_DAYS, DEFAULT_EXPIRATION_ALERT_DAYS
        )
        # The food day is bounded in Home Assistant's own configured time
        # zone, never a guessed default: that is exactly the kind of value
        # that gets it wrong twice a year, silently. See
        # async_resolve_time_zone for the guard.
        tz = await async_resolve_time_zone(self.hass)
        # Both reads happen in ONE executor job. A refresh runs every fifteen
        # minutes; two round trips to the executor for it would be exactly
        # twice as many as it needs.
        horizon = self.config_entry.options.get(
            CONF_SHOPPING_LIST_HORIZON_DAYS, DEFAULT_SHOPPING_LIST_HORIZON_DAYS
        )

        def _read() -> dict[str, Any]:
            data = self.manager.summary(expiration_alert_days=days, tz=tz)
            data["meals"] = self.manager.meal_summary(tz=tz)
            # La réconciliation tourne sur le tic de quinze minutes, APRÈS
            # les lectures et AVANT le rendu : la liste que les entités
            # publient est celle que cette passe vient d'écrire, jamais
            # celle d'il y a un quart d'heure.
            self.manager.reconcile_shopping_list(
                today=datetime.now(tz).date(), horizon_days=horizon)
            data["shopping_list"] = self.manager.shopping_list()
            data["list_estimate"] = self.manager.list_estimate()
            data["receipts"] = repo.pending_receipts(self.manager.db.read())
            return data

        data = await self.hass.async_add_executor_job(_read)
        # Les options vivent ici, jamais dans application.py : le gestionnaire
        # ne connaît pas l'entrée de configuration, et n'a pas à la connaître.
        # Le calcul est pur, il n'a rien à faire dans l'exécuteur.
        breaches = goals_domain.exceeded(
            data["today"], data["week_mean"],
            self.config_entry.options.get(CONF_GOALS, {}) or {})
        data["goals"] = {
            "exceeded": breaches,
            "count": len(breaches),
            "day_count": sum(1 for b in breaches if b["scope"] == "day"),
            "week_count": sum(1 for b in breaches if b["scope"] == "week"),
            "food_day": data["today"]["food_day"],
        }
        data.update(await self._async_battery_data())
        self._schedule_food_day_rollover(tz)
        return data

    async def _async_battery_data(self) -> dict[str, Any]:
        """The two keys lot 5 adds: `batteries` and `warranties`, plus the
        undeclared sensors the counter reads.

        The registry and the state machine can only be read on the event loop,
        the database only in the executor: hence one executor read, the
        resolution here, one grouped executor write, and nothing else.
        """
        rows = await self.hass.async_add_executor_job(self.manager.list_batteries)
        resolved = resolve_battery_anchors(self.hass, rows)

        readings = []
        moment = dt_util.utcnow().replace(tzinfo=None).isoformat(timespec="seconds")
        for row in resolved:
            percent = _numeric_percent(row["state"])
            if percent is None:
                # Nothing numeric to read. `last_reading_at` must mean "the
                # device spoke", never "we looked": confusing the two empties
                # the 26-hour threshold of all its meaning.
                continue
            # An unchanged value is NOT silence — the device did speak — so
            # the moment moves even when the percent does not. Otherwise a
            # battery sitting at 100 % would pass for mute after 26 hours.
            readings.append((row["id"], percent, moment))
            row["last_percent"] = percent
            row["last_reading_at"] = moment

        if readings:
            await self.hass.async_add_executor_job(self.manager.record_readings, readings)

        known = {row["entity_registry_id"] for row in rows if row["entity_registry_id"]}
        never_declared = undeclared_battery_sensors(self.hass, known)
        # A row with `tracked = NULL` means "discovered, not decided": silent
        # in todo.maintenance, but still owed a decision, so it belongs in the
        # same list as a sensor nobody has declared at all. The two counts stay
        # separate as attributes; the list the panel reads is the union.
        undecided = [row for row in resolved
                     if row["tracked"] is None and row["entity_id"]]
        undeclared = sorted(never_declared + undecided,
                            key=lambda row: row["entity_id"] or "")
        warranties = await self.hass.async_add_executor_job(
            partial(self.manager.warranties, today=dt_util.now().date()))
        return {
            "batteries": resolved,
            "undeclared_batteries": undeclared,
            "never_declared_batteries": never_declared,
            "undecided_batteries": undecided,
            "warranties": warranties,
        }

    async def async_maintenance_plan(self, *, extra_items=None, extra_keep=None,
                                     ) -> dict[str, Any]:
        """The plan the `home_stock.maintenance_plan` service answers with.

        Lives here rather than in the service because only the coordinator can
        resolve an anchor: `application` knows neither `entity_id` nor
        `state`.
        """
        rows = await self.hass.async_add_executor_job(self.manager.list_batteries)
        resolved = resolve_battery_anchors(self.hass, rows)
        readings = {row["id"]: {"entity_id": row["entity_id"], "state": row["state"]}
                    for row in resolved}
        return await self.hass.async_add_executor_job(partial(
            self.manager.maintenance_plan,
            now=dt_util.utcnow().replace(tzinfo=None), readings=readings,
            extra_items=extra_items, extra_keep=extra_keep))

    @callback
    def _schedule_food_day_rollover(self, tz: ZoneInfo) -> None:
        """Wake up at the next 04:00, so a day with no activity still turns.

        Rescheduled after every refresh rather than once at setup: the
        house's timezone can change, and a daylight-saving shift moves the
        next boundary by an hour without anything else telling us. Reuses
        the timezone `_async_update_data` already resolved (with its UTC
        fallback) instead of resolving it a second time here.
        """
        if self._food_day_unsub is not None:
            self._food_day_unsub()
        _, end = food_day_bounds(dt_util.utcnow(), tz)
        # `end` is the instant *excluded* from the day that is ending. Waking
        # up exactly on it would leave food_day_of sitting on the boundary,
        # at the mercy of second-level rounding to decide which day shows.
        # One second of margin is not superstition; it is the smallest push
        # that lands unambiguously inside the new day.
        when = datetime.fromisoformat(end).replace(tzinfo=UTC) + timedelta(seconds=1)
        self._food_day_unsub = async_track_point_in_utc_time(
            self.hass, self._on_food_day_rollover, when
        )

    @callback
    def _on_food_day_rollover(self, _now: datetime) -> None:
        self._food_day_unsub = None
        self.hass.async_create_task(self.async_request_refresh())

    async def async_shutdown(self) -> None:
        """Drop the rendezvous with the entry: a timer left behind would call
        back into a coordinator nobody owns any more."""
        if self._food_day_unsub is not None:
            self._food_day_unsub()
            self._food_day_unsub = None
        await super().async_shutdown()
