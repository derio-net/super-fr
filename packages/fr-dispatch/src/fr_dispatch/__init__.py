"""Queue protocol + runner framework — `discover_plans` + `tick`.

Runner-agnostic since the super-fr split (2026-06-05 design): `tick`
orchestrates observe → render → diff → apply → dispatch against the
`fr_dispatch.protocols.Runner` contract; the VibeKanban adapter
(`fr_vk`) is the first implementation. These functions are intentionally
NOT wired into the CLI — the bridge daemon (`python -m fr_vk.bridge`)
consumes them as a library.

The per-phase backend dispatch is the runner's `dispatch()`; test B2
enforces single-source on the VK adapter's MCP chain. Issue creation is
operator-only (`apply(skip_issue_create=True)`) — see the 2026-05-18
incident.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from fr import plan_ops
from fr._urls import parse_issue_url
from fr.apply import apply
from fr.diff import diff
from fr.ghclient import GhClient
from fr.labels import FR_READY, FR_SYNCED
from fr.observe import observe
from fr.parser import Plan, PlanSchemaError, parse
from fr.plan_ops import PlanEditError
from fr.render import render
from fr.types import PhaseDoc

from fr_dispatch.metrics import MetricsPusher, NullMetrics
from fr_dispatch.protocols import Runner

__all__ = ["Runner", "TickResult", "discover_plans", "tick"]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TickResult:
    """Counters for one `tick()` invocation, returned to the cron caller.

    - `synced`: phases successfully handed to the runner this tick.
    - `errors`: total failures accumulated (apply-side + per-phase).
    - `skipped`: deferred phases (slot budget) when any were eligible;
      1 when the plan had nothing eligible (idle-plan counting).
    - `failures`: human-readable accumulated failure strings.
    """

    synced: int
    errors: int
    skipped: int
    failures: tuple[str, ...] = ()


def _plan_projects_ready(plan: Plan, gh: GhClient) -> bool:
    """True iff rendering the plan projects a phase as ready, not synced.

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
        if FR_READY in ri.labels and FR_SYNCED not in ri.labels:
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


def tick(
    plan: Plan,
    gh: GhClient,
    runner: Runner,
    *,
    metrics: MetricsPusher | None = None,
) -> TickResult:
    """One cron iteration for a single plan, against one runner.

    Pipeline: observe → render → diff → apply (GH-side only,
    `skip_issue_create=True`) → for each phase whose **rendered** labels
    say it's ready but not yet synced, `runner.dispatch(...)`, then flip
    the synced label on the GH Issue. The gate runs against the
    projected label set, not the pre-apply observation: an agent
    claiming the Issue between dispatch and this tick projects
    in-progress (no ready label), and the loop correctly skips.

    All failure paths accumulate; a raising `runner.dispatch` leaves the
    synced stamp unwritten so the next tick retries. `skipped` counts
    slot-deferred phases (or 1 when nothing was eligible — idle-plan
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
            failures.append(f"phase {phase_n}: writeback failed: {e}")

    eligible_phases: list[tuple[PhaseDoc, str, int]] = []
    for phase in plan.phases:
        if phase.phase.number not in observed.phases:
            continue
        ri = rendered.issue_per_phase.get(phase.phase.number)
        tracking = phase.phase.tracking_issue
        if ri is None or not tracking:  # pragma: no cover — defensive guard
            continue
        if FR_READY not in ri.labels or FR_SYNCED in ri.labels:
            continue
        try:
            issue_repo, issue_number = parse_issue_url(tracking)
        except Exception as e:  # noqa: BLE001 — one malformed URL mustn't kill the tick
            failures.append(f"phase {phase.phase.number}: {e}")
            continue
        eligible_phases.append((phase, issue_repo, issue_number))

    synced = 0
    deferred = 0
    if eligible_phases:
        try:
            blocker = runner.preflight()
        except Exception as e:  # noqa: BLE001
            blocker = f"runner preflight raised: {e}"
        if blocker:
            for phase, _, _ in eligible_phases:
                failures.append(f"phase {phase.phase.number}: {blocker}")
                m.push_failure_total(reason="preflight")
            m.push_heartbeat()
            return TickResult(
                synced=0,
                errors=len(failures),
                skipped=len(eligible_phases),
                failures=tuple(failures),
            )

        # Slot gate: snapshot capacity once per tick, decrement as we go.
        try:
            budget = max(0, runner.slot_budget())
        except Exception as e:  # noqa: BLE001 — never let slot-counting break a tick
            failures.append(f"slot check failed: {e}")
            budget = 0

        # Dedup snapshot: one backend call covers every phase in this plan.
        try:
            existing = runner.existing_dispatches()
        except Exception as e:  # noqa: BLE001
            failures.append(f"dedup fetch failed: {e}")
            existing = set()

        for phase, issue_repo, issue_number in eligible_phases:
            try:
                repo_ok = runner.can_dispatch_repo(issue_repo)
            except Exception as e:  # noqa: BLE001
                failures.append(f"phase {phase.phase.number}: repo gate failed: {e}")
                m.push_failure_total(reason="repo_gate")
                continue
            if not repo_ok:
                failures.append(f"phase {phase.phase.number}: unknown repo {issue_repo!r}")
                m.push_failure_total(reason="unknown_repo")
                continue

            already_dispatched = runner.dedup_key(issue_repo, issue_number) in existing

            if not already_dispatched and budget <= 0:
                # No slot left — defer this phase to the next tick.
                deferred += 1
                continue

            # Split backend-side and GH-side error paths so the `reason`
            # label on the failure metric points at the broken system. A
            # dedup hit skips the backend call entirely; the GH stamp
            # still runs so the next tick won't retry.
            if not already_dispatched:
                try:
                    runner.dispatch(plan, phase, issue_repo, issue_number)
                    budget -= 1
                except Exception as e:  # noqa: BLE001 — one bad backend call mustn't kill the tick
                    failures.append(f"phase {phase.phase.number}: {e}")
                    m.push_failure_total(reason="backend_error")
                    continue

            try:
                gh.ensure_labels(issue_repo, [FR_SYNCED])
                gh.edit_issue_labels(
                    issue_repo,
                    issue_number,
                    add=frozenset({FR_SYNCED.name}),
                    remove=frozenset(),
                )
                synced += 1
                m.push_sync_total()
            except Exception as e:  # noqa: BLE001 — GH outage mustn't kill the tick
                failures.append(f"phase {phase.phase.number}: gh stamp failed: {e}")
                m.push_failure_total(reason="gh_error")

    skipped = deferred if eligible_phases else 1
    m.push_heartbeat()
    return TickResult(
        synced=synced,
        errors=len(failures),
        skipped=skipped,
        failures=tuple(failures),
    )
