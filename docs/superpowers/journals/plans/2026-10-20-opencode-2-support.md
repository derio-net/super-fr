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

<!-- fr:journal kind=decision scope=plan id=p2-verdict-table-captured created=2026-10-20T08:44:41+00:00 phase=2 -->
### p2-verdict-table-captured · decision · The 32-row verdict table was produced by running fr-isolation-guard.sh; no row was hand-adjusted (phase 2)

tests/fixtures/hooks/capture_guard_verdicts.py builds a sandbox with tests/fixtures/hooks/guard-world.sh
(base fr repo, a marked linked worktree under HOME/.cache/fr/worktrees, an unmarked linked worktree,
another fr repo, a non-fr git repo, an allowed-prefix dir, a non-allowed dir), writes the row's
sentinel, runs the real bash script on a synthesized PreToolUse payload, and records expected,
the deny text (paths collapsed to placeholders) and sentinel_after. Rows: no sentinel, plain
base command, base subdir, linked-worktree cwd, cwd outside base, cd into worktree (bare, quoted,
tilde), cd into allowed prefix, cd prefix-then-anywhere (blessed #421 rider), cd non-allowed dir,
cd other fr repo + fr isolation up / + make / + FR_BASE_OK, cd non-fr repo, cd non-fr subdir
rider (rev2-f1), cd unmarked same-repo worktree, cd gone path, relative cd, cd base, `fr isolation
status && make`, env-prefixed fr isolation up, uv run fr run start, fr run advance, fr init/--version/
skills, fr plan, `echo fr isolation status`, multi-line, live stamped sentinel, orphaned sentinel heal.
Result: 14 deny, 18 allow, one sentinel retired (the heal). Every row came from the script; none
was edited. Re-running the capture is byte-identical. One builder script serves both engines so
the two loaders cannot judge in different worlds; the YAML carries its own placeholder map, which
the Python loader asserts equals the capture's.

<!-- fr:journal kind=discovery scope=plan id=p2-port-stub-red created=2026-10-20T08:44:41+00:00 phase=2 -->
### p2-port-stub-red · discovery · The TS verdict loader was observed red (15 of 33 failing) against a stub that always allows (phase 2)

Before guard.ts landed in the loader run, decideShell was replaced by an always-allow stub:
18 pass / 15 fail (every deny row plus the heal row). With the port: 33/33. The Python loader
re-runs all 32 rows against the bash script (33 tests incl. coverage/placeholder check).

<!-- fr:journal kind=decision scope=plan id=p2-parity-not-improvement created=2026-10-20T08:44:41+00:00 phase=2 -->
### p2-parity-not-improvement · decision · What the TS port deliberately reproduces, and what it does not (phase 2)

Reproduced on purpose, with comments: start-anchored-only allowances (`fr isolation status && make`
allowed), only the leading cd evaluated (`cd <prefix> && cd <base> && …` allowed), first line only,
FR_BASE_OK honoured only on the cross-repo cd branch (as in bash), fail-open on internal error.
Not reproduced: (1) the bash writer waits up to ~60s for the sentinel lock then writes anyway;
the TS writer and heal wait ~1s (20×50ms) because they run synchronously inside the OpenCode
server — same outcome (writer arms anyway; guard skips heal and stays armed). (2) The lock owner
is the server PID shared by every handler; sound only because every take/act/release is
synchronous with no await between. (3) The external-mode "base repo is itself the workspace"
branch is ported but NOT in the table (needs container evidence) — untested by parity.

<!-- fr:journal kind=decision scope=plan id=p2-workdir-is-cwd created=2026-10-20T08:44:41+00:00 phase=2 -->
### p2-workdir-is-cwd · decision · The shell gate judges V2's `workdir` (resolved against the session directory), not ctx.location.directory alone (phase 2)

Plan P2.T3.S3 said to pass ctx.location.directory. V2's shell input is `{command, workdir?}`
(measured, p2-v2-tool-inputs), and the bash guard judges the cwd the command runs in. Using the
session directory would refuse `git status` with workdir=<worktree> and judge workdir=<base> by
the wrong directory. shellCwd() is used by the gate, the push guard and bind.

<!-- fr:journal kind=decision scope=plan id=p2-sentinel-shape-follows-bash created=2026-10-20T08:44:41+00:00 phase=2 -->
### p2-sentinel-shape-follows-bash · decision · The sentinel is written as {repo_root, skill, started_at[, workspaces]}, not the plan's {repo_root, workspaces, session, created} (phase 2)

Spec R10 requires "the same JSON shape the guard and fr already read". fr-pipeline-sentinel.sh writes
repo_root/skill/started_at and adds workspaces only when it carries a live entry; the plan's shape
would have been a new contract. Python tests (test_sentinel_lifecycle.py) run the TS writer under bun
and assert its key set equals the bash writer's, then stamp it with fr.isolation.types.
stamp_sentinel_workspace, reload it through the TS writer (stamp carried) and have the bash guard
deny — so Python reader, TS writer and bash guard are held together by one test. No Python
production code changed.

<!-- fr:journal kind=decision scope=plan id=p2-plan-vs-spec-names created=2026-10-20T08:44:41+00:00 phase=2 -->
### p2-plan-vs-spec-names · decision · Test file named guard-verdicts.test.ts (spec §B), not guard.test.ts (plan); push guard acts on git push only (phase 2)

Spec §B names packages/fr-opencode-plugin/test/guard-verdicts.test.ts. The plan's "git push / gh pr
merge" push guard: the bash hook refuses only `git push` (its ERE, every line), and R4 says "today's
decision", so `gh pr merge` is allowed by both; push.test.ts compares 15 commands against the real
bash hook with a stub gh, including `gh pr merge 12` (allowed by both).

<!-- fr:journal kind=decision scope=plan id=p2-parity-markers-deferred created=2026-10-20T08:44:41+00:00 phase=2 -->
### p2-parity-markers-deferred · decision · No new super-fr-parity markers in index.ts; phase 5 owns parity.yaml and moves markers with it (phase 2)

Adding markers for the newly ported scripts without moving parity.yaml cells risks a red
`fr harness parity --check`; phase 5's P5 task owns both. index.ts lists the ported scripts in prose.

<!-- fr:journal kind=discovery scope=plan id=p2-v2-tool-inputs created=2026-10-20T08:44:41+00:00 phase=2 -->
### p2-v2-tool-inputs · discovery · Measured in a local OpenCode 2.0.32 store: skill input is {id}, shell input is {command, workdir?} (phase 2)

Read-only sqlite query of session_message tool parts: a `skill` call recorded
`"input":{"id":"fr-goal"}`; `shell` calls carried key sets {command} and {command, workdir}.
The sentinel writer reads `id` first (then name/skill/skill_name, as the bash hook tries spellings).
session.deleted's shape {data:{sessionID}} was read from @opencode/client 2.0.32 typings, not observed live.

<!-- fr:journal kind=decision scope=plan id=p2-spawn-consolidated created=2026-10-20T08:44:41+00:00 phase=2 -->
### p2-spawn-consolidated · decision · One bounded, never-throwing spawn module (src/spawn.ts) for every fr/gh/git call the new and old handlers make (phase 2)

run() (async, execFile with timeout + SIGKILL, resolves {code, stdout, stderr}, code null when it never
ran/was killed) and runSync() (spawnSync, same contract) replace the copies in pin, claim and idle and
serve nag, bind, push, guard and sentinel. marker.ts (the phase-1 edit gate) still uses unbounded
execFileSync — see p2-marker-unbounded.

<!-- fr:journal kind=decision scope=plan id=p2-opencode-2-1-0-measured created=2026-10-20T08:44:41+00:00 phase=2 -->
### p2-opencode-2-1-0-measured · decision · The host binary is OpenCode 2.1.0, so the typings pin moved to 2.1.0 and CI probes both 2.x versions (phase 2)

`@opencode/plugin` was pinned at 2.0.32 (the version phase 1 measured) while the binary on
this host is 2.1.0 — and the live probe, not the typechecker, is what surfaced the
difference: a hand-built context in the probe broke on `session.hook`, which is a probe
bug, but chasing it measured the real 2.1.0 context (`Object.keys(ctx)` from a plugin:
session exposes hook/get/prompt/..., location carries directory + project). 2.1.0 is the
same V2 API, so the spec's "2.0.32" is amended to name both and CI's live probe runs a
matrix over ["2.0.32", "2.1.0"] — a pinned dev dependency that drifts from the running
binary is exactly how a hook-name break ships green.

<!-- fr:journal kind=finding scope=plan id=p2-marker-unbounded created=2026-10-20T08:44:41+00:00 phase=2 state=open review_scope=out -->
### p2-marker-unbounded · finding [open] (reviewer: out of scope) · The edit gate's git calls in marker.ts have no timeout (phase 2)

marker.ts runs git/pwd/bash through execFileSync without a timeout; a hung git stalls the server. Not
changed here because it would alter the edit gate's decision on timeout (phase-1 surface); move it to
runSync with an explicit fail-closed choice.

<!-- fr:journal kind=finding scope=plan id=p2-not-proven-live created=2026-10-20T08:44:41+00:00 phase=2 state=open review_scope=in -->
### p2-not-proven-live · finding [open] (reviewer: in scope) · None of the phase-2 handlers has run inside a real OpenCode 2 session (phase 2)

Every handler is proven against fakes (fake ctx, stub runners) and, for the guard/push/bind decisions,
against the real bash scripts. Not proven: that a throw from execute.before for `shell` reaches the
model as the refusal text, that execute.after fires for `skill` with status "completed", that
`context`'s event.system.push reaches the request, and that session.deleted arrives on the
subscription. These are R15's post-merge live rows.

<!-- fr:journal kind=finding scope=plan id=p2-full-suite-preexisting-failures created=2026-10-20T08:44:41+00:00 phase=2 state=open review_scope=in -->
### p2-full-suite-preexisting-failures · finding [open] (reviewer: in scope) · The first full suite came back red, and three of its failures were this branch's own doing (phase 2)

`uv run pytest -q --no-cov -n auto` came back 12989 passed, 2 failed, 12 errors
(pre-fix log p2-suite-full-suite.log). Two causes were phase 2's: the live delivery
probe builds the context `setup()` runs against, and phase 2 gave setup a
`session.hook("context")` registration, so the probe's `session: {}` made the delivered
plugin fail to load with `ctx.session.hook is not a function`; and
tests/unit/test_triage_driver_adapter.py errored twelve times because a sandbox fixture
imported under an alias is not a fixture pytest can resolve. The third —
test_run_evidence_separate_context.py expecting the old `FR_OPENCODE_SESSION_ID` wording —
was phase 1's R6 change, not phase 2's. All three are fixed in 62575696e, and the full
suite then passed 13003/13003 with exit=0 (post-fix log p2-full-suite.log). The first
version of this entry called all three pre-existing; review p2r-2 caught that, and it is
corrected here rather than left in the durable evidence.

<!-- fr:journal kind=finding scope=plan id=p2-full-suite-preexisting-failures-resolved created=2026-10-20T08:44:41+00:00 phase=2 state=fixed resolves=p2-full-suite-preexisting-failures -->
### p2-full-suite-preexisting-failures-resolved · finding [fixed] · resolves p2-full-suite-preexisting-failures: The first full suite came back red, and three of its failures were this branch's own doing (phase 2)

Fixed in 62575696e: the live probe's sentinel now supplies `session.hook/get/prompt` (the
domains setup registers on), test_triage_driver_adapter.py imports the drive sandbox by
name so pytest resolves it, and the wordings name OPENCODE_SESSION_ID. Full suite
afterwards: 13003 passed, 108 skipped, exit=0.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t1 created=2026-10-20T08:44:41+00:00 phase=2 -->
### no-refactor-p2-t1 · discovery · no-refactor-because P2.T1 (phase 2)

