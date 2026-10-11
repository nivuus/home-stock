"""Correcting a product's unit and kcal (`product_correction.correct_product`).

On a real, freshly migrated database; nothing is mocked except, in the one
transaction test, a write made to fail. The "Feta" fixture is the case that
asked for this service: a product counted in pieces (528 kcal a piece), its
article at 496.8 kcal a piece, one batch typed in grams ("80", meaning 80 g)
and one older batch that really is in pieces.
"""
import sqlite3

import pytest

from custom_components.home_stock.application import StockManager
from custom_components.home_stock.product_correction import (
    CorrectionRefused,
    CorrectionRequest,
    correct_product,
    parse_request,
)
from custom_components.home_stock.storage import repositories as repo
from custom_components.home_stock.storage.database import Database
from custom_components.home_stock.storage.migrations import apply_migrations

NOW = "2026-10-11T08:00:00"


def _seed(conn) -> None:
    conn.execute("INSERT INTO location (id, name, kind) VALUES (1, 'Frigo', 'fridge')")
    conn.execute(
        "INSERT INTO product (id, name, base_unit, min_quantity, reference_kcal) "
        "VALUES (97, 'Feta brebis', 'piece', 0, 528)")
    conn.execute(
        "INSERT INTO article (id, product_id, label, net_quantity, kcal_per_base_unit, "
        "is_generic) VALUES (97, 97, 'Féta Bio', 200, 496.8, 0)")
    for batch_id, quantity, price in ((87, 0.7, 2.40), (194, 80.0, 0.012)):
        conn.execute(
            "INSERT INTO batch (id, article_id, location_id, remaining, initial, entered_at,"
            " price_per_base_unit) VALUES (?, 97, 1, ?, ?, '2026-09-29T08:53:02', ?)",
            (batch_id, quantity, quantity, price))
    conn.execute("INSERT INTO product (id, name, base_unit) VALUES (5, 'Yaourt', 'piece')")
    conn.execute("INSERT INTO article (id, product_id, label, is_generic) "
                 "VALUES (50, 5, 'Yaourt nature', 0)")
    conn.execute("INSERT INTO batch (id, article_id, location_id, remaining, initial,"
                 " entered_at) VALUES (300, 50, 1, 4, 4, '2026-10-01T10:00:00')")


def _manager(path) -> StockManager:
    database = Database(str(path))
    database.connect()
    with database.write() as conn:
        apply_migrations(conn)
        _seed(conn)
    return StockManager(database)


@pytest.fixture
def manager(tmp_path) -> StockManager:
    return _manager(tmp_path / "home_stock.db")


def _correct(manager, **fields):
    return correct_product(manager, parse_request({"product_id": 97, **fields}),
                           occurred_at=NOW)


def _product(manager, product_id=97):
    return repo.get_product(manager.db.read(), product_id)


def _batch(manager, batch_id):
    return manager.db.read().execute(
        "SELECT remaining, initial, price_per_base_unit FROM batch WHERE id = ?",
        (batch_id,)).fetchone()


def _snapshot(manager):
    """Every row a correction may write, so 'nothing written' can be asserted."""
    conn = manager.db.read()
    return {table: [tuple(row) for row in conn.execute(f"SELECT * FROM {table} ORDER BY id")]
            for table in ("product", "article", "batch", "movement", "packaging", "price")}


# --- reading the request -----------------------------------------------------

@pytest.mark.parametrize(("data", "said"), [
    ({}, "Rien à corriger"),
    ({"reference_kcal": -1}, "reference_kcal"),
    ({"reference_kcal": "beaucoup"}, "reference_kcal"),
    ({"reference_kcal": True}, "reference_kcal"),
    ({"target_unit": "kg", "reference_quantity": 200}, "« g » ou « ml »"),
    ({"target_unit": "g"}, "reference_quantity"),
    ({"reference_quantity": 200}, "target_unit"),
    ({"reference_kcal": 2, "unchanged_batches": [194]}, "target_unit"),
    ({"target_unit": "g", "reference_quantity": "lourd"}, "Un nombre est attendu"),
    ({"target_unit": "g", "reference_quantity": 200, "unchanged_batches": ["lot"]},
     "Un nombre entier est attendu"),
    ({"target_unit": "g", "reference_quantity": 200, "unchanged_batches": {"a": 1}},
     "liste"),
])
def test_a_request_that_cannot_be_read_is_refused_in_french(data, said):
    with pytest.raises(CorrectionRefused) as refused:
        parse_request({"product_id": 97, **data})
    assert said in str(refused.value)


