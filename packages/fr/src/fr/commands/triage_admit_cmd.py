"""`fr triage admit <owner/repo#n> [--yes]` (spec 2026-11-22-triage-hardening R2, §B).

Admits an outside author's issue for batching: reads its title and body live from the
forge, adds the `ready-fr` label and posts one comment holding an admit marker over that
content (`fr.triage.admit`). Collect then admits the issue while the latest trusted marker's
digest equals the issue's current one; an edit after this voids it.

Without `--yes` it previews and writes nothing: the label, the comment, the title and body it
would pin (quoted as untrusted text, as a launch brief quotes them) and their digest. `--yes`
needs `--digest`, the digest the operator read in the preview; the issue is read again just
before the write, and a missing or different digest is a refusal that prints the current one
and writes nothing, so an edit between the operator's reading and the write is never pinned
(p1-sec-admit-toctou). Every forge write goes through the
`GhClient` adapter. It refuses a pull request, and it refuses, before any read, a forge
whose adapter cannot list issue comments (GitLab, Gitea): no collect there could read the
marker. The `triage` group stays read-only for the migration gate (`READ_ONLY_COMMANDS`):
like `batch dispatch`, `admit` writes the forge only.
"""

from __future__ import annotations

import re
from typing import NoReturn

import typer
from rich.markup import escape

from fr.commands.triage_cmd import console, err_console, triage_app
from fr.ghclient import GhClient, UnsupportedBatchOps
from fr.hostclient import client_for_url
from fr.labels import READY_FR
from fr.triage.admit import admit_marker, content_digest
from fr.triage.batch_dispatch import (
    UNTRUSTED_CLOSE,
    UNTRUSTED_OPEN,
    UNTRUSTED_RULE,
    quote_untrusted,
)
from fr.triage.collect import ClientForge, _login, read_config_lenient
from fr.triage.errors import TriageError
from fr.triage.model import TriageConfig, claim_trusted

_KEY_RE = re.compile(r"^(?P<repo>[\w.-]+/[\w.-]+)#(?P<number>[1-9]\d*)$")


def make_client(url: str) -> GhClient:
    """The forge adapter for the repo *url* names. Tests replace this."""
    return client_for_url(url)


def _fail(message: str) -> NoReturn:
    err_console.print(f"[red]error:[/red] {escape(message)}", soft_wrap=True)
    raise typer.Exit(2)


@triage_app.command("admit")
def admit_command(
    key: str = typer.Argument(..., help="The issue to admit, as owner/repo#n."),
    yes: bool = typer.Option(False, "--yes", help="Write the label and the comment."),
    digest_opt: str | None = typer.Option(
        None, "--digest", help="The digest the preview printed; --yes needs it."
    ),
) -> None:
    """Admit an outside author's issue for batching: label it ready-fr and pin its content.

    Exits 2 on a key it cannot read, a pull request, a forge that cannot list comments, or
    a --digest that is missing or no longer matches the issue.
    """
    match = _KEY_RE.match(key.strip())
    if match is None:
        _fail(f"{key!r} is not an issue key: give it as owner/repo#n")
    repo, number = match["repo"], int(match["number"])
    client = make_client(f"https://github.com/{repo}")
    if isinstance(client, UnsupportedBatchOps):  # glab/tea: no comment list, no marker read
        _fail(
            f"{repo}: this forge cannot list issue comments, so no collect could read an "
            "admit marker; fr triage admit works on GitHub only"
        )
    forge = ClientForge(client)
    try:
        raw = forge.view_issue(repo=repo, number=number)
        config, _ = read_config_lenient(forge, repo)
        viewer = forge.viewer_login() or None
    except TriageError as exc:
        _fail(f"{repo}#{number}: {exc}")
    if "/pull/" in str(raw.get("url") or ""):
        _fail(f"{key} is a pull request, not an issue: only an issue is admitted")
    author = _login(raw)
    if author and author.lower() in claim_trusted(config or TriageConfig(), viewer):
        console.print(
            f"{escape(key)} is already eligible: its author {escape(author)} is trusted; "
            "nothing written",
            soft_wrap=True,
        )
        return
    title, body = str(raw.get("title") or ""), str(raw.get("body") or "")
    digest = content_digest(title, body)
    comment = admit_marker(digest, key=key)
    if not yes:
        console.print(f"would add label {READY_FR.name} to {escape(key)}", soft_wrap=True)
        console.print("would post this comment:", soft_wrap=True)
        for line in comment.splitlines():
            console.print(f"  {line}", soft_wrap=True, markup=False)
        console.print("it pins this title and body:", soft_wrap=True)
        quoted = [
            UNTRUSTED_RULE,
            UNTRUSTED_OPEN,
            *quote_untrusted([title, "", body]),
            UNTRUSTED_CLOSE,
        ]
        for line in quoted:
            console.print(line, soft_wrap=True, markup=False, highlight=False)
        console.print(f"digest {digest}", soft_wrap=True, markup=False)
        console.print(
            f"read it, then re-run with --yes --digest {digest} to write them",
            soft_wrap=True,
            markup=False,
        )
        return
    if digest_opt is None:
        _fail(f"--yes needs --digest: the current digest of {key} is {digest}; preview it first")
    try:  # read again just before the write: an edit since the preview is never pinned
        live = forge.view_issue(repo=repo, number=number)
    except TriageError as exc:
        _fail(f"{repo}#{number}: {exc}")
    current = content_digest(str(live.get("title") or ""), str(live.get("body") or ""))
    if digest_opt != current:
        _fail(
            f"{key} does not match --digest {digest_opt}: its current digest is {current}; "
            "preview it again, read it, and re-run with that digest"
        )
    comment = admit_marker(current, key=key)
    try:
        client.ensure_labels(repo, [READY_FR])
        client.edit_issue_labels(repo, number, add=frozenset({READY_FR.name}), remove=frozenset())
        client.comment_issue(repo, number, comment)
    except Exception as exc:  # noqa: BLE001 — the adapter's own error, reported as a refusal
        _fail(f"{key}: admission not written: {exc}")
    console.print(
        f"admitted {escape(key)}: labelled {READY_FR.name}, admit marker {escape(current)} posted",
        soft_wrap=True,
    )
