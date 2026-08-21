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


async def test_consume_refuses_a_negative_product_id(hass, hass_ws_client, setup_entry):
    """No real row has a negative id: refused AT THE SCHEMA, the same as the
    services surface (correction round 1 pin — see
    tests/test_services.py::test_consume_rejects_a_negative_product_id).

    Asserts the error code specifically (`invalid_format`, voluptuous's own
    schema-rejection code), not just `success is False`: before this fix,
    product_id went through the bare `_bounded_int` (no floor), so -1
    passed schema validation, reached `StockManager.consume`, and only
    failed once `repo.product_base_unit` raised `LookupError("no product
    -1")` — a message the `no product (\\d+)` pattern in messages.py does
    not match (no digit for a `-`), so it fell through to the generic
    `invalid_value` / "Valeur invalide." A plain `not success` assertion
    would have stayed green through that whole detour, hiding exactly the
    asymmetry this test exists to catch."""
    await setup_entry(with_article=True)
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({
        "type": "home_stock/stock/consume", "product_id": -1, "quantity": 1.0})
    answer = await client.receive_json()
    assert not answer["success"]
    assert answer["error"]["code"] == "invalid_format"


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


async def test_consume_batch_refuses_a_negative_quantity(hass, hass_ws_client,
                                                          setup_entry):
    """The batch-targeted branch of stock/consume used to have no lower
    bound: a negative quantity passed the schema (_finite_float allows any
    sign) and StockManager.consume_batch computed `remaining_after` above
    the stock actually on hand, growing the batch instead of shrinking it.
    Pins the same floor the FIFO branch already gets from domain.stock.allocate."""
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager
    batch_id = await hass.async_add_executor_job(
        lambda: manager.add_stock(article_id=1, quantity=200.0, location_id=1))
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({
        "type": "home_stock/stock/consume", "product_id": 1, "quantity": -50.0,
        "batch_id": batch_id})
    answer = await client.receive_json()

    assert not answer["success"]
    assert answer["error"]["code"] == "invalid_value"
    row = await hass.async_add_executor_job(lambda: manager.db.read().execute(
        "SELECT remaining FROM batch WHERE id = ?", (batch_id,)).fetchone())
    assert row["remaining"] == 200.0
    count = await hass.async_add_executor_job(lambda: manager.db.read().execute(
        "SELECT COUNT(*) AS n FROM movement WHERE reason = 'consumption'").fetchone())
    assert count["n"] == 0


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
    serving — proven by making both sources available at once, with
    different values, so the priority between them is actually exercised.

    A prior version of this test only ever populated one source at a time
    (serving_quantity alone, or three consumptions alone), so it passed
    just as well with the priority order flipped — the very thing it
    claimed to guard. Both are seeded here, with distinct numbers, so
    asserting the learned value specifically proves the ordering.
    """
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager
    await hass.async_add_executor_job(
        lambda: manager.add_stock(article_id=1, quantity=2000.0, location_id=1))

    def _set_the_off_serving():
        with manager.db.write() as conn:
            conn.execute("UPDATE article SET serving_quantity = 200 WHERE id = 1")
    await hass.async_add_executor_job(_set_the_off_serving)

    # Three different consumptions: the median (80) must not be confused
    # with a value that would also satisfy a mean, a last-value, or a
    # first-value implementation.
    for quantity in (70.0, 80.0, 90.0):
        await hass.async_add_executor_job(
            lambda quantity=quantity: manager.consume(product_id=1, quantity=quantity))
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "home_stock/product/get", "product_id": 1})
    result = (await client.receive_json())["result"]
    assert result["suggested_portion"] == 80.0
    assert result["portion_source"] == "learned"


# --- Lot 2bis : la portion manuelle prime, et le bac de l'emballage ----------

async def _seed_500g(hass, entry):
    manager = entry.runtime_data.manager
    await hass.async_add_executor_job(
        lambda: manager.add_stock(article_id=1, quantity=500.0, location_id=1))
    return manager


async def _write(hass, manager, sql, *params):
    def _work():
        with manager.db.write() as conn:
            conn.execute(sql, params)
    await hass.async_add_executor_job(_work)


async def test_a_manual_portion_beats_the_learned_and_the_declared_one(
        hass, hass_ws_client, setup_entry):
    """Une valeur SAISIE par une personne l'emporte toujours sur une valeur
    déduite, sinon la saisie n'a servi à rien — même règle que
    `article.manual_fields` face à une resynchronisation."""
    entry = await setup_entry(with_article=True)
    manager = await _seed_500g(hass, entry)
    await _write(hass, manager, "UPDATE article SET serving_quantity = 200 WHERE id = 1")
    for quantity in (70.0, 80.0, 90.0):
        await hass.async_add_executor_job(
            lambda quantity=quantity: manager.consume(product_id=1, quantity=quantity))
    await _write(hass, manager, "UPDATE product SET manual_portion = 45 WHERE id = 1")
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "home_stock/product/get", "product_id": 1})
    result = (await client.receive_json())["result"]

    assert result["suggested_portion"] == 45.0
    assert result["portion_source"] == "manual"
    assert result["product"]["manual_portion"] == 45.0


async def test_clearing_the_manual_portion_gives_the_learned_one_back(
        hass, hass_ws_client, setup_entry):
    entry = await setup_entry(with_article=True)
    manager = await _seed_500g(hass, entry)
    for quantity in (70.0, 80.0, 90.0):
        await hass.async_add_executor_job(
            lambda quantity=quantity: manager.consume(product_id=1, quantity=quantity))
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({
        "type": "home_stock/product/update", "product_id": 1,
        "fields": {"manual_portion": 45}})
    assert (await client.receive_json())["success"]
    await client.send_json_auto_id({
        "type": "home_stock/product/update", "product_id": 1,
        "fields": {"manual_portion": None}})
    assert (await client.receive_json())["success"]

    await client.send_json_auto_id({"type": "home_stock/product/get", "product_id": 1})
    result = (await client.receive_json())["result"]
    assert result["portion_source"] == "learned"
    assert result["product"]["manual_portion"] is None


async def test_the_packaging_comes_from_the_fifo_batch_article(
        hass, hass_ws_client, setup_entry):
    entry = await setup_entry(with_article=True)
    manager = await _seed_500g(hass, entry)
    await _write(hass, manager,
                 "UPDATE article SET off_raw = ? WHERE id = 1",
                 '{"packagings": [{"material": "en:glass"},'
                 ' {"material": "en:metal"}]}')
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "home_stock/product/get", "product_id": 1})
    result = (await client.receive_json())["result"]

    assert result["packaging"] == {"bins": ["yellow", "glass"],
                                   "materials": ["en:glass", "en:metal"]}


async def test_no_batch_or_no_packaging_answers_null_without_an_error(
        hass, hass_ws_client, setup_entry):
    """Rien de connu → rien d'affiché : c'est un confort d'affichage, jamais
    une donnée dont dépend le stock."""
    entry = await setup_entry(with_article=True)
    client = await hass_ws_client(hass)

    # Aucun lot ouvert.
    await client.send_json_auto_id({"type": "home_stock/product/get", "product_id": 1})
    assert (await client.receive_json())["result"]["packaging"] is None

    # Un lot, mais une fiche sans emballage.
    manager = await _seed_500g(hass, entry)
    await _write(hass, manager,
                 "UPDATE article SET off_raw = ? WHERE id = 1",
                 '{"product_name": "Riz"}')
    await client.send_json_auto_id({"type": "home_stock/product/get", "product_id": 1})
    assert (await client.receive_json())["result"]["packaging"] is None
