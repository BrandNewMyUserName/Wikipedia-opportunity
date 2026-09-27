# Wikipedia Opportunity Research

Research topic attention across Wikipedia language editions. The tool discovers Wikidata concepts, fetches human-classified daily pageviews from the Wikimedia Analytics API, compares two consecutive annual periods, builds curated topic maps and produces auditable reports.

**What it measures:** relative attention trends (growing / declining interest).
**What it does not measure:** real-world prevalence, intent, unique users or causal factors.

## Project structure

```
wikipedia-opportunity/
├── SKILL.md                       # Agent Skill entry point (instructions for AI agents)
├── HANDOFF.md                     # Current status, verified items, open work
├── README.md                      # This file
├── pytest.ini                     # Pytest configuration
├── requirements.txt               # Direct dependency pins
├── requirements.lock              # Full transitive lock (Python 3.12)
│
├── scripts/                       # Core source code
│   ├── wiki_interest.py           # CLI entry point
│   ├── data.py                    # Wikimedia HTTP client, SHA-256 cache, range batching
│   ├── analysis.py                # Growth calculations, signal classification
│   ├── report.py                  # Chart (PNG), table (CSV), report (MD + one-page PDF)
│   ├── topic_map.py               # Cross-language map and spike candidates
│   ├── spike_evidence.py          # Dated-source evidence gate
│   └── evaluate_model.py          # OpenRouter harness for cheap-model evaluation
│
├── references/                    # Documentation
│   ├── methodology.md             # Formulas, units, evidence boundaries
│   ├── development.md             # Reproducing tests, evaluation rubric, iteration roadmap
│   └── input.md                   # Config format, CLI reference, output contract
│
├── tests/                         # Automated tests (pytest)
│   ├── conftest.py                # Shared fixtures
│   ├── test_analysis.py           # Analytical invariants
│   ├── test_cli.py                # CLI scenarios
│   ├── test_client.py             # HTTP, cache, retries, error handling
│   ├── test_report.py             # PDF, PNG, CSV, Unicode output
│   ├── test_skill.py              # SKILL.md frontmatter validation
│   └── test_evaluate_model.py     # Evaluation harness checks
│
├── examples/                      # Historical fixtures; not prompts for new research
│
├── evaluation/                    # Independent model evaluation evidence
│   ├── results.md                 # Summary of all verification checks
│   ├── cheap-model-2026-09-25.md  # gpt-5.6-luna evaluation report
│   ├── cheap-model-2026-09-25/    # Full traces, prompts, answers, artifacts
│   └── luna-partial/              # Earlier partial evaluation (2026-09-23)
│
├── .cache/                        # HTTP response cache (auto-created, gitignored)
└── .gitignore
```

## Requirements

- Python 3.12+
- pip
- HTTPS access to Wikimedia / Wikidata APIs (no API key needed)

## Setup

```sh
cd wikipedia-opportunity
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
```

## Usage

Run commands from the project root with `.venv/bin/python scripts/wiki_interest.py <command>`. Use `<command> --help` for all arguments. Commands print a short JSON result; larger results are saved to files.

### System functions

| Command | What it does | Main input | Result |
|---|---|---|---|
| `discover` | Searches Wikidata for candidate concepts | `--query`, optional `--search-language` | Up to six QIDs with labels and descriptions |
| `plan` | Checks article links in the selected Wikipedia editions and creates a study plan | `--qids`, `--languages`, `--question`, `--out`; optional dates | Config JSON and `.mapping.json` |
| `run` | Collects pageviews, calculates trends and creates a focused report | `--config`, `--out` | Snapshot, analysis, CSV, chart, PDF, Markdown report and provenance |
| `reanalyze` | Recalculates a previous study with changed thresholds, without new network requests | `--run`, `--out`; optional `--criteria` JSON | New analysis and report from the original snapshot |
| `map` | Builds a curated topic map across language editions | `--root-qid`, `--qids`, `--languages`, `--out`; optional dates | `topic-map.json`, Markdown map, snapshot and provenance |
| `verify-spike` | Checks whether inspected sources match a detected spike's date and concepts | `--map`, `--language`, `--date`, `--evidence`; optional `--out` | Evidence status and accepted sources; no causal proof |

Typical flows: `discover → plan → run` for a focused study; `discover → map` for a wider topic, followed by `verify-spike` when the map flags a spike and sources have been inspected. To change only decision thresholds, use `reanalyze`. Changing dates, concepts or languages requires a new plan and `run`, or a new `map`.

