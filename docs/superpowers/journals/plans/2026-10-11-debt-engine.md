<!-- fr:journal-schema=2 -->
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

<!-- fr:journal kind=review scope=plan id=p2-review-r1 created=2026-10-11T22:07:18+00:00 phase=2 -->
### p2-review-r1 · review · phase 2 code review (fr debt engine): 13 findings, all in scope (phase 2)

Independent reviewer (separate context, read-only) over ed236f30 + the mirror fix: engine against R2-R4, figures encoding, fold_owed, R1/R25 exemption, the automated security finding, and test quality. 32 targeted tests passed. Receiving: p2-r1 and p2-r3 confirmed by reading engine.py:165,207 and debt_cmd.py:40; p2-r1 was reproduced by the reviewer as an arbitrary file write. All fixed in f9d21dae (193 targeted tests passed; CI is the full-suite evidence).

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-10-11T22:07:18+00:00 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · run-cursor branch reached git log / pr_for_branch unvalidated (`--output=<f>` arbitrary file write, reproduced) (phase 2)

run-cursor branch reached git log / pr_for_branch unvalidated (`--output=<f>` arbitrary file write, reproduced)

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-10-11T22:07:18+00:00 phase=2 state=open review_scope=in -->
### p2-r2 · finding [open] (reviewer: in scope) · fr debt ignored tracking: none (R4 git-only fallback) (phase 2)

fr debt ignored tracking: none (R4 git-only fallback)

<!-- fr:journal kind=finding scope=plan id=p2-r3 created=2026-10-11T22:07:18+00:00 phase=2 state=open review_scope=in -->
### p2-r3 · finding [open] (reviewer: in scope) · _forge swallowed every exception and the report claimed offline; an unreadable matrix dropped the forge (phase 2)

_forge swallowed every exception and the report claimed offline; an unreadable matrix dropped the forge

<!-- fr:journal kind=finding scope=plan id=p2-r4 created=2026-10-11T22:07:18+00:00 phase=2 state=open review_scope=in -->
### p2-r4 · finding [open] (reviewer: in scope) · owed-issue scan capped at 200 open issues with client-side label filtering: silent undercount (phase 2)

owed-issue scan capped at 200 open issues with client-side label filtering: silent undercount

<!-- fr:journal kind=finding scope=plan id=p2-r5 created=2026-10-11T22:07:18+00:00 phase=2 state=open review_scope=in -->
### p2-r5 · finding [open] (reviewer: in scope) · unescaped sources[*].why plus first-match parse_figures let a forged figures comment win (phase 2)

unescaped sources[*].why plus first-match parse_figures let a forged figures comment win

<!-- fr:journal kind=finding scope=plan id=p2-r6 created=2026-10-11T22:07:18+00:00 phase=2 state=open review_scope=in -->
### p2-r6 · finding [open] (reviewer: in scope) · StalePlan.basis said git+forge when the forge was never consulted (phase 2)

StalePlan.basis said git+forge when the forge was never consulted

<!-- fr:journal kind=finding scope=plan id=p2-r7 created=2026-10-11T22:07:18+00:00 phase=2 state=open review_scope=in -->
### p2-r7 · finding [open] (reviewer: in scope) · plans with no readable activity were silently omitted (phase 2)

plans with no readable activity were silently omitted

<!-- fr:journal kind=finding scope=plan id=p2-r8 created=2026-10-11T22:07:18+00:00 phase=2 state=open review_scope=in -->
### p2-r8 · finding [open] (reviewer: in scope) · merge_evidence fetch_error never surfaced in sources (phase 2)

merge_evidence fetch_error never surfaced in sources

<!-- fr:journal kind=finding scope=plan id=p2-r9 created=2026-10-11T22:07:18+00:00 phase=2 state=open review_scope=in -->
### p2-r9 · finding [open] (reviewer: in scope) · engine hard-coded a status set beside DEBT_STATUSES (against R1) (phase 2)

engine hard-coded a status set beside DEBT_STATUSES (against R1)

<!-- fr:journal kind=finding scope=plan id=p2-r10 created=2026-10-11T22:07:18+00:00 phase=2 state=open review_scope=in -->
### p2-r10 · finding [open] (reviewer: in scope) · figures owed counted row: items while total excluded them (phase 2)

figures owed counted row: items while total excluded them

<!-- fr:journal kind=finding scope=plan id=p2-r11 created=2026-10-11T22:07:18+00:00 phase=2 state=open review_scope=in -->
### p2-r11 · finding [open] (reviewer: in scope) · markdown hard cut could slice the trailing marker/figures (phase 2)

markdown hard cut could slice the trailing marker/figures

<!-- fr:journal kind=finding scope=plan id=p2-r12 created=2026-10-11T22:07:18+00:00 phase=2 state=open review_scope=in -->
### p2-r12 · finding [open] (reviewer: in scope) · digest lost open_rows' oldest-first order (phase 2)

digest lost open_rows' oldest-first order

<!-- fr:journal kind=finding scope=plan id=p2-r13 created=2026-10-11T22:07:18+00:00 phase=2 state=open review_scope=in -->
### p2-r13 · finding [open] (reviewer: in scope) · weak/missing tests: tautological assert, no ClientDebtForge tests, updatedAt only as None (phase 2)

weak/missing tests: tautological assert, no ClientDebtForge tests, updatedAt only as None

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-10-11T22:07:18+00:00 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: run-cursor branch reached git log / pr_for_branch unvalidated (`--output=<f>` arbitrary file write, reproduced) (phase 2)

f9d21dae: _run_branches drops a branch starting with '-' or failing git check-ref-format --branch; --end-of-options in _last_commit; test proves no file written and forge never asked.

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-10-11T22:07:18+00:00 phase=2 state=fixed resolves=p2-r2 -->
### p2-r2-resolved · finding [fixed] · resolves p2-r2: fr debt ignored tracking: none (R4 git-only fallback) (phase 2)

f9d21dae: tracking none gives git-only with that reason; tested.

<!-- fr:journal kind=finding scope=plan id=p2-r3-resolved created=2026-10-11T22:07:18+00:00 phase=2 state=fixed resolves=p2-r3 -->
### p2-r3-resolved · finding [fixed] · resolves p2-r3: _forge swallowed every exception and the report claimed offline; an unreadable matrix dropped the forge (phase 2)

f9d21dae: _forge returns (forge, why), compute takes forge_why; slug from the origin remote.

<!-- fr:journal kind=finding scope=plan id=p2-r4-resolved created=2026-10-11T22:07:18+00:00 phase=2 state=fixed resolves=p2-r4 -->
### p2-r4-resolved · finding [fixed] · resolves p2-r4: owed-issue scan capped at 200 open issues with client-side label filtering: silent undercount (phase 2)

