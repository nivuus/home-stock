"""Attaching a scanned article to a catalogue product."""
import pytest

from custom_components.home_stock.domain.matching import (
    PRESELECT_MARGIN,
    PRESELECT_SCORE,
    Candidate,
    candidates,
    normalise,
    preselect,
    strip_brand,
)

CATALOGUE = [
    {"id": 1, "name": "Pâtes"},
    {"id": 2, "name": "Muesli"},
    {"id": 3, "name": "Œufs"},
    {"id": 4, "name": "Lait demi-écrémé"},
    {"id": 5, "name": "Yaourt nature"},
    {"id": 6, "name": "Huile d'olive"},
]


def test_accents_and_ligatures_fold():
    assert normalise("Œufs") == normalise("oeufs")
    assert normalise("Pâtes") == normalise("pates")
    assert normalise("Lait demi-écrémé") == "lait demi ecreme"


def test_a_simple_plural_does_not_break_a_match():
    assert normalise("yaourts") == normalise("yaourt")


def test_an_invariant_singular_still_matches_itself():
    """"ananas"/"couscous" are not plurals, but the trim is applied
    symmetrically on both sides of every comparison, so an invariant
    singular still folds to the same form wherever it appears and still
    matches itself — even though the trimmed form ("anana", "couscou") is
    not a real word."""
    assert normalise("ananas") == normalise("Ananas")
    found = candidates(names=["ananas"], products=[{"id": 1, "name": "Ananas"},
                                                     {"id": 2, "name": "Pâtes"}])
    assert found[0].product_id == 1


def test_the_brand_is_removed_before_comparing():
    assert strip_brand("Bjorg Muesli Raisin Figue", "Bjorg") == "Muesli Raisin Figue"
    assert strip_brand("Muesli", None) == "Muesli"


def test_the_brand_removal_does_not_corrupt_neighbouring_words():
    """A bare substring replace would turn "Porc fumé Or Label" into
    "P{o}rc fumé Label" when stripping the brand "Or" — the letters "or"
    inside "Porc" must survive."""
    assert strip_brand("Porc fumé Or Label", "Or") == "Porc fumé Label"


def test_a_brand_ending_in_punctuation_still_strips_cleanly():
    assert strip_brand("Bjorg (bio) Muesli", "Bjorg (bio)") == "Muesli"


def test_brands_with_symbols_still_strip_cleanly():
    assert strip_brand("M&S Biscuits", "M&S") == "Biscuits"
    assert strip_brand("Coop+ Lait", "Coop+") == "Lait"


def test_a_brand_absent_from_the_name_leaves_it_untouched():
    assert strip_brand("Muesli", "Nonexistent") == "Muesli"


def test_the_generic_name_finds_the_product():
    found = candidates(names=["Muesli aux fruits", None], products=CATALOGUE)
    assert found[0].product_id == 2


def test_a_ligature_in_the_catalogue_is_still_found():
    found = candidates(names=["oeufs frais de poule"], products=CATALOGUE)
    assert found[0].product_id == 3


def test_the_best_of_the_names_wins():
    """The commercial name is noise; the generic name is the signal."""
    found = candidates(names=["Panzani Torsades 500g", "Pâtes"], products=CATALOGUE)
    assert found[0].product_id == 1


def test_at_most_five_candidates_come_back():
    found = candidates(names=["lait"], products=CATALOGUE, limit=5)
    assert len(found) <= 5


def test_the_order_is_stable_for_equal_scores():
    twins = [{"id": 9, "name": "Sel"}, {"id": 8, "name": "Sel"}]
    found = candidates(names=["Sel"], products=twins)
    assert [c.product_id for c in found] == [8, 9]


def test_nothing_matches_an_empty_name():
    assert candidates(names=[None, ""], products=CATALOGUE) == []


def test_a_clear_winner_is_preselected():
    found = [Candidate(1, "Pâtes", 0.92), Candidate(2, "Muesli", 0.31)]
    assert preselect(found).product_id == 1


def test_a_hesitation_is_never_resolved_on_its_own():
    """Two close candidates mean the panel asks. Guessing writes the wrong
    nutrition onto the wrong product, permanently."""
    found = [Candidate(1, "Yaourt nature", 0.82), Candidate(2, "Yaourt sucré", 0.78)]
    assert preselect(found) is None


def test_a_weak_best_candidate_is_not_preselected():
    found = [Candidate(1, "Pâtes", 0.60), Candidate(2, "Muesli", 0.10)]
    assert preselect(found) is None


def test_a_single_strong_candidate_is_preselected():
    assert preselect([Candidate(1, "Pâtes", 0.90)]).product_id == 1


def test_no_candidates_preselect_to_nothing():
    assert preselect([]) is None


def test_a_score_exactly_at_the_threshold_does_not_preselect():
    """The score boundary is exclusive on purpose: exactly PRESELECT_SCORE is
    the threshold itself, not "clearly above" it."""
    found = [Candidate(1, "Pâtes", PRESELECT_SCORE)]
    assert preselect(found) is None


def test_a_score_just_above_the_threshold_preselects():
    found = [Candidate(1, "Pâtes", PRESELECT_SCORE + 0.01)]
    assert preselect(found).product_id == 1


