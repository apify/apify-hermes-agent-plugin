"""Tests for apify_hermes_agent_plugin.web_search — all mocked, no live Actor calls."""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
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


@pytest.fixture(autouse=True)
def api_token(monkeypatch):
    """Default: get_apify_api_token() returns a fake token."""
    monkeypatch.setattr('apify_hermes_agent_plugin.web_search.get_apify_api_token', lambda: 'tok_123')


@pytest.fixture
def mock_web_fetch(monkeypatch):
    """Install an httpx.MockTransport as the transport for every AsyncClient extract() creates."""

    def _install(handler):
        transport = httpx.MockTransport(handler)
        # `web_search.py` does `import httpx`, so `web_search.httpx` IS the real httpx module —
        # patching `.AsyncClient` on it patches the real class everywhere, including in this
        # closure. Capture the real class first so the replacement doesn't call itself.
        real_async_client = httpx.AsyncClient
        monkeypatch.setattr(
            'apify_hermes_agent_plugin.web_search.httpx.AsyncClient',
            lambda *a, **kw: real_async_client(*a, transport=transport, **kw),
        )

    return _install


def test_name_and_display_name():
    provider = ApifyWebSearchProvider()
    assert provider.name == 'apify'
    assert provider.display_name == 'Apify'


def test_supports_search_and_extract():
    provider = ApifyWebSearchProvider()
    assert provider.supports_search() is True
    assert provider.supports_extract() is True


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
    assert schema['tag'] == 'Google Search and web content extraction via Apify — pay-as-you-go platform usage.'
    assert schema['env_vars'][0]['url'] == (
        'https://console.apify.com/settings/integrations?utm_source=hermes-agent&utm_medium=integrations'
    )


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


def test_search_clamps_limit_above_actor_max(mock_client):
    run = MagicMock()
    run.id = 'run_1'
    mock_client.actor.return_value.start.return_value = run

    finished_run = MagicMock()
    finished_run.status = 'SUCCEEDED'
    finished_run.default_dataset_id = 'dataset_1'
    mock_client.run.return_value.wait_for_finish.return_value = finished_run

    dataset_result = MagicMock()
    dataset_result.items = []
    mock_client.dataset.return_value.list_items.return_value = dataset_result

    ApifyWebSearchProvider().search('apify', limit=250)

    mock_client.actor.return_value.start.assert_called_once_with(
        run_input={'query': 'apify', 'maxResults': 100, 'requestTimeoutSecs': 60}
    )


def test_search_clamps_limit_below_actor_min(mock_client):
    run = MagicMock()
    run.id = 'run_1'
    mock_client.actor.return_value.start.return_value = run

    finished_run = MagicMock()
    finished_run.status = 'SUCCEEDED'
    finished_run.default_dataset_id = 'dataset_1'
    mock_client.run.return_value.wait_for_finish.return_value = finished_run

    dataset_result = MagicMock()
    dataset_result.items = []
    mock_client.dataset.return_value.list_items.return_value = dataset_result

    ApifyWebSearchProvider().search('apify', limit=0)

    mock_client.actor.return_value.start.assert_called_once_with(
        run_input={'query': 'apify', 'maxResults': 1, 'requestTimeoutSecs': 60}
    )


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


def test_search_returns_error_on_wait_for_finish_timeout(mock_client):
    run = MagicMock()
    run.id = 'run_1'
    mock_client.actor.return_value.start.return_value = run
    mock_client.run.return_value.wait_for_finish.return_value = None

    result = ApifyWebSearchProvider().search('apify')

    assert result == {'success': False, 'error': 'Apify search timed out after 90s'}


def test_search_returns_error_when_interrupted(monkeypatch, mock_client):
    monkeypatch.setattr('tools.interrupt.is_interrupted', lambda: True)

    result = ApifyWebSearchProvider().search('apify')

    assert result == {'success': False, 'error': 'Interrupted'}
    mock_client.actor.assert_not_called()


def test_search_returns_error_on_exception(mock_client):
    mock_client.actor.side_effect = RuntimeError('boom')

    result = ApifyWebSearchProvider().search('apify')

    assert result == {'success': False, 'error': 'Apify search failed: boom'}


def test_search_returns_error_when_client_unavailable(monkeypatch):
    def raise_value_error():
        raise ValueError('Apify tools are not configured. Set APIFY_API_TOKEN.')

    monkeypatch.setattr('apify_hermes_agent_plugin.web_search.get_apify_client', raise_value_error)

    result = ApifyWebSearchProvider().search('apify')

    assert result == {
        'success': False,
        'error': 'Apify search failed: Apify tools are not configured. Set APIFY_API_TOKEN.',
    }


@pytest.mark.asyncio
async def test_extract_single_url_success(mock_web_fetch):
    def handler(request):
        assert request.headers['authorization'] == 'Bearer tok_123'
        assert request.headers['x-apify-integration-platform'] == 'hermes-agent'
        return httpx.Response(
            200,
            json={
                'url': 'https://example.com',
                'fetch': {'loadedUrl': 'https://example.com/', 'httpStatusCode': 200},
                'metadata': {'title': 'Example'},
                'markdown': '# Example',
                'html': None,
            },
        )

    mock_web_fetch(handler)

    result = await ApifyWebSearchProvider().extract(['https://example.com'])

    assert result == [
        {
            'url': 'https://example.com/',
            'title': 'Example',
            'content': '# Example',
            'raw_content': '# Example',
            'metadata': {'title': 'Example'},
        }
    ]


