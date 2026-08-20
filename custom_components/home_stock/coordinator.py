"""Refreshes the summary the entities publish."""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from functools import partial
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .application import StockManager
from .const import CONF_EXPIRATION_ALERT_DAYS, DEFAULT_EXPIRATION_ALERT_DAYS, DOMAIN
from .domain.foodday import food_day_bounds

_LOGGER = logging.getLogger(__name__)


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
        # that gets it wrong twice a year, silently. async_get_time_zone can
        # still return None if the configured zone string is unresolvable;
        # falling back to UTC (and logging it loudly) is chosen over raising
        # here, because a coordinator refresh failing every 15 minutes would
        # take down every home_stock sensor for a problem that a hard error
        # elsewhere in HA's own config validation should already have caught
        # long before this ever runs.
        tz = await dt_util.async_get_time_zone(self.hass.config.time_zone)
        if tz is None:
            _LOGGER.warning(
                "Could not resolve configured time zone %r; the food day "
                "falls back to UTC until this is fixed",
                self.hass.config.time_zone,
            )
            tz = ZoneInfo("UTC")
        data = await self.hass.async_add_executor_job(
            partial(self.manager.summary, expiration_alert_days=days, tz=tz)
        )
        self._schedule_food_day_rollover(tz)
        return data

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
