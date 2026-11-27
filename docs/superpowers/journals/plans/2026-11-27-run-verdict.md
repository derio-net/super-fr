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
