# Wave merge queue gaps (#1677)

Three phases, one per ask of the spec (`2026-11-24-wave-queue-gaps-design.md`):

1. Hand-backs (R1-R6): the brief names the stack target, re-issues free of budget when it stops leading to `main`, and a head carrying an ejected combination is held and briefed to reset. It also makes the room the module budgets need (§E) and moves judgements to schema 14.
2. Operator entries (R11-R16): `fr triage queue add/remove`, preapproval, the planner's join, open and drain rules.
3. Overlap-aware waves (R7-R10): it needs PR #1669's `generated:` key, so it runs last and merges `origin/main` once #1669 has landed.

Every phase is TDD; the executor runs the fast tier (`tests: ci` in `.fr/ci.yaml`).
