<!-- fr:journal-schema=4 -->
# Journal: 2026-11-28-tester-gate-auto-pass

<!-- fr:journal kind=discovery scope=plan id=p1-gated-rows-at-kw created=2026-11-28T12:49:41+00:00 phase=1 -->
### p1-gated-rows-at-kw · discovery · a batch read must not pass pr= to gated_rows_at (phase 1)

Existing tests monkeypatch triage_batch_cmd.gated_rows_at with a (checkout, ref, branch) signature, so Driver._gated_rows passes the pr keyword only for a loose PR (triage_drive_loose._pr_kw). triage_batch_cmd.py ends at exactly its 8320-line budget; the new reads and the loose action live in triage_drive_loose.py.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t2 created=2026-11-28T12:49:41+00:00 phase=1 -->
### no-refactor-p1-t2 · discovery · no-refactor-because P1.T2 (phase 1)

drive_pass gained one three-line loop over loose ledgers calling the shared gate_actions; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-11-28T12:49:41+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

gated_rows_at/_run_text gained an optional pr branch beside the unchanged first-match path; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-11-28T12:49:41+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

rows, docs stamps and the change fragment only; no code to clean

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-28T13:01:58+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · Each loose PR re-read every live and archived cursor at the tip (phase 1)

ledger._run_text listed and showed every cursor once per loose PR; the _ledger_rows cache keyed on branch and pr shared nothing. PRs x cursors git calls per pass.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-28T13:01:58+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · A loose PR in a repo with no clone aborted the --yes pass (phase 1)

_reader -> checkout -> _open_checkout calls _fail (a CLI exit, not TriageError) for a repo with no --checkout or another origin (triage_batch_cmd.py:1436-1441).

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-11-28T13:01:58+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · The closed-out batch drive_pass test never built a closed-out batch (phase 1)

test_a_closed_out_batchs_pr_given_as_a_loose_ledger_is_passed duplicated the plain loose test; R8 was unproven at drive_pass.

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-11-28T13:01:58+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · R5 not exercised end to end through loose_ledgers; R6 retry not shown across passes (phase 1)

The cursor-names-another-PR drive test stubbed gated_rows_at to NO_RUN; no two-pass retry assertion.

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-11-28T13:01:58+00:00 phase=1 state=open review_scope=in -->
### p1-r5 · finding [open] (reviewer: in scope) · A run's live and archived cursor counted as two cursors (phase 1)

The >1-cursor refusal at ledger._run_text would make such a PR permanently unreadable.

<!-- fr:journal kind=finding scope=plan id=p1-r6 created=2026-11-28T13:01:58+00:00 phase=1 state=open review_scope=in -->
### p1-r6 · finding [open] (reviewer: in scope) · fr-exit-gates.md overstated and under-stated the loose rule (phase 1)

It said 'a run cursor on its branch names it'; the code also accepts a cursor with no pr, refuses two, and only a whole-scope drive does it.

<!-- fr:journal kind=finding scope=plan id=p1-r7 created=2026-11-28T13:01:58+00:00 phase=1 state=open review_scope=in -->
### p1-r7 · finding [open] (reviewer: in scope) · _pr_kw: a private helper imported across modules, unnecessary (phase 1)

gated_rows_at(..., pr=None) is valid; the helper only added an indirection.

<!-- fr:journal kind=review scope=plan id=review-p1 created=2026-11-28T13:01:58+00:00 phase=1 -->
### review-p1 · review · phase 1 code review (feature-dev:code-reviewer): 7 findings, all fixed (phase 1)

Reviewed spec R1-R9, plan, and every changed module and test. p1-r1..p1-r7 raised, all in scope, all fixed in commit 'fix(triage): loose gate reads ...' with tests; rows re-pointed with fr acceptance set-status.

<!-- fr:journal kind=lens scope=plan id=lens-errors-1 created=2026-11-28T13:01:58+00:00 phase=1 lens=errors step=review-phase -->
### lens-errors-1 · lens · the drive pass must survive a repo or cursor state it has not seen before (p1-r2, p1-r5) (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-28T13:01:58+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: Each loose PR re-read every live and archived cursor at the tip (phase 1)

ledger.read_cursors reads every cursor once; triage_drive_loose reads it once per repo per pass and passes texts= to gated_rows_at. Test test_two_loose_prs_of_one_repo_read_its_cursors_once_per_pass.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-28T13:01:58+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: A loose PR in a repo with no clone aborted the --yes pass (phase 1)

triage_drive_loose._repo_read checks _checkout_refusal first and returns a TriageError reason, reported once per PR; the pass goes on. Test test_a_loose_pr_in_a_repo_with_no_clone_is_reported_and_the_pass_goes_on.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-11-28T13:01:58+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: The closed-out batch drive_pass test never built a closed-out batch (phase 1)

Replaced by test_r8_a_closed_out_batchs_gated_pr_is_passed_once_through_the_loose_route: a real closed-out batch, its ledger visible to the batch route, exactly one gate-pass via the loose route.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-11-28T13:01:58+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: R5 not exercised end to end through loose_ledgers; R6 retry not shown across passes (phase 1)

loose_ledgers tests over the real _ledger_repo clone (this PR, another PR, two runs) and test_a_failed_gate_pass_for_a_loose_pr_is_planned_again_on_the_next_pass (two passes, two failures).

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-11-28T13:01:58+00:00 phase=1 state=fixed resolves=p1-r5 -->
### p1-r5-resolved · finding [fixed] · resolves p1-r5: A run's live and archived cursor counted as two cursors (phase 1)

_run_text dedupes the named cursors by run id. Test test_a_runs_live_and_archived_cursors_are_one_cursor_for_a_pr.

<!-- fr:journal kind=finding scope=plan id=p1-r6-resolved created=2026-11-28T13:01:58+00:00 phase=1 state=fixed resolves=p1-r6 -->
### p1-r6-resolved · finding [fixed] · resolves p1-r6: fr-exit-gates.md overstated and under-stated the loose rule (phase 1)

fr-exit-gates.md now says: a whole-scope drive, exactly one run cursor on the branch, not naming a different PR; the guard sentence rewrapped.

<!-- fr:journal kind=finding scope=plan id=p1-r7-resolved created=2026-11-28T13:01:58+00:00 phase=1 state=fixed resolves=p1-r7 -->
### p1-r7-resolved · finding [fixed] · resolves p1-r7: _pr_kw: a private helper imported across modules, unnecessary (phase 1)

_pr_kw removed; Driver._gated_rows is batch-only again (repo, branch, label); the loose path calls gated_rows_at(..., pr=, texts=) directly.
