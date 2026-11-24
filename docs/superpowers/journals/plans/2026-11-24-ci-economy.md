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

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-24T17:11:51+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · verify_ci waits forever (exit 75) on a cancelled gate nothing replaces (phase 1)

ci_evidence.py: a cancelled gate with no unfinished check raised CiPending with a 'when CI finishes' message; before this change it refused clearly.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-24T17:11:51+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · settle/evaluate.py still compared bucket == 'pending' for `running` (phase 1)

A cancelled check was not counted as running while a gate was absent; missed reader.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-11-24T17:11:51+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · the check-state tripwire only paired cancel with fail/failure and skipped lists (phase 1)

A set like {CANCELLED, TIMED_OUT} or a list escaped it.

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-11-24T17:11:51+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · queue_exec._unreplaced keyed on name alone (phase 1)

commit_checks de-duplicates per (workflow, name), so another workflow's same-named run wrongly replaced a cancel.

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-11-24T17:11:51+00:00 phase=1 state=open review_scope=out -->
### p1-r5 · finding [open] (reviewer: out of scope) · real_glabclient._CI_FAIL still treats canceled as failing (phase 1)

The spec exempts GitLab (gh#611); not caused by this change.

<!-- fr:journal kind=review scope=plan id=p1-review-1 created=2026-11-24T17:11:51+00:00 phase=1 -->
### p1-review-1 · review · phase 1 review: 4 in-scope findings fixed, 1 out of scope (phase 1)

Independent reviewer read spec, plan and the phase diff; every reader conversion verified correct; raised p1-r1..p1-r5. All in-scope findings fixed in 669a5e7e7 with tests (test_run_ci_evidence: stranded cancelled gate refused, running cancel waits; test_settle_evaluate: cancelled counts as running; test_queue_exec: per-workflow replacement; tripwire widened). Spec R3 amended for p1-r1.

<!-- fr:journal kind=lens scope=plan id=lens-errors-1 created=2026-11-24T17:11:51+00:00 phase=1 lens=errors step=review-phase -->
### lens-errors-1 · lens · every new pending path (verify_ci, queue, settle) must bound its wait and say who is told (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-24T17:11:51+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: verify_ci waits forever (exit 75) on a cancelled gate nothing replaces (phase 1)

verify_ci refuses a cancelled gate once nothing on the sha runs, naming the gate and the re-run (669a5e7e7); pending only while a run is in flight; spec R3 amended.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-24T17:11:51+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: settle/evaluate.py still compared bucket == 'pending' for `running` (phase 1)

settle/evaluate.py:151 reads through bucket_verdict; test_a_cancelled_check_counts_as_running_while_a_gate_is_absent.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-11-24T17:11:51+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: the check-state tripwire only paired cancel with fail/failure and skipped lists (phase 1)

Tripwire pairs any cancelled spelling with any FAILED_STATES member or 'fail', and scans list literals.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-11-24T17:11:51+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: queue_exec._unreplaced keyed on name alone (phase 1)

_unreplaced keys on (workflow, name); late lists a required name with any unreplaced cancel; test added.

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-11-24T17:11:51+00:00 phase=1 state=open resolves=p1-r5 out_of_scope=true -->
### p1-r5-resolved · finding [out-of-scope] · resolves p1-r5: real_glabclient._CI_FAIL still treats canceled as failing (phase 1)

GitLab's reader is outside the queue and exempt by the spec (Design §A, gh#611); this change did not touch it.

<!-- fr:journal kind=decision scope=plan id=p2-verdict-needs-classify created=2026-11-24T18:08:41+00:00 phase=2 -->
### p2-verdict-needs-classify · decision · ci_lane verdict requires classify to succeed in every lane (phase 2)

R17 names the classifier only for the landed lane. A failed classify leaves no lane
(and the lane check already fails), but the verdict also lists `classify` among each
lane's required jobs, so a reason names it directly. Any result but success or
skipped (an unknown one included) fails like failure and cancelled.

<!-- fr:journal kind=decision scope=plan id=p2-landed-strict-match created=2026-11-24T18:08:41+00:00 phase=2 -->
### p2-landed-strict-match · decision · landed_run matches path, event, head_branch prefix, conclusion and a different id exactly (phase 2)

`path` must equal `.github/workflows/ci.yml` (the captured payloads carry no `@ref`
suffix), `event` push, `head_branch` start with `fr-queue/`, `conclusion` success
and an integer id other than this run's. Any other payload shape, a non-zero `gh`
exit, non-JSON or a missing `gh` reads `full`. The fixtures are captures of this
repo's own runs (tests/fixtures/ci_lane/README.md); no fr-queue run existed yet, so
the queue case changes only `head_branch` on the captured CI run.

<!-- fr:journal kind=discovery scope=plan id=p2-pinned-tests-moved created=2026-11-24T18:08:41+00:00 phase=2 -->
### p2-pinned-tests-moved · discovery · Five workflow-shape tests pinned what the lanes change (phase 2)

test_ci_shards (ci-ok's old RESULTS case script; now runs ci_lane.py verdict as a
subprocess), test_ci_merge_group (change-fragment keeps its condition, lane rule
appended; a skipped change-fragment passes the full-lane verdict),
test_ci_split_workflow (split-check needs classify), test_pages_workflow and
test_docs_currency_flows (site-build and docs-check skip only in the landed lane,
where the fr-queue run on the same sha already ran them). ci-ok now checks out the
repo and sets up uv to run the verdict script.

<!-- fr:journal kind=discovery scope=plan id=p2-docs-currency created=2026-11-24T18:08:41+00:00 phase=2 -->
### p2-docs-currency · discovery · fr docs check names no page for ci.yml or scripts/ci_lane.py (phase 2)

`uv run fr docs check --base origin/main` reports 32 pages current: no page covers
.github/workflows/ci.yml or scripts/. AGENTS.md's CI job list and a CI lanes
paragraph after Tiers were updated.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t1 created=2026-11-24T18:08:41+00:00 phase=2 -->
### no-refactor-p2-t1 · discovery · no-refactor-because P2.T1 (phase 2)

lane_for and pull_request_lane were written green in final shape; the only cleanup (ruff format) landed in the task's commit

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t2 created=2026-11-24T18:08:41+00:00 phase=2 -->
### no-refactor-p2-t2 · discovery · no-refactor-because P2.T2 (phase 2)

landed_run is one filter and landed_lane one fallible read; the long test lines were wrapped in the same commit

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t3 created=2026-11-24T18:08:41+00:00 phase=2 -->
### no-refactor-p2-t3 · discovery · no-refactor-because P2.T3 (phase 2)

verdict is one table of required and skippable jobs per lane; the test helper name clash was fixed before the commit
