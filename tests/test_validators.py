import pytest
import voluptuous as vol

from custom_components.home_stock.validators import parts_count


def test_parts_count_accepts_a_plain_integer():
    assert parts_count(4) == 4
    assert parts_count(0) == 0


def test_parts_count_refuses_a_float_a_bool_and_text():
    for value in (1.5, True, "2", None, [2]):
        with pytest.raises(vol.Invalid):
            parts_count(value)


def test_parts_count_refuses_out_of_range():
    with pytest.raises(vol.Invalid):
        parts_count(-1)
    with pytest.raises(vol.Invalid):
        parts_count(25)
    assert parts_count(24) == 24
