"""Errors carry a translation key; each surface turns it into words.

The services raise Home Assistant's ServiceValidationError with the key (the
frontend shows it in the person's language, `str()` is English for the log).
The websocket sends the key and placeholders plus a sentence in Home
Assistant's configured language, English when that language has none.
"""
import json
import string
from pathlib import Path

import pytest
from homeassistant.exceptions import ServiceValidationError

from custom_components.home_stock.const import DOMAIN
from custom_components.home_stock.domain.errors import NotFoundError
from custom_components.home_stock.domain.stock import InsufficientStock
from custom_components.home_stock.domain.units import UnitError
from custom_components.home_stock.messages import french_message

TRANSLATIONS = Path(__file__).resolve().parent.parent / "custom_components" \
    / "home_stock" / "translations"


def _exceptions(language: str) -> dict[str, str]:
    table = json.loads((TRANSLATIONS / f"{language}.json").read_text(encoding="utf-8"))
    return {key: entry["message"] for key, entry in table["exceptions"].items()}


def _fields(template: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(template) if name}


def test_every_sentence_exists_in_english_and_french_with_the_same_placeholders():
    english, french = _exceptions("en"), _exceptions("fr")
    assert set(english) == set(french)
    for key in english:
        assert _fields(english[key]) == _fields(french[key]), key


def test_typed_errors_are_still_what_their_call_sites_raised():
    """`except LookupError` and `except ValueError` keep catching them."""
    error = NotFoundError("no product 4", translation_key="product_not_found",
                          product_id=4)
    assert isinstance(error, LookupError) and isinstance(error, ValueError)
    assert str(error) == "no product 4"
    assert isinstance(UnitError("x", translation_key="unit_unknown", unit="x"),
                      ValueError)
    assert InsufficientStock(5, 2).translation_key == "insufficient_stock"


def test_the_hass_less_french_path_reads_the_translation_file():
    error = NotFoundError("unknown batch 9", translation_key="batch_not_found",
                          batch_id=9)
    assert french_message(error) == "Lot 9 inconnu."


async def test_a_service_refusal_carries_its_key(hass, setup_entry):
    await setup_entry(with_article=True)
    with pytest.raises(ServiceValidationError) as refusal:
        await hass.services.async_call(DOMAIN, "consume", {
            "product_id": 999, "quantity": 1}, blocking=True)
    assert refusal.value.translation_domain == DOMAIN
    assert refusal.value.translation_key == "product_not_found"
    assert refusal.value.translation_placeholders == {"product_id": "999"}
    assert str(refusal.value) == "Product 999 not found"


@pytest.mark.parametrize("language, expected", [
    ("fr", "Article 999 inconnu."),
    ("en", "Article 999 not found."),
    # No German sentences yet: Home Assistant's rule for exception text.
    ("de", "Article 999 not found."),
])
async def test_the_websocket_answers_in_the_configured_language(
        hass, setup_entry, hass_ws_client, language, expected):
    await hass.config.async_update(language=language)
    await setup_entry(with_article=True)
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "home_stock/article/delete",
                            "article_id": 999})
    answer = await client.receive_json()
    assert answer["error"]["code"] == "not_found"
    assert answer["error"]["message"] == expected
    assert answer["error"]["translation_key"] == "article_not_found"
    assert answer["error"]["translation_domain"] == DOMAIN
    assert answer["error"]["translation_placeholders"] == {"article_id": "999"}


async def test_a_language_set_after_setup_is_still_answered(
        hass, setup_entry, hass_ws_client):
    """The cache is filled at setup; a later change of language must not
    fall back to English for a language that has sentences."""
    await setup_entry(with_article=True)
    await hass.config.async_update(language="fr")
    await hass.async_block_till_done()
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "home_stock/article/delete",
                            "article_id": 999})
    answer = await client.receive_json()
    assert answer["error"]["message"] == "Article 999 inconnu."
