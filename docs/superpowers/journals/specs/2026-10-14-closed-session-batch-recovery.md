<!-- fr:journal-schema=3 -->
# Journal: 2026-10-14-closed-session-batch-recovery

<!-- fr:journal kind=discovery scope=spec id=operator-goal created=2026-10-14T17:53:47+00:00 input=true -->
### operator-goal · discovery · Operator goal and development authorization

Operator approved taking the supported closed-session recovery fix to a reviewed draft PR. You own implementation of this goal in super-fr; coordinator remains w9:pR. Invoke fr-goal FIRST and follow its full pipeline, starting fr run start in isolation with a feature branch such as feat/closed-session-batch-recovery, binding your actual session ses_ec52e48a3ffeYuGgSUiT9iZD10 and harness opencode. Goal: provide a supported, explicit recovery path for already-dispatched triage batches whose original harness sessions/panes were closed. Preserve batch identity and dispatch history, updated existing branches/worktrees and durable run cursors; audit fresh pane/session ownership; launch fresh OpenCode with --auto and model binding; never replay uncertain submission; retain all operator question/approval gates. Investigate existing restart/replace/dispatch seams to choose the smallest coherent API; comply with super-fr AGENTS.md including bridge audit before spec, isolation, acceptance rows, change fragment, tests and explainers as applicable. Use fr-goal's prescribed spec-review/phase-executor/review delegation. Heavy suites use bash ~/.cache/fr/coord/testslot.sh -- <cmd>. Operator owns design question rounds: do not answer them or default them. Bring the question round back to the coordinator as explicit questions, then hold; coordinator will pass operator answers. This approval is for developing and delivering the fix only: do NOT recover/dispatch the six real batches, mutate their triage state, restart any org loop, ready/merge PRs, add approved-fr, or access live hardware/secrets/vault. Keep existing driver stopped. Any new OpenCode session MUST use opencode --auto. Start now and continue autonomously until an operator gate, genuine blocker, or reviewed draft PR delivery. Report run ID, workspace and question gate when reached.

<!-- fr:journal kind=decision scope=spec id=recovery-hold created=2026-10-14T17:53:47+00:00 decided_by=operator -->
### recovery-hold · decision · Recovered sessions start in HOLD

Operator Q1: Start in HOLD. Reconstruct/report-only until separate operator go-ahead; no automatic cursor continuation. Confirmed through the OpenCode question tool.

<!-- fr:journal kind=decision scope=spec id=recovery-verification created=2026-10-14T17:53:47+00:00 decided_by=operator -->
### recovery-verification · decision · Automated tests and post-merge Tester walk

Operator Q2: tests and the walk, which will be at the Tester gate. Candidate tests run before delivery; the actual disposable herdr recovery walk is post-merge, operator-driven, and holds close-out. Confirmed through the OpenCode question tool.

<!-- fr:journal kind=discovery scope=spec id=bridge-audit created=2026-10-14T17:53:47+00:00 -->
### bridge-audit · discovery · Bridge audit before spec

Read all 12 fr_dispatch and all 14 fr_vk source modules end-to-end. Tick dispatches item graphs and stamps tracker projections; VK is a phase/card adapter. Closed batch session recovery belongs in the optional herdr replacement seam, with unchanged mandatory Runner and dispatch lifecycle.

<!-- fr:journal kind=finding scope=spec id=s1 created=2026-10-14T18:00:50+00:00 state=open review_scope=in -->
### s1 · finding [open] (reviewer: in scope) · Persist recovery intent before allocating a pane

check: consistency
target: spec
evidence: Spec Ownership and persistence, lines 93–98; R7; packages/fr-herdr/src/fr_herdr/runner.py:426–444,449–472; packages/fr-herdr/src/fr_herdr/managed.py:77–90; packages/fr-herdr/src/fr_herdr/runner.py:261–280.
scope: In scope because fresh-pane allocation introduces an uncertain side-effect boundary that the promised recovery and no-duplicate guarantees must cover.
The spec requires durable discoverability once a pane is allocated, but only explicitly orders attempt persistence before launch, leaving allocation-before-first-write undefined: herdr can create a tab and then lose its response, or the process can stop before saving its pane-keyed descriptor. Existing allocation returns ownership only after the external effect, and existing pending lookup requires a known pane, so neither establishes repair discovery across that gap. Specify durable intent keyed by original item/source identity before allocation, plus fail-closed reconciliation of uncertain allocation through fresh labelled-tab observations without another allocation or prompt; add candidate failures between allocation effect, response parsing and the first target-descriptor write.

<!-- fr:journal kind=review scope=spec id=spec-review created=2026-10-14T18:00:50+00:00 -->
### spec-review · review · independent spec review: 1 finding

Independent reviewer honoured recovery-hold and recovery-verification decisions.
Verified _replacement_live_gate/_replacement_transaction/batch_replace_command;
ReplacementRequest/ReplacementResult/ReplacementOperation/SessionReplacer;
fr_dispatch.tick and frozen WorkItem; VK phase-unit adapter;
Operation's single submission, checkpoints and persisted-uptake reconciliation;
agent_name/stable_checkout/_open_tab/replacement_pending and roster defaults;
Descriptor/pane_lock/branch_workspace/reconstruct; launch_args/model_matches/wait_ready;
ReplacementEvent and last_dispatch/recorded_branch/lifecycle_events.
Uncertain submission semantics otherwise agree across R6/R7 and the design: no replay, no automatic second launch, and repair success requires persisted uptake plus matching live ownership. No plan was reviewed. Render/drive unification (#1216) was excluded; no commands, harnesses, hardware, secrets or real batch state were accessed.

<!-- fr:journal kind=finding scope=spec id=s1-resolved created=2026-10-14T18:00:50+00:00 state=fixed resolves=s1 -->
### s1-resolved · finding [fixed] · resolves s1: Persist recovery intent before allocating a pane

R7 and Ownership/persistence now explicitly require source/item-keyed durable intent before allocation, labelled-tab reconciliation of lost responses, no reallocation on unknown truth, and tests across allocation-effect/response/first-descriptor/batch-write boundaries. Repair never allocates, launches or prompts.

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-10-14T18:00:51+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates:
  triage-closed-recovery: tester
  triage-closed-recovery-live: tester
  triage-closed-recovery-refusals: tester
  triage-closed-recovery-repair: tester
row_kinds:
  triage-closed-recovery: candidate
  triage-closed-recovery-live: live
  triage-closed-recovery-refusals: candidate
  triage-closed-recovery-repair: candidate
run_gate: tester
run_kind: candidate
```

<!-- fr:journal kind=decision scope=spec id=tier-2026-10-14-closed-session-batch-recovery-p1 created=2026-10-14T18:02:46+00:00 -->
### tier-2026-10-14-closed-session-batch-recovery-p1 · decision · hard: allocation ownership and uncertain-submission concurrency

One coherent recovery ask; hard tier because durable pre-allocation intent, source/target locks and cross-store reconciliation must preserve no-replay gates.
