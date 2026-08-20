"""The English messages the domain raises, and the French sentence a person
reads instead.

The domain and application layers raise in English — the code is English, and
so are their exceptions. Two boundaries face a person: the websocket commands
(the panel) and the `home_stock.*` services (a script, a voice answer). Both
translate at that seam, and both must say the same thing, so the vocabulary
lives here once rather than twice.
"""
from __future__ import annotations

import re
from typing import Callable, Final

# Pattern, the websocket error code that fits it, and the French sentence.
# The code is only meaningful to the websocket surface; the services surface
# raises HomeAssistantError, which carries a message and nothing else.
DOMAIN_ERROR_PATTERNS: Final[tuple[tuple[re.Pattern[str], str, Callable[[re.Match], str]], ...]] = (
    (re.compile(r"^unknown article (\d+)$"), "not_found",
     lambda m: f"Article {m.group(1)} inconnu."),
    (re.compile(r"^no article (\d+)$"), "not_found",
     lambda m: f"Article {m.group(1)} inconnu."),
    (re.compile(r"^no product (\d+)$"), "not_found",
     lambda m: f"Produit {m.group(1)} inconnu."),
    (re.compile(r"^unknown or closed batch (\d+)$"), "not_found",
     lambda m: f"Lot {m.group(1)} inconnu ou déjà clôturé."),
    (re.compile(r"^unknown batch (\d+)$"), "not_found",
     lambda m: f"Lot {m.group(1)} inconnu."),
    (re.compile(r"^quantity must not be negative, got (.+)$"), "invalid_value",
     lambda m: f"La quantité ne peut pas être négative (reçu : {m.group(1)})."),
    (re.compile(r"^packaging quantity must be positive, got (.+)$"), "invalid_value",
     lambda m: f"Le conditionnement doit être positif (reçu : {m.group(1)})."),
    (re.compile(r"^quantity must be positive, got (.+)$"), "invalid_value",
     lambda m: f"La quantité doit être positive (reçu : {m.group(1)})."),
    (re.compile(r"^(.+) is not a base unit; expected one of .+$"), "invalid_value",
     lambda m: f"Unité inconnue : {m.group(1)}. Les unités possibles sont g, ml et pièce."),
    (re.compile(r"^requested (.+), only (.+) available$"), "insufficient_stock",
     lambda m: f"Stock insuffisant : {m.group(1)} demandé, {m.group(2)} disponible."),
    (re.compile(r"^batch (\d+) does not belong to product (\d+)$"), "invalid_field",
     lambda m: f"Le lot {m.group(1)} n'appartient pas au produit {m.group(2)}."),
)

GENERIC_CODE: Final = "invalid_value"
GENERIC_MESSAGE: Final = "Valeur invalide."


def french_error(err: Exception) -> tuple[str, str]:
    """The (code, French sentence) pair for a domain exception.

    An unrecognised message falls back to the generic sentence rather than
    being shown raw: an English message with a Python repr in it is not
    something to put in front of someone standing in a shop.
    """
    text = str(err)
    for pattern, code, formatter in DOMAIN_ERROR_PATTERNS:
        match = pattern.match(text)
        if match:
            return code, formatter(match)
    return GENERIC_CODE, GENERIC_MESSAGE


def french_message(err: Exception) -> str:
    """Just the French sentence — what the services surface needs."""
    return french_error(err)[1]
