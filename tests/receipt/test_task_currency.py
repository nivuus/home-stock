"""A receipt is read without assuming a country or a currency.

The prompt names neither; the model reports the currency printed on the
receipt, and prices are only accepted when it is the currency Home
Assistant is configured with. The model call is a double: nothing leaves
the process.
"""
import json
from pathlib import Path

import pytest
from homeassistant.components.ai_task import AITaskEntityFeature

from custom_components.home_stock.receipt import task as receipt_task
from custom_components.home_stock.receipt.parse import RECEIPT_STRUCTURE
from custom_components.home_stock.receipt.task import build_instructions, read_receipt

FIXTURES = Path(__file__).parent.parent / "fixtures" / "receipts"


class _Entity:
    supported_features = (AITaskEntityFeature.GENERATE_DATA
                           | AITaskEntityFeature.SUPPORT_ATTACHMENTS)


def _install(monkeypatch, answer):
    async def _generate_data(hass_, **kwargs):
        return type("Result", (), {"data": answer, "conversation_id": "x"})()

    monkeypatch.setattr(receipt_task, "async_generate_data", _generate_data)
    monkeypatch.setattr(receipt_task, "_entity_of", lambda hass_, entity_id: _Entity())


def _answer(currency):
    answer = json.loads((FIXTURES / "propre.json").read_text(encoding="utf-8"))
    if currency is None:
        answer.pop("currency", None)
    else:
        answer["currency"] = currency
    return answer


async def _read(hass):
    return await read_receipt(
        hass, agent_entity_id="ai_task.reader",
        media_content_id="media-source://media_source/local/t.jpg",
        session_labels=(), session_started_on="2026-08-21", today="2026-08-21")


def test_the_prompt_assumes_no_country_and_no_currency():
    prompt = build_instructions(session_labels=("Milk 1 L",))
    for assumed in ("français", "France", "euro", "€", "EUR"):
        assert assumed not in prompt
    assert "ISO 4217" in prompt
    for field in RECEIPT_STRUCTURE.values():
        assert "euro" not in field["description"].lower()


@pytest.mark.parametrize("configured, printed", [("PLN", "EUR"), ("JPY", "EUR"),
                                                 ("EUR", "USD")])
async def test_prices_in_another_currency_are_refused(
        hass, monkeypatch, configured, printed):
    hass.config.currency = configured
    _install(monkeypatch, _answer(printed))
    result = await _read(hass)
    assert result.parsed is None
    assert printed in result.error and configured in result.error
    assert result.raw is not None          # the answer is kept for a retry


async def test_a_receipt_without_a_currency_is_refused(hass, monkeypatch):
    hass.config.currency = "PLN"
    _install(monkeypatch, _answer(None))
    result = await _read(hass)
    assert result.parsed is None
    assert "PLN" in result.error


@pytest.mark.parametrize("configured, printed", [("JPY", "JPY"), ("PLN", " pln ")])
async def test_the_configured_currency_is_accepted(hass, monkeypatch, configured, printed):
    hass.config.currency = configured
    _install(monkeypatch, _answer(printed))
    result = await _read(hass)
    assert result.error is None
    assert len(result.parsed.lines) == 5
