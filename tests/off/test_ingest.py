"""build_article_values: the one place an OFF record becomes `article` columns.

Shared by websocket_api.article_create (a fresh scan) and services._write_resync
(a background catalogue refresh) — see off/ingest.py's own module docstring.
"""
from custom_components.home_stock.off.ingest import (
    MAX_OFF_RAW_BYTES,
    build_article_values,
)

MUESLI = {
    "code": "3229820129488",
    "product_name_fr": "Muesli Raisin, Figue, Datte, Abricot",
    "brands": "Bjorg",
    "product_quantity": 375,
    "product_quantity_unit": "g",
    "nutriscore_grade": "a",
    "categories_tags": ["en:plant-based-foods", "en:breakfasts", "en:breakfast-cereals"],
    "nutrition_data_per": "100g",
    "nutriments": {"energy-kcal_100g": 360, "proteins_100g": 9, "carbohydrates_100g": 60,
                   "fat_100g": 6, "salt_100g": 0.02},
}


def test_the_twelve_mapped_columns_and_nutrition_all_land():
    ingest = build_article_values(MUESLI, "food", "g", synced_at="2026-08-19T10:00:00")

    assert ingest.values["brand"] == "Bjorg"
    assert ingest.values["net_quantity"] == 375
    assert ingest.values["nutriscore"] == "a"
    assert ingest.values["off_source"] == "food"
    assert ingest.values["kcal_per_base_unit"] == 3.6
    assert ingest.values["off_synced_at"] == "2026-08-19T10:00:00"
    assert ingest.values["off_raw"]
    assert ingest.dropped_fields == []


def test_a_thin_record_never_writes_a_none():
    """A resync must be able to fill a gap or correct a value, but never
    erase one (review round 1's ruling) — the mechanism is that a column
    OFF said nothing about is simply absent from `values`, never written as
    an explicit NULL a caller would apply unconditionally."""
    thin = {"code": "3229820129488", "product_name_fr": "Muesli"}

    ingest = build_article_values(thin, "food", "g", synced_at="2026-08-19T10:00:00")

    assert "brand" not in ingest.values
    assert "net_quantity" not in ingest.values
    assert "nutriscore" not in ingest.values
    assert None not in ingest.values.values()
    # What OFF did answer is still there.
    assert ingest.values["label"] == "Muesli"
    assert ingest.values["off_synced_at"] == "2026-08-19T10:00:00"


def test_an_implausible_label_is_dropped_and_reported():
    off_payload = {**MUESLI, "product_name_fr": "x" * 1000}

    ingest = build_article_values(off_payload, "food", "g", synced_at="2026-08-19T10:00:00")

    assert "label" not in ingest.values
    assert ingest.dropped_fields == ["label"]
    # Everything else the record offered still landed.
    assert ingest.values["brand"] == "Bjorg"


def test_an_oversized_off_raw_is_dropped_not_truncated():
    off_payload = {**MUESLI, "ingredients_text_fr": "x" * (MAX_OFF_RAW_BYTES + 1)}

    ingest = build_article_values(off_payload, "food", "g", synced_at="2026-08-19T10:00:00")

    assert "off_raw" not in ingest.values
    assert "off_raw" in ingest.dropped_fields
    # The rest of the record is unaffected by off_raw alone being too big.
    assert ingest.values["brand"] == "Bjorg"
    assert ingest.values["off_synced_at"] == "2026-08-19T10:00:00"


def test_a_nova_off_mapping_already_rejected_is_reported_as_dropped():
    off_payload = {**MUESLI, "nova_group": 1e30}

    ingest = build_article_values(off_payload, "food", "g", synced_at="2026-08-19T10:00:00")

    assert "nova" not in ingest.values
    assert ingest.dropped_fields == ["nova"]


def test_an_off_no_grade_sentinel_reports_nothing_dropped():
    off_payload = {**MUESLI, "nutriscore_grade": "unknown"}

    ingest = build_article_values(off_payload, "food", "g", synced_at="2026-08-19T10:00:00")

    assert "nutriscore" not in ingest.values
    assert ingest.dropped_fields == []
