"""The application layer: composes the domain rules with the repositories.

Everything here is synchronous. Home Assistant calls it from the executor.
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from .const import (
    REASON_CONSUMPTION,
    REASON_INVENTORY,
    REASON_PURCHASE,
    REASON_TRANSFER,
)
from .domain.nutrition import movement_values
from .domain.stock import BatchView, allocate
from .domain.units import format_quantity, to_base_quantity
from .storage import repositories as repo
from .storage.database import Database


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0, tzinfo=None).isoformat()


def _as_batch_view(row: dict[str, Any]) -> BatchView:
    return BatchView(
        id=row["id"],
        remaining=row["remaining"],
        best_before=date.fromisoformat(row["best_before"]) if row["best_before"] else None,
        entered_at=datetime.fromisoformat(row["entered_at"]),
        opened_at=datetime.fromisoformat(row["opened_at"]) if row["opened_at"] else None,
        price_per_base_unit=row["price_per_base_unit"],
        kcal_per_base_unit=row["kcal_per_base_unit"],
    )


class StockManager:
    """Every write to the stock goes through here."""

    def __init__(self, db: Database) -> None:
        self.db = db

    # --- writes -------------------------------------------------------------

    def add_stock(self, *, article_id: int, quantity: float, location_id: int,
                  best_before: str | None = None,
                  price_per_base_unit: float | None = None,
                  packaging_base_quantity: float | None = None,
                  occurred_at: str | None = None,
                  idempotency_key: str | None = None) -> int:
        """Create a batch and its purchase movement. Returns the batch id."""
        moment = occurred_at or _now()
        amount = to_base_quantity(quantity, packaging_base_quantity)
        with self.db.write() as conn:
            if idempotency_key and repo.movement_exists(conn, idempotency_key):
                row = conn.execute(
                    "SELECT batch_id FROM movement WHERE idempotency_key = ?",
                    (idempotency_key,),
                ).fetchone()
                return int(row["batch_id"])
            article = repo.get_article(conn, article_id)
            if article is None:
                raise ValueError(f"unknown article {article_id}")
            batch_id = repo.insert_batch(
                conn, article_id=article_id, location_id=location_id, quantity=amount,
                entered_at=moment, best_before=best_before,
                price_per_base_unit=price_per_base_unit,
            )
            values = movement_values(amount, article["kcal_per_base_unit"],
                                     price_per_base_unit)
            repo.insert_movement(
                conn, occurred_at=moment, product_id=article["product_id"],
                article_id=article_id, batch_id=batch_id, quantity=amount,
                reason=REASON_PURCHASE, kcal=values.kcal, cost=values.cost,
                idempotency_key=idempotency_key,
            )
            if price_per_base_unit is not None:
                repo.insert_price(
                    conn, article_id=article_id, observed_on=moment[:10],
                    price_per_base_unit=price_per_base_unit, source="manual",
                )
            return batch_id

    def consume(self, *, product_id: int, quantity: float,
                reason: str = REASON_CONSUMPTION, occurred_at: str | None = None,
                idempotency_key: str | None = None) -> list[int]:
        """Take a quantity out of stock, across as many batches as needed."""
        moment = occurred_at or _now()
        with self.db.write() as conn:
            if idempotency_key and repo.movement_exists(conn, idempotency_key):
                # Replayed call: return the movements the first call wrote.
                rows = conn.execute(
                    "SELECT id FROM movement WHERE idempotency_key = ?"
                    " OR idempotency_key LIKE ? ORDER BY id",
                    (idempotency_key, f"{idempotency_key}#%"),
                ).fetchall()
                return [int(row["id"]) for row in rows]
            batches = [_as_batch_view(row)
                       for row in repo.list_batches_for_product(conn, product_id)]
            allocations = allocate(batches, quantity)   # raises InsufficientStock
            movement_ids: list[int] = []
            for index, allocation in enumerate(allocations):
                article_row = conn.execute(
                    "SELECT article_id FROM batch WHERE id = ?", (allocation.batch_id,)
                ).fetchone()
                values = movement_values(allocation.quantity,
                                         allocation.kcal_per_base_unit,
                                         allocation.price_per_base_unit)
                # One consumption can span several batches, but the key is UNIQUE:
                # the first movement carries it, the next ones carry "key#1", "key#2".
                key = None
                if idempotency_key:
                    key = idempotency_key if index == 0 else f"{idempotency_key}#{index}"
                movement_ids.append(repo.insert_movement(
                    conn, occurred_at=moment, product_id=product_id,
                    article_id=article_row["article_id"], batch_id=allocation.batch_id,
                    quantity=-allocation.quantity, reason=reason, kcal=values.kcal,
                    cost=values.cost, idempotency_key=key,
                ))
                repo.set_batch_remaining(
                    conn, allocation.batch_id, allocation.remaining_after,
                    closed_at=moment if allocation.closes_batch else None,
                )
            return movement_ids

    def open_batch(self, batch_id: int, *, occurred_at: str | None = None) -> None:
        """Mark a batch open and, if the product says so, bring its date closer."""
        moment = occurred_at or _now()
        with self.db.write() as conn:
            row = conn.execute(
                "SELECT b.best_before, p.days_after_opening FROM batch b"
                " JOIN article a ON a.id = b.article_id"
                " JOIN product p ON p.id = a.product_id WHERE b.id = ?",
                (batch_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"unknown batch {batch_id}")
            best_before = row["best_before"]
            if row["days_after_opening"]:
                shortened = (
                    datetime.fromisoformat(moment).date()
                    + timedelta(days=int(row["days_after_opening"]))
                ).isoformat()
                if best_before is None or shortened < best_before:
                    best_before = shortened
            repo.set_batch_opened(conn, batch_id, moment, best_before)

    def transfer_batch(self, batch_id: int, location_id: int, *,
                       occurred_at: str | None = None) -> int:
        """Move a batch to another location. Nothing is consumed."""
        moment = occurred_at or _now()
        with self.db.write() as conn:
            row = conn.execute(
                "SELECT b.article_id, a.product_id FROM batch b"
                " JOIN article a ON a.id = b.article_id WHERE b.id = ?",
                (batch_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"unknown batch {batch_id}")
            repo.set_batch_location(conn, batch_id, location_id)
            return repo.insert_movement(
                conn, occurred_at=moment, product_id=row["product_id"],
                article_id=row["article_id"], batch_id=batch_id, quantity=0,
                reason=REASON_TRANSFER, ref_type="location", ref_id=location_id,
            )

    def adjust_inventory(self, *, article_id: int, location_id: int,
                         counted_quantity: float,
                         occurred_at: str | None = None) -> int | None:
        """Record what was actually counted. Returns the movement id, or None."""
        moment = occurred_at or _now()
        with self.db.write() as conn:
            article = repo.get_article(conn, article_id)
            if article is None:
                raise ValueError(f"unknown article {article_id}")
            rows = conn.execute(
                "SELECT * FROM batch WHERE article_id = ? AND location_id = ?"
                " AND closed_at IS NULL", (article_id, location_id),
            ).fetchall()
            current = sum(row["remaining"] for row in rows)
            delta = counted_quantity - current
            if abs(delta) < 0.001:
                return None
            if delta < 0:
                # Reuse the same BatchView construction as consume(): the rows
                # from `SELECT * FROM batch` do not carry kcal_per_base_unit, so
                # inject the article's rate before handing them to the helper.
                views = [
                    _as_batch_view({**dict(row), "kcal_per_base_unit": article["kcal_per_base_unit"]})
                    for row in rows
                ]
                for allocation in allocate(views, -delta):
                    repo.set_batch_remaining(
                        conn, allocation.batch_id, allocation.remaining_after,
                        closed_at=moment if allocation.closes_batch else None,
                    )
                batch_id = None
            else:
                batch_id = repo.insert_batch(
                    conn, article_id=article_id, location_id=location_id,
                    quantity=delta, entered_at=moment,
                )
            # kcal and cost stay NULL: a correction is not a consumption (spec 7.5).
            return repo.insert_movement(
                conn, occurred_at=moment, product_id=article["product_id"],
                article_id=article_id, batch_id=batch_id, quantity=delta,
                reason=REASON_INVENTORY,
            )

    # --- reads --------------------------------------------------------------

    def query_stock(self, *, name: str | None = None) -> list[dict[str, Any]]:
        """What is in stock, aggregated per product. Feeds the voice answer."""
        rows = repo.stock_rows(self.db.read())
        grouped: dict[int, dict[str, Any]] = {}
        for row in rows:
            entry = grouped.setdefault(row["product_id"], {
                "product_id": row["product_id"], "product_name": row["product_name"],
                "base_unit": row["base_unit"], "quantity": 0.0, "batches": 0,
            })
            entry["quantity"] += row["remaining"]
            entry["batches"] += 1
        result = list(grouped.values())
        if name:
            needle = name.casefold()
            result = [e for e in result if needle in e["product_name"].casefold()]
        for entry in result:
            entry["display"] = format_quantity(entry["quantity"], entry["base_unit"])
        return sorted(result, key=lambda e: e["product_name"])

    def summary(self, *, expiration_alert_days: int,
                today: str | None = None) -> dict[str, Any]:
        """The numbers the entities publish."""
        reference = date.fromisoformat(today) if today else datetime.now(UTC).date()
        limit = reference + timedelta(days=expiration_alert_days)
        rows = repo.stock_rows(self.db.read())

        value = 0.0
        unpriced = 0
        expiring: list[dict[str, Any]] = []
        per_product: dict[int, dict[str, Any]] = {}
        for row in rows:
            if row["price_per_base_unit"] is None:
                unpriced += 1
            else:
                value += row["remaining"] * row["price_per_base_unit"]
            if row["best_before"] and date.fromisoformat(row["best_before"]) <= limit:
                expiring.append({
                    "batch_id": row["id"], "product_name": row["product_name"],
                    "best_before": row["best_before"],
                    "display": format_quantity(row["remaining"], row["base_unit"]),
                })
            entry = per_product.setdefault(row["product_id"], {
                "product_name": row["product_name"], "quantity": 0.0,
                "min_quantity": row["min_quantity"], "base_unit": row["base_unit"],
            })
            entry["quantity"] += row["remaining"]

        shortages = [
            {"product_name": entry["product_name"],
             "display": format_quantity(entry["quantity"], entry["base_unit"])}
            for entry in per_product.values()
            if entry["min_quantity"] and entry["quantity"] < entry["min_quantity"]
        ]
        return {
            "stock_value": round(value, 2),
            "unpriced_batches": unpriced,
            "batch_count": len(rows),
            "open_batch_count": sum(1 for row in rows if row["opened_at"]),
            "expiring": sorted(expiring, key=lambda e: e["best_before"]),
            "shortages": sorted(shortages, key=lambda e: e["product_name"]),
        }

    def export_journal(self) -> list[dict[str, Any]]:
        """The whole append-only journal. It is enough to rebuild everything."""
        return repo.list_movements(self.db.read())
