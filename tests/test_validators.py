import pytest
import voluptuous as vol

from custom_components.home_stock.const import GOAL_NUTRIENTS, MACRO_COLUMNS, MAX_GOAL
from custom_components.home_stock.validators import (
    check_manual_portion,
    goal_quantity,
    parts_count,
)


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


# --- lot 5 : les invariants de pile, écrits une fois pour les deux surfaces ---

from custom_components.home_stock.validators import (
    cell_count, check_battery_event, check_battery_fields, percent_threshold,
    tracked_flag,
)


def test_percent_threshold_accepts_the_range_and_refuses_the_rest():
    assert percent_threshold(20) == 20.0
    assert percent_threshold("25,5") == 25.5
    assert percent_threshold(0) == 0.0
    assert percent_threshold(100) == 100.0
    for mauvais in (-0.1, 100.1, float("nan"), float("inf"), "beaucoup", None, True):
        with pytest.raises(vol.Invalid):
            percent_threshold(mauvais)


def test_cell_count_refuses_zero_a_float_and_a_bool():
    assert cell_count(2) == 2
    for mauvais in (0, -1, 2.0, True, "2", None, 25):
        with pytest.raises(vol.Invalid):
            cell_count(mauvais)


def test_tracked_flag_is_strict():
    assert tracked_flag(True) is True
    assert tracked_flag(False) is False
    assert tracked_flag(None) is None
    for mauvais in (0, 1, "oui", "true", ""):
        with pytest.raises(vol.Invalid):
            tracked_flag(mauvais)


def test_keep_must_not_be_below_low():
    """Un seuil de maintien plus bas que le seuil d'apparition fait clignoter
    la tâche à CHAQUE synchronisation : elle apparaît sous 20, se ferme au-
    dessus de 15, réapparaît. Impossible à poser, aux deux surfaces."""
    with pytest.raises(vol.Invalid):
        check_battery_fields({"low_percent": 20.0, "keep_percent": 15.0}, kind="primary")
    check_battery_fields({"low_percent": 20.0, "keep_percent": 20.0}, kind="primary")


def test_untracked_requires_a_reason():
    with pytest.raises(vol.Invalid):
        check_battery_fields({"tracked": False}, kind="primary")
    with pytest.raises(vol.Invalid):
        check_battery_fields({"tracked": False, "exclusion_reason": "   "}, kind="primary")
    check_battery_fields({"tracked": False, "exclusion_reason": "tablette sur secteur"},
                         kind="primary")


def test_a_built_in_battery_has_no_spare():
    """Une batterie soudée ne se remplace pas : lui donner un produit de
    rechange, c'est promettre une ligne de courses qui ne servira jamais."""
    with pytest.raises(vol.Invalid):
        check_battery_fields({"product_id": 4}, kind="built_in")
    check_battery_fields({"product_id": 4}, kind="primary")


def test_check_battery_fields_refuses_a_bad_cell_count_a_bad_percent_a_bad_date():
    """Les trois contraintes que le § 12.2 impose aux DEUX surfaces et que
    seule cette fonction fait respecter à la troisième porte, l'import."""
    with pytest.raises(vol.Invalid):
        check_battery_fields({"cell_count": 0}, kind="primary")
    with pytest.raises(vol.Invalid):
        check_battery_fields({"low_percent": 120.0}, kind="primary")
    with pytest.raises(vol.Invalid):
        check_battery_fields({"installed_on": "02/05/2024"}, kind="primary")
    check_battery_fields({"cell_count": 2, "low_percent": 20.0,
                          "installed_on": "2024-05-02"}, kind="primary")


def test_a_primary_cannot_be_charged_and_a_built_in_cannot_be_replaced():
    with pytest.raises(vol.Invalid):
        check_battery_event("charge", battery_kind="primary",
                            consume_spare=False, product_id=None)
    with pytest.raises(vol.Invalid):
        check_battery_event("replacement", battery_kind="built_in",
                            consume_spare=False, product_id=None)
    check_battery_event("charge", battery_kind="rechargeable_cell",
                        consume_spare=False, product_id=None)
    check_battery_event("replacement", battery_kind="primary",
                        consume_spare=True, product_id=3)


