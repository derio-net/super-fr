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
- `dispatch` hands a batch to a run-capable runner as one `unit="run"` item
  (§3.C), reserving its version (§3.D) and making it visible on the forge
  (§3.E); `--repair` redoes only the forge writes.

This module is `fr`'s second sanctioned soft point into `fr_dispatch`
(`tests/unit/test_import_direction.py` `_SOFT_POINTS`): every such import sits
inside a function, behind `importlib.util.find_spec("fr_dispatch")`, with the
same install message as `apply_cmd.py`.

Every forge operation goes through the `GhClient` adapter (§3.J), built by
`make_client`; this module never runs `gh`/`glab`/`tea` and never touches
triage's `Forge`, which serves `collect` alone.

Exit codes: 0 success; 1 a forge write failed (the event is not appended, so a
re-run completes it); 2 a refusal (unknown or duplicate batch, a load or
open-batch rule, a stage that forbids the change, a forge operation the
backend declares unsupported).
"""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, NoReturn
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
from fr.hostclient import FORGE_ERRORS, client_for_backend
from fr.labels import FR_IN_PROGRESS
from fr.triage.batch import (
    CLOSED_OUT,
    batch_branch,
    batch_item_id,
    batch_repo,
    check_open_membership,
    derive_batch_stage,
    last_dispatch,
    resolve_launch,
    save_batches,
    suggest,
    withdrawal_body,
    withdrawn_already,
)
from fr.triage.batch_dispatch import (
    DISPATCHABLE,
    TRIAGE_CONFIG_PATH,
    check_config_fresh,
    dispatch_comment,
    dispatched_already,
    live_reservations,
    render_brief,
)
from fr.triage.batch_version import read_source, reserve
from fr.triage.errors import TriageError
from fr.triage.gitseam import Checkout
from fr.triage.model import (
    Batch,
    CancelEvent,
    DispatchEvent,
    Facts,
    Judgements,
    Launch,
    load_judgements,
    state_dir,
)
from fr.triage.render import plural

if TYPE_CHECKING:
    from fr_dispatch.protocols import Runner
    from fr_dispatch.work_item import WorkItem

DISPATCH_INSTALL_HINT = (
    "dispatching to a runner requires fr-dispatch — install it "
    "(e.g. `uv tool install --with fr-dispatch fr`) and re-run."
)


def make_client(url: str) -> GhClient:
    """The forge adapter for the repo *url* lives on (§3.J). Tests replace this."""
    return client_for_backend(backend_for_url(url))


def make_checkout(path: Path | None) -> Checkout:
    """The local clone the batch verbs work in (§3.I). Tests replace this."""
    return Checkout.at(path)


def load_runner(name: str) -> Runner:
    """Build runner *name* through `fr_dispatch.registry.load_runner` (§3.C step 1).

    The soft point: `fr_dispatch` is imported here, behind find_spec, never at
    module level. Tests replace this.
    """
    if importlib.util.find_spec("fr_dispatch") is None:
        _fail(DISPATCH_INSTALL_HINT)
    from fr_dispatch.registry import RunnerLoadError
    from fr_dispatch.registry import load_runner as _load

    try:
        return _load(name)
    except RunnerLoadError as exc:
        _fail(str(exc))


def _fail(message: str, code: int = 2) -> NoReturn:
    err_console.print(f"[red]error:[/red] {escape(message)}", soft_wrap=True)
    raise typer.Exit(code=code)


def _now_after(batch: Batch) -> datetime:
    """Now, or the batch's last event time if the clock is behind it: a skewed
    clock never breaks the time-order load rule."""
    now = datetime.now(UTC)
    return max(now, batch.events[-1].at) if batch.events else now


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


def _write(target: Path, batches: list[Batch], facts: Facts, *, read: list[Batch]) -> None:
    """Hold the open-batch rule, then write through the loader's model.

    *read* is the batches the verb loaded: the write is refused if the file's
    batches changed since (review r2p-f7).
    """
    try:
        check_open_membership(batches, facts)
        save_batches(target / "judgements.yaml", batches, read=read)
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
    _write(target, [*judgements.batches, new], facts, read=judgements.batches)
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
        ids += list(add_issue or [])  # a key already present is refused by the model
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
    _write(target, _replace(judgements.batches, new), facts, read=judgements.batches)
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
        # Read every member's comments BEFORE any write (review r2p-f8): the read
        # is the one operation a backend may not support, so an unsupported
        # backend is refused (exit 2) with no member half-withdrawn.
        posted: dict[str, bool] = {}
        for key in batch.ids:
            number = int(key.rpartition("#")[2])
            try:
                posted[key] = withdrawn_already(
                    client.list_issue_comments(owner_repo, number), item
                )
            except UnsupportedForgeOperation as exc:
                _fail(str(exc))
            except FORGE_ERRORS as exc:  # a forge failure: report the member, keep going
                failed.append(f"{key}: {exc}")
        for key in batch.ids:
            if key not in posted:
                continue  # its read failed: nothing written for it, reported above
            number = int(key.rpartition("#")[2])
            try:
                client.edit_issue_labels(
                    owner_repo, number, add=frozenset(), remove=frozenset({FR_IN_PROGRESS.name})
                )
                if not posted[key]:
                    client.comment_issue(owner_repo, number, withdrawal_body(batch, item, reason))
            except UnsupportedForgeOperation as exc:
                _fail(str(exc))
            except FORGE_ERRORS as exc:  # a forge failure: report the member, keep going
                failed.append(f"{key}: {exc}")
        if failed:
            _fail(
                "these members were not fully withdrawn, so no cancel event was written; "
                "re-run to complete: " + "; ".join(failed),
                code=1,
            )
    event = CancelEvent(kind="cancel", at=_now_after(batch), reason=reason)
    cancelled = batch.model_copy(update={"events": [*batch.events, event]})
    _write(target, _replace(judgements.batches, cancelled), facts, read=judgements.batches)
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


# ---------------------------------------------------------------- dispatch

CheckoutOpt = Annotated[
    Path | None,
    typer.Option(
        "--checkout",
        help="A local clone of the batch's repo; default: this directory's git toplevel.",
    ),
]


def _open_checkout(path: Path | None, owner_repo: str) -> Checkout:
    """The clone (§3.I), refused unless its origin is the batch's repo."""
    try:
        checkout = make_checkout(path)
        origin = checkout.origin_repo()
    except TriageError as exc:
        _fail(str(exc))
    if origin is None or origin.lower() != owner_repo.lower():
        _fail(
            f"--checkout {checkout.path}: its origin is {origin or 'not a forge repo'}, "
            f"not the batch's repo {owner_repo}"
        )
    return checkout


