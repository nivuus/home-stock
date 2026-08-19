"""Planning a piece -> gram conversion. Nothing here writes."""
import pytest

from custom_components.home_stock.domain.conversion import (
    ConversionError,
    plan_conversion,
)

PRODUCT = {"id": 1, "name": "Pâtes", "base_unit": "piece"}
ARTICLES = [
    {"id": 10, "product_id": 1, "net_quantity": 500.0},
    {"id": 11, "product_id": 1, "net_quantity": None},
]
BATCHES = [
    {"id": 100, "article_id": 10, "remaining": 2.0, "initial": 3.0},
    {"id": 101, "article_id": 11, "remaining": 1.0, "initial": 1.0},
]


def test_each_article_converts_at_its_own_weight():
    plan = plan_conversion(product=PRODUCT, articles=ARTICLES, batches=BATCHES,
                           to_unit="g", reference_quantity=500.0)

    by_id = {a.article_id: a for a in plan.articles}
    assert by_id[10].factor == 500.0
    assert by_id[10].used_reference is False


def test_an_article_with_no_weight_falls_back_to_the_reference():
    """Refusing the whole conversion would freeze 239 products in pieces
    forever. The confirmation screen says which ones fell back."""
    plan = plan_conversion(product=PRODUCT, articles=ARTICLES, batches=BATCHES,
                           to_unit="g", reference_quantity=400.0)

    by_id = {a.article_id: a for a in plan.articles}
    assert by_id[11].factor == 400.0
    assert by_id[11].used_reference is True
    assert plan.articles_using_reference == (11,)


def test_batch_quantities_are_multiplied_by_their_article_s_weight():
    plan = plan_conversion(product=PRODUCT, articles=ARTICLES, batches=BATCHES,
                           to_unit="g", reference_quantity=400.0)

    by_id = {b.batch_id: b for b in plan.batches}
    assert by_id[100].new_remaining == pytest.approx(1000.0)
    assert by_id[100].new_initial == pytest.approx(1500.0)
    assert by_id[101].new_remaining == pytest.approx(400.0)


def test_two_movements_per_batch_because_the_journal_is_append_only():
    plan = plan_conversion(product=PRODUCT, articles=ARTICLES, batches=BATCHES,
                           to_unit="g", reference_quantity=500.0)
    assert plan.movements == 4


def test_a_product_already_in_grams_has_nothing_to_convert():
    with pytest.raises(ConversionError, match="already"):
        plan_conversion(product={"id": 1, "name": "Pâtes", "base_unit": "g"},
                        articles=ARTICLES, batches=BATCHES,
                        to_unit="g", reference_quantity=500.0)


def test_the_target_unit_must_be_a_real_base_unit():
    with pytest.raises(ConversionError, match="target"):
        plan_conversion(product=PRODUCT, articles=ARTICLES, batches=BATCHES,
                        to_unit="paquet", reference_quantity=500.0)


def test_converting_to_pieces_is_refused():
    with pytest.raises(ConversionError, match="target"):
        plan_conversion(product=PRODUCT, articles=ARTICLES, batches=BATCHES,
                        to_unit="piece", reference_quantity=500.0)


@pytest.mark.parametrize("reference", [0.0, -5.0, 0.1, 80_000.0])
def test_an_implausible_reference_weight_is_refused(reference):
    with pytest.raises(ConversionError, match="reference"):
        plan_conversion(product=PRODUCT, articles=ARTICLES, batches=BATCHES,
                        to_unit="g", reference_quantity=reference)


def test_a_product_with_no_batches_still_converts_its_articles():
    plan = plan_conversion(product=PRODUCT, articles=ARTICLES, batches=[],
                           to_unit="g", reference_quantity=500.0)
    assert plan.batches == ()
    assert plan.movements == 0
    assert len(plan.articles) == 2


def test_an_implausible_article_weight_is_treated_as_missing():
    articles = [{"id": 12, "product_id": 1, "net_quantity": 80_000.0}]
    plan = plan_conversion(product=PRODUCT, articles=articles, batches=[],
                           to_unit="g", reference_quantity=500.0)

    assert plan.articles[0].factor == 500.0
    assert plan.articles[0].used_reference is True


def test_a_batch_referring_to_an_unknown_article_is_refused_not_crashed():
    """The journal can go stale — a batch may outlive its article row. The
    caller only catches ConversionError, so a bare KeyError would crash
    unhandled instead of showing an error on the confirmation screen."""
    stale_batches = [{"id": 101, "article_id": 42, "remaining": 1.0, "initial": 1.0}]
    with pytest.raises(ConversionError, match="batch 101"):
        plan_conversion(product=PRODUCT, articles=ARTICLES, batches=stale_batches,
                        to_unit="g", reference_quantity=500.0)


def test_a_product_already_in_millilitres_has_nothing_to_convert():
    with pytest.raises(ConversionError, match="already"):
        plan_conversion(product={"id": 1, "name": "Huile", "base_unit": "ml"},
                        articles=ARTICLES, batches=BATCHES,
                        to_unit="g", reference_quantity=500.0)


def test_a_missing_reference_weight_is_refused():
    with pytest.raises(ConversionError, match="reference"):
        plan_conversion(product=PRODUCT, articles=ARTICLES, batches=BATCHES,
                        to_unit="g", reference_quantity=None)


def test_a_reference_weight_given_as_a_string_is_refused():
    with pytest.raises(ConversionError, match="reference"):
        plan_conversion(product=PRODUCT, articles=ARTICLES, batches=BATCHES,
                        to_unit="g", reference_quantity="500")


@pytest.mark.parametrize("reference", [True, False])
def test_a_boolean_reference_weight_is_refused(reference):
    """bool is an int subclass in Python: without an explicit exclusion,
    True/False would silently pass the range check as 1.0/0.0."""
    with pytest.raises(ConversionError, match="reference"):
        plan_conversion(product=PRODUCT, articles=ARTICLES, batches=BATCHES,
                        to_unit="g", reference_quantity=reference)
