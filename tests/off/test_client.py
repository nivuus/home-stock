"""The cascade, driven by a fake transport. No test here touches the network."""
import pytest

from custom_components.home_stock.off.client import (
    BASES,
    CASCADE_BUDGET,
    OffClient,
)


class FakeTransport:
    """Answers by host. `calls` records the cascade actually walked."""

    def __init__(self, answers: dict[str, tuple[int, dict | None]]):
        self.answers = answers
        self.calls: list[str] = []

    async def get_json(self, url, headers, timeout):
        host = url.split("/")[2]
        self.calls.append(host)
        assert headers["User-Agent"].startswith("home_stock/")
        if host not in self.answers:
            return 200, {"status": 0}
        return self.answers[host]


def _found(name: str) -> tuple[int, dict]:
    return 200, {"status": 1, "product": {"code": "123", "product_name_fr": name}}


@pytest.fixture
def clock():
    """A monotonic clock the test drives by hand."""
    state = {"t": 0.0}

    def now() -> float:
        return state["t"]

    now.advance = lambda seconds: state.__setitem__("t", state["t"] + seconds)
    return now


async def test_a_food_barcode_stops_at_the_first_base(clock):
    transport = FakeTransport({"world.openfoodfacts.org": _found("Muesli")})
    result = await OffClient(transport, user_agent="home_stock/1.0", clock=clock).lookup("123")

    assert result.record.off_source == "food"
    assert result.record.product["product_name_fr"] == "Muesli"
    assert transport.calls == ["world.openfoodfacts.org"]


async def test_a_sponge_is_found_by_walking_down_to_the_products_base(clock):
    transport = FakeTransport({"world.openproductsfacts.org": _found("Éponge")})
    result = await OffClient(transport, user_agent="home_stock/1.0", clock=clock).lookup("123")

    assert result.record.off_source == "products"
    assert transport.calls[:2] == ["world.openfoodfacts.org", "world.openproductsfacts.org"]


async def test_an_unknown_barcode_walks_all_four_and_returns_nothing(clock):
    transport = FakeTransport({})
    result = await OffClient(transport, user_agent="home_stock/1.0", clock=clock).lookup("123")

    assert result.record is None
    assert result.throttled is False
    assert len(transport.calls) == len(BASES)


async def test_a_404_is_an_absence_not_a_failure(clock):
    transport = FakeTransport({
        "world.openfoodfacts.org": (404, None),
        "world.openbeautyfacts.org": _found("Savon"),
    })
    result = await OffClient(transport, user_agent="home_stock/1.0", clock=clock).lookup("123")

    assert result.record.off_source == "beauty"


async def test_a_429_stops_the_cascade_and_says_so(clock):
    """Walking on after a throttle would only deepen it."""
    transport = FakeTransport({"world.openfoodfacts.org": (429, None)})
    result = await OffClient(transport, user_agent="home_stock/1.0", clock=clock).lookup("123")

    assert result.record is None
    assert result.throttled is True
    assert transport.calls == ["world.openfoodfacts.org"]


async def test_the_cascade_gives_up_when_its_budget_is_spent(clock):
    class SlowTransport(FakeTransport):
        async def get_json(self, url, headers, timeout):
            clock.advance(CASCADE_BUDGET / 2 + 0.1)
            return await super().get_json(url, headers, timeout)

    transport = SlowTransport({})
    result = await OffClient(transport, user_agent="home_stock/1.0", clock=clock).lookup("123")

    assert result.record is None
    assert result.timed_out is True
    assert len(transport.calls) < len(BASES)


async def test_a_bulk_retry_waits_and_tries_again(clock):
    slept: list[float] = []

    async def sleeper(seconds: float) -> None:
        slept.append(seconds)
        clock.advance(seconds)

    class ThrottleOnce(FakeTransport):
        def __init__(self):
            super().__init__({})
            self.seen = 0

        async def get_json(self, url, headers, timeout):
            self.seen += 1
            self.calls.append(url.split("/")[2])
            if self.seen == 1:
                return 429, None
            return _found("Muesli")

    transport = ThrottleOnce()
    client = OffClient(transport, user_agent="home_stock/1.0", clock=clock, sleeper=sleeper)
    result = await client.lookup_with_retry("123", attempts=5, backoff=45.0)

    assert result.record is not None
    assert slept == [45.0]


async def test_a_bulk_retry_gives_up_rather_than_hammering(clock):
    async def sleeper(seconds: float) -> None:
        clock.advance(seconds)

    transport = FakeTransport({"world.openfoodfacts.org": (429, None)})
    client = OffClient(transport, user_agent="home_stock/1.0", clock=clock, sleeper=sleeper)
    result = await client.lookup_with_retry("123", attempts=3, backoff=45.0)

    assert result.record is None
    assert result.throttled is True
    assert transport.calls.count("world.openfoodfacts.org") == 3


async def test_the_requested_fields_are_the_ones_the_mapping_reads(clock):
    from custom_components.home_stock.off.client import FIELDS

    for needed in ("product_quantity", "nutriments", "categories_tags",
                   "generic_name_fr", "nutrition_data_per", "serving_quantity",
                   "nutriscore_grade", "labels_tags", "image_front_url"):
        assert needed in FIELDS
