"""The aisle classifier, exercised on the real catalogue fixtures."""
import json
from pathlib import Path

import pytest

from custom_components.home_stock.aisles import AISLES, resolve_aisle

FIXTURES = Path(__file__).parent / "fixtures" / "off"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_the_most_specific_tag_wins():
    # OFF orders tags general -> specific. "frozen-foods" must not beat
    # "ice-creams" just because it comes first.
    tags = ["en:foods", "en:frozen-foods", "en:desserts", "en:ice-creams"]
    assert resolve_aisle(tags, "food") == "Surgelés"


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
