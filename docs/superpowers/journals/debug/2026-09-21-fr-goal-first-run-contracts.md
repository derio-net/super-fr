# Journal: 2026-09-21-fr-goal-first-run-contracts

<!-- fr:journal kind=repro scope=debug id=85b6c5291764 created=2026-09-21T17:59:01 -->
### 85b6c5291764 · repro · C4: fr-goal workspace reports sessions=none after fr run start

Run 2026-09-21-fix-497 started via `cd <repo> && uv run fr run start fr-goal --branch fix/497-...` (AGENTS.md mandates `uv run fr` in this repo). `fr isolation status` then shows the workspace with sessions=none, although every cursor attempt records session 1d0b209a (fr run itself read the session id from CLAUDE_CODE_SESSION_ID, fr/run/telemetry.py:107). Repro with a stub fr on PATH: fr-session-bind.sh calls attach for `fr run start` and `cd X && fr run start`, and calls NOTHING for `uv run fr run start` or `cd X && uv run fr run start`.

<!-- fr:journal kind=root-cause scope=debug id=1f6c1cbffbab created=2026-09-21T17:59:02 -->
### 1f6c1cbffbab · root-cause · C4: fr-session-bind.sh is start-anchored on bare fr; the uv run fr form never matches

The verb regexes are ^[[:space:]]*fr[[:space:]]+(isolation|run start). Any launcher prefix (uv run, uvx, a venv path) silently opts out of binding. Consequence beyond traceability: fr-run-idle-guard.sh keys on ~/.cache/fr/sessions/<id>.json and exits 0 when it is absent, so the Stop guard (#518) was inert for the whole run. Structural note: fr run already knows the session (telemetry.SESSION_ID_ENV) — the engine could bind itself instead of a hook regex-parsing the command line.

<!-- fr:journal kind=repro scope=debug id=fafba5a0e064 created=2026-09-21T17:59:40 -->
### fafba5a0e064 · repro · C1: brainstorm operator gate cleared with no question asked, on Claude Code

Cursor: brainstorm answered_by: agent, 84s after start. `fr run advance` printed only 'blocked on operator gate — answer it, then fr run resolve ...' — no degradation notice. `fr run resolve --step brainstorm --state done` succeeded (answered_by defaults to agent). fr-brainstorming was never invoked.

<!-- fr:journal kind=root-cause scope=debug id=a5886bc80c41 created=2026-09-21T17:59:40 -->
### a5886bc80c41 · root-cause · C1: parity.yaml declares operator-gate enforced on claude-code, but nothing enforces it — which suppresses the only warning

Spec 2026-09-18 §3.E declares claude-code operator-gate: enforced because Claude Code HAS a question tool (test_advance_prints_no_notice_when_the_harness_enforces_the_gate: 'the one harness where the gate genuinely blocks'). Nothing ties clearing the gate to an AskUserQuestion answer; resolve accepts --answered-by agent by default. So the declaration is a capability, not an enforcement, and _gate_degradation_notice returns None on Claude Code — the only harness spared the STOP notice. Predates the recent refactor (4.5.0, #481): a latent false model, not a regression. Proximate cause is agent non-compliance (fr-goal §1 hard gate + skipped fr-brainstorming); the defect is that the system claimed a guarantee it does not have. fr can read the session transcript (fr/run/telemetry.py), so real enforcement is buildable: require an AskUserQuestion tool_result between the gate's block time and the resolve.

<!-- fr:journal kind=root-cause scope=debug id=49dc83be108d created=2026-09-21T18:00:54 -->
### 49dc83be108d · root-cause · C6 (cross-cutting): a brief's skill: is never checked — every named skill was skipped and every step still resolved done

Transcript of session 1d0b209a: during the fr-goal run the only Skill invocation was fr-goal itself. Briefs named fr-brainstorming (brainstorm), fr-plan (plan), requesting-code-review + receiving-code-review (review-phase), verification-before-completion (deliver); none ran. review-phase's evidence gate (--evidence review=<id>) was satisfied by a kind=review journal entry the orchestrator typed itself — #430 again, one layer down: the gate verifies an entry EXISTS, not that a review HAPPENED. Also: the plan's three no-refactor-because discoveries were written before any code existed, with a generic body, to clear self-review. fr can observe Skill tool_use in the Claude Code transcript (telemetry already reads it for usage).

<!-- fr:journal kind=root-cause scope=debug id=3f71c11764d5 created=2026-09-21T18:00:55 -->
### 3f71c11764d5 · root-cause · C7: fr-phase-executor is told to use skills it has no tool to load

Agent frontmatter: tools: Read, Edit, Write, Bash, Grep, Glob — no Skill. Body step 2: 'Implement the phase TDD via superpowers:test-driven-development / fr-execute'. The executor transcript (79 records, claude-opus-5) shows zero Skill calls: it could not comply. Same capability-boundary class as #428.

<!-- fr:journal kind=root-cause scope=debug id=b45b2dc19815 created=2026-09-21T18:00:55 -->
### b45b2dc19815 · root-cause · C2: a plan whose only phase is the walking skeleton passes self-review

_skeleton_issues (plan_ops.py:1544) checks the marker sits on the first agentic phase, not that the skeleton is a smoke test or that work follows it. The run's single phase was both skeleton and the whole change, so the per-phase implement→review loop ran once. The orchestrator also bypassed fr-plan (C6). The run did not stop after phase 1 — it finished, with one phase; the idle guard was inert anyway (C4).

<!-- fr:journal kind=root-cause scope=debug id=2e4bb34a8ad1 created=2026-09-21T18:00:56 -->
### 2e4bb34a8ad1 · root-cause · C3: no orchestrator model contract; executor model recorded from the claim, not the measurement

fr models binds tiers for subagent dispatch only; the orchestrator runs on the session model (claude-sonnet-5 for the whole fr-goal run, 54 records) and nothing records or checks it. Executor did run claude-opus-5 (79/79), but the cursor stores model: opus — the alias passed to fr run claim --model — although fr reads that very transcript for measured: usage. Not a regression.

<!-- fr:journal kind=root-cause scope=debug id=3691b4decce7 created=2026-09-21T18:00:56 -->
### 3691b4decce7 · root-cause · C5: deliver resolves done with no evidence; success relayed from the executor

deliver is kind: agent, skill verification-before-completion, no evidence: — resolved done 28s after dispatch with only the PR url. The orchestrator never re-ran the suite nor looked at CI, and the summary said 'verified locally' on the executor's word. Same shape as C6.

<!-- fr:journal kind=decision scope=debug id=4a76a3bd07e5 created=2026-09-21T18:20:39 -->
### 4a76a3bd07e5 · decision · Operator decisions (AskUserQuestion, 2026-09-21)

C1 gate: BOTH — degrade loudly on claude-code now, add transcript verification of an AskUserQuestion answer, then flip back to enforced. C6/C7: separate-context review — review-phase done by a dispatched reviewer subagent whose agent id is the evidence; deliver requires --evidence tests=<log>; executor gets the Skill tool. C2: skeleton as sole agentic phase is a self-review ERROR, overridable via skeleton-override-*. C3: orchestrator binding in models.yaml; cursor records the MEASURED orchestrator model and warns (never blocks) on mismatch; executor model recorded from measurement, not the claim. C4 (no question): engine binds from CLAUDE_CODE_SESSION_ID in fr run start / isolation up, hook no longer the only path.

<!-- fr:journal kind=finding scope=debug id=eb0eace77a73 created=2026-09-21T18:25:11 state=fixed -->
### eb0eace77a73 · finding [fixed] · C4 fixed: fr run start and fr isolation up bind the ambient session themselves

fr.isolation.sessions.ambient_binding: explicit --session wins; else telemetry.current_session(env) + detect_harness. run start binds non-fatally as before; isolation up binds non-fatally (explicit --session stays fatal). Pinned by test_run_start_binds_the_ambient_session_when_none_is_given, test_run_start_binds_nothing_when_no_session_is_knowable, test_up_without_session_binds_the_ambient_one (verified red with the source stashed). conftest now sandboxes FR_SESSIONS_DIR suite-wide so the ambient default cannot bind the operator's live session. Hook left as-is: exec via uv run fr still does not bind (low value; engine covers the two workspace-creating verbs).

<!-- fr:journal kind=finding scope=debug id=1cadeef0fa35 created=2026-09-21T18:34:07 state=fixed -->
### 1cadeef0fa35 · finding [fixed] · C3 fixed: cursor records OBSERVED models; orchestrator binding warns on mismatch

(a) telemetry.UsageTotals.served_models (from assistant message.model; compare=False) and units.with_measured(served_model=) — a measured dispatch's model replaces the claimed alias. (b) telemetry.orchestrator_model(env): last main-thread assistant model of this session's transcript, tail-read, sidechain skipped, never raises; _open_dispatch records it for orchestrator-run units (agent_type None) — observed, never tier-resolved, so the 'seven false reviews' lesson stands. (c) models.yaml key 'orchestrator' (ORCHESTRATOR_ROLE); fr run start and every advance print a yellow warning when the observed orchestrator model differs from the binding; silent with no binding or no observation; never blocks. Tests: test_resolve_records_the_served_model_not_the_claimed_alias, test_advance_records_the_observed_model_of_an_orchestrator_run_step, test_advance_warns_when_the_orchestrator_is_not_on_its_bound_model, test_advance_is_silent_when_the_orchestrator_matches_its_binding, three orchestrator_model unit tests.

<!-- fr:journal kind=finding scope=debug id=49d4ae443443 created=2026-09-21T18:43:04 state=fixed -->
### 49d4ae443443 · finding [fixed] · C2 fixed: a skeleton that is the only agentic phase is a self-review error

plan_ops._skeleton_issues errors when the first agentic phase is marked skeleton and is the ONLY agentic phase (manual phases do not count), overridable via the existing spec-scope skeleton-override-<plan>. fr-plan SKILL.md states it (mirrors regenerated, both scripts). Pinned by test_self_review_errors_when_the_skeleton_is_the_only_agentic_phase[with_manual=False/True] and test_sole_skeleton_error_is_silenced_by_the_skeleton_override. Blast radius: 13 tests used the one-phase v2_plan_minimal fixture as a 'valid plan' — adding a phase to the fixture broke 34 others (they count its phases), so they now record the sanctioned override via tests/unit/skeleton_override.py; test_self_review_clean_plan_has_no_issues became ..._raises_only_its_sole_skeleton. No live plan in the repo trips the rule.

<!-- fr:journal kind=finding scope=debug id=5d28090b6b92 created=2026-09-21T18:52:04 state=fixed -->
### 5d28090b6b92 · finding [fixed] · C1 fixed: the operator gate on Claude Code is verified from the transcript, and degrades loudly where it cannot be

telemetry.operator_answered_since(env, since): True/False when the session transcript is read (an AskUserQuestion tool_use at/after the gate's block time, paired to a tool_result whose toolUseResult is an object with non-empty answers), None when unobservable. resolve (_gate_provenance, decided before any write): answered → answered_by operator (derived, whatever was claimed); observed-unanswered → exit 2 naming both ways forward; --no-questions requires --reason, records agent, writes decision gate-no-questions-<step> to the spec journal the resolve emits; unobservable on claude-code → claim stands with a 'could not verify' warning. advance: _gate_degradation_notice now treats claude-code 'enforced' as true only when the transcript is readable, otherwise prints the STOP notice. Fixture captured live (tests/fixtures/transcripts/claude-code-askuserquestion.jsonl, NOTE.md updated). fr-goal §1 + Harness — questions clause updated (gate-provenance tripwire kept green), parity.yaml operator-gate summary states the mechanism. 8 new tests (5 telemetry, 5 CLI incl. degrade); existing no-notice test now supplies a readable transcript.

<!-- fr:journal kind=finding scope=debug id=6b2eb8b4214d created=2026-09-21T19:04:36 state=fixed -->
### 6b2eb8b4214d · finding [fixed] · C6 fixed: review-phase requires reviewer=<agent-id> of a separate, dispatched context

_VERIFIABLE_EVIDENCE gains reviewer and tests; _PHASE_EVIDENCE scopes the phase requirement. _verify_reviewer refuses the phase's implementer (any dispatched agent on phase/N/* units) and, via telemetry.subagent_dispatched_since (attribute_dispatches pairing), an id this session never dispatched after the review unit opened; unobservable → recorded + 'could not verify'. Shipped fr-goal.yaml review-phase evidence [review, reviewer, findings] (wheel copy re-synced). fr-goal §6 rewritten; the stale '--model <the model you are running on>' clause (obsolete since C3) removed. tests/unit/test_run_evidence_separate_context.py: 10 tests, verified all-red with run_cmd.py stashed.

<!-- fr:journal kind=finding scope=debug id=63047473d3b0 created=2026-09-21T19:04:36 state=fixed -->
### 63047473d3b0 · finding [fixed] · C5 fixed: deliver requires tests=<log> of a suite the orchestrator ran during delivery

_verify_tests_log: log must exist and be non-empty; telemetry.orchestrator_ran_since — a main-thread Bash tool_use naming the log since deliver opened, whose tool_result is not is_error; unobservable → log must be newer than the unit, warned. Witness recorded as <path>@<sha256[:12]>. Shipped deliver evidence [tests]; fr-goal §8 says run the suite yourself. Captured fixture tests/fixtures/transcripts/claude-code-bash.jsonl (paths redacted).

<!-- fr:journal kind=finding scope=debug id=59d50a841f71 created=2026-09-21T19:04:37 state=fixed -->
### 59d50a841f71 · finding [fixed] · C7 fixed: fr-phase-executor granted Skill; tripwire keeps skill-naming agents capable

tools: + Skill. sync-opencode _TOOL_PERMISSIONS maps Skill → None (OpenCode default; mirrors byte-identical, no diff). tests/unit/test_tripwire_agent_skill_capability.py: any canonical agent whose body names a skill must carry Skill — red with the tools edit stashed. CROSS-PR NOTE: PR #532 widens the neutrality scan to agent files including frontmatter; with Skill on the tools: line its scan flags line 13. Fix belongs in #532's test (skip the tools: frontmatter line — a Claude Code allowlist the sync translates, not prose); whichever PR merges second must carry it.

<!-- fr:journal kind=finding scope=debug id=r1-1 created=2026-09-21T19:18:58 state=fixed -->
### r1-1 · finding [fixed] · review r1-1: tests= evidence was satisfiable by any command mentioning the log's basename

Fixed: telemetry.orchestrator_wrote_since returns the (tool_use, tool_result) windows of main-thread Bash commands that WRITE the log (>, >>, tee naming it, absolute path equal or relative suffix); _verify_tests_log requires the log's mtime inside one window (1s slack). cat/ls refused; bytes written after the command refused. Stated limit (skill §8, explainer, docstring): fr proves who wrote the log and when, not that it was a real suite — 'echo ok > log' is forgery, out of reach without a per-repo runner declaration. Tests: test_a_command_that_only_reads_the_log_does_not_count, test_a_log_whose_bytes_postdate_the_command_is_refused.

<!-- fr:journal kind=finding scope=debug id=r1-2 created=2026-09-21T19:18:58 state=fixed -->
### r1-2 · finding [fixed] · review r1-2: <synthetic> recorded as a model

Fixed: telemetry._is_real_model (TypeGuard) rejects angle-bracketed placeholders in orchestrator_model and read_claude_code. Verified real: 2 transcripts in this operator's project hold main-thread <synthetic> records with zero usage. Tests: test_a_synthetic_record_is_never_the_orchestrators_model, test_a_synthetic_record_never_joins_the_served_models.

<!-- fr:journal kind=finding scope=debug id=r1-3 created=2026-09-21T19:18:59 state=fixed -->
### r1-3 · finding [fixed] · review r1-3: unreadable transcript read as 'not dispatched'

Fixed: subagent_dispatch_since returns None when _read_records fails. Test: test_subagent_dispatch_is_unobservable_without_a_readable_transcript.

<!-- fr:journal kind=finding scope=debug id=r1-4 created=2026-09-21T19:18:59 state=refuted -->
### r1-4 · finding [refuted] · review r1-4: an operator answering in plain chat is refused

Refuted by the operator's decision: the chosen design (AskUserQuestion, 2026-09-21) was verification of an ANSWERED QUESTION in the transcript. fr-goal §1's Harness clause already routes the batch through the question tool on Claude Code; a chat prompt is indistinguishable from any other operator message (including the original request), so accepting it would re-open the exact bypass C1 closed. The refusal names the tool and the recorded --no-questions path.

<!-- fr:journal kind=finding scope=debug id=r1-5 created=2026-09-21T19:19:00 state=fixed -->
### r1-5 · finding [fixed] · review r1-5: --no-questions reason lost when no spec emitted

Fixed: the reason goes to the spec emitted by this resolve, else one already emitted on the run; with neither, --no-questions is refused before anything is written. Test: test_no_questions_with_nowhere_to_record_the_reason_is_refused.

<!-- fr:journal kind=finding scope=debug id=r1-6 created=2026-09-21T19:19:00 state=fixed -->
### r1-6 · finding [fixed] · review r1-6: gate-no-questions journal write not idempotent

Fixed: skipped when the entry id already exists. Test: test_the_no_questions_decision_is_logged_once.

<!-- fr:journal kind=finding scope=debug id=r1-7 created=2026-09-21T19:19:00 state=fixed -->
### r1-7 · finding [fixed] · review r1-7: --no-questions/--reason silently ignored off-gate

Fixed: refused (exit 2) on a resolve that clears no gate. Test: test_gate_flags_on_a_resolve_that_clears_no_gate_are_refused.

<!-- fr:journal kind=finding scope=debug id=r1-8 created=2026-09-21T19:19:01 state=fixed -->
### r1-8 · finding [fixed] · review r1-8: absolute log path could leak a home dir into the tracked cursor

Fixed: witness is repo-relative, or basename when outside the repo. Test: test_the_tests_witness_never_carries_an_absolute_path.

<!-- fr:journal kind=finding scope=debug id=r1-9 created=2026-09-21T19:19:01 state=fixed -->
### r1-9 · finding [fixed] · review r1-9: orchestrator_ran_since could raise on a malformed tool input

Fixed in its replacement orchestrator_wrote_since: every block Mapping-guarded, input type-checked. Test: test_a_malformed_tool_input_never_raises.

<!-- fr:journal kind=finding scope=debug id=r1-10 created=2026-09-21T19:19:02 state=fixed -->
### r1-10 · finding [fixed] · review r1-10: stale 'pragma: no cover — unreachable' on flat-unit evidence

Fixed: comment now says deliver's tests evidence reaches it; pragma dropped.

<!-- fr:journal kind=finding scope=debug id=r1-11 created=2026-09-21T19:19:02 state=fixed -->
### r1-11 · finding [fixed] · review r1-11: reviewer agent type unchecked; undated dispatch accepted

Fixed: a super-fr:fr-phase-executor dispatch is refused as a reviewer; a dispatch with no start timestamp no longer counts. Test: test_a_phase_executor_dispatch_is_never_a_reviewer (the capture itself is an executor).

<!-- fr:journal kind=finding scope=debug id=r1-12 created=2026-09-21T19:19:02 state=fixed -->
### r1-12 · finding [fixed] · review r1-12: in-flight runs and unobservable harnesses not documented

Fixed in the PR body (fr-goal is at its 120-line cap): runs started under 4.13 owe reviewer=/tests= at their next review/deliver; on OpenCode/Hermes reviewer ids are checked only against the implementer set and recorded as unverified.

<!-- fr:journal kind=finding scope=debug id=r1-13 created=2026-09-21T19:19:03 state=fixed -->
### r1-13 · finding [fixed] · review r1-13: claude-code-bash.jsonl provenance undocumented

Fixed: section added to tests/fixtures/transcripts/claude-code-session.NOTE.md.

<!-- fr:journal kind=review scope=debug id=5bc62af4e18a created=2026-09-21T19:19:03 -->
### 5bc62af4e18a · review · Review of fix/fr-goal-first-run-contracts by a separately dispatched reviewer

Reviewer: a general-purpose subagent dispatched via superpowers:requesting-code-review (separate context), over origin/main..45fa88cc. Verdict: with fixes. Findings r1-1..r1-13 (5 important, 8 minor): 12 fixed with tests, r1-4 refuted by the operator's C1 decision. The orchestrator's own full-suite run before the review also caught 6 failures (3 integration tests walking the shipped shape now needing reviewer=/tests=; a prose tripwire pinning the --model self-report, which was wrongly dropped and is restored, scoped to harnesses where fr cannot observe the model).

<!-- fr:journal kind=discovery scope=debug id=0b93f5e1638d created=2026-09-21T19:19:42 -->
### 0b93f5e1638d · discovery · fr acceptance check does not validate #L anchors

Inserting tests above a cited test shifted 5 of this branch's new rows' #L refs onto blank lines or unrelated statements, and fr acceptance check still reported 185 rows OK. Corrected by hand (line numbers only). Not fixed here (out of scope): the check could require the anchored line to be a def/decorator, the same staleness the report-sync tripwire already guards for prose.
