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
- `adopt` puts a session already running (started by hand) under the wave
  driver as an existing batch: it renames the session's branch to the batch
  branch, supersedes an open PR, labels the runner tab, records a dispatch and
  marks the members (spec 2026-10-06-triage-batch-adopt).
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

import importlib
import importlib.metadata
import json
import os
import shlex
import shutil
import sys
import tempfile
import time
import uuid
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, NamedTuple
from urllib.parse import urlparse

import typer
import yaml
from pydantic import ValidationError
from rich.markup import escape

from fr import __version__
from fr.acceptance.ci import CI_CONFIG_PATHS
from fr.commands import triage_kanban_cmd
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
from fr.commands.triage_kanban_cmd import _fail, probe_item, try_load
from fr.commands.triage_kanban_cmd import load_runner as kanban_load_runner
from fr.ghclient import MERGE_METHODS, GhClient, UnsupportedForgeOperation
from fr.hostclient import FORGE_ERRORS, client_for_url
from fr.isolation.rename import IsolationError, rename_branch
from fr.labels import FR_IN_PROGRESS
from fr.models import REPO_MODELS_REL, default_models_path, load_models, resolved_config
from fr.services import ServicesError, require_tracker
from fr.services.resolve import resolve_services
from fr.triage.batch import (
    CLOSED_OUT,
    allowed_authors,
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
    distrust,
    foreign_batch_prs,
    label_refs,
    last_dispatch,
    mixed_themes,
    pr_open_queue,
    resolve_launch,
    save_batches,
    save_exports,
    suggest,
    withdrawal_body,
    withdrawn_already,
)
from fr.triage.batch_dispatch import (
    DISPATCHABLE,
    LIVE_STAGES,
    TRIAGE_CONFIG_PATH,
    check_config_fresh,
    conflict_brief,
    dispatch_comment,
    dispatched_already,
    live_reservations,
    render_brief,
)
from fr.triage.batch_drive import (
    ARCHIVE_PREFIXES,
    DEFAULT_MAX_INFLIGHT,
    DEFAULT_WORKSPACE_PREFIX,
    EXPORT_KINDS,
    RUNS_DIR,
    STALE_CLOSEOUT,
    Action,
    IdleSession,
    LivePr,
    Snapshot,
    Summary,
    action_line,
    attributed,
    checks_verdict,
    closeout_brief,
    closeout_due,
    closeout_event,
    closeout_item_id,
    conflict_decision,
    conflict_item_id,
    default_selection,
    drive_pass,
    export_branch,
    export_target,
    export_wave_of,
    find_run,
    finished_waves,
    fresh_conflicts,
    housekeeping_branch,
    idle_session,
    is_archived,
    is_finished,
    settle,
    summary_line,
    train_line,
    unfinished_waves,
    wave_group,
)
from fr.triage.batch_merge import (
    HeadMovedError,
    MergeAttempt,
    MergeConflictError,
    MergeContext,
    MergeStopError,
    choose_method,
    describe,
    merge_ready,
    plan_queue,
    run_queue,
)
from fr.triage.batch_version import read_source, reserve
from fr.triage.check import batch_awaits_live
from fr.triage.claim_sync import (
    ClaimEnv,
    ClaimOp,
    SyncResult,
    execute,
    plan_sync,
    record_releases,
)
from fr.triage.claims import held_line, held_map, held_members
from fr.triage.dedupe import candidates
from fr.triage.drive_lock import DRIVE_LOCK, lock_holder
from fr.triage.drive_lock import lock_text as _lock_text
from fr.triage.errors import TriageError
from fr.triage.gitseam import Checkout, GitError
from fr.triage.merge_stops import MergeStop, clear_stop, record_stop
from fr.triage.model import (
    Batch,
    CancelEvent,
    ClaimsReleasedEvent,
    CloseoutEvent,
    ConflictEvent,
    DispatchEvent,
    Export,
    Facts,
    Judgements,
    Launch,
    PostMergeEvent,
    PullRequest,
    Scope,
    load_judgements,
    load_scope_facts,
    state_dir,
)
from fr.triage.render import plural
from fr.triage.scope_config import load_scope_config, scope_id
from fr.triage.state_sync import check_scope_name, export_state

if TYPE_CHECKING:
    from fr_dispatch.protocols import Runner
    from fr_dispatch.work_item import WorkItem

    from fr.triage.batch import BatchStage

DISPATCH_INSTALL_HINT = (
    "dispatching to a runner requires fr-dispatch — install it "
    "(e.g. `uv tool install --with fr-dispatch fr`) and re-run."
)


def make_client(url: str) -> GhClient:
    """The forge adapter for the repo *url* lives on, on its own instance (§3.J;
    spec 2026-10-06-forge-remainder §4.D). Tests replace this."""
    return client_for_url(url)


def claim_env(target: Path, facts: Facts) -> ClaimEnv:
    """This scope's claim identity, config and forge clients (triage-claims §3.E): the one
    resolver the batch verbs, the driver and the `claim` group share. The scope is the
    one the facts were collected for (every loader checks they match). A broken host id
    or scope config exits 2 naming its file."""
    try:
        me, config = scope_id(facts.scope), load_scope_config(target)
    except TriageError as exc:
        _fail(str(exc))
    return ClaimEnv(
        me=me,
        config=config,
        facts=facts,
        client_for=lambda owner_repo: make_client(
            f"https://{_host_of(facts, owner_repo)}/{owner_repo}"
        ),
    )


def _stalled_line(blocked: Sequence[str], held_by: Sequence[tuple[str, Sequence[str]]]) -> str:
    """Why an idle loop stops: batches held by another scope wait on that scope (R6) and
    are named apart from those that need the operator (R7)."""
    if not held_by:
        return (
            f"stopped: only blocked batches remain ({', '.join(blocked)}); they need the operator"
        )
    held = ", ".join(f"{b} ({', '.join(who)})" for b, who in held_by)
    parts = [f"held by another scope: {held}"]
    if blocked:
        parts.append(f"need the operator: {', '.join(blocked)}")
    return "stopped: only held or blocked batches remain; " + "; ".join(parts)


def _refuse_held(env: ClaimEnv, keys: Iterable[str], what: str) -> None:
    """Exit 2, nothing written, when another scope holds any of *keys* (R5, R6)."""
    found = held_members(keys, held_map(env.facts, env.me))
    if found:
        now = _now()
        _fail(
            f"{what}: another triage scope holds "
            + "; ".join(held_line(k, h, now) for k, h in found)
        )


def _own_claim_batch(facts: Facts, key: str, me: str) -> str | None:
    issue = next((i for i in facts.issues if i.key == key), None)
    own = next((c for c in issue.claims if c.signer == me), None) if issue else None
    return own.batch if own else None


def _settle_claims(env: ClaimEnv, ops: list[ClaimOp], *, yes: bool) -> SyncResult | None:
    """The claim writes a create/edit made owed (R3, R10). Under --yes, written after the
    judgements change; without it, printed with the command that writes them. A failed
    write exits 1 naming the issue; the judgements change stands."""
    if not ops:
        return None
    for op in ops:
        if op.kind == "claim":
            console.print(f"  claim {op.key} for {op.batch}", markup=False)
        else:
            console.print(f"  {op.kind} {op.key} ({op.batch})", markup=False)
    if not yes:
        console.print(
            "claims not written; `fr triage claim sync --yes` writes them (or re-run with --yes)",
            markup=False,
        )
        return None
    try:
        result = execute(env, ops, _now())
    except UnsupportedForgeOperation as exc:
        _fail(str(exc))
    problems = [f"{op.kind} {op.key}: {why}" for op, why in result.failed] + [
        f"{h.key}: held by {h.holder.signer} (batch {h.holder.batch})" for h in result.held
    ]
    if problems:
        _fail(
            "the judgements change stands, but these claim writes did not complete; "
            "`fr triage claim sync --yes` finishes them: " + "; ".join(problems),
            code=1,
        )
    return result


def _claim_ops(batch: Batch, keys: Iterable[str], facts: Facts, me: str) -> list[ClaimOp]:
    """Claim ops for *keys* of *batch*, skipping members facts show already claimed for it."""
    return [
        ClaimOp("claim", k, batch.id) for k in keys if _own_claim_batch(facts, k, me) != batch.id
    ]


def _withdraw_unowed(env: ClaimEnv, batch: Batch, posted: list[str]) -> None:
    """A wave-less batch owes no claim until it is dispatched (R3): when its dispatch did
    not happen, withdraw the markers this call posted. Best effort: a failure here leaves
    them to `claim sync`, which releases own claims no batch owes."""
    if batch.wave is not None or not posted:
        return
    try:
        execute(env, [ClaimOp("release", k, batch.id) for k in posted], _now())
    except UnsupportedForgeOperation:
        pass


def _claim_for_dispatch(env: ClaimEnv, batch: Batch) -> list[str]:
    """Claim every member for *batch* before its launch (R3, R4); the keys whose marker
    this call posted. A member held elsewhere refuses the batch (exit 2) and a failed
    write exits 1, both with nothing launched.

    Every member goes through the forge, including those facts show already claimed for
    *batch* (p1-r4): facts are as old as the last collect, and a claim taken over since
    must stop the launch. `claim` re-reads, reports Held, or rewrites the own marker in
    place (a fresh heartbeat)."""
    ops = [ClaimOp("claim", k, batch.id) for k in batch.ids]
    if not ops:
        return []
    try:
        result = execute(env, ops, _now())
    except UnsupportedForgeOperation as exc:
        _fail(str(exc))
    posted = [op.key for op, done in result.done if done.action == "posted"]
    if result.held or result.failed:
        _withdraw_unowed(env, batch, posted)
    if result.held:
        now = _now()
        _fail(
            f"batch {batch.id!r} cannot be dispatched: another triage scope holds "
            + "; ".join(held_line(h.key, h.holder, now) for h in result.held)
            + ". Nothing was launched."
        )
    if result.failed:
        _fail(
            f"batch {batch.id!r}: these claims were not written, so nothing was launched; "
            "re-run to complete: " + "; ".join(f"{op.key}: {why}" for op, why in result.failed),
            code=1,
        )
    return posted


def make_checkout(path: Path | None) -> Checkout:
    """The local clone the batch verbs work in (§3.I). Tests replace this."""
    return Checkout.at(path)


def load_runner(name: str) -> Runner:
    """Build runner *name* through the soft point in `triage_kanban_cmd` (§3.C step 1),
    with this module's install hint. Tests replace this."""
    return kanban_load_runner(name, DISPATCH_INSTALL_HINT)


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


def _with_event(judgements: Judgements, batch: Batch, event: DispatchEvent) -> list[Batch]:
    """The batches *judgements* will hold once *event* is appended to *batch*: what
    `dispatch`, `dispatch --repair` (recording a missing event) and `adopt` write."""
    return _replace(judgements.batches, batch.model_copy(update={"events": [*batch.events, event]}))


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


