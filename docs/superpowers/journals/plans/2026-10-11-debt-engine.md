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

<!-- fr:journal kind=review scope=plan id=p1-review-r1 created=2026-10-11T21:27:35+00:00 phase=1 -->
### p1-review-r1 · review · phase 1 code review (skipped split, matrix 4→5, record 8→9): 7 findings (phase 1)

Independent reviewer (separate context, read-only) over 18e354b9^..4d0bae58: every matrix
and record hop, MatrixV4/RecordV8 freezing and pins, the R6 mapping, the one-write and crash
window, the status validator, the R8 surfaces, the reclassification spot-check, and test
quality. 94 targeted tests passed. Findings p1-r1..p1-r7 (five in scope, two out).
Receiving: each verified against the code; p1-r1 (closeout.py prints row.verify) and p1-r3
(matrix header) confirmed by reading, p1-r4's #363 claim confirmed live (open, refreshed
2026-10-05). p1-r2 resolved by enforcing the spec's meaning rather than amending it.

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-10-11T21:27:35+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · close-out walked line printed `--strategy None` for a row held by the spec's Verification section (phase 1)

run/closeout.py printed row.verify; holds_open_for_run also holds spec-section rows with no verify.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-10-11T21:27:35+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · walked rows without a passing walk; nothing enforced R5's "dated by its walk" (phase 1)

23 walked rows carried no walk and set-status --status walked accepted it.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-10-11T21:27:35+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · this repo's v5 matrix header still documented `skipped` (phase 1)

docs/acceptance/matrix.yaml header comment kept the old status list; the line-surgery migration never refreshed it.

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-10-11T21:27:35+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · stale notes after the split (cloud-triage-github-rest, fr-goal-phase-tiering, acceptance-nag-channels) (phase 1)

Notes still said "skipped"/"owed" where the state had moved; acceptance-nag-channels' weekly upsert was already observed (#363).

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-10-11T21:27:35+00:00 phase=1 state=open review_scope=in -->
### p1-r5 · finding [open] (reviewer: in scope) · 4→5 tests missed render-failure, crash-window report regeneration, fail-only walk, and the live-parser tripwire (phase 1)

test_migration_matrix_status_split.py lacked four edge cases.

<!-- fr:journal kind=finding scope=plan id=p1-r6 created=2026-10-11T21:27:35+00:00 phase=1 state=open review_scope=out -->
### p1-r6 · finding [open] (reviewer: out of scope) · matrix_anchors repair reads with the live parse_matrix (silently a no-op on a pre-v5 matrix) (phase 1)

Pre-existing; this change only makes it reachable, and the repair retries after the 4→5 hop.

<!-- fr:journal kind=finding scope=plan id=p1-r7 created=2026-10-11T21:27:35+00:00 phase=1 state=open review_scope=out -->
### p1-r7 · finding [open] (reviewer: out of scope) · record 8→9 reads the row's raw verify; an unmigrated v3 `post-merge` row gives a misleading refusal (phase 1)

Kind ordering migrates the matrix first; an edge case not caused by this phase.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-10-11T21:27:35+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: close-out walked line printed `--strategy None` for a row held by the spec's Verification section (phase 1)

c61bf7d6: prints the effective strategy (row verify, else spec section/shape default, else <strategy>); test for a spec-held row.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-10-11T21:27:35+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: walked rows without a passing walk; nothing enforced R5's "dated by its walk" (phase 1)

b15e9bf4/f5a990ac: walked needs a passing walk in set-status, the record engine and fr acceptance check (new --walk-at); 20 rows got walks recorded from their notes' evidence, 3 with no date moved to walk-owed.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-10-11T21:27:35+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: this repo's v5 matrix header still documented `skipped` (phase 1)

84b759a0/3de11247: header replaced with the scaffold's comment; the 4→5 rewrite swaps an exact old-template header, tested.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-10-11T21:27:35+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: stale notes after the split (cloud-triage-github-rest, fr-goal-phase-tiering, acceptance-nag-channels) (phase 1)

set-status --notes on the three rows; acceptance-nag-channels walked by #363; cloud-triage-github-rest to walk-owed for its owed comparison.

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-10-11T21:27:35+00:00 phase=1 state=fixed resolves=p1-r5 -->
### p1-r5-resolved · finding [fixed] · resolves p1-r5: 4→5 tests missed render-failure, crash-window report regeneration, fail-only walk, and the live-parser tripwire (phase 1)

84b759a0: four new hop tests and the widened tripwire.

<!-- fr:journal kind=finding scope=plan id=p1-r6-resolved created=2026-10-11T21:27:35+00:00 phase=1 state=open resolves=p1-r6 out_of_scope=true -->
### p1-r6-resolved · finding [out-of-scope] · resolves p1-r6: matrix_anchors repair reads with the live parse_matrix (silently a no-op on a pre-v5 matrix) (phase 1)

Not caused by this change (pre-existing live-parser read in matrix_anchors); a clarifying comment was added at 632a5f5c, behaviour unchanged.

<!-- fr:journal kind=finding scope=plan id=p1-r7-resolved created=2026-10-11T21:27:35+00:00 phase=1 state=open resolves=p1-r7 out_of_scope=true -->
### p1-r7-resolved · finding [out-of-scope] · resolves p1-r7: record 8→9 reads the row's raw verify; an unmigrated v3 `post-merge` row gives a misleading refusal (phase 1)

Not caused by this phase: the registry migrates the matrix before records, so the raw v3 spelling is unreachable in order.

<!-- fr:journal kind=decision scope=plan id=p2-forge-protocol created=2026-10-11T21:56:32+00:00 phase=2 -->
### p2-forge-protocol · decision · The engine asks a DebtForge protocol; the real adapter lists issues via GhClient.list_issues (phase 2)

compute() takes a DebtForge (pr_for_branch, owed_issues) or None for offline. debt/forge.py
adapts GhClient (list_issues with fields number,title,body,labels, filtered to fr:owed and
fr:awaiting-live). A forge that cannot do it raises, and compute reports the forge as
unavailable rather than failing. Phase 4 widens the adapters (R26). pr_for_branch gained
updatedAt on gh, glab, tea and the REST client.

<!-- fr:journal kind=decision scope=plan id=p2-run-branch-activity created=2026-10-11T21:56:32+00:00 phase=2 -->
### p2-run-branch-activity · decision · Run-branch activity means commits on the branch not on the default ref (phase 2)

A plain git log -1 on the run branch would see shared main history and keep every plan
active, so staleness uses the branch's commits excluding the default ref, plus the plan
dir on the default ref and the branch, plus the PR updatedAt. Run branches are found by
reading cursors' emitted.plan as raw YAML (any cursor version).

<!-- fr:journal kind=discovery scope=plan id=p2-fold-extension created=2026-10-11T21:56:32+00:00 phase=2 -->
### p2-fold-extension · discovery · fold_owed extension point for phase 3 (phase 2)

Add a field to OwedSources (journal already exists, empty) and name it in OWED_PRECEDENCE;
phase 3 fills journal with owed-entry items keyed spec:/plan:/row:.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t1 created=2026-10-11T21:56:32+00:00 phase=2 -->
### no-refactor-p2-t1 · discovery · no-refactor-because P2.T1 (phase 2)

pure model and renderers written once; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t3 created=2026-10-11T21:56:32+00:00 phase=2 -->
### no-refactor-p2-t3 · discovery · no-refactor-because P2.T3 (phase 2)

thin CLI over the engine; the digest was reduced to the shared section renderer in the same step
