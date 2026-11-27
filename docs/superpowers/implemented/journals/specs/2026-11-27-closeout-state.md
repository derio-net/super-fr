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

<!-- fr:journal kind=finding scope=spec id=s-r1 created=2026-11-27T11:28:50+00:00 state=open review_scope=in -->
### s-r1 · finding [open] (reviewer: in scope) · R5's 'asks for no checkout' unreachable: build_driver asks before reading facts

build_driver (triage_batch_cmd.py:8140) names a checkout for every chosen batch's repo from the scope alone, before facts are read.

<!-- fr:journal kind=finding scope=spec id=s-r2 created=2026-11-27T11:28:50+00:00 state=open review_scope=in -->
### s-r2 · finding [open] (reviewer: in scope) · A repo can be absent from facts.repos because the org list was truncated

collect.py:273-280 caps the org repo list; a truncated list drops repos that are still in the org.

<!-- fr:journal kind=finding scope=spec id=s-r3 created=2026-11-27T11:28:50+00:00 state=open review_scope=in -->
### s-r3 · finding [open] (reviewer: in scope) · R4 contradicts the Design's ordering for a batch with no lifecycle events

Design put the check after the no-events return; column_of/lane_of branch on `not batch.events` first.

<!-- fr:journal kind=finding scope=spec id=s-r4 created=2026-11-27T11:28:50+00:00 state=open review_scope=in -->
### s-r4 · finding [open] (reviewer: in scope) · Closed stage sets the Design did not list

claims.releasing/owed_claims, wave_queue.TERMINAL_STAGES, kanban._TERMINAL_STAGES, preselected_wave, cancelled_waves, drive_pass held filter, pill CSS.

<!-- fr:journal kind=finding scope=spec id=s-r5 created=2026-11-27T11:28:50+00:00 state=open review_scope=in -->
### s-r5 · finding [open] (reviewer: in scope) · batch list prints no stage

batch_list_command (:898) prints no stage column.

<!-- fr:journal kind=finding scope=spec id=s-r6 created=2026-11-27T11:28:50+00:00 state=open review_scope=in -->
### s-r6 · finding [open] (reviewer: in scope) · Per-batch take-back prints its error twice via _fail

_write turns TriageError into _fail, which prints before raising.

<!-- fr:journal kind=finding scope=spec id=s-r7 created=2026-11-27T11:28:50+00:00 state=open review_scope=in -->
### s-r7 · finding [open] (reviewer: in scope) · R2's retry rests on closeout-abandoned, which covers only collected markers

A per-batch CloseoutEvent left behind is not re-owed by any rule.

<!-- fr:journal kind=finding scope=spec id=s-r8 created=2026-11-27T11:28:50+00:00 state=open review_scope=in -->
### s-r8 · finding [open] (reviewer: in scope) · PILL_STAGES cannot hold the pill text

pill_of returns the stage name.

<!-- fr:journal kind=finding scope=spec id=s-r9 created=2026-11-27T11:28:50+00:00 state=open review_scope=in -->
### s-r9 · finding [open] (reviewer: in scope) · fr-triage.md currency flagged but no Design item

Background named the page; no design bullet.

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-11-27T11:28:50+00:00 -->
### spec-review-1 · review · independent spec review: 9 findings

Reviewer checked the four operator decisions (all honoured) and every cited file:line; raised s-r1 to s-r9, all in scope.

<!-- fr:journal kind=lens scope=spec id=lens-tests-1 created=2026-11-27T11:28:50+00:00 lens=tests step=spec-review -->
### lens-tests-1 · lens · R4, R5 and R8 reach several readers and verbs; each needs a facts fixture lacking the repo, plus a truncated one

<!-- fr:journal kind=finding scope=spec id=s-r1-resolved created=2026-11-27T11:28:50+00:00 state=fixed resolves=s-r1 -->
### s-r1-resolved · finding [fixed] · resolves s-r1: R5's 'asks for no checkout' unreachable: build_driver asks before reading facts

Design now filters build_driver's names through left_scope using facts.json when present; R5 says drive asks for no checkout.

<!-- fr:journal kind=finding scope=spec id=s-r2-resolved created=2026-11-27T11:28:50+00:00 state=fixed resolves=s-r2 -->
### s-r2-resolved · finding [fixed] · resolves s-r2: A repo can be absent from facts.repos because the org list was truncated

R4 and the left_scope predicate require no `repos` truncation warning; truncated facts keep today's stage; tested.

<!-- fr:journal kind=finding scope=spec id=s-r3-resolved created=2026-11-27T11:28:50+00:00 state=fixed resolves=s-r3 -->
### s-r3-resolved · finding [fixed] · resolves s-r3: R4 contradicts the Design's ordering for a batch with no lifecycle events

Order is now cancel > left-scope > no-events > PR-derived; column_of and lane_of read the stage first.

<!-- fr:journal kind=finding scope=spec id=s-r4-resolved created=2026-11-27T11:28:50+00:00 state=fixed resolves=s-r4 -->
### s-r4-resolved · finding [fixed] · resolves s-r4: Closed stage sets the Design did not list

Design names each set and its decided behaviour: owes and releases no claims, terminal for waves and cards, delivered for cancelled_waves, CSS rule added.

<!-- fr:journal kind=finding scope=spec id=s-r5-resolved created=2026-11-27T11:28:50+00:00 state=fixed resolves=s-r5 -->
### s-r5-resolved · finding [fixed] · resolves s-r5: batch list prints no stage

R6 and Design: with facts, the row ends `repo left this scope`.

<!-- fr:journal kind=finding scope=spec id=s-r6-resolved created=2026-11-27T11:28:50+00:00 state=fixed resolves=s-r6 -->
### s-r6-resolved · finding [fixed] · resolves s-r6: Per-batch take-back prints its error twice via _fail

_close_out's take-back calls the non-printing _save; fail_text in drive_errors reads FAIL_MESSAGE.

<!-- fr:journal kind=finding scope=spec id=s-r7-resolved created=2026-11-27T11:28:50+00:00 state=fixed resolves=s-r7 -->
### s-r7-resolved · finding [fixed] · resolves s-r7: R2's retry rests on closeout-abandoned, which covers only collected markers

R2 now limits the retry to the collected start and states that a leftover per-batch event reads as close-out started (that start is no longer planned).

<!-- fr:journal kind=finding scope=spec id=s-r8-resolved created=2026-11-27T11:28:50+00:00 state=fixed resolves=s-r8 -->
### s-r8-resolved · finding [fixed] · resolves s-r8: PILL_STAGES cannot hold the pill text

Design: pill_of maps stages to text through a mapping defaulting to the name; left-scope -> 'repo left this scope'.

<!-- fr:journal kind=finding scope=spec id=s-r9-resolved created=2026-11-27T11:28:50+00:00 state=fixed resolves=s-r9 -->
### s-r9-resolved · finding [fixed] · resolves s-r9: fr-triage.md currency flagged but no Design item

R9 and a Design bullet update docs/explainers/fr-triage.md.

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-27T11:28:51+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates:
  batch-left-scope-cancel: none
  batch-left-scope-stage: none
  closeout-takeback-both-errors: none
row_kinds:
  batch-left-scope-cancel: none
  batch-left-scope-stage: none
  closeout-takeback-both-errors: none
run_gate: none
run_kind: none
```

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-27-closeout-state-p2 created=2026-11-27T11:30:10+00:00 -->
### phase-split-2026-11-27-closeout-state-p2 · decision · ask: #1626's left-scope stage and cancel --orphaned is its own ask, independent of #1601's take-back