def _reservation(
    checkout: Checkout, facts: Facts, judgements: Judgements, batch: Batch, owner_repo: str
) -> str | None:
    """Fetch, hold the config-freshness rule, and reserve a version (§3.D, §3.I)."""
    config = facts.config_for(owner_repo)
    try:
        checkout.fetch()
        default = f"origin/{checkout.default_branch()}"
        check_config_fresh(facts.collected_at, checkout.last_change(default, TRIAGE_CONFIG_PATH))
        if config.version is None:
            return None
        text = checkout.show(default, config.version.source.file)
        if text is None:
            _fail(f"{config.version.source.file} does not exist on {default}")
        source = read_source(text, config.version.source)
        live = live_reservations(judgements.batches, facts, owner_repo, skip=batch.id)
        return reserve(source, live, batch.bump)
    except TriageError as exc:
        _fail(str(exc))


def _work_item(
    owner_repo: str, batch: Batch, launch: Launch, brief: str, reserved: str | None, cwd: Path
) -> WorkItem:
    """The run item (§3.C step 4); `tracking` stays None — a batch is many issues."""
    from fr_dispatch.work_item import WorkItem, run_item_id

    payload: dict[str, Any] = {
        "brief": brief,
        "harness": launch.harness,
        "model": launch.model,
        "branch": batch_branch(batch.id),
        "reserved_version": reserved,
        "issues": list(batch.ids),
        "checkout": str(cwd),  # herdr's --cwd (decision p2-dispatch-handle)
    }
    return WorkItem(
        id=run_item_id(owner_repo, f"batch-{batch.id}"),
        unit="run",
        workflow="fr-goal",
        repo=owner_repo,
        parent=None,
        inputs=(),
        payload=payload,
        tracking=None,
    )


