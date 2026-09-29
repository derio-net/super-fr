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

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-09-29T12:50:02+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · _verify_reviewer on OpenCode refuses the tier-suffixed fr-spec-reviewer and accepts a tier-suffixed phase executor; agent_name() not wired (phase 1)

Raised by the independent phase-1 reviewer (a3295680faebbb9c4), tagged in scope. Verified by the orchestrator against the code before fixing.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-09-29T12:50:02+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · OpenCodeSession returns [] (not None) for a session absent from the database, so a wrong db (gh#740) gives false gate refusals (phase 1)

Raised by the independent phase-1 reviewer (a3295680faebbb9c4), tagged in scope. Verified by the orchestrator against the code before fixing.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-09-29T12:50:02+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · Claude Code ChildDispatch.returned is the launch ack for a backgrounded Agent dispatch; the child's SubagentHandback input.message is not read (phase 1)

Raised by the independent phase-1 reviewer (a3295680faebbb9c4), tagged in scope. Verified by the orchestrator against the code before fixing.

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-09-29T12:50:02+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · OpenCodeSession._final_text raises AttributeError on non-mapping part JSON (phase 1)

Raised by the independent phase-1 reviewer (a3295680faebbb9c4), tagged in scope. Verified by the orchestrator against the code before fixing.

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-09-29T12:50:02+00:00 phase=1 state=open review_scope=in -->
### p1-r5 · finding [open] (reviewer: in scope) · _why_unobservable and the _verify_reviewer docstring still say OpenCode has no reader (phase 1)

Raised by the independent phase-1 reviewer (a3295680faebbb9c4), tagged in scope. Verified by the orchestrator against the code before fixing.

<!-- fr:journal kind=finding scope=plan id=p1-r6 created=2026-09-29T12:50:02+00:00 phase=1 state=open review_scope=in -->
### p1-r6 · finding [open] (reviewer: in scope) · current_session returns the child id on OpenCode but the orchestrator id on Claude Code; raw callers (capture, binding, dispatched_from_this_session) do not walk to root (phase 1)

Raised by the independent phase-1 reviewer (a3295680faebbb9c4), tagged in scope. Verified by the orchestrator against the code before fixing.

<!-- fr:journal kind=finding scope=plan id=p1-r7 created=2026-09-29T12:50:02+00:00 phase=1 state=open review_scope=in -->
### p1-r7 · finding [open] (reviewer: in scope) · ClaudeCodeSession.dispatches parses the transcript twice (phase 1)

Raised by the independent phase-1 reviewer (a3295680faebbb9c4), tagged in scope. Verified by the orchestrator against the code before fixing.

<!-- fr:journal kind=review scope=plan id=review-p1 created=2026-09-29T12:50:02+00:00 phase=1 -->
### review-p1 · review · independent review of phase 1: 7 findings (2 Important, 5 Minor), all in scope, all fixed (phase 1)

Reviewer: general-purpose subagent a3295680faebbb9c4 (opus), range 8534cf0c..5be3581a, dispatched after review-phase phase/1 opened; superpowers:requesting-code-review then receiving-code-review. Verdict: 'With fixes'. Raised p1-r1..p1-r7 (the known executor finding p1-cc-background-dispatch-returned is p1-r3). Each was verified against the code by the orchestrator, then fixed test-first by the phase executor (6549e2a1, 430ad284, 2aa091c5, 4deac77a, 78cbbccc, 0ddebddc); full suite exit=0 (7542 passed).

```findings
p1-r1 | in | _verify_reviewer on OpenCode refuses the tier-suffixed fr-spec-reviewer and accepts a tier-suffixed phase executor; agent_name() not wired
p1-r2 | in | OpenCodeSession returns [] (not None) for a session absent from the database, so a wrong db (gh#740) gives false gate refusals
p1-r3 | in | Claude Code ChildDispatch.returned is the launch ack for a backgrounded Agent dispatch; the child's SubagentHandback input.message is not read
p1-r4 | in | OpenCodeSession._final_text raises AttributeError on non-mapping part JSON
p1-r5 | in | _why_unobservable and the _verify_reviewer docstring still say OpenCode has no reader
p1-r6 | in | current_session returns the child id on OpenCode but the orchestrator id on Claude Code; raw callers (capture, binding, dispatched_from_this_session) do not walk to root
p1-r7 | in | ClaudeCodeSession.dispatches parses the transcript twice
```

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-09-29T12:50:02+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: _verify_reviewer on OpenCode refuses the tier-suffixed fr-spec-reviewer and accepts a tier-suffixed phase executor; agent_name() not wired (phase 1)

Commit 2aa091c5. `_same_agent` in commands/run_cmd.py, the phase-executor
refusal in `_verify_reviewer` (now `_same_agent(observed.agent_type,
PHASE_EXECUTOR_AGENT)`) and `_same_agent` in run/visual.py all compare
through `fr.run.observed.agent_name`. Tests (resolve-level, on the
run-tree fixture moved to the unit's clock by tests/unit/opencode_fixture.py):
tests/unit/test_run_observed_resolve_opencode.py::test_the_tiered_opencode_spec_reviewer_is_the_named_reviewer,
::test_a_tiered_opencode_phase_executor_is_never_a_reviewer and
::test_every_agent_type_comparison_folds_the_opencode_tier (red before the
fix, green after). This pulls plan step P2.T1.S2 forward; P2.T1.S1/S2 are
left unticked for phase 2 to confirm.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-09-29T12:50:02+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: OpenCodeSession returns [] (not None) for a session absent from the database, so a wrong db (gh#740) gives false gate refusals (phase 1)

Commit 430ad284. `OpenCodeSession` reads nothing for a session the
database does not hold (`_known`), `observed_session` returns `None` for
it on a readable database, and `orchestrator_wrote_since` no longer falls
back to every top-level session when a session id was exported but is not
in the database (gh#740). Test:
tests/unit/test_run_observed_opencode.py::test_a_session_the_database_does_not_hold_is_unobserved
(`FR_OPENCODE_SESSION_ID=ses_not_in_this_db`).

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-09-29T12:50:02+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: Claude Code ChildDispatch.returned is the launch ack for a backgrounded Agent dispatch; the child's SubagentHandback input.message is not read (phase 1)

Commit 6549e2a1. `ClaudeCodeSession.dispatches` sets `returned` to the
child's last `SubagentHandback` `input.message`, else the parent-side
tool_result text unless that record is a launch ack (`toolUseResult.isAsync`
/ `status: async_launched`, read keys-only from a live session;
`backgroundTaskId` too), else `None`. New fixtures
tests/fixtures/transcripts/claude-code-subagent-handback.jsonl and
claude-code-agent-launch-ack.jsonl (fictional text, shapes noted in
claude-code-session.NOTE.md). Tests:
tests/unit/test_run_observed_claude_code.py::test_a_backgrounded_report_is_the_childs_handback,
::test_the_handback_wins_over_the_parents_result and
::test_a_launch_ack_alone_is_no_return.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-09-29T12:50:02+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: OpenCodeSession._final_text raises AttributeError on non-mapping part JSON (phase 1)

Commit 430ad284. `OpenCodeSession._final_text` skips a part whose JSON is
not a mapping. Test:
tests/unit/test_run_observed_opencode.py::test_a_non_mapping_part_does_not_break_the_final_text.

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-09-29T12:50:02+00:00 phase=1 state=fixed resolves=p1-r5 -->
### p1-r5-resolved · finding [fixed] · resolves p1-r5: _why_unobservable and the _verify_reviewer docstring still say OpenCode has no reader (phase 1)

Commits 78cbbccc and 0ddebddc (keeps the harness name in the text, which
test_run_cli.py::test_a_gate_on_a_harness_with_no_question_reader_records_unobserved[opencode]
asserts). `_why_unobservable` on OpenCode says the session id was
not exported (super-fr OpenCode plugin missing or older than this
release), or not found in the database fr read; Hermes reads "fr has no
session reader for hermes". The `_verify_reviewer` docstring no longer says
OpenCode has no dispatch reader. Tests:
tests/unit/test_run_observed_resolve_opencode.py::test_why_unobservable_on_opencode_names_the_missing_export
and ::test_an_unexported_session_warns_with_the_plugin_wording.

<!-- fr:journal kind=finding scope=plan id=p1-r6-resolved created=2026-09-29T12:50:02+00:00 phase=1 state=fixed resolves=p1-r6 -->
### p1-r6-resolved · finding [fixed] · resolves p1-r6: current_session returns the child id on OpenCode but the orchestrator id on Claude Code; raw callers (capture, binding, dispatched_from_this_session) do not walk to root (phase 1)

Commit 4deac77a. `fr.run.telemetry.run_session(env)` walks an OpenCode
session id up `parent_id` to the top-level session (the raw id when the
database cannot be read) and is `current_session` on Claude Code; it feeds
`advance`'s attempt session, `usage.capture.candidates`, the
`isolation/sessions.py` ambient binding and `dispatched_from_this_session`.
Tests: tests/unit/test_run_observed_resolve_opencode.py::test_advance_from_a_child_session_records_the_run_session,
::test_run_session_walks_to_the_root_on_opencode_only,
::test_a_child_session_binds_and_compares_as_the_run_session, and
tests/unit/test_run_cost_cmd.py::test_an_opencode_runs_own_session_fills_the_cost_table[ses_gen1]
(one session captured, $1.00, not the child counted again).

<!-- fr:journal kind=finding scope=plan id=p1-r7-resolved created=2026-09-29T12:50:02+00:00 phase=1 state=fixed resolves=p1-r7 -->
### p1-r7-resolved · finding [fixed] · resolves p1-r7: ClaudeCodeSession.dispatches parses the transcript twice (phase 1)

Commit 6549e2a1. `attribute_dispatches` (and `tool_use_ids`) take an
optional already-read `records`; `ClaudeCodeSession.dispatches` passes its
own, so the orchestrator transcript is parsed once. No behaviour change:
tests/unit/test_run_observed_claude_code.py::test_dispatches_pair_by_tool_use_id_as_attribute_dispatches
and the existing attribute_dispatches tests in tests/unit/test_run_telemetry.py
stay green.

<!-- fr:journal kind=finding scope=plan id=p1-cc-background-dispatch-returned-resolved created=2026-09-29T12:50:02+00:00 phase=1 state=fixed resolves=p1-cc-background-dispatch-returned -->
### p1-cc-background-dispatch-returned-resolved · finding [fixed] · resolves p1-cc-background-dispatch-returned: On Claude Code a background-dispatched agent's tool_result may be a launch ack, not its final message (phase 1)

Closed by p1-r3 (commit 6549e2a1): a backgrounded dispatch's launch ack is
never `returned`; the child's `SubagentHandback` report is. Tests as p1-r3.

<!-- fr:journal kind=discovery scope=plan id=p2-redispatch-plugin-upgrade created=2026-09-29T14:53:32+00:00 phase=2 -->
### p2-redispatch-plugin-upgrade · discovery · phase 2 re-dispatched as general-purpose + fr-phase-executor.md instructions (phase 2)

The first phase-2 executor stalled when the host slept (watchdog, 600 s) with nothing committed; closed with advance --redispatch. The super-fr plugin was upgraded 4.39.0 -> 4.40.0 mid-session, removing the super-fr:* agent types from this session's registry, so the re-dispatch is a general-purpose agent instructed to follow super-fr/4.40.0/agents/fr-phase-executor.md, committing after every task.

<!-- fr:journal kind=discovery scope=plan id=p2-t1-done-by-p1-r1 created=2026-09-29T15:39:56+00:00 phase=2 -->
### p2-t1-done-by-p1-r1 · discovery · P2.T1 was delivered by review fix p1-r1 (2aa091c5); one missing test added (phase 2)

2aa091c5 routed `_same_agent` (run_cmd.py and run/visual.py) and the
phase-executor refusal through `fr.run.observed.agent_name`, and
`_verify_reviewer` already reads `observed_session(...).dispatches(opened)`.
Its resolve-level tests covered the tiered spec reviewer (ses_rev), the
invented id and the tiered executor, but not P2.T1.S1's `general` child
(ses_gen1) named as the spec reviewer. That test was added
(`test_a_general_child_is_the_wrong_spec_reviewer_on_opencode`) and is
green with no code change. The executor case runs on the grouped shape's
`peer-review` step (the review-phase equivalent in that test shape).

<!-- fr:journal kind=discovery scope=plan id=p2-holder-fill-changes-p2-r4-premise created=2026-09-29T15:39:56+00:00 phase=2 -->
### p2-holder-fill-changes-p2-r4-premise · discovery · R3's holder fill changes the premise of the p2-r4 visual test; it now uses two executor dispatches (phase 2)

`test_a_dispatched_but_unclaimed_implement_phase_is_refused`
(test_run_evidence_visual.py) showed ONE unclaimed executor dispatch and
expected "no holder was claimed". Under R3 that one child is now the
holder, so the witness reads the executor's session and refuses because
IT never opened the shot (the orchestrator's read still does not count).
The test now shows two executor dispatches (no single holder), keeping
the "unclaimed" refusal covered, and a new sibling test pins the
one-child case. The fill is written through `_close_on_resolve`'s claim
path (`_claimed_identity`), so a claimed holder is never replaced.

<!-- fr:journal kind=decision scope=plan id=p2-coverage-compare-before-partition created=2026-09-29T15:39:56+00:00 phase=2 -->
### p2-coverage-compare-before-partition · decision · The returned-block comparison runs before the partition check, on the fenced block only (phase 2)

`_check_returned_coverage` runs inside `_coverage_witness` BEFORE
`check_coverage`, so a re-cut block is named as a divergence from the
reviewer's return rather than reported as a partition problem it may or
may not also have. It compares the fenced block only (fences
included, `fr.requirements.coverage_block` on the recorded side), not
the whole review body: the orchestrator may still add prose around it.
The row is named as "line N of the block", counting the opening fence as
line 1. A dispatch whose return is not readable yet (OpenCode `running`)
or an unreadable session notes `unobserved=reviewer-return` with a
yellow warning; the dispatch lookup is shared with `_verify_reviewer`
(`_reviewer_dispatches`).

<!-- fr:journal kind=decision scope=plan id=p2-findings-check-needs-reviewer-evidence created=2026-09-29T15:39:56+00:00 phase=2 -->
### p2-findings-check-needs-reviewer-evidence · decision · The returned-findings check runs only on a review unit that names a reviewer (phase 2)

`_check_returned_findings` runs in the review-phase `done` path beside
`_closed_findings_witness`, but only when the unit's evidence carries
`reviewer`: a shape without it (the `[review, findings]` shapes in
test_run_evidence_findings.py) names no dispatched subagent whose
return could be owed, and noting `unobserved=reviewer-return` there
changed their recorded evidence for nothing. The shipped fr-goal
`review-phase` declares both, so it is always checked. Every
non-executor child dispatched since the unit opened is a reviewer
(§D); a reviewer whose return is not readable yet is skipped, and when
none is readable the unit notes `unobserved=reviewer-return`.

<!-- fr:journal kind=decision scope=plan id=p2-findings-block-in-the-brief created=2026-09-29T15:39:56+00:00 phase=2 -->
### p2-findings-block-in-the-brief · decision · The review-phase dispatch brief carries a `findings_block` rule (phase 2)

Spec §D names "`fr run advance`'s dispatch brief, and fr-goal §6 prose"
as where the reviewer is told to end with the block; the plan's T4.S3
lists only the prose. The brief half is one key, `findings_block`
(`fr.run.review_return.findings_block_rule(N)`), added only for a
member whose evidence carries both `findings` and `reviewer` on a
`phase/<N>` item, so no other brief's key set moves (test_run_cli's
exact-key assertion is for a flat step and stays green).

<!-- fr:journal kind=discovery scope=plan id=p2-packaged-workflow-copy created=2026-09-29T15:39:56+00:00 phase=2 -->
### p2-packaged-workflow-copy · discovery · Editing plugins/super-fr/workflows/fr-goal.yaml also needs the packaged copy under packages/fr/src/fr/workflows/ (phase 2)

Beside the two mirror generators, the shipped manifest has a third copy,
`packages/fr/src/fr/workflows/fr-goal.yaml`, that
`test_tripwire_shipped_workflows.py::test_the_packaged_copy_is_byte_identical`
pins (`cp plugins/super-fr/workflows/*.yaml packages/fr/src/fr/workflows/`).
The plan's T4.S3 named only the two sync scripts; the copy is committed
with the prose.

<!-- fr:journal kind=discovery scope=plan id=p2-every-non-executor-child-is-a-reviewer created=2026-09-29T15:39:56+00:00 phase=2 -->
### p2-every-non-executor-child-is-a-reviewer · discovery · Any non-executor subagent the orchestrator dispatches during a review window now owes a findings block (phase 2)

Per spec §D every child dispatched since the review-phase unit opened
that is not a phase executor counts as a reviewer, on Claude Code as on
OpenCode. An orchestrator that dispatches a helper (say, a read-only
search agent to verify a finding) inside that window will see the
resolve refused until that helper's return also ends with a findings
block (`none` suffices). The fr-goal §6 prose says "every
non-executor subagent's return"; worth confirming at review that this
is the intended strictness.

<!-- fr:journal kind=discovery scope=plan id=p2-acceptance-rows-moved created=2026-09-29T15:39:56+00:00 phase=2 -->
### p2-acceptance-rows-moved · discovery · The phase's three acceptance rows moved not-implemented -> ci (phase 2)

`opencode-child-dispatch`, `reviewer-return-coverage` and
`review-phase-findings-block` were moved with `fr acceptance set-status`
(cca7db06, c6d49acf, e17f1c2c), each citing the new test files.
`session-observer-protocol` (phase 1's R4 row) is still
`not-implemented`; phase 2 did not touch it.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t1 created=2026-09-29T15:39:56+00:00 phase=2 -->
### no-refactor-p2-t1 · discovery · no-refactor-because P2.T1 (phase 2)

Already built by review fix p1-r1 (2aa091c5): all three comparison sites call agent_name and _verify_reviewer reads observed_session(...).dispatches(opened). This phase only added the one missing RED case (a `general` child named as spec reviewer); no code changed, nothing to clean.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t2 created=2026-09-29T15:39:56+00:00 phase=2 -->
### no-refactor-p2-t2 · discovery · no-refactor-because P2.T2 (phase 2)

One 30-line helper (`_observed_holder`) called at the two resolve paths before any check reads the holder; it reuses the protocol, `agent_name` and the claim path, so there was no duplication to fold.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t3 created=2026-09-29T15:39:56+00:00 phase=2 -->
### no-refactor-p2-t3 · discovery · no-refactor-because P2.T3 (phase 2)

The one duplication the check created (the dispatch lookup `_verify_reviewer` already did) was folded into `_reviewer_dispatches` in the same commit, which both callers use; the pure readers live in their own module with no I/O.
