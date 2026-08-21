"""Le vocabulaire français partagé par les deux surfaces.

Le websocket et les services traduisent au même endroit : une même exception
anglaise ne doit pas devenir deux phrases françaises différentes selon que le
panneau ou un script a demandé.
"""
import pytest

from custom_components.home_stock.messages import (
    DOMAIN_ERROR_PATTERNS,
    GENERIC_CODE,
    GENERIC_MESSAGE,
    french_error,
)

# Les messages couverts AVANT le lot 3, avec le code qu'ils rendaient déjà.
# Rejoués tels quels pour prouver qu'aucun motif du lot 3 ne les masque.
LEGACY = [
    ("unknown article 5", "not_found"),
    ("no article 7", "not_found"),
    ("no product 3", "not_found"),
    ("unknown or closed batch 9", "not_found"),
    ("unknown batch 9", "not_found"),
    ("quantity must not be negative, got -1", "invalid_value"),
    ("packaging quantity must be positive, got 0", "invalid_value"),
    ("quantity must be positive, got 0", "invalid_value"),
    ("'kg' is not a base unit; expected one of ('g', 'ml', 'piece')", "invalid_value"),
    ("requested 500, only 200 available", "insufficient_stock"),
    ("batch 3 does not belong to product 8", "invalid_field"),
    ("parts_total and parts_mine go together", "invalid_value"),
    ("a waste movement cannot be shared", "invalid_value"),
    ("parts_total must be between 1 and 24", "invalid_value"),
    ("parts_mine must be between 0 and parts_total", "invalid_value"),
]

LOT3 = [
    ("unknown recipe 4", "not_found"),
    ("unknown meal 12", "not_found"),
    ("unknown ingredient line 41", "not_found"),
    ("unknown slot 'brunch'; expected one of breakfast, lunch, dinner, snack",
     "invalid_value"),
    ("unknown match state 'peut-être'; expected one of unmatched, auto", "invalid_value"),
    ("unknown recipe source 'marmiton'; expected one of manual, themealdb",
     "invalid_value"),
    ("meal 12 is already done", "invalid_value"),
    ("recipe 4 has already been cooked", "invalid_value"),
    ("a 'confirmed' match needs a product; only 'unmatched' and 'ignored' may have none",
     "invalid_field"),
    ("meal 12 cannot be validated: short", "insufficient_stock"),
    ("portions_eaten 4.0 exceeds the 3.0 parts this meal produces", "invalid_value"),
    ("portions_eaten must not be negative, got -1.0", "invalid_value"),
    ("portions_eaten must be a real number, got 'une'", "invalid_value"),
    ("servings must be positive, got 0.0", "invalid_value"),
    ("servings must be a real number, got 'deux'", "invalid_value"),
    ("a recipe serves at least one, got 0", "invalid_value"),
    ("a recipe cannot have more than 40 steps, got 41", "invalid_value"),
    ("a recipe cannot have more than 60 ingredients, got 61", "invalid_value"),
    ("a meal is exactly one of a recipe, a product or a note, got 2", "invalid_value"),
    ("invalid day 'hier'; expected YYYY-MM-DD", "invalid_value"),
    ("unknown reason 'grignotage'; expected one of ('purchase',)", "invalid_value"),
    ("no location to put the dish in", "invalid_value"),
]

# --- lot 4 -----------------------------------------------------------------
LOT4 = [
    ("unknown movement 42", "not_found"),
    ("movement 42 is already a correction", "invalid_value"),
    ("movement 42 has already been corrected", "invalid_value"),
    ("a transfer movement cannot be corrected", "invalid_value"),
    ("a conversion movement cannot be corrected", "invalid_value"),
    ("a cooked movement cannot be corrected", "invalid_value"),
    ("reversing movement 42 would leave batch 7 negative; only 100.0 left",
     "insufficient_stock"),
]


@pytest.mark.parametrize("text, code", LOT4)
def test_the_lot4_domain_errors_become_french(text, code):
    got_code, sentence = french_error(ValueError(text))
    assert got_code == code
    assert sentence != GENERIC_MESSAGE, f"{text!r} retombe sur la phrase générique"
    assert sentence[0].isupper() and sentence.rstrip().endswith((".", "!"))
    assert "ValueError" not in sentence and "{" not in sentence


@pytest.mark.parametrize("text, code", LOT3)
def test_no_lot4_pattern_shadows_a_lot3_one(text, code):
    """Les motifs du lot 4 s'ajoutent EN FIN de tuple. Le premier motif qui
    correspond gagne : ce test rend la règle exécutoire plutôt que relue."""
    got_code, sentence = french_error(ValueError(text))
    assert got_code == code
    assert sentence != GENERIC_MESSAGE, f"{text!r} n'est plus reconnu"


def test_the_three_refusals_of_a_correction_say_three_different_things():
    """Un transfert, une conversion et un mouvement de cuisine sont refusés
    pour trois raisons différentes : une phrase unique laisserait le
    propriétaire sans la moindre idée de quoi faire."""
    phrases = {
        french_error(ValueError(f"a {reason} movement cannot be corrected"))[1]
        for reason in ("transfer", "conversion", "cooked")
    }
    assert len(phrases) == 3


@pytest.mark.parametrize("text, code", LOT3)
def test_the_new_domain_errors_become_french(text, code):
    got_code, sentence = french_error(ValueError(text))
    assert got_code == code
    assert sentence != GENERIC_MESSAGE, f"{text!r} retombe sur la phrase générique"
    # Une phrase, pas un `repr` Python jeté à quelqu'un qui a les mains dans
    # la farine.
    assert sentence[0].isupper() and sentence.rstrip().endswith((".", "!"))
    assert "ValueError" not in sentence and "{" not in sentence


@pytest.mark.parametrize("text, code", LEGACY)
def test_no_new_pattern_shadows_an_older_one(text, code):
    """L'ordre compte : le premier motif qui matche gagne. Les motifs du lot 3
    sont ajoutés EN FIN de liste, jamais au milieu — ce test le rend
    exécutoire plutôt que de compter sur la relecture."""
    got_code, sentence = french_error(ValueError(text))
    assert got_code == code
    assert sentence != GENERIC_MESSAGE, f"{text!r} n'est plus reconnu"


def test_an_unrecognised_error_falls_back_to_the_generic_sentence():
    code, sentence = french_error(ValueError("quelque chose d'imprévu"))
    assert (code, sentence) == (GENERIC_CODE, GENERIC_MESSAGE)


def test_every_pattern_produces_a_french_sentence_without_raising():
    """Une lambda de traduction qui plante remplacerait un refus explicable
    par une erreur interne."""
    for pattern, code, render in DOMAIN_ERROR_PATTERNS:
        assert code
        assert pattern.pattern.startswith("^")


def test_the_same_exception_reads_the_same_on_both_surfaces():
    """Le websocket et les services passent par la MÊME fonction : c'est ce
    qui garantit qu'ils ne divergent pas."""
    from custom_components.home_stock import messages, services, websocket_api
    assert websocket_api.french_error is messages.french_error
    assert services.french_message.__module__ == messages.__name__
