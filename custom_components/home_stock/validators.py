"""Value validators shared by the websocket commands and the Home Assistant
services. SQLite is dynamically typed and both surfaces write straight into
it, so both need the same guarantee about what a "number" actually is
before it reaches a column: neither is allowed to be the weaker one.
"""
from __future__ import annotations

import math
from typing import Any, Final

import voluptuous as vol

_SQLITE_INT_MIN: Final = -(2**63)
_SQLITE_INT_MAX: Final = 2**63 - 1


def finite_float(value: Any) -> float:
    """A real, finite number. `vol.Coerce(float)` alone accepts "inf",
    "-inf" and "nan": an infinite quantity or price would reach the
    append-only movement/batch/price rows as `Inf` — which Home Assistant's
    JSON encoder then renders as `null`, so a panel or a voice answer shows
    nothing amiss — and NaN would land as SQL NULL just as silently. All
    three are refused here instead of ever reaching a column, whichever
    surface (websocket command or `home_stock.*` service) the value arrived
    through.
    """
    if isinstance(value, bool):
        raise vol.Invalid(f"expected a number, got bool {value!r}")
    try:
        number = float(value)
    except (TypeError, ValueError) as err:
        raise vol.Invalid(f"expected a number, got {value!r}") from err
    if not math.isfinite(number):
        raise vol.Invalid(f"expected a finite number, got {value!r}")
    return number


def bounded_int(value: Any) -> int:
    """A whole number SQLite can actually store as an INTEGER (signed
    64-bit). `vol.Coerce(int)` (and Home Assistant's own `cv.positive_int`,
    which is built on it) truncates a float silently — `aisle_id: 3.7`
    would quietly file the product in aisle 3, a different aisle than the
    one asked for — accepts a bare JSON `true` as `1`, and never bounds the
    result, so a JSON number like `1e308` (or `2**70`) sails through as a
    giant int and only fails later, uncaught, when sqlite3 raises
    OverflowError at bind time. All three are refused here.
    """
    if isinstance(value, bool):
        raise vol.Invalid(f"expected a whole number, got bool {value!r}")
    if isinstance(value, float):
        if not math.isfinite(value) or value != int(value):
            raise vol.Invalid(f"expected a whole number, got {value!r}")
        number = int(value)
    elif isinstance(value, int):
        number = value
    elif isinstance(value, str):
        try:
            number = int(value.strip())
        except ValueError as err:
            # A numeric-looking string like "3.7" is refused the same way,
            # rather than accepted via a float round-trip nobody asked for.
            raise vol.Invalid(f"expected a whole number, got {value!r}") from err
    else:
        raise vol.Invalid(f"expected a whole number, got {value!r}")
    if not _SQLITE_INT_MIN <= number <= _SQLITE_INT_MAX:
        raise vol.Invalid(f"out of range for a 64-bit integer: {value!r}")
    return number
