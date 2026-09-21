# Journal: 2026-09-21-508-live-test-plan-defects

<!-- fr:journal kind=repro scope=debug id=c4-repro created=2026-09-21T14:22:00 -->
### c4-repro · repro · C4: guard denies fr run start from the base clone iff the repo already has a linked worktree

C4. With a pipeline sentinel live and the session cwd in the base clone, fr-isolation-guard.sh denies `fr run start <shape> --branch <b>` (also `uv run fr run start`, `fr run start --help`, `fr models resolve`), while fr-goal calls `fr run start` "the first action" that "enters isolation itself".

Repro (tests/unit/test_hooks_guard.py harness, real script): git repo + sentinel + ONE pre-existing linked worktree of any branch -> deny. The same repo with NO linked worktree -> allow, because the #341 orphan self-heal sees exactly one `worktree ` line, deletes the sentinel and exits 0. So the live report ("denied") and a fresh-repo trial ("allowed") are both true; the variable is whether the repo already has some worktree, anyone's. This repo had eight.

<!-- fr:journal kind=root-cause scope=debug id=c4-root-cause created=2026-09-21T14:22:00 -->
### c4-root-cause · root-cause · C4: the guard's allowlist predates fr run start becoming an isolation-entering command

C4 root cause: the guard's fr allowlist is `fr init|skills|--version` plus `fr isolation ...`, written when `fr isolation up` was the only command that enters isolation. Review fix r2-f5 later made `fr run start` enter isolation ITSELF (fr.run.workspace.ensure_run_workspace is called before anything is written; it is the only run verb that does - `adopt` deliberately does not) and the skill was rewritten to make it the first action. The allowlist never learned the second isolation-entering command. One concept, "commands that enter isolation", spelled in two places that drifted.

Adjacent, NOT fixed here, recorded so it is not rediscovered: the same self-heal that masked this in a fresh repo means that in a repo with no linked worktree the FIRST base-clone command of a new pipeline - any command - deletes the sentinel, and the bash guard is then inert for the rest of that session. The heal cannot tell "outlived all worktrees" from "has not created one yet". Closing it needs a way to tell a fresh sentinel from an orphaned one (age, or a workspace-seen flag): a design decision, not a bug fix.

<!-- fr:journal kind=repro scope=debug id=c3-repro created=2026-09-21T14:23:04 -->
### c3-repro · repro · C3: a grouped unit resolves done without ever being advanced

C3. `fr run resolve <run> --step <member> --item phase/<n> --state done` succeeds for a grouped unit that `fr run advance` never briefed. Live: on the Claude Code proof run, review-phase ended `done` with evidence and NO attempts - no holder, no cost - while the OpenCode run, which advanced first, has one.

Repro (tests/unit/test_run_cli.py helpers, one-phase grouped shape): advance; resolve code done; then, with no second advance, resolve peer-review done -> rc=0, "implement: done (2 members done)". The unit went from absent straight to done.

<!-- fr:journal kind=root-cause scope=debug id=c3-root-cause created=2026-09-21T14:23:04 -->
### c3-root-cause · root-cause · C3: _resolve_member checks the group and the other units, never the unit itself

C3 root cause: _resolve_member guards the GROUP's state (must be running/blocked) and refuses while any OTHER unit is running (one writer), but has no precondition on the unit it is resolving. The flat-step path has one - resolve_cmd refuses "not running or blocked ... advance first" - so the two paths disagree about the same rule, and the grouped one is the newer code. _close_on_resolve is then "silent when there is nothing open", deliberately (adopted runs, gate steps), so nothing downstream notices: the unit is done, attempts is empty, and status prints a done unit with no holder line.

Not a reason to make _close_on_resolve loud: its silence is load-bearing for adopted cursors. The missing check belongs where the flat path has it - before the write.

<!-- fr:journal kind=repro scope=debug id=c2-repro created=2026-09-21T14:24:15 -->
### c2-repro · repro · C2: orchestrator-run units record the tier's model, which is sometimes false

C2. An orchestrator-run unit records a `model` fr never observed. Live (OpenCode proof run): review-phase, run inline, reads "the orchestrator (opencode, <provider>/<model>)" - the standard tier's binding. There the operator confirmed the orchestrator happened to be on that model, so the value was true by coincidence.

It is not always true, and this repo's own archive proves it: docs/superpowers/implemented/runs/2026-09-20-unit-record-unification-r2.yaml records all 7 review-phase attempts as `model: claude-opus-5`, no agent_type, unclaimed. Every one of those reviews was performed inline by the orchestrator, which was running claude-fable-5-1. Seven false records, on main.

<!-- fr:journal kind=root-cause scope=debug id=c2-root-cause created=2026-09-21T14:24:16 -->
### c2-root-cause · root-cause · C2: _open_dispatch derives a model for attempts that were never dispatched to a tier

C2 root cause: _open_dispatch writes `model=_resolved_model(repo, harness, tier)` for EVERY attempt it opens. A tier binding answers "which model does a DISPATCHED agent of this tier get". For an attempt with an agent_type that is what the dispatch asked for. For an attempt with agent_type None - which _attempt_holder renders as "the orchestrator" - nothing was dispatched to a tier: the unit runs in the orchestrator's own session, on a model fr has no way to see. review-phase inherits the group's `tier: from_phase` through _effective_tier, so the phase's tier resolves and a model is written for work that tier never touched.

