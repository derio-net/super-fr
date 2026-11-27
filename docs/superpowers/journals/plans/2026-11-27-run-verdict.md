<!-- fr:journal-schema=4 -->
# Journal: 2026-11-27-run-verdict

<!-- fr:journal kind=decision scope=plan id=p1-emitted-plan-to-steps created=2026-11-27T17:06:34+00:00 phase=1 -->
### p1-emitted-plan-to-steps · decision · _emitted_plan moved to fr/run/steps.py now, and record/apply.py imports it from there (phase 1)

derived.py needs emitted_plan without importing fr.commands, so it moved to fr/run/steps.py (the module phase 2 fills). run_cmd keeps it as `_emitted_plan` (its body uses it); record/apply.py's one call now reads `fr.run.steps.emitted_plan` (R11).

<!-- fr:journal kind=decision scope=plan id=p1-derive-patch-point created=2026-11-27T17:06:34+00:00 phase=1 -->
### p1-derive-patch-point · decision · tests that fake a derived witness patch run_cmd's imported alias, the name derive reads (phase 1)

derive calls `_settle(_proportionality_witness(...))`, where `_proportionality_witness` is run_cmd's alias of fr.run.evidence.derived.proportionality_witness, so test_run_settle_witness patches that alias with a fake returning a refusing Verdict (patching the derived module would not reach derive). Tests of the unobserved channel now import fr.run.unobserved directly.

<!-- fr:journal kind=discovery scope=plan id=p1-derived-fixture-capture created=2026-11-27T17:06:34+00:00 phase=1 -->
### p1-derived-fixture-capture · discovery · the derived refusal capture fakes inputs at their source modules, so the same setup drives old and new code (phase 1)

tests/unit/test_run_verdict_derived.py fakes fr.parser.parse, fr.proportionality.run_report, fr.run.target.target_ref, fr.git.remote_default_ref/git_answer, fr.isolation.types.load_state and fr.docs.* (all imported inside the functions at call time), so one case table drove the pre-move run_cmd functions (captured once into tests/fixtures/run_verdict/derived/ by a throwaway script) and now drives the moved ones. 12 cases, incl. the fallback announce warning followed by a later refusal, for both witnesses.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-11-27T17:06:34+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

verdict.py is four new stdlib definitions written as the spec's Design states them; nothing pre-existing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-11-27T17:06:34+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

unobserved.py is a verbatim move and the adapter is the spec's three functions; the only cleanup, dropping the now-unused TESTS_PROVENANCE_SURFACE import from run_cmd, was done in the green step

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-11-27T17:06:34+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

a move that must keep its bytes; the one structural change (derive accepting str | None and asserting the settled witness) was needed for mypy in the green step, and record/apply.py now imports emitted_plan from fr.run.steps instead of run_cmd

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-27T17:15:24+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · test_run_verdict_derived.py keeps a never-called Case.old/_old capture driver naming run_cmd._witness_base (gone) and the now-Verdict-returning aliases (phase 1)

tests/unit/test_run_verdict_derived.py:128-169 and every _old(...) in _cases(); dead and misleading. Fix - drop the field and helper, name the capture commit in the docstring.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-27T17:15:24+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · row run-engine-cli-free moved to ci while its acceptance says one allowance and the layering test still permits the temporary adopt.py one (phase 1)

docs/acceptance/features/2026-11-27-run-verdict.yaml; tests/unit/test_run_writes_layering.py:96-99 allows adopt.py until phase 2. Fix - name the temporary allowance in the row's notes.

<!-- fr:journal kind=review scope=plan id=review-p1-1 created=2026-11-27T17:15:24+00:00 phase=1 -->
### review-p1-1 · review · phase 1 reviewed by an independent reviewer; 2 findings, both in scope, both fixed (phase 1)

Reviewer checked byte identity of every moved Say against the pre-move prints, derive's gh#768 accumulation, _refusals' cause, unobserved.py, the layering test (per-file package, rich.markup both spellings, both old test names kept), the re-pointed patches, fixtures captured before the move (b39ef3751 before f53d3542f), budget, fragment and stamps. Findings p1-r1 (dead pre-move driver in the capture test) and p1-r2 (row note did not name the temporary adopt.py allowance), both fixed.

