"""fr isolation — CLI over the isolation Target (worktree + devcontainer).

Plain-shell surface by design (agent-agnostic): any agent or a human drives
up/exec/status/down identically. IsolationError maps to exit 2.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path

import typer

from fr.isolation.local import (
    LocalWorktreeDevcontainerTarget,
    _detached_gc_spawn,
    subprocess_runner,
)
from fr.isolation.types import (
    IsolationError,
    clear_repo_sentinels,
    list_states,
    load_state,
)

isolation_app = typer.Typer(
    name="isolation",
    help="Isolated workspaces: git worktree + devcontainer.",
    no_args_is_help=True,
)

# Module-level runner seam so tests can monkeypatch every external call.
_runner = subprocess_runner
# Production entry point opts into the real detached gc spawn on up/down; the
# library default is a no-op. Module seam so tests never fork a real sweep.
_gc_spawner = _detached_gc_spawn

DEFAULT_BRANCH = "vk-iso/work"


def _target(repo: Path) -> LocalWorktreeDevcontainerTarget:
    return LocalWorktreeDevcontainerTarget(repo.resolve(), runner=_runner, gc_spawner=_gc_spawner)


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
    base: str | None = typer.Option(
        None,
        "--base",
        help="Start-point for a NEW branch (e.g. origin/main, HEAD, <sha>). "
        "Given → no fetch, no default-branch resolution. New branches otherwise "
        "default to freshly-fetched origin/<default>.",
    ),
    no_fetch: bool = typer.Option(
        False,
        "--no-fetch",
        help="Skip git fetch; base a new branch on the local origin/<default> "
        "tracking ref (or HEAD if absent).",
    ),
) -> None:
    """Create worktree + start the profile's devcontainer against it."""
    try:
        state = _target(repo).up(
            profile=profile, branch=branch, path=path, base=base, no_fetch=no_fetch
        )
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
def restart(
    repo: Path = typer.Option(Path("."), help="Repo root (default: cwd)."),
    branch: str | None = typer.Option(
        None, help="Isolation branch (default: the single active workspace)."
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Immediate SIGKILL (docker restart --time=0) when a graceful stop hangs.",
    ),
) -> None:
    """Bounce a resource-wedged devcontainer, keeping the worktree intact.

    Unlike `down` + `up`, `restart` cycles only the container process tree — the
    worktree, node_modules, local DB stack, and in-container installs survive.
    """
    root = repo.resolve()
    # Mirror exec's no-branch resolution: the single active workspace, or error.
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
                f"no isolation workspace for branch {branch!r} — run `fr isolation up` first."
                if branch is not None
                else "no isolation workspace — run `fr isolation up` first."
            )
        )
        return
    try:
        container = _target(root).restart(state, force=force)
    except IsolationError as err:
        _fail(err)
        return
    typer.echo(f"isolation restart: {state.branch} bounced ({container}).")


