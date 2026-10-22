"""`repositories.list_products(search=...)`: the catalogue filtered by name.

The filter runs in SQL, on a real migrated SQLite file: `product.name_fold`
holds the name folded once at write time (m010), the searched word is folded
the same way, and LIKE compares the two. So case, accents and the œ/æ
ligatures never decide whether a product is found, and a `%` or `_` typed by
the user is a character, not a wildcard.

No Python function is registered on the connection, on purpose: the reader
connection is shared bare between executor threads, and a Python function
called back from inside a SQLite step is the one thing that deadlocks such a
connection (thread A holds the SQLite mutex and waits for the GIL, thread B
holds the GIL and waits for the mutex). That froze Home Assistant whole on
2026-10-22. The last test replays that scenario in a subprocess.
"""
from __future__ import annotations

import sqlite3
import subprocess
import sys
import textwrap
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from custom_components.home_stock.domain.search import (
    escape_like,
    fold_for_search,
    like_pattern,
)
from custom_components.home_stock.storage import repositories as repo
from custom_components.home_stock.storage.database import Database
from custom_components.home_stock.storage.migrations import apply_migrations

VISIBLE = (
    "Carotte", "CAROTTES râpées", "Purée de carottes", "Carrot cake",
    "Pâtes", "pates complètes", "Œufs frais", "Crème brûlée",
    "Sauce 100% tomate", "Sauce 1000 tomates", "Thé_vert", "Thé vert",
)
HIDDEN = "Carotte violette"
CARROTS = ["CAROTTES râpées", "Carotte", "Purée de carottes"]


@pytest.fixture
def db(tmp_path: Path) -> Iterator[Database]:
    database = Database(str(tmp_path / "t.db"))
    database.connect()
    with database.write() as conn:
        apply_migrations(conn)
        for name in VISIBLE:
            repo.insert_product(conn, name=name, base_unit="g")
        repo.insert_product(conn, name=HIDDEN, base_unit="g", active=0)
    yield database
    database.close()


def _names(rows: list[dict[str, Any]]) -> list[str]:
    return [row["name"] for row in rows]


def _search(db: Database, search: str | None, **kwargs: Any) -> list[str]:
    return _names(repo.list_products(db.read(), search=search, **kwargs))


# --- the folding and the pattern, pure -------------------------------------

@pytest.mark.parametrize(("text", "folded"), [
    ("Carotte", "carotte"),
    ("CAROTTES râpées", "carottes rapees"),
    ("Œufs frais", "oeufs frais"),
    ("Crème Brûlée", "creme brulee"),
    ("PÂTES", "pates"),
])
def test_fold_ignores_case_accents_and_ligatures(text: str, folded: str) -> None:
    assert fold_for_search(text) == folded


def test_escape_like_makes_wildcards_and_the_escape_literal() -> None:
    assert escape_like("dinner_1") == "dinner\\_1"
    assert escape_like("100%") == "100\\%"
    assert escape_like("a\\b") == "a\\\\b"
    assert escape_like("plain") == "plain"


def test_like_pattern_is_folded_trimmed_and_escaped() -> None:
    assert like_pattern("  PÂTE ") == "%pate%"
    assert like_pattern("100%") == "%100\\%%"
    assert like_pattern("thé_v") == "%the\\_v%"
    assert like_pattern("a\\b") == "%a\\\\b%"


@pytest.mark.parametrize("blank", [None, "", "   "])
def test_like_pattern_of_nothing_is_none(blank: str | None) -> None:
    assert like_pattern(blank) is None


# --- list_products, unchanged without a search -----------------------------

@pytest.mark.parametrize("blank", [None, "", "  "])
def test_without_search_the_list_is_the_old_one(db: Database, blank: str | None) -> None:
    conn = db.read()
    old = [dict(row) for row in conn.execute(
        "SELECT * FROM product WHERE active = 1 ORDER BY name")]
    assert repo.list_products(conn, search=blank) == old
    assert repo.list_products(conn) == old
    assert len(old) == len(VISIBLE)


def test_without_search_include_hidden_still_lists_everything(db: Database) -> None:
    assert len(_search(db, None, active_only=False)) == len(VISIBLE) + 1


# --- list_products, filtered -----------------------------------------------

@pytest.mark.parametrize("word", ["carotte", "CAROTTE", "Carotté", " carotte "])
def test_search_finds_every_carrot_whatever_the_case_and_accents(
        db: Database, word: str) -> None:
    assert _search(db, word) == CARROTS


