"""What this scope owes the forge in claims, and doing it (spec 2026-10-06-triage-claims §3.E).

`plan_sync` reads facts and the batches and lists the owed claims, refreshes and releases
(R3, R8, R10, R11); `execute` performs them through `fr.triage.claim_writes`, one member at a
time, and `record_releases` appends the `claims_released` events. The batch commands, the
`fr triage claim` group and (phase 2) the driver share it. The forge client is resolved by a
callable the command layer passes, so nothing here picks a forge.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import cached_property
from typing import Literal

from fr.ghclient import GhClient
from fr.hostclient import FORGE_ERRORS
from fr.triage import claim_writes as cw
from fr.triage.batch import BatchStage, claim_authors, closeout_state, derive_batch_stage
from fr.triage.claims import (
    Claim,
    from_issue_claim,
    holder,
    needs_refresh,
    owed_claims,
    owed_releases,
)
from fr.triage.model import Batch, ClaimsReleasedEvent, Facts, Issue
from fr.triage.scope_config import ScopeConfig

OpKind = Literal["claim", "refresh", "release"]
# A refused claim write or a forge failure: reported per member, never fatal to the rest.
_WRITE_ERRORS: tuple[type[Exception], ...] = (cw.ClaimError, *FORGE_ERRORS)


@dataclass
class ClaimEnv:
    """This scope's identity, its config, the facts, and a forge client per repo."""

    me: str
    config: ScopeConfig
    facts: Facts
    client_for: Callable[[str], GhClient]  # OWNER/REPO -> client
    _clients: dict[str, GhClient] = field(default_factory=dict)

    @property
    def expiry(self) -> timedelta:
        return timedelta(hours=self.config.claim_expiry_hours)

    def client(self, owner_repo: str) -> GhClient:
        if owner_repo not in self._clients:
            self._clients[owner_repo] = self.client_for(owner_repo)
        return self._clients[owner_repo]

    def trusted(self, owner_repo: str) -> frozenset[str]:
        return claim_authors(owner_repo, self.facts)

    @cached_property
    def _repo_index(self) -> dict[str, str]:
        """Repo name (lower-cased) -> OWNER/REPO, the first of a name winning."""
        index: dict[str, str] = {}
        for r in self.facts.repos:
            index.setdefault(r.split("/", 1)[1].lower(), r)
        return index

    @cached_property
    def _issue_index(self) -> dict[str, Issue]:
        """Judgement key -> issue, the first of a key winning."""
        index: dict[str, Issue] = {}
        for i in self.facts.issues:
            index.setdefault(i.key, i)
        return index

    def owner_repo(self, key: str) -> str | None:
        """The OWNER/REPO of judgement key *key* in this scope, from the facts."""
        return self._repo_index.get(key.rpartition("#")[0])

    def issue(self, key: str) -> Issue | None:
        return self._issue_index.get(key)


@dataclass(frozen=True)
class ClaimOp:
    kind: OpKind
    key: str
    batch: str


@dataclass(frozen=True)
class HeldMember:
    key: str
    batch: str
    holder: Claim


@dataclass
class SyncPlan:
    ops: list[ClaimOp] = field(default_factory=list)
    held: list[HeldMember] = field(default_factory=list)


def stages_of(batches: Sequence[Batch], facts: Facts) -> tuple[dict[str, BatchStage], set[str]]:
    """Each batch's stage, and the ids of the batches whose close-out is archived."""
    stages = {b.id: derive_batch_stage(b, facts) for b in batches}
    archived = {b.id for b in batches if closeout_state(b) == "archived"}
    return stages, archived


def plan_sync(env: ClaimEnv, batches: Sequence[Batch], now: datetime) -> SyncPlan:
    """Every owed claim, due refresh and owed release, from facts and the batches.

    A member another scope holds (R4, R6) is listed under `held`, never claimed. A member
    facts know nothing about (closed: collect reads no closed issue's comments) gets a
    refresh, which re-reads and writes only when this scope's marker is due.
    """
    stages, archived = stages_of(batches, env.facts)
    plan = SyncPlan()
    for key, bid in owed_claims(batches, stages, archived):
        issue = env.issue(key)
        if issue is None or issue.state != "open":
            plan.ops.append(ClaimOp("refresh", key, bid))
            continue
        claims = [from_issue_claim(c) for c in issue.claims]
        if (h := holder(claims, env.me)) is not None:
            plan.held.append(HeldMember(key, bid, h))
            continue
        own = next((c for c in claims if c.signer == env.me), None)
        if own is None or own.batch != bid:
            plan.ops.append(ClaimOp("claim", key, bid))
        elif needs_refresh(own, now, env.expiry):
            plan.ops.append(ClaimOp("refresh", key, bid))
    own_claims = [
        (i.key, c.batch)
        for i in env.facts.issues
        if i.state == "open"
        for c in i.claims
        if c.signer == env.me
    ]
    for key, bid in owed_releases(batches, stages, archived, own=own_claims):
        plan.ops.append(ClaimOp("release", key, bid))
    return plan


@dataclass
class SyncResult:
    done: list[tuple[ClaimOp, cw.Done]] = field(default_factory=list)
    held: list[HeldMember] = field(default_factory=list)
    failed: list[tuple[ClaimOp, str]] = field(default_factory=list)

    def released(self, batch: str) -> list[str]:
        return [op.key for op, _ in self.done if op.kind == "release" and op.batch == batch]


def execute(env: ClaimEnv, ops: Sequence[ClaimOp], now: datetime) -> SyncResult:
    """Perform *ops* one member at a time. A forge failure or a refused write is reported
    for that member and the rest go on; an unsupported forge propagates (exit 2)."""
    result = SyncResult()
    for op in ops:
        owner_repo = env.owner_repo(op.key)
        if owner_repo is None:
            result.failed.append((op, f"its repo is not in this scope's facts ({op.key})"))
            continue
        number = int(op.key.rpartition("#")[2])
        client, trusted = env.client(owner_repo), env.trusted(owner_repo)
        try:
            if op.kind == "claim":
                out = cw.claim(
                    client,
                    owner_repo,
                    number,
                    me=env.me,
                    batch=op.batch,
                    expiry=env.expiry,
                    now=now,
                    trusted=trusted,
                )
            elif op.kind == "refresh":
                out = cw.refresh(
                    client,
                    owner_repo,
                    number,
                    me=env.me,
                    expiry=env.expiry,
                    now=now,
                    trusted=trusted,
                    due_only=True,
                )
            else:
                out = cw.release(
                    client,
                    owner_repo,
                    number,
                    me=env.me,
                    now=now,
                    trusted=trusted,
                    batch=op.batch,
                )
        except _WRITE_ERRORS as exc:
            result.failed.append((op, str(exc)))
            continue
        if isinstance(out, cw.Held):
            result.held.append(HeldMember(op.key, op.batch, out.claim))
        else:
            result.done.append((op, out))
    return result


def record_releases(batches: Sequence[Batch], result: SyncResult, now: datetime) -> list[Batch]:
    """*batches* with one `claims_released` event appended to each batch whose members
    `result` released, so a later pass owes them nothing (R10). Releases of keys that are
    no longer members (a removed issue, a stray own claim) record nothing."""
    out: list[Batch] = []
    for b in batches:
        keys = [k for k in result.released(b.id) if k in b.ids]
        if keys:
            at = max(now, b.events[-1].at) if b.events else now
            event = ClaimsReleasedEvent(kind="claims_released", at=at, keys=keys)
            b = b.model_copy(update={"events": [*b.events, event]})
        out.append(b)
    return out
