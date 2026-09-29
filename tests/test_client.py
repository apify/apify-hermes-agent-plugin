"""Tests for apify_hermes_agent_plugin.client."""

from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def _reset_client(monkeypatch):
    from apify_hermes_agent_plugin.client import _reset_client_for_tests

    _reset_client_for_tests()
    yield
    _reset_client_for_tests()


@pytest.fixture(autouse=True)
def _bare_env_resolution(monkeypatch):
    """Make token resolution equivalent to plain os.getenv for most tests.

    ``_resolve_apify_api_token()`` prefers ``agent.web_search_provider.get_provider_env``,
    which itself can fall back to reading a real ``~/.hermes/.env`` off disk. Tests that
    only care about os.environ behavior (the vast majority) shouldn't be at the mercy of
    whatever happens to be in the developer's or CI runner's real dotenv file, so this
    pins tier 1 to a pure os.environ lookup. The fallback-chain tests below override this.
    """
    import agent.web_search_provider as wsp

    monkeypatch.setattr(wsp, 'get_provider_env', lambda name: os.getenv(name, '').strip(), raising=False)


def test_get_api_token_raises_without_token(monkeypatch):
    monkeypatch.delenv('APIFY_API_TOKEN', raising=False)
    from apify_hermes_agent_plugin.client import get_apify_api_token

    with pytest.raises(ValueError, match='APIFY_API_TOKEN'):
        get_apify_api_token()


def test_get_api_token_returns_value(monkeypatch):
    monkeypatch.setenv('APIFY_API_TOKEN', 'tok_123')
    from apify_hermes_agent_plugin.client import get_apify_api_token

    assert get_apify_api_token() == 'tok_123'


def test_check_api_key_false_when_unset(monkeypatch):
    monkeypatch.delenv('APIFY_API_TOKEN', raising=False)
    from apify_hermes_agent_plugin.client import check_apify_api_key

    assert check_apify_api_key() is False


def test_check_api_key_true_when_set(monkeypatch):
    monkeypatch.setenv('APIFY_API_TOKEN', 'tok_123')
    from apify_hermes_agent_plugin.client import check_apify_api_key

    assert check_apify_api_key() is True


def test_check_api_key_false_when_blank(monkeypatch):
    monkeypatch.setenv('APIFY_API_TOKEN', '   ')
    from apify_hermes_agent_plugin.client import check_apify_api_key

    assert check_apify_api_key() is False


def test_get_client_raises_without_token(monkeypatch):
    monkeypatch.delenv('APIFY_API_TOKEN', raising=False)
    from apify_hermes_agent_plugin.client import get_apify_client

    with pytest.raises(ValueError, match='APIFY_API_TOKEN'):
        get_apify_client()


def test_get_client_builds_with_token_and_headers(monkeypatch):
    monkeypatch.setenv('APIFY_API_TOKEN', 'tok_123')
    mock_cls = MagicMock()
    monkeypatch.setattr('apify_hermes_agent_plugin.client.ApifyClient', mock_cls)

    from apify_hermes_agent_plugin.client import get_apify_client

    get_apify_client()

    mock_cls.assert_called_once_with(
        token='tok_123',
        headers={'x-apify-integration-platform': 'hermes-agent'},
    )


def test_get_client_caches_same_instance_for_same_token(monkeypatch):
    monkeypatch.setenv('APIFY_API_TOKEN', 'tok_123')
    mock_cls = MagicMock()
    monkeypatch.setattr('apify_hermes_agent_plugin.client.ApifyClient', mock_cls)

    from apify_hermes_agent_plugin.client import get_apify_client

    first = get_apify_client()
    second = get_apify_client()

    assert first is second
    mock_cls.assert_called_once()


def test_get_client_rebuilds_on_token_change(monkeypatch):
    mock_cls = MagicMock()
    monkeypatch.setattr('apify_hermes_agent_plugin.client.ApifyClient', mock_cls)

    from apify_hermes_agent_plugin.client import get_apify_client

    monkeypatch.setenv('APIFY_API_TOKEN', 'tok_1')
    get_apify_client()
    monkeypatch.setenv('APIFY_API_TOKEN', 'tok_2')
    get_apify_client()

    assert mock_cls.call_count == 2


# ---------------------------------------------------------------------------
# _resolve_apify_api_token() fallback chain
# ---------------------------------------------------------------------------
# These bypass the _bare_env_resolution fixture's tier-1 override by re-patching
# agent.web_search_provider.get_provider_env (and hermes_cli.config.get_env_value)
# directly, to exercise each tier of the real fallback chain in isolation.


def test_resolve_token_prefers_get_provider_env(monkeypatch):
    import agent.web_search_provider as wsp

    monkeypatch.setattr(wsp, 'get_provider_env', lambda name: 'tok_from_provider_env')
    monkeypatch.delenv('APIFY_API_TOKEN', raising=False)

    from apify_hermes_agent_plugin.client import _resolve_apify_api_token

    assert _resolve_apify_api_token() == 'tok_from_provider_env'


def test_resolve_token_falls_back_to_hermes_cli_get_env_value(monkeypatch):
    import agent.web_search_provider as wsp

    monkeypatch.delattr(wsp, 'get_provider_env', raising=False)

    import hermes_cli.config as hc_config

    monkeypatch.setattr(hc_config, 'get_env_value', lambda name: 'tok_from_get_env_value')
    monkeypatch.delenv('APIFY_API_TOKEN', raising=False)

    from apify_hermes_agent_plugin.client import _resolve_apify_api_token

    assert _resolve_apify_api_token() == 'tok_from_get_env_value'


def test_resolve_token_falls_back_to_bare_os_getenv(monkeypatch):
    import agent.web_search_provider as wsp

    monkeypatch.delattr(wsp, 'get_provider_env', raising=False)

    import hermes_cli.config as hc_config

    monkeypatch.delattr(hc_config, 'get_env_value', raising=False)
    monkeypatch.setenv('APIFY_API_TOKEN', 'tok_from_bare_env')

    from apify_hermes_agent_plugin.client import _resolve_apify_api_token

    assert _resolve_apify_api_token() == 'tok_from_bare_env'
