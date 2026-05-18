"""Library surface for the live VK bridge — `discover_plans` + `tick`.

The bridge daemon (`agent-images/kali/scripts/vk-issue-bridge.py`) consumes
these functions. They are intentionally NOT wired into the `vk` CLI — see
spec §"Bridge integration".

`VkMcpClient` is re-exported from `vk._mcp_client` for backwards
compatibility with the cross-repo bridge daemon. The per-phase MCP
dispatch sequence is funnelled through
`vk.bridge.dispatch.dispatch_phase` — see that module for the canonical
chain of MCP calls. Test B2 enforces single-source by failing if the
full chain appears in any other module under `src/`.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from vk import plan_ops
from vk._mcp_client import VkMcpClient
from vk._urls import parse_issue_url
from vk.apply import apply
from vk.bridge import config as _config
from vk.bridge import dedup as _dedup
from vk.bridge import metrics as _metrics
from vk.bridge import slots as _slots
from vk.bridge.dispatch import MCPDispatch, build_card_title, dispatch_phase
from vk.diff import diff
from vk.ghclient import GhClient
from vk.labels import VK_READY, VK_SYNCED
from vk.observe import observe
from vk.parser import Plan, PlanSchemaError, parse
from vk.plan_ops import PlanEditError
from vk.render import render
from vk.types import PhaseDoc

__all__ = ["TickResult", "VkMcpClient", "discover_plans", "tick"]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TickResult:
    """Counters for one `tick()` invocation, returned to the cron caller.

    - `synced`: VK board cards successfully created this tick.
    - `errors`: total failures accumulated (apply-side + per-phase MCP).
      Always equal to `len(failures)`.
    - `skipped`: `1` if this plan had no phases eligible for sync (all
      projected non-ready, or all already `vk-synced`), `0` otherwise.
      The unit is **plans**, not phases — bridges summing across plans
      get a count of idle plans.
    - `failures`: human-readable strings, one per error.
    """

    synced: int = 0
    errors: int = 0
    skipped: int = 0
    failures: tuple[str, ...] = ()


def _repo_checkout_root(repo: str) -> Path:
    """Resolve `owner/name` to a local checkout path.

    Matches the live bridge's REPOS_DIR convention (`~/repos/<name>`).
    Override the parent with `VK_REPOS_DIR` — used by tests and by any
    deployment where checkouts live somewhere other than `$HOME/repos`.
    """
    name = repo.split("/", 1)[1] if "/" in repo else repo
    base = os.environ.get("VK_REPOS_DIR")
    root = Path(base) if base else Path.home() / "repos"
    return root / name


def _any_phase_incomplete(plan: Plan) -> bool:
    """True iff at least one phase is not yet complete (per plan yaml).

    Yaml-only check — no gh API call. Skips fully-shipped plans where
    every phase has `state.completion.at` set; keeps plans where at
    least one phase is still in flight (either never dispatched, in
    progress, or PR-pending) so the bridge's tick can self-heal label
    drift on them.

    Pre-2026-05-18 used `_any_phase_is_vk_ready(plan, gh)` — required
    an observed `vk-ready` label on at least one Issue. That
    optimization had two failure modes:
      1. Operator stripping `vk-ready` (e.g., as race protection
         during a writeback PR) quarantined the plan from the bridge
         — tick never ran, so the label could never be re-projected.
      2. A freshly-dispatched plan whose writeback hadn't merged yet
         had `tracking_issue: None` for every phase → skipped here →
         no chance for tick to re-render.
    Switching to a yaml-only "incomplete" check fixes both, and is
    strictly cheaper (no gh API calls per plan).
    """
    return any(p.state.completion.at is None for p in plan.phases)


def discover_plans(repo: str, gh: GhClient) -> list[Plan]:
    """Walk `docs/superpowers/plans/` in `repo`, return plans with at least
    one incomplete phase.

    Returns `[]` (no exception) if the checkout is missing or the plans
    directory is absent. Individual unparseable plan folders are logged
    and skipped so a single malformed plan can't take down the cron tick.

    The `gh` parameter is kept for backward compatibility but no longer
    consulted — discovery is yaml-only since 2026-05-18 (see
    `_any_phase_incomplete` docstring for the bug-history).
    """
    del gh  # unused; kept in signature for backward compat
    repo_root = _repo_checkout_root(repo)
    plans_dir = repo_root / "docs" / "superpowers" / "plans"
    if not plans_dir.is_dir():
        return []
    out: list[Plan] = []
    for plan_dir in sorted(plans_dir.iterdir()):
        if not plan_dir.is_dir():
            continue
        if not (plan_dir / "_meta.yaml").exists():
            continue
        try:
            plan = parse(plan_dir)
        except PlanSchemaError as e:
            logger.warning("bridge: skipping unparseable plan %s: %s", plan_dir, e)
            continue
        if _any_phase_incomplete(plan):
            out.append(plan)
    return out


def tick(plan: Plan, gh: GhClient, vk_mcp: MCPDispatch) -> TickResult:
    """One cron iteration for a single plan.

    Pipeline: observe → render → diff → apply (GH-side only) → for each
    phase whose **rendered** labels say it's `vk-ready` but not yet
    `vk-synced`, delegate to `vk.bridge.dispatch.dispatch_phase` to
    create the VK card + workspace, then flip `vk-synced` on the GH
    Issue. The gate runs against the projected label set, not the
    pre-apply observation: an agent claiming the Issue between dispatch
    and this tick projects `in-progress` (no `vk-ready`), and the
    bridge correctly skips.

    GH-side `apply()` failures are accumulated rather than raised — they
    don't block per-phase VK syncs for phases whose projected state is
    still ready. Per-phase dispatch failures are likewise accumulated;
    if `dispatch_phase` raises, `vk-synced` is NOT added, so the next
    tick retries.

    Returns `skipped=1` when this plan had no phases eligible for sync
    so the cron caller can distinguish "nothing to do" from a real
    no-op apply. The unit is **plans**, not phases — sum across plans
    to count idle plans, not idle phases.
    """
    # Fresh repo lookup per tick so config drift propagates.
    _config.clear_repo_cache()

    observed = observe(plan, gh)
    rendered = render(plan, observed)
    d = diff(rendered, observed, plan=plan)
    apply_result = apply(d, gh, plan=plan)
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
        if VK_READY not in ri.labels or VK_SYNCED in ri.labels:
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
        # Slot gate: snapshot active workspaces once per tick, then
        # decrement the remaining-budget counter as we dispatch.
        try:
            budget = max(0, _slots.max_concurrent() - _slots.count_active_ws(vk_mcp))
        except Exception as e:  # noqa: BLE001 — never let slot-counting break a tick
            failures.append(f"slot check failed: {e}")
            budget = _slots.max_concurrent()

        # Dedup snapshot: one list_issues call covers every phase in this plan.
        try:
            existing_titles = _dedup.fetch_existing_titles(vk_mcp)
        except Exception as e:  # noqa: BLE001
            failures.append(f"dedup fetch failed: {e}")
            existing_titles = set()

        for phase, issue_repo, issue_number in eligible_phases:
            # Unknown-repo gate (D4) — dispatch against an unlisted repo
            # always fails server-side; refuse early with a clean reason.
            if not _config.is_known_repo(issue_repo, vk_mcp):
                failures.append(f"phase {phase.phase.number}: unknown repo {issue_repo!r}")
                _metrics.push_failure_total(reason="unknown_repo")
                continue

            would_be_title = build_card_title(issue_repo, issue_number)
            already_dispatched = would_be_title in existing_titles

            if not already_dispatched and budget <= 0:
                # No slot left — defer this phase to the next tick.
                deferred += 1
                continue

            # Split MCP-side and GH-side error paths so the `reason` label
            # on the failure metric points at the actually-broken system.
            # A dedup hit skips the MCP block entirely; the GH stamp still
            # runs so the next tick won't retry. In both cases we report a
            # `synced` outcome only when the GH stamp lands.
            if not already_dispatched:
                try:
                    dispatch_phase(plan, phase, vk_mcp)
                    budget -= 1
                except Exception as e:  # noqa: BLE001 — one bad MCP call mustn't kill the tick
                    failures.append(f"phase {phase.phase.number}: {e}")
                    _metrics.push_failure_total(reason="mcp_error")
                    continue

            try:
                gh.ensure_labels(issue_repo, [VK_SYNCED])
                gh.edit_issue_labels(
                    issue_repo,
                    issue_number,
                    add=frozenset({"vk-synced"}),
                    remove=frozenset(),
                )
                synced += 1
                _metrics.push_sync_total()
            except Exception as e:  # noqa: BLE001 — GH outage mustn't kill the tick
                failures.append(f"phase {phase.phase.number}: gh stamp failed: {e}")
                _metrics.push_failure_total(reason="gh_error")

    # `skipped` semantics: number of would-be-dispatched phases left on the
    # floor this tick. When no phase was eligible at all, return 1 so the
    # caller can count idle plans (legacy behavior preserved).
    skipped = deferred if eligible_phases else 1
    _metrics.push_heartbeat()
    return TickResult(
        synced=synced,
        errors=len(failures),
        skipped=skipped,
        failures=tuple(failures),
    )
