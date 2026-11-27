<!-- fr:journal-schema=4 -->
# Journal: 2026-11-27-closeout-state

<!-- fr:journal kind=discovery scope=plan id=p1-dedupe-key created=2026-11-27T12:21:20+00:00 phase=1 -->
### p1-dedupe-key · discovery · The take-back's words must stay out of _dispatch_failed's dedupe key (phase 1)

A runner error with no `code` keys the dedupe on the whole message, so appending the take-back error to it re-said the stop every pass. `_dispatch_failed` takes the take-back text as a separate `also` that is said with the first report and never keyed.

<!-- fr:journal kind=discovery scope=plan id=p1-module-budget created=2026-11-27T12:21:20+00:00 phase=1 -->
### p1-module-budget · discovery · triage_batch_cmd.py sits at its 8300-line budget (phase 1)

The shared take-back wording lives in `fr.triage.drive_errors.takeback_failed` (beside `fail_text`) so the module stays within budget (8299).

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-27T12:25:52+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · Take-back failure tests used only TriageError; the fail_exit and VisibilityUnreadable cases were untested (phase 1)

tests/unit/test_triage_closeout_takeback.py raised only TriageError, so a regression from fail_text back to str(exc) on a fail_exit would go unnoticed; the dedupe test never asserted the take-back text on the first line.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-27T12:25:52+00:00 phase=1 state=open review_scope=out -->
### p1-r2 · finding [open] (reviewer: out of scope) · triage_batch_cmd.py sits at its 8300-line module budget (phase 1)

Not a defect of this phase; phase 2 adds to the module and must extract code or move the budget with a reason in its own diff.

<!-- fr:journal kind=review scope=plan id=review-p1 created=2026-11-27T12:25:52+00:00 phase=1 -->
### review-p1 · review · Phase 1 review: R1-R3 met; findings p1-r1 (in), p1-r2 (out) (phase 1)

Independent reviewer checked both guarded take-backs, the single reported line, the dedupe key, R3's unchanged success path, fail_text and the boundary, the tests and the fragment. Raised p1-r1 and p1-r2.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-27T12:25:52+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: Take-back failure tests used only TriageError; the fail_exit and VisibilityUnreadable cases were untested (phase 1)

The collected take-back test is parametrized over TriageError, fail_exit and VisibilityUnreadable and asserts the carried text (never 'exited 2'); the dedupe test asserts the first line ends with the take-back text.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-27T12:25:52+00:00 phase=1 state=open resolves=p1-r2 out_of_scope=true -->
### p1-r2-resolved · finding [out-of-scope] · resolves p1-r2: triage_batch_cmd.py sits at its 8300-line module budget (phase 1)

The budget was already near full before this change; phase 2, which adds to the module, handles it in its own diff.

<!-- fr:journal kind=discovery scope=plan id=p2-module-budget created=2026-11-27T13:14:37+00:00 phase=2 -->
### p2-module-budget · discovery · triage_batch_cmd.py kept within its budget by moving _checkout_map out (phase 2)

The build_driver filter, the batch list marker and cancel --orphaned needed command-side lines. `_checkout_map` (used only by build_driver) moved to `fr.triage.checkouts.checkout_map` raising TriageError, and the --orphaned flow to `fr.triage.orphan`. The module is 8294 lines, budget 8300 unchanged.

<!-- fr:journal kind=discovery scope=plan id=p2-unknown-repo-overlap created=2026-11-27T13:14:37+00:00 phase=2 -->
### p2-unknown-repo-overlap · discovery · A batch of a repo absent from a complete repo list is now left-scope, so plan overlap no longer reports it unread (phase 2)

`test_a_batch_of_an_unknown_repo_is_not_compared` held a batch of an absent repo as open. Under R4 it is left-scope and closed out; the test now uses a truncated repo list for the unread case and asserts the complete-list case reports nothing.

<!-- fr:journal kind=discovery scope=plan id=p2-pill-class created=2026-11-27T13:14:37+00:00 phase=2 -->
### p2-pill-class · discovery · The board card pill class is stage-<stage>, so left-scope needed its own class (phase 2)

`kanban_render._pill_class` gives a left-scope card `stage-left-scope bstage-left-scope` (the second matches the other pages' pill CSS); other pills keep `stage-<word>`.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t1 created=2026-11-27T13:14:37+00:00 phase=2 -->
### no-refactor-p2-t1 · discovery · no-refactor-because P2.T1 (phase 2)

derive_batch_stage was reordered in place; nothing duplicated to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t2 created=2026-11-27T13:14:37+00:00 phase=2 -->
### no-refactor-p2-t2 · discovery · no-refactor-because P2.T2 (phase 2)

five one-line additions to existing closed sets; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t4 created=2026-11-27T13:14:37+00:00 phase=2 -->
### no-refactor-p2-t4 · discovery · no-refactor-because P2.T4 (phase 2)

the checkout map moved out whole into fr.triage.checkouts; build_driver gained one filter

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t5 created=2026-11-27T13:14:37+00:00 phase=2 -->
### no-refactor-p2-t5 · discovery · no-refactor-because P2.T5 (phase 2)

the --orphaned flow lives in fr.triage.orphan; the command only calls it

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t6 created=2026-11-27T13:14:37+00:00 phase=2 -->
### no-refactor-p2-t6 · discovery · no-refactor-because P2.T6 (phase 2)

docs and stamps only
