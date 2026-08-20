"""The aggregates that sensors and the panel read."""
import pytest

from custom_components.home_stock.storage import repositories as repo
from custom_components.home_stock.storage.database import Database
from custom_components.home_stock.storage.migrations import apply_migrations

DAY = ("2026-08-20T02:00:00", "2026-08-21T02:00:00")


@pytest.fixture
def journal_conn(tmp_path):
    """A migrated database with one product, one article and nothing else:
    these tests write their movements by hand to control exactly the
    timestamps, reasons and parts.
    """
    db = Database(str(tmp_path / "home_stock.db"))
    db.connect()
    with db.write() as conn:
        apply_migrations(conn)
    with db.write() as conn:
        conn.execute("INSERT INTO location (name, kind) VALUES ('Placard', 'cupboard')")
        conn.execute("INSERT INTO product (name, base_unit) VALUES ('Yaourt', 'g')")
        conn.execute("INSERT INTO article (product_id) VALUES (1)")
    with db.write() as conn:
        yield conn
    db.close()


def _movement(conn, **kwargs):
    defaults = dict(occurred_at="2026-08-20T10:00:00", product_id=1, article_id=1,
                    quantity=-200.0, reason="consumption", base_unit="g")
    return repo.insert_movement(conn, **{**defaults, **kwargs})


def test_a_share_of_one_quarter_is_not_swallowed_by_integer_division(journal_conn):
    """The trap of this batch: in SQLite, 1/4 on two INTEGERs is 0."""
    _movement(journal_conn, kcal=480.0, parts_total=4, parts_mine=1)
    totals = repo.totals_between(journal_conn, *DAY)
    assert totals["kcal"] == pytest.approx(120.0)


def test_null_parts_count_as_the_whole_thing(journal_conn):
    _movement(journal_conn, kcal=240.0)
    assert repo.totals_between(journal_conn, *DAY)["kcal"] == pytest.approx(240.0)


def test_zero_parts_mine_contributes_nothing(journal_conn):
    _movement(journal_conn, kcal=480.0, parts_total=4, parts_mine=0)
    assert repo.totals_between(journal_conn, *DAY)["kcal"] == 0.0


def test_waste_never_reaches_the_calories(journal_conn):
    _movement(journal_conn, kcal=500.0, cost=1.5, reason="waste")
    _movement(journal_conn, kcal=300.0, cost=0.9, reason="expired")
    _movement(journal_conn, kcal=240.0, cost=0.8, reason="consumption")
    totals = repo.totals_between(journal_conn, *DAY)
    assert totals["kcal"] == pytest.approx(240.0)
    assert totals["cost"] == pytest.approx(0.8)
    assert totals["waste_cost"] == pytest.approx(2.4)


def test_money_is_never_divided_by_the_parts(journal_conn):
    """The spec's explicit rule: the pack cost what it cost."""
    _movement(journal_conn, kcal=480.0, cost=2.0, parts_total=4, parts_mine=1)
    totals = repo.totals_between(journal_conn, *DAY)
    assert totals["cost"] == pytest.approx(2.0)
    assert totals["kcal"] == pytest.approx(120.0)


def test_a_purchase_is_never_counted(journal_conn):
    _movement(journal_conn, kcal=1000.0, cost=5.0, reason="purchase", quantity=800.0)
    totals = repo.totals_between(journal_conn, *DAY)
    assert totals["kcal"] == 0.0 and totals["cost"] == 0.0 and totals["waste_cost"] == 0.0


def test_conversion_inventory_and_transfer_are_never_counted(journal_conn):
    """A purchase is excluded by the reason filter itself, as the test above
    proves by pricing it and still seeing it excluded. Conversion, inventory
    and transfer are, in today's application code, always written with
    kcal=None and cost=None (application.py's convert_product_unit,
    adjust_inventory, transfer_batch), so the filter's protection of these
    three reasons is never actually exercised by the application's own
    writes. A movement written here by hand, with non-null kcal and cost,
    is what proves the SQL filter really does exclude them, independently
    of that upstream discipline — and keeps proving it the day a future
    version of one of these three starts valuing its movements."""
    _movement(journal_conn, kcal=1000.0, cost=5.0, reason="conversion")
    _movement(journal_conn, kcal=700.0, cost=3.0, reason="inventory")
    _movement(journal_conn, kcal=400.0, cost=2.0, reason="transfer")
    totals = repo.totals_between(journal_conn, *DAY)
    assert totals["kcal"] == 0.0 and totals["cost"] == 0.0 and totals["waste_cost"] == 0.0


