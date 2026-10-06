"""`fr verification ...` CLI — resolve + validate verification strategies
(spec 2026-10-06-verification-strategies §A, R2).

`list` shows every strategy that resolves and where it came from. `check
[<name> | --all]` refuses a malformed manifest — whether a parse-time
`StrategyError` (unknown key, bad `when`/`driver`, unknown placeholder) or a
semantic `check_strategy` finding — through one report. Like `fr workflow
check --all`, `--all` FAILS when there is nothing to validate: a broken
installation is not a clean bill of health.

The group is deliberately NOT in `fr.artifacts.trigger.READ_ONLY_COMMANDS`: a
later subcommand (`walk`) reads the matrix with the live parser and must not
run over a stale one, and the gate exempts top-level names only.

Exit codes: 0 clean, 2 any failure or a usage error (a git that cannot answer
included — refused, never a traceback).
"""

from __future__ import annotations

import os
from pathlib import Path

import typer
from rich.console import Console

from fr.commands.common import resolve_repo_root
from fr.verification.check import check_strategy
from fr.verification.model import StrategyError
from fr.verification.resolve import (
    REPO_VERIFICATIONS_REL,
    list_strategies,
    resolve_strategy,
    shipped_verification_dirs,
)

console = Console(highlight=False)
err_console = Console(stderr=True, highlight=False)

verification_app = typer.Typer(
    help="Verification strategies: resolve (repo > shipped) and validate.",
    no_args_is_help=True,
)


def _check_one(name: str, repo_root: Path) -> list[str]:
    try:
        manifest = resolve_strategy(name, repo_root)
    except StrategyError as e:
        return [str(e)]
    return check_strategy(manifest)


@verification_app.command("list")
def list_cmd() -> None:
    """Every strategy that resolves, and where it came from."""
    for name, source in list_strategies(resolve_repo_root()):
        console.print(f"{name}  {source}")


@verification_app.command("check")
def check_cmd(
    name: str | None = typer.Argument(None, help="Strategy name (resolved repo > shipped)."),
    all_: bool = typer.Option(False, "--all", help="Validate every discoverable strategy."),
) -> None:
    """Validate one strategy by name, or every discoverable one with --all."""
    repo_root = resolve_repo_root()

    if all_:
        names = [n for n, _ in list_strategies(repo_root)]
        if not names:
            err_console.print("[red]no verification strategies found — nothing to validate.[/red]")
            err_console.print("Searched:")
            for d in [repo_root / REPO_VERIFICATIONS_REL, *shipped_verification_dirs()]:
                err_console.print(f"  {d}", soft_wrap=True)
            raise typer.Exit(2)
    elif name:
        names = [name]
    else:
        err_console.print("provide a strategy name or --all.")
        raise typer.Exit(2)

    had_errors = False
    for strategy in names:
        errors = _check_one(strategy, repo_root)
        if errors:
            had_errors = True
            for err in errors:
                err_console.print(f"[red]{strategy}:[/red] {err}", soft_wrap=True)
        else:
            console.print(f"{strategy}: ok")

    if had_errors:
        raise typer.Exit(2)


