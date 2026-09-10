"""Lot 3: the `home_stock.create_product` service.

Covers R1 (registered), R2 (schema, extra field refused), R3/R4 (nominal
creation and its response), R6 (visible right after creation), R8/R9
(validation, mapped to `ServiceValidationError`) and R12 (this test's own
list of cases).

R6's own example, `home_stock.query_stock`, reads stock BATCHES
(`repositories.stock_rows`), not the product table: a freshly created
product with no batch never shows up there, exactly like a product created
through the existing barcode path before any stock is added
(`docs/inventory.md`, `## QUERY_STOCK`; the deviation is also recorded in
`docs/delivery.md`). So visibility here is checked through the panel's own
websocket surface, `home_stock/products/list` (`websocket_api.py:300-308`),
the read Maxime's UI actually calls, rather than through `query_stock`.
"""
import pytest
import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from custom_components.home_stock.aisles import AISLES
from custom_components.home_stock.storage import products as store
from custom_components.home_stock.storage import repositories as repo

RAYON = AISLES[0]


async def _create(hass, payload, response=True):
    return await hass.services.async_call(
        "home_stock", "create_product", payload, blocking=True,
        return_response=response)


async def test_service_is_registered(hass: HomeAssistant, setup_entry):
    await setup_entry()
    assert hass.services.has_service("home_stock", "create_product")


async def test_creates_a_product_without_a_barcode(hass: HomeAssistant, setup_entry):
    await setup_entry()

    answer = await _create(hass, {"name": "Mangue", "rayon": RAYON})

    assert answer["product_id"].startswith(store.PRODUCT_ID_PREFIX)
    assert answer["name"] == "Mangue"
    assert answer["rayon"] == RAYON
    assert answer["unit"] == store.DEFAULT_BASE_UNIT
    assert answer["barcode"] is None


async def test_created_product_is_visible_right_away(
        hass: HomeAssistant, setup_entry, hass_ws_client):
    entry = await setup_entry()
    await _create(hass, {"name": "Piment antillais", "rayon": RAYON})

    def _rayon_id() -> int:
        aisle = next(a for a in repo.list_aisles(entry.runtime_data.manager.db.read())
                     if a["name"] == RAYON)
        return aisle["id"]

    expected_aisle_id = await hass.async_add_executor_job(_rayon_id)

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "home_stock/products/list"})
    message = await client.receive_json()

    assert message["success"] is True
    match = next(p for p in message["result"]["products"]
                if p["name"] == "Piment antillais")
    assert match["aisle_id"] == expected_aisle_id


async def test_product_survives_an_integration_reload(hass: HomeAssistant, setup_entry):
    entry = await setup_entry()
    answer = await _create(hass, {"name": "Kimchi", "rayon": RAYON})

    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    reloaded = hass.config_entries.async_loaded_entries("home_stock")[0]

    def _read():
        return store.get_product(reloaded.runtime_data.manager.db.read(),
                                 answer["product_id"])

    product = await hass.async_add_executor_job(_read)
    assert product is not None
    assert product["name"] == "Kimchi"
    assert product["rayon"] == RAYON


async def test_rejects_a_blank_name(hass: HomeAssistant, setup_entry):
    entry = await setup_entry()

    with pytest.raises(ServiceValidationError):
        await _create(hass, {"name": "   ", "rayon": RAYON})

    def _read():
        return store.list_products(entry.runtime_data.manager.db.read())

    assert await hass.async_add_executor_job(_read) == []


async def test_rejects_a_barcode_already_in_use(hass: HomeAssistant, setup_entry):
    entry = await setup_entry()
    await _create(hass, {"name": "A", "rayon": RAYON, "barcode": "3017620422003"})

    with pytest.raises(ServiceValidationError) as excinfo:
        await _create(hass, {"name": "B", "rayon": RAYON, "barcode": "3017620422003"})

    assert "3017620422003" in str(excinfo.value)

    def _read():
        return store.list_products(entry.runtime_data.manager.db.read())

    assert len(await hass.async_add_executor_job(_read)) == 1


async def test_rejects_an_unknown_rayon(hass: HomeAssistant, setup_entry):
    await setup_entry()

    with pytest.raises(vol.Invalid) as excinfo:
        await _create(hass, {"name": "A", "rayon": "nope"})

    message = str(excinfo.value)
    for name in AISLES:
        assert name in message


async def test_rejects_an_unknown_field(hass: HomeAssistant, setup_entry):
    await setup_entry()

    with pytest.raises(vol.Invalid):
        await _create(hass, {"name": "A", "rayon": RAYON, "extra": 1})


async def test_blank_barcode_is_treated_as_absent(hass: HomeAssistant, setup_entry):
    await setup_entry()

    answer = await _create(hass, {"name": "A", "rayon": RAYON, "barcode": ""})

    assert answer["barcode"] is None


async def test_rejects_a_duplicate_name(hass: HomeAssistant, setup_entry):
    """Non-goal (spec.md): two calls with the same name create two products
    upstream (`product.name UNIQUE`, see `docs/delivery.md`), so the second
    call here must fail explicitly rather than silently create nothing."""
    entry = await setup_entry()
    await _create(hass, {"name": "Avocat", "rayon": RAYON})

    with pytest.raises(ServiceValidationError) as excinfo:
        await _create(hass, {"name": "Avocat", "rayon": RAYON})

    assert "Avocat" in str(excinfo.value)

    def _read():
        return store.list_products(entry.runtime_data.manager.db.read())

    assert len(await hass.async_add_executor_job(_read)) == 1

