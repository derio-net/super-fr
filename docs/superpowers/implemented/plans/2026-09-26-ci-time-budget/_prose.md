# CI time budget — implementation plan

Spec: `docs/superpowers/specs/2026-09-26-ci-time-budget-design.md`.

Two agentic phases:

1. **Sharding (walking skeleton).** Add pytest-split, move the coverage sources
   into `[tool.coverage.run]`, commit `.test_durations`, and turn ci.yml's
   `test` job into 4 shards plus a `coverage` combine job. The skeleton is proven
   live: the branch's own CI push run must take under 240s of wall clock, with
   coverage still gated at 75.
2. **Watcher.** Build `scripts/ci_budget.py` (a pure core plus a `gh` adapter),
   `.github/ci-budget.yaml` and `.github/workflows/ci-budget.yml`, the watch-list
   tripwire, and the dedup and auto-close state machine, all unit-tested against
   captured fixtures.

The watcher is inert until merge (`workflow_run` fires only from the default
branch). The post-merge Test Plan (observe, then a forced breach) is
operator-driven and is not a plan phase. No change fragment is needed (spec
§3.C).
