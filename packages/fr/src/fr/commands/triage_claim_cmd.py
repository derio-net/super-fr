"""`fr triage scope show` and the `fr triage claim` group (spec 2026-10-06-triage-claims §3.A,
§3.E; R1, R7, R9).

`claim list` reads facts only. `claim sync`, `take` and `release` print what they would write
and write it only under `--yes`, through `fr.triage.claim_sync` / `fr.triage.claim_writes`.
The forge client, the scope id and the scope config come from `triage_batch_cmd.claim_env`,
the one resolver the batch verbs share.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
import yaml

from fr.commands import triage_batch_cmd
from fr.commands.triage_cmd import (
    DirOpt,
    OrgOpt,
    RepoOpt,
    _load_state,
    _scope,
    console,
    print_claim_sets,
    triage_app,
)
from fr.commands.triage_kanban_cmd import _fail
from fr.ghclient import UnsupportedForgeOperation
from fr.hostclient import FORGE_ERRORS
from fr.triage import claim_writes as cw
from fr.triage.check import claim_sets
from fr.triage.claim_sync import ClaimEnv, SyncResult, execute, plan_sync, record_releases
from fr.triage.claims import Claim, from_issue_claim, holder
from fr.triage.errors import TriageError
from fr.triage.model import Batch, Facts, normalize_key, state_dir
from fr.triage.scope_config import default_board_name, load_scope_config, scope_id

scope_app = typer.Typer(name="scope", help="This triage scope's identity and config.")
claim_app = typer.Typer(
    name="claim",
    help="Claims: which scope may act on an issue (fr:claimed plus a marker comment).",
    no_args_is_help=True,
)
triage_app.add_typer(scope_app)
triage_app.add_typer(claim_app)

YesOpt = Annotated[bool, typer.Option("--yes", help="Write; without it, print the plan.")]
KeyArg = Annotated[str, typer.Argument(help="The issue, <repo-name>#<n>.")]


def _now() -> datetime:
    """The clock claims are judged by; tests replace it."""
    return datetime.now(UTC)


@scope_app.command("show")
def scope_show_command(
    repo: RepoOpt = None, org: OrgOpt = None, dir_override: DirOpt = None
) -> None:
    """Print the scope's name, id, state directory and scope config. Never touches the forge."""
    scope = _scope(repo, org)
    target = state_dir(scope, dir_override)
    try:
        sid, config = scope_id(scope), load_scope_config(target)
    except TriageError as exc:
        _fail(str(exc))
    console.print(f"name: {scope.name}", markup=False, soft_wrap=True)
    console.print(f"id: {sid}", markup=False)
    console.print(f"state dir: {target}", markup=False, soft_wrap=True)
    console.print(
        f"board name: {config.board_name or default_board_name(scope)}",
        markup=False,
        soft_wrap=True,
    )
    body = yaml.safe_dump(config.model_dump(), sort_keys=False).rstrip()
    console.print("config:", markup=False)
    for line in body.splitlines():
        console.print(f"  {line}", markup=False, soft_wrap=True)


@claim_app.command("list")
def claim_list_command(
    repo: RepoOpt = None, org: OrgOpt = None, dir_override: DirOpt = None
) -> None:
    """This scope's held-elsewhere, expired and owed claims, from facts. Always exits 0."""
    scope = _scope(repo, org)
    target, facts, judgements = _load_state(scope, dir_override)
    env = triage_batch_cmd.claim_env(scope, target, facts)
    print_claim_sets(claim_sets(facts, judgements, env.me, _now()))


def _say_result(result: SyncResult) -> None:
    for op, done in result.done:
        console.print(f"  {op.kind} {op.key} ({op.batch}): {done.action}", markup=False)
    for h in result.held:
        console.print(
            f"  held {h.key} ({h.batch}) by {h.holder.signer} (batch {h.holder.batch})",
            markup=False,
        )


@claim_app.command("sync")
def claim_sync_command(
    yes: YesOpt = False, repo: RepoOpt = None, org: OrgOpt = None, dir_override: DirOpt = None
) -> None:
    """Write every owed claim, due refresh and owed release (R3, R8, R10, R11)."""
    scope = _scope(repo, org)
    target, facts, judgements = _load_state(scope, dir_override)
    env = triage_batch_cmd.claim_env(scope, target, facts)
    now = _now()
    plan = plan_sync(env, judgements.batches, now)
    for op in plan.ops:
        if op.kind == "claim":
            console.print(f"claim {op.key} for {op.batch}", markup=False)
        else:
            console.print(f"{op.kind} {op.key} ({op.batch})", markup=False)
    for h in plan.held:
        console.print(
            f"held {h.key} ({h.batch}): {h.holder.signer} holds it for batch {h.holder.batch}, "
            f"expires {h.holder.expires.isoformat()}",
            markup=False,
            soft_wrap=True,
        )
    if not plan.ops:
        console.print("nothing owed", markup=False)
        return
    if not yes:
        console.print(
            "nothing written; re-run with `fr triage claim sync --yes` to write", markup=False
        )
        return
    try:
        result = execute(env, plan.ops, now)
    except UnsupportedForgeOperation as exc:
        _fail(str(exc))
    _say_result(result)
    _record(target, facts, judgements.batches, result, now)
    if result.failed:
        _fail(
            "these were not written; re-run to complete: "
            + "; ".join(f"{op.kind} {op.key}: {why}" for op, why in result.failed),
            code=1,
        )


