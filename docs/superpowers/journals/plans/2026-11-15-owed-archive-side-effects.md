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
