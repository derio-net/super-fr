"""`fr undispatch` CLI — the inverse of dispatch (2026-06-05 spec, Phase 6).

For "these Issues were created in error": close each phase's tracking
Issue with a comment + reason `not planned`, then null the
`tracking_issue` field via `plan_ops.clear_tracking_issue`. Makes new
state, never history surgery (the dispatch commit stays). VK cards and
workspaces are deliberately untouched — the bridge's `reap_orphans`
archives workspaces once cards lack live Issues.

Idempotent: re-running skips already-closed Issues and already-null
fields. Per-phase failures accumulate (apply's doctrine) — the field is
NOT nulled when the gh side failed, so a retry can find the Issue again.

Exit codes: 0 done (or clean no-op); 2 usage / legacy layout;
4 gh failures (partial work reported); 5 parse error.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.console import Console

from fr import plan_ops
from fr._urls import parse_issue_url
from fr.commands.common import require_migrated_layout
from fr.parser import PlanSchemaError, parse
from fr.plan_ops import PlanEditError

if TYPE_CHECKING:
    from fr.ghclient import GhClient

console = Console()
err_console = Console(stderr=True)


def _make_gh_client() -> GhClient:
    """Factory hook — tests monkeypatch this (same seam as apply_cmd)."""
    from fr.real_ghclient import RealGhClient

    return RealGhClient()


def undispatch_command(
    plan_dir: Path = typer.Argument(..., help="Path to plan folder."),
    yes: bool = typer.Option(
        False,
        "--yes",
        help="Close Issues and null tracking_issue fields. Default is a preview.",
    ),
) -> None:
    """Close a plan's tracking Issues (reason: not planned) and null the
    tracking_issue fields — one command instead of N manual gh calls."""
    require_migrated_layout()
    gh = _make_gh_client()

    try:
        plan = parse(plan_dir)
    except PlanSchemaError as e:
        err_console.print(f"parse error: {e}")
        raise typer.Exit(5) from e

    tracked = [(p, p.phase.tracking_issue) for p in plan.phases if p.phase.tracking_issue]
    if not tracked:
        typer.echo("nothing to undispatch — no phase has a tracking_issue.")
        return

    failures: list[str] = []
    for phase, url in tracked:
        n = phase.phase.number
        assert url is not None
        try:
            repo, issue_n = parse_issue_url(url)
        except ValueError as e:
            failures.append(f"phase {n}: malformed tracking_issue {url!r}: {e}")
            continue

        if not yes:
            typer.echo(f"  phase {n}: would close {url} (not planned) and null tracking_issue")
            continue

        # Close (skip when already closed — idempotency).
        try:
            state = str(gh.view_issue(repo, issue_n).get("state", ""))
        except Exception as e:  # noqa: BLE001 — accumulate, keep going
            # A DELETED issue is terminal, not transient: retrying can
            # never succeed, so treat it as already-gone and fall through
            # to clearing the field (review finding, 2026-06-06).
            # Transient failures (network, auth) accumulate and RETAIN
            # the field so a retry can find the Issue again.
            msg = str(e).lower()
            gone = isinstance(e, KeyError) or "404" in msg or "could not resolve" in msg
            if not gone:
                failures.append(f"phase {n}: view {repo}#{issue_n} failed: {e}")
                continue
            typer.echo(f"  phase {n}: {url} no longer exists — clearing the field")
            state = "CLOSED"
        if state != "CLOSED":
            try:
                gh.comment_issue(
                    repo,
                    issue_n,
                    f"fr undispatch: dispatched in error from {plan.meta.plan}",
                )
                gh.edit_issue_state(repo, issue_n, state="CLOSED", reason="not planned")
            except Exception as e:  # noqa: BLE001 — keep field for retry
                failures.append(f"phase {n}: close {repo}#{issue_n} failed: {e}")
                continue
            typer.echo(f"  phase {n}: closed {url} (not planned)")
        else:
            typer.echo(f"  phase {n}: {url} already closed — skipping close")

        # Null the field only after the gh side is settled.
        try:
            cleared = plan_ops.clear_tracking_issue(plan_dir, n)
        except (PlanEditError, OSError, PlanSchemaError) as e:
            failures.append(f"phase {n}: tracking_issue writeback failed: {e}")
            continue
        if cleared:
            typer.echo(f"  phase {n}: tracking_issue cleared")

    if failures:
        typer.echo(f"\n{len(failures)} failure(s):")
        for f in failures:
            typer.echo(f"  {f}")
        raise typer.Exit(4)
    if not yes:
        typer.echo("\n(dry-run; pass --yes to undispatch)")
