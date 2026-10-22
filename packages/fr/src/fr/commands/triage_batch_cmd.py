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
import re
import shlex
import shutil
import sys
import tempfile
import time
import uuid
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager, nullcontext, suppress
from dataclasses import asdict, dataclass, replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Annotated, Any, NamedTuple
from urllib.parse import urlparse

import typer
import yaml
from pydantic import ValidationError
from rich.markup import escape

from fr import __version__
from fr.acceptance.ci import CI_CONFIG_PATHS
from fr.artifacts.atomic import write_text_atomic
from fr.commands import triage_cmd, triage_kanban_cmd
from fr.commands.triage_cmd import (
    DirOpt,
    OrgOpt,
    QuotaFloorOpt,
    RepoOpt,
    WorkspaceOpt,
    _load_state,
    _scope,
    _sync_with_ref,
    batch_app,
    collect_into,
    console,
    drive_lock_dir,
    err_console,
    fetch_now,
    plan_paced_pass,
    push_now,
    rate_limit_reason,
    resolve_state_dir,
)
from fr.commands.triage_kanban_cmd import _fail, probe_item, try_load
from fr.commands.triage_kanban_cmd import load_runner as kanban_load_runner
from fr.ghclient import MERGE_METHODS, BaseRules, GhClient, QueueState, UnsupportedForgeOperation
from fr.hostclient import FORGE_ERRORS, client_for_url
from fr.isolation.adopt import (
    bind_session,
    enter_workspace,
    reusable_workspace,
    session_worktree,
    workspace_containing,
    workspace_path,
)
from fr.isolation.rename import IsolationError, rename_branch
from fr.labels import APPROVED_FR, FR_AWAITING_LIVE, FR_IN_PROGRESS, held_gates, passed_gates
from fr.models import REPO_MODELS_REL, default_models_path, load_models, resolved_config
from fr.services import ServicesError, require_tracker
from fr.services.resolve import resolve_services
from fr.triage import batch_closeout as collected
from fr.triage.approval import (
    ApprovalVerdict,
    EventWriter,
    approval_verdict,
    ensure_approval_label,
    facts_without_label,
    is_approved,
    reaches,
    settle_approvals,
)
from fr.triage.batch import (
    CLOSED_OUT,
    QueueEntry,
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
    effective_handle,
    foreign_batch_prs,
    last_dispatch,
    lifecycle_events,
    mixed_themes,
    parse_refs,
    pr_open_queue,
    recorded_branch,
    resolve_launch,
    resolve_ref,
    save_batches,
    save_closeouts,
    save_exports,
    session_state,
    suggest,
    withdrawal_body,
    withdrawn_already,
)
from fr.triage.batch_dispatch import (
    CLOUD_PREFLIGHT_RUNNERS,
    DISPATCHABLE,
    LIVE_STAGES,
    NO_APPROVAL_LINE,
    TRIAGE_CONFIG_PATH,
    archive_conflict_brief,
    check_config_fresh,
    conflict_brief,
    dispatch_comment,
    dispatched_already,
    live_reservations,
    red_brief,
    render_brief,
    worker_remedy,
)
from fr.triage.batch_drive import (
    ARCHIVE_PREFIXES,
    DEFAULT_MAX_INFLIGHT,
    DEFAULT_WORKSPACE_PREFIX,
    EXPORT_KINDS,
    RUNS_DIR,
    STALE_CLOSEOUT,
    Action,
    ChecksVerdict,
    GateLedger,
    IdleSession,
    LivePr,
    Snapshot,
    Summary,
    action_line,
    archive_conflict_decision,
    archive_conflict_item_id,
    attributed,
    awaiting_unlabelled,
    checks_verdict,
    closeout_brief,
    closeout_due,
    closeout_event,
    closeout_item_id,
    closeout_of,
    collected_candidate,
    collected_item_id,
    collected_name,
    collected_used,
    conflict_decision,
    conflict_item_id,
    default_selection,
    drive_pass,
    export_branch,
    export_target,
    export_wave_of,
    fact_ledger_unknown,
    fact_ledgers,
    find_run,
    finished_waves,
    fresh_conflicts,
    housekeeping_branch,
    idle_session,
    is_archived,
    is_finished,
    last_enqueue,
    marker_of,
    red_decision,
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
    _approved_and_ready,
    choose_method,
    describe,
    merge_ready,
    plan_queue,
    pr_checks_verdict,
    run_queue,
    update_failing,
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
from fr.triage.claims import Claim, expired, held_line, held_map, held_members, taken_keys
from fr.triage.claims import stale as claim_stale
from fr.triage.cursor import read_cursor
from fr.triage.dedupe import candidates
from fr.triage.drive_lock import DRIVE_LOCK, lock_holder
from fr.triage.drive_lock import lock_text as _lock_text
from fr.triage.driver import HOST, Driver, Mailbox, driver_of_holder
from fr.triage.errors import TriageError
from fr.triage.gitseam import Checkout, GitError
from fr.triage.lease import acquire, load_lease, mark_pass, release
from fr.triage.ledger import LedgerRead, closeout_read, gated_rows_at
from fr.triage.merge_stops import (
    MergeStop,
    archive_stop_key,
    clear_stop,
    export_stop_key,
    record_stop,
)
from fr.triage.model import (
    ApprovalEvent,
    ArchiveConflictEvent,
    Batch,
    BatchEvent,
    CancelEvent,
    ClaimsReleasedEvent,
    CloseoutEvent,
    CloseoutHandbackEvent,
    CloseoutHoldEvent,
    CollectedCloseout,
    ConflictDelivery,
    ConflictEvent,
    CursorPosition,
    CursorReader,
    DispatchEvent,
    EnqueueEvent,
    Export,
    Facts,
    Judgements,
    Launch,
    PostMergeEvent,
    PullRequest,
    RedHandbackEvent,
    ReplacementEvent,
    Scope,
    UpdateEvent,
    load_judgements,
    load_scope_facts,
)
from fr.triage.operation_lock import replacement_scope_lock
from fr.triage.pacing import Pacer
from fr.triage.privacy import VisibilityUnreadable, guard_write
from fr.triage.probe import PassPlan
from fr.triage.quota import Pace
from fr.triage.render import plural
from fr.triage.scope_config import load_durable, load_scope_config, scope_id
from fr.triage.state_sync import check_scope_name, export_state
from fr.verification.labels import GATE_PASS_MARKER, pass_gate

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


def _skip_held(env: ClaimEnv, queue: Sequence[QueueEntry]) -> list[QueueEntry]:
    """R7 for `batch merge` with no ids: print `skipped <batch>: held by <scope>` for each
    batch another scope holds a member of, and return the rest."""
    held = held_map(env.facts, env.me)
    kept: list[QueueEntry] = []
    for e in queue:
        found = held_members(e.batch.ids, held)
        if not found:
            kept.append(e)
            continue
        scopes = ", ".join(dict.fromkeys(h.signer for _, h in found))
        console.print(f"skipped {e.batch.id}: held by {scopes}", markup=False, soft_wrap=True)
    return kept


def _admit_held(env: ClaimEnv, keys: Iterable[str], what: str) -> list[tuple[str, Claim]]:
    """R5 for `batch create` / `batch edit`: exit 2, nothing written, when another scope
    holds any of *keys* with a FRESH claim. A member whose foreign claim is stale (R8;
    expired included) is admitted (gh#1120, gh#1123): `claim take` needs it in one of this
    scope's batches, and the take stays the operator's explicit step. Admitting writes no
    claim, and R6 still keeps every action off the batch until the take. Returns the
    admitted held members."""
    found = held_members(keys, held_map(env.facts, env.me))
    now = _now()
    fresh = [(k, h) for k, h in found if not claim_stale(h, now)]
    if fresh:
        _fail(
            f"{what}: another triage scope holds "
            + "; ".join(held_line(k, h, now) for k, h in fresh)
        )
    return found


def _say_takes(batch_id: str, held: Iterable[tuple[str, Claim]]) -> None:
    """The take each admitted held member is waiting for (gh#1120, gh#1123)."""
    now = _now()
    for k, h in held:
        state, flag = ("an expired", "") if expired(h, now) else ("a stale", " --stale")
        console.print(
            f"  {k} is held by {state} claim of {h.signer}; take it over with "
            f"`fr triage claim take {k} --batch {batch_id}{flag} --yes`",
            markup=False,
            soft_wrap=True,
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
            console.print(f"  {op.kind} {op.label}", markup=False)
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


def event_writer(target: Path, facts: Facts, *, read_errors: bool = False) -> EventWriter:
    """Append one event to a batch through the one judgements writer (`_write`),
    re-reading the file each time, so a write never races an earlier one of the same
    command (merge-train-safety §A, §B). An event older than the batch's last is
    stamped at that time: a skewed clock never breaks the time-order rule. The driver
    passes *read_errors*, so an unreadable visibility skips its pass (gh#1145)."""

    def write(batch_id: str, event: BatchEvent) -> None:
        judgements = load_judgements(target / "judgements.yaml")
        batch = _find(judgements.batches, batch_id)
        if batch.events and event.at < batch.events[-1].at:
            event = event.model_copy(update={"at": batch.events[-1].at})
        new = batch.model_copy(update={"events": [*batch.events, event]})
        _write(
            target, _replace(judgements.batches, new), facts, read=judgements.batches,
            read_errors=read_errors,
        )  # fmt: skip

    return write


def update_recorder(
    writer: EventWriter, batch_of: Callable[[int], str | None]
) -> Callable[[int, str, str, str], None]:
    """`MergeContext.on_update` for a writer: an `update` event on the PR's batch (R8)."""

    def record(pr: int, before: str, after: str, base: str) -> None:
        batch_id = batch_of(pr)
        if batch_id is not None:
            event = UpdateEvent(
                kind="update", at=datetime.now(UTC), pr=pr, head_before=before,
                head_after=after, base=base,
            )  # fmt: skip
            writer(batch_id, event)

    return record


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
    guard_write(
        added_keys(batches, read),
        scope=facts_scope(facts),
        facts=facts,
        state_repo=load_durable(target).state_repo,
        client_for=lambda r: make_client(f"https://{_host_of(facts, r)}/{r}"),
    )
    save_batches(target / "judgements.yaml", batches, read=read, dry_run=dry_run)


def added_keys(batches: Sequence[Batch], read: Sequence[Batch]) -> list[str]:
    """The keys a write adds to a batch or a wave (cloud-triage R8): every member of a new
    batch, each new member of an existing one, and every member of a batch whose wave was
    set or moved."""
    before = {b.id: b for b in read}
    added: list[str] = []
    for batch in batches:
        old = before.get(batch.id)
        if old is None:
            added += batch.ids
            continue
        added += [k for k in batch.ids if k not in old.ids]
        if batch.wave is not None and batch.wave != old.wave:
            added += [k for k in batch.ids if k in old.ids]
    return list(dict.fromkeys(added))


def facts_scope(facts: Facts) -> Scope:
    """The scope *facts* were collected for (every loader checked it matches)."""
    if facts.kind == "repo":
        return Scope(kind="repo", target=facts.repos[0])
    if facts.kind == "group":
        return Scope.group(facts.repos)
    return Scope(kind="org", target=facts.scope)


def _write(
    target: Path,
    batches: list[Batch],
    facts: Facts,
    *,
    read: list[Batch],
    dry_run: bool = False,
    read_errors: bool = False,
) -> None:
    """`_save`, with a refusal as exit 2. With *read_errors* (the driver's writes), an
    unreadable visibility is a `ForgeReadError`, so a looping drive skips the pass and
    retries as it does for the lease and the save (gh#1145); a leak still exits 2."""
    try:
        _save(target, batches, facts, read=read, dry_run=dry_run)
    except VisibilityUnreadable as exc:
        if read_errors:
            raise ForgeReadError(str(exc), code=2) from exc
        _fail(str(exc))
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
    workspace: WorkspaceOpt = None,
) -> None:
    """Print one line per batch in judgements.yaml, or "no batches"."""
    scope = _scope(repo, org)
    path = resolve_state_dir(scope, dir_override, workspace) / "judgements.yaml"
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
    workspace: WorkspaceOpt = None,
) -> None:
    """Add a proposed batch of judged issues. With --wave, its claims are owed (R3)."""
    target, facts, judgements = _load_state(_scope(repo, org), dir_override, workspace)
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
    admitted = _admit_held(env, new.ids, f"batch {new.id!r} cannot be created")
    _write(target, [*judgements.batches, new], facts, read=judgements.batches)
    console.print(f"created batch {new.id} ({plural(len(new.ids), 'issue')})", markup=False)
    _say_takes(new.id, admitted)
    _warn_mixed_themes(new, judgements)
    if new.wave is not None:  # a wave makes claims owed from now (R3)
        free = [k for k in new.ids if k not in dict(admitted)]
        _settle_claims(env, _claim_ops(new, free, facts, env.me), yes=yes)


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
    workspace: WorkspaceOpt = None,
) -> None:
    """Change a proposed batch; past `proposed`, only --order (and, until it merges,
    --wave and --after) may change. Claims follow the change (R3, R5, R10)."""
    if no_wave and wave is not None:
        _fail("--no-wave and --wave contradict each other")
    if no_after and after is not None:
        _fail("--no-after and --after contradict each other")
    target, facts, judgements = _load_state(_scope(repo, org), dir_override, workspace)
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
    admitted = dict(_admit_held(env, checked, f"batch {new.id!r} cannot take these members"))
    _write(target, _replace(judgements.batches, new), facts, read=judgements.batches)
    console.print(f"edited batch {new.id}", markup=False)
    _say_takes(new.id, [(k, h) for k, h in admitted.items() if k in added])
    _warn_mixed_themes(new, judgements)
    owed_before = batch.wave is not None or stage != "proposed"
    owed_after = new.wave is not None or stage != "proposed"
    dropped = [k for k in batch.ids if k not in new.ids]
    ops = [ClaimOp("release", k, batch.id) for k in dropped] if owed_before else []
    if owed_before and not owed_after:  # --no-wave on a proposed batch
        kept = set(taken_keys(new))  # a member the operator took stays owed (gh#1120)
        ops += [ClaimOp("release", k, batch.id) for k in new.ids if k not in kept]
    elif owed_after:
        ops += _claim_ops(new, [k for k in new.ids if k not in admitted], facts, env.me)
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
    workspace: WorkspaceOpt = None,
) -> None:
    """Withdraw a batch: unlabel and comment on each member, append a cancel event."""
    target, facts, judgements = _load_state(_scope(repo, org), dir_override, workspace)
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
    workspace: WorkspaceOpt = None,
) -> None:
    """Print candidate groupings (shared file, theme, pattern). Writes nothing."""
    _, facts, judgements = _load_state(_scope(repo, org), dir_override, workspace)
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
    read_errors: bool = False,
) -> str | None:
    """Fetch, hold the config-freshness rule, and reserve a version (§3.D, §3.I).

    *read_errors*: the driver's boundary (gh#1025). A failed fetch, or main's config
    moving under the pass, raises `ForgeReadError` as the merge path's does, so the
    loop skips the pass; `batch dispatch` keeps its exit code."""
    config = facts.config_for(owner_repo)
    try:
        default = _fresh_config(checkout, facts, owner_repo)
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
    checkout: Checkout, facts: Facts, owner_repo: str, *, hold_unknown: bool = False
) -> str:
    """Fetch, then hold the §3.I rule: the collected `.fr/triage.yaml` must be the
    one on `origin/<default>` now. Returns that ref. The read ignores a top-level
    key this `fr` does not know (R4). *hold_unknown*: a failed fetch or default-branch
    read raises `DefaultBranchUnknown` (the merge path's, R13) rather than a `GitError`."""
    try:
        checkout.fetch()
        default = f"origin/{checkout.default_branch()}"
    except GitError as exc:
        if not hold_unknown:
            raise
        raise DefaultBranchUnknown(owner_repo, exc) from exc
    ignored = check_config_fresh(
        facts.config.get(owner_repo),
        checkout.show(default, TRIAGE_CONFIG_PATH),
    )
    if ignored:
        err_console.print(
            f"[yellow]warning:[/yellow] {escape(owner_repo)}: ignoring {TRIAGE_CONFIG_PATH} "
            f"keys this fr does not know: {escape(', '.join(ignored))} (written for a newer fr)",
            soft_wrap=True,
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
    event = last_dispatch(batch)
    assert event is not None
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


def _replacement_live_gate(batch: Batch, facts: Facts, repo: str, client: GhClient) -> None:
    """Fresh forge reads are mandatory even with no cached PR; unknown is refusal."""
    event = last_dispatch(batch)
    assert event is not None
    try:
        records = client.list_prs_by_head(repo, event.branch)
        if not isinstance(records, list) or any(
            not isinstance(r, dict) or not isinstance(r.get("number"), int) for r in records
        ):
            raise ValueError("unreadable branch PR lookup")
        cached = batch_pr(batch, facts)
        numbers = {r["number"] for r in records}
        if cached:
            numbers.add(cached.number)
        if len(numbers) > 1:
            raise ValueError("ambiguous branch PR identity")
        for number in numbers:
            live = client.pr_view(repo, number)
            if live.get("state") != "OPEN" or live.get("head_ref") != event.branch:
                raise ValueError("live PR is merged/closed/unknown or its branch changed")
        if any(r.get("isCrossRepository") is not False for r in records):
            raise ValueError("PR origin is foreign or unreadable")
    except Exception as exc:  # noqa: BLE001 - unknown forge state is never permission to stop
        _fail(f"replacement live forge gate refused: {exc}")


def _replacement_transaction(
    target: Path,
    facts: Facts,
    batch_id: str,
    *,
    checkout_path: Path | None,
    harness: str | None,
    model: str | None,
    reason: str,
    yes: bool,
    repair: bool,
    recover: bool = False,
    driver_lock_target: Path | None = None,
) -> None:
    if importlib.util.find_spec("fr_dispatch") is None:
        _fail(DISPATCH_INSTALL_HINT)
    from fr_dispatch.launch import validate_model
    from fr_dispatch.protocols import ReplacementRequest, ReplacementResult, SessionReplacer

    path = target / "judgements.yaml"
    j = load_judgements(path)
    batch = _find(j.batches, batch_id)
    original = last_dispatch(batch)
    if original is None or derive_batch_stage(batch, facts) not in LIVE_STAGES:
        _fail("replacement requires a dispatched or pr-open unmerged batch")
    repo = batch_repo(batch, facts)
    if repo is None:
        _fail("batch repo is absent from scope facts")
    checkout = _open_checkout(checkout_path, repo)
    dispatch_index = batch.events.index(original)
    audits = [e for e in batch.events[dispatch_index + 1 :] if isinstance(e, ReplacementEvent)]
    latest = audits[-1] if audits else None
    source_pane = effective_handle(batch) or original.handle
    if original.runner != "herdr":
        _fail("replacement requires the original herdr runner")
    runner = load_runner(original.runner)
    if not isinstance(runner, SessionReplacer):
        _fail("runner does not implement SessionReplacer")
    pending = None
    if repair:
        if harness is not None or model is not None:
            _fail("--repair uses the persisted target; do not supply --harness/--model")
        pending = runner.replacement_pending(batch_item_id(repo, batch.id), source_pane)
        if pending and (latest is None or pending.attempt != latest.attempt):
            if pending.branch != original.branch or pending.checkout != str(
                checkout.main_worktree()
            ):
                _fail("pending descriptor does not match original branch/checkout")
            old = Launch(runner="herdr", harness=pending.old_harness, model=pending.old_model)
            new = Launch(runner="herdr", harness=pending.harness, model=pending.model)
            attempt = pending.attempt
            latest = None  # prepared before the attempt write; still no input replay
        elif latest:
            old, new, attempt = latest.old, latest.new, latest.attempt
        else:
            _fail("no replacement attempt or pending descriptor to repair")
        recover = pending.recover if pending else bool(latest and latest.recover)
    else:
        if runner.replacement_pending(batch_item_id(repo, batch.id), source_pane):
            _fail("pending replacement; use --repair --reason <inspection> --yes")
        if latest and latest.result != "success" and not latest.reconciled:
            _fail("unreconciled replacement; use --repair --reason <inspection> --yes")
        old = resolve_launch(
            batch, facts.config_for(repo), orchestrator=_orchestrator(checkout.path)
        ).launch
        if harness is not None and harness != old.harness and model is None:
            _fail("harness change requires an explicit --model")
        new = old.model_copy(
            update={
                "harness": harness if harness is not None else old.harness,
                "model": model if model is not None else old.model,
            }
        )
        if new == old and not recover:
            _fail("replacement is a no-op")
        attempt = uuid.uuid4().hex
    if original.runner != "herdr" or old.runner != "herdr" or new.runner != "herdr":
        _fail("replacement requires the original herdr runner; runner changes are unsupported")
    if new.harness not in {"claude", "opencode"} or not new.model or not new.model.strip():
        _fail("unsupported harness or empty model")
    validate_model(str(new.harness), new.model)
    source_pane = pending.pane if pending else latest.pane if repair and latest else source_pane
    op = runner.replacement_session(
        ReplacementRequest(
            batch_item_id(repo, batch.id),
            source_pane,
            latest.name if repair and latest else pending.name if pending else "",
            original.branch,
            str(checkout.main_worktree()),
            str(old.harness),
            str(old.model),
            str(new.harness),
            str(new.model),
            attempt,
            recover=recover,
            target_pane=pending.target_pane
            if pending
            else latest.target_pane
            if repair and latest
            else None,
        )
    )
    repair_line = (
        f"fr triage batch replace {batch.id} --repair --reason <inspection> --yes "
        f"--dir {shlex.quote(str(target))} "
        f"--checkout {shlex.quote(str(checkout.path))} --repo {repo}"
    )
    # Serialise recovery against a newly starting local driver as well as scope/panes.
    with (
        drive_lock(driver_lock_target or target) if recover and yes else nullcontext(),
        op.ownership() if yes else nullcontext(),
    ):
        if recover:
            lease = load_lease(target)
            if lease and not lease.expired(datetime.now(UTC)):
                _fail(f"recovery refused: live scope driver lease ({lease.holder})")
        _replacement_live_gate(
            batch, facts, repo, make_client(f"https://{_host_of(facts, repo)}/{repo}")
        )
        if repair:
            result = op.reconcile()
            if latest and latest.result == "success" and not result.ok:
                _fail("committed batch success no longer matches live target; inspect both stores")
            if latest and latest.result == "failure" and latest.reconciled and result.ok:
                _fail("committed batch failure disagrees with live target; inspect both stores")
        else:
            op.inspect()
        console.print(
            f"{'repair' if repair else 'recover' if recover else 'replace'} batch {batch.id}: "
            f"{old.harness}/{old.model} → {new.harness}/{new.model}; "
            f"pane {source_pane}; branch {original.branch}",
            markup=False,
        )
        if recover:
            console.print(
                "fresh pane; HOLD: acknowledge/report only; separate operator release required",
                markup=False,
            )
            console.print(
                f"item {batch_item_id(repo, batch.id)}; name {op.name}; "
                f"existing workspace {getattr(op, 'workspace', 'inspect branch workspace')}; "
                f"dirty work preserved: {getattr(op, 'dirty', 'inspect')}; repair: {repair_line}",
                markup=False,
            )
        if not yes:
            console.print("nothing written or sent; re-run with --yes", markup=False)
            return

        def write(event: ReplacementEvent, success: bool = False) -> None:
            nonlocal j, batch
            changed = batch.model_copy(
                update={
                    "events": [*batch.events, event],
                    "launch": new if success else batch.launch,
                }
            )
            j = save_batches(path, _replace(j.batches, changed), read=j.batches)
            batch = _find(j.batches, batch.id)

        outcome: ReplacementResult | None = None

        def audit(status: str, detail: str = "", reconciled: bool = False) -> ReplacementEvent:
            return ReplacementEvent.model_validate(
                {
                    "kind": "replacement",
                    "at": _now_after(batch),
                    "attempt": attempt,
                    "result": status,
                    "reason": reason,
                    "old": old,
                    "new": new,
                    "handle": source_pane,
                    "pane": source_pane,
                    "name": op.name,
                    "branch": original.branch,
                    "detail": detail,
                    "reconciled": reconciled,
                    "recover": recover,
                    "target_pane": outcome.pane if outcome else getattr(op, "target_pane", None),
                    "session": outcome.session if outcome else None,
                }
            )

        try:
            if not repair:
                # Validate compare-write BEFORE descriptor preparation; prepared alone can
                # be reconciled manually but no pane input has occurred at that boundary.
                save_batches(path, j.batches, read=j.batches, dry_run=True)
                op.prepare()
                write(audit("attempt"))
                result = op.execute()
            outcome = result
            if not (
                repair
                and latest
                and (
                    latest.result == "success" or (latest.result == "failure" and latest.reconciled)
                )
            ):
                write(
                    audit("success" if result.ok else "failure", result.detail, reconciled=repair),
                    success=result.ok,
                )
            if result.ok or repair:
                op.activate(success=result.ok)
        except Exception as exc:  # noqa: BLE001 - pending stores remain the reconciliation point
            _fail(
                f"replacement metadata/operation failure: {exc}; inspect source/target/shell; "
                f"{getattr(op, 'failure_context', 'inspect persisted checkpoints')}; "
                f"repair: {repair_line}",
                code=1,
            )
        if not result.ok and not repair:
            _fail(
                f"replacement failed at {result.phase}; survivor {result.survivor}: "
                f"{result.detail}; repair: {repair_line}",
                code=1,
            )
        console.print(f"replacement {'reconciled' if repair else 'completed'}", markup=False)


@batch_app.command("replace")
def batch_replace_command(
    batch_id: Annotated[str, typer.Argument()],
    reason: Annotated[str, typer.Option("--reason", help="Required audit reason.")],
    harness: Annotated[str | None, typer.Option("--harness")] = None,
    model: Annotated[str | None, typer.Option("--model")] = None,
    repair: Annotated[bool, typer.Option("--repair")] = False,
    recover: Annotated[bool, typer.Option("--recover")] = False,
    yes: Annotated[bool, typer.Option("--yes")] = False,
    checkout_path: CheckoutOpt = None,
    repo: RepoOpt = None,
    org: OrgOpt = None,
    dir_override: DirOpt = None,
    workspace: WorkspaceOpt = None,
) -> None:
    """Replace a managed batch harness/model in place, or reconcile without replay."""
    if recover and (repair or harness != "opencode" or not model):
        _fail(
            "--recover requires explicit --harness opencode --model provider/model "
            "and cannot use --repair"
        )
    if (
        not reason.strip()
        or (harness is not None and not harness.strip())
        or (model is not None and not model.strip())
    ):
        _fail("--reason, --harness and --model cannot be empty")
    scope = _scope(repo, org)
    target = resolve_state_dir(scope, dir_override, workspace, sync=False, prepare=False)
    if recover:
        from fr.triage.drive_lock import live_driver

        held = live_driver(drive_lock_dir(scope, dir_override))
        if held:
            _fail(f"recovery refused: running scope driver ({held})")
        lease = load_lease(target)
        if lease and not lease.expired(datetime.now(UTC)):
            _fail(f"recovery refused: live scope driver lease ({lease.holder})")
    try:
        with replacement_scope_lock(target) if yes else nullcontext():
            finish = None
            if yes:
                resolve_state_dir(scope, dir_override, workspace, sync=False)
                finish = _sync_with_ref(scope, target, defer_push=False)
            try:
                _, facts, _ = _load_state(scope, target, None, read_only=True)
                _replacement_transaction(
                    target,
                    facts,
                    batch_id,
                    checkout_path=checkout_path,
                    harness=harness,
                    model=model,
                    reason=reason,
                    yes=yes,
                    repair=repair,
                    recover=recover,
                    driver_lock_target=drive_lock_dir(scope, dir_override),
                )
            finally:
                if finish is not None:
                    finish()
    except typer.Exit:
        raise
    except Exception as exc:  # noqa: BLE001 - read/lock/identity refusals send no input
        _fail(f"replacement refused: {exc}")


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
    workspace: WorkspaceOpt = None,
) -> None:
    """Hand a batch to a runner as one fr-goal run, and mark its issues taken."""
    target, facts, judgements = _load_state(_scope(repo, org), dir_override, workspace)
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
    read_errors: bool = False,
    driver: Driver = HOST,
    load: Callable[[str], Runner] | None = None,
    label_seen: set[str] | None = None,
) -> None:
    """The body of `batch dispatch`, callable: one batch, one runner, one dispatch.
    *label_seen* is the caller's set of repos whose approval label was checked already
    (a driver pass's, so R4's at-most-once-per-pass holds); None is this call alone.

    `batch dispatch` and the wave driver share it, so a driver dispatch runs the same
    preflight, version reservation, brief, event write and forge labels. A refusal is
    `typer.Exit` with the verb's own exit code, exactly as at the command line; a
    runner that fails to dispatch raises `RunnerDispatchError`, which each caller
    handles its own way (gh#931).
    *read_errors* is the driver's failed-fetch boundary, a `ForgeReadError` (gh#1025).
    *driver* names the runner (cloud-triage R10): the host keeps `--to`, else the batch's.
    *load* is the driver's own runner cache, so a mailbox runner it opened takes the
    dispatch (cloud-triage §F); `load_runner` otherwise.
    """
    try:
        to = driver.runner_for(batch, to)
    except TriageError as exc:
        _fail(str(exc))
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
        if last_dispatch(batch) is not None:
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
    runner = (load or load_runner)(runner_name)  # step 1
    reserved = _reservation(  # step 2
        checkout,
        facts,
        judgements,
        batch,
        owner_repo,
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
        runner=runner_name,
        remedy=worker_remedy() if runner_name in CLOUD_PREFLIGHT_RUNNERS else None,
    )
    item = _work_item(owner_repo, batch, launch, brief, reserved, checkout.main_worktree(), group)
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

    _write(
        target, _after(event), facts, read=judgements.batches, dry_run=True,
        read_errors=read_errors,
    )  # fmt: skip
    if not runner.can_dispatch(item):
        _fail(f"runner `{runner_name}` does not take run-unit work")
    refusal = runner.preflight([item])
    if refusal:
        _fail(f"runner `{runner_name}` refused: {refusal}")
    if item.id in runner.existing_dispatches([item]):
        _fail(f"runner `{runner_name}` already holds {item.id} live; nothing written")
    _write(
        target, _after(event), facts, read=judgements.batches, dry_run=True,
        read_errors=read_errors,
    )  # fmt: skip
    # The label the operator approves the batch's PR with (merge-train-safety R4).
    ensure_approval_label(
        client, owner_repo, _say, seen=label_seen if label_seen is not None else set()
    )
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
"""The runner `adopt --list` reads on the host when `--to` names none; a driver with a
runner of its own (`Driver.adopt_runner`) reads that one instead (cloud-triage §F)."""

