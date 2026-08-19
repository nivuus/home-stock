"""Contract test: every command the panel's offline queue can hold must
accept an `idempotency_key`.

`FileAttente.ajouter` (frontend/src/file-attente.ts) stamps this key onto
EVERY action pushed through it, with no notion of "this command doesn't take
one" — see fix round 1's incident: three commands had strict schemas with no
such key, so the very first offline retry of one of them was refused,
dropped, and (before round 1) silently blocked everything queued behind it.
Two more (checkout, article/update) turned out to have the same gap in round
2. A hand-written list of "commands to check" is exactly what let two slip
through last time; this scans the actual TypeScript call sites instead, so a
new queued command with a strict schema fails THIS test the day it's added,
not a shopper mid-trip.
"""
from __future__ import annotations

import re
from pathlib import Path

from homeassistant.core import HomeAssistant

FRONTEND_SRC = Path(__file__).resolve().parent.parent / "frontend" / "src"

# Matches the literal `home_stock/...` type string passed to `.ajouter(...)`
# (FileAttente's own method) or to a screen's `ecrire(...)` wrapper around it
# (panier.ts, rangement.ts) — the two places a queued write's command type is
# ever spelled out. `type` used as a forwarded variable (the wrapper itself)
# has no string literal to match here, which is exactly why it's invisible
# to this scan and doesn't need to be: it carries whatever literal a CALL
# SITE of `ecrire(...)` passed, and every such call site is a real match.
_QUEUED_COMMAND_RE = re.compile(r"\.(?:ajouter|ecrire)\(\s*'(home_stock/[a-z_/]+)'")


def discover_queued_command_types() -> set[str]:
    types: set[str] = set()
    for path in FRONTEND_SRC.rglob("*.ts"):
        types.update(_QUEUED_COMMAND_RE.findall(path.read_text(encoding="utf-8")))
    return types


# What the scan above is expected to find, today. Kept only as a sanity check
# on the scanner itself (test below) — the scan result, not this constant, is
# what drives which commands get exercised against the real schemas.
EXPECTED_QUEUED_COMMAND_TYPES = {
    "home_stock/session/add_line",
    "home_stock/session/update_line",
    "home_stock/session/remove_line",
    "home_stock/session/checkout",
    "home_stock/session/store_line",
    "home_stock/stock/add",
    "home_stock/article/update",
}


def test_the_scanner_finds_exactly_the_commands_the_front_end_can_queue():
    """A refactor of how `ajouter`/`ecrire` are called (a helper renamed, a
    call site restructured) could make the regex above silently match
    nothing, and the contract test below would then vacuously pass — zero
    commands checked, zero failures. This pins today's known-correct result
    so that kind of drift fails loudly instead of just checking less.
    """
    assert discover_queued_command_types() == EXPECTED_QUEUED_COMMAND_TYPES


async def _send(client, id_, type_, **payload):
    await client.send_json({"id": id_, "type": type_, **payload})
    return await client.receive_json()


async def test_every_queued_command_accepts_the_offline_queue_s_idempotency_key(
    hass: HomeAssistant, setup_entry, hass_ws_client
):
    discovered = discover_queued_command_types()
    tested: set[str] = set()
    ids = iter(range(1, 100))

    def _id() -> int:
        return next(ids)

    entry = await setup_entry(with_article=True)
    client = await hass_ws_client(hass)

    # --- independent of any session -----------------------------------
    updated_article = await _send(
        client, _id(), "home_stock/article/update", article_id=1,
        fields={"net_quantity": 500}, idempotency_key="contract-article-update",
    )
    assert updated_article["success"] is True, updated_article.get("error")
    tested.add("home_stock/article/update")

    added_stock = await _send(
        client, _id(), "home_stock/stock/add", article_id=1, quantity=200,
        location_id=1, idempotency_key="contract-stock-add",
    )
    assert added_stock["success"] is True, added_stock.get("error")
    tested.add("home_stock/stock/add")

    # --- the shopping-session lifecycle, exactly as the panel drives it -
    started = await _send(client, _id(), "home_stock/session/start", store="Leclerc")
    assert started["success"] is True

    line_a = await _send(
        client, _id(), "home_stock/session/add_line", article_id=1, quantity=500,
        unit_price=0.002, idempotency_key="contract-add-line-a",
    )
    assert line_a["success"] is True, line_a.get("error")
    tested.add("home_stock/session/add_line")

    line_b = await _send(
        client, _id(), "home_stock/session/add_line", article_id=1, quantity=100,
        unit_price=None, idempotency_key="contract-add-line-b",
    )
    assert line_b["success"] is True, line_b.get("error")

    updated_line = await _send(
        client, _id(), "home_stock/session/update_line", line_id=line_a["result"]["id"],
        quantity=750, idempotency_key="contract-update-line",
    )
    assert updated_line["success"] is True, updated_line.get("error")
    tested.add("home_stock/session/update_line")

    checked_out = await _send(
        client, _id(), "home_stock/session/checkout", idempotency_key="contract-checkout",
    )
    assert checked_out["success"] is True, checked_out.get("error")
    tested.add("home_stock/session/checkout")

    # remove_line doesn't require the session to still be "shopping" — only
    # that the line itself isn't stored yet — so removing line_b after
    # checkout (put-away, not shopping) is the realistic path: "I got home
    # and didn't actually buy that."
    removed_line = await _send(
        client, _id(), "home_stock/session/remove_line", line_id=line_b["result"]["id"],
        idempotency_key="contract-remove-line",
    )
    assert removed_line["success"] is True, removed_line.get("error")
    tested.add("home_stock/session/remove_line")

    stored_line = await _send(
        client, _id(), "home_stock/session/store_line", line_id=line_a["result"]["id"],
        location_id=1, best_before="2027-01-01", idempotency_key="contract-store-line",
    )
    assert stored_line["success"] is True, stored_line.get("error")
    tested.add("home_stock/session/store_line")

    # Every command the front end can actually queue was exercised — not a
    # subset the test author remembered to write a case for.
    assert tested == discovered == EXPECTED_QUEUED_COMMAND_TYPES
