"""Queue protocol + runner framework — `discover_plans` + `tick`.

Runner-agnostic since the super-fr split (2026-06-05 design): `tick`
orchestrates observe → render → diff → apply → dispatch against the
`fr_dispatch.protocols.Runner` contract; the VibeKanban adapter
(`fr_vk`) is the first implementation. These functions are intentionally
NOT wired into the CLI — the bridge daemon (`python -m fr_vk.bridge`)
consumes them as a library.

`tick` iterates `WorkItem`s (2026-08-14 workflow-shapes spec §4.D), not
phases: the granularity is the shape's declared `unit`, and every item
comes from the one builder, `fr_dispatch.item_graph.build_items` —
`_eligible_items` below is a tracker-state filter over it, not a second
construction path. The backend dispatch is the runner's
`dispatch(item)`; test B2 enforces single-source on the VK adapter's MCP
chain. Issue creation is operator-only (`apply(skip_issue_create=True)`)
— see the 2026-05-18 incident.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from fr import plan_ops
from fr.apply import apply
from fr.diff import diff
from fr.ghclient import GhClient
from fr.item_state import DISPATCH_STAMP, ItemState, state_from_labels
from fr.observe import observe
from fr.parser import Plan, PlanSchemaError, parse
from fr.plan_ops import PlanEditError
from fr.render import render
from fr.spec import SpecMeta
from fr.states import GhState, RenderedIssue, RenderedState
from fr.workflow.model import WorkflowManifest
from fr.workflow.shapes import FR_GOAL_PHASE_DISPATCH

from fr_dispatch.capabilities import missing_capabilities
from fr_dispatch.item_graph import build_items, phase_item_ref
from fr_dispatch.metrics import MetricsPusher, NullMetrics
from fr_dispatch.protocols import Runner
from fr_dispatch.work_item import ArtifactRef, WorkItem

if TYPE_CHECKING:
    from collections.abc import Sequence

    from fr.tracker.model import Tracker

__all__ = [
    "ArtifactRef",
    "Runner",
    "TickResult",
    "WorkItem",
    "build_items",
    "discover_plans",
    "tick",
]

logger = logging.getLogger(__name__)


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


def discover_plans(
    repo: str,
    gh: GhClient,
    *,
    metrics: MetricsPusher | None = None,
    failures: list[str] | None = None,
) -> list[Plan]:
    """Walk `docs/superpowers/plans/` in `repo`, return plans with a ready phase.

    Returns `[]` (no exception) if the checkout is missing or the plans
    directory is absent. The per-plan I9 boundary still holds — one bad
    plan folder can't take down the cron tick — but a `PlanSchemaError`
    is no longer swallowed as a quiet warning (Phase 5, spec §3.C/§3.E.1).

    Under a `fr` version bump, a plan's `_meta.yaml` can fail `parse()`
    because its artifacts are stale (e.g. an `fr_version` ceiling that
    excludes the installed major) — and the old behaviour here was to log
    a WARNING and silently drop the plan, so the tick kept reporting
    healthy while dispatch quietly stopped for it. That is now a LOUD
    refusal: an ERROR log naming the plan, a `stale_artifact` failure
    metric, and (via the `failures` outparam, mirroring `tick`'s own
    `failures: list[str]` accumulator) a message the caller can count as
    an error and fold into its own totals. `metrics` defaults to
    `NullMetrics()` so a caller that doesn't care sees no behavior change;
    `failures` defaults to `None` and is simply not written to.

    This function never migrates and never shells out — it only reads.
    The bridge's checkout is hard-reset to `origin/main` every tick
    (#286), so a commit made here would be silently discarded next
    tick: refusing loudly is the only correct response to staleness in
    this context, mirroring `is_interactive()`'s daemon branch
    (`fr.artifacts.trigger`) without calling it — the bridge never goes
    through the CLI's `ensure_artifacts_current` gate at all (it calls
    `fr_dispatch`/`fr.parser` as a library, not `fr <command>` as a
    subprocess), so there is no TTY/CI context to test here: it is
    unconditionally non-interactive by construction, and refuses
    unconditionally rather than re-deriving that fact through the
    predicate.
    """
    m = metrics if metrics is not None else NullMetrics()
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
            msg = f"{plan_dir}: refusing (artifacts stale or unparseable): {e}"
            logger.error("bridge: %s", msg)
            m.push_failure_total(reason="stale_artifact")
            if failures is not None:
                failures.append(msg)
            continue
        try:
            ready = _plan_projects_ready(plan, gh)
        except Exception as e:  # noqa: BLE001 — one bad plan mustn't kill the tick
            logger.warning("bridge: discovery check failed for %s: %s", plan_dir, e)
            continue
        if ready:
            out.append(plan)
    return out


def _eligible_items(
    plan: Plan | SpecMeta | None,
    observed: GhState | None,
    rendered: RenderedState | None,
    failures: list[str],
    *,
    workflow: WorkflowManifest = FR_GOAL_PHASE_DISPATCH,
    repo: str | None = None,
    run_id: str | None = None,
) -> list[WorkItem]:
    """The subset of this plan's item graph that is dispatchable right now.

    A **filter over `build_items`**, never a second construction path —
    `item_graph.build_items` is the one builder, and the granularity is the
    shape's declared `unit`.

    The gate runs against the **rendered** state, not the pre-apply
    observation: a phase an agent claimed between dispatch and this tick
    projects `in_progress` and is correctly skipped. Eligible means the
    projected `ItemState` is `queued` **and** the dispatch stamp is absent
    — the stamp is bookkeeping, not a state (see `fr.item_state`), so the
    two are read separately.

    With no `observed`/`rendered` state there is no tracker projection to
    filter against at all (a shape with no plan — see `tick`), so the graph
    is returned whole.

    A **non-phase** item is passed through: `observed`/`rendered` project
    plan phases and nothing else, so there is no state to read for a run-
    or spec-unit item. Inventing "ineligible" for one would make a shape
    that tracks nothing undispatchable — re-dispatch protection for those
    is the runner's `existing_dispatches`. A phase item with no Issue *is*
    filtered out: its plan is tracked, so a missing Issue means the phase
    has not been queued yet, not that it needs no tracker.

    One malformed phase (bad tracking URL, un-composable id) fails only
    itself: the failure is accumulated and the graph is still returned.
    """
    items = build_items(workflow, plan, repo=repo, run_id=run_id, failures=failures)
    if observed is None or rendered is None:
        return items
    eligible: list[WorkItem] = []
    for item in items:
        phase_number = _phase_number(item)
        if phase_number is None:
            eligible.append(item)
            continue
        if not item.tracking or phase_number not in observed.phases:
            continue
        ri = rendered.issue_per_phase.get(phase_number)
        if ri is None or not _is_dispatchable(ri):
            continue
        eligible.append(item)
    return eligible


def _phase_number(item: WorkItem) -> int | None:
    """The phase number an item's payload carries, if it is a phase item."""
    if item.unit != "phase":
        return None
    phase = item.payload.get("phase")
    number = getattr(getattr(phase, "phase", None), "number", None)
    return number if isinstance(number, int) else None