_ADOPTER_METHODS = ("describe", "list_sessions", "adopt")


def _adopter(runner: object) -> bool:
    """Whether *runner* is a `SessionAdopter` (spec 2026-10-06-triage-batch-adopt §E),
    read off its methods: this module imports `fr_dispatch` only inside functions."""
    return all(callable(getattr(runner, m, None)) for m in _ADOPTER_METHODS)


def supersede_comment(new_pr: int, batch: Batch) -> str:
    """The comment on a superseded PR (§C step 2)."""
    return f"Superseded by #{new_pr} — this branch was adopted as batch {batch.id}"


HOLD_LINES = (
    "HOLD: acknowledge this message only. Make no commits, merges, rebases, artifact",
    "migrations, pushes or PR edits, and start no skill or pipeline run. Wait for the",
    "operator's go-ahead.",
)
"""The block that holds an adopted agent until the operator releases it (2026-10-11 R1)."""


def adopt_message(
    batch: Batch,
    item_id: str,
    old: str,
    new: str,
    pr: str | None,
    reserved: str | None,
    *,
    hold: bool = True,
    workspace: Path | None = None,
) -> str:
    """The one message an adopted session's agent gets (R6; 2026-10-11 §A). Held by
    default: the agent acknowledges it and waits. *workspace* names the fr workspace
    of a session adopted from the default branch."""
    lines = [
        f"fr triage batch adopt: this session is now tracked as batch {batch.id} ({item_id}).",
        f"Your branch {old} was renamed to {new}; push to it from now on with "
        f"`git push origin {new}` (its upstream is set). Your push target changed: "
        f"never push {old} again.",
    ]
    if workspace is not None:
        lines[1] = (
            f"Your batch branch is {new}, in the fr workspace {workspace}. Do all further "
            f"work on this batch there, never in the base clone. Publish it only with "
            f"`git push -u origin {new}`; never push {old}."
        )
    elif old == new:
        lines[1] = f"Your branch is {new}; keep pushing to it."
    if pr:
        lines.append(f"The PR is now {pr}; the earlier one was closed as superseded.")
    if reserved:
        lines.append(f"Reserved version for this batch: {reserved}.")
    lines.append(NO_APPROVAL_LINE)
    if hold:
        lines.extend(HOLD_LINES)
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
    driver: Driver = HOST,
    hold: bool = True,
) -> None:
    """The body of `batch adopt` (spec 2026-10-06-triage-batch-adopt §A): every read
    and refusal first, then the plan, then — with *yes* — each step not yet done.
    *driver* names the runner, as for `dispatch_batch` (cloud-triage R10)."""
    try:
        to = driver.runner_for(batch, to)
    except TriageError as exc:
        _fail(str(exc))
    # 1. The batch, its stage, and whether this is a re-run of an adoption (R2, R10).
    owner_repo = batch_repo(batch, facts)
    if owner_repo is None:
        _fail(f"batch {batch.id!r}: its repo {batch.repo_name!r} is not in this scope's facts")
    new = batch_branch(batch)
    old = branch
    lifecycle = lifecycle_events(batch)
    last = lifecycle[-1] if lifecycle else None
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
    except TriageError as exc:
        _fail(str(exc))
    if new == default:
        _fail(f"batch branch {new} is {owner_repo}'s default branch: refusing")
    if old == default:  # 2026-10-11 §B: a session in a base clone moves to a workspace
        _adopt_from_default(
            target, facts, judgements, batch, checkout=checkout, default=default,
            tab=tab, session=session, runner=runner, runner_name=runner_name, probe=probe,
            client=client, owner_repo=owner_repo, recorded=recorded, last=last,
            checkout_path=checkout_path, yes=yes, hold=hold,
        )  # fmt: skip
        return
    try:
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
    reserved, floor, event, after = _adopt_event(
        target, facts, judgements, batch, checkout, owner_repo, recorded=recorded,
        last=last, runner_name=runner_name, tab=tab, new=new, opened=_pr_time(new_pr),
    )  # fmt: skip

    # 6. The plan (R8).
    state: dict[str, Any] = {"pr": new_pr, "event": event, "after": after}

    def _pr_ref() -> str | None:
        pr = state["pr"]
        return f"#{pr['number']} ({pr['url']})" if pr else None

    _say_session(tab, batch, probe, session, runner_name)
    _say(f"  branch: {old} -> {new} in {worktree}")
    for step in renames:
        _say(f"    {step}")
    if old != new and not renames:
        _say("    already renamed")
    if publish:
        _say(f"  remote: publish {new} (git push -u origin {new})")
    elif not remote_new:
        _say(f"  remote: {old} was never pushed; nothing to publish")
    if old_pr is not None and old_view is not None:
        kind = "draft PR" if old_view.get("draft") else "PR"
        if new_pr is None:
            _say(f"  forge: supersede PR #{old_pr['number']} with a new {kind} from {new} into "
                 f"{old_view.get('base_ref')} ({old_view.get('title')!r}), then comment and "
                 f"close #{old_pr['number']}")  # fmt: skip
        else:
            _say(f"  forge: supersede PR #{old_pr['number']} by the open #{new_pr['number']}")
    if remote_old:
        _say(f"  forge: delete remote branch {old}")
    shown_pr = _pr_ref()
    if shown_pr is None and old_pr is not None and new_pr is None:
        shown_pr = "#<new PR>"
    _say_tail(tab, probe, runner, runner_name, recorded=recorded, new=new, reserved=reserved,
              hold=hold, message=adopt_message(batch, probe.id, old, new, shown_pr, reserved,
                                               hold=hold))  # fmt: skip
    if not yes:
        _say("nothing written; re-run with --yes to act")
        return

    # 7. Each step not done yet, in §A.7's order (R10).
    def _not_default(*names: str) -> None:  # refused above; held again at each write
        for name in names:
            if name == default:
                raise RuntimeError(f"{name} is the default branch: refusing to touch it")

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
    steps += _adopt_tail_steps(
        target, facts, judgements, batch, state, tab=tab, runner=runner, probe=probe,
        client=client, owner_repo=owner_repo, recorded=recorded,
        message=lambda: adopt_message(batch, probe.id, old, new, _pr_ref(), reserved,
                                      hold=hold),
    )  # fmt: skip
    _run_adopt_steps(steps, batch=batch, tab=tab, old=old, checkout_path=checkout_path, hold=hold)
    _say(f"adopted tab {tab} as batch {batch.id} on {new}")


def _adopt_event(
    target: Path,
    facts: Facts,
    judgements: Judgements,
    batch: Batch,
    checkout: Checkout,
    owner_repo: str,
    *,
    recorded: bool,
    last: object,
    runner_name: str,
    tab: str,
    new: str,
    opened: datetime | None,
) -> tuple[str | None, datetime | None, DispatchEvent, list[Batch]]:
    """Adopt's step 5, on both paths: the reserved version (R11; a re-run keeps the
    recorded one), the event, its time (§D), and a dry run of its write. Returns
    (reserved, floor, event, the batches once it is appended)."""
    if recorded and isinstance(last, DispatchEvent):
        reserved = last.reserved_version
    else:
        reserved = _reservation(checkout, facts, judgements, batch, owner_repo)
    # Whole seconds, as the forge's createdAt is: a PR opened in the same second as
    # the event is still of it (`of_dispatch`, created >= at). Never before the last event.
    floor = batch.events[-1].at if batch.events else None
    at = _now_after(batch).replace(microsecond=0)
    at = max(at, floor) if floor is not None else at
    if opened is not None and opened < at:  # a re-run: that PR was opened by this adoption
        at = max(opened, floor) if floor is not None else opened
    event = DispatchEvent(
        kind="dispatch", at=at, runner=runner_name, handle=tab, branch=new,
        reserved_version=reserved,
    )  # fmt: skip
    after = _with_event(judgements, batch, event)
    if not recorded:
        _write(target, after, facts, read=judgements.batches, dry_run=True)
    return reserved, floor, event, after


def _say_session(tab: str, batch: Batch, probe: WorkItem, session: Any, runner_name: str) -> None:
    _say(f"adopt tab {tab} as batch {batch.id} ({probe.id})")
    _say(f"  session: {session.label!r} in {session.group or '-'}, agent {session.agent} "
         f"({session.status}); runner {runner_name}")  # fmt: skip


def _say_tail(
    tab: str,
    probe: WorkItem,
    runner: Any,
    runner_name: str,
    *,
    recorded: bool,
    new: str,
    reserved: str | None,
    hold: bool,
    message: str,
) -> None:
    """The plan's last lines on both paths: the tab, the record, the marks, and the
    exact message the agent will get (R4)."""
    _say(f"  runner: rename tab {tab} to {probe.id}, and its agent")
    if recorded:
        _say("  record: the dispatch event is recorded already")
    else:
        _say(f"  record: dispatch event (runner {runner_name}, handle {tab}, branch {new}, "
             f"reserved version {reserved or '(none)'})")  # fmt: skip
    _say(f"  forge: add {FR_IN_PROGRESS.name} and the marker comment on every member")
    if callable(getattr(runner, "message", None)):
        _say(f"  runner: message the agent ({'held' if hold else 'not held'})")
        for line in message.splitlines():
            _say(f"    | {line}")


def _adopt_tail_steps(
    target: Path,
    facts: Facts,
    judgements: Judgements,
    batch: Batch,
    state: dict[str, Any],
    *,
    tab: str,
    runner: Any,
    probe: WorkItem,
    client: GhClient,
    owner_repo: str,
    recorded: bool,
    message: Callable[[], str],
) -> list[tuple[str, Callable[[], object]]]:
    """The steps both adopt paths end with: adopt the tab, record the event (unless a
    re-run recorded it), mark every member, message the agent. *state*["after"] is
    the batches once the event is appended; *message* builds the text when sent."""
    steps: list[tuple[str, Callable[[], object]]] = [
        (f"adopt tab {tab}", lambda: runner.adopt(probe, tab))
    ]
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
        steps.append(("message the agent", lambda: runner.message(probe, message())))
    return steps


def _run_adopt_steps(
    steps: list[tuple[str, Callable[[], object]]],
    *,
    batch: Batch,
    tab: str,
    old: str,
    checkout_path: Path | None,
    hold: bool,
) -> None:
    """Run each step in order; the first failure ends in the stop report, which names
    what was done, what remains and the command that finishes it (R10; 2026-10-11 R9)."""
    done: list[str] = []
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
                f"`fr triage batch adopt {shlex.quote(batch.id)} --tab {shlex.quote(tab)} "
                f"--branch {shlex.quote(old)}"
                f"{f' --checkout {shlex.quote(str(checkout_path))}' if checkout_path else ''}"
                f"{'' if hold else ' --no-hold'} --yes`",
                code=1,
            )
        done.append(what)


def _refuse_agent_elsewhere(cwd: Path, root: Path, new: str) -> None:
    """Refuse a default-branch adopt unless the agent works inside *root* (the main
    worktree) or inside *new*'s own recorded workspace, which a re-run needs (R7). An
    agent in any other worktree, a linked one on its own branch included, was adopted
    with a mistaken `--branch <default>`: name its branch and the rename path."""
    where = cwd.resolve()
    if where == root or root in where.parents:
        return
    mine = workspace_containing(root, where)
    if mine is not None and mine.resolve() == workspace_path(root, new).resolve():
        return
    try:
        theirs = Checkout.at(where)
        if theirs.main_worktree() != root:
            raise TriageError("another repository")
        branch = theirs.head_branch()
    except TriageError:
        _fail(
            f"the agent works in {cwd}, not in this checkout {root}; pass --checkout with "
            "the clone it works in"
        )
    on = f" on {branch}" if branch else " on a detached HEAD"
    hint = (
        f"adopt it with --branch {branch} to rename its branch instead"
        if branch
        else "check out a branch there, or adopt from the default branch in the main worktree"
    )
    _fail(
        f"the agent works in {cwd}{on}, not in this checkout {root} nor in {new}'s fr "
        f"workspace: {hint}"
    )


