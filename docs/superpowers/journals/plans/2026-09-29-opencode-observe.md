# Journal: 2026-09-29-opencode-observe

<!-- fr:journal kind=discovery scope=plan id=p1-current-session-green-at-t2 created=2026-09-29T12:24:08+00:00 phase=1 -->
### p1-current-session-green-at-t2 · discovery · T4.S1's current_session, cost and ambient-binding tests were green before T4 began (phase 1)

The plan makes `current_session` harness-keyed in P1.T2.S2, and three of
P1.T4.S1's four tests — (a) `current_session` per harness with a stale
`CLAUDE_CODE_SESSION_ID`, (c) `fr run cost` printing real figures for an
OpenCode run (`tests/unit/test_run_cost_cmd.py::test_an_opencode_runs_own_session_fills_the_cost_table`)
and (d) the ambient workspace binding
(`tests/unit/test_run_cli.py::test_run_start_binds_the_ambient_opencode_session`)
— depend only on that change, so they passed when written. Only (b),
`advance` recording `session: ses_run` on an OpenCode attempt, was red, and
went green when `_open_attempt`'s `== ClaudeCodeReader.harness` guard was
dropped. With no harness detected `current_session` still reads the Claude
Code key (only Claude Code sets it); Hermes reads none.

<!-- fr:journal kind=discovery scope=plan id=p1-cc-agent-result-not-captured created=2026-09-29T12:24:08+00:00 phase=1 -->
### p1-cc-agent-result-not-captured · discovery · No captured transcript carries the parent-side tool_result of an Agent dispatch (phase 1)

`tests/fixtures/transcripts/` holds the dispatching `Agent` tool_use
(claude-code-session.jsonl line 7) but not its answer. P1.T2.S1 therefore
builds it with `tests/unit/transcript_sessions.py::agent_result_row`: the
captured `Bash` result record (claude-code-bash.jsonl line 1) re-keyed to the
dispatch's tool_use id, its content re-shaped to `[{type: text, text}]`, its
Bash-specific `toolUseResult` dropped. Recorded in
`claude-code-session.NOTE.md`. The shape is the one the plan states, not a
fresh capture.

<!-- fr:journal kind=finding scope=plan id=p1-cc-background-dispatch-returned created=2026-09-29T12:24:08+00:00 phase=1 state=open review_scope=in -->
### p1-cc-background-dispatch-returned · finding [open] (reviewer: in scope) · On Claude Code a background-dispatched agent's tool_result may be a launch ack, not its final message (phase 1)

`ChildDispatch.returned` on Claude Code is the text of the `tool_result`
answering the dispatch (spec §A), and that is what phase 1 implements. The
captured subagent meta carries `requestShape: background`, and for a
backgrounded `Bash` the tool_result is only a launch ack (`_is_launch_ack`);
if a background `Agent` dispatch behaves the same, `returned` is the ack and
phase 2's coverage/findings-block checks would refuse an honest reviewer.
Not captured, so not assumed either way. Phase 2 should capture one
background Agent result before it binds R5/R7 on Claude Code, and read the
completion notice when the tool_result is an ack.

<!-- fr:journal kind=decision scope=plan id=p1-gates-observe-opencode-early created=2026-09-29T12:24:08+00:00 phase=1 -->
### p1-gates-observe-opencode-early · decision · Routing the gates through the protocol makes OpenCode observed as soon as the plugin exports the session (phase 1)

`answered_rounds_since` (and so `_gate_provenance`, `operator_answered_since`
and `journal/operator.py`), `orchestrator_wrote_since` and
`_verify_reviewer` now read through `fr.run.observed.observed_session`. On
OpenCode WITHOUT `FR_OPENCODE_SESSION_ID` nothing changes (no view; the
`tests=` gate keeps its unscoped top-level reading). WITH it, the operator
gate and the reviewer id are observed from phase 1 on, before phase 2
(`agent_name` at the phase-executor refusal, still an exact `==` compare)
and phase 3 (OpenCode-neutral refusal wording, which still names
AskUserQuestion) land. The branch ships all three phases together, so no
release carries the intermediate state. `run/visual.py` reads the Claude
Code transcript through the protocol (`ClaudeCodeSession.transcript`), so
no gate imports `_this_session`; its OpenCode witness is phase 3.

<!-- fr:journal kind=decision scope=plan id=p1-shell-env-no-parity-marker created=2026-09-29T12:24:08+00:00 phase=1 -->
### p1-shell-env-no-parity-marker · decision · The shell.env export carries no super-fr-parity marker (phase 1)

`fr.harness.observe` derives OpenCode cells from `// super-fr-parity:
<script>` markers, each naming a hook script in plugins/super-fr/hooks/.
The `shell.env` export ports no hook script (Claude Code exports its own
session key natively), exactly like the child-session claim, so it gets a
comment in index.ts and no marker; `uv run fr harness parity --check` stays
green. Its `run-session-identity` row lands in phase 3.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-09-29T12:24:08+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

A fixture builder extension plus a protocol skeleton: the skeleton was replaced wholesale by Tasks 2-3, so there was nothing of its own to clean.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-09-29T12:24:08+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

Wiring only: one guard dropped in _open_attempt, three call sites switched to fr.run.observed, and a 30-line plugin handler. The duplication the routing could have left (the OpenCode wrote-reader in telemetry) was removed in P1.T3.S2, not left for a refactor.
