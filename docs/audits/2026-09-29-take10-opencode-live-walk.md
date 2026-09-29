# Live walk: wave 5/6 Test Plans in two recorded /fr-goal runs on OpenCode + GitLab (take 10 of super-fr-3)

**Date:** 2026-09-29. **fr:** 4.35.0 (origin/main `274ba2cd` + #794). **Harness:** OpenCode 1.18.32 on macOS.
**Isolation:** devcontainer (profile `dev`). **Forge:** self-hosted GitLab with no CI.

**The fr-profiles file:** v2 (#774) with `ci: {type: none}` and `tracking: {type: none}`. The base was produced by
`fr migrate artifacts` on the demo repo's v1 file, which inferred `ci: none` and `tracking: gitlab`. The operator then
set `tracking` to `none`.

**The feature:** one phase: a whole-basket weight check at self-checkout, with an API and a basket mode in the demo
UI. The brief was issue-shaped, with explicit UI acceptance criteria. The operator answered only from a fixed answer
sheet.

| | run A | run B |
|---|---|---|
| models | orchestrator, hard tier and reviewers gpt-6-sol (default variant); mechanical and standard gpt-6-luna (high) | gpt-6-luna (high) everywhere |
| effective | **all sol**: the plan chose `tier: hard` (#813), and review-phase went to `general` on the session model | all luna high |
| delivery | $5.91 · 29.7 min · 220 turns · 4 sessions | $1.38 · 81.6 min · 555 turns · 18 sessions (13 spec-review dispatches) |
| closeout (fresh session, `fr pickup --run`) | $0.25 · 3.1 min | $0.01 · 2.8 min |
| operator input | prompt; 1 prose question round (4 questions) | prompt; 2 question-tool rounds (2 + 2) |

For comparison, **a plain agent with no fr** delivered the same brief for $0.15 / 15.0 min on luna-high and for $2.13 /
12.8 min on sol.

The evidence is outside this repo, in the super-fr-3 project: `runs/frgoal/attempt-17/notes/evidence-A/` and
`runs/frgoal/notes/evidence-B/`. Each holds the opencode.db, a docs snapshot, measure output and a findings table.

## Verdicts per Test Plan item

| Item | A | B | Notes / issue |
|---|---|---|---|
| **visual-evidence-live-run** (#789/#779; owed) | PARTIAL | PARTIAL | Checks 1–3 are enforced and deliver's freshness refusal worked (A). But every witness is `unobserved` on OpenCode (#797), and the review records list the **orchestrator's** shots, not the reviewer's. The row stays `not-implemented`. |
| **#792** phase sizing (owed) | PASS | PASS | One phase; self-review passed; "1 agentic phase serves N of N". The single-phase prompt suppresses the split path. The stray "none." line is #815. |
| **#794** services (owed) | PASS | PASS | `fr services`: ci and tracking `none`, declared. No pipeline scaffolded; `set-status ci` refused; no issue-filing lines. The v1 → v2 migration was observed on a scratch clone before the runs. |
| **#790/#733** closeout | PASS with defects | PARTIAL | `fr pickup --run` fails in a base clone that isn't pulled yet (#811). B's fallback `--branch` gives `chore/closeout-*`. Scratch plan inputs are `held:` (#812). Archive leaves the matrix `levels` ref to the plan stale, so `fr acceptance check` fails after closeout (#528). The lock file blocks `isolation down`, and the housekeeping workspace is never downed (#610). |
| **#772/#758** `tests=` log | PASS | PASS | B exercised the `/tmp` → `/private/tmp` symlink case. |
| **#784/#783** question rounds | PASS | PASS | A used the labelled prose fallback, B the question tool. B's round 2, triggered by spec review, is recorded nowhere (#810), and its brainstorm gate says `answered_by: agent` (#809). |
| **#786/#776** requirements grammar | PARTIAL | PARTIAL | The grammar works. The pre-check refuses citations that the same resolve writes, and Deferred-section errors are mislabelled (comment on #776). |
| **#788/#777** coverage as returned | PASS | **FAIL** | B's orchestrator re-cut the reviewer's partition (93 → 94 spans, 3 relabels), which is invisible on OpenCode (comment on #777). The review loop is #808. |
| **#787/#775** acceptance init without CI | PARTIAL/FAIL | PARTIAL | The no-CI half works. Init's `.gitignore` and `.claude/rules` edits were not committed in A (closeout stashed them), and B only committed them because the orchestrator did it by hand. Process-directive rows remain (comment on #775). |
| **#791/#778** raw input to children | PARTIAL | PASS/PARTIAL | The briefs carry `operator_input`. A's orchestrator replaced it with a pointer (0 hits of brief phrases in the child prompts), and B's re-reviewers got none (comment on #778). |
| **bookkeeping-turns-per-step** | FAIL (6.75) | FAIL (~24) | The target is ≤ 2 (comment on #780). fr captured no per-step cost on OpenCode (comment on #636). |
| **acceptance-pipeline-rows** | PARTIAL | PARTIAL | Rows are born at brainstorm and linked in the plan, but flipped by the orchestrator at deliver, not at execution. |
| **run-idle-reprompt-opencode** | not observed | not observed | No mid-run idle happened. |

## Defects filed or updated

**New:**
- #808 spec-review re-dispatch loop, with no divergence named and no cap;
- #809 OpenCode question tool and `answered_by: agent`;
- #810 an unrecorded operator round from spec review;
- #811 pickup and status in a base clone that isn't pulled;
- #812 scratch inputs for `plan create`, and the misleading "must be migrated";
- #813 no tier criteria;
- #814 the operator's review approval, and the closeout line not relayed;
- #815 two misleading output lines;
- #816 a fabricated reviewer id and dropped findings.

**Evidence added:**
- #777, #778, #775, #610, #636 and #776: closed, but their stated expectations aren't met in these runs, so each comment
  suggests reopening;
- #528, #780 and #797: open.

## Matrix rows touched

Notes only; no status moved:
- `visual-evidence-live-run`
- `bookkeeping-turns-per-step`
- `closeout-branch-live-run`
- `requirements-spec-review-traceability`
- `acceptance-pipeline-rows`
- `fr-goal-main-session-cost`

Each note gains the take-10 OpenCode/GitLab evidence. None of the owed walks passed completely, so the statuses stay
where they were. The commits read "X → X" (#769).