f9d21dae: PartialIssuesError at the cap; the source reports read with a partial note (the adapter has no label filter).

<!-- fr:journal kind=finding scope=plan id=p2-r5-resolved created=2026-10-11T22:07:18+00:00 phase=2 state=fixed resolves=p2-r5 -->
### p2-r5-resolved · finding [fixed] · resolves p2-r5: unescaped sources[*].why plus first-match parse_figures let a forged figures comment win (phase 2)

f9d21dae: why escaped through _cell; parse_figures takes the last match; forged-why test.

<!-- fr:journal kind=finding scope=plan id=p2-r6-resolved created=2026-10-11T22:07:18+00:00 phase=2 state=fixed resolves=p2-r6 -->
### p2-r6-resolved · finding [fixed] · resolves p2-r6: StalePlan.basis said git+forge when the forge was never consulted (phase 2)

f9d21dae: basis git+forge only when pr_for_branch returned.

<!-- fr:journal kind=finding scope=plan id=p2-r7-resolved created=2026-10-11T22:07:18+00:00 phase=2 state=fixed resolves=p2-r7 -->
### p2-r7-resolved · finding [fixed] · resolves p2-r7: plans with no readable activity were silently omitted (phase 2)

f9d21dae: listed with idle_days=None; HEAD fallback when no default ref.

<!-- fr:journal kind=finding scope=plan id=p2-r8-resolved created=2026-10-11T22:07:18+00:00 phase=2 state=fixed resolves=p2-r8 -->
### p2-r8-resolved · finding [fixed] · resolves p2-r8: merge_evidence fetch_error never surfaced in sources (phase 2)

f9d21dae: fetch failure shown in sources['git'].

<!-- fr:journal kind=finding scope=plan id=p2-r9-resolved created=2026-10-11T22:07:18+00:00 phase=2 state=fixed resolves=p2-r9 -->
### p2-r9-resolved · finding [fixed] · resolves p2-r9: engine hard-coded a status set beside DEBT_STATUSES (against R1) (phase 2)

f9d21dae: LISTED_STATUSES = DEBT_STATUSES | {walked, manual}.

<!-- fr:journal kind=finding scope=plan id=p2-r10-resolved created=2026-10-11T22:07:18+00:00 phase=2 state=fixed resolves=p2-r10 -->
### p2-r10-resolved · finding [fixed] · resolves p2-r10: figures owed counted row: items while total excluded them (phase 2)

f9d21dae: owed = counted total, owed_items = list length.

<!-- fr:journal kind=finding scope=plan id=p2-r11-resolved created=2026-10-11T22:07:18+00:00 phase=2 state=fixed resolves=p2-r11 -->
### p2-r11-resolved · finding [fixed] · resolves p2-r11: markdown hard cut could slice the trailing marker/figures (phase 2)

f9d21dae: truncate content first, append the tail once; near-limit sweep test.

<!-- fr:journal kind=finding scope=plan id=p2-r12-resolved created=2026-10-11T22:07:18+00:00 phase=2 state=fixed resolves=p2-r12 -->
### p2-r12-resolved · finding [fixed] · resolves p2-r12: digest lost open_rows' oldest-first order (phase 2)

f9d21dae: debt rows sorted oldest origin first.

<!-- fr:journal kind=finding scope=plan id=p2-r13-resolved created=2026-10-11T22:07:18+00:00 phase=2 state=fixed resolves=p2-r13 -->
### p2-r13-resolved · finding [fixed] · resolves p2-r13: weak/missing tests: tautological assert, no ClientDebtForge tests, updatedAt only as None (phase 2)

f9d21dae: assert fixed; test_debt_forge.py; populated updatedAt fixtures; origin/<branch>, raising pr_for_branch, complete-unmerged, --stale-days 0.

<!-- fr:journal kind=decision scope=plan id=p3-owed-entry-shape created=2026-10-11T23:07:15+00:00 phase=3 -->
### p3-owed-entry-shape · decision · owed entries carry what/why/how/owed_key as body lines; filed_as is a header token (phase 3)

