"""Apify web-search provider for Hermes Agent's pluggable web-search backend."""

from __future__ import annotations

import logging
from typing import Any

from agent.web_search_provider import WebSearchProvider

from apify_hermes_agent_plugin.client import check_apify_api_key, get_apify_client
from apify_hermes_agent_plugin.tools import _attr

logger = logging.getLogger(__name__)

_RAG_ACTOR = 'apify~rag-web-browser'
_MAX_DESCRIPTION_CHARS = 500


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

    def search(self, query: str, limit: int = 5) -> dict[str, Any]:
        """Run apify~rag-web-browser and return normalized web search results."""
        from tools.interrupt import is_interrupted

        if is_interrupted():
            return {'success': False, 'error': 'Interrupted'}

        client = get_apify_client()
        try:
            run = client.actor(_RAG_ACTOR).start(
                run_input={'query': query, 'maxResults': limit, 'requestTimeoutSecs': 60}
            )
            finished = client.run(_attr(run, 'id')).wait_for_finish()
            status = _attr(finished, 'status')
            if status != 'SUCCEEDED':
                return {'success': False, 'error': f'Apify search run ended with status: {status}'}

            dataset_id = _attr(finished, 'default_dataset_id')
            items = list(_attr(client.dataset(dataset_id).list_items(), 'items') or []) if dataset_id else []
        except Exception as exc:  # BLE001 ignored repo-wide — report to the caller, never raise
            logger.warning('Apify web search error for %r: %s', query, exc)
            return {'success': False, 'error': f'Apify search failed: {exc}'}

        return {'success': True, 'data': {'web': _normalize_results(items, limit)}}

    def get_setup_schema(self) -> dict[str, Any]:
        """Return the setup configuration schema for this provider."""
        return {
            'name': 'Apify',
            'badge': 'paid',
            'tag': "Apify's RAG Web Browser Actor, with residential-proxy-backed search.",
            'env_vars': [
                {
                    'key': 'APIFY_API_TOKEN',
                    'prompt': 'Apify API token',
                    'url': 'https://console.apify.com/settings/integrations',
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
