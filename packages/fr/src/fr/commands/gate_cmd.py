"""`fr gate` — the post-merge gate ledger's explicit route (spec 2026-10-14-exit-gates R14,
§D).

A post-merge gate (`tester`, `devops`) passes in one of two ways, and both do the same
thing: comment what passed it on the PR, then swap its `gate:<g>` label for
`gate:<g>-passed`. The driver does it when every row the gate gates reads `walked` on
the default branch; `fr gate pass` is the route for a gate with no row (a run-level
`gate: devops`) or a pass the operator records by hand. The merged PR's labels are the
ledger, so a pass needs no commit: this group touches no registered artifact and is in
`fr.artifacts.trigger.READ_ONLY_COMMANDS`. Dry-run without `--yes`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from fr.gates import GATES, POST_MERGE_GATES
from fr.ghclient import UnsupportedForgeOperation
from fr.hostclient import FORGE_ERRORS, client_for_url
from fr.labels import gate_label, held_gates
from fr.verification.labels import gate_pass_comment, pass_gate

gate_app = typer.Typer(
    help="Post-merge gates: record that a gate passed on its PR (the gate ledger).",
    no_args_is_help=True,
)

RELEASE_WORKFLOW = "release.yml"
DEFAULT_HOST = "github.com"
_FORGE_FAILURES: tuple[type[Exception], ...] = (*FORGE_ERRORS, UnsupportedForgeOperation)


def _refuse(message: str) -> None:
    typer.echo(f"fr gate pass: {message}", err=True)
    raise typer.Exit(code=2)


def release_command(repo: str) -> str:
    """The dispatch that cuts the final once the last gate passed (R20)."""
    return f"gh workflow run {RELEASE_WORKFLOW} --repo {repo}"


def resolve_target(repo: str | None, host: str | None, root: Path) -> tuple[str, str]:
    """`(OWNER/REPO, host)` of the PR (p4-r6), read from evidence before falling back to
    github.com, as the triage driver's `_host_of` does: *host* when named; else the
    checkout's origin host when its origin is *repo* (or *repo* is not named); else
    `github.com`. A repo that cannot be named at all is refused."""
    from fr import _hosts

    origin = _hosts.origin_slug(root)
    repo = repo or origin
    if repo is None:
        _refuse("no `origin` remote here to name the repo: pass --repo OWNER/REPO")
    assert repo is not None
    if host:
        return repo, host
    if origin is not None and origin.lower() == repo.lower():
        return repo, _hosts.origin_hostname(root) or DEFAULT_HOST
    return repo, DEFAULT_HOST


@gate_app.command("pass")
def pass_command(
    pr: Annotated[int, typer.Option("--pr", help="The merged PR whose gate passed.")],
    gate: Annotated[str, typer.Option("--gate", help="The post-merge gate: tester | devops.")],
    notes: Annotated[str, typer.Option("--notes", help="What passed it (the PR comment).")],
    repo: Annotated[
        str | None,
        typer.Option("--repo", help="OWNER/REPO; default: this checkout's origin."),
    ] = None,
    host: Annotated[
        str | None,
        typer.Option("--host", help="The forge host; default: the origin's, else github.com."),
    ] = None,
    yes: Annotated[bool, typer.Option("--yes", help="Write to the forge.")] = False,
) -> None:
    """Comment why PR <n>'s gate <g> passed, then swap gate:<g> for gate:<g>-passed (R14)."""
    if gate not in GATES:
        _refuse(f"unknown gate {gate!r}: one of {', '.join(sorted(GATES))}")
    if gate not in POST_MERGE_GATES:
        _refuse(
            f"{gate!r} is not a post-merge gate: only {', '.join(sorted(POST_MERGE_GATES))} "
            "hold a merge, so only they pass"
        )
    repo, forge_host = resolve_target(repo, host, Path.cwd())
    held, passed = gate_label(gate).name, gate_label(gate, passed=True).name
    try:
        client = client_for_url(f"https://{forge_host}/{repo}")
        view = client.pr_view(repo, pr)
    except _FORGE_FAILURES as exc:
        _refuse(f"cannot read PR #{pr} of {repo} on {forge_host}: {exc}")
        return
    state = str(view.get("state") or "UNKNOWN")
    if state != "MERGED":
        _refuse(f"PR #{pr} of {repo} is {state}, not merged: a post-merge gate passes on a merge")
    labels = {str(n) for n in view.get("labels") or []}
    if held not in labels:
        have = ", ".join(sorted(n for n in labels if n.startswith("gate:"))) or "no gate label"
        _refuse(f"PR #{pr} of {repo} does not carry {held} ({have}): nothing to pass")
    left = sorted(held_gates((labels - {held}) | {passed}))
    typer.echo(f"PR #{pr} ({repo}): {held} -> {passed}")
    typer.echo(f"comment: {gate_pass_comment(gate, notes)}")
    if yes:
        try:
            pass_gate(client, repo, pr, gate, why=notes)
        except _FORGE_FAILURES as exc:
            typer.echo(f"fr gate pass: the forge refused: {exc}", err=True)
            raise typer.Exit(code=1) from exc
        typer.echo(f"passed: PR #{pr} now carries {passed}")
    if left:  # p4-r9: no final while a post-merge gate still holds this PR
        typer.echo(f"{', '.join(f'gate:{g}' for g in left)} still holds PR #{pr}: no release yet")
    else:
        typer.echo(f"release: this was the PR's last gate; cut the final: {release_command(repo)}")
    if not yes:
        typer.echo("nothing done; re-run with --yes to act")
