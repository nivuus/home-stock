"""home_stock.resync_off: a background catalogue refresh from Open Food Facts."""
import json

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.home_stock.const import DOMAIN
from custom_components.home_stock.off.client import OffLookup, OffRecord
from custom_components.home_stock.storage import repositories as repo

MUESLI = {
    "code": "3229820129488",
    "product_name_fr": "Muesli Raisin, Figue, Datte, Abricot",
    "brands": "Bjorg",
    "product_quantity": 375,
    "product_quantity_unit": "g",
    "nutriscore_grade": "a",
    "categories_tags": ["en:plant-based-foods", "en:breakfasts", "en:breakfast-cereals"],
    "nutrition_data_per": "100g",
    "nutriments": {"energy-kcal_100g": 360, "proteins_100g": 9, "carbohydrates_100g": 60,
                   "fat_100g": 6, "salt_100g": 0.02},
}


class FakeOffClient:
    """Stands in for the cascade. Nothing here reaches the network."""

    def __init__(self, records: dict[str, dict]):
        self._records = records
        self.codes: list[str] = []

    async def lookup_with_retry(self, code: str, **kwargs) -> OffLookup:
        self.codes.append(code)
        product = self._records.get(code)
        if product is None:
            return OffLookup()
        return OffLookup(record=OffRecord(code, "food", product))


@pytest.fixture
async def entry(hass: HomeAssistant, setup_entry):
    entry = await setup_entry()
    entry.runtime_data.off_client = FakeOffClient({"3229820129488": MUESLI})
    return entry


def _seed_article(manager, *, kcal_per_base_unit, manual_fields=()):
    with manager.db.write() as conn:
        product_id = repo.insert_product(conn, name="Muesli", base_unit="g")
        article_id = repo.insert_article(
            conn, product_id=product_id, kcal_per_base_unit=kcal_per_base_unit,
            manual_fields=json.dumps(list(manual_fields)) if manual_fields else None,
        )
        repo.link_barcode(conn, "3229820129488", article_id)
    return article_id


async def test_a_hand_corrected_field_survives_a_resync_that_disagrees(
        hass: HomeAssistant, entry):
    """The one thing this task exists to prove: manual_fields wins over a
    fresh, disagreeing OFF answer, and everything NOT protected still
    refreshes — a resync that overwrote the correction, or one that changed
    nothing at all, would both hide here."""
    manager = entry.runtime_data.manager
    # 9.9 is what a person typed by hand; MUESLI's own kcal (360 per 100 g,
    # 3.6 per base unit for a g-based product) disagrees with it — the resync
    # must not be a no-op that happens to agree by coincidence.
    article_id = await hass.async_add_executor_job(
        lambda: _seed_article(manager, kcal_per_base_unit=9.9,
                              manual_fields=("kcal_per_base_unit",)))

    await hass.services.async_call(DOMAIN, "resync_off", {"article_id": article_id},
                                   blocking=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    def _read():
        return repo.get_article(manager.db.read(), article_id)

    article = await hass.async_add_executor_job(_read)
    # Protected: the human's number, not OFF's 3.6.
    assert article["kcal_per_base_unit"] == 9.9
    # Not protected: OFF's answer for everything else actually landed.
    assert article["brand"] == "Bjorg"
    assert article["net_quantity"] == 375
    assert article["off_source"] == "food"
    assert article["off_synced_at"] is not None
    assert json.loads(article["off_raw"])["code"] == "3229820129488"


async def test_an_unprotected_field_is_overwritten_by_the_resync(
        hass: HomeAssistant, entry):
    """The mirror of the test above: without manual_fields, OFF's answer
    wins outright — proving the protection above comes from manual_fields,
    not from some accidental refusal to ever overwrite kcal."""
    manager = entry.runtime_data.manager
    article_id = await hass.async_add_executor_job(
        lambda: _seed_article(manager, kcal_per_base_unit=9.9))

    await hass.services.async_call(DOMAIN, "resync_off", {"article_id": article_id},
                                   blocking=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    def _read():
        return repo.get_article(manager.db.read(), article_id)

    article = await hass.async_add_executor_job(_read)
    assert article["kcal_per_base_unit"] == pytest.approx(3.6)


async def test_resync_off_refreshes_the_coordinator(hass: HomeAssistant, entry):
    manager = entry.runtime_data.manager
    article_id = await hass.async_add_executor_job(
        lambda: _seed_article(manager, kcal_per_base_unit=9.9))

    await hass.services.async_call(DOMAIN, "resync_off", {"article_id": article_id},
                                   blocking=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    def _read():
        return repo.get_article(manager.db.read(), article_id)["brand"]

    assert (await hass.async_add_executor_job(_read)) == "Bjorg"


async def test_resync_off_a_code_off_no_longer_knows_is_a_no_op(hass: HomeAssistant, entry):
    """A card OFF answers "not found" for (delisted, mistyped) must not clear
    what is already stored."""
    manager = entry.runtime_data.manager
    with manager.db.write() as conn:
        product_id = repo.insert_product(conn, name="Muesli", base_unit="g")
        article_id = repo.insert_article(conn, product_id=product_id, brand="Bjorg")
        repo.link_barcode(conn, "0000000000000", article_id)

    await hass.services.async_call(DOMAIN, "resync_off", {"article_id": article_id},
                                   blocking=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    def _read():
        return repo.get_article(manager.db.read(), article_id)["brand"]

    assert (await hass.async_add_executor_job(_read)) == "Bjorg"


async def test_resync_off_requires_a_loaded_entry(hass: HomeAssistant):
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN, "resync_off", {"all": True}, blocking=True)
