"""Tests for apify_hermes_agent_plugin.web_search — all mocked, no live Actor calls."""

from __future__ import annotations

import json

import httpx
import pytest

from apify_hermes_agent_plugin.web_search import ApifyWebSearchProvider


@pytest.fixture
def mock_search(monkeypatch):
    """Route every sync httpx.Client search() creates through a MockTransport; return the request log."""

    def _install(handler):
        requests: list[httpx.Request] = []

        def _record(request):
            requests.append(request)
            return handler(request)

        transport = httpx.MockTransport(_record)
        # Same trick as mock_web_fetch below: capture the real class before patching it.
        real_client = httpx.Client
        monkeypatch.setattr(
            'apify_hermes_agent_plugin.web_search.httpx.Client',
            lambda *a, **kw: real_client(*a, transport=transport, **kw),
        )
        return requests

    return _install


@pytest.fixture(autouse=True)
def no_search_env_defaults(monkeypatch):
    """Default: no APIFY_WEB_SEARCH_* overrides are configured."""
    monkeypatch.setattr('apify_hermes_agent_plugin.web_search.get_hermes_env', lambda name: '', raising=False)


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


_SEARCH_URL = 'https://api.apify.com/v2/acts/apify~web-search/run-sync-get-dataset-items'


def _search_item(*results):
    """Build the single dataset item apify~web-search returns, holding ``results``."""
    return {'query': 'apify', 'search': {'provider': 'google'}, 'results': list(results)}


def test_search_returns_normalized_results(mock_search):
    requests = mock_search(
        lambda request: httpx.Response(
            201,
            json=[
                _search_item(
                    {
                        'title': 'Apify',
                        'url': 'https://apify.com',
                        'snippet': 'Web scraping and automation platform',
                        'position': 1,
                        'domain': 'apify.com',
                    }
                )
            ],
        )
    )

    result = ApifyWebSearchProvider().search('apify', limit=5)

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
    assert len(requests) == 1
    request = requests[0]
    assert request.method == 'POST'
    assert str(request.url) == _SEARCH_URL
    assert request.headers['Authorization'] == 'Bearer tok_123'
    assert request.headers['x-apify-integration-platform'] == 'hermes-agent'
    assert json.loads(request.content) == {'query': 'apify', 'maxResults': 5}


def test_search_clamps_limit_above_one_results_page(mock_search):
    requests = mock_search(lambda request: httpx.Response(201, json=[_search_item()]))

    ApifyWebSearchProvider().search('apify', limit=250)

    assert json.loads(requests[0].content)['maxResults'] == 10


def test_search_clamps_limit_below_actor_min(mock_search):
    requests = mock_search(lambda request: httpx.Response(201, json=[_search_item()]))

    ApifyWebSearchProvider().search('apify', limit=0)

    assert json.loads(requests[0].content)['maxResults'] == 1


def test_search_caps_returned_results_at_limit(mock_search):
    items = [{'title': f'T{i}', 'url': f'https://example.com/{i}', 'snippet': 's'} for i in range(5)]
    mock_search(lambda request: httpx.Response(201, json=[_search_item(*items)]))

    result = ApifyWebSearchProvider().search('q', limit=2)

    assert [r['url'] for r in result['data']['web']] == ['https://example.com/0', 'https://example.com/1']
    assert [r['position'] for r in result['data']['web']] == [1, 2]


def test_search_passes_country_and_language_defaults_from_env(monkeypatch, mock_search):
    env = {'APIFY_WEB_SEARCH_COUNTRY': 'DE', 'APIFY_WEB_SEARCH_LANGUAGE': 'de'}
    monkeypatch.setattr('apify_hermes_agent_plugin.web_search.get_hermes_env', lambda name: env.get(name, ''))
    requests = mock_search(lambda request: httpx.Response(201, json=[_search_item()]))

    ApifyWebSearchProvider().search('apify', limit=5)

    assert json.loads(requests[0].content) == {
        'query': 'apify',
        'maxResults': 5,
        'countryCode': 'DE',
        'languageCode': 'de',
    }


def test_search_truncates_long_snippets(mock_search):
    mock_search(
        lambda request: httpx.Response(
            201, json=[_search_item({'title': 'T', 'url': 'https://example.com', 'snippet': 'x' * 600})]
        )
    )

    result = ApifyWebSearchProvider().search('q')

    assert len(result['data']['web'][0]['description']) == 500


def test_search_tolerates_missing_and_malformed_fields(mock_search):
    mock_search(
        lambda request: httpx.Response(
            201,
            json=[_search_item('not a dict', {'url': 'https://example.com', 'title': None, 'snippet': 42})],
        )
    )

    result = ApifyWebSearchProvider().search('q')

    assert result == {
        'success': True,
        'data': {'web': [{'title': '', 'url': 'https://example.com', 'description': '', 'position': 1}]},
    }


@pytest.mark.parametrize('body', [[], [{}], [{'results': None}], [{'results': 5}], ['not a dict']])
def test_search_returns_empty_list_when_no_results(mock_search, body):
    mock_search(lambda request: httpx.Response(201, json=body))

    result = ApifyWebSearchProvider().search('q')

    assert result == {'success': True, 'data': {'web': []}}


def test_search_returns_error_on_http_error_with_apify_error_body(mock_search):
    mock_search(
        lambda request: httpx.Response(
            402, json={'error': {'type': 'not-enough-usage-to-run-paid-actor', 'message': 'Not enough credit'}}
        )
    )

    result = ApifyWebSearchProvider().search('apify')

    assert result == {'success': False, 'error': 'Apify search failed with status 402: Not enough credit'}


