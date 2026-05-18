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

from vk._urls import issue_number as _issue_number_from_url
from vk.labels import (
    IN_PROGRESS,
    MANUAL,
    PR_READY,
    VK_BLOCKED,
    VK_READY,
    VK_SYNCED,
    LabelDef,
    phase_label,
    plan_label,
    spec_label,
)
from vk.parser import Plan
from vk.states import (
    GhState,
    PhaseObservation,
    RenderedIssue,
    RenderedState,
    Warning,
)
from vk.types import PhaseDoc

_DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-")


def _spec_slug(spec_path: str | None) -> str | None:
    """Strip date prefix and `.md` suffix from spec path; return None if unset."""
    if not spec_path:
        return None
    stem = Path(spec_path).stem
    return _DATE_PREFIX_RE.sub("", stem)


def _deps_satisfied(phase: PhaseDoc, plan: Plan, observed: GhState) -> bool:
    """True iff every phase in `phase.depends_on` is complete."""
    phase_by_number = {p.phase.number: p for p in plan.phases}
    for dep_n in phase.phase.depends_on:
        dep_phase = phase_by_number.get(dep_n)
        if dep_phase is None:
            return False
        dep_obs = observed.phases.get(dep_n)
        if not _phase_complete(dep_phase, dep_obs):
            return False
    return True


def _lifecycle_label(
    phase: PhaseDoc,
    obs: PhaseObservation | None,
    plan: Plan,
    observed: GhState,
) -> LabelDef | None:
    """Compute the single lifecycle LabelDef for a phase.

    Returns None when the Issue should be closed (phase complete).
    """
    if _phase_complete(phase, obs):
        return None  # closed; no lifecycle label
    if phase.phase.tag == "manual":
        return MANUAL
    if not _deps_satisfied(phase, plan, observed):
        return VK_BLOCKED
    if obs is None:
        return VK_READY
    has_open_pr_nondraft = any(
        pr.state == "OPEN" and not pr.draft and not pr.merged for pr in obs.linked_prs
    )
    if has_open_pr_nondraft:
        return PR_READY
    has_assignee_or_draft_pr = bool(obs.issue_assignees) or any(
        pr.state == "OPEN" and pr.draft for pr in obs.linked_prs
    )
    if has_assignee_or_draft_pr:
        return IN_PROGRESS
    return VK_READY


def _phase_complete(phase: PhaseDoc, obs: PhaseObservation | None) -> bool:
    """Per spec rules.

    - Manual phase: requires `completion.at` AND `completion.note`. Steps optional.
    - Agentic phase: requires `completion.at` AND a merged PR observed AND no
      open linked PR remains. BOTH signals required:
        - `completion.at` is the agent's "I'm done" signal
        - merged PR is the operator's "I accepted the work" signal
      Either alone is insufficient. Setting `completion.at` without a merged
      PR keeps the Issue OPEN (renderer projects pr-ready when a PR exists,
      vk-ready otherwise) so the work surfaces correctly until merge.

    Pre-2026-05-18 behavior was `completion.at OR (all_steps_ticked + merged PR)`
    — the OR shortcut closed Issues prematurely when an agent set
    `completion.at` before opening its PR. See 2026-05-18 incident
    (multiple VK-spawned agents skipped `vk apply --yes` to avoid the
    premature close).
    """
    completion = phase.state.completion

    if phase.phase.tag == "manual":
        return completion.at is not None and completion.note is not None

    if completion.at is None:
        return False
    if obs is None:
        return False
    has_merged_pr = any(pr.merged for pr in obs.linked_prs)
    has_open_pr = any(pr.state == "OPEN" and not pr.merged for pr in obs.linked_prs)
    return has_merged_pr and not has_open_pr


def render_body(
    phase: PhaseDoc,
    plan: Plan,
    *,
    phase_to_issue: dict[int, int] | None = None,
    phase_to_repo: dict[int, str] | None = None,
) -> str:
    """Static body template. Same content from dispatch through close.

    Uses `plan.repo_relative_dir` (NOT `plan.dir`) for the `📋 Plan:`
    line so the body doesn't leak the dispatcher's absolute filesystem
    path — the body is consumed by humans + tooling in every clone of
    the repo, including pod-side agents on different filesystems.

    `phase_to_issue` maps phase numbers to the predecessor's tracking
    Issue number (int). When set, `- Blocked by #N` uses the Issue
    number, not the phase number — which is what the bridge actually
    parses. `phase_to_repo` is forward-compat for cross-repo deps; v2
    doesn't dispatch cross-repo today, but the bridge already accepts
    `owner/repo#N`, so making the renderer symmetric now avoids a
    second rework.

    Both default to None (treated as empty dict) — callers that
    haven't been updated still get the phase-number form, which is
    obviously broken at a glance, so the operator notices and
    re-dispatches.

    Deliberately does NOT carry a "include `Closes #N` to auto-close"
    hint. v2 handles auto-close via the renderer projection
    (`apply()` closes Issues when the phase becomes Complete) so the
    hint that v1's body needed is structurally unnecessary now.
    """
    total = len(plan.phases)
    repo = plan.meta.target_repo
    spec = plan.meta.spec or "—"
    plan_path = plan.repo_relative_dir
    tracking = (
        f"📦 Repo:   {repo}\n"
        f"📋 Plan:   {plan_path}\n"
        f"📐 Spec:   {spec}\n"
        f"🎯 Phase:  {phase.phase.number}/{total} — {phase.phase.title} [{phase.phase.tag}]\n"
        f"🔗 Issue:  {phase.phase.tracking_issue or '(assigned on create)'}\n"
    )

    def _dep_ref(n: int) -> str:
        issue_n = (phase_to_issue or {}).get(n)
        if issue_n is None:
            # Predecessor hasn't been dispatched yet AND isn't in this
            # apply's created_issues. Fall back to the phase-number form —
            # the operator will see the broken ref and re-dispatch.
            return f"#{n}"
        dep_repo = (phase_to_repo or {}).get(n)
        if dep_repo and dep_repo != plan.meta.target_repo:
            return f"{dep_repo}#{issue_n}"
        return f"#{issue_n}"

    if phase.phase.depends_on:
        deps_block = "\n".join(f"- Blocked by {_dep_ref(n)}" for n in phase.phase.depends_on)
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


