"""The harness itself is worth one test: everything else depends on it."""
from custom_components.home_stock.const import (
    BASE_UNITS,
    CONSUME_REASONS,
    DEFAULT_EXPIRATION_ALERT_DAYS,
    DOMAIN,
    REASON_COOKED,
    REASONS,
)


def test_constants_are_exposed():
    assert DOMAIN == "home_stock"
    assert BASE_UNITS == ("g", "ml", "piece")
    assert "consumption" in REASONS
    assert DEFAULT_EXPIRATION_ALERT_DAYS == 3


def test_reasons_keeps_its_exact_order():
    """L'ordre de `REASONS` est un contrat, pas une commodité.

    Les lots 3 et 5 sont écrits en parallèle dans deux worktrees et fusionnés
    ensuite : chacun ajoute son motif. Un motif inséré au MILIEU du tuple
    décalerait tous les suivants, et les valeurs déjà écrites dans `movement`
    changeraient de sens sans qu'aucune migration ne s'en aperçoive. Le seul
    ajout sûr est en fin de tuple, et c'est ce que ce test rend exécutoire —
    le plan du lot 3 le croyait déjà écrit ; il ne l'était pas.
    """
    assert REASONS == (
        "purchase",
        "consumption",
        "waste",
        "expired",
        "inventory",
        "transfer",
        "conversion",
        "cooked",
    )


def test_cooked_is_a_reason_but_never_a_consumed_one():
    """Cuisiner déplace de la valeur, ça n'en retire pas.

    Les six ingrédients quittent leurs lots pour devenir un plat qui, lui,
    entre en stock. Si `cooked` rejoignait `CONSUME_REASONS`, ces sorties
    seraient comptées comme mangées : les kcal du jour, les macros et le coût
    du jour compteraient deux fois le même repas, une fois à la cuisson et une
    fois à la bouchée.
    """
    assert REASON_COOKED in REASONS
    assert REASON_COOKED not in CONSUME_REASONS
    assert CONSUME_REASONS == ("consumption", "waste", "expired")
