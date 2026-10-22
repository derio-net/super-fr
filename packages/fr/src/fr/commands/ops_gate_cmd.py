"""`fr ops gate --run <id>` — the DevOps stage (spec 2026-10-22-fr-ops R15, §I).

The sequencer is `fr.ops.gate`; this module resolves the run and wires the real
ports: `fr.triage.gitseam` runs git and this `fr` (on the harness host, in the base
checkout or the ops workspace), the forge is the `GhClient` adapter, and the
operator's terminal is `fr.ops.apply.TtyPrompt`. It refuses a non-interactive context
(the artifact gate's `is_interactive`: that is how a delivering agent is kept out),
previews by default and acts with `--yes`. Registered on `fr ops` by `ops_cmd`.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, Any, NoReturn

import typer


def _refuse(message: str) -> NoReturn:
    typer.echo(f"fr ops gate: {message}", err=True)
    raise typer.Exit(code=2)


def _interactive() -> bool:
    """An operator at a terminal (the artifact gate's predicate); a seam for tests."""
    from fr.artifacts.trigger import is_interactive

    return is_interactive()


def _forge(url: str) -> Any:
    """The forge adapter for *url*; a seam for tests."""
    from fr.hostclient import client_for_url

    return client_for_url(url)


def _prompt() -> Any:
    from fr.ops.apply import TtyPrompt

    return TtyPrompt()


class OpsWorkspace:
    """The ops workspace on the host: git through `gitseam.Worktree`, and this `fr`
    with the workspace as its checkout."""

    def __init__(self, path: Path) -> None:
        from fr.triage.gitseam import Worktree

        self.path = path
        self._tree = Worktree(path)

    def head(self) -> str:
        return self._tree.head()

    def show(self, ref: str, path: str) -> str | None:
        return self._tree.show(ref, path)

    def fr(self, args: Sequence[str], *, terminal: bool = False) -> tuple[int, str]:
        from fr.triage.gitseam import run_this_fr

        return run_this_fr(list(args), self.path, terminal=terminal)

    def commit_paths(self, paths: list[str], message: str) -> str | None:
        return self._tree.commit_paths(paths, message)

    def rebase_onto(self, new_base: str, upstream: str) -> None:
        from fr.triage.gitseam import git

        git(["fetch", "--quiet", "origin"], self.path)
        self._tree.rebase_onto(new_base, upstream)

    def push(self, branch: str, lease: str | None = None) -> None:
        """fr owns the ops branch and stage 3 rebases it, so a later push replaces it, but
        only while the remote is still at the sha fr last pushed (`--force-with-lease`);
        the first push creates it, refusing a branch someone else already holds."""
        from fr.triage.gitseam import GitError, git, git_ok

        ref = f"refs/heads/{branch}"
        if lease is None:
            if git_ok(["ls-remote", "--exit-code", "origin", ref], self.path):
                raise GitError(f"origin already has {branch} and fr never pushed it; refusing")
            git(["push", "origin", f"HEAD:{ref}"], self.path)
            return
        git(["push", f"--force-with-lease={ref}:{lease}", "origin", f"HEAD:{ref}"], self.path)


class HostCheckout:
    """The base checkout `fr isolation …` runs against, on the harness host."""

    def __init__(self, primary: Path) -> None:
        self.primary = primary

    def fr(self, args: Sequence[str], *, terminal: bool = False) -> tuple[int, str]:
        from fr.triage.gitseam import run_this_fr

        return run_this_fr(list(args), self.primary, terminal=terminal)

    def fetch(self, ref: str) -> None:
        from fr.triage.gitseam import GitError, git

        try:
            git(["fetch", "--quiet", "origin", "--end-of-options", ref], self.primary)
        except GitError as exc:  # a deleted branch: the PR head may still be here
            typer.echo(f"fr ops gate: warning: {exc}", err=True)

    def changed_paths(self, base: str, head: str, paths: Sequence[str]) -> list[str]:
        from fr.triage.gitseam import git

        out = git(["diff", "--name-only", "--end-of-options", base, head, "--", *paths],
                  self.primary)  # fmt: skip
        return [line for line in out.splitlines() if line]

    def origin_head(self) -> str | None:
        from fr.triage.gitseam import GitError, git

        try:
            out = git(["symbolic-ref", "--short", "refs/remotes/origin/HEAD"], self.primary)
        except GitError:
            return None
        name = out.strip()
        return name.removeprefix("origin/") or None

    def workspace(self, branch: str) -> OpsWorkspace | None:
        from fr.isolation.types import load_state

        state = load_state(self.primary, branch)
        if state is None or not Path(state.worktree).is_dir():
            return None
        return OpsWorkspace(Path(state.worktree))


def _profile(root: Path, named: str | None) -> str:
    from fr.ops.profile import ops_profiles

    names = ops_profiles(root)
    if named is not None:
        if named not in names:
            _refuse(
                f"{named!r} is not a profile declared `ops: true` ({', '.join(names) or 'none'})"
            )
        return named
    if not names:
        _refuse(
            "no profile here is declared `ops: true`: scaffold one with "
            "`fr init scaffold --ops`, then re-run"
        )
    if len(names) > 1:
        _refuse(f"several ops profiles ({', '.join(names)}): pass --profile <name>")
    return names[0]


def gate(
    run: Annotated[
        str, typer.Option("--run", help="The delivered run whose DevOps stage this is.")
    ],
    yes: Annotated[bool, typer.Option("--yes", help="Act; without it, preview.")] = False,
    profile: Annotated[
        str | None, typer.Option("--profile", help="The ops profile (default: the only one).")
    ] = None,
    method: Annotated[
        str | None,
        typer.Option("--method", help="Merge method (default: the repo's): merge|squash|rebase."),
    ] = None,
) -> None:
    """The DevOps stage: pre-merge ops, the merge, post-merge ops, the devops Test Plan
    steps, the gate pass, the tester hand-off and the archive, in 8 recorded stages.

    Runs on the harness host at a terminal; previews without --yes. The merge asks its
    own confirmation even with --yes. A rerun resumes at the first unrecorded stage."""
    from fr.commands.gate_cmd import RunLookupError, find_run, resolve_target
    from fr.git import repo_root as git_repo_root
    from fr.ops import gate as engine
    from fr.run.closeout import primary_checkout

    if not _interactive():
        _refuse(
            "the DevOps stage runs only at a terminal (no terminal on stdin and stdout, or "
            "CI is set); nothing done"
        )
    try:
        root = git_repo_root(Path.cwd())
    except Exception:  # noqa: BLE001 — any git failure means "not in a repo"
        _refuse("not inside a git repository")
    try:
        state = find_run(root, run)
    except RunLookupError as exc:
        _refuse(f"{exc}; run it from a checkout that holds the run")
    emitted = {k: v for r in state.steps.values() for k, v in (r.emitted or {}).items()}
    pr = engine.pr_number(emitted.get("pr"))
    if pr is None:
        _refuse(f"run {run} recorded no PR: deliver it first")
    plan_rel = emitted.get("plan")
    if not plan_rel:
        _refuse(f"run {run} recorded no plan")
    repo, host = resolve_target(None, None, root)
    target = engine.GateTarget(
        run=state,
        repo=repo,
        pr=pr,
        plan_rel=plan_rel,
        profile=_profile(root, profile),
        primary=primary_checkout(root),
        method=method,
    )
    g = engine.Gate(
        target,
        HostCheckout(target.primary),
        _forge(f"https://{host}/{repo}"),
        _prompt(),
        typer.echo,
        engine.HostGateState(engine.gate_state_path(target.primary, state.run)),
    )
    if not yes:
        for line in engine.preview(g):
            typer.echo(line)
        return
    result = engine.run(g)
    raise typer.Exit(code=result.code)
