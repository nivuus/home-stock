"""Compare totals to caps. Nothing else.

A goal is a MAXIMUM, never a floor. On an empty day every total is zero,
nothing is over its cap, and the alert at 04:01 on a day nobody has eaten
yet is impossible by construction — no "is the day empty?" guard appears
here, and one would be the proof a floor had crept in.

This module reads no entity: five of the nine daily sensors are created
disabled, and a goal set on one of them must work without turning it on.
It computes no day boundary either: `domain/foodday.py` has already done it.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..const import GOAL_NUTRIENTS


def _number(value: Any) -> float | None:
    """A usable total, or nothing. NULL is not 0.0, and not infinity either:
    a nutrient the journal cannot quantify is not a breach."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def exceeded(today: Mapping[str, Any], week_mean: Mapping[str, Any],
             goals: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Every cap the day, or the mean of the seven closed days, went over.

    Sorted by ratio descending, then by nutrient name so two equal ratios
    always come out in the same order.
    """
    breaches: list[dict[str, Any]] = []
    for nutrient in GOAL_NUTRIENTS:
        goal = _number(goals.get(nutrient))
        if goal is None or goal <= 0:
            continue
        for scope, totals in (("day", today), ("week", week_mean)):
            value = _number(totals.get(nutrient))
            if value is None or value <= goal:   # `>`, jamais `>=`
                continue
            breaches.append({
                "nutrient": nutrient,
                "scope": scope,
                "value": value,
                "goal": goal,
                "ratio": round(value / goal, 3),
            })
    breaches.sort(key=lambda entry: (-entry["ratio"], entry["nutrient"]))
    return breaches
