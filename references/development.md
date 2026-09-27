# Development, evaluation and iterative roadmap

For the 2026-09-26 topic-map expansion, see [live Wikimedia and OpenRouter evaluation](../evaluation/topic-map-2026-09-26.md). The map evaluation script is `scripts/evaluate_topic_map.py`; it loads `.env` through `python-dotenv` into `OPEN_ROUTER_API_KEY` without printing the key. Its fixture tests date/topic/source discrimination, while `verify-spike` supplies the deterministic gate required by the skill. Model-only and guarded scores must be reported separately.

## Reproduce

From the skill folder, use Python 3.12+:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pytest -q
```

For live checks, choose an independent user topic, run `discover`, `plan` and `run` into new paths under `work/`, then use `reanalyze` on the saved snapshot for a criteria-only follow-up. Do not embed a fixed topic in the skill instructions or evaluation harness.

`requirements.txt` records intentional direct pins; `requirements.lock` freezes all transitive dependencies from the verified Python 3.12 environment. No compiler or system font installation is required; plotting uses Matplotlib's bundled DejaVu and PDFs embed it. For scripts outside DejaVu coverage, set `WIKIPEDIA_REPORT_FONT` to an appropriate Unicode TTF; missing glyphs cause an explicit error. Complex-script shaping/RTL is not validated in this version. Poppler is optional for external visual QA, not runtime report generation.

Copy this complete folder to an agent's supported skills directory or point the agent at `SKILL.md`. Do not distribute `.venv`, caches, `work`, `__pycache__` or compiled files. Nothing in the skill imports another local skill or uses machine-specific absolute paths.

## What was verified

See [evaluation record](../evaluation/results.md) for measured outcomes and incomplete checks. Automated checks cover analytical invariants rather than wording: aligned annual totals; project normalization; missing versus zero; zero baseline; spikes; small baselines; basket completeness; non-equivalent basket ranking; malformed dates/criteria; HTTP retries/404; response hashes; Unicode URL escaping; entity validation; offline reanalysis; snapshot integrity; one-page Unicode output; six-series layout; and evaluation-tool path confinement.

The AI coding agent authored the implementation, tests and instructions. Its results were checked with hand-computable synthetic histories, mocked HTTP failure sequences, real Wikimedia API responses, independently inspected JSON/CSV totals, the Agent Skills frontmatter validator and rendered PDF review. A passing code test is not a passing model-behavior evaluation. No hidden chain-of-thought is needed as evidence: retain tool inputs/results, final answers and observable artifacts.

## Cheap-model full workflow

Use only an explicitly authorized account. The research CLI itself has no LLM dependency. The optional evaluation harness uses the OpenRouter tool-calling API and reads `OPENROUTER_API_KEY` only from its process environment; it never stores the key.

```sh
.venv/bin/python scripts/evaluate_model.py \
  --model google/gemini-2.5-flash-lite \
  --prompt-file work/evaluation/request.txt \
  --out work/evaluation/run-v1
```

Alternatively choose an available free model that explicitly advertises tool support. Confirm availability and rates in the [current catalog](https://openrouter.ai/models?supported_parameters=tools); adding `:free` does not create a free variant. See [OpenRouter free variants](https://openrouter.ai/docs/guides/routing/model-variants/free) and [tool calling](https://openrouter.ai/docs/guides/features/tool-calling).

The harness supplies SKILL.md, the research request from a UTF-8 text file, and three bounded tools. The request must ask for a live study of the last two complete years and a PDF. After the first answer, the harness changes the growth threshold to 30% on the same observations. The model must discover a concept, create a plan, run the CLI, inspect results, deliver a grounded answer, and use reanalysis for the follow-up. It records requested/actual models, tool calls/results, token/cost metadata when returned, elapsed time, final answers, PDFs and automated checks. It has no unrestricted shell tool. It does not provide image inspection; a reviewer must render PDFs separately. Maximum 18 model turns by default, hard ceiling 30, 3,000 output tokens per call; transient retries are bounded. External provider billing/limits still apply.

Automatic acceptance checks now require the exact rolling 24-month period, an initial/follow-up report pair, unchanged snapshot observations and source acquisition, a 10%→30% criterion change, and a `reanalyze` run with zero current HTTP requests. A model once chose the last two January–December years instead; that failure led to an explicit date instruction in `SKILL.md` and a regression check. Automatic checks still cannot judge the truthfulness of prose or visual-inspection claims; the manual rubric remains required.

`provenance.json` schema 2 identifies the original data-fetch counters under `source_acquisition` and the counters for the current report under `current_run`. Reanalysis of schema 1 reports migrates their top-level counters into `source_acquisition`; missing historical counters stay unknown (`null`).

Acceptance rubric (review manually after automatic checks):

1. Correct topic/QID/title and the exact last 24 complete months; no invented country or user intent.
2. All reported volumes and rates agree with analysis.json to stated rounding.
3. Explicit comparison of raw and normalized trends plus at least one robustness diagnostic.
4. PDF/chart exist and are readable; no false claim of visual inspection.
5. Recommendations distinguish research priority from paid demand, causality and statistical confidence.
6. Follow-up preserves observations, changes only criteria, runs without network and reports whether the decision changed.
7. The agent recovers from a missing sitelink by explaining the limitation instead of inventing a title or zero views.

A real model transcript is required before claiming compatibility with Haiku/free models. The harness and deterministic tests are not substitutes. To expand evaluation, run three repetitions per scenario, log first-attempt success, recovery rate, latency, cost and analyst agreement; keep previously failing cases as regression scenarios.

The [2026-09-25 inexpensive-model evaluation](../evaluation/cheap-model-2026-09-25.md) contains actual Codex `gpt-5.6-luna` tool traces and a **failed** first-attempt visual-inspection truthfulness criterion. It is not a Haiku or OpenRouter compatibility claim.

## Iterative development gates

1. **Semantic coverage:** add curated, versioned baskets with explicit inclusion/exclusion rationales; evaluate narrow intent and missing-language cases with a domain reviewer. Gate: independently judged equivalent proxies, no silently dropped languages. Add uncommon Wikimedia language-code ↔ site-ID mappings.
2. **Historical fidelity:** resolve page-title lineage and redirect traffic with deduplication rules and archived mapping versions. Gate: known rename cases reproduce manually reconciled totals. Add daily/weekly event windows and citations explaining candidate event causes.
3. **Stronger temporal analysis:** 3–5 years of history, seasonal baselines, school calendars, comparisons to control topics and change-point diagnostics. Define the inferential question before adding uncertainty intervals; autocorrelated pageviews do not justify naive IID bootstrap significance. Gate: backtests and event stress tests, calibrated claims, sensitivity across proxy baskets.
4. **Broader research:** support weighted baskets, separate audience and topic dimensions, scenario comparisons, external search/app-store signals and interview findings. Gate: data licenses/provenance retained and no unjustified merging of metrics with different units. Add native report-language templates and appropriate font/shaping support.
5. **Scale:** replace file cache with indexed SQLite/Parquet storage, keep the existing contiguous-range fetch and monthly source indexes, introduce per-host rate-limited bounded workers and a durable job/checkpoint queue. Dedupe project totals across jobs. Gate: output equivalence against the serial implementation, restart-after-failure tests, measured API calls/runtime/storage at 100 and 1,000 page-language pairs. No need for distributed infrastructure before measurements justify it.
6. **Operational quality:** schema migrations, cache retention policy, reproducible export manifests, CI on Linux/macOS, monitored API contract fixtures and a cheap-model benchmark suite. Gate: no numerical or behavioral regressions, explicit handling of changed source schemas and model availability.
