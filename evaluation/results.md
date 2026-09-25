# Verification record

Date: 2026-09-23. Environment: macOS arm64, Python 3.12.14.

## Implemented and checked

- Agent Skills frontmatter validation: **passed** (`skill-creator/scripts/quick_validate.py`). An older validator rejected the specification's optional `compatibility` field; environment requirements were moved into the body, preserving compatibility with both.
- Automated tests: **34 passed**. Run `.venv/bin/python -m pytest -q` to reproduce. Test data is synthetic and hand-checkable; HTTP failures are mocked.
- Dependency consistency: `pip check` passed; direct and full transitive pins are included.
- Live Wikidata/MediaWiki/AQS integration: astronomy, Ukrainian Wikipedia, 2024-09-01 through 2026-08-31; canonical article `Астрономія`, Q333, 100% daily coverage.
- Independent CSV totals: prior 12 months **16,614**, latest 12 months **6,708**, raw growth **−59.6244%**, edition-share growth **−46.4252%**, peak-excluded growth **−57.5249%**. These describe one article, not total astronomy-course demand.
- Initial implementation, cold Ukrainian collection: **55 HTTP attempts**, zero cache hits (includes transient retries). Offline repeat before range optimization: **50 cache hits, zero HTTP requests**, identical numerical results.
- Criteria follow-up: minimum raw growth changed from 10% to 30%; `reanalyze` made **zero HTTP requests**, retained source timestamps and numerical metrics, and kept `no_clear_growth`. Both PDFs have one page.
- PDF QA: page rasterized with Poppler and visually inspected; Ukrainian title/article text, table, both charts and source links are readable without clipping. Automated PDF text assertions also check Unicode and key values. English report labels are intentional in this version.
- Missing-equivalent scenario: Q1666254 (intermittent fasting) did not return a `plwiki` sitelink at retrieval. Planning `pl cs` stopped with a missing-sitelink error before producing a misleading comparison. This is a time-scoped API observation, not a claim that Polish readers have no interest.

- Final cold-cache live verification: **four HTTP requests**, zero cache hits for the entire Ukrainian study; every analytical field matched the earlier 50-response cached study.
- Performance iteration: observed slow cold per-month HTTP requests, replaced them with contiguous-range fetching plus monthly indexes referencing original source responses. Tests verify one request for 12 months, only the missing tail for an overlapping request, offline equivalence, explicit refresh and rejection of out-of-window API items.

## Cheap-model requirement: partially executed, stopped at user's request

An independent agent was dispatched explicitly on the fast/affordable `gpt-6-luna` model inside Codex. It received SKILL.md and the astronomy request, without expected numerical answers. It produced a plan, an initial study/PDF and a criteria-only follow-up/PDF. The first run's provenance records four HTTP requests; the follow-up uses the original snapshot and changes minimum raw growth from 10% to 30%. Both analysis files retain `no_clear_growth`.

The user then requested stopping development at a concrete milestone. The evaluating agent was interrupted before delivering its final behavioral evaluation and user-facing answers. Therefore **full cheap-model acceptance is not marked passed**. Preserved evidence: `evaluation/luna-partial/`. Finish the manual rubric in `references/development.md`, record final answers and verify the agent's actual tool trace before claiming the full requirement is met. Model token/cost/latency measurements are not available.

The optional OpenRouter harness was also checked for its missing-credential error: `OPENROUTER_API_KEY is not set. No model call made.` It did not invoke a model. The prohibited corporate Claude account was not used for model requests. No external model account is needed to resume an equivalent evaluation with an authorized Codex small model.

Note: a follow-up's provenance preserves the original acquisition request counters; they do not represent new requests made during reanalysis. The CLI reports current-run counters separately. Making this distinction explicit in the provenance schema is a remaining improvement.

## Follow-up verification — 2026-09-25

The earlier partial-model and provenance notes above describe the 2026-09-23 state. The subsequent implementation now uses provenance schema 2 with distinct `source_acquisition` and `current_run` counters; legacy schema 1 reanalysis is tested. The automated suite has **37 passing tests**. Final reports print the applied raw-growth criterion in both Markdown and PDF.

The inexpensive `gpt-5.6-luna` model completed the astronomy request, offline 10%→30% reanalysis, and a missing-sitelink scenario. The numerical, period, proxy, provenance and recommendation criteria passed manual review. The model's repeated unsupported claim that it visually inspected PDFs **failed** criterion 4; a later image-attached correction of the initial answer does not change first-attempt acceptance. The full rubric, prompts, tool traces, answers and output files are retained in [cheap-model-2026-09-25.md](cheap-model-2026-09-25.md). This evaluates an inexpensive Codex model, not Haiku/OpenRouter. No model request was sent through the OpenRouter harness.

The final ZIP was extracted into a new `/private/tmp` folder on macOS arm64 with Python 3.12.14. Installing `requirements.lock`, `pip check`, and all **37 tests** succeeded. A cold-cache live astronomy run made **4 HTTP requests**, returned 6,708 latest-year views and `no_clear_growth`; offline `reanalyze` made **0 HTTP requests** and preserved observations and source counters while changing the criterion 10%→30%. Both final-code PDFs are one-page A4, contain the applied criterion, and were rendered for visual QA. A Linux runtime was unavailable (Docker daemon not running), so the optional Linux check remains unverified.

## Remaining limitations

- Descriptive heuristic prioritization, not causal inference, payment propensity or statistical confidence.
- Current-title traffic only; no complete historical moves/redirect aggregation.
- Six audiences and six articles per audience; long reports may require splitting.
- Font coverage checked; complex-script shaping/RTL and multilingual report templates are not validated.
- Serial range requests with monthly source indexes reuse overlaps; cold API runs may still be slow during upstream retries. Scaling changes and acceptance gates are in `references/development.md`.
- No external publishing, messaging or deployment performed.

## Additional live language comparison

- Astronomy, Q333, Polish and Czech editions, 2024-09-01 through 2026-08-31: both had 100% daily coverage.
- Polish: latest annual views 17,175; raw growth −16.1254%; share growth −8.0085%; peak-excluded growth −27.6409%.
- Czech: latest annual views 6,188; raw growth −33.3405%; share growth −23.7337%; peak-excluded growth −31.3477%.
- The optimized run reused 88 cached responses and fetched the remaining contiguous ranges in two HTTP requests. Both series returned `no_clear_growth`; no automatic shortlist.
- One-page two-language PDF rasterized and visually checked. An obsolete slower pre-optimization run was cancelled after the optimized run completed.
- Ukrainian analysis after optimization matched the saved pre-optimization JSON exactly after JSON serialization (tuple/list normalization only).
