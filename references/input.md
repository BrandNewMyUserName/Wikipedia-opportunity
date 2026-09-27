# Input and commands

Run `scripts/wiki_interest.py --help` or `<command> --help`. JSON stdout is intentionally compact; large data stays in files. Exit 2 means actionable input/network failure. All paths below are relative to this skill folder.

`discover`: Wikidata search, six candidates; `--search-language` controls the query language.
`plan`: QIDs → current sitelinks → config + `.mapping.json` evidence. A missing language/QID stops the plan, preventing unequal baskets. Review concept meaning independently: Wikidata identity establishes an entity link, not identical reader intent or article quality.
`run`: validated config → snapshot + analysis + report + provenance. Existing nonempty output directories are rejected. An interrupted run may leave a partial folder; retain it for diagnosis and choose another output folder. Monthly network cache survives failures.
`reanalyze`: the original snapshot plus optional criteria JSON → new report without network. Use `run` for changed dates or proxies.
`map`: a selected root QID plus 1–11 curated related QIDs → a cross-language topic map. Missing sitelinks are represented explicitly. The same QIDs define each language's conceptual scope; map totals are comparable only when coverage and observations are complete. Use `discover` to find candidate QIDs, then inspect meaning before inclusion.
`verify-spike`: a `topic-map.json` spike plus inspected web evidence JSON → a deterministic evidence gate. It makes no network requests and never proves traffic causation. Each evidence object has `url`, `publisher`, `event_date`, `matched_qids`. Two distinct HTTPS hosts whose metadata matches the spike date and leading QID yield `plausible_not_proven`; otherwise `unverified`. The agent must inspect source content and cite URLs.

## Config

The JSON config contains `schema_version: 1`, the user's `question`, full-month `start` and `end`, a `series` array, and optional `criteria`. Each series needs a unique `id`, a readable `label`, a Wikipedia `language` code and an `articles` array. Each article needs its verified Wikidata `qid` and current Wikipedia `title`. The criteria fields are `min_baseline_views`, `min_growth_pct`, `min_share_growth_pct`, `min_robust_growth_pct`, `min_positive_months`, and `max_top7_share`; omitted fields use code defaults. Use `plan` to create a valid config whenever possible.

Only complete months, 24–60 months, data since July 2015. At most six series and six articles per series. Long questions/baskets can exceed a one-page PDF; shorten labels/question or split reports. The generator errors rather than clipping content or silently adding pages.

To compare several topics in one language, give series unique IDs and different article lists. To compare audiences for the same topic, use the same QID basket for each language. Different baskets remain individually analyzable, but automatic cross-series ranking is withheld. Summed baskets are pageview volume, not distinct visitors.

When the user's intent is narrower than a broad subject, choose matching concepts and disclose which part of that intent the basket captures. Never silently substitute a broader article when the intended concept lacks a sitelink.

Criteria JSON for `reanalyze` contains just changed fields, e.g. `{"min_growth_pct":20}`. No opaque scoring weights. Thresholds are hypotheses, not learned or calibrated probabilities.

## Output contract

- `snapshot.json`: exact dates, config, validated pages/QIDs/URLs, daily observations and edition totals.
- `analysis.json`: annual volumes, raw/share growth, peak-excluded growth, median month YoY, positive-month count, coverage, top seven days, flags and research ordering.
- `monthly.csv`: one row per series/month; empty measurements mean missing, numeric zero means observed zero.
- `trend.png`: monthly raw volume and edition-normalized interest; gaps stay visible.
- `report.pdf`: one-page brief, Unicode font embedded; fixed English analytical labels.
- `report.md`: compact readable report with source article links.
- `provenance.json`: exact request URLs, retrieval UTC timestamps, HTTP status, response hashes and code version. Schema 2 separates `source_acquisition` (cache hits and HTTP requests of the original data collection) from `current_run` (operation, cache hits and HTTP requests of this report run). A `reanalyze` report retains original source timestamps and acquisition counters, while its `current_run` counters are zero. Older schema 1 reports with top-level counters remain accepted as reanalysis inputs and are converted to schema 2 on output.

`map` writes `topic-map-snapshot.json` (QID-aligned pages, daily observations, edition totals), `topic-map.json` (concept and basket trends, coverage and candidate spike dates), `topic-map.md` (readable map), and `topic-map-provenance.json` (request URLs, retrieval times and hashes). It uses the same full-month 24–60-month window. Last-12-month share is a share of the **selected article basket**, not all Wikipedia attention or distinct readers. The map reports raw and edition-normalized year-over-year change, positive matched months and growth after removing the highest latest-year month plus its prior-year match. Candidate spikes use a descriptive rule of at least 100 views and three times the preceding 28-day median; adjacent candidate days are grouped within three days. Search queries are leads only.

Cache: SHA-256 of the actual request URL, response payload hash validated on reads, atomic file replacement. Contiguous missing months are fetched in one range request; monthly indexes reference that unmodified raw response, so overlapping studies reuse prior months and provenance retains the real URL. Metadata TTL: one day; source ranges ending within 60 days: one day; older ranges retained until explicit refresh. Offline mode allows older cache records and preserves their timestamps. 404 observations become missing data, other nonretryable HTTP errors stop the run. Up to four attempts on transient network/429/5xx errors. Retry-After numeric values are respected up to 60 seconds; longer pauses return an error. Requests are serial and bounded; do not launch many concurrent runs against Wikimedia.
