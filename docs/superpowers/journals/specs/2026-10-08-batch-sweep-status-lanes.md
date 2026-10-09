# Journal: 2026-10-08-batch-sweep-status-lanes

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-10-09T04:36:03+00:00 input=true -->
### operator-brief · discovery · Operator brief

Implement derio-net/super-fr#1086 end to end: add Needs you start/review lanes driven by run cursors at the batch PR head; never call conflicting or dirty PRs merge ready; relay conflicts and red CI to the batch session once per head; verify through the candidate strategy; deliver a draft PR and never merge it.

<!-- fr:journal kind=decision scope=spec id=d1-human-lanes created=2026-10-09T04:36:03+00:00 -->
### d1-human-lanes · decision · Two explicit operator-attention lanes

Add Needs you · start for pre-PR gates and idle unfinished runs, and Needs you · review for completed draft delivery, manual phases, exhausted merge stops, and operator close-out work. Conflict and red CI remain agent work while a session can be prompted. Decider: operator.

<!-- fr:journal kind=decision scope=spec id=d2-cursor-source created=2026-10-09T04:36:03+00:00 -->
### d2-cursor-source · decision · Read run state from the PR head

Use the batch PR's changed docs/superpowers/runs/*.yaml files and Checkout.show(head_oid, path); do not inspect the host triage cache or infer questions from session prose. Missing or malformed cursor data fails soft to existing lifecycle behavior. Decider: operator.

<!-- fr:journal kind=decision scope=spec id=d3-session-relay created=2026-10-09T04:36:03+00:00 -->
### d3-session-relay · decision · Relay through the canonical optional runner protocol

Use fr_dispatch.protocols.SessionMessenger with the existing batch WorkItem, once per head OID, and retain the standing batch-branch, push, and never-merge boundaries. Do not add a harness-specific messaging path. Decider: operator.

<!-- fr:journal kind=decision scope=spec id=d4-verification created=2026-10-09T04:36:03+00:00 -->
### d4-verification · decision · Candidate verification

Verify all acceptance rows with a candidate walk and tests/scenarios/triage-batch-status-lanes.sh; there is no post-merge-only test plan. Decider: operator.

<!-- fr:journal kind=decision scope=spec id=d5-mechanical-model created=2026-10-09T04:36:03+00:00 -->
### d5-mechanical-model · decision · OpenCode mechanical model binding

Old: unbound. New: openai/gpt-6.1-sol-fast. Reason: upgrade. Decider: operator. Rule: use the selected OpenCode tier binding for autonomous phase dispatch.

<!-- fr:journal kind=decision scope=spec id=d6-standard-model created=2026-10-09T04:36:03+00:00 -->
### d6-standard-model · decision · OpenCode standard model binding

Old: unbound. New: openai/gpt-6.1-sol. Reason: upgrade. Decider: operator. Rule: use the selected OpenCode tier binding for autonomous phase dispatch.

<!-- fr:journal kind=decision scope=spec id=d7-hard-model created=2026-10-09T04:36:03+00:00 -->
### d7-hard-model · decision · OpenCode hard model binding

Old: unbound. New: openai/gpt-6.1-sol. Reason: upgrade. Decider: operator. Rule: use the selected OpenCode tier binding for autonomous phase dispatch.

<!-- fr:journal kind=decision scope=spec id=gate-question-rounds-brainstorm created=2026-10-09T04:36:12+00:00 -->
### gate-question-rounds-brainstorm · decision · Operator gate `brainstorm` took two question rounds

Trigger: operator-request. The operator supplied replacement OpenCode model choices after the first selection was rejected by the provider; that unannounced follow-up was recorded as round 2.
