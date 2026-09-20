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

<!-- fr:journal kind=discovery scope=plan id=p2-red-t2 created=2026-09-20T15:59:36 phase=2 -->
### p2-red-t2 · discovery · RED for P2.T2: the top-level agent step re-briefs too, and the gated path already behaves (phase 2)

Command: uv run pytest tests/unit/test_run_cli.py -q --no-cov -k "refuses_a_running_top_level or still_briefs_a_blocked" -> 1 failed, 1 passed.

test_advance_refuses_a_running_top_level_agent_step FAILED, verbatim:

    assert result.exit_code == 2, result.output
    AssertionError: plan: dispatch brief
      {"agent": null, "emits": ["plan", "journal:plan"], "for_each": null, "gate": null, "kind": "agent", "needs": ["spec"], "run": "r1", "skill": "super-fr:fr-plan", "step": "plan", "steps": [], "tier": "from_phase", "workflow": "agentic@1"}

    assert 0 == 2

test_advance_still_briefs_a_blocked_gated_agent_step PASSED on the first run, as the plan predicted. That is the point of writing it: spec 3.A leaves the gated path untouched, and the only way to know the refusal did not bleed into it is a test that was green BEFORE the change and stays green after. A blocked step is state "blocked", never "running", so the two branches cannot collide - but the new check still has to live after the _gate_pending block for that to stay true.

<!-- fr:journal kind=finding scope=plan id=p2-f1 created=2026-09-20T16:00:59 phase=2 state=fixed -->
### p2-f1 · finding [fixed] · An existing test pinned the #499 bug as the contract, and had to be rewritten, not deleted (phase 2)

test_advance_agent_step_brief_is_re_emitted_idempotently_while_running (test_run_cli.py:433) asserted exit 0 on the SECOND advance of a running top-level agent step - i.e. it pinned exactly the behaviour #499 reports as the defect. It went red the moment the refusal landed:

    assert result.exit_code == 0, result.output
    AssertionError: plan: plan is ALREADY RUNNING (dispatched 2026-09-20T13:59:54+00:00).
        Waiting on that agent - do NOT dispatch again.
        resolve it:      fr run resolve r1 --step plan --state done   (or --state failed)
        re-brief anyway: fr run advance r1 --redispatch

    assert 2 == 0

Deleting it would have dropped a claim that is still true and still load-bearing: the monkeypatched subprocess.run boom proves the second advance executes NOTHING (the structural half of no-claude-p-batch). Rewritten as test_advance_refusing_a_running_agent_step_executes_and_writes_nothing, which keeps the boom, asserts exit 2, and adds the stronger claim the refusal makes possible - the run file is byte-identical across it.

A sibling in the grouped section, test_advance_is_idempotent_over_the_snapshot, did NOT go red: its assertion (list(accounting) == ["phase/1/code"]) still holds when the second advance refuses and writes nothing. It passed for the wrong reason for one commit. Task 3 restores its meaning by giving it --redispatch, which is where re-dispatch now lives.

<!-- fr:journal kind=discovery scope=plan id=p2-red-t3 created=2026-09-20T16:02:52 phase=2 -->
### p2-red-t3 · discovery · RED for P2.T3: five redispatch tests, and two of them nearly passed for the wrong reason (phase 2)

Command: uv run pytest tests/unit/test_run_cli.py -q --no-cov -k redispatch -> 5 failed, 136 deselected.

Failure, verbatim:

    assert result.exit_code == 0, result.output
    AssertionError: Usage: fr run advance [OPTIONS] RUN_ID
      Try fr run advance --help for help.
      No such option: --redispatch

    assert 2 == 0

Worth recording: click exits 2 on an unknown option, which is the SAME code the refusal uses. So the two refusal tests (nothing outstanding, cli step) would have gone green on exit code alone while the flag did not exist at all - the "reports success while doing nothing" shape this whole PR is about. What actually held them red is the message assertion (`nothing is running` in result.output) and the state assertion beside it. Any later phase adding a refusal test to this file should assert the MESSAGE, never the bare 2.

Also pinned here: _backdate(repo, step_id) rewinds a step records `at` to 2026-01-01T00:00:00+00:00 before the re-dispatch. _now() has SECOND resolution, so two advances in one test usually land on the same string and an "at moved" assertion would be a coin flip. Phases 3-7 asserting a refreshed timestamp should reuse it.

<!-- fr:journal kind=discovery scope=plan id=p2-d1 created=2026-09-20T16:12:16 phase=2 -->
### p2-d1 · discovery · What phases 3-7 inherit: _advance_group's new shape, two refusal renderers, and the --redispatch contract (phase 2)

