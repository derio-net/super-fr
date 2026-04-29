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


@admin_app.callback()
def _admin() -> None:
    """Operator-driven cross-repo administration."""


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
    existing: list[dict[str, str | None]],
    registry: list[_labels.LabelDef],
) -> list[LabelAction]:
    """Compute per-label actions to bring existing in line with the registry.

    ``existing`` comes from the GitHub API which returns ``"description": null``
    for labels with no description — hence ``str | None`` values.
    """
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
        # Use `or ""` (not .get(key, "")) because GitHub returns
        # {"description": null} and dict.get returns None when the key
        # exists with a null value — the default is only used when the
        # key is absent entirely.
        cur_color = (cur.get("color") or "").lower()
        cur_desc = cur.get("description") or ""
        if cur_color == ld.color.lower() and cur_desc == ld.description:
            actions.append(LabelAction(kind="unchanged", name=ld.name))
        else:
            actions.append(
                LabelAction(
                    kind="update",
                    name=ld.name,
                    old_color=cur.get("color") or "",
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
    existing: list[dict[str, str | None]],
) -> list[LabelAction]:
    """Return remove actions for default labels with zero attached Issues.

    Defaults with attached Issues are silently skipped — that's user data.
    """
    actions: list[LabelAction] = []
    for lbl in existing:
        name = lbl.get("name") or ""
        if name.lower() not in DEFAULT_LABELS:
            continue
        if gh.count_issues_with_label(repo=repo, name=name) == 0:
            actions.append(
                LabelAction(
                    kind="remove",
                    name=name,
                    old_color=lbl.get("color") or "",
                    old_desc=lbl.get("description") or "",
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
        help="Print planned changes without mutating (default). Pass --apply to execute.",
    ),
    yes: bool = typer.Option(
        False, "--yes", help="Apply immediately; implies --apply, overrides --dry-run."
    ),
) -> None:
    """Sync repo labels to the canonical registry across one or many repos."""
    # --yes is a convenience shorthand for --apply; it overrides the default
    # dry-run mode.  Note: --dry-run/--apply is a bool toggle whose default
    # is True (dry-run), so we cannot distinguish "user passed --dry-run
    # explicitly" from "default was used" — mutual-exclusion enforcement
    # would require changing the flag structure and is deferred to Phase 3.
    is_dry_run = dry_run and not yes

    repos = _resolve_target_repos(owner=owner, repo=repo)
    if not repos:
        err_console.print(f"No repos found for owner '{owner}'.")
        raise typer.Exit(1)

    registry = list(_labels.LIFECYCLE.values())

    any_errors = False
    for slug in repos:
        # Per-repo progress summary lines go to stdout; per-repo errors go to
        # err_console (stderr) so CI pipelines can grep stderr for failures
        # without noise from normal output.  Fatal command-level errors (e.g.
        # "no repos found") also use err_console.
        try:
            existing = gh.list_labels(repo=slug)
            actions = _diff_labels(existing=existing, registry=registry)
            if remove_defaults:
                actions += _default_label_actions(repo=slug, existing=existing)
        except (gh.GhError, ValueError) as exc:
            # ValueError covers json.JSONDecodeError (malformed gh output).
            # GhError covers permission failures, 404s, and network errors —
            # including those raised inside _default_label_actions when
            # count_issues_with_label fails.  Both are non-blocking per spec.
            err_console.print(f"{slug}: failed: {exc}")
            any_errors = True
            continue

        _render_dryrun_table(repo=slug, actions=actions)

        if is_dry_run:
            continue

        # Apply mode
        repo_summary = {"created": 0, "updated": 0, "removed": 0, "unchanged": 0}
        try:
            for a in actions:
                if a.kind in ("create", "update"):
                    ld = next((d for d in registry if d.name == a.name), None)
                    if ld is None:
                        continue
                    gh.ensure_label(
                        repo=slug,
                        name=ld.name,
                        color=ld.color,
                        description=ld.description,
                    )
                    repo_summary["created" if a.kind == "create" else "updated"] += 1
                elif a.kind == "remove":
                    gh.delete_label(repo=slug, name=a.name)
                    repo_summary["removed"] += 1
                else:
                    repo_summary["unchanged"] += 1
        except gh.GhError as exc:
            err_console.print(f"{slug}: apply failed: {exc}")
            any_errors = True
            continue

        console.print(
            f"{slug}: {repo_summary['created']} created, "
            f"{repo_summary['updated']} updated, "
            f"{repo_summary['removed']} removed, "
            f"{repo_summary['unchanged']} unchanged."
        )

    if any_errors:
        raise typer.Exit(1)
