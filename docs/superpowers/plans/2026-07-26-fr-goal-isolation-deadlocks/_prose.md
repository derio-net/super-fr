# 2026-07-26-fr-goal-isolation-deadlocks

Fixes derio-net/super-fr#420 and #421 — two hooks that each deadlock fr-goal,
at different steps, for unrelated reasons. Spec:
`docs/superpowers/specs/2026-07-26-fr-goal-isolation-deadlocks-design.md`.

## Why one plan for two issues

Distinct root causes in distinct files, but both gate **fr-goal itself** — #420
poisons §6's per-phase dispatch, #421 blocks §3's cross-repo dispatch — so they
ship together rather than leaving fr-goal half-fixed between two merges.
Phase 1/2 (#420) and phase 3 (#421) are independent; phase 3 carries no
`depends_on`, so its RED/GREEN cycle can run whenever.

## Phase shape

| Phase | Issue | Deliverable |
|---|---|---|
| 1 | #420 | `fr-phase-executor-guard.sh` + registration + behavioural tests |
| 2 | #420 | agent `description:`, fr-goal §6, org-hook stderr repair, tripwire |
| 3 | #421 | target-scoped `cd` allowance + composable `fr isolation` match |
| 4 | both | acceptance flips, minor version bump, full-suite gate |

Every implementation phase is TDD: the RED task writes the tests and confirms
they fail for the right reason before the GREEN task touches the surface under
test. Phase 4 depends on all three so the acceptance rows flip only against
tests that actually exist.

## The two things easiest to get wrong

**Phase 1 — the refusal must be unconditional.** The issue's checklist says
"while a pipeline sentinel is live", but `fr-pipeline-sentinel.sh` writes *no*
sentinel when the session cwd is a linked worktree — precisely where an fr-goal
session lives after §1. Gating on the sentinel would leave the backstop silent
in the very shape it exists to catch. Spec decision 2.

**Phase 3 — the new allowance must not weaken the old guard.** The whole of
`TestCdTransitionAllowance` and `TestBootstrapAllowance` must stay green, and
phase 3's own tests fence the boundary in both directions: a `cd` into a
*different* git repo is allowed, a `cd` back into the pipeline's own repo is
still denied, and only a *leading* `cd` is ever stripped, so
`test_non_leading_cd_denied` continues to hold.

## Explicitly not in scope

Per-repo sentinels, bringing the org `agent-worktree-*` files under version
control, and turning the guard into a security boundary. See the spec's
Non-goals — each is declined for a stated reason, not overlooked.
