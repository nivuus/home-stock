"""The `home_stock.update_product` service, called the way Developer Tools calls it.

Every test goes through Home Assistant's real service registry (or its REST
API, or the websocket the panel uses) on a real, freshly created database:
nothing is mocked. The product is the fixture's "Yaourts nature": counted in
pieces, one article of 125 g net, one open batch of 6 (ids 1, 1 and 1).
"""
import pytest
import voluptuous as vol
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.service import async_get_all_descriptions
from homeassistant.setup import async_setup_component

from custom_components.home_stock.const import DOMAIN
from custom_components.home_stock.storage import repositories as repo

FIELDS = ("product_id", "reference_kcal", "target_unit", "reference_quantity",
          "unchanged_batches", "dry_run")


async def _call(hass, data, *, response=True):
    return await hass.services.async_call(DOMAIN, "update_product", data, blocking=True,
                                          return_response=response)


async def _product(hass, entry, product_id=1):
    manager = entry.runtime_data.manager
    return await hass.async_add_executor_job(repo.get_product, manager.db.read(), product_id)


async def _rows(hass, entry):
    """Every row a correction may write, so 'nothing written' can be asserted."""
    conn = entry.runtime_data.manager.db.read()

    def read():
        return {table: [tuple(row) for row in conn.execute(f"SELECT * FROM {table}")]
                for table in ("product", "article", "batch", "movement", "packaging")}

    return await hass.async_add_executor_job(read)


# --- registration and description ---------------------------------------------

async def test_update_product_is_registered_with_its_french_description(hass, setup_entry):
    await setup_entry()
    assert hass.services.has_service(DOMAIN, "update_product")

    # The real descriptions loader: it reads services.yaml the way the
    # frontend's action editor does.
    descriptions = await async_get_all_descriptions(hass)
    described = descriptions[DOMAIN]["update_product"]
    assert described["name"] == "Corriger un produit"
    assert described["description"].startswith("Corrige un produit existant")
    assert tuple(described["fields"]) == FIELDS
    assert described["fields"]["target_unit"]["selector"]["select"]["options"] == ["g", "ml"]
    assert described["fields"]["dry_run"]["name"] == "Simuler seulement"
    # Optional response: a script may ignore it, a dry run reads it.
    assert described["response"] == {"optional": True}
    # The loader read the WHOLE file, not only this entry.
    assert descriptions[DOMAIN]["create_product"]["name"] == "Créer un produit"
    assert descriptions[DOMAIN]["skip_meal"]["name"] == "Ignorer un repas"


async def test_update_product_is_listed_by_the_rest_api(hass, hass_client, setup_entry):
    await setup_entry()
    assert await async_setup_component(hass, "api", {})
    client = await hass_client()

    response = await client.get("/api/services")

    assert response.status == 200
    domains = {item["domain"]: item["services"] for item in await response.json()}
    assert "update_product" in domains[DOMAIN]


# --- what it does ---------------------------------------------------------------

async def test_a_dry_run_answers_the_plan_and_writes_nothing(hass, setup_entry):
    entry = await setup_entry(with_piece_product=True)
    before = await _rows(hass, entry)

    answer = await _call(hass, {"product_id": 1, "target_unit": "g",
                                "reference_quantity": 125, "dry_run": True})

    assert await _rows(hass, entry) == before
    assert answer["applied"] is False
    assert answer["base_unit"] == {"before": "piece", "after": "g"}
    assert answer["conversion"]["applied"] is False
    [batch] = answer["batches_plan"]
    assert (batch["remaining_before"], batch["remaining_after"]) == (6, 750)


async def test_the_unit_and_the_kcal_are_corrected_in_one_call(hass, setup_entry):
    entry = await setup_entry(with_piece_product=True)

    answer = await _call(hass, {"product_id": 1, "target_unit": "g",
                                "reference_quantity": 125, "reference_kcal": 0.6})

    product = await _product(hass, entry)
    assert (product["base_unit"], product["reference_kcal"]) == ("g", pytest.approx(0.6))
    assert answer["applied"] is True
    assert answer["conversion"]["applied"] is True
    [batch] = answer["batches_plan"]
    assert batch["remaining_after"] == 750
    assert batch["kcal_per_base_unit_after"] == pytest.approx(0.6)


async def test_the_kcal_alone_is_written_like_the_panel_writes_it(hass, setup_entry):
    entry = await setup_entry(with_piece_product=True)

    answer = await _call(hass, {"product_id": 1, "reference_kcal": 75})

    product = await _product(hass, entry)
    assert (product["base_unit"], product["reference_kcal"]) == ("piece", 75)
    assert answer["conversion"] is None
    assert answer["reference_kcal"] == {"before": None, "after": 75}