def _record(
    target: Path, facts: Facts, batches: list[Batch], result: SyncResult, now: datetime
) -> None:
    """Append the `claims_released` events `result` earned, through the one writer."""
    recorded = record_releases(batches, result, now)
    if recorded != list(batches):
        triage_batch_cmd._write(target, recorded, facts, read=list(batches))


def _foreign(env: ClaimEnv, key: str) -> tuple[Claim | None, Claim | None]:
    """(this scope's claim, the foreign holder) on *key*, from facts."""
    issue = env.issue(key)
    claims = [from_issue_claim(c) for c in issue.claims] if issue is not None else []
    own = next((c for c in claims if c.signer == env.me), None)
    return own, holder(claims, env.me)


def _repo_of(env: ClaimEnv, key: str) -> tuple[str, int]:
    owner_repo = env.owner_repo(key)
    if owner_repo is None:
        _fail(f"{key}: its repo is not in this scope's facts")
    return owner_repo, int(key.rpartition("#")[2])


def _write_one(call: Callable[[], cw.Outcome], key: str) -> cw.Outcome:
    try:
        out: cw.Outcome = call()
    except (cw.ClaimError, UnsupportedForgeOperation) as exc:
        _fail(str(exc))
    except FORGE_ERRORS as exc:
        _fail(f"{key}: {exc}", code=1)
    return out


@claim_app.command("take")
def claim_take_command(
    key: KeyArg,
    batch: Annotated[str, typer.Option("--batch", help="This scope's batch holding the issue.")],
    yes: YesOpt = False,
    repo: RepoOpt = None,
    org: OrgOpt = None,
    dir_override: DirOpt = None,
) -> None:
    """Replace another scope's EXPIRED claim with this scope's, for *batch* (R9)."""
    scope = _scope(repo, org)
    target, facts, judgements = _load_state(scope, dir_override)
    key = normalize_key(key)
    chosen = next((b for b in judgements.batches if b.id == batch.lower()), None)
    if chosen is None or key not in chosen.ids:
        _fail(f"{key} is not a member of a batch {batch!r} of this scope; take names its batch")
    env = triage_batch_cmd.claim_env(scope, target, facts)
    now = _now()
    _, rival = _foreign(env, key)
    if rival is not None and now < rival.expires:
        _fail(
            f"{key}: the claim of {rival.signer} (batch {rival.batch}) is live until "
            f"{rival.expires.isoformat()}; only an expired claim can be taken"
        )
    who = f"{rival.signer} (batch {rival.batch})" if rival is not None else "its expired holder"
    console.print(f"take {key} from {who} for batch {chosen.id}", markup=False, soft_wrap=True)
    if not yes:
        console.print("nothing written; re-run with --yes to take it", markup=False)
        return
    owner_repo, number = _repo_of(env, key)
    out = _write_one(
        lambda: cw.take(
            env.client(owner_repo),
            owner_repo,
            number,
            me=env.me,
            batch=chosen.id,
            expiry=env.expiry,
            now=now,
            trusted=env.trusted(owner_repo),
        ),
        key,
    )
    if isinstance(out, cw.Held):
        _fail(f"{key}: still held by {out.claim.signer} (batch {out.claim.batch})")
    console.print(f"took {key} for batch {chosen.id}", markup=False)


@claim_app.command("release")
def claim_release_command(
    key: KeyArg,
    yes: YesOpt = False,
    repo: RepoOpt = None,
    org: OrgOpt = None,
    dir_override: DirOpt = None,
) -> None:
    """Withdraw this scope's claim on *key* at any time, or another scope's once expired (R9)."""
    scope = _scope(repo, org)
    target, facts, _ = _load_state(scope, dir_override)
    key = normalize_key(key)
    env = triage_batch_cmd.claim_env(scope, target, facts)
    now = _now()
    own, rival = _foreign(env, key)
    if own is not None:
        of = env.me
        console.print(f"release this scope's claim on {key} (batch {own.batch})", markup=False)
    elif rival is not None:
        if now < rival.expires:
            _fail(
                f"{key}: the claim of {rival.signer} (batch {rival.batch}) is live until "
                f"{rival.expires.isoformat()}; another scope's claim is released only once expired"
            )
        of = rival.signer
        console.print(
            f"release the expired claim of {rival.signer} on {key} (batch {rival.batch})",
            markup=False,
        )
    else:
        console.print(f"{key}: facts show no claim to release", markup=False)
        return
    if not yes:
        console.print("nothing written; re-run with --yes to release it", markup=False)
        return
    owner_repo, number = _repo_of(env, key)
    _write_one(
        lambda: cw.release(
            env.client(owner_repo),
            owner_repo,
            number,
            me=env.me,
            now=now,
            trusted=env.trusted(owner_repo),
            of=of,
        ),
        key,
    )
    console.print(f"released {key}", markup=False)
