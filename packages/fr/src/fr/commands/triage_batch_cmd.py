"""`fr triage batch` — groups of judged issues delivered as one run
(spec 2026-09-25-triage-batches §3.A, §3.B, §3.E).

- `list` prints the batches in `judgements.yaml`; it needs no facts.json.
- `create` / `edit` write only the `batches:` section, through the loader's
  own model (`fr.triage.batch.save_batches`), then hold the open-batch rule.
  They load facts.json too, because that rule needs derived stages.
- `cancel` removes `fr:in-progress`, posts a withdrawal marker comment on each
  member and appends a `cancel` event — only with `--yes` (decision d1);
  without it, it prints what it would do and writes nothing.
- `suggest` prints candidate groupings and writes nothing.

Every forge operation goes through the `GhClient` adapter (§3.J), built by
`make_client`; this module never runs `gh`/`glab`/`tea` and never touches
triage's `Forge`, which serves `collect` alone.

Exit codes: 0 success; 1 a forge write failed (the event is not appended, so a
re-run completes it); 2 a refusal (unknown or duplicate batch, a load or
open-batch rule, a stage that forbids the change, a forge operation the
backend declares unsupported).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, NoReturn
from urllib.parse import urlparse

import typer
from pydantic import ValidationError
from rich.markup import escape

from fr._hosts import backend_for_url
from fr.commands.triage_cmd import (
    DirOpt,
    OrgOpt,
    RepoOpt,
    _load_state,
    _scope,
    batch_app,
    console,
    err_console,
)
from fr.ghclient import GhClient, UnsupportedForgeOperation
from fr.hostclient import client_for_backend
from fr.labels import FR_IN_PROGRESS
from fr.triage.batch import (
    CLOSED_OUT,
    batch_item_id,
    batch_repo,
    check_open_membership,
    derive_batch_stage,
    save_batches,
    suggest,
    withdrawal_body,
    withdrawn_already,
)
from fr.triage.errors import TriageError
from fr.triage.model import Batch, CancelEvent, Facts, load_judgements, state_dir
from fr.triage.render import plural


def make_client(url: str) -> GhClient:
    """The forge adapter for the repo *url* lives on (§3.J). Tests replace this."""
    return client_for_backend(backend_for_url(url))


def _fail(message: str, code: int = 2) -> NoReturn:
    err_console.print(f"[red]error:[/red] {escape(message)}", soft_wrap=True)
    raise typer.Exit(code=code)


def _find(batches: list[Batch], batch_id: str) -> Batch:
    wanted = batch_id.lower()
    for b in batches:
        if b.id == wanted:
            return b
    _fail(f"no batch {batch_id!r} in judgements.yaml")


def _replace(batches: list[Batch], new: Batch) -> list[Batch]:
    return [new if b.id == new.id else b for b in batches]


IssueOpt = Annotated[
    list[str] | None, typer.Option("--issue", help="A member key, <repo-name>#<n>; repeat.")
]
TitleOpt = Annotated[str | None, typer.Option("--title", help="One-line batch title.")]
RationaleOpt = Annotated[str | None, typer.Option("--rationale", help="Why these belong together.")]
OrderOpt = Annotated[
    int | None, typer.Option("--order", help="Hard constraint on merge order (lower first).")
]
BumpOpt = Annotated[str | None, typer.Option("--bump", help="patch | minor | major.")]
RunnerOpt = Annotated[str | None, typer.Option("--runner", help="Runner to launch with.")]
HarnessOpt = Annotated[str | None, typer.Option("--harness", help="Harness to launch.")]
ModelOpt = Annotated[str | None, typer.Option("--model", help="Model for every tier.")]


def _launch(runner: str | None, harness: str | None, model: str | None) -> dict[str, str]:
    """Only the launch values given explicitly (§3.B): dispatch resolves the rest."""
    given = {"runner": runner, "harness": harness, "model": model}
    return {k: v for k, v in given.items() if v is not None}


def _write(target: Path, batches: list[Batch], facts: Facts) -> None:
    """Hold the open-batch rule, then write through the loader's model."""
    try:
        check_open_membership(batches, facts)
        save_batches(target / "judgements.yaml", batches)
    except TriageError as exc:
        _fail(str(exc))


