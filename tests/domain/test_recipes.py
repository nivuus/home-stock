"""La mise à l'échelle et la conversion « 2 cs d'huile » → « 30 ml ».

Ce sont exactement les deux calculs que Grocy a ratés, et ils se testent sans
démarrer quoi que ce soit : le module est pur, sans `hass`, sans SQLite et
sans réseau.
"""
from datetime import datetime

import pytest

from custom_components.home_stock.domain.recipes import (
    STATUSES,
    IngredientLine,
    Measure,
    base_amount,
    display_amount,
    per_part_values,
    plan_decrement,
    scale_factor,
)
from custom_components.home_stock.domain.stock import BatchView

CS = Measure(id=1, name="cuillère à soupe", base_unit="ml", base_quantity=15.0)
PINCEE = Measure(id=4, name="pincée", base_unit="g", base_quantity=1.0)


def _line(**kwargs):
    base = dict(id=1, position=1, product_id=1, product_base_unit="g", amount=None,
                packaging_base_quantity=None, packaging_name=None, measure=None,
                raw_text="", match_state="auto", optional=False)
    return IngredientLine(**{**base, **kwargs})


def _batch(batch_id, remaining):
    return BatchView(id=batch_id, remaining=float(remaining), best_before=None,
                     entered_at=datetime(2026, 8, 1, 12, 0), opened_at=None,
                     price_per_base_unit=None, kcal_per_base_unit=None)


# --- l'échelle -------------------------------------------------------------

def test_the_factor_is_the_ratio_of_servings():
    assert scale_factor(3, 2) == 1.5
    assert scale_factor(1, 1) == 1.0


def test_a_line_without_a_quantity_is_untouched_by_the_factor():
    assert base_amount(_line(amount=None), factor=1.5) is None


def test_a_non_integer_factor_scales_the_base_quantity_not_the_spoon():
    """15 ml × 1,5 = 22,5 ml se décrémente ; « 1,5 cs » ne se décrémente pas."""
    line = _line(product_base_unit="ml", amount=1, measure=CS)
    assert base_amount(line, factor=1.5) == 22.5


def test_a_recipe_for_nobody_is_refused_rather_than_scaled_to_zero():
    for meal, recipe in ((0, 2), (-1, 2), (2, 0)):
        with pytest.raises(ValueError):
            scale_factor(meal, recipe)


# --- le tableau du § 9, refus compris --------------------------------------

def test_a_number_without_any_measure_is_already_in_the_base_unit():
    assert base_amount(_line(amount=150)) == 150.0


def test_a_product_packaging_wins_over_everything():
    line = _line(amount=2, packaging_base_quantity=30.0, packaging_name="tranche")
    assert base_amount(line) == 60.0


def test_a_product_packaging_wins_even_over_a_culinary_measure():
    """Le conditionnement propre au produit l'emporte dès qu'il existe : il est
    mesuré, la cuillère normalisée ne l'est pas."""
    line = _line(product_base_unit="ml", amount=2, measure=CS,
                 packaging_base_quantity=33.0, packaging_name="canette")
    assert base_amount(line) == 66.0


def test_a_culinary_measure_applies_when_the_dimension_matches():
    assert base_amount(_line(product_base_unit="ml", amount=2, measure=CS)) == 30.0
    assert base_amount(_line(product_base_unit="g", amount=1, measure=PINCEE)) == 1.0


def test_a_spoon_of_a_piece_product_is_refused():
    """Un yaourt ne se dose pas à la cuillère."""
    assert base_amount(_line(product_base_unit="piece", amount=2, measure=CS)) is None


def test_a_volume_measure_for_a_gram_product_is_refused():
    assert base_amount(_line(product_base_unit="g", amount=2, measure=CS)) is None


def test_a_line_with_no_product_has_no_base_quantity():
    assert base_amount(_line(product_id=None, product_base_unit=None, amount=2)) is None


def test_half_stays_half_and_never_becomes_zero():
    assert base_amount(_line(product_base_unit="piece", amount=0.5)) == 0.5


# --- le libellé, calculé, jamais stocké ------------------------------------

@pytest.mark.parametrize("line, expected", [
    (_line(product_base_unit="ml", amount=2, measure=CS), "2 cuillères à soupe"),
    (_line(product_base_unit="ml", amount=1, measure=CS), "1 cuillère à soupe"),
    (_line(amount=150), "150 g"),
    (_line(amount=2, packaging_base_quantity=30.0, packaging_name="tranche"), "2 tranches"),
    (_line(amount=1, packaging_base_quantity=30.0, packaging_name="tranche"), "1 tranche"),
    (_line(amount=None, raw_text="un filet d'huile"), "un filet d'huile"),
])
def test_the_label_is_computed_from_the_single_written_number(line, expected):
    assert display_amount(line) == expected


def test_the_label_never_reads_raw_text_when_a_number_exists():
    """`raw_text` est de la PROVENANCE, jamais un calcul. Tant qu'il y a un
    nombre écrit, c'est lui qui s'affiche — sinon une fiche importée dirait
    « 2 tbsp » à côté d'un décrément de 30 ml."""
    line = _line(product_base_unit="ml", amount=2, measure=CS, raw_text="2 tbsp")
    assert display_amount(line) == "2 cuillères à soupe"


# --- le plan de décrément ---------------------------------------------------