def test_search_returns_error_on_http_error_with_non_json_body(mock_search):
    mock_search(lambda request: httpx.Response(502, text='<html>Bad Gateway</html>'))

    result = ApifyWebSearchProvider().search('apify')

    assert result == {'success': False, 'error': 'Apify search failed with status 502'}


def test_search_returns_error_on_non_list_body(mock_search):
    mock_search(lambda request: httpx.Response(201, json={'unexpected': True}))

    result = ApifyWebSearchProvider().search('apify')

    assert result == {'success': False, 'error': 'Apify search failed: unexpected response body'}


def test_search_returns_error_on_timeout(mock_search):
    def raise_timeout(request):
        raise httpx.ReadTimeout('timed out', request=request)

    mock_search(raise_timeout)

    result = ApifyWebSearchProvider().search('apify')

    assert result == {'success': False, 'error': 'Apify search failed: timed out'}


def test_search_returns_error_when_interrupted(monkeypatch, mock_search):
    monkeypatch.setattr('tools.interrupt.is_interrupted', lambda: True)
    requests = mock_search(lambda request: httpx.Response(201, json=[]))

    result = ApifyWebSearchProvider().search('apify')

    assert result == {'success': False, 'error': 'Interrupted'}
    assert requests == []


def test_search_returns_error_when_token_unavailable(monkeypatch, mock_search):
    def raise_value_error():
        raise ValueError('Apify tools are not configured. Set APIFY_API_TOKEN.')

    monkeypatch.setattr('apify_hermes_agent_plugin.web_search.get_apify_api_token', raise_value_error)
    requests = mock_search(lambda request: httpx.Response(201, json=[]))

    result = ApifyWebSearchProvider().search('apify')

    assert result == {
        'success': False,
        'error': 'Apify search failed: Apify tools are not configured. Set APIFY_API_TOKEN.',
    }
    assert requests == []


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
async def test_extract_target_http_error_returns_structured_error(mock_web_fetch):
    """response.status_code is the Actor's own status (200); fetch.httpStatusCode is the target's."""

    def handler(request):
        return httpx.Response(
            200,
            json={
                'url': 'https://example.com/missing',
                'fetch': {'loadedUrl': 'https://example.com/missing', 'httpStatusCode': 404},
                'metadata': {'title': 'Not Found'},
                'markdown': '# 404 Not Found',
                'html': None,
            },
        )

    mock_web_fetch(handler)

    result = await ApifyWebSearchProvider().extract(['https://example.com/missing'])

    assert result == [
        {
            'url': 'https://example.com/missing',
            'title': '',
            'content': '',
            'raw_content': '',
            'error': 'Target URL returned HTTP 404',
        }
    ]


@pytest.mark.asyncio
async def test_extract_redirect_target_blocked_by_website_policy(monkeypatch, mock_web_fetch):
    """The input URL is allowed, but the Actor's server-side redirect lands on a blocked host."""

    def handler(request):
        return httpx.Response(
            200,
            json={
                'url': 'https://allowed.example.com',
                'fetch': {'loadedUrl': 'https://blocked.example.com/', 'httpStatusCode': 200},
                'metadata': {'title': 'Secret'},
                'markdown': '# secret content',
                'html': None,
            },
        )

    mock_web_fetch(handler)

    def fake_check(url):
        if 'blocked' in url:
            return {
                'url': url,
                'host': 'blocked.example.com',
                'rule': '*.example.com',
                'source': 'config',
                'message': f"Blocked by website policy: '{url}' matched rule",
            }
        return None

    monkeypatch.setattr('tools.website_policy.check_website_access', fake_check)

    result = await ApifyWebSearchProvider().extract(['https://allowed.example.com'])

    assert result == [
        {
            'url': 'https://blocked.example.com/',
            'title': '',
            'content': '',
            'raw_content': '',
            'error': "Blocked by website policy: 'https://blocked.example.com/' matched rule",
            'blocked_by_policy': {'host': 'blocked.example.com', 'rule': '*.example.com', 'source': 'config'},
        }
    ]


@pytest.mark.asyncio
async def test_extract_closes_http_client_after_each_call(monkeypatch):
    def handler(request):
        return httpx.Response(
            200,
            json={
                'url': 'https://example.com',
                'fetch': {'loadedUrl': 'https://example.com', 'httpStatusCode': 200},
                'metadata': {'title': 'Example'},
                'markdown': '# Example',
                'html': None,
            },
        )

    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient
    created: list[httpx.AsyncClient] = []

    def spy_async_client(*a, **kw):
        client = real_async_client(*a, transport=transport, **kw)
        created.append(client)
        return client

    monkeypatch.setattr('apify_hermes_agent_plugin.web_search.httpx.AsyncClient', spy_async_client)

    provider = ApifyWebSearchProvider()
    await provider.extract(['https://example.com', 'https://example.org'])
    await provider.extract(['https://example.com'])

    # One client per extract() call (shared across that batch's URLs), closed when it returns.
    assert len(created) == 2
    assert all(client.is_closed for client in created)


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
async def test_extract_non_json_error_body_reports_status(mock_web_fetch):
    def handler(request):
        return httpx.Response(502, content=b'<html>Bad Gateway</html>', headers={'content-type': 'text/html'})

    mock_web_fetch(handler)

    result = await ApifyWebSearchProvider().extract(['https://example.com'])

    assert result == [
        {
            'url': 'https://example.com',
            'title': '',
            'content': '',
            'raw_content': '',
            'error': 'Apify web fetch failed with status 502',
        }
    ]


@pytest.mark.asyncio
async def test_extract_non_dict_error_body_reports_status(mock_web_fetch):
    def handler(request):
        return httpx.Response(500, json=['unexpected'])

    mock_web_fetch(handler)

    result = await ApifyWebSearchProvider().extract(['https://example.com'])

    assert result[0]['error'] == 'Apify web fetch failed with status 500'


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
