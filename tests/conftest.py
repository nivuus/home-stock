"""Shared fixtures. The custom integration must be enabled for every test."""
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.home_stock.const import DOMAIN
from custom_components.home_stock.storage import repositories as repo


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Let Home Assistant load custom_components/home_stock during tests."""
    yield


@pytest.fixture
def hass_config_dir(hass_tmp_config_dir: str) -> str:
    """Give every test its own config directory.

    Left at the plugin's default, `hass_config_dir` resolves to a single fixed
    `testing_config` folder shared by the whole pytest run: home_stock.db (and
    its UNIQUE constraints on names) would then leak between unrelated tests
    that both create a "Frigo" location, in file order, silently making the
    suite order-dependent. `hass_tmp_config_dir` is the plugin's own fixture
    for this, copying the base config into a fresh tmp_path per test.
    """
    return hass_tmp_config_dir


async def setup_entry(hass, *, with_article: bool = False,
                      with_piece_product: bool = False) -> MockConfigEntry:
    """Set up the home_stock integration for a test, and optionally seed it.

    Called with no arguments, this is exactly what every lot 0 test already
    did by hand: add a bare MockConfigEntry and let the integration load.

    `with_article` adds a location and a g-based article with no batch yet —
    ready for home_stock/stock/add. `with_piece_product` adds a piece-based
    product with one open batch — ready for home_stock/product/convert_unit.
    Both insert their location/product/article first, so with either flag
    alone the seeded row lands on id 1, matching the ids the tests hardcode.
    """
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    if not (with_article or with_piece_product):
        return entry

    manager = entry.runtime_data.manager

    def _seed() -> tuple[int | None, int | None]:
        piece_article_id = piece_location_id = None
        with manager.db.write() as conn:
            if with_article:
                location_id = repo.insert_location(conn, name="Placard", kind="pantry")
                product_id = repo.insert_product(
                    conn, name="Article prêt à ranger", base_unit="g")
                repo.insert_article(conn, product_id=product_id)
            if with_piece_product:
                piece_location_id = repo.insert_location(
                    conn, name="Frigo courses", kind="fridge")
                piece_product_id = repo.insert_product(
                    conn, name="Yaourts nature", base_unit="piece")
                piece_article_id = repo.insert_article(
                    conn, product_id=piece_product_id, net_quantity=125)
        return piece_article_id, piece_location_id

    piece_article_id, piece_location_id = await hass.async_add_executor_job(_seed)
    if with_piece_product:
        await hass.async_add_executor_job(lambda: manager.add_stock(
            article_id=piece_article_id, quantity=6, location_id=piece_location_id,
            occurred_at="2026-08-18T10:00:00"))
    # Mirror what both production write paths (the services, the todo entity)
    # do: refresh the coordinator after writing directly through the manager,
    # bypassing both of those paths.
    await entry.runtime_data.coordinator.async_request_refresh()
    return entry
