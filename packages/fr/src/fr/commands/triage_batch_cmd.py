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
import json
import os
import tempfile
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, NoReturn
from urllib.parse import urlparse

import typer
import yaml
from pydantic import ValidationError
from rich.markup import escape

from fr._hosts import backend_for_url
from fr.acceptance.ci import CI_CONFIG_PATHS
from fr.commands.triage_cmd import (
    DirOpt,
    OrgOpt,
    RepoOpt,
    _load_state,
    _scope,
    batch_app,
    collect_into,
    console,
    err_console,
)
from fr.ghclient import MERGE_METHODS, GhClient, UnsupportedForgeOperation
from fr.hostclient import FORGE_ERRORS, client_for_backend
from fr.labels import FR_IN_PROGRESS
from fr.models import REPO_MODELS_REL, default_models_path, load_models, resolved_config
from fr.services import ServicesError, require_tracker
from fr.services.resolve import resolve_services
from fr.triage.batch import (
    CLOSED_OUT,
    batch_branch,
    batch_item_id,
    batch_pr,
    batch_repo,
    batch_workflow,
    check_dependencies,
    check_open_membership,
    closeout_state,
    dependency_state,
    derive_batch_stage,
    last_dispatch,
    mixed_themes,
    pr_open_queue,
    resolve_launch,
    save_batches,
    suggest,
    withdrawal_body,
    withdrawn_already,
)
from fr.triage.batch_dispatch import (
    DISPATCHABLE,
    LIVE_STAGES,
    TRIAGE_CONFIG_PATH,
    check_config_fresh,
    dispatch_comment,
    dispatched_already,
    live_reservations,
    render_brief,
)
from fr.triage.batch_drive import (
    ARCHIVE_PREFIXES,
    DEFAULT_MAX_INFLIGHT,
    RUNS_DIR,
    Action,
    LivePr,
    Snapshot,
    Summary,
    action_line,
    checks_verdict,
    closeout_brief,
    closeout_due,
    closeout_event,
    closeout_item_id,
    drive_pass,
    find_run,
    housekeeping_branch,
    is_archived,
    settle,
    summary_line,
)
from fr.triage.batch_merge import (
    MergeContext,
    MergeStopError,
    choose_method,
    describe,
    merge_ready,
    plan_queue,
    run_queue,
)
from fr.triage.batch_version import read_source, reserve
from fr.triage.errors import ForgeError, TriageError
from fr.triage.gitseam import Checkout
from fr.triage.model import (
    Batch,
    CancelEvent,
    CloseoutEvent,
    DispatchEvent,
    Facts,
    Judgements,
    Launch,
    PostMergeEvent,
    Scope,
    load_facts,
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
WaveOpt = Annotated[
    int | None, typer.Option("--wave", help="Wave number; the driver dispatches lower waves first.")
]
AfterOpt = Annotated[
    list[str] | None,
    typer.Option(
        "--after", help="A batch id that must be merged first; repeat (on edit: replaces the set)."
    ),
]
BumpOpt = Annotated[str | None, typer.Option("--bump", help="patch | minor | major.")]
SkillOpt = Annotated[
    str | None,
    typer.Option("--skill", help="goal | debug; goal dispatches /fr-goal, debug /fr-debugging."),
]
RunnerOpt = Annotated[str | None, typer.Option("--runner", help="Runner to launch with.")]
HarnessOpt = Annotated[str | None, typer.Option("--harness", help="Harness to launch.")]
ModelOpt = Annotated[
    str | None,
    typer.Option(
        "--model",
        help="Session model (the run's orchestrator); subagents use their `fr models` tiers.",
    ),
]


LIVE_WAVE_EDIT = frozenset({"proposed", "dispatched", "pr-open"})
"""The stages where `--wave` and `--after` may still change: the driver reads them live."""


def _launch(runner: str | None, harness: str | None, model: str | None) -> dict[str, str]:
    """Only the launch values given explicitly (§3.B): dispatch resolves the rest."""
    given = {"runner": runner, "harness": harness, "model": model}
    return {k: v for k, v in given.items() if v is not None}


def _save(
    target: Path, batches: list[Batch], facts: Facts, *, read: list[Batch], dry_run: bool = False
) -> None:
    """Hold the open-batch rule, then write through the loader's model; raise
    `TriageError` on a refusal. *dry_run* checks everything and writes nothing.

    *read* is the batches the verb loaded: the write is refused if the file's
    batches changed since (review r2p-f7).
    """
    check_open_membership(batches, facts)
    check_dependencies(batches)
    save_batches(target / "judgements.yaml", batches, read=read, dry_run=dry_run)


def _write(
    target: Path, batches: list[Batch], facts: Facts, *, read: list[Batch], dry_run: bool = False
) -> None:
    """`_save`, with a refusal as exit 2."""
    try:
        _save(target, batches, facts, read=read, dry_run=dry_run)
    except TriageError as exc:
        _fail(str(exc))


def _wave_columns(batch: Batch, batches: list[Batch], facts: Facts | None) -> str:
    """The `batch list` wave, dependency and close-out columns (wave-driver §A)."""
    deps = ",".join(
        f"{d}({dependency_state(d, batches, facts)})" if facts is not None else d
        for d in batch.after
    )
    closeout = closeout_state(batch, facts) if facts is not None else "none"
    wave = "-" if batch.wave is None else str(batch.wave)
    after = f"  after {deps}" if deps else ""
    return f"  wave {wave}{after}  close-out {closeout}"


def _warn_mixed_themes(batch: Batch, judgements: Judgements) -> None:
    """Print the §C d3 warning after a create/edit write; never a refusal."""
    if themes := mixed_themes(batch, judgements):
        console.print(
            f"warning: debug batch {batch.id} mixes themes ({', '.join(themes)}): a debug "
            "batch should be one root cause",
            markup=False,
        )


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
    facts = (
        load_facts(path.with_name("facts.json")) if path.with_name("facts.json").exists() else None
    )
    for b in batches:
        console.print(
            f"{b.id}  {plural(len(b.ids), 'issue')}  {b.title}{_wave_columns(b, batches, facts)}",
            markup=False,
            soft_wrap=True,
        )


@batch_app.command("create")
def batch_create_command(
    batch_id: Annotated[str, typer.Argument(help="Batch id, a slug: [a-z][a-z0-9-]{0,39}.")],
    title: TitleOpt = None,
    issue: IssueOpt = None,
    rationale: RationaleOpt = None,
    order: OrderOpt = None,
    wave: WaveOpt = None,
    after: AfterOpt = None,
    bump: BumpOpt = None,
    skill: SkillOpt = None,
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
    doc |= {"wave": wave} if wave is not None else {}
    doc |= {"after": list(after)} if after else {}
    doc |= {"bump": bump} if bump is not None else {}
    doc |= {"skill": skill} if skill is not None else {}
    doc |= {"launch": _launch(runner, harness, model)}
    try:
        new = Batch.model_validate(doc)
    except ValidationError as exc:
        _fail(f"invalid batch: {exc}")
    if any(b.id == new.id for b in judgements.batches):
        _fail(f"batch {new.id!r} already exists; use `fr triage batch edit`")
    _write(target, [*judgements.batches, new], facts, read=judgements.batches)
    console.print(f"created batch {new.id} ({plural(len(new.ids), 'issue')})", markup=False)
    _warn_mixed_themes(new, judgements)


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
    wave: WaveOpt = None,
    after: AfterOpt = None,
    no_wave: Annotated[bool, typer.Option("--no-wave", help="Clear the wave.")] = False,
    no_after: Annotated[
        bool, typer.Option("--no-after", help="Clear every dependency (`after`).")
    ] = False,
    bump: BumpOpt = None,
    skill: SkillOpt = None,
    runner: RunnerOpt = None,
    harness: HarnessOpt = None,
    model: ModelOpt = None,
    repo: RepoOpt = None,
    org: OrgOpt = None,
    dir_override: DirOpt = None,
) -> None:
    """Change a proposed batch; past `proposed`, only --order (and, until it merges,
    --wave and --after) may change."""
    if no_wave and wave is not None:
        _fail("--no-wave and --wave contradict each other")
    if no_after and after is not None:
        _fail("--no-after and --after contradict each other")
    target, facts, judgements = _load_state(_scope(repo, org), dir_override)
    batch = _find(judgements.batches, batch_id)
    changes: dict[str, object] = {}
    for name, value in (
        ("title", title),
        ("rationale", rationale),
        ("bump", bump),
        ("skill", skill),
    ):
        if value is not None:
            changes[name] = value
    if launch := _launch(runner, harness, model):
        changes["launch"] = batch.launch.model_dump(exclude_defaults=True) | launch
    if add_issue or remove_issue:
        drop = {k.lower() for k in remove_issue or []}
        ids = [k for k in batch.ids if k not in drop]
        ids += list(add_issue or [])  # a key already present is refused by the model
        changes["ids"] = ids
    set_wave = wave is not None or no_wave
    set_after = after is not None or no_after
    if not changes and order is None and not set_wave and not set_after:
        _fail("nothing to change: give at least one option")
    stage = derive_batch_stage(batch, facts)
    if changes and stage != "proposed":
        _fail(
            f"batch {batch.id!r} is {stage}; past proposed only --order, --wave and --after "
            "may change"
        )
    if (set_wave or set_after) and stage not in LIVE_WAVE_EDIT:
        _fail(f"batch {batch.id!r} is {stage}; --wave and --after change only until it merges")
    if order is not None:
        changes["order"] = order
    if set_wave:
        changes["wave"] = wave  # None under --no-wave
    if set_after:
        changes["after"] = list(after or [])
    try:
        doc = batch.model_dump(by_alias=True, exclude_defaults=True) | changes
        new = Batch.model_validate(doc)
    except ValidationError as exc:
        _fail(f"invalid batch: {exc}")
    _write(target, _replace(judgements.batches, new), facts, read=judgements.batches)
    console.print(f"edited batch {new.id}", markup=False)
    _warn_mixed_themes(new, judgements)


@batch_app.command("cancel")
def batch_cancel_command(
    batch_id: Annotated[str, typer.Argument(help="The batch to withdraw.")],
    reason: Annotated[str, typer.Option("--reason", help="Why; posted on each member.")] = "",
    yes: Annotated[bool, typer.Option("--yes", help="Act; without it, print the plan.")] = False,
    checkout_path: CheckoutOpt = None,
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
    if touches_forge:
        # gh#803: withdrawing writes labels and comments to the tracker, so it
        # is gated as dispatch is — a proposed batch writes nothing and needs
        # no clone.
        _tracking_gate(checkout_path, owner_repo, yes=yes)
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


def _tracking_gate(checkout_path: Path | None, owner_repo: str, *, yes: bool) -> None:
    """R6: dispatch marks issues taken and cancel withdraws them (gh#803), so a
    repo with `tracking: {type: none}` refuses `--yes` (exit 2) before the first
    forge call; a dry run only warns. `merge` is not gated: it writes no issue.
    Strict: a malformed tracking block refuses too. With `--yes` the clone must
    open AND be the batch's repo (`_open_checkout`), on `--repair` as well, so
    the declaration read is the target repo's and never another clone's."""
    if yes:
        checkout = _open_checkout(checkout_path, owner_repo)
    else:
        try:
            checkout = make_checkout(checkout_path)
        except TriageError:
            return  # a dry run needs no clone to warn
    try:
        require_tracker(checkout.path)
    except ServicesError as exc:
        if yes:
            _fail(str(exc))
        console.print(f"warning: --yes would be refused — {exc}", markup=False, soft_wrap=True)


def _orchestrator(repo_root: Path | None) -> Callable[[str], str | None]:
    """The `resolve_launch` orchestrator rung (spec 2026-09-27-triage-batch-launch
    §A): the ORCHESTRATOR tier binding for a harness, repo-over-user, read from
    *repo_root*'s own `docs/superpowers/models.yaml` (the checkout the run will
    work in, not the dispatcher's cwd) when one is known."""
    repo_cfg = load_models(repo_root / REPO_MODELS_REL) if repo_root else {}
    user_cfg = load_models(default_models_path())
    config = resolved_config(repo_cfg=repo_cfg, user_cfg=user_cfg)

    def resolve(harness: str) -> str | None:
        return config.get(harness, {}).get("orchestrator")

    return resolve


def _reservation(
    checkout: Checkout, facts: Facts, judgements: Judgements, batch: Batch, owner_repo: str
) -> str | None:
    """Fetch, hold the config-freshness rule, and reserve a version (§3.D, §3.I)."""
    config = facts.config_for(owner_repo)
    try:
        default = _fresh_config(checkout, facts, owner_repo)
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


def _fresh_config(checkout: Checkout, facts: Facts, owner_repo: str) -> str:
    """Fetch, then hold the §3.I rule: the collected `.fr/triage.yaml` must be the
    one on `origin/<default>` now. Returns that ref."""
    checkout.fetch()
    default = f"origin/{checkout.default_branch()}"
    check_config_fresh(facts.config.get(owner_repo), checkout.show(default, TRIAGE_CONFIG_PATH))
    return default


def _work_item(
    owner_repo: str, batch: Batch, launch: Launch, brief: str, reserved: str | None, cwd: Path
) -> WorkItem:
    """The run item (§3.C step 4); `tracking` stays None — a batch is many issues."""
    from fr_dispatch.work_item import WorkItem, run_item_id

    payload: dict[str, Any] = {
        "brief": brief,
        "harness": launch.harness,
        "model": launch.model,
        "branch": batch_branch(batch),
        "reserved_version": reserved,
        "issues": list(batch.ids),
        "checkout": str(cwd),  # herdr's --cwd (decision p2-dispatch-handle)
    }
    return WorkItem(
        id=run_item_id(owner_repo, f"batch-{batch.id}"),
        unit="run",
        workflow=batch_workflow(batch),
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


def _repair(
    batch: Batch,
    owner_repo: str,
    client: GhClient,
    facts: Facts,
    *,
    yes: bool,
) -> None:
    """`dispatch --repair` (§3.C): redo only the forge writes of the last dispatch.

    Never calls the runner and never re-reserves: the event's branch and
    reserved version stand as recorded. Only a batch still in flight
    (`dispatched`, `pr-open`) is repaired: a merged, partial or abandoned
    batch's members are closed or released, and re-labelling them would mark
    them taken again (review r3-f9).
    """
    event = batch.events[-1]
    assert isinstance(event, DispatchEvent)
    stage = derive_batch_stage(batch, facts)
    if stage not in LIVE_STAGES:
        _fail(
            f"batch {batch.id!r} is {stage}; --repair only completes the forge writes of a "
            "dispatched or pr-open batch"
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


def _probe(owner_repo: str, batch: Batch, launch: Launch) -> WorkItem:
    """The run item's identity alone, for `preflight` / `existing_dispatches`."""
    from fr_dispatch.work_item import WorkItem, run_item_id

    return WorkItem(
        id=run_item_id(owner_repo, f"batch-{batch.id}"),
        unit="run",
        workflow=batch_workflow(batch),
        repo=owner_repo,
        parent=None,
        inputs=(),
        payload={"harness": launch.harness, "model": launch.model},
        tracking=None,
    )


def _record_missing(
    target: Path,
    judgements: Judgements,
    facts: Facts,
    batch: Batch,
    owner_repo: str,
    client: GhClient,
    *,
    to: str | None,
    handle: str | None,
    reserved: str | None,
    yes: bool,
    checkout_path: Path | None,
) -> None:
    """`dispatch --repair` for a launch whose event was never written (r3-f1).

    The runner must report the run live: that, not the operator's word, is the
    evidence a dispatch happened. The event records the handle and reserved
    version the failed dispatch printed; nothing is launched or re-reserved.
    """
    try:
        resolved = resolve_launch(
            _with_runner(batch, to),
            facts.config_for(owner_repo),
            orchestrator=_orchestrator(checkout_path),
        )
    except TriageError as exc:
        _fail(str(exc))
    launch = resolved.launch
    runner_name = str(launch.runner)
    runner = load_runner(runner_name)
    probe = _probe(owner_repo, batch, launch)
    refusal = runner.preflight([probe])
    if refusal:
        _fail(f"runner `{runner_name}` refused: {refusal}")
    if probe.id not in runner.existing_dispatches([probe]):
        _fail(
            f"batch {batch.id!r} has no dispatch as its last event, and runner "
            f"`{runner_name}` holds no live {probe.id}. --repair records a dispatch only for "
            f"a run the runner reports live; to start one, `fr triage batch dispatch "
            f"{batch.id} --yes`"
        )
    if reserved is None and facts.config_for(owner_repo).version is not None:
        _fail(
            "this repo reserves versions: give --reserved-version, the version the failed "
            "dispatch printed (the run was briefed with it)"
        )
    branch = batch_branch(batch)
    console.print(f"record the missing dispatch of batch {batch.id} ({probe.id})", markup=False)
    console.print(f"  runner: {runner_name} (reports it live)", markup=False)
    console.print(f"  handle: {handle or probe.id}", markup=False)
    console.print(f"  branch: {branch}", markup=False)
    console.print(f"  reserved version: {reserved or '(none)'}", markup=False)
    console.print("  then add the label and marker comment on every member", markup=False)
    if not yes:
        console.print("nothing written; re-run with --yes to act", markup=False)
        return
    event = DispatchEvent(
        kind="dispatch",
        at=_now_after(batch),
        runner=runner_name,
        handle=handle or probe.id,
        branch=branch,
        reserved_version=reserved,
    )
    dispatched = batch.model_copy(update={"events": [*batch.events, event]})
    _write(target, _replace(judgements.batches, dispatched), facts, read=judgements.batches)
    _report_forge_writes(_forge_writes(client, owner_repo, dispatched, probe.id), batch)
    console.print(f"recorded and repaired batch {batch.id}", markup=False)


def _with_runner(batch: Batch, to: str | None) -> Batch:
    """*batch* with `--to` as its launch runner, when given."""
    if not to:
        return batch
    return batch.model_copy(update={"launch": batch.launch.model_copy(update={"runner": to})})


def _recovery(
    batch: Batch, runner_name: str, handle: str, reserved: str | None, to: str | None
) -> str:
    """The exact command that records a launched run's missing event."""
    parts = [f"fr triage batch dispatch {batch.id} --repair --yes --handle {handle}"]
    if reserved is not None:
        parts.append(f"--reserved-version {reserved}")
    if to:
        parts.append(f"--to {runner_name}")
    return " ".join(parts)


@batch_app.command("dispatch")
def batch_dispatch_command(
    batch_id: Annotated[str, typer.Argument(help="The batch to dispatch.")],
    to: Annotated[
        str | None, typer.Option("--to", help="Runner; default: the batch's launch.runner.")
    ] = None,
    checkout_path: CheckoutOpt = None,
    repair: Annotated[
        bool,
        typer.Option(
            "--repair",
            help="Redo only the forge writes of the last dispatch; or record the dispatch "
            "of a run the runner reports live whose event was never written.",
        ),
    ] = False,
    handle: Annotated[
        str | None,
        typer.Option("--handle", help="With --repair: the handle a failed dispatch printed."),
    ] = None,
    reserved_version: Annotated[
        str | None,
        typer.Option(
            "--reserved-version",
            help="With --repair: the reserved version a failed dispatch printed.",
        ),
    ] = None,
    yes: Annotated[bool, typer.Option("--yes", help="Act; without it, print the plan.")] = False,
    repo: RepoOpt = None,
    org: OrgOpt = None,
    dir_override: DirOpt = None,
) -> None:
    """Hand a batch to a runner as one fr-goal run, and mark its issues taken."""
    target, facts, judgements = _load_state(_scope(repo, org), dir_override)
    batch = _find(judgements.batches, batch_id)
    dispatch_batch(
        target,
        facts,
        judgements,
        batch,
        to=to,
        checkout_path=checkout_path,
        repair=repair,
        handle=handle,
        reserved_version=reserved_version,
        yes=yes,
    )


def dispatch_batch(
    target: Path,
    facts: Facts,
    judgements: Judgements,
    batch: Batch,
    *,
    to: str | None = None,
    checkout_path: Path | None = None,
    repair: bool = False,
    handle: str | None = None,
    reserved_version: str | None = None,
    yes: bool = False,
) -> None:
    """The body of `batch dispatch`, callable: one batch, one runner, one dispatch.

    `batch dispatch` and the wave driver share it, so a driver dispatch runs the same
    preflight, version reservation, brief, event write and forge labels. A refusal is
    `typer.Exit` with the verb's own exit code, exactly as at the command line.
    """
    owner_repo = batch_repo(batch, facts)
    if owner_repo is None:
        _fail(f"batch {batch.id!r}: its repo {batch.repo_name!r} is not in this scope's facts")
    _tracking_gate(checkout_path, owner_repo, yes=yes)  # before any forge call
    client = make_client(f"https://{_host_of(facts, owner_repo)}/{owner_repo}")
    if (handle or reserved_version) and not repair:
        _fail("--handle and --reserved-version go with --repair only")
    if repair:
        if batch.events and isinstance(batch.events[-1], DispatchEvent):
            _repair(batch, owner_repo, client, facts, yes=yes)
        else:
            _record_missing(
                target,
                judgements,
                facts,
                batch,
                owner_repo,
                client,
                to=to,
                handle=handle,
                reserved=reserved_version,
                yes=yes,
                checkout_path=checkout_path,
            )
        return
    checkout = _open_checkout(checkout_path, owner_repo)
    try:
        resolved = resolve_launch(
            _with_runner(batch, to),
            facts.config_for(owner_repo),
            orchestrator=_orchestrator(checkout.path),
        )
    except TriageError as exc:
        _fail(str(exc))
    launch = resolved.launch
    runner_name, model = str(launch.runner), str(launch.model)
    runner = load_runner(runner_name)  # step 1
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
    )
    item = _work_item(owner_repo, batch, launch, brief, reserved, checkout.path)  # step 4
    branch = batch_branch(batch)
    console.print(f"dispatch batch {batch.id} as {item.id}", markup=False)
    console.print(f"  runner: {runner_name}", markup=False)
    console.print(f"  harness: {launch.harness}", markup=False)
    console.print(f"  model: {model} ({resolved.model_source})", markup=False)
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
    # The event the launch will record, and the judgements it will leave. The
    # open-batch rule and compare-before-write run on them HERE, before any
    # runner call, and again just before the launch: a launch cannot be undone,
    # so the write after it must not be able to refuse on either (review r3-f1).
    event = DispatchEvent(
        kind="dispatch",
        at=_now_after(batch),
        runner=runner_name,
        handle=item.id,
        branch=branch,
        reserved_version=reserved,
    )

    def _after(ev: DispatchEvent) -> list[Batch]:
        return _replace(
            judgements.batches, batch.model_copy(update={"events": [*batch.events, ev]})
        )

    _write(target, _after(event), facts, read=judgements.batches, dry_run=True)
    if not runner.can_dispatch(item):
        _fail(f"runner `{runner_name}` does not take run-unit work")
    refusal = runner.preflight([item])
    if refusal:
        _fail(f"runner `{runner_name}` refused: {refusal}")
    if item.id in runner.existing_dispatches([item]):
        _fail(f"runner `{runner_name}` already holds {item.id} live; nothing written")
    _write(target, _after(event), facts, read=judgements.batches, dry_run=True)
    try:
        launched = runner.dispatch(item)
    except Exception as exc:  # the runner's own failure: nothing is written
        _fail(f"runner `{runner_name}` failed to dispatch {item.id}: {exc}", code=1)
    # Review r2p-handle: a runner with no handle of its own returns None; the
    # item id is its identity for the dispatch (`existing_dispatches` matches it).
    event = event.model_copy(update={"handle": launched if launched else item.id})
    try:
        _save(target, _after(event), facts, read=judgements.batches)
    except TriageError as exc:
        _fail(
            f"runner `{runner_name}` launched {item.id} (handle {event.handle}), but its "
            f"dispatch event was not recorded: {exc}. The run is live on branch {branch}"
            + (f", briefed with reserved version {reserved}" if reserved else "")
            + ". Nothing was written to the forge. Once the refusal is resolved, record it "
            f"and complete the forge writes with "
            f"`{_recovery(batch, runner_name, event.handle, reserved, to)}`",
            code=1,
        )
    dispatched = _after(event)
    _report_forge_writes(  # 6.7
        _forge_writes(client, owner_repo, _find(dispatched, batch.id), item.id), batch
    )
    console.print(f"dispatched batch {batch.id}", markup=False)


# ------------------------------------------------------------------- merge


@batch_app.command("merge")
def batch_merge_command(
    batch_ids: Annotated[
        list[str] | None, typer.Argument(help="Batches to merge; default: every pr-open batch.")
    ] = None,
    checkout_path: CheckoutOpt = None,
    method: Annotated[
        str | None,
        typer.Option(
            "--method",
            help="merge | squash | rebase; default: the repo's own (it must allow it).",
        ),
    ] = None,
    yes: Annotated[bool, typer.Option("--yes", help="Act; without it, print the plan.")] = False,
    repo: RepoOpt = None,
    org: OrgOpt = None,
    dir_override: DirOpt = None,
) -> None:
    """Merge pr-open batch PRs in the computed order, re-slotting versions (§3.F).

    Blocks in the foreground while required checks run; Ctrl-C and re-run
    resumes at the first unmerged batch.
    """
    if method is not None and method not in MERGE_METHODS:
        _fail(f"--method must be one of {', '.join(sorted(MERGE_METHODS))}, got {method!r}")
    target, facts, judgements = _load_state(_scope(repo, org), dir_override)
    queue = pr_open_queue(judgements.batches, facts, judgements.issues)
    if batch_ids:
        wanted = {b.lower() for b in batch_ids}
        known = {e.batch.id for e in queue}
        if missing := sorted(wanted - known):
            _fail(f"not a pr-open batch here: {', '.join(missing)}")
        queue = [e for e in queue if e.batch.id in wanted]
    if not queue:
        console.print("no pr-open batches to merge", markup=False)
        return
    repos = {batch_repo(e.batch, facts) for e in queue}
    if len(repos) != 1 or None in repos:
        _fail(
            "merge one repo's batches at a time: name the batches of one repo, "
            f"with --checkout a clone of it (these span {', '.join(sorted(map(str, repos)))})"
        )
    owner_repo = str(next(iter(repos)))
    checkout = _open_checkout(checkout_path, owner_repo)
    client = make_client(f"https://{_host_of(facts, owner_repo)}/{owner_repo}")
    try:
        # Merge runs the collected version.files / set / relock: the same
        # freshness rule as dispatch (review r3-f3), before anything is read.
        _fresh_config(checkout, facts, owner_repo)
        chosen = choose_method(method, client.repo_merge_methods(owner_repo))
    except UnsupportedForgeOperation as exc:
        _fail(str(exc))
    except TriageError as exc:
        _fail(str(exc))
    ctx = MergeContext(
        client=client,
        checkout=checkout,
        repo=owner_repo,
        version=facts.config_for(owner_repo).version,
        scratch_root=target / "merge",
        method=chosen,
        say=lambda line: console.print(line, markup=False, soft_wrap=True),
    )
    try:
        slots, merged = plan_queue(ctx, queue)
        for step in merged:
            ctx.say(f"{step.batch.id}: already merged (PR #{step.pr.number})")
        ctx.say(f"merge plan for {owner_repo} ({chosen}):")
        for i, slot in enumerate(slots, 1):
            ctx.say(describe(i, slot))
        if not yes:
            ctx.say("nothing merged; re-run with --yes to act")
            return
        run_queue(ctx, slots)
    except UnsupportedForgeOperation as exc:
        _fail(str(exc))
    except MergeStopError as exc:
        _fail(f"merge stopped: {exc}", code=1)
    except TriageError as exc:
        _fail(str(exc))
    ctx.say(f"merged {plural(len(slots), 'batch')}")


# ------------------------------------------------------------------- drive

DRIVE_LOCK = "drive.lock"
DEFAULT_INTERVAL = 120
LOCK_GRACE = 10.0
"""Seconds an unreadable `drive.lock` is held: long enough for a starter that
created it to have written it (review rg-7)."""
SERVICE_PATHS: tuple[str, ...] = (
    ".devcontainer/fr-profiles.yaml",
    *sorted({p for paths in CI_CONFIG_PATHS.values() for p in paths}),
)
"""What `ci none` is resolved from: the services declaration and the CI configs."""

DriveCheckoutOpt = Annotated[
    list[str] | None,
    typer.Option(
        "--checkout",
        help="REPO=PATH: the local clone of a repo's batches; repeat. A single-repo scope "
        "defaults to this directory's git toplevel.",
    ),
]


class ForgeReadError(Exception):
    """A forge read failed or timed out during a drive pass (gh#910). Loop mode skips
    the rest of the pass and reads again after `--interval`; `--once` and plan mode
    exit with *code*, as before."""

    def __init__(self, message: str, *, code: int) -> None:
        super().__init__(message)
        self.code = code


def recollect(scope: Scope, target: Path) -> None:
    """Re-collect facts.json through the `Forge` seam, as `fr triage collect` does:
    every stage is derived from facts, so each pass starts here (wave-driver §B).
    A forge that fails to answer raises `ForgeReadError`; any other refusal exits."""
    try:
        collect_into(scope, target)
    except ForgeError as exc:
        raise ForgeReadError(str(exc), code=2) from exc
    except TriageError as exc:
        _fail(str(exc))


def ci_is_none(path: Path) -> bool:
    """Whether the repo at *path* declares `ci none` (R4: merge on non-draft alone).
    An unreadable declaration is not `none`: the checks still gate the merge."""
    try:
        return resolve_services(path, lenient=True).ci.type == "none"
    except Exception:  # noqa: BLE001 — a services read never stops a pass
        return False


def _now() -> datetime:
    """The pass's clock; tests replace it."""
    return datetime.now(UTC)


def _sleep(seconds: float) -> None:
    """The loop's wait between passes; tests replace it."""
    time.sleep(seconds)


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # alive, owned by someone else
    return True


def _lock_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def _lock_pid(text: str) -> int | None:
    """The pid a lock names, or None when it is not (yet) a whole lock."""
    try:
        return int(json.loads(text)["pid"])
    except (ValueError, KeyError, TypeError):
        return None


@contextmanager
def drive_lock(target: Path) -> Iterator[None]:
    """`<state dir>/drive.lock` (pid, start time) for as long as a driver runs (R6).

    It serialises drivers only. A second driver on the same state directory refuses
    (exit 2). The lock is written to a private file first and linked into place, so
    it is never visible half-written; one that cannot be read anyway is held for
    `LOCK_GRACE` seconds before it counts as stale. A stale lock (its pid is gone)
    is moved aside atomically and checked to be the one judged stale, so two
    starters never both take it; and a driver removes the lock on exit only while
    it is still its own (review rg-7).
    """
    path = target / DRIVE_LOCK
    target.mkdir(parents=True, exist_ok=True)
    mine = json.dumps({"pid": os.getpid(), "started": _now().isoformat()})
    for _ in range(5):
        private = target / f".{DRIVE_LOCK}.{os.getpid()}.{uuid.uuid4().hex}"
        private.write_text(mine, encoding="utf-8")
        try:
            os.link(private, path)
            break
        except FileExistsError:
            pass
        finally:
            private.unlink(missing_ok=True)
        held = _lock_text(path)
        if held is None:
            continue  # released meanwhile: try again
        pid = _lock_pid(held)
        if pid is None:
            try:
                age = time.time() - path.stat().st_mtime
            except FileNotFoundError:
                continue
            if age < LOCK_GRACE:
                _fail(f"another driver is taking {path}; wait for it, or stop it first")
        elif _pid_alive(pid):
            started = json.loads(held).get("started")
            _fail(
                f"another driver holds {path} (pid {pid}, started {started}); "
                "stop it first, or wait for it to finish"
            )
        aside = target / f".{DRIVE_LOCK}.stale.{uuid.uuid4().hex}"
        try:
            os.rename(path, aside)
        except FileNotFoundError:
            continue
        if _lock_text(aside) != held:  # another starter took it over meanwhile
            try:
                os.link(aside, path)  # put theirs back
            except FileExistsError:
                pass
        aside.unlink(missing_ok=True)
    else:
        _fail(f"cannot take {path}: another driver keeps re-creating it")
    try:
        yield
    finally:
        if _lock_text(path) == mine:
            path.unlink(missing_ok=True)


def _batch_slug(scope: Scope, repo_name: str) -> str:
    """The OWNER/REPO a batch of *repo_name* lives in, among *scope*'s repos."""
    if scope.kind == "org":
        return f"{scope.target}/{repo_name}"
    if scope.kind == "group":
        return next((r for r in scope.repos if r.split("/", 1)[1].lower() == repo_name), repo_name)
    return scope.target


def _checkout_map(
    values: list[str] | None, scope: Scope, repos: set[str]
) -> dict[str, Path | None]:
    """`--checkout REPO=PATH`, repeatable, keyed by lower-cased OWNER/REPO.

    A single-repo scope defaults to the current git toplevel (None), as `batch
    dispatch` does; any other scope needs a mapping for every repo with a batch to
    drive, refused before anything runs."""
    out: dict[str, Path | None] = {}
    for value in values or []:
        name, sep, where = value.partition("=")
        if not sep or name.count("/") != 1 or not where:
            _fail(f"--checkout takes REPO=PATH (OWNER/REPO=/path/to/clone), got {value!r}")
        out[name.lower()] = Path(where).expanduser()
    if scope.kind == "repo":
        stray = sorted(set(out) - {scope.target.lower()})
        if stray:
            _fail(
                f"--checkout names {', '.join(stray)}, which is not this scope's repo "
                f"{scope.target}"
            )
        out.setdefault(scope.target.lower(), None)
        return out
    if scope.kind == "group":
        stray = sorted(set(out) - {r.lower() for r in scope.repos})
        if stray:
            _fail(f"--checkout names {', '.join(stray)}, which is not in this scope's group")
        repos = set(
            scope.repos
        )  # a group needs a clone for EVERY repo, not only those with batches
    missing = sorted(r for r in repos if r.lower() not in out)
    if missing:
        _fail(f"give --checkout REPO=PATH for {', '.join(missing)}: no clone is known for it")
    return out


def _chosen(batches: list[Batch], named: list[str] | None) -> list[Batch]:
    """The batches to drive: those named; else every batch with a wave; else all."""
    if named:
        return [_find(batches, b) for b in named]
    waved = [b for b in batches if b.wave is not None]
    return waved or list(batches)


def _parse_at(stamp: str | None) -> datetime | None:
    if not stamp:
        return None
    try:
        parsed = datetime.fromisoformat(stamp)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _live_head_prs(client: GhClient, repo: str, head: str) -> list[LivePr]:
    """The PRs with head *head*, as the archive step reads them (merged ones too)."""
    out: list[LivePr] = []
    for rec in client.list_prs_by_head(repo, head):
        out.append(
            LivePr(
                number=int(rec.get("number", 0)),
                state=str(rec.get("state", "")).upper(),
                draft=bool(rec.get("isDraft")),
                head=str(rec.get("headRefOid") or ""),
                checks="pending",  # an open one's checks come from the facts' record
                head_ref=str(rec.get("headRefName") or head),
                files=tuple(
                    str(f.get("path") if isinstance(f, dict) else f) for f in rec.get("files") or ()
                ),
            )
        )
    return out


class _Driver:
    """One driver run: the scope's state, the clients and clones it reaches, and
    what it has reported (a failing head, a preflight refusal) across passes."""

    def __init__(
        self,
        scope: Scope,
        target: Path,
        *,
        named: list[str] | None,
        checkouts: dict[str, Path | None],
        max_inflight: int,
        yes: bool,
    ) -> None:
        self.scope, self.target, self.named = scope, target, named
        self.checkout_paths = checkouts
        self.max_inflight, self.yes = max_inflight, yes
        self.warned: set[str] = set()
        self.reported: set[str] = set()  # merge refusals already printed in full
        self.read_failures: set[str] = set()  # forge read failures, since the last good pass
        self.failed_write = False  # a forge write failed this pass (--once exits 1)
        self._first_seen: dict[str, datetime] = {}  # merged with no merge time known
        self._ci: dict[str, bool] = {}  # per pass: repo -> origin/<default> says ci none
        self._unlanded: set[str] = set()  # per pass: planned merges that did not land
        self._held = 0  # per pass: planned dispatches that did not start
        self._clients: dict[str, GhClient] = {}
        self._checkouts: dict[str, Checkout] = {}
        self._runners: dict[str, Runner] = {}
        self._merge: dict[str, MergeContext] = {}

    # -------------------------------------------------------------- reaching out

    def client(self, facts: Facts, repo: str) -> GhClient:
        if repo not in self._clients:
            self._clients[repo] = make_client(f"https://{_host_of(facts, repo)}/{repo}")
        return self._clients[repo]

    def path_of(self, repo: str) -> Path | None:
        return self.checkout_paths.get(repo.lower())

    def checkout(self, repo: str) -> Checkout:
        if repo not in self._checkouts:
            self._checkouts[repo] = _open_checkout(self.path_of(repo), repo)
        return self._checkouts[repo]

    def runner(self, name: str) -> Runner:
        if name not in self._runners:
            self._runners[name] = load_runner(name)
        return self._runners[name]

    def merge_ctx(self, facts: Facts, repo: str) -> MergeContext:
        if repo not in self._merge:
            client, checkout = self.client(facts, repo), self.checkout(repo)
            try:
                _fresh_config(checkout, facts, repo)
                method = choose_method(None, client.repo_merge_methods(repo))
            except UnsupportedForgeOperation as exc:
                _fail(str(exc))
            except TriageError as exc:
                _fail(str(exc))
            except FORGE_ERRORS as exc:
                raise ForgeReadError(f"a forge read failed: {exc}", code=1) from exc
            self._merge[repo] = MergeContext(
                client=client,
                checkout=checkout,
                repo=repo,
                version=facts.config_for(repo).version,
                scratch_root=self.target / "merge",
                method=method,
                say=lambda line: None,  # the driver prints one line per action itself
            )
        return self._merge[repo]

    # ------------------------------------------------------------------ snapshot

    def snapshot(self, facts: Facts, judgements: Judgements, now: datetime) -> Snapshot:
        """Every batch of the file, with the selection marked: the in-flight cap and
        the dependencies read them all, the actions only the selection (rg-3)."""
        chosen = _chosen(judgements.batches, self.named)
        ids = {b.id for b in chosen}
        repos = {b.id: r for b in judgements.batches if (r := batch_repo(b, facts)) is not None}
        stages = {b.id: derive_batch_stage(b, facts) for b in judgements.batches}
        queue = tuple(
            e
            for e in pr_open_queue(judgements.batches, facts, judgements.issues)
            if e.batch.id in ids
        )
        live: dict[str, LivePr] = {}
        merged_at: dict[str, datetime] = {}
        released: set[str] = set()
        archived: set[str] = set()
        archives: dict[str, tuple[LivePr, ...]] = {}
        due: list[Batch] = []
        try:
            for e in queue:
                repo = repos[e.batch.id]
                client = self.client(facts, repo)
                view = client.pr_view(repo, e.pr.number)
                verdict, failing = checks_verdict(
                    client.pr_required_checks(repo, e.pr.number),
                    e.pr.checks,
                    ci_none=self._ci_none(repo),
                )
                live[e.batch.id] = LivePr(
                    number=e.pr.number,
                    state=str(view.get("state")),
                    draft=bool(view.get("draft")),
                    head=str(view.get("head_oid") or ""),
                    checks=verdict,
                    failing=failing,
                    head_ref=e.pr.head_ref,
                )
            for b in chosen:
                if stages[b.id] not in ("merged", "partial") or b.id not in repos:
                    continue
                event = closeout_event(b)
                if event is None:
                    repo = repos[b.id]
                    pr = batch_pr(b, facts)
                    merge = (
                        str(self.client(facts, repo).pr_view(repo, pr.number).get("merge_commit")
                            or "")
                        if pr is not None
                        else ""
                    )  # fmt: skip
                    if self._archived(repo, merge):
                        archived.add(b.id)
                        continue
                    when = _parse_at(pr.merged_at if pr else None)
                    merged_at[b.id] = when or self._first_seen.setdefault(b.id, now)
                    if self._released(repo, merge):
                        released.add(b.id)
                    if closeout_due(released=b.id in released, merged_at=merged_at[b.id], now=now):
                        due.append(b)
                    continue
                if event.archived is not None:
                    continue  # its archive PR was merged by the driver: finished
                archives[repos[b.id]] = (
                    *archives.get(repos[b.id], ()),
                    *self._archive_prs(facts, repos[b.id], b, event),
                )
        except UnsupportedForgeOperation as exc:
            _fail(str(exc))
        except FORGE_ERRORS as exc:
            raise ForgeReadError(f"a forge read failed: {exc}", code=1) from exc
        return Snapshot(
            batches=tuple(judgements.batches),
            stages=stages,
            queue=queue,
            live=live,
            repos=repos,
            now=now,
            max_inflight=self.max_inflight,
            merged_at=merged_at,
            released=frozenset(released),
            archives=archives,
            existing=self._existing(facts, due, repos) if self.yes else frozenset(),
            warned=frozenset(self.warned),
            selected=frozenset(ids),
            archived=frozenset(archived),
        )

    def _reader(self, repo: str) -> Checkout:
        """The clone for a read: the checked one with --yes, else leniently opened
        (plan mode never refuses on a clone it does not write)."""
        return self.checkout(repo) if self.yes else make_checkout(self.path_of(repo))

    def _ci_none(self, repo: str) -> bool:
        """Whether `origin/<default>` declares `ci none` (R4), read from the default
        branch the way `_fresh_config` reads `.fr/triage.yaml` — never from the
        clone's working tree, which may be on any branch (review rg-5). Cached for
        the pass; an unreadable declaration is not `none`."""
        if repo not in self._ci:
            try:
                checkout = self._reader(repo)
                checkout.fetch()
                ref = f"origin/{checkout.default_branch()}"
                with tempfile.TemporaryDirectory(prefix="fr-ci-") as tmp:
                    checkout.snapshot_paths(ref, SERVICE_PATHS, Path(tmp))
                    self._ci[repo] = ci_is_none(Path(tmp))
            except TriageError:
                self._ci[repo] = False
        return self._ci[repo]

    def _archived(self, repo: str, merge_commit: str) -> bool:
        """Whether the batch merged by *merge_commit* was closed out already: the run
        artifacts it added are all gone from `origin/<default>` (`is_archived`), as
        `fr archive` leaves them, whether a driver or a hand ran the close-out."""
        try:
            checkout = self._reader(repo)
            checkout.fetch()
            tip = f"origin/{checkout.default_branch()}"
            return is_archived(
                checkout.added_paths(merge_commit), lambda p: checkout.exists_at(tip, p)
            )
        except TriageError as exc:
            if self.yes:
                _fail(str(exc))
            return False

    def _released(self, repo: str, merge_commit: str) -> bool:
        try:
            checkout = self._reader(repo)
            checkout.fetch()
            return checkout.released_after(merge_commit)
        except TriageError as exc:
            if self.yes:
                _fail(str(exc))
            return False

    def _archive_prs(
        self, facts: Facts, repo: str, batch: Batch, event: CloseoutEvent
    ) -> list[LivePr]:
        """Archive PR candidates: the open `chore/*` PRs collect read (with files and
        checks), plus any PR on the close-out's own heads, merged ones included."""
        client = self.client(facts, repo)
        out: dict[int, LivePr] = {}
        for pr in facts.prs:
            if (
                pr.repo != repo
                or pr.state != "OPEN"
                or not pr.head_ref.startswith(ARCHIVE_PREFIXES)
            ):
                continue
            verdict, failing = checks_verdict(
                client.pr_required_checks(repo, pr.number),
                pr.checks,
                ci_none=self._ci_none(repo),
            )
            out[pr.number] = LivePr(
                number=pr.number, state="OPEN", draft=pr.is_draft, head=pr.head_oid,
                checks=verdict, failing=failing, head_ref=pr.head_ref, files=tuple(pr.files),
            )  # fmt: skip
        last = last_dispatch(batch)
        heads = {housekeeping_branch(last.branch if last else batch_branch(batch), None, None)}
        heads |= {event.archive} if event.archive else set()
        for head in sorted(heads):
            for found in _live_head_prs(client, repo, head):
                if found.state != "OPEN" or found.number not in out:
                    out[found.number] = found
        return list(out.values())

    def _existing(
        self, facts: Facts, closing: list[Batch], repos: dict[str, str]
    ) -> frozenset[str]:
        """The close-out items the runners already hold live, so a kill between the
        dispatch and its event never starts a second session (§B step 2). Only the
        close-outs that are due are probed (review rg-10): a runner that cannot start
        one now must not stop a merge or a dispatch. A runner's preflight refusal is
        reported once and exits 2."""
        from fr_dispatch.work_item import WorkItem

        found: set[str] = set()
        by_runner: dict[str, list[WorkItem]] = {}
        for b in closing:
            launch = self._launch(facts, b, repos[b.id])
            probe = WorkItem(
                id=closeout_item_id(repos[b.id], b.id),
                unit="run",
                workflow=batch_workflow(b),
                repo=repos[b.id],
                parent=None,
                inputs=(),
                payload={"kind": "closeout", "harness": launch.harness, "model": launch.model},
                tracking=None,
            )
            by_runner.setdefault(str(launch.runner), []).append(probe)
        for name, probes in by_runner.items():
            runner = self.runner(name)
            refusal = runner.preflight(probes)
            if refusal:
                _fail(f"runner `{name}` refused: {refusal}")
            found |= runner.existing_dispatches(probes)
        return frozenset(found)

    def _launch(self, facts: Facts, batch: Batch, repo: str) -> Launch:
        try:
            return resolve_launch(  # the clone's models.yaml, as dispatch_batch reads it (rg-8)
                batch, facts.config_for(repo), orchestrator=_orchestrator(self.checkout(repo).path)
            ).launch
        except TriageError as exc:
            _fail(str(exc))

    # ------------------------------------------------------------------- execute

    def run_pass(self) -> tuple[bool, Summary, list[str]]:
        """One pass: re-collect, decide, act (with --yes) or print the plan.
        Returns whether it acted, the settled summary, and the blocked batch ids."""
        recollect(self.scope, self.target)
        _, facts, judgements = _load_state(self.scope, self.target)
        self._ci, self._unlanded, self._held = {}, set(), 0
        self.failed_write = False
        snap = self.snapshot(facts, judgements, _now())
        plan = drive_pass(snap)
        acted = False
        in_flight = sum(1 for b in snap.batches if snap.stages[b.id] in LIVE_STAGES)
        for action in plan.actions:
            if not self.yes:
                _say(action_line(action))
                continue
            outcome, did, in_flight = self._act(action, facts, in_flight)
            acted = acted or did
            _say(action_line(action, outcome))
        summary = settle(plan.summary, unlanded=len(self._unlanded), held=self._held)
        _say(summary_line(summary))
        if not self.yes:
            _say("nothing done; re-run with --yes to act")
        return acted, summary, [a.batch for a in plan.actions if a.kind == "blocked"]

    def _act(self, action: Action, facts: Facts, in_flight: int) -> tuple[str, bool, int]:
        """Execute *action*; its outcome line, whether it acted, and the in-flight count."""
        judgements = load_judgements(self.target / "judgements.yaml")
        batch = _find(judgements.batches, action.batch)
        repo = batch_repo(batch, facts)
        if action.kind in ("blocked", "held") or repo is None:
            return action.detail, False, in_flight
        if action.kind == "warn":
            self.warned.add(action.head)
            return action.detail, False, in_flight
        if action.kind == "merge":
            return self._merge_batch(action, facts, judgements, batch, repo, in_flight)
        if action.kind == "closeout":
            outcome, did = self._close_out(action, facts, judgements, batch, repo)
            return outcome, did, in_flight
        if action.kind == "archive":
            return self._archive(action, facts, judgements, batch, repo), True, in_flight
        waits = sorted(d for d in batch.after if d in self._unlanded)
        if waits:  # the pass planned this dispatch on a merge that did not land (rg-1)
            self._held += 1
            return (
                f"held: waits on {', '.join(waits)}, whose merge did not land this pass",
                False,
                in_flight,
            )
        if in_flight >= self.max_inflight:  # a planned merge did not land this pass
            self._held += 1
            return "held: the in-flight cap is reached", False, in_flight
        with console.capture():  # dispatch_batch's own plan: one line per action here
            dispatch_batch(
                self.target,
                facts,
                judgements,
                batch,
                checkout_path=self.path_of(repo),
                yes=True,
            )
        after = _find(load_judgements(self.target / "judgements.yaml").batches, batch.id)
        event = last_dispatch(after)
        assert event is not None
        return (
            f"dispatched to {event.runner} as {batch_item_id(repo, batch.id)}",
            True,
            in_flight + 1,
        )

    def _merge_batch(
        self,
        action: Action,
        facts: Facts,
        judgements: Judgements,
        batch: Batch,
        repo: str,
        in_flight: int,
    ) -> tuple[str, bool, int]:
        ctx = self.merge_ctx(facts, repo)
        entries = [
            e
            for e in pr_open_queue(judgements.batches, facts, judgements.issues)
            if e.batch.id == batch.id
        ]
        self._unlanded.add(batch.id)  # until the forge says it merged
        try:
            slots, _ = plan_queue(ctx, entries)
            if not slots:
                self._unlanded.discard(batch.id)
                return f"PR #{action.pr} is already merged", False, in_flight - 1
            if slots[0].head != action.head:  # pinned to the head whose checks were judged
                return (
                    f"held: PR #{action.pr} head moved from {action.head[:12]} to "
                    f"{slots[0].head[:12]} since its checks were judged; it is judged "
                    "again next pass",
                    False,
                    in_flight,
                )
            attempt = merge_ready(ctx, slots[0], None)
        except UnsupportedForgeOperation as exc:
            _fail(str(exc))
        except MergeStopError as exc:
            # A refusal ends neither the loop nor the pass (rg-4): it is reported in
            # full once per batch, head and reason, and `--once` exits 1 on it.
            self.failed_write = True
            key = f"{batch.id}\0{action.head}\0{exc}"
            if key in self.reported:
                return f"stopped again at {action.head[:12]} (reported above)", False, in_flight
            self.reported.add(key)
            return f"stopped: {exc}", False, in_flight
        except TriageError as exc:
            _fail(str(exc))
        except FORGE_ERRORS as exc:  # a re-read of the PR or its checks; the merge's own
            # refusal is a MergeStopError above, so no write failure lands here
            raise ForgeReadError(f"a forge read failed: {exc}", code=1) from exc
        if attempt.outcome in ("merged", "already-merged"):
            self._unlanded.discard(batch.id)
            return f"merged PR #{action.pr} at {attempt.head[:12]}", True, in_flight - 1
        if attempt.outcome == "updated":
            return (
                f"updated PR #{action.pr} to {attempt.head[:12]}; it merges on a later pass",
                True,
                in_flight,
            )
        held = f": {', '.join(attempt.checks)}" if attempt.checks else ""
        return f"held: PR #{action.pr} is {attempt.outcome}{held}", False, in_flight

    def _close_out(
        self, action: Action, facts: Facts, judgements: Judgements, batch: Batch, repo: str
    ) -> tuple[str, bool]:
        """§B step 2 and §C: fast-forward, post_merge, then the close-out item."""
        checkout = self.checkout(repo)
        try:
            checkout.fast_forward()
            _fresh_config(checkout, facts, repo)
        except TriageError as exc:
            return f"close-out held: {exc}", False
        command = facts.config_for(repo).post_merge
        if action.post_merge and command:
            try:
                checkout.run_command(command)
            except TriageError as exc:
                return f"post_merge failed, close-out held: {exc}", False
            batch = self._append(
                judgements, facts, batch, PostMergeEvent(kind="post_merge", at=_now_after(batch))
            )
            judgements = load_judgements(self.target / "judgements.yaml")
        last = last_dispatch(batch)
        branch = last.branch if last else batch_branch(batch)
        found = find_run(_cursors(checkout.path), branch)
        run, plan_slug = found if found else (None, None)
        archive = housekeeping_branch(branch, run, plan_slug)
        item_id = closeout_item_id(repo, batch.id)
        launch = self._launch(facts, batch, repo)
        if action.recorded:
            self._append(
                judgements, facts, batch,
                CloseoutEvent(kind="closeout", at=_now_after(batch), runner=str(launch.runner),
                              handle=item_id, run=run, archive=archive),
            )  # fmt: skip
            return f"recorded the live {item_id}", True
        item = _closeout_item(repo, batch, launch, run=run, checkout=checkout.path)
        runner = self.runner(str(launch.runner))
        if not runner.can_dispatch(item):
            _fail(f"runner `{launch.runner}` does not take run-unit work")
        refusal = runner.preflight([item])
        if refusal:
            _fail(f"runner `{launch.runner}` refused: {refusal}")
        try:
            handle = runner.dispatch(item)
        except Exception as exc:  # the runner's own failure: nothing is written
            _fail(f"runner `{launch.runner}` failed to dispatch {item.id}: {exc}", code=1)
        self._append(
            judgements, facts, batch,
            CloseoutEvent(kind="closeout", at=_now_after(batch), runner=str(launch.runner),
                          handle=handle or item.id, run=run, archive=archive),
        )  # fmt: skip
        pickup = f"--run {run}" if run else f"--branch {branch}"
        return f"started {item.id} (fr pickup {pickup})", True

    def _append(self, judgements: Judgements, facts: Facts, batch: Batch, event: Any) -> Batch:
        new = batch.model_copy(update={"events": [*batch.events, event]})
        _write(self.target, _replace(judgements.batches, new), facts, read=judgements.batches)
        return new

    def _archive(
        self, action: Action, facts: Facts, judgements: Judgements, batch: Batch, repo: str
    ) -> str:
        ctx = self.merge_ctx(facts, repo)
        assert action.pr is not None
        try:
            ctx.client.pr_merge(repo, action.pr, head_sha=action.head, method=ctx.method)
        except UnsupportedForgeOperation as exc:
            _fail(str(exc))
        except FORGE_ERRORS as exc:
            _fail(f"archive PR #{action.pr}: the forge refused the merge: {exc}", code=1)
        # Record it: a PR attributed by its files alone is not found again once it
        # left the open-PR list, and the batch would read as closing forever (rg-6).
        event = closeout_event(batch)
        if event is not None:
            self._append(
                judgements, facts, batch,
                event.model_copy(update={"at": _now_after(batch), "archived": action.pr}),
            )  # fmt: skip
        return f"merged archive PR #{action.pr}"


def _say(line: str) -> None:
    console.print(line, markup=False, soft_wrap=True, highlight=False)


def _cursors(root: Path) -> list[object]:
    """The parsed run cursors of the fast-forwarded checkout; an unreadable one is
    skipped (it cannot name the batch branch for certain)."""
    out: list[object] = []
    for path in sorted((root / RUNS_DIR).glob("*.yaml")):
        try:
            out.append(yaml.safe_load(path.read_text(encoding="utf-8")))
        except (OSError, yaml.YAMLError):
            continue
    return out


def _closeout_item(
    repo: str, batch: Batch, launch: Launch, *, run: str | None, checkout: Path
) -> WorkItem:
    """The close-out work item (§C): unit `run`, `payload.kind: closeout`, model from
    `resolve_launch`, checkout from the `--checkout` map."""
    from fr_dispatch.work_item import WorkItem

    last = last_dispatch(batch)
    payload: dict[str, Any] = {
        "kind": "closeout",
        "brief": closeout_brief(batch, run=run, checkout=checkout),
        "harness": launch.harness,
        "model": launch.model,
        "branch": last.branch if last else batch_branch(batch),
        "issues": list(batch.ids),
        "checkout": str(checkout),
    }
    return WorkItem(
        id=closeout_item_id(repo, batch.id),
        unit="run",
        workflow=batch_workflow(batch),
        repo=repo,
        parent=None,
        inputs=(),
        payload=payload,
        tracking=None,
    )


@batch_app.command("drive")
def batch_drive_command(
    batch_ids: Annotated[
        list[str] | None,
        typer.Argument(help="Batches to drive; default: every batch with a wave (else all)."),
    ] = None,
    once: Annotated[bool, typer.Option("--once", help="One pass, then exit (0, 3 or 2).")] = False,
    max_inflight: Annotated[
        int,
        typer.Option("--max-inflight", min=1, help="Batches dispatched and unmerged at once."),
    ] = DEFAULT_MAX_INFLIGHT,
    interval: Annotated[
        int, typer.Option("--interval", min=1, help="Seconds between passes in loop mode.")
    ] = DEFAULT_INTERVAL,
    checkout: DriveCheckoutOpt = None,
    yes: Annotated[
        bool, typer.Option("--yes", help="Act; without it, print one pass's plan and exit.")
    ] = False,
    repo: RepoOpt = None,
    org: OrgOpt = None,
    dir_override: DirOpt = None,
) -> None:
    """Drive batches to completion: merge what is ready, close out what merged,
    dispatch what may start (wave order, then merge order, then id).

    Exit codes: 0 acted or everything is done; 3 nothing to do while work remains;
    2 a refusal (a runner's preflight included); 1 a forge write failed.
    """
    scope = _scope(repo, org)
    target = state_dir(scope, dir_override)
    path = target / "judgements.yaml"
    try:
        known = load_judgements(path).batches if path.exists() else []
    except TriageError as exc:
        _fail(str(exc))
    chosen = _chosen(known, batch_ids) if known else []
    names = {_batch_slug(scope, b.repo_name) for b in chosen}
    checkouts = _checkout_map(checkout, scope, names)
    driver = _Driver(
        scope, target, named=batch_ids, checkouts=checkouts, max_inflight=max_inflight, yes=yes
    )
    with drive_lock(target):
        while True:
            try:
                acted, summary, blocked = driver.run_pass()
            except ForgeReadError as exc:
                if once or not yes:
                    _fail(str(exc), code=exc.code)
                # Like a refused merge (rg-4), a degraded forge ends neither the run nor
                # the loop: reported once per cause, then read again (gh#910).
                if str(exc) not in driver.read_failures:
                    driver.read_failures.add(str(exc))
                    err_console.print(
                        f"[yellow]warning:[/yellow] {escape(str(exc))}; pass skipped, "
                        f"retrying every {interval}s",
                        soft_wrap=True,
                    )
                _sleep(interval)
                continue
            driver.read_failures.clear()
            if not yes:
                return  # the plan of one pass, in loop mode too
            if once:
                if driver.failed_write:
                    raise typer.Exit(code=1)
                if acted or summary.done:
                    return
                raise typer.Exit(code=3)
            if summary.done:
                return
            if summary.waiting_on_operator:
                _say(
                    f"stopped: only blocked batches remain ({', '.join(blocked)}); "
                    "they need the operator"
                )
                raise typer.Exit(code=3)
            _sleep(interval)