For optional agent testing, `scripts/evaluate_model.py` runs a research request from a `.txt` file under `work/evaluation/` with `--model`, `--prompt-file` and `--out`. Use a fast, inexpensive OpenRouter model that supports tools. This evaluation needs `OPENROUTER_API_KEY`; Wikimedia research does not.

### 1. Discover concepts

Search Wikidata for entities using the user's topic terms with `discover --query`.

Returns up to six candidates with QID, label and description. Pick the semantic match — do not blindly use the first result. Use `--search-language uk` for non-English queries.

### 2. Create a research plan

Map verified QIDs to requested Wikipedia language editions with `plan --qids --languages --question --out`.

This checks Wikidata sitelinks and produces a versioned config JSON plus a `.mapping.json` evidence file. A missing sitelink is an error — it does not mean zero demand.

Override dates with `--start YYYY-MM-01 --end YYYY-MM-DD` (defaults to the last 24 complete UTC months).

### 3. Run the study

Use `run --config --out` with the plan path and a new output directory.

The output folder must be new or empty. The command:
- validates pages (existence, redirects, disambiguation, Wikidata QID match)
- fetches daily pageviews and monthly edition totals
- computes growth metrics and classifies each series
- generates all outputs: `snapshot.json`, `analysis.json`, `monthly.csv`, `trend.png`, `report.pdf`, `report.md`, `provenance.json`

### 4. Re-analyse with different criteria

Change thresholds without re-downloading data:

Save changed thresholds as JSON, then use `reanalyze --run --criteria --out` with the original run and a new output directory.

This re-uses the original snapshot with **zero network requests**. Only criteria can change — for different dates, topics or languages, create a new plan and `run`.

### Topic maps and spike checks

Use `map --root-qid --qids --languages --out` with a curated, verified concept set. It writes a QID-aligned map, per-concept and basket trends, missing sitelinks and candidate spike dates. Inspect source pages found by date and topic, then pass their metadata to `verify-spike --map --language --date --evidence --out`. The gate can mark an event plausible; it cannot establish traffic causation.

### CLI flags

| Flag | Effect |
|---|---|
| `--offline` | Read cache only; fail on any cache miss |
| `--refresh` | Re-fetch every used response (ignore cache) |
| `--cache PATH` | Custom cache directory (default: `.cache/`) |

## Output files

Each run produces a self-contained folder:

| File | Contents |
|---|---|
| `snapshot.json` | Full input config, validated pages, daily observations, edition totals |
| `analysis.json` | Computed metrics: growth, share, peak-excluded growth, signals, research ordering |
| `monthly.csv` | One row per series/month; empty = missing, 0 = observed zero |
| `trend.png` | Two-panel chart: raw monthly views + views per million edition views |
| `report.pdf` | One-page A4 brief with embedded Unicode font |
| `report.md` | Markdown report with source links |
| `provenance.json` | Exact API URLs, retrieval timestamps, response hashes, cache/HTTP counters |

## Signals

The analysis classifies each series into one of four signals:

| Signal | Meaning |
|---|---|
| `research_next` | Meets all configured growth thresholds — worth investigating further |
| `no_clear_growth` | Valid data but does not meet criteria — does not settle a broader decision |
| `fragile` | Small baseline, spike concentration, peak-sensitive growth, or detected title move |
| `insufficient_data` | Missing observations or undefined baseline — cannot draw a growth conclusion |

## Testing

```sh
.venv/bin/python -m pytest -q
```

Tests cover analytical invariants, cache behaviour, API error handling, topic maps, PDF output, provenance integrity and evaluation harness boundaries.

## Environment variables

| Variable | Purpose |
|---|---|
| `WIKIMEDIA_USER_AGENT` | Identifies your application to Wikimedia APIs (recommended for production) |
| `WIKIPEDIA_REPORT_FONT` | Path to a Unicode TTF font for PDF rendering (default: bundled DejaVu Sans) |
| `OPENROUTER_API_KEY` | Required only for the optional `evaluate_model.py` harness |

## Limitations

- Pageviews measure attention, not people, intent or real-world prevalence.
- Wikipedia language editions are not countries; audiences can overlap.
- Only current article titles are tracked — redirect traffic and historical renames are not fully merged.
- Signals are descriptive heuristics, not statistical confidence or causal evidence.
- Maximum six series and six articles per series per one-page report.
- Serial API requests; not designed for large-scale concurrent use against Wikimedia.

See [references/methodology.md](references/methodology.md) for detailed formulas and evidence boundaries.