<!-- fr:journal kind=lens scope=plan id=lens-tests-1 created=2026-11-27T17:15:24+00:00 phase=1 lens=tests step=review-phase -->
### lens-tests-1 · lens · each later slice's fixtures must be captured before its move, with no capture driver left behind as dead code (phase 1)

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-27T17:15:24+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: test_run_verdict_derived.py keeps a never-called Case.old/_old capture driver naming run_cmd._witness_base (gone) and the now-Verdict-returning aliases (phase 1)

Removed Case.old and _old; the docstring names capture commit b39ef3751 (test commit after the review). 13 tests pass.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-27T17:15:24+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: row run-engine-cli-free moved to ci while its acceptance says one allowance and the layering test still permits the temporary adopt.py one (phase 1)

set-status --notes on run-engine-cli-free names the temporary adopt.py allowance that slice 2 removes.

<!-- fr:journal kind=decision scope=plan id=p2-adapters-in-run-cmd created=2026-11-27T18:29:45+00:00 phase=2 -->
### p2-adapters-in-run-cmd · decision · unit_key and resolve_manifest_for_read are reached through two adapter functions in run_cmd, not wrapped at every call site (phase 2) (phase 2)

`_unit_key` runs `fr.run.steps.unit_key` inside `_refusals()` and `_resolve_manifest_for_read` passes `_say` as the warn; the two names keep their one definition each so the 12 call sites see typer.Exit and the printed warning exactly as before. Other moved names are imported under their old underscore spellings because run_cmd's body uses them; tests, record/apply.py, verification/baseline.py, pickup_cmd.py and adopt.py use fr.run.steps directly.

<!-- fr:journal kind=discovery scope=plan id=p2-lookup-capture created=2026-11-27T18:29:45+00:00 phase=2 -->
### p2-lookup-capture · discovery · the lookup capture drives one case table through run_cmd's old functions once and now through the moved ones (phase 2) (phase 2)

tests/unit/test_run_verdict_steps.py holds the cases; the fixtures in tests/fixtures/run_verdict/steps/ were taken by a throwaway script (not committed) that called run_cmd's pre-move functions with the same table, in commit 74f3a5ee8 before the move. The test calls only fr.run.steps; no pre-move driver is left behind. 9 cases: 7 unit_key refusals incl. the unparseable-plan AdoptError path, 2 drift warnings (step list, members).

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t1 created=2026-11-27T18:29:45+00:00 phase=2 -->
### no-refactor-p2-t1 · discovery · no-refactor-because P2.T1 (phase 2)

a capture task: fixtures and a test, nothing pre-existing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t2 created=2026-11-27T18:29:45+00:00 phase=2 -->
### no-refactor-p2-t2 · discovery · no-refactor-because P2.T2 (phase 2)

a verbatim move that must keep its bytes; the only cleanup (unused imports left in run_cmd) was done in the green step

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-11-27T18:35:50+00:00 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · pickup_cmd._say prints through a highlight-on Console, while the old warning used run_cmd's highlight=False console, so a TTY warning is no longer byte-identical (phase 2)

packages/fr/src/fr/commands/pickup_cmd.py `_say`; pickup's err_console is Console(stderr=True) with highlighting on. Fix - pass highlight=False.

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-11-27T18:35:50+00:00 phase=2 state=open review_scope=in -->
### p2-r2 · finding [open] (reviewer: in scope) · fr docs check fails - fr-brainstorming-and-plan.md (pickup_cmd.py) and verification-strategies.md (baseline.py) have no updated reviewed stamp (phase 2)

Both pages stay true; the change is an import re-point. Fix - stamp both.

<!-- fr:journal kind=finding scope=plan id=p2-r3 created=2026-11-27T18:35:50+00:00 phase=2 state=open review_scope=in -->
### p2-r3 · finding [open] (reviewer: in scope) · run-verdict acceptance fragment's layering-row note still says the adopt.py allowance exists until slice 2, which this phase removed (phase 2)

