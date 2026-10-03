"""`occurred_at`: the moment a movement really happened, sent by a client.

`movement.occurred_at` holds a naive UTC ISO string at second precision —
`application._now()` writes exactly that, and `domain/foodday.py` compares
every food-day bound against it as plain text. A client, on the other hand,
knows the moment in its own local time. So the value is accepted only when it
names an instant without ambiguity (an ISO 8601 timestamp carrying its UTC
offset, or `Z`), and it is converted here, at the edge, into the stored form.
Passing "2026-10-02T12:00:00+02:00" through as given would book it two hours
late, which is enough to change its food day near the 04:00 boundary.

A local time without an offset, or a bare date, is refused rather than
guessed: whether it meant UTC or the household's time is exactly what cannot
be known here. So is a moment in the future: antidating is the point, and a
movement booked into a day that has not happened yet would sit in tomorrow's
totals. A small allowance absorbs a client clock running slightly ahead.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Final

import voluptuous as vol

# A client clock a little ahead of the server's must not turn "now" into a
# refusal; anything later than this is a typo or a wrong year, not skew.
CLOCK_SKEW_ALLOWANCE: Final = timedelta(minutes=5)

# The longest ISO 8601 timestamp is far shorter; anything longer is not one.
MAX_TIMESTAMP_LENGTH: Final = 64

_EXPECTED: Final = (
    "horodatage ISO 8601 avec fuseau attendu (ex. 2026-10-02T12:30:00+02:00)")


def to_stored_moment(moment: datetime) -> str:
    """The form `movement.occurred_at` holds: naive UTC ISO, to the second."""
    return moment.astimezone(UTC).replace(tzinfo=None, microsecond=0).isoformat()


def past_moment(value: Any, *, now: datetime | None = None) -> str:
    """Validate a client's `occurred_at` and return it in the stored form.

    Raises `vol.Invalid` — which the websocket layer answers with
    `invalid_format` — on anything that is not a past, offset-carrying
    ISO 8601 timestamp. `now` exists for tests; callers leave it out.
    """
    if not isinstance(value, str) or len(value) > MAX_TIMESTAMP_LENGTH:
        raise vol.Invalid(f"{_EXPECTED}, reçu : {value!r:.80}")
    try:
        moment = datetime.fromisoformat(value)
    except ValueError as err:
        raise vol.Invalid(f"{_EXPECTED}, reçu : {value!r}") from err
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise vol.Invalid(f"fuseau horaire manquant : {_EXPECTED}, reçu : {value!r}")
    try:
        utc = moment.astimezone(UTC)
    except OverflowError as err:
        raise vol.Invalid(f"{_EXPECTED}, reçu : {value!r}") from err
    reference = now or datetime.now(UTC)
    if utc > reference + CLOCK_SKEW_ALLOWANCE:
        raise vol.Invalid(f"occurred_at est dans le futur : {value!r}")
    return to_stored_moment(utc)
