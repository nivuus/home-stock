"""Shared fixtures. The custom integration must be enabled for every test."""
import pytest


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
