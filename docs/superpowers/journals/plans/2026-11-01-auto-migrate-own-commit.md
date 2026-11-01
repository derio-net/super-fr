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
