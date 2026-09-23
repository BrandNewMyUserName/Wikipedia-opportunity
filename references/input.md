# Input and commands

Run `scripts/wiki_interest.py --help` or `<command> --help`. JSON stdout is intentionally compact; large data stays in files. Exit 2 means actionable input/network failure. All paths below are relative to this skill folder.

`discover`: Wikidata search, six candidates; `--search-language` controls the query language.
`plan`: QIDs → current sitelinks → config + `.mapping.json` evidence. A missing language/QID stops the plan, preventing unequal baskets. Review concept meaning independently: Wikidata identity establishes an entity link, not identical reader intent or article quality.
`run`: validated config → snapshot + analysis + report + provenance. Existing nonempty output directories are rejected. An interrupted run may leave a partial folder; retain it for diagnosis and choose another output folder. Monthly network cache survives failures.
`reanalyze`: the original snapshot plus optional criteria JSON → new report without network. Use `run` for changed dates or proxies.

## Config

```json
{
  "schema_version": 1,
  "question": "Should we research an astronomy course in Ukrainian?",
  "start": "2024-09-01",
  "end": "2026-08-31",
  "series": [{
    "id": "uk",
    "label": "Astronomy / Ukrainian",
    "language": "uk",
    "articles": [{"qid": "Q333", "title": "Астрономія"}]
  }],
  "criteria": {
    "min_baseline_views": 1000,
    "min_growth_pct": 10,
    "min_share_growth_pct": 0,
    "min_robust_growth_pct": 0,
    "min_positive_months": 8,
    "max_top7_share": 0.15
  }
}
```

Only complete months, 24–60 months, data since July 2015. At most six series and six articles per series. Long questions/baskets can exceed a one-page PDF; shorten labels/question or split reports. The generator errors rather than clipping content or silently adding pages.

To compare several topics in one language, give series unique IDs and different article lists. To compare audiences for the same topic, use the same QID basket for each language. Different baskets remain individually analyzable, but automatic cross-series ranking is withheld. Summed baskets are pageview volume, not distinct visitors.

For learning English, first distinguish studying English from general attention to the English language. Search for education/learning concepts, inspect available equivalents, then disclose which part of intent the basket captures. Never substitute a broad language article silently when a learning-specific article is missing.

Criteria JSON for `reanalyze` contains just changed fields, e.g. `{"min_growth_pct":20}`. No opaque scoring weights. Thresholds are hypotheses, not learned or calibrated probabilities.

## Output contract

- `snapshot.json`: exact dates, config, validated pages/QIDs/URLs, daily observations and edition totals.
- `analysis.json`: annual volumes, raw/share growth, peak-excluded growth, median month YoY, positive-month count, coverage, top seven days, flags and research ordering.
- `monthly.csv`: one row per series/month; empty measurements mean missing, numeric zero means observed zero.
- `trend.png`: monthly raw volume and edition-normalized interest; gaps stay visible.
- `report.pdf`: one-page brief, Unicode font embedded; fixed English analytical labels.
- `report.md`: compact readable report with source article links.
- `provenance.json`: exact request URLs, retrieval UTC timestamps, HTTP status, response hashes and code version. Schema 2 separates `source_acquisition` (cache hits and HTTP requests of the original data collection) from `current_run` (operation, cache hits and HTTP requests of this report run). A `reanalyze` report retains original source timestamps and acquisition counters, while its `current_run` counters are zero. Older schema 1 reports with top-level counters remain accepted as reanalysis inputs and are converted to schema 2 on output.

Cache: SHA-256 of the actual request URL, response payload hash validated on reads, atomic file replacement. Contiguous missing months are fetched in one range request; monthly indexes reference that unmodified raw response, so overlapping studies reuse prior months and provenance retains the real URL. Metadata TTL: one day; source ranges ending within 60 days: one day; older ranges retained until explicit refresh. Offline mode allows older cache records and preserves their timestamps. 404 observations become missing data, other nonretryable HTTP errors stop the run. Up to four attempts on transient network/429/5xx errors. Retry-After numeric values are respected up to 60 seconds; longer pauses return an error. Requests are serial and bounded; do not launch many concurrent runs against Wikimedia.
