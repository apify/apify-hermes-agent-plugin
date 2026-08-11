# apify-hermes-agent-plugin

Hermes Agent plugin for [Apify](https://apify.com), the world's largest marketplace for AI tools — discover
Actors in the Apify Store, start runs, and collect structured results, all from natural language, via
[Hermes Agent](https://hermes-agent.nousresearch.com).

## Install

    pip install apify-hermes-agent-plugin

`hermes plugins enable apify` currently doesn't recognize pip-installed plugins (a hermes-agent
CLI bug — it only scans bundled/user plugin directories, not `hermes_agent.plugins` entry points).
Until that's fixed upstream, enable it directly in `~/.hermes/config.yaml`:

    plugins:
      enabled:
        - apify

Then run:

    hermes apify-setup

This prompts for your `APIFY_API_TOKEN` (get one at https://apify.com/account/integrations),
saves it, and enables the Apify Actors toolset for the CLI. Pass `--token <token>` to skip the
prompt.

## Tools

- `apify_discover` — search the Apify Store by keyword, or fetch an Actor's input schema + README by `actor_id`.
- `apify_start` — fire-and-forget batch Actor starts (up to 10 per call).
- `apify_collect` — poll run statuses and return completed dataset results.

## Development

    pip install -e ".[dev]"
    pytest
