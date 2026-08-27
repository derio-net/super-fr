"""`fr workflow check` — semantic validation, code not prose (spec §4.A, Phase 6).

Structural validity (unknown top-level/step keys, wrong types, an
unsupported `schema:`) is already enforced by `fr.workflow.model.parse_manifest`
at parse time — a manifest that fails those checks can never become a
`WorkflowManifest`, so it can never reach `check_workflow` here. What this
module catches is everything only meaningful once a valid step graph
exists: duplicate step ids, `needs` naming an artifact no earlier step
`emits`, a cycle anywhere in the needs/emits graph, a capability name
outside the closed set, and a `for_each` that contradicts its manifest's
`unit`.

`check_workflow` is pure — no I/O, no exit codes. `fr workflow check`
(`fr.commands.workflow_cmd`) is the one place a `WorkflowError` (parse-time)
and this module's error list (semantic) are reported through the same
exit-1 shape, so an operator never has to know which layer a given shape
failed at.
"""

from __future__ import annotations

from fr.capabilities import CAPABILITIES
from fr.workflow.model import Step, WorkflowManifest

__all__ = ["check_workflow"]


def check_workflow(manifest: WorkflowManifest) -> list[str]:
    """Every problem with `manifest`, as human-readable strings. Empty = clean."""
    errors: list[str] = []
    errors.extend(_duplicate_step_ids(manifest.steps))
    errors.extend(_dangling_needs(manifest.steps))
    errors.extend(_cycles(manifest.steps))
    errors.extend(_unknown_capabilities(manifest.requires))
    errors.extend(_for_each_unit_conflicts(manifest))
    return errors


def _duplicate_step_ids(steps: tuple[Step, ...]) -> list[str]:
    seen: set[str] = set()
    errors: list[str] = []
    for step in steps:
        if step.id in seen:
            errors.append(f"duplicate step id: {step.id!r}")
        seen.add(step.id)
    return errors


def _dangling_needs(steps: tuple[Step, ...]) -> list[str]:
    """A step's `needs` must name an artifact some STRICTLY EARLIER step
    `emits` — a forward reference (a later step's `emits`) or an artifact
    nobody ever emits are both dangling, and both reported here."""
    errors: list[str] = []
    emitted_so_far: set[str] = set()
    for step in steps:
        for artifact in step.needs:
            if artifact not in emitted_so_far:
                errors.append(f"step {step.id!r} needs {artifact!r} but no earlier step emits it")
        emitted_so_far.update(step.emits)
    return errors


def _cycles(steps: tuple[Step, ...]) -> list[str]:
    """A cycle in the needs/emits graph, independent of list order.

    Builds edges producer -> consumer for every (artifact, step) pair where
    `step` needs an artifact some step `emits` — including a later step, so
    this catches a genuine mutual dependency `_dangling_needs` alone would
    only ever report as one-sided "dangling" errors, never name as a cycle.
    Reports at most one cycle (deterministic — steps and neighbours are
    walked in sorted-id order); a validator's job is "reject", not
    "enumerate every cycle".
    """
    emitters: dict[str, list[str]] = {}
    for step in steps:
        for artifact in step.emits:
            emitters.setdefault(artifact, []).append(step.id)

    graph: dict[str, set[str]] = {step.id: set() for step in steps}
    for step in steps:
        for artifact in step.needs:
            for producer in emitters.get(artifact, ()):
                if producer != step.id:
                    graph[producer].add(step.id)

    white, gray, black = 0, 1, 2
    color = dict.fromkeys(graph, white)
    path: list[str] = []
    cycle: list[str] | None = None

    def visit(node: str) -> None:
        nonlocal cycle
        if cycle is not None:
            return
        color[node] = gray
        path.append(node)
        for nxt in sorted(graph[node]):
            if cycle is not None:
                return
            if color[nxt] == gray:
                cycle = path[path.index(nxt) :] + [nxt]
                return
            if color[nxt] == white:
                visit(nxt)
                if cycle is not None:
                    return
        path.pop()
        color[node] = black

    for node in sorted(graph):
        if color[node] == white:
            visit(node)
        if cycle is not None:
            break

    if cycle is None:
        return []
    return [f"cycle detected in needs/emits: {' -> '.join(cycle)}"]


def _unknown_capabilities(requires: tuple[str, ...]) -> list[str]:
    unknown = sorted(set(requires) - CAPABILITIES)
    return [
        f"unknown capability {c!r} in requires (valid: {sorted(CAPABILITIES)})" for c in unknown
    ]


def _for_each_unit_conflicts(manifest: WorkflowManifest) -> list[str]:
    """`for_each: phase` is legal in a `unit: run` shape (spec's fr-goal
    example: `implement` fans out one dispatch per phase) and an error in a
    `unit: phase` shape — that shape's items are already per-phase, so
    `for_each` there can only mean "dispatch each phase's step once per
    phase of itself", which is nonsensical."""
    if manifest.unit != "phase":
        return []
    return [
        f"step {step.id!r} sets for_each: {step.for_each!r}, which is redundant/invalid "
        f"when the manifest's unit is already 'phase'"
        for step in manifest.steps
        if step.for_each is not None
    ]
