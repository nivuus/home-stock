"""The harness itself is worth one test: everything else depends on it."""
from custom_components.home_stock.const import (
    BASE_UNITS,
    DEFAULT_EXPIRATION_ALERT_DAYS,
    DOMAIN,
    REASONS,
)


def test_constants_are_exposed():
    assert DOMAIN == "home_stock"
    assert BASE_UNITS == ("g", "ml", "piece")
    assert "consumption" in REASONS
    assert DEFAULT_EXPIRATION_ALERT_DAYS == 3
