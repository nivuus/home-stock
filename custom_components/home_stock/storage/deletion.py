"""SQL for deleting a product or an article: what blocks it, whether it ever
served, and the erase itself.

Kept apart from `repositories.py`, which is already far past this project's
line limit. No function here touches `movement`: the journal is append-only,
and an element that has a movement is never erased, only hidden.
"""
from __future__ import annotations

import sqlite3
from typing import Any

# Each query returns one row per blocking thing, with the name a person would
# recognise it by (NULL when it has none worth showing).
_PRODUCT_BLOCKERS: tuple[tuple[str, str], ...] = (
    ("open_batches", """
        SELECT l.name AS name FROM batch b
        JOIN article a ON a.id = b.article_id
        JOIN location l ON l.id = b.location_id
        WHERE a.product_id = :id AND b.closed_at IS NULL ORDER BY b.id"""),
    ("active_recipes", """
        SELECT DISTINCT r.id, r.name AS name FROM recipe_ingredient ri
        JOIN recipe r ON r.id = ri.recipe_id
        WHERE ri.product_id = :id AND r.active = 1 ORDER BY r.name, r.id"""),
    ("planned_meals", """
        SELECT m.day, m.slot_key FROM meal m
        WHERE m.product_id = :id AND m.state = 'planned'
        ORDER BY m.day, m.position, m.id"""),
    ("shopping_items", """
        SELECT NULL AS name FROM shopping_list_item
        WHERE product_id = :id AND checked_at IS NULL AND removed_at IS NULL"""),
    ("recurring", """
        SELECT NULL AS name FROM shopping_recurring
        WHERE product_id = :id AND active = 1"""),
    ("equipment", """
        SELECT DISTINCT e.id, e.name AS name FROM equipment_consumable c
        JOIN equipment e ON e.id = c.equipment_id
        WHERE c.product_id = :id ORDER BY e.name, e.id"""),
    ("battery", """
        SELECT label AS name FROM battery WHERE product_id = :id ORDER BY label, id"""),
    ("leftover", """
        SELECT name FROM recipe WHERE leftover_product_id = :id AND active = 1
        ORDER BY name, id"""),
    # Same rule as for one article: in the cart now, stock on it tomorrow.
    ("shopping_session", """
        SELECT NULL AS name FROM shopping_line sl
        JOIN article a ON a.id = sl.article_id
        JOIN shopping_session s ON s.id = sl.session_id
        WHERE a.product_id = :id AND s.state <> 'done'"""),
)

_ARTICLE_BLOCKERS: tuple[tuple[str, str], ...] = (
    ("open_batches", """
        SELECT l.name AS name FROM batch b
        JOIN location l ON l.id = b.location_id
        WHERE b.article_id = :id AND b.closed_at IS NULL ORDER BY b.id"""),
    ("shopping_session", """
        SELECT NULL AS name FROM shopping_line sl
        JOIN shopping_session s ON s.id = sl.session_id
        WHERE sl.article_id = :id AND s.state <> 'done'"""),
)

# Anything that ever referenced the element. One hit and it is history: it is
# hidden, never erased. Closed batches, inactive recipes, done meals and
# removed list items all count — only "never touched" is an error to erase.
_ARTICLE_HISTORY = """
    SELECT EXISTS (SELECT 1 FROM batch WHERE article_id = :id)
        OR EXISTS (SELECT 1 FROM movement WHERE article_id = :id)
        OR EXISTS (SELECT 1 FROM shopping_line WHERE article_id = :id)
        OR EXISTS (SELECT 1 FROM receipt_line WHERE article_id = :id)
        OR EXISTS (SELECT 1 FROM recipe_ingredient ri JOIN packaging pk
                   ON pk.id = ri.packaging_id
                   WHERE pk.scope = 'article' AND pk.target_id = :id)
        OR EXISTS (SELECT 1 FROM meal m JOIN packaging pk ON pk.id = m.packaging_id
                   WHERE pk.scope = 'article' AND pk.target_id = :id)
"""

