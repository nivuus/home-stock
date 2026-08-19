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
    assert hass.states.get("sensor.home_stock_to_store").state == "1"


async def test_the_cart_sensors_are_zero_with_no_session(hass: HomeAssistant, setup_entry):
    await setup_entry()
    await hass.async_block_till_done()

    assert hass.states.get("sensor.home_stock_cart_total").state == "0.0"
    assert hass.states.get("sensor.home_stock_to_store").state == "0"
