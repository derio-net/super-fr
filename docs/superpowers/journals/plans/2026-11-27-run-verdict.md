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
