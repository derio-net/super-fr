"""Probes and the pass kind (spec 2026-10-12-quota-pacing §B, R8-R11, R15).

A probe is a conditional REST read sent with a stored ETag; a 304 costs no budget. Per
pass: probe every scope repo BEFORE any collect, keeping each answer's ETag *pending*;
decide the pass kind (`plan_pass`); collect the chosen repos; write `facts.json`; only
then `promote` the pending ETags of the repos read successfully, dropping a failed
repo's. A change landing between the probe and the collect therefore answers 200 next
time, never a stale 304.

Pure but for `run_probes`, which sends the probes through the `Forge` seam.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal, Protocol

from fr.triage.batch import batch_pr, batch_repo, derive_batch_stage
from fr.triage.batch_dispatch import LIVE_STAGES
from fr.triage.batch_drive import ARCHIVE_PREFIXES, closeout_event
from fr.triage.errors import ForgeError
from fr.triage.model import Facts, Judgements
from fr.triage.pacing_state import PacingState

# R11: a full pass at least this often, whatever the probes say.
FULL_EVERY = timedelta(minutes=15)
# R7: why an essential-only pass dispatches nothing.
QUOTA_HOLD = "quota below floor"

PassKind = Literal["full", "quiet", "partial", "essential"]
Pending = dict[str, dict[str, str]]  # repo -> probe path -> ETag


class Prober(Protocol):
    def probe(self, path: str, etag: str | None) -> tuple[bool, str | None]: ...


def issues_probe(repo: str) -> str:
    """The repo's one probe: its most recently updated issue or PR (R8)."""
    return f"repos/{repo}/issues?state=all&sort=updated&direction=desc&per_page=1"


def checks_probes(repo: str, head: str) -> tuple[str, str]:
    """A live PR's CI, which moves without touching the issue list (R8)."""
    return (
        f"repos/{repo}/commits/{head}/check-runs?per_page=100",
        f"repos/{repo}/commits/{head}/status",
    )


def _live_heads(facts: Facts, judgements: Judgements) -> dict[str, list[str]]:
    """repo -> the heads of its live batches' open PRs and of its open close-out or
    archive PRs (R7, R8)."""
    heads: dict[str, list[str]] = {}
    for batch in judgements.batches:
        repo = batch_repo(batch, facts)
        if repo is None or derive_batch_stage(batch, facts) not in LIVE_STAGES:
            continue
        heads.setdefault(repo, [])
        pr = batch_pr(batch, facts)
        if pr is not None and pr.state == "OPEN" and pr.head_oid:
            heads[repo].append(pr.head_oid)
    for pr in facts.prs:
        if pr.state == "OPEN" and pr.head_ref.startswith(ARCHIVE_PREFIXES):
            heads.setdefault(pr.repo, [])
            if pr.head_oid:
                heads[pr.repo].append(pr.head_oid)
    return heads


def closing_repos(facts: Facts | None, judgements: Judgements | None) -> set[str]:
    """The repos of batches whose close-out has started and is not archived (merge-truth
    R8): read every pass, so an archive PR opened since the last full collect is seen."""
    if facts is None or judgements is None:
        return set()
    out: set[str] = set()
    for batch in judgements.batches:
        event = closeout_event(batch)
        repo = batch_repo(batch, facts)
        if event is not None and event.archived is None and repo is not None:
            out.add(repo)
    return out


def live_repos(facts: Facts | None, judgements: Judgements | None) -> set[str]:
    """The repos an essential-only pass reads (R7): those of batches in `LIVE_STAGES`,
    those with an open close-out or archive PR, and the closing ones (merge-truth R8)."""
    if facts is None or judgements is None:
        return set()
    return set(_live_heads(facts, judgements)) | closing_repos(facts, judgements)


def probe_set(
    repos: Iterable[str], facts: Facts | None, judgements: Judgements | None
) -> dict[str, tuple[str, ...]]:
    """repo -> its probe paths, in the order they are sent (R8)."""
    heads = _live_heads(facts, judgements) if facts and judgements else {}
    out: dict[str, tuple[str, ...]] = {}
    for repo in repos:
        paths = [issues_probe(repo)]
        for head in dict.fromkeys(heads.get(repo, ())):
            paths.extend(checks_probes(repo, head))
        out[repo] = tuple(paths)
    return out