def _adopt_from_default(
    target: Path,
    facts: Facts,
    judgements: Judgements,
    batch: Batch,
    *,
    checkout: Checkout,
    default: str,
    tab: str,
    session: Any,
    runner: Any,
    runner_name: str,
    probe: WorkItem,
    client: GhClient,
    owner_repo: str,
    recorded: bool,
    last: object,
    checkout_path: Path | None,
    yes: bool,
    hold: bool,
) -> None:
    """`adopt --branch <default>` (spec 2026-10-11-batch-adopt-safety-2 §B, R5–R9): the
    default branch stays where it is, and the session moves to the batch branch's fr
    workspace. Every git read runs in the main worktree; every refusal comes before the
    first write; nothing here writes the default branch, the main worktree's files,
    index or HEAD (R8)."""
    new = batch_branch(batch)
    root = checkout.main_worktree()
    # 1. Refusals (R7), in the spec's order.
    try:
        on = checkout.current_branch()
        if on != default:
            _fail(
                f"the base clone is on {on or 'a detached HEAD'}, not {default} ({root}): "
                f"adopting from the default branch needs {default} checked out there"
            )
        dirty = checkout.dirty_paths()
        if dirty:
            _fail(
                f"the base clone {root} has uncommitted changes: {', '.join(dirty)}. Commit "
                "or stash them first: the workspace is cut from origin, so they would be lost "
                "to the batch"
            )
        checkout.fetch()
        unpushed = checkout.unpushed(default)
        if unpushed:
            _fail(
                f"local {default} has commits origin/{default} lacks: {'; '.join(unpushed)}. "
                "Push or move them first: the workspace is cut from origin, without them"
            )
        if session.cwd:
            _refuse_agent_elsewhere(Path(session.cwd), root, new)
        local = checkout.has_branch(new)
        remote = checkout.remote_branch_exists(new)
        reuse: Path | None = None
        if local or remote:
            ahead = max(
                checkout.ahead(f"refs/heads/{new}", f"origin/{default}") if local else 0,
                checkout.ahead(f"refs/remotes/origin/{new}", f"origin/{default}")
                if remote else 0,
            )  # fmt: skip
            reuse = reusable_workspace(root, new, session.session, ahead=ahead)
            if reuse is None:
                place = "on origin" if remote and not local else "here"
                _fail(
                    f"branch {new} already exists {place}, and is neither an fr workspace of "
                    f"this checkout with no commits beyond origin/{default} nor one this "
                    "session is bound to: refusing"
                )
    except TriageError as exc:
        _fail(str(exc))
    where = reuse or workspace_path(root, new)

    # 2. The version and the event (step 5), then the plan.
    reserved, _floor, event, after = _adopt_event(
        target, facts, judgements, batch, checkout, owner_repo, recorded=recorded,
        last=last, runner_name=runner_name, tab=tab, new=new, opened=None,
    )  # fmt: skip
    state: dict[str, Any] = {"event": event, "after": after, "workspace": where}
    _say_session(tab, batch, probe, session, runner_name)
    if reuse is not None:
        _say(f"  branch: {default} stays; resume workspace {where} on {new}")
    else:
        _say(f"  branch: {default} stays; workspace {where} on {new} from origin/{default}")
    if session.session:
        _say(f"  isolation: bind session {session.session} to the workspace")
    _say_tail(tab, probe, runner, runner_name, recorded=recorded, new=new, reserved=reserved,
              hold=hold, message=adopt_message(batch, probe.id, default, new, None, reserved,
                                               hold=hold, workspace=where))  # fmt: skip
    if not yes:
        _say("nothing written; re-run with --yes to act")
        return

    # 3. The steps (R9: entering is always run, so a re-run resumes the workspace).
    def _enter() -> None:
        if new == default:  # refused above; held again at the one git write
            raise RuntimeError(f"{new} is the default branch: refusing to touch it")
        state["workspace"] = enter_workspace(root, new)

    def _bind() -> None:
        warning = bind_session(root, new, session.session, session.harness or "unknown")
        if warning:
            _say(warning)

    steps: list[tuple[str, Callable[[], object]]] = [(f"enter workspace {where}", _enter)]
    if session.session:
        steps.append((f"bind session {session.session}", _bind))
    steps += _adopt_tail_steps(
        target, facts, judgements, batch, state, tab=tab, runner=runner, probe=probe,
        client=client, owner_repo=owner_repo, recorded=recorded,
        message=lambda: adopt_message(batch, probe.id, default, new, None, reserved,
                                      hold=hold, workspace=state["workspace"]),
    )  # fmt: skip
    _run_adopt_steps(
        steps, batch=batch, tab=tab, old=default, checkout_path=checkout_path, hold=hold
    )
    _say(f"adopted tab {tab} as batch {batch.id} in workspace {state['workspace']} on {new}")


def _scope_driver(
    repo: str | None, org: str | None, dir_override: Path | None, workspace: Path | None
) -> Driver:
    """The driver of the scope `adopt --list` names: the cloud one when a cloud driver
    holds its lease (p5-r7), else the host's; no scope named is the host's, as before."""
    if repo is None and org is None:
        return HOST
    target = resolve_state_dir(_scope(repo, org), dir_override, workspace)
    try:
        current = load_lease(target)
    except TriageError:
        return HOST
    return driver_of_holder(current.holder if current else None)


def _list_sessions(to: str | None, driver: Driver = HOST) -> None:
    """`adopt --list` (R12): every session, with the issue refs in its label. Without
    `--to` it reads the driver's runner (cloud-triage §F), herdr on the host; a default
    runner that adopts nothing skips the listing with a message."""
    name = to or driver.adopt_runner or ADOPT_LIST_RUNNER
    runner: Any = load_runner(name)
    if not _adopter(runner):
        if to is None:
            console.print(
                f"runner {name} cannot adopt sessions (it is no SessionAdopter); "
                "adopt --list skipped",
                markup=False,
                soft_wrap=True,
            )
            return
        _fail(f"runner `{name}` cannot adopt sessions (it is no SessionAdopter)")
    try:
        sessions = runner.list_sessions()
    except Exception as exc:  # the runner's own failure
        _fail(f"runner `{name}` could not list its sessions: {exc}", code=1)
    typer.echo(LIST_HEADER)  # not `console`: rich expands the tabs the columns are split on
    reads = _ListReads()
    for s in sessions:
        typer.echo("\t".join(_session_row(s, reads)))


LIST_HEADER = "\t".join(
    ("TAB", "WORKSPACE", "STATUS", "STATE", "REPO", "BRANCH", "FR WORKSPACE", "PR", "REFS", "LABEL")
)


def _url_host(url: str) -> str:
    m = re.match(r"^(?:[a-z+]+://(?:[^@/]+@)?|[^@/:]+@)([^/:]+)", url.strip())
    return m[1] if m else url


class _ListReads:
    """What one `adopt --list` has read already: a client per host, a PR cell per
    repo+branch and a kind per resolved ref, each failure kept as the answer too, so a
    read that failed is not retried by the next row (R15, R16)."""

    def __init__(self) -> None:
        self._clients: dict[str, Any] = {}
        self._prs: dict[tuple[str, str], str] = {}
        self._kinds: dict[tuple[str, int], str] = {}

    def client(self, url: str) -> Any:
        host = _url_host(url)
        if host not in self._clients:
            try:
                self._clients[host] = make_client(url)
            except Exception as exc:  # one host's client, degrading its rows only
                self._clients[host] = exc
        got = self._clients[host]
        if isinstance(got, Exception):
            raise got
        return got

    def pr_cell(self, url: str, repo: str, branch: str) -> str:
        if (repo, branch) not in self._prs:
            try:
                self._prs[(repo, branch)] = _pr_cell(
                    self.client(url).list_prs_by_head(repo, branch)
                )
            except Exception:  # forge, client or shape: this pair's cell only
                self._prs[(repo, branch)] = "-"
        return self._prs[(repo, branch)]

    def kind(self, url: str, repo: str, number: int) -> str:
        if (repo, number) not in self._kinds:
            try:
                self._kinds[(repo, number)] = self.client(url).ref_kind(repo, number) or "?"
            except Exception:  # incl. UnsupportedForgeOperation: `(?)`
                self._kinds[(repo, number)] = "?"
        return self._kinds[(repo, number)]


def _pr_cell(records: list[dict[str, Any]]) -> str:
    """`#<n> closes a#1,b#2` for the newest OPEN PR of the same repo, else `-`."""
    own = [r for r in records if r.get("state") == "OPEN" and not r.get("isCrossRepository")]
    if not own:
        return "-"
    newest = max(own, key=lambda r: str(r.get("createdAt") or ""))
    closes = ",".join(
        f"{c['repository']['name']}#{c['number']}"
        for c in newest.get("closingIssuesReferences", [])
    )
    return f"#{newest['number']}" + (f" closes {closes}" if closes else "")


def _tilde(path: Path) -> str:
    text, home = str(path), str(Path.home())
    return "~" + text[len(home) :] if text == home or text.startswith(home + os.sep) else text


def _session_row(s: Any, reads: _ListReads) -> list[str]:
    """One listing row (R11–R17); each read that fails leaves its own cells `-`/`(?)`."""
    facts = None
    if s.cwd:
        try:
            facts = Checkout.facts(Path(s.cwd))
        except Exception:  # this row's git read
            facts = None
    state = session_state(
        has_agent=s.agent is not None,
        label=s.label,
        toplevel=facts.toplevel if facts else None,
        branch=facts.branch if facts else None,
        default=facts.default if facts else None,
    )
    repo = facts.repo if facts else None
    branch = facts.branch if facts else None
    workspace = None
    try:
        workspace = session_worktree(s.session) if s.session else None
        if workspace is None and facts is not None:
            workspace = workspace_containing(facts.main_worktree, Path(s.cwd))
    except Exception:  # this row's workspace lookup
        workspace = None
    pr = "-"
    if state == "adoptable" and facts and facts.origin_url and repo and branch:
        pr = reads.pr_cell(facts.origin_url, repo, branch)
    refs = []
    for ref in parse_refs(s.label):
        target = resolve_ref(ref, repo)
        kind = "?"
        if target is not None and facts and facts.origin_url:
            kind = reads.kind(facts.origin_url, target, ref.number)
        refs.append(f"{ref.text()} ({kind})")
    return [
        s.tab,
        s.group or "-",
        s.status,
        state,
        repo or "-",
        branch or "-",
        _tilde(workspace) if workspace else "-",
        pr,
        ", ".join(refs) or "-",
        s.label,
    ]


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
    no_hold: Annotated[
        bool,
        typer.Option(
            "--no-hold", help="Do not tell the agent to wait for the operator's go-ahead."
        ),
    ] = False,
    yes: Annotated[bool, typer.Option("--yes", help="Act; without it, print the plan.")] = False,
    repo: RepoOpt = None,
    org: OrgOpt = None,
    dir_override: DirOpt = None,
    workspace: WorkspaceOpt = None,
) -> None:
    """Put a running session under the wave driver as an existing batch; launches nothing.

    Renames the session's branch to the batch branch (supersede an open PR with one
    from it), labels its tab and agent as the batch's, and records a dispatch. Not the
    driver's `adopt` action, which records a close-out started by hand.
    """
    if list_sessions:
        _list_sessions(to, _scope_driver(repo, org, dir_override, workspace))
        return
    if batch_id is None or tab is None or branch is None:
        _fail("give a batch, --tab and --branch (or --list)")
    target, facts, judgements = _load_state(_scope(repo, org), dir_override, workspace)
    batch = _find(judgements.batches, batch_id)
    adopt_batch(
        target, facts, judgements, batch, tab=tab, branch=branch, to=to,
        checkout_path=checkout_path, yes=yes, hold=not no_hold,
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
    workspace: WorkspaceOpt = None,
) -> None:
    """Merge pr-open batch PRs in the computed order, re-slotting versions (§3.F).

    Blocks in the foreground while the checks run (R4: the required ones, else
    every check; a head with none yet waits, unless the repo declares `ci none`);
    Ctrl-C and re-run resumes at the first unmerged batch.
    """
    if method is not None and method not in MERGE_METHODS:
        _fail(f"--method must be one of {', '.join(sorted(MERGE_METHODS))}, got {method!r}")
    target, facts, judgements = _load_state(_scope(repo, org), dir_override, workspace)
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
    if batch_ids:
        for e in queue:  # R6: a batch another scope holds a member of is never merged here
            _refuse_held(env, e.batch.ids, f"batch {e.batch.id!r} cannot be merged")
    else:  # R7: with no ids, a held batch is skipped, named, and the rest merge
        queue = _skip_held(env, queue)
        if not queue:
            console.print("nothing to merge", markup=False)
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
    try:  # R14: once per command, read before anything merges
        ctx.rules = client.base_rules(owner_repo, checkout.default_branch())
    except FORGE_ERRORS as exc:
        _fail(f"a forge read failed: {exc}", code=1)
    writer = event_writer(target, facts)

    def record(batch_id: str, event: BatchEvent) -> None:
        writer(batch_id, event)
        ctx.recorded.setdefault(batch_id, []).append(event)

    by_pr = {e.pr.number: e.batch.id for e in queue}
    ctx.on_update = update_recorder(writer, by_pr.get)
    try:
        if yes:  # the label the operator approves with (merge-train-safety R4)
            ensure_approval_label(client, owner_repo, ctx.say, seen=set())
        # The approval gate (merge-train-safety §A, R1-R2): settle under --yes, say what
        # would be settled otherwise, then hold every batch without a valid approval.
        verdicts = settle_approvals(
            client, record, owner_repo, [(e.batch, e.pr.number) for e in queue], ctx.say,
            now=_now(), dry_run=not yes,
        )  # fmt: skip
    except UnsupportedForgeOperation as exc:
        _fail(str(exc))
    # A PR no longer open has no verdict: the plan reports it (already merged, or refused).
    unapproved = [
        e for e in queue if e.batch.id in verdicts and not is_approved(verdicts[e.batch.id])
    ]
    if unapproved and batch_ids:
        names = ", ".join(f"{e.batch.id} (PR #{e.pr.number})" for e in unapproved)
        _fail(
            f"not approved: {names}: fr merges a batch PR only with the operator's "
            f"`{APPROVED_FR.name}` label on it"
        )
    for e in unapproved:
        ctx.say(f"held {e.batch.id}: PR #{e.pr.number} awaits the {APPROVED_FR.name} label")
    queue = [e for e in queue if e not in unapproved]
    if not queue:
        ctx.say("nothing to merge")
        return
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


# ------------------------------------------------- collected close-out (exit-gates R15)


def gate_pass_url(client: GhClient, host: str, repo: str, pr: int, gates: Iterable[str]) -> str:
    """The URL of PR *pr*'s first gate-pass comment for one of *gates* (R15 step 2's
    evidence), else the PR's own URL: a pass recorded with no comment still has a label."""
    wanted = tuple(f"{GATE_PASS_MARKER}{g} -->" for g in sorted(gates))
    for c in client.list_issue_comments(repo, pr):
        if str(c.get("body") or "").lstrip().startswith(wanted) and c.get("id"):
            return f"https://{host}/{repo}/pull/{pr}#issuecomment-{c['id']}"
    return f"https://{host}/{repo}/pull/{pr}"


def _collected_member(
    batch: Batch, facts: Facts, client: GhClient, checkout: Checkout, ref: str, repo: str
) -> collected.Member:
    """One batch as R15 needs it: its run, missing Test Plan steps and passed gates' rows
    from the default branch (`closeout_read`), its passed gates from the merged PR's
    labels, and the gate-pass comment as evidence."""
    branch = recorded_branch(batch)
    read = closeout_read(checkout, ref, branch, repo)
    pr = batch_pr(batch, facts)
    passed = passed_gates(pr.labels or ()) if pr is not None else frozenset()
    evidence = (
        gate_pass_url(client, _host_of(facts, repo), repo, pr.number, passed)
        if passed and pr is not None
        else None
    )
    cited = [i for r in read.rows if r.gate in passed for i in r.issues]
    return collected.Member(
        batch=batch.id, branch=branch, run=read.run, passed=tuple(sorted(passed)),
        evidence=evidence, missing=read.missing,
        closes=collected.issues_to_close(cited, narrowed=read.narrowed),
    )  # fmt: skip


def _closeout_branch(
    repo: str, judgements: Judgements, checkout: Checkout, day: date, given: str | None
) -> str:
    """The branch of this collected close-out: *given* (`--branch`, the driver's brief),
    else the next free one of *day* (no marker, no event and no remote branch names it)."""
    if given:
        return given
    used = collected_used(repo, judgements.batches, judgements.closeouts)
    n = collected.next_collected(used, day)
    while checkout.remote_branch_exists(collected.collected_branch(day, n)):
        n += 1
    return collected.collected_branch(day, n)


def _save_marker(target: Path, branch: str, **fields: Any) -> None:
    """Update the start marker of the close-out on *branch* (R15); `create` fields make one."""
    path = target / "judgements.yaml"
    read = list(load_judgements(path).closeouts)
    create = fields.pop("create", None)
    found = marker_of(branch, read)
    if found is None:
        if create is None:
            return
        out = [*read, create]
    else:
        out = [c.model_copy(update=fields) if c is found else c for c in read]
    try:
        save_closeouts(path, out, read=read)
    except TriageError as exc:
        _fail(str(exc))


def _record_collected(target: Path, facts: Facts, batch_id: str, branch: str, run: str | None,
                      ) -> None:  # fmt: skip
    """R15: the batch's one close-out event, `archive` the shared branch, written once the
    PR carrying it is open; runner and handle are the marker's. Idempotent (a resume)."""
    judgements = load_judgements(target / "judgements.yaml")
    batch = _find(judgements.batches, batch_id)
    if any(isinstance(e, CloseoutEvent) and e.archive == branch for e in batch.events):
        return
    marker = marker_of(branch, judgements.closeouts)
    event_writer(target, facts)(
        batch_id,
        CloseoutEvent(
            kind="closeout", at=_now_after(batch),
            runner=marker.runner if marker else "hand",
            handle=(marker.handle or marker.item) if marker else branch,
            run=run, archive=branch,
        ),
    )  # fmt: skip


def _record_hold(target: Path, facts: Facts, batch_id: str, item: str, reason: str) -> None:
    """R15: a held batch's durable `closeout_hold` event: the driver never collects it
    again; `fr triage batch closeout <id>` retries it."""
    batch = _find(load_judgements(target / "judgements.yaml").batches, batch_id)
    event_writer(target, facts)(
        batch_id,
        CloseoutHoldEvent(kind="closeout_hold", at=_now_after(batch), item=item, reason=reason),
    )


def _resume_or_refuse(
    client: GhClient, checkout: Checkout, repo: str, branch: str, allowed: frozenset[str]
) -> tuple[int, str] | None:
    """p6-r9, p6b-r3: `(PR, head)` to resume when *branch* already carries an open PR that
    is the repo's own by an allowed author (never a fork's); None when the branch is new.
    Any other pushed head is refused by name, with the way out."""
    prs = [p for p in client.list_prs_by_head(repo, branch) if p.get("state") == "OPEN"]
    if prs:
        number = int(prs[0]["number"])
        why = _untrusted(prs[0], allowed)
        if why is not None:
            _fail(f"{branch} already has PR #{number}, which is not the repo's own by an "
                  f"allowed author ({why}): close it, or pass another --branch")  # fmt: skip
        return number, str(prs[0].get("headRefOid") or "")
    if checkout.remote_branch_exists(branch):
        _fail(f"{branch} is already pushed and has no open PR: delete it (`git push origin "
              f"--delete {branch}`) or open its PR, then re-run")  # fmt: skip
    return None


def _record_anchor(
    target: Path, checkout: Checkout, ref: str, branch: str, head: str, pr: int,
    members: Sequence[collected.Member], repo: str,
) -> None:  # fmt: skip
    """R15's trust anchor, written by the verb on the operator's host after the push: the
    pushed head, the members, the exact diff (through gitseam, renames split) and the
    recorded closes. The driver merges without approval only at exactly these."""
    files = sorted(checkout.changed_status(ref, head))
    _save_marker(target, branch, pr=pr, head=head, members=[m.batch for m in members],
                 files=files, closes=list(collected.recorded_closes(members, repo)))  # fmt: skip


_TRANSIENT_READ_ERRORS: tuple[type[Exception], ...] = (GitError, *FORGE_ERRORS)
"""p6b-r9: a git or forge failure reading a batch leaves it owed; never a durable hold."""


def _under_way_line(marker: CollectedCloseout) -> str:
    pushed = f"PR #{marker.pr}" if marker.pr else "not yet pushed"
    return f"collected close-out {marker.item} is under way ({marker.branch}, {pushed})"