def _forge_writes(client: GhClient, owner_repo: str, batch: Batch, item_id: str) -> list[str]:
    """Make the dispatch visible on each member (§3.E); the members NOT written.

    Idempotent, which is what makes `--repair` safe: the label add is a no-op
    when present, and the comment is skipped when a dispatch marker newer than
    the latest withdrawal exists. Every member's comments are read BEFORE any
    write, so a backend that cannot read them is refused (exit 2) with no
    member half-written (the r2p-f8 pattern of `cancel`).
    """
    failed: list[str] = []
    posted: dict[str, bool] = {}
    for key in batch.ids:
        number = int(key.rpartition("#")[2])
        try:
            posted[key] = dispatched_already(
                client.list_issue_comments(owner_repo, number), item_id
            )
        except UnsupportedForgeOperation as exc:
            _fail(str(exc))
        except FORGE_ERRORS as exc:
            failed.append(f"{key}: {exc}")
    if not posted:
        return failed
    try:
        client.ensure_labels(owner_repo, [FR_IN_PROGRESS])
    except UnsupportedForgeOperation as exc:
        _fail(str(exc))
    except FORGE_ERRORS as exc:
        return [*failed, *(f"{k}: {exc}" for k in posted)]
    for key, already in posted.items():
        number = int(key.rpartition("#")[2])
        try:
            client.edit_issue_labels(
                owner_repo, number, add=frozenset({FR_IN_PROGRESS.name}), remove=frozenset()
            )
            if not already:
                client.comment_issue(owner_repo, number, dispatch_comment(batch, item_id, key))
        except UnsupportedForgeOperation as exc:
            _fail(str(exc))
        except FORGE_ERRORS as exc:
            failed.append(f"{key}: {exc}")
    return failed


def _report_forge_writes(failed: list[str], batch: Batch) -> None:
    if failed:
        _fail(
            "the dispatch is recorded, but these members were not fully marked on the "
            f"forge: {'; '.join(failed)}. Complete them with "
            f"`fr triage batch dispatch {batch.id} --repair --yes`",
            code=1,
        )


def _repair(batch: Batch, owner_repo: str, client: GhClient, *, yes: bool) -> None:
    """`dispatch --repair` (§3.C): redo only the forge writes of the last dispatch.

    Never calls the runner and never re-reserves: the event's branch and
    reserved version stand as recorded.
    """
    event = batch.events[-1] if batch.events else None
    if not isinstance(event, DispatchEvent):
        _fail(
            f"batch {batch.id!r} has no dispatch as its last event; --repair only "
            "completes the forge writes of one"
        )
    item_id = batch_item_id(owner_repo, batch.id)
    console.print(f"repair the forge writes of batch {batch.id} ({item_id})", markup=False)
    console.print(f"  branch: {event.branch}", markup=False)
    console.print(f"  reserved version: {event.reserved_version or '(none)'}", markup=False)
    for key in batch.ids:
        console.print(
            f"  {key}: add {FR_IN_PROGRESS.name}, post the marker comment if missing",
            markup=False,
        )
    if not yes:
        console.print("nothing written; re-run with --yes to act", markup=False)
        return
    _report_forge_writes(_forge_writes(client, owner_repo, batch, item_id), batch)
    console.print(f"repaired batch {batch.id}", markup=False)


