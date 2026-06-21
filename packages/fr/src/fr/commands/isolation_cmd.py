"""fr isolation — CLI over the isolation Target (worktree + devcontainer).

Plain-shell surface by design (agent-agnostic): any agent or a human drives
up/exec/status/down identically. IsolationError maps to exit 2.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import typer

from fr.isolation.local import LocalWorktreeDevcontainerTarget, subprocess_runner
from fr.isolation.types import IsolationError, list_states, load_state

isolation_app = typer.Typer(
    name="isolation",
    help="Isolated workspaces: git worktree + devcontainer.",
    no_args_is_help=True,
)

# Module-level runner seam so tests can monkeypatch every external call.
_runner = subprocess_runner

DEFAULT_BRANCH = "vk-iso/work"


def _target(repo: Path) -> LocalWorktreeDevcontainerTarget:
    return LocalWorktreeDevcontainerTarget(repo.resolve(), runner=_runner)


def _fail(err: IsolationError) -> None:
    typer.echo(f"error: {err}", err=True)
    raise typer.Exit(2)


@isolation_app.command()
def up(
    repo: Path = typer.Option(Path("."), help="Repo root (default: cwd)."),
    profile: str | None = typer.Option(
        None, help="Devcontainer profile (default: repo's configured default)."
    ),
    branch: str = typer.Option(DEFAULT_BRANCH, help="Branch for the worktree."),
    path: Path | None = typer.Option(
        None, help="Worktree path (default: ~/.cache/fr/worktrees/<repo>/<branch>)."
    ),
) -> None:
    """Create worktree + start the profile's devcontainer against it."""
    try:
        state = _target(repo).up(profile=profile, branch=branch, path=path)
    except IsolationError as err:
        _fail(err)
        return
    typer.echo(
        f"isolation up: worktree={state.worktree} profile={state.profile} branch={state.branch}"
    )
    if os.environ.get("CLAUDECODE"):
        typer.echo(
            "tip: register the worktree as a Claude Code working directory so the "
            "shell cwd persists there (no more `cd <worktree> && …` for host git/gh):\n"
            f"    /add-dir {state.worktree}"
        )


@isolation_app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def exec(  # noqa: A001 - typer command name
    ctx: typer.Context,
    repo: Path = typer.Option(Path("."), help="Repo root (default: cwd)."),
    branch: str | None = typer.Option(
        None, help="Isolation branch (default: the single active workspace)."
    ),
) -> None:
    """Run a command inside the isolation container (exit code passthrough)."""
    root = repo.resolve()
    # super-fr#299 part 3: with --branch omitted, resolve to the single active
    # workspace instead of a hardcoded vk-iso/work default — so `exec` after an
    # `up --branch feat/x` targets the workspace the operator actually has,
    # never a phantom default. Mirrors `status`/`down`'s no-branch handling.
    if branch is None:
        states = list_states(root)
        if len(states) > 1:
            _fail(
                IsolationError(
                    "multiple isolation workspaces — specify --branch: "
                    + ", ".join(s.branch for s in states)
                )
            )
            return
        state = states[0] if states else None
    else:
        state = load_state(root, branch)
    if state is None:
        msg = (
            f"no isolation workspace for branch {branch!r} — run `fr isolation up` first."
            if branch is not None
            else "no isolation workspace — run `fr isolation up` first."
        )
        _fail(IsolationError(msg))
        return
    argv = list(ctx.args)
    if argv and argv[0] == "--":
        argv = argv[1:]
    if not argv:
        _fail(IsolationError("nothing to run — usage: fr isolation exec -- CMD ..."))
        return
    raise typer.Exit(_target(repo).exec(state, argv))


@isolation_app.command()
def status(
    repo: Path = typer.Option(Path("."), help="Repo root (default: cwd)."),
    branch: str | None = typer.Option(None, help="Limit to one isolation branch."),
    format: str = typer.Option("text", "--format", help="text | json"),
) -> None:
    """Show worktree, container, and PR state for isolation workspaces."""
    root = repo.resolve()
    states = (
        [s for s in [load_state(root, branch)] if s is not None] if branch else list_states(root)
    )
    if branch and not states:
        _fail(IsolationError(f"no isolation workspace for branch {branch!r}."))
        return
    target = _target(root)
    rows = [target.status(s) for s in states]
    if format == "json":
        typer.echo(json.dumps(rows, indent=2))
        return
    if not rows:
        typer.echo("no isolation workspaces.")
        return
    for r in rows:
        pr = r["pr"]
        pr_text = f"{pr['state']} {pr.get('url', '')}".strip() if pr else "none"
        typer.echo(
            f"{r['branch']}: profile={r['profile']} container={r['container']} "
            f"worktree={r['worktree']} pr={pr_text}"
        )


@isolation_app.command()
def down(
    repo: Path = typer.Option(Path("."), help="Repo root (default: cwd)."),
    branch: str = typer.Option(DEFAULT_BRANCH, help="Isolation branch to tear down."),
    force: bool = typer.Option(False, "--force", help="Tear down even with an open PR."),
) -> None:
    """Stop the container, remove the worktree, drop the state."""
    root = repo.resolve()
    state = load_state(root, branch)
    if state is None:
        _fail(IsolationError(f"no isolation workspace for branch {branch!r}."))
        return
    try:
        _target(root).down(state, force=force)
    except IsolationError as err:
        _fail(err)
        return
    typer.echo(f"isolation down: {branch} cleaned up.")


@isolation_app.command(name="verify-merge")
def verify_merge(
    repo: Path = typer.Option(Path("."), help="Repo root (default: cwd)."),
    branch: str | None = typer.Option(
        None, help="Branch whose merge to verify (default: the single active workspace)."
    ),
    default_branch: str = typer.Option(
        "main", "--default-branch", help="Base branch the PR merged into."
    ),
) -> None:
    """Verify a merged branch's changes actually reached the base branch.

    Squash/rebase/merge-safe: checks content presence on `origin/<default>`,
    not commit ancestry (the #320 close-out). Exit 1 if not verified — the fix
    may have orphaned (a commit pushed after the PR merged).
    """
    root = repo.resolve()
    if branch is None:
        states = list_states(root)
        if len(states) > 1:
            _fail(
                IsolationError(
                    "multiple isolation workspaces — specify --branch: "
                    + ", ".join(s.branch for s in states)
                )
            )
            return
        state = states[0] if states else None
    else:
        state = load_state(root, branch)
    if state is None:
        _fail(
            IsolationError(
                f"no isolation workspace for branch {branch!r}."
                if branch is not None
                else "no isolation workspace — run `fr isolation up` first."
            )
        )
        return
    res = _target(root).verify_merge(state, default_branch=default_branch)
    if res["verified"]:
        typer.echo(
            f"verify-merge: {res['branch']} ✓ changes present on "
            f"origin/{default_branch}, PR MERGED."
        )
        return
    reasons = []
    if not res["fetched"]:
        reasons.append(f"could not fetch origin/{default_branch} (check may be stale)")
    if not res["changes_present"]:
        reasons.append(f"changes missing from origin/{default_branch}: {res['missing']}")
    if res["pr_state"] != "MERGED":
        reasons.append(f"PR state is {res['pr_state']} (expected MERGED)")
    typer.echo(
        f"verify-merge: {res['branch']} ✗ NOT verified — {'; '.join(reasons)}. "
        "Do NOT declare done; recover (cherry-pick onto the base branch / open a fresh PR).",
        err=True,
    )
    raise typer.Exit(1)
