# Journal: 2026-09-29-fr-goal-light-path

<!-- fr:journal kind=discovery scope=spec id=input-batch-light-path created=2026-09-29T07:19:13+00:00 input=true -->
### input-batch-light-path · discovery · Operator input — batch light-path (super-fr#780), verbatim

/fr-goal fr-goal light path for small single-phase goals: one review dispatch, one bookkeeping call per step, deliver reuses the verified suite log

Batch `light-path` of derio-net/super-fr: 1 issues, delivered as ONE pull request.

## super-fr#780: fr-goal: a light path for small single-phase goals; the orchestrator's per-step bookkeeping is most of the cost gap to a plain agent
Feature C (small, one phase): plain OpenCode $2.13 / 12.8 min / 83 turns; fr-goal take 9 $7.67 / 45 min / 269 turns (≈2.3× money, 2.8× time without #758). The orchestrator carries 76% (193 turns), re-reading its context per bookkeeping step; 3.6 bookkeeping turns/step on OpenCode against 1–2; fr_cli_learning 3.2%.
Note: Operator-prioritised for the talk. Feature (fr-goal), batch `light-path` (wave 8): fold plan review into spec review for one-phase plans, one bookkeeping call per step, deliver reuses the executor's verified suite log on an unchanged tree. Target ≤ 2× plain's cost, ≤ 2.5× its time on feature C. After phase-sizing (#745) and the wave-6 skill edits.

## Why these belong together
Wave 8, the ceremony tax. Take 9 (feature C, one phase) cost ≈2.3× plain's money and ≈2.8× its time without #758; the orchestrator carries 76% of it, re-reading its context on every fr run bookkeeping step. Target from #780: ≤ 2× plain's cost and ≤ 2.5× its time on feature C. Fold plan review into spec review for a one-phase plan; resolve+record+advance in one fr run call; deliver reuses the executor's verified suite log when the tree is unchanged; subagents return structured results. After phase-sizing (#745) and the wave-6 fr-goal skill edits (rebase). Take 10's plain-vs-fr gap is the benchmark.

## Delivery rules
- Work on branch `feat/batch-light-path`.
- Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges:
  Closes derio-net/super-fr#780
- Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels.

<!-- fr:journal kind=decision scope=spec id=d1-select-brainstorm-rebind created=2026-09-29T07:19:13+00:00 -->
### d1-select-brainstorm-rebind · decision · Light path is a second shape, reachable at start or by a brainstorm-record rebind

Q: How does a run get onto the light path? A: Brainstorm record rebinds (recommended).
Ship `fr-goal-light`; the brainstorm record may declare `shape: fr-goal-light` and resolve
rebinds the cursor (only at the first step, only onto a shape beginning with it); the
operator may also `fr run start fr-goal-light`. The light `plan` step refuses >1 agentic phase.

<!-- fr:journal kind=decision scope=spec id=d2-reviews-spec-plan-once-code-once created=2026-09-29T07:19:13+00:00 -->
### d2-reviews-spec-plan-once-code-once · decision · Light path keeps one spec+plan reviewer dispatch and the per-phase code review

Q: Which review dispatches does the light path keep? A: Spec+plan once, code once (recommended).
One fr-spec-reviewer dispatch reviews spec and one-phase plan together after the plan is
written; `fr plan self-review` stays as a cli step; review-phase with a dispatched reviewer stays.

<!-- fr:journal kind=decision scope=spec id=d3-one-call-default-all-shapes created=2026-09-29T07:19:13+00:00 -->
### d3-one-call-default-all-shapes · decision · resolve --record advances by default on every shape; advance chains cli steps

Q: One bookkeeping call per step — all runs or light only? A: Default, all shapes (recommended).
`resolve --record` advances by default (`--no-advance` opts out); `fr run advance` chains
consecutive cli steps until the next agent step or first failure.

<!-- fr:journal kind=decision scope=spec id=d4-suite-reuse-tree-matched created=2026-09-29T07:19:13+00:00 -->
### d4-suite-reuse-tree-matched · decision · deliver reuses the latest tree-matched phase suite log, writer verified where readable

Q: How does deliver reuse an earlier suite log? A: Latest log, tree-matched (recommended).
Executor / review-fix records name `evidence: {tests: <log>}`; fr stores hash + code tree
(excluding fr bookkeeping); deliver accepts it while HEAD's code tree matches, else a fresh
run is required; writer verified from the subagent transcript where readable, else unobserved.
Applies on both shapes.

<!-- fr:journal kind=decision scope=spec id=d5-context-prose-and-brief-keys created=2026-09-29T07:19:13+00:00 -->
### d5-context-prose-and-brief-keys · decision · Context discipline ships as skill prose plus fixed agent return shapes

Q: How much of the 'orchestrator context stays small' bullet is in this PR?
A: Skill prose + brief keys (recommended). Light-path section in fr-goal SKILL.md with
explicit rules; executor and reviewer agent files get a fixed return shape; no new fr code
beyond what the other decisions need.

<!-- fr:journal kind=decision scope=spec id=d6-test-plan-rerun-feature-c created=2026-09-29T07:19:13+00:00 -->
### d6-test-plan-rerun-feature-c · decision · Post-merge Test Plan reruns the super-fr-3 feature-C benchmark

Q: Post-merge Test Plan? A: Rerun feature C (recommended). Operator-driven rerun of the
feature-C brief on the light path (take 9/10 base and models), cost and time against plain,
result recorded on #780; the target is a `verify: post-merge` acceptance row.

<!-- fr:journal kind=finding scope=spec id=s1 created=2026-09-29T07:25:12+00:00 state=open review_scope=in -->
### s1 · finding [open] (reviewer: in scope) · `evidence: {tests: <log>}` on implement-phase/review-phase is refused by today's evidence parser; 'no manifest change is needed' is wrong

check: codebase
evidence: spec §D "Recording on a phase unit … It is optional, so no manifest change is needed"; packages/fr/src/fr/commands/run_cmd.py:1510-1519 (`_parse_evidence` refuses any name the step does not declare), run_cmd.py:4663 (every resolve, record form included, goes through it: record/apply.py:927 → resolve_in_process run_cmd.py:5012); plugins/super-fr/workflows/fr-goal.yaml:134 and :185 (implement-phase declares only [visual], review-phase only [review, reviewer, findings, visual]); run_cmd.py:1657-1661 (every declared non-derived name is mandatory on `done`)
scope: this is the mechanism R6 rests on, and the spec as written cannot work against the code it cites
As things stand, a phase record carrying `tests:` is refused with "step 'implement-phase' does not require 'tests' evidence". Adding `tests` to the members' `evidence:` would make it mandatory on every phase, which contradicts "optional". The design has to say how an optional evidence name works: for example a new `_OPTIONAL_EVIDENCE` set that `_parse_evidence` accepts and the `missing` rule skips, plus a manifest edit declaring it. It should also say whether the shipped fr-goal.yaml changes. The Test Plan (item 3) should pin that a phase record without `tests` still resolves.

<!-- fr:journal kind=finding scope=spec id=s2 created=2026-09-29T07:25:12+00:00 state=open review_scope=in -->
### s2 · finding [open] (reviewer: in scope) · §B's advance loop stops before briefing the next agent step, contradicting R4/R5

check: consistency
evidence: spec §B "`fr run advance` loops `_advance_once` while it returns `cli-done` and the new cursor is a `cli` step"; R5 "It stops at the first agent step (printing its brief)"; R4 "prints the next dispatch brief"; §B's own example "`plan-review` → `implement` … costs one call"
scope: an internal contradiction in this spec's core mechanism
Read literally, the loop ends as soon as a `cli-done` leaves the cursor on an agent step, so it never calls `_advance_once` again to brief that step. The `plan-review` → `implement` transition would then still need a second call, which is the cost R4/R5 exist to remove. Fix the loop condition: keep calling `_advance_once` while the previous call returned `cli-done`, so the loop ends on `brief`, `gate`, `cli-failed`, `refused` or `complete`. Add a Test Plan assertion that one `advance` from `plan-review` prints `implement`'s brief.

<!-- fr:journal kind=finding scope=spec id=s3 created=2026-09-29T07:25:12+00:00 state=open review_scope=in -->
### s3 · finding [open] (reviewer: in scope) · Default auto-advance after a `failed`/`blocked` record would immediately re-brief the step that just failed

check: consistency
evidence: spec §B "A refused record never advances" (the only outcome carve-out); R4 "On every shape, `fr run resolve --record` also advances by default"; run_cmd.py:886-889 (a `failed` outcome leaves the cursor in place); run_cmd.py:4155-4177 (advance on a non-running agent step flips it to `running`, opens a new dispatch and prints the brief)
scope: R4 makes this the default on every shape, so the spec has to define the outcome it introduces
A record with `outcome: failed` (or `blocked`, which resolves as failed per record/apply.py:942) leaves the cursor on the failed step. The chained advance would then open a fresh dispatch of that same step and print a new brief, so the orchestrator is told to redispatch work that just failed, with nobody deciding to. Say that only a `done` outcome chains, and that `failed`/`blocked` print the one-line outcome and stop. Add that case to Test Plan item 2.

<!-- fr:journal kind=finding scope=spec id=s4 created=2026-09-29T07:25:12+00:00 state=open review_scope=in -->
### s4 · finding [open] (reviewer: in scope) · Decision d6's `verify: post-merge` acceptance row for the benchmark is not in the spec

check: decisions
evidence: decision d6-test-plan-rerun-feature-c "the target is a `verify: post-merge` acceptance row"; spec R8 and Test Plan item 6 (neither says the row is `verify: post-merge`); fr-goal.yaml:209-214 (`requirement-rows` refuses a `not-implemented` row unless it declares `verify: post-merge`)
scope: an operator decision the spec leaves out, and without it this run's own `deliver` is refused
R8 can only be verified after merge. If the spec does not say its acceptance row carries `verify: post-merge`, the row is an ordinary `not-implemented` row and `deliver`'s derived `requirement-rows` gate refuses it. State in R8 or Test Plan item 6 that R8's row is `verify: post-merge` and that the PR body lists it under `## Post-merge verification owed`.

<!-- fr:journal kind=finding scope=spec id=s5 created=2026-09-29T07:25:12+00:00 state=open review_scope=in -->
### s5 · finding [open] (reviewer: in scope) · R8 adds a pass condition ('with delivery still verified') that neither the input nor d6 states

check: traceability
evidence: input "Target ≤ 2× plain's cost, ≤ 2.5× its time on feature C."; decision d6 ("cost and time against plain"); spec R8 "…takes at most 2.5× plain's time, with delivery still verified"; Test Plan 6 "with `deliver`'s evidence verified"
scope: traceability findings are always in scope
resolution: reinterpreted
The input's target is two ratios. R8 adds a third condition that decides pass or fail, so it says more than its quotes. Either resolve this `unconfirmed` with a note stating that the benchmark also requires deliver's evidence gates to pass (not unobserved), or remove the clause so the literal two-ratio target is enough. Do not rewrite the input quote to fit.

<!-- fr:journal kind=finding scope=spec id=s6 created=2026-09-29T07:25:12+00:00 state=open review_scope=in -->
### s6 · finding [open] (reviewer: in scope) · The record-kind bump also needs `RECORD_SCHEMA_VERSION` in record/model.py, which refuses any other stamp

check: codebase
evidence: spec §A "`current_version` goes 4 → 5 (packages/fr/src/fr/artifacts/registry.py:441)"; packages/fr/src/fr/record/model.py:54 (`RECORD_SCHEMA_VERSION = 4`); record/model.py:220 and :251-255 (`StepRecord` rejects any `schema_version` other than that constant); prior pattern fr/artifacts/record_visual.py registered at fr/artifacts/__init__.py:53
scope: part of this change's own artifact-versioning obligation; unsure it is more than an omission in the prose, so tagged in
The record model keeps its own literal stamp. Bumping only the registry leaves every migrated v5 record unparseable by `load_record`, and a new `shape:` key without the model bump is refused as an extra field. Name `RECORD_SCHEMA_VERSION` (and the `shape` field on `StepRecord`) alongside the registry line. Test Plan item 4 should load a v5 record carrying `shape:`.

<!-- fr:journal kind=finding scope=spec id=s7 created=2026-09-29T07:25:12+00:00 state=open review_scope=in -->
### s7 · finding [open] (reviewer: in scope) · Observing an executor's log on OpenCode assumes a child-session lookup fr does not have

check: codebase
evidence: spec §D.1 "on OpenCode it is the child session named by the claim" and §E "observed on … OpenCode (child session)"; packages/fr/src/fr/run/telemetry.py:1215-1241 (`_opencode_wrote_since` deliberately reads TOP-LEVEL sessions only; "No OpenCode session id reaches fr's environment"); run_cmd.py:5163-5203 (`_claim_identity` stores an `agent` id, with no stated mapping to an OpenCode session id)
scope: the harness-parity claim is this change's; unsure whether the claimed `agent` id on OpenCode is already the child session id, so tagged in
The spec presents OpenCode child-session verification as if it generalises an existing reader, but the only reader excludes child sessions by design. It also takes no session id, so there is nothing yet for the claim to point at. Either specify how the claimed `agent` id resolves to a child session (and pin it with a test), or declare OpenCode `unobserved` for phase logs, as Hermes is, and correct §E.

<!-- fr:journal kind=review scope=spec id=spec-review created=2026-09-29T07:25:12+00:00 -->
### spec-review · review · independent spec review: 7 findings

input-coverage:
```input-coverage
| span | coverage |
|---|---|
| "/fr-goal fr-goal light path for small single-phase goals:" | R1, R2 |
| "one review dispatch," | R3 |
| "one bookkeeping call per step," | R4, R5 |
| "deliver reuses the verified suite log" | R6 |
| "" | context |
| "Batch `light-path` of derio-net/super-fr: 1 issues, delivered as ONE pull request." | context |
| "" | context |
| "## super-fr#780: fr-goal: a light path for small single-phase goals; the orchestrator's per-step bookkeeping is most of the cost gap to a plain agent" | R1, R4 |
| "Feature C (small, one phase): plain OpenCode $2.13 / 12.8 min / 83 turns; fr-goal take 9 $7.67 / 45 min / 269 turns (≈2.3× money, 2.8× time without #758). The orchestrator carries 76% (193 turns), re-reading its context per bookkeeping step; 3.6 bookkeeping turns/step on OpenCode against 1–2; fr_cli_learning 3.2%." | context |
| "Note: Operator-prioritised for the talk. Feature (fr-goal), batch `light-path` (wave 8):" | context |
| "fold plan review into spec review for one-phase plans," | R2, R3 |
| "one bookkeeping call per step," | R4, R5 |
| "deliver reuses the executor's verified suite log on an unchanged tree." | R6 |
| "Target ≤ 2× plain's cost, ≤ 2.5× its time on feature C." | R8 |
| "After phase-sizing (#745) and the wave-6 skill edits." | context |
| "" | context |
| "## Why these belong together" | context |
| "Wave 8, the ceremony tax. Take 9 (feature C, one phase) cost ≈2.3× plain's money and ≈2.8× its time without #758; the orchestrator carries 76% of it, re-reading its context on every fr run bookkeeping step." | context |
| "Target from #780: ≤ 2× plain's cost and ≤ 2.5× its time on feature C." | R8 |
| "Fold plan review into spec review for a one-phase plan;" | R2, R3 |
| "resolve+record+advance in one fr run call;" | R4 |
| "deliver reuses the executor's verified suite log when the tree is unchanged;" | R6 |
| "subagents return structured results." | R7 |
| "After phase-sizing (#745) and the wave-6 fr-goal skill edits (rebase). Take 10's plain-vs-fr gap is the benchmark." | context |
| "" | context |
| "## Delivery rules" | context |
| "- Work on branch `feat/batch-light-path`." | context |
| "- Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges:" | context |
| "  Closes derio-net/super-fr#780" | context |
| "- Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels." | context |
```
verified:
- plugins/super-fr/workflows/fr-goal.yaml:98-112 — spec-review (fr-spec-reviewer, tier hard, evidence [review, reviewer, findings, requirements, coverage]), plan, plan-review cli `fr plan self-review {{ artifacts.plan }}`
- plugins/super-fr/workflows/fr-goal.yaml:114-218 — implement group {implement-phase [visual], review-phase [review, reviewer, findings, visual]}, journal-check cli, deliver [tests, proportionality, requirement-rows, visual]
- packages/fr/src/fr/record/apply.py:831-956 — `apply_record` applies, then runs `resolve_in_process`; the outcome line carries `next:` but no brief
- packages/fr/src/fr/commands/run_cmd.py:886-889 — `_complete_step` moves the cursor to `_next_step_id` only on done and only from the cursor
- packages/fr/src/fr/commands/run_cmd.py:4155-4177 — `advance` prints the agent brief
- packages/fr/src/fr/commands/run_cmd.py:4199-4214 — the cli branch executes one step and returns; exit 1 on failure
- packages/fr/src/fr/commands/run_cmd.py:4031-4214 — `advance_cmd` body (decorated `_commits_run_writes("advance")`, 3999-4000)
- packages/fr/src/fr/commands/run_cmd.py:5042-5084 — `_resolve_with_record`
- packages/fr/src/fr/commands/run_cmd.py:2212-2313 — `_verify_tests_log` (records-dir refusal, main-thread writer window, unobserved fallback)
- packages/fr/src/fr/run/telemetry.py:993-1009 — `witness_transcript`
- packages/fr/src/fr/run/telemetry.py:1012-1034 — `orchestrator_wrote_since`
- packages/fr/src/fr/run/telemetry.py:1215 — `_opencode_wrote_since` (top-level sessions only)
- packages/fr/src/fr/commands/run_cmd.py:1452-1462 — `_evidence_target` routes a `journal:spec` emitter to the spec journal
- packages/fr/src/fr/commands/run_cmd.py:2096 and :1701 — `_verify_reviewer`, `expected_agent=step.agent` for a flat target
- packages/fr/src/fr/commands/run_cmd.py:1580-1753 — `_verified_evidence` derived-evidence dispatch
- packages/fr/src/fr/commands/run_cmd.py:1389,1405,1415 — `_VERIFIABLE_EVIDENCE`, `_DERIVED_EVIDENCE`, `_PHASE_EVIDENCE` (where `single-phase` must be added)
- packages/fr/src/fr/commands/run_cmd.py:756-806 — `_check_step_drift`
- packages/fr/src/fr/commands/run_cmd.py:734-753 — `_resolve_manifest_for_state` (`workflow` is `<name>@<schema>`)
- packages/fr/src/fr/workflow/resolve.py:151-198 — `shipped_workflow_dirs` / `resolve_workflow`; packages/fr/src/fr/workflows/README.md — the packaged copy is kept in step by test_tripwire_shipped_workflows
- packages/fr/src/fr/workflow/model.py:27,115 — `SUPPORTED_SCHEMA = 1`, `schema_version: Literal[1]`
- packages/fr/src/fr/record/model.py:216-247 — `StepRecord` (no `shape` field today)
- packages/fr/src/fr/artifacts/registry.py:441 — record kind `current_version=4`
- packages/fr/src/fr/artifacts/__init__.py:53 — record migrations registered by import (record_visual)
- packages/fr/src/fr/run/model.py:221 — unit `evidence: dict[str, str] | None`
- plugins/super-fr/agents/fr-phase-executor.md:131 — "the test command run and its pass/fail summary"; :151-154 the detached `exit=N` long-command form
- plugins/super-fr/agents/fr-spec-reviewer.md — exists
- plugins/super-fr/skills/fr-goal/SKILL.md — §5 implement and §8 deliver exist
- docs/explainers/01-fr-goal.md, docs/explainers/01-fr-goal.html — exist
- scripts/sync-opencode.py, scripts/sync-hermes.py — exist

<!-- fr:journal kind=finding scope=spec id=s1-resolved created=2026-09-29T07:25:12+00:00 state=fixed resolves=s1 -->
### s1-resolved · finding [fixed] · resolves s1: `evidence: {tests: <log>}` on implement-phase/review-phase is refused by today's evidence parser; 'no manifest change is needed' is wrong

§D now defines offered evidence (`_OFFERED_EVIDENCE = {tests}`): accepted undeclared on phase-group members, never counted missing, mandatory where declared; shipped manifests unchanged; Test Plan 3 pins a phase record without tests.

<!-- fr:journal kind=finding scope=spec id=s2-resolved created=2026-09-29T07:25:12+00:00 state=fixed resolves=s2 -->
### s2-resolved · finding [fixed] · resolves s2: §B's advance loop stops before briefing the next agent step, contradicting R4/R5

§B loop now continues while the previous call returned cli-done, ending on brief/gate/cli-failed/refused/complete; Test Plan 2 pins one advance from plan-review printing implement-phase's brief.

<!-- fr:journal kind=finding scope=spec id=s3-resolved created=2026-09-29T07:25:12+00:00 state=fixed resolves=s3 -->
### s3-resolved · finding [fixed] · resolves s3: Default auto-advance after a `failed`/`blocked` record would immediately re-brief the step that just failed

§B: only an outcome: done record chains; failed/blocked print the outcome line and stop. Test Plan 2 covers it.

<!-- fr:journal kind=finding scope=spec id=s4-resolved created=2026-09-29T07:25:12+00:00 state=fixed resolves=s4 -->
### s4-resolved · finding [fixed] · resolves s4: Decision d6's `verify: post-merge` acceptance row for the benchmark is not in the spec

Test Plan 6 states R8's row light-path-benchmark carries verify: post-merge and is listed under Post-merge verification owed (the brainstorm record already staged it so).

<!-- fr:journal kind=finding scope=spec id=s5-resolved created=2026-09-29T07:25:12+00:00 state=open resolves=s5 unconfirmed=true -->
### s5-resolved · finding [unconfirmed] · resolves s5: R8 adds a pass condition ('with delivery still verified') that neither the input nor d6 states

Built as written: the benchmark passes only when cost ≤ 2× and time ≤ 2.5× plain AND deliver's evidence gates passed on the benchmark run (not skipped), since the input's 'without losing verified delivery' framing lives in #780's issue body, not in the recorded input.

<!-- fr:journal kind=finding scope=spec id=s6-resolved created=2026-09-29T07:25:12+00:00 state=fixed resolves=s6 -->
### s6-resolved · finding [fixed] · resolves s6: The record-kind bump also needs `RECORD_SCHEMA_VERSION` in record/model.py, which refuses any other stamp

§A names RECORD_SCHEMA_VERSION 4→5 (record/model.py:54) and the optional StepRecord.shape field alongside the registry bump; Test Plan 4 loads a v5 record with shape.

<!-- fr:journal kind=finding scope=spec id=s7-resolved created=2026-09-29T07:25:12+00:00 state=fixed resolves=s7 -->
### s7-resolved · finding [fixed] · resolves s7: Observing an executor's log on OpenCode assumes a child-session lookup fr does not have

§D/§E: OpenCode phase logs are recorded unobserved=tests like Hermes (its reader is top-level only); freshness and tree checks still apply; child-session reader left for later.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-09-29-fr-goal-light-path-p2 created=2026-09-29T07:26:54+00:00 -->
### phase-split-2026-09-29-fr-goal-light-path-p2 · decision · ask: deliver reuses a verified phase suite log (R6)

Its own ask in the input; a separate review surface (telemetry/evidence gates).

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-09-29-fr-goal-light-path-p3 created=2026-09-29T07:26:55+00:00 -->
### phase-split-2026-09-29-fr-goal-light-path-p3 · decision · ask: the fr-goal-light shape and its prose (R1-R3, R7)

Its own ask in the input (fold plan review into spec review for one-phase plans).