ClaimYesOpt = Annotated[
    bool,
    typer.Option(
        "--yes",
        help="Also write the claims this change makes owed (the judgements write happens "
        "either way).",
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
    closeout = closeout_state(batch)
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
    scope = _scope(repo, org)
    path = state_dir(scope, dir_override) / "judgements.yaml"
    try:
        batches = load_judgements(path).batches if path.exists() else []
    except TriageError as exc:
        _fail(str(exc))
    if not batches:
        console.print("no batches")
        return
    facts_path = path.with_name("facts.json")
    try:
        facts = load_scope_facts(facts_path, scope) if facts_path.exists() else None
    except TriageError as exc:
        _fail(str(exc))
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
    yes: ClaimYesOpt = False,
    repo: RepoOpt = None,
    org: OrgOpt = None,
    dir_override: DirOpt = None,
) -> None:
    """Add a proposed batch of judged issues. With --wave, its claims are owed (R3)."""
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
    env = claim_env(target, facts)
    _refuse_held(env, new.ids, f"batch {new.id!r} cannot be created")
    _write(target, [*judgements.batches, new], facts, read=judgements.batches)
    console.print(f"created batch {new.id} ({plural(len(new.ids), 'issue')})", markup=False)
    _warn_mixed_themes(new, judgements)
    if new.wave is not None:  # a wave makes claims owed from now (R3)
        _settle_claims(env, _claim_ops(new, new.ids, facts, env.me), yes=yes)


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
    yes: ClaimYesOpt = False,
    repo: RepoOpt = None,
    org: OrgOpt = None,
    dir_override: DirOpt = None,
) -> None:
    """Change a proposed batch; past `proposed`, only --order (and, until it merges,
    --wave and --after) may change. Claims follow the change (R3, R5, R10)."""
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
    env = claim_env(target, facts)
    added = [k for k in new.ids if k not in batch.ids]
    checked = new.ids if wave is not None else added
    _refuse_held(env, checked, f"batch {new.id!r} cannot take these members")
    _write(target, _replace(judgements.batches, new), facts, read=judgements.batches)
    console.print(f"edited batch {new.id}", markup=False)
    _warn_mixed_themes(new, judgements)
    owed_before = batch.wave is not None or stage != "proposed"
    owed_after = new.wave is not None or stage != "proposed"
    dropped = [k for k in batch.ids if k not in new.ids]
    ops = [ClaimOp("release", k, batch.id) for k in dropped] if owed_before else []
    if owed_before and not owed_after:  # --no-wave on a proposed batch
        ops += [ClaimOp("release", k, batch.id) for k in new.ids]
    elif owed_after:
        ops += _claim_ops(new, new.ids, facts, env.me)
    if set_wave or add_issue or remove_issue:
        _settle_claims(env, ops, yes=yes)


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
    env = claim_env(target, facts)
    # R6: a member another scope holds keeps its fr:in-progress label and comments;
    # they are its holder's. This scope's own claims are released (R10).
    held = {k for k, _ in held_members(batch.ids, held_map(facts, env.me))}
    owes = batch.wave is not None or any(e.kind == "dispatch" for e in batch.events)
    claimed = any(_own_claim_batch(facts, k, env.me) for k in batch.ids)
    releases = owes or claimed
    withdraws = [k for k in batch.ids if k not in held] if stage != "proposed" else []
    # a proposed batch reached the forge only when its claims were written; a wave owes
    # claims from the moment it is set, so ones written since the last collect may
    # exist whatever facts say (p1-r8)
    touches_forge = stage != "proposed" or claimed or batch.wave is not None
    if touches_forge:
        # gh#803: withdrawing writes labels and comments to the tracker, so it
        # is gated as dispatch is — a proposed batch writes nothing and needs
        # no clone.
        _tracking_gate(checkout_path, owner_repo, yes=yes)
    console.print(f"cancel batch {batch.id} ({stage})", markup=False)
    for key in withdraws:
        console.print(
            f"  {key}: remove {FR_IN_PROGRESS.name}, post the withdrawal comment",
            markup=False,
        )
    for key in sorted(held):
        console.print(
            f"  {key}: held by another triage scope; its label and comments are left to it",
            markup=False,
        )
    if releases and touches_forge:
        for key in batch.ids:
            console.print(f"  {key}: release this scope's claim", markup=False)
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
        for key in withdraws:
            number = int(key.rpartition("#")[2])
            try:
                posted[key] = withdrawn_already(
                    client.list_issue_comments(owner_repo, number), item
                )
            except UnsupportedForgeOperation as exc:
                _fail(str(exc))
            except FORGE_ERRORS as exc:  # a forge failure: report the member, keep going
                failed.append(f"{key}: {exc}")
        for key in withdraws:
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
        released: list[str] = []
        if releases and not failed:
            try:
                result = execute(env, [ClaimOp("release", k, batch.id) for k in batch.ids], _now())
            except UnsupportedForgeOperation as exc:
                _fail(str(exc))
            failed += [f"{op.key}: {why}" for op, why in result.failed]
            # only real releases: a member with no claim of this scope's is left to the
            # next `claim sync`, which records it, so a claim-free cancel reads as before
            released = [op.key for op, done in result.done if done.action == "released"]
        if failed:
            _fail(
                "these members were not fully withdrawn, so no cancel event was written; "
                "re-run to complete: " + "; ".join(failed),
                code=1,
            )
    else:
        released = []
    event = CancelEvent(kind="cancel", at=_now_after(batch), reason=reason)
    events: list[Any] = [*batch.events, event]
    if released:
        events.append(ClaimsReleasedEvent(kind="claims_released", at=event.at, keys=released))
    cancelled = batch.model_copy(update={"events": events})
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
    checkout: Checkout,
    facts: Facts,
    judgements: Judgements,
    batch: Batch,
    owner_repo: str,
    *,
    lenient: bool = False,
    read_errors: bool = False,
) -> str | None:
    """Fetch, hold the config-freshness rule, and reserve a version (§3.D, §3.I).

    *read_errors*: the driver's boundary (gh#1025). A failed fetch, or main's config
    moving under the pass, raises `ForgeReadError` as the merge path's does, so the
    loop skips the pass; `batch dispatch` keeps its exit code."""
    config = facts.config_for(owner_repo)
    try:
        default = _fresh_config(checkout, facts, owner_repo, lenient=lenient)
    except TriageError as exc:
        if read_errors:
            raise ForgeReadError(str(exc), code=2) from exc
        _fail(str(exc))
    try:
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


def _fresh_config(
    checkout: Checkout, facts: Facts, owner_repo: str, *, lenient: bool = False
) -> str:
    """Fetch, then hold the §3.I rule: the collected `.fr/triage.yaml` must be the
    one on `origin/<default>` now. Returns that ref. *lenient*: the wave driver's
    read, which ignores a top-level key this `fr` does not know (gh#998)."""
    checkout.fetch()
    default = f"origin/{checkout.default_branch()}"
    check_config_fresh(
        facts.config.get(owner_repo),
        checkout.show(default, TRIAGE_CONFIG_PATH),
        lenient=lenient,
    )
    return default


def _work_item(
    owner_repo: str,
    batch: Batch,
    launch: Launch,
    brief: str,
    reserved: str | None,
    cwd: Path,
    group: str | None = None,
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
    if group:
        payload["group"] = group  # the runner group (herdr workspace); the driver's alone
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
    after = _with_event(judgements, batch, event)
    _write(target, after, facts, read=judgements.batches)
    _report_forge_writes(_forge_writes(client, owner_repo, _find(after, batch.id), probe.id), batch)
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
    try:
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
    except RunnerDispatchError as exc:
        _fail(str(exc), code=1)


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
    group: str | None = None,
    lenient_config: bool = False,
    read_errors: bool = False,
) -> None:
    """The body of `batch dispatch`, callable: one batch, one runner, one dispatch.

    `batch dispatch` and the wave driver share it, so a driver dispatch runs the same
    preflight, version reservation, brief, event write and forge labels. A refusal is
    `typer.Exit` with the verb's own exit code, exactly as at the command line; a
    runner that fails to dispatch raises `RunnerDispatchError`, which each caller
    handles its own way (gh#931).
    *lenient_config* is the driver's `.fr/triage.yaml` read (gh#998); *read_errors*
    its failed-fetch boundary, a `ForgeReadError` (gh#1025).
    """
    owner_repo = batch_repo(batch, facts)
    if owner_repo is None:
        _fail(f"batch {batch.id!r}: its repo {batch.repo_name!r} is not in this scope's facts")
    _tracking_gate(checkout_path, owner_repo, yes=yes)  # before any forge call
    env = claim_env(target, facts)
    _refuse_held(env, batch.ids, f"batch {batch.id!r} cannot be dispatched")  # R6
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
    reserved = _reservation(  # step 2
        checkout,
        facts,
        judgements,
        batch,
        owner_repo,
        lenient=lenient_config,
        read_errors=read_errors,
    )
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
    item = _work_item(owner_repo, batch, launch, brief, reserved, checkout.path, group)  # step 4
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
    except TriageError as exc:  # a forge read: the driver's boundary (gh#1025, review)
        if read_errors:
            raise ForgeReadError(str(exc), code=2) from exc
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
        return _with_event(judgements, batch, ev)

    _write(target, _after(event), facts, read=judgements.batches, dry_run=True)
    if not runner.can_dispatch(item):
        _fail(f"runner `{runner_name}` does not take run-unit work")
    refusal = runner.preflight([item])
    if refusal:
        _fail(f"runner `{runner_name}` refused: {refusal}")
    if item.id in runner.existing_dispatches([item]):
        _fail(f"runner `{runner_name}` already holds {item.id} live; nothing written")
    _write(target, _after(event), facts, read=judgements.batches, dry_run=True)
    # R3: the claims, R4's re-read included, before the launch, which cannot be undone,
    # and before any other forge write. A member another scope holds refuses the batch.
    posted = _claim_for_dispatch(env, batch)
    try:
        launched = runner.dispatch(item)
    except Exception as exc:  # the runner's own failure: nothing else is written
        _withdraw_unowed(env, batch, posted)
        raise RunnerDispatchError(
            f"runner `{runner_name}` failed to dispatch {item.id}: {exc}"
        ) from exc
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


# --------------------------------------------------------------- adopt (2026-10-06)

ADOPT_LIST_RUNNER = "herdr"
"""The runner `adopt --list` reads when `--to` names none: the one that adopts today."""

_ADOPTER_METHODS = ("describe", "list_sessions", "adopt")


def _adopter(runner: object) -> bool:
    """Whether *runner* is a `SessionAdopter` (spec 2026-10-06-triage-batch-adopt §E),
    read off its methods: this module imports `fr_dispatch` only inside functions."""
    return all(callable(getattr(runner, m, None)) for m in _ADOPTER_METHODS)


def supersede_comment(new_pr: int, batch: Batch) -> str:
    """The comment on a superseded PR (§C step 2)."""
    return f"Superseded by #{new_pr} — this branch was adopted as batch {batch.id}"


def adopt_message(
    batch: Batch, item_id: str, old: str, new: str, pr: str | None, reserved: str | None
) -> str:
    """The one message an adopted session's agent gets (R6)."""
    lines = [
        f"fr triage batch adopt: this session is now batch {batch.id} ({item_id}), "
        "driven by `fr triage batch drive`.",
        f"Your branch {old} was renamed to {new}; push to it from now on with "
        f"`git push origin {new}` (its upstream is set). Your push target changed: "
        f"never push {old} again.",
    ]
    if old == new:
        lines[1] = f"Your branch is {new}; keep pushing to it."
    if pr:
        lines.append(f"The PR is now {pr}; the earlier one was closed as superseded.")
    if reserved:
        lines.append(f"Reserved version for this batch: {reserved}.")
    return "\n".join(lines)


def _open_prs(client: GhClient, owner_repo: str, head: str) -> list[dict[str, Any]]:
    return [p for p in client.list_prs_by_head(owner_repo, head) if p.get("state") == "OPEN"]


def _untrusted(record: Mapping[str, Any], allowed: frozenset[str]) -> str | None:
    """`distrust` over a `list_prs_by_head` record: why the PR is not the repo's own
    by an allowed author, or None when it is (gh#936)."""
    author = record.get("author")
    login = author.get("login") if isinstance(author, dict) else None
    cross = record.get("isCrossRepository")
    return distrust(
        str(login) if login else None, cross if isinstance(cross, bool) else None, allowed
    )


def _pr_time(record: Mapping[str, Any] | None) -> datetime | None:
    stamp = record.get("createdAt") if record else None
    try:
        parsed = datetime.fromisoformat(str(stamp)) if stamp else None
    except ValueError:
        return None
    return parsed if parsed is not None and parsed.tzinfo is not None else None