def _capability_blocker(
    items: Sequence[WorkItem], runner: Runner, required_capabilities: frozenset[str]
) -> str | None:
    """§4.F: the tick-wide capability check, run BEFORE `runner.preflight`.

    Ordered ahead of `runner.preflight` so a capability mismatch is
    reported as a capability problem rather than a config one — the caller
    (`tick`) skips the `preflight` call entirely when this returns
    non-`None`, feeding the result into the SAME blocker-handling code
    `preflight`'s own return value uses (one message, every eligible item
    fails, `synced=0`, `dispatch` never called). This is deliberately the
    one refusal mechanism, not a second one: Phase 10's tracker-state
    refusals are expected to produce a blocker string through this same
    path rather than add a third.

    `required_capabilities` is empty by default (see `tick`'s docstring —
    the Phase 6 seam), so every pre-Phase-6 caller sees no behavior change.
    """
    if not required_capabilities:
        return None
    missing = missing_capabilities(required_capabilities, runner.capabilities)
    if not missing:
        return None
    word = "capability" if len(missing) == 1 else "capabilities"
    return f"runner {runner.name!r} is missing {word}: {', '.join(missing)}"


def _tracker_blocker(
    tracker: Tracker | None,
    tracker_instance: str | None,
    required_tracker_states: frozenset[ItemState],
) -> str | None:
    """§4.G: the tracker-state refusal, chained AFTER `_capability_blocker`
    and BEFORE `runner.preflight` — the same short-circuit `tick` already
    runs for §4.F, not a second one. Phase 5's handoff named this shape
    exactly: "a tracker-state refusal should be a third function with the
    same `str | None` -> blocker-assignment shape, checked in the same
    short-circuit chain."

    `required_tracker_states` is empty by default, mirroring
    `required_capabilities`: no caller that doesn't pass it (every
    pre-Phase-10 caller, including the live bridge) sees any behavior
    change. `tracker=None` is equally silent — a tracker that cannot be
    reached (or was never configured) must not make dispatch impossible;
    it just cannot be checked, so nothing here refuses on its behalf.
    """
    if not required_tracker_states or tracker is None:
        return None
    missing = tuple(sorted(s for s in required_tracker_states if not tracker.supports(s)))
    if not missing:
        return None
    word = "state" if len(missing) == 1 else "states"
    instance = tracker_instance if tracker_instance is not None else "?"
    return (
        f"tracker {tracker.name!r} instance {instance!r} cannot express required "
        f"{word}: {', '.join(missing)}"
    )


