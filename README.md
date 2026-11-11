# Apify for Hermes Agent

**Scrape websites and get structured data in [Hermes Agent](https://hermes-agent.nousresearch.com).**
Ask in plain language, and your agent finds and runs the right [Apify](https://apify.com) Actor from
Apify Store. The plugin can also power Hermes' built-in web search and page extraction.

## Why use Apify with Hermes Agent?

- **Get structured data, not raw pages.** Actors return clean JSON fields like prices, ratings,
  follower counts, and contact details, ready for the agent to analyze.
- **Skip the scraper work.** Apify Store has thousands of ready-to-run Actors, including ones for
  Instagram, Google Maps, and LinkedIn. Apify runs them in the cloud and manages hosting and proxies.
- **Start up to 10 Actor runs in one call.** The agent collects results as the runs finish.
- **Find an Actor faster.** A bundled skill recommends Actors for common tasks.

## Use cases

- **Lead generation:** "Find 20 dentists in Chicago on Google Maps and pull their websites and any
  listed emails."
- **Instagram trends:** "Find up to 20 recent Instagram posts tagged #skincare and summarize the
  products they mention."
- **TikTok trends:** "Find up to 20 popular TikTok videos tagged #booktok and list their view counts."
- **Product prices:** "Find up to 20 standing desks on Amazon US and list their prices and product
  links."
- **Competitor ads:** "Get Nike's active ads from the Meta Ad Library with their ad copy and start
  dates."
- **Video research:** "Get transcripts for these 10 YouTube videos so I can index them for search."
- **Website content for RAG:** "Crawl docs.example.com and give me clean Markdown I can index."

For anything else, the agent searches Apify Store.

## How much does it cost?

The plugin is free to install. Actor runs, web searches, and page fetches count toward your
[Apify plan](https://apify.com/pricing), the same as runs you start in Apify Console. The Free plan
includes $5 of monthly usage, and no credit card is required. Each Actor's pricing is on its Apify Store
page. Web searches and page fetches use pay-per-event pricing: see
[Web Search](https://apify.com/apify/web-search/pricing) and
[Web Fetch](https://apify.com/apify/web-fetch/pricing) pricing.

## Getting started

1. Install the plugin from the Hermes plugin catalog:

    ```bash
    hermes plugins install apify --enable
    ```

    When asked whether to prepare the plugin's Python dependencies (`apify-client`, `httpx`), answer
    `y`.

2. Sign up at [apify.com](https://apify.com), copy your API token from
   [Apify Console](https://console.apify.com/settings/integrations?utm_source=hermes-agent&utm_medium=integrations),
   and run:

    ```bash
    hermes apify-setup
    ```

    The command saves the token as `APIFY_API_TOKEN` in `~/.hermes/.env` and enables the Apify Actors
    toolset for the CLI. To skip the prompt, run `hermes apify-setup --token <your-token>`.

3. Ask Hermes for data:

    ```text
    Find 20 coffee shops in Austin on Google Maps and list their websites and phone numbers.
    ```

    Hermes runs a Google Maps Actor and replies with the list.

To update to a newer listed version later, run `hermes plugins update apify`.

Paths in this README use the default Hermes home on macOS and Linux, `~/.hermes`. If your Hermes home
is elsewhere, like a folder set with `HERMES_HOME`, the files are there instead.

### Install from PyPI

If you installed Hermes itself with pip, install the plugin from
[PyPI](https://pypi.org/project/apify-hermes-agent-plugin/) into the same Python environment instead
of step 1:

```bash
pip install apify-hermes-agent-plugin
hermes plugins enable apify
```

## Tools

| Tool | What it does |
| --- | --- |
| `apify_discover` | Searches Apify Store by keyword, or returns an Actor's input schema and README by `actor_id`. |
| `apify_start` | Starts up to 10 Actor runs per call and returns run references without waiting for them to finish. |
| `apify_collect` | Checks run status and returns each successful run's dataset items as JSON. A failed, aborted, or timed-out run returns an error. |

`apify_collect` returns large results in pages, and the agent fetches the next page with `offset`. When
several runs share a response, a run that doesn't fit is collected on its own. An item too large for
one response has its long text fields shortened.

The `apify:actor-routing` skill lists recommended Actors for Instagram, Facebook, TikTok, YouTube, X,
LinkedIn, Google Maps, Google Search, reviews, real estate, SEO, website crawling, and contact
enrichment. The agent loads it before searching Apify Store.

## Web search and fetch

The plugin registers `apify` as a backend for Hermes' web search and web extract tools. Both use the
API token you set up with `hermes apify-setup`:

- **Search** runs the [Web Search](https://apify.com/apify/web-search) Actor and returns Google organic
  results (title, URL, and snippet). Each query returns up to 10 results from one results page.
- **Extract** runs the [Web Fetch](https://apify.com/apify/web-fetch) Actor and returns full page
  content as Markdown or HTML.

To turn them on, set the backends in `~/.hermes/config.yaml`:

```yaml
web:
  search_backend: apify
  extract_backend: apify
```

Or select `apify` interactively with `hermes tools`.

Searches run from the US in English by default. To change that for every search, set these optional
variables in `~/.hermes/.env`:

```bash
APIFY_WEB_SEARCH_COUNTRY=DE   # ISO 3166-1 alpha-2 country code
APIFY_WEB_SEARCH_LANGUAGE=de  # ISO 639-1 language code
```

## Troubleshooting

### Plugin installed but disabled?

If you declined the dependency prompt, or ran `hermes plugins install` in a non-interactive shell,
`hermes plugins list` shows `apify` as disabled. Enable it:

```bash
hermes plugins enable apify
```

### Enable fails after a pip install?

If `hermes plugins enable apify` prints `Plugin 'apify' is not installed or bundled.`, your
`hermes-agent` is older than `0.18.1`, which fixed plugin discovery for pip installs. Check your
version and upgrade:

```bash
hermes --version
pip install --upgrade hermes-agent
```

If you can't upgrade, add `apify` to the `plugins.enabled` list in `~/.hermes/config.yaml`, then run
`hermes apify-setup`:

```yaml
plugins:
  enabled:
    - apify
```

### Toolset not enabled after setup?

If `hermes apify-setup` saves the token but can't enable the toolset, run `hermes tools` and turn on
**apify**.

### Web search rejects the country or language?

Fix or unset `APIFY_WEB_SEARCH_COUNTRY` or `APIFY_WEB_SEARCH_LANGUAGE` in `~/.hermes/.env`. Both take a
two-letter code, like `DE` or `de`.

### Need support or a custom feature?

Open an issue on [GitHub](https://github.com/apify/apify-hermes-agent-plugin/issues) with the command
or prompt you ran and the error. Remove your API token first. If Apify Store doesn't have the scraper
you need, Apify can [build a custom solution](https://apify.com/custom-solutions) for you.

## FAQ

### What's an Actor?

An Actor is a serverless cloud program on the Apify platform. It takes JSON input, does one job like
scraping a website, and saves its results to a dataset. Apify Store lists Actors built by Apify and by
independent developers.

### What does the plugin send to Apify?

The plugin sends your API token and requests to `api.apify.com`, `web-search.apify.actor`, and
`web-fetch.apify.actor`. Each request carries an `x-apify-integration-platform: hermes-agent` header so
Apify can attribute the traffic. `hermes apify-setup` writes your token to the `.env` file in your
Hermes home and enables the `apify` toolset in your Hermes config.

### Can scraped content steer my agent?

Actor results come from third-party websites. `apify_collect` tells the agent to treat them as data,
never as instructions.

### Is web scraping legal?

Scraping publicly available, non-personal data is generally legal. What you do with the data matters,
and some content is protected by copyright or a site's terms of service. If you're unsure, seek legal
advice. See [Is web scraping legal?](https://blog.apify.com/is-web-scraping-legal/) on the Apify blog.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, releases, and updating the Hermes catalog
listing.

## License

[MIT](LICENSE)
