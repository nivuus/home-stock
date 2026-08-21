"""L'algèbre d'une contrepassation. Pur : aucun `hass`, aucun SQLite.

Une erreur de signe ici est catastrophique et SILENCIEUSE — elle ne lève
rien, elle fausse une comptabilité. D'où un module que l'on peut épingler
sans base et sans Home Assistant.

`reason` est le COMPTE COMPTABLE, pas une étiquette d'affichage. Une
contrepassation porte donc le motif de la ligne qu'elle annule, et le lien
vit dans `movement.corrects_id` (amendement A1). Un motif `correction`
serait invisible de `repo.totals_between`, `repo._PERSONAL_SUMS`,
`repo.journal_entries`, `repo.counted_movements` et de onze capteurs : le
stock reviendrait, mais ni les kilocalories ni les euros.
"""
from __future__ import annotations

from typing import Any, Mapping

from ..const import (
    MACRO_COLUMNS,
    REASON_CONVERSION,
    REASON_COOKED,
    REASON_TRANSFER,
    REASONS,
)


class CorrectionError(ValueError):
    """Un mouvement qui ne se contrepasse pas."""


# `transfer` : quantité nulle de part et d'autre, rien à compenser.
# `conversion` et `cooked` : des PAIRES transactionnelles — les compenser
# une ligne à la fois laisserait le stock incohérent entre les deux.
_UNCORRECTABLE = (REASON_TRANSFER, REASON_CONVERSION, REASON_COOKED)
CORRECTABLE_REASONS: tuple[str, ...] = tuple(
    reason for reason in REASONS if reason not in _UNCORRECTABLE
)


def correction_key(movement_id: int) -> str:
    """La clé d'idempotence d'une contrepassation, dérivée et stable."""
    return f"correction:{movement_id}"


def _flip(value: float | None) -> float | None:
    """`None` reste `None` : zéro voudrait dire « mesuré à zéro » (lot 2),
    et compenser un NULL par 0.0 inventerait une mesure."""
    return None if value is None else -value


def check_correctable(movement: Mapping[str, Any], *, allow_cooked: bool = False) -> None:
    """Lève `CorrectionError` si ce mouvement ne peut pas être contrepassé.

    `allow_cooked` n'est vrai que pour `application.correct_meal()`, seul
    appelant autorisé : il contrepasse le bloc entier, dans l'ordre inverse,
    en une transaction.
    """
    if movement.get("corrects_id") is not None:
        raise CorrectionError("ce mouvement est déjà une correction")
    reason = movement.get("reason")
    if reason == REASON_COOKED and allow_cooked:
        return
    if reason not in CORRECTABLE_REASONS:
        raise CorrectionError(f"un mouvement « {reason} » ne se corrige pas ligne à ligne")


def _macros(movement: Mapping[str, Any], *, flip: bool) -> dict[str, float | None]:
    return {
        column: _flip(movement.get(column)) if flip else movement.get(column)
        for column in MACRO_COLUMNS
    }


def reversal(movement: Mapping[str, Any], *, moment: str) -> dict[str, Any]:
    """La ligne miroir, prête pour `repo.insert_movement`.

    Les parts sont RECOPIÉES, jamais inversées : ce sont des ratios positifs,
    et c'est le signe des valeurs qu'elles multiplient qui porte l'annulation.
    """
    return {
        "occurred_at": moment,
        "product_id": movement["product_id"],
        "article_id": movement["article_id"],
        "batch_id": movement.get("batch_id"),
        "quantity": _flip(movement["quantity"]),
        "reason": movement["reason"],
        "base_unit": movement["base_unit"],
        "kcal": _flip(movement.get("kcal")),
        "cost": _flip(movement.get("cost")),
        "macros": _macros(movement, flip=True),
        "parts_total": movement.get("parts_total"),
        "parts_mine": movement.get("parts_mine"),
        "corrects_id": movement["id"],
        "idempotency_key": correction_key(movement["id"]),
    }


def reprice(movement: Mapping[str, Any], *, price_per_base_unit: float | None,
            moment: str) -> dict[str, Any]:
    """La réécriture au coût corrigé (§ 12.4). Nutriments IDENTIQUES : un
    prix faux n'a jamais faussé des calories. Ce n'est pas une annulation —
    `corrects_id` reste nul."""
    quantity = movement["quantity"]
    cost = None if price_per_base_unit is None else abs(quantity) * price_per_base_unit
    return {
        "occurred_at": moment,
        "product_id": movement["product_id"],
        "article_id": movement["article_id"],
        "batch_id": movement.get("batch_id"),
        "quantity": quantity,
        "reason": movement["reason"],
        "base_unit": movement["base_unit"],
        "kcal": movement.get("kcal"),
        "cost": cost,
        "macros": _macros(movement, flip=False),
        "parts_total": movement.get("parts_total"),
        "parts_mine": movement.get("parts_mine"),
        "corrects_id": None,
        "idempotency_key": None,
    }
