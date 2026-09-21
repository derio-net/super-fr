# One record per unit — implementation plan

Spec: `docs/superpowers/specs/2026-09-20-unit-record-unification-design.md`
Delivers in PR #508, on `feat/phase-holder-identity`. Absorbs #430 (via gh#517's branch),
#518, and the cost-attribution half of #464; #496, #499, #500, #501 and #503 are already on
the branch.

## What this plan builds

`StepRecord.units` — one `UnitRecord` per unit, holding its attempts — replaces `items`,
`dispatch` and top-level `accounting`. Each attempt carries who held it, which session
dispatched it, what it was estimated to cost and what it measurably burned. A review unit
cannot reach `done` without journal evidence. `fr run check --idle` tells an advanceable,
unattended run from every legitimate stop, and a guard acts on it as strongly as each harness
allows.

## Why seven phases, when fr-plan prefers four to six

Because the alternative is one phase nobody can review. Collapsing three maps into one breaks
every reader at once, and `run_cmd.py` alone is ~2,300 lines. So the rewrite is **staged so
that no phase ends red**:

- **Phase 1 gets the branch green first.** It folds in gh#517, applies decision u1 (the
  dispatch record is the only witness) *within the current shape*, and captures real cursors
  as fixtures. Nine tests are red on the branch today by design; this phase ends that. The
  witness predicate survives the collapse unchanged — it just reads a different map later —
  so nothing here is throwaway.
- **Phase 2 changes no behaviour at all.** It ports every reader and writer to a small
  accessor layer over the OLD shape, and adds the new models, the frozen legacy reader and
  the 4 → 5 rewrite as a *pure function* — none of it wired. Its exit criterion is a grep:
  outside the accessor module, nothing touches `.items`, `.dispatch` or `.accounting`.
- **Phase 3 is the flip**, and phase 2 is what makes it small: re-implement the accessors,
  swap the model, register the migration, bump the registry. One shipped shape, one shipped
  migration — decision u4 is about what *ships*, not about how many commits it takes.
- **Phases 4, 5 and 6 are independent of each other** (each depends only on 3): cost
  semantics, the evidence gate, liveness. They run serially in one worktree, but a finding
  in one does not block the others.
- **Phase 7 is the prose**, which gh#494 taught is the actual gate.

Phases 1, 3 and 6 are tiered `hard`. Phase 1 is a merge needing judgement; phase 3 is the
one place a mistake corrupts every in-flight cursor on every node; phase 6 ships a hook, and
a hook that blocks wrongly leaves an operator unable to end a turn.

## The fixtures are captured, not constructed

This repo already holds real run cursors at **every** version: archived ones frozen at v1,
v2 and v3 under `docs/superpowers/implemented/runs/`, and live v4 ones — including this
run's own, which carries all three maps. Phase 1 copies them byte-for-byte into
`tests/fixtures/run_cursors/`. The legacy reader, the rewrite and the full chain
`[2, 3, 4, 5]` are all tested against files fr really wrote.

## The flaw this plan exists to not repeat

Every existing run migration "parses first, refuses rather than certifies" — with the LIVE
model. That was sound only while every change was additive. This one removes fields from an
`extra="forbid"` model, so without a frozen legacy reader the chain would refuse every old
cursor at its first hop. Phase 2 freezes `RunStateV4`; phase 3 moves every migration onto
it; a tripwire pins the frozen source so nobody edits it later.

## Working rules, each learned on this branch

- **Exit codes come from files, never pipes** — `pytest … | tail` exits with tail's status —
  and **`set -e` is inert** in the harness's Bash tool (the script is eval'd as the left
  operand of `&&`). Check `rc` explicitly.
- **Declare the harness in tests** (`FR_HARNESS`); run the suite with `CLAUDE*` unset. Three
  tests once passed only because the authoring machine was a Claude Code session.
- **Merge the matrix by row block**, never by text hunk; then `fr validate artifacts`, whose
  strict loader catches the duplicate key `safe_load` hides.
- **Two mirror generators**, `sync-opencode.py` and `sync-hermes.py`. Always both.
- **Long commands run in the background with a bounded wait**, and nothing is left running
  at handback — the defect #503 began with.
- **Verify a harness claim on the binary.** Phase 6 captures what a `Stop` hook really
  receives before building on it.

## Not plan steps, on purpose

Closing #517 as superseded and adding `Closes #430` to #508 are the orchestrator's, after
phase 1's review — an executor should not close a PR before its merge has been reviewed.
The post-merge Test Plan (spec §6, items 16-18, plus #508's 13-15) is operator-driven.
