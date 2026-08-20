"""Where a food day starts, and how a series is bucketed.

Pure: no hass, no SQLite. The timezone is passed in, never looked up here —
that is what makes both daylight-saving changes testable without starting
anything.

Every bound this module returns is a **naive UTC ISO string**, because that is
what `movement.occurred_at` holds (lot 0). Comparing two ISO strings in SQLite
is then exact, and needs no timezone database on SQLite's side — which is just
as well, since SQLite has none.
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import NamedTuple
from zoneinfo import ZoneInfo

from ..const import FOOD_DAY_START_HOUR

GRANULARITIES = ("day", "week", "month")


class Bucket(NamedTuple):
    """One bar of a series: its label, and the half-open range it covers."""

    label: str      # ISO date of the bucket's first food day
    start: str      # naive UTC ISO, inclusive
    end: str        # naive UTC ISO, exclusive


def _to_naive_utc(moment: datetime) -> str:
    return moment.astimezone(UTC).replace(tzinfo=None, microsecond=0).isoformat()


def _start_of(day: date, tz: ZoneInfo) -> datetime:
    """04:00 local on that date. Neither ambiguous nor missing in any zone
    that shifts at 02:00 or 03:00, which is every European one; elsewhere
    `fold=0` picks the first occurrence, deterministically."""
    return datetime(day.year, day.month, day.day, FOOD_DAY_START_HOUR, tzinfo=tz)


def food_day_of(moment: datetime, tz: ZoneInfo) -> date:
    """The date this moment is booked against."""
    local = moment.astimezone(tz)
    if local.hour < FOOD_DAY_START_HOUR:
        return (local - timedelta(days=1)).date()
    return local.date()


def bounds_of_food_day(day: date, tz: ZoneInfo) -> tuple[str, str]:
    """[start, end[ of one food day, in naive UTC ISO.

    The two bounds are computed from two different local dates, each with its
    own UTC offset: that is precisely why a spring day comes out 23 hours long
    and an autumn one 25, instead of a hard-coded 24 that would leak an hour
    of meals into the neighbouring day twice a year.
    """
    return (_to_naive_utc(_start_of(day, tz)),
            _to_naive_utc(_start_of(day + timedelta(days=1), tz)))


def food_day_bounds(moment: datetime, tz: ZoneInfo) -> tuple[str, str]:
    """[start, end[ of the food day containing `moment`."""
    return bounds_of_food_day(food_day_of(moment, tz), tz)


def _first_day_of_bucket(day: date, granularity: str) -> date:
    if granularity == "day":
        return day
    if granularity == "week":
        return day - timedelta(days=day.weekday())
    return day.replace(day=1)


def _previous_bucket(day: date, granularity: str) -> date:
    if granularity == "day":
        return day - timedelta(days=1)
    if granularity == "week":
        return day - timedelta(days=7)
    return (day - timedelta(days=1)).replace(day=1)


def _next_bucket(day: date, granularity: str) -> date:
    if granularity == "day":
        return day + timedelta(days=1)
    if granularity == "week":
        return day + timedelta(days=7)
    # Day 28 exists in every month, so +4 days always lands in the next one.
    return (day.replace(day=28) + timedelta(days=4)).replace(day=1)


def bucket_bounds(granularity: str, count: int, now: datetime,
                  tz: ZoneInfo) -> list[Bucket]:
    """The `count` most recent buckets, oldest first, current one last."""
    if granularity not in GRANULARITIES:
        raise ValueError(f"unknown granularity {granularity!r}")
    if count < 1:
        raise ValueError(f"count must be at least 1, got {count}")

    first = _first_day_of_bucket(food_day_of(now, tz), granularity)
    starts = [first]
    for _ in range(count - 1):
        starts.append(_previous_bucket(starts[-1], granularity))
    starts.reverse()

    return [
        Bucket(label=start.isoformat(),
               start=_to_naive_utc(_start_of(start, tz)),
               end=_to_naive_utc(_start_of(_next_bucket(start, granularity), tz)))
        for start in starts
    ]
