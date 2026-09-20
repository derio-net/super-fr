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

<!-- fr:journal kind=finding scope=plan id=p1-f2 created=2026-09-20T15:46:06 phase=1 state=open -->
### p1-f2 · finding [open] · Three suite failures are pre-existing and HOST-SPECIFIC — not this branch, and expected green in CI (phase 1)

`uv run pytest -q --no-cov` on this workspace ends `3 failed, 3292 passed, 80 skipped`. All three predate phase 1 and predate the branch. Proven, not assumed: (a) `git checkout 9b4d903 -- packages/fr/src/fr/commands/run_cmd.py tests/unit/test_run_cli.py` (the plan commit, before any phase-1 code) reproduces exactly the same three; (b) `git diff --stat origin/main...HEAD -- packages/fr/src/fr/run/ packages/fr/src/fr/workflow/ tests/unit/test_run_workspace.py tests/unit/test_workflow_check.py` is EMPTY, so the branch has never touched the code or the tests involved.

Causes, both host-local — they should be green on CI's Linux runners, and a later phase seeing them should not go hunting:

1. `test_run_workspace.py::test_a_forged_worktree_marker_in_a_plain_directory_is_refused` and `::test_an_external_marker_without_container_evidence_is_refused` — rich folds the refusal at the console width and the assertion's substring straddles the fold (`...is not a linked git \nworktree`). The message embeds `tmp_path`, and macOS pytest tmp paths (`/private/var/folders/dr/<random>/T/pytest-of-<user>/...`) are far longer than Linux's `/tmp/pytest-of-runner/...`, so where the fold lands is a function of the host's tmp path length. A real latent fragility (same class as the p1-f1 soft_wrap defect), but out of phase 1's scope.

2. `test_workflow_check.py::test_cli_all_fails_when_nothing_is_discoverable` — it monkeypatches `packaged_shipped_workflows_dir` to defeat the wheel-internal copy, but `fr/workflow/resolve.py` has a FOURTH source it does not defeat: `Path.home() / '.claude/plugins/marketplaces/derio-net--super-fr/plugins/super-fr/workflows'` (resolve.py:88, :174). This machine has super-fr installed there, so `--all` finds `fr-goal: ok` and exits 0 where the test wants 1. On a runner with no marketplace install there is nothing to find and it passes.

Left OPEN deliberately: phase 1 must not widen into unrelated fixes, but both are genuine and worth a follow-up issue.

<!-- fr:journal kind=discovery scope=plan id=p1-d1 created=2026-09-20T15:47:09 phase=1 -->
### p1-d1 · discovery · What phase 2 inherits: _split_member_id and _resolve_hint signatures, and the print order in _advance_group (phase 1)

Both helpers live in `packages/fr/src/fr/commands/run_cmd.py`.

`_split_member_id(manifest: WorkflowManifest, step_id: str) -> tuple[str, str] | None` — sits immediately above `_find_step`. Returns `(item, member_id)`, in that order (`('phase/1', 'implement-phase')`), or None. Recognition is manifest-driven, not string-shaped: it splits on the LAST slash and requires the tail to name a member of a step that has `for_each` set, so `foo/bar` with no matching member still gets the plain not-found message. It never resolves the composite — spec 3.B keeps one canonical spelling in `--step`.

`_resolve_hint(run_id: str, member_id: str, item: str) -> str` — sits immediately above `_advance_group`. Note the argument order is (member, item), the same order the flags print in, NOT the (item, member) tuple `_split_member_id` returns; phase 2 must not splat one into the other. Returns exactly `fr run resolve <run> --step <member> --item <item> --state done|failed` with no leading indent and no trailing newline — the caller supplies its own prefix (`advance` prints `  resolve with: ` + the string).

`_advance_group` now ends with THREE console.print calls, all soft_wrap=True, in this order:
1. `f"{step.id}: dispatch brief ({pending})"`
2. `f"  resolve with: {_resolve_hint(state.run, member_id, item)}"`
3. the `json.dumps(...)` brief

