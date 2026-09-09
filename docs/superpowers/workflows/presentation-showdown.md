# presentation-showdown — companion prose (fr reads only the .yaml)

This file is the human half of the `presentation-showdown` shape. The YAML
orders the steps; this doc says what "done" means for each. Neutrality rule:
no outcome is presumed — the deck closes on measured numbers, not a moral.

## 0. Context (agreed so far)

- Format: Markdown slides (Marp). Audience: dev team, 30–45 min.
- Harness: OpenCode, same pinned model on both runs (record the version string).
- Half 1: fr-goal's bundled features + why each exists (failure mode it counters),
  fr-brainstorming / fr-debugging standalone, custom flows, harness + git-server
  integration points.
- Half 2: side-by-side recording of the same feature built with fr-goal vs
  vanilla plan/execute, same prompts + bounded corrections, asciinema →
  HyperFrames edit, then a metrics comparison.

## 1. outline (gate: operator)

Brainstorm the deck inside isolation. Emit a spec (the deck outline + narrative
arc). Ask the operator ONCE (≤4 questions): slide tooling, feature candidates
for half 2, model pin, correction budget. Unanswered = stop, never default.

## 2. experiment-design

Turn the spec into a plan: demo-feature shortlist (2–4 phase scope, CLI + tests,
no secrets), identical seed prompt file (`experiment/prompts/goal.md`),
correction budget (unlimited but logged — every clarification timestamped per run), branch hygiene
(two fresh branches from same `origin/HEAD`).

## 3. design-review

`fr plan self-review` must pass. Fix findings, re-run.

## 4. instrument

Define the metrics + how each is captured on BOTH runs:

- Target acquired: acceptance checklist pass/fail per row (binary).
- Wall time + active operator time (asciinema duration + prompt timestamps).
- Cost: OpenCode session tokens in/out + $ (session log export; journal gives
  the fr-goal phase breakdown).
- Quality: `uv run pytest -q`, `ruff check`, `mypy`, coverage delta,
  review findings fixed/refuted/missed.
- Maintainability: LOC changed, files touched, spec/plan/journal/run present?,
  `fr validate artifacts` + `fr acceptance check` green?

## 5. record-compare

Record both runs (`asciinema rec`), edit side-by-side in HyperFrames with
chapter marks (Q&A / spec / plan / implement / review / PR). Fill the comparison
table from measurements only. Stills as fallback if video fails live.

## 6. deliver-deck

Build the Marp deck + experiment files, open ONE draft PR, mark ready only after
self-review + full suite pass. Close by posing the thesis question, not answering
it: **is all this ceremony worth it, given increasing model capabilities?**
Ceremony costs vs. hypothesized benefits (fewer wrong-thing builds, less context
loss, auditable trail) — each possibly shrinking as models improve. The numbers
decide.
