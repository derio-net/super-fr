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

<!-- fr:journal kind=finding scope=spec id=sr-1 created=2026-11-01T11:58:54+00:00 state=open review_scope=in -->
### sr-1 · finding [open] (reviewer: in scope) · Stage 1 has no way to read the PR head's spec/plan/matrix before the ops workspace exists

check: codebase/consistency
target: spec
evidence: GateHost has no show/list; OpsTree.show exists only after isolation up (gate.py:71-112, 632-636); gap inputs are path-based (exit.py:100-136, load.py:181-223,308-319). R5's 'nothing brought up' has no mechanism.

<!-- fr:journal kind=finding scope=spec id=sr-2 created=2026-11-01T11:58:54+00:00 state=open review_scope=in -->
### sr-2 · finding [open] (reviewer: in scope) · The runner protocol returns only the probe's last stdout line, not its output (R9)

check: codebase/consistency
target: spec
evidence: ShellRunner keeps lines[-1] (engine.py:5,33-34,93-102); sanitise_reason blanks body-shaped/long lines (mask.py:67-89).

<!-- fr:journal kind=finding scope=spec id=sr-3 created=2026-11-01T11:58:54+00:00 state=open review_scope=in -->
### sr-3 · finding [open] (reviewer: in scope) · R8 leaves N/A, ESCALATE and non-check DONE unhandled; status exit codes and trust skipped

check: codebase/consistency
target: spec
evidence: State includes N/A/ESCALATE (engine.py:29,177-183); DONE can be legacy/proof/attested (engine.py:150-174); STATUS_OK_CODES 0,1,3 (gate.py:56); gate.trust only in apply_phase (gate.py:382-391,537).

<!-- fr:journal kind=finding scope=spec id=sr-4 created=2026-11-01T11:58:54+00:00 state=open review_scope=in -->
### sr-4 · finding [open] (reviewer: in scope) · Stub ops (no check, apply = first command) cannot close a step as ran, or close it with false evidence; stage 4 runs their apply

check: codebase/consistency
target: spec
evidence: apply_phase runs apply for non-DONE post-merge ops and needs attestation for UNVERIFIABLE (gate.py:542-565); mutating defaults False (model.py:49).

<!-- fr:journal kind=finding scope=spec id=sr-5 created=2026-11-01T11:58:54+00:00 state=open review_scope=in -->
### sr-5 · finding [open] (reviewer: in scope) · R2's fenced-block detection does not survive test_plan_steps' line joining

check: codebase/consistency
target: spec
evidence: test_plan_steps joins item lines with spaces (spec.py:547-567); a fence becomes one span with the info string as first word; bare-word regex accepts any prose span.

<!-- fr:journal kind=finding scope=spec id=sr-6 created=2026-11-01T11:58:54+00:00 state=open review_scope=in -->
### sr-6 · finding [open] (reviewer: in scope) · R1 counts every Test Plan step, including [tester]-tagged ones

check: codebase/consistency
target: spec
evidence: A literal [tester] tag wins (testplan.py:16-29); stage 5 only walks devops steps (holds.py:103-122).

<!-- fr:journal kind=finding scope=spec id=sr-7 created=2026-11-01T11:58:54+00:00 state=open review_scope=in -->
### sr-7 · finding [open] (reviewer: in scope) · Spec-review hook hard-codes has_plan=False (wrong on fr-goal-light); exit function unnamed

check: codebase/consistency
target: spec
evidence: spec_review_steps returns spec-plan-review on the light shape (baseline.py:173-189); exit_for_spec vs run_exit (exit.py:90-136).

<!-- fr:journal kind=finding scope=spec id=sr-8 created=2026-11-01T11:58:54+00:00 state=open review_scope=in -->
### sr-8 · finding [open] (reviewer: in scope) · ReviewIssue has no `warning` severity; the literal is `warn`

check: codebase/consistency
target: spec
evidence: plan_ops.py:1305-1311 Literal['info','warn','error'].

<!-- fr:journal kind=finding scope=spec id=sr-9 created=2026-11-01T11:58:54+00:00 state=open review_scope=in -->
### sr-9 · finding [open] (reviewer: in scope) · R10's regex never matches a bare `retry`; a closed terminal is indistinguishable from an empty line

