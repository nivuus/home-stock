"""Consumption and the journal, as seen from the panel."""
import pytest


async def test_consume_takes_from_the_fifo_batch(hass, hass_ws_client, setup_entry):
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager
    await hass.async_add_executor_job(
        lambda: manager.add_stock(article_id=1, quantity=500.0, location_id=1))
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({
        "type": "home_stock/stock/consume", "product_id": 1, "quantity": 200.0})
    answer = await client.receive_json()

    assert answer["success"]
    assert len(answer["result"]["movement_ids"]) == 1


async def test_consume_records_the_parts(hass, hass_ws_client, setup_entry):
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager
    await hass.async_add_executor_job(
        lambda: manager.add_stock(article_id=1, quantity=500.0, location_id=1))
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({
        "type": "home_stock/stock/consume", "product_id": 1, "quantity": 400.0,
        "parts_total": 4, "parts_mine": 1})
    assert (await client.receive_json())["success"]

    row = await hass.async_add_executor_job(lambda: manager.db.read().execute(
        "SELECT parts_total, parts_mine FROM movement"
        " WHERE reason = 'consumption'").fetchone())
    assert (row["parts_total"], row["parts_mine"]) == (4, 1)


async def test_consume_refuses_more_parts_eaten_than_served(hass, hass_ws_client,
                                                            setup_entry):
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager
    await hass.async_add_executor_job(
        lambda: manager.add_stock(article_id=1, quantity=500.0, location_id=1))
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({
        "type": "home_stock/stock/consume", "product_id": 1, "quantity": 100.0,
        "parts_total": 2, "parts_mine": 3})
    answer = await client.receive_json()

    assert not answer["success"]
    # A message a shopper standing in the kitchen could read as-is.
    assert answer["error"]["code"] in ("invalid_field", "invalid_value")


async def test_consume_refuses_a_batch_of_another_product(hass, hass_ws_client,
                                                          setup_entry):
    """The inconsistent pair is refused rather than trusting either side of it."""
    entry = await setup_entry(with_article=True, with_piece_product=True)
    manager = entry.runtime_data.manager
    batch_id = await hass.async_add_executor_job(
        lambda: manager.add_stock(article_id=1, quantity=500.0, location_id=1))
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({
        "type": "home_stock/stock/consume", "product_id": 2, "quantity": 1.0,
        "batch_id": batch_id})
    answer = await client.receive_json()
    assert not answer["success"]


async def test_consume_is_idempotent(hass, hass_ws_client, setup_entry):
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager
    await hass.async_add_executor_job(
        lambda: manager.add_stock(article_id=1, quantity=500.0, location_id=1))
    client = await hass_ws_client(hass)

    for _ in range(2):
        await client.send_json_auto_id({
            "type": "home_stock/stock/consume", "product_id": 1, "quantity": 100.0,
            "idempotency_key": "abc"})
        assert (await client.receive_json())["success"]

    count = await hass.async_add_executor_job(lambda: manager.db.read().execute(
        "SELECT COUNT(*) FROM movement WHERE reason = 'consumption'").fetchone()[0])
    assert count == 1


async def test_consume_refuses_an_insufficient_stock_in_french(hass, hass_ws_client,
                                                               setup_entry):
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager
    await hass.async_add_executor_job(
        lambda: manager.add_stock(article_id=1, quantity=50.0, location_id=1))
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({
        "type": "home_stock/stock/consume", "product_id": 1, "quantity": 500.0})
    answer = await client.receive_json()
    assert not answer["success"]
    assert not answer["error"]["message"].isascii() or "stock" in answer["error"]["message"]


async def test_journal_day_answers_the_current_food_day(hass, hass_ws_client,
                                                        setup_entry):
    await setup_entry()
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "home_stock/journal/day"})
    answer = await client.receive_json()
    assert answer["success"]
    assert set(answer["result"]) >= {"food_day", "start", "end", "entries", "totals"}


async def test_journal_series_refuses_an_unknown_granularity(hass, hass_ws_client,
                                                             setup_entry):
    await setup_entry()
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({
        "type": "home_stock/journal/series", "granularity": "fortnight", "count": 3})
    assert not (await client.receive_json())["success"]


async def test_journal_series_bounds_the_count(hass, hass_ws_client, setup_entry):
    """Twelve months of bars, not ten thousand: the command bounds it rather
    than trusting the client."""
    await setup_entry()
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({
        "type": "home_stock/journal/series", "granularity": "day", "count": 5000})
    assert not (await client.receive_json())["success"]


async def test_product_get_carries_the_portion_and_the_next_batch(hass, hass_ws_client,
                                                                  setup_entry):
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager
    await hass.async_add_executor_job(
        lambda: manager.add_stock(article_id=1, quantity=500.0, location_id=1))
    def _set_the_portion():
        # `with`, not `.__enter__()`: the database's write lock is not
        # reentrant, and a transaction left open would block the rest of the
        # test silently.
        with manager.db.write() as conn:
            conn.execute("UPDATE article SET serving_quantity = 125 WHERE id = 1")
    await hass.async_add_executor_job(_set_the_portion)
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "home_stock/product/get", "product_id": 1})
    result = (await client.receive_json())["result"]

    assert result["suggested_portion"] == 125.0
    assert result["portion_source"] == "serving"
    assert result["next_batch"]["remaining"] == 500.0


async def test_the_learned_portion_beats_the_open_food_facts_one(hass, hass_ws_client,
                                                                 setup_entry):
    """What the owner actually eats beats what the manufacturer calls a
    serving."""
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager
    await hass.async_add_executor_job(
        lambda: manager.add_stock(article_id=1, quantity=2000.0, location_id=1))
    for _ in range(3):
        await hass.async_add_executor_job(
            lambda: manager.consume(product_id=1, quantity=80.0))
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "home_stock/product/get", "product_id": 1})
    result = (await client.receive_json())["result"]
    assert result["suggested_portion"] == 80.0
    assert result["portion_source"] == "learned"
