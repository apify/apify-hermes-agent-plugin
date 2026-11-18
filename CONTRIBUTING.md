# Contributing

## Environment

Python 3.11–3.13. Clone the repo, then install it in editable mode with the dev tooling:

```bash
pip install -r requirements-dev.txt
```

Keep dev tooling in `requirements-dev.txt`, not in `pyproject.toml`'s optional dependencies or
dependency groups. A conflicting pin there stops the plugin from being enabled from the catalog:
Hermes resolves every extra and group of an installed plugin against its own pinned dev dependencies.
See [Packaging](AGENTS.md#packaging) in `AGENTS.md`.

## Running checks

```bash
pytest                                      # full test suite
pytest tests/test_tools.py::test_name -v    # a single test

ruff check .            # lint
ruff check --fix .      # lint, autofixing
ruff format --check .   # format check (what CI runs)
ruff format .           # format, autofixing

ty check src/ tests/    # type check
```

CI (`.github/workflows/test.yml`) runs lint, type-check, and the test matrix (Python
3.11/3.12/3.13) on every push and pull request.

## Building the package

```bash
python -m build       # builds sdist + wheel into dist/
twine check dist/*    # validates the built artifacts
```

## Commit messages

Commit messages and PR titles follow [Conventional Commits](https://www.conventionalcommits.org/)
(`feat:`, `fix:`, `chore:`, etc.). The release pipeline uses them to infer version bumps and
generate the changelog. See [Release process](AGENTS.md#release-process) in `AGENTS.md` for which
commit types trigger a release.

## Releasing

Releases are cut from the **Actions** tab, not by creating a GitHub Release by hand: open the
`publish` workflow, select **Run workflow**, and choose a release type (`auto`, `patch`, `minor`,
`major`, or `custom`). The pipeline bumps the version, updates `CHANGELOG.md`, creates the GitHub
Release, and publishes to PyPI.

`auto` infers the version bump from Conventional Commits since the last tag. It only works when at
least one of those commits qualifies (`feat:`, `fix:`, etc.). If you're not sure, pick `patch`,
`minor`, or `major` explicitly. Those always compute correctly regardless of commit history.

Before releasing, set `version` in `plugin.yaml` to the version you're about to ship. The pipeline
only bumps `pyproject.toml`, and the Hermes catalog requires the two to match.

## Updating the Hermes catalog listing

A release here updates PyPI only. Each new version also needs a re-pin PR in
[NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent), reviewed by a Hermes
maintainer, because the catalog entry (`plugin-catalog/apify.yaml`) pins an exact commit. The
marketplace page shows that entry's `description` and renders `README.md` from the pinned commit.
README and description changes go live only after a re-pin.

1. Pin the release commit: the `chore(release)` commit that `publish` pushes
   (`git rev-parse vX.Y.Z^{commit}`).
2. Update `sha` and `version`, and re-pin the `image:` banner URL to the same commit.
3. Open the PR from a **personal** fork, where maintainers can push edits. Use a commit email that's
   mapped in their `contributors/emails/`.
4. Before opening it, check that the plugin installs **and enables** on current Hermes `main`.
   `hermes plugins validate` alone isn't enough.

The full procedure, entry fields, PR description format, and verification steps are in
[Hermes plugin catalog](AGENTS.md#hermes-plugin-catalog-marketplace-listing) in `AGENTS.md`.
