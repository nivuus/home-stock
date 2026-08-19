"""The aisle classifier, exercised on the real catalogue fixtures."""
import json
from pathlib import Path

import pytest

from custom_components.home_stock.aisles import AISLES, resolve_aisle

FIXTURES = Path(__file__).parent / "fixtures" / "off"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_the_most_specific_tag_wins():
    # OFF orders tags general -> specific, most specific last. This test
    # discriminates forward from backward: backward finds en:cheeses (Fromages),
    # forward finds en:dairies (Crémerie). If resolve_aisle() used forward scan,
    # this would fail.
    tags = ["en:foods", "en:dairies", "en:cheeses"]
    assert resolve_aisle(tags, "food") == "Fromages"


def test_an_unrecognised_tag_falls_back_to_the_database_of_origin():
    assert resolve_aisle(["en:unknown-thing"], "beauty") == "Hygiène et beauté"
    assert resolve_aisle(["en:unknown-thing"], "petfood") == "Animalerie"
    assert resolve_aisle(["en:unknown-thing"], "products") == "Entretien et maison"
    assert resolve_aisle(["en:unknown-thing"], "food") == "Épicerie salée"


def test_no_tags_at_all_still_yields_an_aisle():
    assert resolve_aisle(None, None) == "Autre"
    assert resolve_aisle([], None) == "Autre"


def test_generic_tags_only_falls_back_rather_than_guessing():
    record = _load("anomalies.json")["categories_generiques_seulement"]["product"]
    assert resolve_aisle(record["categories_tags"], "food") == "Épicerie salée"


def test_every_catalogue_fixture_lands_in_a_real_aisle():
    catalogue = _load("catalogue.json")
    for code, entry in catalogue.items():
        product = entry.get("product")
        if not product:
            continue
        aisle = resolve_aisle(product.get("categories_tags"), entry["off_source"])
        assert aisle in AISLES, f"{code} landed outside the referential: {aisle}"


def test_the_sister_databases_classify_out_of_the_food_aisles():
    for entry in _load("soeurs.json").values():
        product = entry["product"]
        aisle = resolve_aisle(product.get("categories_tags"), entry["off_source"])
        assert aisle in ("Hygiène et beauté", "Entretien et maison", "Animalerie", "Autre")


def test_real_records_resolve_to_their_most_specific_aisle():
    # Three real catalogue records that would fail if we scanned forward instead
    # of backward: forward scan finds a general tag first, backward finds a more
    # specific one. These records prove the backward walk is used.
    catalogue = _load("catalogue.json")

    # 3017800078860: canned legumes. Backward finds en:legumes → Fruits et légumes.
    entry = catalogue["3017800078860"]
    assert resolve_aisle(entry["product"].get("categories_tags"), entry["off_source"]) == "Fruits et légumes"

    # 3245414638853: petit suisse (fermented dairy dessert). Backward finds
    # en:desserts (index 9 backward) before en:cheeses (index 10 backward) →
    # Épicerie sucrée. Forward would find en:cheeses first → Fromages.
    entry = catalogue["3245414638853"]
    assert resolve_aisle(entry["product"].get("categories_tags"), entry["off_source"]) == "Épicerie sucrée"

    # 8445290871923: coffee capsule. Backward finds en:coffees → Petit-déjeuner.
    entry = catalogue["8445290871923"]
    assert resolve_aisle(entry["product"].get("categories_tags"), entry["off_source"]) == "Petit-déjeuner"


def test_tags_are_normalised_before_lookup():
    # Real OFF data contains tags with spaces and capitals. Normalisation
    # (lowercase + replace spaces with hyphens) ensures they match canonical keys.
    tags = ["en:foods", "en:Pet-Foods"]
    # en:Pet-Foods -> en:pet-foods (canonically in TAG_TO_AISLE)
    assert resolve_aisle(tags, "food") == "Animalerie"


def test_non_food_sources_skip_tag_table_to_avoid_cross_contamination():
    # en:Creams on Open Beauty Facts is a hand cream, not dairy. If TAG_TO_AISLE
    # were consulted for beauty records, it would file hand cream under "Crémerie"
    # (which is where dairy creams go). SOURCE_TO_AISLE correctly sends beauty to
    # "Hygiène et beauté".
    tags = ["en:Creams", "en:Non-food-products"]
    assert resolve_aisle(tags, "beauty") == "Hygiène et beauté"

    # Conversely, the same tag on a food record should go to the dairy aisle.
    tags_lowercased = ["en:creams"]
    assert resolve_aisle(tags_lowercased, "food") == "Crémerie"


@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        ("en:cheeses", "Fromages"),
        ("en:yogurts", "Crémerie"),
        ("en:hams", "Charcuterie et traiteur"),
        ("en:breakfast-cereals", "Petit-déjeuner"),
        ("en:fresh-vegetables", "Fruits et légumes"),
        ("en:waters", "Boissons"),
        ("en:breads", "Boulangerie"),
        ("en:biscuits", "Épicerie sucrée"),
        ("en:fishes", "Poissonnerie"),
        ("en:pastas", "Épicerie salée"),
    ],
)
def test_known_tags_map_where_a_shopper_expects(tag, expected):
    assert resolve_aisle(["en:foods", tag], "food") == expected
