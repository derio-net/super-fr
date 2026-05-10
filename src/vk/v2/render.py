"""Pure projection: (Plan, GhState) -> RenderedState.

The renderer never performs I/O. Same inputs always produce the same
output. Drift detection is `actual == rendered`-comparison-free for
consumers because everything is hashable+frozen.

Projection rules implemented here come straight from the spec:
  docs/superpowers/specs/2026-05-06-vk-rebuild-state-machine-design.md
  §"Rendering"
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from vk.v2.parser import Plan
from vk.v2.states import (
    GhState,
    PhaseObservation,
    RenderedIssue,
    RenderedState,
)
from vk.v2.types import PhaseDoc

_DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-")


def _spec_slug(spec_path: str | None) -> str | None:
    """Strip date prefix and `.md` suffix from spec path; return None if unset."""
    if not spec_path:
        return None
    stem = Path(spec_path).stem
    return _DATE_PREFIX_RE.sub("", stem)


def _lifecycle_label(phase: PhaseDoc, obs: PhaseObservation | None) -> str | None:
    """Compute the single lifecycle label for a phase.

    Returns None when the Issue should be closed (phase complete).
    """
    if _phase_complete(phase, obs):
        return None  # closed; no lifecycle label
    if phase.phase.tag == "manual":
        return "manual"
    if obs is None:
        return "vk-ready"
    has_open_pr_nondraft = any(
        pr.state == "OPEN" and not pr.draft and not pr.merged for pr in obs.linked_prs
    )
    if has_open_pr_nondraft:
        return "pr-ready"
    has_assignee_or_draft_pr = bool(obs.issue_assignees) or any(
        pr.state == "OPEN" and pr.draft for pr in obs.linked_prs
    )
    if has_assignee_or_draft_pr:
        return "in-progress"
    return "vk-ready"


def _phase_complete(phase: PhaseDoc, obs: PhaseObservation | None) -> bool:
    """Per spec rules.

    - Manual phase: requires `completion.at` AND `completion.note`. Steps optional.
    - Agentic phase: `completion.at` set OR (all steps ticked AND a merged PR
      observed AND no open linked PR remains).
    """
    completion = phase.state.completion
    all_steps_ticked = all(s.state in ("x", "-") for s in phase.state.steps.values())

    if phase.phase.tag == "manual":
        return completion.at is not None and completion.note is not None

    if completion.at is not None:
        return True
    if not all_steps_ticked:
        return False
    if obs is None:
        return False
    has_merged_pr = any(pr.merged for pr in obs.linked_prs)
    has_open_pr = any(pr.state == "OPEN" and not pr.merged for pr in obs.linked_prs)
    return has_merged_pr and not has_open_pr


def _render_body(phase: PhaseDoc, plan: Plan) -> str:
    """Static body template. Same content from dispatch through close."""
    total = len(plan.phases)
    repo = plan.meta.target_repo
    spec = plan.meta.spec or "—"
    plan_path = plan.dir
    tracking = (
        f"📦 Repo:   {repo}\n"
        f"📋 Plan:   {plan_path}\n"
        f"📐 Spec:   {spec}\n"
        f"🎯 Phase:  {phase.phase.number}/{total} — {phase.phase.title} [{phase.phase.tag}]\n"
        f"🔗 Issue:  {phase.phase.tracking_issue or '(assigned on create)'}\n"
    )
    if phase.phase.depends_on:
        deps_block = "\n".join(f"- Blocked by #{n}" for n in phase.phase.depends_on)
    else:
        deps_block = "None — no blocking phases."
    return (
        f"{tracking}"
        f"\n---\n\n"
        f"## Instruction\n\n"
        f"Use superpowers-for-vk:vk-execute to implement Phase "
        f"{phase.phase.number} of this plan.\n\n"
        f"## Workspace\n\n"
        f"Repos: {repo}\n\n"
        f"## Dependencies\n\n"
        f"{deps_block}\n"
    )


def _phase_labels(phase: PhaseDoc, plan: Plan) -> frozenset[str]:
    """Taxonomy + lifecycle label set for a phase."""
    spec_slug = _spec_slug(plan.meta.spec)
    labels: set[str] = {f"plan:{plan.meta.plan}", f"phase:{phase.phase.number}"}
    if spec_slug:
        labels.add(f"spec:{spec_slug}")
    return frozenset(labels)


def _drift_warnings(plan: Plan, observed: GhState) -> tuple[str, ...]:
    """Surface non-blocking drift signals for operator review."""
    warnings: list[str] = []
    for phase in plan.phases:
        n = phase.phase.number
        obs = observed.phases.get(n)
        steps = phase.state.steps
        all_ticked = bool(steps) and all(s.state in ("x", "-") for s in steps.values())
        if obs is None:
            continue
        has_merged_pr = any(pr.merged for pr in obs.linked_prs)
        # Steps all ticked but no merged PR (operator may have ticked prematurely)
        if all_ticked and not has_merged_pr and obs.linked_prs:
            warnings.append(
                f"Phase {n}: all steps ticked but no merged PR observed — "
                f"operator may have ticked prematurely."
            )
        # Merged PR but some steps still unticked (agent forgot to tick)
        if has_merged_pr and not all_ticked:
            warnings.append(
                f"Phase {n}: PR merged but steps unticked — agent may have forgotten to tick them."
            )
        # Issue closed but plan says incomplete (someone closed it manually)
        if obs.issue_state == "CLOSED" and not _phase_complete(phase, obs):
            warnings.append(
                f"Phase {n}: Issue closed but plan is incomplete — reconciliation needed."
            )
    return tuple(warnings)


def render(plan: Plan, observed: GhState) -> RenderedState:
    """Project (plan, observed) → RenderedState. Pure function."""
    issues: dict[int, RenderedIssue] = {}
    for phase in plan.phases:
        n = phase.phase.number
        obs = observed.phases.get(n)
        labels = set(_phase_labels(phase, plan))
        lifecycle = _lifecycle_label(phase, obs)
        if lifecycle is not None:
            labels.add(lifecycle)
        state: Literal["OPEN", "CLOSED"] = (
            "CLOSED" if _phase_complete(phase, obs) else "OPEN"
        )
        issues[n] = RenderedIssue(
            body=_render_body(phase, plan),
            labels=frozenset(labels),
            state=state,
        )
    archive = all(_phase_complete(p, observed.phases.get(p.phase.number)) for p in plan.phases)
    return RenderedState(
        issue_per_phase=issues,
        archive_decision=archive,
        warnings=_drift_warnings(plan, observed),
    )
