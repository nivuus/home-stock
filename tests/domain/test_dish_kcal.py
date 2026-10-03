"""What a validated dish is worth in kcal: what is known is eaten and counted.

The rule decided on 2026-10-03: what is eaten counts in the day's kcal. A dish
whose ingredients are only PARTLY valued must still carry the kcal that are
known — one unvalued tomato must not erase the 336 kcal of the crispbread next
to it. Only a dish with no valued ingredient at all stays unknown (None).
"""
import pytest

from custom_components.home_stock.domain.recipes import per_part_values


def test_an_unvalued_ingredient_no_longer_erases_the_known_kcal() -> None:
    # 03/10 breakfast: crispbread 80 g x 4.2, egg 78, cream cheese 50 g x 0.9,
    # and a tomato that carried no value when the meal was validated.
    frozen: list[dict[str, float | None]] = [
        {"kcal": 336.0}, {"kcal": 78.0}, {"kcal": 45.0}, {"kcal": None}]
    assert per_part_values(frozen, 1)["kcal"] == pytest.approx(459.0)


def test_the_known_kcal_are_shared_between_the_parts() -> None:
    frozen: list[dict[str, float | None]] = [
        {"kcal": 600.0}, {"kcal": None}, {"kcal": 300.0}]
    assert per_part_values(frozen, 3)["kcal"] == pytest.approx(300.0)


def test_a_dish_with_no_valued_ingredient_stays_unknown() -> None:
    """None, never 0.0: the day's counter adds nothing either way, but only
    None keeps the meal visible in `unvalued_movements`."""
    assert per_part_values([{"kcal": None}, {"kcal": None}], 2)["kcal"] is None


def test_a_measured_zero_next_to_an_unknown_is_still_a_measured_zero() -> None:
    assert per_part_values([{"kcal": 0.0}, {"kcal": None}], 1)["kcal"] == 0.0


def test_the_macros_keep_their_own_rule() -> None:
    """Only the kcal changed rule: one missing protein value still makes the
    dish's protein unknown, as before (the macro counters are not this fix)."""
    frozen: list[dict[str, float | None]] = [
        {"kcal": 100.0, "proteins": 5.0}, {"kcal": None, "proteins": None}]
    result = per_part_values(frozen, 1)
    assert result["kcal"] == pytest.approx(100.0)
    assert result["proteins"] is None
