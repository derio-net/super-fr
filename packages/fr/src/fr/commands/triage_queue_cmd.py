"""`fr triage queue add|remove --pr N` (spec 2026-11-24-wave-queue-gaps R11, §C).

An operator puts any open same-repo PR by an allowed author into the scope's wave merge
queue (`add`), or takes it out again (`remove`). Each verb appends one `queue_add` /
`queue_remove` event to the judgements' `queue_requests:`, naming the PR and the forge
login the command authenticates as, through the one judgements writer, and pushes the
scope's state ref at once. `add --preapproved` asks the driver to approve the PR itself
at each green head (R13); on a batch PR of the scope, which is already an entry, that
preapproval is all `add` records. Every refusal comes before any write, and a write the
state refuses (changed since read, or a refused push) leaves the file as it was and exits
2. The `triage` group stays read-only for the migration gate: its state is no artifact.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, NoReturn

import typer

from fr.commands.triage_cmd import (
    DirOpt,
    OrgOpt,
    RepoOpt,
    WorkspaceOpt,
    _load_state,
    _scope,
    console,
    fail,
    push_now,
    triage_app,
)
from fr.ghclient import GhClient, UnsupportedForgeOperation
from fr.hostclient import FORGE_ERRORS, client_for_url
from fr.triage.batch import (
    allowed_authors,
    batch_pr,
    batch_repo,
    distrust,
    save_queue_requests,
)
from fr.triage.errors import TriageError
from fr.triage.model import (
    Facts,
    Judgements,
    PullRequest,
    QueueAddEvent,
    QueueRemoveEvent,
    Scope,
)
from fr.triage.operator_entries import reserved_entry
from fr.triage.queue_requests import added
from fr.triage.scope_config import scope_id

queue_app = typer.Typer(
    name="queue",
    help="Put a PR in the wave merge queue, or take it out (operator entries).",
    no_args_is_help=True,
)
triage_app.add_typer(queue_app)

PrOpt = Annotated[
    str,
    typer.Option(
        "--pr", help="The PR: N in a one-repo scope, else OWNER/REPO#N.", show_default=False
    ),
]
AGAIN = "; nothing changed, run the command again"


def make_client(url: str) -> GhClient:
    """The forge adapter for the repo *url* names. Tests replace this."""
    return client_for_url(url)


def _target(pr: str, facts: Facts) -> tuple[str, int]:
    """The repo and number *pr* names: `N` in a one-repo scope, `OWNER/REPO#N` in any."""
    repo, _, number = pr.rpartition("#")
    if not repo:
        if len(facts.repos) != 1:
            fail(f"--pr {pr}: this scope holds {len(facts.repos)} repos; give OWNER/REPO#N")
        repo = facts.repos[0]
    if repo not in facts.repos:
        fail(f"--pr {pr}: {repo} is not a repo of this scope ({', '.join(facts.repos)})")
    if not number.isdigit() or int(number) < 1:
        fail(f"--pr {pr}: not a PR number")
    return repo, int(number)


def _unsupported(repo: str, exc: UnsupportedForgeOperation) -> NoReturn:
    """l-errors-r6: a glab or tea repo has no wave merge queue (the queue is held there)."""
    fail(f"the merge queue needs a GitHub repo ({repo} is {exc.backend}); nothing written")


def _client(facts: Facts, repo: str) -> GhClient:
    host = next((i.url.split("/")[2] for i in facts.issues if i.repo == repo), "github.com")
    return make_client(f"https://{host}/{repo}")


def _batch_of(repo: str, number: int, facts: Facts, judgements: Judgements) -> str | None:
    """The id of the scope's batch whose PR *number* is, or None."""
    for batch in judgements.batches:
        if batch_repo(batch, facts) == repo and (p := batch_pr(batch, facts)) is not None:
            if p.number == number:
                return batch.id
    return None


def _known_pr(repo: str, number: int, facts: Facts) -> PullRequest | None:
    """PR *number* of *repo* as collect read it, from the pool `batch_pr` reads: the PRs
    linked to an issue (a Closes line files a batch PR under its members), the unlinked
    open PRs and the head-branch lookups (gh#1741). A record whose author and origin were
    read wins over one where they were not."""
    pool = [p for issue in facts.issues for p in issue.prs]
    pool += [*facts.prs, *facts.batch_prs]
    found = [p for p in pool if p.repo == repo and p.number == number]
    read = [p for p in found if p.author is not None and p.cross_repo is not None]
    return next(iter(read or found), None)


def _refuse(repo: str, number: int, why: str) -> NoReturn:
    fail(f"{repo}#{number}: {why}; nothing written")


def _write(
    target: Path, judgements: Judgements, event: QueueAddEvent | QueueRemoveEvent, scope: Scope
) -> None:
    """Append *event* through the one writer and push the state ref now. A refusal of either
    restores the file byte for byte and exits 2 (R11)."""
    path = target / "judgements.yaml"
    before = path.read_bytes()
    read = list(judgements.queue_requests)
    try:
        save_queue_requests(path, [*read, event], read=read)
    except TriageError as exc:
        fail(f"{exc}{AGAIN}")
    try:
        push_now(scope, target)
    except TriageError as exc:
        path.write_bytes(before)
        fail(f"the state ref refused the write: {exc}{AGAIN}")


