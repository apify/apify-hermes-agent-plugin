"""apify-hermes-agent-plugin — Apify Actor execution tools for Hermes Agent."""

from __future__ import annotations

from apify_hermes_agent_plugin.cli import apify_setup_command, register_cli
from apify_hermes_agent_plugin.tools import (
    _COLLECT_SCHEMA,
    _DISCOVER_SCHEMA,
    _START_SCHEMA,
    _check_token,
    collect_handler_str,
    discover_handler_str,
    start_handler_str,
)

_TOOLS = (
    ('apify_discover', _DISCOVER_SCHEMA, discover_handler_str, '🔍', False),
    ('apify_start', _START_SCHEMA, start_handler_str, '▶️', False),
    ('apify_collect', _COLLECT_SCHEMA, collect_handler_str, '📦', True),
)


def register(ctx) -> None:
    """Register the three Apify Actor tools. Called once by the Hermes plugin loader."""
    for name, schema, handler, emoji, is_async in _TOOLS:
        ctx.register_tool(
            name=name,
            toolset='apify',
            schema=schema,
            handler=handler,
            check_fn=_check_token,
            requires_env=['APIFY_API_TOKEN'],
            is_async=is_async,
            emoji=emoji,
        )

    ctx.register_cli_command(
        name='apify-setup',
        help='Set your Apify API token',
        setup_fn=register_cli,
        handler_fn=apify_setup_command,
        description=('Prompt for (or accept via --token) your APIFY_API_TOKEN and save it to ~/.hermes/.env.'),
    )