@isolation_app.command()
def status(
    repo: Path = typer.Option(Path("."), help="Repo root (default: cwd)."),
    branch: str | None = typer.Option(None, help="Limit to one isolation branch."),
    format: str = typer.Option("text", "--format", help="text | json"),
    stats: bool = typer.Option(
        False,
        "--stats",
        help="Include container resource use (docker stats --no-stream) — opt-in "
        "to keep the default status fast; helps spot a thrashing container (#341).",
    ),
    push_check: bool = typer.Option(
        False,
        "--push-check",
        help="Read-only preflight for #377: worktree remotes, in-container SSH-agent "
        "presence (informational — expected absent), and a backend-aware pointer at "
        "the correct host-side push workflow. Never prints key material or "
        "token/socket contents.",
    ),
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
    if stats:
        for row, s in zip(rows, states):
            row["stats"] = target.stats(s)
    if push_check:
        for row, s in zip(rows, states):
            row["push_check"] = target.push_check(s)
    if format == "json":
        typer.echo(json.dumps(rows, indent=2))
        return
    if not rows:
        typer.echo("no isolation workspaces.")
        return
    for r in rows:
        pr = r["pr"]
        pr_text = f"{pr['state']} {pr.get('url', '')}".strip() if pr else "none"
        line = (
            f"{r['branch']}: profile={r['profile']} container={r['container']} "
            f"worktree={r['worktree']} pr={pr_text}"
        )
        if stats:
            st = r.get("stats")
            line += (
                f" stats=cpu={st['cpu']} mem={st['mem']} ({st['mem_perc']})" if st else " stats=n/a"
            )
        typer.echo(line)
        if push_check:
            pc = r.get("push_check")
            if pc:
                remotes_text = ", ".join(pc["remotes"]) if pc["remotes"] else "(none)"
                typer.echo(f"  remotes: {remotes_text}")
                ssh = pc["ssh_agent_in_container"]
                ssh_text = "present" if ssh["present"] else "absent (expected — informational only)"
                typer.echo(f"  ssh-agent-in-container: {ssh_text}")
                typer.echo(f"  {pc['guidance']}")


@isolation_app.command()
def down(
    repo: Path = typer.Option(Path("."), help="Repo root (default: cwd)."),
    branch: str = typer.Option(DEFAULT_BRANCH, help="Isolation branch to tear down."),
    force: bool = typer.Option(False, "--force", help="Tear down even with an open PR."),
    all_: bool = typer.Option(
        False,
        "--all",
        help="Tear down EVERY workspace for the repo and clear the pipeline "
        "sentinel(s) — the escape from an orphaned-sentinel deadlock (#341).",
    ),
) -> None:
    """Stop the container, remove the worktree, drop the state.

    With --all, ignore --branch: tear down all workspaces (keeping any with an
    OPEN PR unless --force) and clear this repo's pipeline sentinel(s).
    """
    root = repo.resolve()
    if all_:
        _down_all(root, force=force)
        return
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


def _down_all(root: Path, force: bool) -> None:
    """Tear down every workspace + drop session sentinel(s) (#341 Task 2A).

    A workspace whose PR is still OPEN is KEPT (never silently destroyed) unless
    --force — that open-PR check is the only IsolationError `down` raises, so
    "kept" always means an open PR. Sentinels are cleared regardless — `down
    --all` is the deliberate "end this pipeline" lever, with the guard self-heal
    as the lazy backstop.
    """
    target = _target(root)
    torn: list[str] = []
    kept: list[str] = []
    for state in list_states(root):
        try:
            target.down(state, force=force)
            torn.append(state.branch)
        except IsolationError:
            kept.append(state.branch)
    cleared = clear_repo_sentinels(root)
    summary = f"isolation down --all: {len(torn)} torn down"
    if kept:
        summary += f", {len(kept)} kept (open PR — rerun with --force): {', '.join(kept)}"
    summary += f", {cleared} sentinel(s) cleared."
    typer.echo(summary)


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


@isolation_app.command()
def gc(
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Classify + report only; mutate nothing."
    ),
    format: str = typer.Option("text", "--format", help="text | json"),
) -> None:
    """Reconcile isolation workspaces host-wide (#354).

    Tears down workspaces whose PR merged, skips open PRs, warns on no-PR work,
    and reaps orphaned containers — so end-to-end runs no longer depend on a
    human running `down` in the originating session. Fired opportunistically on
    every up/down; also runnable standalone or on a schedule.
    """
    actions = _target(Path.cwd()).gc(dry_run=dry_run)
    if format == "json":
        typer.echo(json.dumps([asdict(a) for a in actions], indent=2))
        return
    if not actions:
        typer.echo("gc: no isolation workspaces.")
        return
    for a in actions:
        line = f"gc: {a.branch or a.worktree}: {a.verdict} → {a.action}"
        if a.detail:
            line += f" ({a.detail})"
        typer.echo(line)
