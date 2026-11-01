<!-- fr:journal-schema=3 -->
# Journal: 2026-11-01-auto-migrate-own-commit

<!-- fr:journal kind=decision scope=plan id=p1-run-start-takes-missing-mode-as-worktree created=2026-11-01T16:19:06+00:00 phase=1 -->
### p1-run-start-takes-missing-mode-as-worktree · decision · fr run start now reads a marker with no mode as worktree, like the edit gate (phase 1)

`marker_mode_holds` moved into `fr.isolation.marker` and now treats a missing `mode` as
`worktree` (the edit gate's reading, fr-isolation-decision.sh). `fr run start` used to refuse
such a marker as "unknown mode None"; it now accepts it when the checkout is a real linked
worktree. One implementation for both callers, as P1.T1.S3 asked. No test pinned the old refusal.

<!-- fr:journal kind=decision scope=plan id=p1-commit-notice-carries-sha created=2026-11-01T16:19:06+00:00 phase=1 -->
### p1-commit-notice-carries-sha · decision · CommitOutcome gained an optional sha for the gate's one-line commit notice (phase 1)

`commit_paths` fills `CommitOutcome.sha` with `git rev-parse --short HEAD` after a successful
commit (None when git cannot name it). The gate emits
`fr: migrated and committed <n> artifact(s): <subject> (<sha>)`, which both nag hooks relay by
prefix. In-memory only; no artifact shape moved.

<!-- fr:journal kind=discovery scope=plan id=p1-devcontainer-exec-toplevel created=2026-11-01T16:19:06+00:00 phase=1 -->
### p1-devcontainer-exec-toplevel · discovery · Inside a devcontainer, a workspace validates only if the container sees the marker's toplevel (phase 1)

`valid_workspace` requires the marker's recorded `toplevel` to equal the checkout's real
toplevel, exactly as the edit gate does (R2). `fr isolation exec` in devcontainer mode runs in
a container whose mount path may differ from the host path the marker records, in which case
the gate refuses there (the old behaviour, with the new `carry it:` line) rather than
committing. Host-worktree and external modes are unaffected. Not verified live here.

<!-- fr:journal kind=finding scope=plan id=p1-full-suite-red-preexisting created=2026-11-01T16:19:06+00:00 phase=1 state=open review_scope=out -->
### p1-full-suite-red-preexisting · finding [open] (reviewer: out of scope) · The local full suite is red on 13 tests that also fail against origin/main's fr source (phase 1)

Full suite under a host load average of 100-300 (another session's suite in the other slot):
13 failed, 13601 passed, 126 skipped in 3h03m. The failures are
tests/integration/test_install_atomic.py (5: install lock / atomic replacement timing),
tests/unit/test_run_evidence_visual.py (7) and
tests/unit/test_records_commit.py::test_a_record_commit_gives_up_on_a_stuck_index_lock_quickly.
None of those files or the code they exercise is touched by this phase. Re-run with
`PYTHONPATH=<git archive origin/main packages/fr/src>`, test_a_named_script_that_was_run_passes
and the stuck-index-lock test still fail, so they are not caused by this branch (time- or
load-sensitive). The PR's CI run is the clean evidence.
The log's final `exit=1` line was appended from testslot.sh's own `end rc=1` record, because the
suite was detached from its `timeout` wrapper (which would have killed it) before it finished.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t2 created=2026-11-01T16:19:06+00:00 phase=1 -->
### no-refactor-p1-t2 · discovery · no-refactor-because P1.T2 (phase 1)

classify is one new pure function beside is_interactive, which it calls; the keyword swap left nothing duplicated to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-11-01T16:19:06+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

_migrate_in_place deliberately mirrors _migrate_and_commit's refusal lines without its commit and adoption offer; folding them together would put a commit branch back into the CI path

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-11-01T16:19:06+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

the hook and nag.ts each gained one notice lookup and one reworded line; no structure to simplify

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t6 created=2026-11-01T16:19:06+00:00 phase=1 -->
### no-refactor-p1-t6 · discovery · no-refactor-because P1.T6 (phase 1)

two new scenario scripts and two registration lines; the matrix moves were made by fr acceptance set-status

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t7 created=2026-11-01T16:19:06+00:00 phase=1 -->
### no-refactor-p1-t7 · discovery · no-refactor-because P1.T7 (phase 1)

prose, mirrors and a fragment only

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-01T17:23:36+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · _ci_veto swallowed GitRefusal (not just NoRepo) and dropped the uncommitted veto (phase 1)

trigger.py:581-587: unknown git state treated as clean in the CI path.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-01T17:23:36+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · valid_workspace applied branch drift to mode: external (phase 1)

marker.py:155-163 vs fr-isolation-decision.sh:281-283, which checks drift only for worktree/empty mode.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-11-01T17:23:36+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · The opt-out refusal offered 'carry it: fr isolation up' (phase 1)

False while FR_NON_INTERACTIVE stays set (trigger.py:457-467).

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-11-01T17:23:36+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · Both nags dropped the commit notice on a partial migration (commit landed, exit 2) (phase 1)

fr-acceptance-nag.sh:30-38 and nag.ts:99-102.

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-11-01T17:23:36+00:00 phase=1 state=open review_scope=in -->
### p1-r5 · finding [open] (reviewer: in scope) · Stale docstring 'CI refuses rather than migrating' (phase 1)

tests/unit/test_migration_run_provenance.py:137.

<!-- fr:journal kind=review scope=plan id=p1-review-1 created=2026-11-01T17:23:36+00:00 phase=1 -->
### p1-review-1 · review · phase 1 code review: 5 findings (all in scope, Minor), all fixed (phase 1)

Dispatched general-purpose code reviewer (separate context, read-only against the fr workspace) over d0d7af45..613f2398. Verdict: no Critical or Important issues. 5 Minor in-scope findings p1-r1..p1-r5, each verified against the code and fixed with a test in 122dbe848. Considered-and-set-aside list in the reviewer's return (devcontainer exec toplevel mismatch fails safe; NoRepo+interactive unchanged; CI+FR_NON_INTERACTIVE migrates in place per spec precedence).

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-01T17:23:36+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: _ci_veto swallowed GitRefusal (not just NoRepo) and dropped the uncommitted veto (phase 1)

Dropped _ci_veto; the CI path calls uncommitted_veto inside the try, so a GitUnavailableError refuses. Test test_ci_refuses_when_git_cannot_say_what_is_uncommitted (red, then green).

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-01T17:23:36+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: valid_workspace applied branch drift to mode: external (phase 1)

Drift is now limited to worktree or empty mode. Test test_an_external_marker_is_never_branch_drift.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-11-01T17:23:36+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: The opt-out refusal offered 'carry it: fr isolation up' (phase 1)

carry=False on the opt-out refusal; test_fr_non_interactive_in_a_valid_workspace_refuses asserts the line is absent.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-11-01T17:23:36+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: Both nags dropped the commit notice on a partial migration (commit landed, exit 2) (phase 1)

Both relay the notice from the failure branch too. Tests test_a_partial_migration_still_relays_its_commit (red, then green) and the bun case 'a partial migration's commit notice is relayed on its refusal too'.

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-11-01T17:23:36+00:00 phase=1 state=fixed resolves=p1-r5 -->
### p1-r5-resolved · finding [fixed] · resolves p1-r5: Stale docstring 'CI refuses rather than migrating' (phase 1)

Docstring rewritten to the new behaviour.

<!-- fr:journal kind=finding scope=plan id=p1-full-suite-red-preexisting-resolved created=2026-11-01T17:23:36+00:00 phase=1 state=open resolves=p1-full-suite-red-preexisting out_of_scope=true -->
### p1-full-suite-red-preexisting-resolved · finding [out-of-scope] · resolves p1-full-suite-red-preexisting: The local full suite is red on 13 tests that also fail against origin/main's fr source (phase 1)

The 13 local failures (test_install_atomic, test_run_evidence_visual, test_records_commit) are in files and code this change does not touch. The PR's CI test shards, which include them, passed on 9db6c735 (tests: ci evidence). The local failures are host-load-sensitive (load averages 100-300 during the 3 h run), not caused by this change.

<!-- fr:journal kind=finding scope=plan id=p1-full-suite-red-preexisting-resolved-2 created=2026-11-01T17:30:19+00:00 phase=1 state=open resolves=p1-full-suite-red-preexisting tracked_by=https://github.com/derio-net/super-fr/issues/1280 -->
### p1-full-suite-red-preexisting-resolved-2 · finding [deferred → https://github.com/derio-net/super-fr/issues/1280] · resolves p1-full-suite-red-preexisting: The local full suite is red on 13 tests that also fail against origin/main's fr source (phase 1)

Filed at deliver as https://github.com/derio-net/super-fr/issues/1280.
