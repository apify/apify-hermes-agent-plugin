"""Apify web-search provider for Hermes Agent's pluggable web-search backend."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

import httpx
from agent.web_search_provider import WebSearchProvider

from apify_hermes_agent_plugin.client import check_apify_api_key, get_apify_api_token, get_apify_client
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
            return [{'url': u, 'title': '', 'content': '', 'raw_content': '', 'error': 'Interrupted'} for u in urls]

        formats = ['html'] if kwargs.get('format') == 'html' else ['markdown']

        async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT_SECS) as client:
            return list(await asyncio.gather(*(self._fetch_one(client, url, formats) for url in urls)))

    async def _fetch_one(self, client: httpx.AsyncClient, url: str, formats: list[str]) -> dict[str, Any]:
        """Fetch a single URL, never raising — failures come back as a structured error dict."""
        from tools.website_policy import check_website_access

        blocked = check_website_access(url)
        if blocked is not None:
            return {'url': url, 'title': '', 'content': '', 'raw_content': '', 'error': blocked['message']}

        try:
            token = get_apify_api_token()
            response = await client.post(
                _WEB_FETCH_URL,
                json={'url': url, 'formats': formats},
                headers={'Authorization': f'Bearer {token}'},
            )
        except Exception as exc:  # BLE001 ignored repo-wide — report to the caller, never raise
            return {'url': url, 'title': '', 'content': '', 'raw_content': '', 'error': str(exc)}

        try:
            body = response.json()
        except Exception as exc:  # malformed response body
            return {'url': url, 'title': '', 'content': '', 'raw_content': '', 'error': f'Invalid response body: {exc}'}

        if not isinstance(body, dict):
            return {
                'url': url,
                'title': '',
                'content': '',
                'raw_content': '',
                'error': 'Invalid response body: expected an object',
            }

        if response.status_code >= _HTTP_ERROR_STATUS:
            return {
                'url': url,
                'title': '',
                'content': '',
                'raw_content': '',
                'error': _parse_web_fetch_error(response.status_code, body),
            }

        metadata = body.get('metadata') or {}
        content = body.get(formats[0]) or ''
        fetched_url = (body.get('fetch') or {}).get('loadedUrl') or url

        return {
            'url': fetched_url,
            'title': metadata.get('title') or '',
            'content': content,
            'raw_content': content,
            'metadata': metadata,
        }

    def get_setup_schema(self) -> dict[str, Any]:
        """Return the setup configuration schema for this provider."""
        return {
            'name': 'Apify',
            'badge': 'paid',
            'tag': "Google Search via Apify's RAG Web Browser Actor — pay-as-you-go platform usage.",
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


def _parse_web_fetch_error(status_code: int, body: dict[str, Any]) -> str:
    """Parse either of apify/web-fetch's two error response shapes into a message."""
    error = body.get('error')
    if isinstance(error, str) and isinstance(body.get('code'), str):
        return f'{error} (code: {body["code"]})'
    if isinstance(error, dict) and isinstance(error.get('message'), str):
        return error['message']
    return f'Apify web fetch failed with status {status_code}'