def adopt_batch(
    target: Path,
    facts: Facts,
    judgements: Judgements,
    batch: Batch,
    *,
    tab: str,
    branch: str,
    to: str | None = None,
    checkout_path: Path | None = None,
    yes: bool = False,
) -> None:
    """The body of `batch adopt` (spec 2026-10-06-triage-batch-adopt §A): every read
    and refusal first, then the plan, then — with *yes* — each step not yet done."""
    # 1. The batch, its stage, and whether this is a re-run of an adoption (R2, R10).
    owner_repo = batch_repo(batch, facts)
    if owner_repo is None:
        _fail(f"batch {batch.id!r}: its repo {batch.repo_name!r} is not in this scope's facts")
    new = batch_branch(batch)
    old = branch
    last = batch.events[-1] if batch.events else None
    recorded = isinstance(last, DispatchEvent) and last.handle == tab and last.branch == new
    if not recorded:
        stage = derive_batch_stage(batch, facts)
        if stage not in DISPATCHABLE:
            _fail(
                f"batch {batch.id!r} is {stage}; adopt takes a batch `batch dispatch` would "
                f"start ({', '.join(sorted(DISPATCHABLE))})"
            )
    _tracking_gate(checkout_path, owner_repo, yes=yes)  # before any forge call
    client = make_client(f"https://{_host_of(facts, owner_repo)}/{owner_repo}")

    # 2. The runner: it must adopt sessions.
    try:
        resolved = resolve_launch(
            _with_runner(batch, to),
            facts.config_for(owner_repo),
            orchestrator=_orchestrator(checkout_path),
        )
    except TriageError as exc:
        _fail(str(exc))
    runner_name = str(resolved.launch.runner)
    runner: Any = load_runner(runner_name)
    if not _adopter(runner):
        _fail(f"runner `{runner_name}` cannot adopt sessions (it is no SessionAdopter)")
    probe = _probe(owner_repo, batch, resolved.launch)
    refusal = runner.preflight([probe])
    if refusal:
        _fail(f"runner `{runner_name}` refused: {refusal}")

    # 3. The session (R9's tab and agent refusals).
    session = runner.describe(tab)
    if session is None:
        _fail(f"runner `{runner_name}` has no tab {tab}; `fr triage batch adopt --list` lists them")
    if session.label != probe.id and "/run/batch-" in session.label:
        _fail(f"tab {tab} is labelled {session.label}: it is another batch's session")
    if session.agent is None:
        _fail(f"tab {tab} does not hold exactly one agent (it holds none, or several)")
    if session.status == "working":
        _fail(
            f"the agent in tab {tab} is working: renaming its branch under it races its next "
            "push. Wait until it is idle, then adopt"
        )

    # 4. The git side and the PRs (R9's branch and worktree refusals).
    checkout = _open_checkout(checkout_path, owner_repo)
    try:
        default = checkout.default_branch()
        if old == default:
            _fail(f"--branch {old} is {owner_repo}'s default branch: adopt never renames it")
        if new == default:
            _fail(f"batch branch {new} is {owner_repo}'s default branch: refusing")
        worktree = (checkout.worktree_of(old) if old != new else None) or checkout.worktree_of(new)
        if worktree is None:
            _fail(f"no worktree of {checkout.path} has {old} (or {new}) checked out")
        if Path(worktree).resolve() == Path(checkout.main_worktree()).resolve():
            _fail(
                f"{old} is checked out in the main worktree {worktree}: adopt renames only a "
                "linked worktree's branch"
            )
        # Planned even when *old* is *new*: R9's worktree refusals hold either way.
        renames = rename_branch(checkout.path, worktree, old, new, dry_run=True)
        pending_local = old != new and checkout.has_branch(old)
        remote_old = old != new and checkout.remote_branch_exists(old)
        remote_new = checkout.remote_branch_exists(new)
    except IsolationError as exc:
        _fail(str(exc))
    except TriageError as exc:
        _fail(str(exc))
    if remote_new and pending_local:
        _fail(f"branch {new} is already on origin and is not this adoption's: refusing")
    allowed = allowed_authors(owner_repo, facts)
    try:
        old_open = _open_prs(client, owner_repo, old) if old != new else []
        new_open = _open_prs(client, owner_repo, new)
    except UnsupportedForgeOperation as exc:
        _fail(str(exc))
    except FORGE_ERRORS as exc:
        _fail(f"cannot read {owner_repo}'s PRs: {exc}")
    # A head NAME is chosen by whoever opens the PR, a fork included (gh#936): an
    # untrusted PR is never copied, commented on or closed, nor taken as ours.
    for head, open_prs, what in ((old, old_open, "adopt never supersedes it"),
                                 (new, new_open, "it is not this adoption's")):  # fmt: skip
        for p in open_prs:
            if (why := _untrusted(p, allowed)) is not None:
                _fail(f"open PR #{p['number']} on {head} is not trusted ({why}): {what}; refusing")
    old_pr = max(old_open, key=lambda p: int(p["number"]), default=None)
    new_pr = max(new_open, key=lambda p: int(p["number"]), default=None)
    try:
        old_view = client.pr_view(owner_repo, int(old_pr["number"])) if old_pr else None
        commented = bool(
            old_pr
            and new_pr
            and any(
                str(c.get("author") or "").lower() in allowed
                and str(c.get("body", "")).startswith(f"Superseded by #{new_pr['number']}")
                for c in client.list_issue_comments(owner_repo, int(old_pr["number"]))
            )
        )
    except UnsupportedForgeOperation as exc:
        _fail(str(exc))
    except FORGE_ERRORS as exc:
        _fail(f"cannot read {owner_repo}'s PRs: {exc}")
    publish = not remote_new and (remote_old or old_pr is not None)

    # 5. The version (R11), the event time (§D) and a dry run of the write.
    if recorded and isinstance(last, DispatchEvent):
        reserved = last.reserved_version
    else:
        reserved = _reservation(checkout, facts, judgements, batch, owner_repo)
    # Whole seconds, as the forge's createdAt is: a PR opened in the same second as
    # the event is still of it (`of_dispatch`, created >= at). Never before the last event.
    floor = batch.events[-1].at if batch.events else None
    at = _now_after(batch).replace(microsecond=0)
    at = max(at, floor) if floor is not None else at
    opened = _pr_time(new_pr)
    if opened is not None and opened < at:  # a re-run: that PR was opened by this adoption
        at = max(opened, floor) if floor is not None else opened
    event = DispatchEvent(
        kind="dispatch", at=at, runner=runner_name, handle=tab, branch=new,
        reserved_version=reserved,
    )  # fmt: skip
    after = _with_event(judgements, batch, event)
    if not recorded:
        _write(target, after, facts, read=judgements.batches, dry_run=True)

    # 6. The plan (R8).
    def say(line: str) -> None:
        console.print(line, markup=False, soft_wrap=True, highlight=False)

    say(f"adopt tab {tab} as batch {batch.id} ({probe.id})")
    say(f"  session: {session.label!r} in {session.group or '-'}, agent {session.agent} "
        f"({session.status}); runner {runner_name}")  # fmt: skip
    say(f"  branch: {old} -> {new} in {worktree}")
    for step in renames:
        say(f"    {step}")
    if old != new and not renames:
        say("    already renamed")
    if publish:
        say(f"  remote: publish {new} (git push -u origin {new})")
    elif not remote_new:
        say(f"  remote: {old} was never pushed; nothing to publish")
    if old_pr is not None and old_view is not None:
        kind = "draft PR" if old_view.get("draft") else "PR"
        if new_pr is None:
            say(f"  forge: supersede PR #{old_pr['number']} with a new {kind} from {new} into "
                f"{old_view.get('base_ref')} ({old_view.get('title')!r}), then comment and close "
                f"#{old_pr['number']}")  # fmt: skip
        else:
            say(f"  forge: supersede PR #{old_pr['number']} by the open #{new_pr['number']}")
    if remote_old:
        say(f"  forge: delete remote branch {old}")
    say(f"  runner: rename tab {tab} to {probe.id}, and its agent")
    if recorded:
        say("  record: the dispatch event is recorded already")
    else:
        say(f"  record: dispatch event (runner {runner_name}, handle {tab}, branch {new}, "
            f"reserved version {reserved or '(none)'})")  # fmt: skip
    say(f"  forge: add {FR_IN_PROGRESS.name} and the marker comment on every member")
    if callable(getattr(runner, "message", None)):
        say("  runner: message the agent its new branch, PR and version")
    if not yes:
        say("nothing written; re-run with --yes to act")
        return

    # 7. Each step not done yet, in §A.7's order (R10).
    state: dict[str, Any] = {"pr": new_pr, "event": event, "after": after}
    done: list[str] = []

    def _not_default(*names: str) -> None:  # refused above; held again at each write
        for name in names:
            if name == default:
                raise RuntimeError(f"{name} is the default branch: refusing to touch it")

    def _pr_ref() -> str | None:
        pr = state["pr"]
        return f"#{pr['number']} ({pr['url']})" if pr else None

    def _create() -> None:
        assert old_view is not None
        made = client.create_pr(
            owner_repo, head=new, base=str(old_view.get("base_ref") or ""),
            title=str(old_view.get("title") or ""), body=str(old_view.get("body") or ""),
            draft=bool(old_view.get("draft")),
        )  # fmt: skip
        state["pr"] = made
        # The forge's clock decides `of_dispatch`: an event later than the PR it
        # opened would disown it, so the event moves down to its createdAt (p1-r2).
        created = next((p for p in _open_prs(client, owner_repo, new)
                        if int(p["number"]) == int(made["number"])), None)  # fmt: skip
        opened = _pr_time(created)
        if opened is not None and opened < state["event"].at:
            moved = state["event"].model_copy(
                update={"at": max(opened, floor) if floor is not None else opened}
            )
            state["event"], state["after"] = moved, _with_event(judgements, batch, moved)

    def _rename() -> None:
        _not_default(old, new)
        rename_branch(checkout.path, worktree, old, new)

    def _delete_old() -> None:
        _not_default(old)
        client.delete_branch(owner_repo, old)

    steps: list[tuple[str, Callable[[], object]]] = []
    if renames:
        steps.append((f"rename {old} to {new}", _rename))
    if publish:
        steps.append((f"publish {new}", lambda: checkout.publish_branch(new)))
    if old_pr is not None:
        number = int(old_pr["number"])
        if new_pr is None:
            steps.append((f"open the PR superseding #{number}", _create))

        def _comment() -> None:
            body = supersede_comment(int(state["pr"]["number"]), batch)
            client.comment_issue(owner_repo, number, body)

        if not commented:
            steps.append((f"comment on #{number}", _comment))
        steps.append((f"close #{number}", lambda: client.close_pr(owner_repo, number)))
    if remote_old:
        steps.append((f"delete remote branch {old}", _delete_old))
    steps.append((f"adopt tab {tab}", lambda: runner.adopt(probe, tab)))
    if not recorded:
        steps.append(("record the dispatch event",
                      lambda: _save(target, state["after"], facts,
                                    read=judgements.batches)))  # fmt: skip

    def _marks() -> None:
        failed = _forge_writes(client, owner_repo, _find(state["after"], batch.id), probe.id)
        if failed:
            raise RuntimeError("; ".join(failed))

    steps.append(("mark every member on the forge", _marks))
    if callable(getattr(runner, "message", None)):
        steps.append(("message the agent", lambda: runner.message(
            probe, adopt_message(batch, probe.id, old, new, _pr_ref(), reserved))))  # fmt: skip
    for i, (what, act) in enumerate(steps):
        try:
            act()
        except Exception as exc:  # each step's own failure: report it, the rest remain
            if isinstance(exc, typer.Exit) and exc.exit_code == 0:
                raise
            # A refusal inside a step (`_fail`) printed its words already; exit 2 is
            # for refusals before any write, so it too ends in this report (p1-r8).
            detail = "refused, as printed above" if isinstance(exc, typer.Exit) else exc
            remaining = [w for w, _ in steps[i:]]
            _fail(
                f"adopt stopped at: {what}: {detail}. Done: {'; '.join(done) or 'nothing'}. "
                f"Still remain: {'; '.join(remaining)}. Re-run the same command to finish: "
                f"`fr triage batch adopt {batch.id} --tab {tab} --branch {old} --yes`",
                code=1,
            )
        done.append(what)
    say(f"adopted tab {tab} as batch {batch.id} on {new}")


def _list_sessions(to: str | None) -> None:
    """`adopt --list` (R12): every session, with the issue refs in its label."""
    name = to or ADOPT_LIST_RUNNER
    runner: Any = load_runner(name)
    if not _adopter(runner):
        _fail(f"runner `{name}` cannot adopt sessions (it is no SessionAdopter)")
    try:
        sessions = runner.list_sessions()
    except Exception as exc:  # the runner's own failure
        _fail(f"runner `{name}` could not list its sessions: {exc}", code=1)
    for s in sessions:
        refs = ", ".join(label_refs(s.label)) or "-"
        console.print(
            f"{s.tab}\t{s.group or '-'}\t{s.status}\t{refs}\t{s.label}",
            markup=False,
            soft_wrap=True,
            highlight=False,
        )


@batch_app.command("adopt")
def batch_adopt_command(
    batch_id: Annotated[
        str | None, typer.Argument(help="The batch to adopt the session as.")
    ] = None,
    tab: Annotated[
        str | None, typer.Option("--tab", help="The runner tab holding the session.")
    ] = None,
    branch: Annotated[
        str | None, typer.Option("--branch", help="The branch the session works on now.")
    ] = None,
    to: Annotated[
        str | None, typer.Option("--to", help="Runner; default: the batch's launch.runner.")
    ] = None,
    checkout_path: CheckoutOpt = None,
    list_sessions: Annotated[
        bool, typer.Option("--list", help="List every session and its issue refs; write nothing.")
    ] = False,
    yes: Annotated[bool, typer.Option("--yes", help="Act; without it, print the plan.")] = False,
    repo: RepoOpt = None,
    org: OrgOpt = None,
    dir_override: DirOpt = None,
) -> None:
    """Put a running session under the wave driver as an existing batch; launches nothing.

    Renames the session's branch to the batch branch (supersede an open PR with one
    from it), labels its tab and agent as the batch's, and records a dispatch. Not the
    driver's `adopt` action, which records a close-out started by hand.
    """
    if list_sessions:
        _list_sessions(to)
        return
    if batch_id is None or tab is None or branch is None:
        _fail("give a batch, --tab and --branch (or --list)")
    target, facts, judgements = _load_state(_scope(repo, org), dir_override)
    batch = _find(judgements.batches, batch_id)
    adopt_batch(
        target, facts, judgements, batch, tab=tab, branch=branch, to=to,
        checkout_path=checkout_path, yes=yes,
    )  # fmt: skip


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

    Blocks in the foreground while the checks run (R4: the required ones, else
    every check; a head with none yet waits, unless the repo declares `ci none`);
    Ctrl-C and re-run resumes at the first unmerged batch.
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
    env = claim_env(target, facts)
    for e in queue:  # R6: a batch another scope holds a member of is never merged here
        _refuse_held(env, e.batch.ids, f"batch {e.batch.id!r} cannot be merged")
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
        chosen = choose_method(
            method,
            client.repo_merge_methods(owner_repo),
            configured=facts.config_for(owner_repo).merge_method,
        )
        ci_none = ci_none_at(checkout)  # fetched by `_fresh_config`
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
        ci_none=ci_none,
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

DEFAULT_INTERVAL = 120
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


class RunnerDispatchError(Exception):
    """A runner's `dispatch` raised, so nothing started and nothing was written
    (gh#931). `batch dispatch` exits 1 with it; the driver reports it once per cause
    and dispatches again on a later pass, as it does a refused merge (rg-4)."""


class ForgeReadError(Exception):
    """A read a drive pass depends on failed or timed out (gh#910): the forge's, the
    clone's fetch, or `.fr/triage.yaml` on the default branch (gh#921, gh#998). Loop
    mode skips the rest of the pass and reads again after `--interval`; `--once` and
    plan mode exit with *code*, as before."""

    def __init__(self, message: str, *, code: int) -> None:
        super().__init__(message)
        self.code = code


def recollect(scope: Scope, target: Path) -> Mapping[str, tuple[str, ...]]:
    """Re-collect facts.json through the `Forge` seam, as `fr triage collect` does:
    every stage is derived from facts, so each pass starts here (wave-driver §B).
    Unlike `fr triage collect` it carries known-closed facts over from the
    previous pass instead of viewing every settled judged issue again (gh#911),
    and says what the pass cost. Config is read leniently (gh#998): returns the
    top-level `.fr/triage.yaml` keys dropped, per repo. A forge that fails to answer,
    or any other refusal (a config broken on the default branch, a judgements file
    mid-edit), raises `ForgeReadError`: the loop waits for it to be fixed."""
    try:
        _, _, stats = collect_into(scope, target, carry=True, lenient=True)
    except TriageError as exc:  # ForgeError included
        raise ForgeReadError(str(exc), code=2) from exc
    _say(f"collect: {plural(stats.viewed, 'issue')} viewed, {stats.carried} carried over")
    return stats.ignored


def ci_none_at(checkout: Checkout) -> bool:
    """Whether the clone's `origin/<default>`, as last fetched, declares `ci none` (R4)."""
    ref = f"origin/{checkout.default_branch()}"
    with tempfile.TemporaryDirectory(prefix="fr-ci-") as tmp:
        checkout.snapshot_paths(ref, SERVICE_PATHS, Path(tmp))
        return ci_is_none(Path(tmp))


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


def _installed_version() -> str | None:
    """The `fr` version installed now, read afresh from its metadata; None when it
    cannot be read. A `post_merge` that reinstalls `fr` changes it under the running
    driver, whose own code stays what it imported (gh#998)."""
    importlib.invalidate_caches()
    try:
        return importlib.metadata.version("fr")
    except importlib.metadata.PackageNotFoundError:
        return None