@pytest.mark.parametrize("word", ["pâte", "PÂTE", "pate", "Pates"])
def test_search_ignores_accents_on_both_sides(db: Database, word: str) -> None:
    assert _search(db, word) == ["Pâtes", "pates complètes"]


@pytest.mark.parametrize("word", ["oeuf", "œuf", "ŒUFS"])
def test_search_expands_ligatures(db: Database, word: str) -> None:
    assert _search(db, word) == ["Œufs frais"]


def test_percent_is_searched_literally(db: Database) -> None:
    assert _search(db, "100%") == ["Sauce 100% tomate"]


def test_underscore_is_searched_literally(db: Database) -> None:
    assert _search(db, "thé_v") == ["Thé_vert"]


def test_search_with_no_match_is_an_empty_list(db: Database) -> None:
    assert _search(db, "rutabaga") == []


def test_search_keeps_hidden_products_out_unless_asked(db: Database) -> None:
    assert HIDDEN not in _search(db, "carotte")
    assert _search(db, "carotte", active_only=False) == [
        "CAROTTES râpées", "Carotte", HIDDEN, "Purée de carottes"]


def test_filtered_rows_are_whole_product_rows(db: Database) -> None:
    every = {row["name"]: row for row in repo.list_products(db.read())}
    for row in repo.list_products(db.read(), search="carotte"):
        assert row == every[row["name"]]


def test_search_works_on_the_writer_connection_too(db: Database) -> None:
    with db.write() as conn:
        assert _names(repo.list_products(conn, search="carotte")) == CARROTS


def test_search_works_on_a_bare_connection(tmp_path: Path, db: Database) -> None:
    """A connection nobody prepared searches too: nothing to register on it."""
    conn = sqlite3.connect(str(tmp_path / "t.db"))
    conn.row_factory = sqlite3.Row
    try:
        assert _names(repo.list_products(conn, search="CAROTTE")) == CARROTS
        assert _names(repo.list_products(conn, search="pâte")) == ["Pâtes", "pates complètes"]
    finally:
        conn.close()


# --- the folded name is a column, not a function ---------------------------

def test_insert_product_stores_the_folded_name(db: Database) -> None:
    rows = db.read().execute(
        "SELECT name, name_fold FROM product ORDER BY name").fetchall()
    assert len(rows) == len(VISIBLE) + 1
    for row in rows:
        assert row["name_fold"] == fold_for_search(row["name"])


def test_update_product_fields_with_a_name_refolds_it(db: Database) -> None:
    with db.write() as conn:
        row_id = conn.execute(
            "SELECT id FROM product WHERE name = 'Carotte'").fetchone()["id"]
        repo.update_product_fields(conn, row_id, {"name": "Épinards HACHÉS"})
    row = db.read().execute(
        "SELECT name, name_fold FROM product WHERE id = ?", (row_id,)).fetchone()
    assert (row["name"], row["name_fold"]) == ("Épinards HACHÉS", "epinards haches")
    assert _search(db, "epinard") == ["Épinards HACHÉS"]


def test_search_registers_no_python_function_on_the_connection(db: Database) -> None:
    conn = db.read()
    _names(repo.list_products(conn, search="carotte"))
    with pytest.raises(sqlite3.OperationalError, match="no such function"):
        conn.execute("SELECT home_stock_fold('x')")


def test_concurrent_searches_on_the_shared_reader_finish(tmp_path: Path, db: Database) -> None:
    """Several executor threads searching through the one reader connection.

    This is the production shape (`Database.read()` hands the same connection
    to every thread). Run in a subprocess: a deadlock here takes the GIL with
    it, so an in-process version could never time out, it would hang pytest.
    """
    script = textwrap.dedent(f"""
        import threading
        from custom_components.home_stock.storage import repositories as repo
        from custom_components.home_stock.storage.database import Database

        db = Database({str(tmp_path / "t.db")!r})
        db.connect()
        conn = db.read()

        def search():
            for word in ("carotte", "pâte", "oeuf", "thé") * 50:
                repo.list_products(conn, search=word)

        threads = [threading.Thread(target=search) for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        print("searches finished")
    """)
    root = Path(__file__).resolve().parents[2]
    try:
        done = subprocess.run([sys.executable, "-c", script], cwd=root, timeout=60,
                              capture_output=True, text=True)
    except subprocess.TimeoutExpired:
        pytest.fail("concurrent searches never finished: the reader connection deadlocked")
    assert done.returncode == 0, done.stderr
    assert "searches finished" in done.stdout