docs/acceptance/features/2026-11-27-run-verdict.yaml run-engine-cli-free note. Fix - set-status --notes with current wording.

<!-- fr:journal kind=review scope=plan id=review-p2-1 created=2026-11-27T18:35:50+00:00 phase=2 -->
### review-p2-1 · review · phase 2 reviewed by an independent reviewer; 3 findings, all in scope, all fixed (phase 2)

Reviewer confirmed byte identity of all seven unit_key Says and the drift warning, the run_cmd adapters keep refusals at the same frame for _advance_once, derive, resolve_in_process and the claim/resolve paths, record/apply.py reaches no RunRefusal-raising function, fixtures captured in 74f3a5ee8 before the move with no dead driver, no compat re-export, layering names kept, budget +20; ran 446 tests green. Findings p2-r1 (pickup warning highlighting), p2-r2 (two page stamps), p2-r3 (stale row note), all fixed.

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-11-27T18:35:50+00:00 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: pickup_cmd._say prints through a highlight-on Console, while the old warning used run_cmd's highlight=False console, so a TTY warning is no longer byte-identical (phase 2)

pickup_cmd._say passes highlight=False; test_pickup_prints_the_drift_warning_unhighlighted failed before the fix and passes after.

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-11-27T18:35:50+00:00 phase=2 state=fixed resolves=p2-r2 -->
### p2-r2-resolved · finding [fixed] · resolves p2-r2: fr docs check fails - fr-brainstorming-and-plan.md (pickup_cmd.py) and verification-strategies.md (baseline.py) have no updated reviewed stamp (phase 2)

Stamped fr-brainstorming-and-plan.md and verification-strategies.md, plus fr-exit-gates.md which covers the latter; fr docs check reports 33 pages current.

<!-- fr:journal kind=finding scope=plan id=p2-r3-resolved created=2026-11-27T18:35:50+00:00 phase=2 state=fixed resolves=p2-r3 -->
### p2-r3-resolved · finding [fixed] · resolves p2-r3: run-verdict acceptance fragment's layering-row note still says the adopt.py allowance exists until slice 2, which this phase removed (phase 2)

set-status --notes on run-engine-cli-free now names the single workspace.py allowance.

<!-- fr:journal kind=decision scope=plan id=p3-adapters-in-run-cmd created=2026-11-27T20:01:02+00:00 phase=3 -->
### p3-adapters-in-run-cmd · decision · questions_from_flags and answered_by_or_exit keep one run_cmd adapter each; the witness and the resume hint are parameters (phase 3) (phase 3)

resolve_in_process reads the answered-by narrowing inside its held-stdout try, so a refusal there must still be a typer.Exit: `_answered_by_or_exit` and `_questions_from_flags` run the moved function inside `_refusals()`. `deliver_label_sync` takes the `fr run resolve` hint, and `deliver_local_stamp_plan` / `local_stamp_plan` take the local-suite witness function, because `_resolve_hint` (slice 4) and `_local_stamp_witness` (slice 5) are still in run_cmd and fr/run cannot import it.

<!-- fr:journal kind=decision scope=plan id=p3-stays-in-run-cmd created=2026-11-27T20:01:02+00:00 phase=3 -->
### p3-stays-in-run-cmd · decision · _queue_exit_baseline, _print_unrunnable_warnings and _spec_review_ids stay in run_cmd (phase 3) (phase 3)

They sit inside the H line range but are not gates: `_queue_exit_baseline` writes a journal decision through `_queue_gate_decision` (slice 6, C), `_print_unrunnable_warnings` reads `_unrunnable_spec_warnings` (still in run_cmd) and `_spec_review_ids` is also called from outside H. `_print_unrunnable_warnings` takes `deliver.repo_relative(root, value)`.

<!-- fr:journal kind=discovery scope=plan id=p3-show-me-skill-names-moved-function created=2026-11-27T20:01:02+00:00 phase=3 -->
### p3-show-me-skill-names-moved-function · discovery · the fr-show-me skill's call-tree example named `_deliver_pr_gate`, and test_show_me_skill checks that every function it names is defined (phase 3) (phase 3)