def tick(
    plan: Plan | SpecMeta | None,
    gh: GhClient,
    runner: Runner,
    *,
    workflow: WorkflowManifest = FR_GOAL_PHASE_DISPATCH,
    repo: str | None = None,
    run_id: str | None = None,
    required_capabilities: frozenset[str] = frozenset(),
    tracker: Tracker | None = None,
    tracker_instance: str | None = None,
    required_tracker_states: frozenset[ItemState] = frozenset(),
    metrics: MetricsPusher | None = None,
) -> TickResult:
    """One cron iteration for a single unit of work, against one runner.

    Pipeline: [tracker sync] → build a `WorkItem` for every eligible unit
    of work → capability check → `runner.preflight` → `runner.dispatch
    (item)` → [flip the dispatch stamp]. The bracketed stages are the
    tracker's, and they run only for the items that have one.

    `workflow` is the shape whose declared `unit` decides the granularity
    (§4.E); it defaults to the phase-unit shape the bridge has always
    dispatched, so an existing caller sees no change. `plan` is the source
    that shape decomposes — a `Plan` for `unit: phase`, a `SpecMeta` for
    `unit: spec` (§4.E fan-out: one item per repo its plan table names),
    and **`None` is legal** for `unit: run`: a run may have no plan at all
    (the spec's marketing-research example emits only a document), in
    which case `repo` and `run_id` name the run instead. Only a `Plan`
    source is ever observed/rendered/diffed/applied — those stages project
    a *plan* onto a GitHub tracker specifically, and neither `None` nor a
    `SpecMeta` source has a plan's phases to project. A run or spec-unit
    dispatch therefore makes no tracker call at all.

    When `plan` IS a `Plan`: observe → render → diff → apply (GH-side
    only, `skip_issue_create=True`) runs first, and eligibility is read
    off the **rendered** state via `fr.item_state` (projected `queued`,
    stamp absent), not off raw label strings and not off the pre-apply
    observation.

    `required_capabilities` (§4.F) is the whole tick's declared need —
    empty by default. Non-empty, it is checked against `runner.capabilities`
    BEFORE `runner.preflight` is even called; a shortfall fails every
    eligible item with one message and returns without touching `preflight`
    or `dispatch`. It stays a parameter rather than being read off
    `workflow.requires` so that passing a shape cannot silently start
    refusing work for a caller that never asked for the check.

    `tracker`/`tracker_instance`/`required_tracker_states` (§4.G) is the
    same negotiation, one step later in the SAME short-circuit: a
    tracker-state shortfall is checked after the capability check and
    still before `runner.preflight`, so a capability mismatch is always
    reported first when both are wrong. `required_tracker_states` is empty
    by default and `tracker` is `None` by default, so no pre-Phase-10
    caller — including the live bridge — sees any behavior change.

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

    failures: list[str] = []
    observed: GhState | None = None
    rendered: RenderedState | None = None
    if isinstance(plan, Plan):
        observed = observe(plan, gh)
        rendered = render(plan, observed)
        d = diff(rendered, observed, plan=plan)
        # Issue creation is operator-only (via `apply --yes`). The tick must
        # NEVER auto-create Issues — see the 2026-05-18 incident
        # (sfv#196-#214 and sfv#216-#234).
        apply_result = apply(d, gh, plan=plan, skip_issue_create=True)
        failures.extend(f.error for f in apply_result.failures)
        for phase_n, url in apply_result.created_issues.items():
            try:
                plan_ops.set_tracking_issue(plan.dir, phase_n, url)
            except (PlanEditError, OSError, PlanSchemaError) as e:
                failures.append(f"{phase_item_ref(plan, phase_n, url)}: writeback failed: {e}")

    items = _eligible_items(
        plan, observed, rendered, failures, workflow=workflow, repo=repo, run_id=run_id
    )

    synced = 0
    deferred = 0
    if items:
        blocker = _capability_blocker(items, runner, required_capabilities)
        if blocker is None:
            blocker = _tracker_blocker(tracker, tracker_instance, required_tracker_states)
        if blocker is None:
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

            if item.tracking is None:
                # No tracker artifact to stamp. The dispatch stamp is
                # bookkeeping that lives on the tracker item because there
                # is nowhere better — an item that has none is not "unsynced",
                # it simply has nothing to write to, and re-dispatch
                # protection for it is `runner.existing_dispatches`.
                synced += 1
                m.push_sync_total()
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
