# Contributing

## Environment

Python 3.11–3.13. Clone the repo, then install in editable mode with the dev extras:

```bash
pip install -e ".[dev]"
```

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
twine check dist/*     # validates the built artifacts
```

## Commit messages

Commit messages and PR titles follow [Conventional Commits](https://www.conventionalcommits.org/)
(`feat:`, `fix:`, `chore:`, etc.) — the release pipeline uses them to infer version bumps and
generate the changelog. See [AGENTS.md](AGENTS.md) for the full architecture and release-process
notes, including which commit types actually trigger a release.

## Releasing

See the [Releasing](README.md#releasing) section in the README.
