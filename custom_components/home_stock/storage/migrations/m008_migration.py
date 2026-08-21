"""Lot 7: the Grocy id of a batch, so the stock import is replayable.

`batch` is the only table in the schema without an external_ref. product,
article, recipe, recipe_ingredient, meal, battery and equipment all have one,
all for the reason written in lot 0: "Grocy id, for a replayable import". A
stock import that could not be replayed would be the only one in the chain,
and the most dangerous — it is the one you re-run after fixing a price.

Schema-only, no apply(): there is nothing to backfill. The single batch in
production is the 19 August trial, which does not come from Grocy.

Numbering: the file name and VERSION move together, in the same commit. A
strict contiguity test requires [1..8].
"""
from __future__ import annotations

VERSION = 8

SQL = """
-- L'id Grocy du lot. Même rôle exactement que product.external_ref au lot 0 :
-- c'est ce qui rend l'import du stock rejouable, donc ce qui permet de le
-- lancer en simulation, de corriger la source, et de le relancer.
ALTER TABLE batch ADD COLUMN external_ref TEXT;

-- Partiel, comme idx_recipe_source : un lot créé au scan n'a pas de référence
-- externe, et cent lots sans référence ne doivent pas se gêner.
CREATE UNIQUE INDEX idx_batch_external_ref
  ON batch(external_ref) WHERE external_ref IS NOT NULL;
"""
