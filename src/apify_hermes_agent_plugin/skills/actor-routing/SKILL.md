---
name: actor-routing
description: >-
  Curated Actor picks for common scraping tasks (Instagram, Facebook, TikTok,
  YouTube, Google Maps, and more). Load before calling apify_discover for a
  task that might already be covered by the table below.
version: 1.0.0
author: Apify
metadata:
  hermes:
    tags: [apify, web-scraping, data-extraction, social-media]
    related_skills: []
---

# Apify Actor Routing

## Core Rule

Actor IDs use tilde format: `username~actor-name` (not slash). All IDs in the
routing table below are already in the correct format.

Prefer `apify`-tier actors. Use `community`-tier only when no `apify` actor
covers the task.

Never call `apify_discover` in query mode for tasks listed in the routing
table below — use the exact actor ID directly with `apify_start`. Still call
`apify_discover({"actor_id": "..."})` first if you haven't run that actor
before, or need its input schema.

## Actor Routing Table

> Seed content — the full catalog is synced automatically from
> [apify-plugins-internal](https://github.com/apify/apify-plugins-internal)
> once its CI is retargeted at this repo (phase 2 of the routing-table
> migration).

### Instagram

| Actor | Tier | Best for |
|-------|------|----------|
| apify~instagram-scraper | apify | all Instagram data |
| apify~instagram-profile-scraper | apify | profiles, followers, bio |

### Facebook

| Actor | Tier | Best for |
|-------|------|----------|
| apify~facebook-posts-scraper | apify | posts, videos, engagement |
| apify~facebook-comments-scraper | apify | comment extraction |

### TikTok

| Actor | Tier | Best for |
|-------|------|----------|
| clockworks~tiktok-scraper | apify | all TikTok data |
| clockworks~tiktok-profile-scraper | apify | profiles, videos |

### YouTube

| Actor | Tier | Best for |
|-------|------|----------|
| streamers~youtube-scraper | apify | videos, metrics |
| streamers~youtube-channel-scraper | apify | channel info |

### Google Maps

| Actor | Tier | Best for |
|-------|------|----------|
| compass~crawler-google-places | apify | business listings |
| compass~google-maps-extractor | apify | detailed business data |
