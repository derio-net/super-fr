"""`fr gate` — the post-merge gate ledger's explicit route (spec 2026-10-14-exit-gates R14,
§D).

A post-merge gate (`tester`, `devops`) passes in one of two ways, and both do the same
thing: swap the PR's `gate:<g>` label for `gate:<g>-passed` and comment what passed it.
The driver does it when every row the gate gates reads `walked` on the default branch;
`fr gate pass` is the route for a gate with no row (a run-level `gate: devops`) or a
pass the operator records by hand. The merged PR's labels are the ledger, so a pass
needs no commit: this group touches no registered artifact and is in
`fr.artifacts.trigger.READ_ONLY_COMMANDS`. Dry-run without `--yes`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from fr.gates import GATES, POST_MERGE_GATES
from fr.ghclient import GhClient, UnsupportedForgeOperation
from fr.hostclient import FORGE_ERRORS, client_for, client_for_url
from fr.labels import gate_label
from fr.verification.labels import gate_pass_comment, pass_gate

gate_app = typer.Typer(
    help="Post-merge gates: record that a gate passed on its PR (the gate ledger).",
    no_args_is_help=True,
)

RELEASE_WORKFLOW = "release.yml"
_FORGE_FAILURES: tuple[type[Exception], ...] = (*FORGE_ERRORS, UnsupportedForgeOperation)


def client_for_repo(repo: str, root: Path | None = None) -> GhClient:
    """The forge client for *repo*: the checkout's own (*root*, whose origin it is), else
    the one its github.com URL names. Tests replace this factory."""
    return client_for(root) if root is not None else client_for_url(f"https://github.com/{repo}")


def _refuse(message: str) -> None:
    typer.echo(f"fr gate pass: {message}", err=True)
    raise typer.Exit(code=2)


def release_command(repo: str) -> str:
    """The dispatch that cuts the final once the last gate passed (R20)."""
    return f"gh workflow run {RELEASE_WORKFLOW} --repo {repo}"


@gate_app.command("pass")
def pass_command(
    pr: Annotated[int, typer.Option("--pr", help="The PR whose gate passed.")],
    gate: Annotated[str, typer.Option("--gate", help="The post-merge gate: tester | devops.")],
    notes: Annotated[str, typer.Option("--notes", help="What passed it (the PR comment).")],
    repo: Annotated[
        str | None,
        typer.Option("--repo", help="OWNER/REPO; default: this checkout's origin."),
    ] = None,
    yes: Annotated[bool, typer.Option("--yes", help="Write to the forge.")] = False,
) -> None:
    """Swap PR <n>'s gate:<g> for gate:<g>-passed and comment why (R14)."""
    if gate not in GATES:
        _refuse(f"unknown gate {gate!r}: one of {', '.join(sorted(GATES))}")
    if gate not in POST_MERGE_GATES:
        _refuse(
            f"{gate!r} is not a post-merge gate: only {', '.join(sorted(POST_MERGE_GATES))} "
            "hold a merge, so only they pass"
        )
    root: Path | None = None
    if repo is None:
        from fr import _hosts

        root = Path.cwd()
        repo = _hosts.origin_slug(root)
        if repo is None:
            _refuse("no `origin` remote here to name the repo: pass --repo OWNER/REPO")
    assert repo is not None
    held, passed = gate_label(gate).name, gate_label(gate, passed=True).name
    try:
        client = client_for_repo(repo, root) if root is not None else client_for_repo(repo)
        labels = {str(n) for n in client.pr_view(repo, pr).get("labels") or []}
    except _FORGE_FAILURES as exc:
        _refuse(f"cannot read PR #{pr} of {repo}: {exc}")
        return
    if held not in labels:
        have = ", ".join(sorted(n for n in labels if n.startswith("gate:"))) or "no gate label"
        _refuse(f"PR #{pr} of {repo} does not carry {held} ({have}): nothing to pass")
    typer.echo(f"PR #{pr} ({repo}): {held} -> {passed}")
    typer.echo(f"comment: {gate_pass_comment(gate, notes)}")
    if not yes:
        typer.echo(f"release: once this is the last pass, cut the final: {release_command(repo)}")
        typer.echo("nothing done; re-run with --yes to act")
        return
    try:
        pass_gate(client, repo, pr, gate, why=notes)
    except _FORGE_FAILURES as exc:
        typer.echo(f"fr gate pass: the forge refused: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"passed: PR #{pr} now carries {passed}")
    typer.echo(f"release: once this is the last pass, cut the final: {release_command(repo)}")
