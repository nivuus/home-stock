"""The three announcement blueprints hand the agent data, never a sentence.

Each blueprint's action is run for real through Home Assistant's script engine,
with `conversation.process` replaced by a recorder, so what is checked is what
the agent would receive: the rendered text after Home Assistant's own template
handling (which parses a bare JSON or Python literal back into a dict).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from homeassistant.core import ServiceCall, SupportsResponse
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.script import Script
from homeassistant.util import yaml as yaml_util

ROOT = Path(__file__).resolve().parent.parent / "blueprints" / "automation" / "home_stock"


def _substituted(name: str) -> tuple[dict, dict]:
    document = yaml_util.load_yaml_dict(ROOT / name)
    defaults = {key: spec["default"]
                for key, spec in document["blueprint"]["input"].items()}
    return defaults, yaml_util.substitute(document, defaults)


async def _run(hass, name: str, entity_attrs: dict) -> dict:
    defaults, blueprint = _substituted(name)
    calls: list[ServiceCall] = []

    async def _record(call: ServiceCall) -> dict:
        calls.append(call)
        return {}

    hass.services.async_register("conversation", "process", _record,
                                 supports_response=SupportsResponse.OPTIONAL)
    hass.states.async_set(defaults["capteur"], "on", entity_attrs)
    script = Script(hass, cv.SCRIPT_SCHEMA(blueprint["actions"]), "blueprint test", "home_stock")
    variables = {key: value for key, value in blueprint["variables"].items()}
    await script.async_run(variables, context=None)
    await hass.async_block_till_done()
    assert len(calls) == 1
    return dict(calls[0].data)


def _event(data: dict, expected_event: str) -> dict:
    text = data["text"]
    assert isinstance(text, str), "Home Assistant parsed the payload into a dict"
    event, _, payload = text.partition(" ")
    assert event == expected_event
    return json.loads(payload)


@pytest.mark.parametrize("name", ["dlc_bleuenn.yaml", "courses_bleuenn.yaml",
                                  "objectifs_bleuenn.yaml"])
def test_no_blueprint_forces_a_language(name):
    """No `language:` key: Home Assistant then hands the agent the instance's
    language (conversation/agent_manager.py), which is the household's."""
    _, blueprint = _substituted(name)
    assert "language" not in blueprint["actions"][0]["data"]


async def test_expiry_blueprint_sends_names_in_any_script(hass):
    batches = [
        {"product_name": "牛乳", "best_before": "2026-11-17"},
        {"product_name": "Γιαούρτι", "best_before": "2026-11-18"},
        {"product_name": "Œufs", "best_before": "2026-11-18"},
    ]
    data = await _run(hass, "dlc_bleuenn.yaml", {"batches": batches})
    payload = _event(data, "home_stock.expiring_soon")
    assert payload == {"items": [
        {"product": "牛乳", "best_before": "2026-11-17"},
        {"product": "Γιαούρτι", "best_before": "2026-11-18"},
        {"product": "Œufs", "best_before": "2026-11-18"},
    ]}
    assert data["agent_id"] == "conversation.personas_studio_home_manager"


SHOPPING = [
    {"id": 1, "name": "Молоко", "aisle": "Молочные", "checked": False},
    {"id": 2, "name": "バター", "aisle": "Молочные", "checked": False},
    {"id": 3, "name": "خبز", "aisle": None, "checked": False},
    {"id": 4, "name": "Café", "aisle": "Épicerie", "checked": True},
]


async def test_shopping_blueprint_groups_open_lines_by_aisle(hass):
    data = await _run(hass, "courses_bleuenn.yaml", {"items": SHOPPING})
    payload = _event(data, "home_stock.shopping_reminder")
    assert payload["open_items"] == 3
    assert payload["by_aisle"] == [{"aisle": "Молочные", "count": 2},
                                   {"aisle": None, "count": 1}]
    assert payload["items"] == ["Молоко", "バター", "خبز"]


async def test_shopping_blueprint_drops_the_detail_of_a_long_list(hass):
    long_list = [{"id": i, "name": f"P{i}", "aisle": "A", "checked": False}
                 for i in range(12)]
    data = await _run(hass, "courses_bleuenn.yaml", {"items": long_list})
    payload = _event(data, "home_stock.shopping_reminder")
    assert payload == {"open_items": 12, "by_aisle": [{"aisle": "A", "count": 12}]}


async def test_shopping_blueprint_reports_an_all_ticked_list(hass):
    data = await _run(hass, "courses_bleuenn.yaml", {"items": [SHOPPING[3]]})
    payload = _event(data, "home_stock.shopping_reminder")
    assert payload == {"open_items": 0, "by_aisle": [], "items": []}


async def test_goals_blueprint_sends_nutrient_keys(hass):
    exceeded = [{"nutrient": "salt", "scope": "day", "value": 8.44,
                 "goal": 6.0, "ratio": 1.4},
                {"nutrient": "kcal", "scope": "week", "value": 2400.0,
                 "goal": 2000.0, "ratio": 1.2}]
    data = await _run(hass, "objectifs_bleuenn.yaml", {"exceeded": exceeded})
    payload = _event(data, "home_stock.nutrition_goals_exceeded")
    assert payload == {"items": [
        {"nutrient": "salt", "scope": "day", "value": 8.4, "goal": 6.0},
        {"nutrient": "kcal", "scope": "week", "value": 2400.0, "goal": 2000.0},
    ]}