def _phase_labels(phase: PhaseDoc, plan: Plan) -> frozenset[LabelDef]:
    """Taxonomy LabelDef set for a phase (factory-resolved, registry-colored)."""
    labels: set[LabelDef] = {
        plan_label(plan.meta.plan),
        phase_label(phase.phase.number),
    }
    spec_slug = _spec_slug(plan.meta.spec)
    if spec_slug:
        labels.add(spec_label(spec_slug))
    return frozenset(labels)


def _drift_warnings(plan: Plan, observed: GhState) -> tuple[Warning, ...]:
    """Surface non-blocking drift signals for operator review.

    Severity levels:
      - "info":  benign — agent forgot a checkbox tick
      - "warn":  ambiguous — operator action may be needed
      - "error": something is wrong — Issue closed without plan agreement
    """
    warnings: list[Warning] = []
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
                Warning(
                    severity="warn",
                    message=(
                        f"Phase {n}: all steps ticked but no merged PR observed — "
                        f"operator may have ticked prematurely."
                    ),
                )
            )
        # Merged PR but some steps still unticked (agent forgot to tick)
        if has_merged_pr and not all_ticked:
            warnings.append(
                Warning(
                    severity="info",
                    message=(
                        f"Phase {n}: PR merged but steps unticked — "
                        f"agent may have forgotten to tick them."
                    ),
                )
            )
        # Issue closed but plan says incomplete (someone closed it manually)
        if obs.issue_state == "CLOSED" and not _phase_complete(phase, obs):
            warnings.append(
                Warning(
                    severity="error",
                    message=(
                        f"Phase {n}: Issue closed but plan is incomplete — reconciliation needed."
                    ),
                )
            )
    return tuple(warnings)


def build_phase_to_issue(
    plan: Plan, created_issues: dict[int, str] | None = None
) -> dict[int, int]:
    """Map phase number → tracking-issue number.

    Pulls from each phase's persisted `tracking_issue`. If `created_issues`
    is supplied (the in-flight `phase_number → issue_url` dict returned by
    `apply()`), its entries take precedence — that's how `apply()` can
    re-render a dependent phase's body after its predecessor's
    `IssueCreate` lands in the same run.
    """
    result: dict[int, int] = {}
    for ph in plan.phases:
        n = _issue_number_from_url(ph.phase.tracking_issue)
        if n is not None:
            result[ph.phase.number] = n
    if created_issues:
        for phase_n, url in created_issues.items():
            n = _issue_number_from_url(url)
            if n is not None:
                result[phase_n] = n
    return result


def render(
    plan: Plan,
    observed: GhState,
    *,
    created_issues: dict[int, str] | None = None,
) -> RenderedState:
    """Project (plan, observed) → RenderedState. Pure function.

    `created_issues` is the in-flight `phase_number → issue_url` map from
    a running `apply()`. When set, dependent phases' bodies render with
    the now-known Issue numbers instead of the phase-number fallback.
    """
    phase_to_issue = build_phase_to_issue(plan, created_issues)
    # phase_to_repo is forward-compat for cross-repo deps. v2 is
    # single-target_repo today, so the map is always empty in practice.
    phase_to_repo: dict[int, str] = {}
    issues: dict[int, RenderedIssue] = {}
    for phase in plan.phases:
        n = phase.phase.number
        obs = observed.phases.get(n)
        labels: set[LabelDef] = set(_phase_labels(phase, plan))
        lifecycle = _lifecycle_label(phase, obs, plan, observed)
        if lifecycle is not None:
            labels.add(lifecycle)
        # `vk-synced` is bridge-owned: the renderer doesn't set it, but it
        # shares the `vk-` managed prefix, so without explicit preservation
        # `diff()` would strip it on every tick after the bridge added it.
        # Carry it forward from observed so apply() sees no drift.
        if obs is not None and VK_SYNCED.name in obs.issue_labels:
            labels.add(VK_SYNCED)
        state: Literal["OPEN", "CLOSED"] = "CLOSED" if _phase_complete(phase, obs) else "OPEN"
        issues[n] = RenderedIssue(
            body=render_body(
                phase, plan, phase_to_issue=phase_to_issue, phase_to_repo=phase_to_repo
            ),
            labels=frozenset(labels),
            state=state,
        )
    archive = all(_phase_complete(p, observed.phases.get(p.phase.number)) for p in plan.phases)
    return RenderedState(
        issue_per_phase=issues,
        archive_decision=archive,
        warnings=_drift_warnings(plan, observed),
    )
