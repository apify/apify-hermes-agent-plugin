# AGENTS.md

Guidance for AI coding agents working in this repository.

## What this is

A [Hermes Agent](https://hermes-agent.nousresearch.com) plugin that exposes Apify Actor
execution as three tools (`apify_discover`, `apify_start`, `apify_collect`), an `apify`
web search/extract provider (`web_search.py`), an `actor-routing` skill
(`skills/actor-routing/SKILL.md`), and a `hermes apify-setup` CLI command.

It ships through **two channels**, and both must keep working:

1. **PyPI**, as `apify-hermes-agent-plugin`. It's loaded via the `hermes_agent.plugins`
   entry point (see below).
2. **The Hermes plugin catalog ("marketplace")**, via `hermes plugins install apify`. Hermes
   git-clones this repo at a pinned commit and imports the root `__init__.py` shim. See
   [Hermes plugin catalog](#hermes-plugin-catalog-marketplace-listing).

## Commands

```bash
pip install -r requirements-dev.txt   # editable install with dev deps
pytest                          # run all tests
pytest tests/test_tools.py::test_name -v   # run a single test
ruff check .                    # lint
ruff check --fix .              # lint, autofixing
ruff format --check .           # format check (what CI runs)
ruff format .                   # format, autofixing
ty check src/ tests/            # type check
python -m build                 # build sdist + wheel into dist/
twine check dist/*              # validate built artifacts before upload
```

CI (`.github/workflows/test.yml`) runs lint + type-check + the test matrix (Python
3.11/3.12/3.13) on every push/PR, and is also callable as a reusable workflow
(`workflow_call`) so `publish.yml` can gate a release on it. `.github/workflows/publish.yml`
is a manually-triggered (`workflow_dispatch`) release pipeline that bumps the version,
regenerates the changelog, creates the GitHub Release, and publishes to PyPI via OIDC
trusted publishing (no stored token), all in one run — see [Release process](#release-process)
below.

## Architecture

### Plugin entry point — the one sharp edge

`register(ctx)` in `src/apify_hermes_agent_plugin/__init__.py` is called once by
hermes-agent's plugin loader. It registers the three tools and the `apify-setup` CLI
command via `ctx.register_tool(...)` / `ctx.register_cli_command(...)`.

The `pyproject.toml` entry point must point at the **bare module**
(`apify = "apify_hermes_agent_plugin"`), never `"apify_hermes_agent_plugin:register"`.
hermes-agent's loader (`hermes_cli/plugins.py::_load_entrypoint_module`) calls `ep.load()`
and then `getattr(result, "register")`, expecting a module back. Per
`importlib.metadata` semantics, a `module:attr` entry point makes `ep.load()` return the
attribute itself (the function), so `getattr(register_fn, "register")` finds nothing and
the plugin silently fails to load with "no register() function". This diverges from
hermes-agent's own plugin docs example — see the comment above the entry point in
`pyproject.toml`.

### Request flow

1. `tools.py` defines the three handlers (`_discover_handler`, `_start_handler`,
   `_collect_handler`), their JSON schemas (`_DISCOVER_SCHEMA` etc.), and thin
   string-returning wrappers (`discover_handler_str`, `start_handler_str`,
   `collect_handler_str`) that hermes-agent's tool dispatcher actually calls — the
   dispatcher expects `str` (JSON-encoded) returns, not native dicts.
   `collect_handler_str` is async (it polls run status via `asyncio.gather`); the other
   two are sync.
2. `client.py`'s `get_apify_client()` returns a cached `ApifyClient` (module-level
   singleton, rebuilt only if `APIFY_API_TOKEN` changes) that attaches an
   `x-apify-integration-platform: hermes-agent` header for traffic attribution.
   `check_apify_api_key()` is the `check_fn` hermes-agent calls before every tool
   invocation to decide whether the tool is available.
3. `_attr(obj, key)` in `tools.py` is a compatibility shim: `apify-client` 3.x returns
   Pydantic models for some calls and plain dicts for others, and the Pydantic models
   expose only snake_case attributes even though the underlying JSON is camelCase (e.g.
   `Build.actor_definition`, not `.actorDefinition` — camelCase exists only as a
   serialization alias). Always go through `_attr()` when reading SDK response objects;
   direct `.attr` or `["key"]` access will silently return defaults on a mismatch.
4. Interrupt checks (`from tools.interrupt import is_interrupted`) and the hermes_cli
   internals used by `cli.py`'s `_enable_apify_toolset_for_cli` are imported *inside* the
   functions that use them, not at module top level. This is deliberate: it lets tests
   `monkeypatch.setattr("tools.interrupt.is_interrupted", ...)` after import and have it
   take effect. A top-level import binds the original function at import time, and
   monkeypatching the source module afterward wouldn't reach it.

### `hermes apify-setup` (`cli.py`)

Prompts for/accepts `--token`, saves it via `hermes_cli.config.save_env_value`, then
best-effort auto-enables the `apify` toolset for the `cli` platform by reusing
hermes-agent's own config read/merge/save logic (`hermes_cli.tools_config`) rather than
reimplementing it — those functions reconcile `agent.disabled_toolsets`, preserve MCP
server entries, etc. Failure there is treated as non-fatal (prints a manual fallback
instruction), since these are private hermes_cli internals with no stability guarantee.

## Testing conventions

- `asyncio_mode = "strict"` (pytest-asyncio) — async tests need an explicit
  `@pytest.mark.asyncio`.
- Tests monkeypatch `tools.interrupt.is_interrupted` and `hermes_cli` internals directly
  rather than mocking at a higher layer — see the interrupt-fixture pattern in
  `tests/test_tools.py`.
- Token-shaped strings in tests (`tok_123`, `abc123`, `tok_from_flag`, ...) are
  intentional fake placeholders, not real credentials — this is why `ruff`'s `S105`/`S106`
  are ignored for `tests/*`.

## Packaging

- `src/` layout; `[tool.setuptools.packages.find]` restricts discovery to `src/`.
- `MANIFEST.in` controls sdist-specific inclusion/exclusion (`include CHANGELOG.md`,
  `prune tests`). setuptools' sdist defaults don't auto-include arbitrary root-level docs
  and *do* auto-include `tests/` — `MANIFEST.in` is where that gets corrected, not
  `[tool.setuptools]`.
- `version` in `pyproject.toml` is a static string, but never bump it by hand — the release
  pipeline's `changelog_update` job bumps it for you. See [Release process](#release-process).
- `version` in `plugin.yaml` (what `hermes plugins list` shows for git/catalog installs) is
  **not** bumped by the pipeline — set it by hand to the version you're about to release.
- Dev tooling lives in `requirements-dev.txt`, never in `pyproject.toml`'s
  `[project.optional-dependencies]` or `[dependency-groups]`. Hermes' plugin manager locks an
  installed plugin into its own uv workspace *including every extra and group*, so a dev pin
  that disagrees with Hermes' exact dev pins (e.g. `pytest==9.0.2` vs `9.1.1`) gets the plugin
  refused at enable time ("not admitted"). `hermes plugins validate --install-deps` does not
  catch this — it only resolves runtime requirements.

## Release process

Releases are cut by manually dispatching the `publish` workflow (Actions tab → `publish` →
**Run workflow**), not by creating a GitHub Release directly. Pick a **Release type**:

- `auto` (the pre-selected default) — `git-cliff` infers patch/minor/major from Conventional
  Commits since the last tag.
- `patch` / `minor` / `major` — force that specific bump regardless of what commits exist.
- `custom` — supply an exact version via `custom_version`.

`publish.yml` runs five jobs in sequence: `checks` (re-runs `test.yml` as a gate) →
`release_prepare` (computes the version/changelog via `apify/actions/git-cliff-release`) →
`changelog_update` (bumps `pyproject.toml` and pushes the changelog to `main`, via Apify's
shared `python_bump_and_update_changelog.yaml` workflow) → `github_release` + `publish`
(both build off that pushed commit; `publish` builds the sdist/wheel, smoke-tests that
`apify_hermes_agent_plugin.register` imports and is callable, then uploads to PyPI).

**`auto` gotcha — verified against this repo's real tag history:** if there are zero commits
since the last tag that count as release-worthy (see below), `git-cliff --bumped-version`
silently falls back to its config's `[bump].initial_tag` (`v0.1.0`) instead of erroring, and
`release_prepare`'s own "nothing to release" guard doesn't catch this — it compares tag
*strings*, not version ordering, so `v0.1.1` (current) vs. the fallback `v0.1.0` looks like a
legitimate change to it. Left unchecked, this ships a version *older* than the one already on
PyPI: `changelog_update` pushes a downgrade commit to `main`, `github_release` creates a
bogus release, and only `publish` fails, at the very last step (PyPI rejects re-uploading a
used version) — by which point two artifacts need manual cleanup. Before dispatching with
`auto`, confirm at least one commit since the last tag is release-worthy, or just dispatch
with `patch`/`minor`/`major` instead — those always compute correctly regardless of commit
history.

**Which commits count:** the version/changelog logic lives in `apify/actions/git-cliff-release`'s
own bundled `cliff.toml` (not a file in this repo — there is nothing to configure here).
It only treats `feat`/`fix`/`perf`/`revert`, breaking-marked (`!:`) `docs`/`refactor`/
`style`/`test`/`build`/`chore`/`ci`, and commits whose body mentions "security" as
release-worthy. A plain `chore:`/`ci:`/`docs:`/etc. commit (no `!`) is silently skipped —
it neither appears in the changelog nor counts toward an `auto` bump. On `0.x` versions
that `cliff.toml` sets `features_always_bump_minor = false`, so even `feat:` commits only
bump the **patch** number. Dispatching `patch` gives the same version as `auto` would.

**Requires** the `APIFY_SERVICE_ACCOUNT_GITHUB_TOKEN` org secret (received via `secrets:
inherit`) — `changelog_update`'s push to `main` authenticates as that service account, not
the job's default `GITHUB_TOKEN`.

## Hermes plugin catalog (marketplace listing)

The listing is one file, `plugin-catalog/apify.yaml`, in
[NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent). It pins an exact
commit of this repo. Releasing here does **not** update it: every SHA bump is a new upstream
PR that a human reviews (catalog rule 4). Rules, schema and CI live in that repo's
`plugin-catalog/README.md` and `.github/workflows/plugin-catalog-ci.yml`. Read them at
current `main`, because they change often.

History: first listed via #114254 → #115946 (pin `07b21464`, 0.1.3). Re-pinned to v0.1.5
(`a3a7af0c`) via #133341.

### How Hermes installs it (as of Hermes `main`, 2026-10)

- `hermes plugins install apify` clones this repo at the pinned SHA into
  `$HERMES_HOME/plugins/apify`. Its package manager then puts the plugin into **Hermes' own
  uv workspace**, and enabling it re-locks that workspace.
- That lock resolves **every extra and dependency group** the plugin's `pyproject.toml`
  declares, together with Hermes' exact-pinned dev group. A conflicting pin means the plugin
  is "not admitted": it installs, but enabling it is refused. That's why dev tooling lives in
  `requirements-dev.txt` (see [Packaging](#packaging)).
- The `hermes-agent` requirement is stripped on purpose ("the application checkout supplies
  Hermes itself"). Current Hermes reports its own version as `0.0.0`, because the real version
  comes from an install stamp. So `hermes-agent>=0.15.1` is a no-op for catalog installs, but
  a raw `pip install` into a current Hermes environment would pull the stale PyPI
  `hermes-agent==0.19.0` (PyPI stopped at 0.19.0).
- **Who runs this code:** the official `install.sh` clones Hermes `main`, and `hermes update`
  defaults to `--branch main`. Tagged releases (v0.21.4/v0.21.5) don't have the
  package-manager admission step yet. So test against Hermes **`main`**, not the latest tag:
  that's what new users get.
- By-name installs read the **live** catalog JSON
  (`hermes-agent.nousresearch.com/docs/api/plugin-catalog.json`, built by
  `website/scripts/extract-plugins.py`), not the files in a Hermes checkout. A merged re-pin
  reaches users only after the docs site redeploys.

### Re-pin procedure

1. Merge the change, then dispatch `publish` with **`patch`**. Before releasing, make sure
   `plugin.yaml`'s `version` equals the version about to ship, because catalog rule 14 says
   "version matches the pinned code".
2. Pin the **release commit**, the `chore(release)` commit that `changelog_update` pushes
   (`git rev-parse vX.Y.Z^{commit}`). Don't pin the feature/fix commit, whose
   `pyproject.toml` still has the old version.
3. Edit only `plugin-catalog/apify.yaml`:
   - `sha` → the release commit (full 40 hex characters).
   - `version: "X.Y.Z"` (quoted).
   - `image:` → `https://raw.githubusercontent.com/apify/apify-hermes-agent-plugin/<sha>/assets/banner.png`.
     That's the 2000×1000 (2:1) banner, which must be on a GitHub host, pinned to the same SHA.
     It only appears if `image:` is set; the docs site uses it for the card, the
     `/docs/plugins/apify` hero image and `og:image`.
   - `title: Apify`: the display name in Hermes' own catalog list. The docs site ignores it.
   - Under `capabilities`, only `provides_tools`, `provides_hooks`, `provides_middleware` and
     `requires_env` are recognised. Don't add the web provider or the skill there; unknown
     keys produce a warning.
4. Open the PR **from a personal fork** (`<login>/hermes-agent`), branched from
   `upstream/main`. Leave "Allow edits by maintainers" on.
   - GitHub never allows maintainer edits on PRs from **organization-owned** forks
     (`apify/hermes-agent`), and Hermes maintainers often fix catalog PRs themselves. With
     #114254 they couldn't push, so they re-opened it as their own PR. Org forks are
     accepted otherwise, but every requested change then has to be pushed by us.
   - **Commit email must be mapped**, or the `Contributor Attribution Check` fails. GitHub
     noreply emails resolve automatically; otherwise add `contributors/emails/<email>`
     containing the GitHub login, in the same PR (catalog CI allows changes under that path).
   - Rule 5: the submitter must be the repo owner or a major contributor. Say you're
     submitting for Apify as a maintainer of this repo.
5. Title convention for re-pins: `chore(plugin-catalog): repin apify to <sha8> (X.Y.Z)`.
   Description: use the upstream PR template, and include:
   - old → new SHA;
   - why the bump is needed;
   - what changed in this repo between the two pins (reviewers read that commit range,
     rule 4);
   - a **Disclosure** section (rule 13: network calls to `api.apify.com` /
     `web-fetch.apify.actor` with the user's token, Actor runs billed to their Apify account,
     `apify-setup` writing `$HERMES_HOME/.env` and enabling the toolset, the
     `x-apify-integration-platform` header);
   - concrete test steps with results.

   A disclosure line inside the entry's `description` is optional; reviewers may add one.
6. Workflows on fork PRs wait for a maintainer to approve them, so `action_required` with no
   checks running is normal. Re-pins typically merge within about a day; a bot comments
   "Verified at …" first.

Likely reviewer requests we haven't addressed yet:
- Rule 10: bare dependency floors get a request for an upper bound, and `httpx>=0.27` has none.
- Rule 13: the disclosure should also be in the README.

### Verifying a pin before opening the PR

Do these in this order, using a Hermes checkout at upstream `main` and a **fresh, throwaway
`HERMES_HOME`** for each step:

1. `python3 scripts/validate_plugin_catalog.py plugin-catalog/` in the Hermes checkout, with
   the edited entry.
2. Clone this repo, `git checkout --detach <sha>`, then
   `hermes plugins validate --install-deps <clone>`. This is what catalog CI runs.
   - It **only resolves runtime requirements**, so it passed even when the `[dev]` extra made
     the plugin impossible to enable. Don't treat it as proof of installability.
3. Install and enable for real:
   `hermes plugins install apify/apify-hermes-agent-plugin --ref <sha> --enable`, answering `y`
   to the dependency prompt.
   - Check that `hermes plugins list` shows `apify │ enabled │ X.Y.Z` and that the next
     `hermes` run resyncs cleanly.
   - In a non-interactive shell the dependency prompt is skipped and the plugin stays
     disabled. Hermes supports `--yes-deps` internally but doesn't expose it on the command
     line yet; use a pseudo-terminal (`script`) to answer.
4. `hermes apify-setup --token …`, then exercise the tools, the web provider
   (`search()`/`extract()`) and the skill from inside Hermes' Python environment.
5. `curl` the pinned `image:` URL and expect HTTP 200 `image/png`.

Gotchas from doing this:
- `validate --install-deps` leaves a staged copy of the validated directory in that
  `HERMES_HOME`. A later enable in the same home fails with
  `Distribution not found at …/plugin-sources/<dir>-…`. That comes from the test setup, not
  the plugin: use a separate home.
- A Hermes **dev** checkout's `scripts/run-in-hermes-env` also syncs the test environment.
  Users' runtime installs don't, so don't mistake test-environment failures for user-facing
  ones (the `[dev]` failure did reproduce with `setup-hermes.sh --runtime-only`).
- Upstream Hermes can't be `pip install`ed from source any more (wheel builds are refused). Use
  `install.sh` or `setup-hermes.sh`.
- macOS has no `timeout` command, so drop the `timeout 600` wrappers that catalog CI uses.
- An older global `hermes` (e.g. v0.21.4) has no admission step. Running it against a scratch
  `HERMES_HOME` gives misleadingly positive results.

## Ruff configuration — rules turned off for real design reasons

Full rationale lives in `pyproject.toml`'s `[tool.ruff.lint] ignore` comments. The ones
that reflect deliberate design rather than convenience:

- `BLE001` (no blind `except`): every tool handler must turn arbitrary SDK/network
  failures into a JSON error object for the calling LLM — a raised exception would crash
  the tool call instead of reporting it.
- `PLC0415` (imports not at top level): the interrupt-check / hermes_cli-internals imports
  described above are deliberately scoped inside functions for monkeypatchability.
- `PLW0603` (`global`): `client.py`'s two module-level variables are a deliberate
  single-client memoization cache.
