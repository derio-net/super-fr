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

<!-- fr:journal kind=decision scope=plan id=p2-waits-at-every-first-reader created=2026-11-27T15:35:38+00:00 phase=2 -->
### p2-waits-at-every-first-reader · decision · R2's waits is passed wherever a first label would read as approved, not only in settle_approvals (phase 2)

A Waiting PR records nothing, so the drive's live snapshot (`judge_approval` in
triage_batch_cmd's queue read) would otherwise judge it `First`, which `is_approved`
admits to the queue. The snapshot, `views.fact_approvals` and `lanes` (the board's
"delivered: approve it" line) all compute waits with `approval.conflict_waits`, so a
Waiting PR is never a queue member and the board never asks for its label.

<!-- fr:journal kind=decision scope=plan id=p2-waiting-said-once-per-process created=2026-11-27T15:35:38+00:00 phase=2 -->
### p2-waiting-said-once-per-process · decision · The Waiting line is said once per (repo, PR, head) through a module-level set by default (phase 2)

`settle_approvals(said=...)` takes the set; its default is a module-level set, so the
long-lived drive process says it once per head with no change in triage_batch_cmd
(8293 of 8300 lines). Tests pass their own set.

<!-- fr:journal kind=discovery scope=plan id=p2-fast-tier created=2026-11-27T15:35:38+00:00 phase=2 -->
### p2-fast-tier · discovery · The --fr-scope fast tier again selected about the whole suite and was stopped; touched and neighbouring files were run instead (phase 2)

`uv run pytest --fr-scope origin/main -n 2 -q --no-cov` reached about 1% in roughly
eight minutes on this loaded host and was stopped by its own PIDs. Run instead, all green:
test_triage_approval, test_merge_train_* (approval, label_board, gate, base_rules,
commands, forge_seams, red_decision, red_phrase, safety_smoke), test_triage_readiness*,
test_operator_entries_lineage, test_tripwire_forge_writes, test_tripwire_approval_label_prose,
test_triage_board_*, test_wave_queue_operator_*, test_triage_batch_board, test_triage_kanban*,
test_tripwire_triage_board_columns, test_opencode_rendered_readiness, test_triage_batch_drive*,
test_import_direction and test_tripwire_module_budget (1,391 tests). Advisory; CI is this
repo's tests evidence. test_merge_train_gate's LabelForge fake gained the comment methods
(the void now comments), and a real-policy `forge.comments: off` test was added there.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t1 created=2026-11-27T15:35:38+00:00 phase=2 -->
### no-refactor-p2-t1 · discovery · no-refactor-because P2.T1 (phase 2)

the end of an approval is one shared helper (_ended/_end) for both settle functions; the cmd's voided set now comes from settle_approvals' removed set, which dropped a repo_of map and an import

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t2 created=2026-11-27T15:35:38+00:00 phase=2 -->
### no-refactor-p2-t2 · discovery · no-refactor-because P2.T2 (phase 2)

conflict_waits/view_waits is the one R2 test, shared by settle_approvals, the drive's live snapshot, fact_approvals and lanes; nothing duplicated left

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t3 created=2026-11-27T15:35:38+00:00 phase=2 -->
### no-refactor-p2-t3 · discovery · no-refactor-because P2.T3 (phase 2)

ended_by_label is one small helper read by readiness and views; nothing to tidy around it

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t4 created=2026-11-27T15:35:38+00:00 phase=2 -->
### no-refactor-p2-t4 · discovery · no-refactor-because P2.T4 (phase 2)

_comments_off moved beside _labels_off and re-exported; the test fakes gained the comment methods on the base _Forge instead of a parallel fake

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-11-27T15:46:18+00:00 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · needs_you's Waiting skip is redundant with conflict_at, so the R2 board test passes without the change (phase 2)

Raised by the phase 2 reviewer; verified against the code before acting.

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-11-27T15:46:18+00:00 phase=2 state=open review_scope=in -->
### p2-r2 · finding [open] (reviewer: in scope) · lanes.py's Waiting exclusion from the Reviewer lane has no test (phase 2)

Raised by the phase 2 reviewer; verified against the code before acting.

<!-- fr:journal kind=finding scope=plan id=p2-r3 created=2026-11-27T15:46:18+00:00 phase=2 state=open review_scope=in -->
### p2-r3 · finding [open] (reviewer: in scope) · Waiting's said-once used a module-global set, the reverse of the plan (phase 2)

Raised by the phase 2 reviewer; verified against the code before acting.

<!-- fr:journal kind=review scope=plan id=review-p2 created=2026-11-27T15:46:18+00:00 phase=2 -->
### review-p2 · review · phase 2 code review: 3 minor findings, no correctness defect (phase 2)

A dispatched reviewer read spec, plan 02.yaml and the phase 2 diff (approval, operator_entries, readiness, views, lanes, batch_drive readers, triage_batch_cmd). It traced R1's ended event through _live_index/reaches/_pinned_ids and the entry translation, R2's Waiting through every reader (admission, drive, board, lanes, needs_you), and R3's ordering and trusted-marker suppression, and found them correct. Raised p2-r1..p2-r3 (test gaps and a global set): two fixed in 67ba3f6db, p2-r1 refuted.

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-11-27T15:46:18+00:00 phase=2 state=refuted resolves=p2-r1 -->
### p2-r1-resolved · finding [refuted] · resolves p2-r1: needs_you's Waiting skip is redundant with conflict_at, so the R2 board test passes without the change (phase 2)

