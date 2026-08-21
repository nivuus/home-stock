"""The battery plan: which tasks appear in `todo.maintenance`, and which are
allowed to close.

Pure: no hass, no SQLite, no registry — same discipline as `domain/foodday.py`
(lot 2), and for the same reason: the rule that decides to open or close a
task in the real house must be testable without starting Home Assistant, and
especially without the house. `now` is always an argument, never
`datetime.now()`.

Two invariants hold across every branch below:
  - `items` is always a subset of `keep`. Breaking it is exactly the task
    flicker CLAUDE.md describes: the task appears, the next sync closes it,
    the one after reopens it, and Bleuenn announces it every time.
  - never close a task on an unreadable sensor. A non-numeric state, an
    orphaned anchor (`entity_id is None`), or a battery that was never read
    all feed `keep` without `items` — we only close a task on a measurement
    that proves the condition is gone.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Mapping, Sequence, TypedDict

from ..const import BATTERY_MUTE_HOURS, BATTERY_VERBS, MUTE_SUMMARY_PREFIX

# Which state earns the right to ESCALATE into a "Pile HS ?" task — not
# which state is safe. Both `unavailable` and `unknown` are unreadable, and
# both therefore hold their summary in `keep` and create nothing: that safety
# rule is honoured below for either state, and it is the one CLAUDE.md states.
#
# The difference is what each one PROVES.
#   - `unavailable`: the device stopped answering. Z2M only publishes
#     `offline` for a battery device after 25 h of silence (see the comment
#     on `BATTERY_MUTE_HOURS` in const.py), so 26 h of it is evidence of a
#     dead cell — escalating is right.
#   - `unknown`: the entity answers, it just has no usable value. That is
#     what HA looks like while it boots, right after an MQTT restart, or on a
#     probe that has not published yet. It proves nothing, so escalating on
#     it would manufacture the exact false positive this lot exists to
#     remove.
_OFFLINE_STATE = "unavailable"


class PlanItem(TypedDict):
    summary: str
    description: str
    entity: str | None


def summary_for(kind: str, label: str) -> str:
    """The one and only grammar for a level summary: `«{verb} — {label}»`.

    `BATTERY_VERBS` is the sole source of the verb — never spell it out here.
    """
    return f"{BATTERY_VERBS[kind]} — {label}"


def mute_summary_for(label: str) -> str:
    return f"{MUTE_SUMMARY_PREFIX}{label}"


def spare_suffix(cell_count: int, in_stock: float, label: str, *,
                  feminine: bool = True) -> str:
    """`«1× CR2032, aucune en stock»` / `«2× AAA, 4 en stock»`.

    Genered by the caller: piles (lot 5, task 2) default to feminine
    (`aucune`); a filter (lot 5, task 3) will pass `feminine=False` for
    `aucun`. This is the single function both tasks share — never duplicate
    it for the masculine case.

    The stock count drops its decimal when it is a whole number: `4.0` reads
    as `4`, not `4.0`.
    """
    none_word = "aucune" if feminine else "aucun"
    if in_stock == 0:
        stock = f"{none_word} en stock"
    else:
        count = str(int(in_stock)) if in_stock == int(in_stock) else str(in_stock)
        stock = f"{count} en stock"
    return f"{cell_count}× {label}, {stock}"


def _as_float(value: Any) -> float | None:
    """A usable percent, or `None` for anything that is not one: `None`
    itself, an unavailable/unknown/empty/garbage string, or NaN (`float`
    happily parses `"NaN"`, which is exactly the kind of silent success this
    module must not have)."""
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed != parsed:  # NaN is the only float that is not equal to itself.
        return None
    return parsed


def _parse_naive_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _level_description(percent: float, spare: Mapping[str, Any] | None) -> str:
    # `int()` truncates, it does not round: the macro this mirrors renders
    # `s.state | int(-1)`, so 19.6 % must read "19 %", not "20 %".
    description = f"{int(percent)} %"
    if spare is not None:
        suffix = spare_suffix(
            int(spare["cell_count"]), float(spare["in_stock"]), spare["label"],
        )
        description = f"{description} — {suffix}"
    return description


def battery_plan(batteries: Sequence[Mapping[str, Any]], *, now: datetime,
                  mute_hours: int = BATTERY_MUTE_HOURS) -> dict[str, list]:
    """One pass over `batteries`, in order:

    1. Inactive (`active` falsy, defaulting to true when absent), or
       `tracked` not true → silent everywhere (neither `items` nor `keep`):
       visibility for those lives in the undeclared-batteries counter and the
       panel, not in `todo.maintenance`.
    2. Orphaned anchor (`entity_id is None`) → `keep` only, unconditionally.
    3. Non-numeric live state (`state` does not parse to a real float) →
       `keep` only, unconditionally — we cannot prove the level is fine.
       When that state is specifically `"unavailable"` (the device itself
       went quiet, not merely "unknown") and `last_reading_at` is known, the
       mute summary joins `keep` too, as a standing protection for whatever
       task may already exist; it only becomes an `items` entry once the
       silence reaches `mute_hours`.
    4. Otherwise, compare the percent (`last_percent` when present, else the
       parsed state — they agree whenever both are supplied) to the two
       per-battery thresholds.

    `items` are sorted by ascending percent (mute items sort first, being the
    more urgent unknown); `keep` is deduplicated, keeping the order of first
    appearance. The spare suffix is added to the description only — the
    summary never moves a character.
    """
    items: list[tuple[float, PlanItem]] = []
    keep: list[str] = []

    def _add_keep(summary: str) -> None:
        if summary not in keep:
            keep.append(summary)

    for row in batteries:
        if not row.get("active", 1):
            continue
        if not row.get("tracked"):
            continue

        level_summary = summary_for(row["kind"], row["label"])
        entity_id = row.get("entity_id")

        if entity_id is None:
            _add_keep(level_summary)
            continue

        state = row.get("state")
        live_percent = _as_float(state)

        if live_percent is None:
            _add_keep(level_summary)

            if state == _OFFLINE_STATE:
                read_at = _parse_naive_iso(row.get("last_reading_at"))
                if read_at is not None:
                    mute_summary = mute_summary_for(row["label"])
                    _add_keep(mute_summary)
                    silence = now - read_at
                    if silence >= timedelta(hours=mute_hours):
                        hours = int(silence.total_seconds() // 3600)
                        items.append((float("-inf"), {
                            "summary": mute_summary,
                            "description": f"{hours} h sans nouvelle",
                            "entity": entity_id,
                        }))
            continue

        last_percent = row.get("last_percent")
        percent = float(last_percent) if last_percent is not None else live_percent
        low = float(row["low_percent"])
        keep_threshold = float(row["keep_percent"])

        if percent < keep_threshold:
            _add_keep(level_summary)
        if percent < low:
            items.append((percent, {
                "summary": level_summary,
                "description": _level_description(percent, row.get("spare")),
                "entity": entity_id,
            }))

    items.sort(key=lambda pair: pair[0])
    return {"items": [item for _, item in items], "keep": keep}
