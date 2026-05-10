"""Pure diff: (RenderedState, GhState) -> Diff.

A `Diff` is a list of typed mutations. The applier consumes it.
Both diff() and apply() are deterministic, idempotent, and
managed-labels-only (won't touch labels outside the registry).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from vk.v2.parser import Plan
from vk.v2.states import GhState, RenderedState

# Prefixes the applier is allowed to add/remove. Operator labels
# (e.g. "good-first-issue", "bug") never get touched.
MANAGED_LABEL_PREFIXES = ("vk-", "spec:", "plan:", "phase:")
MANAGED_LIFECYCLE_LABELS = frozenset({"vk-ready", "manual", "in-progress", "pr-ready"})


def _is_managed(label: str) -> bool:
    if label in MANAGED_LIFECYCLE_LABELS:
        return True
    return any(label.startswith(p) for p in MANAGED_LABEL_PREFIXES)


_ISSUE_URL_RE = re.compile(r"^https://github\.com/([^/]+/[^/]+)/issues/(\d+)$")


def _parse_issue_url(url: str) -> tuple[str, int]:
    m = _ISSUE_URL_RE.match(url)
    if not m:
        raise ValueError(f"not a github issue url: {url}")
    return m.group(1), int(m.group(2))


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
    new_state: str  # "OPEN" or "CLOSED"
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
    labels: frozenset[str]


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

    # Always ensure managed labels exist on the repo before any Issue ops
    all_managed_labels: set[str] = set()
    for issue in rendered.issue_per_phase.values():
        all_managed_labels.update(lbl for lbl in issue.labels if _is_managed(lbl))
    if all_managed_labels:
        mutations.append(RepoLabelEnsure(repo=repo, labels=frozenset(all_managed_labels)))

    for phase_n, ri in rendered.issue_per_phase.items():
        phase = next(p for p in plan.phases if p.phase.number == phase_n)
        tracking = phase.phase.tracking_issue
        obs = observed.phases.get(phase_n)

        if tracking is None or obs is None:
            # Undispatched: create the Issue
            mutations.append(
                IssueCreate(
                    repo=repo,
                    title=_build_title(plan, phase_n),
                    body=ri.body,
                    labels=ri.labels,
                    phase_number=phase_n,
                )
            )
            continue

        issue_repo, issue_number = _parse_issue_url(tracking)

        # Label diff (managed labels only)
        rendered_managed = frozenset(lbl for lbl in ri.labels if _is_managed(lbl))
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
