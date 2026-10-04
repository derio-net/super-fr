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

<!-- fr:journal kind=discovery scope=plan id=p2-t1-green-on-arrival created=2026-10-02T20:29:56+00:00 phase=2 -->
### p2-t1-green-on-arrival · discovery · P2.T1's RED tests passed on arrival — phase 1 had already ported the agent_name normaliser (phase 2) (phase 2)

Phase 1's port of salvage 2aa091c5 already routed `_same_agent` (run_cmd),
`run/visual.py`'s `_same_agent` and the phase-executor refusal through
`observed.agent_name`, and `_verify_reviewer` already asks
`observed_session(...).dispatches` for the named id. The invented-id
spec-review test and the tiered-executor test existed; T1.S1 added the
invented id at the PHASE review and the `general` child named as spec
reviewer (salvage 33fed900). Both passed without a code change — the
GREEN step is the phase-1 code, verified, not new code.

<!-- fr:journal kind=discovery scope=plan id=p2-review-findings-brief-is-a-member-brief created=2026-10-02T20:29:56+00:00 phase=2 -->
### p2-review-findings-brief-is-a-member-brief · discovery · The review_findings key lives in _build_member_brief, not _build_brief (phase 2) (phase 2)

Spec §E names `_build_brief` (run_cmd.py:2737), but `review-phase` is a
member of the grouped `implement` step, so its brief is built by
`_build_member_brief`; `_build_brief` only briefs flat steps and the
group. The key is emitted there (`_review_findings_brief`) for any
member whose evidence holds both `findings` and `reviewer` — the shipped
`review-phase` of fr-goal and fr-goal-light — and pinned by
`test_every_shipped_review_phase_brief_carries_the_review_findings_rule`
over both shipped manifests. The check at resolve fires on the same
condition (`findings` derived, `reviewer` declared, a phase), so the
brief and the gate cannot disagree about which units owe a block.

<!-- fr:journal kind=decision scope=plan id=p2-reviewer-return-scope created=2026-10-02T20:29:56+00:00 phase=2 -->
### p2-reviewer-return-scope · decision · Who owes a review-findings block — the named reviewer, or a child whose return carries the fence (phase 2) (phase 2)

