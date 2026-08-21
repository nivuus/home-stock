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
    (re.compile(r"^parts_total and parts_mine go together$"), "invalid_value",
     lambda m: "Les parts sont incohérentes : il faut donner "
               "« parts servies » et « parts mangées » ensemble, ou aucun des deux."),
    (re.compile(r"^a (.+) movement cannot be shared$"), "invalid_value",
     lambda m: f"Un mouvement « {m.group(1)} » ne peut pas être partagé en parts."),
    (re.compile(r"^parts_total must be between 1 and (\d+)$"), "invalid_value",
     lambda m: f"Le nombre de parts servies doit être entre 1 et {m.group(1)}."),
    (re.compile(r"^parts_mine must be between 0 and parts_total$"), "invalid_value",
     lambda m: "Les parts sont incohérentes : on ne mange pas plus de parts "
               "qu'il n'en a été servi."),
    # --- lot 5 : piles, équipements et consommables -------------------------
    # L'ordre compte : premier motif qui matche gagne. Ces couples s'ajoutent
    # EN FIN de tuple, jamais au milieu.
    (re.compile(r"^keep_percent must not be below low_percent"), "invalid_value",
     lambda m: "Le seuil de maintien ne peut pas être sous le seuil d'apparition : "
               "la tâche apparaîtrait et se refermerait à chaque synchronisation."),
    (re.compile(r"^an untracked battery needs a reason$"), "invalid_value",
     lambda m: "Ignorer une pile demande un motif — sinon personne ne saura "
               "pourquoi elle n'est plus suivie."),
    (re.compile(r"^a built_in battery has no spare$"), "invalid_value",
     lambda m: "Une batterie intégrée ne se remplace pas : elle n'a pas de pile de rechange."),
    (re.compile(r"^a primary battery cannot be charged$"), "invalid_value",
     lambda m: "Une pile jetable ne se recharge pas."),
    (re.compile(r"^a built_in battery cannot be replaced$"), "invalid_value",
     lambda m: "Une batterie intégrée ne se remplace pas : on la recharge."),
    (re.compile(r"^cannot consume a spare without a spare product$"), "invalid_value",
     lambda m: "Aucune pile de rechange n'est rattachée : impossible d'en sortir "
               "une du placard."),
    (re.compile(r"^unknown battery (\d+)$"), "not_found",
     lambda m: f"Pile {m.group(1)} inconnue."),
    (re.compile(r"^unknown equipment (\d+)$"), "not_found",
     lambda m: f"Équipement {m.group(1)} inconnu."),
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
