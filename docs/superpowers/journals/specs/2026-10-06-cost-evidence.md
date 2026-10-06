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
