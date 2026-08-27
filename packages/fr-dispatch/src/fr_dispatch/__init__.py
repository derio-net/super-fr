"""Queue protocol + runner framework — `discover_plans` + `tick`.

Runner-agnostic since the super-fr split (2026-06-05 design): `tick`
orchestrates observe → render → diff → apply → dispatch against the
`fr_dispatch.protocols.Runner` contract; the VibeKanban adapter
(`fr_vk`) is the first implementation. These functions are intentionally
NOT wired into the CLI — the bridge daemon (`python -m fr_vk.bridge`)
consumes them as a library.

`tick` iterates `WorkItem`s (2026-08-14 workflow-shapes spec §4.D), not
phases: the granularity is the shape's declared `unit`. Today the only
builder is the phase-unit one below — `unit: run` / `unit: spec` items
arrive with the shape axis. The backend dispatch is the runner's
`dispatch(item)`; test B2 enforces single-source on the VK adapter's MCP
chain. Issue creation is operator-only (`apply(skip_issue_create=True)`)
— see the 2026-05-18 incident.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from fr import plan_ops
from fr._urls import is_cross_repo_spec, parse_issue_url
from fr.apply import apply
from fr.diff import diff
from fr.ghclient import GhClient
from fr.item_state import DISPATCH_STAMP, state_from_labels
from fr.observe import observe
from fr.parser import Plan, PlanSchemaError, parse
from fr.plan_ops import PlanEditError
from fr.render import render
from fr.states import GhState, RenderedIssue, RenderedState

from fr_dispatch.metrics import MetricsPusher, NullMetrics
from fr_dispatch.protocols import Runner
from fr_dispatch.work_item import ArtifactRef, WorkItem, item_id, parent_id

__all__ = ["ArtifactRef", "Runner", "TickResult", "WorkItem", "discover_plans", "tick"]

logger = logging.getLogger(__name__)

# The shape these items come from until the shape axis lands: `fr-goal`'s
# `implement` step is `for_each: phase` (spec §4.A), which is exactly what
# the bridge dispatches today.
_DEFAULT_WORKFLOW = "fr-goal"

# `item_id` needs a spec segment, but `PlanMeta.spec` is optional. A plan
# without one still needs a deterministic, collision-free identity, so the
# segment degrades to this sentinel rather than raising — identity is pure
# string composition and must never depend on an artifact existing.
_NO_SPEC_SLUG = "_no-spec"


@dataclass(frozen=True)
class TickResult:
    """Counters for one `tick()` invocation, returned to the cron caller.

    - `synced`: items successfully handed to the runner this tick.
    - `errors`: total failures accumulated (apply-side + per-item).
    - `skipped`: deferred items (slot budget) when any were eligible;
      1 when the plan had nothing eligible (idle-plan counting).
    - `failures`: human-readable accumulated failure strings.
    """

    synced: int
    errors: int
    skipped: int
    failures: tuple[str, ...] = ()


def _is_dispatchable(rendered_issue: RenderedIssue) -> bool:
    """True iff a rendered tracker item is queued and not yet stamped.

    The one eligibility rule, shared by discovery and the tick so the two
    can never drift apart. Expressed in `fr.item_state` terms rather than
    label names: the projected `ItemState` must be `queued`, and the
    dispatch stamp must be absent. The stamp is read separately because it
    is bookkeeping, not a state — `state_from_labels` ignores it outright.
    """
    label_names = {label.name for label in rendered_issue.labels}
    return state_from_labels(label_names) == "queued" and DISPATCH_STAMP.name not in label_names


def _plan_projects_ready(plan: Plan, gh: GhClient) -> bool:
    """True iff rendering the plan projects a phase as dispatchable.

    Projection-based (the #251 deadlock fix): a phase whose dependency
    just completed may project ready while its on-Issue label is still
    the stale blocked one — discovery must see the projection, not the
    label.
    """
    observed = observe(plan, gh)
    rendered = render(plan, observed)
    for phase in plan.phases:
        if not phase.phase.tracking_issue:
            continue
        ri = rendered.issue_per_phase.get(phase.phase.number)
        if ri is None:
            continue
        if _is_dispatchable(ri):
            return True
    return False


def _repo_checkout_root(repo: str) -> Path:
    """Resolve `owner/name` to a local checkout path.

    Matches the live bridge's REPOS_DIR convention (`~/repos/<name>`).
    Override the parent with `FR_REPOS_DIR` — used by tests and by any
    deployment where checkouts live somewhere other than `$HOME/repos`.
    """
    name = repo.split("/", 1)[1] if "/" in repo else repo
    base = os.environ.get("FR_REPOS_DIR")
    root = Path(base) if base else Path.home() / "repos"
    return root / name


def discover_plans(repo: str, gh: GhClient) -> list[Plan]:
    """Walk `docs/superpowers/plans/` in `repo`, return plans with a ready phase.

    Returns `[]` (no exception) if the checkout is missing or the plans
    directory is absent. Individual unparseable plan folders are logged
    and skipped so a single malformed plan can't take down the cron tick.
    """
    repo_root = _repo_checkout_root(repo)
    plans_dir = repo_root / "docs" / "superpowers" / "plans"
    if not plans_dir.is_dir():
        return []
    out: list[Plan] = []
    for plan_dir in sorted(plans_dir.iterdir()):
        if not plan_dir.is_dir() or not (plan_dir / "_meta.yaml").exists():
            continue
        try:
            plan = parse(plan_dir)
        except PlanSchemaError as e:
            logger.warning("bridge: skipping unparseable plan %s: %s", plan_dir, e)
            continue
        try:
            ready = _plan_projects_ready(plan, gh)
        except Exception as e:  # noqa: BLE001 — one bad plan mustn't kill the tick
            logger.warning("bridge: discovery check failed for %s: %s", plan_dir, e)
            continue
        if ready:
            out.append(plan)
    return out


def _spec_slug(plan: Plan) -> str:
    """Identity segment for the plan's spec — its filename stem.

    Mirrors the derivation `render.py` already uses for the `spec:` label,
    so an item id and an Issue label name the same spec. Falls back to
    `_NO_SPEC_SLUG` when the plan declares no spec.
    """
    spec = plan.spec_path or plan.meta.spec
    return Path(spec).stem if spec else _NO_SPEC_SLUG


def _plan_inputs(plan: Plan) -> tuple[ArtifactRef, ...]:
    """The artifacts every item of this plan reads (§4.D `inputs`).

    Each ref is a *coordinate*: `repo` plus a path relative to THAT repo.
    A cross-repo spec (`<owner>/<repo>:<path>` notation) is therefore split
    rather than passed through — `plan.spec_path` is deliberately None for
    one (the parser can't resolve a path in a checkout it doesn't have), so
    the raw notation would otherwise land in `path` and be attributed to
    `target_repo`, the one repo the file is not in. Same split
    `render.spec_url` and `repair` already do.

    Phase 8 (reachability from inputs) and Phase 9 (multi-repo fan-out)
    consume these refs as coordinates, so a wrong `repo` is not cosmetic.
    """
    refs = [ArtifactRef(kind="plan", repo=plan.meta.target_repo, path=str(plan.repo_relative_dir))]
    spec_rel = plan.spec_path or plan.meta.spec
    if spec_rel:
        if is_cross_repo_spec(spec_rel):
            spec_repo, spec_rel = spec_rel.split(":", 1)
        else:
            spec_repo = plan.meta.target_repo
        refs.append(ArtifactRef(kind="spec", repo=spec_repo, path=spec_rel))
    return tuple(refs)


def _phase_item_ref(plan: Plan, phase_number: int, tracking: str | None = None) -> str:
    """The would-be `WorkItem.id` for a phase, for FAILURE STRINGS only.

    Every failure `tick` accumulates is prefixed with the item it concerns,
    because the id also names the plan — on a bridge running many plans,
    `"phase 3: …"` says nothing about which phase 3. The two failures raised
    before (or instead of) a `WorkItem` — item construction and tracking-issue
    writeback — have no item to read an id off, so the ref is composed
    segment-wise here.

    Deliberately does NOT call `item_id`: this runs on the failure path, and
    `item_id` raising (a reserved slug, a `/` in one) is one of the things
    that lands here. Composition must never be the reason a failure string
    can't be produced.
    """
    repo = plan.meta.target_repo
    if tracking:
        try:
            repo = parse_issue_url(tracking)[0]
        except ValueError:
            pass  # keep target_repo — a malformed URL is likely the failure itself
    return f"{repo}/{_spec_slug(plan)}/{plan.meta.plan}/phase/{phase_number}"


def _eligible_items(
    plan: Plan,
    observed: GhState,
    rendered: RenderedState,
    failures: list[str],
) -> list[WorkItem]:
    """Phase-unit `WorkItem`s this tick should hand to the runner.

    The gate runs against the **rendered** state, not the pre-apply
    observation: a phase an agent claimed between dispatch and this tick
    projects `in_progress` and is correctly skipped. Eligible means the
    projected `ItemState` is `queued` **and** the dispatch stamp is absent
    — the stamp is bookkeeping, not a state (see `fr.item_state`), so the
    two are read separately.

    One malformed phase (bad tracking URL, un-composable id) fails only
    itself: the failure is accumulated and the loop continues.
    """
    spec_slug = _spec_slug(plan)
    plan_slug = plan.meta.plan
    inputs = _plan_inputs(plan)
    items: list[WorkItem] = []
    for phase in plan.phases:
        n = phase.phase.number
        if n not in observed.phases:
            continue
        ri = rendered.issue_per_phase.get(n)
        tracking = phase.phase.tracking_issue
        if ri is None or not tracking:  # pragma: no cover — defensive guard
            continue
        if not _is_dispatchable(ri):
            continue
        try:
            issue_repo, issue_number = parse_issue_url(tracking)
            iid = item_id(issue_repo, spec_slug, plan_slug, phase=n)
            items.append(
                WorkItem(
                    id=iid,
                    unit="phase",
                    workflow=_DEFAULT_WORKFLOW,
                    repo=issue_repo,
                    parent=parent_id(iid),
                    inputs=inputs,
                    payload={"plan": plan, "phase": phase, "issue_number": issue_number},
                    tracking=tracking,
                )
            )
        except Exception as e:  # noqa: BLE001 — one bad phase mustn't kill the tick
            failures.append(f"{_phase_item_ref(plan, n, tracking)}: {e}")
            continue
    return items


def tick(
    plan: Plan,
    gh: GhClient,
    runner: Runner,
    *,
    metrics: MetricsPusher | None = None,
) -> TickResult:
    """One cron iteration for a single plan, against one runner.

    Pipeline: observe → render → diff → apply (GH-side only,
    `skip_issue_create=True`) → build a `WorkItem` for every eligible
    unit of work → `runner.dispatch(item)` → flip the dispatch stamp on
    the tracker item. Eligibility is read off the **rendered** state via
    `fr.item_state` (projected `queued`, stamp absent), not off raw label
    strings and not off the pre-apply observation.

    All failure paths accumulate; a raising `runner.dispatch` leaves the
    dispatch stamp unwritten so the next tick retries. `skipped` counts
    slot-deferred items (or 1 when nothing was eligible — idle-plan
    counting, legacy behavior preserved).
    """
    m = metrics or NullMetrics()

    try:
        runner.refresh()
    except Exception as e:  # noqa: BLE001 — cache refresh must not kill the tick
        logger.warning("runner refresh failed: %s", e)

    observed = observe(plan, gh)
    rendered = render(plan, observed)
    d = diff(rendered, observed, plan=plan)
    # Issue creation is operator-only (via `apply --yes`). The tick must
    # NEVER auto-create Issues — see the 2026-05-18 incident
    # (sfv#196-#214 and sfv#216-#234).
    apply_result = apply(d, gh, plan=plan, skip_issue_create=True)
    failures: list[str] = [f.error for f in apply_result.failures]
    for phase_n, url in apply_result.created_issues.items():
        try:
            plan_ops.set_tracking_issue(plan.dir, phase_n, url)
        except (PlanEditError, OSError, PlanSchemaError) as e:
            failures.append(f"{_phase_item_ref(plan, phase_n, url)}: writeback failed: {e}")

    items = _eligible_items(plan, observed, rendered, failures)

    synced = 0
    deferred = 0
    if items:
        try:
            blocker = runner.preflight(items)
        except Exception as e:  # noqa: BLE001
            blocker = f"runner preflight raised: {e}"
        if blocker:
            for item in items:
                failures.append(f"{item.id}: {blocker}")
                m.push_failure_total(reason="preflight")
            m.push_heartbeat()
            return TickResult(
                synced=0,
                errors=len(failures),
                skipped=len(items),
                failures=tuple(failures),
            )

        # Slot gate: snapshot capacity once per tick, decrement as we go.
        try:
            budget = max(0, runner.slot_budget())
        except Exception as e:  # noqa: BLE001 — never let slot-counting break a tick
            failures.append(f"slot check failed: {e}")
            budget = 0

        # Dedup snapshot: one backend call covers every item in this plan.
        # Keyed on `WorkItem.id` — identity lives on the item now, so there
        # is no `dedup_key` round trip through the adapter. The items are
        # passed explicitly: an adapter that inverts board state into ids
        # needs them, and reading them out of a `preflight`-set attribute
        # instead would make the call ORDER load-bearing and silent.
        try:
            existing = runner.existing_dispatches(items)
        except Exception as e:  # noqa: BLE001
            failures.append(f"dedup fetch failed: {e}")
            existing = set()

        for item in items:
            try:
                routable = runner.can_dispatch(item)
            except Exception as e:  # noqa: BLE001
                failures.append(f"{item.id}: repo gate failed: {e}")
                m.push_failure_total(reason="repo_gate")
                continue
            if not routable:
                failures.append(f"{item.id}: unknown repo {item.repo!r}")
                m.push_failure_total(reason="unknown_repo")
                continue

            already_dispatched = item.id in existing

            if not already_dispatched and budget <= 0:
                # No slot left — defer this item to the next tick.
                deferred += 1
                continue

            # Split backend-side and tracker-side error paths so the
            # `reason` label on the failure metric points at the broken
            # system. A dedup hit skips the backend call entirely; the
            # stamp still runs so the next tick won't retry.
            if not already_dispatched:
                try:
                    runner.dispatch(item)
                    budget -= 1
                except Exception as e:  # noqa: BLE001 — one bad backend call mustn't kill the tick
                    failures.append(f"{item.id}: {e}")
                    m.push_failure_total(reason="backend_error")
                    continue

            try:
                # `payload` is deliberately opaque (`Mapping[str, object]`)
                # — the phase-unit builder puts the already-parsed number
                # there, so this is a narrowing, not a re-parse.
                issue_number = int(item.payload["issue_number"])  # type: ignore[call-overload]
                gh.ensure_labels(item.repo, [DISPATCH_STAMP])
                gh.edit_issue_labels(
                    item.repo,
                    issue_number,
                    add=frozenset({DISPATCH_STAMP.name}),
                    remove=frozenset(),
                )
                synced += 1
                m.push_sync_total()
            except Exception as e:  # noqa: BLE001 — GH outage mustn't kill the tick
                failures.append(f"{item.id}: gh stamp failed: {e}")
                m.push_failure_total(reason="gh_error")

    skipped = deferred if items else 1
    m.push_heartbeat()
    return TickResult(
        synced=synced,
        errors=len(failures),
        skipped=skipped,
        failures=tuple(failures),
    )
