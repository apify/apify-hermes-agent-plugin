"""Apify SDK client — token validation and cache."""

from __future__ import annotations

import os
from typing import Any

from apify_client import ApifyClient

# Sent with every request so Apify can attribute traffic to this integration.
_HERMES_HEADERS = {'x-apify-integration-platform': 'hermes-agent'}

_CLIENT: Any | None = None
_CLIENT_CONFIG: Any | None = None


def check_apify_api_key() -> bool:
    """Return True when APIFY_API_TOKEN is configured."""
    return bool(os.getenv('APIFY_API_TOKEN', '').strip())


def get_apify_client() -> Any:
    """Return a cached ApifyClient built from APIFY_API_TOKEN.

    Raises ValueError when the token is not set.
    """
    global _CLIENT, _CLIENT_CONFIG
    api_token = os.getenv('APIFY_API_TOKEN', '').strip()
    if not api_token:
        raise ValueError(
            'Apify tools are not configured. Set APIFY_API_TOKEN '
            '(get one at https://console.apify.com/settings/integrations?utm_source=hermes-agent&utm_medium=integrations).'
        )
    client_config = ('direct', api_token)
    if _CLIENT is not None and client_config == _CLIENT_CONFIG:
        return _CLIENT
    _CLIENT = ApifyClient(token=api_token, headers=_HERMES_HEADERS)
    _CLIENT_CONFIG = client_config
    return _CLIENT


def _reset_client_for_tests() -> None:
    """Drop cached client so tests can re-instantiate cleanly."""
    global _CLIENT, _CLIENT_CONFIG
    _CLIENT = None
    _CLIENT_CONFIG = None
