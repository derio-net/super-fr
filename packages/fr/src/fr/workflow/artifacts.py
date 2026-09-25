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
    "ALWAYS_RECORD_SECTIONS",
    "IMPLIED_INPUTS_BY_UNIT",
    "RECORD_EMIT_TOKENS",
    "REPO_TRACKED_ARTIFACTS",
    "journal_scope",
    "record_sections",
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


# --- step records (spec 2026-09-25-lean-cost-aware-process §5.C.2.1) --------
#
# A step record's sections are allowed by what the step EMITS, literally, so a
# repo-overridden manifest gets the same rules without code. Two tokens exist
# only for this: neither names a file, and neither feeds a `needs`.

RECORD_EMIT_TOKENS = frozenset({"plan:ticks", "acceptance"})
"""`plan:ticks` — the step ticks plan steps (and justifies a missing refactor);
`acceptance` — the step writes acceptance-matrix rows."""

ALWAYS_RECORD_SECTIONS = frozenset({"outcome", "evidence"})
"""Every step's record may say how it ended and what proves it."""

_JOURNAL_PREFIX = "journal:"


def record_sections(emits: tuple[str, ...] | list[str]) -> frozenset[str]:
    """The record sections `emits` allows beyond `ALWAYS_RECORD_SECTIONS`."""
    out: set[str] = set()
    for token in emits:
        if token.startswith(_JOURNAL_PREFIX):
            out.update({"journal", "resolves"})
        elif token == "plan:ticks":
            out.update({"ticks", "refactor"})
        elif token == "acceptance":
            out.add("acceptance")
    return frozenset(out)


def journal_scope(emits: tuple[str, ...] | list[str]) -> str | None:
    """The journal scope a record's `journal`/`resolves` entries land in —
    the first `journal:<scope>` the step emits, or None."""
    for token in emits:
        if token.startswith(_JOURNAL_PREFIX):
            return token[len(_JOURNAL_PREFIX) :]
    return None
