"""Tests for apify_hermes_agent_plugin.cli — the `hermes apify-setup` command."""
from __future__ import annotations

import argparse

import pytest


@pytest.fixture
def env_path(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "apify_hermes_agent_plugin.cli.get_hermes_home",
        lambda: tmp_path,
    )
    return tmp_path / ".env"


@pytest.fixture(autouse=True)
def _mock_hermes_cli_internals(monkeypatch):
    """By default, stub the hermes_cli internals _enable_apify_toolset_for_cli
    reaches into, so tests never touch the real ~/.hermes/config.yaml.

    Patched at the source (hermes_cli.config / hermes_cli.tools_config)
    rather than on our own wrapper function — tests that exercise the
    wrapper itself need the real wrapper, just with safe internals.
    """
    monkeypatch.setattr("hermes_cli.config.load_config", lambda: {})
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


def test_setup_command_with_token_flag_writes_env_and_skips_prompt(env_path, monkeypatch):
    prompted = []
    monkeypatch.setattr(
        "apify_hermes_agent_plugin.cli.getpass.getpass",
        lambda *a, **k: prompted.append(True) or "should-not-be-used",
    )

    from apify_hermes_agent_plugin.cli import apify_setup_command
    args = argparse.Namespace(token="tok_from_flag")
    rc = apify_setup_command(args)

    assert rc == 0
    assert not prompted
    assert env_path.read_text() == "APIFY_API_TOKEN=tok_from_flag\n"


def test_setup_command_prompts_when_no_token_flag(env_path, monkeypatch):
    monkeypatch.setattr(
        "apify_hermes_agent_plugin.cli.getpass.getpass",
        lambda *a, **k: "tok_from_prompt",
    )

    from apify_hermes_agent_plugin.cli import apify_setup_command
    args = argparse.Namespace(token=None)
    rc = apify_setup_command(args)

    assert rc == 0
    assert env_path.read_text() == "APIFY_API_TOKEN=tok_from_prompt\n"


def test_setup_command_rejects_empty_token(env_path, monkeypatch):
    monkeypatch.setattr(
        "apify_hermes_agent_plugin.cli.getpass.getpass",
        lambda *a, **k: "   ",
    )

    from apify_hermes_agent_plugin.cli import apify_setup_command
    args = argparse.Namespace(token=None)
    rc = apify_setup_command(args)

    assert rc == 1
    assert not env_path.exists()


def test_setup_command_replaces_existing_key_preserving_others(env_path, monkeypatch):
    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text("OTHER_KEY=keep-me\nAPIFY_API_TOKEN=old-token\nANOTHER=also-keep\n")

    from apify_hermes_agent_plugin.cli import apify_setup_command
    args = argparse.Namespace(token="new-token")
    rc = apify_setup_command(args)

    assert rc == 0
    content = env_path.read_text()
    assert "OTHER_KEY=keep-me" in content
    assert "ANOTHER=also-keep" in content
    assert "APIFY_API_TOKEN=new-token" in content
    assert "old-token" not in content


def test_setup_command_appends_when_env_file_has_no_apify_key(env_path, monkeypatch):
    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text("OTHER_KEY=keep-me\n")

    from apify_hermes_agent_plugin.cli import apify_setup_command
    args = argparse.Namespace(token="fresh-token")
    rc = apify_setup_command(args)

    assert rc == 0
    content = env_path.read_text()
    assert "OTHER_KEY=keep-me" in content
    assert "APIFY_API_TOKEN=fresh-token" in content


def test_write_env_var_sets_restrictive_permissions(env_path, monkeypatch):
    from apify_hermes_agent_plugin.cli import _write_env_var
    _write_env_var("APIFY_API_TOKEN", "tok")

    mode = env_path.stat().st_mode & 0o777
    assert mode == 0o600


# ---------------------------------------------------------------------------
# Toolset auto-enable
# ---------------------------------------------------------------------------

def test_setup_command_enables_apify_toolset_for_cli(env_path, monkeypatch):
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


def test_setup_command_succeeds_even_if_toolset_enable_raises(env_path, monkeypatch, capsys):
    def _boom():
        raise RuntimeError("hermes_cli internals changed")

    monkeypatch.setattr("hermes_cli.config.load_config", _boom)

    from apify_hermes_agent_plugin.cli import apify_setup_command
    args = argparse.Namespace(token="tok")
    rc = apify_setup_command(args)

    assert rc == 0
    assert env_path.read_text() == "APIFY_API_TOKEN=tok\n"
    assert "hermes tools" in capsys.readouterr().out


def test_enable_apify_toolset_for_cli_merges_with_existing_and_saves(monkeypatch):
    fake_config = {"marker": "config"}
    saved = {}

    monkeypatch.setattr("hermes_cli.config.load_config", lambda: fake_config)
    monkeypatch.setattr(
        "hermes_cli.tools_config._get_platform_tools",
        lambda config, platform: {"web_search"} if platform == "cli" else set(),
    )

    def _fake_save(config, platform, enabled):
        saved["config"] = config
        saved["platform"] = platform
        saved["enabled"] = enabled

    monkeypatch.setattr("hermes_cli.tools_config._save_platform_tools", _fake_save)

    from apify_hermes_agent_plugin.cli import _enable_apify_toolset_for_cli
    _enable_apify_toolset_for_cli()

    assert saved["config"] is fake_config
    assert saved["platform"] == "cli"
    assert saved["enabled"] == {"web_search", "apify"}