The capture script and world builder are new and single-purpose; the loader reuses the script's own judge(), so there was no duplication to remove.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t2 created=2026-10-20T08:44:41+00:00 phase=2 -->
### no-refactor-p2-t2 · discovery · no-refactor-because P2.T2 (phase 2)

sentinel.ts already holds the lock, path and workspace readers that guard.ts reuses; the bounded spawn went to spawn.ts in P2.T4.S3.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t3 created=2026-10-20T08:44:41+00:00 phase=2 -->
### no-refactor-p2-t3 · discovery · no-refactor-because P2.T3 (phase 2)

guard.ts and push.ts share sentinel.ts and spawn.ts; the remaining duplication (regex spellings of [[:space:]]) mirrors the bash script line for line on purpose.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t4 created=2026-10-20T08:44:41+00:00 phase=2 -->
### no-refactor-p2-t4 · discovery · no-refactor-because P2.T4 (phase 2)

Done as P2.T4.S3: pin, claim, idle, nag and bind now spawn fr through spawn.ts run(); guard/sentinel use runSync.

<!-- fr:journal kind=review scope=plan id=p2r-review created=2026-10-20T08:44:53+00:00 phase=2 -->
### p2r-review · review · Phase 2 reviewed by an independent agent: 3 in-scope findings, 1 filed, and 38 extra inputs with no divergence (phase 2)