def test_the_eight_macros_are_aggregated_too(journal_conn):
    _movement(journal_conn, kcal=480.0, parts_total=2, parts_mine=1,
              macros={"proteins": 20.0, "salt": 1.0})
    totals = repo.totals_between(journal_conn, *DAY)
    assert totals["proteins"] == pytest.approx(10.0)
    assert totals["salt"] == pytest.approx(0.5)
    assert totals["fiber"] == 0.0        # nothing measured: the sum is empty


def test_unvalued_counts_the_consumptions_without_calories(journal_conn):
    _movement(journal_conn, kcal=240.0)
    _movement(journal_conn, kcal=None)
    _movement(journal_conn, kcal=None, reason="waste")     # not a consumption
    assert repo.totals_between(journal_conn, *DAY)["unvalued"] == 1


def test_bounds_are_half_open(journal_conn):
    _movement(journal_conn, occurred_at="2026-08-20T02:00:00", kcal=10.0)   # included
    _movement(journal_conn, occurred_at="2026-08-21T02:00:00", kcal=99.0)   # excluded
    _movement(journal_conn, occurred_at="2026-08-20T01:59:59", kcal=99.0)   # excluded
    assert repo.totals_between(journal_conn, *DAY)["kcal"] == pytest.approx(10.0)


def test_without_bounds_the_totals_are_cumulative(journal_conn):
    _movement(journal_conn, occurred_at="2024-01-01T10:00:00", kcal=100.0)
    _movement(journal_conn, occurred_at="2026-08-20T10:00:00", kcal=240.0)
    assert repo.totals_between(journal_conn)["kcal"] == pytest.approx(340.0)


def test_journal_entries_carry_what_the_panel_shows(journal_conn):
    _movement(journal_conn, occurred_at="2026-08-20T12:00:00", kcal=240.0,
              parts_total=2, parts_mine=1)
    _movement(journal_conn, occurred_at="2026-08-20T09:00:00", kcal=100.0)
    entries = repo.journal_entries(journal_conn, *DAY)
    assert [e["occurred_at"] for e in entries] == [
        "2026-08-20T09:00:00", "2026-08-20T12:00:00"]
    assert entries[0]["product_name"] == "Yaourt"
    assert entries[1]["parts_mine"] == 1
    assert entries[0]["base_unit"] == "g"


def test_journal_entries_show_what_was_thrown_away_too(journal_conn):
    _movement(journal_conn, reason="waste", kcal=500.0)
    _movement(journal_conn, reason="purchase", quantity=800.0)
    reasons = [e["reason"] for e in repo.journal_entries(journal_conn, *DAY)]
    assert reasons == ["waste"]


def test_learned_portion_is_the_median_of_the_last_three(journal_conn):
    for quantity in (-100.0, -300.0, -150.0, -140.0, -160.0):
        _movement(journal_conn, quantity=quantity)
    # The last THREE are 150, 140, 160: median 150.
    assert repo.learned_portion(journal_conn, 1) == pytest.approx(150.0)


def test_learned_portion_needs_three_consumptions(journal_conn):
    _movement(journal_conn, quantity=-100.0)
    _movement(journal_conn, quantity=-120.0)
    assert repo.learned_portion(journal_conn, 1) is None


def test_learned_portion_ignores_waste_and_purchases(journal_conn):
    _movement(journal_conn, quantity=-100.0)
    _movement(journal_conn, quantity=-100.0)
    _movement(journal_conn, quantity=-999.0, reason="waste")
    _movement(journal_conn, quantity=800.0, reason="purchase")
    assert repo.learned_portion(journal_conn, 1) is None


def test_counted_movements_reports_the_raw_rows_for_a_series(journal_conn):
    _movement(journal_conn, occurred_at="2026-08-19T10:00:00", kcal=100.0)
    _movement(journal_conn, occurred_at="2026-08-20T10:00:00", kcal=240.0,
              parts_total=2, parts_mine=1)
    _movement(journal_conn, occurred_at="2026-08-20T11:00:00", reason="purchase",
              quantity=800.0, cost=5.0)
    rows = repo.counted_movements(journal_conn, "2026-08-19T02:00:00")
    assert len(rows) == 2
    assert rows[0]["occurred_at"] == "2026-08-19T10:00:00"
    assert rows[1]["parts_total"] == 2