The example now names `deliver_pr_gate`; the OpenCode and Hermes mirrors were regenerated and docs/explainers/fr-show-me.md (which covers the skill) was stamped.

<!-- fr:journal kind=discovery scope=plan id=p3-deliver-capture created=2026-11-27T20:01:02+00:00 phase=3 -->
### p3-deliver-capture · discovery · the deliver capture drives one 40-case table through run_cmd's old functions once and now through the moved ones (phase 3) (phase 3)

tests/unit/test_run_verdict_deliver.py holds the cases; the fixtures in tests/fixtures/run_verdict/deliver/ were taken by a throwaway script (not committed) that called run_cmd's pre-move functions with the same table, in commit 6fffb053f's successor before the move. The test drives only fr.run.deliver. Repo root is a fixed path so no temp directory reaches a fixture.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t1 created=2026-11-27T20:01:02+00:00 phase=3 -->
### no-refactor-p3-t1 · discovery · no-refactor-because P3.T1 (phase 3)

a capture task: fixtures and a test, nothing pre-existing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t2 created=2026-11-27T20:01:02+00:00 phase=3 -->
### no-refactor-p3-t2 · discovery · no-refactor-because P3.T2 (phase 3)

a verbatim move that must keep its bytes; the only cleanup (imports left unused in run_cmd, the test fakes' shapes) was done in the green step

<!-- fr:journal kind=finding scope=plan id=p3-r1 created=2026-11-27T20:11:59+00:00 phase=3 state=open review_scope=in -->
### p3-r1 · finding [open] (reviewer: in scope) · test_run_verdict_deliver.py keeps a dead sym/_ALIASES shim that existed to drive run_cmd's pre-move functions; call deliver directly (phase 3)

tests/unit/test_run_verdict_deliver.py:27-41. Fix - drop _ALIASES and sym, look names up on the moved module directly.

<!-- fr:journal kind=finding scope=plan id=p3-r2 created=2026-11-27T20:11:59+00:00 phase=3 state=open review_scope=out -->
### p3-r2 · finding [open] (reviewer: out of scope) · tests/unit/test_deliver_local_stamp.py:508 docstring still names removed _deliver_exit_guard (cosmetic) (phase 3)

Only the docstring is stale; the body patches deliver.deliver_exit_guard.

<!-- fr:journal kind=review scope=plan id=review-p3-1 created=2026-11-27T20:11:59+00:00 phase=3 -->
### review-p3-1 · review · phase 3 reviewed by an independent reviewer; 1 in-scope finding fixed, 1 out-of-scope note (phase 3)

Reviewer confirmed byte identity of every moved Say (style="red" refusals, markup lines, warn-routed warnings), _resolve_body's gate order, RECORD_ROWS name and set/reset, the held-stdout flush after a refusal, record/apply.py untouched, layering, no dead names or re-exports, patches at the lookup site, fixtures captured before the move, the stay-in-run_cmd decisions, the needed fr-show-me example edit with both mirror generators in sync, budget +20, docs current. Findings p3-r1 (dead name fallback in the capture test, fixed) and p3-r2 (stale docstring, out of scope).

<!-- fr:journal kind=finding scope=plan id=p3-r1-resolved created=2026-11-27T20:11:59+00:00 phase=3 state=fixed resolves=p3-r1 -->
### p3-r1-resolved · finding [fixed] · resolves p3-r1: test_run_verdict_deliver.py keeps a dead sym/_ALIASES shim that existed to drive run_cmd's pre-move functions; call deliver directly (phase 3)

Removed _ALIASES and sym in 07ba9b646; the module parameter stays as the one injection point every case uses. 67 tests pass.

<!-- fr:journal kind=finding scope=plan id=p3-r2-resolved created=2026-11-27T20:11:59+00:00 phase=3 state=open resolves=p3-r2 out_of_scope=true -->
### p3-r2-resolved · finding [out-of-scope] · resolves p3-r2: tests/unit/test_deliver_local_stamp.py:508 docstring still names removed _deliver_exit_guard (cosmetic) (phase 3)

Cosmetic docstring only; the reviewer tagged it out of scope. The docstring was updated in passing in 07ba9b646 to name fr.run.deliver.deliver_exit_guard.

<!-- fr:journal kind=decision scope=plan id=p4-warn-and-refusal-plumbing created=2026-11-27T23:00:16+00:00 phase=4 -->
### p4-warn-and-refusal-plumbing · decision · the dispatch-record helpers take a `warn` callable and raise RunRefusal; run_cmd's call sites wrap them in `_refusals()` (phase 4) (phase 4)

`merge_claim`, `claimed_identity`, `close_on_resolve` and `observed_model` print a warning (`Say`, markup and wrap as before) through a `warn` parameter run_cmd fills with `_say`; `claimed_identity`, `tests_brief`, `manual_placement_preflight` and `lens_set_or_refuse` raise `RunRefusal`. The call sites in `_advance_group`, `_advance_step`, `_resolve_member`, `_resolve_body`, `_claim_identity` and `_print_member_dispatch` run them inside `with _refusals():`, so `resolve_in_process` and `_advance_once` still see `typer.Exit`. `_print_member_dispatch` takes `repo_root`, which `_advance_group` already holds.

<!-- fr:journal kind=decision scope=plan id=p4-phase-executor-agent-lives-in-brief created=2026-11-27T23:00:16+00:00 phase=4 -->
### p4-phase-executor-agent-lives-in-brief · decision · PHASE_EXECUTOR_AGENT moved to fr/run/brief.py with the briefs (phase 4) (phase 4)

`tests_brief` keys on it and fr/run cannot import run_cmd, so the constant is defined in brief.py and run_cmd imports it for the reviewer check that still uses it (slice 5 moves that check).

<!-- fr:journal kind=discovery scope=plan id=p4-brief-capture created=2026-11-27T23:00:16+00:00 phase=4 -->
### p4-brief-capture · discovery · the brief capture drives one 22-case table through run_cmd's old functions once and now through the moved ones (phase 4) (phase 4)

tests/unit/test_run_verdict_brief.py holds the cases; fixtures in tests/fixtures/run_verdict/brief/ (stderr, exit code, and the returned value as JSON, covering one flat brief and one grouped member brief) were taken by a throwaway driver (not committed) calling the pre-move `_`-named functions with `resolve_repo_root` patched to the test's root, in the commit before the move. The test drives only fr.run.brief and fr.run.evidence.lenses.

<!-- fr:journal kind=discovery scope=plan id=p4-docs-check-clean created=2026-11-27T23:00:16+00:00 phase=4 -->
### p4-docs-check-clean · discovery · fr docs check reported every page current after the brief move (phase 4) (phase 4)

Earlier phases stamped the pages that cover run_cmd.py; no page names a moved function, so nothing needed a new stamp.

<!-- fr:journal kind=discovery scope=plan id=p4-fast-tier-run created=2026-11-27T23:00:16+00:00 phase=4 -->
### p4-fast-tier-run · discovery · the fast tier ran 9908 passed, 118 skipped; its one collection error (test_git_policy_briefs importing commit_templates_brief from run_cmd) was fixed after and the file re-run green (phase 4) (phase 4)

The re-point grep matched `_name` and `run_cmd.<name>` spellings but not a public name imported with `from fr.commands.run_cmd import commit_templates_brief`; the run's only error was that file, and it passes alone (2 passed).

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t1 created=2026-11-27T23:00:16+00:00 phase=4 -->
### no-refactor-p4-t1 · discovery · no-refactor-because P4.T1 (phase 4)

a capture task: fixtures and a test, nothing pre-existing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t2 created=2026-11-27T23:00:16+00:00 phase=4 -->
### no-refactor-p4-t2 · discovery · no-refactor-because P4.T2 (phase 4)

a verbatim move that must keep its bytes; the only cleanup (imports left unused in run_cmd, the re-pointed tests) was done in the green step