def test_a_margin_exactly_at_the_threshold_does_not_preselect():
    """The margin boundary is exclusive on purpose: exactly PRESELECT_MARGIN
    over the runner-up is the threshold itself, not a clear gap."""
    best = PRESELECT_SCORE + 0.15
    found = [Candidate(1, "Pâtes", best), Candidate(2, "Muesli", best - PRESELECT_MARGIN)]
    assert preselect(found) is None


def test_a_margin_just_above_the_threshold_preselects():
    best = PRESELECT_SCORE + 0.15
    found = [Candidate(1, "Pâtes", best), Candidate(2, "Muesli", best - PRESELECT_MARGIN - 0.01)]
    assert preselect(found).product_id == 1


def test_the_real_catalogue_matches_a_real_card():
    """Reads the 34 captured cards and the real product names."""
    import json
    from pathlib import Path

    fixtures = Path(__file__).parent.parent / "fixtures" / "off" / "catalogue.json"
    cards = [e for e in json.loads(fixtures.read_text(encoding="utf-8")).values()
             if e.get("product")]
    assert cards, "the fixtures must be present"

    any_candidates = False
    for entry in cards:
        product = entry["product"]
        names = [product.get("generic_name_fr"), product.get("product_name_fr")]
        found = candidates(names=names, products=CATALOGUE)
        any_candidates = any_candidates or bool(found)
        # Nothing is asserted about which product wins — the point is that
        # scoring never raises and never returns a score outside [0, 1].
        assert all(0.0 <= c.score <= 1.0 for c in found)

    # A stubbed-out matcher that always returns [] would satisfy every
    # assertion above; require that real scoring actually happens at least
    # once across the 34 records.
    assert any_candidates


# --- lot 4 : rapprocher une ligne de caisse d'une ligne de panier -----------

from custom_components.home_stock.domain.matching import (  # noqa: E402
    LineMatch, receipt_candidates,
)

CART = [
    {"id": 1, "article_label": "Lait demi-écrémé 1 L", "brand": "Lactel",
     "unit_price": 1.05},
    {"id": 2, "article_label": "Panzani Coquillettes 500 g", "brand": "Panzani",
     "unit_price": 1.30},
    {"id": 3, "article_label": "Yaourt nature x4", "brand": "Malo",
     "unit_price": 2.00},
]


def test_a_till_abbreviation_matches_its_article():
    """« LT DEMI ECR 1L » contre « Lait demi-écrémé 1 L »."""
    found = receipt_candidates(label="LT DEMI ECR 1L", lines=CART, unit_price=None)
    assert found[0].line_id == 1
    assert found[0].score > found[1].score


def test_the_brand_is_tried_both_ways():
    """« COQUILLETTES 500G » ne nomme pas la marque ; « PANZANI COQ » ne
    nomme que la marque. Les deux doivent tomber sur la même ligne."""
    for label in ("COQUILLETTES 500G", "PANZANI COQ 500G"):
        found = receipt_candidates(label=label, lines=CART, unit_price=None)
        assert found[0].line_id == 2, label


def test_a_price_within_one_percent_earns_a_bonus():
    plain = receipt_candidates(label="YAO NAT X4", lines=CART, unit_price=None)
    priced = receipt_candidates(label="YAO NAT X4", lines=CART, unit_price=2.005)
    assert dict((c.line_id, c.score) for c in priced)[3] > \
        dict((c.line_id, c.score) for c in plain)[3]


def test_a_price_two_percent_away_earns_nothing():
    plain = receipt_candidates(label="YAO NAT X4", lines=CART, unit_price=None)
    priced = receipt_candidates(label="YAO NAT X4", lines=CART, unit_price=2.05)
    assert dict((c.line_id, c.score) for c in priced)[3] == \
        pytest.approx(dict((c.line_id, c.score) for c in plain)[3])


def test_a_price_bonus_alone_does_not_reach_the_auto_threshold():
    """Garde-fou : la prime AIDE, elle ne décide pas. Deux articles à 1,99 €
    ne se confondent pas parce qu'ils coûtent pareil."""
    from custom_components.home_stock.domain.matching import preselect
    found = receipt_candidates(label="XYZ QRS TUV", lines=CART, unit_price=1.05)
    assert preselect(found) is None


def test_the_lot_one_thresholds_are_unchanged():
    """0,75 et 0,10 : un test les relit depuis `matching`, pour qu'un
    ajustement du lot 4 ne déplace pas l'appariement d'ingrédients du lot 3."""
    assert PRESELECT_SCORE == 0.75
    assert PRESELECT_MARGIN == 0.10


def test_receipt_candidates_are_deterministic_and_typed():
    first = receipt_candidates(label="LT DEMI ECR 1L", lines=CART, unit_price=1.05)
    second = receipt_candidates(label="LT DEMI ECR 1L", lines=CART, unit_price=1.05)
    assert first == second
    assert all(isinstance(candidate, LineMatch) for candidate in first)


def test_an_empty_cart_matches_nothing():
    assert receipt_candidates(label="LT DEMI", lines=[], unit_price=None) == []
    assert receipt_candidates(label="", lines=CART, unit_price=None) == []