def run_probes(
    forge: Prober, probes: Mapping[str, Iterable[str]], state: PacingState, *, full: bool
) -> tuple[set[str], Pending]:
    """Send every probe, conditionally unless *full* (R11). The changed repos (any probe
    not a 304, a failure or a missing ETag included) and the PENDING ETags, which only
    `promote` may store."""
    changed: set[str] = set()
    pending: Pending = {}
    for repo, paths in probes.items():
        stored = {} if full else state.etags.get(repo, {})
        for path in paths:
            try:
                moved, etag = forge.probe(path, stored.get(path))
            except ForgeError:
                moved, etag = True, None
            if moved:
                changed.add(repo)
            if etag:
                pending.setdefault(repo, {})[path] = etag
    return changed, pending


def promote(
    state: PacingState, pending: Mapping[str, Mapping[str, str]], *, read_ok: Iterable[str],
    failed: Iterable[str],
) -> PacingState:  # fmt: skip
    """The state once `facts.json` is written (R11): the pending ETags of exactly the
    repos read successfully; a failed repo's dropped; a carried repo's left as they were,
    so a change it was not read for still shows next pass."""
    etags = {repo: dict(paths) for repo, paths in state.etags.items()}
    for repo in read_ok:
        etags[repo] = dict(pending.get(repo, {}))
    for repo in failed:
        etags.pop(repo, None)
    return replace(state, etags=etags)


def judgements_digest(path: Path) -> str:
    """The digest R9 compares: of the bytes, so any edit is a change."""
    try:
        data = path.read_bytes()
    except OSError:
        data = b""
    return hashlib.sha256(data).hexdigest()


def full_due(state: PacingState, now: datetime) -> bool:
    """R11: no `pacing.json` yet, or its last full pass 15 minutes old."""
    return state.full_at is None or now - state.full_at >= FULL_EVERY


def pass_kind(
    state: PacingState, now: datetime, changed: set[str], digest: str, *, below_floor: bool
) -> PassKind:
    """R9: quiet when nothing changed and the judgements are the last planned pass's (and
    that pass's summary is on record, to stand for this one); below the floor every other
    pass is essential-only (R7); else full when due (R11), partial otherwise (R10). Above
    the floor after a pass that held its dispatches for the quota, never quiet: those
    dispatches are owed a planned pass (p2-r3)."""
    due = full_due(state, now)
    owed = state.held_for_quota and not below_floor
    if (
        not due
        and not changed
        and not owed
        and state.summary is not None
        and digest == state.judgements_digest
    ):
        return "quiet"
    if below_floor:
        return "essential"
    return "full" if due else "partial"


@dataclass(frozen=True)
class PassPlan:
    """What one paced pass reads, carries and holds: built here, read by the drive."""

    kind: PassKind
    only: frozenset[str] | None  # the repos to collect; None: every repo
    carried: frozenset[str]  # repos taken from the last facts.json, never read this pass
    dispatch_held: str | None = None
    full: bool = False  # the probes went unconditionally
    digest: str = ""
    pending: Pending = field(default_factory=dict)
    probes: int = 0

    @property
    def collects(self) -> bool:
        return self.kind != "quiet"


def plan_pass(
    state: PacingState,
    now: datetime,
    *,
    repos: Iterable[str],
    changed: set[str],
    digest: str,
    below_floor: bool,
    live: set[str],
    pending: Pending,
    probes: int,
    full: bool | None = None,
    closing: set[str] | frozenset[str] = frozenset(),
) -> PassPlan:
    """The pass's kind and the repos it reads (R7, R9-R11). The *closing* repos
    (`closing_repos`) are read on every pass, whatever its kind: a would-be quiet pass
    with any becomes a partial one that reads only them (merge-truth R8)."""
    every = frozenset(repos)
    if state.summary is None:
        # The last pass never planned (it failed after its collect, p2-r1): its ETags may be
        # promoted, but the actions it owed were never planned, so nothing is carried.
        changed = set(every)
    due = full_due(state, now) if full is None else full
    kind = pass_kind(state, now, changed, digest, below_floor=below_floor)
    reading = frozenset(closing) & every
    if kind == "quiet" and reading:
        kind = "partial"
    held: str | None = None
    if kind == "quiet":
        only: frozenset[str] | None = frozenset()
    elif kind == "essential":
        only = (frozenset(live if due else changed & live) | reading) & every
        held = QUOTA_HOLD
    elif kind == "full":
        only = None
    else:
        only = (frozenset(changed) | reading) & every
    if only is not None and kind != "quiet" and only >= every:
        only = None
    carried = every - only if only is not None else frozenset()
    return PassPlan(kind, only, carried, held, due, digest, pending, probes)