check: codebase/consistency
target: spec
evidence: Mandatory separator group; TtyPrompt.ask returns '' for no tty and empty line (apply.py:72-82).

<!-- fr:journal kind=finding scope=spec id=sr-10 created=2026-11-01T11:58:54+00:00 state=open review_scope=in -->
### sr-10 · finding [open] (reviewer: in scope) · No Verification row covers the stage-1 refusal, pointer, probes, output field or R10 grammar

check: codebase/consistency
target: spec
evidence: Verification lists four override lines only.

<!-- fr:journal kind=finding scope=spec id=sr-11 created=2026-11-01T11:58:54+00:00 state=open review_scope=in -->
### sr-11 · finding [open] (reviewer: in scope) · Recording 2000 chars of probe output as committed evidence widens the third-party leak surface

check: codebase/consistency
target: spec
evidence: mask.py masks secret values only (mask.py:1-8,52-64); stage evidence is committed and pushed (gate.py:417-433).

<!-- fr:journal kind=finding scope=spec id=sr-12 created=2026-11-01T11:58:54+00:00 state=open review_scope=in -->
### sr-12 · finding [open] (reviewer: in scope) · `none:` can sit beside `# manual-operation` step blocks; a hand-added `none:` can carry a v1 stamp

check: codebase/consistency
target: spec
evidence: plan_has_ops true for step blocks alone (load.py:308-319); OpsFile.schema_version defaults to 1 (model.py:160-166).

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-11-01T11:58:54+00:00 -->
### spec-review-1 · review · independent spec review: 12 findings, all in scope

fr-spec-reviewer raised sr-1..sr-12 (all in scope); decisions q1-q6 confirmed honoured; the trust subset question, `(op:)` collisions and the Verification grammar were checked clean. All twelve fixed in the spec.

<!-- fr:journal kind=finding scope=spec id=sr-1-resolved created=2026-11-01T11:58:54+00:00 state=fixed resolves=sr-1 -->
### sr-1-resolved · finding [fixed] · resolves sr-1: Stage 1 has no way to read the PR head's spec/plan/matrix before the ops workspace exists

R5 + §A now materialise the PR head into a scratch tree via a new GateHost.materialise(ref, paths) (`git archive`) before isolation up; the fake host implements it too.

<!-- fr:journal kind=finding scope=spec id=sr-2-resolved created=2026-11-01T11:58:54+00:00 state=fixed resolves=sr-2 -->
### sr-2-resolved · finding [fixed] · resolves sr-2: The runner protocol returns only the probe's last stdout line, not its output (R9)

R9 + §C: ShellRunner returns full stdout; engine derives last_line itself (one-line fakes unchanged); new mask.clip_output/evidence_lines keep lines, mask secret values, bounded.

<!-- fr:journal kind=finding scope=spec id=sr-3-resolved created=2026-11-01T11:58:54+00:00 state=fixed resolves=sr-3 -->
### sr-3-resolved · finding [fixed] · resolves sr-3: R8 leaves N/A, ESCALATE and non-check DONE unhandled; status exit codes and trust skipped

R8 now: gate.trust(tree) first; exit 0/1/3 are reports, 2 fails the stage; ran auto-recorded only for DONE how=checked; ESCALATE joins the failing set; N/A or non-check DONE asks the usual question.

<!-- fr:journal kind=finding scope=spec id=sr-4-resolved created=2026-11-01T11:58:54+00:00 state=fixed resolves=sr-4 -->
### sr-4-resolved · finding [fixed] · resolves sr-4: Stub ops (no check, apply = first command) cannot close a step as ran, or close it with false evidence; stage 4 runs their apply

R11: stubs carry mutating: true and check: TODO (reserved sentinel: status reports UNVERIFIABLE 'write a real probe', self-review errors, R7); a step reaches ran once a real probe passes.

<!-- fr:journal kind=finding scope=spec id=sr-5-resolved created=2026-11-01T11:58:54+00:00 state=fixed resolves=sr-5 -->
### sr-5-resolved · finding [fixed] · resolves sr-5: R2's fenced-block detection does not survive test_plan_steps' line joining

R2 + §A: Step keeps raw lines; each fenced line is one command (info string dropped); inline spans need a shipped ops-tool first word, a path, or a flag/path argument; false-positive class stated beside the none: escape.

