"""`fr release status` — what still waits on a post-merge gate (spec 2026-10-14-exit-gates
R21, §G).

Lists every PR merged since the last final tag (`vX.Y.Z`, read from this checkout's
tags) that a `gate:tester` or `gate:devops` label still holds, with its owed rows, read
through the forge adapter. `scripts/release.py` decides between an RC and the final
from `--json`. It touches no registered artifact, so `release` is in
`fr.artifacts.trigger.READ_ONLY_COMMANDS`; a forge read that fails exits 1, never an
empty list, because "nothing waits" would cut a final.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any

import typer

from fr.commands.gate_cmd import resolve_target
from fr.ghclient import GhClient, UnsupportedForgeOperation
from fr.hostclient import FORGE_ERRORS, client_for_url
from fr.release_status import OwedRows, last_final_tag, release_status

release_app = typer.Typer(
    help="Release gating: what still waits on a post-merge gate since the last final.",
    no_args_is_help=True,
)

_FORGE_FAILURES: tuple[type[Exception], ...] = (*FORGE_ERRORS, UnsupportedForgeOperation)


class ClientReleaseForge:
    """`fr.release_status.ReleaseForge` over a `GhClient`: one bulk merged-PR list, then
    one PR view per PR merged since the tag (no list read carries a merged PR's labels)."""

    def __init__(self, client: GhClient, repo: str, limit: int) -> None:
        self.client, self.repo, self.limit = client, repo, limit

    def merged_prs(self) -> list[dict[str, Any]]:
        return self.client.list_prs(self.repo, "merged", self.limit)

    def labels(self, number: int) -> list[str]:
        return [str(n) for n in self.client.pr_view(self.repo, number).get("labels") or []]


def owed_rows_reader(root: Path) -> Callable[[str], OwedRows | None]:
    """The rows each gate of a run still owes, read on the default branch's tip (as the
    triage driver reads the gate ledger, `fr.triage.ledger.gated_rows_at`); None when
    they cannot be read."""
    from fr.triage.errors import TriageError
    from fr.triage.gitseam import Checkout
    from fr.triage.ledger import gated_rows_at

    checkout = Checkout(root)
    try:
        ref = f"origin/{checkout.default_branch()}"
        checkout.rev_parse(ref)
    except TriageError:
        ref = "HEAD"

    def read(branch: str) -> OwedRows | None:
        if not branch:
            return None
        try:
            ledger = gated_rows_at(checkout, ref, branch)
        except TriageError:
            return None
        owed: dict[str, list[str]] = {}
        for row in ledger.rows:
            if not row.walked:
                owed.setdefault(row.gate, []).append(row.id)
        return {g: tuple(ids) for g, ids in owed.items()}

    return read


def _fail(message: str, code: int) -> None:
    typer.echo(f"fr release status: {message}", err=True)
    raise typer.Exit(code=code)


def _last_final(root: Path) -> tuple[str | None, str | None]:
    """(the last final tag, its commit's ISO time) in the checkout at *root*."""
    from fr.triage.gitseam import git

    tag = last_final_tag(git(["tag", "--list", "v*"], root).split())
    if tag is None:
        return None, None
    return tag, git(["log", "-1", "--format=%cI", f"refs/tags/{tag}"], root).strip()


@release_app.command("status")
def status_command(
    as_json: Annotated[bool, typer.Option("--json", help="Machine-readable output.")] = False,
    repo: Annotated[
        str | None,
        typer.Option("--repo", help="OWNER/REPO; default: this checkout's origin."),
    ] = None,
    host: Annotated[
        str | None,
        typer.Option("--host", help="The forge host; default: the origin's, else github.com."),
    ] = None,
    limit: Annotated[
        int, typer.Option("--limit", help="How many merged PRs to read, newest first.")
    ] = 200,
) -> None:
    """List every PR merged since the last final tag that still waits on a post-merge gate."""
    from fr.triage.errors import TriageError
    from fr.triage.gitseam import Checkout

    try:
        root = Checkout.at(None).path
        tag, since = _last_final(root)
    except TriageError as exc:
        _fail(str(exc), 2)
        return
    slug, forge_host = resolve_target(repo, host, root)
    try:
        client = client_for_url(f"https://{forge_host}/{slug}")
        status = release_status(
            repo=slug,
            last_final=tag,
            since=since,
            forge=ClientReleaseForge(client, slug, limit),
            owed_rows=owed_rows_reader(root),
        )
    except _FORGE_FAILURES as exc:
        _fail(f"cannot read {slug}'s merged PRs on {forge_host}: {exc}", 1)
        return
    if as_json:
        typer.echo(json.dumps(status.to_json(), indent=2))
        return
    typer.echo(f"last final: {status.last_final or '(none)'}")
    if not status.waiting:
        typer.echo("nothing waits on a post-merge gate: a final may be cut")
        return
    for w in status.waiting:
        typer.echo(f"#{w.number} {w.title} ({w.url})")
        for gate in w.gates:
            rows = None if w.owed_rows is None else w.owed_rows.get(gate, ())
            owed = "rows unreadable" if rows is None else (", ".join(rows) or "no row")
            typer.echo(f"  gate:{gate} owes: {owed}")
    typer.echo(f"{len(status.waiting)} PR(s) wait: a release now is an RC")
