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

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-11-27T13:23:25+00:00 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · After cancel --orphaned, plan_sync owes claim releases every pass that fail on the departed repo (phase 2)

Once cancelled, releasing() is true and owed_releases lists the members; execute fails each with 'its repo is not in this scope's facts' (claim_sync.py:201-204), setting failed_write so drive --once exits 1 every pass.

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-11-27T13:23:25+00:00 phase=2 state=open review_scope=in -->
### p2-r2 · finding [open] (reviewer: in scope) · build_driver loads facts.json strictly, so an unusable file makes drive exit 2 at startup (phase 2)

load_scope_facts refuses an old-schema, corrupt or other-scope file; before this change build_driver read no facts and collect re-read such a file leniently (triage_cmd._previous_facts).

<!-- fr:journal kind=finding scope=plan id=p2-r3 created=2026-11-27T13:23:25+00:00 phase=2 state=open review_scope=in -->
### p2-r3 · finding [open] (reviewer: in scope) · Docstrings of is_open, wave_queue.is_terminal and finished_waves list the old closed sets (phase 2)

batch.py:387, wave_queue.py:352, batch_drive.py:1245 omitted left-scope.

<!-- fr:journal kind=finding scope=plan id=p2-r4 created=2026-11-27T13:23:25+00:00 phase=2 state=open review_scope=out -->
### p2-r4 · finding [open] (reviewer: out of scope) · A batch that comes after a left-scope batch waits forever (phase 2)

dependency_state gives waiting for left-scope (in neither meets_dependency nor UNSATISFIABLE). Unchanged from before: the batch derived dispatched, which also waited; the spec does not decide this case.

<!-- fr:journal kind=review scope=plan id=review-p2 created=2026-11-27T13:23:25+00:00 phase=2 -->
### review-p2 · review · Phase 2 review: R4-R9 met apart from p2-r1..p2-r3 (in), p2-r4 (out) (phase 2)

Independent reviewer checked the predicate, stage order, every closed set, board, build_driver and the checkout-map move, focus and cancel --orphaned, batch list, the changed plan_overlap test, the README regeneration, the tests and the explainer.

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-11-27T13:23:25+00:00 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: After cancel --orphaned, plan_sync owes claim releases every pass that fail on the departed repo (phase 2)

plan_sync drops every batch left_scope holds, whatever its stage; test_an_orphan_cancelled_batch_plans_no_release.

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-11-27T13:23:25+00:00 phase=2 state=fixed resolves=p2-r2 -->
### p2-r2-resolved · finding [fixed] · resolves p2-r2: build_driver loads facts.json strictly, so an unusable file makes drive exit 2 at startup (phase 2)

build_driver reads facts through triage_cmd._previous_facts, so an unusable file counts as absent; test_unusable_facts_count_as_absent (old schema, corrupt, empty).

<!-- fr:journal kind=finding scope=plan id=p2-r3-resolved created=2026-11-27T13:23:25+00:00 phase=2 state=fixed resolves=p2-r3 -->
### p2-r3-resolved · finding [fixed] · resolves p2-r3: Docstrings of is_open, wave_queue.is_terminal and finished_waves list the old closed sets (phase 2)

The three docstrings name left-scope.

<!-- fr:journal kind=finding scope=plan id=p2-r4-resolved created=2026-11-27T13:23:25+00:00 phase=2 state=open resolves=p2-r4 out_of_scope=true -->
### p2-r4-resolved · finding [out-of-scope] · resolves p2-r4: A batch that comes after a left-scope batch waits forever (phase 2)

Pre-existing: a dependent of the batch waited the same way when it derived dispatched; deciding left-scope as unsatisfiable is a separate change.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r1 created=2026-11-27T14:31:27+00:00 state=open review_scope=in -->
### l-docs-accuracy-r1 · finding [open] (reviewer: in scope) · A batch whose after names a left-scope batch waits forever

dependency_state gave waiting for left-scope (batch.py:406, 439-454); a cross-repo dependent never showed blocked.

<!-- fr:journal kind=finding scope=plan id=l-errors-r1 created=2026-11-27T14:31:27+00:00 state=open review_scope=in -->
### l-errors-r1 · finding [open] (reviewer: in scope) · A take-back that first fails on a repeat dispatch failure was never said

_dispatch_failed dropped `also` once the dispatch key was reported.

<!-- fr:journal kind=finding scope=plan id=l-errors-r2 created=2026-11-27T14:31:27+00:00 state=open review_scope=in -->
### l-errors-r2 · finding [open] (reviewer: in scope) · The take-back failure line named no consequence

takeback_failed gave only the error text.

<!-- fr:journal kind=finding scope=plan id=l-tests-r1 created=2026-11-27T14:31:27+00:00 state=open review_scope=in -->
### l-tests-r1 · finding [open] (reviewer: in scope) · Direct left_scope callers had no truncated-repo-list fixture

build_driver, plan_sync, the batch list note and the verbs were tested only with complete facts.

<!-- fr:journal kind=finding scope=plan id=l-tests-r2 created=2026-11-27T14:31:27+00:00 state=open review_scope=in -->
### l-tests-r2 · finding [open] (reviewer: in scope) · The said-once test hand-built _Driver

No real two-pass drive exercised the dedupe.

<!-- fr:journal kind=finding scope=plan id=l-tests-r3 created=2026-11-27T14:31:27+00:00 state=open review_scope=in -->
### l-tests-r3 · finding [open] (reviewer: in scope) · Two assertions could not fail

