"""Apify web-search provider for Hermes Agent's pluggable web-search backend."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

import httpx
from agent.web_search_provider import WebSearchProvider

from apify_hermes_agent_plugin.client import (
    _HERMES_HEADERS,
    check_apify_api_key,
    get_apify_api_token,
    get_apify_client,
)
from apify_hermes_agent_plugin.tools import _attr

logger = logging.getLogger(__name__)

_RAG_ACTOR = 'apify~rag-web-browser'
_MAX_DESCRIPTION_CHARS = 500
_SEARCH_WAIT_SECS = 90  # 60s request timeout + startup headroom
_MAX_RESULTS = 100  # apify~rag-web-browser's maxResults input schema bound (min 1, max 100)
_WEB_FETCH_URL = 'https://web-fetch.apify.actor/'
_FETCH_TIMEOUT_SECS = 600
# apify/web-fetch itself is fast once warm (see plan's Global Constraints); this is generous
# headroom for a rare Standby cold start + a slow page.
_HTTP_ERROR_STATUS = 400  # smallest HTTP status code that apify/web-fetch treats as a failure


class ApifyWebSearchProvider(WebSearchProvider):
    """Apify web search backend — runs the apify~rag-web-browser Actor."""

    @property
    def name(self) -> str:
        """Return the provider identifier."""
        return 'apify'

    @property
    def display_name(self) -> str:
        """Return the user-facing provider name."""
        return 'Apify'

    def is_available(self) -> bool:
        """Return True when APIFY_API_TOKEN is configured."""
        return check_apify_api_key()

    def supports_search(self) -> bool:
        """Return True, as this provider supports web search."""
        return True

    def supports_extract(self) -> bool:
        """Return True, as this provider supports web content extraction."""
        return True

    def search(self, query: str, limit: int = 5) -> dict[str, Any]:
        """Run apify~rag-web-browser and return normalized web search results."""
        from tools.interrupt import is_interrupted

        if is_interrupted():
            return {'success': False, 'error': 'Interrupted'}

        try:
            clamped_limit = max(1, min(int(limit), _MAX_RESULTS))
            client = get_apify_client()
            run = client.actor(_RAG_ACTOR).start(
                run_input={'query': query, 'maxResults': clamped_limit, 'requestTimeoutSecs': 60}
            )
            finished = client.run(_attr(run, 'id')).wait_for_finish(wait_duration=timedelta(seconds=_SEARCH_WAIT_SECS))
            if finished is None or _attr(finished, 'status') not in {'SUCCEEDED', 'FAILED', 'ABORTED', 'TIMED-OUT'}:
                return {'success': False, 'error': f'Apify search timed out after {_SEARCH_WAIT_SECS}s'}
            status = _attr(finished, 'status')
            if status != 'SUCCEEDED':
                return {'success': False, 'error': f'Apify search run ended with status: {status}'}

            dataset_id = _attr(finished, 'default_dataset_id')
            items = list(_attr(client.dataset(dataset_id).list_items(), 'items') or []) if dataset_id else []
        except Exception as exc:  # BLE001 ignored repo-wide — report to the caller, never raise
            logger.warning('Apify web search error for %r: %s', query, exc)
            return {'success': False, 'error': f'Apify search failed: {exc}'}

        return {'success': True, 'data': {'web': _normalize_results(items, clamped_limit)}}

    async def extract(self, urls: list[str], **kwargs: Any) -> list[dict[str, Any]]:
        """Fetch one or more URLs via the apify/web-fetch Standby Actor."""
        from tools.interrupt import is_interrupted

        if is_interrupted():
            return [_error_result(u, 'Interrupted') for u in urls]

        formats = ['html'] if kwargs.get('format') == 'html' else ['markdown']

        try:
            token = get_apify_api_token()
        except Exception as exc:  # BLE001 ignored repo-wide — report to the caller, never raise
            return [_error_result(u, str(exc)) for u in urls]

        headers = {'Authorization': f'Bearer {token}'}

        # One client per call, shared by every URL in the batch. Not cached across calls: a
        # client's connection pool is bound to the event loop it was created under, and
        # hermes-agent may run each tool call on a different (sometimes disposable) loop, where
        # a cached client could neither be reused nor cleanly closed.
        # return_exceptions=True is a structural belt-and-braces guarantee: even if a future
        # change to _fetch_one lets an exception slip through, one bad URL still can't crash
        # the whole batch — it just becomes that URL's error result below.
        async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT_SECS, headers=_HERMES_HEADERS) as client:
            results = await asyncio.gather(
                *(self._fetch_one(client, url, formats, headers) for url in urls), return_exceptions=True
            )

        return [
            _error_result(url, str(result)) if isinstance(result, BaseException) else result
            for url, result in zip(urls, results, strict=True)
        ]

    async def _fetch_one(
        self, client: httpx.AsyncClient, url: str, formats: list[str], headers: dict[str, str]
    ) -> dict[str, Any]:
        """Fetch a single URL, never raising — failures come back as a structured error dict."""
        from tools.website_policy import check_website_access

        blocked = check_website_access(url)
        if blocked is not None:
            return _blocked_result(url, blocked)

        try:
            response = await client.post(_WEB_FETCH_URL, json={'url': url, 'formats': formats}, headers=headers)
        except Exception as exc:  # BLE001 ignored repo-wide — report to the caller, never raise
            logger.warning('Apify web fetch error for %r: %s', url, exc)
            return _error_result(url, str(exc))

        return _build_fetch_result(url, response, formats)

    def get_setup_schema(self) -> dict[str, Any]:
        """Return the setup configuration schema for this provider."""
        return {
            'name': 'Apify',
            'badge': 'paid',
            'tag': 'Google Search and web content extraction via Apify — pay-as-you-go platform usage.',
            'env_vars': [
                {
                    'key': 'APIFY_API_TOKEN',
                    'prompt': 'Apify API token',
                    'url': 'https://console.apify.com/settings/integrations?utm_source=hermes-agent&utm_medium=integrations',
                },
            ],
        }


def _normalize_results(items: list[Any], limit: int) -> list[dict[str, Any]]:
    """Normalize apify~rag-web-browser dataset items to the web_search_registry shape."""
    results: list[dict[str, Any]] = []
    for item in items[:limit]:
        search_result = _attr(item, 'searchResult') or {}
        title = _attr(search_result, 'title') or _attr(item, 'title', '')
        url = _attr(search_result, 'url') or _attr(item, 'url', '')
        description = _attr(search_result, 'description') or _attr(item, 'markdown', '')
        if description and len(description) > _MAX_DESCRIPTION_CHARS:
            description = description[:_MAX_DESCRIPTION_CHARS]
        results.append(
            {
                'title': title,
                'url': url,
                'description': description,
                'position': len(results) + 1,
            }
        )
    return results


def _error_result(url: str, message: str, **extra: Any) -> dict[str, Any]:
    """Build the standard per-URL extract() error result, with optional extra fields."""
    return {'url': url, 'title': '', 'content': '', 'raw_content': '', 'error': message, **extra}


def _blocked_result(url: str, blocked: dict[str, str]) -> dict[str, Any]:
    """Build the structured error result for a website-policy block (pre-fetch or post-redirect)."""
    return _error_result(
        url,
        blocked['message'],
        blocked_by_policy={'host': blocked['host'], 'rule': blocked['rule'], 'source': blocked['source']},
    )


def _coerce_dict(value: Any) -> dict[str, Any]:
    """Return value if it's a dict, else an empty dict."""
    return value if isinstance(value, dict) else {}


