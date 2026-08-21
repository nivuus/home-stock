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

    # --- lot 3 : recettes, planning, repas ---------------------------------
    #
    # Added at the END, never in the middle: the FIRST pattern that matches
    # wins, so inserting above would silently change which sentence an older
    # message produces. A test replays every message the earlier lots covered
    # to prove none of these shadows one.
    #
    # The English left-hand sides are the messages `application.py` actually
    # raises, not the ones the plan sketched: a regex for a sentence nothing
    # raises is dead code that reads like a guarantee.
    (re.compile(r"^unknown recipe (\d+)$"), "not_found",
     lambda m: f"Recette {m.group(1)} introuvable."),
    (re.compile(r"^unknown meal (\d+)$"), "not_found",
     lambda m: f"Repas {m.group(1)} introuvable."),
    (re.compile(r"^unknown ingredient line (\d+)$"), "not_found",
     lambda m: f"Ligne d'ingrédient {m.group(1)} introuvable."),
    (re.compile(r"^unknown slot '(.+?)'; expected one of .+$"), "invalid_value",
     lambda m: f"Créneau inconnu : {m.group(1)}. "
               "Attendu : petit-déjeuner, déjeuner, dîner ou en-cas."),
    (re.compile(r"^unknown match state '(.+?)'; expected one of .+$"), "invalid_value",
     lambda m: f"État d'appariement inconnu : {m.group(1)}."),
    (re.compile(r"^unknown recipe source '(.+?)'; expected one of .+$"), "invalid_value",
     lambda m: f"Source de recette inconnue : {m.group(1)}."),
    (re.compile(r"^meal (\d+) is already done$"), "invalid_value",
     lambda m: "Ce repas a déjà été validé. Un repas validé ne se déplace pas "
               "et ne se revalide pas : ses mouvements portent une date figée."),
    (re.compile(r"^recipe (\d+) has already been cooked$"), "invalid_value",
     lambda m: "Cette recette a servi à un repas validé : désactivez-la plutôt "
               "que de la supprimer, pour que le journal reste lisible."),
    (re.compile(r"^a '(.+?)' match needs a product; .+$"), "invalid_field",
     lambda m: "Choisissez un produit avant de confirmer cet ingrédient."),
    (re.compile(r"^meal (\d+) cannot be validated: (.+)$"), "insufficient_stock",
     lambda m: "Il manque du stock pour au moins un ingrédient : ajustez la "
               "quantité ou retirez ces lignes avant de valider."),
    (re.compile(r"^portions_eaten (.+) exceeds the (.+) parts this meal produces$"),
     "invalid_value",
     lambda m: "On ne mange pas plus de parts que le plat n'en fait."),
    (re.compile(r"^portions_eaten must not be negative, got (.+)$"), "invalid_value",
     lambda m: "Le nombre de parts mangées ne peut pas être négatif."),
    (re.compile(r"^portions_eaten must be a real number, got (.+)$"), "invalid_value",
     lambda m: "Le nombre de parts mangées doit être un nombre."),
    (re.compile(r"^servings must be positive, got (.+)$"), "invalid_value",
     lambda m: "Le nombre de parts doit être supérieur à zéro."),
    (re.compile(r"^servings must be a real number, got (.+)$"), "invalid_value",
     lambda m: "Le nombre de parts doit être un nombre."),
    (re.compile(r"^a recipe serves at least one, got (.+)$"), "invalid_value",
     lambda m: "Une recette est prévue pour au moins une part."),
    (re.compile(r"^a recipe cannot have more than (\d+) (steps|ingredients), got .+$"),
     "invalid_value",
     lambda m: f"Une recette ne peut pas dépasser {m.group(1)} "
               + ("étapes." if m.group(2) == "steps" else "ingrédients.")),
    (re.compile(r"^a meal is exactly one of a recipe, a product or a note, got (\d+)$"),
     "invalid_value",
     lambda m: "Un repas est soit une recette, soit un produit, soit une note — "
               "jamais deux à la fois, jamais aucun."),
    (re.compile(r"^invalid day '(.+?)'; expected YYYY-MM-DD$"), "invalid_value",
     lambda m: f"Date invalide : {m.group(1)}. Format attendu : AAAA-MM-JJ."),
    (re.compile(r"^unknown reason '(.+?)'; expected one of .+$"), "invalid_value",
     lambda m: f"Motif de mouvement inconnu : {m.group(1)}."),
    (re.compile(r"^no location to put the dish in$"), "invalid_value",
     lambda m: "Aucun emplacement où ranger le plat : déclarez au moins un "
               "emplacement avant de valider un repas."),
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

    # --- lot 4 : liste de courses, ticket, correction -----------------------
    # EN FIN de tuple, jamais au milieu : le PREMIER motif qui correspond
    # gagne, et une insertion plus haut changerait la phrase d'un message
    # plus ancien. Un test rejoue les messages des lots antérieurs.
    (re.compile(r"^unknown movement (\d+)$"), "not_found",
     lambda m: f"Mouvement {m.group(1)} inconnu."),
    (re.compile(r"^movement (\d+) is already a correction$"), "invalid_value",
     lambda m: "Cette ligne est déjà une correction : corriger une correction, "
               "c'est refaire la saisie."),
    (re.compile(r"^movement (\d+) has already been corrected$"), "invalid_value",
     lambda m: "Cette ligne a déjà été corrigée."),
    (re.compile(r"^a transfer movement cannot be corrected$"), "invalid_value",
     lambda m: "Un transfert ne se corrige pas : il ne change aucune quantité, "
               "seulement un emplacement."),
    (re.compile(r"^a conversion movement cannot be corrected$"), "invalid_value",
     lambda m: "Une conversion d'unité ne se corrige pas ligne à ligne : "
               "ses deux écritures vont par paire."),
    (re.compile(r"^a cooked movement cannot be corrected$"), "invalid_value",
     lambda m: "Un mouvement de cuisine s'annule en corrigeant le repas entier, "
               "pas ligne à ligne."),
    (re.compile(r"^reversing movement (\d+) would leave batch (\d+) negative;"
                r" only (.+) left$"), "insufficient_stock",
     lambda m: f"Impossible d'annuler cette ligne : le lot n'a plus que {m.group(3)}. "
               "Le stock a déjà été repris ailleurs."),
    (re.compile(r"^meal (\d+) was never validated$"), "invalid_value",
     lambda m: "Ce repas n'a pas été validé : il n'y a rien à annuler."),
    (re.compile(r"^unknown receipt (\d+)$"), "not_found",
     lambda m: f"Ticket {m.group(1)} inconnu."),
    (re.compile(r"^receipt (\d+) was never read$"), "invalid_value",
     lambda m: "Ce ticket n'a pas été lu : rien à appliquer."),
    (re.compile(r"^meal (\d+) cannot be corrected: its dish has been started$"),
     "invalid_value",
     lambda m: "Ce plat a été entamé depuis : corrigez la consommation fautive, "
               "ou finissez le plat avant d'annuler le repas."),
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
