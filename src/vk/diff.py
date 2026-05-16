"""Pure diff: (RenderedState, GhState) -> Diff.

A `Diff` is a list of typed mutations. The applier consumes it.
Both diff() and apply() are deterministic, idempotent, and
managed-labels-only (won't touch labels outside the registry).

**Body-diff caveat.** v1 plans usually didn't change Issue bodies
post-create — body was set once at IssueCreate (with a placeholder
where the URL would go), then best-effort patched once. v2's
renderer produces the body from `(plan, observed)`, so the body
naturally re-renders when `tracking_issue` is filled in. We diff
bodies and emit `IssueBodyChange` when they drift; this catches
the URL-fill-in case AND any future plan-rework that changes the
body's substantive content.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from vk._urls import parse_issue_url
from vk.labels import LabelDef
from vk.parser import Plan
from vk.states import GhState, RenderedState

# Prefix-owned namespaces. The applier may add/remove anything starting
# with one of these; everything else (e.g. `good-first-issue`, `bug`)
# is operator-owned and never touched.
MANAGED_LABEL_PREFIXES = ("vk-", "spec:", "plan:", "phase:")

# Bare lifecycle names — managed by the renderer but don't have a
# distinguishing prefix. NOTE: `vk-ready` is omitted here because the
# `vk-` prefix already covers it; including it would just be redundant.
MANAGED_BARE_LABELS = frozenset({"manual", "in-progress", "pr-ready"})


def _is_managed(label: str) -> bool:
    if label in MANAGED_BARE_LABELS:
        return True
    return any(label.startswith(p) for p in MANAGED_LABEL_PREFIXES)


@dataclass(frozen=True)
class IssueLabelChange:
    repo: str
    issue_number: int
    add: frozenset[str]
    remove: frozenset[str]


@dataclass(frozen=True)
class IssueStateChange:
    repo: str
    issue_number: int
    new_state: Literal["OPEN", "CLOSED"]
    close_reason: str | None = None


@dataclass(frozen=True)
class IssueBodyChange:
    repo: str
    issue_number: int
    new_body: str


@dataclass(frozen=True)
class IssueCreate:
    repo: str
    title: str
    body: str
    labels: frozenset[str]
    phase_number: int  # for back-linking after creation


@dataclass(frozen=True)
class RepoLabelEnsure:
    repo: str
    labels: frozenset[LabelDef]


Mutation = IssueLabelChange | IssueStateChange | IssueBodyChange | IssueCreate | RepoLabelEnsure


@dataclass(frozen=True)
class Diff:
    mutations: tuple[Mutation, ...]


def _build_title(plan: Plan, phase_number: int) -> str:
    """[<repo>] <plan-slug> · Phase N/M · <subject>."""
    phase = next(p for p in plan.phases if p.phase.number == phase_number)
    total = len(plan.phases)
    return (
        f"[{plan.meta.target_repo}] {plan.meta.plan} · "
        f"Phase {phase_number}/{total} · {phase.phase.title}"
    )


def diff(rendered: RenderedState, observed: GhState, *, plan: Plan) -> Diff:
    """Compute mutations to bring observed → rendered. Pure."""
    mutations: list[Mutation] = []
    repo = plan.meta.target_repo

    # Ensure managed labels exist on every destination repo before any Issue ops.
    # For dispatched phases the destination is parsed from tracking_issue; for
    # undispatched phases it is plan.meta.target_repo (where IssueCreate will fire).
    # Rendered labels are LabelDefs (registry-colored); we filter by name against the
    # managed-prefix allowlist and pass LabelDefs straight to the GhClient so
    # colors/descriptions survive the trip.
    labels_by_repo: dict[str, set[LabelDef]] = {}
    phase_by_number = {p.phase.number: p for p in plan.phases}
    for phase_n, issue in rendered.issue_per_phase.items():
        managed = {ld for ld in issue.labels if _is_managed(ld.name)}
        if not managed:
            continue
        phase = phase_by_number[phase_n]
        tracking = phase.phase.tracking_issue
        dest_repo = parse_issue_url(tracking)[0] if tracking else repo
        labels_by_repo.setdefault(dest_repo, set()).update(managed)
    for dest_repo, labels in sorted(labels_by_repo.items()):
        mutations.append(RepoLabelEnsure(repo=dest_repo, labels=frozenset(labels)))

    for phase_n, ri in rendered.issue_per_phase.items():
        phase = phase_by_number[phase_n]
        tracking = phase.phase.tracking_issue
        obs = observed.phases.get(phase_n)

        if tracking is None or obs is None:
            # Undispatched: create the Issue. gh.create_issue takes label
            # names — project the rendered LabelDefs to their .name.
            mutations.append(
                IssueCreate(
                    repo=repo,
                    title=_build_title(plan, phase_n),
                    body=ri.body,
                    labels=frozenset(ld.name for ld in ri.labels),
                    phase_number=phase_n,
                )
            )
            continue

        issue_repo, issue_number = parse_issue_url(tracking)

        # Label diff (managed labels only). Observed labels come back as
        # plain strings from GitHub; rendered are LabelDefs — compare by name.
        rendered_managed = frozenset(ld.name for ld in ri.labels if _is_managed(ld.name))
        observed_managed = frozenset(lbl for lbl in obs.issue_labels if _is_managed(lbl))
        to_add = rendered_managed - observed_managed
        to_remove = observed_managed - rendered_managed
        if to_add or to_remove:
            mutations.append(
                IssueLabelChange(
                    repo=issue_repo,
                    issue_number=issue_number,
                    add=to_add,
                    remove=to_remove,
                )
            )

        # Body diff (catches the post-IssueCreate URL fill-in case)
        if obs.body != ri.body:
            mutations.append(
                IssueBodyChange(
                    repo=issue_repo,
                    issue_number=issue_number,
                    new_body=ri.body,
                )
            )

        # State diff (open/closed)
        if obs.issue_state != ri.state:
            mutations.append(
                IssueStateChange(
                    repo=issue_repo,
                    issue_number=issue_number,
                    new_state=ri.state,
                    close_reason="completed" if ri.state == "CLOSED" else None,
                )
            )

    return Diff(mutations=tuple(mutations))
