<!-- fr:journal-schema=2 -->
# Journal: 2026-10-20-opencode-2-support

<!-- fr:journal kind=decision scope=plan id=five-phases created=2026-10-20T05:45:16+00:00 -->
### five-phases · decision · Five phases — restore, enforce, status line, readers, published surfaces

Phase 1 restores the plugin on V2 (entrypoint, edit gate, pin, idle, claim,
session-id export) and carries the run's one measured premise: V2's
`ShellCreateBefore` has no session id, so `FR_OPENCODE_SESSION_ID` is
correlated from the `shell` tool call's `execute.before`. The stated
failure outcome is "export nothing", never a guess.

Phase 2 adds the pipeline sentinel, the whole-command shell gate (porting
the bash entrypoint's decision, held to it by a verdict table captured by
running the script) and the merged-PR push guard, then the nag and
bind/unbind.

Phase 3 lands the TUI status line and its delivery/registration, risk
first: a TUI entrypoint OpenCode will not load without consumer-side peer
packages is a real possibility, and the phase records which mechanism
shipped.

Phase 4 moves both store readers (`fr.run.observed` and `fr.usage`) onto
`session_v2`/`session_message` behind an explicit version probe, so an
OpenCode 1.x session is refused by name instead of reading as empty.

Phase 5 closes the loop: parity rows, the matrix and its three reports, the
canonical rule and both mirrors, the explainer and the `bump: major`
fragment.

Every `opencode-2-*` row is linked to the phase that implements it; phase 5
records their evidence as bookkeeping. `fr plan self-review` passes with
the split and tier decisions recorded in the spec journal.

<!-- fr:journal kind=discovery scope=plan id=p1-baseline-smoke created=2026-10-20T06:58:27+00:00 phase=1 -->
### p1-baseline-smoke · discovery · Baseline smoke green before any code moved (phase 1)

On the branch at 8e20a4b25: `bun test` in packages/fr-opencode-plugin 103 pass / 0 fail;
`uv run pytest -q --no-cov tests/unit/test_hooks_guard.py` 105 passed. P1.T1.S2's red
was observed: plugin.test.ts against the old src/index.ts → 0 pass, 1 fail.

<!-- fr:journal kind=discovery scope=plan id=p1-v2-hook-order-measured created=2026-10-20T06:58:27+00:00 phase=1 -->
### p1-v2-hook-order-measured · discovery · Measured on OpenCode 2.0.32: execute.before precedes create.before, same command (phase 1)

A throwaway probe plugin under isolated XDG_{CONFIG,DATA,STATE,CACHE}_HOME (own service
port) logged both hooks for `opencode run --auto -m opencode/deepseek-v4.1-flash-free`
in a temp git repo. Observed: execute.before {tool: "shell", sessionID, agent: "build",
input: {command}} fired ~1 ms BEFORE shell create.before {command, cwd, env}, and
input.command === event.command byte-for-byte (also for a child session's shell call,
agent "general"). The premise of R7's correlation holds. End-to-end with the DELIVERED
plugin: a model-run `echo SID=$FR_OPENCODE_SESSION_ID PIN=$FR_HARNESS_FR` printed the
session's own id (matched `opencode session list`) and the fr identity, so the session
export and the pin both work live on 2.0.32.

<!-- fr:journal kind=discovery scope=plan id=p1-clean-launch-opencode-session-id created=2026-10-20T06:58:27+00:00 phase=1 -->
### p1-clean-launch-opencode-session-id · discovery · Clean launch: create.before's env has no OPENCODE_SESSION_ID; OpenCode sets it on the spawned command, to the ISSUING session (phase 1)