def _exec(argv: list[str]) -> None:
    """Replace this process with *argv* (gh#998: the driver restarts on the `fr`
    `post_merge` installed); tests replace it."""
    sys.stdout.flush()
    sys.stderr.flush()
    os.execv(argv[0], argv)


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
        holder = lock_holder(path, held)  # the one rule `--watch` reads too
        if holder is not None:
            _fail(
                f"another driver holds {path} ({holder}); stop it first, or wait for it to finish"
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
    selected = default_selection(batches)
    return [b for b in batches if b.id in selected]


def _parse_at(stamp: str | None) -> datetime | None:
    if not stamp:
        return None
    try:
        parsed = datetime.fromisoformat(stamp)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _settled(batch: Batch) -> bool:
    """Whether *batch* is finished on its events alone, with no forge read: cancelled,
    or its archive PR merged by a driver."""
    event = closeout_event(batch)
    cancelled = bool(batch.events) and isinstance(batch.events[-1], CancelEvent)
    return cancelled or (event is not None and event.archived is not None)


def _closeout_head(batch: Batch) -> str:
    """`chore/closeout-<batch branch with / as ->`: the close-out head only *batch*
    can produce, from the branch it was last dispatched on."""
    last = last_dispatch(batch)
    return housekeeping_branch(last.branch if last else batch_branch(batch), None, None)


def _live_head_prs(client: GhClient, repo: str, head: str, allowed: frozenset[str]) -> list[LivePr]:
    """The PRs with head *head*, as the archive step reads them (merged ones too),
    each `trusted` only from *repo* itself by an *allowed* author (gh#936)."""
    out: list[LivePr] = []
    for rec in client.list_prs_by_head(repo, head):
        trusted = _untrusted(rec, allowed) is None
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
                trusted=trusted,
            )
        )
    return out


class _MergeOutcome(NamedTuple):
    """What `_Driver._merge_batch` did: the outcome line, whether it acted, the
    in-flight count, and whether it stops the repo's train (`_stops_train`)."""

    line: str
    acted: bool
    in_flight: int
    stops: bool


