<!-- fr:journal-schema=2 -->
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