The OPENCODE_SESSION_ID seen in the first probe's create.before env (ses_ea827d28…) was the
LAUNCHER's (this executor's own OpenCode session), inherited by the background service.
Re-run with `env -u OPENCODE -u OPENCODE_SESSION_ID -u OPENCODE_TERMINAL`, service stopped
first, one `opencode run` (deepseek-v4.1-flash-free) delegating `echo` to a subagent. Raw lines:
  {"hook":"execute.before","tool":"subagent","sessionID":"ses_ea809700affecVqut6W6uK4kns","agent":"build"}
  {"hook":"execute.before","tool":"shell","sessionID":"ses_ea809628effe9IXyhuOWm2XRjV","agent":"general","input":{"command":"echo CHILD_SID=$OPENCODE_SESSION_ID"}}
  {"hook":"create.before","command":"echo CHILD_SID=$OPENCODE_SESSION_ID","OPENCODE_SESSION_ID":null,"keys":["ATUIN_SESSION","SECURITYSESSIONID","OPENCODE_TERMINAL"]}
  command output: CHILD_SID=ses_ea809628effe9IXyhuOWm2XRjV
(a) No: create.before's event.env carries no OPENCODE_SESSION_ID on a clean launch (same for
a root-session shell call in the preceding run). (b) OpenCode nonetheless sets
OPENCODE_SESSION_ID in the spawned command's environment AFTER the hook, and its value is
the ISSUING session (the child), not the root. So the plugin cannot read it from event.env,
but fr can read it natively from its own environment; a later phase should teach fr's
OpenCode session reader to accept OPENCODE_SESSION_ID (walking parent_id to the root, as it
already does for FR_OPENCODE_SESSION_ID) and then delete the plugin's pending-queue
correlation. Never trust it in create.before's env: an inherited value there is the
launcher's.

<!-- fr:journal kind=decision scope=plan id=p1-r6-queue-removed created=2026-10-20T06:58:27+00:00 phase=1 -->
### p1-r6-queue-removed · decision · R6 simplified: the queue was built, measured redundant, and removed (phase 1)

The measurement (p1-clean-launch-opencode-session-id) settles it: OpenCode itself puts the
ISSUING session's id in every spawned command's environment as OPENCODE_SESSION_ID, after
create.before. fr reads its own environment, so it needs no plugin export at all — and the
value it sees is exactly the one the queue reconstructed. The pending queue (session.ts,
its tests and the create.before wiring) was therefore removed in this same phase rather
than kept as a second mechanism for the same fact.

The spec was amended in the same phase (R6 and §C now say "measured, not correlated"; the
§A table row for shell.env is gone) and the plan's P1.T3 was rewritten from "build the
queue" to "measure, then build only what is missing". A later phase teaches fr's reader to
accept OPENCODE_SESSION_ID (falling back to FR_OPENCODE_SESSION_ID when a wrapper sets it)
and walk parent_id to the root, which it already does. Until then fr's OpenCode reading
stays unobserved on 2.0 — the same state it is in today — and no behaviour regresses.

<!-- fr:journal kind=discovery scope=plan id=p1-v2-dispatch-tool-name created=2026-10-20T06:58:27+00:00 phase=1 -->
### p1-v2-dispatch-tool-name · discovery · OpenCode 2's dispatch tool is `subagent`, input {agent, description, prompt} (phase 1)

Observed live (2.0.32): the parent's execute.before for a delegation had tool "subagent",
input {agent: "general", description, prompt}; the child's own calls carry a different
sessionID and agent "general". Later phases that read dispatch (OpenCode readers, the
`task` name in Python) must treat `subagent` as the V2 name.

<!-- fr:journal kind=finding scope=plan id=p1-v2-loads-sources-dir-as-plugin created=2026-10-20T06:58:27+00:00 phase=1 state=open review_scope=out -->
### p1-v2-loads-sources-dir-as-plugin · finding [open] (reviewer: out of scope) · OpenCode 2 loads the delivered sources directory as a second plugin (phase 1)

