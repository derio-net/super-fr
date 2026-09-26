# fr-plan/fr-goal: a one-phase plan is a first-class shape

- **Date:** 2026-09-26
- **Status:** designed
- **Origin:** gh#673 (operator-flagged fix-now), gh#662 (folded in: one assertion)
- **Goal:** size phases to the change. The walking-skeleton gate only means
  something when there is work after the skeleton, so it applies to plans with
  two or more agentic phases and stops forcing small fixes into 2–3 phases.

## 1. Problem

`_skeleton_issues` (`packages/fr/src/fr/plan_ops.py`) errors on a plan with ONE
agentic phase, both ways:

- **Unmarked** — the first agentic phase carries no `skeleton: true`, so the
  gate demands a marker or an operator override.
- **Marked** — the phase carries the marker but is also the only agentic phase
  ("the skeleton IS the plan"), so the gate demands a split or an override.

The only way through is a `skeleton-override-<plan-slug>` spec decision, which
the error text and `fr-plan/SKILL.md` call an *operator* override, and
`fr-goal/SKILL.md` §3 says flatly "Phase 1 is the walking skeleton". The result
is that every small fix is planned as 2–3 phases purely to satisfy the gate:
ceremony phases whose per-phase implement → review loop tests nothing new.

The two errors were each added for a real reason (a skeleton smokes delivery
infrastructure BEFORE the expensive part; a one-phase plan wearing the marker
ran its review loop once). Both reasons presuppose a "later part". With one
agentic phase there is no later part to protect, so neither has anything to say.

## 2. Design

### 2.A The gate

`_skeleton_issues` counts agentic phases (it already does) and applies the
skeleton rule **only when there are two or more**:

| agentic phases | unmarked first | marked first | marker on a later phase |
|---|---|---|---|
| 0 | pass | pass | — |
| 1 | **pass** (was error) | **pass** (was error) | — |
| 2+ | error unless `skeleton-override-*` (unchanged) | pass | error (unchanged) |

- Manual phases never count toward the two (unchanged: they are not the work a
  skeleton de-risks). One agentic phase plus a manual phase is a one-phase plan.
- The sole-skeleton error block is deleted; the unmarked-first error gains the
  `agentic >= 2` condition; the misplaced-marker error is untouched (it can only
  fire with a marked non-first agentic phase, hence with 2+).
- A `skeleton: true` marker on a sole agentic phase is still accepted, and the
  `fr_version` floor probe still applies to it, so a marked plan cannot admit a
  pre-marker `fr`.
- The `skeleton-override-<plan-slug>` decision stays, for the 2+ case. It is no
  longer needed for one-phase plans.

### 2.B The prose

Rewrite the two statements that make the skeleton universal, in canonical
sources only, then regenerate mirrors:

- `plugins/super-fr/skills/fr-plan/SKILL.md` "Walking skeleton first": size
  phases to the change; a one-agentic-phase plan is first-class and needs no
  marker or override; with two or more agentic phases the first smokes delivery
  and is marked `skeleton: true`, and self-review errors without it (override:
  `skeleton-override-*`).
- `plugins/super-fr/skills/fr-goal/SKILL.md` §3: replace "Phase 1 is the walking
  skeleton" with the same rule.

Mirrors are generated: `scripts/sync-opencode.py` AND `scripts/sync-hermes.py`
(both, per AGENTS.md).

### 2.C #662 — one assertion

`test_create_no_table_error_names_the_header_and_creates_nothing` asserts no
plan dir is created but not that the SPEC is unmutated. Add one assertion: the
spec's bytes are identical after the raise. It stays one assertion (the
pre-flight raises before any write), so it is folded in rather than filed.

### 2.D Non-goals

No new phase-count vocabulary, no change to `PHASE_TIERS`, the refactor gate, or
`fr run` cursor semantics. No artifact shape changes, so no stamp bump or
migration. The shared one-phase fixture's `write_skeleton_override` callers are
left as harmless no-ops beyond a corrected docstring.

## 3. Test Plan

**In this PR:**

1. One agentic phase, unmarked: `self_review` raises no skeleton issue.
2. One agentic phase, marked, with and without a trailing manual phase: no
   skeleton issue (inverts the C2 tests).
3. The shared minimal fixture (one marked agentic phase) self-reviews clean.
4. Two agentic phases, first unmarked: still an error; override still silences
   it; marker on a later phase still an error (existing tests, unchanged).
5. A sole marked phase whose `fr_version` admits a pre-marker `fr` still gets
   the floor error.
6. #662: the spec is byte-identical after the no-table pre-flight raises.
7. Mirrors: both sync scripts `--check` clean; skill tripwires green.

## 4. Scope

`plan_ops.py`, `test_v2_plan_ops.py`, the two SKILL.md files and their
generated mirrors, the acceptance matrix row for the retired C2 behaviour plus a
new row, one `.changes` fragment (patch: skill copy and a CLI fix).

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-09-26-one-phase-plans | `derio-net/super-fr` | `2026-09-26-one-phase-plans` | — |
