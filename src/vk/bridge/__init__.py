"""Library surface for the live VK bridge — `discover_plans` + `tick`.

The bridge daemon (`agent-images/kali/scripts/vk-issue-bridge.py`) consumes
these functions. They are intentionally NOT wired into the `vk` CLI — see
spec §"Bridge integration".

`VkMcpClient` is a Protocol describing the subset of the live MCP client
the bridge needs; the library never instantiates one. The live
implementation lives in `agent-images/kali/scripts/vk_mcp_client.py`.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from vk._urls import parse_issue_url
from vk.apply import apply
from vk.diff import diff
from vk.ghclient import GhClient
from vk.labels import VK_READY, VK_SYNCED
from vk.observe import observe
from vk.parser import Plan, PlanSchemaError, parse
from vk.render import render

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


class VkMcpClient(Protocol):
    """Subset of the MCP client surface the bridge needs.

    The live implementation lives in agent-images/kali/scripts/
    vk_mcp_client.py; we only describe what we call here so tests
    can stub it without dragging the MCP wire format in.
    """

    def create_card(self, *, title: str, body: str, issue_url: str) -> str: ...

    def update_card(self, *, card_id: str, status: str) -> None: ...


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


def _any_phase_is_vk_ready(plan: Plan, gh: GhClient) -> bool:
    """True iff at least one phase Issue carries `vk-ready`."""
    for phase in plan.phases:
        url = phase.phase.tracking_issue
        if not url:
            continue
        try:
            repo, number = parse_issue_url(url)
            info = gh.view_issue(repo, number)
        except Exception as e:  # noqa: BLE001 — bridge must survive one bad phase
            logger.warning("bridge: failed to view %s: %s", url, e)
            continue
        if "vk-ready" in set(info.get("labels", [])):
            return True
    return False


def discover_plans(repo: str, gh: GhClient) -> list[Plan]:
    """Walk `docs/superpowers/plans/` in `repo`, return plans with a vk-ready phase.

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
        if not plan_dir.is_dir():
            continue
        if not (plan_dir / "_meta.yaml").exists():
            continue
        try:
            plan = parse(plan_dir)
        except PlanSchemaError as e:
            logger.warning("bridge: skipping unparseable plan %s: %s", plan_dir, e)
            continue
        if _any_phase_is_vk_ready(plan, gh):
            out.append(plan)
    return out


def tick(plan: Plan, gh: GhClient, vk_mcp: VkMcpClient) -> TickResult:
    """One cron iteration for a single plan.

    Pipeline: observe → render → diff → apply (GH-side only) → sync VK
    board cards for phases whose **rendered** labels say they're
    `vk-ready` but not yet `vk-synced`. The gate runs against the
    projected label set (`rendered.issue_per_phase[N].labels`), not the
    pre-apply observation: if an agent claimed the Issue between dispatch
    and this tick, the renderer projects `in-progress` (no `vk-ready`)
    and the bridge correctly skips. `vk-synced` is preserved by the
    renderer from observed labels (see `render.py`) so the gate stays
    accurate after the first successful sync.

    GH-side `apply()` failures are accumulated rather than raised — they
    don't block per-phase VK syncs for phases whose projected state is
    still ready. Per-phase MCP failures are likewise accumulated; if
    `create_card` raises, `vk-synced` is NOT added, so the next tick
    retries.

    Returns `skipped=1` when this plan had no phases eligible for sync
    so the cron caller can distinguish "nothing to do" from a real
    no-op apply. The unit is **plans**, not phases — sum across plans
    to count idle plans, not idle phases.
    """
    observed = observe(plan, gh)
    rendered = render(plan, observed)
    d = diff(rendered, observed, plan=plan)
    apply_result = apply(d, gh, plan=plan)
    failures: list[str] = [f.error for f in apply_result.failures]

    synced = 0
    eligible = 0
    for phase in plan.phases:
        if phase.phase.number not in observed.phases:
            continue
        ri = rendered.issue_per_phase.get(phase.phase.number)
        tracking = phase.phase.tracking_issue
        if ri is None or not tracking:  # pragma: no cover — defensive guard
            continue
        rlabels = ri.labels
        if VK_READY not in rlabels or VK_SYNCED in rlabels:
            continue
        eligible += 1
        try:
            issue_repo, issue_number = parse_issue_url(tracking)
            vk_mcp.create_card(
                title=phase.phase.title,
                body=ri.body,
                issue_url=tracking,
            )
            gh.edit_issue_labels(
                issue_repo,
                issue_number,
                add=frozenset({"vk-synced"}),
                remove=frozenset(),
            )
            synced += 1
        except Exception as e:  # noqa: BLE001 — one bad MCP call mustn't kill the tick
            failures.append(f"phase {phase.phase.number}: {e}")

    skipped = 1 if eligible == 0 else 0
    return TickResult(
        synced=synced,
        errors=len(failures),
        skipped=skipped,
        failures=tuple(failures),
    )