Finding f8 (the #508 run) reasoned about exactly this site and got half of it: it made `harness` self-describing on orchestrator-run attempts ("which nothing ever claims") and did not notice that the model beside it was being derived for a dispatch that did not happen.

Scope of the fix, stated: stop deriving a model where there is no agent_type; an orchestrator can still REPORT one (claim/resolve --model). NOT in scope: marking provenance (derived vs reported) on executor attempts - that is a new Attempt field, which is a `run` shape change with a version bump and migration - and rewriting cursors that already carry the false value (a repair would be guessing which unclaimed models were derived; archived cursors are frozen by rule).

<!-- fr:journal kind=repro scope=debug id=c5-repro created=2026-09-21T14:26:49 -->
### c5-repro · repro · C5: host and container delete and rebuild one shared .venv on every alternation

C5. Alternating `uv run` between the host and the devcontainer deletes and rebuilds the worktree's `.venv` every time.

Repro, deterministic, in this fix workspace, with a control:
  1. container: `fr isolation exec -- uv run fr --version` -> "Ignoring existing virtual environment linked to non-existent Python interpreter", "Removed virtual environment at: .venv", re-downloads mypy/ruff/pygments/pydantic-core (~26 MB), installs 31 packages. `.venv/bin/python` now links into the container's uv-managed CPython.
  2. host: `uv run fr --version` -> the same three lines, rebuilds for the host interpreter.
  3. host again -> no removal (control).

fr-isolation's exec-bridge discipline mandates exactly this alternation (orchestrator on the host, commands through `fr isolation exec`), so under fr it is the normal case, not an edge. Beyond the cost: a host pytest running while the container rebuilds `.venv` is running on an environment being deleted under it.

<!-- fr:journal kind=root-cause scope=debug id=c5-root-cause created=2026-09-21T14:26:49 -->
### c5-root-cause · root-cause · C5: the scaffold emits a uv-enabled bind-mounted profile with one project env for two operating systems

C5 root cause: the worktree is bind-mounted into the container, and uv on both sides defaults its project environment to `<project>/.venv` - one path, two operating systems. A venv's interpreter link is only valid on the side that made it, so each side finds the other's venv broken and replaces it. Nothing sets UV_PROJECT_ENVIRONMENT on either side.

The source is `fr init scaffold`, not this repo's two profiles: KNOWN_TOOL_FEATURES knows `uv` and emits the uv feature into a bind-mounted profile, so every repo scaffolded with `--tool uv` inherits it. This repo's committed dev/admin profiles are instances.

<!-- fr:journal kind=repro scope=debug id=c1-repro created=2026-09-21T14:26:49 -->
### c1-repro · repro · C1: on OpenCode the holder's agent id arrives only when the blocking dispatch returns

C1. On OpenCode the dispatch holder's agent id is not knowable while the unit is held. Live: the orchestrator learned the child session id "only when the task tool returned", from the return value's task-id field; status from INSIDE the child read "HELD BY an unclaimed agent (opencode, <model>)". The claim, and the item-15 second-advance refusal, could only be exercised after the child had already returned.

What is wrong is what fr SAYS, in two places. parity.yaml `subagent-dispatch` declares `opencode: {state: enforced}` and its summary says `fr run claim --agent <id>` names the holder "identically on every harness". fr-goal section 5 says "The moment a dispatch goes out, name its holder" - an instruction an OpenCode orchestrator cannot follow, because its dispatch tool blocks.

<!-- fr:journal kind=root-cause scope=debug id=c1-root-cause created=2026-09-21T14:26:50 -->
### c1-root-cause · root-cause · C1: a parity cell and a skill instruction asserted from Claude Code's dispatch shape, never observed on OpenCode

C1 root cause: the claim protocol was designed and live-verified on a harness whose dispatch returns an id immediately and runs the child in the background (Claude Code), then declared for a harness whose dispatch BLOCKS and returns the id with the result (OpenCode). "enforced" was asserted from the unit tests of the record, not from a run; the first live OpenCode run is what showed the id arrives too late to answer "who holds it right now". Same defect class as the OpenCode SDK-version claim corrected in #508: a parity cell asserted rather than observed.

What still holds, and must not be lost in the correction: the OPEN record refuses a second dispatch on OpenCode exactly as elsewhere, and harness + model are recorded at dispatch. Only the agent id is late.

A real closing of the gap exists and is NOT attempted here: fr-opencode-plugin already distinguishes child sessions (idle.ts isTopLevel) and sees a sessionID on every tool call, so it could claim on the child's first tool call. That is a new plugin behaviour plus a new CLI affordance (claim "the one open unclaimed unit"), and it cannot be live-verified from a Claude Code session. Recorded as the follow-up; this fix makes the declaration true.

<!-- fr:journal kind=finding scope=debug id=c3-fixed created=2026-09-21T14:33:30 state=fixed -->
### c3-fixed · finding [fixed] · C3 fixed: a grouped unit must be briefed before it can be resolved

_resolve_member now refuses a unit whose state is absent or `pending` (exit 2, naming `fr run advance <run>`), for `done` and `failed` alike. Placed AFTER the one-writer refusal: my first placement put it before, which replaced "phase/1/code is still running" with advice to run an `advance` that would itself have refused a held unit - two existing tests caught that. A `running` unit with no record (adopted mid-flight) still resolves.

Failing-first: tests/unit/test_run_resolve_requires_advance.py (2 red, 1 control green before the fix; 3 green after). One existing test, test_resolve_member_items_completes_the_group_in_order, ENCODED the defect - it resolved peer-review straight after code - and now takes the write-claim like a real run. The grouped-loop spec (2026-09-09 methodology-restoration, section 5 "write-claim") is why that is a correction and not a weakening: the claim is what `advance` records, so a unit resolved without it never held one. 993 run-related tests green.
