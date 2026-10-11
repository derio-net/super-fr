# Journal: 2026-10-11-debt-engine

<!-- fr:journal kind=decision scope=plan id=plan-shape created=2026-10-11T17:47:38+00:00 -->
### plan-shape · decision · Five agentic phases, the skipped split first as the skeleton

One phase per ask of #1121: P1 the skipped split and its migrations (skeleton, hard,
risk-first and the status vocabulary the rest counts with), P2 the engine, P3 owed
actions (hard), P4 the weekly issue/archive PR/forge adapters/scaffolds, P5 triage.
No [manual] phase: the live checks are the spec's post-merge Test Plan rows.

<!-- fr:journal kind=decision scope=plan id=p1-open-rows-include-failing created=2026-10-11T20:59:18+00:00 phase=1 -->
### p1-open-rows-include-failing · decision · open_rows is exactly DEBT_STATUSES, so failing rows now join the nag set (phase 1)

`check.open_rows` returned skipped + not-implemented; it now returns the
DEBT_STATUSES rows (not-implemented, unwired, walk-owed, failing), as P1.T2.S1
asked. `failing` therefore also appears in `fr acceptance status`, the digest
and the check's warning annotations, as well as still failing the check (exit 2).

<!-- fr:journal kind=decision scope=plan id=p1-walked-without-walk created=2026-10-11T20:59:18+00:00 phase=1 -->
### p1-walked-without-walk · decision · rows reclassified as walked without a recorded walk are undated (phase 1)

R7's hand reclassification moved 18 former skipped rows whose notes record a
live walk (no `walks:` entry) to `walked`, and 5 mechanically walk-owed rows
whose notes say the walk already happened. `set-status --status walked` does
not require `--walk`; such a row shows no date in the reports
(`latest_passing_walk_at` returns None). Phase 2's R2 rendering should say
"undated" rather than omit it.

<!-- fr:journal kind=discovery scope=plan id=p1-reclassification created=2026-10-11T20:59:18+00:00 phase=1 -->
### p1-reclassification · discovery · this repo's 38 former skipped rows, after the mechanical rule and R7 (phase 1)

Mechanical 4->5: 27 unwired, 8 walk-owed, 3 walked (as the spec counted).
After R7 (each via `fr acceptance set-status`, the note naming why): walked 18
more from unwired and 5 from walk-owed (live walk recorded in notes); walk-owed
7 from unwired (acceptance-pipeline-rows, acceptance-nag-channels, hermes-fr-goal-delegation,
goal-executor-refuses-tick, fr-goal-main-session-cost, ci-under-time-budget,
ci-actions-dependabot-updates); manual 1 (acceptance-added-since). Left
unwired: 1 (cli-starts-from-a-clean-install: no test asserts the installed CLI runs).
Final: ci 393 (+2 this phase), walked 26, walk-owed 10, unwired 1, manual 1,
not-implemented 37 (-2), scheduled 1.

<!-- fr:journal kind=discovery scope=plan id=p1-index-lock-timing-under-load created=2026-10-11T20:59:18+00:00 phase=1 -->
### p1-index-lock-timing-under-load · discovery · test_a_record_commit_gives_up_on_a_stuck_index_lock_quickly is wall-clock-tight (phase 1)

Under a host load average of ~850 (other processes, not this run) the test
measured 19.9 s against its `< 5.0` bound, alone and in a targeted run. This
phase does not touch the record commit path. If the full suite reds on it,
it is load, not a regression.

<!-- fr:journal kind=finding scope=plan id=p1-ci-scenario-matrix-version created=2026-10-11T20:59:18+00:00 phase=1 state=fixed review_scope=in -->
### p1-ci-scenario-matrix-version · finding [fixed] (reviewer: in scope) · spec-verification-section.sh hardcoded matrix schema 4 (phase 1)

PR #1139 CI (run 38169463074): the scenario asserted the migrated matrix reached
schema 4; the chain now ends at 5. It and shipped-verification-strategies.sh now
write and expect schema 5. Fixed; tests/integration/test_scenarios.py 30 passed.

<!-- fr:journal kind=finding scope=plan id=p1-ci-scenario-record-version created=2026-10-11T20:59:18+00:00 phase=1 state=fixed review_scope=in -->
### p1-ci-scenario-record-version · finding [fixed] (reviewer: in scope) · cloud-triage-ci-evidence.sh wrote a v8 step record (phase 1)

The live StepRecord reads only version 9, so the scenario's record was refused
(exit 2). It now derives the stamp from the candidate's RECORD_SCHEMA_VERSION,
so the next bump cannot break it. Fixed; scenario tests 30 passed.

<!-- fr:journal kind=finding scope=plan id=p1-ci-skill-duty-needle created=2026-10-11T20:59:18+00:00 phase=1 state=fixed review_scope=in -->
### p1-ci-skill-duty-needle · finding [fixed] (reviewer: in scope) · test_skill_validation needle 'choose skipped' no longer in fr-acceptance (phase 1)

The duty now reads "choose unwired"; the needle was updated to it. Fixed;
tests/unit/test_skill_validation.py passes.

<!-- fr:journal kind=finding scope=plan id=p1-ci-triage-render-fixture created=2026-10-11T20:59:18+00:00 phase=1 state=fixed review_scope=in -->
### p1-ci-triage-render-fixture · finding [fixed] (reviewer: in scope) · test_triage_render_command fixture matrix used status skipped (phase 1)

A matrix saying `skipped` no longer loads, so the stored acceptance was None.
The fixture and assertion now use `unwired`. Fixed;
tests/unit/test_triage_render_command.py passes.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-10-11T20:59:18+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

a fragment and a one-assert smoke test; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-10-11T20:59:18+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

the 8->9 hop reuses matrix_status_split.split_status (R6's rule, one definition) and the v7 frozen classes; the only duplication left is the frozen RecordV8 itself, which must not share code with the live model

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-10-11T20:59:18+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

a migration run, set-status calls and doc/skill edits; no code to restructure
