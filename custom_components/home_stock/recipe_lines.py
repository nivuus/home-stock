"""Edit one ingredient line of an existing recipe, take it out, or put one back.

Until now a line could only be re-matched (`home_stock/recipe/ingredient/match`):
changing how much of a product a recipe uses, or dropping a line, meant
deleting the recipe and writing it again — steps, servings and every other
line included. These two gestures touch ONE `recipe_ingredient` row and
nothing else.

The quantity given is in the product's base unit (g, ml, piece). `amount` is
the only number a line stores, and it means a count of packagings when the
line has a `packaging_id`, a count of measures when it has a `measure_id`,
and a base quantity otherwise (`domain.recipes.base_amount`). So writing a
base quantity clears both references — otherwise "50" would be read as fifty
packagings. `raw_text` is provenance ("320 g krisprolls", as imported) and is
never rewritten: it says where the line came from, not what it asks for.

No other table references `recipe_ingredient`, and no stored figure is
derived from it: the dish kcal of a meal preview and the next-meal sensor
read the lines when they are asked, so the caller only has to refresh the
coordinator after a write.

The validator lives here, once, and both surfaces (websocket and service)
use it: a bound that exists on one side only is a back door on the other.
"""
from __future__ import annotations

from typing import Any, Final

import voluptuous as vol

from .const import MAX_LIST_QUANTITY
from .validators import finite_float, preview

# The same ceiling as a shopping-list line: 100 kg or 100 l of one product.
MAX_INGREDIENT_QUANTITY: Final = MAX_LIST_QUANTITY


def ingredient_quantity(value: Any) -> float:
    """A line quantity in base unit: `]0 ; MAX_INGREDIENT_QUANTITY]`.

    Zero is refused: a line that asks for nothing is a line to remove, and
    there is a gesture for that.
    """
    number = finite_float(value)
    if number <= 0:
        raise vol.Invalid(f"quantity must be positive, got {preview(value)}")
    if number > MAX_INGREDIENT_QUANTITY:
        raise vol.Invalid(
            f"quantity must not exceed {MAX_INGREDIENT_QUANTITY:g}, got {preview(value)}")
    return number


def _line_of(conn: Any, ingredient_id: int, recipe_id: int | None) -> dict[str, Any]:
    """The line, or the English refusal `messages.py` translates."""
    row = conn.execute(
        "SELECT * FROM recipe_ingredient WHERE id = ?", (ingredient_id,)).fetchone()
    if row is None:
        raise ValueError(f"unknown ingredient line {ingredient_id}")
    if recipe_id is not None and row["recipe_id"] != recipe_id:
        raise ValueError(
            f"ingredient line {ingredient_id} is not in recipe {recipe_id}")
    return dict(row)


def designated_line(db: Any, data: dict[str, Any]) -> int:
    """The line a gesture names: by `ingredient_id`, or by the readable name
    of its product within a recipe (`recipe_id` + `product`), like
    `todo.update_item` takes an item's name or its UID.

    The name is matched without regard to case against the line's product,
    then — for an unmatched line such as "eau" — against its imported text.
    Two lines answering to one name are refused: the id then decides.
    `ingredient_id` wins when both are given.
    """
    if data.get("ingredient_id") is not None:
        return int(data["ingredient_id"])
    recipe_id, product = data.get("recipe_id"), (data.get("product") or "").strip()
    if recipe_id is None or not product:
        raise ValueError("line not designated")
    conn = db.read()
    if conn.execute("SELECT 1 FROM recipe WHERE id = ?", (recipe_id,)).fetchone() is None:
        raise ValueError(f"unknown recipe {recipe_id}")
    rows = conn.execute(
        """
        SELECT ri.id, p.name AS product, ri.raw_text
        FROM recipe_ingredient ri LEFT JOIN product p ON p.id = ri.product_id
        WHERE ri.recipe_id = ?
        """, (recipe_id,)).fetchall()
    wanted = product.casefold()
    matches = [row["id"] for row in rows
               if (row["product"] or "").strip().casefold() == wanted]
    if not matches:
        matches = [row["id"] for row in rows
                   if (row["raw_text"] or "").strip().casefold() == wanted]
    if not matches:
        raise ValueError(f"no line named <{product}> in recipe {recipe_id}")
    if len(matches) > 1:
        raise ValueError(
            f"{len(matches)} lines named <{product}> in recipe {recipe_id}")
    return int(matches[0])


def set_ingredient_quantity(db: Any, ingredient_id: int, quantity: float, *,
                            recipe_id: int | None = None) -> dict[str, Any]:
    """Write `quantity` (base unit) on one line. Returns the updated line."""
    try:
        amount = ingredient_quantity(quantity)
    except vol.Invalid as err:
        # The schemas check it first; a direct caller gets the domain's own
        # exception type, which both surfaces translate.
        raise ValueError(str(err)) from err
    with db.write() as conn:
        _line_of(conn, ingredient_id, recipe_id)
        conn.execute(
            "UPDATE recipe_ingredient SET amount = ?, packaging_id = NULL,"
            " measure_id = NULL WHERE id = ?", (amount, ingredient_id))
        return _line_of(conn, ingredient_id, None)


