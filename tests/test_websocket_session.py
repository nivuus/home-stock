"""The shopping session, driven exactly as the panel drives it."""
from homeassistant.core import HomeAssistant

from custom_components.home_stock.storage import repositories as repo


async def _send(client, id_, type_, **payload):
    await client.send_json({"id": id_, "type": type_, **payload})
    return await client.receive_json()


async def test_a_full_trip_from_the_aisle_to_the_cupboard(hass: HomeAssistant, setup_entry,
                                                           hass_ws_client):
    # with_article seeds one location ("Placard") and one g-based article,
    # both landing on id 1 — see conftest.setup_entry's own docstring. Its
    # product carries no aisle by default; list_lines' walking order depends
    # on one, so give it the first one an OFF-derived scan would have.
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager

    def _assign_aisle() -> None:
        aisle_id = repo.list_aisles(manager.db.read())[0]["id"]
        with manager.db.write() as conn:
            repo.update_product_fields(conn, 1, {"aisle_id": aisle_id})

    await hass.async_add_executor_job(_assign_aisle)
    client = await hass_ws_client(hass)

    await _send(client, 1, "home_stock/session/start", store="Leclerc")
    added = await _send(client, 2, "home_stock/session/add_line", article_id=1,
                        quantity=500, unit_price=0.002, idempotency_key="scan-1")
    assert added["success"] is True
    line_id = added["result"]["id"]

    current = await _send(client, 3, "home_stock/session/current")
    assert current["result"]["totals"]["total"] == 1.0
    assert current["result"]["lines"][0]["aisle_name"]

    await _send(client, 4, "home_stock/session/checkout")
    stored = await _send(client, 5, "home_stock/session/store_line", line_id=line_id,
                         location_id=1, best_before="2027-01-01")
    assert stored["success"] is True
    assert stored["result"]["batch_id"]

    after = await _send(client, 6, "home_stock/session/current")
    assert after["result"] is None


async def test_a_second_session_is_refused_with_a_readable_error(hass: HomeAssistant,
                                                                  setup_entry, hass_ws_client):
    await setup_entry()
    client = await hass_ws_client(hass)
    await _send(client, 1, "home_stock/session/start", store="Leclerc")

    answer = await _send(client, 2, "home_stock/session/start", store="Lidl")

    assert answer["success"] is False
    assert "déjà" in answer["error"]["message"]


async def test_a_replayed_scan_does_not_double_the_cart(hass: HomeAssistant, setup_entry,
                                                         hass_ws_client):
    await setup_entry(with_article=True)
    client = await hass_ws_client(hass)
    await _send(client, 1, "home_stock/session/start", store=None)

    first = await _send(client, 2, "home_stock/session/add_line", article_id=1,
                        quantity=500, unit_price=None, idempotency_key="scan-1")
    again = await _send(client, 3, "home_stock/session/add_line", article_id=1,
                        quantity=500, unit_price=None, idempotency_key="scan-1")

    assert first["result"]["id"] == again["result"]["id"]
    current = await _send(client, 4, "home_stock/session/current")
    assert len(current["result"]["lines"]) == 1


async def test_a_line_cannot_be_removed_once_stored(hass: HomeAssistant, setup_entry,
                                                     hass_ws_client):
    """A readable ShoppingError for a refusal other than "session already open" —
    the two together prove _shopping_error is reused for every ShoppingError,
    not hand-rolled per command."""
    await setup_entry(with_article=True)
    client = await hass_ws_client(hass)
    await _send(client, 1, "home_stock/session/start", store=None)
    added = await _send(client, 2, "home_stock/session/add_line", article_id=1,
                        quantity=500, unit_price=None, idempotency_key="scan-1")
    line_id = added["result"]["id"]
    await _send(client, 3, "home_stock/session/store_line", line_id=line_id,
               location_id=1, best_before=None)

    answer = await _send(client, 4, "home_stock/session/remove_line", line_id=line_id)

    assert answer["success"] is False
    assert "rangée" in answer["error"]["message"]


async def test_the_cart_sensors_follow_the_session(hass: HomeAssistant, setup_entry,
                                                    hass_ws_client):
    entry = await setup_entry(with_article=True)
    client = await hass_ws_client(hass)
    await _send(client, 1, "home_stock/session/start", store="Leclerc")
    await _send(client, 2, "home_stock/session/add_line", article_id=1,
               quantity=500, unit_price=0.002, idempotency_key="scan-1")
    # Each command already awaited its own async_request_refresh(), but that
    # call is debounced (see websocket_api.subscribe's own comment on it):
    # two writes issued back to back can coalesce into one trailing refresh
    # that only fires after a real cooldown, which async_block_till_done()
    # does not wait out. async_refresh() forces the read synchronously — the
    # same way every state-asserting test in test_entities.py already does.
    await entry.runtime_data.coordinator.async_refresh()

    cart = hass.states.get("sensor.home_stock_cart_total")
    assert float(cart.state) == 1.0
    assert cart.attributes["store"] == "Leclerc"
    # Still in the aisle (session/checkout not called yet): nothing is
    # "awaiting put-away" yet, even though the line has no batch either —
    # to_store only starts counting once the session has left `shopping`.
    assert hass.states.get("sensor.home_stock_to_store").state == "0"

    await _send(client, 3, "home_stock/session/checkout")
    await entry.runtime_data.coordinator.async_refresh()
    assert hass.states.get("sensor.home_stock_to_store").state == "1"