def test_a_plan_spanning_two_batches_lists_both():
    needs = plan_decrement([_line(amount=700)], {1: [_batch(1, 500), _batch(2, 400)]},
                           factor=1.0)
    assert needs[0].status == "ok"
    assert [a.quantity for a in needs[0].allocations] == [500.0, 200.0]


def test_a_short_stock_is_reported_reduced_never_raised():
    needs = plan_decrement([_line(amount=500)], {1: [_batch(1, 200)]}, factor=1.0)
    assert needs[0].status == "short"
    assert needs[0].available == 200.0
    assert sum(a.quantity for a in needs[0].allocations) == 200.0


def test_no_batch_at_all_falls_back_to_by_hand():
    needs = plan_decrement([_line(amount=500)], {}, factor=1.0)
    assert needs[0].status == "short" and needs[0].allocations == ()
    assert needs[0].available == 0.0


@pytest.mark.parametrize("line, status", [
    (_line(product_id=None, match_state="unmatched", amount=2), "unmatched"),
    (_line(match_state="ignored", amount=2), "ignored"),
    (_line(amount=None), "unquantified"),
    (_line(product_base_unit="piece", amount=2, measure=CS), "unquantified"),
])
def test_the_statuses_the_validation_screen_shows(line, status):
    assert plan_decrement([line], {1: [_batch(1, 500)]}, factor=1.0)[0].status == status


def test_every_status_it_can_return_is_declared():
    """`STATUSES` est lu par le websocket et par l'écran de validation : un
    statut rendu mais non déclaré s'afficherait comme une case vide."""
    lines = [_line(id=1, amount=500), _line(id=2, product_id=None,
                                            match_state="unmatched", amount=2),
             _line(id=3, match_state="ignored", amount=2), _line(id=4, amount=None),
             _line(id=5, amount=900)]
    needs = plan_decrement(lines, {1: [_batch(1, 600)]}, factor=1.0)
    assert {need.status for need in needs} <= set(STATUSES)


def test_a_skipped_line_is_not_planned():
    needs = plan_decrement([_line(id=7, amount=500)], {1: [_batch(1, 500)]},
                           factor=1.0, skipped_ids={7})
    assert needs[0].status == "ignored" and needs[0].allocations == ()


def test_two_lines_on_the_same_product_share_the_same_stock():
    """Deux lignes d'oignon dans une recette ne prennent pas deux fois le même
    lot en entier : le plan alloue en séquence, pas en parallèle."""
    lines = [_line(id=1, amount=300), _line(id=2, amount=300)]
    needs = plan_decrement(lines, {1: [_batch(1, 500)]}, factor=1.0)
    assert needs[0].status == "ok" and needs[1].status == "short"
    assert needs[1].available == 200.0


def test_the_factor_reaches_the_plan():
    needs = plan_decrement([_line(amount=300)], {1: [_batch(1, 500)]}, factor=1.5)
    assert needs[0].needed == 450.0


def test_an_optional_line_is_planned_like_any_other():
    """« Facultatif » décrit la recette, pas le décrément : si l'ingrédient est
    en stock et que personne ne l'a décoché, il part comme les autres."""
    needs = plan_decrement([_line(amount=100, optional=True)],
                           {1: [_batch(1, 500)]}, factor=1.0)
    assert needs[0].status == "ok"


def test_the_plan_keeps_the_order_of_the_lines():
    lines = [_line(id=3, position=3, amount=10), _line(id=1, position=1, amount=10)]
    assert [need.line.id for need in plan_decrement(lines, {}, factor=1.0)] == [3, 1]


# --- les valeurs par part ---------------------------------------------------

def test_per_part_divides_the_frozen_sums():
    frozen = [{"kcal": 600.0, "proteins": 30.0}, {"kcal": 300.0, "proteins": 6.0}]
    result = per_part_values(frozen, 3)
    assert result["kcal"] == 300.0
    assert result["proteins"] == 12.0


def test_per_part_always_reports_the_same_nine_keys():
    """La forme du résultat ne dépend pas de ce que les mouvements portaient :
    l'appelant écrit neuf colonnes, il doit en recevoir neuf. Un nutriment que
    personne n'a mesuré vaut `None`, pas « absent »."""
    from custom_components.home_stock.domain.recipes import PER_PART_KEYS
    assert set(per_part_values([{"kcal": 1.0}], 1)) == set(PER_PART_KEYS)
    assert set(per_part_values([], 1)) == set(PER_PART_KEYS)


def test_one_missing_nutrient_nulls_that_nutrient_and_not_the_other_eight():
    frozen = [{"kcal": 600.0, "proteins": None}, {"kcal": 300.0, "proteins": 6.0}]
    result = per_part_values(frozen, 3)
    assert result["proteins"] is None
    assert result["kcal"] == 300.0


def test_an_empty_plan_gives_null_everywhere_never_zero():
    assert per_part_values([], 3)["kcal"] is None


def test_zero_parts_is_refused_rather_than_dividing():
    with pytest.raises(ValueError):
        per_part_values([{"kcal": 1.0}], 0)


def test_a_measured_zero_is_kept_as_zero():
    """`0.0` est une mesure, `None` est une absence — la distinction tient
    jusque dans la division."""
    assert per_part_values([{"kcal": 0.0}, {"kcal": 0.0}], 2)["kcal"] == 0.0


def test_no_rounding_is_applied():
    """Arrondir ici ferait diverger le total du plat et la somme de ses parts."""
    assert per_part_values([{"kcal": 100.0}], 3)["kcal"] == pytest.approx(100 / 3)
