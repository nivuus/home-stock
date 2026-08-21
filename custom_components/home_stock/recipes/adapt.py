"""Adapting an imported recipe through a Home Assistant conversation agent.

Translate the card into French, cut the instruction block into cooking pages,
name each ingredient in isolation. All of it optional: **no agent, a broken
agent, an agent out of quota or one that answers gibberish must all leave the
recipe existing**, in English, flagged for review. What must never happen is a
half-written adaptation — a French title over English bullets, or five pages
where the source had eight.

The call goes through the SERVICE, not through an import of `conversation`:

- the component then does not depend on Home Assistant's `conversation` module
  at import time, so `manifest.json` stays as it is and the integration starts
  on an installation without it;
- the agent is named by `entity_id`, exactly as the options selector yields it;
- a test replaces the service with a double, without standing up a whole
  `conversation` integration.

No API key is embedded or read here — not `GEMINI_KEY`, not the `.env` of
`data/tools/grocy-off`, nothing. That is a rule, not a preference: this
component ships on HACS.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Final

import voluptuous as vol

from ..validators import bounded_int, bounded_text
from .mapping import SourceRecipe

# Past this, the source block is truncated — never the agent's answer. A card
# with a runaway instruction field must not turn into a prompt nobody will
# serve, and truncating what we send is recoverable; truncating what comes
# back would silently drop cooking steps.
MAX_PROMPT_INSTRUCTIONS: Final = 8000

MAX_ADAPTED_STEPS: Final = 40
MAX_TIMER_SECONDS: Final = 24 * 3600


@dataclass(frozen=True)
class AdaptedStep:
    title: str | None
    bullets: tuple[tuple[str, str | None, int | None], ...]   # text, label, seconds


@dataclass(frozen=True)
class AdaptedRecipe:
    name: str
    summary: str | None
    total_minutes: int | None
    utensils: str | None
    servings: int
    steps: tuple[AdaptedStep, ...]
    ingredient_names: tuple[str, ...]
    ingredient_amounts: tuple[tuple[float | None, str | None], ...]


def build_prompt(recipe: SourceRecipe) -> str:
    """The instruction sent to the agent. French, and it asks for JSON only."""
    instructions = recipe.instructions[:MAX_PROMPT_INSTRUCTIONS]
    lines = [
        f"{ingredient.position}. {ingredient.raw_text}"
        for ingredient in recipe.ingredients
    ]
    return (
        "Tu adaptes une recette de cuisine pour une tablette murale.\n"
        "Réponds UNIQUEMENT par un objet JSON, sans texte autour, sans bloc de code.\n\n"
        "Traduis en français, découpe les instructions en étapes courtes, et donne "
        "pour chaque ingrédient son nom isolé (sans la quantité).\n\n"
        "Le JSON attendu :\n"
        '{"name": "titre en français", "summary": "une phrase d\'accroche",\n'
        ' "total_minutes": 35, "utensils": "poêle, four", "servings": 4,\n'
        ' "steps": [{"title": "Préparer la sauce",\n'
        '            "bullets": [{"text": "Émincer l\'oignon"},\n'
        '                        {"text": "Cuire", "timer_label": "Cuisson",\n'
        '                         "timer_seconds": 600}]}],\n'
        ' "ingredients": [{"name": "sauce soja"}]}\n\n'
        "Un minuteur porte SON libellé ET sa durée, ou aucun des deux.\n"
        f"Rends exactement {len(recipe.ingredients)} ingrédients, dans l'ordre.\n\n"
        f"Titre : {recipe.name}\n"
        f"Ingrédients :\n" + "\n".join(lines) + "\n\n"
        f"Instructions :\n{instructions}\n"
    )


def extract_json(text: Any) -> dict[str, Any] | None:
    """The first balanced-brace object in the answer, or None.

    A conversation agent is allowed to write "Voici la recette adaptée :" in
    front of its JSON — that is its job. So the payload is tried as-is first,
    then the first block delimited by BALANCED braces is carved out.

    Counted, not matched with a regular expression: a non-greedy regex stops
    at the first inner `}` and would hand back the outer object truncated at
    its first nested one. Braces inside strings are skipped, escapes included,
    or a title containing "{" would end the scan early.
    """
    if not isinstance(text, str):
        return None
    stripped = text.strip()
    try:
        parsed = json.loads(stripped)
    except (ValueError, TypeError):
        pass
    else:
        # The whole answer IS valid JSON. Then it is the answer, whatever it
        # is: a top-level array means the agent misread the requested shape,
        # and digging its first object out would be guessing at what it meant.
        # Only prose-wrapped payloads get the brace scan below.
        return parsed if isinstance(parsed, dict) else None

    start = stripped.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(stripped)):
        character = stripped[index]
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                try:
                    candidate = json.loads(stripped[start:index + 1])
                except ValueError:
                    return None
                return candidate if isinstance(candidate, dict) else None
    return None


def _optional_text(value: Any) -> str | None:
    """`bounded_text`, but an absent value is fine and a bad one is fatal."""
    if value is None:
        return None
    return bounded_text(value)


def validate_adaptation(payload: Any, *,
                        source: SourceRecipe) -> AdaptedRecipe | None:
    """The agent's answer, checked field by field. Any anomaly fails it whole.

    There is no partial adaptation. A title that validates over bullets that
    do not would leave a French heading on English steps, which reads as a bug
    to whoever cooks from it and cannot be told apart from a real translation.
    So every field goes through the same validators both surfaces use, and the
    first refusal returns None — the caller then writes the source card as it
    stands, in English, flagged for review.
    """
    if not isinstance(payload, dict):
        return None
    try:
        name = bounded_text(payload.get("name"))
        if not name:
            return None
        summary = _optional_text(payload.get("summary"))
        utensils = _optional_text(payload.get("utensils"))

        total_minutes = payload.get("total_minutes")
        if total_minutes is not None:
            total_minutes = bounded_int(total_minutes)
            if total_minutes <= 0:
                return None

        servings = bounded_int(payload.get("servings", 1))
        if servings < 1:
            return None

        raw_steps = payload.get("steps", [])
        if not isinstance(raw_steps, list) or len(raw_steps) > MAX_ADAPTED_STEPS:
            return None
        steps: list[AdaptedStep] = []
        for raw_step in raw_steps:
            if not isinstance(raw_step, dict):
                return None
            raw_bullets = raw_step.get("bullets", [])
            if not isinstance(raw_bullets, list):
                return None
            bullets: list[tuple[str, str | None, int | None]] = []
            for raw_bullet in raw_bullets:
                if not isinstance(raw_bullet, dict):
                    return None
                text = bounded_text(raw_bullet.get("text"))
                if not text:
                    return None
                label = _optional_text(raw_bullet.get("timer_label"))
                seconds = raw_bullet.get("timer_seconds")
                if seconds is not None:
                    seconds = bounded_int(seconds)
                    if not 0 < seconds <= MAX_TIMER_SECONDS:
                        return None
                # A "Cooking" button with no duration is not a button, and a
                # duration with no name is a countdown to nothing. The schema
                # says the same thing with a CHECK; saying it here too means
                # the refusal arrives before any row is written.
                if (label is None) != (seconds is None):
                    return None
                bullets.append((text, label, seconds))
            steps.append(AdaptedStep(title=_optional_text(raw_step.get("title")),
                                     bullets=tuple(bullets)))

        raw_ingredients = payload.get("ingredients", [])
        if not isinstance(raw_ingredients, list):
            return None
        # More names than the source had means the agent invented a line. That
        # line would have no quantity, no product and no provenance, and it
        # would sit in the recipe looking exactly like a real one.
        if len(raw_ingredients) > len(source.ingredients):
            return None
        names: list[str] = []
        for raw_ingredient in raw_ingredients:
            if not isinstance(raw_ingredient, dict):
                return None
            ingredient_name = bounded_text(raw_ingredient.get("name"))
            if not ingredient_name:
                return None
            names.append(ingredient_name)
    except (ValueError, TypeError, vol.Invalid):
        return None

    return AdaptedRecipe(
        name=name, summary=summary, total_minutes=total_minutes,
        utensils=utensils, servings=servings, steps=tuple(steps),
        ingredient_names=tuple(names),
        ingredient_amounts=tuple((None, None) for _ in names),
    )


async def adapt(hass, *, agent_id: str | None,
                recipe: SourceRecipe) -> AdaptedRecipe | None:
    """Ask the configured agent to adapt this card. Never raises.

    No agent configured is a setting, not a failure: it returns None without
    calling anything. Every other outcome — the service missing, the agent
    raising, timing out, being out of quota, or answering something
    unreadable — also returns None, and the caller writes the English card.
    """
    if not agent_id:
        return None
    try:
        response = await hass.services.async_call(
            "conversation", "process",
            {"text": build_prompt(recipe), "agent_id": agent_id},
            blocking=True, return_response=True,
        )
    except Exception:       # noqa: BLE001 — an idea source may not break dinner
        return None
    return validate_adaptation(extract_json(_spoken_text(response)), source=recipe)


def _spoken_text(response: Any) -> Any:
    """Dig the plain speech out of a conversation response, defensively.

    The shape is `response.speech.plain.speech`, and every level of it is
    read with `.get` because a different agent implementation answering a
    different shape must read as "unusable answer", not as an AttributeError
    escaping into the import.
    """
    if isinstance(response, str):
        return response
    if not isinstance(response, dict):
        return None
    speech = response.get("response", response)
    if isinstance(speech, dict):
        speech = speech.get("speech", speech)
    if isinstance(speech, dict):
        speech = speech.get("plain", speech)
    if isinstance(speech, dict):
        speech = speech.get("speech")
    return speech
