"""The food day as seen from the application layer."""
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest

from custom_components.home_stock.const import MACRO_COLUMNS
from test_application import _seed_article

PARIS = ZoneInfo("Europe/Paris")
NOON = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)


def test_the_day_totals_only_hold_today(manager):
    article_id, product_id = _seed_article(manager, base_unit="g", kcal_per_base_unit=1.2)
    manager.add_stock(article_id=article_id, quantity=1000.0, location_id=1)
    # Yesterday 20:00 local = 18:00 UTC the day before.
    manager.consume(product_id=product_id, quantity=100.0,
                    occurred_at="2026-08-19T18:00:00")
    manager.consume(product_id=product_id, quantity=200.0,
                    occurred_at="2026-08-20T10:00:00")

    summary = manager.summary(expiration_alert_days=3, tz=PARIS, now=NOON)

    assert summary["today"]["kcal"] == pytest.approx(240.0)
    assert summary["today"]["food_day"] == "2026-08-20"
    # Naive UTC ISO, like every other bound this module returns: 04:00 Paris
    # in August (UTC+2) is 02:00 UTC.
    assert summary["today"]["start"] == "2026-08-20T02:00:00"


def test_a_meal_at_two_in_the_morning_belongs_to_yesterday(manager):
    article_id, product_id = _seed_article(manager, base_unit="g", kcal_per_base_unit=1.2)
    manager.add_stock(article_id=article_id, quantity=1000.0, location_id=1)
    # 02:00 Paris time on August 20 = 00:00 UTC: still the food day of the 19th.
    manager.consume(product_id=product_id, quantity=100.0,
                    occurred_at="2026-08-20T00:00:00")

    summary = manager.summary(expiration_alert_days=3, tz=PARIS, now=NOON)
    assert summary["today"]["kcal"] == 0.0


def test_kcal_total_no_longer_counts_what_was_thrown_away(manager):
    article_id, product_id = _seed_article(manager, base_unit="g", kcal_per_base_unit=1.2)
    manager.add_stock(article_id=article_id, quantity=1000.0, location_id=1)
    manager.consume(product_id=product_id, quantity=100.0)
    manager.consume(product_id=product_id, quantity=200.0, reason="waste")

    summary = manager.summary(expiration_alert_days=3, tz=PARIS, now=NOON)
    assert summary["kcal_total"] == pytest.approx(120.0)


def test_waste_has_its_own_euro_counter(manager):
    article_id, product_id = _seed_article(manager, base_unit="g", kcal_per_base_unit=1.2)
    manager.add_stock(article_id=article_id, quantity=1000.0, location_id=1,
                      price_per_base_unit=0.01)
    manager.consume(product_id=product_id, quantity=100.0)
    manager.consume(product_id=product_id, quantity=200.0, reason="expired")

    summary = manager.summary(expiration_alert_days=3, tz=PARIS, now=NOON)
    assert summary["cost_total"] == pytest.approx(1.0)
    assert summary["cost_waste_total"] == pytest.approx(2.0)


def test_the_day_reports_how_much_it_could_not_value(manager):
    article_id, product_id = _seed_article(manager, base_unit="g", kcal_per_base_unit=None)
    manager.add_stock(article_id=article_id, quantity=1000.0, location_id=1)
    manager.consume(product_id=product_id, quantity=100.0,
                    occurred_at="2026-08-20T10:00:00")

    summary = manager.summary(expiration_alert_days=3, tz=PARIS, now=NOON)
    assert summary["today"]["unvalued"] == 1


def test_journal_day_lists_the_entries_of_that_day(manager):
    article_id, product_id = _seed_article(manager, base_unit="g", kcal_per_base_unit=1.2)
    manager.add_stock(article_id=article_id, quantity=1000.0, location_id=1)
    manager.consume(product_id=product_id, quantity=200.0,
                    occurred_at="2026-08-20T10:00:00")

    day = manager.journal_day(date(2026, 8, 20), tz=PARIS, now=NOON)
    assert day["food_day"] == "2026-08-20"
    assert day["start"] == "2026-08-20T02:00:00"
    assert len(day["entries"]) == 1
    assert day["entries"][0]["product_name"]
    assert day["totals"]["kcal"] == pytest.approx(240.0)


