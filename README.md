# apify-hermes-agent-plugin

Hermes Agent plugin for [Apify](https://apify.com), the world's largest marketplace for AI tools - discover
Actors in Apify Store, start runs, and collect structured results, all from natural language, via
[Hermes Agent](https://hermes-agent.nousresearch.com).

## Install

The plugin is listed in the [Hermes plugin catalog](https://hermes-agent.nousresearch.com/docs/plugins/apify)
and published on [PyPI](https://pypi.org/project/apify-hermes-agent-plugin/).

### From the Hermes plugin catalog (recommended)

Use this if you installed Hermes with its official installer or keep it current with `hermes update`:

    hermes plugins install apify --enable

When asked whether to prepare the plugin's Python dependencies (`apify-client`, `httpx`),
answer `y`. If you decline, or run the command non-interactively, the plugin is installed but
stays disabled until you run `hermes plugins enable apify`. To move to a newer listed version
later, run `hermes plugins update apify`.

### From PyPI

Use this if you installed Hermes itself with pip. Install the plugin into the same Python
environment:

    pip install apify-hermes-agent-plugin
    hermes plugins enable apify

### Set your Apify token

Then run:

    hermes apify-setup

This prompts for your `APIFY_API_TOKEN` (get one at https://console.apify.com/settings/integrations?utm_source=hermes-agent&utm_medium=integrations),
saves it, and enables the Apify Actors toolset for the CLI. Pass `--token <token>` to skip the
prompt.

### Troubleshooting: `hermes plugins enable apify` fails after a pip install

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

The plugin also ships an `actor-routing` skill (`apify:actor-routing`) with curated Actor
picks for common scraping tasks. The agent loads it before searching Apify Store.

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

    pip install -r requirements-dev.txt
    pytest

Keep dev tooling in `requirements-dev.txt`, not in `pyproject.toml`'s optional dependencies or
dependency groups. Hermes resolves every extra and group of an installed plugin against its
own pinned dev dependencies, so a conflicting pin stops the plugin from being enabled from the
catalog. See `AGENTS.md`'s [Packaging](AGENTS.md#packaging).

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

Before releasing, set `version` in `plugin.yaml` to the version you're about to ship. The
pipeline only bumps `pyproject.toml`, and the Hermes catalog requires the two to match.

### Updating the Hermes catalog listing

A release here updates PyPI only. The catalog entry (`plugin-catalog/apify.yaml` in
[NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)) pins an exact
commit, so each new version needs a re-pin PR there, which a Hermes maintainer reviews:

1. Pin the release commit: the `chore(release)` commit that `publish` pushes, i.e.
   `git rev-parse vX.Y.Z^{commit}`.
2. Update `sha` and `version`, and re-pin the `image:` banner URL to the same commit.
3. Open the PR from a **personal** fork, so maintainers can edit it, with a commit email
   that's mapped in their `contributors/emails/`.
4. Before opening it, check that the plugin installs **and enables** on current Hermes
   `main`. `hermes plugins validate` alone isn't enough.

The full procedure, entry fields, PR description format and verification steps are in
`AGENTS.md`'s [Hermes plugin catalog](AGENTS.md#hermes-plugin-catalog-marketplace-listing).
