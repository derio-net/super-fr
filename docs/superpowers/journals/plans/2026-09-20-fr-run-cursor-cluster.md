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

<!-- fr:journal kind=discovery scope=plan id=p3-red-t1 created=2026-09-20T17:34:21 phase=3 -->
### p3-red-t1 · discovery · RED for P3.T1: both bind tests fail on the flag not existing, and the state file is a second artifact (phase 3)

`uv run pytest tests/unit/test_run_cli.py -k 'binds_the_session or warns_but_succeeds' -q --no-cov` → 2 failed. Both fail identically, at the click layer:

    Usage: fr run start [OPTIONS] WORKFLOW
    ╭─ Error ─╮
    │ No such option: --session │
    ╰─╯
    assert 2 == 0

Trap noted and avoided: click's usage error is ALSO exit 2, so a test asserting only `exit_code == 2` would pass with the flag absent. Both of these assert `exit_code == 0` plus a positive fact (the binding, or the stderr text), so neither can pass by accident.

Discovery worth carrying: `_repo` builds a real linked worktree carrying a `.fr-isolation` MARKER, which is what `ensure_run_workspace` reads — but `sessions.attach` reads a DIFFERENT artifact, the isolation STATE file at `<common .git>/fr/isolation/<branch>.json`, which only `fr isolation up` writes. A test that only has the marker gets `IsolationError` from attach, i.e. the warning path. New helper `_isolation_state_for(repo, branch)` writes that state; `state_path` resolves through `_git_common_dir`, so repo_root=the worktree and repo_root=the base clone key to the same file, exactly as spec 3.C.1 says.

`FR_SESSIONS_DIR` is set to tmp in both tests so the per-session index under ~/.cache/fr/sessions is never touched by the suite.

<!-- fr:journal kind=discovery scope=plan id=p3-red-t2 created=2026-09-20T17:37:33 phase=3 -->
### p3-red-t2 · discovery · RED for P3.T2: the hook logs nothing for 'fr run start', and the two negatives pass vacuously until it does (phase 3)

`uv run pytest tests/unit/test_hooks_session_bind.py -q --no-cov` → `1 failed, 16 passed`. The positive case:

    assert [] == ['isolation a...rness claude']
    Right contains one more item: 'isolation attach --session sess-1 --repo <tmp>/repo --branch feat/x --harness claude'

Said plainly, because it matters for judging the test's worth: the two NEGATIVE cases I added in the same step (`echo fr run start --branch a`, `fr run advance r1`) pass in the RED run for the wrong reason — the hook matches no `fr run` spelling at all yet, so everything is a no-op. They only become meaningful once GREEN lands, which is why they are asserted again after it. `echo fr run start` is the start-anchoring guard the plan asks for explicitly; `fr run advance r1` is the extra one — `advance` creates no workspace, so binding on it would attribute a session to a workspace it may not be in.

<!-- fr:journal kind=discovery scope=plan id=p3-d1 created=2026-09-20T17:40:39 phase=3 -->
### p3-d1 · discovery · A SKILL.md edit has TWO generated mirrors, and the plan step only names one (phase 3)

P3.T3.S2 says to run `scripts/sync-opencode.py`. That is necessary and not sufficient: `.hermes/skills/fr/<name>/SKILL.md` is a second byte-for-byte mirror, regenerated by `scripts/sync-hermes.py`, and it drifted the moment the fr-goal prose changed:

    diff .hermes/skills/fr/fr-goal/SKILL.md plugins/super-fr/skills/fr-goal/SKILL.md
    21c21,26 ...

Its drift guard is `tests/unit/test_tripwire_hermes_skills_sync.py`, a sibling of the OpenCode one, so the full suite would have caught it — but only at the end, and the phase would have looked done. Both were regenerated and both `--check` runs are clean. Any later phase touching a canonical skill or rule must run BOTH scripts; AGENTS.md's 'Skills/rules: canonical source vs. generated mirrors' section names only the OpenCode one, which is the prose gap that made this easy to miss.

<!-- fr:journal kind=finding scope=plan id=p3-f1 created=2026-09-20T17:45:46 phase=3 state=fixed -->
### p3-f1 · finding [fixed] · fr-goal/SKILL.md was sitting exactly ON its 120-line ceiling, so 'two sentences' cost two test failures (phase 3)

The full suite came back `5 failed` where phase 1 recorded 3. The two extras were mine:

    FAILED tests/unit/test_skill_validation.py::TestSkillValidation::test_under_120_lines[fr-goal]
      AssertionError: fr-goal/SKILL.md has 125 lines (max 120)
    FAILED tests/unit/test_fr_goal_hermes_dispatch.py::test_fr_goal_stays_under_120_lines

