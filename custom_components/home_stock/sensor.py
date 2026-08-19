"""Summary sensors. There is deliberately no entity per product."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    ENTITY_ID_FORMAT,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeStockConfigEntry
from .coordinator import HomeStockCoordinator
from .entity import HomeStockEntity


class StockValueSensor(HomeStockEntity, SensorEntity):
    _attr_native_unit_of_measurement = "EUR"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: HomeStockCoordinator) -> None:
        super().__init__(coordinator, "stock_value", ENTITY_ID_FORMAT)

    @property
    def native_value(self) -> float:
        return self.coordinator.data["stock_value"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        # Batches without a price are excluded from the value: say how many.
        # by_location breaks the same total down per location (spec 8.1).
        return {
            "unpriced_batches": self.coordinator.data["unpriced_batches"],
            "by_location": self.coordinator.data["stock_value_by_location"],
        }


class BatchesSensor(HomeStockEntity, SensorEntity):
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: HomeStockCoordinator) -> None:
        super().__init__(coordinator, "batches", ENTITY_ID_FORMAT)

    @property
    def native_value(self) -> int:
        return self.coordinator.data["batch_count"]

    @property
    def extra_state_attributes(self) -> dict[str, int]:
        return {"open": self.coordinator.data["open_batch_count"]}


class KcalTotalSensor(HomeStockEntity, SensorEntity):
    """Cumulative kcal that left the stock. The lot 2 utility_meter slices it per day."""

    _attr_native_unit_of_measurement = "kcal"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator: HomeStockCoordinator) -> None:
        super().__init__(coordinator, "kcal_total", ENTITY_ID_FORMAT)

    @property
    def native_value(self) -> float:
        return self.coordinator.data["kcal_total"]


class CostTotalSensor(HomeStockEntity, SensorEntity):
    """Cumulative cost of what left the stock, purchases excluded."""

    _attr_native_unit_of_measurement = "EUR"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator: HomeStockCoordinator) -> None:
        super().__init__(coordinator, "cost_total", ENTITY_ID_FORMAT)

    @property
    def native_value(self) -> float:
        return self.coordinator.data["cost_total"]


class CartTotalSensor(HomeStockEntity, SensorEntity):
    """What the open (or not-yet-put-away) shopping session is worth."""

    _attr_native_unit_of_measurement = "EUR"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: HomeStockCoordinator) -> None:
        super().__init__(coordinator, "cart_total", ENTITY_ID_FORMAT)

    @property
    def native_value(self) -> float:
        return self.coordinator.data["cart_total"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "store": self.coordinator.data["cart_store"],
            "lines": self.coordinator.data["cart_lines"],
            "pending": self.coordinator.data["cart_pending"],
        }


class ToStoreSensor(HomeStockEntity, SensorEntity):
    """How many bought lines are still waiting to be put away.

    Zero while the session is still `shopping`: a line just scanned in the
    aisle has no batch yet either, but it is not "awaiting put-away" until
    the trolley has actually left the shop (`session/checkout`) — reading 1
    while still walking the aisles would make this sensor's own name a lie.
    """

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: HomeStockCoordinator) -> None:
        super().__init__(coordinator, "to_store", ENTITY_ID_FORMAT)

    @property
    def native_value(self) -> int:
        return self.coordinator.data["cart_to_store"]


async def async_setup_entry(hass: HomeAssistant, entry: HomeStockConfigEntry,
                            async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data.coordinator
    async_add_entities([
        StockValueSensor(coordinator),
        BatchesSensor(coordinator),
        KcalTotalSensor(coordinator),
        CostTotalSensor(coordinator),
        CartTotalSensor(coordinator),
        ToStoreSensor(coordinator),
    ])