def test_consuming_a_spare_that_does_not_exist_is_refused_before_writing():
    with pytest.raises(vol.Invalid):
        check_battery_event("replacement", battery_kind="primary",
                            consume_spare=True, product_id=None)


def test_every_new_refusal_has_a_french_sentence():
    """Le texte anglais de chaque refus est écrit DEUX fois : dans
    `validators.py` (l'exception) et dans `messages.py` (le motif qui la
    traduit). C'est exactement le genre de duplication qui dérive — une
    reformulation d'un côté et le refus repart en « Valeur invalide. »
    générique, aux deux surfaces, sans que rien n'échoue. Ce test apparie les
    deux fichiers sur les refus du lot 5.
    """
    from custom_components.home_stock.messages import GENERIC_MESSAGE, french_message

    refus = [
        lambda: check_battery_fields({"low_percent": 20.0, "keep_percent": 15.0},
                                     kind="primary"),
        lambda: check_battery_fields({"tracked": False}, kind="primary"),
        lambda: check_battery_fields({"product_id": 4}, kind="built_in"),
        lambda: check_battery_event("charge", battery_kind="primary",
                                    consume_spare=False, product_id=None),
        lambda: check_battery_event("replacement", battery_kind="built_in",
                                    consume_spare=False, product_id=None),
        lambda: check_battery_event("replacement", battery_kind="primary",
                                    consume_spare=True, product_id=None),
    ]
    for appel in refus:
        with pytest.raises(vol.Invalid) as leve:
            appel()
        phrase = french_message(leve.value)
        assert phrase != GENERIC_MESSAGE, str(leve.value)


# --- Lot 2bis : portion manuelle et objectifs nutritionnels ------------------

def test_a_manual_portion_is_a_number_in_the_lot_two_bounds():
    assert check_manual_portion(45, base_unit="g", max_net_quantity=500) == 45.0
    assert check_manual_portion("45,5", base_unit="ml", max_net_quantity=1000) == 45.5
    assert check_manual_portion(5000, base_unit="g", max_net_quantity=None) == 5000.0


def test_clearing_a_manual_portion_is_allowed():
    """`null` est l'effacement, pas une erreur : le produit repasse à la
    médiane apprise au rechargement suivant."""
    assert check_manual_portion(None, base_unit="g", max_net_quantity=500) is None


def test_a_manual_portion_is_refused_on_a_piece_product():
    with pytest.raises(vol.Invalid, match="pièce"):
        check_manual_portion(45, base_unit="piece", max_net_quantity=None)


def test_a_manual_portion_out_of_bounds_says_the_bound():
    for value in (0, -5, 5000.1):
        with pytest.raises(vol.Invalid, match="5000"):
            check_manual_portion(value, base_unit="g", max_net_quantity=None)


def test_a_manual_portion_bigger_than_the_biggest_pack_is_refused():
    with pytest.raises(vol.Invalid, match="1000"):
        check_manual_portion(1200, base_unit="g", max_net_quantity=1000)
    # Exactement le paquet reste plausible : une conserve individuelle.
    assert check_manual_portion(1000, base_unit="g", max_net_quantity=1000) == 1000.0


def test_a_manual_portion_is_accepted_when_no_pack_weight_is_known():
    assert check_manual_portion(80, base_unit="g", max_net_quantity=None) == 80.0


def test_a_manual_portion_refuses_what_is_not_a_number():
    for value in ("", "trente", True, [45]):
        with pytest.raises(vol.Invalid):
            check_manual_portion(value, base_unit="g", max_net_quantity=None)


def test_a_goal_is_a_positive_finite_number_under_the_cap():
    assert goal_quantity(6) == 6.0
    assert goal_quantity("6,5") == 6.5
    assert goal_quantity(MAX_GOAL) == float(MAX_GOAL)
    for value in (0, -1, MAX_GOAL + 1, True, float("inf"), "beaucoup"):
        with pytest.raises(vol.Invalid):
            goal_quantity(value)


def test_the_nine_goal_nutrients_are_the_nine_journal_columns():
    """Un objectif sur un nutriment que le journal ne fige pas ne pourrait
    jamais être comparé à quoi que ce soit."""
    assert GOAL_NUTRIENTS == ("kcal", *MACRO_COLUMNS)
    assert len(GOAL_NUTRIENTS) == 9
