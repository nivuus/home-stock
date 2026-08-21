"""La réponse structurée d'un modèle → des lignes validées, une par une.

Aucun réseau, aucun `hass`, aucun SQLite. `parse()` **ne lève jamais** : le
seul appelant est une lecture de ticket, et un ticket illisible est un
inconvénient, pas une panne.

**La réponse structurée est validée quand même.** Un schéma contraint la
FORME, pas la VRAISEMBLANCE : rien n'empêche un modèle de rendre 4 000 € ou
une date en 1970.

**Une ligne fautive est écartée SEULE**, contrairement à la nutrition OFF du
lot 1 où un dépassement refuse toute la fiche. La différence est assumée :
une fiche OFF est un tout cohérent dont une valeur aberrante trahit la table
entière ; un ticket est une suite de lignes indépendantes, et perdre les
dix-neuf bonnes parce que la vingtième est illisible n'aide personne.
L'écart au total rend l'omission visible.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Mapping

from ..const import (
    MAX_RECEIPT_LINE_PRICE,
    MAX_RECEIPT_LINE_QUANTITY,
    MAX_RECEIPT_LINES,
    MAX_RECEIPT_TOTAL,
    RECEIPT_BACKDATE_DAYS,
    RECEIPT_TOTAL_TOLERANCE,
)

# La forme demandée au modèle. Décrite ici et pas dans `task.py` : c'est le
# même fichier qui la demande et qui la vérifie, donc les deux ne peuvent
# pas diverger sans qu'un test le voie.
RECEIPT_STRUCTURE: dict[str, Any] = {
    "store": {"description": "Le nom de l'enseigne, tel qu'il est imprimé",
              "required": False, "selector": {"text": None}},
    "purchased_on": {"description": "La date d'achat, au format AAAA-MM-JJ",
                     "required": False, "selector": {"text": None}},
    "total": {"description": "Le total payé, en euros",
              "required": False, "selector": {"number": None}},
    "currency": {"description": "Le code de la devise, par exemple EUR",
                 "required": False, "selector": {"text": None}},
    "lines": {
        "description": "Une entrée par article acheté : libellé de caisse, "
                       "quantité, prix unitaire et prix total",
        "required": False,
        "selector": {"object": None},
    },
}


@dataclass(frozen=True)
class ParsedLine:
    position: int
    label: str
    quantity: float | None
    unit_price: float | None
    total_price: float | None


@dataclass(frozen=True)
class ParsedReceipt:
    store: str | None = None
    purchased_on: str | None = None
    total: float | None = None
    currency: str | None = None
    lines: tuple[ParsedLine, ...] = ()
    dropped: tuple[str, ...] = ()
    total_gap: float | None = None
    warnings: tuple[str, ...] = ()


def _text(value: Any, *, limit: int = 200) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned[:limit] or None


def _number(value: Any) -> float | None:
    """Un nombre fini, ou rien. `bool` est refusé : `True` vaut 1.0 en
    Python, et une quantité de `True` article n'a aucun sens."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def _iso_day(value: Any) -> date | None:
    text = _text(value, limit=10)
    if text is None or len(text) != 10:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _parse_line(raw: Any, position: int) -> tuple[ParsedLine | None, str | None]:
    if not isinstance(raw, Mapping):
        return None, f"ligne {position} : forme illisible"
    label = _text(raw.get("label"))
    if label is None:
        return None, f"ligne {position} : sans libellé"
    quantity = _number(raw.get("quantity"))
    if quantity is not None and not 0 < quantity <= MAX_RECEIPT_LINE_QUANTITY:
        # `0 <` strict : une ligne de zéro article n'a pas été achetée, c'est
        # une remise ou un point de fidélité déguisé.
        return None, f"« {label} » : quantité invraisemblable ({quantity})"
    prices = {}
    for field in ("unit_price", "total_price"):
        price = _number(raw.get(field))
        if price is not None and not 0 <= price <= MAX_RECEIPT_LINE_PRICE:
            return None, f"« {label} » : prix invraisemblable ({price} €)"
        prices[field] = price
    if prices["unit_price"] is None and prices["total_price"] is None:
        # Un ticket sert à RELIRE DES PRIX. Une ligne qui n'en porte aucun
        # ne peut rien corriger, et la garder ferait croire à une lecture
        # utilisable — c'est l'écart au total qui doit la signaler.
        return None, f"« {label} » : aucun prix lu"
    return ParsedLine(
        position=position,
        label=label,
        quantity=quantity,
        unit_price=_number(raw.get("unit_price")),
        total_price=_number(raw.get("total_price")),
    ), None


