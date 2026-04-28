"""vk admin — operator-driven cross-repo administration."""

from __future__ import annotations

from dataclasses import dataclass

import typer
from rich.console import Console
from rich.table import Table

from vk import gh
from vk import labels as _labels

console = Console()
err_console = Console(stderr=True)

admin_app = typer.Typer(help="Operator-driven cross-repo administration.")


@dataclass(frozen=True)
class LabelAction:
    kind: str  # "create" | "update" | "remove" | "unchanged"
    name: str
    old_color: str = ""
    new_color: str = ""
    old_desc: str = ""
    new_desc: str = ""


def _diff_labels(
    *,
    existing: list[dict[str, str]],
    registry: list[_labels.LabelDef],
) -> list[LabelAction]:
    """Compute per-label actions to bring existing in line with the registry."""
    by_name = {e["name"]: e for e in existing}
    actions: list[LabelAction] = []
    for ld in registry:
        cur = by_name.get(ld.name)
        if cur is None:
            actions.append(
                LabelAction(
                    kind="create",
                    name=ld.name,
                    new_color=ld.color,
                    new_desc=ld.description,
                )
            )
            continue
        cur_color = cur.get("color", "").lower()
        cur_desc = cur.get("description", "")
        if cur_color == ld.color.lower() and cur_desc == ld.description:
            actions.append(LabelAction(kind="unchanged", name=ld.name))
        else:
            actions.append(
                LabelAction(
                    kind="update",
                    name=ld.name,
                    old_color=cur.get("color", ""),
                    new_color=ld.color,
                    old_desc=cur_desc,
                    new_desc=ld.description,
                )
            )
    return actions


DEFAULT_LABELS = frozenset(
    {
        "bug",
        "documentation",
        "duplicate",
        "enhancement",
        "good first issue",
        "help wanted",
        "invalid",
        "question",
        "wontfix",
    }
)


def _default_label_actions(
    *,
    repo: str,
    existing: list[dict[str, str]],
) -> list[LabelAction]:
    """Return remove actions for default labels with zero attached Issues.

    Defaults with attached Issues are silently skipped — that's user data.
    """
    actions: list[LabelAction] = []
    for lbl in existing:
        name = lbl.get("name", "")
        if name not in DEFAULT_LABELS:
            continue
        if gh.count_issues_with_label(repo=repo, name=name) == 0:
            actions.append(
                LabelAction(
                    kind="remove",
                    name=name,
                    old_color=lbl.get("color", ""),
                    old_desc=lbl.get("description", ""),
                )
            )
    return actions


def _render_dryrun_table(*, repo: str, actions: list[LabelAction]) -> None:
    table = Table(title=repo, show_header=True, header_style="bold")
    table.add_column("Action")
    table.add_column("Label")
    table.add_column("Detail")
    for a in actions:
        if a.kind == "create":
            table.add_row("+ create", a.name, f"color={a.new_color}")
        elif a.kind == "update":
            table.add_row("~ update", a.name, f"{a.old_color or '?'} → {a.new_color}")
        elif a.kind == "remove":
            table.add_row("- remove", a.name, "(default, no Issues)")
        else:
            table.add_row("= unchanged", a.name, "")
    console.print(table)


def _resolve_target_repos(*, owner: str, repo: str | None) -> list[str]:
    """Resolve target repos as `owner/name` slugs.

    With explicit `repo`, returns the single slug. Without, enumerates
    non-archived repos under `owner` via gh.list_repos.
    """
    if repo:
        return [f"{owner}/{repo}"]
    return [f"{owner}/{r['name']}" for r in gh.list_repos(owner=owner)]


@admin_app.command(name="labels-sync")
def labels_sync(
    owner: str = typer.Option(..., "--owner", help="GitHub owner / org."),
    repo: str | None = typer.Option(
        None, "--repo", help="Single repo (without owner). Default: all repos under owner."
    ),
    remove_defaults: bool = typer.Option(
        False,
        "--remove-defaults",
        help="Also remove GitHub default labels with zero attached Issues.",
    ),
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--apply",
        help="Print planned changes without mutating (default). Use --apply or --yes.",
    ),
    yes: bool = typer.Option(False, "--yes", help="Apply changes without confirmation."),
) -> None:
    """Sync repo labels to the canonical registry across one or many repos."""
    if yes:
        dry_run = False

    repos = _resolve_target_repos(owner=owner, repo=repo)
    if not repos:
        err_console.print(f"No repos found for owner '{owner}'.")
        raise typer.Exit(1)

    registry = list(_labels.LIFECYCLE.values())

    any_errors = False
    for slug in repos:
        try:
            existing = gh.list_labels(repo=slug)
        except gh.GhError as exc:
            err_console.print(f"{slug}: list-labels failed: {exc}")
            any_errors = True
            continue

        actions = _diff_labels(existing=existing, registry=registry)
        if remove_defaults:
            actions += _default_label_actions(repo=slug, existing=existing)

        _render_dryrun_table(repo=slug, actions=actions)

        if dry_run:
            continue
        # Apply mode lands in Phase 3 of this plan.
        raise NotImplementedError("apply mode lands in Phase 3 of this plan.")

    if any_errors:
        raise typer.Exit(1)
