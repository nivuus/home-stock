"""Lot 2bis: the portion this household decided on, for one product.

Schema-only, no `apply()`: there is nothing to backfill. `article.serving_quantity`
is the manufacturer's portion, `repo.learned_portion` is the median of the last
three meals — and neither is what someone typed. NULL means "work it out",
which on migration day is the whole catalogue.

Numbering: lot 4 claims m006 (shopping). If this module is renumbered, its
file name AND its VERSION move together, in the same commit.
"""
from __future__ import annotations

VERSION = 7

SQL = """
-- La portion que le foyer a fixée à la main, dans l'unité de base du produit.
-- Prime sur la médiane apprise et sur la portion d'Open Food Facts.
ALTER TABLE product ADD COLUMN manual_portion REAL;
"""
