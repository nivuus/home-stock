"""One event entity for expiry announcements.

Grouped: one event per stage per refresh, carrying the list of batches. Firing
once per batch would put several state writes in the same second — and would
make a voice assistant say three sentences where one ("three things are going
off") is what a person wants.
"""
from __future__ import annotations

from functools import partial

from homeassistant.components.event import ENTITY_ID_FORMAT, EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeStockConfigEntry
from .application import EXPIRY_STAGES
from .const import CONF_EXPIRATION_ALERT_DAYS, DEFAULT_EXPIRATION_ALERT_DAYS
from .coordinator import HomeStockCoordinator
from .entity import HomeStockEntity


class ExpirationEventEntity(HomeStockEntity, EventEntity):
    _attr_event_types = list(EXPIRY_STAGES)

    def __init__(self, coordinator: HomeStockCoordinator) -> None:
        super().__init__(coordinator, "expiration", ENTITY_ID_FORMAT)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # The coordinator's first refresh happens before the platforms are set
        # up: claiming there would mark a fresh install's whole backlog as
        # announced with nobody listening. The entity claims, once it exists.
        await self._announce()

    @callback
    def _handle_coordinator_update(self) -> None:
        self.hass.async_create_task(self._announce())

    async def _announce(self) -> None:
        days = self.coordinator.config_entry.options.get(
            CONF_EXPIRATION_ALERT_DAYS, DEFAULT_EXPIRATION_ALERT_DAYS)
        claimed = await self.hass.async_add_executor_job(partial(
            self.coordinator.manager.claim_expiry_announcements,
            expiration_alert_days=days))
        for stage, batches in claimed:
            self._trigger_event(stage, {"count": len(batches), "batches": batches})
            self.async_write_ha_state()


async def async_setup_entry(hass: HomeAssistant, entry: HomeStockConfigEntry,
                            async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities([ExpirationEventEntity(entry.runtime_data.coordinator)])