def _stops_train(outcome: MergeAttempt | MergeStopError | GitError) -> bool:
    """Whether a merge's outcome stops its repo's train (spec §B): the head did not
    merge and is waiting on something (its new CI, its checks, a moved head); a
    refusal, a failed git write, a failing or draft PR, a PR no longer open or one
    already merged is stepped over or gone, and the train goes on."""
    if isinstance(outcome, (MergeStopError, GitError)):
        return isinstance(outcome, HeadMovedError)
    return outcome.outcome in ("updated", "pending")


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
        workspace_prefix: str = DEFAULT_WORKSPACE_PREFIX,
        keep_sessions: bool = False,
        scope_args: list[str] | None = None,
    ) -> None:
        self.scope, self.target, self.named = scope, target, named
        self.scope_args = scope_args or []
        self.board_failures: set[str] = set()  # board write failures, since the last good one
        self.workspace_prefix = workspace_prefix
        self.keep_sessions = keep_sessions
        self.checkout_paths = checkouts
        self.max_inflight, self.yes = max_inflight, yes
        self.warned: set[str] = set()
        self.reported: set[str] = set()  # merge and dispatch refusals already printed in full
        self.read_failures: set[str] = set()  # forge read failures, since the last good pass
        self.failed_write = False  # a forge write or a dispatch failed this pass (--once exits 1)
        self._first_seen: dict[str, datetime] = {}  # merged with no merge time known
        self._ci: dict[str, bool] = {}  # per pass: repo -> origin/<default> says ci none
        self._unlanded: set[str] = set()  # per pass: planned merges that did not land
        self._held = 0  # per pass: planned dispatches that did not start
        self._stopped: dict[str, str] = {}  # per pass: repo -> batch that stopped its train
        # per pass: repo -> the conflicts its train met, (batch, refused paths) in order
        self._conflicts: dict[str, list[tuple[str, tuple[str, ...]]]] = {}
        self._queued = 0  # per pass: candidates not attempted behind a stopped train
        self._clients: dict[str, GhClient] = {}
        self._checkouts: dict[str, Checkout] = {}
        self._runners: dict[str, Runner] = {}
        self._unloadable: set[str] = set()  # runners that failed to load, reported once
        self._probes: dict[str, tuple[Runner, Any]] = {}  # per pass: live item id -> its runner
        # per pass: runner name -> the close-out probe, for every runner whose close-out
        # followed a successful `post_merge` in a repo that opted in (driver-sessions sr-7)
        self._restart: dict[str, Any] = {}
        self._merge: dict[str, MergeContext] = {}
        # The waves this process's previous pass found unfinished; None before its first
        # pass, so a wave already finished at start is never reported (R10).
        self._unfinished: frozenset[str] | None = None
        self._observed_last = False  # the one extra pass `observation_owed` grants
        self._export_refusals = 0  # per pass: owed exports refused before any write
        self._export_failures = 0  # per pass: export writes that failed, retried (gh#1025)
        # per pass: repo -> why collect skipped it, and the unfinished batches of those
        # repos, left out of the pass because their PRs and config were not read (gh#921)
        self._unread: dict[str, str] = {}
        self._left_out: dict[str, str] = {}
        # per pass, plan mode only: repo -> why its clone could not be read, so the
        # checks that needed it were skipped, never guessed (gh#991)
        self._clone_unread: dict[str, str] = {}
        self.restart_to: str | None = None  # a newer fr post_merge installed (gh#998)
        # per pass: the claim env (this scope's id and config), the batches a claim write
        # found held (the pass stops acting on them), and the claim writes done so far
        self._claims: ClaimEnv | None = None
        self._held_now: dict[str, str] = {}
        self.publish_failures: set[str] = set()  # R14: one warning per distinct cause
        self.held_by: tuple[tuple[str, tuple[str, ...]], ...] = ()  # last pass: waiting on others
        self._claim_done = SyncResult()

    # -------------------------------------------------------------- reaching out

    def client(self, facts: Facts, repo: str) -> GhClient:
        if repo not in self._clients:
            self._clients[repo] = make_client(f"https://{_host_of(facts, repo)}/{repo}")
        return self._clients[repo]

    def group_of(self, batch: Batch) -> str:
        """The runner group of *batch*'s sessions: its CURRENT wave's workspace."""
        return wave_group(self.workspace_prefix, batch.wave)

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

    def _try_runner(
        self, name: str, consequence: str = "its sessions are not closed"
    ) -> Runner | None:
        """Runner *name*, or None (reported once) when it cannot be loaded: closing and
        the idle probe are best effort, so a load failure never ends the drive (R10).
        *consequence* names what the caller loses, so the warning says the right thing."""
        if name in self._unloadable:
            return None
        runner, reason = try_load(name, self.runner)
        if runner is not None:
            return runner
        self._unloadable.add(name)
        err_console.print(
            f"[yellow]warning:[/yellow] runner `{escape(name)}` could not be loaded "
            f"({escape(reason or 'no reason given')}); {escape(consequence)}",
            soft_wrap=True,
        )
        return None

    def merge_ctx(self, facts: Facts, repo: str) -> MergeContext:
        if repo not in self._merge:
            client, checkout = self.client(facts, repo), self.checkout(repo)
            try:
                _fresh_config(checkout, facts, repo, lenient=True)
            except TriageError as exc:  # a fetch, or main's config moved under the pass
                raise ForgeReadError(str(exc), code=2) from exc
            try:
                method = choose_method(
                    None,
                    client.repo_merge_methods(repo),
                    configured=facts.config_for(repo).merge_method,
                )
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
        # Read each pass, as the pass's own verdict is: the context outlives a pass.
        self._merge[repo].ci_none = self._ci_none(repo)
        return self._merge[repo]

    # ------------------------------------------------------------------ snapshot

    def snapshot(self, facts: Facts, judgements: Judgements, now: datetime) -> Snapshot:
        """Every batch of the file, with the selection marked: the in-flight cap and
        the dependencies read them all, the actions only the selection (rg-3)."""
        repos = {b.id: r for b in judgements.batches if (r := batch_repo(b, facts)) is not None}
        # A repo collect skipped (org or group scope: its lists or config failed) still
        # resolves its batches, but with no PRs, so a pr-open or merged one would read
        # as dispatched and a proposed one dispatch on default config. Its batches sit
        # this pass out; the in-flight cap and dependencies still count them (gh#921).
        unread = {s.repo: s.reason for s in facts.skipped}
        chosen = _chosen(judgements.batches, self.named)
        self._unread = {r: why for r, why in unread.items()
                        if any(repos.get(b.id) == r for b in chosen)}  # fmt: skip
        self._left_out = {
            b.id: repos[b.id] for b in chosen if repos.get(b.id) in unread and not _settled(b)
        }
        chosen = [b for b in chosen if repos.get(b.id) not in unread]
        ids = {b.id for b in chosen}
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
        unverified: set[str] = set()
        adopted: dict[str, LivePr] = {}
        archives: dict[str, tuple[LivePr, ...]] = {}
        due: list[Batch] = []
        stale: list[Batch] = []  # recorded close-outs old enough to ask the runner about
        try:
            for e in queue:
                repo = repos[e.batch.id]
                client = self.client(facts, repo)
                view = client.pr_view(repo, e.pr.number)
                verdict, failing = checks_verdict(
                    client.pr_required_checks(repo, e.pr.number),
                    e.pr.checks or {},
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
                    trusted=True,  # the queue holds `batch_pr`s only (gh#936)
                )
            # Every landed batch, selected or not: adopting a finished close-out is
            # bookkeeping (gh#990). Only the selection is read further.
            for b in judgements.batches:
                if stages[b.id] not in ("merged", "partial") or b.id not in repos:
                    continue
                if repos[b.id] in unread:
                    continue
                mine = b.id in ids
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
                    gone = self._archived(repo, merge)
                    if gone is None:  # plan mode, an unreadable clone (gh#991)
                        unverified.add(b.id)
                        continue
                    if gone:
                        archived.add(b.id)
                        continue
                    hand = self._hand_closeout(facts, repo, b)
                    if hand is not None and (mine or hand.state == "MERGED"):
                        adopted[b.id] = hand
                        continue
                    if not mine:
                        continue
                    when = _parse_at(pr.merged_at if pr else None)
                    merged_at[b.id] = when or self._first_seen.setdefault(b.id, now)
                    shipped = self._released(repo, merge)
                    if shipped is None:
                        unverified.add(b.id)
                        continue
                    if shipped:
                        released.add(b.id)
                    if closeout_due(released=b.id in released, merged_at=merged_at[b.id], now=now):
                        due.append(b)
                    continue
                if event.archived is not None or not mine:
                    continue  # its archive PR was merged by the driver: finished
                archives[repos[b.id]] = (
                    *archives.get(repos[b.id], ()),
                    *self._archive_prs(facts, repos[b.id], b, event),
                )
                if now - event.at >= STALE_CLOSEOUT:  # is its tab still live? (gh#1025)
                    stale.append(b)
        except UnsupportedForgeOperation as exc:
            _fail(str(exc))
        except FORGE_ERRORS as exc:
            raise ForgeReadError(f"a forge read failed: {exc}", code=1) from exc
        done_waves = finished_waves(judgements.batches, stages)
        claim_plan = self._claim_plan(facts, judgements, repos, unread, now)
        export_path, export_refused = self._export_config(facts)
        export_prs, export_orphans = self._export_reads(
            facts, judgements, repos, done_waves, export_path
        )
        default_branch = {r: self._default_branch(r) for r in {*export_path, *archives}}
        closing_sessions = self.yes and not self.keep_sessions
        sessions = frozenset[str]()
        self._probes = {}
        if closing_sessions:
            finished = [
                b
                for b in chosen
                if b.id in repos and is_finished(b, stages[b.id], archives.get(repos[b.id], ()))
            ]
            sessions = self._sessions(facts, finished, repos)
        existing, probed = frozenset[str](), frozenset[str]()
        if self.yes:
            existing, _ = self._existing(facts, due, repos)
            stale_live, asked = self._existing(facts, stale, repos, soft=True)
            existing |= stale_live
            probed = frozenset(b.id for b in stale if closeout_item_id(repos[b.id], b.id) in asked)
        idle = self._idle(facts, chosen, repos, stages, archives, now) if self.yes else ()
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
            existing=existing,
            closeout_probed=probed,
            idle=idle,
            scope_args=tuple(self.scope_args),
            warned=frozenset(self.warned),
            close_sessions=closing_sessions,
            sessions=sessions,
            selected=frozenset(ids),
            unfinished_waves=self._unfinished,
            duplicate_groups=len(candidates(facts, judgements)),
            dedupe_command=shlex.join(["fr", "triage", "check", *self.scope_args]),
            archived=frozenset(archived),
            adopted=adopted,
            foreign={b.id: found for b in chosen if (found := tuple(foreign_batch_prs(b, facts)))},
            export_path=export_path,
            exports=tuple(judgements.exports),
            export_prs=export_prs,
            export_orphans=export_orphans,
            default_branch=default_branch,
            unverified=frozenset(unverified),
            finished=done_waves,
            export_refused=export_refused,
            awaiting=frozenset(b.id for b in judgements.batches if batch_awaits_live(b, facts)),
            **claim_plan,
        )

    def _claim_plan(
        self,
        facts: Facts,
        judgements: Judgements,
        repos: dict[str, str],
        unread: dict[str, str],
        now: datetime,
    ) -> dict[str, Any]:
        """The Snapshot's claim fields (triage-claims §3.F), from facts alone: nothing here
        reaches the forge, so plan mode shows them too. `plan_sync` decides what is owed
        (the same reading `claim sync` has); a batch of a repo collect skipped is left
        out, its issues' comments were not read."""
        env = self._claims = claim_env(self.target, facts)
        plan = plan_sync(env, judgements.batches, now)

        def blind(op: ClaimOp) -> bool:
            """A refresh of a member facts cannot see (closed: collect reads no closed
            issue's comments): a read that writes only when the marker is due, so it is
            made with --yes and never announced in a plan."""
            issue = env.issue(op.key)
            return op.kind == "refresh" and (issue is None or issue.state != "open")

        def owed(kind: str) -> tuple[tuple[str, str], ...]:
            return tuple(
                (op.key, op.batch) for op in plan.ops
                if op.kind == kind and repos.get(op.batch) not in unread
                and (self.yes or not blind(op))
            )  # fmt: skip

        keys = {k for b in judgements.batches for k in b.ids}
        return {
            "me": env.me,
            "held": dict(held_members(sorted(keys), held_map(facts, env.me))),
            "claims_owed": owed("claim"),
            "refresh_owed": owed("refresh"),
            "releases_owed": owed("release"),
        }

    def _default_branch(self, repo: str) -> str:
        """*repo*'s default branch, the only base an export PR may have (p4-r15); ""
        when the clone cannot say, which matches no base."""
        try:
            return self._reader(repo).default_branch()
        except TriageError as exc:
            self._unreadable(repo, exc)
            return ""

    def _export_files(self, repo: str, head: str) -> tuple[str, ...]:
        """The paths *head* changed since it forked from `origin/<default>`, renames
        split into a delete and an add, never truncated; () when git cannot read it."""
        if not head:
            return ()
        try:
            checkout = self._reader(repo)
            checkout.fetch()
            ref = f"origin/{checkout.default_branch()}"
            return tuple(sorted(checkout.changed_paths(ref, head)))
        except TriageError:
            return ()

    def _export_config(self, facts: Facts) -> tuple[dict[str, str], frozenset[str]]:
        """(repo -> export directory `<path>/<scope>`) for a single-repo scope that opts
        in (R13), and the repos of a group or org scope that opt in, which never export."""
        opted = {
            r: f"{c.path}/{self.scope.name}"  # normalised at load (p4-r2)
            for r in facts.repos
            if (c := facts.config_for(r).export) is not None
        }
        if self.scope.kind == "repo":
            return opted, frozenset()
        return {}, frozenset(opted)

    def _export_reads(
        self,
        facts: Facts,
        judgements: Judgements,
        repos: dict[str, str],
        finished: frozenset[str],
        export_path: dict[str, str],
    ) -> tuple[dict[tuple[str, str], LivePr], dict[str, tuple[LivePr, ...]]]:
        """§I's live reads: the export PR of each repo's newest unmerged export (keyed
        by its wave), and the repo's orphans: open PRs from the repo itself on any
        `chore/triage-state-wave-<N>` head that no entry records (p4-r3). A cross-repo
        PR is never an orphan (p4-r7). Trust is the author check; state and head are
        fresh from `pr_view` for a recorded PR, from this pass's collect for an orphan.

        `files` are NEVER the forge's: gh names only a rename's new path and stops at
        100 entries (p4-sec-file-list). They are git's diff of the head the decision is
        about (the recorded head, or the orphan's) against `origin/<default>`; an
        unreadable head reads as no files, which the decision refuses. An orphan's
        content is never read: the export reuses the PR, never its head (p4-r12)."""
        collected = {pr.number: pr for pr in facts.prs}
        prs: dict[tuple[str, str], LivePr] = {}
        orphans: dict[str, tuple[LivePr, ...]] = {}
        try:
            for repo in sorted(export_path):
                allowed = allowed_authors(repo, facts)
                # a PR whose entry is recorded closed is reusable once reopened (p4-r13)
                recorded = {e.pr for e in judgements.exports if e.repo == repo and not e.closed}
                found = tuple(
                    self._orphan(self.client(facts, repo), repo, pr, allowed)
                    for pr in facts.prs
                    if pr.repo == repo
                    and pr.state == "OPEN"
                    and export_wave_of(pr.head_ref) is not None
                    and pr.cross_repo is not True  # a fork never stalls the export
                    and pr.number not in recorded
                )
                if found:
                    orphans[repo] = found
                target = export_target(
                    repo, judgements.batches, repos, finished, judgements.exports, found
                )
                if target is None or target.recorded is None or target.recorded.pr is None:
                    continue
                done, number = target.recorded, target.recorded.pr
                client = self.client(facts, repo)
                listed = next(
                    (p for p in _live_head_prs(client, repo, export_branch(target.wave), allowed)
                     if p.number == number),
                    None,
                )  # fmt: skip
                view = client.pr_view(repo, number)
                pick = replace(
                    listed or LivePr(number=number, state="", draft=False, head=""),
                    state=str(view.get("state", "")).upper(),
                    draft=bool(view.get("draft")),
                    head=str(view.get("head_oid") or ""),
                    base=str(view.get("base_ref") or ""),  # p4-r15
                    files=self._export_files(repo, done.head or ""),
                )
                if pick.state == "OPEN":
                    pr = collected.get(pick.number)
                    verdict, failing = checks_verdict(
                        client.pr_required_checks(repo, pick.number),
                        (pr.checks if pr is not None else None) or {},
                        ci_none=self._ci_none(repo),
                    )
                    pick = replace(pick, checks=verdict, failing=failing)
                prs[(repo, target.wave)] = pick
        except UnsupportedForgeOperation as exc:
            _fail(str(exc))
        except FORGE_ERRORS as exc:
            raise ForgeReadError(f"a forge read failed: {exc}", code=1) from exc
        return prs, orphans

    @staticmethod
    def _orphan(client: GhClient, repo: str, pr: PullRequest, allowed: frozenset[str]) -> LivePr:
        """An unrecorded open export PR, as reuse judges it: open, trusted, and its base
        read fresh (p4-r15). Nothing else of it is read: nothing of it is kept (p4-r12)."""
        view = client.pr_view(repo, pr.number)
        return LivePr(
            number=pr.number,
            state=str(view.get("state", "")).upper() or "OPEN",
            draft=pr.is_draft,
            head=pr.head_oid,
            head_ref=pr.head_ref,
            trusted=distrust(pr.author, pr.cross_repo, allowed) is None,
            base=str(view.get("base_ref") or ""),
        )

    def _hand_closeout(self, facts: Facts, repo: str, batch: Batch) -> LivePr | None:
        """The close-out PR started by hand for *batch*, merged first, else open: the
        one on `chore/closeout-<batch branch>`, a head only this batch produces, the
        attribution the archive step already trusts (gh#912). A closed one is
        abandoned and attributes nothing. Only a `trusted` PR is adopted (gh#936):
        batch branch names are predictable, and an adopted open PR is merged by the
        archive step once green, so a fork's or a foreign author's never is."""
        client, allowed = self.client(facts, repo), allowed_authors(repo, facts)
        found = [
            p for p in _live_head_prs(client, repo, _closeout_head(batch), allowed) if p.trusted
        ]
        for state in ("MERGED", "OPEN"):
            pick = next((p for p in found if p.state == state), None)
            if pick is not None:
                return pick
        return None

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
                self._ci[repo] = ci_none_at(checkout)
            except TriageError as exc:
                self._ci[repo] = False  # an unreadable declaration is not `none`
                self._unreadable(repo, exc)
        return self._ci[repo]

    def _unreadable(self, repo: str, exc: TriageError) -> None:
        """Record, in plan mode, that *repo*'s clone could not be read: the pass reports
        it once instead of presenting a guess as the plan (gh#991). With --yes a read
        that fails is fatal to the pass already."""
        if not self.yes:
            self._clone_unread.setdefault(repo, str(exc))

    def _archived(self, repo: str, merge_commit: str) -> bool | None:
        """Whether the batch merged by *merge_commit* was closed out already: the run
        artifacts it added are all gone from `origin/<default>` (`is_archived`), as
        `fr archive` leaves them, whether a driver or a hand ran the close-out. None in
        plan mode when the clone cannot be read: unknown, never "not archived" (gh#991)."""
        try:
            checkout = self._reader(repo)
            checkout.fetch()
            tip = f"origin/{checkout.default_branch()}"
            return is_archived(
                checkout.added_paths(merge_commit), lambda p: checkout.exists_at(tip, p)
            )
        except TriageError as exc:
            if self.yes:  # a fetch on a degraded forge: read again next pass (gh#921)
                raise ForgeReadError(str(exc), code=2) from exc
            self._unreadable(repo, exc)
            return None

    def _released(self, repo: str, merge_commit: str) -> bool | None:
        try:
            checkout = self._reader(repo)
            checkout.fetch()
            return checkout.released_after(merge_commit)
        except TriageError as exc:
            if self.yes:  # as `_archived` (gh#921)
                raise ForgeReadError(str(exc), code=2) from exc
            self._unreadable(repo, exc)
            return None

    def _archive_prs(
        self, facts: Facts, repo: str, batch: Batch, event: CloseoutEvent
    ) -> list[LivePr]:
        """Archive PR candidates: the open `chore/*` PRs collect read (with files and
        checks), plus any PR on the close-out's own heads, merged ones included."""
        client = self.client(facts, repo)
        allowed = allowed_authors(repo, facts)
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
                pr.checks or {},
                ci_none=self._ci_none(repo),
            )
            out[pr.number] = LivePr(
                number=pr.number, state="OPEN", draft=pr.is_draft, head=pr.head_oid,
                checks=verdict, failing=failing, head_ref=pr.head_ref, files=tuple(pr.files),
                trusted=distrust(pr.author, pr.cross_repo, allowed) is None,
            )  # fmt: skip
        heads = {_closeout_head(batch)}
        heads |= {event.archive} if event.archive else set()
        for head in sorted(heads):
            for found in _live_head_prs(client, repo, head, allowed):
                if found.state != "OPEN" or found.number not in out:
                    out[found.number] = found
        # The base, read fresh as the export reads it (p4-r15): an archive PR is merged
        # only into the default branch (gh#1004). Only an open one this batch owns can
        # be merged, so only those cost a read.
        return [
            replace(p, base=str(client.pr_view(repo, p.number).get("base_ref") or ""))
            if p.state == "OPEN" and attributed(p, batch, event)
            else p
            for p in out.values()
        ]

    def _existing(
        self, facts: Facts, closing: list[Batch], repos: dict[str, str], *, soft: bool = False
    ) -> tuple[frozenset[str], frozenset[str]]:
        """The close-out items the runners already hold live, so a kill between the
        dispatch and its event never starts a second session (§B step 2), and the
        items actually asked about. Only the close-outs that are due are probed
        (review rg-10): a runner that cannot start one now must not stop a merge or a
        dispatch. A runner's preflight refusal is reported once and exits 2.

        *soft*: the stale-close-out probe (gh#1025), a report only. A runner that cannot
        load or refuses is skipped, and its items are left unasked, so none is called
        stale on a read that never happened."""
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
                # The group the close-out itself carries: a runner's preflight reads it
                # (herdr needs no workspace of its own for a grouped item, review p1-r1).
                payload={
                    "kind": "closeout",
                    "harness": launch.harness,
                    "model": launch.model,
                    "group": self.group_of(b),
                },
                tracking=None,
            )
            by_runner.setdefault(str(launch.runner), []).append(probe)
        asked: set[str] = set()
        for name, probes in by_runner.items():
            if soft:
                loaded = self._try_runner(name)
                if loaded is None or loaded.preflight(probes):
                    continue
                runner = loaded
            else:
                runner = self.runner(name)
                refusal = runner.preflight(probes)
                if refusal:
                    _fail(f"runner `{name}` refused: {refusal}")
            found |= runner.existing_dispatches(probes)
            asked.update(p.id for p in probes)
        return frozenset(found), frozenset(asked)

    def _sessions(
        self, facts: Facts, finished: list[Batch], repos: dict[str, str]
    ) -> frozenset[str]:
        """The sessions of finished batches that a closing runner holds live: each
        item against the runner its own event recorded (the batch's last dispatch,
        the close-out's own; a `hand` close-out has no session). One preflight and
        one `existing_dispatches` per runner; a runner that cannot load, cannot close,
        or refuses is skipped, never an exit (R10)."""
        if not finished:
            return frozenset()
        from fr_dispatch.protocols import SessionCloser

        by_runner: dict[str, list[WorkItem]] = {}
        for b in finished:
            repo = repos[b.id]
            dispatch, closeout = last_dispatch(b), closeout_event(b)
            wanted = [(False, dispatch.runner if dispatch else None)]
            if closeout is not None and closeout.runner != "hand":
                wanted.append((True, closeout.runner))
            for is_closeout, name in wanted:
                if not name:
                    continue
                probe = probe_item(repo, b, closeout=is_closeout, prefix=self.workspace_prefix)
                by_runner.setdefault(str(name), []).append(probe)
        for name, probes in by_runner.items():
            runner = self._try_runner(name)
            if runner is None or not isinstance(runner, SessionCloser):
                continue
            try:
                refusal = runner.preflight(probes)
                held = set() if refusal else runner.existing_dispatches(probes)
            except Exception as exc:  # noqa: BLE001 - closing is best effort
                refusal = str(exc) or type(exc).__name__
                held = set()
            if refusal:
                self._report_once(f"closing\0{name}\0{refusal}",
                                  f"runner `{name}` cannot close sessions: {refusal}")  # fmt: skip
                continue
            for probe in probes:
                if probe.id in held:
                    self._probes[probe.id] = (runner, probe)
        return frozenset(self._probes)

    def _idle(
        self,
        facts: Facts,
        chosen: list[Batch],
        repos: dict[str, str],
        stages: dict[str, BatchStage],
        archives: dict[str, tuple[LivePr, ...]],
        now: datetime,
    ) -> tuple[IdleSession, ...]:
        """The sessions the runner reports idle with nothing to show for it (R7).

        Only candidates are probed: a batch whose last dispatch is older than the repo's
        `idle_session_minutes` and that has no PR, and a recorded, unfinished close-out
        older than that. One `session_statuses` per runner, and soft: a runner that cannot
        load, refuses or raises is skipped, so no session reads idle from a read that never
        happened. The verdict itself is `idle_session`, the one definition the board reads."""
        from fr_dispatch.protocols import SessionInspector

        candidates: list[tuple[Batch, bool, str]] = []  # (batch, is_closeout, runner name)
        for b in chosen:
            repo, stage = repos.get(b.id), stages.get(b.id)
            if repo is None or stage is None:
                continue
            threshold = facts.config_for(repo).idle_session_minutes
            dispatch, event = last_dispatch(b), closeout_event(b)
            for is_closeout, owner in ((False, dispatch), (True, event)):
                if owner is None or (is_closeout and owner.runner == "hand"):
                    continue
                # A candidate is a session `idle_session` would report were it idle: the
                # rule alone decides what is owed work, so no second test lives here.
                if idle_session(
                    b, repo=repo, closeout=is_closeout, status="idle", stage=stage,
                    archives=archives.get(repo, ()), now=now, threshold=threshold,
                ) is not None:  # fmt: skip
                    candidates.append((b, is_closeout, str(owner.runner)))
        by_runner: dict[str, list[tuple[Batch, bool, WorkItem]]] = {}
        for b, is_closeout, name in candidates:
            probe = probe_item(repos[b.id], b, closeout=is_closeout, prefix=self.workspace_prefix)
            by_runner.setdefault(name, []).append((b, is_closeout, probe))
        found: list[IdleSession] = []
        for name, entries in by_runner.items():
            runner = self._try_runner(name, "idle sessions are not reported")
            if runner is None or not isinstance(runner, SessionInspector):
                continue
            probes = [probe for _, _, probe in entries]
            try:
                refusal = runner.preflight(probes)
                statuses = {} if refusal else runner.session_statuses(probes)
            except Exception as exc:  # noqa: BLE001 - reporting is best effort
                refusal, statuses = str(exc) or type(exc).__name__, {}
            if refusal:
                self._report_once(
                    f"idle-probe\0{name}\0{refusal}",
                    f"runner `{name}` cannot report session status: {refusal}",
                )
                continue
            for b, is_closeout, probe in entries:
                repo = repos[b.id]
                idle = idle_session(
                    b, repo=repo, closeout=is_closeout, status=statuses.get(probe.id),
                    stage=stages[b.id], archives=archives.get(repo, ()), now=now,
                    threshold=facts.config_for(repo).idle_session_minutes,
                )  # fmt: skip
                if idle is not None:
                    found.append(idle)
        return tuple(found)

    def _report_once(self, key: str, message: str) -> bool:
        """Print *message* the first time *key* is seen; whether it was printed."""
        if key in self.warned:
            return False
        self.warned.add(key)
        err_console.print(f"[yellow]warning:[/yellow] {escape(message)}", soft_wrap=True)
        return True

    def _close_sessions(self, action: Action) -> str:
        """Close *action*'s sessions. Never a failure: a busy or raised close is
        reported once per batch and cause, and the pass goes on (R10). Returns the
        outcome line, or "" for a cause already reported."""
        closed: list[str] = []
        busy: list[str] = []
        failed: list[tuple[str, Exception]] = []
        for item_id in action.items:
            runner, probe = self._probes[item_id]
            try:
                outcome = str(runner.close(probe))  # type: ignore[attr-defined]
            except Exception as exc:  # noqa: BLE001 - closing is best effort
                failed.append((item_id, exc))
                continue
            (busy if outcome == "busy" else closed).append(item_id)
        # A cause is the item and what kept it open (an exception by its type, never
        # its message), so a sibling closing, or a timeout's figure, is not a new
        # cause (review p2-r2). The bitwise `|` keeps every cause recorded.
        fresh = False
        for item_id in busy:
            fresh |= self._report_cause(action.batch, f"{item_id}\0busy")
        for item_id, error in failed:
            fresh |= self._report_cause(action.batch, f"{item_id}\0{type(error).__name__}")
        done = f"closed {', '.join(closed)}" if closed else ""
        if (busy or failed) and not fresh:
            return done  # every cause reported already: only what closed is news
        parts = [done] if done else []
        if busy:
            parts.append(f"busy, retried next pass: {', '.join(busy)}")
        if failed:
            parts.append(f"failed to close {'; '.join(f'{i}: {e}' for i, e in failed)}")
        return "; ".join(parts)

    def _report_cause(self, batch: str, cause: str) -> bool:
        key = f"close\0{batch}\0{cause}"
        if key in self.warned:
            return False
        self.warned.add(key)
        return True

    def _launch(self, facts: Facts, batch: Batch, repo: str) -> Launch:
        try:
            return resolve_launch(  # the clone's models.yaml, as dispatch_batch reads it (rg-8)
                batch, facts.config_for(repo), orchestrator=_orchestrator(self.checkout(repo).path)
            ).launch
        except TriageError as exc:
            _fail(str(exc))

    # ------------------------------------------------------------------- execute

    def observation_owed(self) -> bool:
        """Whether a finishing loop owes one more pass before it exits (review p1-r4).

        A pass that ends the drive may itself finish a wave (an archive merge, an adopted
        close-out); only the NEXT pass observes it, so the loop runs that pass once, with
        no nap, whenever some wave was unfinished when the last pass began (R10)."""
        if self._observed_last or not self._unfinished:
            return False
        self._observed_last = True
        return True

    def run_pass(self) -> tuple[bool, Summary, list[str]]:
        """One pass: re-collect, decide, act (with --yes) or print the plan.
        Returns whether it acted, the settled summary, and the blocked batch ids."""
        ignored = recollect(self.scope, self.target) or {}
        for repo, keys in sorted(ignored.items()):
            self._report_once(
                f"ignored\0{repo}\0{','.join(keys)}",
                f"{repo}: {TRIAGE_CONFIG_PATH} on the default branch has "
                f"{plural(len(keys), 'key')} this fr does not know ({', '.join(keys)}); "
                "ignored until an fr that knows them runs",
            )
        _, facts, judgements = _load_state(self.scope, self.target)
        self._ci, self._unlanded, self._held = {}, set(), 0
        self._clone_unread = {}
        self._restart = {}
        self._stopped, self._queued, self._conflicts = {}, 0, {}
        self._export_refusals = 0
        self._export_failures = 0
        self._held_now, self._claim_done = {}, SyncResult()
        self.failed_write = False
        snap = self.snapshot(facts, judgements, _now())
        for repo, why in sorted(self._unread.items()):
            mine = sorted(b for b, r in self._left_out.items() if r == repo)
            self._report_once(
                f"unread\0{repo}\0{why}",
                f"{repo} was not read this pass ({why}); "
                + (f"its batches {', '.join(mine)} are left out until it is"
                   if mine else "its batches are left out until it is"),
            )  # fmt: skip
        for repo, why in sorted(self._clone_unread.items()):
            mine = sorted(b for b in snap.unverified if snap.repos.get(b) == repo)
            self._report_once(
                f"clone\0{repo}\0{why}",
                f"cannot read {repo}'s clone ({why}); the checks that need it are skipped"
                + (f", so no close-out is planned for {', '.join(mine)}" if mine else ""),
            )  # fmt: skip
        plan = drive_pass(snap)
        self.held_by = plan.held_by
        self._unfinished = unfinished_waves(snap)
        acted = False
        in_flight = sum(1 for b in snap.batches if snap.stages[b.id] in LIVE_STAGES)
        try:  # a pass that aborts after a post_merge still restarts what it owes (p2-r1)
            for train in plan.trains:
                _say(train_line(train))
            for action in plan.actions:
                if not self.yes:
                    _say(action_line(action))
                    continue
                refused = self._export_refusals
                outcome, did, in_flight = self._act(action, facts, in_flight)
                acted = acted or did
                if self._export_refusals > refused:  # refused before any write: a warning
                    action = replace(action, kind="warn")
                if outcome or action.kind not in ("close", "claim", "refresh", "release"):
                    # a close reported already stays quiet, as does a claim write that wrote nothing
                    _say(action_line(action, outcome))
            if self.yes:
                self._record_released(facts)
            summary = settle(
                plan.summary, unlanded=len(self._unlanded), held=self._held, queued=self._queued
            )
            if self._left_out:  # not done, only unread: the drive keeps waiting for them
                summary = replace(summary, pending=summary.pending + len(self._left_out))
            if self._export_refusals:  # still owed, but only the operator can move it
                summary = replace(
                    summary,
                    closing=summary.closing - self._export_refusals,
                    blocked=summary.blocked + self._export_refusals,
                )
            _say(summary_line(summary))
        finally:
            if self.yes:
                self._restart_sessions()  # soft: never raises out of here
        if self.yes:
            self._write_board()
        else:
            _say("nothing done; re-run with --yes to act")
        stuck = [a.batch for a in plan.actions if a.kind == "blocked"]
        stuck += [f"export wave {a.wave} {a.batch}" for a in plan.actions
                  if a.wave is not None and a.kind == "warn"]  # fmt: skip
        return acted, summary, stuck

    def _restart_sessions(self) -> None:
        """Restart idle sessions once per recorded runner, after every close-out this pass
        started (driver-sessions §B, sr-7). Soft like `_sessions`: a runner that cannot
        load, refuses, or cannot restart is reported once per process, a raise is reported,
        and none of it holds the drive or changes `--once`'s exit code."""
        from fr_dispatch.protocols import SessionRestarter

        for name, probe in self._restart.items():
            runner = self._try_runner(name)
            if runner is None:
                continue
            if not isinstance(runner, SessionRestarter):
                self._report_once(f"restart\0{name}", f"runner `{name}` cannot restart sessions")
                continue
            try:
                refusal = runner.preflight([probe])
                if refusal:
                    self._report_once(
                        f"restart\0{name}\0{refusal}",
                        f"runner `{name}` cannot restart sessions: {refusal}",
                    )
                    continue
                result = runner.restart_idle()
            except Exception as exc:  # noqa: BLE001 - upkeep, never the drive's work
                err_console.print(
                    f"[yellow]warning:[/yellow] restarting `{escape(name)}` sessions failed: "
                    f"{escape(str(exc) or type(exc).__name__)}",
                    soft_wrap=True,
                )
                continue
            _say(f"restart: {result.ok} ok, {result.skipped} skipped, {len(result.failed)} failed")
            for pane, reason in result.failed:
                _say(f"restart failed {pane}: {reason}")

    def _write_board(self) -> None:
        """Render `board.html` from what this pass left on disk (R11). A board that cannot
        be written is one warning per distinct cause and never changes the pass."""
        try:
            out, _ = triage_kanban_cmd.write_board(
                self.scope,
                self.target,
                scope_args=self.scope_args,
                prefix=self.workspace_prefix,
            )
        except Exception as exc:  # noqa: BLE001 - the board is a view; it never fails a pass
            cause = triage_kanban_cmd.one_line(exc)
            if cause not in self.board_failures:
                self.board_failures.add(cause)
                err_console.print(
                    f"[yellow]warning:[/yellow] could not write the board: {escape(cause)}",
                    soft_wrap=True,
                )
        else:
            self.board_failures.clear()
            triage_kanban_cmd.publish(self.scope, self.target, out, self.publish_failures)

    def _act(self, action: Action, facts: Facts, in_flight: int) -> tuple[str, bool, int]:
        """Execute *action*; its outcome line, whether it acted, and the in-flight count."""
        if action.kind == "dedupe":  # names no batch: a report, never a forge write (sr-1)
            return action.detail, False, in_flight
        if action.kind in EXPORT_KINDS:
            refusals, failures = self._export_refusals, self._export_failures
            line = self._export_act(action, facts)
            did = (self._export_refusals, self._export_failures) == (refusals, failures)
            return line, did, in_flight  # a refusal or a failed write did nothing
        if action.kind in ("warn", "foreign"):
            if action.head:  # an export's warn names no head: it is said every pass
                self.warned.add(action.head)
            return action.detail, False, in_flight
        if action.kind in ("blocked", "held"):
            return action.detail, False, in_flight
        if action.kind in ("claim", "refresh", "release"):
            if action.kind == "claim" and action.batch in self._held_now:
                return "", False, in_flight  # one claim was lost: the batch's rest wait (R6)
            line, did = self._claim_write(action)
            return line, did, in_flight
        if action.batch in self._held_now:  # a claim write found it held: leave it alone (R6)
            if action.kind == "dispatch":
                self._held += 1  # planned in flight, did not start: still pending
            elif action.kind == "merge":
                self._unlanded.add(action.batch)  # planned merged, did not land
            return f"held: {self._held_now[action.batch]}", False, in_flight
        judgements = load_judgements(self.target / "judgements.yaml")
        batch = _find(judgements.batches, action.batch)
        repo = batch_repo(batch, facts)
        if repo is None:
            return action.detail, False, in_flight
        if action.kind == "close":
            return self._close_sessions(action), False, in_flight  # never `acted`
        if action.kind == "merge":
            behind = self._stopped.get(action.train)
            if behind is not None:  # an earlier head of this train did not merge (R3)
                self._unlanded.add(batch.id)
                self._queued += 1
                return f"queued: behind {behind}", False, in_flight
            merged = self._merge_batch(action, facts, judgements, batch, repo, in_flight)
            if merged.stops:
                self._stopped[action.train] = batch.id
            return merged.line, merged.acted, merged.in_flight
        if action.kind == "closeout":
            outcome, did = self._close_out(action, facts, judgements, batch, repo)
            return outcome, did, in_flight
        if action.kind == "archive":
            line, did = self._archive(action, facts, judgements, batch, repo)
            return line, did, in_flight
        if action.kind == "adopt":
            started = closeout_event(batch)
            self._append(
                judgements, facts, batch,
                # A close-out this driver started: the same event again, now archived,
                # as `_archive` records one it merged itself (gh#882).
                started.model_copy(update={"at": _now_after(batch), "archived": action.archived})
                if started is not None
                else CloseoutEvent(kind="closeout", at=_now_after(batch), runner="hand",
                                   handle=f"PR #{action.pr}" if action.pr else "archived",
                                   archive=_closeout_head(batch) if action.pr else None,
                                   archived=action.archived),
            )  # fmt: skip
            return action.detail, True, in_flight
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
        try:
            with console.capture():  # dispatch_batch's own plan: one line per action here
                dispatch_batch(
                    self.target,
                    facts,
                    judgements,
                    batch,
                    checkout_path=self.path_of(repo),
                    yes=True,
                    group=self.group_of(batch),
                    lenient_config=True,
                    read_errors=True,
                )
        except RunnerDispatchError as exc:
            return self._dispatch_failed(batch, str(exc), exc.__cause__), False, in_flight
        after = _find(load_judgements(self.target / "judgements.yaml").batches, batch.id)
        event = last_dispatch(after)
        assert event is not None
        return (
            f"dispatched to {event.runner} as {batch_item_id(repo, batch.id)}",
            True,
            in_flight + 1,
        )

    def _claim_write(self, action: Action) -> tuple[str, bool]:
        """Execute one claim, refresh or release through `claim_sync.execute` (R3, R8,
        R10). A claim that turned out held (R4) stops the pass acting on its batch; a
        failed write is reported, makes `--once` exit 1, and is retried next pass."""
        assert self._claims is not None
        op = ClaimOp(action.kind, action.key, action.batch)  # type: ignore[arg-type]
        try:
            result = execute(self._claims, [op], _now())
        except UnsupportedForgeOperation as exc:
            _fail(str(exc))
        if result.held:
            line = held_line(op.key, result.held[0].holder, _now())
            self._held_now.setdefault(action.batch, line)
            return line, False
        if result.failed:
            self.failed_write = True
            return f"failed: {result.failed[0][1]}", False
        self._claim_done.done.extend(result.done)
        done = result.done[0][1].action
        # Never `acted`: a claim write moves no batch, so it must not make a pass that
        # does nothing else read as progress (exit 3, "nothing to do", still holds).
        return ("" if done == "none" else done), False

    def _record_released(self, facts: Facts) -> None:
        """One `claims_released` event per batch released this pass, after its releases,
        through the one judgements writer, so the next pass owes nothing (R10)."""
        if not any(op.kind == "release" for op, _ in self._claim_done.done):
            return
        batches = load_judgements(self.target / "judgements.yaml").batches
        recorded = record_releases(batches, self._claim_done, _now())
        if recorded == batches:
            return
        try:
            _save(self.target, recorded, facts, read=batches)
        except TriageError as exc:  # idempotent at the forge: the next pass records it
            self._report_once(
                f"claims_released\0{exc}",
                f"could not record the released claims ({exc}); recorded on a later pass",
            )

    def _merge_batch(
        self,
        action: Action,
        facts: Facts,
        judgements: Judgements,
        batch: Batch,
        repo: str,
        in_flight: int,
    ) -> _MergeOutcome:
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
                clear_stop(self.target, batch.id)
                return _MergeOutcome(
                    f"PR #{action.pr} is already merged", False, in_flight - 1, False
                )
            if slots[0].head != action.head:  # pinned to the head whose checks were judged
                return _MergeOutcome(
                    f"held: PR #{action.pr} head moved from {action.head[:12]} to "
                    f"{slots[0].head[:12]} since its checks were judged; it is judged "
                    "again next pass",
                    False,
                    in_flight,
                    True,
                )
            attempt = merge_ready(ctx, slots[0], None)
        except UnsupportedForgeOperation as exc:
            _fail(str(exc))
        except MergeConflictError as exc:
            line, acted = self._conflict(exc, action, facts, judgements, batch, repo)
            return _MergeOutcome(line, acted, in_flight, _stops_train(exc))
        except (MergeStopError, GitError) as exc:
            # A git write that failed (a rejected update push, gh#921) is a refusal
            # too: that PR is stepped over and tried again next pass.
            return _MergeOutcome(self._stopped_line(batch, action, exc), False, in_flight,
                                 _stops_train(exc))  # fmt: skip
        except TriageError as exc:
            _fail(str(exc))
        except FORGE_ERRORS as exc:  # a re-read of the PR or its checks; the merge's own
            # refusal is a MergeStopError above, so no write failure lands here
            raise ForgeReadError(f"a forge read failed: {exc}", code=1) from exc
        stops = _stops_train(attempt)
        if attempt.outcome in ("merged", "already-merged"):
            self._unlanded.discard(batch.id)
            clear_stop(self.target, batch.id)
            return _MergeOutcome(
                f"merged PR #{action.pr} at {attempt.head[:12]}", True, in_flight - 1, stops
            )
        if attempt.outcome == "updated":
            return _MergeOutcome(
                f"updated PR #{action.pr} to {attempt.head[:12]}; it merges on a later pass",
                True,
                in_flight,
                stops,
            )
        held = f": {', '.join(attempt.checks)}" if attempt.checks else ""
        return _MergeOutcome(
            f"held: PR #{action.pr} is {attempt.outcome}{held}", False, in_flight, stops
        )

    def _stopped_line(self, batch: Batch, action: Action, exc: MergeStopError | GitError) -> str:
        """A refusal ends neither the loop nor the pass (rg-4): it is reported in full
        once per batch, head and reason, and `--once` exits 1 on it. Every stop but a
        moved head (re-judged, not owed) is recorded in `merge-stops.json` at the head
        it stopped at, so the board shows it as needing you (#1008)."""
        self.failed_write = True
        key = f"{batch.id}\0{action.head}\0{exc}"
        if not isinstance(exc, HeadMovedError):
            stamp = datetime.now(UTC).isoformat(timespec="seconds")
            record_stop(self.target, batch.id, MergeStop(action.head, str(exc), stamp))
        if key in self.reported:
            return f"stopped again at {action.head[:12]} (reported above)"
        self.reported.add(key)
        return f"stopped: {exc}"

    # ------------------------------------------------- conflict hand-back (§G)

    def _conflict(
        self,
        exc: MergeConflictError,
        action: Action,
        facts: Facts,
        judgements: Judgements,
        batch: Batch,
        repo: str,
    ) -> tuple[str, bool]:
        """A real conflict (spec 2026-10-06-verification-strategies §G, R20-R22): the
        stop line, then what `conflict_decision` says, from the persisted events and
        the conflicts this pass's train met before it. Returns the line and whether
        it acted (wrote an event or handed back)."""
        stopped = self._stopped_line(batch, action, exc)
        earlier = self._conflicts.setdefault(action.train, [])
        decision = conflict_decision(batch.events, exc.head, exc.paths, tuple(earlier))
        earlier.append((batch.id, exc.paths))
        if decision.kind == "skip":
            return stopped, False
        if decision.kind == "wait-behind":
            return (
                f"{stopped}; waits behind {decision.behind}, whose conflict shares a path, "
                "before it is handed back",
                False,
            )
        if decision.kind == "held":
            self._append(judgements, facts, batch, self._conflict_event(exc, batch, "held"))
            return (
                f"{stopped}; held: its hand-backs since its dispatch are spent, it needs you",
                True,
            )
        return self._hand_back(exc, stopped, action, facts, judgements, batch, repo)

    @staticmethod
    def _conflict_event(
        exc: MergeConflictError, batch: Batch, delivered: str, handle: str | None = None
    ) -> ConflictEvent:
        return ConflictEvent(
            kind="conflict", at=_now_after(batch), head=exc.head, paths=list(exc.paths),
            delivered=delivered, handle=handle,  # type: ignore[arg-type]
        )  # fmt: skip

    def _hand_back(
        self,
        exc: MergeConflictError,
        stopped: str,
        action: Action,
        facts: Facts,
        judgements: Judgements,
        batch: Batch,
        repo: str,
    ) -> tuple[str, bool]:
        """Deliver the brief: to the target's idle session, else nothing while it is
        working or blocked, else to a fresh conflict session (R20, R23)."""
        from fr_dispatch.protocols import SessionInspector, SessionMessenger
        from fr_dispatch.work_item import WorkItem

        last = last_dispatch(batch)
        launch = self._launch(facts, batch, repo)
        name = str(last.runner if last else launch.runner)
        branch = last.branch if last else batch_branch(batch)
        brief = conflict_brief(
            batch, pr=action.pr, head=exc.head, paths=exc.paths, branch=branch,
            base=self.merge_ctx(facts, repo).main, mirrors=facts.config_for(repo).mirrors,
        )  # fmt: skip
        runner = self.runner(name)
        since = fresh_conflicts(batch, since_dispatch=True)
        target = WorkItem(
            id=conflict_item_id(repo, batch.id, fresh_conflicts(batch, since_dispatch=False))
            if since
            else batch_item_id(repo, batch.id),
            unit="run", workflow=batch_workflow(batch), repo=repo, parent=None, inputs=(),
            payload={"group": self.group_of(batch)}, tracking=None,
        )  # fmt: skip
        if isinstance(runner, SessionMessenger) and isinstance(runner, SessionInspector):
            try:
                status = runner.session_statuses([target]).get(target.id, "unknown")
                if status == "idle":
                    runner.message(target, brief)
            except Exception as exc_:  # noqa: BLE001 - retried next pass, never the drive's end
                return (
                    f"{stopped}; hand-back to {target.id} failed, retried next pass: {exc_}",
                    False,
                )
            if status == "idle":
                event = self._conflict_event(exc, batch, "session", target.id)
                self._append(judgements, facts, batch, event)
                return f"{stopped}; handed back to its session {target.id}", True
            if status not in ("absent", "done"):
                return (
                    f"{stopped}; its session is {status}: nothing sent, retried next pass",
                    False,
                )
        return self._fresh_conflict(
            exc, stopped, judgements, facts, batch, repo, brief=brief, name=name, launch=launch,
            branch=branch,
        )  # fmt: skip

    def _fresh_conflict(
        self,
        exc: MergeConflictError,
        stopped: str,
        judgements: Judgements,
        facts: Facts,
        batch: Batch,
        repo: str,
        *,
        brief: str,
        name: str,
        launch: Launch,
        branch: str,
    ) -> tuple[str, bool]:
        """Start `<repo>/run/conflict-<id>-<n>` through the batch's runner, the way a
        close-out is started; a live one (a pass killed before its event) is recorded."""
        from fr_dispatch.work_item import WorkItem

        item = WorkItem(
            id=conflict_item_id(repo, batch.id, fresh_conflicts(batch, since_dispatch=False) + 1),
            unit="run",
            workflow=batch_workflow(batch),
            repo=repo,
            parent=None,
            inputs=(),
            payload={
                "kind": "conflict",
                "brief": brief,
                "harness": launch.harness,
                "model": launch.model,
                "branch": branch,
                "issues": list(batch.ids),
                "checkout": str(self.checkout(repo).path),
                "group": self.group_of(batch),
            },
            tracking=None,
        )
        runner = self.runner(name)
        if not runner.can_dispatch(item):
            _fail(f"runner `{name}` does not take run-unit work")
        refusal = runner.preflight([item])
        if refusal:
            _fail(f"runner `{name}` refused: {refusal}")
        if item.id in runner.existing_dispatches([item]):
            self._append(
                judgements, facts, batch, self._conflict_event(exc, batch, "fresh", item.id)
            )
            return f"{stopped}; recorded the live {item.id}", True
        try:
            handle = runner.dispatch(item)
        except Exception as err:  # the runner's own failure: nothing is written
            _fail(f"runner `{name}` failed to dispatch {item.id}: {err}", code=1)
        event = self._conflict_event(exc, batch, "fresh", handle or item.id)
        self._append(judgements, facts, batch, event)
        return f"{stopped}; handed back to a fresh session {item.id}", True

    def _close_out(
        self, action: Action, facts: Facts, judgements: Judgements, batch: Batch, repo: str
    ) -> tuple[str, bool]:
        """§B step 2 and §C: fast-forward, post_merge, then the close-out item."""
        checkout = self.checkout(repo)
        try:
            checkout.fast_forward()
            _fresh_config(checkout, facts, repo, lenient=True)
        except TriageError as exc:
            return f"close-out held: {exc}", False
        command = facts.config_for(repo).post_merge
        post_merged = False
        if action.post_merge and command:
            try:
                checkout.run_command(command)
            except TriageError as exc:
                return f"post_merge failed, close-out held: {exc}", False
            batch = self._append(
                judgements, facts, batch, PostMergeEvent(kind="post_merge", at=_now_after(batch))
            )
            judgements = load_judgements(self.target / "judgements.yaml")
            post_merged = True
            installed = _installed_version()
            if installed is not None and installed != __version__:
                self.restart_to = installed  # after this pass: see `batch_drive_command`
        last = last_dispatch(batch)
        branch = last.branch if last else batch_branch(batch)
        found = find_run(_cursors(checkout.path), branch)
        run, plan_slug = found if found else (None, None)
        archive = housekeeping_branch(branch, run, plan_slug)
        item_id = closeout_item_id(repo, batch.id)
        launch = self._launch(facts, batch, repo)
        if post_merged and facts.config_for(repo).post_merge_restart == "idle":
            name = str(launch.runner)  # restarted once at the end of the pass, not here
            self._restart.setdefault(
                name, probe_item(repo, batch, closeout=True, prefix=self.workspace_prefix)
            )
        if action.recorded:
            self._append(
                judgements, facts, batch,
                CloseoutEvent(kind="closeout", at=_now_after(batch), runner=str(launch.runner),
                              handle=item_id, run=run, archive=archive),
            )  # fmt: skip
            return f"recorded the live {item_id}", True
        item = _closeout_item(
            repo, batch, launch, run=run, checkout=checkout.path, group=self.group_of(batch)
        )
        runner = self.runner(str(launch.runner))
        if not runner.can_dispatch(item):
            _fail(f"runner `{launch.runner}` does not take run-unit work")
        refusal = runner.preflight([item])
        if refusal:
            _fail(f"runner `{launch.runner}` refused: {refusal}")
        # Recorded BEFORE the tab starts (gh#883). The runner only knows the tabs it
        # holds open: one that ran and ended before a restart is invisible to
        # `existing_dispatches`, so a close-out recorded only after `dispatch` returned
        # was started twice by a driver killed in between. The event is the dedupe key.
        started = CloseoutEvent(kind="closeout", at=_now_after(batch), runner=str(launch.runner),
                                handle=item.id, run=run, archive=archive)  # fmt: skip
        recorded = self._append(judgements, facts, batch, started)
        after = _replace(judgements.batches, recorded)
        try:
            handle = runner.dispatch(item)
        except Exception as exc:  # the runner's own failure: nothing started, so
            # the record is taken back and a later pass starts it
            _write(self.target, judgements.batches, facts, read=after)
            return self._dispatch_failed(
                batch, f"runner `{launch.runner}` failed to dispatch {item.id}: {exc}", exc
            ), False
        if handle and handle != item.id:  # the runner's own handle, once it is known
            known = started.model_copy(update={"handle": handle})
            final = recorded.model_copy(update={"events": [*recorded.events[:-1], known]})
            _write(self.target, _replace(after, final), facts, read=after)
        pickup = f"--run {run}" if run else f"--branch {branch}"
        return f"started {item.id} (fr pickup {pickup})", True

    def _dispatch_failed(self, batch: Batch, message: str, cause: BaseException | None) -> str:
        """A runner failed to start *batch*'s session (gh#931): as a refused merge
        (rg-4), reported in full once per batch and cause and tried again on a later
        pass; `--once` exits 1. Nothing was written, so the retry is a fresh start.

        The cause is the runner error's `code` when it carries one: each retry opens a
        new tab, so herdr's words name a different pane every pass."""
        self.failed_write = True
        code = getattr(cause, "code", None)
        key = f"dispatch\0{batch.id}\0{code if isinstance(code, str) else message}"
        if key in self.reported:
            return "stopped again: the runner failed to dispatch (reported above)"
        self.reported.add(key)
        return f"stopped: {message}"

    def _append(self, judgements: Judgements, facts: Facts, batch: Batch, event: Any) -> Batch:
        new = batch.model_copy(update={"events": [*batch.events, event]})
        _write(self.target, _replace(judgements.batches, new), facts, read=judgements.batches)
        return new

    def _archive(
        self, action: Action, facts: Facts, judgements: Judgements, batch: Batch, repo: str
    ) -> tuple[str, bool]:
        ctx = self.merge_ctx(facts, repo)
        assert action.pr is not None
        try:
            ctx.client.pr_merge(repo, action.pr, head_sha=action.head, method=ctx.method)
        except UnsupportedForgeOperation as exc:
            _fail(str(exc))
        except FORGE_ERRORS as exc:
            # As a refused batch-PR merge (rg-4): reported in full once per batch, head
            # and reason, merged again on a later pass; `--once` exits 1 (gh#921).
            self.failed_write = True
            key = f"archive\0{batch.id}\0{action.head}\0{exc}"
            if key in self.reported:
                return f"stopped again at {action.head[:12]} (reported above)", False
            self.reported.add(key)
            return f"stopped: archive PR #{action.pr}: the forge refused the merge: {exc}", False
        # Record it: a PR attributed by its files alone is not found again once it
        # left the open-PR list, and the batch would read as closing forever (rg-6).
        event = closeout_event(batch)
        if event is not None:
            self._append(
                judgements, facts, batch,
                event.model_copy(update={"at": _now_after(batch), "archived": action.pr}),
            )  # fmt: skip
        return f"merged archive PR #{action.pr}", True

    # ------------------------------------------------------- state export (R13)

    def _export_act(self, action: Action, facts: Facts) -> str:
        assert action.wave is not None
        if action.kind == "export":
            return self._export(action, facts, action.batch, action.wave)
        if action.kind == "export-reconcile":  # merged outside the driver (p4-r1)
            assert action.pr is not None
            self._mark(action.batch, action.pr, merged=True)
            return f"recorded export PR #{action.pr} as merged"
        if action.kind == "export-closed":  # closed unmerged: said once (p4-r6)
            assert action.pr is not None
            self._mark(action.batch, action.pr, closed=True)
            err_console.print(f"[yellow]warning:[/yellow] {escape(action.detail)}", soft_wrap=True)
            return f"recorded export PR #{action.pr} as closed; its waves are owed again"
        return self._export_merge(action, facts, action.batch, action.wave)

    def _record_export(
        self, repo: str, waves: tuple[str, ...], *, pr: int | None, head: str | None = None
    ) -> None:
        """Record one `exports:` entry per covered wave (§G, R13), all with the same PR
        and head, replacing earlier entries of those waves; a refused write exits 2."""
        path = self.target / "judgements.yaml"
        read = load_judgements(path).exports
        at = _now()
        new = [Export(wave=w, repo=repo, at=at, pr=pr, head=head) for w in waves]
        kept = [e for e in read if not (e.repo == repo and e.wave in waves)]
        self._save_exports(path, [*kept, *new], read)

    def _mark(self, repo: str, pr: int, *, merged: bool = False, closed: bool = False) -> None:
        """Mark every entry carrying export PR *pr* merged (or closed): a PR covers all
        its waves, so all of them move together."""
        path = self.target / "judgements.yaml"
        read = load_judgements(path).exports
        update = {"merged": True} if merged else {"closed": True}
        marked = [e.model_copy(update=update) if (e.repo, e.pr) == (repo, pr) else e for e in read]
        self._save_exports(path, marked, read)

    @staticmethod
    def _save_exports(path: Path, exports: list[Export], read: list[Export]) -> None:
        try:
            save_exports(path, exports, read=read)
        except TriageError as exc:
            _fail(str(exc))

    def _export_failed(self, wave: str, message: str) -> str:
        """A git or forge write of the export failed (gh#1025): as a refused archive
        merge (gh#921), reported in full once per wave and cause and tried again on a
        later pass; `--once` exits 1. Not a refusal: the export stays owed, not blocked."""
        self.failed_write = True
        self._export_failures += 1
        key = f"export\0{wave}\0{message}"
        if key in self.reported:
            return "stopped again (reported above)"
        self.reported.add(key)
        return f"stopped: {message}"

    def _export(self, action: Action, facts: Facts, repo: str, wave: str) -> str:
        """§I: export the state into a worktree of `origin/<default>`, commit only
        `<path>/<scope>/`, force-push the wave's export branch and open a ready PR.
        A repo-side root that a symlink or a `..` would take outside the worktree is
        refused before any write (a warn; the drive goes on). A git or forge write
        that fails stops the export for this pass; a later pass tries again."""
        config = facts.config_for(repo).export
        assert config is not None
        checkout = self.checkout(repo)
        where = self.target / "export" / wave
        branch = export_branch(wave)
        try:
            checkout.fetch()
            default = checkout.default_branch()
            if (where / ".git").exists():  # a pass that died left it: driver-owned
                checkout.remove_worktree(where)
            if where.exists():  # fr's own scratch, not a worktree: replaced (p4-r10)
                shutil.rmtree(where)
            worktree = checkout.add_worktree(where, f"origin/{default}")
        except (TriageError, OSError) as exc:
            return self._export_failed(wave, f"export wave {wave}: {exc}")
        try:
            rel = f"{config.path}/{check_scope_name(self.scope.name)}"
            try:
                report = export_state(self.target, worktree.path, rel)
            except TriageError as exc:
                self._export_refusals += 1
                return f"refused, nothing committed or pushed: {exc}"
            try:
                # Never forced past the repo's .gitignore (p4-r9): named, not staged.
                left = worktree.ignored([f"{rel}/{p}" for p in report.copied])
                head = worktree.commit_paths(
                    [rel], f"chore(triage): export the triage state after wave {wave}"
                )
            except TriageError as exc:
                return self._export_failed(wave, f"export wave {wave}: {exc}")
            note = _ignored_note(left)
            if left:
                _say(action_line(Action("warn", repo, note, wave=wave)))
            suffix = f"; {_ignored_note(left, short=True)}" if left else ""
            if head is None:
                self._record_export(repo, _covers(action), pr=None)
                if action.pr is not None:  # p4-r13: left open, said once (never recorded)
                    stale = (f"export PR #{action.pr} on {branch} is stale: the state on the "
                             "default branch is already current; it can be closed")  # fmt: skip
                    _say(action_line(Action("warn", repo, stale, pr=action.pr, wave=wave)))
                return f"{rel} is unchanged; recorded with no PR{suffix}"
            try:
                worktree.push(branch, force=True)
            except TriageError as exc:
                return self._export_failed(wave, f"export wave {wave}: {exc}")
            if action.pr is not None:  # reuse (p4-r12): the PR now carries OUR commit
                self._record_export(repo, _covers(action), pr=action.pr, head=head)
                return f"pushed {head[:12]} to {branch}; reused PR #{action.pr}{suffix}"
            client = self.client(facts, repo)
            try:
                number = client.pr_create(
                    repo,
                    head=branch,
                    base=default,
                    title=f"chore(triage): triage state after wave {wave}",
                    body=(
                        f"The triage state of `{self.scope.target}` once wave {wave} finished, "
                        f"exported under `{rel}/` by `fr triage batch drive` "
                        "(`fr triage state import` reads it back).\n\n"
                        "Facts and rendered pages are not exported; they are rebuilt."
                        + (f"\n\n{_ignored_count(left)}" if left else "")
                    ),
                )
            except UnsupportedForgeOperation as exc:
                _fail(str(exc))
            except FORGE_ERRORS as exc:
                return self._export_failed(
                    wave, f"export wave {wave}: the forge refused the PR: {exc}"
                )
            self._record_export(repo, _covers(action), pr=number, head=head)  # the pin
            return f"opened PR #{number} from {branch} at {head[:12]}{suffix}"
        finally:
            try:
                checkout.remove_worktree(where)
            except TriageError:
                pass  # scratch: the next export replaces it

    def _export_merge(self, action: Action, facts: Facts, repo: str, wave: str) -> str:
        """Merge the export PR at its RECORDED head (`action.head`, which step 3b sets
        from the export record and only when the live head equals it), never the live
        one: nobody reviews this PR, so a commit someone else pushed to its branch must
        not reach the default branch (p4-sec-unpinned-merge). Then record it merged."""
        ctx = self.merge_ctx(facts, repo)
        assert action.pr is not None
        try:
            ctx.client.pr_merge(repo, action.pr, head_sha=action.head, method=ctx.method)
        except UnsupportedForgeOperation as exc:
            _fail(str(exc))
        except FORGE_ERRORS as exc:
            return self._export_failed(
                wave, f"export PR #{action.pr}: the forge refused the merge: {exc}"
            )
        self._mark(repo, action.pr, merged=True)
        return f"merged export PR #{action.pr} at {action.head[:12]}"