The file was at 120 of 120 before the edit — the budget the plan step warns about is enforced in LINES, by two independent tests, and it had zero headroom. The instinct to wrap new prose at the ~95 columns the surrounding text uses is what broke it; the budget does not count columns. The file already carries lines of 561, 312 and 304 characters, so the fix is the file's own existing convention: the two sentences were rewrapped onto the physical line they continue, and the trimmed wording is shorter besides. Back to 120 lines, both tests green, and the OpenCode + Hermes mirrors regenerated after the rewrap.

For any later phase editing a shipped skill: check `wc -l` BEFORE writing, not after. Several of these files are at or near their ceiling.

<!-- fr:journal kind=discovery scope=plan id=p3-d2 created=2026-09-20T17:50:11 phase=3 -->
### p3-d2 · discovery · What phases 4-7 inherit from phase 3: _bind_session, the hook's fall-through verb, and two live line budgets (phase 3)

**`_bind_session(workspace, branch, session, harness)`** — `packages/fr/src/fr/commands/run_cmd.py`, immediately above `start_cmd`. Returns early when `session` is falsy, so an unflagged `start` is byte-identical to before. Catches only `IsolationError` and prints TWO stderr lines, both `soft_wrap=True`: the warning, then a pasteable `fr isolation attach --session <s> --branch <b> --harness <h>` recovery line. That recovery line carries no shell metacharacter — r1-f1's rule — and deliberately omits `--repo`, because `state_path` resolves through `_git_common_dir` and the base clone and the worktree therefore key to the same state file.

It is called AFTER `save_run_state` and after `start_cmd`'s two `console.print` calls. Anything a later phase adds to `start_cmd` should stay above it; `start` has no JSON-brief-last invariant (that is `advance`), and the warning is on stderr, so stdout is unchanged either way.

**run_cmd.py gained two module-level imports** — `from fr.isolation import sessions as _sessions` and `from fr.isolation.types import IsolationError`. No cycle: `fr.isolation.sessions` imports only `.types`. `fr/run/workspace.py`'s lazy `_select_target` import is a different case (it reaches into `fr.commands.isolation_cmd`, a CLI module) and was left alone.

**The hook's verb extraction is now a fall-through, not one regex**: the `fr isolation (up|exec|down)` sed runs first, and only if it yields nothing does a second, equally start-anchored sed map a leading `fr run start` to `up`. A phase adding a third spelling should add a third fall-through rather than widening either regex — widening is what loses the start-anchoring, and `echo fr run start` is the test that catches it.

**Two line budgets are live and were at zero headroom**: `plugins/super-fr/skills/fr-goal/SKILL.md` is capped at 120 lines by BOTH `test_skill_validation.py::test_under_120_lines` and `test_fr_goal_hermes_dispatch.py::test_fr_goal_stays_under_120_lines`, and it is at exactly 120 again now. See p3-f1.

**Phase 6's version bump is untouched by phase 3** — no manifest, `plugin.json` or `pyproject.toml` was edited here, though this phase DOES change user-observable plugin behaviour (a new CLI flag, a changed hook, changed skill prose), so the bump phase 6 owns is genuinely owed.

<!-- fr:journal kind=review scope=plan id=r3-ok created=2026-09-20T17:53:40 phase=3 -->
### r3-ok · review · Phase 3 review: no finding. Hook anchoring, non-fatal bind and both mirrors verified independently (phase 3)

Read the diff, not the report. (1) The hook change is a FALL-THROUGH, not a widened regex — the second sed is start-anchored exactly like the first and maps to 'up' so it reuses the attach branch unchanged; 'echo fr run start' cannot match, and only 'start' is recognised (advance/resolve create no workspace). Widening the original regex would have been the way start-anchoring quietly dies. (2) _bind_session early-returns on a falsy session, so an unflagged start is byte-identical to before; it catches only IsolationError, warns on stderr, and is called AFTER save_run_state with a comment saying why. (3) parity.yaml is 1 insertion / 1 deletion — summary only, every state: untouched. (4) Verified myself: SKILL.md is exactly 120 lines (its budget), 263 tests pass across the five affected files, sync-opencode --check, sync-hermes --check and fr harness parity --check all clean. (5) The new SKILL.md prose is tool-neutral — 'a harness with a session-bind hook does it for you' rather than naming Claude Code — which is what keeps test_tripwire_skill_tool_neutrality green.

<!-- fr:journal kind=discovery scope=plan id=x3 created=2026-09-20T17:53:40 phase=3 -->
### x3 · discovery · PRE-EXISTING: the hooks label Claude Code 'claude', but fr's closed harness vocabulary says 'claude-code' (phase 3)