All in packages/fr/src/fr/commands/run_cmd.py.

_advance_group is now (repo_root, state, manifest, step, record, *, redispatch: bool = False). Its head is FLAT on purpose - three statements before any dispatch work, in this order:

  1. running = next((k for k in expected if items.get(k) == "running"), None)
  2. if running is not None and not redispatch: -> _already_running_refusal, exit 2
  3. if redispatch and running is None: -> _nothing_running_refusal, exit 2
  4. pending = running if redispatch else next((k for k in expected if items.get(k) != "done"), None)
  5. if pending is None: complete the group, return

PHASE 5 (manual filter + preflight) adds to the SAME function. Put the manual filter inside _expected_group_items or immediately after it, i.e. ABOVE line 1 - `expected` is the one place that decides which units exist, and both refusals above read it. Filtering later would mean a manual phase can still be the `running` key. The preflight belongs after line 5 and before the snapshot/items write, where `pending` is known and nothing has been saved yet. An earlier draft nested these as if/elif/else with the type annotation buried in a branch; it typechecked but the next person adding a rule had to re-derive the precedence. Keep it flat.

Two renderers, both returning a string with rich markup and printed with soft_wrap=True:
- _already_running_refusal(step_id, subject, at, run_id, member_id, item) - collapses "plan: plan is" to "plan is" when subject == step_id; item=None drops --item.
- _nothing_running_refusal(subject, detail, run_id) - `detail` is the only per-call-site difference.

_resolve_hint now takes item: str | None (None omits --item). Its (member, item) argument order is still the opposite of _split_member_id`s (item, member) return - p1-d1`s trap is unchanged.

--redispatch contract, pinned by five tests: it re-briefs the OUTSTANDING unit only; never selects a different unit; never resets an item to pending; refreshes the record`s `at` (hence `or redispatch` in the save guard - neither state nor items moves on a re-dispatch, so without it the next refusal would name the original dispatch); rewrites only that unit`s accounting snapshot; and exits 2 when nothing is running. advance_cmd holds a guard `if redispatch and record.state != "running"` BEFORE every other branch, which is also what keeps the flag away from cli steps (a cli step is executed inline and is never `running`) and away from the gated path.

<!-- fr:journal kind=decision scope=plan id=d8 created=2026-09-20T17:29:12 phase=6 -->
### d8 · decision · Operator scoped p1-f2's two root causes INTO this PR, as phase 6 task 3 (phase 6)

Phase 1 surfaced three Mac-only suite failures, verified pre-existing (CI green on main, branch never touched those files). Neither fr journal resolve state — fixed | refuted — is honest for 'real, but not here', so an open finding would have blocked deliver. Offered three ways out; the operator chose to fix both causes here. The reasoning that carried it: cause 1 is this PR's own subject — fr run start's refusal is printed without soft_wrap, so rich folds it and the assertion straddles the break, the same defect as p1-f1 and r1-f2 one function away. Fixing the SOURCE rather than the test makes an operator-facing refusal readable on any host with long tmp paths. Cause 2 is a one-line monkeypatch of the fourth workflow-resolution source. Plan edited mid-flight to add P6.T3.S1-S4; self-review re-run and passing.

<!-- fr:journal kind=review scope=plan id=r2-ok created=2026-09-20T17:30:45 phase=2 -->
### r2-ok · review · Phase 2 review: no finding. Gate path, redispatch precedence and the suite state all verified independently (phase 2)

Read the whole diff rather than the report. Checks that mattered: (1) the ALREADY RUNNING branch sits AFTER _gate_pending in advance_cmd, and the gated-brief test was green both before and after the change — the refusal does not bleed into the gate path, which was the one way this could have broken the shipped fr-goal shape at its first step. (2) The top-level branch's save became unconditional, which is correct only because 'running' is refused above it and redispatch+running is the intended fall-through; traced both. (3) 'if redispatch and record.state != \"running\"' sits before the run-complete check, so --redispatch on a finished run reports 'nothing is running (the step is done)' rather than 'run complete' — different from before, and better. (4) Ran the full suite myself: 3 failed, 3303 passed, and the three are EXACTLY the p1-f2 set. CONSIDERED AND DECLINED: the running-check scans 'expected', so a stale running key for a phase removed from the plan mid-run would not be seen. Making it scan 'items' instead is one line but introduces a crash path — 'next(m for m in step.steps if m.id == member_id)' would raise StopIteration on an orphan key — and a plan losing a phase mid-run is drift the plan machinery owns. Left as is, deliberately, recorded so the next reader need not re-derive it.
