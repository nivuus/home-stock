"""Price observations and opening dates use the household's civil date.

Same frozen clock as tests/test_civil_date_expiry.py: 00:30 on the 15th in
Tokyo, still the 14th in UTC. Before the fix both dates were the UTC day.
"""
from freezegun import freeze_time

MIDNIGHT_AHEAD = "2026-11-14T15:30:00+00:00"


async def test_a_price_seen_after_midnight_is_dated_on_the_local_day(
        hass, setup_entry):
    await hass.config.async_set_time_zone("Asia/Tokyo")
    entry = await setup_entry(with_article=True)
    shopping = entry.runtime_data.shopping
    manager = entry.runtime_data.manager

    def _scan_then_correct():
        shopping.start(store="Konbini")
        line = shopping.add_line(article_id=1, quantity=500, unit_price=0.4,
                                 idempotency_key="k1")
        shopping.update_line(line["id"], unit_price=0.5)
        with manager.db.write() as conn:
            return [row["observed_on"] for row in conn.execute(
                "SELECT observed_on FROM price ORDER BY id")]

    with freeze_time(MIDNIGHT_AHEAD):
        observed = await hass.async_add_executor_job(_scan_then_correct)
    assert observed == ["2026-11-15", "2026-11-15"]


async def test_opening_after_midnight_counts_from_the_local_day(hass, setup_entry):
    await hass.config.async_set_time_zone("Asia/Tokyo")
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager

    def _seed():
        with manager.db.write() as conn:
            conn.execute("UPDATE product SET days_after_opening = 3 WHERE id = 1")
        return manager.add_stock(article_id=1, quantity=500.0, location_id=1,
                                 best_before="2027-01-01")

    batch_id = await hass.async_add_executor_job(_seed)
    with freeze_time(MIDNIGHT_AHEAD):
        await hass.services.async_call("home_stock", "open_batch",
                                       {"batch_id": batch_id}, blocking=True)

    def _read():
        with manager.db.write() as conn:
            return conn.execute("SELECT opened_at, best_before FROM batch"
                                " WHERE id = ?", (batch_id,)).fetchone()
    row = await hass.async_add_executor_job(_read)
    # The journal keeps UTC timestamps; only the civil date moves.
    assert row["opened_at"] == "2026-11-14T15:30:00"
    assert row["best_before"] == "2026-11-18"
