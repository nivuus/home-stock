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


@pytest.mark.parametrize(
    "unit, amount, expected",
    [
        ("g", 250, (250.0, "g")),
        ("gr", 250, (250.0, "g")),
        ("gram", 250, (250.0, "g")),
        ("grammes", 250, (250.0, "g")),
        ("kg", 1.5, (1500.0, "g")),
        # A wrong factor here is exactly the class of bug this module exists
        # to prevent: a mangled "mg" -> "g" factor would report 500 mg of a
        # spice as 500 g, a thousand-fold overstatement.
        ("mg", 500, (0.5, "g")),
        ("ml", 250, (250.0, "ml")),
        ("cl", 75, (750.0, "ml")),
        ("dl", 5, (500.0, "ml")),
        ("l", 1.5, (1500.0, "ml")),
    ],
)
def test_every_unit_to_base_factor_is_pinned(unit, amount, expected):
    assert parse_net_quantity({"product_quantity": amount, "product_quantity_unit": unit}) == expected


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


def test_a_present_per_100_table_is_not_overwritten_by_a_serving_table():
    """The per-100 table is the source of truth; the per-serving table is
    only ever a fallback for its ABSENCE. Twenty-five of the thirty-four
    real records carry both key families, so this is not a theoretical
    case: if the "no per-100 data yet" guard around the serving fallback
    were ever lost, a record's real per-100 figures would silently be
    overwritten by its (here, deliberately disagreeing) per-serving ones.
    Built inline rather than added to anomalies.json: this shape — a
    complete per-100 table plus a contradicting per-serving one — did not
    occur in the real captured data, so it does not belong in the fixture
    that records what real data actually looks like."""
    product = {
        "nutriments": {
            "energy-kcal_100g": 360,
            "energy-kcal_serving": 150,  # 150 kcal / 30 g would rescale to 500/100g
        },
        "serving_quantity": 30,
        "nutrition_data_per": "serving",
    }
    mapped = map_article(product, "food")
    assert mapped.nutrition_per_100["kcal"] == pytest.approx(360)


def test_serving_values_are_not_rescaled_without_an_explicit_per_serving_claim():
    """*_serving keys are only trusted as a per-100 stand-in when OFF itself
    marks nutrition_data_per == "serving". Without that explicit claim we do
    not actually know what basis those numbers are on, and must not invent a
    rescaling — the record must come back with no usable nutrition instead
    of a confidently wrong one."""
    product = {
        "nutriments": {"energy-kcal_serving": 108},
        "serving_quantity": 30,
        "nutrition_data_per": "100g",
    }
    mapped = map_article(product, "food")
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


# --- Fix round 3: a Nova group or Nutri-Score a contributor mistyped -------

def test_an_absurd_nova_group_is_dropped_instead_of_kept():
    """A value like 1e30 must not reach int() and only fail later, uncaught,
    when it is bound as a SQLite parameter — refused here, at the source."""
    mapped = map_article({"nova_group": 1e30}, "food")
    assert mapped.nova is None


def test_a_nova_group_outside_the_four_real_groups_is_dropped():
    mapped = map_article({"nova_group": 99}, "food")
    assert mapped.nova is None


def test_a_real_nova_group_passes_through():
    mapped = map_article({"nova_group": 4}, "food")
    assert mapped.nova == 4


def test_an_implausible_nutriscore_grade_is_dropped_instead_of_kept():
    """"zzz" is exactly what article/update already refuses one line away —
    an OFF-sourced value gets the same bound, at the source that owns it."""
    mapped = map_article({"nutriscore_grade": "zzz"}, "food")
    assert mapped.nutriscore is None


def test_a_real_nutriscore_grade_passes_through_case_folded():
    mapped = map_article({"nutriscore_grade": "A"}, "food")
    assert mapped.nutriscore == "a"


def test_a_dropped_nutriscore_is_recorded_in_rejections():
    """article_create's off_dropped_fields needs a way to know a value was
    dropped even though this module already neutralises it before the
    handler ever sees a bad value — recorded by column name, not a
    sentence, so a caller can merge it straight in."""
    mapped = map_article({"nutriscore_grade": "zzz"}, "food")
    assert mapped.nutriscore is None
    assert "nutriscore" in mapped.rejections


def test_a_dropped_nova_group_is_recorded_in_rejections():
    mapped = map_article({"nova_group": 99}, "food")
    assert mapped.nova is None
    assert "nova" in mapped.rejections


