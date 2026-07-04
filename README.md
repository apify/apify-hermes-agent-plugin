# apify-hermes-agent-plugin

Apify Actor execution tools for [Hermes Agent](https://hermes-agent.nousresearch.com) — discover Actors in the
Apify Store, start runs, and collect structured results, all from natural language.

## Install

    pip install apify-hermes-agent-plugin
    hermes plugins enable apify

Then run `hermes tools`, find **Apify Actors**, enable the toolset, and set your `APIFY_API_TOKEN`
(get one at https://apify.com/account/integrations).

## Tools

- `apify_discover` — search the Apify Store by keyword, or fetch an Actor's input schema + README by `actor_id`.
- `apify_start` — fire-and-forget batch Actor starts (up to 10 per call).
- `apify_collect` — poll run statuses and return completed dataset results.

## Development

    pip install -e ".[dev]"
    pytest
