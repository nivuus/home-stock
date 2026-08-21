"""Constants shared across the integration."""
from typing import Final

DOMAIN: Final = "home_stock"

BASE_UNITS: Final = ("g", "ml", "piece")

# Movement reasons. See spec section 7.5 for the sign and accounting rules.
REASON_PURCHASE: Final = "purchase"
REASON_CONSUMPTION: Final = "consumption"
REASON_WASTE: Final = "waste"
REASON_EXPIRED: Final = "expired"
REASON_INVENTORY: Final = "inventory"
REASON_TRANSFER: Final = "transfer"
REASON_CONVERSION: Final = "conversion"
REASONS: Final = (
    REASON_PURCHASE,
    REASON_CONSUMPTION,
    REASON_WASTE,
    REASON_EXPIRED,
    REASON_INVENTORY,
    REASON_TRANSFER,
    REASON_CONVERSION,
)

# Reasons a "consume" call may legitimately carry — offered by both the
# services.yaml selector and the websocket schema. The other three reasons
# (purchase, inventory, transfer) are written exclusively by
# add_stock/adjust_inventory/transfer_batch; letting them through here would
# tag a negative-quantity movement with a reason that repo.totals_between/
# journal_entries/counted_movements do not track, silently under-counting
# the kcal, cost or cost_waste totals for stock that really did leave the
# pantry. Lives here, not in services.py, so the websocket surface can use
# the exact same tuple without importing from the older module — the newer
# surface must not be at the mercy of the older one.
CONSUME_REASONS: Final = (REASON_CONSUMPTION, REASON_WASTE, REASON_EXPIRED)

DATABASE_FILENAME: Final = "home_stock.db"
DEFAULT_EXPIRATION_ALERT_DAYS: Final = 3
CONF_EXPIRATION_ALERT_DAYS: Final = "expiration_alert_days"

# Below this many base units, a batch is empty: floating point dust (spec 7.2).
QUANTITY_EPSILON: Final = 0.001

# The eight macros of `article`, exactly as the schema names them. `kcal` is
# not among them: it is `kcal_per_base_unit` on `article` and `kcal` on
# `movement`, and it is the only one with a fallback at the product level
# (`product.reference_kcal`).
MACRO_COLUMNS: Final = (
    "proteins", "carbohydrates", "sugars", "added_sugars",
    "fat", "saturated_fat", "fiber", "salt",
)

# A serving above this value is not a serving: it is a data entry mistake in
# a collaborative database (a pallet announced in grams).
MAX_SERVING: Final = 5000.0

# A food day runs from 04:00 local to 04:00 local: what you eat at one in the
# morning belongs to the evening you are still finishing, not to the calendar
# day that just started.
FOOD_DAY_START_HOUR: Final = 4

# Twenty-four plates is already a party; past that it is a typo, and the
# number ends up dividing someone's calories by a hundred.
MAX_PARTS: Final = 24