Per spec §E (not the salvage's "every non-executor child"): a child
dispatched since the review unit opened is a reviewer when it is the id
in `reviewer` evidence or when its return carries a `review-findings`
fence. A named reviewer with no block, or any fenced block that is
malformed, refuses; an unnamed child with no fence (a helper) is
skipped. An unreadable session, or a named reviewer whose return is not
readable yet, is `unobserved=reviewer-return` with a yellow warning.
The input-coverage half of the salvage (9689ee7a) was not ported.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t1 created=2026-10-02T20:29:56+00:00 phase=2 -->
### no-refactor-p2-t1 · discovery · no-refactor-because P2.T1 (phase 2)

T1's GREEN had already landed with phase 1 (salvage 2aa091c5 ported there: agent_name at all three sites, _verify_reviewer through the protocol); this task only added the two missing refusal tests, so there was no new code to clean.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t2 created=2026-10-02T20:29:56+00:00 phase=2 -->
### no-refactor-p2-t2 · discovery · no-refactor-because P2.T2 (phase 2)

One helper (_observed_holder) and one line at each of the two resolve paths; the helper reuses agent_name and observed_session, so nothing was duplicated to consolidate.

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-10-02T20:35:57+00:00 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · OpenCode resumed child (two task parts, one session) trips the duplicate-id refusal and the holder fill's ≥2 match (phase 2)

observed.py:433-460 emitted one ChildDispatch per task part; a reviewer sent back (OpenCode resumes a task by its session) appeared twice with the same agent_id and return, so run_cmd.py:2165-2190 refused every id as "returned by both ses_x and ses_x" and _observed_holder (:4384-4389) counted two matches. A single id repeated within one block gave the same misleading message.

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-10-02T20:35:57+00:00 phase=2 state=open review_scope=in -->
### p2-r2 · finding [open] (reviewer: in scope) · flat resolve path fills the holder but does not pass it as holder= to _verified_evidence (phase 2)

run_cmd.py:5356-5369: the visual witness still saw attempt.agent None, so a flat agent step owing visual was refused as unclaimed — what §D says the fill prevents. No shipped flat step carries both agent and visual; a repo-override manifest hits it.

<!-- fr:journal kind=finding scope=plan id=p2-r3 created=2026-10-02T20:35:57+00:00 phase=2 state=open review_scope=in -->
### p2-r3 · finding [open] (reviewer: in scope) · phase==N journal requirement conflicts with the manifest's 'file a later-phase finding against THAT phase' convention (phase 2)

run_cmd.py:2191-2201 required phase == N while fr-goal.yaml:151-152 says a finding that belongs to a later phase is filed against that phase and gates its review — an orchestrator following the convention was refused at phase N. Spec-level: R7 literally said "for that phase".

<!-- fr:journal kind=review scope=plan id=review-p2 created=2026-10-02T20:35:57+00:00 phase=2 -->
### review-p2 · review · phase 2 independent code review: 3 findings (p2-r1 medium, p2-r2/p2-r3 low), all in scope (phase 2)

Reviewer checked R5–R8, §D, §E: reviewer identity on both steps and harnesses, holder fill ordering in both resolve paths, the review-findings check (fence name, reviewer set, every refusal, unobserved path, no input-coverage), edge cases (none, letters, extra findings, reclassified), the PR-body render, brief key on both shapes, manifest pairs, cost. Found p2-r1, p2-r2, p2-r3. Received: each verified in the code; p2-r1 and p2-r3 reproduced by failing tests first; p2-r3 resolved by aligning code AND spec (R7, §E) with the manifest convention — phase N or later counts, an earlier phase still does not.

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-10-02T20:35:57+00:00 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: OpenCode resumed child (two task parts, one session) trips the duplicate-id refusal and the holder fill's ≥2 match (phase 2)

6370168e: OpenCodeSession.dispatches keys by child session (latest dispatch wins), so the review check and the holder fill see one child; parse_review_findings refuses an id listed twice in one block as malformed. Tests: test_a_resumed_reviewer_is_one_reviewer (with_resumed_child fixture helper), test_an_id_repeated_within_one_block_is_malformed — both red first.

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-10-02T20:35:57+00:00 phase=2 state=fixed resolves=p2-r2 -->
### p2-r2-resolved · finding [fixed] · resolves p2-r2: flat resolve path fills the holder but does not pass it as holder= to _verified_evidence (phase 2)

6370168e: the flat path passes holder=agent to _verified_evidence, as the member path does. No dedicated test: no shipped flat step carries agent+visual; the member-path test pins the same derive.

<!-- fr:journal kind=finding scope=plan id=p2-r3-resolved created=2026-10-02T20:35:57+00:00 phase=2 state=fixed resolves=p2-r3 -->
### p2-r3-resolved · finding [fixed] · resolves p2-r3: phase==N journal requirement conflicts with the manifest's 'file a later-phase finding against THAT phase' convention (phase 2)

6370168e: returned ids count when journaled against phase N or later (an earlier phase still refused, test_a_finding_against_another_phase_does_not_count unchanged); spec R7/§E and the fr-goal.yaml comment pair say so. Test: test_a_finding_filed_against_a_later_phase_counts (red first).

<!-- fr:journal kind=discovery scope=plan id=p3-t1-green-on-arrival created=2026-10-02T21:28:00+00:00 phase=3 -->
### p3-t1-green-on-arrival · discovery · P3.T1's RED tests passed on arrival (phase 3) (phase 3)

Phases 1-2 routed _gate_provenance (and question_rounds_refusal's caller)
through answered_rounds_since -> observed_session, so OpenCode question
rounds were already read. test_run_observed_gate_opencode.py (one answered
round resolves as derived operator; a declared rounds: 2 against one
observed is refused; declined-only is no answer) is kept as the regression.

<!-- fr:journal kind=discovery scope=plan id=p3-r10-test-churn created=2026-10-02T21:28:00+00:00 phase=3 -->
### p3-r10-test-churn · discovery · Removing the answered_by default breaks every fixture that cleared a gate without a claim (phase 3) (phase 3)

About 25 test files resolved the brainstorm gate bare in an unobservable
context and relied on the default. They now state --answered-by agent (or
evidence answered_by in a record); _clear_cli_gate gained claimed=False for
the refusal tests. The gate refusal precedes the declared-emit check, so
test_done_without_a_declared_emit now states its claim too.

<!-- fr:journal kind=discovery scope=plan id=p3-stale-no-question-tool-claims created=2026-10-02T21:28:00+00:00 phase=3 -->
### p3-stale-no-question-tool-claims · discovery · Two other places still said OpenCode has no question tool (phase 3) (phase 3)

The out-of-scope-operator-guard parity row is partial on OpenCode now (its
journal test pinned advisory), and fr-init's Harness - questions clause said
Hermes and OpenCode have no question tool. Both fixed; journal/operator.py's
docstring too.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t1 created=2026-10-02T21:28:00+00:00 phase=3 -->
### no-refactor-p3-t1 · discovery · no-refactor-because P3.T1 (phase 3) (phase 3)

green on arrival, nothing to restructure

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t2 created=2026-10-02T21:28:00+00:00 phase=3 -->
### no-refactor-p3-t2 · discovery · no-refactor-because P3.T2 (phase 3) (phase 3)

defaults removed in place; one shared wording helper

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t3 created=2026-10-02T21:28:00+00:00 phase=3 -->
### no-refactor-p3-t3 · discovery · no-refactor-because P3.T3 (phase 3) (phase 3)

the protocol call replaced the Claude-Code-only transcript calls in place

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p3-t4 created=2026-10-02T21:28:00+00:00 phase=3 -->
### no-refactor-p3-t4 · discovery · no-refactor-because P3.T4 (phase 3) (phase 3)

data, prose and a regenerated page only

<!-- fr:journal kind=discovery scope=plan id=p3-explainer-regenerated created=2026-10-02T21:28:00+00:00 phase=3 -->
### p3-explainer-regenerated · discovery · Explainer page regenerated byte-identically first (phase 3) (phase 3)

The unmodified 01-fr-goal.md re-rendered from / with --isolated matched the
committed .html byte for byte, so the edited .md's render was committed; no
regeneration is owed.

<!-- fr:journal kind=finding scope=plan id=p3-r1 created=2026-10-02T22:05:47+00:00 phase=3 state=open review_scope=in -->
### p3-r1 · finding [open] (reviewer: in scope) · advance's gate degradation notice still tells OpenCode to ask in chat and STOP and says clearing defaults to answered_by: agent — both now false (phase 3)

run_cmd.py _gate_degradation_notice (~992-1043, printed ~4576-4589; pinned by test_run_cli.py ~358-380): with OpenCode now partial it told the agent to ask in chat (resolve then refuses "no answered question", pushing it to --no-questions and a false agent clearance) and promised an answered_by: agent default R10 removed; the resolve hint omitted the now-required claim.

<!-- fr:journal kind=finding scope=plan id=p3-r2 created=2026-10-02T22:05:47+00:00 phase=3 state=open review_scope=in -->
### p3-r2 · finding [open] (reviewer: in scope) · fr run check never prints a claimed-unobserved operator gate; spec/plan R11 name check as well as gates (phase 3)

run_cmd.py ~6233-6239 listed only agent-cleared gates; test_run_answered_by_no_default.py ~119-126 covered only gates for the claimed-operator case.

<!-- fr:journal kind=finding scope=plan id=p3-r3 created=2026-10-02T22:05:47+00:00 phase=3 state=open review_scope=in -->
### p3-r3 · finding [open] (reviewer: in scope) · out-of-scope-operator-guard OpenCode partial cell has no guard-level fixture test, and its unreadable-store advisory quotes a scope_note claiming verification (phase 3)

parity.yaml ~242-250 cited only the round reader's test; journal/operator.py ~74-84 quoted the cell's scope_note ("…is verified…") right after "recorded as stated" when the store was unreadable.

<!-- fr:journal kind=finding scope=plan id=p3-r4 created=2026-10-02T22:05:47+00:00 phase=3 state=open review_scope=in -->
### p3-r4 · finding [open] (reviewer: in scope) · _resolve_body answered_by still typed str | None with a cast; spec §F says AnsweredBy | None (phase 3)

run_cmd.py ~5144 / cast ~5281.

<!-- fr:journal kind=finding scope=plan id=p3-r5 created=2026-10-02T22:05:47+00:00 phase=3 state=open review_scope=in -->
### p3-r5 · finding [open] (reviewer: in scope) · stale _gate_provenance comment says OpenCode has no question reader (phase 3)

run_cmd.py ~1327-1330.

<!-- fr:journal kind=finding scope=plan id=p3-r6 created=2026-10-02T22:05:47+00:00 phase=3 state=open review_scope=in -->
### p3-r6 · finding [open] (reviewer: in scope) · SKILL.md §6 review_findings insertion splits the in/out-scope definition sentence (mirrors too) (phase 3)

plugins/super-fr/skills/fr-goal/SKILL.md ~97 and both generated mirrors.

<!-- fr:journal kind=finding scope=plan id=p3-r7 created=2026-10-02T22:05:47+00:00 phase=3 state=open review_scope=in -->
### p3-r7 · finding [open] (reviewer: in scope) · gate-provenance prose tripwire docstring/message still says --answered-by defaults to agent (phase 3)

tests/unit/test_tripwire_gate_provenance_prose.py ~4-8, 43-45.

<!-- fr:journal kind=review scope=plan id=review-p3 created=2026-10-02T22:05:47+00:00 phase=3 -->
### review-p3 · review · phase 3 independent code review: 7 findings (p3-r1 important, p3-r2..r7 low), all in scope (phase 3)

Reviewer checked R9–R14, §F/§G/§H/§J. Most important check cleared: the ~25 tests now passing --answered-by agent hide no regression (all target a gated brainstorm with no readable session; ungated steps resolve without a claim via _clears_gate; an observed gate still derives provenance; --no-questions still means agent; nothing downstream breaks on answered_by None). R9, R12, R13/R14, SKILL/mirrors, explainer and acceptance rows confirmed correct apart from p3-r1..r7. Received: each verified in the code and fixed by a helper subagent in this workspace, red-first where behaviour changed (p3-r1, p3-r2, p3-r3); one orchestrator-found follow-through of p2-r3 rode along (5c26b162: the review_findings rule says "phase N or a later phase"). Full suite after the fixes: 7782 passed, 97 skipped.

<!-- fr:journal kind=finding scope=plan id=p3-r1-resolved created=2026-10-02T22:05:47+00:00 phase=3 state=fixed resolves=p3-r1 -->
### p3-r1-resolved · finding [fixed] · resolves p3-r1: advance's gate degradation notice still tells OpenCode to ask in chat and STOP and says clearing defaults to answered_by: agent — both now false (phase 3)

cd01ecdf: no notice where fr can read the session (Claude Code transcript, or OpenCode with an exported readable session); elsewhere the notice names why (shared why_unobservable) and that the resolve must carry answered_by operator|agent, no default; the advance hint adds --answered-by when unobservable. Tests: test_advance_on_opencode_without_a_session_says_the_claim_is_owed, test_advance_on_opencode_with_a_readable_session_prints_no_notice, test_advance_on_hermes_quotes_the_row_and_owes_a_claim.

<!-- fr:journal kind=finding scope=plan id=p3-r2-resolved created=2026-10-02T22:05:47+00:00 phase=3 state=fixed resolves=p3-r2 -->
### p3-r2-resolved · finding [fixed] · resolves p3-r2: fr run check never prints a claimed-unobserved operator gate; spec/plan R11 name check as well as gates (phase 3)

c4c14b5c: fr run check prints claimed-unobserved operator gates with the shared _operator_answer sentence; test_a_claimed_operator_on_an_unobserved_gate_says_so covers check and gates.

<!-- fr:journal kind=finding scope=plan id=p3-r3-resolved created=2026-10-02T22:05:47+00:00 phase=3 state=fixed resolves=p3-r3 -->
### p3-r3-resolved · finding [fixed] · resolves p3-r3: out-of-scope-operator-guard OpenCode partial cell has no guard-level fixture test, and its unreadable-store advisory quotes a scope_note claiming verification (phase 3)

96e7bf58, 77c88997: tests/unit/test_journal_operator_guard_opencode.py runs the guard on the OpenCode fixture (refused with no round since, accepted with one, unreadable store, no session export); the OpenCode advisory uses why_unobservable; the parity cell cites the new test.

<!-- fr:journal kind=finding scope=plan id=p3-r4-resolved created=2026-10-02T22:05:47+00:00 phase=3 state=fixed resolves=p3-r4 -->
### p3-r4-resolved · finding [fixed] · resolves p3-r4: _resolve_body answered_by still typed str | None with a cast; spec §F says AnsweredBy | None (phase 3)

b1cc88a7: _resolve_body takes AnsweredBy | None; the closed-set check moved to _answered_by_or_exit at the string entry points; cast removed; mypy clean.

<!-- fr:journal kind=finding scope=plan id=p3-r5-resolved created=2026-10-02T22:05:47+00:00 phase=3 state=fixed resolves=p3-r5 -->
### p3-r5-resolved · finding [fixed] · resolves p3-r5: stale _gate_provenance comment says OpenCode has no question reader (phase 3)

b1cc88a7: _gate_provenance comment lists the real unobservable cases.

<!-- fr:journal kind=finding scope=plan id=p3-r6-resolved created=2026-10-02T22:05:47+00:00 phase=3 state=fixed resolves=p3-r6 -->
### p3-r6-resolved · finding [fixed] · resolves p3-r6: SKILL.md §6 review_findings insertion splits the in/out-scope definition sentence (mirrors too) (phase 3)

e48f14aa, c3255ff7: sentence moved after the out-of-scope definition; both mirrors regenerated; prose pin updated with an ordering assertion.

<!-- fr:journal kind=finding scope=plan id=p3-r7-resolved created=2026-10-02T22:05:47+00:00 phase=3 state=fixed resolves=p3-r7 -->
### p3-r7-resolved · finding [fixed] · resolves p3-r7: gate-provenance prose tripwire docstring/message still says --answered-by defaults to agent (phase 3)

461f9555: tripwire docstring and message describe R10.
