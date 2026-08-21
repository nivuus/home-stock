"""Which price to offer when an article is scanned.

Pure. The caller has already looked up what it could; this decides what wins.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PriceSuggestion:
    price_per_base_unit: float | None = None
    source: str | None = None
    store: str | None = None
    # Amendement A3 : une SUGGESTION n'est pas une OBSERVATION. Seule la
    # branche « ce magasin » repose sur un prix que quelqu'un a réellement
    # vu ici. Écrire les deux autres comme observées ferait que la cascade
    # se nourrit de ses propres suppositions dès le deuxième voyage.
    observed: bool = False


def suggest_price(*, in_store: float | None, open_prices: float | None,
                  last_known: float | None, store: str | None) -> PriceSuggestion:
    """The first price available, in order of how much it is worth trusting.

    `is not None` rather than truthiness throughout: a free item priced at 0 is
    a real observation, and dropping it would silently fall through to a stale
    price from another shop.
    """
    if in_store is not None:
        return PriceSuggestion(in_store, "store", store, observed=True)
    if open_prices is not None:
        return PriceSuggestion(open_prices, "open_prices", store)
    if last_known is not None:
        return PriceSuggestion(last_known, "last_known", None)
    return PriceSuggestion()
