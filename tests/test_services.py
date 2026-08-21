import sqlite3
from unittest.mock import AsyncMock

import pytest
import voluptuous as vol
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.service import async_get_all_descriptions
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.home_stock.const import DOMAIN
from custom_components.home_stock.storage import repositories as repo


def _write_empty_grocy(path: str) -> None:
    """A structurally valid but empty grocy.db — enough for the import to run
    end to end without needing real catalogue data, to exercise the service
    itself (schema, response shape, refresh gating) rather than import_catalog's
    own logic, which tests/test_import_grocy.py already covers.
    """
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE quantity_units (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE locations (id INTEGER PRIMARY KEY, name TEXT, is_freezer INTEGER);
        CREATE TABLE product_groups (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE products (
            id INTEGER PRIMARY KEY, name TEXT, active INTEGER, product_group_id INTEGER,
            location_id INTEGER, qu_id_stock INTEGER, min_stock_amount REAL,
            calories REAL, default_best_before_days_after_open INTEGER,
            picture_file_name TEXT);
        CREATE TABLE product_barcodes (
            id INTEGER PRIMARY KEY, product_id INTEGER, barcode TEXT, qu_id INTEGER,
            amount REAL, last_price REAL);
        CREATE TABLE userfields (id INTEGER PRIMARY KEY, entity TEXT, name TEXT);
        CREATE TABLE userfield_values (
            id INTEGER PRIMARY KEY, field_id INTEGER, object_id INTEGER, value TEXT);
    """)
    conn.commit()
    conn.close()


@pytest.fixture
async def seeded(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    manager = entry.runtime_data.manager

    def _seed() -> dict[str, int]:
        with manager.db.write() as conn:
            location_id = repo.insert_location(conn, name="Placard", kind="pantry")
            product_id = repo.insert_product(conn, name="Pâtes", base_unit="g")
            article_id = repo.insert_article(conn, product_id=product_id,
                                             kcal_per_base_unit=3.5)
            repo.link_barcode(conn, "3038350201553", article_id)
        return {"location_id": location_id, "product_id": product_id,
                "article_id": article_id}

    ids = await hass.async_add_executor_job(_seed)
    return entry, ids


async def test_add_stock_accepts_a_barcode(hass, seeded):
    entry, ids = seeded
    await hass.services.async_call(DOMAIN, "add_stock", {
        "barcode": "3038350201553", "quantity": 500,
        "location_id": ids["location_id"], "price_per_base_unit": 0.004,
    }, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.home_stock_batches").state == "1"


async def test_add_stock_requires_an_article_id_or_a_barcode(hass, seeded):
    """Neither field is required on its own (vol.Exclusive only forbids giving
    both), so without this the call would reach the service handler with
    article_id=None, resolve barcode=None too, and answer the confusing
    "Code-barres None inconnu" — caught here at schema validation instead."""
    entry, ids = seeded
    with pytest.raises(vol.Invalid, match="at least one of"):
        await hass.services.async_call(DOMAIN, "add_stock", {
            "quantity": 1, "location_id": ids["location_id"],
        }, blocking=True)


async def test_add_stock_rejects_an_unknown_barcode(hass, seeded):
    entry, ids = seeded
    # Creating an article from an EAN needs Open Food Facts: that is lot 1.
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(DOMAIN, "add_stock", {
            "barcode": "0000000000000", "quantity": 1,
            "location_id": ids["location_id"],
        }, blocking=True)


# --- Fix round 4: services must not be the weaker surface ------------------
# The websocket commands refuse "inf"/"nan" and an out-of-64-bit id before
# they ever reach SQL (see tests/test_websocket_write.py); a service call —
# an automation, a voice command through Bleuenn — used to have no such
# guard and could write the exact same Inf/NaN into the append-only journal,
# or crash uncaught on an id past 64 bits.

async def test_add_stock_rejects_an_infinite_quantity(hass, seeded):
    entry, ids = seeded
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(DOMAIN, "add_stock", {
            "article_id": ids["article_id"], "quantity": "inf",
            "location_id": ids["location_id"],
        }, blocking=True)


async def test_add_stock_rejects_an_infinite_price(hass, seeded):
    entry, ids = seeded
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(DOMAIN, "add_stock", {
            "article_id": ids["article_id"], "quantity": 100,
            "location_id": ids["location_id"], "price_per_base_unit": "inf",
        }, blocking=True)


async def test_add_stock_rejects_an_infinite_packaging_quantity(hass, seeded):
    entry, ids = seeded
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(DOMAIN, "add_stock", {
            "article_id": ids["article_id"], "quantity": 1,
            "location_id": ids["location_id"], "packaging_base_quantity": "inf",
        }, blocking=True)


async def test_adjust_inventory_rejects_a_non_finite_counted_quantity(hass, seeded):
    entry, ids = seeded
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(DOMAIN, "adjust_inventory", {
            "article_id": ids["article_id"], "location_id": ids["location_id"],
            "counted_quantity": "nan",
        }, blocking=True)


async def test_add_stock_rejects_an_id_larger_than_64_bits(hass, seeded):
    entry, ids = seeded
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(DOMAIN, "add_stock", {
            "article_id": 2**64, "quantity": 1,
            "location_id": ids["location_id"],
        }, blocking=True)


async def test_consume_rejects_an_id_larger_than_64_bits(hass, seeded):
    entry, ids = seeded
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(DOMAIN, "consume", {
            "product_id": 2**64, "quantity": 1,
        }, blocking=True)


async def test_consume_rejects_a_negative_product_id(hass, seeded):
    """No real row has a negative id: refused at the schema, the same as the
    websocket surface (correction round 1 pin — see
    tests/test_websocket_consume.py::test_consume_refuses_a_negative_product_id)."""
    entry, ids = seeded
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(DOMAIN, "consume", {
            "product_id": -1, "quantity": 1,
        }, blocking=True)


# --- Fix round 5: best_before must not be able to disable the pantry -------
# A bad best_before used to be accepted by cv.string, stored verbatim, and
# from that moment application.py's summary() raised ValueError on every
# coordinator refresh — every sensor and the todo entity went unavailable
# and stayed there, in an append-only table nothing in the integration can
# repair. This household drives add_stock from automations and from a voice
# assistant, so a template rendering to anything but a date is not
# hypothetical.

async def test_add_stock_with_an_invalid_best_before_does_not_disable_the_pantry(hass, seeded):
    """Pins the actual failure, not just the refusal: the entities must
    still be available afterwards — that is what was at stake, not merely
    that the call itself failed."""
    entry, ids = seeded
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(DOMAIN, "add_stock", {
            "article_id": ids["article_id"], "quantity": 100,
            "location_id": ids["location_id"], "best_before": "pas une date",
        }, blocking=True)
    await hass.async_block_till_done()

    for entity_id in ("sensor.home_stock_batches", "sensor.home_stock_stock_value",
                      "sensor.home_stock_kcal_total", "binary_sensor.home_stock_expirations"):
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state != "unavailable"


async def test_add_stock_rejects_a_compact_date(hass, seeded):
    """date.fromisoformat has accepted the compact form ("20261201") since
    Python 3.11; SQLite's julianday() then returns NULL for it, silently
    dropping the batch from shelf-life learning and from the
    first-expiring-first ordering. Only the extended AAAA-MM-JJ form the
    error message promises is accepted."""
    entry, ids = seeded
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(DOMAIN, "add_stock", {
            "article_id": ids["article_id"], "quantity": 1,
            "location_id": ids["location_id"], "best_before": "20261201",
        }, blocking=True)


async def test_add_stock_rejects_a_week_form_date(hass, seeded):
    entry, ids = seeded
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(DOMAIN, "add_stock", {
            "article_id": ids["article_id"], "quantity": 1,
            "location_id": ids["location_id"], "best_before": "2026-W01-1",
        }, blocking=True)


async def test_add_stock_rejects_an_overlong_idempotency_key(hass, seeded):
    entry, ids = seeded
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(DOMAIN, "add_stock", {
            "article_id": ids["article_id"], "quantity": 1,
            "location_id": ids["location_id"], "idempotency_key": "x" * 500_000,
        }, blocking=True)


async def test_consume_rejects_an_overlong_idempotency_key(hass, seeded):
    entry, ids = seeded
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(DOMAIN, "consume", {
            "product_id": ids["product_id"], "quantity": 1,
            "idempotency_key": "x" * 500_000,
        }, blocking=True)


async def test_consume_reports_insufficient_stock_as_a_home_assistant_error(hass, seeded):
    entry, ids = seeded
    await hass.services.async_call(DOMAIN, "add_stock", {
        "article_id": ids["article_id"], "quantity": 100,
        "location_id": ids["location_id"],
    }, blocking=True)
    with pytest.raises(HomeAssistantError, match="Stock insuffisant"):
        await hass.services.async_call(DOMAIN, "consume", {
            "product_id": ids["product_id"], "quantity": 500,
        }, blocking=True)


async def test_consume_reports_an_unknown_product_as_a_home_assistant_error(hass, seeded):
    """StockManager.consume's FIFO path (no batch_id) calls
    repo.product_base_unit(conn, product_id) directly on the caller's own
    id, before any existence check — it raises a bare `LookupError`, not a
    `ValueError`. `_run` used to only translate the `ValueError` family, so
    a well-formed but nonexistent product_id (a deleted product an
    automation still references) escaped as a raw Python exception instead
    of the French refusal the websocket surface already gives for the same
    case. Pins both: a HomeAssistantError, in French, not a bare
    LookupError."""
    entry, ids = seeded
    with pytest.raises(HomeAssistantError) as refusal:
        await hass.services.async_call(DOMAIN, "consume", {
            "product_id": 999, "quantity": 1,
        }, blocking=True)
    assert str(refusal.value) == "Produit 999 inconnu."


async def test_consume_rejects_a_reason_not_meant_for_consumption(hass, seeded):
    entry, ids = seeded
    # "purchase"/"inventory"/"transfer" are written by other services; letting
    # consume() carry them would silently escape the reasons totals_between
    # tracks, and under-count the kcal/cost/cost_waste totals for stock that
    # really left the pantry.
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(DOMAIN, "consume", {
            "product_id": ids["product_id"], "quantity": 1, "reason": "purchase",
        }, blocking=True)


async def test_the_consume_service_records_the_parts(hass, setup_entry):
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager
    await hass.async_add_executor_job(
        lambda: manager.add_stock(article_id=1, quantity=800.0, location_id=1))

    await hass.services.async_call(DOMAIN, "consume", {
        "product_id": 1, "quantity": 400.0, "parts_total": 4, "parts_mine": 1,
    }, blocking=True)

    row = await hass.async_add_executor_job(lambda: manager.db.read().execute(
        "SELECT parts_total, parts_mine FROM movement"
        " WHERE reason = 'consumption'").fetchone())
    assert (row["parts_total"], row["parts_mine"]) == (4, 1)


async def test_the_consume_service_refuses_impossible_parts(hass, setup_entry):
    """The same rule as the websocket surface, on the oldest surface."""
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager
    await hass.async_add_executor_job(
        lambda: manager.add_stock(article_id=1, quantity=800.0, location_id=1))

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(DOMAIN, "consume", {
            "product_id": 1, "quantity": 100.0, "parts_total": 2, "parts_mine": 3,
        }, blocking=True)


@pytest.mark.parametrize("value", [1.5, "2", -1, 25])
async def test_the_consume_service_refuses_a_parts_value_the_schema_rejects(
        hass, setup_entry, value):
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager
    await hass.async_add_executor_job(
        lambda: manager.add_stock(article_id=1, quantity=800.0, location_id=1))

    with pytest.raises((vol.Invalid, HomeAssistantError)):
        await hass.services.async_call(DOMAIN, "consume", {
            "product_id": 1, "quantity": 100.0, "parts_total": value, "parts_mine": 1,
        }, blocking=True)


async def test_the_consume_service_refuses_a_negative_quantity_on_a_batch(
        hass, setup_entry):
    """Same guard as the websocket surface (test_websocket_consume.py::
    test_consume_batch_refuses_a_negative_quantity): the service's own
    finite_float schema lets a negative quantity through, so the floor has
    to live in StockManager.consume_batch itself."""
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager
    batch_id = await hass.async_add_executor_job(
        lambda: manager.add_stock(article_id=1, quantity=200.0, location_id=1))

    with pytest.raises(HomeAssistantError, match="positive"):
        await hass.services.async_call(DOMAIN, "consume", {
            "product_id": 1, "quantity": -50.0, "batch_id": batch_id,
        }, blocking=True)

    row = await hass.async_add_executor_job(lambda: manager.db.read().execute(
        "SELECT remaining FROM batch WHERE id = ?", (batch_id,)).fetchone())
    assert row["remaining"] == 200.0


async def test_the_consume_service_can_target_one_batch(hass, setup_entry):
    entry = await setup_entry(with_article=True)
    manager = entry.runtime_data.manager
    old = await hass.async_add_executor_job(
        lambda: manager.add_stock(article_id=1, quantity=100.0, location_id=1))
    recent = await hass.async_add_executor_job(
        lambda: manager.add_stock(article_id=1, quantity=100.0, location_id=1))

    await hass.services.async_call(DOMAIN, "consume", {
        "product_id": 1, "quantity": 50.0, "batch_id": recent,
    }, blocking=True)

    remaining = await hass.async_add_executor_job(lambda: dict(
        manager.db.read().execute("SELECT id, remaining FROM batch ORDER BY id")
        .fetchall()[1]))
    assert remaining["remaining"] == 50.0


async def test_query_stock_returns_a_response(hass, seeded):
    entry, ids = seeded
    await hass.services.async_call(DOMAIN, "add_stock", {
        "article_id": ids["article_id"], "quantity": 500,
        "location_id": ids["location_id"],
    }, blocking=True)
    response = await hass.services.async_call(
        DOMAIN, "query_stock", {"name": "pât"}, blocking=True, return_response=True
    )
    assert response["products"][0]["display"] == "500 g"


async def test_export_journal_returns_the_movements(hass, seeded):
    entry, ids = seeded
    await hass.services.async_call(DOMAIN, "add_stock", {
        "article_id": ids["article_id"], "quantity": 500,
        "location_id": ids["location_id"],
    }, blocking=True)
    response = await hass.services.async_call(
        DOMAIN, "export_journal", {}, blocking=True, return_response=True
    )
    assert [m["reason"] for m in response["movements"]] == ["purchase"]


async def test_the_state_refreshes_right_after_a_write(hass, seeded):
    entry, ids = seeded
    await hass.services.async_call(DOMAIN, "add_stock", {
        "article_id": ids["article_id"], "quantity": 500,
        "location_id": ids["location_id"],
    }, blocking=True)
    await hass.async_block_till_done()
    # No waiting for the 15-minute poll: a write refreshes immediately.
    assert hass.states.get("sensor.home_stock_batches").state == "1"


async def test_import_grocy_catalog_is_response_only(hass, seeded):
    entry, ids = seeded
    _write_empty_grocy(hass.config.path("grocy_import.db"))
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "import_grocy_catalog", {"path": "grocy_import.db"}, blocking=True,
        )


async def test_import_grocy_catalog_schema_defaults(hass, seeded):
    entry, ids = seeded
    # The default path ("grocy_import.db") is relative to the config directory.
    _write_empty_grocy(hass.config.path("grocy_import.db"))
    response = await hass.services.async_call(
        DOMAIN, "import_grocy_catalog", {}, blocking=True, return_response=True,
    )
    assert response == {
        "products": 0, "articles": 0, "barcodes": 0, "prices": 0,
        "categories": 0, "locations": 0, "skipped": 0, "anomalies": [], "ok": True,
    }


async def test_import_grocy_catalog_dry_run_does_not_refresh_the_coordinator(hass, seeded):
    entry, ids = seeded
    _write_empty_grocy(hass.config.path("grocy_import.db"))
    entry.runtime_data.coordinator.async_request_refresh = AsyncMock()
    await hass.services.async_call(
        DOMAIN, "import_grocy_catalog", {"path": "grocy_import.db"},
        blocking=True, return_response=True,
    )
    entry.runtime_data.coordinator.async_request_refresh.assert_not_called()


async def test_import_grocy_catalog_apply_refreshes_the_coordinator(hass, seeded):
    entry, ids = seeded
    _write_empty_grocy(hass.config.path("grocy_import.db"))
    entry.runtime_data.coordinator.async_request_refresh = AsyncMock()
    await hass.services.async_call(
        DOMAIN, "import_grocy_catalog", {"path": "grocy_import.db", "apply": True},
        blocking=True, return_response=True,
    )
    entry.runtime_data.coordinator.async_request_refresh.assert_called_once()


async def test_services_yaml_parses_for_every_service(hass, seeded):
    # A single invalid selector (e.g. a number `step` below Home Assistant's
    # floor) makes HA discard services.yaml wholesale: every service falls
    # back to its bare name with no French description or fields, silently,
    # with only a WARNING in the log. This regresses that failure mode by
    # asserting the real descriptions loader actually produced our text.
    descriptions = await async_get_all_descriptions(hass)
    assert descriptions[DOMAIN]["add_stock"]["name"] == "Ajouter au stock"
    assert descriptions[DOMAIN]["add_stock"]["description"] == (
        "Crée un lot et son mouvement d'achat."
    )
    assert (
        descriptions[DOMAIN]["add_stock"]["fields"]["price_per_base_unit"]["name"]
        == "Prix par unité de base"
    )
    for service in (
        "add_stock", "consume", "open_batch", "transfer_batch",
        "adjust_inventory", "query_stock", "export_journal", "import_grocy_catalog",
        "resync_off",
    ):
        assert descriptions[DOMAIN][service]["name"], service


async def test_a_domain_refusal_reaches_the_service_caller_in_french(hass, seeded):
    """`services._run` re-raised `str(error)` — the domain's English original
    ("unknown article 999") — into a notification or a voice answer, while
    its own comment claimed it matched the websocket surface's wording. Both
    now translate through `messages.py`, one vocabulary."""
    entry, ids = seeded
    with pytest.raises(HomeAssistantError) as refusal:
        await hass.services.async_call(DOMAIN, "add_stock", {
            "article_id": 999, "quantity": 100, "location_id": ids["location_id"],
        }, blocking=True)

    assert str(refusal.value) == "Article 999 inconnu."


async def test_add_stock_rejects_a_negative_price(hass, seeded):
    """The same rule as the websocket surface: a price is never negative, on
    any surface that writes one into the append-only journal."""
    entry, ids = seeded
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(DOMAIN, "add_stock", {
            "article_id": ids["article_id"], "quantity": 100,
            "location_id": ids["location_id"], "price_per_base_unit": -2.5,
        }, blocking=True)
