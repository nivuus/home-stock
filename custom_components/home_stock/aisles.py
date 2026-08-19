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

# OFF category tags, from the specific to the generic. resolve_aisle() walks
# categories_tags backwards — OFF orders them general first — so the first
# match is the most precise statement OFF makes about the product.
# Non-food aisle entries (household, beauty, petfood) classify items found in the
# food database; they are not dead weight. resolve_aisle() scopes lookups by
# off_source, so these only match when processing food records.
TAG_TO_AISLE: Final = {
    "en:fresh-vegetables": "Fruits et légumes",
    "en:vegetables": "Fruits et légumes",
    "en:fresh-fruits": "Fruits et légumes",
    "en:fruits": "Fruits et légumes",
    "en:legumes": "Fruits et légumes",
    "en:meats": "Boucherie",
    "en:fresh-meats": "Boucherie",
    "en:poultry": "Boucherie",
    "en:beef": "Boucherie",
    "en:fishes": "Poissonnerie",
    "en:seafood": "Poissonnerie",
    "en:hams": "Charcuterie et traiteur",
    "en:charcuteries": "Charcuterie et traiteur",
    "en:prepared-meats": "Charcuterie et traiteur",
    "en:delicatessen": "Charcuterie et traiteur",
    "en:cheeses": "Fromages",
    "en:dairies": "Crémerie",
    "en:milks": "Crémerie",
    "en:yogurts": "Crémerie",
    "en:creams": "Crémerie",
    "en:butters": "Crémerie",
    "en:eggs": "Crémerie",
    "en:breads": "Boulangerie",
    "en:bakery-products": "Boulangerie",
    "en:viennoiseries": "Boulangerie",
    "en:breakfast-cereals": "Petit-déjeuner",
    "en:breakfasts": "Petit-déjeuner",
    "en:spreads": "Petit-déjeuner",
    "en:jams": "Petit-déjeuner",
    "en:coffees": "Petit-déjeuner",
    "en:teas": "Petit-déjeuner",
    "en:beverages": "Boissons",
    "en:waters": "Boissons",
    "en:juices": "Boissons",
    "en:alcoholic-beverages": "Boissons",
    "en:frozen-foods": "Surgelés",
    "en:ice-creams": "Surgelés",
    "en:frozen-desserts": "Surgelés",
    "en:biscuits": "Épicerie sucrée",
    "en:biscuits-and-cakes": "Épicerie sucrée",
    "en:chocolates": "Épicerie sucrée",
    "en:confectioneries": "Épicerie sucrée",
    "en:sweet-snacks": "Épicerie sucrée",
    "en:desserts": "Épicerie sucrée",
    "en:pastas": "Épicerie salée",
    "en:rice": "Épicerie salée",
    "en:canned-foods": "Épicerie salée",
    "en:sauces": "Épicerie salée",
    "en:condiments": "Épicerie salée",
    "en:spices": "Épicerie salée",
    "en:vegetable-oils": "Épicerie salée",
    "en:salty-snacks": "Épicerie salée",
    "en:groceries": "Épicerie salée",
    "en:hygiene": "Hygiène et beauté",
    "en:body-care": "Hygiène et beauté",
    "en:hair-care": "Hygiène et beauté",
    "en:cosmetics": "Hygiène et beauté",
    "en:household-products": "Entretien et maison",
    "en:cleaning-products": "Entretien et maison",
    "en:laundry": "Entretien et maison",
    "en:sponges": "Entretien et maison",
    "en:batteries": "Entretien et maison",
    "en:pet-foods": "Animalerie",
    "en:cat-foods": "Animalerie",
    "en:dog-foods": "Animalerie",
}

# What a database says about a product when none of its tags is recognised.
SOURCE_TO_AISLE: Final = {
    "food": "Épicerie salée",
    "products": "Entretien et maison",
    "beauty": "Hygiène et beauté",
    "petfood": "Animalerie",
}


def resolve_aisle(categories_tags: list[str] | None, off_source: str | None) -> str:
    """Pick the aisle a scanned article belongs to. Always returns a real aisle.

    OFF orders categories_tags from general to specific. We walk them backwards
    to match the most specific tag first. Tags are normalized (lowercased, spaces
    replaced with hyphens) to handle variations in OFF data.

    TAG_TO_AISLE is consulted only for 'food' source; non-food sources go
    straight to SOURCE_TO_AISLE to avoid cross-database contamination (e.g.,
    en:Creams on beauty is a hand cream, not dairy).
    """
    if off_source == "food":
        for tag in reversed(categories_tags or []):
            normalized_tag = tag.lower().replace(" ", "-")
            aisle = TAG_TO_AISLE.get(normalized_tag)
            if aisle is not None:
                return aisle
    return SOURCE_TO_AISLE.get(off_source or "", FALLBACK_AISLE)
