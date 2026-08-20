"""La journée alimentaire court de 4 h à 4 h, heure locale.

`occurred_at` est stocké en UTC naïf (décision du lot 0) : toutes les bornes
rendues par ce module sont donc en UTC naïf elles aussi, pour que la
comparaison SQL reste une comparaison de chaînes ISO.
"""
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest

from custom_components.home_stock.domain.foodday import (
    bucket_bounds, bounds_of_food_day, food_day_bounds, food_day_of,
)

PARIS = ZoneInfo("Europe/Paris")


def _paris(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=PARIS)


def test_a_meal_at_three_in_the_morning_belongs_to_the_day_before():
    assert food_day_of(_paris("2026-08-20T03:30:00"), PARIS) == date(2026, 8, 19)


def test_a_meal_at_four_starts_the_new_day():
    assert food_day_of(_paris("2026-08-20T04:00:00"), PARIS) == date(2026, 8, 20)
    assert food_day_of(_paris("2026-08-20T03:59:59"), PARIS) == date(2026, 8, 19)


def test_bounds_are_utc_naive_iso():
    start, end = food_day_bounds(_paris("2026-08-20T12:00:00"), PARIS)
    # Été : Paris est à UTC+2, donc 4 h locales valent 2 h UTC.
    assert start == "2026-08-20T02:00:00"
    assert end == "2026-08-21T02:00:00"


def test_bounds_in_winter_shift_with_the_offset():
    start, end = food_day_bounds(_paris("2026-01-15T12:00:00"), PARIS)
    assert start == "2026-01-15T03:00:00"
    assert end == "2026-01-16T03:00:00"


def test_the_spring_forward_day_is_twenty_three_hours_long():
    """Paris avance ses horloges dans la nuit du 28 au 29 mars 2026 (02:00 →
    03:00). La journée alimentaire raccourcie est donc celle du **28**, qui
    commence à 4 h en heure d'hiver et finit à 4 h en heure d'été. Celle du 29
    dure 24 heures pleines — se tromper de jour ici passerait inaperçu, et
    c'est exactement l'erreur que ce test existe pour empêcher."""
    start, end = bounds_of_food_day(date(2026, 3, 28), PARIS)
    assert start == "2026-03-28T03:00:00"    # 4 h locales = UTC+1 ce matin-là
    assert end == "2026-03-29T02:00:00"      # 4 h locales = UTC+2 le lendemain
    duration = datetime.fromisoformat(end) - datetime.fromisoformat(start)
    assert duration.total_seconds() == 23 * 3600


def test_the_autumn_day_is_twenty_five_hours_long():
    """Paris recule ses horloges dans la nuit du 24 au 25 octobre 2026
    (03:00 → 02:00) : c'est la journée du **24** qui dure 25 heures."""
    start, end = bounds_of_food_day(date(2026, 10, 24), PARIS)
    assert start == "2026-10-24T02:00:00"
    assert end == "2026-10-25T03:00:00"
    duration = datetime.fromisoformat(end) - datetime.fromisoformat(start)
    assert duration.total_seconds() == 25 * 3600


def test_the_day_after_a_change_is_back_to_twenty_four_hours():
    """Le garde-fou du test précédent : si les bornes étaient calculées depuis
    une seule date locale, ces deux journées-ci sortiraient fausses aussi."""
    for day in (date(2026, 3, 29), date(2026, 10, 25)):
        start, end = bounds_of_food_day(day, PARIS)
        duration = datetime.fromisoformat(end) - datetime.fromisoformat(start)
        assert duration.total_seconds() == 24 * 3600, day


def test_a_movement_stored_in_utc_lands_in_the_right_day_across_the_change():
    """Le vrai piège : un repas à 03:30 locales le lendemain du changement.
    Stocké en UTC naïf, il doit tomber dans la journée de la veille."""
    stored = "2026-10-26T02:30:00"        # 03:30 à Paris, UTC+1 ce jour-là
    start, end = bounds_of_food_day(date(2026, 10, 25), PARIS)
    assert (start, end) == ("2026-10-25T03:00:00", "2026-10-26T03:00:00")
    assert start <= stored < end


def test_buckets_by_day_are_contiguous_and_ordered():
    now = _paris("2026-08-20T12:00:00")
    buckets = bucket_bounds("day", 3, now, PARIS)
    assert [b.label for b in buckets] == ["2026-08-18", "2026-08-19", "2026-08-20"]
    assert buckets[0].end == buckets[1].start
    assert buckets[1].end == buckets[2].start


def test_buckets_by_week_start_on_monday():
    now = _paris("2026-08-20T12:00:00")           # un jeudi
    buckets = bucket_bounds("week", 2, now, PARIS)
    assert [b.label for b in buckets] == ["2026-08-10", "2026-08-17"]


def test_buckets_by_month_start_on_the_first():
    now = _paris("2026-08-20T12:00:00")
    buckets = bucket_bounds("month", 3, now, PARIS)
    assert [b.label for b in buckets] == ["2026-06-01", "2026-07-01", "2026-08-01"]


def test_a_month_bucket_starts_at_four_in_the_morning_too():
    buckets = bucket_bounds("month", 1, _paris("2026-08-20T12:00:00"), PARIS)
    assert buckets[0].start == "2026-08-01T02:00:00"


def test_an_unknown_granularity_is_refused():
    with pytest.raises(ValueError):
        bucket_bounds("fortnight", 3, _paris("2026-08-20T12:00:00"), PARIS)


def test_a_count_below_one_is_refused():
    with pytest.raises(ValueError):
        bucket_bounds("day", 0, _paris("2026-08-20T12:00:00"), PARIS)


def test_an_aware_utc_moment_is_accepted_as_well():
    """Le coordinateur passe `dt_util.utcnow()`, qui porte UTC."""
    assert food_day_of(datetime(2026, 8, 20, 1, 0, tzinfo=UTC), PARIS) == date(2026, 8, 19)
