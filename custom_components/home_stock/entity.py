"""Base class for every entity: one device, English ids, French display names."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HomeStockCoordinator


class HomeStockEntity(CoordinatorEntity[HomeStockCoordinator]):
    """Everything hangs off one device, named in French by the translations."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: HomeStockCoordinator, key: str,
                 entity_id_format: str) -> None:
        super().__init__(coordinator)
        self._attr_translation_key = key
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{key}"
        # Spec section 14: entity ids in English. Left to Home Assistant they would
        # be built from the French device and entity names.
        self.entity_id = entity_id_format.format(f"{DOMAIN}_{key}")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name="Garde-manger",
            manufacturer="Maison",
        )
