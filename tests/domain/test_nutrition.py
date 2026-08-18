import pytest

from custom_components.home_stock.domain.nutrition import (
    MovementValues,
    counts_in_daily_totals,
    movement_values,
)


def test_values_are_the_quantity_times_the_rates():
    # 200 g at 3.5 kcal/g and 0.004 €/g.
    values = movement_values(200, 3.5, 0.004)
    assert values.kcal == pytest.approx(700.0)
    assert values.cost == pytest.approx(0.8)


def test_a_negative_quantity_yields_positive_values():
    # A movement of -200 g still costs 0.8 €; the sign lives on the quantity.
    values = movement_values(-200, 3.5, 0.004)
    assert values.kcal == pytest.approx(700.0)
    assert values.cost == pytest.approx(0.8)


def test_unknown_rates_give_none_not_zero():
    # None means "unknown". Zero would mean "measured at zero" and would silently
    # understate the daily total.
    assert movement_values(200, None, None) == MovementValues(kcal=None, cost=None)
    assert movement_values(200, 3.5, None).cost is None
    assert movement_values(200, None, 0.004).kcal is None


def test_a_zero_rate_is_kept_as_zero():
    values = movement_values(200, 0.0, 0.0)
    assert values.kcal == 0.0
    assert values.cost == 0.0


def test_values_are_not_rounded():
    # Rounding happens at display time only; summing rounded values drifts.
    values = movement_values(3, 1 / 3, None)
    assert values.kcal == pytest.approx(1.0, abs=1e-12)


def test_which_reasons_count_in_the_daily_totals():
    assert counts_in_daily_totals("consumption") is True
    assert counts_in_daily_totals("waste") is True
    assert counts_in_daily_totals("expired") is True
    assert counts_in_daily_totals("purchase") is False
    assert counts_in_daily_totals("inventory") is False
    assert counts_in_daily_totals("transfer") is False
