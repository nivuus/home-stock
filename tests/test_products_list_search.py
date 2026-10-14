"""`home_stock/products/list` with `search`, through Home Assistant's websocket.

Before this change the command declared no `search` field: Home Assistant
refused one (invalid_format, "extra keys not allowed"), and the only read of
the catalogue was the whole of it (357 products on Maxime's instance). Now the
field is declared and the answer holds only the products whose name contains
the word, ignoring case and accents; without it, the answer is the whole
list, as before.
"""
from __future__ import annotations

from typing import Any

import pytest
from homeassistant.core import HomeAssistant

from custom_components.home_stock.storage import repositories as repo

VISIBLE = ("Carotte", "CAROTTES râpées", "Purée de carottes", "Carrot cake",
           "Pâtes", "Riz basmati")
HIDDEN = "Carotte violette"


@pytest.fixture
async def client(hass: HomeAssistant, setup_entry, hass_ws_client):
    entry = await setup_entry()
    db = entry.runtime_data.manager.db

    def _seed() -> None:
        with db.write() as conn:
            for name in VISIBLE:
                repo.insert_product(conn, name=name, base_unit="g")
            repo.insert_product(conn, name=HIDDEN, base_unit="g", active=0)

    await hass.async_add_executor_job(_seed)
    return await hass_ws_client(hass)


async def _list(client, **fields: Any) -> dict[str, Any]:
    await client.send_json_auto_id({"type": "home_stock/products/list", **fields})
    answer: dict[str, Any] = await client.receive_json()
    return answer


def _names(answer: dict[str, Any]) -> list[str]:
    assert answer["success"] is True, answer
    return [product["name"] for product in answer["result"]["products"]]


async def test_without_search_the_whole_list_comes_back(client) -> None:
    assert _names(await _list(client)) == sorted(VISIBLE)


async def test_search_carotte_returns_only_the_carrots(client) -> None:
    names = _names(await _list(client, search="carotte"))
    assert names == ["CAROTTES râpées", "Carotte", "Purée de carottes"]
    assert all("carotte" in name.casefold() for name in names)


async def test_search_ignores_case_and_accents(client) -> None:
    assert _names(await _list(client, search="PATE")) == ["Pâtes"]
    assert _names(await _list(client, search="purée DE")) == ["Purée de carottes"]


async def test_search_and_include_hidden_combine(client) -> None:
    names = _names(await _list(client, search="carotte", include_hidden=True))
    assert names == ["CAROTTES râpées", "Carotte", HIDDEN, "Purée de carottes"]


async def test_blank_search_is_no_search(client) -> None:
    assert _names(await _list(client, search="  ")) == sorted(VISIBLE)


async def test_search_with_no_match_is_an_empty_list(client) -> None:
    assert _names(await _list(client, search="rutabaga")) == []


async def test_a_search_that_is_not_text_is_refused(client) -> None:
    answer = await _list(client, search=12)
    assert answer["success"] is False
    assert answer["error"]["code"] == "invalid_format"
