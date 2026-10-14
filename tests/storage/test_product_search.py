"""`repositories.list_products(search=...)`: the catalogue filtered by name.

The filter runs in SQL, on a real migrated SQLite file: the name is folded by
the integration's own folding function (registered on the connection), the
searched word is folded the same way, and LIKE compares the two. So case,
accents and the œ/æ ligatures never decide whether a product is found, and a
`%` or `_` typed by the user is a character, not a wildcard.
"""
from __future__ import annotations

import sqlite3
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
from custom_components.home_stock.storage.product_search import FOLD_FUNCTION

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
    """A connection nobody prepared gets the folding function on first use."""
    conn = sqlite3.connect(str(tmp_path / "t.db"))
    conn.row_factory = sqlite3.Row
    try:
        assert _names(repo.list_products(conn, search="CAROTTE")) == CARROTS
        assert _names(repo.list_products(conn, search="pâte")) == ["Pâtes", "pates complètes"]
        folded = conn.execute(f"SELECT {FOLD_FUNCTION}('Œufs Brûlés')").fetchone()[0]
        assert folded == "oeufs brules"
    finally:
        conn.close()
