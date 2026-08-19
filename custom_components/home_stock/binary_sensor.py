"""Two alerts: something expires soon, something ran short."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    ENTITY_ID_FORMAT,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeStockConfigEntry
from .coordinator import HomeStockCoordinator
from .entity import HomeStockEntity


class ExpirationsBinarySensor(HomeStockEntity, BinarySensorEntity):
    def __init__(self, coordinator: HomeStockCoordinator) -> None:
        super().__init__(coordinator, "expirations", ENTITY_ID_FORMAT)

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data["expiring"])

    @property
    def extra_state_attributes(self) -> dict[str, list]:
        return {"batches": self.coordinator.data["expiring"]}


class ShortagesBinarySensor(HomeStockEntity, BinarySensorEntity):
    def __init__(self, coordinator: HomeStockCoordinator) -> None:
        super().__init__(coordinator, "shortages", ENTITY_ID_FORMAT)

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data["shortages"])

    @property
    def extra_state_attributes(self) -> dict[str, list[str]]:
        return {"products": [s["product_name"] for s in self.coordinator.data["shortages"]]}


async def async_setup_entry(hass: HomeAssistant, entry: HomeStockConfigEntry,
                            async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data.coordinator
    async_add_entities([ExpirationsBinarySensor(coordinator),
                        ShortagesBinarySensor(coordinator)])
