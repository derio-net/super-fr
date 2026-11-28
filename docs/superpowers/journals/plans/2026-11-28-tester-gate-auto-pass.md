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

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r1 created=2026-11-28T13:12:45+00:00 state=open review_scope=in -->
### l-docs-accuracy-r1 · finding [open] (reviewer: in scope) · fr-exit-gates.md said 'outside any batch' and 'exactly one run cursor'

loose_prs also takes a closed-out batch's PR, and _run_text counts one run (live + archived copies), not one cursor file.

<!-- fr:journal kind=finding scope=plan id=l-errors-r1 created=2026-11-28T13:12:45+00:00 state=open review_scope=in -->
### l-errors-r1 · finding [open] (reviewer: in scope) · A cursor naming another PR silently yielded NO_RUN; a non-string pr skipped the check

ledger._run_text returned None for a mismatching pr, with no report; isinstance(recorded, str) let a non-string pr through.

<!-- fr:journal kind=finding scope=plan id=l-errors-r2 created=2026-11-28T13:12:45+00:00 state=open review_scope=in -->
### l-errors-r2 · finding [open] (reviewer: in scope) · A repo-level failure was reported once per loose PR under a key with no repo

triage_drive_loose._read re-raised the cached repo error per PR keyed 'ledger\0PR #n\0exc': floods output and can drop another repo's same-number warning.

<!-- fr:journal kind=finding scope=plan id=l-errors-r3 created=2026-11-28T13:12:45+00:00 state=open review_scope=out -->
### l-errors-r3 · finding [open] (reviewer: out of scope) · read_cursors drops malformed run cursors silently, and R5's two-run check now depends on it

The yaml.YAMLError swallow predates this change (moved unchanged from _run_text).

<!-- fr:journal kind=finding scope=plan id=l-security-r1 created=2026-11-28T13:12:45+00:00 state=open review_scope=in -->
### l-security-r1 · finding [open] (reviewer: in scope) · Loose PRs bound to a cursor by branch name alone; url check ignored owner/repo; forks not excluded

_run_text accepted any cursor with no pr, compared only the url's /<n> suffix, and loose_prs ignored cross_repo.

<!-- fr:journal kind=finding scope=plan id=l-tests-r1 created=2026-11-28T13:12:45+00:00 state=open review_scope=in -->
### l-tests-r1 · finding [open] (reviewer: in scope) · The copy of run_gate/run_gate_inherited/ops_promoted into the loose ledger was untested

Driver fakes always returned defaults.

<!-- fr:journal kind=finding scope=plan id=l-tests-r2 created=2026-11-28T13:12:45+00:00 state=open review_scope=in -->
### l-tests-r2 · finding [open] (reviewer: in scope) · LooseWorld left batch PRs out of gated_prs, unlike collect

No driver test of a landed gated batch whose PR is also in gated_prs, nor of R8 through the real _ledgers skip.

<!-- fr:journal kind=finding scope=plan id=l-tests-r3 created=2026-11-28T13:12:45+00:00 state=open review_scope=in -->
### l-tests-r3 · finding [open] (reviewer: in scope) · test_a_cursor_naming_another_pr_means_no_rows... never exercised the cursor rule

It stubbed gated_rows_at to NO_RUN.

<!-- fr:journal kind=finding scope=plan id=l-tests-r4 created=2026-11-28T13:12:45+00:00 state=open review_scope=in -->
### l-tests-r4 · finding [open] (reviewer: in scope) · R4's tracker closure and labels-off were not asserted for a loose gate-pass

repo now comes from action.repo.

<!-- fr:journal kind=finding scope=plan id=l-tests-r5 created=2026-11-28T13:12:45+00:00 state=open review_scope=in -->
### l-tests-r5 · finding [open] (reviewer: in scope) · The once-only report key named 'PR #n' without the repo

Same-number PRs of two repos with the same error were reported once in all.

<!-- fr:journal kind=decision scope=plan id=no-pr-cursor-kept created=2026-11-28T13:12:45+00:00 -->
### no-pr-cursor-kept · decision · A loose PR's cursor that records no pr is still accepted (R5), after l-security-r1

On origin/main 95 of 144 run cursors (live 1 of 11, archived 95 of 133) record no pr: they predate `fr pr create` recording it (run v11). Refusing them would leave most of the Needs you · Tester cards this batch exists to clear stuck. The binding is tightened instead: fork PRs and PRs of unknown origin are never loose, exactly one run may name the branch, a recorded pr must match owner/repo and number, and the rows must read walked on the default branch, behind a gate label only triage rights can set.

<!-- fr:journal kind=review scope=plan id=lens-review created=2026-11-28T13:12:45+00:00 -->
### lens-review · review · lens review: docs-accuracy, errors, security, tests — 11 findings

docs-accuracy 1 (in), errors 3 (2 in, 1 out), security 1 (in), tests 5 (in). All in-scope fixed with tests; l-errors-r3 out of scope (predates the change).

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r1-resolved created=2026-11-28T13:12:45+00:00 state=fixed resolves=l-docs-accuracy-r1 -->
### l-docs-accuracy-r1-resolved · finding [fixed] · resolves l-docs-accuracy-r1: fr-exit-gates.md said 'outside any batch' and 'exactly one run cursor'