@pytest.mark.asyncio
async def test_extract_multiple_urls_preserves_order(mock_web_fetch):
    import json

    def handler(request):
        url = json.loads(request.read())['url']
        return httpx.Response(
            200,
            json={
                'url': url,
                'fetch': {'loadedUrl': url, 'httpStatusCode': 200},
                'metadata': {'title': url},
                'markdown': f'content for {url}',
                'html': None,
            },
        )

    mock_web_fetch(handler)

    urls = ['https://a.example.com', 'https://b.example.com', 'https://c.example.com']
    result = await ApifyWebSearchProvider().extract(urls)

    assert [r['url'] for r in result] == urls
    assert [r['title'] for r in result] == urls


@pytest.mark.asyncio
async def test_extract_non_dict_body_returns_structured_error(mock_web_fetch):
    def handler(request):
        # `json=None` is httpx.Response's "no body given" sentinel (produces an empty body,
        # which already exercises the JSONDecodeError branch) — use `content=b'null'` to get an
        # actual `null` JSON body, which parses successfully to a non-dict `None`.
        return httpx.Response(200, content=b'null', headers={'content-type': 'application/json'})

    mock_web_fetch(handler)

    result = await ApifyWebSearchProvider().extract(['https://example.com'])

    assert result == [
        {
            'url': 'https://example.com',
            'title': '',
            'content': '',
            'raw_content': '',
            'error': 'Invalid response body: expected an object',
        }
    ]


@pytest.mark.asyncio
async def test_extract_malformed_nested_fields_fall_back_to_safe_defaults(mock_web_fetch):
    def handler(request):
        return httpx.Response(200, json={'fetch': 'not-a-dict', 'metadata': 'also-not-a-dict', 'markdown': 123})

    mock_web_fetch(handler)

    result = await ApifyWebSearchProvider().extract(['https://example.com'])

    assert result == [
        {
            'url': 'https://example.com',
            'title': '',
            'content': '',
            'raw_content': '',
            'metadata': {},
        }
    ]


@pytest.mark.asyncio
async def test_extract_error_code_error_shape(mock_web_fetch):
    def handler(request):
        return httpx.Response(422, json={'code': 'UNSUPPORTED_CONTENT_TYPE', 'error': 'Cannot convert content type'})

    mock_web_fetch(handler)

    result = await ApifyWebSearchProvider().extract(['https://example.com/file.zip'])

    assert result == [
        {
            'url': 'https://example.com/file.zip',
            'title': '',
            'content': '',
            'raw_content': '',
            'error': 'Cannot convert content type (code: UNSUPPORTED_CONTENT_TYPE)',
        }
    ]


@pytest.mark.asyncio
async def test_extract_error_nested_error_shape(mock_web_fetch):
    def handler(request):
        return httpx.Response(401, json={'error': {'message': 'Invalid API token', 'type': 'invalid_request_error'}})

    mock_web_fetch(handler)

    result = await ApifyWebSearchProvider().extract(['https://example.com'])

    assert result == [
        {
            'url': 'https://example.com',
            'title': '',
            'content': '',
            'raw_content': '',
            'error': 'Invalid API token',
        }
    ]


@pytest.mark.asyncio
async def test_extract_null_format_returns_empty_content(mock_web_fetch):
    def handler(request):
        return httpx.Response(
            200,
            json={
                'url': 'https://example.com/image.png',
                'fetch': {'loadedUrl': 'https://example.com/image.png', 'httpStatusCode': 200},
                'metadata': {'title': ''},
                'markdown': None,
                'html': None,
            },
        )

    mock_web_fetch(handler)

    result = await ApifyWebSearchProvider().extract(['https://example.com/image.png'])

    assert result == [
        {
            'url': 'https://example.com/image.png',
            'title': '',
            'content': '',
            'raw_content': '',
            'metadata': {'title': ''},
        }
    ]


@pytest.mark.asyncio
async def test_extract_blocked_by_website_policy(monkeypatch, mock_web_fetch):
    called = False

    def handler(request):
        nonlocal called
        called = True
        return httpx.Response(200, json={})

    mock_web_fetch(handler)
    monkeypatch.setattr(
        'tools.website_policy.check_website_access',
        lambda url: {
            'url': url,
            'host': 'blocked.example.com',
            'rule': '*.example.com',
            'source': 'config',
            'message': f"Blocked by website policy: '{url}' matched rule",
        },
    )

    result = await ApifyWebSearchProvider().extract(['https://blocked.example.com'])

    assert called is False
    assert result == [
        {
            'url': 'https://blocked.example.com',
            'title': '',
            'content': '',
            'raw_content': '',
            'error': "Blocked by website policy: 'https://blocked.example.com' matched rule",
            'blocked_by_policy': {'host': 'blocked.example.com', 'rule': '*.example.com', 'source': 'config'},
        }
    ]


@pytest.mark.asyncio
async def test_extract_timeout_returns_structured_error(mock_web_fetch):
    def handler(request):
        raise httpx.ConnectTimeout('timed out', request=request)

    mock_web_fetch(handler)

    result = await ApifyWebSearchProvider().extract(['https://slow.example.com'])

    assert len(result) == 1
    assert result[0]['url'] == 'https://slow.example.com'
    assert result[0]['content'] == ''
    assert 'error' in result[0]


@pytest.mark.asyncio
async def test_extract_returns_error_when_interrupted(monkeypatch, mock_web_fetch):
    called = False

    def handler(request):
        nonlocal called
        called = True
        return httpx.Response(200, json={})

    mock_web_fetch(handler)
    monkeypatch.setattr('tools.interrupt.is_interrupted', lambda: True)

    result = await ApifyWebSearchProvider().extract(['https://example.com', 'https://example.org'])

    assert called is False
    assert result == [
        {'url': 'https://example.com', 'title': '', 'content': '', 'raw_content': '', 'error': 'Interrupted'},
        {'url': 'https://example.org', 'title': '', 'content': '', 'raw_content': '', 'error': 'Interrupted'},
    ]
