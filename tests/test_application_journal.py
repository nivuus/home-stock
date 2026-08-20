"""The food day as seen from the application layer."""
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest

from test_application import _seed_article, manager  # noqa: F401

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
    manager.add_stock(article_id=article_id, quantity=2000.0, location_id=1)
    manager.consume(product_id=product_id, quantity=400.0, parts_total=4, parts_mine=1,
                    occurred_at="2026-08-20T10:00:00")

    series = manager.journal_series("day", 1, tz=PARIS, now=NOON)
    assert series["buckets"][0]["kcal"] == pytest.approx(120.0)


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
