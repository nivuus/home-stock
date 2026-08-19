"""Attaching a scanned article to a catalogue product."""
import pytest

from custom_components.home_stock.domain.matching import (
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


def test_the_brand_is_removed_before_comparing():
    assert strip_brand("Bjorg Muesli Raisin Figue", "Bjorg") == "Muesli Raisin Figue"
    assert strip_brand("Muesli", None) == "Muesli"


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


def test_the_real_catalogue_matches_a_real_card():
    """Reads the 34 captured cards and the real product names."""
    import json
    from pathlib import Path

    fixtures = Path(__file__).parent.parent / "fixtures" / "off" / "catalogue.json"
    cards = [e for e in json.loads(fixtures.read_text(encoding="utf-8")).values()
             if e.get("product")]
    assert cards, "the fixtures must be present"

    for entry in cards:
        product = entry["product"]
        names = [product.get("generic_name_fr"), product.get("product_name_fr")]
        found = candidates(names=names, products=CATALOGUE)
        # Nothing is asserted about which product wins — the point is that
        # scoring never raises and never returns a score outside [0, 1].
        assert all(0.0 <= c.score <= 1.0 for c in found)