def _ignored_note(paths: tuple[str, ...], *, short: bool = False) -> str:
    """What the export left out because the target repo ignores it (p4-r9), the first
    few named: the warn's words, or (*short*) the export line's."""
    n = len(paths)
    shown = ", ".join(paths[:5]) + (f", and {n - 5} more" if n > 5 else "")
    files = "file" if n == 1 else "files"
    if short:
        return f"{n} durable {files} ignored by the target repo not exported: {shown}"
    verb = "is" if n == 1 else "are"
    return f"{n} durable {files} {verb} ignored by the target repo and were not exported: {shown}"


def _ignored_count(paths: tuple[str, ...]) -> str:
    """The PR body's line about ignored files: a count, never a name (p4-r14). The
    body is public; the names stay in the local line and warn."""
    n = len(paths)
    if n == 1:
        return "1 durable file is ignored by this repo and was not exported."
    return f"{n} durable files are ignored by this repo and were not exported."


def _covers(action: Action) -> tuple[str, ...]:
    """The waves an export or adoption records: every one its PR covers (R13)."""
    return action.covers or ((action.wave,) if action.wave is not None else ())


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
    repo: str,
    batch: Batch,
    launch: Launch,
    *,
    run: str | None,
    checkout: Path,
    group: str | None = None,
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
    if group:
        payload["group"] = group
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
    workspace_prefix: Annotated[
        str,
        typer.Option(
            "--workspace-prefix",
            help="Prefix of the runner workspace each wave's sessions open in "
            "(`<prefix>-wave-<n>`).",
        ),
    ] = DEFAULT_WORKSPACE_PREFIX,
    keep_sessions: Annotated[
        bool,
        typer.Option(
            "--keep-sessions",
            help="Leave a finished batch's batch and close-out sessions open.",
        ),
    ] = False,
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
    if not workspace_prefix.strip():
        _fail("--workspace-prefix must not be blank")
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
        scope,
        target,
        named=batch_ids,
        checkouts=checkouts,
        max_inflight=max_inflight,
        yes=yes,
        workspace_prefix=workspace_prefix,
        keep_sessions=keep_sessions,
        scope_args=triage_kanban_cmd.scope_args(repo, org, dir_override),
    )
    restart: str | None = None
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
                if driver.observation_owed():
                    continue  # the last wave's transition is seen only by one more pass
                return
            if driver.restart_to is not None:
                restart = driver.restart_to
                break
            if summary.stalled:
                _say(_stalled_line(blocked, driver.held_by))
                raise typer.Exit(code=3)
            _sleep(interval)
    if restart is not None:
        # A `post_merge` installed a newer fr: this process still runs the code it
        # imported, which reads the state and config the new one writes (gh#998,
        # gh#964). It finished its pass; the lock is released, so the new process,
        # with the same pid and arguments, takes it as a fresh driver would.
        _say(f"restart: post_merge installed fr {restart} (this driver runs {__version__}); "
             "restarting on it")  # fmt: skip
        try:
            _exec([sys.executable, "-m", "fr", *sys.argv[1:]])
        except OSError as exc:  # the interpreter moved under a reinstall: say so, not a trace
            _fail(
                f"could not restart on fr {restart} ({exc}); every pass so far is saved, "
                "so start `fr triage batch drive` again with the same arguments",
                code=1,
            )