Reviewer: ses_ea7a1e857ffeH3VpiFAWn8ns2S (general agent, read-only, one context). Given the
spec, 02.yaml, the implementer's record, the plan journal, both bash engines and the TS port,
and told to treat the record as a hypothesis list rather than evidence. It ran every suite
itself (tsc exit 0, bun 202 pass, the two Python hook files 151 passed, the live probe 2
passed on the host's 2.1.0, ruff clean), re-ran the capture without writing and confirmed
`guard-verdicts.yaml` is byte-identical, then drove both engines over 38 inputs NOT in the
table (cd variants, `;` and tab separators, tilde, quoted paths, relative `..`, the
allow-prefix root, a corrupt sentinel, a numeric repo_root, non-array workspaces, live and
gone workspaces, a symlinked cwd, cwd-is-a-file, empty command, redirects, env prefixes,
multi-line) and got 0 divergent verdicts and 0 divergent reason strings. It also compared
the push matcher and the bind/unbind argv against the real bash hooks.

It found three things phase 2 had to fix (p2r-1 nag memory, p2r-2 a stale record, p2r-3 a
plan step describing a sentinel shape nobody implemented), filed one for a follow-up
(p2r-4 bare `git` from PATH, beside the implementer's p2-marker-unbounded), and explicitly
cleared the things it expected to be wrong and were not (sentinel shape/GC across bash, TS
and Python; push refusal text; the start-anchored allowance; the bounded spawn path).

<!-- fr:journal kind=finding scope=plan id=p2r-1 created=2026-10-20T08:44:53+00:00 phase=2 state=open review_scope=in -->
### p2r-1 · finding [open] (reviewer: in scope) · The nag's once-per-session memory is per plugin copy, so R9's one system part becomes two (phase 2)

nag.ts allocated its `served` set inside createNagHandler and took no shared-memory seam, so
index.ts could not pass one. OpenCode 2 loads the delivered plugin twice while the 1.x
loader+sources layout is still being delivered (phase-1 finding
p1-v2-loads-sources-dir-as-plugin, deferred to P3.T3.S4), and `claim.ts`/`idle.ts` already
document and fix exactly this ("module state is per copy, globalThis is not"). Each copy
registers its own `session.hook("context")`, so a top-level session's first request would get
two identical system parts and two `fr acceptance status --brief` spawns — contradicting R9
and Test Plan item 6, which the post-merge live row would have failed. No test could see it:
every test built one handler.

<!-- fr:journal kind=finding scope=plan id=p2r-2 created=2026-10-20T08:44:53+00:00 phase=2 state=open review_scope=in -->
### p2r-2 · finding [open] (reviewer: in scope) · The phase record called three of its own failures pre-existing, and miscounted the verdict table (phase 2)

The record filed `p2-full-suite-preexisting-failures` claiming the suite's 2 failures and 12
errors were in files the phase did not touch, naming the live delivery probe among them and
concluding "No commit in a52a0756f..HEAD touches packages/fr or those test files". Two of the
three were this phase's: the probe's sentinel builds the context setup() runs against, and
phase 2 gave setup a `session.hook("context")` registration against `session: {}`; and the
drive tests' sandbox, imported under an alias, was never a resolvable fixture. It also said
"13 deny, 19 allow" where the captured table is 14 deny / 18 allow, and its evidence log
predated the fix. The record is transient but journalled as-is by `fr run resolve`, so an
uncorrected record would have written a false cause into an append-only log.

<!-- fr:journal kind=finding scope=plan id=p2r-3 created=2026-10-20T08:44:53+00:00 phase=2 state=open review_scope=in -->
### p2r-3 · finding [open] (reviewer: in scope) · P2.T2.S2 still asserts a sentinel shape that was never implemented and that the reader rejects (phase 2)

The step text says the writer produces `{repo_root, workspaces, session, created}`. The
shipped writer produces `{repo_root, skill, started_at}` plus `workspaces` only when it
carries a live entry — matching fr-pipeline-sentinel.sh and the Python reader, which reads
none of `session`/`created`. The code is right and the journal records the divergence
(p2-sentinel-shape-follows-bash), but the plan is the live contract later phases read, and
phase 1 already set the precedent of rewriting a step whose premise fell (p1-r6).

<!-- fr:journal kind=finding scope=plan id=p2r-4 created=2026-10-20T08:44:53+00:00 phase=2 state=open review_scope=out -->
### p2r-4 · finding [open] (reviewer: out of scope) · The edit gate spawns bare `git` from PATH where the bash guard resolves FR_GIT_CANDIDATES (phase 2)

lib/fr-isolation-decision.sh pins an absolute git for the same reason gh#746 pins `fr`:
hooks and this plugin spawn with no shell. guard.ts (phase 2) and marker.ts (phase 1) call
`git` directly, and with git unreachable every toplevel probe is undefined, so the gate fails
open where the bash guard still denies. The verdict table cannot cover it — the sandbox
always has git on PATH. Filed with p2-marker-unbounded as issue #1221; moving both onto
resolved git belongs with the edit gate's own bounded-spawn work, not mid-port.

<!-- fr:journal kind=discovery scope=plan id=p2-tests-opened-a-credential-prompt created=2026-10-20T08:44:53+00:00 phase=2 -->
### p2-tests-opened-a-credential-prompt · discovery · A triage test could open a macOS credential dialog: a fixture repo with no origin/HEAD makes git ask github.com (phase 2)

Reported by another session watching the desktop: a full-suite run raised "Username for
'https://github.com'". Cause: test fixtures `git init` + `remote add origin
https://github.com/...` (a URL, never a network clone) and leave `origin/HEAD` unset, so any
path that resolves the default branch reaches `Checkout.default_branch()`'s fallback
`git remote set-head origin --auto`, which is a network call; with no credentials git falls
back to SSH_ASKPASS and macOS shows a modal dialog. Two fixes: `tests/conftest.py` gains an
autouse `_no_git_credential_prompt` (GIT_TERMINAL_PROMPT=0, GIT_ASKPASS=true,
SSH_ASKPASS/SUDO_ASKPASS dropped) so no test can ever ask a HUMAN, and the triage render
fixture records `refs/remotes/origin/HEAD` like a real clone so the network path is not
taken at all. This is test infrastructure, not a phase-2 surface, but it was found by
running the phase's suite and a prompt is worse than a failure.

<!-- fr:journal kind=finding scope=plan id=p2r-1-resolved created=2026-10-20T08:44:53+00:00 phase=2 state=fixed resolves=p2r-1 -->
### p2r-1-resolved · finding [fixed] · resolves p2r-1: The nag's once-per-session memory is per plugin copy, so R9's one system part becomes two (phase 2)

nag.ts exports SHARED_SERVED/sharedServed() (globalThis, the shape claim.ts uses), NagHandlerOptions takes `served?: Set<string>`, and index.ts passes sharedServed(). Test: two handlers built over one set serve one part between them and spawn fr once (test/nag.test.ts). bun 203 pass, tsc exit 0.

<!-- fr:journal kind=finding scope=plan id=p2r-2-resolved created=2026-10-20T08:44:53+00:00 phase=2 state=fixed resolves=p2r-2 -->
### p2r-2-resolved · finding [fixed] · resolves p2r-2: The phase record called three of its own failures pre-existing, and miscounted the verdict table (phase 2)

The implement-phase phase/2 record is corrected before resolve: 14 deny/18 allow, the suite finding now says two of its three causes were phase 2's (the live probe's fake context and the aliased sandbox fixture) and one was phase 1's wording, with the fix commit named, review_scope moved to `in`, resolved fixed, and evidence.tests re-pointed at a post-fix full-suite log.

<!-- fr:journal kind=finding scope=plan id=p2r-3-resolved created=2026-10-20T08:44:53+00:00 phase=2 state=fixed resolves=p2r-3 -->
### p2r-3-resolved · finding [fixed] · resolves p2r-3: P2.T2.S2 still asserts a sentinel shape that was never implemented and that the reader rejects (phase 2)

02.yaml P2.T2.S2 now states the shape fr-pipeline-sentinel.sh and fr.isolation.types actually use ({repo_root, skill, started_at}[, workspaces]), cites spec R10 and journal decision p2-sentinel-shape-follows-bash, and keeps the Python key-set assertion.

<!-- fr:journal kind=finding scope=plan id=p2r-4-resolved created=2026-10-20T08:44:53+00:00 phase=2 state=open resolves=p2r-4 tracked_by=derio-net/super-fr#1221 -->
### p2r-4-resolved · finding [deferred → derio-net/super-fr#1221] · resolves p2r-4: The edit gate spawns bare `git` from PATH where the bash guard resolves FR_GIT_CANDIDATES (phase 2)

Filed with p2-marker-unbounded as derio-net/super-fr#1221: bound the edit gate's git calls on spawn.ts' runSync and resolve git as the bash guard does, with a verdict-table row for git absent from PATH.

<!-- fr:journal kind=finding scope=plan id=p2-marker-unbounded-resolved created=2026-10-20T08:44:53+00:00 phase=2 state=open resolves=p2-marker-unbounded tracked_by=derio-net/super-fr#1221 -->
### p2-marker-unbounded-resolved · finding [deferred → derio-net/super-fr#1221] · resolves p2-marker-unbounded: The edit gate's git calls in marker.ts have no timeout (phase 2)

Same issue: marker.ts is the last caller still using unbounded execFileSync; moving it changes the edit gate's timeout decision, which is phase-1 surface and needs a deliberate fail-closed choice.

<!-- fr:journal kind=finding scope=plan id=p2-not-proven-live-resolved created=2026-10-20T08:44:53+00:00 phase=2 state=open resolves=p2-not-proven-live out_of_scope=true -->
### p2-not-proven-live-resolved · finding [out-of-scope] · resolves p2-not-proven-live: None of the phase-2 handlers has run inside a real OpenCode 2 session (phase 2)

By design and by contract: R15 and Test Plan items 1-6 name these as POST-MERGE live rows (a throw from execute.before reaching the model as the refusal text, execute.after on skill, context's system part reaching the request, session.deleted arriving). No pre-merge phase can prove them, and the acceptance matrix carries them as the opencode-2-* rows whose status stays walk-owed until the live walk, which `fr acceptance check` keeps failing until then.

<!-- fr:journal kind=discovery scope=plan id=p3-tui-spike created=2026-10-20T10:44:50+00:00 phase=3 -->
### p3-tui-spike · discovery · TUI spike, measured on opencode 2.1.0: a plugin DIRECTORY's `tui` entry loads and renders with no consumer-side packages; a cli.json FILE path is silently ignored (phase 3)

Throwaway XDG_CONFIG/DATA/STATE/CACHE_HOME and HOME, own service port (`opencode service set port`, stopped after),
TUI started under a pseudo-terminal in a git repo. Minimal entry `export default {id, setup(ctx)}` registering
`ctx.ui.slot({append: "prompt.footer.status"|"home.footer.status", render: () => <text>…</text>})`, setup writing a proof file.
1. `cli.json` = `{"plugins": ["<abs>/tui/statusline.tsx"]}` (a FILE): not loaded, no proof, no error, no toast.
   Reason, read from the binary: reconciliation does `if (resolved path isFile) continue` — only directories are taken.
2. Directory `<config>/opencode/plugins/fr-opencode-plugin/` containing `tui.tsx`, NO cli.json: loaded, setup ran,
   both slot texts rendered. The TUI scans the same plugins dirs as the server and resolves entrypoints by name:
   server = `<dir>/server` else `<dir>/index`; tui = `<dir>/tui` (a `tui/index.tsx` directory resolves too — the delivered layout).
3. cli.json `{"plugins": ["<abs dir outside plugins/>"]}`: loaded and rendered. So the working registration is key `plugins`,
   value an absolute DIRECTORY path (or file:// URL / ./relative), never a file.
4. Directory discovered AND listed in cli.json: setup ran ONCE (entries are de-duplicated by resolved href).
JSX, `solid-js` and `@opentui/solid` are supplied by the binary's runtime plugin (it maps those specifiers and
`@opencode/plugin/tui` to bundled modules and runs a Solid babel transform on .tsx): nothing installed consumer-side.
Hence P3.T1.S2's fallback (a keymap command) was NOT taken; the status line is real.

<!-- fr:journal kind=discovery scope=plan id=p3-one-load-measured created=2026-10-20T10:44:50+00:00 phase=3 -->
### p3-one-load-measured · discovery · Exactly one `loading plugin` line for the directory-only delivery; two for the 1.x shape (measured) (phase 3)

Isolated config, `opencode plugin list` under its own service. Directory only: one line,
`id=<plugins>/fr-opencode-plugin entrypoint=…/fr-opencode-plugin/index.ts`. Same plus the 1.x top-level loader
`fr-opencode-plugin.ts`: two lines (the directory, and the loader). The live test now asserts one.
(Under the interactive TUI the same single id is logged at each server reconciliation; that is one plugin, not two.)

<!-- fr:journal kind=decision scope=plan id=p3-tui-inside-the-plugin-dir created=2026-10-20T10:44:50+00:00 phase=3 -->
### p3-tui-inside-the-plugin-dir · decision · The TUI entry ships INSIDE the plugin directory (tui/index.tsx), contrary to R12's 'beside, not inside' (phase 3)

R12's premise ("the server loader picks up every top-level file", so the TUI must sit beside it) is false on 2.x:
the server resolves only `<dir>/server|index` and never imports `tui/`, and the TUI resolves only `<dir>/tui`.
The plan (P3.T3.S1) already said "into the plugin DIRECTORY (never top level)"; the measurement agrees with the plan.
A unit test asserts no server source imports `./tui`; the live test proves the server loads index.ts once and the TUI renders.
Sources live at packages/fr-opencode-plugin/src/tui/ (not the plan's packages/fr-opencode-plugin/tui/) so that
segment.ts's `../spawn` import resolves identically in the repo and in the delivered directory.

<!-- fr:journal kind=decision scope=plan id=p3-cli-json-lists-the-directory created=2026-10-20T10:44:50+00:00 phase=3 -->
### p3-cli-json-lists-the-directory · decision · install lists the plugin DIRECTORY in cli.json's plugins (redundant with discovery, kept for R12 and the probe) (phase 3)

deliver-opencode-plugin.sh install (called by install.sh) appends `<abs plugins>/fr-opencode-plugin` to
`<config>/opencode/cli.json`'s `plugins` with jq: created when absent; refused with the file named when it is not
a JSON object with a plugins array (JSONC with comments is refused, never rewritten); idempotent by exact path;
uninstall removes only that string. On 2.1.0 the TUI already discovers the directory, so the entry changes nothing
at runtime (de-duplicated, measured) — it is the R12 enablement directive and what the parity probe reads.

<!-- fr:journal kind=decision scope=plan id=p3-segment-uses-cwd-not-session created=2026-10-20T10:44:50+00:00 phase=3 -->
### p3-segment-uses-cwd-not-session · decision · The status line runs fr-statusline-segment.sh --format plain --cwd <the slot's session directory>; rule 1 (bound session) never fires (phase 3)

spawn.ts run() takes no stdin, and passing the OpenCode session id would mean a second spawn path, so the script is
asked by --cwd. The directory is per render: the slot input's `sessionID` is looked up with
context.data.session.get(id).location.directory (declared in @opencode/plugin dist/tui/context.d.ts and
@opencode/client SessionInfo.location), falling back to context.location.directory (the TUI's launch dir) for the
home screen or a session not loaded yet. segment.ts's createSegmentCache keeps one entry per session id, each with
its own coalesced refresher (250 ms, one read in flight, one queued); a render only reads the cache, so no
per-render or per-keystroke spawn. Text: `fr ⎇ <branch>` in a workspace, `<branch> · no fr-isolation` outside, an
em-dash for a missing branch or unreadable output, "" outside a git repo (a filesystem walk, no spawn). Refresh on
session.execution.{started,succeeded,failed,interrupted} and session.idle via ctx.data.on (the event's sessionID
when present, else every cached session). Proven: unit tests over the lookup and the cache; the live TUI test
(launch dir == session dir). Claimed, not live-proven: a session from ANOTHER project shows its own repo — spec
Test Plan item 5's "outside any repo shows none" for such a session is owed to the post-merge walk.

<!-- fr:journal kind=decision scope=plan id=p3-parity-probe-runs-the-delivery created=2026-10-20T10:44:50+00:00 phase=3 -->
### p3-parity-probe-runs-the-delivery · decision · fr.harness.observe's status-line probe runs this checkout's delivery into a temp config and reads it back (phase 3)

opencode_status_line_configured(config_dir): cli.json lists a directory (string or {package}, file:// accepted)
AND `<dir>/tui/index.tsx` exists; unreadable cli.json raises (unknown state is never absent). observe_interactions(root)
runs scripts/deliver-opencode-plugin.sh install into a TemporaryDirectory and applies that probe, so the observation
is derived from the delivery, not transcribed. check() takes it as an optional third argument and compares only probed
interaction cells (today status-line/opencode); commands/harness_cmd.py passes it (outside the phase's file list,
necessarily). parity.yaml is untouched: the row's `partial` maps to `present`, which the probe observes.

<!-- fr:journal kind=discovery scope=plan id=p3-tsx-not-typechecked created=2026-10-20T10:44:50+00:00 phase=3 -->
### p3-tsx-not-typechecked · discovery · src/tui/index.tsx is excluded from tsc; its proof is the live TUI test (phase 3)

Its JSX types come from @opentui/solid, a peer the binary bundles but node_modules does not carry. tsconfig excludes
exactly src/tui/index.tsx (pinned by test/tsconfig.test.ts); segment.ts (all the logic) is type-checked and unit-tested. tests/integration/test_opencode_plugin_live.py::
test_opencode_tui_renders_the_delivered_status_line starts the real TUI on a pty (own session, process group killed
after) and asserts `frstatusprobe · no fr-isolation` on screen. pty.fork() inside pytest hung in waitpid (pytest is
multi-threaded; forkpty warns of exactly this), so the probe uses openpty + Popen(start_new_session=True).

<!-- fr:journal kind=finding scope=plan id=p3-r12-text-contradicts-measurement created=2026-10-20T10:44:50+00:00 phase=3 state=open review_scope=in -->
### p3-r12-text-contradicts-measurement · finding [open] (reviewer: in scope) · Spec R12 says the TUI entry lives 'beside, not inside' the server plugin; the shipped (and only working) layout is inside (phase 3)

See p3-tui-inside-the-plugin-dir. The spec is the contract, so its R12 sentence (and its stated reason) should be
corrected to the measured layout: one directory, `index.ts` for the server, `tui/` for the TUI, cli.json listing the
directory (a file path is ignored by 2.1.0). Left open by the implementer because the spec was not in the phase's
files; the orchestrator edited R12 and section E before review — a contract that states a layout the code must not
use is worse than no sentence.

<!-- fr:journal kind=finding scope=plan id=p3-package-readme-describes-the-1x-loader created=2026-10-20T10:44:50+00:00 phase=3 state=open review_scope=in -->
### p3-package-readme-describes-the-1x-loader · finding [open] (reviewer: in scope) · packages/fr-opencode-plugin/README.md still described the 1.x loader, and said the shell is ungated (phase 3)

The delivery no longer writes the loader (and deletes a stale one), so the README's "How consumers get it" block
described a layout that no longer exists. It also carried a larger falsehood: "Bash is intentionally ungated
because an OpenCode tool hook cannot inspect filesystem effects performed by a shell command" — phase 2 shipped
the whole-line shell gate, so the README told a reader the opposite of what the plugin does. Rewritten before
review: the surface table, the one-directory layout with the cli.json entry and the stale-loader removal, the
shell gate and the push backstop, the nag, and the status line (including why tui/index.tsx alone is out of tsc).
R16 gives phase 5 the repo-level prose; this file documents the package and had to move with the code.

<!-- fr:journal kind=discovery scope=plan id=p3-live-test-leaked-a-service created=2026-10-20T10:44:50+00:00 phase=3 -->
### p3-live-test-leaked-a-service · discovery · The live test left an OpenCode service behind, and it held the runner's stdout open for three more minutes (phase 3)

`time uv run pytest tests/integration/test_opencode_plugin_live.py` printed "3 passed in 34.19s" and then took
3m19s of wall clock to exit (175s of system CPU). Cause: OpenCode's service is a detached daemon that inherits the
stdio of the CLI call that first started it, so a survivor keeps the runner's stdout pipe open — and under a
`timeout` wrapper that reads as `exit 124` on a run whose tests had all passed (the flake seen during the phase).
`service stop` deletes service.json when it succeeds, so the fix captures the pid recorded in this environment's
service.json BEFORE stopping and reaps it (SIGTERM, then SIGKILL, 5s bound) if it is still alive. Same command
after: 3 passed in 33.09s, 33.8s total.

<!-- fr:journal kind=discovery scope=plan id=p3-review-fix-measurements created=2026-10-20T10:44:50+00:00 phase=3 -->
### p3-review-fix-measurements · discovery · After the review fixes: live file 3 passed in 34.18s (34.8s wall, no lingering exit), full suite 13026 passed / 108 skipped, exit=0 (phase 3)

`time FR_REQUIRE_OPENCODE=1 uv run pytest -q --no-cov tests/integration/test_opencode_plugin_live.py`: 3 passed in
34.18s, 34.8s total, so the p3-live-test-leaked-a-service fix still holds (the 33.8s claim is now 34.8s). The only
opencode processes afterwards were the operator's own pre-existing sessions. Full suite `-n auto` took 21m39s on
this host (contended). For later phases: deliver-opencode-plugin.sh now validates cli.json before any write, and its
one writer (write_cli_json) follows symlinks and keeps the mode — any new cli.json edit must go through it.

<!-- fr:journal kind=finding scope=plan id=p3-r12-text-contradicts-measurement-resolved created=2026-10-20T10:44:50+00:00 phase=3 state=fixed resolves=p3-r12-text-contradicts-measurement -->
### p3-r12-text-contradicts-measurement-resolved · finding [fixed] · resolves p3-r12-text-contradicts-measurement: Spec R12 says the TUI entry lives 'beside, not inside' the server plugin; the shipped (and only working) layout is inside (phase 3)

Spec R12 now states the measured layout (the TUI inside the plugin directory as its `tui` entry, cli.json listing
the DIRECTORY, a file path silently ignored by 2.1.0), records the earlier draft's false premise and the double
load it caused, and keeps the fallback/partial clause. Section E ("Delivery and configuration") is corrected the
same way.

<!-- fr:journal kind=finding scope=plan id=p3-package-readme-describes-the-1x-loader-resolved created=2026-10-20T10:44:50+00:00 phase=3 state=fixed resolves=p3-package-readme-describes-the-1x-loader -->
### p3-package-readme-describes-the-1x-loader-resolved · finding [fixed] · resolves p3-package-readme-describes-the-1x-loader: packages/fr-opencode-plugin/README.md still described the 1.x loader, and said the shell is ungated (phase 3)

packages/fr-opencode-plugin/README.md rewritten against the shipped code: surface table matched to index.ts's
registrations, one-directory delivery, cli.json semantics (create/refuse-unparsable/idempotent/uninstall),
stale 1.x loader removed, shell gate and push backstop explained, nag and status line documented, and
`bunx tsc --noEmit` added to the dev commands.

<!-- fr:journal kind=finding scope=plan id=p1-v2-loads-sources-dir-as-plugin-resolved-2 created=2026-10-20T10:44:50+00:00 phase=3 state=fixed resolves=p1-v2-loads-sources-dir-as-plugin -->
### p1-v2-loads-sources-dir-as-plugin-resolved-2 · finding [fixed] · resolves p1-v2-loads-sources-dir-as-plugin: OpenCode 2 loads the delivered sources directory as a second plugin (phase 3)

The delivery is now the directory alone (index.ts is the server entry); the top-level loader is no longer written and
a stale one is deleted on install and uninstall. tests/integration/test_opencode_plugin_live.py asserts exactly one
`loading plugin` line for super-fr against opencode 2.1.0; the unit tests assert nothing is delivered at the top level.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t1 created=2026-10-20T10:44:50+00:00 phase=3 -->
### no-refactor-p3-t1 · discovery · no-refactor-because P3.T1 (phase 3)

The spike's throwaway statusline.tsx was replaced outright by the real src/tui/index.tsx; nothing of it survived to clean.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t2 created=2026-10-20T10:44:50+00:00 phase=3 -->
### no-refactor-p3-t2 · discovery · no-refactor-because P3.T2 (phase 3)

segment.ts is new and single-purpose and reuses spawn.ts run(); index.tsx is a 30-line shell over it, so there was no duplication to remove.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t3 created=2026-10-20T10:44:50+00:00 phase=3 -->
### no-refactor-p3-t3 · discovery · no-refactor-because P3.T3 (phase 3)

deliver-opencode-plugin.sh got shorter (the generated loader is gone); register/unregister are its only new functions, and observe's probe reuses the delivery script rather than re-describing it.

<!-- fr:journal kind=review scope=plan id=p3-review created=2026-10-20T10:44:55+00:00 phase=3 -->
### p3-review · review · Phase 3 reviewed by an independent agent: 1 red gate it did not cause, 2 major-ish delivery defects, 7 smaller ones — all reproduced, none argued (phase 3)

Reviewer: ses_ea738c8b4ffeMnME45Y0tkt4bk (general agent, read-only, its own context). Given the
spec, 03.yaml, the implementer's record as a HYPOTHESIS list, and the earlier phases' findings,
and told to measure rather than accept. It ran tsc (exit 0), bun test (214 pass), the delivery
and harness unit tests (191 pass), the live probe (3 passed in 33.04s, 33.4s wall — reproducing
the record's 33.8s), `fr harness parity --check`, `fr validate artifacts` and ruff (all clean),
then counted `opencode serve` processes before and after the live run (no leak) and drove the
delivery script by hand in /tmp for each promise it makes.

It confirmed the two claims that mattered most and were easiest to fake: the `loading plugin`
assertion requires exactly one line (zero fails too), and the TUI assertion is
`frstatusprobe · no fr-isolation`, text only `fr-statusline-segment.sh` can produce, so a stale
render cannot satisfy it.

It then reproduced eight defects the record had not noticed — the important one being that
`install` copies the plugin BEFORE deciding about `cli.json`, so a refused config leaves a
partial install and aborts every later install.sh step (the repo's own rule: a refusal must
move no byte). It also found the acceptance gate already red from a phase-1 deletion (filed
out, absorbed by P5.T2.S1) and that the record's evidence log predated the commit it was cited
for — the same defect the phase-2 review filed.

<!-- fr:journal kind=finding scope=plan id=p3-r1 created=2026-10-20T10:44:55+00:00 phase=3 state=open review_scope=out -->
### p3-r1 · finding [open] (reviewer: out of scope) · fr acceptance check is red on the branch: a matrix row cites a test phase 1 deleted (phase 3)

`uv run fr acceptance check` exits 1: row `opencode-run-session` cites
`super-fr:packages/fr-opencode-plugin/test/session.test.ts`, deleted in b67e1a50e ("drop the
session-export queue") — i.e. in phase 1, so the ref is already dangling at phase 3's base and
phases 1-2's reviews did not catch it. The row's note still describes the removed `shell.env`
export. .github/workflows/acceptance-report.yml runs `fr acceptance check` as a gating step, so
the PR is red on that job however green everything else is. Phase 5 owns the matrix, and
P5.T2.S1 now names this obligation explicitly (re-point the level ref at the session probe
phase 4 ships, by test NAME).

<!-- fr:journal kind=finding scope=plan id=p3-r2 created=2026-10-20T10:44:55+00:00 phase=3 state=open review_scope=in -->
### p3-r2 · finding [open] (reviewer: in scope) · install copies the plugin directory before deciding about cli.json, so a refused config leaves a partial install and aborts install.sh (phase 3)

deliver-opencode-plugin.sh ran `mkdir -p`, `rm -rf`, three `cp`s and only then `register`, whose
validation can refuse. Reproduced with a JSONC cli.json: exit 1 "refusing to edit …cli.json",
with `<plugins>/fr-opencode-plugin` already written. scripts/install.sh is `set -euo pipefail`
and calls it unguarded, so the abort also skips every later step (Hermes, the fr CLI, cache
cleanup) after that partial write. The same order exposed the old plugin dir to `rm -rf` before
anything was validated — the exact shape this repo forbids elsewhere ("every refusal must fire
before a byte moves").

<!-- fr:journal kind=finding scope=plan id=p3-r3 created=2026-10-20T10:44:55+00:00 phase=3 state=open review_scope=in -->
### p3-r3 · finding [open] (reviewer: in scope) · uninstall cannot remove the cli.json entry once the plugins dir is gone, and install.sh skips delivery entirely in that case (phase 3)

Two paths leave the entry: `uninstall` returned early on `[ -d "$plugins" ] || return 0`
(measured: cli.json still holding the exact path, no plugins dir, exit 0, file byte-identical),
and install.sh --uninstall only called the delivery script when the loader file or the directory
existed, so a directory removed by hand or another tool never reached unregister. Both contradict
the phase's claim that uninstall removes exactly what install wrote, and the residue is precisely
the state the new config probe reports as `absent`.

<!-- fr:journal kind=finding scope=plan id=p3-r4 created=2026-10-20T10:44:55+00:00 phase=3 state=open review_scope=in -->
### p3-r4 · finding [open] (reviewer: in scope) · the cli.json rewrite does not preserve the file's identity: a symlinked cli.json is replaced, and its mode is reset (phase 3)

register/unregister wrote a temp file and `mv`d it over cli.json. Measured: with
`opencode/cli.json -> ../dot/cli.json`, install left a REGULAR file at the config path and the
dotfiles target unchanged (so the next stow/checkout silently reverts the entry), and a 0600
cli.json came back 0644. Dotfile managers symlinking ~/.config files are ordinary; "leaves every
other key untouched" was not the whole promise.

<!-- fr:journal kind=finding scope=plan id=p3-r5 created=2026-10-20T10:44:55+00:00 phase=3 state=open review_scope=in -->
### p3-r5 · finding [open] (reviewer: in scope) · register was append-if-absent, not the spec's drop-then-append: duplicates survive (phase 3)

The spec's §E says reinstall is idempotent by exact entry path "(drop ours, then append ours)";
the jq filter was `if index($e) then . else . + [$e] end`. Measured: a file already holding our
path twice still held it twice. The runtime effect is nil (OpenCode de-duplicates by href) but
the file the operator reads accumulates junk and the spec sentence was false.

<!-- fr:journal kind=finding scope=plan id=p3-r6 created=2026-10-20T10:44:55+00:00 phase=3 state=open review_scope=in -->
### p3-r6 · finding [open] (reviewer: in scope) · parity.yaml's status-line note still said no renderer or registration ships — the opposite of this phase (phase 3)

The note read "fr-statusline-segment.sh is harness-neutral (stdin or --cwd) and callable today; no
renderer/registration ships for OpenCode" while phase 3 ships both and the phase's own probe reads
that row. `fr harness parity --check` stayed green because it compares `state`, never the note, so
a green check was certifying prose that contradicts the code — and `fr harness parity` prints that
note to operators.

<!-- fr:journal kind=finding scope=plan id=p3-r7 created=2026-10-20T10:44:55+00:00 phase=3 state=open review_scope=in -->
### p3-r7 · finding [open] (reviewer: in scope) · the plan still described a cli.json FILE entry and a tui/ source dir the phase measured wrong and did not use (phase 3)

03.yaml's P3.T3.S2 still said install appends "the TUI entry's path" — a file path, which this
phase measured as silently ignored by 2.1.0 — and the phase's `files:` listed
`packages/fr-opencode-plugin/tui/**` where the sources are at `.../src/tui/**`. The plan is the
contract later phases and executors read; phase 1 (P1.T3) and phase 2's review (p2r-3) both set
the precedent of rewriting a step whose premise was measured false.

<!-- fr:journal kind=finding scope=plan id=p3-r8 created=2026-10-20T10:44:55+00:00 phase=3 state=open review_scope=in -->
### p3-r8 · finding [open] (reviewer: in scope) · the status line described the TUI's launch directory, not the session whose footer it renders (phase 3)

index.tsx captured `cwd` once in setup from `context.location?.directory`, and `render` ignored
the slot input whose payload carries `sessionID` — so every session tab and the home screen showed
the branch of the directory the TUI started in. The README said `--cwd <session dir>`, and Test
Plan item 5 ("a session opened outside any repo shows none") cannot hold for a session from
another project. The record was candid about the choice; the shipped prose was not.

<!-- fr:journal kind=finding scope=plan id=p3-r9 created=2026-10-20T10:44:55+00:00 phase=3 state=open review_scope=in -->
### p3-r9 · finding [open] (reviewer: in scope) · "src/tui/index.tsx is the only file outside tsc" was true but unenforced: the exclusion was a glob (phase 3)

tsconfig.json excluded `src/**/*.tsx`, not the one file the README named, and no test pinned the
excluded set. A future .tsx (a component, a second TUI entry) would silently escape the type gate
phase 1 added precisely because bun transpiles without typechecking.

<!-- fr:journal kind=finding scope=plan id=p3-r10 created=2026-10-20T10:44:55+00:00 phase=3 state=open review_scope=in -->
### p3-r10 · finding [open] (reviewer: in scope) · evidence.tests pointed at a suite log that predates the commit which changed the live test it is cited for (phase 3)

The phase-3 record cited a full-suite log taken before 365eaac90 rewrote
tests/integration/test_opencode_plugin_live.py (`_service_pid`/`_reap_service`), so the cited run
covered a different live test than HEAD's. The claim itself reproduced (3 passed, 33.4s), so this
is a stale pointer, not a false claim — but it is the same defect phase 2's review filed (p2r-2),
and a record is journalled as-is by `fr run resolve`.

<!-- fr:journal kind=decision scope=plan id=p3-acceptance-gate-is-red-until-phase-5 created=2026-10-20T10:44:55+00:00 phase=3 -->
### p3-acceptance-gate-is-red-until-phase-5 · decision · One red gate stays red through phases 4 and 5 by design: the matrix row phase 1 broke is fixed with the rest of the matrix (phase 3)

`fr acceptance check` exits 1 until phase 5 re-points `opencode-run-session`. It is deliberately
not fixed here: the row's honest replacement is the session probe PHASE 4 ships, and every
`opencode-2-*` row plus the three committed reports are rewritten together in P5.T2 so they never
disagree mid-run. P5.T2.S1 now carries the obligation in its own text, so it cannot be lost.

<!-- fr:journal kind=finding scope=plan id=p3-r1-resolved created=2026-10-20T10:44:55+00:00 phase=3 state=open resolves=p3-r1 out_of_scope=true -->
### p3-r1-resolved · finding [out-of-scope] · resolves p3-r1: fr acceptance check is red on the branch: a matrix row cites a test phase 1 deleted (phase 3)

Phase 1's deletion, discovered here, fixed where the matrix lives: P5.T2.S1 in
docs/superpowers/plans/2026-10-20-opencode-2-support/05.yaml now requires re-pointing
`opencode-run-session`'s level ref at the session probe phase 4 ships (by test NAME, never a
line number) and rewriting its stale `shell.env` note. The gate stays red, by design, until
phase 5 — which is also the only phase that may touch the matrix or its three reports.

<!-- fr:journal kind=finding scope=plan id=p3-r2-resolved created=2026-10-20T10:44:55+00:00 phase=3 state=fixed resolves=p3-r2 -->
### p3-r2-resolved · finding [fixed] · resolves p3-r2: install copies the plugin directory before deciding about cli.json, so a refused config leaves a partial install and aborts install.sh (phase 3)

validate_cli_json runs first and refuses with the file named, the remedy, and "Nothing was
written"; delivery then copies, then registers. install.sh catches the refusal and exits 1
saying fr-opencode-plugin was NOT installed, so the failure is one loud message rather than a
partial install plus silent skipping. Tests: test_a_refused_cli_json_moves_no_byte,
test_install_sh_fails_loudly_when_delivery_refuses.

<!-- fr:journal kind=finding scope=plan id=p3-r3-resolved created=2026-10-20T10:44:55+00:00 phase=3 state=fixed resolves=p3-r3 -->
### p3-r3-resolved · finding [fixed] · resolves p3-r3: uninstall cannot remove the cli.json entry once the plugins dir is gone, and install.sh skips delivery entirely in that case (phase 3)

The entry path is derived from the plugins directory's parent, so unregister no longer needs the
directory, and install.sh --uninstall calls the delivery script unconditionally. Tests:
test_uninstall_drops_the_entry_after_the_plugins_dir_is_gone,
test_install_sh_uninstall_calls_delivery_unconditionally.

<!-- fr:journal kind=finding scope=plan id=p3-r4-resolved created=2026-10-20T10:44:55+00:00 phase=3 state=fixed resolves=p3-r4 -->
### p3-r4-resolved · finding [fixed] · resolves p3-r4: the cli.json rewrite does not preserve the file's identity: a symlinked cli.json is replaced, and its mode is reset (phase 3)

One writer, write_cli_json: follows the symlink (relative links too), captures the target's mode
portably (stat -f '%Lp' / stat -c '%a'), writes the temp beside the REAL file, chmods it, then
moves it into place. Tests: a symlinked cli.json stays a symlink on install and uninstall; a 0600
file stays 0600.

<!-- fr:journal kind=finding scope=plan id=p3-r5-resolved created=2026-10-20T10:44:55+00:00 phase=3 state=fixed resolves=p3-r5 -->
### p3-r5-resolved · finding [fixed] · resolves p3-r5: register was append-if-absent, not the spec's drop-then-append: duplicates survive (phase 3)

The filter is now `((.plugins // []) | map(select(. != $e))) + [$e]`, matching spec §E. Test: a
file holding our path twice plus an object, a number and a null comes out with those three kept
and exactly one copy of ours.

<!-- fr:journal kind=finding scope=plan id=p3-r6-resolved created=2026-10-20T10:44:55+00:00 phase=3 state=fixed resolves=p3-r6 -->
### p3-r6-resolved · finding [fixed] · resolves p3-r6: parity.yaml's status-line note still said no renderer or registration ships — the opposite of this phase (phase 3)

The status-line/OpenCode note now describes what ships, including that render is proven live and
the post-merge walks are still owed; `state` stays `partial`. `fr harness parity --check` and the
parity tripwire stay green.

<!-- fr:journal kind=finding scope=plan id=p3-r7-resolved created=2026-10-20T10:44:55+00:00 phase=3 state=fixed resolves=p3-r7 -->
### p3-r7-resolved · finding [fixed] · resolves p3-r7: the plan still described a cli.json FILE entry and a tui/ source dir the phase measured wrong and did not use (phase 3)

03.yaml's P3.T3.S2 now says the plugin DIRECTORY is the registered entry and a file path is
ignored (citing p3-tui-spike and p3-cli-json-lists-the-directory), and the phase's `files:` names
packages/fr-opencode-plugin/src/tui/**.

<!-- fr:journal kind=finding scope=plan id=p3-r8-resolved created=2026-10-20T10:44:55+00:00 phase=3 state=fixed resolves=p3-r8 -->
### p3-r8-resolved · finding [fixed] · resolves p3-r8: the status line described the TUI's launch directory, not the session whose footer it renders (phase 3)

render now resolves its directory per session id via context.data.session.get(id) ->
location.directory, cached per session, with the launch directory as the fallback for the home
screen and a not-yet-loaded session; one coalesced reader per session id, never a process per
render. The README and the record's decision (p3-segment-uses-cwd-not-session, edited in place
because it had not been journalled yet) state the final behaviour. Proven by unit tests against
the API's declared types; a session from ANOTHER project rendering its own repo remains owed to
the post-merge walk, and the record says so.

<!-- fr:journal kind=finding scope=plan id=p3-r9-resolved created=2026-10-20T10:44:55+00:00 phase=3 state=fixed resolves=p3-r9 -->
### p3-r9-resolved · finding [fixed] · resolves p3-r9: "src/tui/index.tsx is the only file outside tsc" was true but unenforced: the exclusion was a glob (phase 3)

tsconfig.json excludes exactly "src/tui/index.tsx", and test/tsconfig.test.ts asserts the exclude
list is that one path, so a second excluded file has to be argued for in a diff.

<!-- fr:journal kind=finding scope=plan id=p3-r10-resolved created=2026-10-20T10:44:55+00:00 phase=3 state=fixed resolves=p3-r10 -->
### p3-r10-resolved · finding [fixed] · resolves p3-r10: evidence.tests pointed at a suite log that predates the commit which changed the live test it is cited for (phase 3)

evidence.tests re-pointed at the post-fix full suite (13026 passed, 108 skipped, exit=0) run after
the last code commit, and the record now states the live run's measured 34.8s end to end rather
than the pre-fix 33.8s.

<!-- fr:journal kind=discovery scope=plan id=p4-store-shape-measured created=2026-10-21T08:31:35+00:00 phase=4 -->
### p4-store-shape-measured · discovery · OpenCode 2.1.0 store measured from a read-only copy: session_v2/session_message shape, and where it differs from spec §C (phase 4)

Measured 2026-10-20 on a read-only COPY of a live OpenCode 2.1.0 opencode.db (copy deleted after; no identity recorded).
Tables: session_v2 (id, project_id, parent_id, slug, directory, title, version, cost, tokens_*, agent, model,
time_created/updated/…, plus 2.x-only fork_session_id, fork_boundary, time_suspended, resume_attempts, time_idle,
time_viewed, idle_outcome); session_message (id, session_id, type, seq, time_created, time_updated, data; unique
(session_id, seq), seq not contiguous). Legacy session/message/part keep their 1.x DDL.
Differences from spec §C/§D, all coded to the measurement:
1. The role is the ROW's `type` column (assistant|user|system|synthetic|compaction|idle), not data.role.
2. A tool item carries its times on the ITEM, not in state: {type:"tool", id, name, time:{created, ran?, completed?},
   state:{status, input, metadata, content:[{type:"text", text}], error?}, executed?}. `time.ran` is present only
   when the call ran. fr reads began = time.ran, else time.created, else the message's; ended = time.completed.
3. Output is state.content[].text; shell/bash exit is state.metadata.exit (as §C). Migrated bash items also keep
   metadata.output.
4. 2.x dispatch is `subagent`: metadata {sessionID (capital ID), status}, input {agent, description, prompt,
   sessionID?}; there is NO parentSessionId — the parent is the session whose message carries the item.
   Migrated 1.x `task` items keep metadata {sessionId, parentSessionId}, input.subagent_type. Both are read.
5. data.cost is sometimes an integer (0); data.model is {id, providerID, variant}; data.time is {created, completed?}.
6. skill input is {name} in most rows; {id} also occurs (p2-v2-tool-inputs saw only {id}).
7. Context says the legacy tables "receive nothing" and part has 0 rows: on this store the legacy tables still HOLD
   the historical 1.x rows (every one also present in session_v2) — frozen, not empty. Only new 2.x sessions are
   absent from them. v1-only (a legacy row with no session_v2 row) did not occur on this store, which is why the
   fixture builds it.
8. Migrated history in session_message keeps 1.x tool names (bash, task) alongside 2.x ones (shell, subagent).

<!-- fr:journal kind=decision scope=plan id=p4-one-adapter-and-alias-table created=2026-10-21T08:31:35+00:00 phase=4 -->
### p4-one-adapter-and-alias-table · decision · fr.run.opencode_store is the one adapter; TOOL_ALIASES (bash->shell, task->subagent) is the one alias list (phase 4)

packages/fr/src/fr/run/opencode_store.py holds store_version (the R14 probe), open_ro/query, the SQL for every
query site (session probe, children, root walk, per-session messages, top-level messages + activity probe since a
time, the usage tree), StoredMessage/ToolItem and the dispatch accessors. fr.run.observed and
fr.usage.readers.opencode import it (open_ro is re-exported for the hermes reader). Readers compare against
canonical 2.x names; the usage classifier gained `shell`->Bash and `subagent`->Agent beside its existing
multi-harness names. test_usage_opencode_store_agreement.py proves both readers see the same tool calls, the
same child and the same 1.x reason on the fixture.

<!-- fr:journal kind=decision scope=plan id=p4-probe-answers-and-wording created=2026-10-21T08:31:35+00:00 phase=4 -->
### p4-probe-answers-and-wording · decision · The four probe answers and how each is worded (phase 4)

store_version(db, sid): unreadable = open/query fails, or the file has neither session_v2 nor session;
v2 = a session_v2 row; v1-only = no session_v2 row but a legacy session row (also when session_v2 is missing,
i.e. a 1.x store — reported per session, never as a preflight); absent = neither.
observed_session returns None for absent and v1-only (unreadable keeps a view whose methods are all None).
why_unobservable (after walking the root): v1-only -> "...cannot have its <what> read: it is an OpenCode 1.x session
(present only in the legacy `session` table) — upgrade opencode; super-fr supports 2.0 only" (no FR_OPENCODE_DB);
unreadable -> names the database path that could not be read + check FR_OPENCODE_DB / XDG_DATA_HOME;
absent -> today's "not in the OpenCode database fr read … check FR_OPENCODE_DB / XDG_DATA_HOME";
no session id -> phase 1's OPENCODE_SESSION_ID wording, unchanged. The usage reader maps v1-only to
unavailable("session <id>: " + the same reason). The probe test is
tests/unit/test_run_observed_opencode_v2.py::test_a_session_is_probed_as_v2_v1_only_absent_or_unreadable.

<!-- fr:journal kind=decision scope=plan id=p4-v1-test-stores-folded-to-v2 created=2026-10-21T08:31:35+00:00 phase=4 -->
### p4-v1-test-stores-folded-to-v2 · decision · Existing 1.x-shaped test stores are folded into 2.x tables by tests/unit/opencode_v2.to_v2; the 1.x files are untouched (phase 4)

~10 test modules built or mutated 1.x session/message/part rows. Rather than rewrite each, tests/unit/opencode_v2.py
folds a 1.x store into session_v2/session_message the way the measured migration did (parts into data.content[],
1.x tool names kept, part state.time.start/end -> item time.created/ran/completed, output -> state.content[].text,
message role -> row type, modelID/providerID -> data.model). opencode_fixture.DB is now that 2.x copy (V1_DB the
original); shifted/with_copied_child/with_resumed_child and the in-test mutations re-fold after editing. Their
assertions are unchanged except the usage tool name `bash` -> `shell` (the alias). This fold is a construction,
not a capture: it encodes the measured migration, and two-sessions.db (built to the captured DDL) is the
independent pin. tests/fixtures/usage/opencode/ and its builder are untouched and now prove the 1.x refusal
(test_opencode_1x_only_session_is_unavailable_naming_1x_and_the_upgrade).

<!-- fr:journal kind=discovery scope=plan id=p4-scenario-output created=2026-10-21T08:31:35+00:00 phase=4 -->
### p4-scenario-output · discovery · tests/scenarios/opencode-store-v2.sh passes against the candidate install (phase 4)

Candidate-installed fr, HOME in a temp dir, store = a copy of two-sessions.db: `fr usage collect` reports
"collected 2 session(s), 1 unavailable"; `fr usage report` shows ses_v2demo at $0.01 exact on example-model and
ses_v1only `—` with the 1.x/upgrade note; `fr run advance` on an operator gate prints no notice for the 2.x session
and the R14 wording (not FR_OPENCODE_DB) for the 1.x one; `fr run status` reads the cursor. Registered in
tests/integration/test_scenarios.py (test_opencode_store_v2 + the every-script list); that module: 50 passed.

<!-- fr:journal kind=discovery scope=plan id=p4-full-suite-first-run created=2026-10-21T08:31:35+00:00 phase=4 -->
### p4-full-suite-first-run · discovery · The first full suite found three cost-table tests still reading the 1.x fixture for data; fixed before the evidence run (phase 4)

tests/unit/test_run_cost_cmd.py pointed FR_OPENCODE_DB at tests/fixtures/usage/opencode/opencode.db (1.x) and
expected figures; now refused as 1.x, they failed (3 failed, 13043 passed). Pointed at opencode_fixture.DB (the
2.x fold), commit b40821dba; the evidence run is 13046 passed, 108 skipped, exit=0.

<!-- fr:journal kind=finding scope=plan id=p4-compaction-tokens-uncounted created=2026-10-21T08:31:35+00:00 phase=4 state=open review_scope=out -->
### p4-compaction-tokens-uncounted · finding [open] (reviewer: out of scope) · OpenCode 2 `compaction` messages carry tokens (cost 0) that the usage reader does not count (phase 4)

Measured: every compaction row has data.tokens and data.cost 0 (none priced). The usage reader counts only
type == "assistant" rows, as the 1.x reader counted only role == "assistant". Dollars are unaffected (cost 0);
token totals undercount compaction work. Not in R13's field list; left as is.

<!-- fr:journal kind=finding scope=plan id=p4-r1 created=2026-10-21T08:31:35+00:00 phase=4 state=open review_scope=in -->
### p4-r1 · finding [open] (reviewer: in scope) · why_unobservable worded a healthy v2 session with the absent answer's FR_OPENCODE_DB sentence (phase 4)

Review: store_version == "v2" fell through to "not in the OpenCode database … check FR_OPENCODE_DB", printed on
the operator-gate refusal whenever a healthy 2.x session shows no observed question/dispatch/command.

<!-- fr:journal kind=finding scope=plan id=p4-r2 created=2026-10-21T08:31:35+00:00 phase=4 state=open review_scope=in -->
### p4-r2 · finding [open] (reviewer: in scope) · an unparseable session_message.data row became {} and the usage figure stayed `exact` (phase 4)

Review: opencode_store.loads swallowed JSONDecodeError into {}; one corrupt row lowered cost with source exact and
unavailable None, and dropped that row's tool calls and tokens.

<!-- fr:journal kind=finding scope=plan id=p4-r3 created=2026-10-21T08:31:35+00:00 phase=4 state=open review_scope=in -->
### p4-r3 · finding [open] (reviewer: in scope) · two alias tables and two canonical_tool functions, mapping bash to different targets, both claiming to be the only one (phase 4)

Review: opencode_store.TOOL_ALIASES/canonical_tool (bash->shell) and usage.classify.canonical_tool (bash->Bash),
each docstring claiming the ONE table.

<!-- fr:journal kind=finding scope=plan id=p4-r4 created=2026-10-21T08:31:35+00:00 phase=4 state=open review_scope=out -->
### p4-r4 · finding [open] (reviewer: out of scope) · spec §D's field mapping did not record the measured shape (role = session_message.type column, row time beside item time.*) (phase 4)

Review: the spec still described data.role and per-state times; the measured divergences are in p4-store-shape-measured.

<!-- fr:journal kind=finding scope=plan id=p4-r5 created=2026-10-21T08:31:35+00:00 phase=4 state=open review_scope=in -->
### p4-r5 · finding [open] (reviewer: in scope) · the store fixture was built, not captured, against R13's 'migrated V1 rows taken from a real store' (phase 4)

Review: DDL verbatim from a live store, rows constructed — the reader was pinned against its author's own mapping.

<!-- fr:journal kind=decision scope=plan id=p4-r2-degradation created=2026-10-21T08:31:35+00:00 phase=4 -->
### p4-r2-degradation · decision · An unreadable message row makes the usage record unavailable (naming the row) and the observation None (phase 4)

opencode_store.parse_data returns None for data that is not a JSON object; StoredMessage carries unreadable=True
(data {} only so read-around code cannot crash). The usage reader returns unavailable("OpenCode message row(s)
<ids> have unreadable data, so the session's cost, tokens and tool calls cannot be read whole"); observed._messages
returns None, so every gate reads the session as unobservable. Chosen over an `estimated`-labelled partial sum:
the missing row's cost, tokens AND tool calls are unknown, a partial figure would still be attributed across
activities as if whole, and R14 says never a figure that hides what could not be read. A value that does not even
decode as UTF-8 (CAST(x'fffe' AS TEXT)) fails inside sqlite's fetch and was already unavailable via the
sqlite3.Error path; the case that silently passed is valid text that is not JSON ('{not json', '[]').

<!-- fr:journal kind=discovery scope=plan id=p4-migrated-session-captured created=2026-10-21T08:31:35+00:00 phase=4 -->
### p4-migrated-session-captured · discovery · A real migrated 1.x session read whole by the 2.x readers; captured, redacted, into the fixture (phase 4)

Read-only COPY of the live 2.1.0 store (2026-10-20): 242 session_v2 rows, 229 also in the legacy session table
(versions 1.17.x-1.19.x migrated; 2.0.x/2.1.0 native). session_message types: assistant, user, system, synthetic,
compaction, idle. 145 rows carry migrated task metadata (sessionId/parentSessionId). One small migrated session
(four rows: user, assistant, assistant, system; two 1.x `bash` items; an assistant row with error.type aborted and
integer cost 0; tool items with providerState and a reasoning item with state.signature; message rows' time_updated
past data.time.completed) is now tests/fixtures/opencode/migrated-1x-session.json, ids/text/model/absolute times
redacted and figures rounded to two significant digits. The usage reader reads it whole (cost exact, both calls as
shell) — test_a_captured_migrated_1x_session_reads_whole. The capture holds no migrated `task` item; a migrated
dispatch is still pinned only by the constructed fold.

<!-- fr:journal kind=discovery scope=plan id=p4-full-suite-flake-is-the-install-locks-60s-bound created=2026-10-21T08:31:35+00:00 phase=4 -->
### p4-full-suite-flake-is-the-install-locks-60s-bound · discovery · A full-suite re-run at HEAD failed two install-lock tests at their hard 60s bound; serially they pass, and the branch does not touch them (phase 4)

Re-running the whole suite (to produce a log this session could itself be credited with) gave
2 failed, 13049 passed: both were tests/integration/test_install_atomic.py lock-reclaim tests,
each timing out at `p.communicate(timeout=60)` after the sandbox install had printed normally
past its marketplace step. They predate this branch (#1088/#946) and this branch touches neither
them nor the lock; run alone the file is 8 passed in 70s (~9s per sandbox). They are the last two
of their class, i.e. they run after the file's other installs have saturated the disk, and this
host was also running two busy OpenCode sessions. Filed as #1223 with the reproduction shape and
the observation that the file's process tree burns ~85% of a core in SYSTEM time while its tests
finish in 67s — a possible busy-wait worth its own look.

So the evidence below is a targeted run this session wrote, plus the full suite the phase's own
executor ran after the last code commit (13051 passed, exit=0, its log named in that commit's
record body); a single full-suite run at the final HEAD is owed before the PR, and it is what the
deliver step will read.

<!-- fr:journal kind=finding scope=plan id=p4-r1-resolved created=2026-10-21T08:31:35+00:00 phase=4 state=fixed resolves=p4-r1 -->
### p4-r1-resolved · finding [fixed] · resolves p4-r1: why_unobservable worded a healthy v2 session with the absent answer's FR_OPENCODE_DB sentence (phase 4)

packages/fr/src/fr/run/observed.py why_unobservable: a `v2` branch — "the session your harness (opencode) exported
in <key> (<sid>) was read, and it holds no <what> yet", no FR_OPENCODE_DB pointer. Test
tests/unit/test_run_observed_opencode_v2.py::test_each_of_the_four_answers_words_itself (four distinct sentences).

<!-- fr:journal kind=finding scope=plan id=p4-r2-resolved created=2026-10-21T08:31:35+00:00 phase=4 state=fixed resolves=p4-r2 -->
### p4-r2-resolved · finding [fixed] · resolves p4-r2: an unparseable session_message.data row became {} and the usage figure stayed `exact` (phase 4)

opencode_store.parse_data + StoredMessage.unreadable; usage reader -> unavailable naming the row; observed._messages
-> None (decision p4-r2-degradation). Tests: test_opencode_an_unparseable_message_row_is_unavailable_naming_it,
the tightened test_opencode_one_bad_row_is_unavailable_or_tolerated_never_a_crash (a tolerated row must keep the
healthy figure and source), test_an_unparseable_message_row_makes_the_session_unobservable.

<!-- fr:journal kind=finding scope=plan id=p4-r3-resolved created=2026-10-21T08:31:35+00:00 phase=4 state=fixed resolves=p4-r3 -->
### p4-r3-resolved · finding [fixed] · resolves p4-r3: two alias tables and two canonical_tool functions, mapping bash to different targets, both claiming to be the only one (phase 4)

opencode_store.TOOL_ALIASES/canonical_tool -> STORE_TOOL_ALIASES/store_tool_name (+ STORE_TOOLS), docstrings say
which job each table does; classify gains `question` -> AskUserQuestion so every store name is a classify key.
Test test_every_store_tool_name_is_known_to_the_activity_vocabulary.

<!-- fr:journal kind=finding scope=plan id=p4-r4-resolved created=2026-10-21T08:31:35+00:00 phase=4 state=fixed resolves=p4-r4 -->
### p4-r4-resolved · finding [fixed] · resolves p4-r4: spec §D's field mapping did not record the measured shape (role = session_message.type column, row time beside item time.*) (phase 4)

Fixed by the orchestrator: spec §D's field mapping now records the role as the session_message.type column, the
row's time_created beside per-item time.*, and the other measured divergences. Committed with p4-r1's commit.

<!-- fr:journal kind=finding scope=plan id=p4-r5-resolved created=2026-10-21T08:31:35+00:00 phase=4 state=fixed resolves=p4-r5 -->
### p4-r5-resolved · finding [fixed] · resolves p4-r5: the store fixture was built, not captured, against R13's 'migrated V1 rows taken from a real store' (phase 4)

Captured route: one real migrated 1.x session's message rows, redacted, in
tests/fixtures/opencode/migrated-1x-session.json, loaded by build.py as ses_v1migrated; README states exactly
what is captured and what is constructed (session rows, the other three sessions). R13's sentence now holds as
written for the message rows; a migrated `task` dispatch is not in the capture (p4-migrated-session-captured).

<!-- fr:journal kind=finding scope=plan id=p4-compaction-tokens-uncounted-resolved created=2026-10-21T08:31:35+00:00 phase=4 state=open resolves=p4-compaction-tokens-uncounted tracked_by=derio-net/super-fr#1222 -->
### p4-compaction-tokens-uncounted-resolved · finding [deferred → derio-net/super-fr#1222] · resolves p4-compaction-tokens-uncounted: OpenCode 2 `compaction` messages carry tokens (cost 0) that the usage reader does not count (phase 4)

Out of scope for phase 4. Tracked by derio-net/super-fr#1222, the issue being filed for it; if the filed number
differs the orchestrator corrects it here.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t1 created=2026-10-21T08:31:35+00:00 phase=4 -->
### no-refactor-p4-t1 · discovery · no-refactor-because P4.T1 (phase 4)

The fixture builder and its pinning test are new and single-purpose; the one candidate for sharing (the 1.x builder in tests/fixtures/usage/opencode/) must stay untouched as the 1.x refusal evidence, so there was nothing to merge.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p4-t2 created=2026-10-21T08:31:35+00:00 phase=4 -->
### no-refactor-p4-t2 · discovery · no-refactor-because P4.T2 (phase 4)

The adapter was extracted before the reader moved (P4.T3.S3 done first, deliberately): observed.py's ToolPart/tool_part/_final_text JSON handling went into fr.run.opencode_store, leaving observed with queries by name only; nothing further to clean in the observed reader.

<!-- fr:journal kind=review scope=plan id=p4-review created=2026-10-21T08:44:29+00:00 phase=4 -->
### p4-review · review · Phase 4 reviewed by an independent agent: two majors, one of them a silent money bug, found by driving a throwaway store (phase 4)

Reviewer: ses_ea6d1b71fffepKaui9YJGoGmGf (general agent, read-only, its own context). It ran
the opencode/usage modules (88 passed), the scenarios (50 passed in 194s), mypy (302 files),
ruff, and grep'd every legacy query site: exactly one `FROM session` hit remains, in the R14
detection, so "every query site moved" held. It checked the record's evidence log against the
commit times (suite born the same second as the last code commit) rather than accepting it.

Then it did the thing that found the defects: it built its own throwaway stores and BROKE them
one way at a time — a corrupt `data` blob, `session_v2` dropped, `session_v2` renamed, a column
renamed, a zero-byte file, a session only in `session`, a session in both — and drove the probe,
`why_unobservable` and `fr usage collect` against each. Two majors fell out of that matrix:
a healthy 2.x session was told its database was wrong (the fall-through to the absent sentence),
and one corrupt `session_message.data` row silently turned 0.0143 into 0.002 labelled `exact` —
a wrong dollar figure indistinguishable from a measured one, which is precisely the class R14
forbids. Neither was reachable from the record's own tests, and both are on the routine path.

It also found a second alias table this phase had created while editing the first (both
docstrings claiming to be the only one, mapping `bash` to different targets), and that the
fixture's provenance did not match what R13 promised: the rows were authored to the same mapping
the reader encodes, so the "migration lost nothing" pin proved only self-consistency.

Everything is closed: the two majors by code plus a degradation test, the alias tables by one
name per job plus a test tying store names to the activity vocabulary, the provenance by
capturing ONE real migrated 1.x row set (redacted) from a copy of the store and labelling
exactly what is captured versus constructed, and §D by naming the role COLUMN.
The reviewer opened no finding this phase could not fix; its one out-of-scope item (§D) was
corrected anyway, because the spec is what phases 5 and 6 read.

<!-- fr:journal kind=review scope=plan id=p4-review-verify created=2026-10-21T08:44:29+00:00 phase=4 -->
### p4-review-verify · review · Verification round on the fixes: all five hold when driven, and three residuals closed (phase 4)

Reviewer: ses_ea2696a16ffefTjW5oEKjXk42Y (general agent, read-only, its own context,
dispatched after the fixes because the fixes were written by a different agent than the one
that found the defects). It re-drove each claim instead of reading the resolve text:

- r1: four stores (healthy v2 with no matching call, fixture session, v1-only, zero-byte,
  missing) each produced a distinct sentence; the v2 one carries no `FR_OPENCODE_DB`. Held.
- r2: one row corrupted five ways (`CAST(x'fffe' AS TEXT)`, `'{not json'`, `'[]'`, a child row,
  a user row) — every case became `usd=None, source=none` or `unavailable` naming the rows, with
  `—`/`none` rendered and `fr usage collect` exiting 0. No silent `exact` figure survives. Held.
- r3: one table per job, neither docstring overclaims, and the new test FAILS when a store tool
  name with no activity mapping is injected (`'webfetch'`). Held.
- r5: README's CAPTURED/CONSTRUCTED split matches `build.py` and the JSON; the committed `.db`
  holds only `/home/u/…`, `example-model`, `example-provider` and `redacted text`, is
  `VACUUM`ed (no stale pages) and exists in exactly one commit, never unredacted. Held.
- regression risk: a store path that is a directory, a zero-byte file, a missing file and a
  dropped column raised in `why_unobservable` in no case.

All five fixes hold (283 passed, mypy clean, ruff clean). The round produced three residuals,
all closed in this phase: the v2 sentence and the unreadable observation contradicted each other
(a corrupt row printed the identical "was read, holds nothing" sentence — the very reassurance
r2 exists to prevent), one assertion in the new r3 test could never fail (an Activity compared
to a sub), and the "no real identity" test asserted directories only.

<!-- fr:journal kind=finding scope=plan id=p4b-r1 created=2026-10-21T08:44:29+00:00 phase=4 state=open review_scope=in -->
### p4b-r1 · finding [open] (reviewer: in scope) · a v2 session whose rows could not be decoded was told "was read, and it holds no questions yet" — identical to a healthy store (phase 4)

packages/fr/src/fr/run/observed.py, the v2 branch of `why_unobservable`: it decided from
`store_version` alone, which says WHERE the session lives, not whether its messages can be read.
Measured on a copy of the fixture with `UPDATE session_message SET data = '{not json' WHERE
id = 'msg_a1'` (the row carrying the answered question): the sentence was byte-identical to the
healthy store's. Same for a store whose `session_message` table was dropped — `store_version`
still answers `v2`, `_messages` returns None, and the operator is told the store was read and
holds nothing. This is the routine operator-gate refusal path (commands/run_cmd.py), and it
composes badly with p4-r2: that fix makes such a session unobservable precisely so no gate reads
it as "found nothing", and this sentence then asserts it was read and found nothing.

<!-- fr:journal kind=finding scope=plan id=p4b-r2 created=2026-10-21T08:44:29+00:00 phase=4 state=open review_scope=in -->
### p4b-r2 · finding [open] (reviewer: in scope) · one assertion in the new alias test can never fail: an Activity compared to a sub (phase 4)

tests/unit/test_run_observed_opencode_v2.py,
`classify.classify("shell", "ls").activity != "other_tool"`: `Classification.activity` is one of
paperwork/implementation/other while `other_tool` is a `sub`, so the comparison was True for every
input, including a completely unknown tool name. The test's real pin (membership in
`classify._ALIASES`) does work — injecting `webfetch` fails it — but the line read as a check on
the unknown bucket and checked nothing.

<!-- fr:journal kind=finding scope=plan id=p4b-r3 created=2026-10-21T08:44:29+00:00 phase=4 state=open review_scope=in -->
### p4b-r3 · finding [open] (reviewer: in scope) · the fixture's "no real identity" test asserted directories only (phase 4)

tests/unit/test_opencode_store_fixture.py asserted `directory.startswith("/home/u/")` and nothing
else, so a real title, slug, prompt, command, output, model id or provider could be committed into
tests/fixtures/opencode/two-sessions.db and the test stayed green — in the one file where a leak
would land, in a public repo. The fixture is clean today (the verification round dumped every row
and ran `strings` over the file), so this was a claim wider than its evidence, not a live leak.

<!-- fr:journal kind=finding scope=plan id=p4b-r1-resolved created=2026-10-21T08:44:29+00:00 phase=4 state=fixed resolves=p4b-r1 -->
### p4b-r1-resolved · finding [fixed] · resolves p4b-r1: a v2 session whose rows could not be decoded was told "was read, and it holds no questions yet" — identical to a healthy store (phase 4)

`opencode_store.rows_state(db, session)` is now the one readability probe ("ok" / "partial" /
"unreadable"), and `why_unobservable`'s v2 branch asks it before it speaks: a session whose rows
could not be decoded says so and says fr "cannot say whether it holds <what>", and a store whose
`session_message` cannot be queried says "its message rows could not be read". Neither points at
`FR_OPENCODE_DB` (the database was found and read). Tested in
test_a_v2_store_fr_could_not_decode_is_never_described_as_read_and_empty, which corrupts one row
and, separately, drops the table, and asserts the three sentences are distinct.

<!-- fr:journal kind=finding scope=plan id=p4b-r2-resolved created=2026-10-21T08:44:29+00:00 phase=4 state=fixed resolves=p4b-r2 -->
### p4b-r2-resolved · finding [fixed] · resolves p4b-r2: one assertion in the new alias test can never fail: an Activity compared to a sub (phase 4)

The vacuous line (`classify.classify("shell", "ls").activity != "other_tool"` — `other_tool` is a
`sub`) is replaced by the assertion it meant: a known store name does not land in the unknown
sub, and `classify("totally-unknown-tool").sub == "other_tool"`.

<!-- fr:journal kind=finding scope=plan id=p4b-r3-resolved created=2026-10-21T08:44:29+00:00 phase=4 state=fixed resolves=p4b-r3 -->
### p4b-r3-resolved · finding [fixed] · resolves p4b-r3: the fixture's "no real identity" test asserted directories only (phase 4)

test_the_fixture_carries_no_real_identity now reads every text value in every table and asserts
each absolute path is under `/home/u/`, each URL host is a reserved name (RFC 2606: `.invalid`,
`.example`, `.test`, `.localhost`, `example.{com,org,net}`) and each email domain likewise. The
scan is pinned non-vacuous (`assert values`) and was checked against synthetic leaks: a
`/Users/x/proj` path, a `gitlab.corp.example` host and a `realcompany.io` mail are each caught.

<!-- fr:journal kind=decision scope=plan id=p5-parity-gates-enforced created=2026-10-21T10:50:53+00:00 phase=5 -->
### p5-parity-gates-enforced · decision · parity: OpenCode edit gate partial→enforced, shell gate (fr-isolation-guard) absent→enforced, push guard absent→enforced (phase 5)

check.py maps both enforced and partial to an observed `present`, so the state is a judgement.
All three throw from `execute.before` on a violating call, which is what Claude Code's enforced
cells mean. Evidence: the edit gate in index.test.ts/marker.test.ts and the delivered copy
refusing a base-clone edit inside the real 2.x binary (test_opencode_runs_the_delivered_gate,
CI on 2.0.32 and 2.1.0); the shell gate through the captured verdict table run against both
engines; the push guard through push.test.ts, which compares commands against the real
script. Each scope note says the model-driven walk is still owed after merge. New markers sit
on the handler module each one credits: guard.ts, push.ts, nag.ts, sentinel.ts, bind.ts (bind
and unbind).

<!-- fr:journal kind=decision scope=plan id=p5-parity-advisory-not-inflated created=2026-10-21T10:50:53+00:00 phase=5 -->
### p5-parity-advisory-not-inflated · decision · parity: nag absent→partial, sentinel absent→partial, bind and unbind absent→partial (the plan said enforced); pin and idle stay partial with notes rewritten (phase 5)

The nag cannot be `advisory`: check.py expects `advisory` to observe `absent`, and the nag
carries a marker. It is `partial`, because the evidence comes only from a fake context; the
live reach is Test Plan item 6. The plan asked for sentinel and bind/unbind `enforced`. I
declared them `partial` instead. execute.after firing for a live skill call, and
session.deleted arriving, were never observed live (p2-not-proven-live), and bind is
best-effort by design. The pin note now names create.before and cites the live echo from
p1-v2-hook-order-measured. The idle note now names ctx.event.subscribe/ctx.session.prompt in
place of the 1.x SDK endpoint. I also corrected interaction notes that named 1.x mechanics:
deliver-tests-provenance (shell items, OPENCODE_SESSION_ID), spec-review-independence
(subagent), run-session-identity (1.x refused by name), visual-evidence (shell),
dispatch-holder-identity (observed on 1.x, not re-observed on 2.x). The status-line cell
stays `partial` and its note is unchanged.

<!-- fr:journal kind=decision scope=plan id=p5-matrix-ci-rows created=2026-10-21T10:50:53+00:00 phase=5 -->
### p5-matrix-ci-rows · decision · matrix → ci: opencode-2-plugin-loads, store-read, v1-refusal, push-guard, claim, pin, nag, sentinel, bind-unbind; opencode-run-session and opencode-isolation-enforcement re-pointed (stay ci) (phase 5)

plugin-loads: plugin.test.ts and wiring.test.ts, plus int refs to
test_opencode_registers_the_delivered_plugin_exactly_once and
test_opencode_runs_the_delivered_gate. store-read: test_a_2x_session_is_observed_end_to_end,
test_both_readers_see_the_same_tool_calls_of_a_2x_session, int test_scenarios.py#test_opencode_store_v2.
v1-refusal: test_a_1x_only_session_is_refused_naming_1x_and_the_upgrade,
test_opencode_1x_only_session_is_unavailable_naming_1x_and_the_upgrade,
test_both_readers_refuse_a_1x_session_with_the_same_reason, plus the scenario. The plugin rows
cite their bun test file (push/claim/pin/nag/sentinel/bind .test.ts); sentinel also cites the
two test_sentinel_lifecycle.py OpenCode-writer tests. opencode-run-session: removed the
session.test.ts ref, added test_a_session_is_probed_as_v2_v1_only_absent_or_unreadable, and
rewrote the note and the acceptance text, which had said "the plugin hands fr the session id".
opencode-isolation-enforcement: rewrote the note (the 1.18.32 sessions were on 1.x, now
unsupported) and added int test_opencode_runs_the_delivered_gate.

<!-- fr:journal kind=decision scope=plan id=p5-matrix-walk-owed-rows created=2026-10-21T10:50:53+00:00 phase=5 -->
### p5-matrix-walk-owed-rows · decision · matrix → walk-owed: opencode-2-edit-gate, bash-gate, session-export, idle-nudge, status-line (verify: live, Test Plan items 1-5) (phase 5)

Each row cites the CI evidence for its half that does not need a model (index/marker,
guard-verdicts with test_the_verdict_table_covers_what_the_spec_names, idle.test.ts,
segment.test.ts with the live TUI test, and the session-id reader tests
test_current_session_reads_the_key_its_harness_owns, test_a_child_id_walks_to_its_2x_root,
test_no_session_id_names_opencode_session_id). The model-driven half is post-merge at the
Tester gate. opencode-2-session-export's acceptance named FR_OPENCODE_SESSION_ID, an export
R6 removed. It now names OPENCODE_SESSION_ID, which OpenCode sets itself. The text was edited
by hand, string only, because set-status cannot edit acceptance text; the reports were
regenerated by the CLI.

<!-- fr:journal kind=finding scope=plan id=p5-plugin-scenario-missing created=2026-10-21T10:50:53+00:00 phase=5 state=open review_scope=in -->
### p5-plugin-scenario-missing · finding [open] (reviewer: in scope) · Six matrix rows name scenario tests/scenarios/opencode-plugin-v2.sh, which was never written (phase 5)

opencode-2-push-guard, claim, pin, nag, sentinel and bind-unbind each carry
`scenario: tests/scenarios/opencode-plugin-v2.sh`, from spec review. The file does not exist,
and `fr acceptance check` does not flag it. The rows are `ci` on their bun tests, which run in
CI's opencode-plugin-test job and drive the handlers with a fake context. That is exactly the
spec's candidate item 4. But a `fr verification walk` that reads the rows' scenario would find
no script. Two ways to close it: write the scenario (outside this phase's files), or move the
rows' scenario off it (set-status can replace a scenario but cannot clear one). Each row's
note says so.

<!-- fr:journal kind=discovery scope=plan id=p5-suite-evidence-is-two-parts created=2026-10-21T10:50:53+00:00 phase=5 -->
### p5-suite-evidence-is-two-parts · discovery · The suite is green only as two parts on this host: -n auto busts two pre-existing install-lock bounds (phase 5)

`pytest -n auto` over everything was run twice: both times 2 failed, 13051 passed, and both
failures were tests/integration/test_install_atomic.py's two lock-reclaim tests timing out at
their hard `communicate(timeout=60)` (they pass serially in ~70s for the whole file, and this
branch touches neither them nor the lock). Filed as #1223 with the reproduction shape. CI is
unlikely to hit it: it shards four ways, so each job runs a quarter of the suite; the flake
needs 12 concurrent sandboxed `install.sh` runs on one busy host.

So the evidence log is honest rather than lucky: part 1 is the whole suite minus that one file
under `-n auto` (13045 passed, exit=0), part 2 is that file alone, serially (8 passed, exit=0),
and the log carries both headers and both exit lines. Coverage is complete — 13053 tests, the
same count the red run covered — and the split is stated in the log, not hidden in a re-run.

<!-- fr:journal kind=decision scope=plan id=p5-plugin-scenario-written created=2026-10-21T10:50:53+00:00 phase=5 -->
### p5-plugin-scenario-written · decision · The scenario the six rows name now exists; it proves the delivery contract, not the hooks' enforcement (phase 5)

tests/scenarios/opencode-plugin-v2.sh was written and registered in
tests/integration/test_scenarios.py (both halves: the `here` registry tripwire and a
`test_opencode_plugin_v2` that runs it), so a `fr verification walk` reading
opencode-2-{push-guard,claim,pin,nag,sentinel,bind-unbind} finds a script instead of a dangling
path. What it proves is deliberately BOUNDED: the delivery contract every one of those hooks
rides on — install writes one plugin directory and nothing at top level, cli.json names the
DIRECTORY (a file path is silently ignored by 2.x), a second install is idempotent, a foreign
cli.json entry and key survive, an unparsable cli.json is refused with the file named and
nothing written, uninstall removes its own directory and entry only — plus, where the real
binary exists, exactly one `loading plugin` line for the delivered directory.

Why the enforcement proofs stay where they are: each hook's decision is compared against the
bash engine by a bun test with a fake context (push.test.ts, claim.test.ts, nag.test.ts,
sentinel.test.ts, bind.test.ts), which is what the rows' `ci` status rests on and what the
spec's candidate item 4 asks for. The load probe is conditional because the binary is not
present in every scenario container, and the script says so on stdout rather than passing
silently. The model-driven behaviour behind each hook is the post-merge live rows, per R15.

Two things measured while writing it, both now pinned in the script: the daemon logs
`loading plugin` about 150ms AFTER `opencode plugin list` returns, so a straight grep races the
load and reads zero (the script waits, bounded, for the line); and a survivor of that probe
inherits the runner's stdio, so the script always captures the service pid before
`service stop` and TERM/KILLs it afterwards. Verified: the script runs in 3.3s against the real
2.1.0 binary, prints the probe line, and leaves no `serve --service` process behind.

<!-- fr:journal kind=discovery scope=plan id=p5-prose-surfaces created=2026-10-21T10:50:53+00:00 phase=5 -->
### p5-prose-surfaces · discovery · Prose: the rule and its mirror, AGENTS.md, README.md and 01-fr-goal corrected; fr-isolation.html and index.html left as they are, because neither is false (phase 5)

fr-isolation.html describes only the Claude Code PreToolUse hook and makes no OpenCode or bash
claim. index.html has no harness text outside its base64. 01-fr-goal.md had two false
sentences: "the plugin hands the calling session's identifier" (now OpenCode does it itself)
and "an older plugin" (now an OpenCode 1.x session). Re-rendering the UNMODIFIED .md from /
with --isolated produced output byte-identical to the committed .html. The edited render then
changed exactly those lines. README line 427 ("third harness alongside Claude Code and
OpenCode") and line 346 are still true and were not changed.

<!-- fr:journal kind=finding scope=plan id=p5-plugin-scenario-missing-resolved created=2026-10-21T10:50:53+00:00 phase=5 state=fixed resolves=p5-plugin-scenario-missing -->
### p5-plugin-scenario-missing-resolved · finding [fixed] · resolves p5-plugin-scenario-missing: Six matrix rows name scenario tests/scenarios/opencode-plugin-v2.sh, which was never written (phase 5)

tests/scenarios/opencode-plugin-v2.sh exists, is executable, and is registered in
tests/integration/test_scenarios.py (`test_opencode_plugin_v2`, and the `here` set the
every-script-has-a-test tripwire reads). It covers the delivery contract all six rows ride on
and probes the real binary where present; the rows' notes were re-pointed through
`fr acceptance set-status` so none of them still claims the scenario was never written.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p5-t1 created=2026-10-21T10:50:53+00:00 phase=5 -->
### no-refactor-p5-t1 · discovery · no-refactor-because P5.T1 (phase 5)

Only declarations moved: five one-line parity markers and two stale comments in index.ts; the drift fixture in test_harness_check.py was re-pointed from fr-session-bind (now ported) to fr-worktree-create (still unported). Nothing to clean.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p5-t2 created=2026-10-21T10:50:53+00:00 phase=5 -->
### no-refactor-p5-t2 · discovery · no-refactor-because P5.T2 (phase 5)

Matrix moved through the CLI; two acceptance strings re-worded by hand because no verb edits them. No code.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p5-t3 created=2026-10-21T10:50:53+00:00 phase=5 -->
### no-refactor-p5-t3 · discovery · no-refactor-because P5.T3 (phase 5)

Prose and generated mirrors only.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p5-t4 created=2026-10-21T10:50:53+00:00 phase=5 -->
### no-refactor-p5-t4 · discovery · no-refactor-because P5.T4 (phase 5)

Fragment plus gates; no code.

<!-- fr:journal kind=finding scope=plan id=p5-r5 created=2026-10-21T13:55:53+00:00 phase=5 state=open review_scope=out -->
### p5-r5 · finding [open] (reviewer: out of scope) · The plugin README still names 1.x's /session/{id}/prompt_async as the idle-nudge transport (phase 5)

packages/fr-opencode-plugin/README.md's idle-guard section said the nudge is sent back "into the session (`/session/{id}/prompt_async`)". `src/idle.ts` sends it with `ctx.session.prompt`, per R5; the 1.x transport does not exist in 2.x. Outside the phase's declared `files:` (which name the root README, not the package's).