<!-- fr:journal kind=finding scope=spec id=sr-6-resolved created=2026-11-01T11:58:54+00:00 state=fixed resolves=sr-6 -->
### sr-6-resolved · finding [fixed] · resolves sr-6: R1 counts every Test Plan step, including [tester]-tagged ones

R1 counts only steps whose effective gate is devops (steps_gated); command_steps takes exit_gates.

<!-- fr:journal kind=finding scope=spec id=sr-7-resolved created=2026-11-01T11:58:54+00:00 state=fixed resolves=sr-7 -->
### sr-7-resolved · finding [fixed] · resolves sr-7: Spec-review hook hard-codes has_plan=False (wrong on fr-goal-light); exit function unnamed

R3 + §A: hook uses run_plan_dir when the run has a plan; self-review/stage 1 use exit_for_spec, the hook run_exit; SectionError/AcceptanceError/OpsLoadError swallowed by the advisory callers.

<!-- fr:journal kind=finding scope=spec id=sr-8-resolved created=2026-11-01T11:58:54+00:00 state=fixed resolves=sr-8 -->
### sr-8-resolved · finding [fixed] · resolves sr-8: ReviewIssue has no `warning` severity; the literal is `warn`

R3 and §A now say `warn`.

<!-- fr:journal kind=finding scope=spec id=sr-9-resolved created=2026-11-01T11:58:54+00:00 state=fixed resolves=sr-9 -->
### sr-9-resolved · finding [fixed] · resolves sr-9: R10's regex never matches a bare `retry`; a closed terminal is indistinguishable from an empty line

R10 + §C: separator grammar rewritten (end of input allowed, retry bare); every empty answer counts as a non-match and is re-prompted; three consecutive non-matches fail; tests pin retry, rancid, na-ive, empty.

<!-- fr:journal kind=finding scope=spec id=sr-10-resolved created=2026-11-01T11:58:54+00:00 state=fixed resolves=sr-10 -->
### sr-10-resolved · finding [fixed] · resolves sr-10: No Verification row covers the stage-1 refusal, pointer, probes, output field or R10 grammar

Clarified: ops-gate-gap-refusal, ops-gate-step-probe and ops-gate-answer-grammar carry no override and so take the run-level candidate strategy + scenario (rows exist from brainstorm); R7 sits with ops-gap-advisory. Verification prose now names them.

<!-- fr:journal kind=finding scope=spec id=sr-11-resolved created=2026-11-01T11:58:54+00:00 state=fixed resolves=sr-11 -->
### sr-11-resolved · finding [fixed] · resolves sr-11: Recording 2000 chars of probe output as committed evidence widens the third-party leak surface

R9: screen shows up to 40 lines; only `evidence` (last ≤3 non-blank lines, ≤300 chars) is recorded; docs/ops.md states the privacy consequence and asks probes to end with a summary line.

<!-- fr:journal kind=finding scope=spec id=sr-12-resolved created=2026-11-01T11:58:54+00:00 state=fixed resolves=sr-12 -->
### sr-12-resolved · finding [fixed] · resolves sr-12: `none:` can sit beside `# manual-operation` step blocks; a hand-added `none:` can carry a v1 stamp

R4 + §B: none: with step blocks is refused by name (ops_none raises); validate_ops refuses none: under a stamp below 2.

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-01T11:58:56+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates:
  ops-gap-advisory: none
  ops-gate-answer-grammar: none
  ops-gate-gap-refusal: none
  ops-gate-probes-first-real-use: none
  ops-gate-step-probe: none
  ops-none-acknowledgement: none
  ops-stub-cli: none
row_kinds:
  ops-gap-advisory: none
  ops-gate-answer-grammar: candidate
  ops-gate-gap-refusal: candidate
  ops-gate-probes-first-real-use: live
  ops-gate-step-probe: candidate
  ops-none-acknowledgement: none
  ops-stub-cli: none
run_gate: none
run_kind: candidate
```

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-01-ops-gate-probes-p2 created=2026-11-01T12:01:50+00:00 -->
### phase-split-2026-11-01-ops-gate-probes-p2 · decision · ask: stage-5 probes, probe output and the answer grammar are their own ask (#1273 part 2 + the _ANSWER bug)
