"""The one unit table every Grocy import shares.

Three imports converting units each in their own way would end up diverging —
and a unit conversion that diverges is a bottle and a half of olive oil per
burger. The tables below are *moved* here from import_grocy.py, not copied:
the lot 0 module re-imports these very objects.
"""
from __future__ import annotations

MASS_UNITS = {"g": 1.0, "kg": 1000.0}
VOLUME_UNITS = {"ml": 1.0, "cl": 10.0, "l": 1000.0}
CONTAINER_UNITS = {
    "Pièce", "Paquet", "Pot", "Bouteille", "Barquette", "Brique", "Boîte",
    "Sachet", "Lot",
}
# Doser n'est pas stocker : un produit stocké « à la cuillère » est une erreur
# de saisie. base_unit() les refuse donc explicitement.
DOSAGE_UNITS = {"cs", "cc"}


def base_unit(unit_name: str) -> tuple[str, float] | None:
    """The base unit and the factor towards it, or None when there is none."""
    if unit_name in MASS_UNITS:
        return "g", MASS_UNITS[unit_name]
    if unit_name in VOLUME_UNITS:
        return "ml", VOLUME_UNITS[unit_name]
    if unit_name in CONTAINER_UNITS:
        return "piece", 1.0
    return None
