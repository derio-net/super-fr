# Journal: 2026-10-02-opencode-observe-2

<!-- fr:journal kind=decision scope=plan id=p1-t2-t3-landed-together created=2026-10-02T19:49:54+00:00 phase=1 -->
### p1-t2-t3-landed-together · decision · The Claude Code and OpenCode backends landed in one commit (phase 1)

The salvaged telemetry.py hunks are interdependent: `run_session` calls
`observed.opencode_root`, `orchestrator_wrote_since` calls
`observed.opencode_unscoped`, and `answered_rounds_since` delegates through
`observed_session` to both backends. So both test files (T2.S1 and T3.S1)
were ported and seen RED against the stub first (27 failed), then observed.py
and the telemetry hunks went in together (T2.S2 + T3.S2) in one commit. The
ToolPart single-parse refactor (T3.S3) came over with the salvaged backend.

<!-- fr:journal kind=discovery scope=plan id=p1-wrote-since-replaces-orchestrator-wrote-in created=2026-10-02T19:49:54+00:00 phase=1 -->
### p1-wrote-since-replaces-orchestrator-wrote-in · discovery · main's wrote_since backs ClaudeCodeSession.wrote_windows, not the salvage's orchestrator_wrote_in (phase 1)

Since #837 branched, main split `orchestrator_wrote_since` into
`wrote_since(transcript, log, since, *, main_thread)` for the phase `tests=`
witness. The port kept main's function and dropped #837's
`orchestrator_wrote_in`; `ClaudeCodeSession.wrote_windows` passes its own
`main_thread`, so a child view (a subagent file, all sidechain) reads its
own writes — which is exactly what `_phase_log_windows` now needs through
`view.child(holder).wrote_windows(...)`.

<!-- fr:journal kind=decision scope=plan id=p1-gates-reach-observed-through-telemetry created=2026-10-02T19:49:54+00:00 phase=1 -->
### p1-gates-reach-observed-through-telemetry · decision · Operator and tests= gates reach fr.run.observed through the telemetry wrappers (phase 1)

`_gate_provenance` / `journal/operator.py` call `answered_rounds_since` /
`operator_answered_since`, and `_verify_tests_log` / `_wrote_before` call
`orchestrator_wrote_since`; each of those now resolves `observed_session`
internally (with the unscoped OpenCode fallback for tests=). Their call sites
were left as they are rather than duplicating that dispatch. `_verify_reviewer`
and `_phase_log_windows` call `observed_session` directly; no gate imports
`_this_session` any more.

<!-- fr:journal kind=discovery scope=plan id=p1-unobservable-wording-815 created=2026-10-02T19:49:54+00:00 phase=1 -->
### p1-unobservable-wording-815 · discovery · OpenCode's unobservable wording still names the gate's own noun (#815) (phase 1)

main's `_why_unobservable(what)` gained a noun argument (#815) after #837.
The ported OpenCode branch names the missing FR_OPENCODE_SESSION_ID export
(or the wrong database) and still carries `what`; Hermes keeps "fr has no
transcript reader for hermes's <what>". The #815 test was split: Hermes
keeps the exact wording, OpenCode gets its own test.

<!-- fr:journal kind=discovery scope=plan id=p1-findings-block-renamed created=2026-10-02T19:49:54+00:00 phase=1 -->
### p1-findings-block-renamed · discovery · Ported fixtures carry a review-findings block, not (phase 1)

The run tree's ses_gen1 return, the Claude Code handback fixture and the
observed tests use a fenced ```review-findings block (spec §E naming);
ses_rev returns a plain schema_version 7 YAML record with no
input-coverage block (#851).

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-10-02T19:49:54+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

Smoke task: a fixture addition beside main's rows and a stub module; the stub was replaced wholesale by the ported backends in Tasks 2-3, so there was nothing in it to clean.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-10-02T19:49:54+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

Each edit replaced a gate's reader in place with the session-protocol call (no duplicated logic left behind); _this_session is now imported by no gate (the T2.S3 refactor), so the wiring had nothing further to consolidate.

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-10-02T19:57:58+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · _open_dispatch dropped main's harness guard: an undetected harness records the stale CLAUDE_CODE_SESSION_ID (gh#537 regression; becomes R3 evidence) (phase 1)

run_cmd.py:3011 recorded run_session(os.environ) unconditionally; with detect_harness → None (mixed CLAUDECODE+OPENCODE env, pid not placeable) current_session (telemetry.py:436) falls back to Claude Code's key, so the inherited stale session was recorded and then counted as positive evidence by candidates(ambient=False). Spec §B: record only on a harness that OWNS its key. Untested because every test set FR_HARNESS.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-10-02T19:57:58+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · OpenCode backend reopens sqlite per query and loads unfiltered parts; run_session runs detect_harness twice (phase 1)

observed.py _parts/_children opened a second connection for _known on every call; _final_text decoded every part of each child to find its last text part; run_session detected the harness twice (each may run ps). Not quadratic, but megabytes of JSON per gate on a long session.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-10-02T19:57:58+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · session.ts assigns output.env[...] without ensuring env exists; a missing env object fails R1 invisibly (phase 1)

packages/fr-opencode-plugin/src/session.ts:30 — a binary handing over no env object raised a swallowed TypeError and the session was never exported.

<!-- fr:journal kind=review scope=plan id=review-p1 created=2026-10-02T19:57:58+00:00 phase=1 -->
### review-p1 · review · phase 1 independent code review: 3 findings (p1-r1 important, p1-r2/p1-r3 low), all in scope (phase 1)

Reviewer checked the seven focus areas (three-valued contract, run_session root walk and call sites, §C ambient threading with no caller left ambient, gates routed through the protocol with no Claude Code behaviour change, fixture added beside main's rows, plugin never throws / no parity marker, tests non-tautological) and found them correct apart from p1-r1, p1-r2, p1-r3. Received: each verified against the code; p1-r1 reproduced by a failing test first.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-10-02T19:57:58+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: _open_dispatch dropped main's harness guard: an undetected harness records the stale CLAUDE_CODE_SESSION_ID (gh#537 regression; becomes R3 evidence) (phase 1)

dc098745: _open_dispatch records run_session only when the detected harness is in SESSION_ID_ENVS (None otherwise, as main); test_advance_records_no_session_when_no_harness_owns_one (red first).

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-10-02T19:57:58+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: OpenCode backend reopens sqlite per query and loads unfiltered parts; run_session runs detect_harness twice (phase 1)

dc098745: _parts/_children ask _known only on an empty answer (one connection in the common case); _final_text filters text parts in SQL (json_valid/json_extract); run_session detects the harness once via _session_under.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-10-02T19:57:58+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: session.ts assigns output.env[...] without ensuring env exists; a missing env object fails R1 invisibly (phase 1)

dc098745: output.env ??= {} before assigning; bun test 'creates the env object when the output carries none' (red first).
