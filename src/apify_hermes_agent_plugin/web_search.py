"""Apify web-search provider for Hermes Agent's pluggable web-search backend."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx
from agent.web_search_provider import WebSearchProvider

from apify_hermes_agent_plugin.client import (
    _HERMES_HEADERS,
    check_apify_api_key,
    get_apify_api_token,
    get_hermes_env,
)

logger = logging.getLogger(__name__)

_SEARCH_ACTOR = 'apify~web-search'
# One synchronous request: starts the run, waits for it, and returns its dataset items.
_SEARCH_URL = f'https://api.apify.com/v2/acts/{_SEARCH_ACTOR}/run-sync-get-dataset-items'
_SEARCH_TIMEOUT_SECS = 90  # a Google results page is fast; this is headroom for a cold Actor start
_MAX_DESCRIPTION_CHARS = 500
_MAX_RESULTS = 10  # apify~web-search scrapes a single Google results page, which holds ~10 organic results
# Optional install-wide search defaults. Hermes only hands search() a query and a limit, so the
# agent can't pick these per call; unset means the Actor's own defaults (US / en).
_SEARCH_ENV_INPUTS = {'APIFY_WEB_SEARCH_COUNTRY': 'countryCode', 'APIFY_WEB_SEARCH_LANGUAGE': 'languageCode'}
_WEB_FETCH_URL = 'https://web-fetch.apify.actor/'
_FETCH_TIMEOUT_SECS = 600
# apify/web-fetch itself is fast once warm (see plan's Global Constraints); this is generous
# headroom for a rare Standby cold start + a slow page.
_HTTP_ERROR_STATUS = 400  # smallest HTTP status code treated as a failure (Apify API and apify/web-fetch)


class ApifyWebSearchProvider(WebSearchProvider):
    """Apify web search backend — runs apify~web-search for search and apify/web-fetch for extract."""

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
        """Run apify~web-search synchronously and return normalized web search results."""
        from tools.interrupt import is_interrupted

        if is_interrupted():
            return {'success': False, 'error': 'Interrupted'}

        try:
            clamped_limit = max(1, min(int(limit), _MAX_RESULTS))
            run_input: dict[str, Any] = {'query': query, 'maxResults': clamped_limit}
            for env_name, input_key in _SEARCH_ENV_INPUTS.items():
                value = (get_hermes_env(env_name) or '').strip()
                if value:
                    run_input[input_key] = value
            headers = {'Authorization': f'Bearer {get_apify_api_token()}'}
            with httpx.Client(timeout=_SEARCH_TIMEOUT_SECS, headers=_HERMES_HEADERS) as client:
                response = client.post(_SEARCH_URL, json=run_input, headers=headers)
            if response.status_code >= _HTTP_ERROR_STATUS:
                message = _parse_apify_api_error(response)
                logger.warning('Apify web search failed for %r: %s', query, message)
                return {'success': False, 'error': message}
            items = response.json()
        except Exception as exc:  # BLE001 ignored repo-wide — report to the caller, never raise
            logger.warning('Apify web search error for %r: %s', query, exc)
            return {'success': False, 'error': f'Apify search failed: {exc}'}

        if not isinstance(items, list):
            return {'success': False, 'error': 'Apify search failed: unexpected response body'}

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
    """Normalize apify~web-search dataset items to the web_search_registry shape.

    The Actor returns one item per search, holding the organic hits in ``results``.
    """
    hits = [hit for item in items if isinstance(item, dict) for hit in _coerce_list(item.get('results'))]
    results: list[dict[str, Any]] = []
    for hit in hits:
        if len(results) >= limit:
            break
        if not isinstance(hit, dict):
            continue
        results.append(
            {
                'title': _coerce_str(hit.get('title')),
                'url': _coerce_str(hit.get('url')),
                'description': _coerce_str(hit.get('snippet'))[:_MAX_DESCRIPTION_CHARS],
                'position': len(results) + 1,
            }
        )
    return results


def _parse_apify_api_error(response: httpx.Response) -> str:
    """Turn an Apify API error response (``{"error": {"message": ...}}``) into a message."""
    message = f'Apify search failed with status {response.status_code}'
    try:
        error = _coerce_dict(_coerce_dict(response.json()).get('error'))
    except Exception:  # non-JSON error body, e.g. an HTML 502 from a gateway
        return message
    detail = _coerce_str(error.get('message'))
    return f'{message}: {detail}' if detail else message


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


def _coerce_list(value: Any) -> list[Any]:
    """Return value if it's a list, else an empty list."""
    return value if isinstance(value, list) else []


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
