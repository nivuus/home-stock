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
from typing import Any, Final, Mapping

import voluptuous as vol

from .const import MAX_PARTS, PRICE_SOURCES

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


# --- lot 5 : les invariants de pile, écrits UNE fois pour les deux surfaces ---
#
# Le voluptuous d'un service et celui d'un websocket peuvent valider *un champ*
# de la même façon sans effort ; ils divergent toujours sur les règles qui
# LIENT deux champs, parce que ce sont les seules qu'on écrit à la main deux
# fois. `keep_percent >= low_percent` est exactement de celles-là, et un
# `keep` plus bas qu'un `low` fait clignoter la tâche à chaque synchronisation.
# D'où une seule fonction, appelée par le service, par le websocket, et par la
# troisième porte que personne ne pense à compter : l'import, qui écrit 14
# lignes d'un coup.

MAX_CELL_COUNT: Final = 24


def percent_threshold(value: Any) -> float:
    """A battery threshold: a real, finite number between 0 and 100.

    Accepts the French decimal comma ("25,5"), because these thresholds are
    typed on a tablet in a French household — and a comma silently refused
    would read as "the app is broken", not as "use a dot".
    """
    if isinstance(value, str):
        value = value.replace(",", ".")
    number = finite_float(value)
    if not 0.0 <= number <= 100.0:
        raise vol.Invalid(f"percent must be between 0 and 100, got {preview(value)}")
    return number


def cell_count(value: Any) -> int:
    """How many cells a place holds: a real integer, at least one.

    Stricter than `bounded_int` on purpose, and for the same reason as
    `parts_count`: a float would truncate silently, and a bool is an integer
    in Python — `cell_count: true` must not be read as one cell. Zero is
    refused because a place with no cell is not a place, and it would make a
    replacement consume nothing while claiming success.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise vol.Invalid(f"expected a whole number of cells, got {preview(value)}")
    if not 1 <= value <= MAX_CELL_COUNT:
        raise vol.Invalid(
            f"cell_count must be between 1 and {MAX_CELL_COUNT}, got {value}")
    return value


def tracked_flag(value: Any) -> bool | None:
    """True, False or None — strictly, and nothing else.

    The three values mean three different things (`suivie`, `écartée avec un
    motif`, `découverte mais pas décidée`), and the middle one is the only
    one that demands an `exclusion_reason`. Accepting 0/1/"oui" here would let
    a caller land in the wrong one of the three without noticing.
    """
    if value is None or value is True or value is False:
        return value
    raise vol.Invalid(f"expected true, false or null, got {preview(value)}")


def check_battery_fields(fields: Mapping[str, Any], *, kind: str) -> None:
    """The invariants that bind two fields together, checked once for every
    surface. Raises `vol.Invalid` in English; `messages.py` carries the French.

    Only the keys actually present are checked: this same function validates a
    full declaration and a partial update.
    """
    if "cell_count" in fields and fields["cell_count"] is not None:
        cell_count(fields["cell_count"])

    low = fields.get("low_percent")
    keep = fields.get("keep_percent")
    if low is not None:
        low = percent_threshold(low)
    if keep is not None:
        keep = percent_threshold(keep)
    if low is not None and keep is not None and keep < low:
        raise vol.Invalid(
            f"keep_percent must not be below low_percent: {keep} < {low}")

    if "tracked" in fields:
        tracked = tracked_flag(fields["tracked"])
        if tracked is False and not (fields.get("exclusion_reason") or "").strip():
            raise vol.Invalid("an untracked battery needs a reason")

    if kind == "built_in" and fields.get("product_id") is not None:
        raise vol.Invalid("a built_in battery has no spare")

    if fields.get("installed_on") is not None:
        iso_date(fields["installed_on"])


def check_battery_event(kind: str, *, battery_kind: str, consume_spare: bool,
                        product_id: int | None) -> None:
    """What a given nature of battery is physically able to undergo.

    A disposable cell does not get charged, and a soldered battery does not
    get replaced — recording either would put an event in an append-only
    table that describes something that did not happen.
    """
    if kind == "charge" and battery_kind == "primary":
        raise vol.Invalid("a primary battery cannot be charged")
    if kind == "replacement" and battery_kind == "built_in":
        raise vol.Invalid("a built_in battery cannot be replaced")
    if consume_spare and product_id is None:
        raise vol.Invalid("cannot consume a spare without a spare product")


def media_path(value: Any) -> str | None:
    """A file under Home Assistant's `media/`, and nowhere else.

    Three shapes are refused, each for its own reason:
      - an ABSOLUTE path ("/etc/passwd"), which is not under media/ at all;
      - a path that CLIMBS ("../config/secrets.yaml"): `..` anywhere in it
        makes the final location impossible to reason about locally;
      - anything under `www/`, because everything served from there is
        reachable on `/local/` WITHOUT authentication — and a manual carries
        a serial number, a receipt carries a name and a price.

    Nothing here checks that the file EXISTS: a missing file is reported as
    "introuvable" by the panel, and no entity becomes unavailable over it.
    """
    if value is None:
        return None
    text = bounded_text(value)
    if text is None:
        return None
    cleaned = text.strip()
    if not cleaned:
        return None
    if cleaned.startswith("/") or cleaned.startswith("\\"):
        raise vol.Invalid(f"media path must be relative, got {preview(value)}")
    normalised = cleaned.replace("\\", "/")
    if ".." in normalised.split("/"):
        raise vol.Invalid(f"media path must not climb out of media/, got {preview(value)}")
    if normalised.lower().startswith("www/"):
        raise vol.Invalid(
            f"media path must not point under www/, got {preview(value)}")
    return cleaned


# --- lot 4 -----------------------------------------------------------------
# En fin de fichier, et sans toucher à `bounded_text`, `finite_float`,
# `iso_date` ni `media_path` : les deux surfaces (websocket et services)
# lisent les mêmes bornes, et aucune n'a le droit d'être la plus faible.

def price_source(value: Any) -> str | None:
    """L'une de `PRICE_SOURCES`, ou `None`.

    Un mot inconnu est refusé plutôt que rangé tel quel : `source` décide du
    rang 1 de la cascade (amendement A3), et une faute de frappe y ferait
    disparaître un prix réellement observé sans que rien ne le signale.
    """
    if value is None:
        return None
    text = bounded_text(value)
    if not text:
        return None
    if text not in PRICE_SOURCES:
        raise vol.Invalid(
            f"unknown price source '{text}'; expected one of {PRICE_SOURCES}")
    return text