def remove_ingredient(db: Any, ingredient_id: int, *,
                      recipe_id: int | None = None) -> dict[str, Any]:
    """Delete one line. Returns the line as it was, so the caller can say what went.

    The other lines keep their `position`: the gap left is harmless (only
    `UNIQUE(recipe_id, position)` binds it) and renumbering would rewrite
    rows nobody asked to touch.
    """
    with db.write() as conn:
        line = _line_of(conn, ingredient_id, recipe_id)
        conn.execute("DELETE FROM recipe_ingredient WHERE id = ?", (ingredient_id,))
        return line


def _product_named(conn: Any, name: str) -> int:
    """The one product called `name`, without regard to case."""
    wanted = name.casefold()
    ids = [row["id"] for row in conn.execute("SELECT id, name FROM product")
           if row["name"].strip().casefold() == wanted]
    if not ids:
        raise ValueError(f"unknown product <{name}>")
    if len(ids) > 1:
        raise ValueError(f"{len(ids)} products named <{name}>")
    return int(ids[0])


def add_ingredient(db: Any, recipe_id: int, *, product: str | None = None,
                   quantity: Any = None, raw_text: str | None = None,
                   position: int | None = None) -> dict[str, Any]:
    """Put one line (back) into a recipe. Returns the new line.

    The undo of `remove_ingredient`: Maxime asked for it before the first
    removal ever shipped. A line names an existing product (matched like
    `designated_line`, without regard to case) with an optional quantity in
    its base unit, or is only a text such as "eau", which is then `ignored`
    by the preview, as an imported line with no product is. `position`
    puts it back where it was (the gap a removal leaves); without it the
    line goes last. Nothing else in the recipe is touched.
    """
    name, text = (product or "").strip(), (raw_text or "").strip()
    if not name and not text:
        raise ValueError("line not described")
    if quantity is not None and not name:
        raise ValueError("quantity without product")
    amount = None
    if quantity is not None:
        try:
            amount = ingredient_quantity(quantity)
        except vol.Invalid as err:
            raise ValueError(str(err)) from err
    with db.write() as conn:
        if conn.execute("SELECT 1 FROM recipe WHERE id = ?", (recipe_id,)).fetchone() is None:
            raise ValueError(f"unknown recipe {recipe_id}")
        product_id = _product_named(conn, name) if name else None
        if position is None:
            position = conn.execute(
                "SELECT COALESCE(MAX(position), 0) + 1 FROM recipe_ingredient"
                " WHERE recipe_id = ?", (recipe_id,)).fetchone()[0]
        elif conn.execute("SELECT 1 FROM recipe_ingredient WHERE recipe_id = ?"
                          " AND position = ?", (recipe_id, position)).fetchone():
            raise ValueError(f"position {position} taken in recipe {recipe_id}")
        cursor = conn.execute(
            "INSERT INTO recipe_ingredient (recipe_id, position, raw_text,"
            " product_id, amount, match_state) VALUES (?, ?, ?, ?, ?, ?)",
            (recipe_id, position, text or name, product_id, amount,
             "confirmed" if product_id else "ignored"))
        return _line_of(conn, int(cursor.lastrowid), None)


def list_lines(db: Any, recipe_id: int) -> list[dict[str, Any]]:
    """Every line of a recipe with the id the two gestures above take.

    Read-only. Without it the `ingredient_id` a service asks for could only
    be found through the websocket `recipe/get`, out of reach of a script or
    an automation. `unit` is what `amount` counts: the packaging or the
    measure when the line has one, the product's base unit otherwise.
    """
    conn = db.read()
    if conn.execute("SELECT 1 FROM recipe WHERE id = ?", (recipe_id,)).fetchone() is None:
        raise ValueError(f"unknown recipe {recipe_id}")
    rows = conn.execute(
        """
        SELECT ri.id AS ingredient_id, ri.position, ri.product_id,
               p.name AS product, ri.amount,
               COALESCE(pk.name, cm.name, p.base_unit) AS unit,
               ri.raw_text, ri.match_state
        FROM recipe_ingredient ri
        LEFT JOIN product p ON p.id = ri.product_id
        LEFT JOIN packaging pk ON pk.id = ri.packaging_id
        LEFT JOIN culinary_measure cm ON cm.id = ri.measure_id
        WHERE ri.recipe_id = ?
        ORDER BY ri.position
        """, (recipe_id,)).fetchall()
    return [dict(row) for row in rows]
