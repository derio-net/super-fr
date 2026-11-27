<!-- fr:journal-schema=4 -->
# Journal: 2026-11-27-queue-followups

<!-- fr:journal kind=discovery scope=plan id=p1-cmd-due-list-feeds-existing-probe created=2026-11-27T15:06:48+00:00 phase=1 -->
### p1-cmd-due-list-feeds-existing-probe · discovery · The command's close-out due list only decides which live close-out sessions are asked about (phase 1)

`drive_pass` computes `due` itself from `snap.queue_records`, so a queue-landed batch is
started without the command's change. The command's `due` list (triage_batch_cmd ~:4640)
feeds `_existing`, `_collected_reads` and `closeout_waits`; its test therefore uses a live
close-out tab (recorded, not redispatched) to tell the two apart.

<!-- fr:journal kind=decision scope=plan id=p1-planned-at-uses-plan-clock created=2026-11-27T15:06:48+00:00 phase=1 -->
### p1-planned-at-uses-plan-clock · decision · planned_at is stamped with the clock `Pacer.plan` used, not the clock at record_summary (phase 1)

`deadline_repos` reads the window (planned_at, now]. Stamping the later record_summary time
would drop a deadline that fell between the plan and its record. `Pacer.plan` keeps its
`now` in `_planning_at`, and `record_summary` stamps it (falling back to the clock).

<!-- fr:journal kind=decision scope=plan id=p1-wave-hold-only-when-collecting created=2026-11-27T15:06:48+00:00 phase=1 -->
### p1-wave-hold-only-when-collecting · decision · The R6 `held` action is emitted only for a wave that has a due member to collect (phase 1)

A wave whose members are all not yet due starts nothing anyway; emitting `held` there would
add an action to every single-batch pass inside the fallback window (and break
test_no_closeout_before_the_release_commit_or_the_fallback). The held line names each
blocker as `<id> (not due|unverified|ledger unread)`. No existing assertion changed.

<!-- fr:journal kind=decision scope=plan id=p1-docs-updated created=2026-11-27T15:06:48+00:00 phase=1 -->
### p1-docs-updated · decision · fr-wave-driver.md describes the new close-out timing and the probe's classification (phase 1)

The conflict-probe paragraph no longer says stamps and generated files count as conflicts;
the close-out step says a queue-landed batch is ready at once, the wave waits for every
member and names them, and a deadline wakes a quiet paced pass. Four other covering pages
got `reviewed` stamps (fr-triage, index, herdr-control-sessions, cli reference).

<!-- fr:journal kind=discovery scope=plan id=p1-fast-tier-selects-nearly-everything created=2026-11-27T15:06:48+00:00 phase=1 -->
### p1-fast-tier-selects-nearly-everything · discovery · The --fr-scope fast tier selected about the whole suite for this phase and ran at ~17 tests/min here (phase 1)

The changes reach batch_drive.py, triage_batch_cmd.py and docs/ (which selects every
own_artifacts test), so `--fr-scope origin/main -n 2` selected roughly the full suite; at host
load ~20 it ran ~290 tests in 17 minutes and was stopped. The touched test files and their
neighbours were run instead (18 files, 862 passed; advisory, like the fast tier); CI is this
repo's tests evidence.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-11-27T15:06:48+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

a one-expression change (repo names lower-cased) with nothing around it to tidy

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t2 created=2026-11-27T15:06:48+00:00 phase=1 -->
### no-refactor-p1-t2 · discovery · no-refactor-because P1.T2 (phase 1)

the classification is one small helper beside trial_conflicts; ruff format only dropped the except parentheses

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-11-27T15:06:48+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

tidied in T6: the per-repo queue-landed set became batch_drive.queue_landed_by_repo, shared with the pacer's deadline_repos

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-11-27T15:06:48+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

the blockers were first joined strings and split back; refactored to (id, why) tuples, and the key renamed wave_key after mypy caught a shadowed `key`

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-11-27T15:06:48+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

deadline_repos reuses queue_landed_by_repo, closeout_event, LANDED and parse_aware; nothing left duplicated

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-27T15:20:51+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · Board watch plans with deadline_repos but never stamps planned_at, so a passed deadline makes every board pass partial (phase 1)

