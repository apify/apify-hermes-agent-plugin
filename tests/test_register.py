"""Tests for apify_hermes_agent_plugin.register()."""

from __future__ import annotations

from unittest.mock import MagicMock

from apify_hermes_agent_plugin import register
from apify_hermes_agent_plugin.cli import apify_setup_command, register_cli
from apify_hermes_agent_plugin.tools import _check_token


def test_register_registers_three_tools():
    ctx = MagicMock()
    register(ctx)
    assert ctx.register_tool.call_count == 3


def test_register_uses_apify_toolset_and_check_fn():
    ctx = MagicMock()
    register(ctx)
    for _, call in enumerate(ctx.register_tool.call_args_list):
        kwargs = call.kwargs
        assert kwargs['toolset'] == 'apify'
        assert kwargs['check_fn'] is _check_token
        assert kwargs['requires_env'] == ['APIFY_API_TOKEN']


def test_register_covers_all_three_tool_names():
    ctx = MagicMock()
    register(ctx)
    names = {call.kwargs['name'] for call in ctx.register_tool.call_args_list}
    assert names == {'apify_discover', 'apify_start', 'apify_collect'}


def test_register_marks_only_collect_as_async():
    ctx = MagicMock()
    register(ctx)
    by_name = {call.kwargs['name']: call.kwargs for call in ctx.register_tool.call_args_list}
    assert by_name['apify_discover'].get('is_async', False) is False
    assert by_name['apify_start'].get('is_async', False) is False
    assert by_name['apify_collect']['is_async'] is True


def test_register_wires_apify_setup_cli_command():
    ctx = MagicMock()
    register(ctx)
    ctx.register_cli_command.assert_called_once_with(
        name='apify-setup',
        help='Set your Apify API token',
        setup_fn=register_cli,
        handler_fn=apify_setup_command,
        description=('Prompt for (or accept via --token) your APIFY_API_TOKEN and save it to ~/.hermes/.env.'),
    )
