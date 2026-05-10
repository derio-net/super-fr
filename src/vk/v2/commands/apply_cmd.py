"""`vk v2 apply` CLI — render + observe + diff + apply for a plan.

Wires the library functions into a typer command. The real `GhClient`
implementation lands in Phase 4 alongside the v1 retirement; until
then `--dry-run` is the only safe production usage. Tests inject
`FakeGhClient` via the `_make_gh_client` factory hook.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.console import Console

from vk.v2.apply import apply
from vk.v2.diff import (
    Diff,
    IssueBodyChange,
    IssueCreate,
    IssueLabelChange,
    IssueStateChange,
    RepoLabelEnsure,
    diff,
)
from vk.v2.observe import observe
from vk.v2.parser import PlanSchemaError, parse
from vk.v2.render import render

if TYPE_CHECKING:
    from vk.v2.ghclient import GhClient

console = Console()
err_console = Console(stderr=True)

# Single-command app — registered as a leaf via add_typer in v2/cli.py


def _make_gh_client() -> GhClient:
    """Factory hook for the production GhClient (wired in Phase 4).

    Tests monkeypatch this to inject FakeGhClient.
    """
    raise NotImplementedError(
        "Real GhClient implementation lands in Phase 4. "
        "Tests should monkeypatch vk.v2.commands.apply_cmd._make_gh_client."
    )


def _format_diff(d: Diff) -> str:
    """Human-readable summary of mutations."""
    if not d.mutations:
        return "no mutations — already in sync."
    lines: list[str] = []
    for m in d.mutations:
        if isinstance(m, RepoLabelEnsure):
            lines.append(f"  ensure labels on {m.repo}: {sorted(m.labels)}")
        elif isinstance(m, IssueCreate):
            lines.append(f"  create Issue on {m.repo} for phase {m.phase_number}: {m.title!r}")
        elif isinstance(m, IssueLabelChange):
            lines.append(
                f"  edit labels on {m.repo}#{m.issue_number}: +{sorted(m.add)} -{sorted(m.remove)}"
            )
        elif isinstance(m, IssueStateChange):
            lines.append(f"  set state on {m.repo}#{m.issue_number} to {m.new_state}")
        elif isinstance(m, IssueBodyChange):
            lines.append(f"  update body on {m.repo}#{m.issue_number} ({len(m.new_body)} chars)")
    return "\n".join(lines)


def _apply_one(plan_dir: Path, gh: GhClient, *, dry_run: bool) -> tuple[int, str]:
    """Apply one plan with an injected GhClient. Returns (exit_code, output)."""
    try:
        plan = parse(plan_dir)
    except PlanSchemaError as e:
        return 5, f"parse error: {e}"

    observed = observe(plan, gh)
    rendered = render(plan, observed)
    d = diff(rendered, observed, plan=plan)

    parts = [f"plan: {plan.meta.plan}", _format_diff(d)]
    if rendered.warnings:
        parts.append("\nwarnings:")
        for w in rendered.warnings:
            parts.append(f"  [{w.severity}] {w.message}")

    if dry_run:
        return 0, "\n".join(parts)

    result = apply(d, gh)
    if result.failures:
        parts.append(f"\n{len(result.failures)} failure(s):")
        for f in result.failures:
            parts.append(f"  {type(f.mutation).__name__}: {f.error}")
        return 4, "\n".join(parts)
    if result.created_issues:
        parts.append("\ncreated:")
        for phase_n, url in result.created_issues.items():
            parts.append(f"  phase {phase_n}: {url}")
    return 0, "\n".join(parts)


def apply_command(
    plan_dir: Path | None = typer.Argument(None, help="Path to plan folder."),
    all_plans: bool = typer.Option(False, "--all", help="Walk all plans in current repo."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show diff without mutating."),
) -> None:
    """Apply a v2 plan to GitHub (render → observe → diff → mutate)."""
    if all_plans and plan_dir is not None:
        err_console.print("--all and plan_dir are mutually exclusive")
        raise typer.Exit(2)
    if not all_plans and plan_dir is None:
        err_console.print("Either provide a plan_dir argument or use --all")
        raise typer.Exit(2)

    if all_plans:
        plans_dir = Path.cwd() / "docs" / "superpowers" / "plans"
        if not plans_dir.is_dir():
            err_console.print(f"plans dir not found: {plans_dir}")
            raise typer.Exit(2)
        targets = sorted(p for p in plans_dir.iterdir() if p.is_dir())
        if not targets:
            console.print("no plan folders found.")
            return
    else:
        assert plan_dir is not None
        targets = [plan_dir]

    gh = _make_gh_client()  # tests monkeypatch this
    overall_rc = 0
    for t in targets:
        rc, output = _apply_one(t, gh, dry_run=dry_run)
        console.print(output)
        if rc != 0:
            overall_rc = max(overall_rc, rc)
    if overall_rc:
        raise typer.Exit(overall_rc)
