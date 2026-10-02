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