@verification_app.command("walk")
def walk_cmd(
    run: str = typer.Option(..., "--run", help="The run whose spec's rows are walked."),
    model: str = typer.Option(
        ..., "--model", help="The model driving this walk (fr cannot detect one)."
    ),
    harness: str | None = typer.Option(None, "--harness", help="Override the detected harness."),
    strategy: str | None = typer.Option(
        None, "--strategy", help="The pre-merge strategy to walk (default: the run's)."
    ),
    client: Path | None = typer.Option(
        None, "--client", help="Run the scenarios with this client repo as their cwd."
    ),
    row: list[str] = typer.Option([], "--row", help="Walk only this row (repeatable)."),
) -> None:
    """Install the candidate into a throwaway prefix, smoke it, run each row's
    scenario, and write the log `deliver` verifies (spec §C)."""
    from fr.acceptance.model import AcceptanceError
    from fr.git import GitUnavailableError
    from fr.harness import HarnessError
    from fr.harness.detect import detect_harness
    from fr.requirements import load_spec_matrix
    from fr.run.code_tree import code_tree, dirty_code_paths
    from fr.run.model import RunStateError, load_run_state
    from fr.verification.rows import run_verification
    from fr.verification.spec_section import SectionError
    from fr.verification.walk import WalkError, plan_rows, run_walk

    repo_root = resolve_repo_root()

    def refuse(message: str) -> typer.Exit:
        err_console.print(f"[red]refused:[/red] {message}", soft_wrap=True)
        return typer.Exit(2)

    try:
        state = load_run_state(repo_root, run)
        spec_rel, verification = run_verification(repo_root, state)
        if spec_rel is None:
            raise refuse(f"run {run!r} has not emitted a spec yet")
        matrix, spec_ref = load_spec_matrix(repo_root, spec_rel)
        name = (
            strategy
            or (verification.section.strategy if verification.section is not None else None)
            or verification.shape_default
        )
        if name is None:
            raise refuse(
                f"run {run!r} names no strategy — give --strategy or add a "
                "`strategy:` line to the spec's `## Verification`"
            )
        manifest = resolve_strategy(name, repo_root)
        if manifest.when != "pre-merge":
            raise refuse(f"strategy {name!r} is {manifest.when}: there is nothing to walk")
        rows = plan_rows(matrix, spec_ref, verification, name, row)
        if not model.strip():
            raise refuse("--model is required (fr cannot detect a model)")
        dirty = dirty_code_paths(repo_root)
        if dirty:
            raise refuse(
                f"{len(dirty)} uncommitted code path(s), e.g. {dirty[0]} — the log records "
                "HEAD's code tree, so commit before walking"
            )
        detected = harness or detect_harness(os.environ) or "unknown"
        path, log = run_walk(
            repo_root=repo_root,
            run=run,
            manifest=manifest,
            rows=rows,
            model=model,
            harness=detected,
            code_tree=code_tree(repo_root),
            client=client.resolve() if client is not None else None,
        )
    except (
        RunStateError,
        AcceptanceError,
        SectionError,
        StrategyError,
        WalkError,
        HarnessError,
        GitUnavailableError,
    ) as e:
        raise refuse(str(e)) from e

    for step in log.steps:
        mark = "ok" if step.exit == 0 else f"FAILED (exit {step.exit})"
        console.print(f"{step.name}: {mark}")
    console.print(f"walk log: {path}", soft_wrap=True)
    if not log.passed:
        raise typer.Exit(1)


PRERELEASE_WORKFLOW = "prerelease.yml"


def rc_tag(branch: str, sha: str) -> str:
    """`rc/<branch-slug>/<sha12>` — the tag `prerelease.yml` cuts (slug: `/` -> `-`)."""
    return f"rc/{branch.replace('/', '-')}/{sha[:12]}"


@verification_app.command("prerelease")
def prerelease_cmd(
    branch: str = typer.Option(..., "--branch", help="The PR branch to cut a pre-release of."),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Print the dispatch and the rc tag; call nothing."
    ),
) -> None:
    """Cut an on-demand pre-release of BRANCH (spec §H, R24): dispatch the
    `prerelease.yml` workflow, then print the rc tag and the install source
    (`git+<remote>@<tag>`) the `prerelease` strategy installs from."""
    from fr import hostclient
    from fr._hosts import origin_slug
    from fr.ghclient import UnsupportedForgeOperation
    from fr.git import GitUnavailableError, git_answer, remote_name
    from fr.real_ghclient import workflow_run_args

    repo_root = resolve_repo_root()

    def refuse(message: str) -> typer.Exit:
        err_console.print(f"[red]refused:[/red] {message}", soft_wrap=True)
        return typer.Exit(2)

    try:
        remote = remote_name(repo_root)
        if remote is None or not isinstance(remote, str):
            raise refuse("no single git remote to cut a pre-release from")
        sha = ""
        for ref in (f"refs/remotes/{remote}/{branch}", f"refs/heads/{branch}"):
            found = git_answer(repo_root, "rev-parse", "--verify", "--quiet", ref)
            if found.returncode == 0 and found.stdout.strip():
                sha = found.stdout.strip()
                break
        if not sha:
            raise refuse(f"branch {branch!r} is not on {remote} or local — push it first")
        url = git_answer(repo_root, "remote", "get-url", remote).stdout.strip()
    except GitUnavailableError as e:
        raise refuse(str(e)) from e

    slug = origin_slug(repo_root)
    if slug is None:
        raise refuse("cannot read the origin repository slug")
    inputs = {"branch": branch}
    tag = rc_tag(branch, sha)
    if dry_run:
        console.print("dry run: would dispatch", soft_wrap=True)
        console.print("gh " + " ".join(workflow_run_args(slug, PRERELEASE_WORKFLOW, inputs)),
                      soft_wrap=True)  # fmt: skip
    else:
        try:
            hostclient.client_for(repo_root).dispatch_workflow(
                slug, PRERELEASE_WORKFLOW, inputs=inputs
            )
        except UnsupportedForgeOperation as e:
            raise refuse(str(e)) from e
        except hostclient.FORGE_ERRORS as e:
            raise refuse(f"the dispatch failed: {e}") from e
        console.print(f"dispatched {PRERELEASE_WORKFLOW} for {branch}", soft_wrap=True)
    console.print(f"rc tag (once the workflow has run): {tag}", soft_wrap=True)
    console.print("install source for `{source}`:", soft_wrap=True)
    console.print(f"git+{url}@{tag}", soft_wrap=True, markup=False)
