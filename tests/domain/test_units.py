import pytest

from custom_components.home_stock.domain.units import (
    UnitError,
    format_quantity,
    to_base_quantity,
    validate_base_unit,
)


def test_validate_base_unit_accepts_the_three_units():
    assert validate_base_unit("g") == "g"
    assert validate_base_unit("ml") == "ml"
    assert validate_base_unit("piece") == "piece"


def test_validate_base_unit_rejects_everything_else():
    # "Paquet" as a stock unit is exactly what this model refuses.
    with pytest.raises(UnitError):
        validate_base_unit("Paquet")
    with pytest.raises(UnitError):
        validate_base_unit("kg")


def test_to_base_quantity_without_packaging_is_the_identity():
    assert to_base_quantity(200) == 200


def test_to_base_quantity_multiplies_by_the_packaging():
    # Two 500 g packs are 1000 g.
    assert to_base_quantity(2, 500) == 1000


def test_to_base_quantity_rejects_a_non_positive_packaging():
    with pytest.raises(UnitError):
        to_base_quantity(2, 0)


def test_to_base_quantity_rejects_a_negative_amount():
    with pytest.raises(UnitError):
        to_base_quantity(-1)


def test_format_quantity_uses_french_notation():
    assert format_quantity(1500, "g") == "1,5 kg"
    assert format_quantity(200, "g") == "200 g"
    assert format_quantity(1200, "ml") == "1,2 l"
    assert format_quantity(250, "ml") == "250 ml"
    assert format_quantity(1, "piece") == "1 pièce"
    assert format_quantity(3, "piece") == "3 pièces"
