"""Summary sensors. There is deliberately no entity per product."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Final

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
    """Cumulative kcal that left the stock.

    Since lot 2 (amendment A2) this counts consumption only, weighted by the
    share actually eaten — what is thrown away or expired no longer inflates
    it. The food day itself has its own sensor, kcal_today, below.
    """

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


# The nine daily nutrient sensors: key, the key inside coordinator.data["today"],
# its unit, and whether it is worth a slot in the sidebar out of the box. The
# five disabled ones exist in the registry and turn on with one click; their
# long-term history starts then, which is the announced price (spec 11).
DAILY_NUTRIENTS: Final = (
    ("kcal_today", "kcal", "kcal", True),
    ("proteins_today", "proteins", "g", True),
    ("sugars_today", "sugars", "g", True),
    ("salt_today", "salt", "g", True),
    ("carbohydrates_today", "carbohydrates", "g", False),
    ("added_sugars_today", "added_sugars", "g", False),
    ("fat_today", "fat", "g", False),
    ("saturated_fat_today", "saturated_fat", "g", False),
    ("fiber_today", "fiber", "g", False),
)


class DailyTotalSensor(HomeStockEntity, SensorEntity):
    """One nutrient (or the money) over the current food day, 04:00 to 04:00.

    Declared TOTAL with an explicit `last_reset` rather than TOTAL_INCREASING:
    this counter really does drop back to zero every morning, and saying so is
    what stops Home Assistant reading that drop as a meter rollover.

    Its native daily statistic is still cut at midnight — Home Assistant has no
    other bucket. The panel is the authority for the 04:00 day (spec 4, A1).
    """

    _attr_state_class = SensorStateClass.TOTAL

    def __init__(self, coordinator: HomeStockCoordinator, key: str,
                 field: str, unit: str, *, enabled: bool = True) -> None:
        super().__init__(coordinator, key, ENTITY_ID_FORMAT)
        self._field = field
        self._attr_native_unit_of_measurement = unit
        self._attr_entity_registry_enabled_default = enabled

    @property
    def native_value(self) -> float:
        return self.coordinator.data["today"][self._field]

    @property
    def last_reset(self) -> datetime:
        """Start of the current food day, as an aware UTC datetime.

        The coordinator resolves Home Assistant's configured time zone
        asynchronously and with a guarded fallback (coordinator.py); it
        already folds that into `today["start"]`, a naive UTC ISO string.
        This property only attaches UTC tzinfo to it — a synchronous entity
        property has no business resolving a time zone itself.
        """
        start = self.coordinator.data["today"]["start"]
        return datetime.fromisoformat(start).replace(tzinfo=UTC)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "food_day": self.coordinator.data["today"]["food_day"],
            # A day at 1 800 kcal with three unvalued outings is not the same
            # information as a complete one (spec 8).
            "unvalued_movements": self.coordinator.data["today"]["unvalued"],
        }


class CostWasteTotalSensor(HomeStockEntity, SensorEntity):
    """Cumulative cost of what was thrown away or expired.

    Split out of cost_total at lot 2: what you waste is a figure worth seeing,
    not one to drown in what you ate (spec 4, A2).
    """

    _attr_native_unit_of_measurement = "EUR"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator: HomeStockCoordinator) -> None:
        super().__init__(coordinator, "cost_waste_total", ENTITY_ID_FORMAT)

    @property
    def native_value(self) -> float:
        return self.coordinator.data["cost_waste_total"]


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
        *(DailyTotalSensor(coordinator, key, field, unit, enabled=enabled)
          for key, field, unit, enabled in DAILY_NUTRIENTS),
        DailyTotalSensor(coordinator, "cost_today", "cost", "EUR"),
        CostWasteTotalSensor(coordinator),
    ])
