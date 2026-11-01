<!-- fr:journal-schema=3 -->
# Journal: 2026-11-01-ops-gate-probes

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-11-01T11:48:01+00:00 input=true -->
### operator-brief · discovery · Operator brief: super-fr#1273 via coordinator goal file

Goal brief (coordinator goal file, gist): implement super-fr#1273 — (1) warn when a devops gate has no ops, at fr-plan/plan review, spec review and gate stage 1, when Test Plan steps contain commands; (2) let a Test Plan step carry or point at a probe so stage 5 runs it, shows DONE/OPEN with output, records it as `ran` evidence, asking only about probe-less steps; (3) fr-plan guidance to split runnable steps (ops with stubs) from physical/judgement steps (prose). Plus: stage 5's `_ANSWER` rejects `ran: …` — accept optional `:`/`-`, re-prompt on non-match, echo what was received with the grammar. Settle in the spec whether stage 1 refuses (vs warns) without ops or an explicit `ops: none` acknowledgement.

Issue #1273 (title): "fr ops gate: a devops-gated run with no ops degrades to prose prompts — warn on runnable Test Plan steps, let stage 5 run probes (+ stage 5 rejects `ran: …`)". Evidence from a private infra repo (identity redacted): spec `gate: devops`, 7-step Test Plan, plan 0 ops; 4 of 7 steps scriptable (IaC converge, config playbook, verify playbook, pinned-ref check); probes would have caught a missing backend login in the ops profile, SSH keys missing for some groups, an archived base image. Nothing flagged the mismatch.

<!-- fr:journal kind=decision scope=spec id=q1 created=2026-11-01T11:48:01+00:00 decided_by=operator -->
### q1 · decision · Stage 1 refuses an ops gap unless acknowledged

Refuse (exit 2, nothing brought up) when gate devops + 0 ops + command steps, unless ops exist or `none:` is acknowledged. Plan self-review and spec review only warn. (spec R3, R5)

decider: operator (round 1)

<!-- fr:journal kind=decision scope=spec id=q2 created=2026-11-01T11:48:01+00:00 decided_by=operator -->
### q2 · decision · The acknowledgement lives in the plan's ops.yaml

`ops.yaml` `none: <reason>` with an empty op list, not a spec Verification line. Consequence: `ops` artifact kind 1→2 with stamp migration + validator. (spec R4)

decider: operator (round 1)

<!-- fr:journal kind=decision scope=spec id=q3 created=2026-11-01T11:48:01+00:00 decided_by=operator -->
### q3 · decision · A step points at an op; no inline check

`(op: <id>)` leading the step text; stage 5 runs that op's check through fr ops status, reusing trust/env/masking. Inline step `check:` rejected. (spec R6)

decider: operator (round 1)

<!-- fr:journal kind=decision scope=spec id=q4 created=2026-11-01T11:48:01+00:00 decided_by=operator -->
### q4 · decision · DONE records, OPEN asks retry/na/owed

A passing probe records `ran` with its masked, clipped output, no question; a failing probe shows its reason and asks `retry`, `na <reason>` or `owed <why>`; `ran` is refused for a failing probe. (spec R8)

decider: operator (round 1)

<!-- fr:journal kind=decision scope=spec id=q5 created=2026-11-01T11:48:01+00:00 decided_by=operator -->
### q5 · decision · New `fr ops stub` CLI generates op stubs

`fr ops stub [--plan] [--yes]` proposes ops.yaml stubs + step pointers for command steps; dry-run by default. fr-plan prose points at it. (spec R11, R12)

decider: operator (round 1)

<!-- fr:journal kind=decision scope=spec id=q6 created=2026-11-01T11:48:01+00:00 decided_by=operator -->
### q6 · decision · Verification: candidate, no gate

Strategy candidate (new scenario fr-ops-gate-probes.sh); gate none; the real-use walk is a post-merge Test Plan row with a cost line, walked on first real use, no close-out hold. (spec Verification, Test Plan)

decider: operator (round 1)
