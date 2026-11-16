"""The server's folding is the reference the panel's folding is held to.

`tests/fixtures/text_folding.json` lists inputs in several scripts with the
folded form; the panel's test (`frontend/tests/fold.test.ts`) reads the same
file. If either side changes alone, one of the two tests turns red.
"""
import json
from pathlib import Path

import pytest

from custom_components.home_stock.domain.textfold import fold

CASES = json.loads((Path(__file__).parent / "fixtures" / "text_folding.json")
                   .read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", CASES, ids=[case["text"] for case in CASES])
def test_the_server_folds_as_the_shared_table_says(case):
    assert fold(case["text"]) == case["folded"]