async def test_the_cart_sensors_are_zero_with_no_session(hass: HomeAssistant, setup_entry):
    await setup_entry()
    await hass.async_block_till_done()

    assert hass.states.get("sensor.home_stock_cart_total").state == "0.0"
    assert hass.states.get("sensor.home_stock_to_store").state == "0"


async def test_an_unknown_article_on_add_line_is_a_readable_error(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    """ShoppingService.add_line does not pre-check article_id the way
    manager.add_stock does — an unknown id reaches SQLite as a bare
    FOREIGN KEY violation. Without the integrity-error guard this used to
    surface to the panel as "Unknown error"."""
    await setup_entry()
    client = await hass_ws_client(hass)
    await _send(client, 1, "home_stock/session/start", store=None)

    answer = await _send(client, 2, "home_stock/session/add_line", article_id=999,
                         quantity=500, unit_price=None, idempotency_key=None)

    assert answer["success"] is False
    assert answer["error"]["message"] != "Unknown error"


async def test_an_unknown_location_on_store_line_is_a_readable_error(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    """store_line calls the very same manager.add_stock as
    home_stock/stock/add: an unknown location_id must be translated the
    same way there, not left to surface as "Unknown error"."""
    await setup_entry(with_article=True)
    client = await hass_ws_client(hass)
    await _send(client, 1, "home_stock/session/start", store=None)
    added = await _send(client, 2, "home_stock/session/add_line", article_id=1,
                        quantity=500, unit_price=None, idempotency_key="scan-1")
    line_id = added["result"]["id"]

    answer = await _send(client, 3, "home_stock/session/store_line", line_id=line_id,
                         location_id=999, best_before=None)

    assert answer["success"] is False
    assert answer["error"]["message"] != "Unknown error"


async def test_the_offline_queue_s_idempotency_key_is_accepted_on_every_line_write(
    hass: HomeAssistant, setup_entry, hass_ws_client
):
    """FileAttente (the panel's offline queue) stamps `idempotency_key` onto
    every action it sends, uniformly — it has no notion of "this command
    doesn't take one". update_line, remove_line and store_line used to have
    strict schemas with no such key, so a client replaying a queued edit or
    removal got "extra keys not allowed" back, and worse: the queue treated
    that refusal exactly like being offline and never moved past it, taking
    the whole trip down. The three commands must accept the key (and may
    ignore it) exactly like add_line and stock/add already do.
    """
    entry = await setup_entry(with_article=True)
    client = await hass_ws_client(hass)

    await _send(client, 1, "home_stock/session/start", store="Leclerc")
    added = await _send(client, 2, "home_stock/session/add_line", article_id=1,
                        quantity=500, unit_price=0.002, idempotency_key="scan-1")
    line_id = added["result"]["id"]

    updated = await _send(client, 3, "home_stock/session/update_line", line_id=line_id,
                          quantity=750, idempotency_key="edit-1")
    assert updated["success"] is True
    assert updated["result"]["quantity"] == 750

    await _send(client, 4, "home_stock/session/checkout")
    stored = await _send(client, 5, "home_stock/session/store_line", line_id=line_id,
                         location_id=1, best_before="2027-01-01", idempotency_key="store-1")
    assert stored["success"] is True

    added2 = await _send(client, 6, "home_stock/session/start", store="Leclerc")
    assert added2["success"] is True
    second_line = await _send(client, 7, "home_stock/session/add_line", article_id=1,
                              quantity=200, unit_price=0.002, idempotency_key="scan-2")
    removed = await _send(client, 8, "home_stock/session/remove_line",
                          line_id=second_line["result"]["id"], idempotency_key="remove-1")
    assert removed["success"] is True


async def test_a_price_corrected_at_the_till_corrects_the_observation(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    """add_line records the price seen in the aisle; update_line used to
    record nothing at all. A suggestion accepted at 0,004 €/g and corrected
    to 0,006 €/g at the checkout therefore left 0,004 recorded against that
    shop, at rank 1 of the suggestion cascade, for every later trip."""
    entry = await setup_entry(with_article=True)
    client = await hass_ws_client(hass)

    await _send(client, 1, "home_stock/session/start", store="Leclerc")
    added = await _send(client, 2, "home_stock/session/add_line", article_id=1,
                        quantity=500, unit_price=0.004, idempotency_key="scan-1")
    await _send(client, 3, "home_stock/session/update_line",
                line_id=added["result"]["id"], unit_price=0.006)

    def latest() -> float | None:
        return repo.latest_price_in_store(
            entry.runtime_data.manager.db.read(), 1, "Leclerc")

    assert await hass.async_add_executor_job(latest) == 0.006


async def test_a_price_typed_only_at_the_till_is_recorded_at_all(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    """A line added without a price (nothing was suggested, nothing typed in
    the aisle) and priced later in the cart used to record no observation
    whatsoever — the shop's price history simply never learned it."""
    entry = await setup_entry(with_article=True)
    client = await hass_ws_client(hass)

    await _send(client, 1, "home_stock/session/start", store="Lidl")
    added = await _send(client, 2, "home_stock/session/add_line", article_id=1,
                        quantity=500, unit_price=None, idempotency_key="scan-1")
    await _send(client, 3, "home_stock/session/update_line",
                line_id=added["result"]["id"], unit_price=0.003)

    def rows() -> list[tuple]:
        return [tuple(r) for r in entry.runtime_data.manager.db.read().execute(
            "SELECT price_per_base_unit, store FROM price ORDER BY id").fetchall()]

    assert await hass.async_add_executor_job(rows) == [(0.003, "Lidl")]


async def test_re_sending_the_same_price_does_not_pile_up_observations(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    """The panel replays its offline queue in order, so the same update_line
    can arrive twice. An unchanged price must not write a second row."""
    entry = await setup_entry(with_article=True)
    client = await hass_ws_client(hass)

    await _send(client, 1, "home_stock/session/start", store="Lidl")
    added = await _send(client, 2, "home_stock/session/add_line", article_id=1,
                        quantity=500, unit_price=0.004, idempotency_key="scan-1")
    line_id = added["result"]["id"]
    await _send(client, 3, "home_stock/session/update_line", line_id=line_id,
                unit_price=0.006, idempotency_key="edit-1")
    await _send(client, 4, "home_stock/session/update_line", line_id=line_id,
                unit_price=0.006, idempotency_key="edit-1")

    def count() -> int:
        return entry.runtime_data.manager.db.read().execute(
            "SELECT COUNT(*) FROM price").fetchone()[0]

    assert await hass.async_add_executor_job(count) == 2


async def test_a_negative_price_is_refused_on_every_session_write(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    entry = await setup_entry(with_article=True)
    client = await hass_ws_client(hass)

    await _send(client, 1, "home_stock/session/start", store="Leclerc")
    refused = await _send(client, 2, "home_stock/session/add_line", article_id=1,
                          quantity=500, unit_price=-2.5, idempotency_key="scan-1")
    assert refused["success"] is False

    added = await _send(client, 3, "home_stock/session/add_line", article_id=1,
                        quantity=500, unit_price=0.004, idempotency_key="scan-2")
    corrected = await _send(client, 4, "home_stock/session/update_line",
                            line_id=added["result"]["id"], unit_price=-1.0)
    assert corrected["success"] is False

    def prices() -> list[float]:
        return [r[0] for r in entry.runtime_data.manager.db.read().execute(
            "SELECT price_per_base_unit FROM price").fetchall()]

    assert await hass.async_add_executor_job(prices) == [0.004]


async def test_closing_a_session_stops_its_leftovers_blocking_a_conversion(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    """A shopping line never put away used to block its product's unit
    conversion forever: the check counted every line with `stored_at IS
    NULL`, whatever its session's state, and a line of a closed session can
    never be removed. Giving up a trip is what `session/close` is for."""
    await setup_entry(with_piece_product=True)
    client = await hass_ws_client(hass)

    await _send(client, 1, "home_stock/session/start", store="Leclerc")
    await _send(client, 2, "home_stock/session/add_line", article_id=1,
                quantity=6, unit_price=None, idempotency_key="scan-1")

    blocked = await _send(client, 3, "home_stock/product/convert_unit", product_id=1,
                          to_unit="g", reference_quantity=125, dry_run=True)
    assert blocked["success"] is False
    assert "ligne(s) de courses" in blocked["error"]["message"]

    closed = await _send(client, 4, "home_stock/session/close")
    assert closed["success"] is True
    assert closed["result"]["state"] == "done"

    after = await _send(client, 5, "home_stock/product/convert_unit", product_id=1,
                        to_unit="g", reference_quantity=125, dry_run=True)
    assert after["success"] is True
