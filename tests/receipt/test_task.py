"""Le seul module du composant qui appelle un modèle. Le double est INJECTÉ.

Aucun test ne sort sur le réseau, aucun ne lit une clé d'API : l'entité
`ai_task` est remplacée par un double, exactement comme le transport OFF
l'est depuis le lot 1.
"""
import json
from pathlib import Path

import pytest
import voluptuous as vol
from homeassistant.components.ai_task import AITaskEntityFeature
from homeassistant.exceptions import HomeAssistantError

from custom_components.home_stock.receipt import task as receipt_task
from custom_components.home_stock.receipt.task import (
    ReceiptReadResult, build_instructions, read_receipt, supports_attachments,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "receipts"
LABELS = ("Lait demi-écrémé 1 L", "Panzani 500 g", "Yaourt nature x4")


class _FakeEntity:
    def __init__(self, features=AITaskEntityFeature.GENERATE_DATA
                 | AITaskEntityFeature.SUPPORT_ATTACHMENTS):
        self.supported_features = features


def _install(hass, monkeypatch, *, answer=None, boom=None,
             features=AITaskEntityFeature.GENERATE_DATA
             | AITaskEntityFeature.SUPPORT_ATTACHMENTS,
             entity=True):
    """Injecte le double : rien ne sort du processus."""
    seen: dict = {}

    async def _generate_data(hass_, **kwargs):
        seen.update(kwargs)
        if boom is not None:
            raise boom
        return type("Result", (), {"data": answer, "conversation_id": "x"})()

    monkeypatch.setattr(receipt_task, "async_generate_data", _generate_data)
    monkeypatch.setattr(
        receipt_task, "_entity_of",
        lambda hass_, entity_id: _FakeEntity(features) if entity else None)
    return seen


async def _read(hass, **kwargs):
    kwargs.setdefault("agent_entity_id", "ai_task.gemini")
    kwargs.setdefault("media_content_id", "media-source://media_source/local/t.jpg")
    kwargs.setdefault("session_labels", LABELS)
    kwargs.setdefault("session_started_on", "2026-08-21")
    kwargs.setdefault("today", "2026-08-21")
    return await read_receipt(hass, **kwargs)


# --- l'invite ---------------------------------------------------------------

def test_the_prompt_carries_the_labels_of_the_session():
    """Un modèle qui sait qu'il cherche « LT DEMI ECR 1L » parmi vingt
    candidats connus se trompe beaucoup moins qu'un modèle qui lit dans le
    vide."""
    prompt = build_instructions(session_labels=LABELS)
    for label in LABELS:
        assert label in prompt


def test_the_prompt_is_in_french_and_names_what_to_ignore():
    """Promotions de fidélité, points, mode de paiement."""
    prompt = build_instructions(session_labels=LABELS).lower()
    assert "ticket de caisse" in prompt
    for ignored in ("fidélité", "promotion", "paiement"):
        assert ignored in prompt


def test_the_prompt_survives_an_empty_session():
    assert build_instructions(session_labels=())


# --- la lecture -------------------------------------------------------------

async def test_no_agent_configured_returns_a_result_that_says_so(hass):
    """Pas de bouton « Photographier » ; les réglages disent pourquoi.
    Un réglage, pas une panne."""
    result = await _read(hass, agent_entity_id=None)
    assert isinstance(result, ReceiptReadResult)
    assert result.parsed is None
    assert "réglages" in result.error.lower() or "aucune" in result.error.lower()


async def test_a_successful_read_returns_parsed_lines_and_the_raw_answer(
        hass, monkeypatch):
    """`raw` est conservée telle quelle, comme `article.off_raw`."""
    answer = json.loads((FIXTURES / "propre.json").read_text(encoding="utf-8"))
    seen = _install(hass, monkeypatch, answer=answer)

    result = await _read(hass)

    assert result.error is None
    assert len(result.parsed.lines) == 5
    assert json.loads(result.raw)["store"] == "Leclerc"
    assert result.agent_entity_id == "ai_task.gemini"
    assert seen["entity_id"] == "ai_task.gemini"
    assert seen["attachments"] == [
        {"media_content_id": "media-source://media_source/local/t.jpg",
         "media_content_type": "image/jpeg"}]
    assert isinstance(seen["structure"], vol.Schema)


@pytest.mark.parametrize("boom, expected", [
    (HomeAssistantError("nope"), "modèle"),
    (TimeoutError(), "délai"),
    (RuntimeError("quota exceeded"), "modèle"),
])
async def test_an_agent_that_raises_yields_a_french_error_not_an_exception(
        hass, monkeypatch, boom, expected):
    _install(hass, monkeypatch, boom=boom)
    result = await _read(hass)
    assert result.parsed is None
    assert expected in result.error.lower()


async def test_an_agent_that_disappeared_names_the_missing_entity(hass, monkeypatch):
    """`receipt.state = 'failed'`, message NOMMANT l'entité manquante — pas
    « Unknown error »."""
    _install(hass, monkeypatch, entity=False)
    result = await _read(hass, agent_entity_id="ai_task.partie")
    assert result.parsed is None
    assert "ai_task.partie" in result.error


async def test_an_agent_without_attachments_is_named_too(hass, monkeypatch):
    _install(hass, monkeypatch, features=AITaskEntityFeature.GENERATE_DATA)
    result = await _read(hass)
    assert result.parsed is None
    assert "pièce jointe" in result.error.lower()


async def test_an_answer_out_of_bounds_drops_the_bad_lines_only(hass, monkeypatch):
    answer = json.loads(
        (FIXTURES / "ligne_a_4000_euros.json").read_text(encoding="utf-8"))
    _install(hass, monkeypatch, answer=answer)

    result = await _read(hass)

    assert len(result.parsed.lines) == 19
    assert len(result.parsed.dropped) == 1


async def test_an_empty_answer_is_a_failure_not_a_crash(hass, monkeypatch):
    _install(hass, monkeypatch, answer={})
    result = await _read(hass)
    assert result.parsed is None
    assert result.error


async def test_a_json_string_answer_is_read_too(hass, monkeypatch):
    """Un modèle peut rendre la structure sérialisée plutôt qu'un objet."""
    answer = (FIXTURES / "propre.json").read_text(encoding="utf-8")
    _install(hass, monkeypatch, answer=answer)
    result = await _read(hass)
    assert len(result.parsed.lines) == 5


def test_supports_attachments_reads_the_feature_flag(hass, monkeypatch):
    """Lu dans la machine à états : le flux d'options s'ouvre sans que
    l'intégration propriétaire de l'entité soit forcément chargée."""
    hass.states.async_set(
        "ai_task.gemini", "unknown",
        {"supported_features": AITaskEntityFeature.GENERATE_DATA
                               | AITaskEntityFeature.SUPPORT_ATTACHMENTS})
    hass.states.async_set(
        "ai_task.texte", "unknown",
        {"supported_features": AITaskEntityFeature.GENERATE_DATA})

    assert supports_attachments(hass, "ai_task.gemini") is True
    assert supports_attachments(hass, "ai_task.texte") is False
    monkeypatch.setattr(receipt_task, "_entity_of", lambda hass_, entity_id: None)
    assert supports_attachments(hass, "ai_task.absente") is False
    assert supports_attachments(hass, None) is False


# --- les règles du composant ------------------------------------------------

def test_no_api_key_is_read_anywhere_in_the_component():
    """Scan littéral de `custom_components/` : ni `GEMINI_KEY`, ni `.env`,
    ni `.mcp.json`, ni `api_key`. C'est une RÈGLE, pas une préférence : ce
    composant part sur HACS."""
    import io
    import tokenize

    component = Path(receipt_task.__file__).resolve().parent.parent
    offenders = []
    for path in component.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            # Commentaires et docstrings ont le DROIT de nommer le piège —
            # c'est même là qu'il est expliqué. Seul le code réel est
            # interdit.
            if token.type in (tokenize.COMMENT, tokenize.STRING):
                continue
            for needle in ("GEMINI_KEY", "mcp", "environ", "getenv"):
                if needle in token.string:
                    offenders.append(
                        f"{path.relative_to(component).as_posix()}"
                        f":{token.start[0]} {needle}")
    assert offenders == []


async def test_no_test_in_this_file_reaches_the_network(hass):
    """Le double est injecté ; `aiohttp` n'est jamais importé ici."""
    source = Path(__file__).read_text(encoding="utf-8")
    for forbidden in ("aio" + "http", "req" + "uests", "urll" + "ib"):
        assert f"import {forbidden}" not in source
