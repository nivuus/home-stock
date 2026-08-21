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
#
# The opening quote is `['"`` ]` — single, double, or backtick — on purpose:
# nothing in the TypeScript config or lint rules pins one quote style, and a
# scanner that only understands single quotes is a guard that depends on a
# coding habit, not a guard. It doesn't bother matching the CLOSING quote:
# `home_stock/[a-z_/]+` already stops at the first character that isn't part
# of a command name, so there is nothing a closing-quote check would add.
_QUEUED_COMMAND_RE = re.compile(r"""\.(?:ajouter|ecrire)\(\s*['"`](home_stock/[a-z_/]+)""")


def discover_queued_command_types(root: Path = FRONTEND_SRC) -> set[str]:
    types: set[str] = set()
    for path in root.rglob("*.ts"):
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
    # Task 17: the catalogue and settings screens write through the same
    # offline queue as every other screen (spec §14) — a product edit and an
    # aisle reorder are writes like any other, even though their usual
    # context (a desk, not a shop aisle) makes the queue's offline tolerance
    # rarely exercised in practice.
    "home_stock/product/update",
    "home_stock/aisles/reorder",
    # Final fix wave: the « Courses » screen is what opens and closes a
    # shopping session. Both writes go through the same offline queue as
    # every other — the car park of a shop has no more signal than its
    # aisles — so both schemas have to accept the key the queue stamps.
    "home_stock/session/start",
    "home_stock/session/close",
    # Lot 2, task 14: the "manger" screen declares what was eaten, thrown
    # away, or found expired. It's stood in the kitchen, not a shop aisle,
    # but the network there is no more reliable — this is the first command
    # this screen queues, and the exact gap that stalled a whole cart behind
    # one refused button in lot 1's round 1 (see this file's module
    # docstring) if its schema didn't accept the queue's idempotency key.
    "home_stock/stock/consume",
    # Lot 3, task 18: the recipe list marks an imported recipe as reviewed.
    # It is a write like any other and goes through the same queue — the
    # kitchen's network is no better than a shop aisle's.
    "home_stock/recipe/update",
    # Lot 3, task 20: the validation screen. Cooking then eating is the
    # heaviest write the panel makes, and it is made standing in a kitchen —
    # the queue must be able to hold it and replay it exactly once.
    "home_stock/meal/validate",
}


def test_the_scanner_finds_exactly_the_commands_the_front_end_can_queue():
    """A refactor of how `ajouter`/`ecrire` are called (a helper renamed, a
    call site restructured) could make the regex above silently match
    nothing, and the contract test below would then vacuously pass — zero
    commands checked, zero failures. This pins today's known-correct result
    so that kind of drift fails loudly instead of just checking less.
    """
    assert discover_queued_command_types() == EXPECTED_QUEUED_COMMAND_TYPES


def test_the_scanner_catches_a_queued_command_regardless_of_quote_style(tmp_path):
    """The blind spot that defeated this test once already: the regex used
    to require a single quote, so a queued command written with double
    quotes (or a template literal) was invisible to it — a strict-schema
    command shipped that way would pass both tests here while still being
    able to silence a whole trip in production. Proven against a scratch
    directory, not the real frontend source: changing `frontend/src/*.ts` to
    a different quote style just to exercise this would be editing
    production code to flatter a test.
    """
    (tmp_path / "exemple.ts").write_text(
        'this.file.ajouter("home_stock/session/scratch_double", {});\n'
        "this.ecrire(`home_stock/session/scratch_backtick`, {});\n"
        "this.ecrire('home_stock/session/scratch_single', {});\n",
        encoding="utf-8",
    )

    assert discover_queued_command_types(tmp_path) == {
        "home_stock/session/scratch_double",
        "home_stock/session/scratch_backtick",
        "home_stock/session/scratch_single",
    }


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

    # No batch_id: the "manger" screen always targets one, but the schema
    # doesn't require it (a caller can let FIFO pick) — the 200 g just
    # added above is what gets walked.
    consumed = await _send(
        client, _id(), "home_stock/stock/consume", product_id=1, quantity=50,
        reason="consumption", idempotency_key="contract-stock-consume",
    )
    assert consumed["success"] is True, consumed.get("error")
    tested.add("home_stock/stock/consume")

    updated_product = await _send(
        client, _id(), "home_stock/product/update", product_id=1,
        fields={"name": "Article prêt à ranger (modifié)"}, idempotency_key="contract-product-update",
    )
    assert updated_product["success"] is True, updated_product.get("error")
    tested.add("home_stock/product/update")

    # No aisle needs to exist for this contract: an empty list is a valid
    # (no-op) reorder, and the point here is only the schema's acceptance of
    # idempotency_key, already exercised against real reordering in
    # test_websocket_write.py::test_reordering_aisles_accepts_the_offline_
    # queues_idempotency_key.
    reordered_aisles = await _send(
        client, _id(), "home_stock/aisles/reorder", aisle_ids=[], idempotency_key="contract-aisles-reorder",
    )
    assert reordered_aisles["success"] is True, reordered_aisles.get("error")
    tested.add("home_stock/aisles/reorder")

    # --- lot 3: recipes ------------------------------------------------
    created_recipe = await _send(
        client, _id(), "home_stock/recipe/create", name="Recette du contrat",
        idempotency_key="contract-recipe-create",
    )
    assert created_recipe["success"] is True, created_recipe.get("error")

    updated_recipe = await _send(
        client, _id(), "home_stock/recipe/update",
        recipe_id=created_recipe["result"]["recipe_id"],
        fields={"needs_review": 0}, idempotency_key="contract-recipe-update",
    )
    assert updated_recipe["success"] is True, updated_recipe.get("error")
    tested.add("home_stock/recipe/update")

    planned_meal = await _send(
        client, _id(), "home_stock/meal/plan", day="2026-08-21",
        slot_key="dinner", note="Repas du contrat",
        idempotency_key="contract-meal-plan",
    )
    assert planned_meal["success"] is True, planned_meal.get("error")

    # A note meal decrements nothing, which is exactly what this contract
    # needs: the point is the SCHEMA's acceptance of the queue's key, not the
    # arithmetic — that is proven in test_websocket_meals.py.
    validated_meal = await _send(
        client, _id(), "home_stock/meal/validate",
        meal_id=planned_meal["result"]["meal_id"], portions_eaten=0,
        idempotency_key="contract-meal-validate",
    )
    assert validated_meal["success"] is True, validated_meal.get("error")
    tested.add("home_stock/meal/validate")

    # --- the shopping-session lifecycle, exactly as the panel drives it -
    started = await _send(client, _id(), "home_stock/session/start", store="Leclerc",
                          idempotency_key="contract-session-start")
    assert started["success"] is True, started.get("error")
    tested.add("home_stock/session/start")

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

    # `close` needs a session to close, and the one above closed itself the
    # moment its last line was put away (ShoppingService.store_line). So the
    # next trip is opened and then abandoned — which is precisely what
    # `close` is for, and the only way to reopen one afterwards.
    reopened = await _send(client, _id(), "home_stock/session/start", store="Lidl",
                           idempotency_key="contract-session-start-2")
    assert reopened["success"] is True, reopened.get("error")

    closed = await _send(client, _id(), "home_stock/session/close",
                         idempotency_key="contract-session-close")
    assert closed["success"] is True, closed.get("error")
    tested.add("home_stock/session/close")

    # Every command the front end can actually queue was exercised — not a
    # subset the test author remembered to write a case for.
    assert tested == discovered == EXPECTED_QUEUED_COMMAND_TYPES
