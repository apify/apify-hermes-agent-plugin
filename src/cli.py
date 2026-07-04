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
    print("Run `hermes tools` to enable the Apify Actors toolset if you haven't already.")
    return 0


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
