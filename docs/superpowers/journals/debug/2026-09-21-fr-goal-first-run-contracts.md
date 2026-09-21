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