def test_an_absent_nutriscore_is_not_recorded_as_a_rejection():
    """A field OFF never sent is an absence, not a rejection — the
    difference matters to off_dropped_fields, which must not claim
    something was "dropped" when nothing was ever offered."""
    mapped = map_article({}, "food")
    assert mapped.nutriscore is None
    assert mapped.nova is None
    assert "nutriscore" not in mapped.rejections
    assert "nova" not in mapped.rejections


@pytest.mark.parametrize("sentinel", ["unknown", "not-applicable", "UNKNOWN"])
def test_offs_own_no_grade_sentinel_reports_nothing_dropped(sentinel):
    """The round-4 fix over-reported: 14 of 51 real catalogue records carry
    OFF's own "unknown" placeholder here, meaning "no grade", not "a
    contributor typed something implausible". Reporting that as dropped
    would tell the user something was rejected on more than a quarter of
    ordinary scans. A genuinely implausible value ("zzz", tested above)
    must still be reported — only OFF's own sentinels are exempt."""
    mapped = map_article({"nutriscore_grade": sentinel}, "food")
    assert mapped.nutriscore is None
    assert "nutriscore" not in mapped.rejections


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


def test_an_unexpected_nutrition_key_raises_instead_of_vanishing():
    """This function's whole purpose is to be the seam where a key that
    would otherwise vanish through repo.insert_article's silent filtering
    stops the caller instead. Filtering it out here too would just move the
    same silent failure one step earlier."""
    with pytest.raises(ValueError):
        to_article_columns({"kcal": 3.5, "mystery": 1.0})


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


def test_map_article_survives_a_malformed_categories_tags():
    """The module's promise is that it never raises: a non-string inside
    `categories_tags` must cost one ignored tag, not the whole scan."""
    mapped = map_article({"code": "1", "product_name_fr": "Emmental râpé",
                          "categories_tags": [None, "en:cheeses", 7]}, "food")

    assert mapped.aisle == "Fromages"
    assert mapped.label == "Emmental râpé"


from custom_components.home_stock.off.mapping import plausible_serving, serving_from_raw


def test_plausible_serving_accepts_a_number_and_a_numeric_string():
    assert plausible_serving(30, base_unit="g", net_quantity=500) == 30.0
    assert plausible_serving("30", base_unit="g", net_quantity=500) == 30.0
    assert plausible_serving("12,5", base_unit="ml", net_quantity=1000) == 12.5


def test_plausible_serving_refuses_a_piece_product():
    # A serving of a product tracked by the piece is one piece: the column
    # has nothing to say, and a number in grams would be a trap there.
    assert plausible_serving(30, base_unit="piece", net_quantity=None) is None


def test_plausible_serving_refuses_zero_and_the_absurd():
    assert plausible_serving(0, base_unit="g", net_quantity=500) is None
    assert plausible_serving(-5, base_unit="g", net_quantity=500) is None
    assert plausible_serving(5000.1, base_unit="g", net_quantity=None) is None
    assert plausible_serving(5000, base_unit="g", net_quantity=None) == 5000.0


def test_plausible_serving_refuses_a_serving_bigger_than_the_pack():
    assert plausible_serving(300, base_unit="g", net_quantity=250) is None
    # Exactly the pack size stays plausible: a single-serving tin.
    assert plausible_serving(250, base_unit="g", net_quantity=250) == 250.0


def test_plausible_serving_refuses_malformed_text():
    for value in ("", "1,", "trente", None, True, [30]):
        assert plausible_serving(value, base_unit="g", net_quantity=None) is None


def test_serving_from_raw_reads_the_stored_record():
    raw = '{"serving_quantity": "30", "product_name": "Yaourt"}'
    assert serving_from_raw(raw, base_unit="g", net_quantity=125) == 30.0


def test_serving_from_raw_survives_anything_unusable():
    for raw in (None, "", "{tronqu", "[1, 2]", '"une chaine"', "{}"):
        assert serving_from_raw(raw, base_unit="g", net_quantity=None) is None


def test_off_mapping_still_exposes_the_unit_table():
    """Le déplacement dans le domaine ne doit rien casser chez les appelants
    du lot 1 : `off.mapping.UNIT_TO_BASE` reste importable, et c'est le MÊME
    objet — pas une copie qui dériverait."""
    from custom_components.home_stock.domain.units import UNIT_TO_BASE as source
    from custom_components.home_stock.off.mapping import UNIT_TO_BASE as reexport
    assert reexport is source
