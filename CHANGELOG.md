# Changelog

All notable changes to this project will be documented in this file.

## [0.1.2](https://github.com/apify/apify-hermes-agent-plugin/releases/tag/v0.1.2) (2026-09-17)

### 🚀 Features

- Introduce apify house CI  ([#5](https://github.com/apify/apify-hermes-agent-plugin/pull/5)) ([3812d43](https://github.com/apify/apify-hermes-agent-plugin/commit/3812d437b254a9df1c7ba81641101140b8e7e7c8)) by [@JanHranicky](https://github.com/JanHranicky)
- Plugin marketplace dependencies ([#6](https://github.com/apify/apify-hermes-agent-plugin/pull/6)) ([bd5862e](https://github.com/apify/apify-hermes-agent-plugin/commit/bd5862e669ef74ef78def57d6396fca10d2c2cff)) by [@JanHranicky](https://github.com/JanHranicky)


# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.1] - 2026-08-12

### Changed

- README: added a troubleshooting section for `hermes plugins enable apify` failing with
  "not installed or bundled" on `hermes-agent` versions before `0.18.1`.

## [0.1.0] - 2026-08-11

### Added

- Initial release.
- `apify_discover` tool — search the Apify Store by keyword, or fetch an Actor's input schema and README by `actor_id`.
- `apify_start` tool — fire-and-forget batch Actor runs (up to 10 per call).
- `apify_collect` tool — poll run statuses and return completed dataset results.
- `hermes apify-setup` CLI command — prompt for (or accept via `--token`) the `APIFY_API_TOKEN` and enable the Apify toolset.
