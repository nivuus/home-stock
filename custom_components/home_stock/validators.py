"""Value validators shared by the websocket commands and the Home Assistant
services. SQLite is dynamically typed and both surfaces write straight into
it, so both need the same guarantee about what a "number", a "date" and a
"string" actually are before either one reaches a column: neither surface
is allowed to be the weaker one.
"""
from __future__ import annotations

import math
import re
from datetime import date
from typing import Any, Final

import voluptuous as vol

from .const import MAX_PARTS

_SQLITE_INT_MIN: Final = -(2**63)
_SQLITE_INT_MAX: Final = 2**63 - 1

MAX_TEXT_LENGTH: Final = 200  # generous for a product name; not for a novel

# The extended ISO 8601 calendar-date form, and only that form:
# date.fromisoformat() has accepted the compact form ("20261201") and the
# week form ("2026-W01-1") since Python 3.11, both of which then make
# SQLite's julianday() return NULL — silently dropping the batch from
# shelf-life learning and from the first-expiring-first ordering. Checked
# before fromisoformat() is even called, so the shape promised by the error
# message ("AAAA-MM-JJ") is the only shape actually accepted.
_ISO_DATE_RE: Final = re.compile(r"^\d{4}-\d{2}-\d{2}$")


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


def non_negative_float(value: Any) -> float:
    """A price: finite, and never below zero.

    A negative price is nobody's observation. Left unchecked it reached the
    append-only movement journal as a negative cost — `stock/add` with
    `price_per_base_unit: -2.5` answered success, wrote -250 € against a
    purchase, and `sensor.home_stock_stock_value` read -250. A wrong number
    written there cannot be corrected, only offset.

    Zero stays valid: a free item (a sample, a gift, a two-for-one second
    pack) is a real observation, and that distinction is load-bearing
    elsewhere in this lot — see off/open_prices._price, which rejects a
    negative Open Prices figure and keeps a zero one for the same reason.
    """
    number = finite_float(value)
    if number < 0:
        raise vol.Invalid(f"expected a number of at least 0, got {number!r}")
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


def parts_count(value: Any) -> int:
    """A number of plates: a real integer between 0 and MAX_PARTS.

    Stricter than `bounded_int` on purpose. A float would silently truncate
    (2.9 plates becoming 2 changes the divisor of someone's calories), and a
    bool is an integer in Python — `parts_mine: true` must not be read as one
    plate.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise vol.Invalid(f"expected a whole number of parts, got {preview(value)}")
    if not 0 <= value <= MAX_PARTS:
        raise vol.Invalid(f"parts must be between 0 and {MAX_PARTS}, got {value}")
    return value


def preview(value: Any, limit: int = 80) -> str:
    """A short, safe-to-echo representation of a value for an error message.
    repr() of a 500 000-character string would repeat the whole thing back
    to whoever just sent it."""
    text = repr(value)
    return text if len(text) <= limit else f"{text[:limit]}…"


def bounded_text(value: Any) -> str | None:
    """Free text, capped. A 500 000-character label is not something a
    person typed, nor something an edit should have to echo back in full to
    refuse."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise vol.Invalid(f"expected a string, got {preview(value)}")
    if len(value) > MAX_TEXT_LENGTH:
        raise vol.Invalid(
            f"text too long: {len(value)} characters (max {MAX_TEXT_LENGTH})")
    return value


def iso_date(value: Any) -> str | None:
    """A calendar date, ISO 8601 extended form (AAAA-MM-JJ), or nothing.

    Both surfaces need this, and the household drives them both: a bad
    value here is not just refused input, it is `application.py`'s
    `summary()` raising `ValueError` on every coordinator refresh from the
    moment it is stored — every sensor and the todo entity go `unavailable`
    and stay there, in a table an append-only design cannot repair short of
    hand-editing the database. "pas une date" (a voice command, a template
    that rendered wrong) must never reach a batch row.
    """
    if value is None:
        return None
    if not isinstance(value, str) or not _ISO_DATE_RE.match(value):
        raise vol.Invalid(f"date attendue au format AAAA-MM-JJ, reçu : {preview(value)}")
    try:
        date.fromisoformat(value)
    except ValueError as err:
        raise vol.Invalid(
            f"date attendue au format AAAA-MM-JJ, reçu : {preview(value)}") from err
    return value
