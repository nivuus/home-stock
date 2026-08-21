"""The shopping session: what is scanned in the aisle, and put away at home.

The session lives here, server-side, not in the phone. A screen that goes to
sleep, an app that is closed, a basement with no signal — none of them lose a
cart. The panel keeps only a replay queue of writes it could not send.
"""
from __future__ import annotations

import statistics
from datetime import UTC, datetime
from typing import Any

from .application import StockManager
from .storage import repositories as repo


class ShoppingError(Exception):
    """A shopping action that does not make sense in the current state."""


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0, tzinfo=None).isoformat()


class ShoppingService:
    """Every write to a shopping session goes through here."""

    def __init__(self, manager: StockManager) -> None:
        self.manager = manager

    # --- session ------------------------------------------------------------

    def start(self, *, store: str | None = None,
              store_id: int | None = None) -> dict[str, Any]:
        """Open a trip. Refuses ANY session that is not `done`.

        Not just an open one: the partial unique index only covers
        `state = 'shopping'`, so the database happily accepts a second
        session while a `to_store` trip is still waiting to be put away —
        and `current_session` then surfaces only the newer one. The older
        trip's unstored lines become invisible on every screen while still
        counting against their product's unit conversion, and the natural
        reflex on seeing a stale "Courses à ranger" is to close it, which
        abandons those lines for good. So the refusal lives here, in
        Python, where it can say what is in the way and what to do about it
        — the index alone cannot.
        """
        with self.manager.db.write() as conn:
            existing = repo.current_session(conn)
            # current_session only ever returns a 'shopping' or a 'to_store'
            # row (see its WHERE clause): anything it hands back is a trip
            # still in progress.
            if existing is not None:
                if existing["state"] == "shopping":
                    raise ShoppingError("Une session de courses est déjà ouverte.")
                enseigne = f" ({existing['store']})" if existing["store"] else ""
                raise ShoppingError(
                    f"Des courses{enseigne} attendent encore d'être rangées : "
                    "rangez-les ou clôturez-les avant d'en ouvrir de nouvelles."
                )
            # Le magasin est une LIGNE depuis le lot 4 (amendement A4).
            # `store_id` prime : le panneau envoie une pastille, pas une
            # chaîne. Un nom sans identifiant crée le magasin s'il n'existe
            # pas, par égalité EXACTE — deux orthographes restent deux
            # magasins tant que le propriétaire ne les a pas fusionnés.
            name = store.strip() if isinstance(store, str) else store
            if store_id is not None:
                row = repo.get_store(conn, store_id)
                if row is None:
                    raise ShoppingError("Ce magasin n'existe pas.")
                name = row["name"]
            elif name:
                store_id = repo.upsert_store(conn, name=name)
            else:
                name = None
            session_id = repo.open_session(conn, started_at=_now(), store=name,
                                           store_id=store_id)
            return repo.get_session(conn, session_id)

    def merge_stores(self, *, keep_id: int, merge_id: int) -> dict[str, Any]:
        """Réunir deux orthographes du même magasin.

        Refusé tant qu'une session est en cours dans l'un des deux : on ne
        déplace pas le sol sous une session de courses.
        """
        if keep_id == merge_id:
            raise ShoppingError("Ces deux magasins sont le même.")
        with self.manager.db.write() as conn:
            current = repo.current_session(conn)
            if current is not None and current["store_id"] in (keep_id, merge_id):
                raise ShoppingError(
                    "Une session de courses est en cours dans ce magasin : "
                    "clôturez-la avant de fusionner.")
            for store_id in (keep_id, merge_id):
                if repo.get_store(conn, store_id) is None:
                    raise ShoppingError("Ce magasin n'existe pas.")
            return repo.merge_stores(conn, keep_id=keep_id, merge_id=merge_id)

    def list_stores(self, *, active_only: bool = True) -> list[dict[str, Any]]:
        return repo.list_stores(self.manager.db.read(), active_only=active_only)

    def upsert_store(self, *, name: str, store_id: int | None = None,
                     position: int | None = None,
                     active: int | None = None) -> dict[str, Any]:
        with self.manager.db.write() as conn:
            written = repo.upsert_store(conn, name=name, store_id=store_id,
                                        position=position, active=active)
            return repo.get_store(conn, written)

    def current(self) -> dict[str, Any] | None:
        conn = self.manager.db.read()
        session = repo.current_session(conn)
        if session is None:
            return None
        return {
            "session": session,
            "lines": repo.list_lines(conn, session["id"]),
            "totals": repo.session_totals(conn, session["id"]),
            "stores": repo.list_stores(conn),
        }

    def checkout(self) -> dict[str, Any]:
        with self.manager.db.write() as conn:
            session = self._open_session(conn)
            repo.set_session_state(conn, session["id"], "to_store")
            return repo.get_session(conn, session["id"])

    def close(self) -> dict[str, Any]:
        with self.manager.db.write() as conn:
            session = repo.current_session(conn)
            if session is None:
                raise ShoppingError("Aucune session de courses en cours.")
            repo.set_session_state(conn, session["id"], "done", closed_at=_now())
            return repo.get_session(conn, session["id"])

    # --- lines --------------------------------------------------------------

    def add_line(self, *, article_id: int, quantity: float, unit_price: float | None,
                 idempotency_key: str | None,
                 price_source: str | None = None) -> dict[str, Any]:
        with self.manager.db.write() as conn:
            if idempotency_key:
                # The panel's offline queue replays in order; a replayed scan
                # must return the line it already created, not a second packet.
                existing = repo.line_by_key(conn, idempotency_key)
                if existing is not None:
                    return existing

            session = self._open_session(conn)
            # Amendement A3 : d'où vient ce prix. Un appelant qui ne dit rien
            # décrit un prix tapé — c'est ce que faisait le lot 1, et c'est
            # le choix qui ne perd rien. Une ligne sans prix n'a pas de
            # source : il n'y a pas de valeur dont on puisse dire l'origine.
            source = (price_source or "manual") if unit_price is not None else None
            line_id = repo.add_line(
                conn, session_id=session["id"], article_id=article_id,
                quantity=quantity, unit_price=unit_price, scanned_at=_now(),
                idempotency_key=idempotency_key, price_source=source,
            )
            if unit_price is not None:
                # The observation happens in the aisle, so it is recorded in the
                # aisle — not later, when the pack is put away somewhere else.
                repo.insert_price(
                    conn, article_id=article_id, observed_on=_now()[:10],
                    price_per_base_unit=unit_price, store=session["store"],
                    source=source,
                )
            # Always hand back the row as the database holds it, whether or
            # not a key was supplied: a caller must not have to guess the
            # shape of the answer from what it sent.
            return repo.get_line(conn, line_id)

    def update_line(self, line_id: int, *, quantity: float | None = None,
                    unit_price: float | None = None,
                    price_source: str | None = None) -> dict[str, Any]:
        with self.manager.db.write() as conn:
            line = self._line(conn, line_id)
            if line["stored_at"]:
                raise ShoppingError("Cette ligne est déjà rangée.")
            changed = unit_price is not None and unit_price != line["unit_price"]
            # Une valeur qui change ici est une saisie HUMAINE, quelle que
            # soit la source annoncée : on vient de la corriger devant
            # l'étiquette. Une valeur inchangée conserve la source déclarée.
            repo.update_line(conn, line_id, quantity=quantity, unit_price=unit_price,
                             price_source="manual" if changed else price_source)
            if changed:
                # A price corrected at the till has to correct the observation
                # the scan seeded, and a price typed here for the first time
                # has to record one. Without this, a suggestion accepted at
                # 0,004 €/g in the aisle and corrected to 0,006 €/g at the
                # checkout left 0,004 recorded against that shop — at rank 1
                # of the suggestion cascade (spec 11), reseeding the wrong
                # figure on every later trip.
                #
                # A new observation rather than an UPDATE of the earlier row:
                # `price` is a log of what was seen, nothing links a row to
                # the line that wrote it, and both readings really were made.
                # latest_price_in_store orders by observed_on then id, so the
                # correction is what the cascade answers from now on.
                #
                # Guarded on an actual change of value: a replayed queue (the
                # panel stamps every action with a key and replays in order)
                # must not pile up identical rows.
                session = repo.get_session(conn, line["session_id"])
                repo.insert_price(
                    conn, article_id=line["article_id"], observed_on=_now()[:10],
                    price_per_base_unit=unit_price,
                    store=session["store"] if session else None,
                    source="manual",
                )
            return self._line(conn, line_id)

    def remove_line(self, line_id: int) -> None:
        with self.manager.db.write() as conn:
            line = self._line(conn, line_id)
            if line["stored_at"]:
                # The batch exists and the journal has recorded the purchase.
                # Undoing that is an inventory correction, not a deletion.
                raise ShoppingError(
                    "Cette ligne est déjà rangée : corrigez le lot, pas la liste."
                )
            repo.remove_line(conn, line_id)

    def store_line(self, line_id: int, *, location_id: int,
                   best_before: str | None) -> dict[str, Any]:
        """Turn a bought line into a real batch. This is where stock is created.

        Known, harmless race: the read below takes no lock, so two concurrent
        calls on the same not-yet-stored line can both pass the `stored_at`
        check and both reach add_stock(). That is safe because add_stock is
        idempotent on `f"shopping_line:{line_id}"` — the second call finds the
        first call's movement and returns its batch_id instead of creating a
        second batch. The only redundant work is below: mark_line_stored runs
        twice (same values), the shelf life is learned twice from the same
        data, and the session-close check runs twice — all idempotent in
        effect, so not worth a lock for.
        """
        line = self._line(self.manager.db.read(), line_id)
        if line["stored_at"]:
            return {"line_id": line_id, "batch_id": line["batch_id"],
                    "already_stored": True}

        # Database.write() takes a non-reentrant lock: add_stock() opens its
        # own transaction, so the read above must already be finished (it is
        # — self.manager.db.read() never took the lock) and this call must
        # not be nested inside another with self.manager.db.write() block.
        # record_price_observation=False: the price was already recorded, with
        # its shop, at scan time in add_line() — put-away is not a second
        # observation, and writing it again here duplicated every priced
        # line's price history.
        batch_id = self.manager.add_stock(
            article_id=line["article_id"], quantity=line["quantity"],
            location_id=location_id, best_before=best_before,
            price_per_base_unit=line["unit_price"],
            idempotency_key=f"shopping_line:{line_id}",
            record_price_observation=False,
        )

        with self.manager.db.write() as conn:
            repo.mark_line_stored(conn, line_id, batch_id=batch_id, stored_at=_now())
            self._learn_shelf_life(conn, line["product_id"])
            session = repo.get_session(conn, line["session_id"])
            pending = repo.session_totals(conn, session["id"])["pending"]
            if pending == 0 and session["state"] != "shopping":
                repo.set_session_state(conn, session["id"], "done", closed_at=_now())

        return {"line_id": line_id, "batch_id": batch_id, "already_stored": False}

    # --- helpers ------------------------------------------------------------

    def _open_session(self, conn) -> dict[str, Any]:
        session = repo.current_session(conn)
        if session is None or session["state"] != "shopping":
            raise ShoppingError("aucune session de courses ouverte : ouvrez-en une pour scanner.")
        return session

    def _line(self, conn, line_id: int) -> dict[str, Any]:
        row = conn.execute(
            """
            SELECT l.*, a.product_id FROM shopping_line l
            JOIN article a ON a.id = l.article_id WHERE l.id = ?
            """,
            (line_id,),
        ).fetchone()
        if row is None:
            raise ShoppingError(f"Ligne inconnue : {line_id}")
        return dict(row)

    def _learn_shelf_life(self, conn, product_id: int) -> None:
        """Update the one-tap default from what was actually posed.

        The median of the last three, not the last one: a date typed wrong
        should not drag the default with it.
        """
        observed = repo.recent_shelf_lives(conn, product_id, limit=3)
        if not observed:
            return
        repo.update_product_fields(
            conn, product_id, {"default_shelf_life_days": round(statistics.median(observed))}
        )