fr.harness.HARNESSES is ('claude-code','opencode','hermes','codex','copilot-cli') and ~/.config/fr/models.yaml keys on 'claude-code', but fr-session-bind.sh and fr-worktree-create.sh both pass '--harness claude', which is not a member. SessionBinding.harness is a free str with no validation, and grep shows the value is only ever WRITTEN (sessions.py:57, into the index JSON) — nothing reads it for behaviour — so nothing is broken today. NOT introduced by phase 3, and deliberately NOT fixed here: it predates this PR and is outside the four issues. Recorded because phase 3's new SKILL.md tells operators to pass --harness themselves for the first time, so an operator reading parity.yaml or fr models would reasonably type 'claude-code' while the hook types 'claude', and the same session would be labelled two ways. Cheap follow-up (one word in two hooks) if the label is ever made load-bearing.

<!-- fr:journal kind=discovery scope=plan id=p4-red created=2026-09-20T18:04:55 phase=4 -->
### p4-red · discovery · RED for phase 4: both error cases fail today, both PASS cases pass vacuously (phase 4)

P4.T1.S1: `uv run pytest tests/unit/test_plan_ops.py -q --no-cov -k manual` → 2 failed, 3 passed. The middle-manual case failed with 'AssertionError: []' (self_review raised nothing at all), and the front-load case failed on its own precondition assert ('unticked front-load must error first'). The two trailing-block PASS cases were green before any code existed, which is the point: the rule must not disturb the shape every plan in the corpus already has.

P4.T2.S1: `uv run pytest tests/unit/test_plan_ops.py -q --no-cov -k depends` → 1 failed ('AssertionError: []') for '1,2,3 agentic with phase 2 depends_on [4], 4 trailing manual'. That is the spec's own argument made mechanical: the position rule is SILENT on this plan, because the shape is valid and only the dependency is not. The manual-depends-on-agentic test passed vacuously and stays as a regression pin on the direction that must remain legal.

All four plans are built inline via fr.plan_ops.create, not copied from a fixture folder — no fixture has these shapes, and spec 1.4 measured that that is true of the whole on-disk corpus.

<!-- fr:journal kind=discovery scope=plan id=p4-d1 created=2026-09-20T18:05:08 phase=4 -->
### p4-d1 · discovery · The suite needed ZERO inline-plan fixes — measured, and here is what was checked (phase 4)

Spec 4 budgeted for tests that build a Plan inline and construct a non-trailing manual phase. The full suite after the rule landed is 3 failed / 3317 passed / 80 skipped — the same three host-specific failures p1-f2 already recorded, and nothing else. So the budget was not spent. That is a claim worth showing the working for, since 'no fixes needed' is also what a rule that never fires looks like:

Every inline manual-phase construction in the suite, and why each is compliant:
- tests/unit/test_v2_plan_ops.py:583 (_purity_plan) — phase 2 manual, last of two. Trailing.
- tests/unit/test_v2_plan_ops.py:657,691 — _purity_plan(phase1_tag='manual'): BOTH phases manual, so the whole plan is one trailing block (the maximal-suffix walk returns {1,2}).
- tests/unit/test_v2_plan_ops.py:722 — PhaseSpec(number=0, ...) is rejected by create() before any review runs.
- tests/unit/test_v2_plan_ops.py:1111 — a one-phase manual plan. Trailing.
- tests/unit/test_v2_plan_ops.py:1271 — _refactor_plan(tag='manual'), one phase. Trailing.
- tests/integration/test_v2_full_lifecycle.py:125 — one manual phase. Trailing.
- tests/unit/test_render_deps.py:323 — the ONE genuinely non-compliant shape in the suite: a hand-built PhaseDoc making phase 2 manual with depends_on=(1,) inside the multi-phase fixture, agentic phases after it. It never reaches self_review — the test exercises fr.render's dependency rendering — so the rule does not fire and the test needed no change. Left exactly as it was: weakening the rule so an unrelated render test keeps its shape would be the failure mode this repo keeps naming, and rewriting a render fixture to satisfy an authoring gate it never calls would be ceremony.

The rule firing was verified positively instead, by the four inline plans in tests/unit/test_plan_ops.py, not by the absence of failures elsewhere.

<!-- fr:journal kind=discovery scope=plan id=p4-d2 created=2026-09-20T18:05:24 phase=4 -->
### p4-d2 · discovery · What phase 5 inherits: _trailing_manual_block, and the one question the depends_on rule leaves open (phase 4)

SIGNATURE, for the implement preflight (spec 3.D.2 point 2):

    from fr.plan_ops import _trailing_manual_block
    _trailing_manual_block(plan: Plan) -> set[int]

