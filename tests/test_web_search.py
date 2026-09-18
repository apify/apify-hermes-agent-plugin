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


def test_search_returns_normalized_results(mock_client):
    run = MagicMock()
    run.id = 'run_1'
    mock_client.actor.return_value.start.return_value = run

    finished_run = MagicMock()
    finished_run.status = 'SUCCEEDED'
    finished_run.default_dataset_id = 'dataset_1'
    mock_client.run.return_value.wait_for_finish.return_value = finished_run

    dataset_result = MagicMock()
    dataset_result.items = [
        {
            'searchResult': {
                'title': 'Apify',
                'url': 'https://apify.com',
                'description': 'Web scraping and automation platform',
            }
        },
    ]
    mock_client.dataset.return_value.list_items.return_value = dataset_result

    provider = ApifyWebSearchProvider()
    result = provider.search('apify', limit=5)

    assert result == {
        'success': True,
        'data': {
            'web': [
                {
                    'title': 'Apify',
                    'url': 'https://apify.com',
                    'description': 'Web scraping and automation platform',
                    'position': 1,
                },
            ]
        },
    }
    mock_client.actor.assert_called_once_with('apify~rag-web-browser')
    mock_client.actor.return_value.start.assert_called_once_with(
        run_input={'query': 'apify', 'maxResults': 5, 'requestTimeoutSecs': 60}
    )
    mock_client.run.assert_called_once_with('run_1')


def test_search_truncates_long_descriptions(mock_client):
    run = MagicMock()
    run.id = 'run_1'
    mock_client.actor.return_value.start.return_value = run

    finished_run = MagicMock()
    finished_run.status = 'SUCCEEDED'
    finished_run.default_dataset_id = 'dataset_1'
    mock_client.run.return_value.wait_for_finish.return_value = finished_run

    long_description = 'x' * 600
    dataset_result = MagicMock()
    dataset_result.items = [
        {'searchResult': {'title': 'T', 'url': 'https://example.com', 'description': long_description}},
    ]
    mock_client.dataset.return_value.list_items.return_value = dataset_result

    result = ApifyWebSearchProvider().search('q')

    assert len(result['data']['web'][0]['description']) == 500


def test_search_returns_error_on_failed_run(mock_client):
    run = MagicMock()
    run.id = 'run_1'
    mock_client.actor.return_value.start.return_value = run

    finished_run = MagicMock()
    finished_run.status = 'FAILED'
    finished_run.default_dataset_id = None
    mock_client.run.return_value.wait_for_finish.return_value = finished_run

    result = ApifyWebSearchProvider().search('apify')

    assert result == {'success': False, 'error': 'Apify search run ended with status: FAILED'}


def test_search_returns_error_when_interrupted(monkeypatch, mock_client):
    monkeypatch.setattr('tools.interrupt.is_interrupted', lambda: True)

    result = ApifyWebSearchProvider().search('apify')

    assert result == {'success': False, 'error': 'Interrupted'}
    mock_client.actor.assert_not_called()


def test_search_returns_error_on_exception(mock_client):
    mock_client.actor.side_effect = RuntimeError('boom')

    result = ApifyWebSearchProvider().search('apify')

    assert result == {'success': False, 'error': 'Apify search failed: boom'}
