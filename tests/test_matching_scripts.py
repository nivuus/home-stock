"""Ingredient matching and search keep every script's letters.

Latin diacritics fold (a search convention of Latin-script languages); no
other script loses a letter or a meaningful mark, an empty key is never
stored nor looked up, and a search term in any script filters.
"""
import sqlite3

import pytest

from custom_components.home_stock.application import (
    StockManager,
    resolve_ingredient_match,
)
from custom_components.home_stock.domain.matching import normalise
from custom_components.home_stock.domain.search import fold_for_search
from custom_components.home_stock.storage import repositories as repo
from custom_components.home_stock.storage.database import Database
from custom_components.home_stock.storage.migrations import apply_migrations

MOMENT = "2026-11-14T12:00:00"


@pytest.fixture
def manager(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.connect()
    with db.write() as conn:
        apply_migrations(conn)
    yield StockManager(db)
    db.close()


# --- the pure folding ---------------------------------------------------------

@pytest.mark.parametrize("left, right", [
    ("молоко", "сыр"),          # Russian: milk, cheese
    ("牛肉", "猪肉"),             # Chinese: beef, pork
    ("حليب", "جبن"),            # Arabic: milk, cheese
    ("חלב", "גבינה"),           # Hebrew: milk, cheese
    ("か", "が"),                # Japanese: a voiced mark is a different kana
    ("दाल", "दल"),              # Hindi: a vowel sign is a letter
    ("ใหม่", "ไหม"),             # Thai: a tone mark changes the word
])
def test_distinct_words_stay_distinct(left, right):
    assert normalise(left), left
    assert normalise(right), right
    assert normalise(left) != normalise(right)


@pytest.mark.parametrize("text", ["молоко", "牛肉", "حليب", "חלב", "łosoś", "Ωμέγα"])
def test_non_ascii_letters_survive(text):
    assert normalise(text)
    assert fold_for_search(text).strip()


@pytest.mark.parametrize("left, right", [
    ("pâtes", "pates"), ("Crème Fraîche", "creme fraiche"), ("Œufs", "oeuf"),
    ("STRASSE", "straße"),
])
def test_latin_accents_case_and_plurals_still_fold(left, right):
    assert normalise(left) == normalise(right)


@pytest.mark.parametrize("text, letter", [("łosoś", "ł"), ("smør", "ø")])
def test_latin_letters_without_decomposition_are_kept(text, letter):
    assert letter in normalise(text)


def test_a_cyrillic_word_ending_like_a_plural_is_not_trimmed():
    assert normalise("квас") == "квас"


def test_search_folding_keeps_meaningful_marks():
    assert fold_for_search("Pâté") == "pate"
    assert fold_for_search("й") != fold_for_search("и")
    assert fold_for_search("が") != fold_for_search("か")


# --- aliases ------------------------------------------------------------------

def _line(conn, raw_text):
    recipe_id = repo.insert_recipe(conn, name="R", source="manual", created_at=MOMENT)
    return repo.insert_ingredient(conn, recipe_id=recipe_id, position=1,
                                  raw_text=raw_text)


def test_two_cyrillic_aliases_stay_apart(manager):
    with manager.db.write() as conn:
        milk = repo.insert_product(conn, name="Молоко", base_unit="ml")
        cheese = repo.insert_product(conn, name="Сыр", base_unit="g")
        first = _line(conn, "молоко")
        second = _line(conn, "сыр")
    manager.match_ingredient(first, product_id=milk, state="confirmed", create_alias=True)
    manager.match_ingredient(second, product_id=cheese, state="confirmed",
                             create_alias=True)
    with manager.db.write() as conn:
        products = repo.list_products(conn)
        assert resolve_ingredient_match(
            conn, raw_text="молоко", ingredient_name=None, products=products)[:2] == (
                "confirmed", milk)
        assert resolve_ingredient_match(
            conn, raw_text="сыр", ingredient_name=None, products=products)[:2] == (
                "confirmed", cheese)
        keys = [r[0] for r in conn.execute("SELECT normalised FROM ingredient_alias")]
    assert "" not in keys and len(keys) == 2


def test_an_empty_key_is_never_stored_nor_matched(manager):
    with manager.db.write() as conn:
        product = repo.insert_product(conn, name="Sel", base_unit="g")
        punctuation = _line(conn, "— ! —")
        other = _line(conn, "…")
    manager.match_ingredient(punctuation, product_id=product, state="confirmed",
                             create_alias=True)
    with manager.db.write() as conn:
        assert conn.execute("SELECT COUNT(*) FROM ingredient_alias").fetchone()[0] == 0
        with pytest.raises(ValueError):
            repo.upsert_alias(conn, normalised="", product_id=product,
                              created_at=MOMENT)
        assert repo.find_alias(conn, "") is None
        state, _, _, _ = resolve_ingredient_match(
            conn, raw_text="…", ingredient_name=None,
            products=repo.list_products(conn))
    assert state != "confirmed"
    assert other


def test_a_non_latin_search_term_filters_recipes(manager):
    manager.create_recipe(name="Борщ")
    manager.create_recipe(name="Pâtes au beurre")
    assert [r["name"] for r in manager.list_recipes(search="борщ")] == ["Борщ"]
    assert [r["name"] for r in manager.list_recipes(search="pates")] == [
        "Pâtes au beurre"]
    # Nothing searchable in the term: no filter, said explicitly.
    assert len(manager.list_recipes(search="…")) == 2


# --- existing rows --------------------------------------------------------------

def test_the_migration_drops_the_empty_alias_and_refolds_names(tmp_path):
    from custom_components.home_stock.storage import migrations

    path = str(tmp_path / "old.db")
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    previous = [m for m in migrations.MIGRATIONS if m.VERSION <= 10]
    for migration in previous:
        conn.executescript(migration.SQL)
        if hasattr(migration, "apply"):
            migration.apply(conn)
    conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
    conn.execute("DELETE FROM schema_version")
    conn.execute("INSERT INTO schema_version VALUES (10)")
    product = conn.execute(
        "INSERT INTO product (name, base_unit, name_fold) VALUES ('Борщ', 'g', '')"
    ).lastrowid
    conn.execute("INSERT INTO ingredient_alias (normalised, product_id, created_at)"
                 " VALUES ('', ?, ?)", (product, MOMENT))
    conn.execute("INSERT INTO ingredient_alias (normalised, product_id, created_at)"
                 " VALUES ('creme fraiche', ?, ?)", (product, MOMENT))
    # Taught from a mixed line: the old folding kept only its Latin word.
    _line(conn, "Сыр fromage")
    conn.execute("INSERT INTO ingredient_alias (normalised, product_id, created_at)"
                 " VALUES ('fromage', ?, ?)", (product, MOMENT))
    conn.commit()

    apply_migrations(conn)
    keys = sorted(r[0] for r in conn.execute("SELECT normalised FROM ingredient_alias"))
    assert keys == ["creme fraiche", "сыр fromage"]
    fold = conn.execute("SELECT name_fold FROM product WHERE id = ?",
                        (product,)).fetchone()[0]
    assert fold == "борщ"
    conn.close()