def test_a_request_is_read_with_the_panel_validator_for_kcal():
    request = parse_request({"product_id": 97, "reference_kcal": "2.65", "target_unit": "g",
                             "reference_quantity": 200, "unchanged_batches": [194, 194]})
    assert request == CorrectionRequest(
        product_id=97, kcal_given=True, reference_kcal=2.65, target_unit="g",
        reference_quantity=200.0, unchanged_batches=(194,), dry_run=False)
    # null clears the value, exactly as home_stock/product/update allows.
    assert parse_request({"product_id": 97, "reference_kcal": None}).kcal_given is True
    # one batch id alone is read as a list of one.
    assert parse_request({"product_id": 97, "target_unit": "g", "reference_quantity": 200,
                          "unchanged_batches": 194}).unchanged_batches == (194,)


# --- kcal alone --------------------------------------------------------------

def test_kcal_alone_is_written_and_nothing_else_moves(manager):
    before = _snapshot(manager)

    answer = _correct(manager, reference_kcal=600)

    assert _product(manager)["reference_kcal"] == 600
    assert _product(manager)["base_unit"] == "piece"
    after = _snapshot(manager)
    assert {k: v for k, v in after.items() if k != "product"} == \
        {k: v for k, v in before.items() if k != "product"}
    assert answer["applied"] is True
    assert answer["conversion"] is None
    assert answer["reference_kcal"] == {"before": 528, "after": 600}


def test_kcal_alone_shows_which_rate_each_batch_really_uses(manager):
    """The article's own 496.8 wins over the product's reference_kcal: the
    answer says so batch by batch, so a correction that cannot change what a
    meal counts is visible before anyone relies on it."""
    answer = _correct(manager, reference_kcal=600, dry_run=True)

    rates = {line["batch_id"]: (line["kcal_per_base_unit_before"],
                                line["kcal_per_base_unit_after"])
             for line in answer["batches_plan"]}
    assert rates == {87: (496.8, 496.8), 194: (496.8, 496.8)}


def test_an_unknown_product_is_refused_and_nothing_is_written(manager):
    before = _snapshot(manager)
    with pytest.raises(CorrectionRefused, match="Produit 404 inconnu"):
        correct_product(manager, parse_request({"product_id": 404, "reference_kcal": 1}),
                        occurred_at=NOW)
    assert _snapshot(manager) == before


# --- the unit ----------------------------------------------------------------

def test_a_dry_run_writes_nothing_and_answers_the_plan_batch_by_batch(manager):
    before = _snapshot(manager)

    answer = _correct(manager, target_unit="g", reference_quantity=200,
                      unchanged_batches=[194], reference_kcal=2.65, dry_run=True)

    assert _snapshot(manager) == before
    assert answer["applied"] is False
    assert answer["conversion"]["applied"] is False
    assert answer["base_unit"] == {"before": "piece", "after": "g"}
    assert answer["reference_kcal"] == {"before": 528, "after": 2.65}
    plan = {line["batch_id"]: line for line in answer["batches_plan"]}
    assert (plan[194]["remaining_before"], plan[194]["remaining_after"]) == (80, 80)
    assert plan[194]["unchanged"] is True
    assert plan[87]["remaining_after"] == pytest.approx(140)
    assert plan[87]["unchanged"] is False
    assert plan[194]["kcal_per_base_unit_after"] == pytest.approx(2.484)
    [article] = answer["articles_plan"]
    assert article["factor"] == 200
    assert article["kcal_per_base_unit_after"] == pytest.approx(2.484)


def test_the_feta_ends_in_grams_with_its_gram_batch_untouched(manager):
    _correct(manager, target_unit="g", reference_quantity=200, unchanged_batches=[194],
             reference_kcal=2.65)

    product = _product(manager)
    assert product["base_unit"] == "g"
    assert product["reference_kcal"] == pytest.approx(2.65)
    kept = _batch(manager, 194)
    assert (kept["remaining"], kept["initial"]) == (80, 80)
    assert kept["price_per_base_unit"] == pytest.approx(0.012)
    converted = _batch(manager, 87)
    assert converted["remaining"] == pytest.approx(140)
    assert converted["price_per_base_unit"] == pytest.approx(0.012)
    article = repo.get_article(manager.db.read(), 97)
    assert article["kcal_per_base_unit"] == pytest.approx(2.484)
    # 40 g of feta now count about a hundred kcal, not 19 872.
    assert manager.consume(product_id=97, quantity=40)
    kcal = manager.db.read().execute(
        "SELECT TOTAL(kcal) FROM movement WHERE reason = 'consumption'").fetchone()[0]
    assert kcal == pytest.approx(40 * 2.484)