Per spec §E the owed key rides in the body (`owed_key: <key>`), validated by
OWED_KEY_RE (spec:<slug>#step<n> | plan:<name>#p<n> | row:<id> | issue:<o/r#n>).
The record engine refuses an owed item without a well-formed key (so `fr journal
add --kind owed` and records agree) and the journal structure validator reports
one. `filed_as=<ref>` is a header token on an `open` resolution record, validated
by TRACKED_BY_RE. Resolution records naming an owed id stay kind `finding`;
open_finding_ids skips them and open_owed_ids folds them. An owed entry resolves
only to `fixed` (discharge); other states are refused.

<!-- fr:journal kind=decision scope=plan id=p3-journal-stamp-on-create created=2026-10-11T23:07:15+00:00 phase=3 -->
### p3-journal-stamp-on-create · decision · new journals are written stamped at the journal kind's current version (phase 3)

With journal at 2, an unstamped journal reads as 1 and would be stale on arrival,
so appended_journal_text (new file) and `fr plan create`'s seeded journal write
`<!-- fr:journal-schema=2 -->` before the title (journal_header). The 1->2 hop is
stamp-only and refuses (byte-identical) a v1 journal carrying an owed entry; the
validator reports the same. Fixture tests that indexed journal lines shifted by one.

<!-- fr:journal kind=decision scope=plan id=p3-hold-semantics created=2026-10-11T23:07:15+00:00 phase=3 -->
### p3-hold-semantics · decision · the outcome hold applies with --force and on --all; closeout outcome also takes --spec (phase 3)

R19's hold (archive.outcome_hold) runs after the archive gate in every mode:
--branch prints it as the held reason, a plan dir exits 2 even with --force, --all
skips the plan. Plans with no run cursor still need a way out, so `fr closeout
outcome` accepts `--spec <path>` as the alternative to `--run <id>`; the hold prints
`--run` when a cursor created the plan, else `--spec`. A spec that is cross-repo or
unresolvable is never held (nothing to read).

<!-- fr:journal kind=decision scope=plan id=p3-manual-owed-when-only-manual-holds created=2026-10-11T23:07:15+00:00 phase=3 -->
### p3-manual-owed-when-only-manual-holds · decision · manual-phase owed entries are written only when unticked manual phases are all that holds the plan (phase 3)

unticked_manual_phases returns the manual phases only when every archive_gate
blocker names one of them, so a plan still open or unmerged on agentic phases owes
nothing yet. Entries are appended (staged, not committed, as archive's other
journal writes) and filed by the same owed step, idempotently by id and owed key.

<!-- fr:journal kind=decision scope=plan id=p3-owed-issue-trust created=2026-10-11T23:07:15+00:00 phase=3 -->
### p3-owed-issue-trust · decision · discharge and reuse act only on this repo's own fr:owed issue carrying the entry's marker (phase 3)

Coordinator security constraint. `fr journal resolve` normalises filed_as against
the identity archive filed under (archive_cmd._repo_slug); a ref naming another
owner/repo or a URL on another host/repo is never closed, nor is a same-repo issue
lacking fr:owed or the `<!-- fr-owed:<key> -->` marker of that entry: the command is
printed with a warning naming the mismatch. The number is ASCII digits; the repo is
a plain owner/repo with no leading dash; comment and title start with fixed text.
Archive's reuse lookup only reuses an own-authored, fr:owed-labelled issue in this
repo whose last line is the marker.

<!-- fr:journal kind=discovery scope=plan id=p3-debt-discharged-suppresses-issue created=2026-10-11T23:07:15+00:00 phase=3 -->
### p3-debt-discharged-suppresses-issue · discovery · fr debt drops a discharged key's still-open fr:owed issue (phase 3)

journal_owed returns the discharged keys; compute filters issue items with those
keys before fold_owed, so a discharge whose close failed (forge down) does not
linger as debt. sources gains a `journals` entry naming any unreadable journal.

<!-- fr:journal kind=discovery scope=plan id=p3-r16-triage-set-left-to-phase-5 created=2026-10-11T23:07:15+00:00 phase=3 -->
### p3-r16-triage-set-left-to-phase-5 · discovery · R16's triage set for fr:owed is not built in phase 3 (phase 3)

This phase adds FR_OWED to fr/labels.py and files issues with it. The triage check
set that keeps fr:owed issues out of the ranked backlog (like fr:awaiting-live) is
triage work, which the plan-shape decision puts in phase 5.

<!-- fr:journal kind=discovery scope=plan id=p3-closeout-on-default-branch created=2026-10-11T23:07:15+00:00 phase=3 -->
### p3-closeout-on-default-branch · discovery · closeout outcome on the default branch leaves the journal uncommitted, and the spec sweep then crashes on it (phase 3)

The record engine refuses to commit on the default branch, so `fr closeout outcome`
run on main writes the spec journal untracked; the next `fr archive` spec sweep's
`git mv` of that journal raises an unhandled ArchiveError (pre-existing in
spec_archive_sweep for any untracked journal). A close-out runs on the housekeeping
branch the brief brings up, which the closeout-owed scenario does.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t1 created=2026-10-11T23:07:15+00:00 phase=3 -->
### no-refactor-p3-t1 · discovery · no-refactor-because P3.T1 (phase 3)

model additions and a stamp-only hop written once; open_owed_ids reuses the one fold (_fold_full) rather than a second walk, so nothing was duplicated to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t2 created=2026-10-11T23:07:15+00:00 phase=3 -->
### no-refactor-p3-t2 · discovery · no-refactor-because P3.T2 (phase 3)

a pure parser and a thin verb over the record engine; no duplication to remove

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t3 created=2026-10-11T23:07:15+00:00 phase=3 -->
### no-refactor-p3-t3 · discovery · no-refactor-because P3.T3 (phase 3)

owed filing sits beside the open-ends filer on purpose (its own marker grammar, label and trust rule); merging the two for two callers was judged churn, and the shared pieces (resolution_entry, append_journal_entry) are already one

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t4 created=2026-10-11T23:07:15+00:00 phase=3 -->
### no-refactor-p3-t4 · discovery · no-refactor-because P3.T4 (phase 3)

one close helper and one engine source; the security follow-up tightened it in place

<!-- fr:journal kind=review scope=plan id=p3-review-r1 created=2026-10-11T23:36:23+00:00 phase=3 -->
### p3-review-r1 · review · phase 3 code review (owed actions, journal 1→2): 11 findings (phase 3)

Independent reviewer (separate context, read-only) over the phase-3 commits: journal 1→2, the owed fold and every other finding-folding caller, closeout outcome, the archive hold in every mode, owed filing, the two automated security notices on journal_cmd.py, the executor-reported ArchiveError, tests and the scenario. 77 targeted tests passed. Receiving: p3-r1 confirmed by reading archive_cmd._repo_slug/resolve_identity (matrix keys win over the remote); p3-r3 was the executor-reported crash. p3-r8 decided (exit-0 --branch convention kept). Fixes in c080d4e8 (395 targeted tests + 2 scenarios passed; CI is the full-suite evidence).

<!-- fr:journal kind=finding scope=plan id=p3-r1 created=2026-10-11T23:36:23+00:00 phase=3 state=open review_scope=in -->
### p3-r1 · finding [open] (reviewer: in scope) · owed close/file 'own repo' identity came from committed matrix.yaml org/repo, not the origin remote — a commit could redirect forge writes (phase 3)

owed close/file 'own repo' identity came from committed matrix.yaml org/repo, not the origin remote — a commit could redirect forge writes

<!-- fr:journal kind=finding scope=plan id=p3-r2 created=2026-10-11T23:36:23+00:00 phase=3 state=open review_scope=in -->
### p3-r2 · finding [open] (reviewer: in scope) · Test Plan section ended at a '# ' line inside a code fence (and could start at a fenced heading), silently dropping steps (phase 3)

Test Plan section ended at a '# ' line inside a code fence (and could start at a fenced heading), silently dropping steps

<!-- fr:journal kind=finding scope=plan id=p3-r3 created=2026-10-11T23:36:23+00:00 phase=3 state=open review_scope=in -->
### p3-r3 · finding [open] (reviewer: in scope) · an outcome recorded on the default branch stayed uncommitted; the spec sweep's unguarded _archive_journal raised an unhandled ArchiveError mid-move (phase 3)

an outcome recorded on the default branch stayed uncommitted; the spec sweep's unguarded _archive_journal raised an unhandled ArchiveError mid-move

<!-- fr:journal kind=finding scope=plan id=p3-r4 created=2026-10-11T23:36:23+00:00 phase=3 state=open review_scope=in -->
### p3-r4 · finding [open] (reviewer: in scope) · resolve's close check accepted the marker on any line and skipped the author check (phase 3)

resolve's close check accepted the marker on any line and skipped the author check

<!-- fr:journal kind=finding scope=plan id=p3-r5 created=2026-10-11T23:36:23+00:00 phase=3 state=open review_scope=in -->
### p3-r5 · finding [open] (reviewer: in scope) · untrusted filed_as ref echoed raw (control characters) (phase 3)

untrusted filed_as ref echoed raw (control characters)

<!-- fr:journal kind=finding scope=plan id=p3-r6 created=2026-10-11T23:36:23+00:00 phase=3 state=open review_scope=in -->
### p3-r6 · finding [open] (reviewer: in scope) · owed discharge through a step record never closed the issue (phase 3)

owed discharge through a step record never closed the issue

<!-- fr:journal kind=finding scope=plan id=p3-r7 created=2026-10-11T23:36:23+00:00 phase=3 state=open review_scope=in -->
### p3-r7 · finding [open] (reviewer: in scope) · closeout outcome could append an owed entry to an unstamped (v1) archived journal (phase 3)

closeout outcome could append an owed entry to an unstamped (v1) archived journal

<!-- fr:journal kind=finding scope=plan id=p3-r8 created=2026-10-11T23:36:23+00:00 phase=3 state=open review_scope=in -->
### p3-r8 · finding [open] (reviewer: in scope) · --branch hold exits 0 though the plan step said exit 2 (phase 3)

--branch hold exits 0 though the plan step said exit 2

<!-- fr:journal kind=finding scope=plan id=p3-r9 created=2026-10-11T23:36:23+00:00 phase=3 state=open review_scope=in -->
### p3-r9 · finding [open] (reviewer: in scope) · empty Test Plan gave a step with empty text; outcome_command printed a non-pasteable 'a | b | c' line (phase 3)

empty Test Plan gave a step with empty text; outcome_command printed a non-pasteable 'a | b | c' line

<!-- fr:journal kind=finding scope=plan id=p3-r10 created=2026-10-11T23:36:23+00:00 phase=3 state=open review_scope=out -->
### p3-r10 · finding [open] (reviewer: out of scope) · a refused archive still writes/stages manual-phase owed entries and files issues, even on the default branch (phase 3)

a refused archive still writes/stages manual-phase owed entries and files issues, even on the default branch

<!-- fr:journal kind=finding scope=plan id=p3-r11 created=2026-10-11T23:36:23+00:00 phase=3 state=open review_scope=out -->
### p3-r11 · finding [open] (reviewer: out of scope) · _existing_owed's 200-issue listing cap can miss an existing marker and file a duplicate (phase 3)

_existing_owed's 200-issue listing cap can miss an existing marker and file a duplicate

<!-- fr:journal kind=finding scope=plan id=p3-r1-resolved created=2026-10-11T23:36:23+00:00 phase=3 state=fixed resolves=p3-r1 -->
### p3-r1-resolved · finding [fixed] · resolves p3-r1: owed close/file 'own repo' identity came from committed matrix.yaml org/repo, not the origin remote — a commit could redirect forge writes (phase 3)

c080d4e8: every owed forge write takes the repo from remote.origin.url only; matrix disagreement refuses and prints the command; mallory/x vs acme/widgets tests.

<!-- fr:journal kind=finding scope=plan id=p3-r2-resolved created=2026-10-11T23:36:23+00:00 phase=3 state=fixed resolves=p3-r2 -->
### p3-r2-resolved · finding [fixed] · resolves p3-r2: Test Plan section ended at a '# ' line inside a code fence (and could start at a fenced heading), silently dropping steps (phase 3)

c080d4e8: line-by-line scan tracking ``` and ~~~ fences for heading and end; both cases tested.

<!-- fr:journal kind=finding scope=plan id=p3-r3-resolved created=2026-10-11T23:36:23+00:00 phase=3 state=fixed resolves=p3-r3 -->
### p3-r3-resolved · finding [fixed] · resolves p3-r3: an outcome recorded on the default branch stayed uncommitted; the spec sweep's unguarded _archive_journal raised an unhandled ArchiveError mid-move (phase 3)

c080d4e8: archive refuses a dirty/untracked spec journal before any move; closeout outcome warns when uncommitted; the sweep reports an unmovable journal as a note. Tested, no traceback, unchanged tree.

<!-- fr:journal kind=finding scope=plan id=p3-r4-resolved created=2026-10-11T23:36:23+00:00 phase=3 state=fixed resolves=p3-r4 -->
### p3-r4-resolved · finding [fixed] · resolves p3-r4: resolve's close check accepted the marker on any line and skipped the author check (phase 3)

c080d4e8: one shared predicate (viewer-authored, fr:owed, numeric, last line is the marker) for reuse and close.

<!-- fr:journal kind=finding scope=plan id=p3-r5-resolved created=2026-10-11T23:36:23+00:00 phase=3 state=fixed resolves=p3-r5 -->
### p3-r5-resolved · finding [fixed] · resolves p3-r5: untrusted filed_as ref echoed raw (control characters) (phase 3)

c080d4e8: filed_as must be printable ASCII; non-printables echoed via repr.

<!-- fr:journal kind=finding scope=plan id=p3-r6-resolved created=2026-10-11T23:36:23+00:00 phase=3 state=fixed resolves=p3-r6 -->
### p3-r6-resolved · finding [fixed] · resolves p3-r6: owed discharge through a step record never closed the issue (phase 3)

c080d4e8: a step record's fixed resolution of an owed entry is refused, pointing to fr journal resolve.

<!-- fr:journal kind=finding scope=plan id=p3-r7-resolved created=2026-10-11T23:36:23+00:00 phase=3 state=fixed resolves=p3-r7 -->
### p3-r7-resolved · finding [fixed] · resolves p3-r7: closeout outcome could append an owed entry to an unstamped (v1) archived journal (phase 3)

c080d4e8: appending an owed entry restamps a sub-2 journal in the same write; tested.

<!-- fr:journal kind=finding scope=plan id=p3-r8-resolved created=2026-10-11T23:36:23+00:00 phase=3 state=fixed resolves=p3-r8 -->
### p3-r8-resolved · finding [fixed] · resolves p3-r8: --branch hold exits 0 though the plan step said exit 2 (phase 3)

Decision: keep --branch's existing 'held:' exit-0 convention (it reports holds for every plan it touched); the plan step's 'exit 2' applies to plan-dir mode, which does exit 2. Comment added at the test and --force help states it does not lift the Test Plan hold (c080d4e8).

<!-- fr:journal kind=finding scope=plan id=p3-r9-resolved created=2026-10-11T23:36:23+00:00 phase=3 state=fixed resolves=p3-r9 -->
### p3-r9-resolved · finding [fixed] · resolves p3-r9: empty Test Plan gave a step with empty text; outcome_command printed a non-pasteable 'a | b | c' line (phase 3)

c080d4e8: placeholder step text; one pasteable line per alternative.

<!-- fr:journal kind=finding scope=plan id=p3-r10-resolved created=2026-10-11T23:36:23+00:00 phase=3 state=open resolves=p3-r10 out_of_scope=true -->
### p3-r10-resolved · finding [out-of-scope] · resolves p3-r10: a refused archive still writes/stages manual-phase owed entries and files issues, even on the default branch (phase 3)

Out of scope: R22's design (owed entries are written when archive holds a plan); not a defect of this phase's code.

<!-- fr:journal kind=finding scope=plan id=p3-r11-resolved created=2026-10-11T23:36:23+00:00 phase=3 state=open resolves=p3-r11 out_of_scope=true -->
### p3-r11-resolved · finding [out-of-scope] · resolves p3-r11: _existing_owed's 200-issue listing cap can miss an existing marker and file a duplicate (phase 3)

Out of scope: the same cap already bounds the existing open-ends dedup (archive_followups); not introduced here.

<!-- fr:journal kind=decision scope=plan id=p4-adapter-surface created=2026-10-12T00:23:24+00:00 phase=4 -->
### p4-adapter-surface · decision · glab implements issue ops, create_pr, open_pr_for_head, edit_pr, viewer_login; tea only the issue ops and viewer_login (phase 4)

R26 says an operation the forge has is implemented, else named unsupported. tea's draft PR support is unverified, so create_pr, open_pr_for_head and edit_pr stay UnsupportedForgeOperation on tea (archive-pr then warns and exits 0). Added beyond the spec list: edit_pr (needed to refresh the one draft PR), viewer_login on glab/tea (author trust), ListingCapped (no silent caps). The glab and tea commands are recorded-command doubles, not live captures; a live walk is owed.

<!-- fr:journal kind=decision scope=plan id=p4-trust-model created=2026-10-12T00:23:24+00:00 phase=4 -->
### p4-trust-model · decision · debt issue edits only issues authored by the viewer or the workflow bot; archive-pr reuses only an open same-repo PR (phase 4)

A body marker alone selects nothing. Marker must be its own line, author in {viewer, github-actions[bot], github-actions, app/github-actions}; others are named in a ::warning:: and left alone. open_pr_for_head now returns same_repo (REST checks head.repo.full_name; glab compares source/target project ids); a fork PR on the same head name is never reused or edited. Identity comes from archive_followups.owed_identity (allow_nested for GitLab subgroups).

<!-- fr:journal kind=decision scope=plan id=p4-no-published-detail created=2026-10-12T00:23:24+00:00 phase=4 -->
### p4-no-published-detail · decision · bodies carry fixed source categories only; all echoed forge text is redacted and control-stripped (phase 4)

render.source_category maps each source to a fixed category (forge error, matrix unreadable, fetch failed, offline, tracking none, partial: listing cap reached); detailed reasons stay in the terminal. render.redact strips URL credentials, ghp_/gho_/github_pat_/glpat- tokens and home paths; debt_cmd._clean also removes control characters. A failed `fr archive` is published as fixed text, its stderr only in the job log.

<!-- fr:journal kind=discovery scope=plan id=p4-refresh-ci-rewrites-whole-file created=2026-10-12T00:23:24+00:00 phase=4 -->
### p4-refresh-ci-rewrites-whole-file · discovery · --refresh-ci replaces an fr-scaffolded file wholesale (phase 4)

Local edits to a recognised GitHub/Gitea file are overwritten (the command says to review the diff). This repo's own workflow, which installs fr from the checkout and pins actions by sha, was therefore edited by hand rather than refreshed.

<!-- fr:journal kind=discovery scope=plan id=p4-push-refusal-warns created=2026-10-12T00:23:24+00:00 phase=4 -->
### p4-push-refusal-warns · discovery · a refused push of the sweep branch is a warning, exit 0, like a refused PR (phase 4)

The weekly job must not go red for a token that may not push; both remedies are named in the ::warning::.

<!-- fr:journal kind=finding scope=plan id=p4-ci1-shared-names created=2026-10-12T00:23:24+00:00 phase=4 state=fixed review_scope=in -->
### p4-ci1-shared-names · finding [fixed] (reviewer: in scope) · viewer_login, open_pr_for_head and the glab flag gate changed meaning for existing callers (phase 4)

Implementing viewer_login on glab/tea broke triage's unsupported contract, and extending open_pr_for_head's dict broke the CI-evidence readers. Fixed with separate methods (authenticated_login, open_pr_in_repo) and the old ones restored; glab's check_argv now allows --source-branch/--target-branch and the boolean --draft/--yes, which its value-only allow-list would have refused live.

<!-- fr:journal kind=finding scope=plan id=p4-ci2-coverage-tables created=2026-10-12T00:23:24+00:00 phase=4 state=fixed review_scope=in -->
### p4-ci2-coverage-tables · finding [fixed] (reviewer: in scope) · new public glab helper and client methods were missing from the host-trust coverage tables (phase 4)

edit_issue added to test_glab's table and the new RealGlabClient methods to test_forge_host_trust's call list; the two-call close stays in the client so the one-host-per-helper table holds.

<!-- fr:journal kind=finding scope=plan id=p4-ci3-stale-tests created=2026-10-12T00:23:24+00:00 phase=4 state=fixed review_scope=in -->
### p4-ci3-stale-tests · finding [fixed] (reviewer: in scope) · own tests and the scaffold tests still asserted the old shapes (phase 4)

debt-ops tests updated for author fields and open_pr_in_repo (and now run glab's argv through check_argv); test_acceptance_init asserts the fr debt steps; test_archive_owed sets a git identity via -c because CI has none.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t1 created=2026-10-12T00:23:24+00:00 phase=4 -->
### no-refactor-p4-t1 · discovery · no-refactor-because P4.T1 (phase 4)

adapter methods are thin one-call wrappers over each forge's existing helpers; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t2 created=2026-10-12T00:23:24+00:00 phase=4 -->
### no-refactor-p4-t2 · discovery · no-refactor-because P4.T2 (phase 4)

debt_cmd gained helpers (_trusted, _clean, _number) as written; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t3 created=2026-10-12T00:23:24+00:00 phase=4 -->
### no-refactor-p4-t3 · discovery · no-refactor-because P4.T3 (phase 4)

selection and body rendering live in debt/sweep.py, git steps in small helpers; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t4 created=2026-10-12T00:23:24+00:00 phase=4 -->
### no-refactor-p4-t4 · discovery · no-refactor-because P4.T4 (phase 4)

scaffold templates share one render_workflow; goldens regenerated, nothing to clean

<!-- fr:journal kind=review scope=plan id=p4-review-r1 created=2026-10-12T00:39:40+00:00 phase=4 -->
### p4-review-r1 · review · phase 4 code review (weekly issue, archive PR, adapters, scaffolds): 12 findings (phase 4)

Independent reviewer (separate context, read-only) over c080d4e8..b3817943: R26 adapters on four clients, fr debt issue, archive-pr, scaffolds and --refresh-ci, the three automated security notices on debt_cmd.py (selection trust, authorization, data exposure, glab gate), and test quality. 206 targeted tests passed. Receiving: p4-r2 confirmed by reading the workflow's workflow-level permissions and checkout token; p4-r1 confirmed (real_glabclient `api user` vs check_argv). Fixes in fa5bb076, be42cb30, e9098934 (729 targeted tests; CI is the full-suite evidence). Owed: a live walk of the glab/tea paths (recorded doubles and a shape-mirror fixture only).

<!-- fr:journal kind=finding scope=plan id=p4-r1 created=2026-10-12T00:39:40+00:00 phase=4 state=open review_scope=in -->
### p4-r1 · finding [open] (reviewer: in scope) · glab authenticated_login hit check_argv's projects/-only api gate: GitLab trusted no issue and duplicated it weekly (phase 4)

glab authenticated_login hit check_argv's projects/-only api gate: GitLab trusted no issue and duplicated it weekly

<!-- fr:journal kind=finding scope=plan id=p4-r2 created=2026-10-12T00:39:40+00:00 phase=4 state=open review_scope=in -->
### p4-r2 · finding [open] (reviewer: in scope) · workflow-level write permissions and the FR_DEBT_TOKEN checkout applied to every PR/push run (PAT persisted while branch code ran) (phase 4)

workflow-level write permissions and the FR_DEBT_TOKEN checkout applied to every PR/push run (PAT persisted while branch code ran)

<!-- fr:journal kind=finding scope=plan id=p4-r3 created=2026-10-12T00:39:40+00:00 phase=4 state=open review_scope=in -->
### p4-r3 · finding [open] (reviewer: in scope) · issue listing newest-first and capped at 200: the oldest debt issue fell past the cap (phase 4)

issue listing newest-first and capped at 200: the oldest debt issue fell past the cap

<!-- fr:journal kind=finding scope=plan id=p4-r4 created=2026-10-12T00:39:40+00:00 phase=4 state=open review_scope=in -->
### p4-r4 · finding [open] (reviewer: in scope) · tea listing was one page clamped to 50: a silent cap (phase 4)

tea listing was one page clamped to 50: a silent cap

<!-- fr:journal kind=finding scope=plan id=p4-r5 created=2026-10-12T00:39:40+00:00 phase=4 state=open review_scope=in -->
### p4-r5 · finding [open] (reviewer: in scope) · archive-pr failure paths left staged moves carried back by the finally switch; untracked docs swept in (phase 4)

archive-pr failure paths left staged moves carried back by the finally switch; untracked docs swept in

<!-- fr:journal kind=finding scope=plan id=p4-r6 created=2026-10-12T00:39:40+00:00 phase=4 state=open review_scope=in -->
### p4-r6 · finding [open] (reviewer: in scope) · push refusal and all forge errors were given GitHub PR-permission remedies (phase 4)

push refusal and all forge errors were given GitHub PR-permission remedies

<!-- fr:journal kind=finding scope=plan id=p4-r7 created=2026-10-12T00:39:40+00:00 phase=4 state=open review_scope=in -->
### p4-r7 · finding [open] (reviewer: in scope) · GITHUB_TOKEN cannot call /user: a warning every scheduled run (phase 4)

GITHUB_TOKEN cannot call /user: a warning every scheduled run

<!-- fr:journal kind=finding scope=plan id=p4-r8 created=2026-10-12T00:39:40+00:00 phase=4 state=open review_scope=in -->
### p4-r8 · finding [open] (reviewer: in scope) · ev.ref_error echoed unredacted; non-numeric forge numbers crashed filter_issues_by_body (phase 4)

ev.ref_error echoed unredacted; non-numeric forge numbers crashed filter_issues_by_body

<!-- fr:journal kind=finding scope=plan id=p4-r9 created=2026-10-12T00:39:40+00:00 phase=4 state=open review_scope=in -->
### p4-r9 · finding [open] (reviewer: in scope) · riskiest paths only exercised against doubles that bypassed the gates (phase 4)

riskiest paths only exercised against doubles that bypassed the gates

<!-- fr:journal kind=finding scope=plan id=p4-r10 created=2026-10-12T00:39:40+00:00 phase=4 state=open review_scope=in -->
### p4-r10 · finding [open] (reviewer: in scope) · _held tracebacks on a missing plan; ``` broke the PR fence; _clean missed bidi/format characters (phase 4)

_held tracebacks on a missing plan; ``` broke the PR fence; _clean missed bidi/format characters

<!-- fr:journal kind=finding scope=plan id=p4-r11 created=2026-10-12T00:39:40+00:00 phase=4 state=open review_scope=out -->
### p4-r11 · finding [open] (reviewer: out of scope) · debt steps lacked if: always(), so failing-row weeks never updated the issue (phase 4)

debt steps lacked if: always(), so failing-row weeks never updated the issue

<!-- fr:journal kind=finding scope=plan id=p4-r12 created=2026-10-12T00:39:40+00:00 phase=4 state=open review_scope=out -->
### p4-r12 · finding [open] (reviewer: out of scope) · Gitea/GitLab scaffolds give the debt steps no forge or push credentials (phase 4)

Gitea/GitLab scaffolds give the debt steps no forge or push credentials

<!-- fr:journal kind=finding scope=plan id=p4-r1-resolved created=2026-10-12T00:39:40+00:00 phase=4 state=fixed resolves=p4-r1 -->
### p4-r1-resolved · finding [fixed] · resolves p4-r1: glab authenticated_login hit check_argv's projects/-only api gate: GitLab trusted no issue and duplicated it weekly (phase 4)

be42cb30: check_argv allows exactly `api user`; real-_run_glab test; lookalikes still refused.

<!-- fr:journal kind=finding scope=plan id=p4-r2-resolved created=2026-10-12T00:39:40+00:00 phase=4 state=fixed resolves=p4-r2 -->
### p4-r2-resolved · finding [fixed] · resolves p4-r2: workflow-level write permissions and the FR_DEBT_TOKEN checkout applied to every PR/push run (PAT persisted while branch code ran) (phase 4)

fa5bb076: separate debt job (schedule or inputs.debt) holds write perms and the token; matrix job contents:read with persist-credentials false; templates and goldens split.

<!-- fr:journal kind=finding scope=plan id=p4-r3-resolved created=2026-10-12T00:39:40+00:00 phase=4 state=fixed resolves=p4-r3 -->
### p4-r3-resolved · finding [fixed] · resolves p4-r3: issue listing newest-first and capped at 200: the oldest debt issue fell past the cap (phase 4)

be42cb30: oldest-first listing (REST sort=created&direction=asc; glab order_by=created_at&sort=asc).

<!-- fr:journal kind=finding scope=plan id=p4-r4-resolved created=2026-10-12T00:39:40+00:00 phase=4 state=fixed resolves=p4-r4 -->
### p4-r4-resolved · finding [fixed] · resolves p4-r4: tea listing was one page clamped to 50: a silent cap (phase 4)

be42cb30: pages until an empty page; ListingCapped at the cap; paging test with a shape-mirror fixture.

<!-- fr:journal kind=finding scope=plan id=p4-r5-resolved created=2026-10-12T00:39:40+00:00 phase=4 state=fixed resolves=p4-r5 -->
### p4-r5-resolved · finding [fixed] · resolves p4-r5: archive-pr failure paths left staged moves carried back by the finally switch; untracked docs swept in (phase 4)

e9098934: entry check includes untracked docs; reset --hard + clean -fdq -- docs before switching back; failed switch-back warned.

<!-- fr:journal kind=finding scope=plan id=p4-r6-resolved created=2026-10-12T00:39:40+00:00 phase=4 state=fixed resolves=p4-r6 -->
### p4-r6-resolved · finding [fixed] · resolves p4-r6: push refusal and all forge errors were given GitHub PR-permission remedies (phase 4)

e9098934: push-specific remedy; settings remedy only for a recognised 403/not-permitted error; generic category otherwise.

<!-- fr:journal kind=finding scope=plan id=p4-r7-resolved created=2026-10-12T00:39:40+00:00 phase=4 state=fixed resolves=p4-r7 -->
### p4-r7-resolved · finding [fixed] · resolves p4-r7: GITHUB_TOKEN cannot call /user: a warning every scheduled run (phase 4)

e9098934: under GITHUB_ACTIONS a 403 viewer lookup is the workflow bot, no warning.

<!-- fr:journal kind=finding scope=plan id=p4-r8-resolved created=2026-10-12T00:39:40+00:00 phase=4 state=fixed resolves=p4-r8 -->
### p4-r8-resolved · finding [fixed] · resolves p4-r8: ev.ref_error echoed unredacted; non-numeric forge numbers crashed filter_issues_by_body (phase 4)

be42cb30/e9098934: ref_error cleaned; non-digit numbers skipped.

<!-- fr:journal kind=finding scope=plan id=p4-r9-resolved created=2026-10-12T00:39:40+00:00 phase=4 state=fixed resolves=p4-r9 -->
### p4-r9-resolved · finding [fixed] · resolves p4-r9: riskiest paths only exercised against doubles that bypassed the gates (phase 4)

e9098934: real `fr archive` subprocess integration tests; glab ops through the real argv gate; tea paging fixture (shape mirror, noted).

<!-- fr:journal kind=finding scope=plan id=p4-r10-resolved created=2026-10-12T00:39:40+00:00 phase=4 state=fixed resolves=p4-r10 -->
### p4-r10-resolved · finding [fixed] · resolves p4-r10: _held tracebacks on a missing plan; ``` broke the PR fence; _clean missed bidi/format characters (phase 4)

e9098934: _held tolerant; backticks escaped; bidi/format characters in _CONTROL.

<!-- fr:journal kind=finding scope=plan id=p4-r11-resolved created=2026-10-12T00:39:40+00:00 phase=4 state=open resolves=p4-r11 out_of_scope=true -->
### p4-r11-resolved · finding [out-of-scope] · resolves p4-r11: debt steps lacked if: always(), so failing-row weeks never updated the issue (phase 4)

Out of scope (pre-existing in the digest step); the p4-r2 job split incidentally removes the dependency.

<!-- fr:journal kind=finding scope=plan id=p4-r12-resolved created=2026-10-12T00:39:40+00:00 phase=4 state=open resolves=p4-r12 out_of_scope=true -->
### p4-r12-resolved · finding [out-of-scope] · resolves p4-r12: Gitea/GitLab scaffolds give the debt steps no forge or push credentials (phase 4)

Out of scope: pre-existing in the shell upsert; Gitea archive-pr degrades to a named Unsupported warning, exit 0.

<!-- fr:journal kind=decision scope=plan id=p5-set-apart created=2026-10-12T01:25:50+00:00 phase=5 -->
### p5-set-apart · decision · one is_set_apart predicate replaces is_awaiting_live in exclusions (phase 5)

is_debt_digest, is_owed and awaiting-live are excluded together wherever is_awaiting_live was (unranked, unplaced, no severity, tiers, parked, features); batch_awaits_live and stale dispatch keep the awaiting-live predicate only.

<!-- fr:journal kind=decision scope=plan id=p5-figures-display-only created=2026-10-12T01:25:50+00:00 phase=5 -->
### p5-figures-display-only · decision · figures cleaned to ints before display or storage (phase 5)

fr.triage.debt.clean_figures drops every non-int count and non-alphanumeric status key from a forge-supplied figures block; all rendered text goes through esc.

<!-- fr:journal kind=discovery scope=plan id=p5-panel-note created=2026-10-12T01:25:50+00:00 phase=5 -->
### p5-panel-note · discovery · v1 previous snapshot gives no trend and a note (phase 5)

SnapshotDiff.debt_before is None when the previous snapshot predates schema 2; the panel says so, and separately notes the skipped split when a previous figure carries skipped that the new one lacks.

<!-- fr:journal kind=finding scope=plan id=p5-f1-ci-shown-as-debt created=2026-10-12T01:25:50+00:00 phase=5 state=fixed review_scope=in -->
### p5-f1-ci-shown-as-debt · finding [fixed] (reviewer: in scope) · the Acceptance debt line listed ci rows as debt (phase 5)

Panel showed every status incl. ci/scheduled. Now only DEBT_STATUSES are on the debt line; walked and manual are on a separate Listed, not debt line; asserted in test_triage_debt_panel.py.

<!-- fr:journal kind=finding scope=plan id=p5-f2-wrong-badge created=2026-10-12T01:25:50+00:00 phase=5 state=fixed review_scope=in -->
### p5-f2-wrong-badge · finding [fixed] (reviewer: in scope) · both repo badges read 36, matching neither repo (phase 5)

The fixture hardcoded total 36; the badge is each repo's own figures total, and a test builds a real DebtReport and checks the badge equals debt_total() across two repos with different totals.

<!-- fr:journal kind=finding scope=plan id=p5-f3-spoofable-digest created=2026-10-12T01:25:50+00:00 phase=5 state=fixed review_scope=in -->
### p5-f3-spoofable-digest · finding [fixed] (reviewer: in scope) · anyone could spoof a repo's debt figures by pasting the marker (phase 5)

Facts schema 9 adds Issue.author (collect now asks for it). A digest counts only from the workflow bot (BOT_LOGINS, now shared with fr debt issue), the viewer or a pr_authors login (claim_trusted); the oldest trusted one wins; others are untrusted_digests in check and render as untrusted digest ignored (#n), never their figures and still ordinary issues. Collect keeps a digest's body to 64 KiB (the figures sit at its end, past the 2000 BODY_LIMIT).

<!-- fr:journal kind=finding scope=plan id=p5-f4-unbounded-figures-decode created=2026-10-12T01:25:50+00:00 phase=5 state=fixed review_scope=in -->
### p5-f4-unbounded-figures-decode · finding [fixed] (reviewer: in scope) · parse_figures decoded unbounded forge text (phase 5)

parse_figures (the shared decoder) now refuses a body past 64 KiB or a base64 payload past 8 KiB before decoding, and a decoded value that is not a flat dict (one level of nested count dicts allowed) of ints and short strings.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p5-t1 created=2026-10-12T01:25:50+00:00 phase=5 -->
### no-refactor-p5-t1 · discovery · no-refactor-because P5.T1 (phase 5)

is_set_apart folded the three exclusions into one predicate used by check, render and views; nothing further to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p5-t2 created=2026-10-12T01:25:50+00:00 phase=5 -->
### no-refactor-p5-t2 · discovery · no-refactor-because P5.T2 (phase 5)

panel and snapshot code was written once against the shared fr.triage.debt helpers; nothing to clean

<!-- fr:journal kind=review scope=plan id=p5-review-r1 created=2026-10-12T01:38:30+00:00 phase=5 -->
### p5-review-r1 · review · phase 5 code review (triage debt/owed sets, Debt panel, snapshot v2, facts 9): 4 findings (phase 5)

Independent reviewer (separate context, read-only) over 71d3ab6a, d394a9b6: R14-R16, the three automated security notices on triage/debt.py, the facts 8→9 bump and its readers, and test quality. 22 targeted tests passed. It drove the UI itself (a copy of the capture script run by absolute path into its own directory) and opened both fresh screenshots, covering every declared state and the expand interaction at both limits. Security: (a) spoofed figures and (b) unbounded decode verified fixed; (c) the 'authentication bypass' via pr_authors refuted: pr_authors is read from the default branch's .fr/triage.yaml (collect.py:63,735), the same claim-marker trust set (model.py:495-502), a missing author fails closed, and facts.json is a local cache that never rides the state ref. Fixes in eb680131 and 3087f287 (210 targeted tests).

<!-- fr:journal kind=discovery scope=plan id=p5-security-pr-authors-refuted created=2026-10-12T01:38:30+00:00 phase=5 -->
### p5-security-pr-authors-refuted · discovery · automated 'authentication-bypass' notice on triage/debt.py refuted: pr_authors is operator-curated default-branch config (phase 5)

See p5-review-r1. Residual, accepted: trust is on who opened the digest, not who last edited its body, so a collaborator with write/triage access can edit a trusted digest's body. That is write-level trust, the same as fr debt issue.

<!-- fr:journal kind=finding scope=plan id=p5-r1 created=2026-10-12T01:38:30+00:00 phase=5 state=open review_scope=in -->
### p5-r1 · finding [open] (reviewer: in scope) · spec §C, plan P5.T1.S1 and the debt.py docstring said no facts bump, but facts moved 8→9 with Issue.author (phase 5)

spec §C, plan P5.T1.S1 and the debt.py docstring said no facts bump, but facts moved 8→9 with Issue.author

<!-- fr:journal kind=finding scope=plan id=p5-r2 created=2026-10-12T01:38:30+00:00 phase=5 state=open review_scope=in -->
### p5-r2 · finding [open] (reviewer: in scope) · the debt.py docstring claimed parity with fr debt issue's trust, but triage also trusts pr_authors (phase 5)

the debt.py docstring claimed parity with fr debt issue's trust, but triage also trusts pr_authors

<!-- fr:journal kind=finding scope=plan id=p5-r3 created=2026-10-12T01:38:30+00:00 phase=5 state=open review_scope=in -->
### p5-r3 · finding [open] (reviewer: in scope) · clean_figures dropped acceptance_available, so a no-matrix digest rendered a false zero (phase 5)

clean_figures dropped acceptance_available, so a no-matrix digest rendered a false zero

<!-- fr:journal kind=finding scope=plan id=p5-r4 created=2026-10-12T01:38:30+00:00 phase=5 state=open review_scope=in -->
### p5-r4 · finding [open] (reviewer: in scope) · manual_open was shown under Plan debt but not counted in the badge (phase 5)

manual_open was shown under Plan debt but not counted in the badge

<!-- fr:journal kind=finding scope=plan id=p5-r1-resolved created=2026-10-12T01:38:30+00:00 phase=5 state=fixed resolves=p5-r1 -->
### p5-r1-resolved · finding [fixed] · resolves p5-r1: spec §C, plan P5.T1.S1 and the debt.py docstring said no facts bump, but facts moved 8→9 with Issue.author (phase 5)

eb680131 amends spec §C (the contract) with the bump and the trust rule; 3087f287 fixes the docstring.

<!-- fr:journal kind=finding scope=plan id=p5-r2-resolved created=2026-10-12T01:38:30+00:00 phase=5 state=fixed resolves=p5-r2 -->
### p5-r2-resolved · finding [fixed] · resolves p5-r2: the debt.py docstring claimed parity with fr debt issue's trust, but triage also trusts pr_authors (phase 5)

Kept deliberately (the claim-marker trust set, read from the default branch); spec §C (eb680131) and the docstring (3087f287) now say so.

<!-- fr:journal kind=finding scope=plan id=p5-r3-resolved created=2026-10-12T01:38:30+00:00 phase=5 state=fixed resolves=p5-r3 -->
### p5-r3-resolved · finding [fixed] · resolves p5-r3: clean_figures dropped acceptance_available, so a no-matrix digest rendered a false zero (phase 5)

3087f287: carried through; renders 'Acceptance: matrix unavailable'; tested.

<!-- fr:journal kind=finding scope=plan id=p5-r4-resolved created=2026-10-12T01:38:30+00:00 phase=5 state=fixed resolves=p5-r4 -->
### p5-r4-resolved · finding [fixed] · resolves p5-r4: manual_open was shown under Plan debt but not counted in the badge (phase 5)

3087f287: moved to the Listed, not debt line ('counted under Owed'); test asserts badge = sum of visible debt lines.
