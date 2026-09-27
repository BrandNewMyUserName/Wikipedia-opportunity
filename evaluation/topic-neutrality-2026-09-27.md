# Topic-neutral agent check — 2026-09-27

Model: OpenRouter `google/gemini-2.5-flash-lite` (tool-capable, low-cost). The test used this model exclusively. The API key was loaded through `OPEN_ROUTER_API_KEY` from `.env` by `python-dotenv`; the file was not opened or printed directly.

Scenario: a live Wikimedia map of two concepts in the Ukrainian and Polish language editions, then a related request about excluding the peak month and adding a third language. The agent had one read-only `read_topic_map` tool backed by the saved live `topic-map.json`. First tool call was required for both versions. Same user questions, data, temperature 0, and token limit were used.

| Variant | Rubric checks | Manual finding |
|---|---:|---|
| Skill before neutralization | 16/18 | Annual change was incorrectly explained using endpoint months; follow-up did not name the new map run. |
| Final skill, run 1 | 17/18 | Misstated the denominator of the concept share. |
| Final skill, run 2 | 15/18 | Omitted exact peak-excluded values in follow-up and did not name the new map run. |
| Final skill, run 3 | 18/18 | Correct figures, limits, robustness conclusion, and new `map --languages` action. |

The final skill had no observed topic contamination, fabricated links, or false spike dependence in these final runs. Earlier iterations exposed fabricated chart links, false peak dependence and inaccurate comparison wording; the instructions were amended and the checks extended. The three-run result is variable, so this is evidence of no clear regression in this scenario, not a guarantee for all topics or prompts. A small model can still omit required details; a production answer should be checked against `topic-map.json` and provenance.

Code checks after edits: `41 passed`; skill validator passed; `git diff --check` passed. The default skill, references, README, handoff and runtime report instructions no longer contain topic-specific examples. Historical fixtures and evaluation records remain as audit data and are not part of the normal agent prompt.
