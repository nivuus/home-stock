"""The cascade, driven by a fake transport. No test here touches the network."""
import pytest

from custom_components.home_stock.off.client import (
    AiohttpTransport,
    BASES,
    CASCADE_BUDGET,
    OffClient,
    TIMEOUT_PER_BASE,
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
                   "nutriscore_grade", "labels_tags", "image_front_url",
                   "packagings", "packaging_tags"):
        assert needed in FIELDS


# --- Fix round 1: a malformed 200 body must not raise ----------------------

@pytest.mark.parametrize("malformed_payload", [["a", "list"], "a bare string", 42])
async def test_a_non_dict_payload_is_treated_as_absence_not_a_crash(clock, malformed_payload):
    class MalformedTransport(FakeTransport):
        async def get_json(self, url, headers, timeout):
            self.calls.append(url.split("/")[2])
            return 200, malformed_payload

    transport = MalformedTransport({})
    result = await OffClient(transport, user_agent="home_stock/1.0", clock=clock).lookup("123")

    assert result.record is None
    assert result.throttled is False
    assert len(transport.calls) == len(BASES)


# --- Fix round 2: a malformed "product" inside an otherwise well-formed body ---

@pytest.mark.parametrize("malformed_product", [["a", "list"], "a bare string", 42])
async def test_a_non_dict_product_is_treated_as_absence_not_a_crash(clock, malformed_product):
    """status == 1 with a "product" that is not a dict must not reach
    map_article() (which raises ValueError on exactly that shape) — this is
    the same defensive shape already applied to the payload and item list."""
    class MalformedProductTransport(FakeTransport):
        async def get_json(self, url, headers, timeout):
            self.calls.append(url.split("/")[2])
            return 200, {"status": 1, "product": malformed_product}

    transport = MalformedProductTransport({})
    result = await OffClient(transport, user_agent="home_stock/1.0", clock=clock).lookup("123")

    assert result.record is None
    assert result.throttled is False
    assert len(transport.calls) == len(BASES)


# --- Fix round 1: the budget bounds the wall clock, not just the per-call check ---

async def test_the_cascade_gives_each_base_only_the_time_left_in_the_budget(clock):
    """A base queried near the end of the budget must not get a full
    TIMEOUT_PER_BASE on top of what is already spent."""
    timeouts: list[float] = []

    class LatentTransport(FakeTransport):
        LATENCY = 7.0

        async def get_json(self, url, headers, timeout):
            timeouts.append(timeout)
            clock.advance(min(self.LATENCY, timeout))
            return await super().get_json(url, headers, timeout)

    transport = LatentTransport({})
    started = clock()
    result = await OffClient(transport, user_agent="home_stock/1.0", clock=clock).lookup("123")

    assert timeouts[0] == TIMEOUT_PER_BASE
    assert timeouts[-1] < TIMEOUT_PER_BASE
    assert clock() - started <= CASCADE_BUDGET
    assert result.timed_out is True  # cut short: not every base got queried


# --- Fix round 1: a full walk that overruns slightly is absence, not a timeout ---

async def test_a_full_walk_that_overruns_slightly_is_not_reported_as_timed_out(clock):
    """Every base got queried and answered nothing; that is a genuine
    absence, not "we did not look", even though the last call pushes the
    clock a bit past CASCADE_BUDGET."""

    class SlowButThorough(FakeTransport):
        async def get_json(self, url, headers, timeout):
            clock.advance(5.5)
            return await super().get_json(url, headers, timeout)

    transport = SlowButThorough({})
    started = clock()
    result = await OffClient(transport, user_agent="home_stock/1.0", clock=clock).lookup("123")

    assert clock() - started > CASCADE_BUDGET  # it did overrun, slightly
    assert result.timed_out is False
    assert result.record is None
    assert len(transport.calls) == len(BASES)


# --- Fix round 1: AiohttpTransport, driven by a fake session, never a socket ---

class FakeResponse:
    def __init__(self, status: int, body):
        self.status = status
        self._body = body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def json(self, content_type=None):
        return self._body


class FakeSession:
    def __init__(self, response=None, *, raises: Exception | None = None):
        self._response = response
        self._raises = raises
        self.calls: list[tuple[str, dict, float]] = []

    def get(self, url, *, headers, timeout):
        self.calls.append((url, headers, timeout))
        if self._raises is not None:
            raise self._raises
        return self._response


async def test_aiohttp_transport_returns_the_decoded_body_on_200():
    body = {"status": 1, "product": {"code": "123"}}
    session = FakeSession(FakeResponse(200, body))
    transport = AiohttpTransport(session)

    status, payload = await transport.get_json("https://example.org/x", {}, 10.0)

    assert status == 200
    assert payload == body


async def test_aiohttp_transport_turns_a_404_into_an_absence():
    session = FakeSession(FakeResponse(404, None))
    transport = AiohttpTransport(session)

    status, payload = await transport.get_json("https://example.org/x", {}, 10.0)

    assert status == 404
    assert payload is None


async def test_aiohttp_transport_turns_a_429_into_a_throttle_signal():
    session = FakeSession(FakeResponse(429, None))
    transport = AiohttpTransport(session)

    status, payload = await transport.get_json("https://example.org/x", {}, 10.0)

    assert status == 429
    assert payload is None


async def test_aiohttp_transport_lets_whatever_the_session_raises_propagate():
    session = FakeSession(raises=ConnectionError("no route to host"))
    transport = AiohttpTransport(session)

    with pytest.raises(ConnectionError):
        await transport.get_json("https://example.org/x", {}, 10.0)


async def test_lookup_swallows_what_the_aiohttp_transport_raises(clock):
    session = FakeSession(raises=ConnectionError("no route to host"))
    transport = AiohttpTransport(session)
    result = await OffClient(transport, user_agent="home_stock/1.0", clock=clock).lookup("123")

    assert result.record is None
    assert result.throttled is False
    assert result.timed_out is False


def test_the_packaging_fields_are_asked_for_by_name():
    """La donnée d'emballage n'est PAS gratuite : `off_raw` ne contient que ce
    que `fields=` a demandé. Retirer ces deux champs un jour viderait
    silencieusement la consigne de tri de tout le catalogue — sans erreur,
    sans log, sans que rien d'autre ne tombe. D'où ce test nommé."""
    from custom_components.home_stock.off.client import FIELDS

    assert "packagings" in FIELDS
    assert "packaging_tags" in FIELDS


def test_the_existing_fixtures_carry_no_packaging_which_is_the_point():
    """Les fiches déjà capturées n'ont pas d'emballage, et n'en auront jamais :
    il n'a pas été demandé au moment de la capture. Ce test fige la
    conséquence — aucune migration, aucun `apply()`, aucun backfill ne peut
    inventer cette donnée (spec § 4, amendement A1)."""
    import json
    from pathlib import Path

    fiches = json.loads(
        (Path(__file__).parent.parent / "fixtures/off/soeurs.json").read_text())
    for code, fiche in fiches.items():
        # La fiche capturée est sous "product" : c'est là que le champ manquerait.
        produit = fiche["product"]
        assert "packagings" not in produit, code
        assert "packaging_tags" not in produit, code
