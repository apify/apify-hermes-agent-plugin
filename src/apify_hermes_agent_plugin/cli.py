"""``hermes apify-setup`` — prompt for and save the Apify API token."""

from __future__ import annotations

import getpass
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import argparse

_ENV_KEY = 'APIFY_API_TOKEN'


def register_cli(parser: argparse.ArgumentParser) -> None:
    """Wire up ``hermes apify-setup`` argument parsing.

    Called by the Hermes plugin loader with the parser for this subcommand.
    """
    parser.add_argument(
        '--token',
        default=None,
        help=("Apify API token (skips the interactive prompt). If omitted, you'll be prompted securely."),
    )


def apify_setup_command(args: argparse.Namespace) -> int:
    """Prompt for (or accept via --token) the Apify API token and save it."""
    token = getattr(args, 'token', None)
    if token is not None:
        token = token.strip()
    else:
        print(
            'Set your Apify API token '
            '(get one at https://console.apify.com/settings/integrations?utm_source=hermes-agent&utm_medium=integrations).'
        )
        token = getpass.getpass(f'{_ENV_KEY}: ').strip()

    if not token:
        print('No token provided — aborted.')
        sys.exit(1)

    from hermes_cli.config import get_env_path, save_env_value

    save_env_value(_ENV_KEY, token)
    print(f'Saved {_ENV_KEY} to {get_env_path()}')

    try:
        _enable_apify_toolset_for_cli()
        print('Enabled the Apify Actors toolset for the CLI.')
    except Exception as exc:
        print(f'Could not auto-enable the Apify Actors toolset ({exc}).')
        print('Run `hermes tools` and enable it manually.')

    return 0


def _enable_apify_toolset_for_cli() -> None:
    """Add "apify" to the set of toolsets enabled for the "cli" platform.

    Reuses hermes-agent's own config read/merge/save logic (rather than
    reimplementing it) since it has non-obvious invariants — reconciling
    agent.disabled_toolsets, preserving MCP server entries, plugin-toolset
    bookkeeping. These are private hermes_cli internals with no stability
    guarantee; callers should treat failure here as non-fatal.

    If the "cli" platform has no explicit toolset list yet, resolving and
    saving it (via ``_get_platform_tools``) would expand the implicit
    default composite (every default-on toolset, plus MCP servers) into a
    frozen explicit snapshot — silently opting this user out of any future
    default-on toolset that ships in a later hermes-agent release. Instead,
    keep the composite referenced by name (the same "[hermes-cli, spotify]"
    mixed-config shape ``_get_platform_tools`` already supports for a single
    explicit opt-in alongside the defaults).
    """
    from hermes_cli.config import load_config
    from hermes_cli.tools_config import PLATFORMS, _get_platform_tools, _save_platform_tools

    config = load_config()
    existing = (config.get('platform_toolsets') or {}).get('cli')

    if isinstance(existing, list):
        enabled = _get_platform_tools(config, 'cli')
    else:
        default_ts = PLATFORMS.get('cli', {}).get('default_toolset', 'hermes-cli')
        enabled = {default_ts}

    enabled.add('apify')
    _save_platform_tools(config, 'cli', enabled)
