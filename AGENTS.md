# AGENTS.md

Guidance for AI coding agents working in this repository.

## What this is

A [Hermes Agent](https://hermes-agent.nousresearch.com) plugin that exposes Apify Actor
execution as three tools (`apify_discover`, `apify_start`, `apify_collect`) plus a
`hermes apify-setup` CLI command. Published to PyPI as `apify-hermes-agent-plugin`.

## Commands

```bash
pip install -e ".[dev]"        # editable install with dev deps
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
it neither appears in the changelog nor counts toward an `auto` bump.

**Requires** the `APIFY_SERVICE_ACCOUNT_GITHUB_TOKEN` org secret (received via `secrets:
inherit`) — `changelog_update`'s push to `main` authenticates as that service account, not
the job's default `GITHUB_TOKEN`.

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
