"""Delete a product or an article: refuse, erase, or hide.

The rules, once, for both surfaces (websocket and services):

- Open stock or an upcoming use BLOCKS: nothing is written, and the refusal
  names every blocker.
- An element that never served is ERASED, with what only describes it
  (articles, barcodes, packagings, prices, ingredient aliases).
- Anything else is HIDDEN (`active = 0`): its history, the movement journal
  first, stays exactly as it was. Hiding a product never writes its articles'
  `active`, so restoring the product brings them back as they were.

Every decision is taken inside the one write transaction that acts on it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from .messages import delete_blocked_message, slot_label
from .storage import deletion as store
from .storage import repositories as repo
from .storage.database import Database

OUTCOME_DELETED: Final = "deleted"
OUTCOME_HIDDEN: Final = "hidden"


@dataclass(frozen=True)
class Blocker:
    """One reason a delete is refused, e.g. two open batches in the fridge."""

    kind: str
    count: int
    names: tuple[str, ...]


class DeleteBlocked(Exception):
    """The delete was refused; `str(err)` is the French sentence to show."""

    def __init__(self, blockers: tuple[Blocker, ...]) -> None:
        super().__init__(delete_blocked_message(blockers))
        self.blockers = blockers


def _blocker(kind: str, rows: list[dict]) -> Blocker:
    if kind == "planned_meals":
        names = [f"{r['day']} ({slot_label(r['slot_key'])})" for r in rows]
    else:
        names = [r["name"] for r in rows if r.get("name")]
    # Several batches in one place name that place once.
    return Blocker(kind=kind, count=len(rows), names=tuple(dict.fromkeys(names)))


def product_blockers(conn, product_id: int) -> tuple[Blocker, ...]:
    return tuple(_blocker(k, rows) for k, rows in store.product_blocking_rows(conn, product_id))


def article_blockers(conn, article_id: int) -> tuple[Blocker, ...]:
    return tuple(_blocker(k, rows) for k, rows in store.article_blocking_rows(conn, article_id))


def product_never_served(conn, product_id: int) -> bool:
    return not store.product_has_history(conn, product_id)


def article_never_served(conn, article_id: int) -> bool:
    return not store.article_has_history(conn, article_id)


def delete_product(db: Database, product_id: int) -> str:
    """Erase or hide a product. Raises LookupError, DeleteBlocked."""
    with db.write() as conn:
        product = repo.get_product(conn, product_id)
        if product is None:
            raise LookupError(f"no product {product_id}")
        if not product["active"]:
            return OUTCOME_HIDDEN
        blockers = product_blockers(conn, product_id)
        if blockers:
            raise DeleteBlocked(blockers)
        if product_never_served(conn, product_id):
            store.erase_product(conn, product_id)
            return OUTCOME_DELETED
        store.set_product_active(conn, product_id, False)
        return OUTCOME_HIDDEN


def delete_article(db: Database, article_id: int) -> str:
    """Erase or hide an article. Raises LookupError, DeleteBlocked."""
    with db.write() as conn:
        article = repo.get_article(conn, article_id)
        if article is None:
            raise LookupError(f"no article {article_id}")
        if not article["active"]:
            return OUTCOME_HIDDEN
        blockers = article_blockers(conn, article_id)
        if blockers:
            raise DeleteBlocked(blockers)
        if article_never_served(conn, article_id):
            store.erase_article(conn, article_id)
            return OUTCOME_DELETED
        store.set_article_active(conn, article_id, False)
        return OUTCOME_HIDDEN


def set_article_active_within(conn, article_id: int, active: bool) -> None:
    """Hide or restore an article inside an open transaction. Restoring an
    article of a hidden product restores the product too: an article nobody
    can see through its product is not restored."""
    article = repo.get_article(conn, article_id)
    if article is None:
        raise LookupError(f"no article {article_id}")
    store.set_article_active(conn, article_id, active)
    if active:
        store.set_product_active(conn, article["product_id"], True)


def set_article_active(db: Database, article_id: int, active: bool) -> None:
    with db.write() as conn:
        set_article_active_within(conn, article_id, active)
