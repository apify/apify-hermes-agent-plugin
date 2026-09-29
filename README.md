# apify-hermes-agent-plugin

Hermes Agent plugin for [Apify](https://apify.com), the world's largest marketplace for AI tools - discover
Actors in Apify Store, start runs, and collect structured results, all from natural language, via
[Hermes Agent](https://hermes-agent.nousresearch.com).

## Install

    pip install apify-hermes-agent-plugin
    hermes plugins enable apify

Then run:

    hermes apify-setup

This prompts for your `APIFY_API_TOKEN` (get one at https://console.apify.com/settings/integrations?utm_source=hermes-agent&utm_medium=integrations),
saves it, and enables the Apify Actors toolset for the CLI. Pass `--token <token>` to skip the
prompt.

### Troubleshooting: `hermes plugins enable apify` fails

If that command prints `Plugin 'apify' is not installed or bundled.`, your installed
`hermes-agent` predates `0.18.1`, when entry-point plugin discovery was fixed upstream.
Check your version and upgrade first:

    hermes --version
    pip install --upgrade hermes-agent

If you can't upgrade, enable the plugin manually instead: open `~/.hermes/config.yaml` and
add `apify` to the `plugins.enabled` list:

    plugins:
      enabled:
        - apify

Then run `hermes apify-setup` as above - it still takes care of enabling the toolset for you.

## Tools

- `apify_discover` - search Apify Store by keyword, or fetch an Actor's input schema + README by `actor_id`.
- `apify_start` - fire-and-forget batch Actor starts (up to 10 per call).
- `apify_collect` - poll run statuses and return completed dataset results.

## Web search & fetch

This plugin also registers `apify` as a Hermes Agent web search and web-fetch backend,
running the [RAG Web Browser](https://apify.com/apify/rag-web-browser) Actor for search and
the [Web Fetch](https://apify.com/apify/web-fetch) Actor for content extraction. Both use the
same `APIFY_API_TOKEN` configured above - no separate setup needed.

To use them, set the search and/or extract backend in `~/.hermes/config.yaml`:

    web:
      search_backend: apify
      extract_backend: apify

or select `apify` interactively via `hermes tools`.

## Development

    pip install -e ".[dev]"
    pytest

### Releasing

Releases are cut from the **Actions** tab, not by creating a GitHub Release by hand: open
the `publish` workflow → **Run workflow** → choose a release type (`auto`, `patch`, `minor`,
`major`, or `custom`). The pipeline then bumps the version, updates `CHANGELOG.md`, creates
the GitHub Release, and publishes to PyPI automatically.

`auto` infers the version bump from Conventional Commits since the last tag, and only works
correctly when at least one qualifies (`feat:`, `fix:`, etc. — see `AGENTS.md`'s
[Release process](AGENTS.md#release-process) for the exact rules). If you're not sure,
pick `patch`/`minor`/`major` explicitly instead — those always compute correctly regardless
of commit history.