@batch_app.command("closeout")
def batch_closeout_command(
    batch_ids: Annotated[
        list[str] | None,
        typer.Argument(help="Batches to close out; default: every landed, ungated, unheld one."),
    ] = None,
    checkout_path: CheckoutOpt = None,
    branch_opt: Annotated[
        str | None,
        typer.Option("--branch", help="The housekeeping branch (the driver's brief names it)."),
    ] = None,
    yes: Annotated[bool, typer.Option("--yes", help="Act; without it, print the plan.")] = False,
    repo: RepoOpt = None,
    org: OrgOpt = None,
    dir_override: DirOpt = None,
    workspace: WorkspaceOpt = None,
) -> None:
    """Close out every landed, ungated batch in ONE housekeeping PR (exit-gates R15).

    Per batch: verify-merge, a passed gate's Test Plan outcomes (`--ran`, the gate-pass
    comment as evidence) and `fr archive --branch <b> --no-issues`; the PR body closes the
    issues a passed gate's rows cite when it merges (never a narrowed one). A batch that
    fails deterministically moves nothing, gets a `closeout_hold` event and is named; the
    verb then exits 1. Naming a held batch retries it. After the push the verb records
    the head, members, diff and closes the driver may merge without approval.
    """
    if branch_opt is not None and collected.collected_name(branch_opt) is None:
        _fail(f"--branch {branch_opt!r} is not a collected close-out branch "
              "(chore/closeout-<YYYY-MM-DD>-<n>)")  # fmt: skip
    target, facts, judgements = _load_state(_scope(repo, org), dir_override, workspace)
    wanted = {b.lower() for b in batch_ids or ()}
    open_markers = [c for c in judgements.closeouts if not (c.merged or c.closed)]
    mine = next((c for c in open_markers if c.branch == branch_opt), None)
    reserved = {b for c in open_markers if c is not mine for b in c.planned}
    owed = collected.closeout_owed(judgements.batches, facts, judgements.closeouts,
                                   named=wanted, reserved=reserved)  # fmt: skip
    if mine is not None:  # the marker's own session: its planned batches still owed
        owed = [b for b in owed if b.id in mine.planned]
    if wanted:
        if missing := sorted(wanted - {b.id for b in owed}):
            under = [c for c in open_markers if c is not mine and wanted & set(c.planned)]
            if under:
                _fail(_under_way_line(under[0]))
            _fail(f"not owed a close-out here (not landed, gated, or closed out): "
                  f"{', '.join(missing)}")  # fmt: skip
        owed = [b for b in owed if b.id in wanted]
    if not owed:
        _say("nothing to close out")
        return
    repos = {batch_repo(b, facts) for b in owed}
    if len(repos) != 1 or None in repos:
        _fail(f"close out one repo's batches at a time (these span "
              f"{', '.join(sorted(map(str, repos)))}): name them, or use --repo")  # fmt: skip
    owner_repo = str(next(iter(repos)))
    if mine is None and (busy := [c for c in open_markers if c.repo == owner_repo]):
        _fail(_under_way_line(busy[0]))  # p6b-r7: one collected close-out per repo
    checkout = _open_checkout(checkout_path, owner_repo)
    client = make_client(f"https://{_host_of(facts, owner_repo)}/{owner_repo}")
    members: list[collected.Member] = []
    unreadable: list[tuple[str, str]] = []
    transient: list[tuple[str, str]] = []
    try:
        checkout.fetch()
        default = checkout.default_branch()
        ref = f"origin/{default}"
        branch = _closeout_branch(owner_repo, judgements, checkout, _now().date(), branch_opt)
        for b in owed:  # p6-r4, p6b-r9: one batch's failure never fails the rest
            try:
                members.append(_collected_member(b, facts, client, checkout, ref, owner_repo))
            except _TRANSIENT_READ_ERRORS as exc:
                transient.append((b.id, f"could not be read now: {exc}"))
            except TriageError as exc:
                unreadable.append((b.id, f"cannot be read for its close-out: {exc}"))
    except UnsupportedForgeOperation as exc:
        _fail(str(exc))
    except TriageError as exc:
        _fail(str(exc))
    except FORGE_ERRORS as exc:
        _fail(f"a forge read failed: {exc}", code=1)
    name = str(collected.collected_name(branch))
    item = collected_item_id(owner_repo, name)
    for line in collected.plan_lines(members, branch, default):
        _say(line)
    for bid, why in [*unreadable, *transient]:
        _say(f"  {bid}: not closed out: {why}")
    if not yes:
        _say("nothing done; re-run with --yes to act")
        return
    runs = {m.batch: m.run for m in members}
    allowed = allowed_authors(owner_repo, facts)
    try:
        resumed = _resume_or_refuse(client, checkout, owner_repo, branch, allowed)
    except FORGE_ERRORS as exc:
        _fail(f"a forge read failed: {exc}", code=1)
    marker = CollectedCloseout(repo=owner_repo, item=item, branch=branch, at=_now(),
                               planned=[b.id for b in owed])  # fmt: skip
    _save_marker(target, branch, create=marker)
    done = False
    try:
        if resumed is not None:  # p6b-r3: membership recomputed, never read from the body
            number, head = resumed
            if not head or not checkout.reach_commit(head, branch):
                _fail(f"PR #{number}'s head on {branch} cannot be read; re-run")
            _record_anchor(target, checkout, ref, branch, head, number, members, owner_repo)
            for m in members:
                _record_collected(target, facts, m.batch, branch, runs.get(m.batch))
            done = True
            _say(f"resumed PR #{number} on {branch}: recorded {', '.join(runs)} at {head[:12]}")
            return
        where = target / "closeout" / branch.removeprefix("chore/")
        try:
            tree = checkout.add_worktree(where, ref)
            tree.start_branch(branch)
            result = collected.execute(
                members, tree=tree, forge=client, repo=owner_repo, default=default,
                branch=branch, record=lambda bid, br: None,
                hold=lambda bid, why: _record_hold(target, facts, bid, item, why),
                say=_say, unreadable=unreadable, transient=transient,
            )  # fmt: skip
            if result.pr is not None and result.head:
                carried = [m for m in members if m.batch in result.done]
                _record_anchor(target, checkout, ref, branch, result.head, result.pr, carried,
                               owner_repo)  # fmt: skip
                for m in carried:
                    _record_collected(target, facts, m.batch, branch, runs.get(m.batch))
        except UnsupportedForgeOperation as exc:
            _fail(str(exc))
        except TriageError as exc:
            _fail(str(exc))
        except FORGE_ERRORS as exc:
            _fail(f"the forge refused: {exc}", code=1)
        done = result.pr is not None
        if result.pr is not None:
            _say(f"opened PR #{result.pr} on {branch}: {', '.join(result.done)}")
        else:
            _save_marker(target, branch, closed=True)  # ended with no archive
        with suppress(TriageError):
            checkout.remove_worktree(where)
        if result.held or result.skipped:
            names = ", ".join(b for b, _ in (*result.held, *result.skipped))
            _say(f"not closed out: {names}; a held one retries with "
                 f"`fr triage batch closeout <id> --yes` once fixed")  # fmt: skip
            raise typer.Exit(1)
    finally:
        if not done:  # p6b-r6: a verb that failed after its marker never wedges the repo
            current = marker_of(branch, load_judgements(target / "judgements.yaml").closeouts)
            if current is not None and not current.head and not current.closed:
                _save_marker(target, branch, closed=True)


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


@dataclass(frozen=True)
class SinglePass:
    """`--once --yes` on the host (gh#1127): *notice* says what one pass leaves undone and
    carries the looping command; *allowed* is `--single-pass`, the operator's word that
    the single pass is deliberate."""

    notice: str
    allowed: bool


def loop_command(
    *,
    batch_ids: list[str] | None,
    scope: Scope,
    scope_args: list[str],
    max_inflight: int,
    interval: int,
    workspace_prefix: str,
    keep_sessions: bool,
    checkout: list[str] | None,
    toplevel: Path | None,
) -> list[str]:
    """The looping `fr triage batch drive` argv a caller should have run instead of one
    pass: the same batches, scope and non-default options, every `--checkout` with an
    absolute path (a single-repo scope's defaulted checkout is *toplevel*, named
    explicitly), `--yes`, and neither `--once` nor `--single-pass`."""
    argv = ["fr", "triage", "batch", "drive", *(batch_ids or []), *scope_args]
    if max_inflight != DEFAULT_MAX_INFLIGHT:
        argv += ["--max-inflight", str(max_inflight)]
    if interval != DEFAULT_INTERVAL:
        argv += ["--interval", str(interval)]
    if workspace_prefix != DEFAULT_WORKSPACE_PREFIX:
        argv += ["--workspace-prefix", workspace_prefix]
    if keep_sessions:
        argv.append("--keep-sessions")
    named = {v.partition("=")[0].lower() for v in checkout or [] if "=" in v}
    for value in checkout or []:
        name, sep, where = value.partition("=")
        argv += ["--checkout", f"{name}={Path(where).expanduser().resolve()}" if sep else value]
    if scope.kind == "repo" and scope.target.lower() not in named and toplevel is not None:
        argv += ["--checkout", f"{scope.target}={toplevel.resolve()}"]
    return [*argv, "--yes"]


def _names_repo(checkout: list[str] | None, repo: str) -> bool:
    return repo.lower() in {v.partition("=")[0].lower() for v in checkout or []}


def _default_toplevel() -> Path | None:
    """The clone a single-repo scope's defaulted `--checkout` names: the working
    directory's git toplevel, None when it is in none."""
    try:
        return make_checkout(None).path
    except TriageError:
        return None


def single_pass_notice(command: list[str]) -> str:
    """What `--once --yes` leaves undone, then the looping *command* (R3)."""
    return (
        "this pass would dispatch, and a single pass leaves no driver behind: ready PRs "
        "stay unmerged, merged batches are not closed out, held dispatches wait for their "
        "wave or --after to clear, and the board is not refreshed. If one pass is "
        "deliberate, add --single-pass; to start the waves, run the looping driver: "
        f"{shlex.join(command)}"
    )


class ForgeReadError(Exception):
    """A read a drive pass depends on failed or timed out (gh#910): the forge's, the
    clone's fetch, `.fr/triage.yaml` on the default branch (gh#921, gh#998), or the state
    repo's visibility, which the lease and the pass's save read (gh#1134). Loop
    mode skips the rest of the pass and reads again after `--interval`; `--once` and
    plan mode exit with *code*, as before."""

    def __init__(self, message: str, *, code: int) -> None:
        super().__init__(message)
        self.code = code


class DefaultBranchUnknown(ForgeReadError):  # noqa: N818 - the spec's name (R13)
    """*repo*'s clone cannot name its default branch because origin cannot answer: the
    fetch, or `checkout.default_branch()`, failed (merge-truth R13, gh#1176). Raised
    ONLY by those two reads in `merge_ctx` and `_base_rules`; every other
    `ForgeReadError` (a merge-methods or config read) behaves as before (gh#921). Each
    caller catches this type alone, holds the repo for the pass and goes on."""

    def __init__(self, repo: str, cause: object) -> None:
        super().__init__(f"{repo} default branch unknown ({cause})", code=2)
        self.repo = repo


def recollect(
    scope: Scope,
    target: Path,
    *,
    only: frozenset[str] | None = None,
    after_write: Callable[[Facts, frozenset[str]], None] | None = None,
    cursor_at: CursorReader | None = None,
) -> Mapping[str, tuple[str, ...]]:
    """Re-collect facts.json through the `Forge` seam, as `fr triage collect` does:
    every stage is derived from facts, so each pass starts here (wave-driver §B).
    Unlike `fr triage collect` it carries known-closed facts over from the
    previous pass instead of viewing every settled judged issue again (gh#911),
    and says what the pass cost. Config is read leniently (gh#998): returns the
    top-level `.fr/triage.yaml` keys dropped, per repo. A forge that fails to answer,
    or any other refusal (a config broken on the default branch, a judgements file
    mid-edit), raises `ForgeReadError`: the loop waits for it to be fixed.

    A paced pass (spec 2026-10-12-quota-pacing R10, R11) reads *only* those repos,
    carrying the rest, and stores its probes' ETags in *after_write*, once facts.json is
    written. Without either, the collect is exactly the unpaced one. *cursor_at* reads
    the run cursor's position at each open batch PR's head (exit-gates R18)."""
    paced: dict[str, Any] = (
        {"only": only, "after_write": after_write}
        if only is not None or after_write is not None
        else {}
    )
    if cursor_at is not None:  # the drive's own `gitseam` reader (exit-gates R18)
        paced["cursor_at"] = cursor_at
    try:
        facts, _, stats = collect_into(scope, target, carry=True, **paced)
    except TriageError as exc:  # ForgeError included
        raise ForgeReadError(str(exc), code=2) from exc
    # A rate limit that did not raise: a repo skipped, a judged key unviewed. The pass ends
    # here, before it plans on facts the exhausted budget left half-read (R2).
    if (reason := rate_limit_reason(facts)) is not None:
        raise ForgeReadError(reason, code=2)
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


def _probe_forge() -> Any:
    """The forge the pass's probes go through (spec 2026-10-12-quota-pacing R8): the
    collect's own. Tests replace it."""
    from fr.commands import triage_cmd

    return triage_cmd.make_forge()


def _pace_forge() -> Any:
    """The forge `/rate_limit` is read through (free, REST under either API); tests replace it."""
    from fr.commands import triage_cmd

    return triage_cmd.make_forge()


def make_pacer(
    target: Path,
    *,
    quota_floor: float | None,
    interval_s: float,
    now: Callable[[], datetime] | None = None,
) -> Pacer:
    """The pacing both adapters share (spec 2026-10-12-quota-pacing): the floor from
    `--quota-floor` or the host file, the adapter `forge.api` names, `pacing.json` in *target*.
    A floor or `forge.api` fr cannot use is refused here, naming where it came from (R6)."""
    return triage_cmd.make_pacer(
        target,
        quota_floor=quota_floor,
        interval_s=interval_s,
        forge=_pace_forge,
        now=now or (lambda: _now()),
    )


def _report_read_failure(driver: _Driver, message: str, action: str) -> None:
    """A forge read failure, reported once per cause until a pass reads cleanly (gh#910)."""
    if message not in driver.read_failures:
        driver.read_failures.add(message)
        err_console.print(f"[yellow]warning:[/yellow] {escape(message)}; {action}", soft_wrap=True)


# A wait that outlives the lease renews it this long before it would lapse (R16).
LEASE_MARGIN = timedelta(minutes=5)
RENEW_RETRY_S = 60


def wait_out(driver: _Driver, pace: Pace) -> None:
    """Sleep until *pace* is over without ever letting the drive's lease lapse (R16): a
    wait that reaches the lease's expiry minus five minutes wakes, renews the lease (the
    state push and its visibility read, the one call a wait makes), and sleeps again."""
    assert pace.until is not None
    left = max(0.0, (pace.until - _now()).total_seconds())
    while left > 0:
        held = load_lease(driver.target) if driver.leased else None
        room = (held.expires - LEASE_MARGIN - _now()).total_seconds() if held else None
        if room is not None and room <= 0:
            try:
                driver.take_lease()
                continue
            except ForgeReadError as exc:  # unreadable visibility: try again a minute on
                _report_read_failure(driver, str(exc), f"renewal retried every {RENEW_RETRY_S}s")
                room = RENEW_RETRY_S
        chunk = left if room is None else min(left, room)
        _sleep(chunk)
        left -= chunk


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
    """`<target>/drive.lock` (pid, start time) for as long as a driver runs (R6). *target*
    is `triage_cmd.drive_lock_dir`: the `--dir`, else `~/.cache/fr/triage/<scope>/` for
    every workspace, so it serialises the drivers of one host across clones (p3-r3).

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
    lifecycle = lifecycle_events(batch)
    cancelled = bool(lifecycle) and isinstance(lifecycle[-1], CancelEvent)
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
                checks="pending",  # the archive step reads an open one's (merge-truth R7)
                head_ref=str(rec.get("headRefName") or head),
                files=tuple(
                    str(f.get("path") if isinstance(f, dict) else f) for f in rec.get("files") or ()
                ),
                trusted=trusted,
            )
        )
    return out


def _judge(
    client: GhClient,
    repo: str,
    pr: LivePr,
    counts: Mapping[str, int] | None,
    ci_none: bool,
    head: str | None = None,
) -> tuple[ChecksVerdict, tuple[str, ...]]:
    """*pr*'s checks verdict, read now: the collected counts stand in for every check
    only while the PR is still at the head they were collected for (*head*, read
    fresh); otherwise every check is read live."""
    if counts is not None and (head is None or head == pr.head):
        return checks_verdict(client.pr_required_checks(repo, pr.number), counts, ci_none=ci_none)
    return pr_checks_verdict(client, repo, pr.number, ci_none=ci_none)


def _pinned(
    client: GhClient,
    repo: str,
    pr: LivePr,
    counts: Mapping[str, int] | None,
    *,
    ci_none: bool,
) -> LivePr:
    """*pr* as the archive step may merge it (p2-r6, security): the head is read, then
    the checks, then the head again, so the verdict is for the head the merge is pinned
    to. A head that moved between the two reads is `pending` this pass, never green; the
    base and `mergeable` are the second read's, for the head it reports."""
    before = client.pr_view(repo, pr.number)
    head = str(before.get("head_oid") or pr.head)
    verdict, failing = _judge(client, repo, pr, counts, ci_none, head)
    after = client.pr_view(repo, pr.number)
    if str(after.get("head_oid") or head) != head:
        verdict, failing = "pending", ()
    return replace(_viewed(pr, after), head=head, checks=verdict, failing=failing)


