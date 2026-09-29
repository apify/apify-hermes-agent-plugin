"""Apify SDK client — token validation and cache."""

from __future__ import annotations

import logging
import os
from typing import Any

from apify_client import ApifyClient

logger = logging.getLogger(__name__)

# Sent with every request so Apify can attribute traffic to this integration.
_HERMES_HEADERS = {'x-apify-integration-platform': 'hermes-agent'}

_CLIENT: Any | None = None
_CLIENT_CONFIG: Any | None = None


def _resolve_apify_api_token() -> str:
    """Resolve APIFY_API_TOKEN across hermes-agent versions.

    Prefers ``agent.web_search_provider.get_provider_env`` (hermes-agent
    >=0.18.1): it checks ``os.environ`` first, then reads ``~/.hermes/.env``
    directly, which matters because gateway sessions, delegate children, and
    subprocess agent runs don't always have the token exported into the
    process environment even though `hermes apify-setup` persisted it.  Falls
    back to ``hermes_cli.config.get_env_value`` (same resolution order,
    available since 0.15.2 — our declared floor) on older hermes-agent, and
    to a bare ``os.getenv`` as a last resort if hermes_cli's internals are
    ever unavailable or change shape.
    """
    try:
        from agent.web_search_provider import get_provider_env

        return get_provider_env('APIFY_API_TOKEN')
    except Exception as exc:  # BLE001 ignored repo-wide — degrade to the next fallback
        logger.debug('get_provider_env unavailable (hermes-agent likely predates 0.18.1): %s', exc)

    try:
        from hermes_cli.config import get_env_value

        return (get_env_value('APIFY_API_TOKEN') or '').strip()
    except Exception as exc:  # BLE001 ignored repo-wide — hermes_cli internals have no stability guarantee
        logger.debug('hermes_cli.config.get_env_value unavailable: %s', exc)

    return os.getenv('APIFY_API_TOKEN', '').strip()


def check_apify_api_key() -> bool:
    """Return True when APIFY_API_TOKEN is configured."""
    return bool(_resolve_apify_api_token())


def get_apify_api_token() -> str:
    """Return APIFY_API_TOKEN, resolved across hermes-agent versions.

    Raises ValueError when the token is not set.
    """
    api_token = _resolve_apify_api_token()
    if not api_token:
        raise ValueError(
            'Apify tools are not configured. Set APIFY_API_TOKEN '
            '(get one at https://console.apify.com/settings/integrations?utm_source=hermes-agent&utm_medium=integrations).'
        )
    return api_token


def get_apify_client() -> Any:
    """Return a cached ApifyClient built from APIFY_API_TOKEN.

    Raises ValueError when the token is not set.
    """
    global _CLIENT, _CLIENT_CONFIG
    api_token = get_apify_api_token()
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
