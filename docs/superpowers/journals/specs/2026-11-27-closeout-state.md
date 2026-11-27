<!-- fr:journal-schema=4 -->
# Journal: 2026-11-27-closeout-state

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-11-27T11:21:54+00:00 input=true -->
### operator-brief · discovery · Batch closeout-state brief (super-fr#1601, super-fr#1626)

/fr-goal batch closeout-state. Batch `closeout-state` of derio-net/super-fr: 2 issues, delivered as ONE pull request.
Batch title: Close-outs and batches never stuck as started or Running.

super-fr#1601 — triage: a failing close-out take-back hides the dispatch error and leaves the close-out stuck as started.
In the close-out start, the take-back after a failed `runner.dispatch` (`save_closeouts(path, read, read=[*read, marker])`) sits unguarded in the `except` block, so if it raises, the dispatch error survives only as `__context__` and the start marker stays recorded, so no later pass restarts the close-out. Suggested fix: wrap the take-back in its own `try`, report both errors and raise a board need.

super-fr#1626 — A batch whose repo left the scope shows as Running and cannot be focused, repaired or cancelled.
A finished batch whose repo was transferred to another org draws in the Running column with an `unknown` issue; its focus, repair, replace and cancel verbs all refuse ("its repo ... is not in this scope's facts"); `batch list` disagrees (`close-out archived`); the driver keeps asking for the departed repo's checkout. Expected: never Running; no Jump; one verb retires it without the repo (e.g. `cancel --orphaned` or a `repo_left_scope` event at collect).

Delivery rules: branch feat/batch-closeout-state; draft PR once the spec is committed, body with `Closes derio-net/super-fr#1601` and `Closes derio-net/super-fr#1626`; batches arch-shared-helpers and queue-followups also change triage_batch_cmd.py (the second to land resolves the queue's conflict hand-back); no member issue as a phase tracking_issue; the wave driver owns mergeability and CI (no `fr pr settle` loop); never add `approved-fr`.

<!-- fr:journal kind=decision scope=spec id=takeback-keep-driving created=2026-11-27T11:21:54+00:00 decided_by=operator -->
### takeback-keep-driving · decision · A failed take-back keeps the driver running and is reported once

Operator chose 'Keep driving, report once' over stopping the driver: both errors in one line, counted as a failed write (`--once` exits 1), no board Need; the existing closeout-abandoned rule re-owes the marker.

<!-- fr:journal kind=decision scope=spec id=left-scope-derived-stage created=2026-11-27T11:21:54+00:00 decided_by=operator -->
### left-scope-derived-stage · decision · A batch whose repo left the scope has a derived `left-scope` stage

Operator chose a derived, never-stored `left-scope` stage (closed out, Done column with a pill, no Jump) over the last recorded state or a stored collect event.

<!-- fr:journal kind=decision scope=spec id=cancel-orphaned created=2026-11-27T11:21:54+00:00 decided_by=operator -->
### cancel-orphaned · decision · `batch cancel --orphaned` retires a left-scope batch

Operator chose an explicit `--orphaned` flag: only the cancel event, no forge writes; cancel without it refuses on a left-scope batch and names the flag.

<!-- fr:journal kind=decision scope=spec id=verification-ci-none created=2026-11-27T11:21:54+00:00 decided_by=operator -->
### verification-ci-none · decision · Verified by CI unit tests; no gate

Operator chose `strategy: none` with CI unit tests; no Test Plan row, nothing holds the close-out.

<!-- fr:journal kind=lens scope=spec id=lens-errors-1 created=2026-11-27T11:21:54+00:00 lens=errors step=brainstorm -->
### lens-errors-1 · lens · #1601 is an error-handling defect: a second failure inside an except block
