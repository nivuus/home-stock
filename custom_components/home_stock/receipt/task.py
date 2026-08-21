"""Le SEUL module du composant qui appelle un modèle.

Comme `off/client.py` est le seul à parler à Open Food Facts. Aucun accès
SQLite ici, et surtout **aucune clé d'API** : la maison a déjà ses backends,
et ce composant part sur HACS.

**Une entité `ai_task`, et pas `conversation`.** La décision du lot 3 est
reprise mot pour mot — aucune clé dans le composant, aucun fournisseur codé
en dur. C'est l'ENTITÉ qui change, parce que l'entrée change : un ticket est
une image, pas une phrase. `conversation.process` prend un texte et rend un
texte ; il n'a ni pièce jointe ni réponse structurée, et décrire la photo est
précisément l'information qu'on cherche à extraire.

`ai_task.async_generate_data` apporte trois choses que `conversation` n'a
pas : `attachments` (des `media_content_id` résolus par `media_source`),
`structure` (le modèle rend un objet conforme — la gymnastique du lot 3,
« le premier bloc délimité par des accolades équilibrées », disparaît), et le
même fournisseur sans configuration en plus.

`read_receipt` **ne lève jamais** : la session se clôt et le rangement se
fait, quoi qu'il arrive au modèle.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Sequence

import voluptuous as vol
from homeassistant.components.ai_task import (
    DATA_COMPONENT,
    AITaskEntityFeature,
    async_generate_data,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector as selector_helper

from .parse import RECEIPT_STRUCTURE, ParsedReceipt, parse

_LOGGER = logging.getLogger(__name__)

TASK_NAME = "home_stock_receipt"

# Le téléversement passe par `/api/media_source/local_source/upload`, fourni
# par Home Assistant : le composant n'écrit aucune vue HTTP.
_ATTACHMENT_TYPE = "image/jpeg"


@dataclass(frozen=True)
class ReceiptReadResult:
    parsed: ParsedReceipt | None = None
    raw: str | None = None
    error: str | None = None
    agent_entity_id: str | None = None


def build_instructions(*, session_labels: Sequence[str]) -> str:
    """L'invite, en français, avec les libellés de la session en cours.

    Un modèle qui sait qu'il cherche « LT DEMI ECR 1L » parmi vingt candidats
    connus se trompe beaucoup moins qu'un modèle qui lit dans le vide.
    """
    lines = [
        "Tu lis la photo d'un ticket de caisse français.",
        "Extrais l'enseigne, la date d'achat (AAAA-MM-JJ), le total payé, la "
        "devise, et une entrée par article acheté : le libellé de caisse tel "
        "qu'il est imprimé, la quantité, le prix unitaire et le prix total.",
        "N'invente aucune ligne : si une ligne est illisible, omets-la.",
        "Ignore les remises et promotions de fidélité, les points de "
        "fidélité, les totaux intermédiaires, la TVA, le mode de paiement et "
        "le rendu de monnaie : ce ne sont pas des articles achetés.",
        "Les prix sont en euros, avec un point décimal.",
    ]
    labels = [label for label in session_labels if label]
    if labels:
        lines.append(
            "Les articles suivants ont été scannés pendant ces courses ; "
            "les libellés de caisse en sont souvent des abréviations : "
            + " ; ".join(labels[:60]) + ".")
    return "\n".join(lines)


def _structure_schema() -> vol.Schema:
    """La forme pure de `parse.py`, traduite en `vol.Schema` pour `ai_task`.

    La description vit dans `parse.py`, à côté de la validation qui la
    vérifie : les deux ne peuvent pas diverger sans qu'un test le voie.
    """
    fields: dict[Any, Any] = {}
    for name, field in RECEIPT_STRUCTURE.items():
        key = vol.Required if field.get("required") else vol.Optional
        fields[key(name, description=field.get("description"))] = (
            selector_helper.selector(field["selector"]))
    return vol.Schema(fields, extra=vol.PREVENT_EXTRA)


def _entity_of(hass: HomeAssistant, entity_id: str):
    component = hass.data.get(DATA_COMPONENT)
    return component.get_entity(entity_id) if component is not None else None


def supports_attachments(hass: HomeAssistant, entity_id: str | None) -> bool:
    """Une entité `ai_task` capable de recevoir une image.

    Lu dans la MACHINE À ÉTATS, pas dans le composant `ai_task` : le flux
    d'options s'ouvre sans que l'intégration propriétaire de l'entité soit
    forcément chargée, et `supported_features` est justement l'attribut
    public qui répond dans tous les cas.

    Vérifié AU RÉGLAGE, pas à l'usage : découvrir l'incompatibilité à 21 h
    sur un parking n'est pas un moment acceptable pour l'apprendre.
    """
    if not entity_id:
        return False
    state = hass.states.get(entity_id)
    if state is None:
        entity = _entity_of(hass, entity_id)
        if entity is None:
            return False
        features = int(entity.supported_features or 0)
    else:
        features = int(state.attributes.get("supported_features") or 0)
    return bool(features & AITaskEntityFeature.SUPPORT_ATTACHMENTS)


def _as_payload(data: Any) -> Any:
    """Un modèle peut rendre la structure sérialisée plutôt qu'un objet."""
    if isinstance(data, str):
        try:
            return json.loads(data)
        except ValueError:
            return None
    return data


