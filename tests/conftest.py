"""Shared fixtures. The custom integration must be enabled for every test."""
import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Let Home Assistant load custom_components/home_stock during tests."""
    yield