def _viewed(pr: LivePr, view: Mapping[str, Any]) -> LivePr:
    """*pr* with the base, head and `mergeable` a fresh `pr_view` read reports: the
    verdict and the head it describes come from the same read (p2-r6)."""
    return replace(
        pr,
        base=str(view.get("base_ref") or ""),
        head=str(view.get("head_oid") or pr.head),
        mergeable=str(view.get("mergeable") or ""),
        merge_state=str(view.get("merge_state") or ""),
    )


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
    refusal, a failed git write, a failing or draft PR, one the approval gate holds
    (`unapproved`, `unready`: merge-train-safety §A), a PR no longer open or one
    already merged is stepped over or gone, and the train goes on."""
    if isinstance(outcome, (MergeStopError, GitError)):
        return isinstance(outcome, HeadMovedError)
    return outcome.outcome in ("updated", "pending")


@dataclass(frozen=True)
class LeaseTerms:
    """The lease a driver holds while it runs (cloud-triage R9, §D): whose, for how long
    each renewal lasts, and the driver session's generation (p6-r4; 0 for a host)."""

    identity: str
    duration: timedelta
    generation: int = 0


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
        driver: Driver = HOST,
        statuses: Any = None,
        lease: LeaseTerms | None = None,
        single_pass: SinglePass | None = None,
    ) -> None:
        self.scope, self.target, self.named = scope, target, named
        self.single_pass = single_pass  # `--once --yes` on the host only (gh#1127)
        self.planned_dispatch = False  # the last pass's plan held a dispatch
        self._single_pass_warned = False
        self.adapter = driver  # the runner and post_merge of where this runs (R10, R20)
        self.statuses = statuses  # the session statuses a mailbox runner reads (§E step 4)
        self.lease, self.leased = lease, False  # R9: renewed every pass, when given
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
        self._rules: dict[str, BaseRules] = {}  # per pass: repo -> its base branch's rules
        self._unknown_said: set[str] = set()  # per pass: repos whose hold was said (R13)
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
        # The latest fr release, read by the cloud driver's pass before it runs; None
        # (the host loop, or a release that could not be read) checks no drift (R17).
        self.fr_release: str | None = None
        # Quota pacing (spec 2026-10-12-quota-pacing): set by a looping drive or the cloud
        # pass, never `--once` or plan mode. With a pacer the pass probes first and may be
        # quiet, partial or essential-only; `pace` is this pass's verdict.
        self.pacer: Pacer | None = None
        self.pace: Pace | None = None
        # (repo, head sha) -> the run cursor's position there: a commit never changes, so
        # each open batch PR head is read once per process (exit-gates R18)
        self._cursors: dict[tuple[str, str], CursorPosition | None] = {}
        # (repo, default-branch tip, batch branch) -> its gated rows there (R13, R14): they
        # move only when the default branch does
        self._ledger_rows: dict[tuple[str, str, str], LedgerRead] = {}
        self._fetched: set[str] = set()  # per pass: repos whose origin was fetched (p4-r7)

    # -------------------------------------------------------------- reaching out

    def cursor_at(self, pr: PullRequest) -> CursorPosition | None:
        """The run cursor's position at open batch PR *pr*'s head, read through the repo's
        clone (`gitseam`); None with no clone, or one that cannot reach the head."""
        key = (pr.repo, pr.head_oid)
        if key not in self._cursors:
            if self.path_of(pr.repo) is None or not pr.head_oid:
                return None
            try:
                self._cursors[key] = read_cursor(self._reader(pr.repo), pr)
            except TriageError:
                return None  # unknown this pass; read again next pass
        return self._cursors[key]

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
        if not self.adapter.carries(name):  # p4-o2: not even to ask it a question
            raise TriageError(f"runner `{name}` is not this driver's ({self.adapter.name})")
        if name not in self._runners:
            loaded = load_runner(name)
            if isinstance(loaded, Mailbox):  # its requests live in this scope's state (§F)
                loaded.open_mailbox(self.target, self.statuses)
            self._runners[name] = loaded
        return self._runners[name]

    def outbox(self) -> list[dict[str, Any]]:
        """Every request the mailbox runners this driver loaded hold pending (§E step 6)."""
        out: list[dict[str, Any]] = []
        for runner in self._runners.values():
            if isinstance(runner, Mailbox):
                out += runner.outbox()
        return out

    # ------------------------------------------------------------------ the lease

    def take_lease(self) -> None:
        """Before a pass: fetch the state ref, then take or renew the lease and push it
        as a compare-and-swap (R9, R12), so a second driver loses before it acts. A lease
        another driver holds, or a lost push, refuses (exit 2)."""
        if self.lease is None:
            return
        terms, scope, target = self.lease, self.scope, self.target
        try:
            fetch_now(scope, target)
            acquire(
                target,
                terms.identity,
                _now(),
                scope_id=scope_id(scope),
                duration=terms.duration,
                generation=terms.generation,
                push=lambda: push_now(scope, target),
            )
        except VisibilityUnreadable as exc:  # a looping drive skips the pass (gh#1134)
            raise ForgeReadError(str(exc), code=2) from exc
        except TriageError as exc:
            _fail(str(exc))
        self.leased = True

    def save_pass(self) -> None:
        """After a pass: record it on the lease and push the state ref, every pass of a
        long-running drive, not only when the command ends (cloud-triage §B)."""
        if not self.leased:
            return
        try:
            mark_pass(self.target, _now())
            push_now(self.scope, self.target)
        except VisibilityUnreadable as exc:  # the next pass pushes what this one left
            raise ForgeReadError(str(exc), code=2) from exc
        except TriageError as exc:
            _fail(str(exc))

    def warn_single_pass(self) -> None:
        """Once: the single-pass notice, when this pass planned a dispatch (R4). It is
        called when the pass ends, and when a refusal inside it (a runner's preflight)
        ends it, so the warning follows whichever way the pass exits."""
        if self.single_pass is None or not self.single_pass.allowed:
            return  # refused (the error carries the notice) or no guard
        if not self.planned_dispatch or self._single_pass_warned:
            return
        self._single_pass_warned = True
        err_console.print(
            f"[yellow]warning:[/yellow] {escape(self.single_pass.notice)}", soft_wrap=True
        )

    def release_lease(self) -> None:
        """On a clean stop: remove this driver's lease and push that. Soft: a failure is
        a warning, and the lease then expires on its own."""
        if not self.leased or self.lease is None:
            return
        self.leased = False
        try:
            if release(self.target, self.lease.identity, scope_id=scope_id(self.scope)):
                push_now(self.scope, self.target)
        except TriageError as exc:
            err_console.print(
                f"[yellow]warning:[/yellow] the drive lease was not released ({escape(str(exc))});"
                " it expires on its own",
                soft_wrap=True,
            )

    def _try_runner(
        self, name: str, consequence: str = "its sessions are not closed"
    ) -> Runner | None:
        """Runner *name*, or None (reported once) when it cannot be loaded: closing and
        the idle probe are best effort, so a load failure never ends the drive (R10).
        *consequence* names what the caller loses, so the warning says the right thing."""
        if name in self._unloadable or not self.adapter.carries(name):
            return None  # another driver's runner: its sessions are that driver's (p4-o2)
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
                _fresh_config(checkout, facts, repo, hold_unknown=True)
            except TriageError as exc:  # main's config moved under the pass
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
        self._merge[repo].rules = self._base_rules(facts, repo)
        return self._merge[repo]

    def _base_rules(self, facts: Facts, repo: str) -> BaseRules:
        """*repo*'s base branch's rules, once per repo per pass (merge-train-safety §D, R12)."""
        if repo not in self._rules:
            try:
                self._rules[repo] = self.client(facts, repo).base_rules(
                    repo, self._reader(repo).default_branch()
                )
            except GitError as exc:  # R13: origin cannot name it
                raise DefaultBranchUnknown(repo, exc) from exc
            except FORGE_ERRORS as exc:
                raise ForgeReadError(f"a forge read failed: {exc}", code=1) from exc
        return self._rules[repo]

    def _ctx_or_hold(self, facts: Facts, repo: str) -> MergeContext | None:
        """`merge_ctx`, or None with *repo* held for the pass (R13): the one catch-and-say
        every merge-path caller shares. Only `DefaultBranchUnknown` is held."""
        try:
            return self.merge_ctx(facts, repo)
        except DefaultBranchUnknown as exc:
            if repo not in self._unknown_said:
                self._unknown_said.add(repo)
                err_console.print(
                    f"[yellow]warning:[/yellow] held: {escape(str(exc))}", soft_wrap=True
                )
            return None

    def _queue_reads(
        self,
        facts: Facts,
        queue: Sequence[QueueEntry],
        repos: Mapping[str, str],
        live: Mapping[str, LivePr],
        approvals: Mapping[str, ApprovalVerdict],
    ) -> dict[str, Any]:
        """The Snapshot's merge-queue fields (§D "Queue mode", R13): the repos whose base
        requires a queue, those held (a `version:` block, `forge.api rest`), the queue state
        of each batch the driver enqueued before, and the base now. Reads only what a decision
        needs: no state for a batch never enqueued, no base without one, and no rules for a
        repo with no PR that could merge or be enqueued (open, not failing, approved; or
        enqueued before). A candidate repo whose clone cannot name its default branch (no
        `origin/HEAD`) is HELD, with a warning said once: whether it has a queue is unknown,
        and merging as if it had none could bypass one."""
        from fr import forgeapi

        try:
            rest = forgeapi.resolve() == "rest"
        except forgeapi.ForgeApiError as exc:
            _fail(str(exc))
        by_repo: dict[str, list[QueueEntry]] = {}
        for e in queue:
            pr = live.get(e.batch.id)
            enqueued = any(isinstance(x, EnqueueEvent) for x in e.batch.events)
            verdict = approvals.get(e.batch.id)
            candidate = pr is not None and pr.checks != "failing" and (
                verdict is not None and is_approved(verdict)
            )  # fmt: skip
            if pr is not None and pr.state == "OPEN" and (candidate or enqueued):
                by_repo.setdefault(repos[e.batch.id], []).append(e)
        queued: set[str] = set()
        unknown: set[str] = set()
        versioned: set[str] = set()
        states: dict[str, QueueState] = {}
        bases: dict[str, str] = {}
        for repo, entries in sorted(by_repo.items()):
            try:
                self._reader(repo).default_branch()
            except (GitError, TriageError) as exc:
                unknown.add(repo)
                queued.add(repo)
                self._report_once(
                    f"queue-unknown\0{repo}",
                    f"cannot tell {repo}'s default branch ({exc}): queue mode unknown, "
                    "its batches are held",
                )
                continue
            # `_base_rules` cannot raise `DefaultBranchUnknown` here: the read above just
            # named the default branch, and a `GitError` on it held the repo and continued.
            if not self._base_rules(facts, repo).merge_queue:
                continue
            queued.add(repo)
            if facts.config_for(repo).version is not None:
                versioned.add(repo)
                continue
            if rest:
                continue
            client = self.client(facts, repo)
            seen = {
                e.batch.id: client.pr_queue_state(repo, e.pr.number)
                for e in entries
                if any(isinstance(x, EnqueueEvent) and x.pr == e.pr.number for x in e.batch.events)
            }
            if not seen:
                continue
            try:
                bases[repo] = self._base_now(repo)
            except (GitError, TriageError):  # unknown base: decide nothing this pass
                continue
            states.update(seen)
        return {
            "queue_repos": frozenset(queued),
            "queue_versioned": frozenset(versioned),
            "queue_rest": rest,
            "queue_unknown": frozenset(unknown),
            "queue_states": states,
            "bases": bases,
        }

    def _base_now(self, repo: str) -> str:
        """The base branch's sha as fetched now (the `UpdateEvent.base` the red path reads)."""
        checkout = self._reader(repo)
        checkout.fetch()
        return checkout.rev_parse(f"origin/{checkout.default_branch()}")

    # ------------------------------------------------------------------ snapshot

    def snapshot(
        self,
        facts: Facts,
        judgements: Judgements,
        now: datetime,
        carried: frozenset[str] = frozenset(),
    ) -> Snapshot:
        """Every batch of the file, with the selection marked: the in-flight cap and
        the dependencies read them all, the actions only the selection (rg-3).

        A *carried* repo (a paced pass did not read it, spec 2026-10-12-quota-pacing R10)
        is not unread: its batches count and dispatch as usual. But no live read is made
        for them (PR view, required checks, merge commit, hand close-out, archive PRs,
        claim and export reads), so none is merged, closed out or archived this pass."""
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
            if e.batch.id in ids and repos.get(e.batch.id) not in carried
        )
        live: dict[str, LivePr] = {}
        approvals: dict[str, ApprovalVerdict] = {}
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
                approvals[e.batch.id] = approval_verdict(
                    e.batch.events, e.pr.number, str(view.get("head_oid") or ""),
                    view.get("labels"),
                )  # fmt: skip
                live[e.batch.id] = LivePr(
                    number=e.pr.number,
                    state=str(view.get("state")),
                    draft=bool(view.get("draft")),
                    head=str(view.get("head_oid") or ""),
                    checks=verdict,
                    failing=failing,
                    head_ref=e.pr.head_ref,
                    trusted=True,  # the queue holds `batch_pr`s only (gh#936)
                    labels=tuple(str(n) for n in view.get("labels") or ()),
                )
            # Every landed batch, selected or not: adopting a finished close-out is
            # bookkeeping (gh#990). Only the selection is read further.
            for b in judgements.batches:
                if stages[b.id] not in ("merged", "partial") or b.id not in repos:
                    continue
                if repos[b.id] in unread:
                    continue
                if repos[b.id] in carried:  # nothing read: unknown, so nothing planned
                    if closeout_event(b) is None:
                        unverified.add(b.id)
                    continue
                mine = b.id in ids
                event = closeout_of(b, judgements.closeouts)  # a closed collected PR: owed
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
                if collected_name(event.archive or "") is not None:
                    continue  # a collected close-out: read once per marker (_collected_reads)
                archives[repos[b.id]] = (
                    *archives.get(repos[b.id], ()),
                    *self._archive_prs(facts, repos[b.id], b, event),
                )
                if now - event.at >= STALE_CLOSEOUT:  # is its tab still live? (gh#1025)
                    stale.append(b)
            queue_reads = self._queue_reads(facts, queue, repos, live, approvals)
        except UnsupportedForgeOperation as exc:
            _fail(str(exc))
        except FORGE_ERRORS as exc:
            raise ForgeReadError(f"a forge read failed: {exc}", code=1) from exc
        done_waves = finished_waves(judgements.batches, stages)
        # A carried repo's issues and claim comments are current (its probes answered
        # unchanged), so its owed claims are planned like any read repo's (p2-r6).
        claim_plan = self._claim_plan(facts, judgements, repos, unread, now)
        export_path, export_refused = self._export_config(facts)
        export_path = {r: p for r, p in export_path.items() if r not in carried}
        export_prs, export_orphans = self._export_reads(
            facts, judgements, repos, done_waves, export_path
        )
        open_markers = {c.repo for c in judgements.closeouts if not (c.merged or c.closed)}
        default_branch = {
            r: self._default_branch(r)
            for r in {*export_path, *archives, *(open_markers - unread.keys() - carried)}
        }
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
        ledgers = self._ledgers(facts, judgements, stages, repos, ids, {*unread, *carried})
        reads = self._collected_reads(facts, judgements, repos, due, {*unread, *carried}, now)
        live_items, asked_items = reads.pop("live"), reads.pop("asked")
        return Snapshot(
            closeouts=tuple(judgements.closeouts),
            **reads,
            approvals=approvals,
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
            existing=existing | live_items,
            closeout_probed=probed | asked_items,
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
            scope_id=scope_id(self.scope),
            default_branch=default_branch,
            unverified=frozenset(unverified),
            finished=done_waves,
            export_refused=export_refused,
            awaiting=frozenset(b.id for b in judgements.batches if batch_awaits_live(b, facts)),
            refused={b.id: why for b in chosen if (why := self.adapter.refusal(b)) is not None},
            ledgers=ledgers,
            awaiting_unlabelled=awaiting_unlabelled(facts),
            ledger_unknown=fact_ledger_unknown(judgements.batches, facts, stages),
            post_merge_repos=frozenset(
                r for r in set(repos.values()) if facts.config_for(r).post_merge
            )
            if self.adapter.kind == "host"
            else frozenset(),
            **queue_reads,
            **claim_plan,
        )

    def _ledgers(
        self,
        facts: Facts,
        judgements: Judgements,
        stages: Mapping[str, str],
        repos: Mapping[str, str],
        selected: set[str],
        unread: set[str],
    ) -> dict[str, GateLedger]:
        """The gate ledger of every landed batch (exit-gates R13, R14): the merged PR's
        labels from facts and, for a selected batch a post-merge gate holds, the rows it
        gates on the default branch. Rows that cannot be read stay unknown (None)."""
        ledgers = fact_ledgers(judgements.batches, facts, stages)
        for batch in judgements.batches:
            ledger = ledgers.get(batch.id)
            repo = repos.get(batch.id)
            if (
                ledger is None
                or repo is None
                or repo in unread
                or batch.id not in selected
                or closeout_event(batch) is not None
                or not held_gates(ledger.labels)
            ):
                continue
            read = self._gated_rows(repo, batch)
            if read is not None:
                ledgers[batch.id] = replace(
                    ledger,
                    rows=read.rows,
                    run_gate=read.run_gate,
                    run_gate_inherited=read.run_gate_inherited,
                    ops_promoted=read.ops_promoted,
                )
        return ledgers

    def _gated_rows(self, repo: str, batch: Batch) -> LedgerRead | None:
        """*batch*'s gated rows on `origin/<default>` (R14's rows-walked check reads that
        branch's matrix); None, reported once, when the clone cannot say."""
        branch = recorded_branch(batch)
        try:
            checkout = self._fetched_reader(repo)
            tip = f"origin/{checkout.default_branch()}"
            key = (repo, checkout.rev_parse(tip), branch)
            if key not in self._ledger_rows:
                self._ledger_rows[key] = gated_rows_at(checkout, tip, branch)
            return self._ledger_rows[key]
        except TriageError as exc:
            self._report_once(
                f"ledger\0{batch.id}\0{exc}",
                f"cannot read the rows {batch.id}'s gates hold on {repo}'s default branch "
                f"({exc}); no fr:awaiting-live label and no gate pass is planned for it",
            )
            return None

    def _collected_reads(
        self,
        facts: Facts,
        judgements: Judgements,
        repos: Mapping[str, str],
        due: Sequence[Batch],
        skip: set[str],
        now: datetime,
    ) -> dict[str, Any]:
        """R15, §D: the driver's OWN reads of each unfinished collected close-out, by item,
        for `review_reasons`: its trusted PR on its branch (checks only at the recorded
        head), the git diff and commits from the default branch to the recorded head, the
        issues its body closes, the issues its members' narrowing decisions name now, and
        whether its branch is pushed; a closed marker's PR open again; and, with --yes,
        which items a runner holds live (a hand marker is asked of no runner) and which
        were asked. Snapshot keyword arguments, plus `live` and `asked`."""
        from fr_dispatch.work_item import WorkItem

        prs: dict[str, LivePr] = {}
        diff: dict[str, frozenset[str] | None] = {}
        commits: dict[str, tuple[str, ...] | None] = {}
        body_closes: dict[str, frozenset[str]] = {}
        narrowed: dict[str, frozenset[str] | None] = {}
        pushed: set[str] = set()
        reopened: dict[str, LivePr] = {}
        asked: set[str] = set()
        probes: dict[str, list[WorkItem]] = {}
        by_id = {b.id: b for b in judgements.batches}

        def probe(name: str, item: str, repo: str, batch: Batch | None) -> None:
            group = self.group_of(batch) if batch is not None else None
            probes.setdefault(name, []).append(WorkItem(
                id=item, unit="run", workflow=batch_workflow(batch) if batch else "fr-goal",
                repo=repo, parent=None, inputs=(),
                payload={"kind": "closeout", **({"group": group} if group else {})},
                tracking=None,
            ))  # fmt: skip

        def git_read(m: CollectedCloseout) -> None:
            try:
                checkout = self._fetched_reader(m.repo)
                if m.item and checkout.remote_branch_exists(m.branch):
                    pushed.add(m.item)
                if not m.head or not checkout.reach_commit(m.head, m.branch):
                    diff[m.item] = commits[m.item] = None
                    return
                ref = f"origin/{checkout.default_branch()}"
                diff[m.item] = checkout.changed_status(ref, m.head)
                commits[m.item] = checkout.commits_since(ref, m.head)
                tip = ref
                names: set[str] = set()
                for bid in m.members:
                    if bid in by_id:
                        read = closeout_read(checkout, tip, recorded_branch(by_id[bid]), m.repo)
                        names |= {n.lower() for n in read.narrowed}
                narrowed[m.item] = frozenset(names)
            except TriageError:
                diff.setdefault(m.item, None)
                commits.setdefault(m.item, None)
                narrowed[m.item] = None

        try:
            for m in judgements.closeouts:
                if m.repo in skip or m.merged:
                    continue
                client, allowed = self.client(facts, m.repo), allowed_authors(m.repo, facts)
                found = _live_head_prs(client, m.repo, m.branch, allowed)
                if m.closed:  # p6b-r10: a closed close-out's PR open again
                    again = next((p for p in found if p.state == "OPEN"
                                  and p.number == m.pr), None)  # fmt: skip
                    if again is not None:
                        reopened[m.item] = again
                    continue
                mine = [p for p in found if p.trusted]
                pick = next(
                    (p for state in ("OPEN", "MERGED", "CLOSED") for p in
                     sorted(mine, key=lambda x: -x.number) if p.state == state), None,
                )  # fmt: skip
                git_read(m)
                if pick is None:
                    first = next((by_id[b] for b in m.planned if b in by_id), None)
                    if m.runner != "hand":
                        probe(m.runner, m.item, m.repo, first)
                    else:
                        asked.add(m.item)  # no runner holds a hand run: asked, never live
                    continue
                view = client.pr_view(m.repo, pick.number)
                body_closes[m.item] = frozenset(
                    collected.closes_from_body(str(view.get("body") or ""))
                )
                head = str(view.get("head_oid") or pick.head)
                pick = replace(pick, head=head)
                if pick.state == "OPEN":
                    key = (m.repo, pick.number)
                    fact = next((p for p in facts.prs if (p.repo, p.number) == key), None)
                    # p6b-r2: only results for the head that will merge; none is pending
                    counts = (
                        (fact.checks or {}) if fact is not None and fact.head_oid == head else {}
                    )
                    required = (
                        client.pr_required_checks(m.repo, pick.number) if head == m.head else []
                    )
                    verdict, failing = checks_verdict(
                        required, counts, ci_none=self._ci_none(m.repo)
                    )
                    pick = replace(pick, checks=verdict, failing=failing,
                                   base=str(view.get("base_ref") or ""),
                                   mergeable=str(view.get("mergeable") or ""),
                                   merge_state=str(view.get("merge_state") or ""))  # fmt: skip
                prs[m.item] = pick
            if self.yes:
                for repo in sorted({repos[b.id] for b in due if b.id in repos} - skip):
                    _, item = collected_candidate(
                        repo, judgements.batches, repos, judgements.closeouts, now.date()
                    )
                    first = next(b for b in due if repos.get(b.id) == repo)
                    probe(str(self._launch(facts, first, repo).runner), item, repo, first)
        except UnsupportedForgeOperation as exc:
            _fail(str(exc))
        except FORGE_ERRORS as exc:
            raise ForgeReadError(f"a forge read failed: {exc}", code=1) from exc
        live: set[str] = set()
        for name, items in probes.items() if self.yes else ():
            runner = self._try_runner(name)
            if runner is None or runner.preflight(items):
                continue
            live |= runner.existing_dispatches(items)
            asked.update(i.id for i in items)
        return {
            "collected_prs": prs, "collected_diff": diff, "collected_commits": commits,
            "collected_body_closes": body_closes, "collected_narrowed": narrowed,
            "collected_pushed": frozenset(pushed), "collected_reopened": reopened,
            "live": frozenset(live), "asked": frozenset(asked),
        }  # fmt: skip

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
            """A refresh of a member facts cannot see (unviewed, or its repo skipped): a
            read that writes only when the marker is due, so it is made with --yes and
            never announced in a plan."""
            return op.kind == "refresh" and env.issue(op.key) is None

        def owed(kind: str) -> tuple[tuple[str, str], ...]:
            return tuple(
                (op.key, op.batch or "") for op in plan.ops
                if op.kind == kind and _op_repo(env, op, repos) not in unread
                and (self.yes or not blind(op))
            )  # fmt: skip

        keys = {k for b in judgements.batches for k in b.ids}
        return {
            "me": env.me,
            "held": dict(held_members(sorted(keys), held_map(facts, env.me))),
            "claims_owed": owed("claim"),
            "refresh_owed": owed("refresh"),
            "releases_owed": owed("release"),
            "settles_owed": owed("settle"),
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
            checkout = self._fetched_reader(repo)
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
                    and export_wave_of(pr.head_ref, scope_id(self.scope)) is not None
                    and pr.cross_repo is not True  # a fork never stalls the export
                    and pr.number not in recorded
                )
                if found:
                    orphans[repo] = found
                target = export_target(
                    repo, judgements.batches, repos, finished, judgements.exports, found,
                    scope=scope_id(self.scope),
                )  # fmt: skip
                if target is None or target.recorded is None or target.recorded.pr is None:
                    continue
                done, number = target.recorded, target.recorded.pr
                client = self.client(facts, repo)
                listed = next(
                    (p for p in _live_head_prs(
                        client, repo, export_branch(target.wave, scope_id(self.scope)), allowed
                    )
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
                    mergeable=str(view.get("mergeable") or ""),  # merge-truth R12
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

    def _fetched_reader(self, repo: str) -> Checkout:
        """`_reader`, fetched once per pass (p4-r7): every read of `origin/<default>` a
        pass makes shares one fetch, however many batches ask."""
        checkout = self._reader(repo)
        if repo not in self._fetched:
            checkout.fetch()
            self._fetched.add(repo)
        return checkout

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
                checkout = self._fetched_reader(repo)
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
            checkout = self._fetched_reader(repo)
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
            checkout = self._fetched_reader(repo)
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
        checks), unlinked or linked to an issue (merge-truth R7), plus any PR on the
        close-out's own heads, merged ones included. A head-found open PR the facts do
        not hold has its checks read live, never assumed pending (R7). An open one this
        batch owns, the only kind the archive step merges, is judged between two fresh
        reads of its head (`_pinned`)."""
        client = self.client(facts, repo)
        allowed = allowed_authors(repo, facts)
        ci_none = self._ci_none(repo)
        out: dict[int, LivePr] = {}
        counts: dict[int, Mapping[str, int]] = {}  # the collected checks, at the facts' head
        linked = [p for issue in facts.issues for p in issue.prs]
        for pr in (*facts.prs, *linked):
            if (
                pr.repo != repo
                or pr.state != "OPEN"
                or not pr.head_ref.startswith(ARCHIVE_PREFIXES)
                or pr.number in out
            ):
                continue
            counts[pr.number] = pr.checks or {}
            out[pr.number] = LivePr(
                number=pr.number, state="OPEN", draft=pr.is_draft, head=pr.head_oid,
                checks="pending", head_ref=pr.head_ref, files=tuple(pr.files),
                trusted=distrust(pr.author, pr.cross_repo, allowed) is None,
            )  # fmt: skip
        heads = {_closeout_head(batch)}
        heads |= {event.archive} if event.archive else set()
        for head in sorted(heads):
            for found in _live_head_prs(client, repo, head, allowed):
                if found.state != "OPEN" or found.number not in out:
                    out[found.number] = found
        judged: list[LivePr] = []
        for p in out.values():
            if p.state != "OPEN":
                judged.append(p)
            elif attributed(p, batch, event):
                judged.append(_pinned(client, repo, p, counts.get(p.number), ci_none=ci_none))
            else:  # never merged by this step: its verdict is only reported
                verdict, failing = _judge(client, repo, p, counts.get(p.number), ci_none)
                judged.append(replace(p, checks=verdict, failing=failing))
        return judged

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
            if not self.adapter.carries(str(launch.runner)):
                continue  # left to the driver that carries it, never loaded here (p4-o2)
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
            if self.adapter.refusal(batch) is None:  # the driver's runner (R10)
                batch = _with_runner(batch, self.adapter.runner_for(batch))
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

    def _settle_approvals(
        self, facts: Facts, judgements: Judgements, carried: frozenset[str] = frozenset()
    ) -> tuple[bool, set[tuple[str, int]]]:
        """Record or void each selected open batch PR's approval before the walk
        (merge-train-safety §A "Recording and voiding", R2); whether it wrote any, and
        the `(repo, PR)` whose label it removed.
        Read-only passes never settle: the walk then reads a first label as approved."""
        repos = {b.id: r for b in judgements.batches if (r := batch_repo(b, facts)) is not None}
        chosen = {b.id for b in _chosen(judgements.batches, self.named)}
        # A carried repo (quota-pacing R10) was not read this pass: its labels are read
        # live when its probes next change or at the full pass, never on carried facts.
        unread = {s.repo for s in facts.skipped} | carried
        by_repo: dict[str, list[tuple[Batch, int]]] = {}
        for e in pr_open_queue(judgements.batches, facts, judgements.issues):
            repo = repos.get(e.batch.id)
            if e.batch.id in chosen and repo is not None and repo not in unread:
                by_repo.setdefault(repo, []).append((e.batch, e.pr.number))
        wrote = False
        voided: set[tuple[str, int]] = set()
        writer = event_writer(self.target, facts, read_errors=True)
        repo_of = {b.id: r for b, r in ((b, repos.get(b.id)) for b in judgements.batches) if r}

        def record(batch_id: str, event: BatchEvent) -> None:
            nonlocal wrote
            writer(batch_id, event)
            wrote = True
            if isinstance(event, ApprovalEvent) and event.voided_at is not None:
                voided.add((repo_of[batch_id], event.pr))

        try:
            for repo, open_prs in sorted(by_repo.items()):
                client = self.client(facts, repo)
                ensure_approval_label(client, repo, _say, seen=self._label_seen)
                settle_approvals(client, record, repo, open_prs, _say, now=_now())
        except UnsupportedForgeOperation as exc:
            _fail(str(exc))
        except FORGE_ERRORS as exc:
            raise ForgeReadError(f"a forge read failed: {exc}", code=1) from exc
        return wrote, voided

    def run_pass(self) -> tuple[bool, Summary, list[str]]:
        """One pass: re-collect, decide, act (with --yes) or print the plan.
        Returns whether it acted, the settled summary, and the blocked batch ids.

        Paced (a pacer set, spec 2026-10-12-quota-pacing §B, §C), it probes first: a quiet
        pass ends there; a partial one collects only the changed repos and reads nothing
        live for the carried ones; an essential-only one dispatches nothing and leaves
        the board as it was."""
        paced = self._pass_plan()
        if paced is not None and not paced.collects:
            return self._quiet_pass(paced)
        # The repos the collect actually carried (p2-r5): one value for the ETags it
        # promotes and the snapshot's live reads, so the two cannot drift.
        collected_carried: list[frozenset[str]] = []
        reader: CursorReader = self.cursor_at
        if paced is None:
            ignored = recollect(self.scope, self.target, cursor_at=reader) or {}
        else:
            pacer = self.pacer
            assert pacer is not None

            def after_write(facts: Facts, carried: frozenset[str]) -> None:
                collected_carried.append(carried)
                pacer.after_collect(paced, facts, carried)

            ignored = recollect(
                self.scope, self.target, only=paced.only, after_write=after_write,
                cursor_at=reader,
            ) or {}  # fmt: skip
        for repo, keys in sorted(ignored.items()):
            self._report_once(
                f"ignored\0{repo}\0{','.join(keys)}",
                f"{repo}: {TRIAGE_CONFIG_PATH} on the default branch has "
                f"{plural(len(keys), 'key')} this fr does not know ({', '.join(keys)}); "
                "ignored until an fr that knows them runs",
            )
        _, facts, judgements = _load_state(self.scope, self.target, None)
        carried = (
            collected_carried[-1]
            if collected_carried
            else paced.carried
            if paced is not None
            else frozenset[str]()
        )
        self._label_seen: set[str] = set()  # one approval-label check per repo per pass (R4)
        if self.yes:
            wrote, voided = self._settle_approvals(facts, judgements, carried)
            if voided:  # what the forge says now: this pass's views never show them approved
                facts = facts_without_label(facts, voided, APPROVED_FR.name)
                write_text_atomic(
                    self.target / "facts.json",
                    json.dumps(facts.to_json(), indent=2, ensure_ascii=False) + "\n",
                )
            if wrote:
                _, facts, judgements = _load_state(self.scope, self.target, None)
        for ctx in self._merge.values():
            ctx.recorded.clear()  # what a context recorded last pass is on disk now
        self._ci, self._unlanded, self._held = {}, set(), 0
        self._fetched = set()
        self._rules = {}
        self._unknown_said = set()
        self._clone_unread = {}
        self._restart = {}
        self._stopped, self._queued, self._conflicts = {}, 0, {}
        self._export_refusals = 0
        self._export_failures = 0
        self._held_now, self._claim_done = {}, SyncResult()
        self.failed_write = False
        snap = self.snapshot(facts, judgements, _now(), carried)
        if paced is not None and paced.dispatch_held is not None:
            snap = replace(snap, dispatch_held=paced.dispatch_held)
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
        if carried:  # nothing was read live for them: no merge, close-out or archive (R10)
            plan = replace(plan, actions=tuple(
                a for a in plan.actions
                if not (a.kind in _LIVE_READ_ACTIONS
                        and read_repo(a, snap.repos, self._claims) in carried)
            ))  # fmt: skip
        if self.single_pass is not None:
            self.planned_dispatch = any(a.kind == "dispatch" for a in plan.actions)
            if self.planned_dispatch and not self.single_pass.allowed:
                self.release_lease()
                _fail(self.single_pass.notice, code=2)
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
                if (
                    outcome
                    or action.kind not in ("close", "claim", "refresh", "release", "settle")
                    and not (action.kind == "warn" and action.red)
                ):
                    # a close reported already stays quiet, as does a claim write that wrote
                    # nothing, and a red PR the recovery has nothing new to say about
                    _say(action_line(action, outcome))
            if self.yes:
                self._record_released(facts)
                self._drift(facts, snap)
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
        if self.pacer is not None and paced is not None:
            self.pacer.record_summary(
                asdict(summary), digest=paced.digest, held=paced.dispatch_held is not None
            )
        if self.yes:
            if paced is None or paced.kind != "essential":
                self._write_board()  # an essential-only pass keeps the last board (R14)
        else:
            _say("nothing done; re-run with --yes to act")
        stuck = [a.batch for a in plan.actions if a.kind == "blocked"]
        stuck += [f"export wave {a.wave} {a.batch}" for a in plan.actions
                  if a.wave is not None and a.kind == "warn"]  # fmt: skip
        return acted, summary, stuck

    def _pass_plan(self) -> PassPlan | None:
        """Probe, then decide the pass (spec 2026-10-12-quota-pacing R7-R11); None when
        unpaced (`--once`, plan mode) or when the pace is not a pass to run."""
        if self.pacer is None or self.pace is None or self.pace.kind == "wait":
            return None
        return plan_paced_pass(
            self.pacer, self.scope, self.target, _probe_forge(), essential=self.pace.essential
        )

    def _quiet_pass(self, paced: PassPlan) -> tuple[bool, Summary, list[str]]:
        """R9: nothing changed since the last planned pass, so nothing is collected,
        read, planned or rendered; that pass's summary stands for this one."""
        self.failed_write = False
        _say(f"quiet: {plural(paced.probes, 'probe')} unchanged")
        assert self.pacer is not None and self.pacer.state.summary is not None
        return False, Summary(**self.pacer.state.summary), []

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
                # The cloud driver reads its own runners only, its mailbox already open
                # (p4-o2); the host's board loads as it always did (R10).
                loader=self.runner if self.adapter.kind == "cloud" else None,
                # the repos this pass judged `ci none`, as the walk did (p1-r2)
                ci_none=frozenset(r for r, none in self._ci.items() if none),
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
        if action.kind == "export-conflict":
            return self._export_conflict(action), False, in_flight  # no session owns it
        if action.kind in EXPORT_KINDS:
            refusals, failures = self._export_refusals, self._export_failures
            line = self._export_act(action, facts)
            did = (self._export_refusals, self._export_failures) == (refusals, failures)
            return line, did, in_flight  # a refusal or a failed write did nothing
        if action.kind == "warn" and action.red:  # a failing batch PR: recover it (§C)
            if action.batch in self._held_now:
                return "", False, in_flight  # another scope holds it (R6)
            line, did = self._recover(action, facts)
            return line, did, in_flight
        if action.kind == "warn" and action.ejected:
            line, did = self._record_ejected(action, facts)
            return line, did, in_flight
        if action.kind in ("warn", "foreign"):
            if action.head:  # an export's warn names no head: it is said every pass
                self.warned.add(action.head)
            return action.detail, False, in_flight
        if action.kind in ("blocked", "held", "ledger-unread", "closeout-held", "closeout-stuck",
                           "closeout-needs-review", "closeout-unrecorded"):  # fmt: skip
            return action.detail, False, in_flight
        if action.kind in ("claim", "refresh", "release", "settle"):
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
        if action.kind == "awaiting-live":
            line, did = self._label_awaiting(action, facts)
            return line, did, in_flight
        if action.kind == "gate-pass":
            line, did = self._pass_gate(action, facts, repo)
            return line, did, in_flight
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
        if action.kind == "enqueue":
            line, did = self._enqueue(action, facts, judgements, batch, repo)
            return line, did, in_flight
        if action.kind == "post-merge":
            outcome, did = self._post_merge(facts, judgements, batch, repo)
            return outcome, did, in_flight
        if action.kind == "closeout-reopened":
            self.warned.add(action.head)
            return action.detail, False, in_flight
        if action.kind in ("closeout-merged", "closeout-pr-closed", "closeout-abandoned"):
            return self._collected_record(action, facts, judgements, repo), True, in_flight
        if action.kind == "closeout-handback":
            line, did = self._closeout_hand_back(action, facts, judgements, repo)
            return line, did, in_flight
        if action.kind == "closeout" and action.items:
            outcome, did = self._collected_close_out(action, facts, judgements, repo)
            return outcome, did, in_flight
        if action.kind == "closeout":
            outcome, did = self._close_out(action, facts, judgements, batch, repo)
            return outcome, did, in_flight
        if action.kind == "archive":
            line, did = self._archive(action, facts, judgements, batch, repo)
            return line, did, in_flight
        if action.kind == "archive-conflict":
            line, did = self._archive_conflict(action, facts, judgements, batch, repo)
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
                    read_errors=True,
                    driver=self.adapter,
                    load=self.runner,
                    label_seen=self._label_seen,
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

    def _label_awaiting(self, action: Action, facts: Facts) -> tuple[str, bool]:
        """R13: label an issue a gated row cites `fr:awaiting-live`, through the adapter. A
        failed write is reported, makes `--once` exit 1, and is planned again next pass."""
        repo, _, number = action.key.rpartition("#")
        try:
            client = self.client(facts, repo)
            client.ensure_labels(repo, [FR_AWAITING_LIVE])
            client.edit_issue_labels(
                repo, int(number), add=frozenset({FR_AWAITING_LIVE.name}), remove=frozenset()
            )
        except _GATE_WRITE_FAILURES as exc:
            self.failed_write = True
            return f"label failed, retried next pass: {exc}", False
        return f"labelled {action.key} {FR_AWAITING_LIVE.name}", True

    def _pass_gate(self, action: Action, facts: Facts, repo: str) -> tuple[str, bool]:
        """R14's rows-walked route: swap the merged PR's gate label and comment why."""
        assert action.pr is not None
        why = action.detail.partition(": ")[2] or action.detail
        try:
            pass_gate(self.client(facts, repo), repo, action.pr, action.gate, why=why)
        except _GATE_WRITE_FAILURES as exc:
            self.failed_write = True
            return f"gate pass failed, retried next pass: {exc}", False
        return f"PR #{action.pr}: gate:{action.gate} -> gate:{action.gate}-passed", True

    def _claim_write(self, action: Action) -> tuple[str, bool]:
        """Execute one claim, refresh or release through `claim_sync.execute` (R3, R8,
        R10). A claim that turned out held (R4) stops the pass acting on its batch; a
        failed write is reported, makes `--once` exit 1, and is retried next pass."""
        assert self._claims is not None
        op = ClaimOp(action.kind, action.key, action.batch or None)  # type: ignore[arg-type]
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

    def _drift(self, facts: Facts, snap: Snapshot) -> None:
        """R17, §G: read each live batch's run cursor from its PR head and ask its runner
        to re-home a run recorded under another fr major, once per (run, major) and at
        the session's idle; a run with no recorded version is reported once. Only runners
        this driver carries that can re-home are asked; anything that cannot be read is
        skipped this pass, never guessed."""
        from fr_dispatch.protocols import SessionInspector

        from fr.triage import drift

        release = self.fr_release
        if release is None:
            return
        try:
            ledger = drift.load_ledger(self.target)
        except TriageError as exc:
            self._report_once(f"drift\0{exc}", f"version drift not checked: {exc}")
            return
        runs: list[drift.RunVersion] = []
        runners: dict[str, Any] = {}
        for batch in snap.batches:
            repo, last = snap.repos.get(batch.id), last_dispatch(batch)
            if not repo or last is None or snap.stages.get(batch.id) not in LIVE_STAGES:
                continue
            runner = self._try_runner(last.runner, "its runs are not checked for version drift")
            if runner is None or not callable(getattr(runner, "rehome", None)):
                continue
            pr = batch_pr(batch, facts)
            paths = drift.cursor_paths(pr.files) if pr is not None and pr.state == "OPEN" else []
            if pr is None or not paths:
                continue  # no cursor on the branch yet
            # The batch's own launch values only: a re-home keeps the recorded session's
            # repo and branch, and drift must not refuse a batch whose launch defaults
            # the repo no longer resolves (the dispatch already happened).
            item = _probe(repo, batch, batch.launch)
            try:  # every cursor the PR carries: only the branch's own is the batch's (p6-r3)
                client = self.client(facts, repo)
                ref = pr.head_oid or pr.head_ref
                texts = {p: client.read_file_at_ref(repo, p, ref) for p in paths}
                path = drift.pick_cursor(texts, last.branch)
                status = (
                    runner.session_statuses([item]).get(item.id, "unknown")
                    if path is not None and isinstance(runner, SessionInspector)
                    else "unknown"
                )
            except Exception as exc:  # noqa: BLE001 - retried next pass, never the drive's end
                self._report_once(
                    f"drift\0{batch.id}\0{exc}",
                    f"batch {batch.id}: its run cursor could not be read ({exc}); version "
                    "drift is checked again next pass",
                )
                continue
            if path is None:
                found = sum(drift.cursor_branch(t) == last.branch for t in texts.values())
                self._report_once(
                    f"drift\0{batch.id}\0cursor\0{found}",
                    f"batch {batch.id}: its PR carries "
                    + ("no run cursor" if not found else f"{found} run cursors")
                    + f" of branch {last.branch} among {len(texts)}; version drift is not "
                    "checked for it",
                )
                continue
            run, version = drift.read_cursor(texts[path])
            runs.append(
                drift.RunVersion(
                    batch=batch.id, item=item.id, branch=last.branch,
                    run=run or PurePosixPath(path).stem, fr_version=version, status=status,
                )
            )  # fmt: skip
            runners[item.id] = (runner, item)
        plan = drift.plan_drift(runs, release, ledger)
        asked: list[drift.Rehome] = []
        for rehome in plan.rehomes:
            runner, item = runners[rehome.item]
            try:
                handle = runner.rehome(item, rehome.brief)
            except Exception as exc:  # noqa: BLE001 - asked again next pass
                self._report_once(
                    f"rehome\0{rehome.item}\0{exc}",
                    f"re-homing run {rehome.run} failed ({exc}); asked again next pass",
                )
                continue
            asked.append(rehome)
            _say(
                f"rehome {rehome.batch}: run {rehome.run} started on fr {rehome.recorded}, the "
                f"latest release is {release}: asked to re-home its session ({handle})"
            )
        for unknown in plan.unknown:
            _say(
                f"drift {unknown.batch}: run {unknown.run} has no recorded fr version; "
                "reported, never re-homed"
            )
        if asked or plan.unknown:
            ledger = ledger.with_rehomes(asked, at=_now().isoformat()).with_reported(plan.unknown)
            try:
                drift.save_ledger(self.target, ledger)
            except OSError as exc:
                self._report_once(f"ledger\0{exc}", f"{drift.REHOMES_FILE} not written: {exc}")

    def _record_released(self, facts: Facts) -> None:
        """One `claims_released` event per batch released this pass, after its releases,
        through the one judgements writer, so the next pass owes nothing (R10)."""
        if not any(op.kind in ("release", "settle") for op, _ in self._claim_done.done):
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
        ctx = self._ctx_or_hold(facts, repo)
        if ctx is None:  # R13: the repo is held for the pass
            self._unlanded.add(batch.id)
            return _MergeOutcome("held: default branch unknown", False, in_flight, False)
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
                # A move fr made (its own update) is judged again next pass and stops the
                # train; any other push voids the approval, so the PR is stepped over
                # like every unapproved one (merge-train-safety §A, p1-r10).
                events = [*batch.events, *ctx.recorded.get(batch.id, [])]
                ours = reaches(events, slots[0].step.pr.number, action.head, slots[0].head)
                if not ours:
                    return _MergeOutcome(
                        f"held: PR #{action.pr} head moved from {action.head[:12]} to "
                        f"{slots[0].head[:12]} by a push fr did not make; its "
                        f"{APPROVED_FR.name} approval is void",
                        False,
                        in_flight,
                        False,
                    )
                return _MergeOutcome(
                    f"held: PR #{action.pr} head moved from {action.head[:12]} to "
                    f"{slots[0].head[:12]} since its checks were judged; it is judged "
                    "again next pass",
                    False,
                    in_flight,
                    True,
                )
            writer = event_writer(self.target, facts, read_errors=True)
            ctx.on_update = update_recorder(
                writer, lambda pr: batch.id if pr == slots[0].step.pr.number else None
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
        if attempt.outcome in ("unapproved", "unready"):
            why = attempt.reason or f"awaits the {APPROVED_FR.name} label"
            return _MergeOutcome(f"held: PR #{action.pr} {why}", False, in_flight, stops)
        held = f": {', '.join(attempt.checks)}" if attempt.checks else ""
        return _MergeOutcome(
            f"held: PR #{action.pr} is {attempt.outcome}{held}", False, in_flight, stops
        )

    def _enqueue(
        self, action: Action, facts: Facts, judgements: Judgements, batch: Batch, repo: str
    ) -> tuple[str, bool]:
        """§D: put the PR in the base's merge queue through the merge path's own gate (the
        live label, a draft marked ready, the head re-checked), pinned to the head whose
        checks were judged; then record an `enqueue` event with the base as fetched BEFORE
        the write (a base that moves meanwhile reads as moved, so an ejection re-enqueues,
        never strands). A refusal is a held line and a `refused` event: the walk retries once
        more at the same head, then asks the operator (`enqueue-refused`)."""
        assert action.pr is not None
        ctx = self._ctx_or_hold(facts, repo)
        if ctx is None:  # R13
            return "held: default branch unknown", False
        entries = [
            e
            for e in pr_open_queue(judgements.batches, facts, judgements.issues)
            if e.batch.id == batch.id
        ]
        n, head = action.pr, action.head
        moved = f"held: PR #{n} head moved from {head[:12]} since its checks were judged"
        try:
            slots, _ = plan_queue(ctx, entries)
            if not slots:
                return f"PR #{n} is already merged", False
            if slots[0].head != head:
                return f"{moved}; it is judged again next pass", False
            view = ctx.client.pr_view(repo, n)
            held = _approved_and_ready(ctx, slots[0], view, wait=False)
            if held is not None:
                if held.outcome in ("unapproved", "unready"):
                    return (
                        f"held: PR #{n} {held.reason or f'awaits the {APPROVED_FR.name} label'}",
                        False,
                    )
                names = f": {', '.join(held.checks)}" if held.checks else ""
                return f"held: PR #{n} is {held.outcome}{names}", False
            if str(view.get("head_oid") or "") != head:
                return f"{moved}; it is judged again next pass", False
            base = self._base_now(repo)
            try:
                ctx.client.pr_enqueue(repo, n, head_sha=head, method=ctx.method)
            except FORGE_ERRORS as exc:
                self.failed_write = True
                self._append(
                    judgements, facts, batch,
                    EnqueueEvent(kind="enqueue", at=_now_after(batch), pr=n, head=head,
                                 base=base, outcome="refused", detail=str(exc).strip()[:300]),
                )  # fmt: skip
                return f"held: PR #{n} enqueue refused: {exc}", False
        except UnsupportedForgeOperation as exc:
            _fail(str(exc))
        except (GitError, TriageError) as exc:
            why = f"the base could not be read ({exc}): retried next pass"
            return self._said_once(batch, action, "enqueue-base", why), False
        except FORGE_ERRORS as exc:  # a re-read of the PR or its checks
            raise ForgeReadError(f"a forge read failed: {exc}", code=1) from exc
        self._append(
            judgements, facts, batch,
            EnqueueEvent(kind="enqueue", at=_now_after(batch), pr=n, head=head, base=base),
        )  # fmt: skip
        return f"enqueued PR #{n} at {head[:12]}", True

    def _record_ejected(self, action: Action, facts: Facts) -> tuple[str, bool]:
        """A queued PR that left the queue unmerged with the base unmoved: recorded once
        per (PR, head) as an `ejected` event, which is the `queue-ejected` need (§D)."""
        judgements = load_judgements(self.target / "judgements.yaml")
        batch = _find(judgements.batches, action.batch)
        last = last_enqueue(batch, action.pr or 0)
        if last is None or last.outcome != "enqueued" or last.head != action.head:
            return "", False
        self._append(
            judgements, facts, batch,
            EnqueueEvent(kind="enqueue", at=_now_after(batch), pr=last.pr, head=last.head,
                         base=last.base, outcome="ejected"),
        )  # fmt: skip
        return f"{action.detail}; it needs you", True

    def _stopped_line(
        self, batch: Batch, action: Action, exc: MergeStopError | GitError, *, failed: bool = True
    ) -> str:
        """A refusal ends neither the loop nor the pass (rg-4): it is reported in full
        once per batch, head and reason, and `--once` exits 1 on it — unless the pass
        handles it (a conflict, §G: `failed=False`). Every stop but a moved head
        (re-judged, not owed) is recorded in `merge-stops.json` at the head it stopped
        at, so the board shows it as needing you (#1008)."""
        if failed:
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
        it acted (wrote an event or handed back). The conflict itself is no failed
        write: the hand-back is the train working (gh#1099); a hand-back that fails
        reports itself."""
        stopped = self._stopped_line(batch, action, exc, failed=False)
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

    # ------------------------------------------------- red recovery (merge-train-safety §C)

    def _recover(self, action: Action, facts: Facts) -> tuple[str, bool]:
        """A failing batch PR the walk stepped over: what `red_decision` says, from the
        persisted events, the base as fetched now and the session's live status (R9-R11).
        Returns the line to print ("" when this pass has nothing new to say) and whether
        it acted (wrote an event, updated the PR, or messaged the session)."""
        from fr_dispatch.protocols import SessionInspector, SessionMessenger

        judgements = load_judgements(self.target / "judgements.yaml")
        batch = _find(judgements.batches, action.batch)
        repo = batch_repo(batch, facts)
        if repo is None or action.pr is None:
            return action.detail, False
        if any(
            isinstance(e, RedHandbackEvent) and (e.pr, e.head) == (action.pr, action.head)
            for e in batch.events
        ):
            return "", False  # rule 1, decided with no I/O: a hand-back covers this head
        ctx = self._ctx_or_hold(facts, repo)
        if ctx is None:  # R13
            return "", False
        events = [*batch.events, *ctx.recorded.get(batch.id, [])]
        try:
            ctx.checkout.fetch()
            base_now = ctx.checkout.rev_parse(ctx.main)
        except (GitError, TriageError) as exc:
            return self._said_once(
                batch, action, "base", f"the base could not be read ({exc}): retried next pass"
            ), False
        checks = action.checks
        # Rules 1-3 never read the session: ask it only when they leave the decision to it.
        decision = red_decision(
            events, action.pr, action.head, checks, base_now, "idle", queue=ctx.rules.merge_queue
        )
        runner: Any = None
        status = "idle"
        if decision == "handback":
            name, target, _ = self._hand_back_target(facts, batch, repo)
            if not self.adapter.carries(name):  # another driver's session
                return self._said_once(
                    batch, action, "carries",
                    f"its session runs on {name}, which this driver lacks: left to that "
                    "runner's driver",
                ), False  # fmt: skip
            runner = self.runner(name)
            if isinstance(runner, SessionMessenger) and isinstance(runner, SessionInspector):
                try:
                    status = runner.session_statuses([target]).get(target.id, "unknown")
                except Exception as exc_:  # noqa: BLE001 - retried next pass
                    return self._said_once(
                        batch, action, "status", f"its session could not be read: {exc_}"
                    ), False
            else:
                status = "absent"  # this runner cannot be messaged: no session can take it
            decision = red_decision(
                events, action.pr, action.head, checks, base_now, status,
                queue=ctx.rules.merge_queue,
            )  # fmt: skip
        if decision == "skip":
            return "", False
        if decision == "reupdate":
            return self._reupdate(action, facts, judgements, batch, repo, ctx)
        if decision == "needs_you":
            event = self._red_event(action, batch, "none")
            self._append(judgements, facts, batch, event)
            return f"{action.detail}; no session can take it: it needs you", True
        if decision == "wait":
            line = self._said_once(
                batch, action, f"wait\0{status}",
                f"its session is {status}: nothing sent, retried next pass",
            )  # fmt: skip
            return line, False
        return self._red_hand_back(action, facts, judgements, batch, repo, name, target, runner)

    def _said_once(self, batch: Batch, action: Action, cause: str, why: str) -> str:
        """The red warn line with *why*, the first time this (batch, head, cause) is seen,
        else "": a pass that decides nothing new says nothing (§C)."""
        key = f"red\0{batch.id}\0{action.head}\0{cause}\0{why}"
        if key in self.reported:
            return ""
        self.reported.add(key)
        return f"{action.detail}; {why}"

    @staticmethod
    def _red_event(action: Action, batch: Batch, delivered: str) -> RedHandbackEvent:
        assert action.pr is not None
        return RedHandbackEvent(
            kind="red_handback", at=_now_after(batch), pr=action.pr, head=action.head,
            checks=list(action.checks), delivered=delivered,  # type: ignore[arg-type]
        )  # fmt: skip

    def _red_hand_back(
        self,
        action: Action,
        facts: Facts,
        judgements: Judgements,
        batch: Batch,
        repo: str,
        name: str,
        target: Any,
        runner: Any,
    ) -> tuple[str, bool]:
        pr = batch_pr(batch, facts)
        brief = red_brief(
            batch, pr_url=pr.url if pr else f"PR #{action.pr}", head=action.head,
            checks=action.checks,
        )  # fmt: skip
        try:
            runner.message(target, brief)
        except Exception as exc_:  # noqa: BLE001 - retried next pass, never the drive's end
            failed = f"hand-back to {target.id} failed, retried next pass: {exc_}"
            return self._said_once(batch, action, "send", failed), False
        self._append(judgements, facts, batch, self._red_event(action, batch, "session"))
        if isinstance(runner, Mailbox):  # sent once the agent records it (§F)
            return f"{action.detail}; handed-back (pending) to its session {target.id}", True
        return f"{action.detail}; handed back to its session {target.id}", True

    def _reupdate(
        self,
        action: Action,
        facts: Facts,
        judgements: Judgements,
        batch: Batch,
        repo: str,
        ctx: MergeContext,
    ) -> tuple[str, bool]:
        """R9: the driver's own update went red and the base moved since: update it again
        through the merge machinery with the green-checks precondition waived. The new
        `update` event is what stops a second update from the same head."""
        entries = [
            e
            for e in pr_open_queue(judgements.batches, facts, judgements.issues)
            if e.batch.id == batch.id
        ]
        try:
            slots, _ = plan_queue(ctx, entries)
            if not slots or slots[0].head != action.head:
                return "", False  # merged, or the head moved: judged again next pass
            writer = event_writer(self.target, facts, read_errors=True)
            ctx.on_update = update_recorder(
                writer, lambda pr: batch.id if pr == slots[0].step.pr.number else None
            )
            attempt = update_failing(ctx, slots[0])
        except UnsupportedForgeOperation as exc:
            _fail(str(exc))
        except MergeConflictError as exc:
            return self._conflict(exc, action, facts, judgements, batch, repo)
        except (MergeStopError, GitError) as exc:
            return self._stopped_line(batch, action, exc), False
        except TriageError as exc:
            _fail(str(exc))
        except FORGE_ERRORS as exc:
            raise ForgeReadError(f"a forge read failed: {exc}", code=1) from exc
        return (
            f"{action.detail}; the base moved: updated PR #{action.pr} to "
            f"{attempt.head[:12]}, its checks run again",
            True,
        )

    @staticmethod
    def _conflict_event(
        exc: MergeConflictError, batch: Batch, delivered: str, handle: str | None = None
    ) -> ConflictEvent:
        return ConflictEvent(
            kind="conflict", at=_now_after(batch), head=exc.head, paths=list(exc.paths),
            delivered=delivered, handle=handle,  # type: ignore[arg-type]
        )  # fmt: skip

    def _hand_back_target(self, facts: Facts, batch: Batch, repo: str) -> tuple[str, Any, Launch]:
        """Where a hand-back goes (conflict or red): the runner's name, the work item of
        the latest fresh conflict session since the dispatch, else the batch's own session,
        and the launch the batch would start a fresh one with."""
        from fr_dispatch.work_item import WorkItem

        last = last_dispatch(batch)
        launch = self._launch(facts, batch, repo)
        name = str(last.runner if last else launch.runner)
        since = fresh_conflicts(batch, since_dispatch=True)
        target = WorkItem(
            id=conflict_item_id(repo, batch.id, fresh_conflicts(batch, since_dispatch=False))
            if since
            else batch_item_id(repo, batch.id),
            unit="run", workflow=batch_workflow(batch), repo=repo, parent=None, inputs=(),
            payload={"group": self.group_of(batch)}, tracking=None,
        )  # fmt: skip
        return name, target, launch

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
        last = last_dispatch(batch)
        name, target, launch = self._hand_back_target(facts, batch, repo)
        branch = last.branch if last else batch_branch(batch)
        ctx = self._ctx_or_hold(facts, repo)
        if ctx is None:  # R13
            return f"{stopped}; held: default branch unknown", False
        brief = conflict_brief(
            batch, pr=action.pr, head=exc.head, paths=exc.paths, branch=branch,
            base=ctx.main, mirrors=facts.config_for(repo).mirrors,
        )  # fmt: skip
        if not self.adapter.carries(name):  # p4-o2: another driver's session
            return (
                f"{stopped}; its session runs on {name}, which this driver lacks: left to "
                "that runner's driver",
                False,
            )
        status, failure = self._offer(name, target, brief)
        if status == "failed":
            return (
                f"{stopped}; hand-back to {target.id} failed, retried next pass: {failure}",
                False,
            )
        if status == "idle":
            event = self._conflict_event(exc, batch, "session", target.id)
            self._append(judgements, facts, batch, event)
            if isinstance(self.runner(name), Mailbox):  # sent once the agent records it (§F)
                return f"{stopped}; handed-back (pending) to its session {target.id}", True
            return f"{stopped}; handed back to its session {target.id}", True
        if status not in (None, "absent", "done"):
            return f"{stopped}; its session is {status}: nothing sent, retried next pass", False
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
                "checkout": str(self.checkout(repo).main_worktree()),
                "group": self.group_of(batch),
            },
            tracking=None,
        )
        handle, live = self._start_fresh(name, item)
        self._append(judgements, facts, batch, self._conflict_event(exc, batch, "fresh", handle))
        if live:
            return f"{stopped}; recorded the live {item.id}", True
        return f"{stopped}; handed back to a fresh session {item.id}", True

    def _offer(self, name: str, target: Any, brief: str) -> tuple[str | None, str]:
        """The hand-back's session step, shared by batch-PR and archive conflicts: the
        target's status, messaging it the brief when it is idle. None: the runner can
        neither tell nor take a message (a fresh session follows, as on `absent`);
        `failed` with the error: retried next pass, never the drive's end."""
        from fr_dispatch.protocols import SessionInspector, SessionMessenger

        runner = self.runner(name)
        if not (isinstance(runner, SessionMessenger) and isinstance(runner, SessionInspector)):
            return None, ""
        try:
            status = runner.session_statuses([target]).get(target.id, "unknown")
            if status == "idle":
                runner.message(target, brief)
        except Exception as exc:  # noqa: BLE001 - retried next pass, never the drive's end
            return "failed", str(exc)
        return status, ""

    def _start_fresh(self, name: str, item: Any) -> tuple[str, bool]:
        """Start *item* through runner *name*, the way a close-out is started: its
        handle, and whether it was live already (a pass killed before its event), in
        which case it is only recorded. A runner that refuses ends the pass."""
        runner = self.runner(name)
        if not runner.can_dispatch(item):
            _fail(f"runner `{name}` does not take run-unit work")
        refusal = runner.preflight([item])
        if refusal:
            _fail(f"runner `{name}` refused: {refusal}")
        if item.id in runner.existing_dispatches([item]):
            return item.id, True
        try:
            handle = runner.dispatch(item)
        except Exception as err:  # the runner's own failure: nothing is written
            _fail(f"runner `{name}` failed to dispatch {item.id}: {err}", code=1)
        return handle or item.id, False

    def _post_merge(
        self, facts: Facts, judgements: Judgements, batch: Batch, repo: str
    ) -> tuple[str, bool]:
        """p4-r2: the repo's `post_merge`, at merge and apart from the close-out, so a
        gated batch's merged build is installed for its walk. From the fast-forwarded
        clone, through the driver adapter (R20); recorded as a `post_merge` event, which
        the close-out waits for. A failure is said and retried next pass."""
        foreign = self.adapter.refusal(batch)
        if foreign is not None:  # another driver's runner dispatched it: its post_merge too
            return f"left to the driver of runner {batch.launch.runner} ({foreign})", False
        checkout = self.checkout(repo)
        try:
            checkout.fast_forward(switch=self.adapter.owns_checkout)
            _fresh_config(checkout, facts, repo)
        except TriageError as exc:
            return f"post_merge held: {exc}", False
        command = facts.config_for(repo).post_merge
        if not command:
            return "no post_merge configured", False
        try:
            ran = self.adapter.post_merge(checkout, command)  # the host's (R20)
        except TriageError as exc:
            return f"post_merge failed, close-out held: {exc}", False
        if not ran:
            return "post_merge is not this driver's to run", False
        self._append(
            judgements, facts, batch, PostMergeEvent(kind="post_merge", at=_now_after(batch))
        )
        installed = _installed_version()
        if installed is not None and installed != __version__:
            self.restart_to = installed  # after this pass: see `batch_drive_command`
        if facts.config_for(repo).post_merge_restart == "idle":
            name = str(self._launch(facts, batch, repo).runner)  # restarted at the pass's end
            self._restart.setdefault(
                name, probe_item(repo, batch, closeout=True, prefix=self.workspace_prefix)
            )
        return f"ran {shlex.join(command)}", True

    def _close_out(
        self, action: Action, facts: Facts, judgements: Judgements, batch: Batch, repo: str
    ) -> tuple[str, bool]:
        """§B step 2 and §C: fast-forward, then the close-out item, once the repo's
        `post_merge` (its own action since p4-r2) has succeeded."""
        foreign = self.adapter.refusal(batch)
        if foreign is not None:  # another driver's runner dispatched it: its close-out too
            return (
                f"left to the driver of runner {batch.launch.runner}, never started through "
                f"a runner this driver lacks ({foreign})"
            ), False  # cloud-triage §E, p4-r10
        if (
            not action.recorded  # a live tab started after its post_merge (the old order)
            and self.adapter.kind == "host"
            and facts.config_for(repo).post_merge
            and not any(e.kind == "post_merge" for e in batch.events)
        ):
            return "close-out held: the repo's post_merge has not succeeded yet", False
        checkout = self.checkout(repo)
        try:
            checkout.fast_forward(switch=self.adapter.owns_checkout)
            _fresh_config(checkout, facts, repo)
            base = checkout.default_branch()
        except TriageError as exc:
            return f"close-out held: {exc}", False
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
        item = _closeout_item(
            repo,
            batch,
            launch,
            run=run,
            checkout=checkout.main_worktree(),
            group=self.group_of(batch),
            base=base,
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
            _write(self.target, judgements.batches, facts, read=after, read_errors=True)
            return self._dispatch_failed(
                batch, f"runner `{launch.runner}` failed to dispatch {item.id}: {exc}", exc
            ), False
        if handle and handle != item.id:  # the runner's own handle, once it is known
            known = started.model_copy(update={"handle": handle})
            final = recorded.model_copy(update={"events": [*recorded.events[:-1], known]})
            _write(self.target, _replace(after, final), facts, read=after, read_errors=True)
        pickup = f"--run {run}" if run else f"--branch {branch}"
        return f"started {item.id} (fr pickup {pickup})", True

    def _collected_close_out(
        self, action: Action, facts: Facts, judgements: Judgements, repo: str
    ) -> tuple[str, bool]:
        """R15: start ONE close-out session for *action*'s batches, briefed to run `fr
        triage batch closeout`. Each member's close-out event (`archive` the shared branch)
        is recorded before the tab starts (gh#883) and taken back if it cannot start."""
        members: list[Batch] = []
        skipped: list[str] = []  # post_merge not yet run: a close-out hold, retried next pass
        foreign: list[str] = []  # another driver's runner: its close-out is not this driver's
        for bid in action.items:
            b = _find(judgements.batches, bid)
            if self.adapter.refusal(b) is not None:
                foreign.append(f"left to the driver of runner {b.launch.runner} ({bid})")
            elif (
                self.adapter.kind == "host"
                and facts.config_for(repo).post_merge
                and not any(e.kind == "post_merge" for e in b.events)
            ):
                skipped.append(f"{bid} (its post_merge has not succeeded)")
            else:
                members.append(b)
        if not members:  # cloud-triage §E, p4-r10: a foreign batch is not a hold
            parts = ([f"close-out held: {'; '.join(skipped)}"] if skipped else []) + foreign
            return "; ".join(parts), False
        checkout = self.checkout(repo)
        try:
            checkout.fast_forward(switch=self.adapter.owns_checkout)
            _fresh_config(checkout, facts, repo)
            base = checkout.default_branch()
            day = _now().date()
            used = collected_used(repo, judgements.batches, judgements.closeouts)
            n = collected.next_collected([*used, f"chore/{action.key}"], day) - 1
            while checkout.remote_branch_exists(collected.collected_branch(day, n)):
                n += 1  # a closeout run by hand, or a start that died: never reuse its head
        except TriageError as exc:
            return f"close-out held: {exc}", False
        branch = collected.collected_branch(day, n)
        name = str(collected.collected_name(branch))
        launch = self._launch(facts, members[0], repo)
        item = _collected_item(
            repo, members, launch, name=name, branch=branch, checkout=checkout.main_worktree(),
            group=self.group_of(members[0]), base=base, scope_args=self.scope_args,
        )  # fmt: skip
        runner = self.runner(str(launch.runner))
        if not runner.can_dispatch(item):
            _fail(f"runner `{launch.runner}` does not take run-unit work")
        refusal = runner.preflight([item])
        if refusal:
            _fail(f"runner `{launch.runner}` refused: {refusal}")
        # The start marker, recorded BEFORE the tab starts (gh#883): it is the dedupe key,
        # never membership, which only the verb records (p6-r1).
        path = self.target / "judgements.yaml"
        read = list(judgements.closeouts)
        planned = [b.id for b in members]
        marker = CollectedCloseout(repo=repo, item=item.id, branch=branch, at=_now(),
                                   runner=str(launch.runner), planned=planned)  # fmt: skip
        try:
            save_closeouts(path, [*read, marker], read=read)
        except TriageError as exc:
            return f"close-out held: {exc}", False
        try:
            handle = runner.dispatch(item)
        except Exception as exc:  # the runner's own failure: nothing started, taken back
            save_closeouts(path, read, read=[*read, marker])
            return self._dispatch_failed(
                members[0], f"runner `{launch.runner}` failed to dispatch {item.id}: {exc}", exc
            ), False
        if handle and handle != item.id:  # the runner's own handle, once it is known
            save_closeouts(path, [*read, marker.model_copy(update={"handle": handle})],
                           read=[*read, marker])  # fmt: skip
        later = [*(f"{s}" for s in skipped), *foreign]
        left = f"; not now: {'; '.join(later)}" if later else ""
        return f"started {item.id} for {', '.join(b.id for b in members)}{left}", True

    def _collected_merged(self, action: Action, facts: Facts, repo: str) -> None:
        """Its PR merged: the marker records it, and each issue the body `Closes` (closed by
        the merge itself, p6-r8) loses `fr:awaiting-live` — only the RECORDED closes, only
        in the marker's repo (p6b-r5), never what the body says. A failed label write is
        said and never undoes the merge."""
        judgements = load_judgements(self.target / "judgements.yaml")
        marker = next((c for c in judgements.closeouts if c.item == action.key), None)
        if marker is not None:
            _save_marker(self.target, marker.branch, pr=action.pr, merged=True)
        client = self.client(facts, repo)
        if marker is None:
            return
        try:
            for ref in marker.closes:
                where, _, n = ref.rpartition("#")
                if where.lower() != marker.repo.lower():
                    continue
                client.edit_issue_labels(where, int(n), add=frozenset(),
                                         remove=frozenset({FR_AWAITING_LIVE.name}))  # fmt: skip
        except FORGE_ERRORS as exc:
            self.failed_write = True
            why = f"cannot remove {FR_AWAITING_LIVE.name} after PR #{action.pr}: {exc}"
            self._report_once(f"unlabel\0{action.key}\0{exc}", why)

    def _collected_record(
        self, action: Action, facts: Facts, judgements: Judgements, repo: str
    ) -> str:
        """Bookkeeping a collected close-out's PR asks for (R15): `reconcile`, the batches
        its body lists get their close-out events (a verb killed between push and record);
        `merged`, every member archived and the marker merged; `pr-closed` / `abandoned`,
        the marker ends with no archive, so its batches are owed again (p6-r5)."""
        marker = next((c for c in judgements.closeouts if c.item == action.key), None)
        if marker is None:
            return action.detail
        if action.kind == "closeout-merged":
            written = list(judgements.batches)
            for bid in action.items:
                member = _find(written, bid)
                event = closeout_event(member)
                if event is not None and event.archived is None:
                    done = event.model_copy(update={"at": _now_after(member),
                                                    "archived": action.pr})  # fmt: skip
                    written = _replace(written, member.model_copy(
                        update={"events": [*member.events, done]}))  # fmt: skip
            _write(self.target, written, facts, read=judgements.batches, read_errors=True)
            self._collected_merged(action, facts, repo)
        else:
            _save_marker(self.target, marker.branch, closed=True, pr=action.pr)
        return action.detail

    def _closeout_hand_back(
        self, action: Action, facts: Facts, judgements: Judgements, repo: str
    ) -> tuple[str, bool]:
        """R27: prompt the collected close-out's session with the conflict or the failing
        checks, and record a `closeout_handback` event on each member, keyed by the item
        and the head: the budget of one is spent whether a session took it or not."""
        from fr_dispatch.protocols import SessionMessenger
        from fr_dispatch.work_item import WorkItem

        members = [_find(judgements.batches, b) for b in action.items]
        started = closeout_event(members[0])
        marker = next((c for c in judgements.closeouts if c.item == action.key), None)
        name = marker.runner if marker is not None else "hand"
        if name != "hand" and not self.adapter.carries(name):
            return f"{action.detail}; its session runs on {name}: left to that driver", False
        default = self.merge_ctx(facts, repo).main
        branch = (started.archive or "") if started is not None else ""
        brief = collected.handback_brief(
            pr=action.pr or 0, branch=branch, base=default, checks=action.checks
        )
        delivered = "none"
        if name != "hand":
            runner = self.runner(name)
            if isinstance(runner, SessionMessenger):
                target = WorkItem(
                    id=action.key, unit="run", workflow=batch_workflow(members[0]), repo=repo,
                    parent=None, inputs=(), payload={"group": self.group_of(members[0])},
                    tracking=None,
                )  # fmt: skip
                try:
                    runner.message(target, brief)
                except Exception as exc:  # noqa: BLE001 - retried next pass, never the drive's end
                    return f"hand-back to {action.key} failed, retried next pass: {exc}", False
                delivered = "session"
        written = list(judgements.batches)
        for member in members:
            event = CloseoutHandbackEvent(
                kind="closeout_handback", at=_now_after(member), item=action.key,
                pr=action.pr or 0, head=action.head, reason=", ".join(action.checks),
                delivered=delivered,  # type: ignore[arg-type]
            )  # fmt: skip
            written = _replace(written, member.model_copy(
                update={"events": [*member.events, event]}))  # fmt: skip
        _write(self.target, written, facts, read=judgements.batches, read_errors=True)
        if marker is not None:  # the item's own count, members or not (p6b-r10)
            _save_marker(self.target, marker.branch, handed=[*marker.handed, action.head])
        if delivered == "none":
            return f"{action.detail}; no session can take it: the operator's", True
        return f"{action.detail}; handed back to its session {action.key}", True

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
        _write(
            self.target, _replace(judgements.batches, new), facts, read=judgements.batches,
            read_errors=True,
        )  # fmt: skip
        return new

    def _archive(
        self, action: Action, facts: Facts, judgements: Judgements, batch: Batch, repo: str
    ) -> tuple[str, bool]:
        ctx = self._ctx_or_hold(facts, repo)
        if ctx is None:  # R13
            return "held: default branch unknown", False
        assert action.pr is not None
        step = "refused the merge"
        try:
            if action.draft:  # merge-truth R11; a collected close-out's PR the same (R15)
                step = "refused to mark it ready"
                ctx.client.pr_ready(repo, action.pr)
                step = "refused the merge"
            ctx.client.pr_merge(repo, action.pr, head_sha=action.head, method=ctx.method)
        except UnsupportedForgeOperation as exc:
            _fail(str(exc))
        except FORGE_ERRORS as exc:
            # As a refused batch-PR merge (rg-4): reported in full once per batch, head
            # and reason, merged again on a later pass; `--once` exits 1 (gh#921).
            self.failed_write = True
            stamp = datetime.now(UTC).isoformat(timespec="seconds")
            stop = MergeStop(action.head, str(exc), stamp)
            record_stop(self.target, archive_stop_key(batch.id), stop)
            key = f"archive\0{batch.id}\0{action.head}\0{exc}"
            if key in self.reported:
                return f"stopped again at {action.head[:12]} (reported above)", False
            self.reported.add(key)
            return f"stopped: archive PR #{action.pr}: the forge {step}: {exc}", False
        # Record it: a PR attributed by its files alone is not found again once it
        # left the open-PR list, and the batch would read as closing forever (rg-6). A
        # collected close-out's PR is recorded on every member (R15).
        members = [_find(judgements.batches, b) for b in action.items] or [batch]
        written = list(judgements.batches)
        for member in members:
            event = closeout_event(member)
            if event is not None:
                done = event.model_copy(update={"at": _now_after(member), "archived": action.pr})
                written = _replace(written, member.model_copy(
                    update={"events": [*member.events, done]}))  # fmt: skip
        _write(self.target, written, facts, read=judgements.batches, read_errors=True)
        if action.key:  # a collected close-out's PR (R15)
            self._collected_merged(action, facts, repo)
        clear_stop(self.target, archive_stop_key(batch.id))  # its stop is over (R12)
        readied = "marked ready, " if action.draft else ""
        return f"{readied}merged archive PR #{action.pr}", True

    # ------------------------------------- archive conflicts (merge-truth R12, §E)

    def _archive_conflict(
        self, action: Action, facts: Facts, judgements: Judgements, batch: Batch, repo: str
    ) -> tuple[str, bool]:
        """A conflicting archive PR is never merged: handed to the close-out once per
        head, at most twice per close-out, then held for the operator with a stop."""
        assert action.pr is not None
        decision = archive_conflict_decision(batch.events, action.head)
        if decision == "skip":
            return f"archive PR #{action.pr} at {action.head[:12]} was handed back already", False
        if decision == "held":
            self._append(
                judgements, facts, batch, self._archive_conflict_event(action, batch, "held")
            )
            stamp = datetime.now(UTC).isoformat(timespec="seconds")
            reason = f"archive PR #{action.pr} conflicts"
            stop = MergeStop(action.head, reason, stamp)
            record_stop(self.target, archive_stop_key(batch.id), stop)
            return f"{reason} and its hand-backs are spent: held for the operator", True
        return self._hand_back_archive(action, facts, judgements, batch, repo)

    @staticmethod
    def _archive_conflict_event(
        action: Action, batch: Batch, delivered: ConflictDelivery, handle: str | None = None
    ) -> ArchiveConflictEvent:
        assert action.pr is not None
        return ArchiveConflictEvent(
            kind="archive_conflict", at=_now_after(batch), head=action.head, pr=action.pr,
            delivered=delivered, handle=handle,
        )  # fmt: skip

    def _hand_back_archive(
        self, action: Action, facts: Facts, judgements: Judgements, batch: Batch, repo: str
    ) -> tuple[str, bool]:
        """Deliver the brief to the close-out: its idle session, else nothing while it is
        working or blocked, else a fresh archive-conflict session (R12)."""
        from fr_dispatch.work_item import WorkItem

        assert action.pr is not None
        event = closeout_event(batch)
        launch = self._launch(facts, batch, repo)
        name = str(event.runner if event is not None and event.runner != "hand" else launch.runner)
        if not self.adapter.carries(name):  # before the brief: it reads the merge context
            return (
                f"its close-out runs on {name}, which this driver lacks: left to that "
                "runner's driver",
                False,
            )
        ctx = self._ctx_or_hold(facts, repo)
        if ctx is None:  # R13
            return "held: default branch unknown", False
        brief = archive_conflict_brief(
            batch, pr=action.pr, head=action.head, branch=action.branch, base=ctx.main,
        )  # fmt: skip
        target = WorkItem(
            id=closeout_item_id(repo, batch.id), unit="run", workflow=batch_workflow(batch),
            repo=repo, parent=None, inputs=(), payload={"group": self.group_of(batch)},
            tracking=None,
        )  # fmt: skip
        status, failure = self._offer(name, target, brief)
        if status == "failed":
            return f"hand-back to {target.id} failed, retried next pass: {failure}", False
        if status == "idle":
            self._append(
                judgements, facts, batch,
                self._archive_conflict_event(action, batch, "session", target.id),
            )  # fmt: skip
            if isinstance(self.runner(name), Mailbox):  # sent once the agent records it (§F)
                return f"handed-back (pending) to its close-out session {target.id}", True
            return f"handed back to its close-out session {target.id}", True
        if status not in (None, "absent", "done"):
            return f"its close-out session is {status}: nothing sent, retried next pass", False
        fresh = sum(
            1 for e in batch.events
            if isinstance(e, ArchiveConflictEvent) and e.delivered == "fresh"
        )  # fmt: skip
        item = WorkItem(
            id=archive_conflict_item_id(repo, batch.id, fresh + 1),
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
                "branch": action.branch,
                "issues": list(batch.ids),
                "checkout": str(self.checkout(repo).main_worktree()),
                "group": self.group_of(batch),
            },
            tracking=None,
        )
        handle, live = self._start_fresh(name, item)
        self._append(
            judgements, facts, batch,
            self._archive_conflict_event(action, batch, "fresh", handle),
        )  # fmt: skip
        if live:
            return f"recorded the live {item.id}", True
        return f"handed back to a fresh session {item.id}", True

    def _export_conflict(self, action: Action) -> str:
        """A conflicting export PR: no session owns it, so it goes straight to the
        operator with a stop keyed `export:<repo>` (R12)."""
        stamp = datetime.now(UTC).isoformat(timespec="seconds")
        reason = f"export PR #{action.pr} conflicts"
        record_stop(
            self.target, export_stop_key(action.batch), MergeStop(action.head, reason, stamp)
        )
        return action.detail

    # ------------------------------------------------------- state export (R13)

    def _export_act(self, action: Action, facts: Facts) -> str:
        assert action.wave is not None
        if action.kind == "export":
            return self._export(action, facts, action.batch, action.wave)
        if action.kind == "export-reconcile":  # merged outside the driver (p4-r1)
            assert action.pr is not None
            self._mark(action.batch, action.pr, merged=True)
            clear_stop(self.target, export_stop_key(action.batch))  # its stop is over (R12)
            return f"recorded export PR #{action.pr} as merged"
        if action.kind == "export-closed":  # closed unmerged: said once (p4-r6)
            assert action.pr is not None
            self._mark(action.batch, action.pr, closed=True)
            clear_stop(self.target, export_stop_key(action.batch))  # its stop is over (R12)
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
        branch = export_branch(wave, scope_id(self.scope))
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
                report = export_state(
                    self.target, worktree.path, rel, owner=scope_id(self.scope)
                )  # never takes over another scope's export (gh#1101)
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
        ctx = self._ctx_or_hold(facts, repo)
        if ctx is None:  # R13
            return "held: default branch unknown"
        assert action.pr is not None
        try:
            if action.draft:  # a collected close-out's PR is readied once clean (R15)
                ctx.client.pr_ready(repo, action.pr)
            ctx.client.pr_merge(repo, action.pr, head_sha=action.head, method=ctx.method)
        except UnsupportedForgeOperation as exc:
            _fail(str(exc))
        except FORGE_ERRORS as exc:
            return self._export_failed(
                wave, f"export PR #{action.pr}: the forge refused the merge: {exc}"
            )
        self._mark(repo, action.pr, merged=True)
        clear_stop(self.target, export_stop_key(repo))  # a conflict stop on it is over (R12)
        return f"merged export PR #{action.pr} at {action.head[:12]}"


# The actions a pass plans only from what it read live this pass (R10): a carried repo's
# batches get none of them.
_GATE_WRITE_FAILURES: tuple[type[Exception], ...] = (*FORGE_ERRORS, UnsupportedForgeOperation)
"""What a gate-ledger write (`awaiting-live`, `gate-pass`) may fail with: reported and
planned again next pass, never fatal to the pass."""

_LIVE_READ_ACTIONS = frozenset(
    {"merge", "update", "closeout", "archive", "archive-conflict", "adopt", "settle", "post-merge"}
)


def _op_repo(env: ClaimEnv, op: ClaimOp, repos: Mapping[str, str]) -> str | None:
    """The repo *op* writes in: a settle's is its key's (it may hold no batch), any other
    op's is its batch's."""
    if op.kind == "settle":
        return env.owner_repo(op.key)
    return repos.get(op.batch or "")


def read_repo(action: Action, repos: Mapping[str, str], env: ClaimEnv | None) -> str | None:
    """The repo a live-read *action* reads, to hold it back when that repo was carried: its
    batch's, or for a settle (which may name no batch) its key's."""
    if action.kind == "settle":
        return env.owner_repo(action.key) if env is not None else None
    return repos.get(action.batch)


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
    base: str | None = None,
) -> WorkItem:
    """The close-out work item (§C): unit `run`, `payload.kind: closeout`, model from
    `resolve_launch`, checkout from the `--checkout` map. `base` is the repo's default
    branch, where a runner that starts a session on a branch starts it: the batch
    branch was deleted when its PR merged (gh#1099)."""
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
    if base:
        payload["base"] = base
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


def collected_brief(
    repo: str, ids: Sequence[str], *, branch: str, checkout: Path, scope_args: Sequence[str]
) -> str:
    """The collected close-out's brief (R15): run the verb once; fix a hand-back (R27)."""
    verb = shlex.join(
        ["fr", "triage", "batch", "closeout", *ids, "--branch", branch, "--yes", *scope_args]
    )
    return (
        f"Close out batches {', '.join(ids)} of {repo}: their PRs have merged.\n"
        f"In {checkout}, run `{verb}` once and report what it prints. It opens ONE PR "
        f"on {branch}; the driver merges it once it is green.\n"
        f"If the driver hands that PR back (a conflict or failing checks), fix it on "
        f"{branch} and push; it hands back once."
    )


def _collected_item(
    repo: str,
    members: Sequence[Batch],
    launch: Launch,
    *,
    name: str,
    branch: str,
    checkout: Path,
    group: str | None,
    base: str,
    scope_args: Sequence[str],
) -> WorkItem:
    """The collected close-out's work item (§E): unit `run`, id `closeout-<date>-<n>`."""
    from fr_dispatch.work_item import WorkItem

    ids = [b.id for b in members]
    payload: dict[str, Any] = {
        "kind": "closeout",
        "brief": collected_brief(
            repo, ids, branch=branch, checkout=checkout, scope_args=scope_args
        ),  # fmt: skip
        "harness": launch.harness,
        "model": launch.model,
        "branch": recorded_branch(members[0]),  # the first member's: as a per-batch item's
        "issues": [k for b in members for k in b.ids],
        "checkout": str(checkout),
        "base": base,
    }
    if group:
        payload["group"] = group
    return WorkItem(
        id=collected_item_id(repo, name), unit="run", workflow=batch_workflow(members[0]),
        repo=repo, parent=None, inputs=(), payload=payload, tracking=None,
    )  # fmt: skip


def build_driver(
    scope: Scope,
    target: Path,
    *,
    batch_ids: list[str] | None,
    checkout: list[str] | None,
    max_inflight: int,
    yes: bool,
    workspace_prefix: str = DEFAULT_WORKSPACE_PREFIX,
    keep_sessions: bool = False,
    scope_args: list[str] | None = None,
    adapter: Driver = HOST,
    statuses: Any = None,
    lease: LeaseTerms | None = None,
    single_pass: SinglePass | None = None,
) -> _Driver:
    """The one `_Driver` both adapters run (cloud-triage R10, R13): the batches to drive,
    their clones, and the adapter, lease and statuses of where it runs."""
    path = target / "judgements.yaml"
    try:
        known = load_judgements(path).batches if path.exists() else []
    except TriageError as exc:
        _fail(str(exc))
    chosen = _chosen(known, batch_ids) if known else []
    names = {_batch_slug(scope, b.repo_name) for b in chosen}
    return _Driver(
        scope,
        target,
        named=batch_ids,
        checkouts=_checkout_map(checkout, scope, names),
        max_inflight=max_inflight,
        yes=yes,
        workspace_prefix=workspace_prefix,
        keep_sessions=keep_sessions,
        scope_args=scope_args,
        driver=adapter,
        statuses=statuses,
        lease=lease,
        single_pass=single_pass,
    )


def one_pass(driver: _Driver, *, lease_taken: bool = False) -> tuple[bool, Summary, list[str]]:
    """THE pass, the host loop's body and the cloud driver's every wake alike (cloud-triage
    R12, R13): with --yes, fetch the state ref and renew the lease (pushed), run the pass
    (`_Driver.run_pass`: collect, plan with `batch_drive.drive_pass`, act), then record the
    pass on the lease and push the state. Whether it acted, the summary, the blocked ids."""
    if driver.yes and not lease_taken:  # the cloud pass took it before its self-update
        driver.take_lease()
    result = driver.run_pass()
    if driver.yes:
        driver.save_pass()
    return result


def pass_exit(driver: _Driver, acted: bool, summary: Summary) -> int:
    """The exit code of one acting pass (`--once`, `drive pass`): 1 a forge write failed,
    0 it acted or everything is done, 3 nothing to do but wait."""
    if driver.failed_write:
        return 1
    return 0 if acted or summary.done else 3


def _host_lease(scope: Scope, target: Path, interval_s: int) -> LeaseTerms | None:
    """The host driver's lease (R9), when the scope has a state ref to hold it on: a scope
    with no state repo has only this host's `drive.lock`. One with a state repo whose state
    sits in no clone cannot sync the ref, so it refuses (exit 2) naming --workspace rather
    than drive unleased beside a cloud driver (cloud-triage §E, p4-r3)."""
    from fr.commands.triage_cmd import state_clone
    from fr.triage.lease import DEFAULT_ROUTINE_MIN, driver_identity, lease_duration
    from fr.triage.scope_config import host_id

    try:
        state_repo = load_durable(target).state_repo
        if state_repo is None:
            return None
        if state_clone(target) is None:
            _fail(
                f"{target} is in no git clone, so this driver cannot sync the state ref in "
                f"{state_repo} nor hold the scope's drive lease, and will not drive unleased "
                "beside another driver: run from a clone, or pass --workspace <clone>"
            )
        identity = driver_identity("host", host_id())
    except TriageError as exc:
        _fail(str(exc))
    return LeaseTerms(identity, lease_duration(interval_s / 60, DEFAULT_ROUTINE_MIN))


@contextmanager
def _sigterm_interrupts() -> Iterator[None]:
    """SIGTERM raises `KeyboardInterrupt` for the block's duration, so a terminated driver
    stops as a Ctrl-C does and releases its lease (cloud-triage §E, p4-r4); the previous
    handler is restored after. Off the main thread no handler can be installed: a no-op."""
    import signal
    import threading

    if threading.current_thread() is not threading.main_thread():
        yield
        return

    def interrupt(signum: int, frame: object) -> None:
        raise KeyboardInterrupt

    previous = signal.signal(signal.SIGTERM, interrupt)
    try:
        yield
    finally:
        signal.signal(signal.SIGTERM, previous)


def _host_loop(
    driver: _Driver, *, once: bool, interval: int, pacer: Pacer | None = None
) -> str | None:
    """`fr triage batch drive`'s loop around `one_pass` (the host adapter, R10). The newer
    fr a `post_merge` installed, when the loop stopped to restart on it; else None.
    With a *pacer*, a looping drive reads the budget before each pass, waits out an
    exhausted one, and backs off a rate limit instead of retrying it (R2-R4)."""
    paced = pacer if pacer is not None and driver.yes and not once else None
    driver.pacer = paced
    pace: Pace | None = None
    while True:
        if paced is not None:
            pace = paced.before_pass()
            if pace.kind == "wait":
                _say(paced.line(pace))
                wait_out(driver, pace)
                continue
            driver.pace = pace
            if pace.essential:  # below the floor: the essential-only pass (R7, R13)
                _say(paced.line(pace))
                paced.stretch(pace.until)
        try:
            acted, summary, blocked = one_pass(driver)
        except ForgeReadError as exc:
            if once or not driver.yes:
                _fail(str(exc), code=exc.code)
            if paced is not None and paced.limited(str(exc)):
                pace = paced.rate_limited()
                _say(paced.line(pace))
                if driver.restart_to is not None:
                    return driver.restart_to
                wait_out(driver, pace)
                continue
            # Like a refused merge (rg-4), a degraded forge ends neither the run nor
            # the loop: reported once per cause, then read again (gh#910).
            _report_read_failure(driver, str(exc), f"pass skipped, retrying every {interval}s")
            if driver.restart_to is not None:  # a skipped save_pass follows a pass whose
                return driver.restart_to  # post_merge installed a newer fr (gh#998)
            _sleep(interval)
            continue
        driver.read_failures.clear()
        if paced is not None and driver.failed_write and paced.limited():
            # a failed write with the budget gone is the limit, not a clean pass (p1-r2)
            pace = paced.rate_limited()
            _say(paced.line(pace))
            if driver.restart_to is not None:
                return driver.restart_to
            wait_out(driver, pace)
            continue
        if paced is not None:
            paced.clean()
        if not driver.yes:
            return None  # the plan of one pass, in loop mode too
        if once:
            driver.warn_single_pass()
            code = pass_exit(driver, acted, summary)
            if code:
                raise typer.Exit(code=code)
            return None
        if summary.done:
            if driver.observation_owed():
                continue  # the last wave's transition is seen only by one more pass
            return None
        if driver.restart_to is not None:
            return driver.restart_to
        if summary.stalled:
            _say(_stalled_line(blocked, driver.held_by))
            raise typer.Exit(code=3)
        if pace is not None and pace.essential and pace.until is not None:
            wait_out(driver, Pace("wait", pace.until, "below floor"))  # 4x, lease-safe (R16)
            continue
        _sleep(interval)


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
    quota_floor: QuotaFloorOpt = None,
    single_pass: Annotated[
        bool,
        typer.Option(
            "--single-pass",
            help="With --once --yes: one pass that dispatches is deliberate (it leaves no "
            "driver behind).",
        ),
    ] = False,
    repo: RepoOpt = None,
    org: OrgOpt = None,
    dir_override: DirOpt = None,
    workspace: WorkspaceOpt = None,
) -> None:
    """Drive batches to completion: merge what is ready, close out what merged,
    dispatch what may start (wave order, then merge order, then id).

    Exit codes: 0 acted or everything is done; 3 nothing to do while work remains;
    2 a refusal (a runner's preflight included); 1 a forge write failed.
    """
    if not workspace_prefix.strip():
        _fail("--workspace-prefix must not be blank")
    if single_pass and not once:
        _fail("--single-pass only applies to --once: a looping driver is not a single pass")
    scope = _scope(repo, org)
    target = resolve_state_dir(scope, dir_override, workspace)
    pacer = make_pacer(target, quota_floor=quota_floor, interval_s=interval)  # refuses a bad floor
    guard: SinglePass | None = None
    if once and yes:
        command = loop_command(
            batch_ids=batch_ids,
            scope=scope,
            scope_args=triage_kanban_cmd.scope_args(repo, org, dir_override, workspace),
            max_inflight=max_inflight,
            interval=interval,
            workspace_prefix=workspace_prefix,
            keep_sessions=keep_sessions,
            checkout=checkout,
            toplevel=_default_toplevel()
            if scope.kind == "repo" and not _names_repo(checkout, scope.target)
            else None,
        )
        guard = SinglePass(single_pass_notice(command), allowed=single_pass)
    driver = build_driver(
        scope,
        target,
        batch_ids=batch_ids,
        checkout=checkout,
        max_inflight=max_inflight,
        yes=yes,
        workspace_prefix=workspace_prefix,
        keep_sessions=keep_sessions,
        scope_args=triage_kanban_cmd.scope_args(repo, org, dir_override, workspace),
        lease=_host_lease(scope, target, interval) if yes else None,
        single_pass=guard,
    )
    restart: str | None = None
    with drive_lock(drive_lock_dir(scope, dir_override)):  # the fast same-host check first
        try:
            with _sigterm_interrupts():
                restart = _host_loop(driver, once=once, interval=interval, pacer=pacer)
        except KeyboardInterrupt:  # Ctrl-C or SIGTERM: a clean stop too (p4-r4)
            driver.release_lease()
            raise
        except typer.Exit as stop:
            if once:
                driver.warn_single_pass()
            if stop.exit_code != 2:  # a clean stop; a refusal keeps what it found
                driver.release_lease()
            raise
        driver.release_lease()
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
