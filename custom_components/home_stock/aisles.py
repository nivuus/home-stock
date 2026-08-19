"""The aisle referential: the order of a shopping trip, and how the catalogue
maps onto it.

Kept out of the migration module because two consumers need it: the migration
that seeds the table, and the OFF classification that gives a scanned article
an aisle. No hass, no network, no SQLite.
"""
from __future__ import annotations

from typing import Final

# Walking order of a supermarket. Position in the table follows this tuple.
AISLES: Final = (
    "Fruits et légumes",
    "Boucherie",
    "Poissonnerie",
    "Charcuterie et traiteur",
    "Crémerie",
    "Fromages",
    "Boulangerie",
    "Épicerie salée",
    "Épicerie sucrée",
    "Petit-déjeuner",
    "Boissons",
    "Surgelés",
    "Hygiène et beauté",
    "Entretien et maison",
    "Animalerie",
    "Autre",
)

FALLBACK_AISLE: Final = "Autre"

# The 21 categories the lot 0 import created from Grocy's product groups.
CATEGORY_TO_AISLE: Final = {
    "Viande": "Boucherie",
    "Poisson": "Poissonnerie",
    "Légume": "Fruits et légumes",
    "Fruit": "Fruits et légumes",
    "Fromage": "Fromages",
    "Œufs": "Crémerie",
    "Produit laitier": "Crémerie",
    "Charcuterie": "Charcuterie et traiteur",
    "Épicerie": "Épicerie salée",
    "Condiment": "Épicerie salée",
    "Épice": "Épicerie salée",
    "Pâtes": "Épicerie salée",
    "Matière grasse": "Épicerie salée",
    "Boulangerie": "Boulangerie",
    "Céréale": "Petit-déjeuner",
    "Boisson": "Boissons",
    "Surgelé": "Surgelés",
    "Snack": "Épicerie sucrée",
    "Ménage": "Entretien et maison",
    "Équipement": "Entretien et maison",
    "Pharmacie/Parapharmacie": "Hygiène et beauté",
}

# Task 2 (OFF classification) adds TAG_TO_AISLE, SOURCE_TO_AISLE and
# resolve_aisle() here.
