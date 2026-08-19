"""The write commands, through a real Home Assistant websocket connection."""
import json

import pytest
from homeassistant.core import HomeAssistant

from custom_components.home_stock.off.client import OffLookup, OffRecord

from conftest import setup_entry


class FakeOffClient:
    """Stands in for the cascade. Nothing here reaches the network."""

    def __init__(self, record: OffRecord | None = None, throttled: bool = False):
        self.result = OffLookup(record=record, throttled=throttled)
        self.codes: list[str] = []

    async def lookup(self, code: str) -> OffLookup:
        self.codes.append(code)
        return self.result

    async def lookup_with_retry(self, code: str, **kwargs) -> OffLookup:
        return await self.lookup(code)


MUESLI = OffRecord("3229820129488", "food", {
    "code": "3229820129488",
    "product_name_fr": "Muesli Raisin, Figue, Datte, Abricot",
    "generic_name_fr": "Muesli",
    "brands": "Bjorg",
    "product_quantity": 375,
    "product_quantity_unit": "g",
    "nutriscore_grade": "a",
    "categories_tags": ["en:plant-based-foods", "en:breakfasts", "en:breakfast-cereals"],
    "nutrition_data_per": "100g",
    "nutriments": {"energy-kcal_100g": 360, "proteins_100g": 9, "carbohydrates_100g": 60,
                   "fat_100g": 6, "salt_100g": 0.02},
})


async def test_an_unknown_barcode_comes_back_with_its_off_card(hass: HomeAssistant,
                                                               hass_ws_client):
    entry = await setup_entry(hass)
    entry.runtime_data.off_client = FakeOffClient(MUESLI)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/lookup",
                            "code": "3229820129488"})
    result = (await client.receive_json())["result"]

    assert result["known"] is False
    assert result["off"]["label"] == "Muesli Raisin, Figue, Datte, Abricot"
    assert result["off"]["net_quantity"] == 375
    assert result["off"]["aisle"] == "Petit-déjeuner"
    assert result["off"]["nutriscore"] == "a"


async def test_a_lookup_never_writes(hass: HomeAssistant, hass_ws_client):
    entry = await setup_entry(hass)
    entry.runtime_data.off_client = FakeOffClient(MUESLI)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/lookup", "code": "3229820129488"})
    await client.receive_json()

    def count() -> int:
        return entry.runtime_data.database.read().execute(
            "SELECT COUNT(*) FROM article").fetchone()[0]

    assert await hass.async_add_executor_job(count) == 0


async def test_a_throttled_lookup_says_so_instead_of_pretending(hass: HomeAssistant,
                                                                hass_ws_client):
    entry = await setup_entry(hass)
    entry.runtime_data.off_client = FakeOffClient(throttled=True)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/lookup", "code": "123"})
    result = (await client.receive_json())["result"]

    assert result["throttled"] is True
    assert result["off"] is None


async def test_creating_an_article_attaches_it_and_remembers_the_barcode(
        hass: HomeAssistant, hass_ws_client):
    entry = await setup_entry(hass)
    entry.runtime_data.off_client = FakeOffClient(MUESLI)
    client = await hass_ws_client(hass)

    await client.send_json({
        "id": 1, "type": "home_stock/article/create",
        "code": "3229820129488",
        "new_product": {"name": "Muesli", "base_unit": "g"},
        "off": MUESLI.product, "off_source": "food",
    })
    created = (await client.receive_json())["result"]

    await client.send_json({"id": 2, "type": "home_stock/lookup", "code": "3229820129488"})
    again = (await client.receive_json())["result"]

    assert again["known"] is True
    assert again["article"]["id"] == created["article_id"]
    assert again["product"]["name"] == "Muesli"


async def test_a_created_article_carries_its_nutrition_per_base_unit(
        hass: HomeAssistant, hass_ws_client):
    entry = await setup_entry(hass)
    client = await hass_ws_client(hass)

    await client.send_json({
        "id": 1, "type": "home_stock/article/create", "code": "3229820129488",
        "new_product": {"name": "Muesli", "base_unit": "g"},
        "off": MUESLI.product, "off_source": "food",
    })
    created = (await client.receive_json())["result"]

    def kcal() -> float:
        return entry.runtime_data.database.read().execute(
            "SELECT kcal_per_base_unit FROM article WHERE id = ?",
            (created["article_id"],)).fetchone()[0]

    assert await hass.async_add_executor_job(kcal) == pytest.approx(3.6)


