<!-- fr:journal-schema=4 -->
# Journal: 2026-11-24-wave-queue-gaps

<!-- fr:journal kind=decision scope=plan id=p1-stack-target-two-sides created=2026-11-25T00:43:26+00:00 phase=1 -->
### p1-stack-target-two-sides · decision · The command layer and the planner compute the stack target with one function (phase 1)

`queue_handback.stack_target(rep)` is the last combination on the replay's base that
holds no ejected entry, else the base. The planner calls it on the combinations `_valid`
leaves after this pass's ejections (`aimed`); the driver's `lineage_reads` calls it on
the last record's replay (or uses `main` now when the record's base is stale). The
planner's target is always a prefix of the records', so an `onto` the planner named is an
ancestor of the target `leads` is read against, and a re-issue never fires spuriously.

<!-- fr:journal kind=decision scope=plan id=p1-carry-brief-mark created=2026-11-25T00:43:26+00:00 phase=1 -->
### p1-carry-brief-mark · decision · A carry brief is recorded as a free re-issue at the carrying head (phase 1)

No new event kind: the carry brief writes `ConflictEvent(head=<carrying head>,
onto=<target>, reissue=true)`, paths taken from the batch's latest conflict. That is the
once-per-head mark (`lineage_actions` emits `queue-carry` only for a head with no conflict
event) and spends no budget. With no clean hand-back head the event is `held`, which the
board already shows as a merge-conflict Need.

<!-- fr:journal kind=decision scope=plan id=p1-base-target-brief created=2026-11-25T00:43:26+00:00 phase=1 -->
### p1-base-target-brief · decision · In slot mode with nothing standing the brief reads as today (phase 1)

Per plan P1.T3.S3, a target on the default branch (`onto_ref` `origin/<default>`) keeps
today's step 2 (`git fetch origin && git merge origin/<default>`); only an `fr-queue/`
ref gets the slot wording and the wait-for-a-re-issue check. The event still records
`onto` (the base sha), so a later move is judged by `leads`.

<!-- fr:journal kind=discovery scope=plan id=p1-fresh-twin created=2026-11-25T00:43:26+00:00 phase=1 -->
### p1-fresh-twin · discovery · Checkout.carried drops a combination rebuilt fresh into main's history (phase 1)

An R13 fresh rebuild has the same tree and parents as the combination it replaces but a
new sha, so a head that merged the original would read as carrying it once the twin
landed. `carried` looks, per candidate, for a commit in the target's history since the
candidate's first parent with the same tree and parents (one `git log` per candidate,
only for built shas the head reaches).

<!-- fr:journal kind=discovery scope=plan id=p1-explicit-reexport created=2026-11-25T00:43:26+00:00 phase=1 -->
### p1-explicit-reexport · discovery · mypy needs src importers of the moved rules to import from handback_rules (phase 1)

`batch_drive` re-exports the moved names for tests and other callers, but mypy's
no-implicit-reexport refuses `from fr.triage.batch_drive import conflict_decision` in
src. `wave_queue`, `views` and `triage_batch_cmd` now import them from
`fr.triage.handback_rules`; one import line changed in `triage_batch_cmd`.

<!-- fr:journal kind=finding scope=plan id=p1-acceptance-check-foreign-rows created=2026-11-25T00:43:26+00:00 phase=1 state=open review_scope=out -->
### p1-acceptance-check-foreign-rows · finding [open] (reviewer: out of scope) · fr acceptance check --no-fetch reports 43 errors on other features' rows (phase 1)

Rows such as `issues-page-filter-guard` and `privacy-snapshot-keys` name tests and a spec
(`2026-11-22-triage-hardening`) this branch does not have; the fold reads them from the
default ref, which is ahead of this branch's base. None is a wave-queue-gaps row; a merge
of origin/main into the branch should clear them.

<!-- fr:journal kind=discovery scope=plan id=p1-t5-test-order created=2026-11-25T00:43:26+00:00 phase=1 -->
### p1-t5-test-order · discovery · The T5.S1 driver tests were written after the T5.S2 wiring (phase 1)

The slot, re-issue and carry driver tests in test_triage_batch_drive_cmd.py passed on
first run because the wiring landed first (red was not observed for them). They assert
strings only the new code produces (`fr-queue/`, `git merge <sha>`, `Merge queue carry`,
`reissue: true`), so they would fail without it.

<!-- fr:journal kind=lens scope=plan id=lens-errors-1 created=2026-11-25T00:43:26+00:00 phase=1 lens=errors step=implement-phase -->
### lens-errors-1 · lens · GitError is mapped to None (R5) in lineage reads and the carry reset search; check no unreadable answer is read as leads or carries nothing (phase 1)

<!-- fr:journal kind=lens scope=plan id=lens-tests-1 created=2026-11-25T00:43:26+00:00 phase=1 lens=tests step=implement-phase -->
### lens-tests-1 · lens · the driver hand-back tests were written after the code; check they pin behaviour, and that the planner tests cover the third-pass no-op (phase 1)

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-11-25T00:43:26+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

a smoke module and a mechanical move out of the budgeted modules; the move is the cleanup, and the delegate is one line

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t2 created=2026-11-25T00:43:26+00:00 phase=1 -->
### no-refactor-p1-t2 · discovery · no-refactor-because P1.T2 (phase 1)

a stamp bump and two optional defaulted fields refused below 14 beside the existing checks; nothing duplicated to fold

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-11-25T00:43:26+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

new pure helpers, and conflict_brief moved as it was plus one step-2 branch; batch_dispatch re-exports it by name

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-11-25T00:43:26+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

the planner logic went into queue_handback helpers from the start (wave_queue grew by the calls only); the two gitseam reads are small methods with no shared shape to extract
