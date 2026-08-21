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
from .const import BATTERY_VERBS
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
    # TOTAL et non TOTAL_INCREASING depuis le lot 4 : une correction fait
    # BAISSER ce cumul, et TOTAL_INCREASING lirait cette baisse comme la
    # remise à zéro d'un compteur d'appareil — HA ajouterait alors la
    # nouvelle valeur au lieu de la soustraire.
    _attr_state_class = SensorStateClass.TOTAL

    def __init__(self, coordinator: HomeStockCoordinator) -> None:
        super().__init__(coordinator, "kcal_total", ENTITY_ID_FORMAT)

    @property
    def native_value(self) -> float:
        return self.coordinator.data["kcal_total"]


class CostTotalSensor(HomeStockEntity, SensorEntity):
    """Cumulative cost of what left the stock, purchases excluded."""

    _attr_native_unit_of_measurement = "EUR"
    # TOTAL depuis le lot 4 : une correction fait baisser ce cumul (§ A2).
    _attr_state_class = SensorStateClass.TOTAL

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
    # TOTAL depuis le lot 4 : une correction fait baisser ce cumul (§ A2).
    _attr_state_class = SensorStateClass.TOTAL

    def __init__(self, coordinator: HomeStockCoordinator) -> None:
        super().__init__(coordinator, "cost_waste_total", ENTITY_ID_FORMAT)

    @property
    def native_value(self) -> float:
        return self.coordinator.data["cost_waste_total"]


# --- lot 3 -----------------------------------------------------------------

