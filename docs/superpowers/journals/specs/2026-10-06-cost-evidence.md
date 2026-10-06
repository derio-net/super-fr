# Journal: 2026-10-06-cost-evidence

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-10-06T17:34:19+00:00 input=true -->
### operator-brief · discovery · Operator brief (batch cost-evidence), verbatim

/fr-goal Cost evidence: per-phase tiers and overhead in the PR body, main-session cost, handoff quality

Batch `cost-evidence` of derio-net/super-fr: 4 issues, delivered as ONE pull request.

## super-fr#838: PR body shows each phase's tier and the model it resolved to
The rendered PR body should show each agentic phase's declared tier and the model it resolved to, so a run that went to the costliest model is visible at a glance (take 10 run A: every phase on the hard tier, $5.91).
Note: Split from #813; #834 already made standard the default tier.

## super-fr#793: fr run cost: per-phase overhead line + before/after audit of phase-per-ask sizing (split from #745)
Split from #745: fr run cost gets a per-phase line splitting executor work from orchestrator and review overhead; a before/after fr-audit of phase-per-ask sizing needs a real run after #792.
Note: Proposed with the light-path follow-ups; the audit needs a run on 4.32+.

## super-fr#593: fr-goal: measure the main session's per-step cost before deciding whether to thin it (and whether spec-review needs its own agent)
Discussion: measure main-session cost per step before thinning it or giving spec-review its own agent. The evidence is one OpenCode run. Option 0 (record per-step main-session tokens in the cursor) is the cheap prerequisite.
Note: Decide before building. It relates to super-fr#537's dispatch-identity gap only by theme.

