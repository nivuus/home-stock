"""La réponse du modèle → des lignes validées, une par une. Aucun réseau.

Une ligne fautive est écartée SEULE, contrairement à la nutrition OFF du
lot 1 où un dépassement refuse toute la fiche. La différence est assumée :
une fiche OFF est un tout cohérent dont une valeur aberrante trahit la table
entière ; un ticket est une suite de lignes indépendantes, et perdre les
dix-neuf bonnes parce que la vingtième est illisible n'aide personne.
"""
import json
from pathlib import Path

import pytest

from custom_components.home_stock.const import (
    MAX_RECEIPT_LINES, RECEIPT_BACKDATE_DAYS, RECEIPT_TOTAL_TOLERANCE,
)
from custom_components.home_stock.receipt.parse import (
    RECEIPT_STRUCTURE, ParsedReceipt, parse,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "receipts"
STARTED = "2026-08-21"
TODAY = "2026-08-21"


def _fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _parse(name, **kwargs):
    kwargs.setdefault("session_started_on", STARTED)
    kwargs.setdefault("today", TODAY)
    return parse(_fixture(name), **kwargs)


def test_a_clean_receipt_reads_every_line():
    receipt = _parse("propre.json")
    assert len(receipt.lines) == 5
    assert receipt.store == "Leclerc"
    assert receipt.purchased_on == "2026-08-21"
    assert receipt.total == pytest.approx(12.40)
    assert receipt.currency == "EUR"
    assert receipt.dropped == ()
    assert [line.position for line in receipt.lines] == [1, 2, 3, 4, 5]
    assert receipt.lines[0].label == "LT DEMI ECR 1L"
    assert receipt.lines[0].quantity == pytest.approx(2)
    assert receipt.lines[0].total_price == pytest.approx(2.10)


def test_loyalty_points_and_promotions_are_ignored():
    """Elles ne sont ni des lignes écartées ni des lignes gardées : elles
    n'entrent pas. L'invite le dit, le parseur le vérifie."""
    receipt = _parse("promotions_et_fidelite.json")
    assert [line.label for line in receipt.lines] == ["LT DEMI ECR 1L", "PAIN COMPLET"]
    assert receipt.dropped == ()


def test_a_four_thousand_euro_line_is_dropped_alone():
    """Les dix-neuf autres survivent, et `dropped` la nomme."""
    receipt = _parse("ligne_a_4000_euros.json")
    assert len(receipt.lines) == 19
    assert len(receipt.dropped) == 1
    assert "TELEVISEUR OLED" in receipt.dropped[0]


def test_a_zero_quantity_line_is_dropped():
    """`0 < v` strict : une ligne de zéro article n'a pas été achetée."""
    receipt = _parse("quantite_nulle.json")
    assert [line.label for line in receipt.lines] == ["LT DEMI ECR 1L"]
    assert len(receipt.dropped) == 1


def test_a_1970_date_is_refused_and_the_receipt_survives():
    """Une date hors fenêtre ne rend pas le ticket illisible : elle rend
    `purchased_on is None`, et le panneau demande."""
    receipt = _parse("date_en_1970.json")
    assert receipt.purchased_on is None
    assert len(receipt.lines) == 1
    assert receipt.warnings


@pytest.mark.parametrize("day, accepted", [
    ("2026-08-19", True),       # started_at − 2 j
    ("2026-08-18", False),      # started_at − 3 j
    ("2026-08-21", True),       # aujourd'hui
    ("2026-08-22", False),      # demain
])
def test_the_purchase_date_window_boundaries(day, accepted):
    """`started_at − 2 j` accepté, `started_at − 3 j` refusé, aujourd'hui
    accepté, demain refusé. Les quatre bornes."""
    assert RECEIPT_BACKDATE_DAYS == 2
    payload = {**_fixture("propre.json"), "purchased_on": day}
    receipt = parse(payload, session_started_on=STARTED, today=TODAY)
    assert (receipt.purchased_on == day) is accepted


def test_a_total_that_does_not_add_up_is_flagged_never_blocking():
    """Au-delà de 2 % : `total_gap` porte l'écart, les lignes restent."""
    receipt = _parse("total_qui_ne_tombe_pas_juste.json")
    assert len(receipt.lines) == 1
    assert receipt.total_gap == pytest.approx(20.0 - 1.05)
    assert receipt.warnings


def test_a_gap_just_under_two_percent_is_silent():
    assert RECEIPT_TOTAL_TOLERANCE == 0.02
    payload = _fixture("propre.json")
    somme = sum(line["total_price"] for line in payload["lines"])
    payload["total"] = round(somme * 1.019, 2)
    receipt = parse(payload, session_started_on=STARTED, today=TODAY)
    assert receipt.total_gap is None
    assert receipt.warnings == ()


def test_an_empty_answer_yields_an_empty_receipt_without_raising():
    receipt = _parse("vide.json")
    assert receipt.lines == ()
    assert receipt.total is None and receipt.store is None


def test_a_truncated_answer_yields_an_empty_receipt_without_raising():
    receipt = _parse("tronquee.json")
    assert receipt.store == "Lecl"
    assert receipt.lines == ()
    assert len(receipt.dropped) == 3


def test_more_than_two_hundred_lines_are_cut_and_the_cut_is_reported():
    payload = {"lines": [{"label": f"A{n}", "quantity": 1, "unit_price": 1.0,
                          "total_price": 1.0}
                         for n in range(MAX_RECEIPT_LINES + 20)]}
    receipt = parse(payload, session_started_on=STARTED, today=TODAY)
    assert len(receipt.lines) == MAX_RECEIPT_LINES
    assert any("200" in warning for warning in receipt.warnings)


@pytest.mark.parametrize("payload", [
    None, "", [], 0, True, {"lines": 3}, {"lines": None}, {"lines": [None]},
    {"total": "beaucoup"}, {"purchased_on": 42},
    *(json.loads((FIXTURES / name).read_text(encoding="utf-8"))
      for name in sorted(path.name for path in FIXTURES.glob("*.json"))),
])
def test_parse_never_raises_on_anything(payload):
    result = parse(payload, session_started_on=STARTED, today=TODAY)
    assert isinstance(result, ParsedReceipt)


def test_the_structure_names_the_five_fields_the_panel_needs():
    assert set(RECEIPT_STRUCTURE) >= {"store", "purchased_on", "total",
                                      "currency", "lines"}


def test_nothing_in_this_module_touches_the_network_or_hass():
    """Scan d'import : ni `homeassistant`, ni `aiohttp`, ni `sqlite3`."""
    from custom_components.home_stock.receipt import parse as module
    source = Path(module.__file__).read_text(encoding="utf-8")
    for forbidden in ("homeassistant", "aiohttp", "sqlite3", "requests"):
        assert f"import {forbidden}" not in source
        assert f"from {forbidden}" not in source