def _coerce_str(value: Any, default: str = '') -> str:
    """Return value if it's a str, else default."""
    return value if isinstance(value, str) else default


def _build_fetch_result(url: str, response: httpx.Response, formats: list[str]) -> dict[str, Any]:
    """Turn a completed apify/web-fetch HTTP response into a result or structured error dict."""
    from tools.website_policy import check_website_access

    # Check the status before parsing: error responses aren't guaranteed to be JSON (e.g. an
    # HTML 502 from the Standby gateway), and that must still surface as a status error.
    if response.status_code >= _HTTP_ERROR_STATUS:
        message = _parse_web_fetch_error(response)
        logger.warning('Apify web fetch failed for %r: %s', url, message)
        return _error_result(url, message)

    try:
        body = response.json()
    except Exception as exc:  # malformed response body
        return _error_result(url, f'Invalid response body: {exc}')

    if not isinstance(body, dict):
        return _error_result(url, 'Invalid response body: expected an object')

    fetch = _coerce_dict(body.get('fetch'))
    fetched_url = _coerce_str(fetch.get('loadedUrl')) or url
    metadata = _coerce_dict(body.get('metadata'))
    content = _coerce_str(body.get(formats[0]))
    title = _coerce_str(metadata.get('title'))

    # The Actor may have followed a server-side redirect our pre-fetch check never saw the
    # final host for. Re-check policy now, and do this *before* looking at the target's real
    # HTTP status below — a blocklisted host must not leak even an error page.
    if fetched_url != url:
        redirect_blocked = check_website_access(fetched_url)
        if redirect_blocked is not None:
            return _blocked_result(fetched_url, redirect_blocked)

    # response.status_code is the Actor invocation's own status — apify/web-fetch returns 200
    # whenever the Actor ran successfully, even if the *target* page 404'd/500'd. The target's
    # real status lives in fetch.httpStatusCode.
    http_status_code = fetch.get('httpStatusCode')
    if isinstance(http_status_code, int) and http_status_code >= _HTTP_ERROR_STATUS:
        return _error_result(fetched_url, f'Target URL returned HTTP {http_status_code}')

    return {
        'url': fetched_url,
        'title': title,
        'content': content,
        'raw_content': content,
        'metadata': metadata,
    }


def _parse_web_fetch_error(response: httpx.Response) -> str:
    """Parse either of apify/web-fetch's two error response shapes into a message.

    Falls back to a generic status message when the body isn't a JSON object.
    """
    fallback = f'Apify web fetch failed with status {response.status_code}'
    try:
        body = response.json()
    except Exception:  # non-JSON error body
        return fallback
    if not isinstance(body, dict):
        return fallback

    error = body.get('error')
    if isinstance(error, str) and isinstance(body.get('code'), str):
        return f'{error} (code: {body["code"]})'
    if isinstance(error, dict) and isinstance(error.get('message'), str):
        return error['message']
    return fallback
