"""Tests for apify_hermes_agent_plugin.web_search — all mocked, no live Actor calls."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from apify_hermes_agent_plugin.web_search import ApifyWebSearchProvider


@pytest.fixture
def mock_client(monkeypatch):
    """Patch get_apify_client to return a MagicMock client."""
    client = MagicMock()
    monkeypatch.setattr(
        'apify_hermes_agent_plugin.web_search.get_apify_client',
        lambda: client,
    )
    return client


@pytest.fixture(autouse=True)
def not_interrupted(monkeypatch):
    """Default: is_interrupted() returns False."""
    monkeypatch.setattr('tools.interrupt.is_interrupted', lambda: False)


def test_name_and_display_name():
    provider = ApifyWebSearchProvider()
    assert provider.name == 'apify'
    assert provider.display_name == 'Apify'


def test_supports_search_but_not_extract():
    provider = ApifyWebSearchProvider()
    assert provider.supports_search() is True
    assert provider.supports_extract() is False


def test_is_available_reflects_token_presence(monkeypatch):
    monkeypatch.setattr('apify_hermes_agent_plugin.web_search.check_apify_api_key', lambda: True)
    assert ApifyWebSearchProvider().is_available() is True

    monkeypatch.setattr('apify_hermes_agent_plugin.web_search.check_apify_api_key', lambda: False)
    assert ApifyWebSearchProvider().is_available() is False


def test_get_setup_schema_includes_token_env_var():
    schema = ApifyWebSearchProvider().get_setup_schema()
    env_var_keys = [e['key'] for e in schema['env_vars']]
    assert 'APIFY_API_TOKEN' in env_var_keys
    assert schema['name'] == 'Apify'