@batch_app.command("list")
def batch_list_command(
    repo: RepoOpt = None,
    org: OrgOpt = None,
    dir_override: DirOpt = None,
) -> None:
    """Print one line per batch in judgements.yaml, or "no batches"."""
    path = state_dir(_scope(repo, org), dir_override) / "judgements.yaml"
    try:
        batches = load_judgements(path).batches if path.exists() else []
    except TriageError as exc:
        _fail(str(exc))
    if not batches:
        console.print("no batches")
        return
    for b in batches:
        console.print(
            f"{b.id}  {plural(len(b.ids), 'issue')}  {b.title}", markup=False, soft_wrap=True
        )


@batch_app.command("create")
def batch_create_command(
    batch_id: Annotated[str, typer.Argument(help="Batch id, a slug: [a-z][a-z0-9-]{0,39}.")],
    title: TitleOpt = None,
    issue: IssueOpt = None,
    rationale: RationaleOpt = None,
    order: OrderOpt = None,
    bump: BumpOpt = None,
    runner: RunnerOpt = None,
    harness: HarnessOpt = None,
    model: ModelOpt = None,
    repo: RepoOpt = None,
    org: OrgOpt = None,
    dir_override: DirOpt = None,
) -> None:
    """Add a proposed batch of judged issues."""
    target, facts, judgements = _load_state(_scope(repo, org), dir_override)
    if not title or not issue:
        _fail("create needs --title and at least one --issue")
    doc: dict[str, object] = {"id": batch_id, "title": title, "ids": list(issue)}
    doc |= {"rationale": rationale} if rationale is not None else {}
    doc |= {"order": order} if order is not None else {}
    doc |= {"bump": bump} if bump is not None else {}
    doc |= {"launch": _launch(runner, harness, model)}
    try:
        new = Batch.model_validate(doc)
    except ValidationError as exc:
        _fail(f"invalid batch: {exc}")
    if any(b.id == new.id for b in judgements.batches):
        _fail(f"batch {new.id!r} already exists; use `fr triage batch edit`")
    _write(target, [*judgements.batches, new], facts)
    console.print(f"created batch {new.id} ({plural(len(new.ids), 'issue')})", markup=False)


@batch_app.command("edit")
def batch_edit_command(
    batch_id: Annotated[str, typer.Argument(help="The batch to change.")],
    title: TitleOpt = None,
    add_issue: Annotated[
        list[str] | None, typer.Option("--add-issue", help="Add a member; repeat.")
    ] = None,
    remove_issue: Annotated[
        list[str] | None, typer.Option("--remove-issue", help="Remove a member; repeat.")
    ] = None,
    rationale: RationaleOpt = None,
    order: OrderOpt = None,
    bump: BumpOpt = None,
    runner: RunnerOpt = None,
    harness: HarnessOpt = None,
    model: ModelOpt = None,
    repo: RepoOpt = None,
    org: OrgOpt = None,
    dir_override: DirOpt = None,
) -> None:
    """Change a proposed batch; past `proposed`, only --order may change."""
    target, facts, judgements = _load_state(_scope(repo, org), dir_override)
    batch = _find(judgements.batches, batch_id)
    changes: dict[str, object] = {}
    for name, value in (("title", title), ("rationale", rationale), ("bump", bump)):
        if value is not None:
            changes[name] = value
    if launch := _launch(runner, harness, model):
        changes["launch"] = batch.launch.model_dump(exclude_defaults=True) | launch
    if add_issue or remove_issue:
        drop = {k.lower() for k in remove_issue or []}
        ids = [k for k in batch.ids if k not in drop]
        ids += [k for k in add_issue or [] if k.lower() not in ids]
        changes["ids"] = ids
    if not changes and order is None:
        _fail("nothing to change: give at least one option")
    stage = derive_batch_stage(batch, facts)
    if changes and stage != "proposed":
        _fail(f"batch {batch.id!r} is {stage}; past proposed only --order may change")
    if order is not None:
        changes["order"] = order
    try:
        doc = batch.model_dump(by_alias=True, exclude_defaults=True) | changes
        new = Batch.model_validate(doc)
    except ValidationError as exc:
        _fail(f"invalid batch: {exc}")
    _write(target, _replace(judgements.batches, new), facts)
    console.print(f"edited batch {new.id}", markup=False)


