"""A cascade that reached no base says so; it never reads as "product unknown".

Every transport here is a fake: no test reaches the network.
"""
import aiohttp
import pytest

from custom_components.home_stock.off.client import OffClient


class RaisingTransport:
    def __init__(self, error: Exception):
        self.error = error
        self.calls = 0

    async def get_json(self, url, headers, timeout):
        self.calls += 1
        raise self.error


class StatusTransport:
    def __init__(self, status: int, payload=None):
        self.status, self.payload = status, payload

    async def get_json(self, url, headers, timeout):
        return self.status, self.payload


def _client(transport) -> OffClient:
    return OffClient(transport, user_agent="home_stock/1.0", clock=lambda: 0.0)


@pytest.mark.parametrize("error", [
    TimeoutError(), ConnectionError("no route to host"),
    aiohttp.ClientConnectionError("reset"), ValueError("not JSON"),
])
async def test_no_base_answering_is_unreachable_not_absent(error):
    transport = RaisingTransport(error)
    result = await _client(transport).lookup("123")
    assert transport.calls == 4
    assert result.record is None
    assert result.unreachable is True


@pytest.mark.parametrize("status, payload", [(404, None), (200, {"status": 0})])
async def test_every_base_saying_no_is_a_genuine_absence(status, payload):
    result = await _client(StatusTransport(status, payload)).lookup("123")
    assert result.record is None
    assert result.unreachable is False


async def test_server_errors_on_every_base_are_unreachable():
    result = await _client(StatusTransport(503)).lookup("123")
    assert result.unreachable is True


async def test_a_bug_in_the_transport_is_not_hidden_as_an_absence():
    with pytest.raises(KeyError):
        await _client(RaisingTransport(KeyError("bug"))).lookup("123")


async def test_the_scan_answer_carries_the_flag(hass, setup_entry, hass_ws_client):
    entry = await setup_entry()
    entry.runtime_data.off_client = _client(RaisingTransport(TimeoutError()))
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "home_stock/lookup", "code": "3017620422003"})
    answer = await client.receive_json()
    assert answer["success"] is True
    assert answer["result"]["known"] is False
    assert answer["result"]["unreachable"] is True