`assert batch_mod` and a stylesheet source grep.

<!-- fr:journal kind=finding scope=plan id=l-tests-r4 created=2026-11-27T14:31:27+00:00 state=open review_scope=in -->
### l-tests-r4 · finding [open] (reviewer: in scope) · A repo back mid-drive had no clone and opened the cwd

build_driver dropped it from the checkout map; path_of None led to _open_checkout(None).

<!-- fr:journal kind=finding scope=plan id=l-tests-r5 created=2026-11-27T14:31:27+00:00 state=open review_scope=in -->
### l-tests-r5 · finding [open] (reviewer: in scope) · cancel --orphaned's 'no checkout' was unasserted

no_forge patched only make_client.

<!-- fr:journal kind=discovery scope=plan id=lens-fix-budget created=2026-11-27T14:31:27+00:00 -->
### lens-fix-budget · discovery · triage_batch_cmd.py budget raised 8300 -> 8320

The l-tests-r4 hold and the l-errors-r1 key needed a few lines in the command module (now 8309); the budget moved in tests/unit/test_tripwire_module_budget.py with a reason comment.

<!-- fr:journal kind=review scope=plan id=lens-review-1 created=2026-11-27T14:31:27+00:00 -->
### lens-review-1 · review · Lens review: docs-accuracy, errors, tests — 8 findings, all fixed

docs-accuracy raised l-docs-accuracy-r1; errors raised l-errors-r1..r2; tests raised l-tests-r1..r5. Each fixed with a test; fast tier green after the last fix.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r1-resolved created=2026-11-27T14:31:27+00:00 state=fixed resolves=l-docs-accuracy-r1 -->
### l-docs-accuracy-r1-resolved · finding [fixed] · resolves l-docs-accuracy-r1: A batch whose after names a left-scope batch waits forever

UNSATISFIABLE holds left-scope; fr-wave-driver.md names it; test_a_dependency_on_a_left_scope_batch_is_unsatisfiable.

<!-- fr:journal kind=finding scope=plan id=l-errors-r1-resolved created=2026-11-27T14:31:27+00:00 state=fixed resolves=l-errors-r1 -->
### l-errors-r1-resolved · finding [fixed] · resolves l-errors-r1: A take-back that first fails on a repeat dispatch failure was never said

`also` dedupes on its own key and joins the 'stopped again' line when new; real two-pass drive test plus unit test.

<!-- fr:journal kind=finding scope=plan id=l-errors-r2-resolved created=2026-11-27T14:31:27+00:00 state=fixed resolves=l-errors-r2 -->
### l-errors-r2-resolved · finding [fixed] · resolves l-errors-r2: The take-back failure line named no consequence

takeback_failed takes COLLECTED_TAKEBACK / PER_BATCH_TAKEBACK consequences; asserted in the take-back tests.

<!-- fr:journal kind=finding scope=plan id=l-tests-r1-resolved created=2026-11-27T14:31:27+00:00 state=fixed resolves=l-tests-r1 -->
### l-tests-r1-resolved · finding [fixed] · resolves l-tests-r1: Direct left_scope callers had no truncated-repo-list fixture

Truncated twins for build_driver, plan_sync, batch list, cancel --orphaned and focus.

<!-- fr:journal kind=finding scope=plan id=l-tests-r2-resolved created=2026-11-27T14:31:27+00:00 state=fixed resolves=l-tests-r2 -->
### l-tests-r2-resolved · finding [fixed] · resolves l-tests-r2: The said-once test hand-built _Driver

A real two-pass drive (--interval, _sleep patched); the unit test builds `also` through takeback_failed.

<!-- fr:journal kind=finding scope=plan id=l-tests-r3-resolved created=2026-11-27T14:31:27+00:00 state=fixed resolves=l-tests-r3 -->
### l-tests-r3-resolved · finding [fixed] · resolves l-tests-r3: Two assertions could not fail

Removed the first; the second asserts the rendered backlog and history pages carry the rule.

<!-- fr:journal kind=finding scope=plan id=l-tests-r4-resolved created=2026-11-27T14:31:27+00:00 state=fixed resolves=l-tests-r4 -->
### l-tests-r4-resolved · finding [fixed] · resolves l-tests-r4: A repo back mid-drive had no clone and opened the cwd

checkouts.unclone_reasons feeds the snapshot's unread hold: one report-once line naming --checkout, nothing opened; test_a_repo_back_mid_drive_with_no_clone_is_held_not_opened_at_the_cwd.

<!-- fr:journal kind=finding scope=plan id=l-tests-r5-resolved created=2026-11-27T14:31:27+00:00 state=fixed resolves=l-tests-r5 -->
### l-tests-r5-resolved · finding [fixed] · resolves l-tests-r5: cancel --orphaned's 'no checkout' was unasserted

no_forge also patches make_checkout, _open_checkout and _tracking_gate; plan and --yes paths assert none called.

<!-- fr:journal kind=finding scope=plan id=p2-r4-resolved-2 created=2026-11-27T14:34:51+00:00 state=fixed resolves=p2-r4 answered_by=operator -->
### p2-r4-resolved-2 · finding [fixed] · resolves p2-r4: A batch that comes after a left-scope batch waits forever

Fixed in this PR by l-docs-accuracy-r1: left-scope is in UNSATISFIABLE, so a dependent shows blocked (test_a_dependency_on_a_left_scope_batch_is_unsatisfiable). Operator approved marking it fixed.