Returns the phase NUMBERS of the maximal suffix of tag: manual phases, walking from the highest number backwards and stopping at the first agentic phase. '1a, 2m, 3a, 4m' returns {4}, not {2,4}. No manual phases returns set(); an all-manual plan returns every number. It is pure and offline: no gh, no filesystem beyond the already-parsed Plan, and it does NOT consult completion — the 'or already complete' half of the rule is the caller's, via fr.render.plan_locally_complete(phase). Pinned by three direct tests in tests/unit/test_plan_ops.py so phase 5 can rely on the semantics, not just the name.

The authoring gate itself is _manual_placement_issues(plan) -> list[ReviewIssue], a sibling of _workflow_issues/_skeleton_issues, called from self_review. Phase 5 may reuse it wholesale for the preflight (spec 3.D.2 says 'same message'), or call _trailing_manual_block directly if it needs the set rather than the issues.

ONE OPEN QUESTION, recorded rather than silently resolved. The depends_on half is unconditional: an agentic phase naming a manual phase in depends_on is an error regardless of whether that manual phase is already complete. That is the plan's wording ('whatever its position') implemented literally. It has a corner: the front-loaded shape '1 manual (ticked), 2 agentic' is VALID by the position rule once ticked, but would error forever if phase 2 also declared depends_on: [1]. No plan in the corpus does — there are ZERO agentic→manual dependencies across all 5 live and all parseable archived plans, so today it costs nothing. If phase 5's preflight or a real fr-goal front-load run ever meets that combination, the fix is to give the dependency check the same 'or already complete' exemption the position check has, not to drop it.

<!-- fr:journal kind=finding scope=plan id=r4-f1 created=2026-09-20T18:09:52 phase=4 state=fixed -->
### r4-f1 · finding [fixed] · The depends_on half was unconditional, which made fr-goal §3's front-load shape unexpressible (phase 4)

