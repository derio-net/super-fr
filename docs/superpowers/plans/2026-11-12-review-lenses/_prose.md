# Review lenses — plan

Implements `docs/superpowers/specs/2026-11-12-review-lenses-design.md`.

A lens is an id plus the instruction text a reviewer is given. Any agent may add
one to a feature during a run; a repo's path rules add one when the feature
changes a path they name. Before `deliver`, a new `lens-review` step has one
reviewer per lens examine the whole change, and fr refuses the step while a lens
is unaccounted for. The per-phase review is not touched.

## Phases

1. **The lens set** (R1-R3, skeleton). The `fr/lenses` package, the four shipped
   manifests with their wheel copy, `.fr/lenses.yaml`, and the read-only
   `fr lenses list|show|check`. Nothing else in fr reads a lens yet.
2. **Adding lenses** (R4-R7). The `lens` journal entry (journal kind 4) and the
   record field that carries it (record kind 12), each with its migration; path
   rules as the default branch's together with the branch's; `lens_set`, the one
   definition of what a feature owes; `fr lenses status`.
3. **The lens-review step** (R8-R11, R13). The step in both shipped manifests,
   its brief, the `review-lens` block, a feature-level evidence target in
   `run_cmd.py`, the derived `lenses` evidence, and the path for runs in flight.
4. **The PR section, skills, agents, docs** (R12, R14).

## Order and risk

Phase 2 changes two artifact shapes and phase 3 changes the evidence gate every
review step goes through; both are `hard` for that reason. Phase 3's third
task is where a regression in the existing phase and spec reviews would come
from, so it ends by re-running every existing review resolve test.

This branch's own run was started against the step list without `lens-review`.
Once phase 3 adds the step to the shipped manifest, the run drifts and is
reshaped (phase 3, task 4) before it can continue.

## Verification

Every row is on the `candidate` strategy with a scenario under
`tests/scenarios/`; `deliver` owes a `fr verification walk`. Nothing is owed
after merge.
