"""Open Prices, driven by a fake transport."""
import pytest

from custom_components.home_stock.off.open_prices import latest_price


class FakeTransport:
    def __init__(self, status=200, payload=None, raises=None):
        self.status, self.payload, self.raises = status, payload, raises
        self.calls: list[str] = []

    async def get_json(self, url, headers, timeout):
        self.calls.append(url)
        if self.raises:
            raise self.raises
        return self.status, self.payload


def _items(*items):
    return {"items": list(items)}


async def test_an_item_price_is_brought_back_to_the_base_unit():
    transport = FakeTransport(payload=_items(
        {"price": 2.5, "currency": "EUR", "date": "2026-08-10",
         "product": {"product_quantity": 500}}))

    price = await latest_price(transport, "123", base_unit="g", net_quantity=500,
                               user_agent="home_stock/1.0")

    assert price == pytest.approx(0.005)


async def test_the_weight_from_open_prices_beats_the_one_we_guessed():
    transport = FakeTransport(payload=_items(
        {"price": 2.0, "currency": "EUR", "date": "2026-08-10",
         "product": {"product_quantity": 1000}}))

    price = await latest_price(transport, "123", base_unit="g", net_quantity=500,
                               user_agent="home_stock/1.0")

    assert price == pytest.approx(0.002)


async def test_a_price_in_another_currency_is_ignored():
    transport = FakeTransport(payload=_items(
        {"price": 3.0, "currency": "CHF", "date": "2026-08-10",
         "product": {"product_quantity": 500}}))

    assert await latest_price(transport, "123", base_unit="g", net_quantity=500,
                              user_agent="home_stock/1.0") is None


async def test_without_a_net_weight_no_price_per_base_unit_can_exist():
    transport = FakeTransport(payload=_items(
        {"price": 3.0, "currency": "EUR", "date": "2026-08-10", "product": {}}))

    assert await latest_price(transport, "123", base_unit="g", net_quantity=None,
                              user_agent="home_stock/1.0") is None


async def test_a_network_failure_is_silent_because_a_suggestion_is_not_load_bearing():
    transport = FakeTransport(raises=TimeoutError())

    assert await latest_price(transport, "123", base_unit="g", net_quantity=500,
                              user_agent="home_stock/1.0") is None


async def test_an_empty_answer_yields_nothing():
    transport = FakeTransport(payload={"items": []})

    assert await latest_price(transport, "123", base_unit="g", net_quantity=500,
                              user_agent="home_stock/1.0") is None


@pytest.mark.parametrize("payload", [
    "not a dict",
    ["not", "a", "dict"],
    {"items": "not a list"},
    {"items": {"not": "a list"}},
    {"items": ["not a dict"]},
])
async def test_a_malformed_shape_yields_nothing_instead_of_raising(payload):
    """Open Prices is a moving target: a shape change must never crash a scan."""
    transport = FakeTransport(payload=payload)

    assert await latest_price(transport, "123", base_unit="g", net_quantity=500,
                              user_agent="home_stock/1.0") is None


async def test_a_string_product_quantity_is_not_compared_and_does_not_raise():
    transport = FakeTransport(payload=_items(
        {"price": 3.0, "currency": "EUR", "date": "2026-08-10",
         "product": {"product_quantity": "500"}}))

    assert await latest_price(transport, "123", base_unit="g", net_quantity=None,
                              user_agent="home_stock/1.0") is None


async def test_a_negative_price_is_rejected_as_a_data_entry_error():
    transport = FakeTransport(payload=_items(
        {"price": -1.0, "currency": "EUR", "date": "2026-08-10",
         "product": {"product_quantity": 500}}))

    assert await latest_price(transport, "123", base_unit="g", net_quantity=500,
                              user_agent="home_stock/1.0") is None


async def test_a_discounted_item_uses_the_undiscounted_price():
    transport = FakeTransport(payload=_items(
        {"price": 1.0, "price_is_discounted": True, "price_without_discount": 2.5,
         "currency": "EUR", "date": "2026-08-10", "product": {"product_quantity": 500}}))

    price = await latest_price(transport, "123", base_unit="g", net_quantity=500,
                               user_agent="home_stock/1.0")

    assert price == pytest.approx(0.005)


async def test_a_discounted_item_without_the_undiscounted_price_falls_back_to_price():
    transport = FakeTransport(payload=_items(
        {"price": 1.0, "price_is_discounted": True,
         "currency": "EUR", "date": "2026-08-10", "product": {"product_quantity": 500}}))

    price = await latest_price(transport, "123", base_unit="g", net_quantity=500,
                               user_agent="home_stock/1.0")

    assert price == pytest.approx(0.002)


async def test_an_undiscounted_item_is_unaffected_by_the_discount_logic():
    transport = FakeTransport(payload=_items(
        {"price": 2.0, "price_is_discounted": False,
         "currency": "EUR", "date": "2026-08-10", "product": {"product_quantity": 500}}))

    price = await latest_price(transport, "123", base_unit="g", net_quantity=500,
                               user_agent="home_stock/1.0")

    assert price == pytest.approx(0.004)


async def test_a_piece_tracked_product_is_never_divided_by_a_net_weight():
    """The pack IS the unit at the piece: 2,50 € of yoghurts must stay 2,50 €
    per pot, not 0,02 € — that division wrote a cost 125 times too small into
    the append-only journal (see the rule at the top of frontend fiche.ts)."""
    transport = FakeTransport(payload=_items(
        {"price": 2.5, "currency": "EUR", "date": "2026-08-10",
         "product": {"product_quantity": 125}}))

    price = await latest_price(transport, "123", base_unit="piece", net_quantity=125,
                               user_agent="home_stock/1.0")

    assert price == pytest.approx(2.5)


async def test_a_piece_tracked_product_needs_no_pack_quantity_at_all():
    """No net weight, no product block: at the piece there is nothing to
    divide by, so the price is still usable — unlike a weighed product,
    which gets nothing."""
    transport = FakeTransport(payload=_items(
        {"price": 1.2, "currency": "EUR", "date": "2026-08-10", "product": {}}))

    price = await latest_price(transport, "123", base_unit="piece", net_quantity=None,
                               user_agent="home_stock/1.0")

    assert price == pytest.approx(1.2)
