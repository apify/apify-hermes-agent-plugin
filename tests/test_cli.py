"""Tests for apify_hermes_agent_plugin.cli — the `hermes apify-setup` command."""
from __future__ import annotations

import argparse

import pytest


@pytest.fixture(autouse=True)
def _mock_hermes_cli_internals(monkeypatch):
    """By default, stub all hermes_cli internals this module reaches into,
    so tests never touch the real ~/.hermes/config.yaml or ~/.hermes/.env.

    Patched at the source (hermes_cli.config / hermes_cli.tools_config)
    rather than on our own wrapper functions — tests that exercise a
    wrapper itself need the real wrapper, just with safe internals.
    """
    monkeypatch.setattr("hermes_cli.config.load_config", lambda: {})
    monkeypatch.setattr("hermes_cli.config.save_env_value", lambda key, value: None)
    monkeypatch.setattr(
        "hermes_cli.tools_config.PLATFORMS", {"cli": {"default_toolset": "hermes-cli"}}
    )
    monkeypatch.setattr(
        "hermes_cli.tools_config._get_platform_tools",
        lambda config, platform: set(),
    )
    monkeypatch.setattr(
        "hermes_cli.tools_config._save_platform_tools",
        lambda config, platform, enabled: None,
    )


def test_register_cli_adds_token_argument():
    from apify_hermes_agent_plugin.cli import register_cli
    parser = argparse.ArgumentParser()
    register_cli(parser)
    args = parser.parse_args(["--token", "abc123"])
    assert args.token == "abc123"


def test_register_cli_token_optional():
    from apify_hermes_agent_plugin.cli import register_cli
    parser = argparse.ArgumentParser()
    register_cli(parser)
    args = parser.parse_args([])
    assert args.token is None


# ---------------------------------------------------------------------------
# apify_setup_command — token handling
# ---------------------------------------------------------------------------

def test_setup_command_with_token_flag_writes_env_and_skips_prompt(monkeypatch):
    prompted = []
    monkeypatch.setattr(
        "apify_hermes_agent_plugin.cli.getpass.getpass",
        lambda *a, **k: prompted.append(True) or "should-not-be-used",
    )
    saved = {}
    monkeypatch.setattr(
        "hermes_cli.config.save_env_value",
        lambda key, value: saved.update(key=key, value=value),
    )

    from apify_hermes_agent_plugin.cli import apify_setup_command
    args = argparse.Namespace(token="tok_from_flag")
    rc = apify_setup_command(args)

    assert rc == 0
    assert not prompted
    assert saved == {"key": "APIFY_API_TOKEN", "value": "tok_from_flag"}


def test_setup_command_prompts_when_no_token_flag(monkeypatch):
    monkeypatch.setattr(
        "apify_hermes_agent_plugin.cli.getpass.getpass",
        lambda *a, **k: "tok_from_prompt",
    )
    saved = {}
    monkeypatch.setattr(
        "hermes_cli.config.save_env_value",
        lambda key, value: saved.update(key=key, value=value),
    )

    from apify_hermes_agent_plugin.cli import apify_setup_command
    args = argparse.Namespace(token=None)
    rc = apify_setup_command(args)

    assert rc == 0
    assert saved == {"key": "APIFY_API_TOKEN", "value": "tok_from_prompt"}


def test_setup_command_rejects_whitespace_only_prompted_token(monkeypatch):
    monkeypatch.setattr(
        "apify_hermes_agent_plugin.cli.getpass.getpass",
        lambda *a, **k: "   ",
    )
    saved = {}
    monkeypatch.setattr(
        "hermes_cli.config.save_env_value",
        lambda key, value: saved.update(key=key, value=value),
    )

    from apify_hermes_agent_plugin.cli import apify_setup_command
    args = argparse.Namespace(token=None)

    with pytest.raises(SystemExit) as exc_info:
        apify_setup_command(args)

    assert exc_info.value.code == 1
    assert not saved