_PRODUCT_HISTORY = """
    SELECT EXISTS (SELECT 1 FROM movement WHERE product_id = :id)
        OR EXISTS (SELECT 1 FROM recipe_ingredient WHERE product_id = :id)
        OR EXISTS (SELECT 1 FROM recipe WHERE leftover_product_id = :id)
        OR EXISTS (SELECT 1 FROM meal WHERE product_id = :id)
        OR EXISTS (SELECT 1 FROM shopping_list_item WHERE product_id = :id)
        OR EXISTS (SELECT 1 FROM shopping_recurring WHERE product_id = :id)
        OR EXISTS (SELECT 1 FROM equipment_consumable WHERE product_id = :id)
        OR EXISTS (SELECT 1 FROM battery WHERE product_id = :id)
        OR EXISTS (SELECT 1 FROM recipe_ingredient ri JOIN packaging pk
                   ON pk.id = ri.packaging_id
                   WHERE pk.scope = 'product' AND pk.target_id = :id)
        OR EXISTS (SELECT 1 FROM meal m JOIN packaging pk ON pk.id = m.packaging_id
                   WHERE pk.scope = 'product' AND pk.target_id = :id)
"""


def _blocking_rows(conn: sqlite3.Connection, queries, element_id: int
                   ) -> list[tuple[str, list[dict[str, Any]]]]:
    found = []
    for kind, sql in queries:
        rows = [dict(r) for r in conn.execute(sql, {"id": element_id}).fetchall()]
        if rows:
            found.append((kind, rows))
    return found


def product_blocking_rows(conn, product_id: int):
    """(kind, rows) for every blocker of this product, in a fixed order."""
    return _blocking_rows(conn, _PRODUCT_BLOCKERS, product_id)


def article_blocking_rows(conn, article_id: int):
    """(kind, rows) for every blocker of this article, in a fixed order."""
    return _blocking_rows(conn, _ARTICLE_BLOCKERS, article_id)


def article_ids(conn, product_id: int) -> list[int]:
    return [r["id"] for r in conn.execute(
        "SELECT id FROM article WHERE product_id = ? ORDER BY id", (product_id,))]


def article_has_history(conn, article_id: int) -> bool:
    return bool(conn.execute(_ARTICLE_HISTORY, {"id": article_id}).fetchone()[0])


def product_has_history(conn, product_id: int) -> bool:
    if conn.execute(_PRODUCT_HISTORY, {"id": product_id}).fetchone()[0]:
        return True
    return any(article_has_history(conn, a) for a in article_ids(conn, product_id))


def erase_article(conn, article_id: int) -> None:
    """Erase an article that never served, with what only describes it."""
    conn.execute("DELETE FROM barcode WHERE article_id = ?", (article_id,))
    conn.execute("DELETE FROM packaging WHERE scope = 'article' AND target_id = ?",
                 (article_id,))
    conn.execute("DELETE FROM price WHERE article_id = ?", (article_id,))
    conn.execute("DELETE FROM article WHERE id = ?", (article_id,))


def erase_product(conn, product_id: int) -> None:
    """Erase a product that never served: aliases, articles, packagings."""
    conn.execute("DELETE FROM ingredient_alias WHERE product_id = ?", (product_id,))
    for article_id in article_ids(conn, product_id):
        erase_article(conn, article_id)
    conn.execute("DELETE FROM packaging WHERE scope = 'product' AND target_id = ?",
                 (product_id,))
    conn.execute("DELETE FROM product WHERE id = ?", (product_id,))


def hidden_product_named(conn, name: str) -> bool:
    """Whether the product holding this name is a hidden one: creating a
    namesake then collides with a product no list shows."""
    row = conn.execute("SELECT active FROM product WHERE name = ?",
                       (name.strip(),)).fetchone()
    return row is not None and not row["active"]


def set_product_active(conn, product_id: int, active: bool) -> None:
    conn.execute("UPDATE product SET active = ? WHERE id = ?",
                 (1 if active else 0, product_id))


def set_article_active(conn, article_id: int, active: bool) -> None:
    conn.execute("UPDATE article SET active = ? WHERE id = ?",
                 (1 if active else 0, article_id))
