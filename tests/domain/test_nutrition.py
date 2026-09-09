import pytest

from custom_components.home_stock.const import MACRO_COLUMNS
from custom_components.home_stock.domain.nutrition import movement_values


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
    assert movement_values(200, None, None).kcal is None
    assert movement_values(200, None, None).cost is None
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


def test_macros_scale_with_the_quantity():
    values = movement_values(
        200.0, 1.2, 0.004,
        macro_rates={"proteins": 0.05, "salt": 0.001},
    )
    assert values.kcal == pytest.approx(240.0)
    assert values.cost == pytest.approx(0.8)
    assert values.macros["proteins"] == pytest.approx(10.0)
    assert values.macros["salt"] == pytest.approx(0.2)


def test_an_unknown_macro_stays_none_and_never_becomes_zero():
    values = movement_values(200.0, None, None, macro_rates={"proteins": None})
    assert values.kcal is None
    assert values.cost is None
    assert values.macros["proteins"] is None


def test_a_macro_measured_at_zero_stays_zero():
    """A food with no salt genuinely has 0 g of salt: that is not a
    missing value, and overwriting it with `None` would lose a real
    measurement."""
    values = movement_values(200.0, None, None, macro_rates={"salt": 0.0})
    assert values.macros["salt"] == 0.0


def test_macros_are_keyed_by_every_column_even_when_the_rates_are_partial():
    """The returned dict ALWAYS covers the eight columns: the caller writes
    it straight into `movement`, and a missing key there would become a
    silent column instead of an explicit NULL."""
    values = movement_values(100.0, None, None, macro_rates={"proteins": 0.1})
    assert set(values.macros) == set(MACRO_COLUMNS)
    assert values.macros["fiber"] is None


def test_no_macro_rates_at_all_still_yields_eight_nulls():
    values = movement_values(100.0, None, None)
    assert set(values.macros) == set(MACRO_COLUMNS)
    assert all(value is None for value in values.macros.values())


def test_macros_use_the_magnitude_like_kcal_does():
    """An outflow carries a negative quantity; its nutrients are positive."""
    values = movement_values(-200.0, 1.2, None, macro_rates={"proteins": 0.05})
    assert values.macros["proteins"] == pytest.approx(10.0)


def test_macros_are_never_rounded():
    values = movement_values(3.0, None, None, macro_rates={"proteins": 0.1})
    assert values.macros["proteins"] == 3.0 * 0.1     # 0.30000000000000004
