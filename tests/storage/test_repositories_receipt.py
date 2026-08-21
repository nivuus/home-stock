"""Le ticket au niveau du dépôt : la photo, ce qu'on en a lu, l'état."""
import sqlite3

import pytest

from custom_components.home_stock.storage import repositories as repo
from custom_components.home_stock.storage.migrations import apply_migrations


@pytest.fixture
def conn() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    apply_migrations(connection)
    connection.execute("INSERT INTO location (id, name, kind) VALUES (1, 'Placard', 'pantry')")
    connection.execute(
        "INSERT INTO product (id, name, base_unit) VALUES (1, 'Lait', 'ml')")
    connection.execute(
        "INSERT INTO article (id, product_id, label, net_quantity)"
        " VALUES (1, 1, 'Lait demi-écrémé 1 L', 1000)")
    return connection


def _receipt(conn, **fields):
    fields.setdefault("media_content_id", "media-source://media_source/local/t.jpg")
    fields.setdefault("captured_at", "2026-08-21T20:00:00")
    return repo.insert_receipt(conn, **fields)


def test_a_receipt_starts_pending(conn):
    receipt_id = _receipt(conn)
    row = repo.get_receipt(conn, receipt_id)
    assert row["state"] == "pending"
    assert row["attempts"] == 0
    assert row["lines"] == []


def test_the_state_moves_and_keeps_the_photo(conn):
    receipt_id = _receipt(conn)
    repo.set_receipt_state(conn, receipt_id, "failed",
                           error="Le modèle n'a pas répondu.", attempts=1)
    row = repo.get_receipt(conn, receipt_id)
    assert row["state"] == "failed"
    assert row["error"] == "Le modèle n'a pas répondu."
    assert row["attempts"] == 1
    assert row["media_content_id"].endswith("t.jpg")


def test_replacing_the_lines_starts_from_scratch(conn):
    """Une relecture remplace ce qu'on avait lu : garder les deux ferait une
    liste où la moitié des lignes vient d'une lecture ratée."""
    receipt_id = _receipt(conn)
    repo.replace_receipt_lines(conn, receipt_id, [
        {"position": 1, "label": "LT DEMI", "quantity": 1, "unit_price": 1.05,
         "total_price": 1.05},
        {"position": 2, "label": "PAIN", "quantity": 1, "unit_price": 1.30,
         "total_price": 1.30},
    ])
    repo.replace_receipt_lines(conn, receipt_id, [
        {"position": 1, "label": "LT DEMI ECR 1L", "quantity": 1,
         "unit_price": 1.05, "total_price": 1.05},
    ])
    lines = repo.get_receipt(conn, receipt_id)["lines"]
    assert [line["label"] for line in lines] == ["LT DEMI ECR 1L"]
    assert lines[0]["match_state"] == "unmatched"


def test_a_matched_line_remembers_its_cart_line(conn):
    receipt_id = _receipt(conn)
    session_id = repo.open_session(conn, started_at="2026-08-21T19:00:00", store=None)
    line_id = repo.add_line(conn, session_id=session_id, article_id=1, quantity=1000,
                            unit_price=0.001, scanned_at="2026-08-21T19:05:00",
                            idempotency_key=None)
    repo.replace_receipt_lines(conn, receipt_id, [
        {"position": 1, "label": "LT DEMI", "quantity": 1, "unit_price": 1.05,
         "total_price": 1.05}])
    receipt_line_id = repo.get_receipt(conn, receipt_id)["lines"][0]["id"]

    repo.set_receipt_line_match(conn, receipt_line_id, line_id=line_id,
                                state="confirmed")

    line = repo.get_receipt(conn, receipt_id)["lines"][0]
    assert line["line_id"] == line_id
    assert line["match_state"] == "confirmed"


def test_ignoring_a_line_clears_its_cart_line(conn):
    receipt_id = _receipt(conn)
    repo.replace_receipt_lines(conn, receipt_id, [
        {"position": 1, "label": "SAC", "quantity": 1, "unit_price": 0.1,
         "total_price": 0.1}])
    receipt_line_id = repo.get_receipt(conn, receipt_id)["lines"][0]["id"]
    repo.set_receipt_line_match(conn, receipt_line_id, line_id=None, state="ignored")
    line = repo.get_receipt(conn, receipt_id)["lines"][0]
    assert line["line_id"] is None and line["match_state"] == "ignored"


def test_pending_receipts_are_the_ones_still_owed_an_answer(conn):
    first = _receipt(conn)
    second = _receipt(conn)
    third = _receipt(conn)
    repo.set_receipt_state(conn, second, "failed", error="Délai dépassé.")
    repo.set_receipt_state(conn, third, "applied")

    pending = repo.pending_receipts(conn)

    assert {row["id"] for row in pending} == {first, second}
    assert repo.list_receipts(conn, states=("applied",))[0]["id"] == third
    assert len(repo.list_receipts(conn)) == 3


def test_marking_a_line_applied_is_what_makes_a_second_pass_a_no_op(conn):
    receipt_id = _receipt(conn)
    repo.replace_receipt_lines(conn, receipt_id, [
        {"position": 1, "label": "LT DEMI", "quantity": 1, "unit_price": 1.05,
         "total_price": 1.05}])
    receipt_line_id = repo.get_receipt(conn, receipt_id)["lines"][0]["id"]
    repo.mark_receipt_line_applied(conn, receipt_line_id, at="2026-08-21T21:00:00")
    assert repo.get_receipt(conn, receipt_id)["lines"][0]["applied_at"] == \
        "2026-08-21T21:00:00"


def test_no_query_of_the_receipt_aliases_a_table_as_b(conn):
    """Le test qui interdit de sélectionner une ligne de lot entière scanne
    ce paquet LITTÉRALEMENT : un alias `b` sur `receipt` le ferait tomber
    sans aucun rapport avec `batch`."""
    import re
    from pathlib import Path

    source = Path(repo.__file__).read_text(encoding="utf-8")
    # `b` seul, pas `br` : la frontière de mot est tout l'objet du test.
    assert re.search(r"FROM receipt(_line)? b\b", source) is None
    assert "FROM receipt br" in source and "FROM receipt_line rl" in source
