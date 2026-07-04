"""Tests for apify_hermes_agent_plugin.client."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def _reset_client(monkeypatch):
    from apify_hermes_agent_plugin.client import _reset_client_for_tests
    _reset_client_for_tests()
    yield
    _reset_client_for_tests()


def test_check_api_key_false_when_unset(monkeypatch):
    monkeypatch.delenv("APIFY_API_TOKEN", raising=False)
    from apify_hermes_agent_plugin.client import check_apify_api_key
    assert check_apify_api_key() is False


def test_check_api_key_true_when_set(monkeypatch):
    monkeypatch.setenv("APIFY_API_TOKEN", "tok_123")
    from apify_hermes_agent_plugin.client import check_apify_api_key
    assert check_apify_api_key() is True


def test_check_api_key_false_when_blank(monkeypatch):
    monkeypatch.setenv("APIFY_API_TOKEN", "   ")
    from apify_hermes_agent_plugin.client import check_apify_api_key
    assert check_apify_api_key() is False


def test_get_client_raises_without_token(monkeypatch):
    monkeypatch.delenv("APIFY_API_TOKEN", raising=False)
    from apify_hermes_agent_plugin.client import get_apify_client
    with pytest.raises(ValueError, match="APIFY_API_TOKEN"):
        get_apify_client()


def test_get_client_builds_with_token_and_headers(monkeypatch):
    monkeypatch.setenv("APIFY_API_TOKEN", "tok_123")
    mock_cls = MagicMock()
    monkeypatch.setattr("apify_hermes_agent_plugin.client.ApifyClient", mock_cls)

    from apify_hermes_agent_plugin.client import get_apify_client
    get_apify_client()

    mock_cls.assert_called_once_with(
        token="tok_123",
        headers={"x-apify-integration-platform": "hermes-agent"},
    )


def test_get_client_caches_same_instance_for_same_token(monkeypatch):
    monkeypatch.setenv("APIFY_API_TOKEN", "tok_123")
    mock_cls = MagicMock()
    monkeypatch.setattr("apify_hermes_agent_plugin.client.ApifyClient", mock_cls)

    from apify_hermes_agent_plugin.client import get_apify_client
    first = get_apify_client()
    second = get_apify_client()

    assert first is second
    mock_cls.assert_called_once()


def test_get_client_rebuilds_on_token_change(monkeypatch):
    mock_cls = MagicMock()
    monkeypatch.setattr("apify_hermes_agent_plugin.client.ApifyClient", mock_cls)

    from apify_hermes_agent_plugin.client import get_apify_client
    monkeypatch.setenv("APIFY_API_TOKEN", "tok_1")
    get_apify_client()
    monkeypatch.setenv("APIFY_API_TOKEN", "tok_2")
    get_apify_client()

    assert mock_cls.call_count == 2
