"""Three alerts: something expires soon, something ran short, a
nutrition cap gave way."""
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


class NutritionGoalsBinarySensor(HomeStockEntity, BinarySensorEntity):
    """Whether a nutrition cap gave way, on the day or on the long window.

    One entity, not one per nutrient: nine copies of the same sentence in the
    registry help nobody. Not an attribute on the kcal entity either — five of
    the nine daily entities are created disabled, and a cap set on one of them
    must still be readable. The list of breaches comes from the coordinator,
    which read it from `data["today"]`, never from a state.
    """

    def __init__(self, coordinator: HomeStockCoordinator) -> None:
        super().__init__(coordinator, "nutrition_goals", ENTITY_ID_FORMAT)

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data["goals"]["count"])

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        return dict(self.coordinator.data["goals"])


async def async_setup_entry(hass: HomeAssistant, entry: HomeStockConfigEntry,
                            async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data.coordinator
    async_add_entities([ExpirationsBinarySensor(coordinator),
                        ShortagesBinarySensor(coordinator),
                        NutritionGoalsBinarySensor(coordinator)])