fr-exit-gates.md: 'a merged pull request that no open batch covers: one outside every batch, or one whose batch has closed out', 'exactly one run ... (live and archived cursors count as one)', plus the fork rule.

<!-- fr:journal kind=finding scope=plan id=l-errors-r1-resolved created=2026-11-28T13:12:45+00:00 state=fixed resolves=l-errors-r1 -->
### l-errors-r1-resolved · finding [fixed] · resolves l-errors-r1: A cursor naming another PR silently yielded NO_RUN; a non-string pr skipped the check

_run_text raises TriageError 'the run cursor <run> on branch <b> records PR <x>, not <repo>#<n>' for a mismatching or non-url pr; reported once, nothing planned. Spec R5 amended. Tests test_a_cursor_naming_another_pr_is_unreadable, test_a_cursor_whose_pr_is_not_a_url_is_unreadable, test_loose_ledgers_reports_a_cursor_naming_another_pr_and_reads_nothing.

<!-- fr:journal kind=finding scope=plan id=l-errors-r2-resolved created=2026-11-28T13:12:45+00:00 state=fixed resolves=l-errors-r2 -->
### l-errors-r2-resolved · finding [fixed] · resolves l-errors-r2: A repo-level failure was reported once per loose PR under a key with no repo

A repo-level failure is reported once per repo and cause (key ledger\0<repo>\0<exc>); a PR's own failure names <owner>/<repo>#<n>. Spec R6 amended. Test test_a_repo_failure_is_reported_once_per_repo_and_a_pr_failure_names_its_repo.

<!-- fr:journal kind=finding scope=plan id=l-errors-r3-resolved created=2026-11-28T13:12:45+00:00 state=open resolves=l-errors-r3 out_of_scope=true -->
### l-errors-r3-resolved · finding [out-of-scope] · resolves l-errors-r3: read_cursors drops malformed run cursors silently, and R5's two-run check now depends on it

The silent YAMLError skip in reading run cursors predates this change (moved verbatim from _run_text); it affects the batch route equally. Filed as a follow-up at deliver.

<!-- fr:journal kind=finding scope=plan id=l-security-r1-resolved created=2026-11-28T13:12:45+00:00 state=fixed resolves=l-security-r1 -->
### l-security-r1-resolved · finding [fixed] · resolves l-security-r1: Loose PRs bound to a cursor by branch name alone; url check ignored owner/repo; forks not excluded

loose_prs skips cross_repo True or None (fail closed); a recorded pr must end in /<owner>/<repo>/pull/<n> (case-insensitive) or the read is refused; a non-string pr is refused. The no-pr leg is kept by decision no-pr-cursor-kept (95 of 144 cursors predate the pr field). Tests: fork/unknown-origin, another repo's same number, non-url pr.

<!-- fr:journal kind=finding scope=plan id=l-tests-r1-resolved created=2026-11-28T13:12:45+00:00 state=fixed resolves=l-tests-r1 -->
### l-tests-r1-resolved · finding [fixed] · resolves l-tests-r1: The copy of run_gate/run_gate_inherited/ops_promoted into the loose ledger was untested

test_r2_a_loose_prs_run_gate_no_row_inherits_is_never_passed_by_walked_rows and test_r2_a_loose_prs_ops_promoted_devops_gate_is_never_passed_by_walked_rows drive the real loose_ledgers copy.

<!-- fr:journal kind=finding scope=plan id=l-tests-r2-resolved created=2026-11-28T13:12:45+00:00 state=fixed resolves=l-tests-r2 -->
### l-tests-r2-resolved · finding [fixed] · resolves l-tests-r2: LooseWorld left batch PRs out of gated_prs, unlike collect

LooseWorld now lists every gated merged PR, batch PRs included; test_a_landed_gated_batchs_pr_in_gated_prs_is_passed_once_by_its_batch and test_r8_a_closed_out_batchs_gated_pr_is_passed_once_through_the_loose_route.

<!-- fr:journal kind=finding scope=plan id=l-tests-r3-resolved created=2026-11-28T13:12:45+00:00 state=fixed resolves=l-tests-r3 -->
### l-tests-r3-resolved · finding [fixed] · resolves l-tests-r3: test_a_cursor_naming_another_pr_means_no_rows... never exercised the cursor rule

Renamed to test_no_run_rows_plan_nothing_and_write_nothing; the real cursor rule is driven by the loose_ledgers tests over a real clone.

<!-- fr:journal kind=finding scope=plan id=l-tests-r4-resolved created=2026-11-28T13:12:45+00:00 state=fixed resolves=l-tests-r4 -->
### l-tests-r4-resolved · finding [fixed] · resolves l-tests-r4: R4's tracker closure and labels-off were not asserted for a loose gate-pass

test_r4_a_loose_gate_pass_closes_the_prs_trackers and test_r4_labels_off_writes_no_gate_pass_for_a_loose_pr.

<!-- fr:journal kind=finding scope=plan id=l-tests-r5-resolved created=2026-11-28T13:12:45+00:00 state=fixed resolves=l-tests-r5 -->
### l-tests-r5-resolved · finding [fixed] · resolves l-tests-r5: The once-only report key named 'PR #n' without the repo

Per-PR label is <owner>/<repo>#<n>; repo failures keyed by repo; covered by test_a_repo_failure_is_reported_once_per_repo_and_a_pr_failure_names_its_repo.
