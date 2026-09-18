"""Apify web-search provider for Hermes Agent's pluggable web-search backend."""

from __future__ import annotations

import logging
from typing import Any

from agent.web_search_provider import WebSearchProvider

from apify_hermes_agent_plugin.client import check_apify_api_key

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
