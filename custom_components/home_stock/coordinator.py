"""Refreshes the summary the entities publish."""
from __future__ import annotations

import logging
from datetime import timedelta
from functools import partial
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .application import StockManager
from .const import CONF_EXPIRATION_ALERT_DAYS, DEFAULT_EXPIRATION_ALERT_DAYS, DOMAIN

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
        return await self.hass.async_add_executor_job(
            partial(self.manager.summary, expiration_alert_days=days, tz=tz)
        )
