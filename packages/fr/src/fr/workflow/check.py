"""`fr workflow check` — semantic validation, code not prose (spec §4.A, Phase 6).

Structural validity (unknown top-level/step keys, wrong types, an
unsupported `schema:`) is already enforced by `fr.workflow.model.parse_manifest`
at parse time — a manifest that fails those checks can never become a
`WorkflowManifest`, so it can never reach `check_workflow` here. What this
module catches is everything only meaningful once a valid step graph
exists: duplicate step ids, a `kind: cli` step with no `run:` command,
`needs` naming an artifact no earlier step `emits`, a cycle anywhere in the
needs/emits graph, a capability name outside the closed set, and a
`for_each` that contradicts its manifest's `unit`.

Nested `for_each` groups (the per-phase implement+review loop) are checked
in the same pass over a flattened id space: member ids share the duplicate
namespace with top-level ids, a member's `needs` resolve against earlier
siblings plus everything the group's own `needs` already proved available,
and cycles are detected across the flattened graph. The group boundary is
the downstream contract — a member's `emits` feed later siblings, but only
the group's `emits` feed later top-level steps.
"""

from __future__ import annotations

from fr.capabilities import CAPABILITIES
from fr.workflow.artifacts import IMPLIED_INPUTS_BY_UNIT
from fr.workflow.model import Step, WorkflowManifest

__all__ = ["check_workflow"]


def _flatten(steps: tuple[Step, ...]) -> list[tuple[Step, Step | None]]:
    """Every step as `(step, parent)` — parent `None` for top-level steps."""
    flat: list[tuple[Step, Step | None]] = []
    for step in steps:
        flat.append((step, None))
        for member in step.steps:
            flat.append((member, step))
    return flat


def check_workflow(manifest: WorkflowManifest) -> list[str]:
    """Every problem with `manifest`, as human-readable strings. Empty = clean."""
    flat = _flatten(manifest.steps)
    errors: list[str] = []
    errors.extend(_duplicate_step_ids(flat))
    errors.extend(_cli_steps_without_a_command(flat))
    errors.extend(_nest_placement(manifest.steps))
    errors.extend(_dangling_needs(manifest.steps, manifest.unit))
    errors.extend(_cycles(flat))
    errors.extend(_unknown_capabilities(manifest.requires))
    errors.extend(_for_each_unit_conflicts(manifest))
    return errors


def _duplicate_step_ids(flat: list[tuple[Step, Step | None]]) -> list[str]:
    """Duplicate ids across the flattened space — a member colliding with a
    top-level id (or a sibling) would make the run cursor ambiguous."""
    seen: set[str] = set()
    errors: list[str] = []
    for step, _parent in flat:
        if step.id in seen:
            errors.append(f"duplicate step id: {step.id!r}")
        seen.add(step.id)
    return errors


def _cli_steps_without_a_command(flat: list[tuple[Step, Step | None]]) -> list[str]:
    """`kind: cli` with no `run:` is a step that cannot do anything.

    `Step.run` is optional because `agent` steps have none, so the schema
    alone cannot express "cli implies run". Left unchecked it is worse than
    a crash: `advance` rendered `""`, `subprocess.run("", shell=True)` exited
    0, and the run reported a green step that did nothing and moved the
    cursor on. `fr run advance` refuses it at runtime too — an authored
    manifest is caught here, a hand-built `WorkflowManifest` there.
    """
    return [
        f"step {step.id!r} is kind: cli but declares no `run:` command"
        for step, _parent in flat
        if step.kind == "cli" and not (step.run or "").strip()
    ]


def _nest_placement(steps: tuple[Step, ...]) -> list[str]:
    """Nesting is one level deep under a `for_each` step, nothing more.

    Members on a step without `for_each` have no fan-out to iterate inside;
    a member with its own `for_each` (or `steps`) would fan out per phase of
    itself — the same nonsense `_for_each_unit_conflicts` rejects for
    `unit: phase` shapes, one level down.
    """
    errors: list[str] = []
    for step in steps:
        if step.steps and step.for_each is None:
            errors.append(
                f"step {step.id!r} declares member steps but no `for_each:` — "
                "members only iterate inside a fan-out scope"
            )
        for member in step.steps:
            if member.for_each is not None:
                errors.append(
                    f"step {member.id!r} sets for_each: {member.for_each!r} inside "
                    f"step {step.id!r} — nesting is one level deep"
                )
            if member.steps:
                errors.append(
                    f"step {member.id!r} declares member steps inside step "
                    f"{step.id!r} — nesting is one level deep"
                )
    return errors


def _dangling_needs(steps: tuple[Step, ...], unit: str) -> list[str]:
    """A step's `needs` must name an artifact some STRICTLY EARLIER step
    `emits` — a forward reference (a later step's `emits`) or an artifact
    nobody ever emits are both dangling, and both reported here.

    **Seeded with the artifacts the `unit` implies already exist**
    (`IMPLIED_INPUTS_BY_UNIT`). Without that seed the rule as written in
    spec §4.A would make a `unit: phase` shape impossible to author: a
    phase item exists only inside a plan, so its steps legitimately need a
    spec and a plan that no step of that shape emits — and §4.E's whole
    reachability rule is about exactly those un-emitted needs. `unit: run`
    seeds nothing, so a run shape is validated exactly as before.
    """
    errors: list[str] = []
    emitted_so_far: set[str] = set(IMPLIED_INPUTS_BY_UNIT.get(unit, frozenset()))
    for step in steps:
        for artifact in step.needs:
            if artifact not in emitted_so_far:
                errors.append(_need_error(step.id, artifact))
        emitted_so_far.update(step.emits)
        # A member's `needs` resolve against earlier siblings plus everything
        # the group's own (already validated) `needs` proved available — the
        # group boundary is the downstream contract, so only the group's
        # `emits` feed later top-level steps, never a member's.
        for member in step.steps:
            for artifact in member.needs:
                if artifact not in emitted_so_far:
                    errors.append(_need_error(member.id, artifact))
            emitted_so_far.update(member.emits)
        emitted_so_far.difference_update(_member_only_emits(step))
    return errors


def _need_error(step_id: str, artifact: str) -> str:
    return f"step {step_id!r} needs {artifact!r} but no earlier step emits it"


def _member_only_emits(step: Step) -> set[str]:
    """Artifacts a member emits that the group does not re-emit — visible to
    later siblings while the group is being walked, withdrawn afterwards so
    the group boundary stays the downstream contract."""
    group_emits = set(step.emits)
    return {a for m in step.steps for a in m.emits} - group_emits


def _cycles(flat: list[tuple[Step, Step | None]]) -> list[str]:
    """A cycle in the needs/emits graph, independent of list order.

    Builds edges producer -> consumer for every (artifact, step) pair where
    `step` needs an artifact some step `emits` — including a later step, so
    this catches a genuine mutual dependency `_dangling_needs` alone would
    only ever report as one-sided "dangling" errors, never name as a cycle.
    Reports at most one cycle (deterministic — steps and neighbours are
    walked in sorted-id order); a validator's job is "reject", not
    "enumerate every cycle". Members share the flattened id space, so a
    cyclic nest is caught the same way.
    """
    emitters: dict[str, list[str]] = {}
    for step, _parent in flat:
        for artifact in step.emits:
            emitters.setdefault(artifact, []).append(step.id)

    graph: dict[str, set[str]] = {step.id: set() for step, _parent in flat}
    for step, _parent in flat:
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
