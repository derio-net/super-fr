# Sweep fixes: implementation plan

**Spec:** `docs/superpowers/specs/2026-11-08-sweep-fixes-design.md`

Five phases, one per ask, on one branch. Phase 1 is the skeleton and carries the smoke, so the
branch has a green CI run and a draft PR before the rest lands. Phases 2 to 5 depend only on it and
run in order.

- **Phase 1 (#1327)** makes the printed commands work and adds the test that executes them. Later
  phases that print a new command extend its table.
- **Phase 2 (#1334)** is a small exclusion in `_lookalikes`.
- **Phase 3 (#1325)** widens the heading repair and moves neighbouring headings.
- **Phase 4 (#1323, #1328)** adds positive evidence first, because both the closing comment and the
  backfill close read it.
- **Phase 5 (#1321)** adds the installable definition, then changes the RC branch only.

## Execution notes

- Targeted tests run through the coordinator's test-slot wrapper; the full suite runs in CI, and
  each phase's record says `tests: ci`.
- No edit under `fr/triage/batch*`: `close_gate_trackers`'s new parameter defaults to empty, so the
  driver's call site is untouched.
- Privacy: fixtures use reserved names, and public text says "a private consumer repo".