async def test_the_call_works_without_asking_for_a_response(hass, setup_entry):
    entry = await setup_entry(with_piece_product=True)

    # An automation calls the service this way: no response requested.
    assert await _call(hass, {"product_id": 1, "reference_kcal": 75}, response=False) is None

    assert (await _product(hass, entry))["reference_kcal"] == 75


# --- what it refuses ------------------------------------------------------------

@pytest.mark.parametrize(("data", "said"), [
    ({}, "product_id est obligatoire"),
    ({"product_id": 1}, "Rien à corriger"),
    ({"product_id": 4242, "reference_kcal": 1}, "Produit 4242 inconnu."),
    ({"product_id": "un", "reference_kcal": 1}, "Un nombre entier est attendu"),
    ({"product_id": 1, "reference_kcal": -1}, "reference_kcal doit être un nombre positif"),
    ({"product_id": 1, "target_unit": "kg", "reference_quantity": 125},
     "L'unité cible doit être « g » ou « ml »"),
    ({"product_id": 1, "target_unit": "g"}, "target_unit demande reference_quantity"),
    ({"product_id": 1, "target_unit": "g", "reference_quantity": 0.1},
     "Le poids de référence doit être compris entre"),
    ({"product_id": 1, "target_unit": "g", "reference_quantity": 125,
      "unchanged_batches": [999]}, "Le lot 999 n'est pas un lot ouvert du produit 1"),
    ({"product_id": 1, "target_unit": "g", "reference_quantity": 125,
      "reference_kcal": 0.6, "dry_run": "oui"}, "dry_run doit valoir true ou false"),
])
async def test_a_wrong_call_is_refused_in_french_and_writes_nothing(
        hass, setup_entry, data, said):
    entry = await setup_entry(with_piece_product=True)
    before = await _rows(hass, entry)

    with pytest.raises(ServiceValidationError) as refused:
        await _call(hass, data)

    assert said in str(refused.value)
    assert await _rows(hass, entry) == before


async def test_an_unknown_field_is_refused(hass, setup_entry):
    await setup_entry(with_piece_product=True)
    with pytest.raises(vol.Invalid):
        await _call(hass, {"product_id": 1, "reference_kcal": 1, "kcal": 1})


# --- neither surface is weaker than the other ----------------------------------

async def _websocket_verdict(client, id_, payload):
    await client.send_json({"id": id_, **payload})
    answer = await client.receive_json()
    return "accepté" if answer.get("success") else "refusé"


async def _service_verdict(hass, data):
    try:
        await _call(hass, data)
    except (HomeAssistantError, vol.Invalid) as err:
        assert str(err)
        return "refusé"
    return "accepté"


@pytest.mark.parametrize("kcal", [-1, "beaucoup", True, "nan", "inf", 0, 2.65, "2.65", None])
async def test_the_kcal_is_refused_exactly_where_product_update_refuses_it(
        hass, setup_entry, hass_ws_client, kcal):
    await setup_entry(with_piece_product=True)
    client = await hass_ws_client(hass)

    from_websocket = await _websocket_verdict(client, 1, {
        "type": "home_stock/product/update", "product_id": 1,
        "fields": {"reference_kcal": kcal}})
    from_service = await _service_verdict(hass, {"product_id": 1, "reference_kcal": kcal})

    assert from_websocket == from_service, (
        f"product/update → {from_websocket}, update_product → {from_service}")


@pytest.mark.parametrize(("to_unit", "quantity"), [
    ("kg", 125), ("g", 0.1), ("g", 50_001), ("g", "lourd"), ("g", "inf"),
    ("g", 125), ("ml", 0.5), ("g", "125"),
])
async def test_the_unit_is_refused_exactly_where_convert_unit_refuses_it(
        hass, setup_entry, hass_ws_client, to_unit, quantity):
    """Dry runs on both sides, so an accepted case leaves the product as it was
    for the other surface."""
    await setup_entry(with_piece_product=True)
    client = await hass_ws_client(hass)

    from_websocket = await _websocket_verdict(client, 1, {
        "type": "home_stock/product/convert_unit", "product_id": 1,
        "to_unit": to_unit, "reference_quantity": quantity, "dry_run": True})
    from_service = await _service_verdict(hass, {
        "product_id": 1, "target_unit": to_unit, "reference_quantity": quantity,
        "dry_run": True})

    assert from_websocket == from_service, (
        f"product/convert_unit → {from_websocket}, update_product → {from_service}")
