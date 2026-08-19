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

    price = await latest_price(transport, "123", net_quantity=500,
                               user_agent="home_stock/1.0")

    assert price == pytest.approx(0.005)


async def test_the_weight_from_open_prices_beats_the_one_we_guessed():
    transport = FakeTransport(payload=_items(
        {"price": 2.0, "currency": "EUR", "date": "2026-08-10",
         "product": {"product_quantity": 1000}}))

    price = await latest_price(transport, "123", net_quantity=500,
                               user_agent="home_stock/1.0")

    assert price == pytest.approx(0.002)


async def test_a_price_in_another_currency_is_ignored():
    transport = FakeTransport(payload=_items(
        {"price": 3.0, "currency": "CHF", "date": "2026-08-10",
         "product": {"product_quantity": 500}}))

    assert await latest_price(transport, "123", net_quantity=500,
                              user_agent="home_stock/1.0") is None


async def test_without_a_net_weight_no_price_per_base_unit_can_exist():
    transport = FakeTransport(payload=_items(
        {"price": 3.0, "currency": "EUR", "date": "2026-08-10", "product": {}}))

    assert await latest_price(transport, "123", net_quantity=None,
                              user_agent="home_stock/1.0") is None


async def test_a_network_failure_is_silent_because_a_suggestion_is_not_load_bearing():
    transport = FakeTransport(raises=TimeoutError())

    assert await latest_price(transport, "123", net_quantity=500,
                              user_agent="home_stock/1.0") is None


async def test_an_empty_answer_yields_nothing():
    transport = FakeTransport(payload={"items": []})

    assert await latest_price(transport, "123", net_quantity=500,
                              user_agent="home_stock/1.0") is None