def parse(payload: Any, *, session_started_on: str, today: str) -> ParsedReceipt:
    """Lire ce que le modèle a rendu, sans jamais lever."""
    if not isinstance(payload, Mapping):
        return ParsedReceipt()

    dropped: list[str] = []
    warnings: list[str] = []

    raw_lines = payload.get("lines")
    if not isinstance(raw_lines, (list, tuple)):
        raw_lines = []
    if len(raw_lines) > MAX_RECEIPT_LINES:
        warnings.append(
            f"Ticket tronqué : plus de {MAX_RECEIPT_LINES} lignes lues.")
        raw_lines = list(raw_lines)[:MAX_RECEIPT_LINES]

    lines: list[ParsedLine] = []
    for raw in raw_lines:
        line, refusal = _parse_line(raw, len(lines) + 1)
        if line is None:
            dropped.append(refusal or "ligne illisible")
            continue
        lines.append(line)

    total = _number(payload.get("total"))
    if total is not None and not 0 <= total <= MAX_RECEIPT_TOTAL:
        warnings.append(f"Total invraisemblable ({total} €), ignoré.")
        total = None

    purchased_on = _purchase_day(payload.get("purchased_on"),
                                 session_started_on=session_started_on,
                                 today=today, warnings=warnings)

    gap = _total_gap(total, lines)
    if gap is not None:
        warnings.append(
            f"La somme des lignes s'écarte du total de {abs(gap):.2f} €.")

    return ParsedReceipt(
        store=_text(payload.get("store")),
        purchased_on=purchased_on,
        total=total,
        currency=_text(payload.get("currency"), limit=8),
        lines=tuple(lines),
        dropped=tuple(dropped),
        total_gap=gap,
        warnings=tuple(warnings),
    )


def _purchase_day(value: Any, *, session_started_on: str, today: str,
                  warnings: list[str]) -> str | None:
    """La date d'achat, si elle tombe dans la fenêtre plausible.

    Hors fenêtre, elle ne rend pas le ticket illisible : elle disparaît, et
    le panneau demande. Deux jours en arrière parce qu'on photographie
    parfois le ticket le lendemain matin — pas trois, parce qu'au-delà on
    ne parle plus du même voyage.
    """
    day = _iso_day(value)
    if day is None:
        return None
    started = _iso_day(session_started_on) or _iso_day(today)
    end = _iso_day(today)
    if started is None or end is None:
        return day.isoformat()
    if not (started - timedelta(days=RECEIPT_BACKDATE_DAYS)) <= day <= end:
        warnings.append(f"Date lue hors de la fenêtre plausible ({day.isoformat()}).")
        return None
    return day.isoformat()


def _total_gap(total: float | None, lines: list[ParsedLine]) -> float | None:
    """L'écart entre le total lu et la somme des lignes, au-delà de 2 %.

    Signalé, JAMAIS bloquant : c'est ce qui rend visible qu'une ligne a été
    écartée, et c'est plus utile qu'un refus qui ne dirait pas laquelle.
    """
    if total is None or not lines:
        return None
    summed = sum(line.total_price for line in lines
                 if line.total_price is not None)
    gap = total - summed
    if total <= 0 or abs(gap) <= total * RECEIPT_TOTAL_TOLERANCE:
        return None
    return round(gap, 4)