class NextMealSensor(HomeStockEntity, SensorEntity):
    """The name of the next meal still to come.

    No meal at all leaves the state empty rather than `0`: a zero here would
    read as a meal named zero, and template authors would have to know which
    of the two it was.
    """

    def __init__(self, coordinator: HomeStockCoordinator) -> None:
        super().__init__(coordinator, "next_meal", ENTITY_ID_FORMAT)

    @property
    def _meal(self) -> dict[str, Any] | None:
        return (self.coordinator.data.get("meals") or {}).get("next")

    @property
    def native_value(self) -> str | None:
        meal = self._meal
        if meal is None:
            return None
        return meal["recipe_name"] or meal["product_name"] or meal["note"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        meal = self._meal
        if meal is None:
            return {"day": None, "slot": None, "recipe_id": None,
                    "missing_ingredients": 0}
        missing = (self.coordinator.data.get("meals") or {}).get("missing", [])
        return {
            "day": meal["day"],
            "slot": meal["slot_key"],
            "recipe_id": meal["recipe_id"],
            "missing_ingredients": len(missing),
        }


class RecipesSensor(HomeStockEntity, SensorEntity):
    """How many active recipes there are, and how much work they still need."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: HomeStockCoordinator) -> None:
        super().__init__(coordinator, "recipes", ENTITY_ID_FORMAT)

    @property
    def _recipes(self) -> dict[str, Any]:
        return (self.coordinator.data.get("meals") or {}).get("recipes", {})

    @property
    def native_value(self) -> int:
        return self._recipes.get("total", 0)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "reviewable": self._recipes.get("to_review", 0),
            "unmatched_ingredients": self._recipes.get("unmatched", 0),
        }


class MissingIngredientsSensor(HomeStockEntity, SensorEntity):
    """How many products the next seven days of meals are short of.

    A COUNTER, not a tickable list. A `todo` entity here would already be the
    shopping list, which is lot 4: ticking one would mean "bought", and that
    means a session, a price and a put-away — a whole mechanism that does not
    exist yet. The sensor carries the information; lot 4 will turn it into a
    list.
    """

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: HomeStockCoordinator) -> None:
        super().__init__(coordinator, "missing_ingredients", ENTITY_ID_FORMAT)

    @property
    def _missing(self) -> list[dict[str, Any]]:
        return (self.coordinator.data.get("meals") or {}).get("missing", [])

    @property
    def native_value(self) -> int:
        return len(self._missing)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"products": self._missing}


# --- lot 5 ---------------------------------------------------------------

class BatteriesLowSensor(HomeStockEntity, SensorEntity):
    """How many TRACKED batteries are under their own threshold.

    Three sensors, not fourteen (lot 0 § 8): the detail of one battery needs a
    form, so it belongs in the panel. What a sensor is for is the number, and
    the list that makes the number actionable — « 12 %, aucune en stock » is
    the sentence that changes what you do this evening, so it has to be DATA
    here, not a reconstruction inside a dashboard card.

    Orphans and mutes are counted apart rather than folded in: an orphaned
    battery has no level at all, so counting it in the value would make the
    number lie, and leaving it out entirely would make it invisible.
    """

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: HomeStockCoordinator) -> None:
        super().__init__(coordinator, "batteries_low", ENTITY_ID_FORMAT)

    def _low(self) -> list[dict[str, Any]]:
        low = []
        for row in self.coordinator.data["batteries"]:
            if not row["tracked"] or not row["active"]:
                continue
            percent = row["last_percent"]
            if percent is None or percent >= row["low_percent"]:
                continue
            spare = row.get("spare")
            low.append({
                "label": row["label"],
                "percent": percent,
                "verb": BATTERY_VERBS[row["kind"]],
                "entity_id": row["entity_id"],
                "spare_label": spare["label"] if spare else None,
                "spare_in_stock": spare["in_stock"] if spare else None,
            })
        low.sort(key=lambda row: (row["percent"], row["label"]))
        return low

    @property
    def native_value(self) -> int:
        return len(self._low())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        rows = [row for row in self.coordinator.data["batteries"] if row["tracked"]]
        mute = sum(1 for row in rows
                   if not row["orphaned"] and row["state"] in ("unavailable", "unknown"))
        return {
            "batteries": self._low(),
            "orphaned": sum(1 for row in rows if row["orphaned"]),
            "mute": mute,
        }


class BatteriesUndeclaredSensor(HomeStockEntity, SensorEntity):
    """Battery sensors still owed a decision.

    Two populations, one number: those with no `battery` row at all, and those
    declared with `tracked = NULL` — "discovered, not decided". The second
    group is silent in todo.maintenance, which is exactly why it must be loud
    here: that is what holds the rule "nothing fails silently". The counter
    holds it, not the task list.
    """

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: HomeStockCoordinator) -> None:
        super().__init__(coordinator, "batteries_undeclared", ENTITY_ID_FORMAT)

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data["undeclared_batteries"])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        return {
            "entities": [row["entity_id"] for row in data["undeclared_batteries"]],
            "never_declared": len(data["never_declared_batteries"]),
            "undecided": len(data["undecided_batteries"]),
        }


class WarrantyNextSensor(HomeStockEntity, SensorEntity):
    """Days until the next warranty runs out, or nothing at all.

    No `state_class`: this is a countdown that jumps when an equipment is
    added, not a measurement worth a long-term statistic. And no task is ever
    produced from it — a deadline is something you look at, not something you
    tick off.
    """

    _attr_native_unit_of_measurement = "d"

    def __init__(self, coordinator: HomeStockCoordinator) -> None:
        super().__init__(coordinator, "warranty_next", ENTITY_ID_FORMAT)

    @property
    def native_value(self) -> int | None:
        warranties = self.coordinator.data["warranties"]
        return warranties[0]["days_left"] if warranties else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"warranties": [
            {"name": row["name"], "warranty_ends_on": row["warranty_ends_on"],
             "days_left": row["days_left"]}
            for row in self.coordinator.data["warranties"]]}


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
        NextMealSensor(coordinator),
        RecipesSensor(coordinator),
        MissingIngredientsSensor(coordinator),
        BatteriesLowSensor(coordinator),
        BatteriesUndeclaredSensor(coordinator),
        WarrantyNextSensor(coordinator),
    ])
