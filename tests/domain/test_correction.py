"""Une écriture de contrepassation porte le COMPTE de l'écriture qu'elle
annule, avec le signe inverse. Règle comptable plus ancienne que ce
composant, et reprise telle quelle (amendement A1) : `reason` reste
identique, `corrects_id` porte le lien, et aucune des quatre requêtes
d'agrégat n'a besoin d'apprendre quoi que ce soit."""
from custom_components.home_stock.const import MACRO_COLUMNS
from custom_components.home_stock.domain.correction import (
    CorrectionError, check_correctable, correction_key, reprice, reversal,
)

import pytest

MOVEMENT = {
    "id": 42, "occurred_at": "2026-08-14T18:00:00", "product_id": 7,
    "article_id": 11, "batch_id": 3, "quantity": -200.0, "reason": "consumption",
    "base_unit": "g", "kcal": 310.0, "cost": 0.42,
    "parts_total": 4, "parts_mine": 1, "corrects_id": None,
    "proteins": 11.0, "carbohydrates": 62.0, "sugars": 2.0, "added_sugars": None,
    "fat": 1.5, "saturated_fat": 0.3, "fiber": 3.0, "salt": 0.01,
}


def test_the_reversal_carries_the_same_reason():
    """Le coeur de l'amendement A1. Un motif `correction` serait invisible de
    totals_between, _PERSONAL_SUMS, journal_entries et counted_movements."""
    assert reversal(MOVEMENT, moment="2026-08-21T09:00:00")["reason"] == "consumption"


def test_the_reversal_copies_the_identifiers():
    line = reversal(MOVEMENT, moment="2026-08-21T09:00:00")
    assert (line["product_id"], line["article_id"], line["batch_id"],
            line["base_unit"]) == (7, 11, 3, "g")
    assert line["corrects_id"] == 42
    assert line["occurred_at"] == "2026-08-21T09:00:00"
    assert line["idempotency_key"] == "correction:42"


def test_the_reversal_flips_quantity_cost_and_the_nine_nutrients():
    line = reversal(MOVEMENT, moment="2026-08-21T09:00:00")
    assert line["quantity"] == 200.0
    assert line["cost"] == -0.42
    assert line["kcal"] == -310.0
    assert line["macros"]["proteins"] == -11.0
    assert line["macros"]["fat"] == -1.5
    assert line["macros"]["salt"] == -0.01
    assert set(line["macros"]) == set(MACRO_COLUMNS)


def test_a_null_nutrient_is_reversed_by_a_null_never_by_a_zero():
    """Zéro veut dire « mesuré à zéro » (règle du lot 2). Compenser un NULL
    par 0.0 inventerait une mesure, et le prouverait faux dans les neuf sommes
    pondérées de _PERSONAL_SUMS."""
    line = reversal(MOVEMENT, moment="2026-08-21T09:00:00")
    assert line["macros"]["added_sugars"] is None
    muet = {**MOVEMENT, "kcal": None, "cost": None}
    autre = reversal(muet, moment="2026-08-21T09:00:00")
    assert autre["kcal"] is None and autre["cost"] is None


def test_the_parts_are_copied_never_inverted():
    """Le facteur personnel est un RATIO positif : c'est le signe des valeurs
    qu'il multiplie qui porte l'annulation. Inverser les parts diviserait des
    calories négatives par un nombre négatif."""
    line = reversal(MOVEMENT, moment="2026-08-21T09:00:00")
    assert (line["parts_total"], line["parts_mine"]) == (4, 1)


def test_reversing_a_positive_movement_gives_a_negative_one():
    achat = {**MOVEMENT, "reason": "purchase", "quantity": 1000.0, "cost": 2.10,
             "parts_total": None, "parts_mine": None}
    line = reversal(achat, moment="2026-08-21T09:00:00")
    assert line["quantity"] == -1000.0 and line["cost"] == -2.10
    assert line["reason"] == "purchase"
    assert line["parts_total"] is None and line["parts_mine"] is None


def test_a_movement_already_corrected_is_refused():
    with pytest.raises(CorrectionError):
        check_correctable({**MOVEMENT, "corrects_id": 41})


def test_transfer_conversion_and_cooked_are_refused():
    """`transfer` : quantité nulle, rien à compenser. `conversion` et `cooked`
    viennent par PAIRES transactionnelles — les compenser un par un laisserait
    le stock incohérent."""
    for reason in ("transfer", "conversion", "cooked"):
        with pytest.raises(CorrectionError):
            check_correctable({**MOVEMENT, "reason": reason})


def test_correct_meal_may_reverse_a_cooked_and_only_it():
    """`application.correct_meal()` est le SEUL appelant autorisé : il
    contrepasse le bloc entier, dans l'ordre inverse, en une transaction."""
    check_correctable({**MOVEMENT, "reason": "cooked"}, allow_cooked=True)
    with pytest.raises(CorrectionError):
        check_correctable({**MOVEMENT, "reason": "conversion"}, allow_cooked=True)


def test_every_correctable_reason_is_a_real_reason():
    from custom_components.home_stock.const import REASONS
    from custom_components.home_stock.domain.correction import CORRECTABLE_REASONS
    assert set(CORRECTABLE_REASONS) < set(REASONS)
    assert "correction" not in REASONS        # amendement A1, épinglé ici


def test_reprice_keeps_the_nutrients_and_moves_only_the_cost():
    """Un prix faux n'a jamais faussé des calories. Le solde nutritionnel de
    la paire contrepassation + réécriture doit être NUL."""
    ligne = reprice(MOVEMENT, price_per_base_unit=0.003, moment="2026-08-21T09:00:00")
    assert ligne["kcal"] == 310.0
    assert ligne["macros"]["proteins"] == 11.0
    assert ligne["quantity"] == -200.0
    assert ligne["cost"] == pytest.approx(0.6)          # 200 g × 0,003 €/g
    assert ligne["reason"] == "consumption"
    assert ligne["corrects_id"] is None                 # ce n'est pas une annulation


def test_the_nutritional_balance_of_a_reprice_pair_is_zero():
    annule = reversal(MOVEMENT, moment="2026-08-21T09:00:00")
    refait = reprice(MOVEMENT, price_per_base_unit=0.003, moment="2026-08-21T09:00:00")
    for column in MACRO_COLUMNS:
        gauche, droite = annule["macros"][column], refait["macros"][column]
        if gauche is None:
            assert droite is None
        else:
            assert gauche + droite == pytest.approx(0.0)
    assert annule["kcal"] + refait["kcal"] == pytest.approx(0.0)
    assert annule["quantity"] + refait["quantity"] == pytest.approx(0.0)


def test_a_reprice_without_a_price_writes_a_null_cost():
    ligne = reprice(MOVEMENT, price_per_base_unit=None, moment="2026-08-21T09:00:00")
    assert ligne["cost"] is None


def test_correction_key_is_derived_and_stable():
    assert correction_key(42) == "correction:42"