@batch_app.command("cancel")
def batch_cancel_command(
    batch_id: Annotated[str, typer.Argument(help="The batch to withdraw.")],
    reason: Annotated[str, typer.Option("--reason", help="Why; posted on each member.")] = "",
    yes: Annotated[bool, typer.Option("--yes", help="Act; without it, print the plan.")] = False,
    repo: RepoOpt = None,
    org: OrgOpt = None,
    dir_override: DirOpt = None,
) -> None:
    """Withdraw a batch: unlabel and comment on each member, append a cancel event."""
    target, facts, judgements = _load_state(_scope(repo, org), dir_override)
    batch = _find(judgements.batches, batch_id)
    stage = derive_batch_stage(batch, facts)
    if stage in CLOSED_OUT:
        _fail(f"batch {batch.id!r} is {stage}; there is nothing to cancel")
    owner_repo = batch_repo(batch, facts)
    if owner_repo is None:
        _fail(f"batch {batch.id!r}: its repo {batch.repo_name!r} is not in this scope's facts")
    item = batch_item_id(owner_repo, batch.id)
    touches_forge = stage != "proposed"  # a proposed batch never reached the forge
    console.print(f"cancel batch {batch.id} ({stage})", markup=False)
    if touches_forge:
        for key in batch.ids:
            console.print(
                f"  {key}: remove {FR_IN_PROGRESS.name}, post the withdrawal comment",
                markup=False,
            )
    console.print("  append a cancel event to judgements.yaml", markup=False)
    if not yes:
        console.print("nothing written; re-run with --yes to act", markup=False)
        return
    if touches_forge:
        client = make_client(f"https://{_host_of(facts, owner_repo)}/{owner_repo}")
        failed: list[str] = []
        for key in batch.ids:
            number = int(key.rpartition("#")[2])
            try:
                client.edit_issue_labels(
                    owner_repo, number, add=frozenset(), remove=frozenset({FR_IN_PROGRESS.name})
                )
                if not withdrawn_already(client.list_issue_comments(owner_repo, number), item):
                    client.comment_issue(owner_repo, number, withdrawal_body(batch, item, reason))
            except UnsupportedForgeOperation as exc:
                _fail(str(exc))
            except Exception as exc:  # any forge failure: report the issue, keep going
                failed.append(f"{key}: {exc}")
        if failed:
            _fail(
                "these members were not fully withdrawn, so no cancel event was written; "
                "re-run to complete: " + "; ".join(failed),
                code=1,
            )
    last = batch.events[-1].at if batch.events else None
    now = datetime.now(UTC)
    at = max(now, last) if last else now  # a skewed clock never breaks event order
    cancelled = batch.model_copy(
        update={"events": [*batch.events, CancelEvent(kind="cancel", at=at, reason=reason)]}
    )
    _write(target, _replace(judgements.batches, cancelled), facts)
    console.print(f"cancelled batch {batch.id}", markup=False)


def _host_of(facts: Facts, owner_repo: str) -> str:
    """The forge host of *owner_repo*, from any collected issue URL there."""
    for i in facts.issues:
        if i.repo == owner_repo and (host := urlparse(i.url).hostname):
            return host
    return "github.com"


@batch_app.command("suggest")
def batch_suggest_command(
    repo: RepoOpt = None,
    org: OrgOpt = None,
    dir_override: DirOpt = None,
) -> None:
    """Print candidate groupings (shared file, theme, pattern). Writes nothing."""
    _, facts, judgements = _load_state(_scope(repo, org), dir_override)
    found = suggest(judgements, facts)
    if not found:
        console.print("no suggestions")
        return
    for s in found:
        console.print(f"{s.signal} {s.label}: {', '.join(s.keys)}", markup=False, soft_wrap=True)