def test_a_kept_batch_still_leaves_both_conversion_movements(manager):
    _correct(manager, target_unit="g", reference_quantity=200, unchanged_batches=[194])

    rows = manager.db.read().execute(
        "SELECT quantity, base_unit FROM movement WHERE reason = 'conversion'"
        " AND batch_id = 194 ORDER BY id").fetchall()
    assert [tuple(row) for row in rows] == [(-80.0, "piece"), (80.0, "g")]


@pytest.mark.parametrize("batch_id", [300, 9999])
def test_a_kept_batch_that_is_not_an_open_batch_of_the_product_is_refused(manager,
                                                                          batch_id):
    before = _snapshot(manager)
    with pytest.raises(CorrectionRefused, match=f"{batch_id}.*produit 97"):
        _correct(manager, target_unit="g", reference_quantity=200,
                 unchanged_batches=[batch_id], reference_kcal=2.65)
    assert _snapshot(manager) == before


def test_the_conversion_is_the_panels_own(manager, tmp_path):
    """Same inputs, two surfaces, the same rows and the same report."""
    panel = _manager(tmp_path / "panel.db")

    report = panel.convert_product_unit(product_id=97, to_unit="g", reference_quantity=200)
    answer = _correct(manager, target_unit="g", reference_quantity=200)

    # `already_converted: False` is what product/convert_unit adds to that report.
    assert answer["conversion"] == {**report, "already_converted": False}
    service_rows, panel_rows = _snapshot(manager), _snapshot(panel)
    for rows in (service_rows, panel_rows):
        # the moment of the conversion is the only thing the two runs cannot share
        rows["movement"] = [row[:1] + row[2:] for row in rows["movement"]]
    assert service_rows == panel_rows


def test_a_given_kcal_is_read_in_the_new_unit_and_wins_over_the_recomputed_one(manager):
    answer = _correct(manager, target_unit="g", reference_quantity=200, reference_kcal=2.65)

    assert _product(manager)["reference_kcal"] == pytest.approx(2.65)   # not 528 / 200
    assert answer["reference_kcal"]["after"] == pytest.approx(2.65)


def test_without_a_kcal_the_conversion_recomputes_it_like_the_panel(manager):
    answer = _correct(manager, target_unit="g", reference_quantity=200)
    assert _product(manager)["reference_kcal"] == pytest.approx(2.64)
    assert answer["reference_kcal"] == {"before": 528, "after": pytest.approx(2.64)}


def test_a_refused_conversion_does_not_write_the_kcal_either(manager):
    before = _snapshot(manager)
    with pytest.raises(CorrectionRefused, match="poids de référence"):
        _correct(manager, target_unit="g", reference_quantity=0.1, reference_kcal=2.65)
    assert _snapshot(manager) == before


def test_pending_shopping_refuses_the_conversion_in_french(manager):
    with manager.db.write() as conn:
        session_id = repo.open_session(conn, started_at="2026-10-11T07:00:00", store=None)
        repo.add_line(conn, session_id=session_id, article_id=97, quantity=1,
                      unit_price=None, scanned_at="2026-10-11T07:05:00", idempotency_key=None)
    before = _snapshot(manager)
    with pytest.raises(CorrectionRefused, match="courses en attente"):
        _correct(manager, target_unit="g", reference_quantity=200, reference_kcal=2.65)
    assert _snapshot(manager) == before


def test_a_product_already_in_the_unit_is_reported_like_the_panel_does(manager):
    _correct(manager, target_unit="g", reference_quantity=200)

    answer = _correct(manager, target_unit="g", reference_quantity=200, reference_kcal=2.7)

    assert answer["conversion"]["already_converted"] is True
    assert answer["conversion"]["applied"] is False
    assert _product(manager)["reference_kcal"] == pytest.approx(2.7)


def test_the_conversion_and_the_kcal_are_one_transaction(manager, monkeypatch):
    original = repo.update_product_fields

    def refuse_the_kcal_write(conn, product_id, fields):
        if set(fields) == {"reference_kcal"}:
            raise sqlite3.OperationalError("disk is on fire")
        original(conn, product_id, fields)

    monkeypatch.setattr(repo, "update_product_fields", refuse_the_kcal_write)
    before = _snapshot(manager)

    with pytest.raises(sqlite3.OperationalError):
        _correct(manager, target_unit="g", reference_quantity=200, reference_kcal=2.65)

    monkeypatch.setattr(repo, "update_product_fields", original)
    assert _snapshot(manager) == before
