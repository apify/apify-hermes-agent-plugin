# apify-hermes-agent-plugin

Hermes Agent plugin for [Apify](https://apify.com), the world's largest marketplace for AI tools — discover
Actors in the Apify Store, start runs, and collect structured results, all from natural language, via
[Hermes Agent](https://hermes-agent.nousresearch.com).

## Install

    pip install apify-hermes-agent-plugin
    hermes plugins enable apify

Then run:

    hermes apify-setup

This prompts for your `APIFY_API_TOKEN` (get one at https://apify.com/account/integrations),
saves it, and enables the Apify Actors toolset for the CLI. Pass `--token <token>` to skip the
prompt.

### Troubleshooting: `hermes plugins enable apify` fails

If that command prints `Plugin 'apify' is not installed or bundled.`, your installed
`hermes-agent` predates the fix for discovering pip/entry-point plugins. Check your version
and upgrade first:

    hermes --version
    pip install --upgrade hermes-agent

If you can't upgrade, enable the plugin manually instead: open `~/.hermes/config.yaml` and
add `apify` to the `plugins.enabled` list:

    plugins:
      enabled:
        - apify

Then run `hermes apify-setup` as above — it still takes care of enabling the toolset for you.

## Tools

- `apify_discover` — search the Apify Store by keyword, or fetch an Actor's input schema + README by `actor_id`.
- `apify_start` — fire-and-forget batch Actor starts (up to 10 per call).
- `apify_collect` — poll run statuses and return completed dataset results.

## Development

    pip install -e ".[dev]"
    pytest
