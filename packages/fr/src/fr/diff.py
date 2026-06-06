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

from fr._urls import parse_issue_url
from fr.labels import LabelDef
from fr.parser import Plan
from fr.render import plan_locally_complete
from fr.states import GhState, RenderedState

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
class SuppressedCreate:
    """An IssueCreate the guard withheld (2026-06-05 stale-plan postmortem).

    Suppression is data, not a log line: apply dry-run, `fr status`, and
    JSON output all render these so the operator sees exactly which phases
    were refused and why. `fr apply --yes --force` re-enables the creates.
    """

    phase_number: int
    reason: str


@dataclass(frozen=True)
class Diff:
    mutations: tuple[Mutation, ...]
    suppressed: tuple[SuppressedCreate, ...] = ()


def _build_title(plan: Plan, phase_number: int) -> str:
    """[<repo>] <plan-slug> · Phase N/M · <subject>."""
    phase = next(p for p in plan.phases if p.phase.number == phase_number)
    total = len(plan.phases)
    return (
        f"[{plan.meta.target_repo}] {plan.meta.plan} · "
        f"Phase {phase_number}/{total} · {phase.phase.title}"
    )


def diff(
    rendered: RenderedState,
    observed: GhState,
    *,
    plan: Plan,
    force_create: bool = False,
) -> Diff:
    """Compute mutations to bring observed → rendered. Pure.

    `force_create=False` (default) suppresses `IssueCreate` for undispatched
    phases that are `plan_locally_complete` — a complete plan must never
    dispatch as new work (2026-06-05 stale-plan incident: 13 spurious
    Issues). Suppressions are returned on `Diff.suppressed`. Pass
    `force_create=True` (CLI `--force`) to emit the creates anyway. Mixed
    plans are never blocked: only the locally-complete phases suppress.
    """
    mutations: list[Mutation] = []
    suppressed: list[SuppressedCreate] = []
    repo = plan.meta.target_repo

    # Group managed labels by destination repo so each repo gets exactly one
    # RepoLabelEnsure. For undispatched phases (no tracking_issue) the
    # destination falls back to target_repo (where IssueCreate will fire).
    # For dispatched phases the destination is parse_issue_url(tracking_issue).
    labels_per_repo: dict[str, set[LabelDef]] = {}
    for phase in plan.phases:
        ri = rendered.issue_per_phase[phase.phase.number]
        if phase.phase.tracking_issue:
            dest_repo, _ = parse_issue_url(phase.phase.tracking_issue)
        else:
            dest_repo = repo
        labels_per_repo.setdefault(dest_repo, set()).update(
            ld for ld in ri.labels if _is_managed(ld.name)
        )
    # Sorted outer iteration for deterministic mutation order.
    for dest_repo, labels in sorted(labels_per_repo.items()):
        if labels:
            mutations.append(RepoLabelEnsure(repo=dest_repo, labels=frozenset(labels)))

    for phase_n, ri in rendered.issue_per_phase.items():
        phase = next(p for p in plan.phases if p.phase.number == phase_n)
        tracking = phase.phase.tracking_issue
        obs = observed.phases.get(phase_n)

        if tracking is None or obs is None:
            # Completion guard: a locally-complete phase (all steps ticked
            # or completion.at set) must not dispatch as new work. See
            # SuppressedCreate docstring.
            if not force_create and plan_locally_complete(phase):
                steps = phase.state.steps
                ticked = sum(1 for s in steps.values() if s.state in ("x", "-"))
                completion_note = " and completion.at is set" if phase.state.completion.at else ""
                suppressed.append(
                    SuppressedCreate(
                        phase_number=phase_n,
                        reason=(
                            f"{ticked}/{len(steps)} steps ticked{completion_note} — "
                            f"locally complete, refusing to create an Issue "
                            f"(override: --force)"
                        ),
                    )
                )
                continue
            # Undispatched: create the Issue on target_repo. v2 does not yet
            # support first-dispatch to a foreign repo; that would require
            # knowing the intended destination before a tracking_issue exists.
            # When cross-repo first-dispatch is added, update both here AND the
            # `phase_to_repo` surface in render.render() — the two coupling
            # points must move together. gh.create_issue takes label names —
            # project the rendered LabelDefs to their .name.
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

    return Diff(mutations=tuple(mutations), suppressed=tuple(suppressed))
