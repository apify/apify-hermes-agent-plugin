"""``hermes apify-setup`` — prompt for and save the Apify API token."""
from __future__ import annotations

import argparse
import getpass

from hermes_constants import get_hermes_home

_ENV_KEY = "APIFY_API_TOKEN"


def register_cli(parser: argparse.ArgumentParser) -> None:
    """Wire up ``hermes apify-setup`` argument parsing.

    Called by the Hermes plugin loader with the parser for this subcommand.
    """
    parser.add_argument(
        "--token",
        default=None,
        help=(
            "Apify API token (skips the interactive prompt). "
            "If omitted, you'll be prompted securely."
        ),
    )


def apify_setup_command(args: argparse.Namespace) -> int:
    """Prompt for (or accept via --token) the Apify API token and save it."""
    token = getattr(args, "token", None)
    if token:
        token = token.strip()
    else:
        print(
            "Set your Apify API token "
            "(get one at https://apify.com/account/integrations)."
        )
        token = getpass.getpass(f"{_ENV_KEY}: ").strip()

    if not token:
        print("No token provided — aborted.")
        return 1

    _write_env_var(_ENV_KEY, token)
    print(f"Saved {_ENV_KEY} to {get_hermes_home() / '.env'}")

    try:
        _enable_apify_toolset_for_cli()
        print("Enabled the Apify Actors toolset for the CLI.")
    except Exception as exc:  # noqa: BLE001
        print(f"Could not auto-enable the Apify Actors toolset ({exc}).")
        print("Run `hermes tools` and enable it manually.")

    return 0


def _enable_apify_toolset_for_cli() -> None:
    """Add "apify" to the set of toolsets enabled for the "cli" platform.

    Reuses hermes-agent's own config read/merge/save logic (rather than
    reimplementing it) since it has non-obvious invariants — reconciling
    agent.disabled_toolsets, preserving MCP server entries, plugin-toolset
    bookkeeping. These are private hermes_cli internals with no stability
    guarantee; callers should treat failure here as non-fatal.
    """
    from hermes_cli.config import load_config
    from hermes_cli.tools_config import _get_platform_tools, _save_platform_tools

    config = load_config()
    enabled = _get_platform_tools(config, "cli")
    enabled.add("apify")
    _save_platform_tools(config, "cli", enabled)


def _write_env_var(key: str, value: str) -> None:
    """Set ``key=value`` in the Hermes home ``.env`` file, preserving other lines."""
    env_path = get_hermes_home() / ".env"
    env_path.parent.mkdir(parents=True, exist_ok=True)

    lines = env_path.read_text().splitlines() if env_path.exists() else []
    prefix = f"{key}="
    new_lines = []
    replaced = False
    for line in lines:
        if line.startswith(prefix):
            new_lines.append(f"{key}={value}")
            replaced = True
        else:
            new_lines.append(line)
    if not replaced:
        new_lines.append(f"{key}={value}")

    env_path.write_text("\n".join(new_lines) + "\n")
    env_path.chmod(0o600)
