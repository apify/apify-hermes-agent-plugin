# Changelog

All notable changes to this project will be documented in this file.

## [0.1.5](https://github.com/apify/apify-hermes-agent-plugin/releases/tag/v0.1.5) (2026-10-05)

### 🚀 Features

- Add actor-routing skill for Hermes Agent ([#8](https://github.com/apify/apify-hermes-agent-plugin/pull/8)) ([1ac1fea](https://github.com/apify/apify-hermes-agent-plugin/commit/1ac1feab7ad65ffdd5b14f7bc5ed6d13b709a461)) by [@JanHranicky](https://github.com/JanHranicky)
- Web fetch ([#14](https://github.com/apify/apify-hermes-agent-plugin/pull/14)) ([591992a](https://github.com/apify/apify-hermes-agent-plugin/commit/591992a12fb4e22abd42ee62af4028fccc95aaac)) by [@JanHranicky](https://github.com/JanHranicky)

### 🐛 Bug Fixes

- Move dev deps out of pyproject so Hermes can enable the plugin ([#17](https://github.com/apify/apify-hermes-agent-plugin/pull/17)) ([d1fb3ef](https://github.com/apify/apify-hermes-agent-plugin/commit/d1fb3efec3eb05d3bde747c7df83cd2cce2812bd)) by [@JanHranicky](https://github.com/JanHranicky)


## [0.1.4](https://github.com/apify/apify-hermes-agent-plugin/releases/tag/v0.1.4) (2026-09-18)

### 🐛 Bug Fixes

- Marketplace insall entry point ([#9](https://github.com/apify/apify-hermes-agent-plugin/pull/9)) ([07b2146](https://github.com/apify/apify-hermes-agent-plugin/commit/07b21464f96cedf5af5d78950623711da77d80f7)) by [@JanHranicky](https://github.com/JanHranicky)


## [0.1.3](https://github.com/apify/apify-hermes-agent-plugin/releases/tag/v0.1.3) (2026-09-17)

### 🚀 Features

- Add CONTRIBUTING.md ([#7](https://github.com/apify/apify-hermes-agent-plugin/pull/7)) ([2e920b8](https://github.com/apify/apify-hermes-agent-plugin/commit/2e920b83801fed5686d345a2765d0b99d3cdd07b)) by [@JanHranicky](https://github.com/JanHranicky)


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