Phase 2's ALREADY RUNNING refusal returns BEFORE all three and goes to `err_console` with exit 2, so the invariant 'the JSON brief is the last stdout line' is not at risk there — but anything phase 2 adds to the dispatching path must stay above line 3. `_brief_of` in the tests (`json.loads(output[output.index('{'):])`) is tolerant of a leading hint because the hint contains no brace; do not put a `{` in any line printed before the brief.

<!-- fr:journal kind=finding scope=plan id=r1-f1 created=2026-09-20T15:52:54 phase=1 state=fixed -->
### r1-f1 · finding [fixed] · The resolve hint printed --state done|failed, which is not pasteable — it pipes (phase 1)

The hint is printed under 'resolve with:' and is meant to be copy-pasted. In every POSIX shell | is a pipe, so pasting 'fr run resolve r1 --step implement-phase --item phase/1 --state done|failed' RUNS the resolve with --state done and then dies with 'command not found: failed', exit 127 — over a run whose state has already moved. A line that reports failure while having done the thing is exactly the defect class this PR exists to remove, reintroduced by the hint that teaches the fix. Demonstrated in a real shell, not reasoned about. FIXED: _resolve_hint gained a state parameter defaulting to 'done' (matching the precedent already set by the operator-gate hint at run_cmd.py:1091) and the caller appends '(or --state failed)' as prose OUTSIDE the pasteable span. Pinned by test_the_printed_resolve_command_actually_runs_as_printed, which lifts the line off stdout, shlex.splits it and RUNS it — and which was confirmed to fail against the old spelling before being kept.

<!-- fr:journal kind=finding scope=plan id=r1-f2 created=2026-09-20T15:52:55 phase=1 state=fixed -->
### r1-f2 · finding [fixed] · The new composite-id refusal is rendered through the one err_console.print in resolve_cmd that lacks soft_wrap (phase 1)

_find_step's message now ends in the flag pair the reader is supposed to copy, but resolve_cmd's except block printed it without soft_wrap=True, so rich folds it at width 80 whenever stderr is not a tty — which is exactly when a harness captures it. Same defect class as p1-f1, which phase 1 had just fixed one function away, and the same class as the two pre-existing workspace-test failures in p1-f2: an operator-facing refusal that a fold makes unusable. Today's ids are short enough not to fold, so this is prophylactic rather than an observed break — recorded honestly as such. FIXED and pinned by test_the_composite_id_refusal_survives_a_narrow_console.

<!-- fr:journal kind=discovery scope=plan id=p2-red-t1 created=2026-09-20T15:56:54 phase=2 -->
### p2-red-t1 · discovery · RED for P2.T1: the second advance re-emits a byte-identical brief, exit 0 (phase 2)

Command: uv run pytest tests/unit/test_run_cli.py::test_advance_refuses_a_running_member -q --no-cov

Failure, verbatim (the whole stdout of the SECOND advance is the assertion message, which is the point — it is indistinguishable from the first):

    assert result.exit_code == 2, result.output
    AssertionError: implement: dispatch brief (phase/1/implement-phase)
        resolve with: fr run resolve r1 --step implement-phase --item phase/1 --state done   (or --state failed)
      {"agent": "super-fr:fr-phase-executor", "emits": ["journal:plan"], "for_each": "phase", "gate": null, "group": "implement", "item": "phase/1", "kind": "agent", "needs": ["spec", "plan"], "run": "r1", "skill": null, "step": "implement-phase", "steps": [], "tier": "from_phase", "workflow": "fr-goal@1"}

    assert 0 == 2
     +  where 0 = <Result okay>.exit_code

Driven through the REAL shipped fr-goal manifest via phase 1s _fr_goal_at_implement, so this is fr-goals own phase/1/implement-phase, not a stand-in.
