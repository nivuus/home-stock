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


def _understood(item: Any) -> bool:
    """An item this module is allowed to touch: a mapping carrying a non-empty
    `summary`. Everything else is copied through untouched — see `merge_plan`.
    """
    return (isinstance(item, Mapping)
            and isinstance(item.get("summary"), str)
            and bool(item["summary"]))


def merge_plan(own: dict[str, list], *,
               extra_items: Sequence[Any] | None,
               extra_keep: Sequence[Any] | None,
               spares: Mapping[str, Mapping[str, Any]] | None = None,
               ) -> dict[str, list]:
    """Fold the macro's own plan into this module's battery plan.

    Four rules, each of them load-bearing:

    1. **An item we do not understand is copied verbatim, never dropped.**
       This service must not be able to make the air-purifier's filter task
       disappear because the shape of an item changed. "Not understood"
       covers an item with no `summary`, an item that is not a mapping at
       all, and an item carrying extra keys.
    2. **The order is stable**: the macro's items first, in their order, then
       lot 5's. Reconciliation does not depend on order, but a stable one
       keeps test diffs readable and Bleuenn's announcement reproducible.
    3. **A macro item is enriched by `entity`, never by the text of its
       summary.** That is the exact lesson of today's Grocy wiring, which
       looks an `entity_id` up inside a free-text description; here `spares`
       is keyed by `entity_id` and the match is a dictionary lookup. The
       spare of a macro item is a consumable — a filter, a bag, a brush — so
       its shortage reads `aucun en stock`, masculine, unlike a battery's.
    4. **A summary present on both sides is merged, not duplicated**, and it
       is the macro's that wins, description included. `home_stock` has no
       business overwriting a vacuum cleaner's own measurement.

    Nothing in here may raise on malformed input: an exception at this point
    disarms the closing pass (task 15), which is safe but costs a whole sync.
    """
    items: list[Any] = []
    summaries_seen: set[str] = set()
    spare_by_entity = spares or {}

    for raw in extra_items or ():
        if not _understood(raw):
            items.append(raw)
            continue
        item = dict(raw)
        spare = spare_by_entity.get(item.get("entity")) if item.get("entity") else None
        if spare is not None:
            suffix = spare_suffix(
                int(spare["cell_count"]), float(spare["in_stock"]), spare["label"],
                feminine=False,
            )
            description = item.get("description")
            item["description"] = f"{description} — {suffix}" if description else suffix
        summaries_seen.add(item["summary"])
        items.append(item)

    for item in own["items"]:
        if item["summary"] in summaries_seen:
            continue
        summaries_seen.add(item["summary"])
        items.append(item)

    keep: list[str] = []
    for summary in list(extra_keep or ()) + list(own["keep"]):
        if isinstance(summary, str) and summary and summary not in keep:
            keep.append(summary)

    return {"items": items, "keep": keep}