def test_setup_command_rejects_explicit_empty_token_flag_without_prompting(monkeypatch):
    """An explicit `--token ""` must abort immediately, not fall through to
    the interactive prompt (that would hang/EOFError on non-interactive stdin,
    e.g. `--token "$TOKEN"` with an unset $TOKEN in a script)."""
    prompted = []
    monkeypatch.setattr(
        "apify_hermes_agent_plugin.cli.getpass.getpass",
        lambda *a, **k: prompted.append(True) or "unused",
    )
    saved = {}
    monkeypatch.setattr(
        "hermes_cli.config.save_env_value",
        lambda key, value: saved.update(key=key, value=value),
    )

    from apify_hermes_agent_plugin.cli import apify_setup_command
    args = argparse.Namespace(token="")

    with pytest.raises(SystemExit) as exc_info:
        apify_setup_command(args)

    assert exc_info.value.code == 1
    assert not prompted
    assert not saved


# ---------------------------------------------------------------------------
# Toolset auto-enable
# ---------------------------------------------------------------------------

def test_setup_command_enables_apify_toolset_for_cli(monkeypatch):
    saved = {}
    monkeypatch.setattr(
        "hermes_cli.tools_config._save_platform_tools",
        lambda config, platform, enabled: saved.update(platform=platform, enabled=enabled),
    )

    from apify_hermes_agent_plugin.cli import apify_setup_command
    args = argparse.Namespace(token="tok")
    rc = apify_setup_command(args)

    assert rc == 0
    assert saved["platform"] == "cli"
    assert "apify" in saved["enabled"]


def test_setup_command_succeeds_even_if_toolset_enable_raises(monkeypatch, capsys):
    def _boom():
        raise RuntimeError("hermes_cli internals changed")

    monkeypatch.setattr("hermes_cli.config.load_config", _boom)

    from apify_hermes_agent_plugin.cli import apify_setup_command
    args = argparse.Namespace(token="tok")
    rc = apify_setup_command(args)

    assert rc == 0
    assert "hermes tools" in capsys.readouterr().out


def test_enable_apify_toolset_preserves_implicit_defaults_when_no_explicit_config(monkeypatch):
    """When the "cli" platform has no explicit toolset list yet, don't
    expand+freeze the implicit default composite — reference it by name."""
    fake_config = {}  # no "platform_toolsets" key at all
    saved = {}
    resolve_calls = []

    monkeypatch.setattr("hermes_cli.config.load_config", lambda: fake_config)
    monkeypatch.setattr(
        "hermes_cli.tools_config.PLATFORMS", {"cli": {"default_toolset": "hermes-cli"}}
    )
    monkeypatch.setattr(
        "hermes_cli.tools_config._get_platform_tools",
        lambda config, platform: resolve_calls.append(True) or set(),
    )

    def _fake_save(config, platform, enabled):
        saved["platform"] = platform
        saved["enabled"] = enabled

    monkeypatch.setattr("hermes_cli.tools_config._save_platform_tools", _fake_save)

    from apify_hermes_agent_plugin.cli import _enable_apify_toolset_for_cli
    _enable_apify_toolset_for_cli()

    assert not resolve_calls, "must not resolve/expand the implicit default set"
    assert saved["platform"] == "cli"
    assert saved["enabled"] == {"hermes-cli", "apify"}


def test_enable_apify_toolset_extends_existing_explicit_config(monkeypatch):
    """When the "cli" platform already has an explicit toolset list, extend
    it via the normal resolve path — no freezing risk since it's already
    explicit."""
    fake_config = {"platform_toolsets": {"cli": ["web_search", "spotify"]}}
    saved = {}

    monkeypatch.setattr("hermes_cli.config.load_config", lambda: fake_config)
    monkeypatch.setattr(
        "hermes_cli.tools_config._get_platform_tools",
        lambda config, platform: {"web_search", "spotify"} if platform == "cli" else set(),
    )

    def _fake_save(config, platform, enabled):
        saved["platform"] = platform
        saved["enabled"] = enabled

    monkeypatch.setattr("hermes_cli.tools_config._save_platform_tools", _fake_save)

    from apify_hermes_agent_plugin.cli import _enable_apify_toolset_for_cli
    _enable_apify_toolset_for_cli()

    assert saved["platform"] == "cli"
    assert saved["enabled"] == {"web_search", "spotify", "apify"}