def _now(judgements: Judgements) -> datetime:
    """Now, or the last request's time if the clock is behind it (the time-order rule)."""
    now = datetime.now(UTC)
    last = judgements.queue_requests[-1].at if judgements.queue_requests else now
    return max(now, last)


@queue_app.command("add")
def queue_add_command(
    pr: PrOpt,
    preapproved: Annotated[
        bool,
        typer.Option(
            "--preapproved",
            help="Let the driver add approved-fr itself at each green, conflict-free head "
            "while the PR stays added (R13).",
        ),
    ] = False,
    repo: RepoOpt = None,
    org: OrgOpt = None,
    dir_override: DirOpt = None,
    workspace: WorkspaceOpt = None,
) -> None:
    """Put an open PR of this repo into the wave merge queue as an operator entry (R11).

    It lands like any entry once `approved-fr` is valid on its head and its own checks are
    green, and the open wave waits for it. A batch PR is already an entry: only
    --preapproved is recorded for it."""
    scope = _scope(repo, org)
    target, facts, judgements = _load_state(scope, dir_override, workspace)
    owner_repo, number = _target(pr, facts)
    client = _client(facts, owner_repo)
    try:
        view = client.pr_view(owner_repo, number)
        default = client.repo_default_branch(owner_repo)
        login = client.viewer_login()
    except FORGE_ERRORS as exc:
        fail(f"{owner_repo}#{number}: a forge read failed: {exc}; nothing written")
    except UnsupportedForgeOperation as exc:
        _unsupported(owner_repo, exc)
    if view.get("state") != "OPEN":
        _refuse(owner_repo, number, f"the PR is not open ({view.get('state')})")
    if (base := str(view.get("base_ref") or "")) != default:
        _refuse(owner_repo, number, f"its base {base!r} is not the default branch {default!r}")
    batch = _batch_of(owner_repo, number, facts, judgements)
    known = _known_pr(owner_repo, number, facts)
    # A batch's PR was trusted by `batch_pr` itself; any other PR on the same read (gh#1741).
    if batch is None and (
        why := distrust(
            known.author if known else None,
            known.cross_repo if known else None,
            allowed_authors(owner_repo, facts),
        )
    ):
        _refuse(owner_repo, number, why)
    sid = scope_id(scope)
    if number in added(judgements.queue_requests, owner_repo, sid):
        _refuse(owner_repo, number, "already added (`fr triage queue remove` takes it out)")
    head_ref = str(view.get("head_ref") or (known.head_ref if known else ""))
    if (kind := reserved_entry(owner_repo, number, head_ref, judgements)) is not None:
        _refuse(owner_repo, number, f"it is fr's own {kind} entry")
    if batch is not None and not preapproved:
        _refuse(owner_repo, number, f"it is batch {batch}'s PR, already an entry; add "
                "--preapproved to let the driver approve it")  # fmt: skip
    event = QueueAddEvent(kind="queue_add", at=_now(judgements), repo=owner_repo, scope=sid,
                          pr=number, by=login, preapproved=preapproved)  # fmt: skip
    _write(target, judgements, event, scope)
    what = f"batch {batch}'s PR preapproved" if batch else "added to the merge queue"
    console.print(
        f"added {owner_repo}#{number} as {login}: {what}"
        + (" (preapproved)" if preapproved and not batch else ""),
        markup=False,
    )
    if preapproved and login.lower() not in allowed_authors(owner_repo, facts):
        console.print(
            f"warning: {login} is not an allowed author of {owner_repo}, so the driver will "
            "not approve it",
            markup=False,
        )


@queue_app.command("remove")
def queue_remove_command(
    pr: PrOpt,
    repo: RepoOpt = None,
    org: OrgOpt = None,
    dir_override: DirOpt = None,
    workspace: WorkspaceOpt = None,
) -> None:
    """Take a PR `queue add` put in out again (R11): the driver ejects it from a combination
    with reason `operator`, and a batch PR's preapproval ends."""
    scope = _scope(repo, org)
    target, facts, judgements = _load_state(scope, dir_override, workspace)
    owner_repo, number = _target(pr, facts)
    sid = scope_id(scope)
    if number not in added(judgements.queue_requests, owner_repo, sid):
        _refuse(owner_repo, number, "not added (`fr triage queue add` puts it in)")
    try:
        login = _client(facts, owner_repo).viewer_login()
    except FORGE_ERRORS as exc:
        fail(f"{owner_repo}#{number}: a forge read failed: {exc}; nothing written")
    except UnsupportedForgeOperation as exc:
        _unsupported(owner_repo, exc)
    event = QueueRemoveEvent(kind="queue_remove", at=_now(judgements), repo=owner_repo,
                             scope=sid, pr=number, by=login)  # fmt: skip
    _write(target, judgements, event, scope)
    batch = _batch_of(owner_repo, number, facts, judgements)
    what = f"batch {batch}'s preapproval withdrawn" if batch else "out of the merge queue"
    console.print(f"removed {owner_repo}#{number} as {login}: {what}", markup=False)
