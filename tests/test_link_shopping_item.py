"""Lot 4: `home_stock.link_shopping_item`, the missing rattachement (R11).

`docs/inventory.md`'s `SHOPPING_LINK` rubric found no existing way to attach
a free-text shopping list line to a product after the fact, so this service
was added. This test proves the three things R11 asks for: the line starts
"sans rayon", the service attaches it to a product created by
`home_stock.create_product`, and it then carries that product's rayon.
"""
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from custom_components.home_stock.aisles import AISLES
from custom_components.home_stock.storage import repositories as repo

RAYON = AISLES[0]


async def _create_product(hass, name: str) -> str:
    answer = await hass.services.async_call(
        "home_stock", "create_product", {"name": name, "rayon": RAYON},
        blocking=True, return_response=True)
    return answer["product_id"]


async def _add_free_text_line(hass, text: str) -> None:
    await hass.services.async_call(
        "home_stock", "add_to_shopping_list", {"free_text": text},
        blocking=True)


def _find_line(conn, text: str) -> dict:
    return next(row for row in repo.list_items(conn) if row.get("free_text") == text)


async def test_service_is_registered(hass: HomeAssistant, setup_entry):
    await setup_entry()
    assert hass.services.has_service("home_stock", "link_shopping_item")


async def test_links_a_free_text_line_to_a_created_product(hass: HomeAssistant, setup_entry):
    entry = await setup_entry()
    product_id = await _create_product(hass, "Mangue")
    await _add_free_text_line(hass, "mangue")

    def _before():
        return _find_line(entry.runtime_data.manager.db.read(), "mangue")

    line = await hass.async_add_executor_job(_before)
    assert line["product_id"] is None
    assert line["aisle_id"] is None

    await hass.services.async_call(
        "home_stock", "link_shopping_item",
        {"item": str(line["id"]), "product_id": product_id}, blocking=True)

    def _after():
        return repo.get_list_item(entry.runtime_data.manager.db.read(), line["id"])

    linked = await hass.async_add_executor_job(_after)
    assert linked["product_id"] == int(product_id.removeprefix("hs_"))
    assert linked["free_text"] is None

    def _rayon_id() -> int:
        aisle = next(a for a in repo.list_aisles(entry.runtime_data.manager.db.read())
                     if a["name"] == RAYON)
        return aisle["id"]

    expected_aisle_id = await hass.async_add_executor_job(_rayon_id)

    def _final_row():
        rows = repo.list_items(entry.runtime_data.manager.db.read())
        return next(r for r in rows if r["id"] == line["id"])

    final_row = await hass.async_add_executor_job(_final_row)
    assert final_row["aisle_id"] == expected_aisle_id


async def test_rejects_an_unknown_line(hass: HomeAssistant, setup_entry):
    await setup_entry()
    product_id = await _create_product(hass, "Kimchi")

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "home_stock", "link_shopping_item",
            {"item": "no-such-line", "product_id": product_id}, blocking=True)


async def test_rejects_an_unknown_product(hass: HomeAssistant, setup_entry):
    entry = await setup_entry()
    await _add_free_text_line(hass, "piment antillais")

    def _line_id():
        row = _find_line(entry.runtime_data.manager.db.read(), "piment antillais")
        return row["id"]

    item_id = await hass.async_add_executor_job(_line_id)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "home_stock", "link_shopping_item",
            {"item": str(item_id), "product_id": "hs_999999"}, blocking=True)
