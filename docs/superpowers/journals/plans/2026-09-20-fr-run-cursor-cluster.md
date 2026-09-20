# Journal: 2026-09-20-fr-run-cursor-cluster

<!-- fr:journal kind=discovery scope=plan id=nrb-P1-T3 created=2026-09-20T15:29:53 -->
### nrb-P1-T3 · discovery · no-refactor-because P1.T3

This task runs lint, types and the full suite, then flips one acceptance row with fr acceptance set-status. It writes no product code — there is nothing to restructure, and inventing a refactor step here would be ceremony that dilutes the marker's meaning where it is real (P1.T1.S3, P1.T2.S3 both do genuine extraction).

<!-- fr:journal kind=discovery scope=plan id=nrb-P3-T3 created=2026-09-20T15:29:53 -->
### nrb-P3-T3 · discovery · no-refactor-because P3.T3

This task edits two sentences of SKILL.md prose, regenerates the OpenCode mirror with scripts/sync-opencode.py, and runs the gates. The mirror is GENERATED — refactoring it is forbidden by AGENTS.md, and two sentences of token-budgeted prose have no internal structure to improve.

<!-- fr:journal kind=discovery scope=plan id=nrb-P4-T3 created=2026-09-20T15:29:53 -->
### nrb-P4-T3 · discovery · no-refactor-because P4.T3

This task runs fr plan self-review over the live plan corpus and the full suite, fixing any inline-constructed test plan that violates the new rule. Those fixes are corrections to test DATA, not code with a shape; the rule's own extraction happened in P4.T1.S3 (_trailing_manual_block) and P4.T2.S3 (merging the two passes).

<!-- fr:journal kind=discovery scope=plan id=nrb-P5-T3 created=2026-09-20T15:29:54 -->
### nrb-P5-T3 · discovery · no-refactor-because P5.T3

This task runs the gate sweep and flips one acceptance row. The refactor for this phase's real code is P5.T2.S3, which re-reads _advance_group end to end after it has accumulated the running-check, the manual filter and the preflight.

<!-- fr:journal kind=discovery scope=plan id=nrb-P6-T1 created=2026-09-20T15:29:54 -->
### nrb-P6-T1 · discovery · no-refactor-because P6.T1

This task verifies the external renderer, edits three passages of published prose, and regenerates the HTML. The .html is generated and must never be hand-edited (explainers-currency.md); the .md is narrative prose for a reader who has never seen this repo. Neither has code structure to improve. The plan's whole-diff refactor pass is P6.T2.S3.

<!-- fr:journal kind=discovery scope=plan id=p1-red-t1 created=2026-09-20T15:34:34 phase=1 -->
### p1-red-t1 · discovery · RED for P1.T1: the shipped fr-goal manifest IS drivable to implement in a unit test (phase 1)

`uv run pytest tests/unit/test_run_cli.py -k composite -q --no-cov` failed with:

    assert '--step implement-phase' in "step 'phase/1/implement-phase' not found in workflow 'fr-goal'\n"

That is today's message verbatim, produced by the real runtime: the new helper `_fr_goal_at_implement` copies `plugins/super-fr/workflows/fr-goal.yaml` into the test's shipped dir and walks it with real `fr run` invocations — start, advance (brainstorm blocks on its operator gate), resolve brainstorm --emitted spec=, advance, resolve spec-review, advance, resolve plan --emitted plan=, advance (executes the `plan-review` `kind: cli` step for real). Cursor lands on `implement`.

Two facts phases 2-5 can rely on:
1. `plan-review` (`run: fr plan self-review {{ artifacts.plan }}`) EXITS 0 against `tests/unit/fixtures/v2_plan_minimal` even though it prints a complaint that the fixture's spec does not resolve. So the cli step does not block the walk. It does shell out to whatever `fr` is on PATH (the venv's, under `uv run pytest`), which is the one environmental coupling in this helper.
2. The ambient `CLAUDECODE=1` in a Claude Code session makes `_gate_degradation_notice()` return None, so the gated `brainstorm` advance prints no notice and exits 0. A test that cares about the notice must use `_invoke_as_harness`.

<!-- fr:journal kind=finding scope=plan id=p1-f1 created=2026-09-20T15:36:41 phase=1 state=fixed -->
### p1-f1 · finding [fixed] · _advance_group printed its JSON brief without soft_wrap, so rich folded it at 80 columns (phase 1)

Found while writing P1.T2.S1's RED test. `advance_cmd`'s top-level agent branch prints its brief with `soft_wrap=True` and carries a comment explaining why (rich's default folding breaks a long token mid-string and produces invalid JSON). `_advance_group` — the grouped `for_each` branch, which is the one fr-goal actually uses for every phase — did not.

Observed in the RED run: the brief came back as three physical lines, the fold landing inside the object between `"run": "r1", ` and `"skill": null`. `_brief_of` (`json.loads(output[output.index('{'):])`) survives that because the inserted newline is legal inter-token whitespace, which is why no existing test caught it. A harness doing `tail -1` gets a fragment.

Rich picks width 80 whenever stdout is not a tty — i.e. exactly when a harness is piping it — so this was a live defect, not a test artifact. Fixed in the same edit as the hint line, since spec 3.B's ordering requirement ('the brief must remain the last stdout line a naive tail -1 parses') is meaningless while the brief is not one line.

Phases 2-5 touching `_advance_group`: the print block at the end of that function is now three `console.print` calls, all `soft_wrap=True`, in the order human-line / resolve-hint / JSON. Keep the JSON last.
