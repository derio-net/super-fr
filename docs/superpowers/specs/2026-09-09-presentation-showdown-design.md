# 2026-09-09 presentation-showdown — deck + fair-fight experiment

## Goal

Half-and-half deck for the dev team (30–45 min, Marp Markdown): half presenting
fr-goal's bundled features and why each exists, half a side-by-side recording
(fr-goal vs vanilla plan/execute on OpenCode) with a metrics comparison. The
deck closes on an open question, not a verdict: **is all this ceremony worth
it, given increasing model capabilities?**

## Decisions (outline gate, 2026-09-09)

- Slide renderer: Marp Markdown.
- Audience/slot: dev team, 30–45 min.
- Harness: OpenCode. Model pinned on BOTH runs: **OpenAI Terra, default effort**
  (record exact version string at record time).
- Demo feature: a ticket from the operator's board (details redacted). NOT
  accessed in this session — the driving model is not cleared for that board.
  Contents to be briefed in by the operator (or a cleared session) before
  `experiment-design`.
- Correction budget: unlimited but LOGGED (every operator clarification
  timestamped per run for the comparison table).
- Recording: asciinema per run → HyperFrames side-by-side edit, chapter marks
  at Q&A / spec / plan / implement / review / PR. Stills as live fallback.

## Half 1 — scope

fr-goal pipeline (shape manifest, run cursor, isolation, single Q&A, spec +
acceptance matrix, plan + self-review, manual phases, TDD implement + tier
models, review loop, draft PR + merge verify + Test Plan), standalone
fr-brainstorming / fr-debugging, custom shapes (`fr run` loop, repo override,
`fr workflow check`), integrations (Claude Code hooks/rules, OpenCode plugin +
mirrors, Hermes skills/hooks/`delegate_task`; git servers gh/glab/tea,
dry-run apply, reachability gate, label lifecycle, VK/CNCD runners).

## Half 2 — scope

Same seed prompt file (`experiment/prompts/goal.md`, derived from the redacted ticket without
exposing board contents here), two fresh branches from same `origin/HEAD`,
vanilla = plan mode + execute, no `fr-*`. Instrumentation per
`workflows/presentation-showdown.md` §4. Comparison table filled from
measurements only.

## Implementation Plans

| Plan | Repo | File | Depends on |
|---|---|---|---|
| 2026-09-09-presentation-showdown | `derio-net/super-fr` | `2026-09-09-presentation-showdown` | — |

## Open items

- Demo brief (operator-provided, outside this session).
- Exact Terra version string at record time.
- Session-log export path for OpenCode token/$ accounting.
