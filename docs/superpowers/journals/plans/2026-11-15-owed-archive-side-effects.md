<!-- fr:journal-schema=4 -->
# Journal: 2026-11-15-owed-archive-side-effects

<!-- fr:journal kind=discovery scope=plan id=p1-closeout-owed-fake-gh created=2026-11-15T19:41:29+00:00 phase=1 -->
### p1-closeout-owed-fake-gh · discovery · tests/scenarios/closeout-owed's recording gh needed an `issue view` answer (phase 1)

Closing an owed issue now reads the one issue (R14), so the existing closeout-owed
scenario's fake gh gained `gh issue view` (record with author and state). Without it
the scenario's discharge step failed on an unexpected call.

<!-- fr:journal kind=discovery scope=plan id=p1-existing-manual-owed-test-contradicted-r7 created=2026-11-15T19:41:29+00:00 phase=1 -->
### p1-existing-manual-owed-test-contradicted-r7 · discovery · a held single-plan archive used to record and file its manual-phase owed entry (phase 1)

test_archive_owed's manual-phase test pinned the behaviour R7 removes (single-plan
refusal wrote and filed owed). It now covers `--all` off the default branch (records and
files), a single-plan refusal (writes nothing) and the default-branch hold (prints
`would record owed`). The --branch hold shares _write_manual_owed, so it is covered by
the same default-branch check.

<!-- fr:journal kind=discovery scope=plan id=p1-followups-test-pinned-old-contract created=2026-11-15T19:41:29+00:00 phase=1 -->
### p1-followups-test-pinned-old-contract · discovery · test_archive_followups pinned follow-ups running after a refused follower move (phase 1)

R7 says a refusal runs no follow-up, so that test now asserts no follow-up and that the
staged plan move was undone. The first CI run also showed two unrelated concurrency
tests (tests/unit/test_hooks_worktree.py) failing on a loaded shard; they pass here.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-11-15T19:41:29+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

the helper moved verbatim into fr.git; docs.load keeps a thin wrapper, nothing else to tidy

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t2 created=2026-11-15T19:41:29+00:00 phase=1 -->
### no-refactor-p1-t2 · discovery · no-refactor-because P1.T2 (phase 1)

the lookup result type was introduced in this task and is already minimal

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-11-15T19:41:29+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

a one-call swap of the listing for view_issue_record; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-11-15T19:41:29+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

scenario scripts share one sourced world builder (_owed_world.sh) from the start

<!-- fr:journal kind=review scope=plan id=review-p1 created=2026-11-15T20:21:10+00:00 phase=1 -->
### review-p1 · review · Phase 1 code review (R7-R9, R12-R14, fr.git helper): 4 in scope, 2 out (phase 1)

Independent reviewer read the post-change files for diff 3b8e06ddb..a46fbfa52 against spec R7-R9 and R12-R14.
Found sound: label-filtered owed lookup failing closed (R12), UnsupportedForgeOperation keeping owed in the journal (R13),
close by number with OPEN and ownership checks (R14), the fr.git helper move, and both scenario fixtures.

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-15T20:21:10+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · R7 undo covers only ArchiveError inside archive_plan_dir; a later failure (sweep, repair) or an OSError in the move leaves the plan move staged (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-15T20:21:10+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · No test for R8 preview or R9 recording on the --branch hold path (_archive_branch_plan) (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-11-15T20:21:10+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · Refusal-runs-no-follow-up spied only for Exit(2); the exception path has a loose assertion over an empty log (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-11-15T20:21:10+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · _owed_step's could-not-file warning lacks soft_wrap, so Rich can split the phrase the scenario greps (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-11-15T20:21:10+00:00 phase=1 state=open review_scope=out -->
### p1-r5 · finding [open] (reviewer: out of scope) · head_on_default_branch treats an unreadable default ref as off-default; GitUnavailableError from it is uncaught in _write_manual_owed (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1-r6 created=2026-11-15T20:21:10+00:00 phase=1 state=open review_scope=out -->
### p1-r6 · finding [open] (reviewer: out of scope) · _forge_lists_issues keys on detect_backend()=='github' rather than the adapter's own capability (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-15T20:21:10+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: R7 undo covers only ArchiveError inside archive_plan_dir; a later failure (sweep, repair) or an OSError in the move leaves the plan move staged (phase 1)

6ef3b862f + 7f0861b71: undoing_staged_moves wraps the whole single-plan span from _with_followups; archive_plan_dir undoes on BaseException. Tests inject failures at _report_sweep, spec_archive_sweep, _repair_in_passing and an OSError in _archive_run, asserting byte-identical status and index; all failed before the fix.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-15T20:21:10+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: No test for R8 preview or R9 recording on the --branch hold path (_archive_branch_plan) (phase 1)

a97bd8d94: two --branch tests in test_archive_owed.py — default branch prints 'would record owed' with tree and index unchanged; off default the owed entry is recorded.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-11-15T20:21:10+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: Refusal-runs-no-follow-up spied only for Exit(2); the exception path has a loose assertion over an empty log (phase 1)

6ef3b862f: parametrized spy test (RuntimeError, SettingsError) asserts _after_moves never runs and the tree is unchanged; test_a_placement_refusal_writes_nothing now asserts exit_code == 2 and 'Nothing was written'.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-11-15T20:21:10+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: _owed_step's could-not-file warning lacks soft_wrap, so Rich can split the phrase the scenario greps (phase 1)

6ef3b862f: soft_wrap=True on the could-not-file-owed print.

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-11-15T20:21:10+00:00 phase=1 state=open resolves=p1-r5 out_of_scope=true -->
### p1-r5-resolved · finding [out-of-scope] · resolves p1-r5: head_on_default_branch treats an unreadable default ref as off-default; GitUnavailableError from it is uncaught in _write_manual_owed (phase 1)

Spec R3 deliberately counts an unreadable default ref as off the default branch; the uncaught GitUnavailableError path predates this change (git absent fails every archive command).

<!-- fr:journal kind=finding scope=plan id=p1-r6-resolved created=2026-11-15T20:21:10+00:00 phase=1 state=open resolves=p1-r6 out_of_scope=true -->
### p1-r6-resolved · finding [out-of-scope] · resolves p1-r6: _forge_lists_issues keys on detect_backend()=='github' rather than the adapter's own capability (phase 1)

_forge_lists_issues predates this change; R13 states GitHub-only listing today, and the backend-vs-adapter duplication is not introduced here.
