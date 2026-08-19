"""OFF record -> article columns, on the real fixtures and the fabricated ones."""
import json
from pathlib import Path

import pytest

from custom_components.home_stock.off.mapping import (
    map_article,
    nutrition_per_base_unit,
    parse_net_quantity,
    to_article_columns,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "off"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _anomaly(key: str) -> dict:
    return _load("anomalies.json")[key]["product"]


# --- net quantity -----------------------------------------------------------

def test_a_weight_in_kilograms_becomes_grams():
    assert parse_net_quantity({"product_quantity": 1.5, "product_quantity_unit": "kg"}) == (1500.0, "g")


def test_a_volume_in_centilitres_becomes_millilitres():
    assert parse_net_quantity(_anomaly("volume_en_cl")) == (750.0, "ml")


def test_an_unreadable_quantity_is_rejected_rather_than_guessed():
    # "1,kg" is a real OFF entry. float("1,".replace(",", ".")) would happily
    # return 1.0 and silently invent a one-kilogram pack.
    assert parse_net_quantity(_anomaly("quantite_illisible")) is None


def test_a_zero_or_absurd_quantity_is_rejected():
    assert parse_net_quantity(_anomaly("quantite_nulle")) is None
    assert parse_net_quantity(_anomaly("quantite_demesuree")) is None


def test_a_countable_unit_is_not_a_weight():
    assert parse_net_quantity(_anomaly("sans_nutrition")) is None


def test_a_decimal_comma_with_digits_is_read():
    assert parse_net_quantity({"product_quantity": "1,5", "product_quantity_unit": "l"}) == (1500.0, "ml")


def test_a_lone_trailing_comma_is_rejected_rather_than_guessed():
    """"1," is the hazard "1,kg" was meant to guard against, and does not:
    any digits-only regex already rejects "1,kg" (it has a trailing "kg"
    inside the number field), so that test passes even if `_NUMBER` were
    loosened to accept a trailing comma. "1," isolates the actual hazard: a
    lenient comma-to-dot replacement would turn it into `float("1.")` == 1.0
    and silently invent a one-kilogram pack out of a malformed number.
    """
    assert parse_net_quantity({"product_quantity": "1,", "product_quantity_unit": "kg"}) is None


# --- nutrition --------------------------------------------------------------

def test_nutrition_comes_back_per_100_grams():
    mapped = map_article(_anomaly("volume_en_cl"), "food")
    assert mapped.nutrition_per_100["kcal"] == pytest.approx(824)
    assert mapped.nutrition_per_100["fat"] == pytest.approx(91.6)
    assert mapped.nutrition_per_100["saturated_fat"] == pytest.approx(13.8)


def test_impossible_calories_reject_the_whole_nutrition():
    mapped = map_article(_anomaly("kcal_impossibles"), "food")
    assert mapped.nutrition_per_100 is None
    assert "kcal" in " ".join(mapped.rejections)


def test_macros_that_do_not_fit_in_100_grams_reject_the_whole_nutrition():
    mapped = map_article(_anomaly("macros_incoherentes"), "food")
    assert mapped.nutrition_per_100 is None


def test_values_given_per_serving_are_brought_back_to_100_grams():
    mapped = map_article(_anomaly("par_portion_seulement"), "food")
    # 140 kcal for a 35 g serving -> 400 kcal per 100 g
    assert mapped.nutrition_per_100["kcal"] == pytest.approx(400)


def test_prepared_values_are_ignored_because_we_stock_the_dry_product():
    mapped = map_article(_anomaly("prepare_seulement"), "food")
    assert mapped.nutrition_per_100 is None


def test_a_record_with_no_nutrition_keeps_the_rest_of_the_card():
    mapped = map_article(_anomaly("sans_nutrition"), "products")
    assert mapped.nutrition_per_100 is None
    assert mapped.label == "Éponge grattante"
    assert mapped.aisle == "Entretien et maison"


def test_an_implausible_added_sugars_rejects_the_whole_nutrition():
    """added_sugars was the one nutriment with no plausibility guard: a
    decimal-shift typo (9999 instead of 9.999) passed straight through the
    "one bad number condemns the table" rule."""
    product = {
        "nutriments": {
            "energy-kcal_100g": 200,
            "proteins_100g": 5,
            "added-sugars_100g": 9999,
        }
    }
    mapped = map_article(product, "food")
    assert mapped.nutrition_per_100 is None


def test_a_nutrition_table_without_an_energy_value_is_not_usable():
    """Calories per day are the whole point of this accounting: a table with
    some nutriments but no energy value must be refused wholesale, not handed
    out missing "kcal" for a later caller to KeyError on."""
    product = {"nutriments": {"added-sugars_100g": 0}}
    mapped = map_article(product, "petfood")
    assert mapped.nutrition_per_100 is None
    assert "no energy value" in " ".join(mapped.rejections)


def test_a_non_dict_product_raises_instead_of_mapping_a_not_found_response():
    """OFF's own "not found" response for a barcode comes back as `product:
    None`. A caller must never be able to map that by accident and get a
    card full of Nones that looks like a real, empty product."""
    with pytest.raises(ValueError):
        map_article(None, "food")


def test_a_tag_field_stored_as_a_bare_string_is_not_corrupted():
    """", ".join("en:milk") silently yields "e, n, :, m, i, l, k" — a string
    is iterable character by character. OFF sometimes stores a single tag as
    a bare string instead of a one-element list."""
    product = {"allergens_tags": "en:milk"}
    mapped = map_article(product, "food")
    assert mapped.allergens == "en:milk"


# --- per base unit ----------------------------------------------------------

def test_a_gram_product_divides_by_a_hundred():
    per_base = nutrition_per_base_unit({"kcal": 350.0, "proteins": 12.0}, "g", None)
    assert per_base["kcal"] == pytest.approx(3.5)
    assert per_base["proteins"] == pytest.approx(0.12)


def test_a_piece_product_needs_its_net_weight():
    per_base = nutrition_per_base_unit({"kcal": 350.0}, "piece", 500.0)
    assert per_base["kcal"] == pytest.approx(1750.0)


def test_a_piece_product_without_a_net_weight_gets_nothing_rather_than_a_guess():
    """NULL is visible and fixable. A factor of a thousand is not."""
    assert nutrition_per_base_unit({"kcal": 350.0}, "piece", None) is None


def test_a_millilitre_product_divides_by_a_hundred():
    """Removing "ml" from the recognised base units sends every liquid down
    the piece branch: a 1000 ml bottle at 824 kcal/100 ml would become 8240
    kcal PER MILLILITRE, a thousand-fold error, and nothing would fail."""
    per_base = nutrition_per_base_unit({"kcal": 824.0}, "ml", None)
    assert per_base["kcal"] == pytest.approx(8.24)


def test_gram_and_millilitre_products_behave_identically():
    same_numbers = {"kcal": 824.0, "fat": 91.6}
    assert nutrition_per_base_unit(same_numbers, "g", None) == nutrition_per_base_unit(
        same_numbers, "ml", None
    )


def test_an_unrecognised_base_unit_raises_instead_of_silently_treating_it_as_a_piece():
    """A caller must never be able to pass OFF's own unit ("kg", "cl", ...)
    here by mistake and get a silently wrong factor back."""
    with pytest.raises(ValueError):
        nutrition_per_base_unit({"kcal": 350.0}, "kg", 1000.0)


# --- article columns ---------------------------------------------------------

def test_kcal_is_renamed_to_its_article_column():
    columns = to_article_columns({"kcal": 3.5, "proteins": 0.12})
    assert columns["kcal_per_base_unit"] == pytest.approx(3.5)
    assert columns["proteins"] == pytest.approx(0.12)
    assert "kcal" not in columns


def test_none_yields_an_empty_dict_of_columns():
    assert to_article_columns(None) == {}


# --- the real catalogue -----------------------------------------------------

def test_every_real_card_maps_without_raising():
    for code, entry in _load("catalogue.json").items():
        product = entry.get("product")
        if not product:
            continue
        mapped = map_article(product, entry["off_source"])
        assert mapped.off_source == entry["off_source"]
        assert mapped.aisle
        if mapped.nutrition_per_100 is not None:
            assert 0 <= mapped.nutrition_per_100["kcal"] <= 900


def test_the_real_catalogue_yields_the_expected_coverage():
    """Guards that reject too much are as bad as guards that reject nothing.
    Measured on the 34 cards captured on 2026-08-19. The "requires an energy
    value" rule (added in fix round 1) does not lower this floor: it rejects
    zero additional catalogue records, all five already lacked a usable
    nutrition table for other reasons (see the plausibility test below)."""
    catalogue = [e for e in _load("catalogue.json").values() if e.get("product")]
    mapped = [map_article(e["product"], e["off_source"]) for e in catalogue]

    with_nutrition = [m for m in mapped if m.nutrition_per_100]
    with_weight = [m for m in mapped if m.net_quantity]

    assert len(mapped) == 34
    assert len(with_nutrition) >= 29, "the guards are throwing away real data"
    assert len(with_weight) >= 24


def test_no_real_catalogue_record_is_rejected_by_a_plausibility_guard():
    """This is the regression alarm the coverage count was standing in for:
    it does not couple to how complete Open Food Facts' data happens to be
    today. Every rejection reason across the 34 real cards must be an
    ABSENCE of usable data ("no usable nutrition table", "no energy value"),
    never a threshold being exceeded (kcal/macro out of range, macro sum).
    If a real record ever trips a plausibility guard, that is the guards
    doing their job and this test should be updated to say so explicitly —
    but today it does not happen even once."""
    catalogue = [e for e in _load("catalogue.json").values() if e.get("product")]
    for entry in catalogue:
        mapped = map_article(entry["product"], entry["off_source"])
        for reason in mapped.rejections:
            assert "out of range" not in reason, reason
            assert "exceed" not in reason, reason


def test_the_sister_databases_map_too():
    for entry in _load("soeurs.json").values():
        mapped = map_article(entry["product"], entry["off_source"])
        assert mapped.off_source in ("products", "beauty", "petfood")
