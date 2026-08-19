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


async def async_setup_entry(hass: HomeAssistant, entry: HomeStockConfigEntry,
                            async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data.coordinator
    async_add_entities([
        StockValueSensor(coordinator),
        BatchesSensor(coordinator),
        KcalTotalSensor(coordinator),
        CostTotalSensor(coordinator),
    ])
