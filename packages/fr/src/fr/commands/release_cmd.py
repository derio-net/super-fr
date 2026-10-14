"""`fr release status` — what still waits on a post-merge gate (spec 2026-10-14-exit-gates
R21, §G).

Lists every PR merged since the last final tag (`vX.Y.Z`, read from this checkout's
tags) that a `gate:tester` or `gate:devops` label still holds, with its owed rows, read
through the forge adapter. `scripts/release.py` does its own forge read (it holds the
release token) and hands the facts to `--from-json FILE`, which never reaches a forge:
fr decides credential-free, through the same `release_status` the forge path calls. It
touches no registered artifact, so `release` is in
`fr.artifacts.trigger.READ_ONLY_COMMANDS`; a forge read that fails exits 1, never an
empty list, because "nothing waits" would cut a final.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any, NoReturn

import typer

from fr.commands.gate_cmd import resolve_target
from fr.ghclient import GhClient, UnsupportedForgeOperation
from fr.hostclient import FORGE_ERRORS, client_for_url
from fr.release_status import OwedRows, ReleaseStatus, last_final_tag, release_status

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


class FactsReleaseForge:
    """`fr.release_status.ReleaseForge` over the facts `release.py` read from the forge:
    its merged PRs, each with its labels (names, or `{name: ...}` records)."""

    def __init__(self, prs: list[dict[str, Any]]) -> None:
        self.prs = prs
        self._labels = {int(p["number"]): _label_names(p.get("labels")) for p in prs}

    def merged_prs(self) -> list[dict[str, Any]]:
        return self.prs

    def labels(self, number: int) -> list[str]:
        return self._labels.get(number, [])


def _label_names(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [str(x.get("name") if isinstance(x, dict) else x) for x in raw]


def owed_rows_reader(root: Path, ref: str | None = None) -> Callable[[str], OwedRows | None]:
    """The rows each gate of a run still owes, read at *ref* (default: the default
    branch's tip), as the triage driver reads the gate ledger
    (`fr.triage.ledger.gated_rows_at`); None when they cannot be read."""
    from fr.triage.errors import TriageError
    from fr.triage.gitseam import Checkout
    from fr.triage.ledger import gated_rows_at

    checkout = Checkout(root)
    if ref is None:
        try:
            ref = f"origin/{checkout.default_branch()}"
            checkout.rev_parse(ref)
        except TriageError:
            ref = "HEAD"

    def read(branch: str) -> OwedRows | None:
        if not branch:
            return None
        assert ref is not None
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


def _fail(message: str, code: int) -> NoReturn:
    typer.echo(f"fr release status: {message}", err=True)
    raise typer.Exit(code=code)


def _from_facts(root: Path, path: Path) -> ReleaseStatus:
    """The decision over *path*'s facts: no forge, no credential (exit-gates R21)."""
    try:
        facts = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        _fail(f"cannot read the facts in {path}: {exc}", 2)
    prs = facts.get("prs") if isinstance(facts, dict) else None
    if not isinstance(prs, list) or not all(isinstance(p, dict) for p in prs):
        _fail(f"{path} has no `prs` list of PR records", 2)
    try:
        return release_status(
            repo=str(facts.get("repo") or ""),
            last_final=facts.get("last_final") or None,
            since=facts.get("since") or None,
            forge=FactsReleaseForge(prs),
            owed_rows=owed_rows_reader(root, "HEAD"),
        )
    except (KeyError, TypeError, ValueError) as exc:
        _fail(f"{path} holds a malformed PR record: {exc}", 2)


def _from_forge(root: Path, repo: str | None, host: str | None, limit: int) -> ReleaseStatus:
    from fr.triage.errors import TriageError

    try:
        tag, since = _last_final(root)
    except TriageError as exc:
        _fail(str(exc), 2)
    slug, forge_host = resolve_target(repo, host, root)
    try:
        client = client_for_url(f"https://{forge_host}/{slug}")
        return release_status(
            repo=slug,
            last_final=tag,
            since=since,
            forge=ClientReleaseForge(client, slug, limit),
            owed_rows=owed_rows_reader(root),
        )
    except _FORGE_FAILURES as exc:
        _fail(f"cannot read {slug}'s merged PRs on {forge_host}: {exc}", 1)


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
    from_json: Annotated[
        Path | None,
        typer.Option(
            "--from-json",
            help="Decide from these facts (repo, last_final, since, prs with labels), "
            "read by release.py; never reaches a forge.",
        ),
    ] = None,
) -> None:
    """List every PR merged since the last final tag that still waits on a post-merge gate."""
    from fr.triage.errors import TriageError
    from fr.triage.gitseam import Checkout

    try:
        root = Checkout.at(None).path
    except TriageError as exc:
        _fail(str(exc), 2)
    if from_json is not None:
        status = _from_facts(root, from_json)
    else:
        status = _from_forge(root, repo, host, limit)
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
