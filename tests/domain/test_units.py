import pytest

from custom_components.home_stock.domain.units import (
    UNIT_TO_BASE,
    UnitError,
    convertible_amount,
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


# --- lot 3 : la table d'unités vit dans le domaine --------------------------

def test_a_mass_converts_to_grams():
    assert convertible_amount(1.5, "kg", "g") == 1500.0
    assert convertible_amount(250, "g", "g") == 250.0
    assert convertible_amount(500, "mg", "g") == 0.5


def test_a_volume_converts_to_millilitres():
    assert convertible_amount(2, "cl", "ml") == 20.0
    assert convertible_amount(1, "l", "ml") == 1000.0


def test_a_mass_given_for_a_volume_product_is_refused():
    """Jamais de densité devinée : 100 g de miel ne font pas 100 ml."""
    assert convertible_amount(100, "g", "ml") is None
    assert convertible_amount(100, "ml", "g") is None


def test_anything_given_for_a_piece_product_is_refused():
    """Le lot 1 refuse déjà d'inventer un diviseur (§ 7.4) ; même raison."""
    assert convertible_amount(100, "g", "piece") is None


def test_an_unknown_unit_is_refused_not_guessed():
    for unit in ("unité", "pcs", "portions", "handful", "", None, "G "):
        assert convertible_amount(1, unit, "g") is None


def test_a_named_unit_is_required_even_when_it_would_be_obvious():
    """Une ligne sans mesure n'est pas convertie ici.

    C'est l'APPELANT (`domain/recipes`) qui décide qu'une quantité sans
    mesure est déjà exprimée en unité de base. Cette fonction ne convertit
    que ce qu'on lui nomme : deviner ici rendrait impossible de savoir, plus
    tard, où la devinette a eu lieu.
    """
    assert convertible_amount(150, None, "g") is None


def test_the_table_did_not_move_a_single_value():
    assert UNIT_TO_BASE["cl"] == ("ml", 10.0)
    assert UNIT_TO_BASE["mg"] == ("g", 0.001)
    assert UNIT_TO_BASE["kg"] == ("g", 1000.0)
    assert UNIT_TO_BASE["l"] == ("ml", 1000.0)
    assert len(UNIT_TO_BASE) == 10


def test_the_domain_does_not_normalise_the_text_a_second_time():
    """Aucun `strip()`, aucun `lower()` ici.

    Normaliser le texte d'une source est le travail de `recipes/mapping` et
    de `off/mapping`, qui savent d'où vient la chaîne. Une fonction qui
    devine deux fois ne dit plus où la devinette a eu lieu.
    """
    assert convertible_amount(1, "KG", "g") is None
    assert convertible_amount(1, " kg", "g") is None