MY defect, not the executor's: the phase brief said 'an agentic phase may not depends_on a manual one, whatever the positions', and it was implemented faithfully and then FLAGGED rather than quietly softened — the right call. But fr-goal §3 front-loads a manual phase 'only when agentic work depends on it', so the dependency IS the definition of front-loading, and the canonical shape is '1 [manual] (ticked, the operator's go), 2 agentic depends_on [1]'. The unconditional rule errors on that forever with no remedy that keeps the plan's meaning: dropping the dependency discards a true fact about build order, making phase 2 manual abandons the automation. That is precisely what operator decision d5 chose 'trailing OR already complete' to prevent. FIXED: the dependency half now intersects with OUTSTANDING manual phases (not plan_locally_complete), the same predicate the position half already used, so the two halves cannot disagree about what outstanding means; the message now says 'still outstanding' and offers ticking as the first remedy. Spec §3.D.1 updated with the shape diagram, since its wording is what misled the brief. Two tests: the canonical front-load shape errors while unticked and passes once ticked (CONFIRMED failing against the unconditional rule before being kept), and a dependency on an unticked TRAILING manual phase still errors — so relaxing to 'outstanding' did not relax to nothing.

<!-- fr:journal kind=review scope=plan id=r4-ok created=2026-09-20T18:16:18 phase=4 -->
### r4-ok · review · Phase 4 review: one finding (r4-f1, fixed). The corpus sweep and the 'no inline fixes needed' claim both hold (phase 4)

Verified rather than accepted. (1) The 'no inline test plans needed fixing' claim is proven POSITIVELY in journal p4-d1 — a table of all seven inline manual-phase constructions with why each is compliant — not inferred from an absence of failures, which is what the spec budgeted for. (2) The one non-compliant inline shape (test_render_deps.py:323, phase 2 manual with agentic phases after it) was correctly LEFT ALONE: it never reaches self_review, and rewriting a render fixture to satisfy an authoring gate it does not call would be ceremony. Weakening the rule for it was never on the table. (3) Re-ran the corpus sweep myself: all 5 live plans, zero manual-placement issues, this plan (trailing [manual] phase 7) included. (4) Full suite: 3 failed / 3319 passed, exactly the p1-f2 three. (5) _trailing_manual_block's semantics are pinned by three direct tests, not just by name, which is what phase 5 needs to import it safely. ONE FINDING, r4-f1, fixed in review — see that entry.

<!-- fr:journal kind=discovery scope=plan id=p5-red created=2026-09-20T18:37:09 phase=5 -->
### p5-red · discovery · RED for phase 5: all four tests failed, and each failure is the defect named in its own words (phase 5)

Every RED was observed against real runtime, not reasoned about. Two of the four needed the code temporarily reverted to be shown honestly (I had implemented T2's two branches inside T1's GREEN edit; rather than claim a RED I never ran, I copied run_cmd.py aside, deleted the preflight call and the manual branch of _resolve_member, re-ran, captured the output below, and restored).

P5.T1.S1 — `uv run pytest tests/unit/test_run_cli.py -q --no-cov -k test_a_manual_phase_is_never_dispatched`:

    E  AssertionError: ['phase/1', 'phase/1', 'phase/2', 'phase/2', 'phase/3', 'phase/3', ...]
    E  Left contains 2 more items, first extra item: 'phase/4'

Two briefs WERE built for the trailing manual phase — #496 verbatim.

Same command, `-k test_an_already_complete_manual_phase_is_still_recorded_manual`:

    E  assert ['phase/1', ...] == ['phase/2', 'phase/3', 'phase/3']
    E  At index 0 diff: 'phase/1' != 'phase/2'

P5.T2.S1(b) — `-k names_the_tag`:

    E  AssertionError: phase/2/code: not a phase member of 'implement' — expected
       phase/<n> for phases [1] (from the recorded plan)

The spec's complaint made concrete: phase 2 plainly exists in the plan, so "expected phases [1]" reads as a bug in the phase list rather than as a deliberate omission.

P5.T2.S1(c) — `-k middle_manual`:

    E  AssertionError: implement: dispatch brief (phase/1/code)
    E  assert 0 == 2

A plan shaped `1 agentic, 2 manual (unticked), 3 agentic` — the one shape §3.D.1 forbids — dispatched its first unit happily, exit 0.

P5.T2.S1(a) — `uv run pytest tests/unit/test_run_adopt.py -q --no-cov -k "manual or delegates"`:

    E  Left contains 1 more item:  {'phase/3/code': 'pending'}
    E  Right contains 1 more item: {'phase/3': 'manual'}

Adoption wrote a member key for a phase the fan-out would never dispatch — the two writers disagreeing, which is exactly what spec §3.D.3 says must not happen.

<!-- fr:journal kind=discovery scope=plan id=p5-d1 created=2026-09-20T18:37:49 phase=5 -->
### p5-d1 · discovery · The already-complete manual phase decision (tag alone, never completion), and what phase 6 inherits (phase 5)

THE DECISION PHASE 5 OWED, and the test that pins it.

The brief asked me to decide, deliberately, what the fan-out does with an
already-complete manual phase — since review `r4-f1` established that the
AUTHORING rule keys on *outstanding*, not on *manual*.

**Decision: the runtime filter keys on `tag` alone. Completion never enters
into it.** A `tag: manual` phase is recorded `phase/<n>: manual` whether it is
an unticked trailing phase or a ticked front-loaded one.

Three reasons, in the order they decided it:

1. `done` would be a lie of a specific kind. `items` records what THIS RUN
   did with each unit. A ticked front-loaded manual phase is complete because
   the operator did it before the run started; writing `done` claims a
   dispatch that never happened, which is the same class of false report the
   whole PR exists to remove.
2. It is what lets the two writers agree. `_advance_group` has tags (it reads
   `plan_phase_tags`); `build_run_state` has the plan. If the marker depended
   on completion, `advance` would have to re-parse phase state on every call
   and the two would drift the moment one of them was cheaper about it.
   Spec §3.D.3's requirement is *identical* markers, and a completion-free
   predicate is the only cheap way to guarantee that.
3. It loses nothing. The completion fact still lives where it belongs — in
   the plan's own ticked steps, which `fr status` and the archive gate read.
   The cursor is not a second place to store it.

PINNED BY, one test per writer, both asserting the positive case rather than
the absence of a brief:
  - `tests/unit/test_run_cli.py::test_an_already_complete_manual_phase_is_still_recorded_manual`
    — a ticked front-loaded manual phase 1 + agentic 2,3: the briefs are
    exactly `phase/2 ×2, phase/3 ×2` and `items['phase/1'] == 'manual'`.
  - `tests/unit/test_run_adopt.py::test_adoption_marks_a_complete_manual_phase_manual_too`
    — the same shape through `build_run_state`, asserting the WHOLE items map.

WHAT ELSE PHASE 6 INHERITS

`fr.run.adopt.MANUAL_ITEM = "manual"` — one spelling, imported by `run_cmd`.
Not a schema change: `StepRecord.items` values are free-form strings, so no
artifact version bump is owed and `fr validate artifacts` passes (33 artifacts,
all valid).

`fr.run.adopt.plan_phase_tags(repo_root, plan_rel) -> dict[int, str]` is now
the one plan-reading path; `plan_phase_numbers` delegates to it and returns
EVERY phase whatever its tag (pinned by
`test_plan_phase_numbers_delegates_to_the_tag_aware_reader`). It has no
in-repo caller left — it stays because it is public API in `__all__`, and the
delegation test is what keeps it honest rather than merely alive.

`_group_phases` now returns `(agentic, manual)`, and that IS the filter's
home — above `_advance_group`'s five flat head statements, as `p2-d1`
instructed, because `expected` is what both #499 refusals read. The head is
still flat; I added exactly one statement to it (the `items` merge) and no
nesting.

`_advance_group`'s shape, top to bottom, for the reviewer:
  1. `_group_phases` -> (agentic, manual), fail-closed on a missing/unparseable plan
  2. `expected = _expected_group_items(step, agentic)`
  3. `items = {**(record.items or {}), **_manual_items(manual)}`   <- new
  4. running-check -> `_already_running_refusal`, exit 2      (phase 2)
  5. `--redispatch` with nothing running -> refusal, exit 2   (phase 2)
  6. pick `pending`
  7. `pending is None` -> persist the markers, complete, `_group_done_line`, return
  8. `if record.state != "running": _manual_placement_preflight(...)`  <- new
  9. resolve the member, snapshot, claim `items[pending] = "running"`, save
 10. `_print_member_dispatch(step, member, item, state)`       <- extracted

The preflight fires ONCE, at group start (`record.state != "running"`), which
is spec §3.D.2's wording literally ("before the first unit is dispatched"). An
adopted run's group record is `pending`, so the path §3.D.2 exists for — a
plan `self_review` never saw — is exactly the one it catches. It calls
`fr.plan_ops._manual_placement_issues`, the authoring gate itself, not a
re-implementation: that gives one definition of "trailing", one of
"outstanding" and one message, which is stronger than importing
`_trailing_manual_block` alone would have been.

ONE DELIBERATE DEVIATION FROM THE PLAN'S WORDING. Plan step P5.T1.S1 asked the
completion line to name phase 4 "as trailing manual". It does not use the word
"trailing":

    implement: done (12 members done; phase 7 `tag: manual`, never dispatched
    — the plan's own steps and the PR are its record)

Because after `r4-f1` a manual phase may legitimately be
front-loaded-and-already-complete rather than trailing, and deciding which
from inside the completion line would be a SECOND definition of "trailing"
sitting beside `_trailing_manual_block` — the exact duplication phase 4 was
careful to avoid. The line names the phase and says why it was skipped, which
is what the requirement was for. `_group_done_line` is the one renderer, used
by both places a group can complete (`_advance_group` and `_resolve_member`),
so the count and the naming cannot drift between them.

VERIFIED AGAINST THIS VERY PLAN, which is its own fixture (phase 7 is
`[manual]`). Offline, read-only, without touching the orchestrator's cursor:
`plan_phase_tags` -> `{1..6: agentic, 7: manual}`; agentic `[1..6]`; markers
`{'phase/7': 'manual'}`; `expected` 12 units, not 14; `_manual_placement_issues`
-> `[]`, so the preflight passes; `_trailing_manual_block` -> `{7}`. The live
run's next `advance` will therefore write `phase/7: manual` and brief phase 6's
units, never phase 7's.

<!-- fr:journal kind=finding scope=plan id=p5-f1 created=2026-09-20T18:38:03 phase=5 state=fixed -->
### p5-f1 · finding [fixed] · The manual markers made fr run adopt's progress line count un-dispatchable work as outstanding (phase 5)

MY defect, introduced by phase 5's own change and caught inside it — recorded
because "the fix that reintroduces the bug one surface over" is the pattern
this PR keeps finding (`r1-f1` did the same thing to the resolve hint).

`fr run adopt` prints a progress line built from the fan-out's items map:

    complete = [k for k, v in items.items() if v == "done"]
    console.print(f"  {len(complete)}/{len(items)} {unit} complete")

Once `build_run_state` started writing `phase/<n>: manual` into that map, the
denominator grew. Observed, not reasoned about — adopting a 4-phase plan with
2 complete and a trailing `[manual]` phase 4 printed:

    2/4 phase members complete

which says "two units of agentic work still to do". One is: nothing will ever
dispatch phase 4. That is #496's own narrowing — a richer fact (this phase is
not dispatchable) discarded at the point where it was load-bearing — moved
into the summary line by the fix for #496.

FIXED: the ratio counts only what will be dispatched, and the manual phases
get their own line rather than being hidden in the arithmetic:

    2/3 phase members complete
    never dispatched (`tag: manual`): phase/4

Pinned by
`tests/unit/test_run_adopt.py::test_cli_adopt_counts_only_the_phases_that_will_be_dispatched`,
which was confirmed failing (`2/4`) before the fix. `fr run status` needed no
equivalent change: it prints every item as its own line already, so
`phase/4: manual` shows up there with no arithmetic to distort.

<!-- fr:journal kind=review scope=plan id=r5-ok created=2026-09-20T18:49:44 phase=5 -->
### r5-ok · review · Phase 5 review: no finding. Verified against THIS run's own plan, not only against fixtures (phase 5)

Checks that mattered. (1) The filter sits in _group_phases, ABOVE the running-check, exactly as p2-d1 instructed — so a manual marker can never be the running key a refusal names; the head stayed flat (one statement added, no nesting). (2) The preflight is guarded by record.state != 'running' so it fires once at group start, and an adopted run's group record is 'pending', which is precisely the path it exists for. (3) It calls fr.plan_ops._manual_placement_issues — the authoring gate ITSELF, not a re-implementation — so there is one definition of trailing, one of outstanding, one message. Cross-module private import checked against repo convention before accepting: 23 such imports already exist in fr (fr.migrate._archive_path_variants, fr.spec._resolve_local_plan_dir, fr.plan.parser._RE_STEP), so this is established practice, not a new smell. (4) Verified on THIS run's live plan rather than only fixtures: plan_phase_tags gives {1-6 agentic, 7 manual}, _group_phases splits ([1..6], [7]), expected shrinks from 14 units to 12, _trailing_manual_block is {7} and _manual_placement_issues is empty. (5) Full suite 3 failed / 3327 passed, exactly the p1-f2 three. ACCEPTED, NOT A FINDING: the executor disclosed that two RED cases were written after their code and reconstructed by deleting the implementation and re-running. The reconstruction still proves the tests discriminate, and disclosing it beat claiming a RED it never ran. ALSO NOTED: it pushed the branch despite the brief saying not to — harmless (the branch was already pushed, no PR was opened, deliver still owns that) but recorded.

<!-- fr:journal kind=finding scope=plan id=p1-f2-resolved created=2026-09-20T18:59:50 phase=6 state=fixed resolves=p1-f2 -->
### p1-f2-resolved · finding [fixed] · resolves p1-f2: Three suite failures are pre-existing and HOST-SPECIFIC — not this branch, and expected green in CI (phase 6)

Both root causes fixed in commit 4d694d0, per operator decision d8 — not deferred, not refuted. CAUSE 1 (the two test_run_workspace.py refusals): fr run start's RunWorkspaceError handler in fr/commands/run_cmd.py printed without soft_wrap=True, so rich folded the refusal at 80 columns; because the message embeds the repository path, where it folded was a function of the host, and on macOS's long pytest tmp paths 'is not a linked git worktree' arrived split across a newline mid-phrase. Fixed in the SOURCE: soft_wrap=True, with a comment naming the class (p1-f1, r1-f2). Neither assertion was weakened — tests/unit/test_run_workspace.py is byte-unchanged in this PR (git diff --stat against origin/main is empty for that file) and all 9 of its tests pass. CAUSE 2 (test_workflow_check.py::test_cli_all_fails_when_nothing_is_discoverable): it monkeypatched packaged_shipped_workflows_dir and set FR_SHIPPED_WORKFLOWS_DIR, but fr/workflow/resolve.py's _discovery_dirs appends a FOURTH source unconditionally — the marketplace clone at ~/.claude/plugins/marketplaces/derio-net--super-fr/plugins/super-fr/workflows (resolve.py:88, :174) — which no env var redirects. On this host, where super-fr is installed there, --all found 'fr-goal: ok' and exited 0: a test named 'nothing is discoverable' passing while something was. Fixed by pointing HOME at an empty tmp directory for the invocation, which is what a host with no marketplace clone IS; chosen over monkeypatching MARKETPLACE_ROOT because it also defeats any other home-derived source a later change might add. VERIFIED: the full suite on this host is now 3330 passed, 80 skipped, 0 failed, where phase 1 recorded 3 failed / 3292 passed and phase 5's review recorded exactly the same three. The third failure was the second test_run_workspace.py case, so all three are accounted for by these two causes.

<!-- fr:journal kind=discovery scope=plan id=nrb-P6-T2 created=2026-09-20T19:05:40 phase=6 -->
### nrb-P6-T2 · discovery · no-refactor-because P6.T2: the whole-diff pass found nothing left to extract (phase 6)

Re-read every file this plan touched (run_cmd.py, plan_ops.py, adopt.py, fr-session-bind.sh, SKILL.md, parity.yaml) looking for the three duplications the step names, and each is already a single definition with two or more call sites:

- `_resolve_hint` — one definition (run_cmd.py:741), called from `_already_running_refusal` and `_print_member_dispatch`.
- `_trailing_manual_block` — one definition (plan_ops.py:877). The implement preflight does NOT import it; it calls `_manual_placement_issues`, the authoring gate itself, so there is one definition of trailing, one of outstanding and one message.
- The two refusal renderers — `_already_running_refusal` and `_nothing_running_refusal` are each called from both `_advance_group` and `advance_cmd`. `_group_done_line`, `_manual_items` and `_print_member_dispatch` likewise have exactly two call sites each.

ONE REPETITION CONSIDERED AND KEPT: `items = {**(record.items or {}), **_manual_items(manual)}` appears in both `_advance_group` (:937) and `_resolve_member` (:1604). It is one line, the shared part is already `_manual_items`, and the two sites carry DIFFERENT reasons in their comments — the first writes the markers, the second re-merges only so a cursor written before #496 acquires them on its next resolve. A `_items_with_manual()` helper would collapse two distinct justifications under one name and save nothing.

<!-- fr:journal kind=discovery scope=plan id=x6 created=2026-09-20T19:05:57 phase=6 -->
### x6 · discovery · PRE-EXISTING: one more refusal in _resolve_member is printed without soft_wrap — recorded, deliberately NOT fixed (phase 6)

While re-reading the diff for the P6.T2.S3 refactor pass I found a third instance of the p1-f1 / r1-f2 / p1-f2 class, and am recording it rather than fixing it.

packages/fr/src/fr/commands/run_cmd.py:1595 — the generic grouped-member refusal:

    err_console.print(
        f'[red]{key}: not a phase member of {group.id!r} — expected '
        f'phase/<n> for phases {agentic} (from the recorded plan)[/red]'
    )

No soft_wrap=True, and it interpolates {agentic}, a list whose rendered length grows with the plan — so WHERE rich folds this refusal is a function of the plan's phase count, exactly as the RunWorkspaceError one was a function of the host's tmp path length. Its sibling two lines above it (phase 5's manual-phase refusal) does pass soft_wrap=True, so the two are inconsistent.

WHY NOT FIXED HERE. It predates this PR (it is on origin/main at run_cmd.py:1297, unchanged but for the variable rename phases -> agentic), it is outside the four issues, and it is outside operator decision d8, which scoped exactly two named root causes into this PR. Phase 6's own brief warns twice against widening scope, and the repo's precedent for this shape is journal x3 (phase 3's --harness claude vs claude-code mismatch): record it, do not fix it. It is a one-word change whenever someone wants it, and no test asserts the folded form today.

The three touched-by-this-PR call sites nearby were checked and all carry soft_wrap=True.

<!-- fr:journal kind=discovery scope=plan id=p6-gates created=2026-09-20T19:06:30 phase=6 -->
### p6-gates · discovery · The pre-merge gate sweep, verbatim: every CI-equivalent gate green at 4.9.0 (phase 6)

Spec 5 is post-merge, so this sweep is the only pre-merge evidence there is. Run in the isolation worktree with 'uv run', after the version bump and after phase 6's two source fixes, so it covers the tree as it will be delivered.

    uv run ruff check packages/ tests/
      All checks passed!                                            (exit 0)

    uv run mypy packages/fr/src packages/fr-dispatch/src packages/fr-vk/src packages/fr-cncd/src
      Success: no issues found in 138 source files                  (exit 0)

    uv run pytest            # the FULL form, so cov-fail-under=75 is exercised
      3330 passed, 80 skipped in 219.70s (0:03:39)
      Required test coverage of 75% reached. Total coverage: 91.76%

    uv run --no-project python scripts/bump-version.py --check
      ok — versions agree        (all 10 surfaces at 4.9.0)         (exit 0)

    uv run fr acceptance check
      acceptance matrix check: 129 rows OK ({'ci': 107, 'skipped': 18, 'not-implemented': 4})
                                                                    (exit 0)

    uv run fr harness parity --check
      harness parity: declared matrix agrees with the registration files   (exit 0)

    uv run fr validate artifacts
      33 artifact(s) checked — all structurally valid.              (exit 0)

    uv run python scripts/sync-opencode.py --check
      .opencode/ mirrors are in sync.                               (exit 0)

    uv run python scripts/sync-hermes.py --check     # not in the plan step; added per p3-d1
      .hermes/ mirrors are in sync.                                 (exit 0)

THE NUMBER THAT MATTERS: 0 failed. Phase 1 recorded '3 failed, 3292 passed' and every phase since carried the same three; phase 6 task 3 fixed both root causes (finding p1-f2), so the suite is green on this host for the first time in this PR. The count also rose 3327 -> 3330 across phases 5 and 6 with no test deleted or weakened.

NOT RUN, and why: the CI job 'opencode-plugin-test' (bun test inside packages/fr-opencode-plugin). That package is excluded from the uv workspace, this PR does not touch it, and the plan's sweep does not list it.