## super-fr#627: Did the bounded executor handoff (2026-09-20) lower phase quality? Measure with usage/ baselines
Investigation. Data now exists (`docs/superpowers/usage/`, 3 live + 1 archived), but per-model comparison is unreliable while the cursor records the binding, not the model that ran (super-fr#637); several captures have `usd: null`.
Note: Park until super-fr#637, or read models from `usage/` files only. Group with super-fr#593 and super-fr#597 §2.

## Why these belong together
Wave 9 feature 3. #597 is a close candidate (shipped in #604), so it is not in this batch.

## Delivery rules
- Work on branch `feat/batch-cost-evidence`.
- Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges:
  Closes derio-net/super-fr#838
  Closes derio-net/super-fr#793
  Closes derio-net/super-fr#593
  Closes derio-net/super-fr#627
- Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels.

<!-- fr:journal kind=decision scope=spec id=q1-persist-split created=2026-10-06T17:34:19+00:00 -->
### q1-persist-split · decision · Persist the per-unit / per-role split in usage schema v2

Operator: persist, provided it is mechanical and costs no extra rounds or tokens. It is computed at capture by session_entry (R6).

<!-- fr:journal kind=decision scope=spec id=q2-record-bound created=2026-10-06T17:34:19+00:00 -->
### q2-record-bound · decision · Record tier and bound model on the attempt (run kind 9)

Operator chose recording the binding at dispatch over resolving at render or showing tier+ran only.

<!-- fr:journal kind=decision scope=spec id=q3-tokens-beside-dollars created=2026-10-06T17:34:19+00:00 -->
### q3-tokens-beside-dollars · decision · Show tokens beside dollars when dollars are missing

Operator chose turns + cache-read/output tokens always, dollars where priced, no invented price.

<!-- fr:journal kind=decision scope=spec id=q4-593-option0-note created=2026-10-06T17:34:19+00:00 -->
### q4-593-option0-note · decision · #593: build option 0 plus a decision note from existing runs

The 3-task x 2-harness campaign stays out of scope; option 2 already shipped as fr-spec-reviewer.

<!-- fr:journal kind=decision scope=spec id=q5-usage-compare-audit created=2026-10-06T17:34:19+00:00 -->
### q5-usage-compare-audit · decision · fr usage compare plus one audit doc for #627 and #793-5

A deterministic compare verb; the audit quotes its output and states data limits.

<!-- fr:journal kind=finding scope=spec id=sr-r1-1 created=2026-10-06T17:43:32+00:00 state=open review_scope=in -->
### sr-r1-1 · finding [open] (reviewer: in scope) · §D: run 8→9 cannot reuse cursor_guard (frozen v1–v4 reader refuses every v8 cursor)

run_cursor.py:39-70 parses with parse_run_state_v4; follow run_driver.py's 7→8 precedent with an _already_v8 check.

<!-- fr:journal kind=finding scope=spec id=sr-r1-2 created=2026-10-06T17:43:32+00:00 state=open review_scope=in -->
### sr-r1-2 · finding [open] (reviewer: in scope) · §C: new usage files would still be stamped schema_version 1

file.py:142 default; constructors capture.py:252,279, backfill.py:180, run_usage_split.py:239. Pass the current version explicitly; 1→2 fn refuses unparseable; unavailable validator covers new fields.

<!-- fr:journal kind=finding scope=spec id=sr-r1-3 created=2026-10-06T17:43:32+00:00 state=open review_scope=in -->
### sr-r1-3 · finding [open] (reviewer: in scope) · Other session_entry callers (backfill, refreshed_file, recompute) unaddressed vs the archived non-goal

backfill.py:77-135,180; cost.py:196-222. Name each caller and what it passes.

<!-- fr:journal kind=finding scope=spec id=sr-r1-4 created=2026-10-06T17:43:32+00:00 state=open review_scope=in -->
### sr-r1-4 · finding [open] (reviewer: in scope) · §B: flat-step subagents (spec-review) land in (unattributed)

forge-remainder cursor :17-31 records step/spec-review's agent and evidence.reviewer. Add an `agent` role.

<!-- fr:journal kind=finding scope=spec id=sr-r1-5 created=2026-10-06T17:43:32+00:00 state=open review_scope=in -->
### sr-r1-5 · finding [open] (reviewer: in scope) · §B window rule misattributes retries, swallows on synthesized attempts, boundary unstated

model.py:63-129; rollup.py:105-115 half-open. Use per-attempt half-open intervals, skip synthesized, open-ended only when open_attempt holds.

<!-- fr:journal kind=finding scope=spec id=sr-r1-6 created=2026-10-06T17:43:32+00:00 state=open review_scope=in -->
### sr-r1-6 · finding [open] (reviewer: in scope) · Sum invariant leaves rollup's remainder unplaced; per-message price is private

rollup.py:118-141,178-185. State where the remainder lives and the exact equations; expose a shared per-message dollar function.

<!-- fr:journal kind=finding scope=spec id=sr-r1-7 created=2026-10-06T17:43:32+00:00 state=open review_scope=in -->
### sr-r1-7 · finding [open] (reviewer: in scope) · §D/R7 ambiguous for orchestrator attempts and unobservable models

run_cmd.py:3543-3557, :3704-3730. Orchestrator observation stays; tier/bound only with agent_type; unobserved ran renders — without mismatch.

<!-- fr:journal kind=finding scope=spec id=sr-r1-8 created=2026-10-06T17:43:32+00:00 state=open review_scope=in -->
### sr-r1-8 · finding [open] (reviewer: in scope) · §F: compare must read v1–v4 archived cursors; run→plan-journal link unspecified

registry.py:386-400; backfill.py:65-74; journal/model.py:96,458-470. Tolerant read via fr.run.legacy; plan via steps.plan.emitted.plan; findings by journal phase.

<!-- fr:journal kind=finding scope=spec id=sr-r1-9 created=2026-10-06T17:43:32+00:00 state=open review_scope=in -->
### sr-r1-9 · finding [open] (reviewer: in scope) · q3 (tokens beside dollars) applied only to the per-phase table

pr_body.py:556-558. State tokens for the step table and compare columns; test unpriced.

<!-- fr:journal kind=finding scope=spec id=sr-r1-10 created=2026-10-06T17:43:32+00:00 state=open review_scope=in -->
### sr-r1-10 · finding [open] (reviewer: in scope) · §A: Hermes reader already has the child session id

hermes.py:113-141 owner. Record it; R3 simply fails to match.

<!-- fr:journal kind=finding scope=spec id=sr-r1-11 created=2026-10-06T17:43:32+00:00 state=open review_scope=in -->
### sr-r1-11 · finding [open] (reviewer: in scope) · Pre-gh#637 attempt model holds the binding; showing it as ran misleads

run_cmd.py:3707-3711. Show ran only for attempts with bound; list as an audit limit.

<!-- fr:journal kind=finding scope=spec id=sr-r1-12 created=2026-10-06T17:43:32+00:00 state=open review_scope=out -->
### sr-r1-12 · finding [open] (reviewer: out of scope) · Reviewer dispatch briefs stay keyed by raw agent id (units_by_agent ignores evidence.reviewer)

usage/file.py:230-243,300-303; forge-remainder usage :59-64. Pre-existing, no requirement asks for it.

<!-- fr:journal kind=review scope=spec id=sr-review-1 created=2026-10-06T17:43:32+00:00 -->
### sr-review-1 · review · Spec review of 2026-10-06-cost-evidence-design

Independent review by fr-spec-reviewer: 12 findings, sr-r1-1..11 in scope, sr-r1-12 out of scope. Decisions q1, q2, q4, q5 honoured; q3 partly (sr-r1-9). Only usage (1→2) and run (8→9) kinds move; record kind unaffected.

<!-- fr:journal kind=finding scope=spec id=sr-r1-1-resolved created=2026-10-06T17:43:32+00:00 state=fixed resolves=sr-r1-1 -->
### sr-r1-1-resolved · finding [fixed] · resolves sr-r1-1: §D: run 8→9 cannot reuse cursor_guard (frozen v1–v4 reader refuses every v8 cursor)

§D now follows run_driver.py's 7→8 precedent with an _already_v8 live-model check; cursor_guard is named as the wrong tool.

<!-- fr:journal kind=finding scope=spec id=sr-r1-2-resolved created=2026-10-06T17:43:32+00:00 state=fixed resolves=sr-r1-2 -->
### sr-r1-2-resolved · finding [fixed] · resolves sr-r1-2: §C: new usage files would still be stamped schema_version 1

R5 + §C: every new-file UsageFile constructor passes current_usage_schema_version(); 1→2 fn refuses unparseable; unavailable validator covers steps_by_role/units; Test Plan asserts a fresh capture is stamped 2.

<!-- fr:journal kind=finding scope=spec id=sr-r1-3-resolved created=2026-10-06T17:43:32+00:00 state=fixed resolves=sr-r1-3 -->
### sr-r1-3-resolved · finding [fixed] · resolves sr-r1-3: Other session_entry callers (backfill, refreshed_file, recompute) unaddressed vs the archived non-goal

R6 + §B 'Callers of session_entry': capture and recompute pass unit_index; backfill and refreshed_file pass None, so archived files are not re-shaped.

<!-- fr:journal kind=finding scope=spec id=sr-r1-4-resolved created=2026-10-06T17:43:32+00:00 state=fixed resolves=sr-r1-4 -->
### sr-r1-4-resolved · finding [fixed] · resolves sr-r1-4: §B: flat-step subagents (spec-review) land in (unattributed)

R3 + §B: role `agent` for flat step/<id> units; in the YAML example and the validator's closed set.

<!-- fr:journal kind=finding scope=spec id=sr-r1-5-resolved created=2026-10-06T17:43:32+00:00 state=fixed resolves=sr-r1-5 -->
### sr-r1-5-resolved · finding [fixed] · resolves sr-r1-5: §B window rule misattributes retries, swallows on synthesized attempts, boundary unstated

§B: per-attempt half-open intervals, synthesized skipped, open-ended only when open_attempt holds, latest-dispatched interval wins on overlap; Test Plan covers retry, synthesized, shared endpoint.

<!-- fr:journal kind=finding scope=spec id=sr-r1-6-resolved created=2026-10-06T17:43:32+00:00 state=fixed resolves=sr-r1-6 -->
### sr-r1-6-resolved · finding [fixed] · resolves sr-r1-6: Sum invariant leaves rollup's remainder unplaced; per-message price is private

§B 'Dollars': public message_dollars shared by rollup and the split; remainder stays in steps['(outside run)']; three exact invariants stated and tested.

<!-- fr:journal kind=finding scope=spec id=sr-r1-7-resolved created=2026-10-06T17:43:32+00:00 state=fixed resolves=sr-r1-7 -->
### sr-r1-7-resolved · finding [fixed] · resolves sr-r1-7: §D/R7 ambiguous for orchestrator attempts and unobservable models

R7 + §D: tier/bound only when agent_type is set; orchestrator attempts keep orchestrator_model; unobserved model renders — and is not a mismatch (R8).

<!-- fr:journal kind=finding scope=spec id=sr-r1-8-resolved created=2026-10-06T17:43:32+00:00 state=fixed resolves=sr-r1-8 -->
### sr-r1-8-resolved · finding [fixed] · resolves sr-r1-8: §F: compare must read v1–v4 archived cursors; run→plan-journal link unspecified

R10 + §F: tolerant raw cursor read with v1–v4 via fr.run.legacy; plan via steps.plan.emitted.plan; findings by journal phase; re-opens via the resolution fold; pre-v5 fixture in Test Plan.

<!-- fr:journal kind=finding scope=spec id=sr-r1-9-resolved created=2026-10-06T17:43:32+00:00 state=fixed resolves=sr-r1-9 -->
### sr-r1-9-resolved · finding [fixed] · resolves sr-r1-9: q3 (tokens beside dollars) applied only to the per-phase table

R8/R9/R10 + §E: every dollar column carries turns and cache-read/output tokens, in both tables and compare; unpriced case tested.

<!-- fr:journal kind=finding scope=spec id=sr-r1-10-resolved created=2026-10-06T17:43:32+00:00 state=fixed resolves=sr-r1-10 -->
### sr-r1-10-resolved · finding [fixed] · resolves sr-r1-10: §A: Hermes reader already has the child session id

R1 + §A: Hermes records the child session id; it falls to (unattributed) because Hermes cursors record the delegate_task handle; R11 lists the limit.

<!-- fr:journal kind=finding scope=spec id=sr-r1-11-resolved created=2026-10-06T17:43:32+00:00 state=fixed resolves=sr-r1-11 -->
### sr-r1-11-resolved · finding [fixed] · resolves sr-r1-11: Pre-gh#637 attempt model holds the binding; showing it as ran misleads

R8 + §E: ran shown only for attempts that recorded bound; R11 lists pre-gh#637 models as a data limit.

<!-- fr:journal kind=finding scope=spec id=sr-r1-12-resolved created=2026-10-06T17:43:32+00:00 state=open resolves=sr-r1-12 out_of_scope=true -->
### sr-r1-12-resolved · finding [out-of-scope] · resolves sr-r1-12: Reviewer dispatch briefs stay keyed by raw agent id (units_by_agent ignores evidence.reviewer)

Pre-existing: brief re-keying ignored evidence.reviewer before this change; no requirement here asks for it, and this change does not alter brief keys.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-06-cost-evidence-p2 created=2026-10-06T17:45:35+00:00 -->
### phase-split-2026-10-06-cost-evidence-p2 · decision · ask: #838 tier/bound model and #793 item 4 per-phase overhead table (R7-R9)
