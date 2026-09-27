# Evidence and interpretation

## Comparable units

Wikidata sitelinks identify language equivalents. MediaWiki validates the actual canonical page, QID and disambiguation status before loading traffic. Treat topic discovery as a semantic decision: a similarly named but different entity or a broader concept may not represent the user's intent. Missing editions have unknown suitability, not zero demand.

All calls use `all-access` and `user` (human-classified, not guaranteed exclusively human). Wikipedia editions differ in total audience, content coverage and search exposure. Report both absolute pageviews and pageviews per million edition pageviews. Neither is population penetration. Editions are not countries, baskets are not unique people, and no views-to-revenue conversion is justified.

## Deterministic calculations

The latest 12 completed months are compared with their preceding 12. Longer histories appear in charts; scoring still uses the latest 24 months. Calendar matching limits simple seasonality bias. Leap years can introduce a small volume difference; these are period totals, not per-day adjusted growth.

- Raw growth: `(latest_sum / prior_sum - 1) × 100`.
- Monthly share: `article_month / edition_month × 1,000,000`.
- Annual share growth: growth between the two ratios `article_year / edition_year` (not a mean of monthly ratios).
- Peak-excluded growth: remove the month with maximum latest-year views and its matched prior-year month from both annual sums. This is a sensitivity check, not causal event removal.
- Median monthly YoY: median of twelve same-calendar-month growth rates with nonzero baseline. Report positive-month count alongside it; zero-baseline months have undefined rates and do not count positive.
- Top-seven-day concentration: sum of the seven largest observed days in the latest year divided by annual views. Dates are retained to support subsequent event investigation.
- Coverage: fraction of expected days present for **every** basket member. Missing API days are never filled with zero. A single missing day within the comparison window withholds annual comparisons. Missing project totals preserve raw growth but withhold normalized conclusions and ranking.

## Decision rules

`insufficient_data`: annual observations/denominators incomplete, or raw growth undefined.
`fragile`: small baseline, top-seven concentration above threshold, a positive result disappearing after peak exclusion, or a detected title move.
`research_next`: remaining data meets all configured minimums for raw growth, share growth, peak-excluded growth and positive months.
`no_clear_growth`: valid remaining data does not meet the criteria. This does not settle the user's broader decision.

For comparable baskets, qualifying series are ordered by share growth, breaking ties on latest-year volume. This is an explicit prioritization heuristic. Default baseline 1,000, growth 10%, positive months 8/12 and spike concentration 15% are analyst defaults, not empirically established cutoffs. Repeat with stricter/looser thresholds; instability lowers trust. Robustness diagnostics do not provide confidence levels, hypothesis-test significance or forecast accuracy.

## Important boundaries

Historical traffic is requested under the current canonical title. Traffic to redirects is not automatically merged by this implementation. A source-title move-log check can flag some moves, but cannot establish complete historical title coverage, especially inbound moves. Always disclose this uncertainty; a sharp discontinuity warrants manual page-history review and an explicit title-lineage study before stronger recommendations. Avoid suggesting that the absence of a flag proves no rename.

Monthly curves can reflect school calendars, news, bots misclassified as users, search-ranking changes, content edits and ecosystem-wide traffic shifts. Project normalization mitigates one confounder but does not identify causality. Do not invent an event attribution from timing alone. A narrow article's fall does not prove total topic demand fell.

## Primary sources

Checked during implementation on 2026-09-23:

- [Agent Skills specification](https://agentskills.io/specification)
- [Wikimedia pageview endpoints](https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/reference/page-views.html)
- [Pageview definition](https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/concepts/page-views.html)
- [MediaWiki Pageprops](https://www.mediawiki.org/wiki/API:Pageprops)
- [Wikidata entity API](https://www.wikidata.org/w/api.php?action=help&modules=wbgetentities)
- [Wikimedia API etiquette](https://www.mediawiki.org/wiki/API:Etiquette)
