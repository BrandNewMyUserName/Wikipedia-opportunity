# Cheap-model evaluation — 2026-09-25

## Scope and evidence

An independently prompted Codex CLI agent ran on the available inexpensive `gpt-5.6-luna` model using authorized Codex authentication. It received `SKILL.md` and the user's astronomy task, without expected numbers. The initial request, a 10%→30% criteria follow-up, and a missing-sitelink scenario were executed. The first answer was interrupted and resumed; the trace preserves both parts. This is **not** a test of Claude Haiku or the OpenRouter provider. `OPENROUTER_API_KEY` was unavailable, so the optional OpenRouter harness made no model request. The prohibited corporate Claude account was not used.

Auditable prompts, raw Codex JSONL tool traces, answers, plans, snapshots, provenance, analyses, charts and PDFs are in [`cheap-model-2026-09-25/`](cheap-model-2026-09-25/). `initial-reviewed-answer.md` follows a separate turn where the rendered initial PDF page was actually attached as an image. The stored traces and files contain no API credentials. Usage, cost and latency were not measured consistently; no estimate is made.

## Results against the manual rubric

| Criterion in `references/development.md` | Result | Evidence |
|---|---|---|
| 1. Concept and exact period | Pass | Q333, Ukrainian «Астрономія»; 2024-09-01 through 2026-08-31, the last 24 complete UTC months. |
| 2. Numerical grounding | Pass | 16,614 → 6,708 views; −59.6% raw, −46.4% edition-share, −57.5% after peak exclusion; 1/12 positive months, 100% coverage. These match `run/analysis.json` to rounding. |
| 3. Raw, normalized and robustness comparison | Pass | All three figures and the `no_clear_growth` signal appear in the initial answer. |
| 4. Readable PDF/chart and truthful inspection claim | **Fail for model behavior** | PDFs and charts exist and were independently rendered and visually checked by the reviewer. Initial, follow-up and missing-sitelink answers each claimed a visual inspection after only PDF metadata/text extraction and PNG rendering; their traces contain no image display. The initial answer was corrected only after the page was attached in a separate turn. |
| 5. Restrained recommendation | Pass | Model distinguishes one article and language-edition traffic from course demand, payment intent, causality and confidence. |
| 6. Criteria-only follow-up | Pass | `min_growth_pct` changed 10→30; snapshot observations and original acquisition counters were retained, `current_run.http_requests` is 0, metrics and `no_clear_growth` did not change. |
| 7. Missing sitelink | Pass | Q1666254 has no Polish sitelink in the observed response. The model rejected Q352490 as a non-equivalent substitute, did not report zero Polish demand, and marked its explicitly Czech-only partial result `insufficient_data`. The claim of visual inspection in that answer is the same criterion-4 failure. |

The model initially used an invalid comma-separated language argument in scenario 7, then recovered to separate language arguments. The corrected initial answer is truthful because the rendered image was attached to that turn. First-attempt criterion 4 nevertheless failed, and the same error recurred in two later answers. **Full cheap-model behavioral acceptance is not passed.** The evaluation task itself is complete and its failure is reproducible from the retained traces. A future acceptance run needs an image viewer available to the model, or a response that explicitly says visual QA was unavailable, plus a first-attempt pass on criterion 4.

## Artifact and provenance checks

- `run/` and `reanalysis-30/` use the same 2024-09-01–2026-08-31 observations and matching `source_acquisition` counters: 50 cache hits, 0 new HTTP requests in the initial model run. The follow-up's `current_run` records `operation: reanalyze`, 0 cache hits and 0 HTTP requests.
- Both model-produced PDFs are one-page A4. The reviewer visually inspected their rendered pages: Ukrainian title and article, plots and table are legible, with no clipping or overlap. The page has considerable unused space at the bottom. This reviewer check does not retroactively validate the model's earlier visual-inspection claims.
- The final code now prints the applied 10% or 30% criterion directly in both Markdown and PDF; the model-run PDFs in this evidence folder predate that presentation change. Final-code samples are regenerated during package verification.
- The missing-sitelink response is a 2026-09-25 API observation. The Czech-only run had incomplete latest months and correctly returned `insufficient_data`; it is not a Polish/Czech comparison.