@batch_app.command("dispatch")
def batch_dispatch_command(
    batch_id: Annotated[str, typer.Argument(help="The batch to dispatch.")],
    to: Annotated[
        str | None, typer.Option("--to", help="Runner; default: the batch's launch.runner.")
    ] = None,
    checkout_path: CheckoutOpt = None,
    repair: Annotated[
        bool,
        typer.Option("--repair", help="Redo only the forge writes of the last dispatch."),
    ] = False,
    yes: Annotated[bool, typer.Option("--yes", help="Act; without it, print the plan.")] = False,
    repo: RepoOpt = None,
    org: OrgOpt = None,
    dir_override: DirOpt = None,
) -> None:
    """Hand a batch to a runner as one fr-goal run, and mark its issues taken."""
    target, facts, judgements = _load_state(_scope(repo, org), dir_override)
    batch = _find(judgements.batches, batch_id)
    owner_repo = batch_repo(batch, facts)
    if owner_repo is None:
        _fail(f"batch {batch.id!r}: its repo {batch.repo_name!r} is not in this scope's facts")
    client = make_client(f"https://{_host_of(facts, owner_repo)}/{owner_repo}")
    if repair:
        _repair(batch, owner_repo, client, yes=yes)
        return
    try:
        launch = resolve_launch(
            batch.model_copy(update={"launch": batch.launch.model_copy(update={"runner": to})})
            if to
            else batch,
            facts.config_for(owner_repo),
        )
    except TriageError as exc:
        _fail(str(exc))
    runner_name, model = str(launch.runner), str(launch.model)
    runner = load_runner(runner_name)  # step 1
    checkout = _open_checkout(checkout_path, owner_repo)
    reserved = _reservation(checkout, facts, judgements, batch, owner_repo)  # step 2
    try:
        refs = [client.closing_ref(owner_repo, int(k.rpartition("#")[2])) for k in batch.ids]
    except UnsupportedForgeOperation as exc:
        _fail(str(exc))
    brief = render_brief(  # step 3
        batch,
        judgements,
        facts,
        repo=owner_repo,
        closing_refs=refs,
        reserved_version=reserved,
        model=model,
    )
    item = _work_item(owner_repo, batch, launch, brief, reserved, checkout.path)  # step 4
    branch = batch_branch(batch.id)
    console.print(f"dispatch batch {batch.id} as {item.id}", markup=False)
    console.print(f"  runner: {runner_name}", markup=False)
    console.print(f"  harness: {launch.harness}", markup=False)
    console.print(f"  model: {model}", markup=False)
    console.print(f"  branch: {branch}", markup=False)
    console.print(f"  reserved version: {reserved or '(none: no version block)'}", markup=False)
    console.print("  brief:", markup=False)
    console.print(brief, markup=False, soft_wrap=True, highlight=False)
    if not yes:  # step 5
        console.print("nothing written; re-run with --yes to act", markup=False)
        return
    # Step 6, in the spec's order: every gate before the first backend call.
    stage = derive_batch_stage(batch, facts)
    if stage not in DISPATCHABLE:
        last = last_dispatch(batch)
        _fail(
            f"batch {batch.id!r} is {stage}; a batch is never started twice "
            f"(last dispatched to {last.runner if last else '?'}, handle "
            f"{last.handle if last else '?'}). To complete its forge writes, run "
            f"`fr triage batch dispatch {batch.id} --repair --yes`"
        )
    try:
        taken = stage == "proposed" and checkout.remote_branch_exists(branch)
    except TriageError as exc:
        _fail(str(exc))
    if taken:
        _fail(
            f"branch {branch} is already on origin for proposed batch {batch.id!r}: it was "
            "already dispatched from another scope"
        )
    if not runner.can_dispatch(item):
        _fail(f"runner `{runner_name}` does not take run-unit work")
    refusal = runner.preflight([item])
    if refusal:
        _fail(f"runner `{runner_name}` refused: {refusal}")
    if item.id in runner.existing_dispatches([item]):
        _fail(f"runner `{runner_name}` already holds {item.id} live; nothing written")
    try:
        handle = runner.dispatch(item)
    except Exception as exc:  # the runner's own failure: nothing is written
        _fail(f"runner `{runner_name}` failed to dispatch {item.id}: {exc}", code=1)
    event = DispatchEvent(
        kind="dispatch",
        at=_now_after(batch),
        runner=runner_name,
        # Review r2p-handle: a runner with no handle of its own returns None; the
        # item id is its identity for the dispatch (`existing_dispatches` matches it).
        handle=handle if handle else item.id,
        branch=branch,
        reserved_version=reserved,
    )
    dispatched = batch.model_copy(update={"events": [*batch.events, event]})
    _write(target, _replace(judgements.batches, dispatched), facts, read=judgements.batches)
    _report_forge_writes(_forge_writes(client, owner_repo, dispatched, item.id), batch)  # 6.6
    console.print(f"dispatched batch {batch.id}", markup=False)