Waiting needs a ConflictEvent at the head AND a conflicting read; conflict_at needs only the event, so every Waiting input already has conflict_at set. No reachable snapshot distinguishes them; a test would need an impossible patched snapshot. The skip stays as a statement of R2's intent.

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-11-27T15:46:18+00:00 phase=2 state=fixed resolves=p2-r2 -->
### p2-r2-resolved · finding [fixed] · resolves p2-r2: lanes.py's Waiting exclusion from the Reviewer lane has no test (phase 2)

test_triage_board_lanes.py::test_deliver_done_labelled_and_waiting_on_a_real_conflict_is_no_reviewer_lane, fails without the exclusion (67ba3f6db).

<!-- fr:journal kind=finding scope=plan id=p2-r3-resolved created=2026-11-27T15:46:18+00:00 phase=2 state=fixed resolves=p2-r3 -->
### p2-r3-resolved · finding [fixed] · resolves p2-r3: Waiting's said-once used a module-global set, the reverse of the plan (phase 2)

default is a fresh set; the driver holds _waiting_said and passes it; test_a_wait_is_said_each_call_by_default_and_once_per_set_the_driver_keeps (67ba3f6db).

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r1 created=2026-11-27T16:07:42+00:00 state=open review_scope=in -->
### l-docs-accuracy-r1 · finding [open] (reviewer: in scope) · fr-wave-driver.md said a generated block is never a conflict in the probe; it is one when the repo declares no mirrors

Raised by the lens reviewer; verified against the code before acting.

<!-- fr:journal kind=finding scope=plan id=l-errors-r1 created=2026-11-27T16:07:42+00:00 state=open review_scope=in -->
### l-errors-r1 · finding [open] (reviewer: in scope) · void_comment discarded _comments_off's reason, so an unreadable policy skipped the comment with no log

Raised by the lens reviewer; verified against the code before acting.

<!-- fr:journal kind=finding scope=plan id=l-errors-r2 created=2026-11-27T16:07:42+00:00 state=open review_scope=in -->
### l-errors-r2 · finding [open] (reviewer: in scope) · R1's unread-labels guard was dead for real clients, which returned [] for a missing key, so a degraded read would end a live approval

Raised by the lens reviewer; verified against the code before acting.

<!-- fr:journal kind=finding scope=plan id=l-errors-r3 created=2026-11-27T16:07:42+00:00 state=open review_scope=out -->
### l-errors-r3 · finding [open] (reviewer: out of scope) · trial_conflicts classified before abort_merge, so a GitError there skipped the abort

Raised by the lens reviewer; verified against the code before acting.

<!-- fr:journal kind=review scope=plan id=lens-review-1 created=2026-11-27T16:07:42+00:00 -->
### lens-review-1 · review · lens review: docs-accuracy 1, errors 3, security none, tests none

One dispatched reviewer per lens over the whole diff from 00809f90 with the shape file. docs-accuracy found one false page claim; errors found a silent comment skip, a dead unread-labels guard and an abort ordering; security found the R2 wait no wider than operator decision q1 and no other issue; tests found every requirement proven by a test that would fail without it. All four findings fixed in a8569adbc.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r1-resolved created=2026-11-27T16:07:42+00:00 state=fixed resolves=l-docs-accuracy-r1 -->
### l-docs-accuracy-r1-resolved · finding [fixed] · resolves l-docs-accuracy-r1: fr-wave-driver.md said a generated block is never a conflict in the probe; it is one when the repo declares no mirrors

Page reworded: only a reviewed: stamp is unconditionally resolved; a generated block or whole file only with mirrors: (a8569adbc).

<!-- fr:journal kind=finding scope=plan id=l-errors-r1-resolved created=2026-11-27T16:07:42+00:00 state=fixed resolves=l-errors-r1 -->
### l-errors-r1-resolved · finding [fixed] · resolves l-errors-r1: void_comment discarded _comments_off's reason, so an unreadable policy skipped the comment with no log

void_comment says 'voided without a comment: <reason>'; test_no_comment_when_comments_are_off_or_the_policy_is_unreadable_and_it_says_why (a8569adbc).

<!-- fr:journal kind=finding scope=plan id=l-errors-r2-resolved created=2026-11-27T16:07:42+00:00 state=fixed resolves=l-errors-r2 -->
### l-errors-r2-resolved · finding [fixed] · resolves l-errors-r2: R1's unread-labels guard was dead for real clients, which returned [] for a missing key, so a degraded read would end a live approval

both pr_view clients return labels None for a missing key (fr.ghclient.pr_label_names); verification/labels.py copes; test_gh_/test_rest_pr_view_reads_a_missing_labels_key_as_unread (a8569adbc).

<!-- fr:journal kind=finding scope=plan id=l-errors-r3-resolved created=2026-11-27T16:07:42+00:00 state=open resolves=l-errors-r3 out_of_scope=true -->
### l-errors-r3-resolved · finding [out-of-scope] · resolves l-errors-r3: trial_conflicts classified before abort_merge, so a GitError there skipped the abort

Reviewer's tag kept (out). The abort ordering was hardened anyway in a8569adbc (classification in try/finally so abort_merge always runs; test_a_failing_conflict_read_still_aborts_the_merge_and_propagates); the scratch worktree was already removed in every case.
