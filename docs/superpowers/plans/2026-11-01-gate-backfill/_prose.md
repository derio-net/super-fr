# gate-backfill — implementation plan

Spec: `docs/superpowers/specs/2026-11-01-gate-backfill-design.md` (R1–R15).

Four agentic phases, one per independently reviewable ask:

1. **Dry run** (skeleton). The `fr gate backfill` verb, candidates from `fr debt`'s
   fold plus the manifest, the delivering-PR evidence chain, gates, the plan file
   and its decisions, the summary and the R11 repo-file commands. Nothing is
   written to the forge. Its first task is the smoke test: the verb exists and a
   dry run makes no write.
2. **Apply** (`--yes`). PR gate labels, fr-owned trackers with the two-line
   marker, adopt, duplicate close, closed-issue link comments, `tracking: none`,
   idempotency and the R15 refusals.
3. **Pass closes trackers.** `close_gate_trackers` beside `pass_gate`, called by
   `fr gate pass` and by the triage driver's rows-walked pass, plus the retry on an
   already-passed PR. Depends on phase 2's markers.
4. **Board.** `fr triage collect` reads gate-labelled merged PRs (facts schema
   bump), and the Needs-you Tester/DevOps lanes list them once. Depends only on
   phase 1 (the shared `GhClient` edits), so it is independent of 2 and 3 in
   substance.

No `[manual]` phase. The one operator act is the post-merge live row
`gate-backfill-first-real-sweep`, which the Test Plan says is walked on the first
real per-repo sweep.

Constraints carried from the spec: `fr gate` stays forge-only (in
`READ_ONLY_COMMANDS`); no artifact kind's version moves; nothing in
`fr/artifacts/trigger.py` or `registry.py`; fixtures use `example-org/widgets`;
heavy suites run through the shared test slot, preferring CI.
