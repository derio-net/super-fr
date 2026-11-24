<!-- fr:journal-schema=4 -->
# Journal: 2026-11-24-ci-economy

<!-- fr:journal kind=decision scope=plan id=p1-replaced-cancel-is-dropped created=2026-11-24T15:50:24+00:00 phase=1 -->
### p1-replaced-cancel-is-dropped · decision · slot_check drops a cancelled run that another run of the same name replaces (phase 1)

The plan said "keep the verdict rules otherwise", but with CANCELLED now pending, a
combination whose check was cancelled and then re-run green would stay pending
forever (any run pending -> pending). Spec R4 scopes the rule to "a cancelled
required check that no newer run replaces", so `queue_exec._unreplaced` drops a
cancelled run when any non-cancelled run of the same name exists before the verdict
and the `late` list are computed. Test:
test_a_cancelled_check_replaced_by_a_newer_run_reads_as_the_newer_run.

<!-- fr:journal kind=decision scope=plan id=p1-cancelled-need-wording created=2026-11-24T15:50:24+00:00 phase=1 -->
### p1-cancelled-need-wording · decision · read_slots words a cancelled check's Need apart from a never-reported one (phase 1)

The existing Need blamed a workflow missing `push: branches: ['fr-queue/**']`, which
is wrong for a check that ran and was cancelled. read_slots now emits a second Need,
"check X was cancelled on combination <sha> and no run replaced it within N min:
re-run the cancelled workflow on <sha>", for late names that did report.

<!-- fr:journal kind=decision scope=plan id=p1-rest-bucket-keeps-gh-names created=2026-11-24T15:50:24+00:00 phase=1 -->
### p1-rest-bucket-keeps-gh-names · decision · The REST client keeps gh's `cancel` and `skipping` bucket names (phase 1)

`real_ghrestclient._BUCKET` became `_bucket(state)`: SKIPPED/NEUTRAL -> skipping,
CANCELLED -> cancel (both as `gh pr checks` renders them), every other state through
`fr.checkstate.verdict_of`. Readers turn a bucket into a verdict with
`bucket_verdict`, so `cancel` is pending everywhere. `batch_merge.FAILING_BUCKETS` was
dropped rather than aliased: no other module imported it.

<!-- fr:journal kind=discovery scope=plan id=p1-verify-ci-cancelled-gate created=2026-11-24T15:50:24+00:00 phase=1 -->
### p1-verify-ci-cancelled-gate · discovery · verify_ci waits on a cancelled gate without marking its workflow busy (phase 1)

A cancelled finished gate check joins the `running` list and the `_where` text, but
not the `unfinished` list that decides which workflows are busy, so a failed gate in
the same workflow is still refused rather than read as a re-run in flight. A
skipped gate still refuses (only success passes there), unchanged.

<!-- fr:journal kind=discovery scope=plan id=p1-docs-currency created=2026-11-24T15:50:24+00:00 phase=1 -->
### p1-docs-currency · discovery · Seven covered pages owed a stamp; the wave-driver explainer gained one paragraph (phase 1)

`fr docs check` named fr-devops-gate, fr-triage, fr-wave-driver, index,
herdr-control-sessions, ops and workflow-shapes. Only fr-wave-driver.md describes
how the queue reads checks; it now says a cancelled check waits for its replacement
and shows under Needs you now after queue.check_wait_minutes. The rest got a
`reviewed` note. The row ci-cancelled-reads-pending moved not-implemented -> ci with
eight unit refs (fr acceptance set-status, its own commit).

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t2 created=2026-11-24T15:50:24+00:00 phase=1 -->
### no-refactor-p1-t2 · discovery · no-refactor-because P1.T2 (phase 1)

fr/checkstate.py was written green in its final shape (four constants, three pure functions); the only cleanup, moving the test's imports to the top, landed in the same commit

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-11-24T15:50:24+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

the late list reuses slot_check's existing by-name grouping; the shared overdue test was factored as it was written, and read_slots' wording split is two short branches