def test_journal_day_defaults_to_the_current_food_day(manager):
    day = manager.journal_day(None, tz=PARIS, now=NOON)
    assert day["food_day"] == "2026-08-20"


def test_journal_series_buckets_by_day(manager):
    article_id, product_id = _seed_article(manager, base_unit="g", kcal_per_base_unit=1.2)
    manager.add_stock(article_id=article_id, quantity=2000.0, location_id=1)
    manager.consume(product_id=product_id, quantity=100.0,
                    occurred_at="2026-08-19T10:00:00")
    manager.consume(product_id=product_id, quantity=200.0,
                    occurred_at="2026-08-20T10:00:00")

    series = manager.journal_series("day", 3, tz=PARIS, now=NOON)
    assert [b["label"] for b in series["buckets"]] == ["2026-08-18", "2026-08-19", "2026-08-20"]
    assert [b["kcal"] for b in series["buckets"]] == [0.0, pytest.approx(120.0),
                                                      pytest.approx(240.0)]


def test_journal_series_applies_the_parts_like_the_day_does(manager):
    article_id, product_id = _seed_article(manager, base_unit="g", kcal_per_base_unit=1.2)
    manager.add_stock(article_id=article_id, quantity=2000.0, location_id=1,
                      price_per_base_unit=0.01)
    manager.consume(product_id=product_id, quantity=400.0, parts_total=4, parts_mine=1,
                    occurred_at="2026-08-20T10:00:00")

    series = manager.journal_series("day", 1, tz=PARIS, now=NOON)
    bucket = series["buckets"][0]
    assert bucket["kcal"] == pytest.approx(120.0)
    # The pack cost what it cost, whether it was eaten alone or shared four
    # ways: unlike kcal, cost is never divided by the parts (spec 7).
    assert bucket["cost"] == pytest.approx(4.0)


def test_journal_series_keeps_waste_out_of_the_calories_but_in_the_euros(manager):
    article_id, product_id = _seed_article(manager, base_unit="g", kcal_per_base_unit=1.2)
    manager.add_stock(article_id=article_id, quantity=2000.0, location_id=1,
                      price_per_base_unit=0.01)
    manager.consume(product_id=product_id, quantity=200.0, reason="waste",
                    occurred_at="2026-08-20T10:00:00")

    bucket = manager.journal_series("day", 1, tz=PARIS, now=NOON)["buckets"][0]
    assert bucket["kcal"] == 0.0
    assert bucket["cost"] == 0.0
    assert bucket["waste_cost"] == pytest.approx(2.0)


def test_journal_series_refuses_an_unknown_granularity(manager):
    with pytest.raises(ValueError):
        manager.journal_series("fortnight", 3, tz=PARIS, now=NOON)


# --- Lot 2bis : la moyenne des sept journées closes -------------------------

def _seven_days_of_meals(manager, product_id, days, *, grams=100.0):
    """Un repas de `grams` à midi UTC sur chacune des journées données."""
    for day in days:
        manager.consume(product_id=product_id, quantity=grams,
                        occurred_at=f"{day}T12:00:00")


def test_the_week_mean_ignores_what_was_eaten_today(manager):
    """La journée courante est exclue : l'inclure ferait chuter la moyenne
    toute la matinée puis remonter au dîner, et le capteur clignoterait."""
    article_id, product_id = _seed_article(manager, base_unit="g",
                                           kcal_per_base_unit=1.2)
    manager.add_stock(article_id=article_id, quantity=5000.0, location_id=1)
    _seven_days_of_meals(manager, product_id, ["2026-08-18", "2026-08-19"])

    before = manager.summary(expiration_alert_days=3, tz=PARIS, now=NOON)["week_mean"]
    manager.consume(product_id=product_id, quantity=2000.0,
                    occurred_at="2026-08-20T10:00:00")
    after = manager.summary(expiration_alert_days=3, tz=PARIS, now=NOON)["week_mean"]

    assert before["kcal"] == pytest.approx(round(2 * 120.0 / 7, 1))
    assert after == before


