"""Refreshes the summary the entities publish."""
from __future__ import annotations

import logging
from datetime import timedelta
from functools import partial
from typing import Any

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
        # that gets it wrong twice a year, silently.
        tz = await dt_util.async_get_time_zone(self.hass.config.time_zone)
        return await self.hass.async_add_executor_job(
            partial(self.manager.summary, expiration_alert_days=days, tz=tz)
        )