OpenCode 2 scans <config>/opencode/plugins/ for directories too: it logs `loading plugin
id=.../plugins/fr-opencode-plugin entrypoint=.../fr-opencode-plugin/index.ts` beside the
top-level loader, so the delivered plugin loads TWICE (both setups ran, no error). The
idle and claim memories are process-wide, so nudges/claims do not double; the gate and the
exports are idempotent. The 1.x layout (loader + sources dir, gh#563) is therefore
redundant on V2. scripts/deliver-opencode-plugin.sh / install.sh belong to a later phase;
that phase should deliver only the directory (or move the sources somewhere unscanned).

<!-- fr:journal kind=discovery scope=plan id=p1-v2-cli-is-opencode-cli-and-service created=2026-10-20T06:58:27+00:00 phase=1 -->
### p1-v2-cli-is-opencode-cli-and-service · discovery · OpenCode 2 ships as npm `@opencode/cli`, and every CLI command talks to one background service (phase 1)

`opencode-ai` on npm stops at 1.19.x; 2.0.32 is `@opencode/cli` (CI pin moved to it).
Every CLI command (debug config, plugin list, run) goes through a background service on a
FIXED port shared across XDG dirs, so an isolated test must set its own port
(`opencode service set port <free>`) and `opencode service stop` after, or it talks to the
operator's own service and plugins. `debug config` now lists config sources, not plugins;
the live probe reads the server log's `loading plugin` / `failed to load plugin` lines
instead (mutation-checked: deleting src/marker.ts fails both probes). The service's shell
env is inherited from whoever started it (an OPENCODE_SESSION_ID from an outer session
leaked into create.before's env) — never trust an inherited OPENCODE_SESSION_ID.

<!-- fr:journal kind=finding scope=plan id=p1-suite-harness-env-leak created=2026-10-20T06:58:27+00:00 phase=1 state=open review_scope=in -->
### p1-suite-harness-env-leak · finding [open] (reviewer: in scope) · The Python suite fails 46 tests when run from inside an OpenCode 2 session (phase 1)

First full run (`uv run pytest -q --no-cov -n auto` from this executor's shell): 48 failed /
12920 passed. 46 (test_run_cli, test_run_evidence_*, test_run_review_return_resolve,
test_run_suite_reuse, test_run_telemetry) pass when re-run with OPENCODE,
OPENCODE_SESSION_ID, OPENCODE_TERMINAL unset: they inherit the harness's OPENCODE_* env.
tests/conftest.py should scrub these as it scrubs the fr pin. The other 2
(test_triage_driver_adapter: expects closeout-2026-10-14-1, gets today's date) fail
identically on the base commit 8e20a4b25 — pre-existing and date-dependent.
Clean-env rerun (the evidence log): 2 failed (those two), 12966 passed, exit=1.
Both are fixed in this phase: tests/conftest.py now scrubs the OPENCODE* variables, and
the driver-adapter module takes the drive tests' `_sandbox` fixture (its autouse scope
does not cross modules), so its close-out ids derive from the pass clock instead of the
wall clock. `git stash pop` note: while checking the base, one `git stash pop` applied
another branch's stash; it was reset to HEAD, the one untracked file removed, and
`stash@{0}` (wip: issue-550-opencode-edit-gate) is still in the list, intact.

<!-- fr:journal kind=decision scope=plan id=p1-out-of-scope-minimal-fixes created=2026-10-20T06:58:27+00:00 phase=1 -->
### p1-out-of-scope-minimal-fixes · decision · Two minimal edits outside the phase's file list, forced by the V2 export (phase 1)

The plugin now has only a default export, so the delivered loader line in
scripts/deliver-opencode-plugin.sh moved from `export { FrIsolationRequired as default }`
to `export { default }`, and tests/unit/test_opencode_plugin_delivery.py's assertion on
that line moved with it. Without them the live probe (in scope) could not pass. No other
delivery behaviour changed. packages/fr-opencode-plugin/README.md still describes the 1.x
hooks and is left to the docs phase.

<!-- fr:journal kind=decision scope=plan id=p1-idle-and-directory-choices created=2026-10-20T06:58:27+00:00 phase=1 -->
### p1-idle-and-directory-choices · decision · Idle loop awaits each event; the plugin's one directory is ctx.location.directory (phase 1)

runIdleLoop awaits each handler so two idle events cannot race the once-per-position
memory (a slow fr delays the next event at most the 20 s fr timeout). isTopLevel now also
requires the looked-up info's id to equal the asked id, so an unexpected get() result is
unknown, never top-level. V2 has no ctx.worktree; gate, claim and idle all use
ctx.location.directory. A call with no string tool name is inspected by the gate (fail
closed), not waved through. The session.prompt nudge carries no per-call directory (V2's
prompt has none), so the idle test's query/body.parts assertions became sessionID/text.

<!-- fr:journal kind=finding scope=plan id=p1-suite-harness-env-leak-resolved created=2026-10-20T06:58:27+00:00 phase=1 state=fixed resolves=p1-suite-harness-env-leak -->
### p1-suite-harness-env-leak-resolved · finding [fixed] · resolves p1-suite-harness-env-leak: The Python suite fails 46 tests when run from inside an OpenCode 2 session (phase 1)

tests/conftest.py scrubs OPENCODE/OPENCODE_SESSION_ID/OPENCODE_TERMINAL/FR_OPENCODE_SESSION_ID; tests/unit/test_triage_driver_adapter.py takes the drive tests' _sandbox (clock + HOME) and derives its close-out ids from NOW. Full suite rerun is the evidence.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-10-20T06:58:27+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

the V2 entrypoint replaced the 1.x export outright; the helpers it wires were already split one per module, and nothing was duplicated

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t2 created=2026-10-20T06:58:27+00:00 phase=1 -->
### no-refactor-p1-t2 · discovery · no-refactor-because P1.T2 (phase 1)

the port changed only each handler's input shape; the gate body moved into one gate() function and the shared fake context (test/fake.ts) was factored as part of the green step

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-10-20T06:58:27+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

the queue was written, measured redundant against OpenCode's own OPENCODE_SESSION_ID, and deleted with its tests; nothing was left to collapse

<!-- fr:journal kind=finding scope=plan id=p1-v2-loads-sources-dir-as-plugin-resolved created=2026-10-20T07:31:17+00:00 state=open resolves=p1-v2-loads-sources-dir-as-plugin out_of_scope=true -->
### p1-v2-loads-sources-dir-as-plugin-resolved · finding [out-of-scope] · resolves p1-v2-loads-sources-dir-as-plugin: OpenCode 2 loads the delivered sources directory as a second plugin

Delivery layout is phase 3's subject, and phase 3 now carries it explicitly as P3.T3.S4: V2 scans the plugins directory for directories too, so the 1.x loader+sources pair loads the plugin twice; the phase delivers exactly one entrypoint and asserts a single 'loading plugin' line.

<!-- fr:journal kind=review scope=plan id=p1-review created=2026-10-20T07:31:21+00:00 phase=1 -->
### p1-review · review · Phase 1 reviewed by an independent agent: 3 findings, all in scope, all fixed (phase 1)

Reviewer: ses_ea7e51e67ffe3eJ0m8pXOhZ7HN (general agent, read-only, one context).
It was given the spec, the phase plan, the implementer's record and the diff
(8e20a4b25..HEAD), told to judge adversarially and to run both suites itself.
It confirmed the port loads and the behaviours survive, and raised three
findings — every one in scope, none refuted:

- p1-r1: src/index.ts named types that no longer exist (ToolBeforeEvent,
  ShellCreateEvent), so `tsc --noEmit` failed and GateEvent collapsed to any;
  bun test transpiles only, so CI had no type gate at all.
- p1-r2: spec R6 claims fr reads OPENCODE_SESSION_ID; the Python reader still
  read only FR_OPENCODE_SESSION_ID, which the plugin no longer sets.
- p1-r3: the "directory, not worktree" test passed its second argument to a
  helper that ignored it, so it was the same call as the test above and could
  not fail for the reason it named.

All three are fixed in a6fd95d7e and every fix is verified below. The review
also confirmed the two things the phase actually depended on: the plugin
loads on 2.0.32 (it previously did not load at all) and the removed session
queue really is redundant.

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-10-20T07:31:21+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · index.ts named deleted types, so tsc failed and the gate event was untyped (phase 1)

src/index.ts:140 `GateEvent = ToolBeforeEvent & {...}` and :214
`event as ShellCreateEvent` referenced types that the session.ts removal had
deleted; `bunx tsc --noEmit` (the package's own strict tsconfig, which
includes src and test) failed on both, and `GateEvent` silently became `any`.
That is the one place the port's correctness lives — that `execute.before`
carries `tool`/`input` — so `event.args` would have compiled just as well.
CI ran only `bun test`, which transpiles without typechecking.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-10-20T07:31:21+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · Spec R6 said fr reads OPENCODE_SESSION_ID, but the reader still read only FR_OPENCODE_SESSION_ID (phase 1)

The phase amended R6 to the measured mechanism (OpenCode 2 sets
OPENCODE_SESSION_ID on every command it spawns) and removed the plugin export
— but left fr reading the FR_ variable the plugin used to set, so the amended
requirement was false as written: on 2.0 fr would have observed no session at
all and reported it unobserved, with a message blaming a plugin that no longer
exports anything. The spec is the contract, so the code had to move to it.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-10-20T07:31:21+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · The 'directory, not worktree' test was a duplicate that could not fail (phase 1)

test/index.test.ts declared `makeHook(directory, _worktree = directory)` and
never read the second parameter, so `makeHook(repo, "/")` was byte-for-byte
the call above it. It is the only assertion the port added for the V1→V2 base
change (`ctx.worktree || ctx.directory` → `ctx.location.directory`), so a
regression back to a project root would have stayed green.

<!-- fr:journal kind=decision scope=plan id=p1-r2-fixed-in-phase-1 created=2026-10-20T07:31:21+00:00 phase=1 -->
### p1-r2-fixed-in-phase-1 · decision · R6's reader half landed in phase 1, not phase 4 (phase 1)

The reviewer is right that an amended requirement must hold. Rather than leave
R6 false until the reader phase, `SESSION_ID_ENVS` became an ordered tuple of
keys per harness (opencode: FR_OPENCODE_SESSION_ID then OPENCODE_SESSION_ID)
and `current_session` reads them in order; `why_unobservable` and visual.py
name the variable fr actually read. Phase 4 keeps the store move
(session_v2/session_message) and the loud 1.x refusal; its plan step was
re-pointed to the wording that is actually left.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-10-20T07:31:21+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: index.ts named deleted types, so tsc failed and the gate event was untyped (phase 1)

GateEvent is `{tool: string; input?: unknown}` and takes the real event at the call site (a renamed hook field is a compile error there); ShellCreateEvent is imported from ./pin; package.json gains `typecheck` and ci.yml runs `bunx tsc --noEmit` before `bun test`. Verified: `bunx tsc --noEmit` exits 0.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-10-20T07:31:21+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: Spec R6 said fr reads OPENCODE_SESSION_ID, but the reader still read only FR_OPENCODE_SESSION_ID (phase 1)

telemetry.session_id_from reads SESSION_ID_ENVS (now a tuple per harness: FR_OPENCODE_SESSION_ID, then OPENCODE_SESSION_ID) and _session_under uses it; observed.why_unobservable and visual.py name OPENCODE_SESSION_ID; tests/unit/test_run_observed_opencode.py asserts the native key resolves and that the FR_ override still wins. Verified: test_run_observed_opencode.py, test_run_observed_resolve_opencode.py, test_journal_operator_guard_opencode.py, test_run_cli.py -k unobservable/opencode/notice all green.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-10-20T07:31:21+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: The 'directory, not worktree' test was a duplicate that could not fail (phase 1)

The fake context carries location.project.directory (test/fake.ts) and the test now loads with directory=<a temp dir outside the repo> + projectDirectory=<the repo>: the relative target is outside any fr-enabled repo (allowed) while an absolute target in the project is still denied — a pair that pins the base rather than an allow. Verified: bun test 107 pass, tsc clean.