Raised by the phase 1 reviewer; verified against the code before acting.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-27T15:20:51+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · Waveless batches share the (repo, None) key, so one not-due waveless batch blocks unrelated ones (phase 1)

Raised by the phase 1 reviewer; verified against the code before acting.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-11-27T15:20:51+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · plan_overlap_report groups by exact repo, so the case-insensitive overlaps() fix is unreachable from the real caller (phase 1)

Raised by the phase 1 reviewer; verified against the code before acting.

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-11-27T15:20:51+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · The command's due list used unscoped queue_landed instead of the repo-scoped set (phase 1)

Raised by the phase 1 reviewer; verified against the code before acting.

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-11-27T15:20:51+00:00 phase=1 state=open review_scope=in -->
### p1-r5 · finding [open] (reviewer: in scope) · R6 blockers ignored closeout_hold/gated/hand/live members; edge-case and probe cache-key tests missing (phase 1)

Raised by the phase 1 reviewer; verified against the code before acting.

<!-- fr:journal kind=finding scope=plan id=p1-r6 created=2026-11-27T15:20:51+00:00 phase=1 state=open review_scope=out -->
### p1-r6 · finding [open] (reviewer: out of scope) · wave_overlap.py:75 compares repo_name exactly, the same case bug as #1695 in a sibling module (phase 1)

Raised by the phase 1 reviewer; verified against the code before acting.

<!-- fr:journal kind=review scope=plan id=review-p1 created=2026-11-27T15:20:51+00:00 phase=1 -->
### review-p1 · review · phase 1 code review: 6 findings (5 in, 1 out) (phase 1)

A dispatched reviewer read spec, plan 01.yaml and the phase diff (plan_overlap, batch_merge, batch_drive, probe, pacing, pacing_state, triage_batch_cmd and tests). Raised p1-r1..p1-r6; R4's stage swap, R7's window and fail-open parse, and the acceptance refs checked fine. Each in-scope finding was verified and fixed with a test in 39184141e; p1-r6 is out of scope.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-27T15:20:51+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: Board watch plans with deadline_repos but never stamps planned_at, so a passed deadline makes every board pass partial (phase 1)

Pacer.plan passes no deadline repos when board=True; test_triage_pacer.py::test_the_board_watch_plans_no_closeout_deadline (39184141e).

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-27T15:20:51+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: Waveless batches share the (repo, None) key, so one not-due waveless batch blocks unrelated ones (phase 1)

_can_hold_wave is false for a waveless batch; test_a_waveless_batch_not_due_holds_no_other_waveless_batch (39184141e).

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-11-27T15:20:51+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: plan_overlap_report groups by exact repo, so the case-insensitive overlaps() fix is unreachable from the real caller (phase 1)

grouped by lower-cased repo, ignore globs unioned over spellings; test_the_report_pairs_two_spellings_of_one_repo (39184141e).

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-11-27T15:20:51+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: The command's due list used unscoped queue_landed instead of the repo-scoped set (phase 1)

uses queue_landed_by_repo(...).get(repo); test_another_repo_s_queue_landing_does_not_make_a_batch_due (39184141e).

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-11-27T15:20:51+00:00 phase=1 state=fixed resolves=p1-r5 -->
### p1-r5-resolved · finding [fixed] · resolves p1-r5: R6 blockers ignored closeout_hold/gated/hand/live members; edge-case and probe cache-key tests missing (phase 1)

all blockers go through _can_hold_wave; parametrised blocking tests, queue_landed_by_repo test, probe cache-key cases for generated/mirrors (39184141e).

<!-- fr:journal kind=finding scope=plan id=p1-r6-resolved created=2026-11-27T15:20:51+00:00 phase=1 state=open resolves=p1-r6 out_of_scope=true -->
### p1-r6-resolved · finding [out-of-scope] · resolves p1-r6: wave_overlap.py:75 compares repo_name exactly, the same case bug as #1695 in a sibling module (phase 1)

Not caused by this change: wave_overlap.py predates it and the spec scopes R8 to plan_overlap; repo_name there is already lower-cased at its source in most paths.
