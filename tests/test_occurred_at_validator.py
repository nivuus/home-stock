"""The occurred_at validator alone: what it accepts, what it stores, what it refuses."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
import voluptuous as vol

from custom_components.home_stock.occurred_at import past_moment, to_stored_moment

NOW = datetime(2026, 10, 3, 13, 0, 0, tzinfo=UTC)


@pytest.mark.parametrize(("given", "stored"), [
    # Paris summer time: two hours ahead of UTC.
    ("2026-10-02T12:00:00+02:00", "2026-10-02T10:00:00"),
    ("2026-10-02T10:00:00Z", "2026-10-02T10:00:00"),
    ("2026-10-02T10:00:00+00:00", "2026-10-02T10:00:00"),
    # An offset that moves the moment across midnight UTC.
    ("2026-10-02T01:30:00+02:00", "2026-10-01T23:30:00"),
    # Seconds are kept, sub-seconds dropped: the precision of application._now().
    ("2026-10-02T12:00:07.987654+02:00", "2026-10-02T10:00:07"),
    # A space instead of the T, and the basic form, are still ISO 8601.
    ("2026-10-02 12:00+02:00", "2026-10-02T10:00:00"),
    ("20261002T120000+0200", "2026-10-02T10:00:00"),
    # Winter time: one hour ahead.
    ("2026-01-15T08:00:00+01:00", "2026-01-15T07:00:00"),
])
def test_an_offset_timestamp_is_stored_as_naive_utc(given: str, stored: str) -> None:
    assert past_moment(given, now=NOW) == stored


def test_the_stored_form_matches_what_application_now_writes() -> None:
    """Same shape as application._now(): no offset, no microseconds."""
    stored = past_moment("2026-10-02T12:00:00+02:00", now=NOW)
    assert stored == to_stored_moment(datetime(2026, 10, 2, 10, tzinfo=UTC))
    assert datetime.fromisoformat(stored).tzinfo is None


@pytest.mark.parametrize("given", [
    "2026-10-02T12:00:00",        # local time without an offset: ambiguous
    "2026-10-02",                 # a bare date: no instant at all
    "2026-02-30T12:00:00+02:00",  # not a calendar date
    "2026-10-02T25:00:00+02:00",  # not a time of day
    "hier midi",
    "",
    "2026-10-02T12:00:00+02:00" + " " * 64,  # longer than any timestamp
    12345,
    None,
    ["2026-10-02T12:00:00+02:00"],
])
def test_anything_but_an_offset_timestamp_is_refused(given: object) -> None:
    with pytest.raises(vol.Invalid):
        past_moment(given, now=NOW)


def test_a_moment_in_the_future_is_refused() -> None:
    with pytest.raises(vol.Invalid, match="futur"):
        past_moment("2026-10-04T12:00:00+02:00", now=NOW)


def test_a_client_clock_slightly_ahead_is_accepted() -> None:
    ahead = (NOW + timedelta(minutes=2)).isoformat()
    assert past_moment(ahead, now=NOW) == "2026-10-03T13:02:00"


def test_past_the_skew_allowance_is_refused() -> None:
    with pytest.raises(vol.Invalid):
        past_moment((NOW + timedelta(minutes=6)).isoformat(), now=NOW)


def test_without_now_the_real_clock_is_the_reference() -> None:
    assert past_moment("2026-10-02T12:00:00+02:00") == "2026-10-02T10:00:00"
    with pytest.raises(vol.Invalid):
        past_moment("2999-01-01T00:00:00+00:00")


def test_a_moment_the_utc_conversion_cannot_hold_is_refused() -> None:
    with pytest.raises(vol.Invalid):
        past_moment("0001-01-01T00:30:00+01:00", now=NOW)
