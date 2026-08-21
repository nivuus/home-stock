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


# --- lot 4 : d'où vient un prix (amendement A3) ----------------------------

def test_price_source_accepts_the_six_declared_sources():
    from custom_components.home_stock.const import PRICE_SOURCES
    from custom_components.home_stock.validators import price_source
    for source in PRICE_SOURCES:
        assert price_source(source) == source


def test_price_source_lets_nothing_through_unknown():
    """`source` décide du rang 1 de la cascade : une faute de frappe y ferait
    disparaître un prix réellement observé, sans que rien ne le signale."""
    from custom_components.home_stock.validators import price_source
    with pytest.raises(vol.Invalid):
        price_source("open_price")
    assert price_source(None) is None
    assert price_source("") is None


def test_a_store_name_is_bounded_and_stripped():
    """`validators.store_name` : vide → refus, 300 caractères → refus,
    espaces de bord retirés."""
    from custom_components.home_stock.validators import store_name
    assert store_name("  Leclerc  ") == "Leclerc"
    with pytest.raises(vol.Invalid):
        store_name("")
    with pytest.raises(vol.Invalid):
        store_name("   ")
    with pytest.raises(vol.Invalid):
        store_name("x" * 300)
    with pytest.raises(vol.Invalid):
        store_name(None)
