"""Artifact vocabulary shared by validation and reachability (spec §4.E).

Steps trade in *artifact names* — `spec`, `plan`, `pr`, `report`,
`journal:plan`. Two questions get asked about that vocabulary, and both are
answered here so they can never drift:

1. **Which names denote a file in a git repo?** Only those can be checked
   for reachability on `origin/HEAD`; `pr`, `report` and `journal:*` are
   real outputs with no repo-tracked path to look for.
2. **Which artifacts already exist by the time a shape starts?** That is
   what the decomposition `unit` says: a `phase` item exists only because a
   plan (and therefore a spec) already does; a `run` starts from nothing.

The second question is why `fr.workflow.check` cannot simply demand that
every `needs` be emitted by an earlier step — see `IMPLIED_INPUTS_BY_UNIT`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fr.workflow.model import WorkflowManifest

__all__ = [
    "IMPLIED_INPUTS_BY_UNIT",
    "REPO_TRACKED_ARTIFACTS",
    "required_inputs",
]

REPO_TRACKED_ARTIFACTS = frozenset({"spec", "plan"})
"""Artifact names that denote a path in a git repo.

Reachability (§4.E) is "is this file on `origin/HEAD`", so it is only
meaningful for these. An artifact outside this set is still a real input
or output — it just has no path a gate could look for, which is exactly
why a shape emitting only a `report` dispatches with nothing to check.
"""

IMPLIED_INPUTS_BY_UNIT: dict[str, frozenset[str]] = {
    "run": frozenset(),
    "spec": frozenset({"spec"}),
    "phase": frozenset({"spec", "plan"}),
}
"""Artifacts that already exist when a shape of this `unit` begins.

Derived from the §4.D identity grammar, whose levels nest: a phase id
contains a plan slug which contains a spec slug, so a `unit: phase` shape
is *by construction* work inside a plan that already exists. Its steps
legitimately `needs: [spec, plan]` while no step of that shape emits them
— they were emitted by whatever produced the plan, which is a different
shape (or a human).

`unit: run` seeds nothing: a run is the level at which a spec and plan are
*outputs* (§4.E), which is why a run-unit goal dispatches with neither on
main.
"""


def required_inputs(manifest: WorkflowManifest) -> frozenset[str]:
    """Repo-tracked artifacts the shape consumes but never produces.

    The §4.E rule in one line: **a step's `needs` are inputs and must be
    reachable; its `emits` are outputs and need not be.** Whatever survives
    `needs - emits` came from outside the shape, so it has to already exist
    where the runner will look for it.

    Pure — no I/O, no manifest resolution. `fr.workflow.reachability` turns
    the result into a path check; `fr_dispatch.item_graph.build_items` uses
    it to decide which `ArtifactRef`s an item declares.
    """
    needed: set[str] = set()
    emitted: set[str] = set()
    for step in manifest.steps:
        needed.update(step.needs)
        emitted.update(step.emits)
    return frozenset(needed - emitted) & REPO_TRACKED_ARTIFACTS