def test_the_week_mean_divides_by_seven_days_across_a_23_hour_day(manager):
    """La journée alimentaire du 28 mars 2026 dure 23 h (passage à l'heure
    d'été). Le diviseur reste SEPT JOURNÉES, jamais une durée."""
    article_id, product_id = _seed_article(manager, base_unit="g",
                                           kcal_per_base_unit=1.2)
    manager.add_stock(article_id=article_id, quantity=5000.0, location_id=1)
    _seven_days_of_meals(manager, product_id, ["2026-03-28"])

    summary = manager.summary(expiration_alert_days=3, tz=PARIS,
                              now=datetime(2026, 4, 1, 12, 0, tzinfo=UTC))
    assert summary["week_mean"]["kcal"] == pytest.approx(round(120.0 / 7, 1))


def test_the_week_mean_divides_by_seven_days_across_a_25_hour_day(manager):
    """Et celle du 24 octobre 2026 en dure 25 (retour à l'heure d'hiver)."""
    article_id, product_id = _seed_article(manager, base_unit="g",
                                           kcal_per_base_unit=1.2)
    manager.add_stock(article_id=article_id, quantity=5000.0, location_id=1)
    _seven_days_of_meals(manager, product_id, ["2026-10-24"])

    summary = manager.summary(expiration_alert_days=3, tz=PARIS,
                              now=datetime(2026, 10, 28, 12, 0, tzinfo=UTC))
    assert summary["week_mean"]["kcal"] == pytest.approx(round(120.0 / 7, 1))


def test_a_database_without_history_has_a_week_mean_of_zeros(manager):
    """Zéro partout, et non `None` : le capteur d'objectifs pourra donc être
    `off` sur une base neuve, sans garde particulière."""
    summary = manager.summary(expiration_alert_days=3, tz=PARIS, now=NOON)
    week = summary["week_mean"]
    assert week["kcal"] == 0.0
    assert all(week[column] == 0.0 for column in MACRO_COLUMNS)
    assert week["cost"] == 0.0
    assert week["waste_cost"] == 0.0
    assert week["unvalued"] == 0


def test_the_week_window_starts_at_the_bound_of_the_seventh_previous_food_day(manager):
    """La borne basse est `bounds_of_food_day(J-7)`, pas « il y a 168 h »."""
    article_id, product_id = _seed_article(manager, base_unit="g",
                                           kcal_per_base_unit=1.2)
    manager.add_stock(article_id=article_id, quantity=5000.0, location_id=1)
    # J-8 à 23:00 local (21:00 UTC) : journée alimentaire du 12, hors fenêtre.
    manager.consume(product_id=product_id, quantity=100.0,
                    occurred_at="2026-08-12T21:00:00")
    assert manager.summary(expiration_alert_days=3, tz=PARIS,
                           now=NOON)["week_mean"]["kcal"] == 0.0

    # J-7 à 04:00 local (02:00 UTC) : première seconde de la fenêtre.
    manager.consume(product_id=product_id, quantity=100.0,
                    occurred_at="2026-08-13T02:00:00")
    assert manager.summary(expiration_alert_days=3, tz=PARIS,
                           now=NOON)["week_mean"]["kcal"] == pytest.approx(
                               round(120.0 / 7, 1))


def test_the_week_mean_carries_the_same_keys_as_today(manager):
    """Moins `food_day` et `start` : un capteur doit pouvoir lire l'une ou
    l'autre fenêtre sans se demander laquelle."""
    summary = manager.summary(expiration_alert_days=3, tz=PARIS, now=NOON)
    assert set(summary["week_mean"]) == set(summary["today"]) - {"food_day", "start"}
