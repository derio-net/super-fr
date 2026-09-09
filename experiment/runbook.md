# Instrumentation + recording runbook (fills P2/P3 of the plan)

Model pinned BOTH runs: OpenAI Terra, default effort. Record exact version
string here at record time: `TERRA_VERSION=<pending>`.

## Seed prompt (pending SPARK-4 brief)

- Template: `experiment/prompts/goal.md` (placeholder — operator fills from
  SPARK-4 during repo prep; board contents never enter uncleared sessions).
- Same file feeds BOTH runs verbatim. Vanilla run gets no additional context.

## Correction log schema (unlimited but logged)

Per run, append every operator clarification:

```
| # | timestamp (UTC) | run | prompt | response | tokens est |
```

No cap; the count itself is a metric.

## Metrics capture (both runs identically)

- Target acquired: acceptance checklist (`experiment/acceptance.md`, pending
  brief) — binary pass/fail per row.
- Wall time + operator time: asciinema duration + correction-log timestamps.
- Cost: OpenCode session token in/out + $ (session log export path: `<pending>`).
- Quality: `uv run pytest -q`, `ruff check`, `mypy`, coverage delta,
  review findings fixed/refuted/missed.
- Maintainability: LOC changed, files touched, artifacts present
  (spec/plan/journal/run), `fr validate artifacts` + `fr acceptance check`.

## Recording runbook

```bash
asciinema rec -c "opencode run ..." experiment/fr-goal.cast
asciinema rec -c "opencode run ..." experiment/vanilla.cast
```

HyperFrames: two tracks side-by-side, chapters at
Q&A / spec / plan / implement / review / PR. Export stills as live fallback.