async def read_receipt(hass: HomeAssistant, *, agent_entity_id: str | None,
                       media_content_id: str, session_labels: Sequence[str],
                       session_started_on: str,
                       today: str) -> ReceiptReadResult:
    """Faire lire la photo. Ne lève jamais : rien ne bloque (§ 10.5)."""
    if not agent_entity_id:
        return ReceiptReadResult(
            error="Aucune entité de lecture n'est configurée : choisissez-en "
                  "une dans les réglages du garde-manger.")
    entity = _entity_of(hass, agent_entity_id)
    if entity is None:
        return ReceiptReadResult(
            agent_entity_id=agent_entity_id,
            error=f"L'entité de lecture {agent_entity_id} n'existe plus.")
    if not entity.supported_features & AITaskEntityFeature.SUPPORT_ATTACHMENTS:
        return ReceiptReadResult(
            agent_entity_id=agent_entity_id,
            error=f"L'entité {agent_entity_id} n'accepte pas de pièce jointe : "
                  "elle ne peut pas lire une photo.")
    try:
        result = await async_generate_data(
            hass,
            task_name=TASK_NAME,
            entity_id=agent_entity_id,
            instructions=build_instructions(session_labels=session_labels),
            structure=_structure_schema(),
            attachments=[{"media_content_id": media_content_id,
                          "media_content_type": _ATTACHMENT_TYPE}],
        )
    except TimeoutError:
        return ReceiptReadResult(
            agent_entity_id=agent_entity_id,
            error="Le délai de lecture du ticket a été dépassé. "
                  "La photo est conservée, vous pouvez réessayer.")
    except Exception as err:                    # noqa: BLE001 — rien ne bloque
        _LOGGER.debug("lecture du ticket échouée", exc_info=True)
        return ReceiptReadResult(
            agent_entity_id=agent_entity_id,
            error=f"Le modèle n'a pas pu lire le ticket ({err}). "
                  "La photo est conservée, vous pouvez réessayer.")

    payload = _as_payload(getattr(result, "data", None))
    parsed = parse(payload, session_started_on=session_started_on, today=today)
    raw = None
    if payload is not None:
        try:
            raw = json.dumps(payload, ensure_ascii=False)
        except (TypeError, ValueError):
            raw = str(payload)
    if not parsed.lines:
        return ReceiptReadResult(
            raw=raw, agent_entity_id=agent_entity_id,
            error="Aucune ligne lisible sur ce ticket. "
                  "La photo est conservée, vous pouvez réessayer.")
    return ReceiptReadResult(parsed=parsed, raw=raw,
                             agent_entity_id=agent_entity_id)
