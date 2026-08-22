"""Ce que `product.external_ref` veut dire, en un seul endroit.

Le lot 0 y écrit l'identifiant Grocy du produit, en clair : « 350 ». Le lot 5
y écrit autre chose — `grocy:spare:CR2032` pour les cinq produits de piles de
rechange, qui n'existent dans aucun catalogue Grocy. Deux espaces de noms dans
une même colonne, et trois lectures du catalogue qui faisaient `int()` sans
regarder : l'import du stock, celui des recettes, et le rejeu du catalogue
lui-même mouraient dès que le geste 7 était passé avant eux.

Un `int()` qui lève au milieu d'une transaction d'import n'est pas une erreur
de plus : c'est un geste du runbook qui s'arrête sur « Valeur invalide » sans
dire lequel des trois cent cinq produits l'a provoqué.
"""
from __future__ import annotations

from typing import Any


def grocy_product_id(ref: Any) -> int | None:
    """L'identifiant Grocy porté par cette référence, ou None.

    None veut dire « cette ligne ne vient pas du catalogue Grocy », pas
    « valeur douteuse » : c'est un cas nominal, pas une anomalie à signaler.
    """
    if ref is None:
        return None
    texte = str(ref).strip()
    if not texte.lstrip("-").isdigit():
        return None
    return int(texte)
