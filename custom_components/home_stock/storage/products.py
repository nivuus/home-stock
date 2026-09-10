"""Product creation with a stable, barcode-independent identifier.

Kept out of `repositories.py` on purpose: that module is already over this
project's line limit, and everything here can be built on its public
functions (`insert_product`, `get_product`, `list_products`, `list_aisles`,
`insert_article`, `link_barcode`, `find_article_by_barcode`,
`first_barcode_for_product`) with only that last, small helper added there.

A product's real primary key is still the SQLite integer of the `product`
table (see `repositories.insert_product`); `format_product_id` only dresses
it so it can never be mistaken for a barcode (an EAN is all digits, a
product_id always starts with a letter), and so a caller comparing the two
never has to know which table they came from.
"""
from __future__ import annotations

import sqlite3
from typing import Any, Final

from ..const import BASE_UNITS
from . import repositories as repo

PRODUCT_ID_PREFIX: Final = "hs_"
DEFAULT_BASE_UNIT: Final = "piece"


class ProductError(ValueError):
    """Base class for every validation error `create_product` can raise."""


class EmptyName(ProductError):
    def __init__(self) -> None:
        super().__init__("product name is empty")


class DuplicateName(ProductError):
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"product name already used: {name}")


class DuplicateBarcode(ProductError):
    def __init__(self, barcode: str) -> None:
        self.barcode = barcode
        super().__init__(f"barcode already used: {barcode}")


class InvalidRayon(ProductError):
    def __init__(self, value: str, allowed: list[str]) -> None:
        self.value = value
        self.allowed = allowed
        super().__init__(f"unknown rayon: {value}")


class InvalidUnit(ProductError):
    def __init__(self, value: str, allowed: list[str]) -> None:
        self.value = value
        self.allowed = allowed
        super().__init__(f"unknown unit: {value}")


def format_product_id(row_id: int) -> str:
    """The `product.id` integer, dressed so it reads as a product_id."""
    return f"{PRODUCT_ID_PREFIX}{row_id}"


def new_product_id(row_id: int) -> str:
    """Alias of `format_product_id`, named after the plan's declared
    interface: this store hands out an id for an already-inserted row
    rather than minting one ahead of the insert (the row's own integer
    primary key is what makes the id stable across a restart)."""
    return format_product_id(row_id)


def parse_product_id(product_id: str) -> int | None:
    """The reverse of `format_product_id`; `None` on anything unparseable
    rather than an exception, so a caller can treat an unknown id as "not
    found" instead of catching a ValueError."""
    if not product_id.startswith(PRODUCT_ID_PREFIX):
        return None
    try:
        return int(product_id[len(PRODUCT_ID_PREFIX):])
    except ValueError:
        return None


def _aisle_id_by_name(conn, name: str) -> int:
    aisles = repo.list_aisles(conn)
    for aisle in aisles:
        if aisle["name"] == name:
            return aisle["id"]
    raise InvalidRayon(name, [aisle["name"] for aisle in aisles])


def _dress(row: dict[str, Any], aisle_names: dict[int, str], barcode: str | None) -> dict[str, Any]:
    """A raw `product` row, plus `product_id`, `unit`, `rayon` and
    `barcode` (`None` when the product has none) -- the shape every
    function in this module returns."""
    dressed = dict(row)
    dressed["product_id"] = format_product_id(row["id"])
    dressed["unit"] = row["base_unit"]
    dressed["rayon"] = aisle_names.get(row["aisle_id"])
    dressed["barcode"] = barcode
    return dressed


def _dress_one(conn, row: dict[str, Any]) -> dict[str, Any]:
    aisle_names = {aisle["id"]: aisle["name"] for aisle in repo.list_aisles(conn)}
    barcode = repo.first_barcode_for_product(conn, row["id"])
    return _dress(row, aisle_names, barcode)


def create_product(conn, *, name: str, rayon: str, unit: str | None = None,
                    barcode: str | None = None) -> dict[str, Any]:
    """Create a product, with or without a barcode.

    Every field is validated before anything is written: on any error, no
    row is inserted (R9). `unit` blank or absent falls back to
    `DEFAULT_BASE_UNIT`; `barcode` blank is treated as absent. A repeated
    name is rejected (`DuplicateName`): the spec's non-goal only waives
    duplicate/merge *detection* of a same-named product created on purpose
    by a resolver, not the database's own `product.name` UNIQUE constraint.
    """
    clean_name = name.strip()
    if not clean_name:
        raise EmptyName()

    clean_rayon = rayon.strip()
    aisle_id = _aisle_id_by_name(conn, clean_rayon)

    clean_unit = (unit or "").strip() or DEFAULT_BASE_UNIT
    if clean_unit not in BASE_UNITS:
        raise InvalidUnit(clean_unit, list(BASE_UNITS))

    clean_barcode = (barcode or "").strip() or None
    if clean_barcode is not None and repo.find_article_by_barcode(conn, clean_barcode):
        raise DuplicateBarcode(clean_barcode)

    try:
        row_id = repo.insert_product(conn, name=clean_name, base_unit=clean_unit,
                                     aisle_id=aisle_id)
    except sqlite3.IntegrityError as exc:
        raise DuplicateName(clean_name) from exc

    if clean_barcode is not None:
        article_id = repo.insert_article(conn, product_id=row_id)
        repo.link_barcode(conn, clean_barcode, article_id)

    product = get_product(conn, format_product_id(row_id))
    assert product is not None  # just inserted, cannot be missing
    return product


def get_product(conn, product_id: str) -> dict[str, Any] | None:
    row_id = parse_product_id(product_id)
    if row_id is None:
        return None
    row = repo.get_product(conn, row_id)
    return _dress_one(conn, row) if row else None


def find_by_barcode(conn, barcode: str) -> dict[str, Any] | None:
    article = repo.find_article_by_barcode(conn, barcode)
    if not article:
        return None
    row = repo.get_product(conn, article["product_id"])
    return _dress_one(conn, row) if row else None


def list_products(conn, active_only: bool = True) -> list[dict[str, Any]]:
    """Every product, dressed -- with or without a barcode (R10)."""
    aisle_names = {aisle["id"]: aisle["name"] for aisle in repo.list_aisles(conn)}
    return [
        _dress(row, aisle_names, repo.first_barcode_for_product(conn, row["id"]))
        for row in repo.list_products(conn, active_only=active_only)
    ]