async def test_the_raw_off_answer_is_kept_verbatim(hass: HomeAssistant, hass_ws_client):
    entry = await setup_entry(hass)
    client = await hass_ws_client(hass)

    await client.send_json({
        "id": 1, "type": "home_stock/article/create", "code": "3229820129488",
        "new_product": {"name": "Muesli", "base_unit": "g"},
        "off": MUESLI.product, "off_source": "food",
    })
    created = (await client.receive_json())["result"]

    def raw() -> str:
        return entry.runtime_data.database.read().execute(
            "SELECT off_raw FROM article WHERE id = ?", (created["article_id"],)
        ).fetchone()[0]

    assert json.loads(await hass.async_add_executor_job(raw))["brands"] == "Bjorg"


async def test_editing_an_article_by_hand_protects_it_from_a_resync(
        hass: HomeAssistant, hass_ws_client):
    entry = await setup_entry(hass)
    client = await hass_ws_client(hass)
    await client.send_json({
        "id": 1, "type": "home_stock/article/create", "code": "1",
        "new_product": {"name": "Muesli", "base_unit": "g"},
        "off": MUESLI.product, "off_source": "food"})
    created = (await client.receive_json())["result"]

    await client.send_json({"id": 2, "type": "home_stock/article/update",
                            "article_id": created["article_id"],
                            "fields": {"kcal_per_base_unit": 4.0}})
    await client.receive_json()

    def manual() -> str:
        return entry.runtime_data.database.read().execute(
            "SELECT manual_fields FROM article WHERE id = ?",
            (created["article_id"],)).fetchone()[0]

    assert "kcal_per_base_unit" in (await hass.async_add_executor_job(manual))


async def test_an_unknown_column_is_refused_rather_than_written(
        hass: HomeAssistant, hass_ws_client):
    """The update path interpolates column names into SQL. The whitelist is
    what keeps that safe."""
    await setup_entry(hass)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/product/update",
                            "product_id": 1, "fields": {"id = 1; DROP TABLE product; --": 1}})
    answer = await client.receive_json()

    assert answer["success"] is False


async def test_a_dry_run_conversion_reports_without_touching_anything(
        hass: HomeAssistant, hass_ws_client):
    entry = await setup_entry(hass, with_piece_product=True)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/product/convert_unit",
                            "product_id": 1, "to_unit": "g",
                            "reference_quantity": 500, "dry_run": True})
    report = (await client.receive_json())["result"]

    assert report["applied"] is False
    assert report["to_unit"] == "g"


async def test_reordering_aisles_writes_the_new_walking_order(hass: HomeAssistant,
                                                              hass_ws_client):
    entry = await setup_entry(hass)
    client = await hass_ws_client(hass)

    def ids() -> list[int]:
        return [r["id"] for r in entry.runtime_data.database.read().execute(
            "SELECT id FROM aisle ORDER BY position").fetchall()]

    order = await hass.async_add_executor_job(ids)
    reversed_order = list(reversed(order))

    await client.send_json({"id": 1, "type": "home_stock/aisles/reorder",
                            "aisle_ids": reversed_order})
    await client.receive_json()

    assert await hass.async_add_executor_job(ids) == reversed_order


async def test_storing_directly_creates_a_batch_outside_any_session(
        hass: HomeAssistant, hass_ws_client):
    entry = await setup_entry(hass, with_article=True)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "home_stock/stock/add", "article_id": 1,
                            "quantity": 500, "location_id": 1,
                            "best_before": "2027-01-01", "idempotency_key": "k1"})
    first = (await client.receive_json())["result"]

    await client.send_json({"id": 2, "type": "home_stock/stock/add", "article_id": 1,
                            "quantity": 500, "location_id": 1,
                            "best_before": "2027-01-01", "idempotency_key": "k1"})
    again = (await client.receive_json())["result"]

    assert first["batch_id"] == again["batch_id"]
