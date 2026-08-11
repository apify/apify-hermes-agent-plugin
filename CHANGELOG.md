# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.0] - 2026-08-11

### Added

- Initial release.
- `apify_discover` tool — search the Apify Store by keyword, or fetch an Actor's input schema and README by `actor_id`.
- `apify_start` tool — fire-and-forget batch Actor runs (up to 10 per call).
- `apify_collect` tool — poll run statuses and return completed dataset results.
- `hermes apify-setup` CLI command — prompt for (or accept via `--token`) the `APIFY_API_TOKEN` and enable the Apify toolset.
