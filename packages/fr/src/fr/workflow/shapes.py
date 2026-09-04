"""The shapes fr dispatches at today, expressed as data (spec §4.A/§4.E).

`fr apply --to <runner>` and the VK/cncd bridge have always dispatched one
work item per plan phase, and have always refused to do so unless the plan
and spec were merged to `origin/HEAD` (the 2026-05-17 reachability-gate
design). Both facts were hardcoded. This module writes the second one down
as the *first* one's consequence: a manifest whose single step `needs`
the spec and the plan, so the gate is `required_inputs` of a real shape
rather than a special case in `apply_cmd`.

It is a manifest, not a constant list of paths, precisely so the derived
rule has something to derive from before Phase 11 wires real shape
resolution into `fr-goal`. Replace the constant with `resolve_workflow(...)`
there; nothing that consumes it needs to change.
"""

from __future__ import annotations

from fr.workflow.model import WorkflowManifest, parse_manifest

__all__ = ["FR_GOAL_PHASE_DISPATCH", "FR_GOAL_PHASE_DISPATCH_YAML"]

FR_GOAL_PHASE_DISPATCH_YAML = """\
workflow: fr-goal
schema: 1
unit: phase
description: >-
  fr-goal's `implement` step as the sub-shape ONE phase item executes: a
  phase executor reads the merged spec and plan from its own checkout of
  main and delivers a PR. The shipped `fr-goal` manifest is `unit: run` —
  this is what its `for_each: phase` fan-out dispatches, not a rival shape.
requires: [git, tests, scm]
steps:
  - id: implement
    kind: agent
    agent: super-fr:fr-phase-executor
    needs: [spec, plan]
    tier: from_phase
    emits: [pr]
"""

FR_GOAL_PHASE_DISPATCH: WorkflowManifest = parse_manifest(FR_GOAL_PHASE_DISPATCH_YAML)
"""The default shape for phase-granularity DISPATCH.

`needs: [spec, plan]` with nothing emitting them is legal for a
`unit: phase` shape — see `fr.workflow.artifacts.IMPLIED_INPUTS_BY_UNIT` —
and is exactly what makes `required_inputs` non-empty, hence what keeps
`fr apply --yes --to <runner>` refusing an unmerged plan.

**There are TWO defaults in this codebase and they answer different
questions** (documented here, once, per review r5-e3):

- **`FR_GOAL_PHASE_DISPATCH`** (this module) answers *"a plan names no
  `workflow:` — at what granularity does the bridge dispatch it?"*
- **`DEFAULT_WORKFLOW`** (`"fr-goal"`, `fr.run.adopt`) answers *"`fr run
  adopt` was given no `--workflow` — which shape's step list is the cursor a
  position in?"*

They are not two spellings of one thing and must not be merged. The first is
a `unit: phase` MANIFEST OBJECT, resolved from nothing, describing the one
item a phase executor runs; it exists so `fr apply --to` and `tick` keep
today's behaviour for every plan in the wild. The second is a shape NAME,
resolved repo > shipped like any other, naming the `unit: run` pipeline whose
steps (`brainstorm` … `deliver`) a run cursor is a position in.

A run cursor cannot live in `FR_GOAL_PHASE_DISPATCH` at all — it has one step
— and a bridge cannot dispatch `DEFAULT_WORKFLOW` at phase granularity,
because that shape is `unit: run`. They happen to share the name `fr-goal`
because the shipped run-shape and the phase sub-shape it fans out to are two
views of one pipeline (see this manifest's `description`).
"""
