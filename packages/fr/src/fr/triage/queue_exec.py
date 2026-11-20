"""The wave merge queue's executor (spec 2026-11-19-wave-merge-queue §C, §D).

`fr.triage.wave_queue` decides; this module does. It builds each combination in a
scratch worktree and pushes it to an fr-owned slot branch (R4–R6), lands the longest
green prefix by ONE atomic leased push (R10) or through the forge's merge API (R11),
reads every landed PR back (R35), tells a repo it cannot drive apart from one it can
(R7, R22, R34, R35), reads each combination's checks (R7, R20) and decides when the
repo's `post_merge` runs and when it pauses landings (R33). A restarted driver resumes
from the queue's events and the remote (`resume`, R24).

Every git operation goes through the `fr.triage.gitseam` classes and every forge one
through the `GhClient` adapter, both passed in, so this module starts no process itself
(`tests/unit/test_forge_adapter_batch_ops.py` pins that).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal, Protocol

from fr.ghclient import UnsupportedBatchOps
from fr.hostclient import FORGE_ERRORS
from fr.triage.batch_merge import MergeConflictError, MergeStopError, unresolvable
from fr.triage.batch_version import bump_version, is_lockfile, read_source
from fr.triage.gitseam import (
    AtomicUnsupportedError,
    Checkout,
    GitError,
    LeaseLostError,
    PushRefusedError,
    Worktree,
)
from fr.triage.model import (
    Batch,
    Bump,
    PostMergeEvent,
    QueueBuiltEvent,
    QueueEntryRef,
    QueueLandEvent,
    QueueRecord,
    VersionBlock,
)
from fr.triage.wave_queue import QueueConfig, SlotCheck, entry_key, replay

Method = Literal["merge", "squash", "rebase"]

SLOT_PREFIX = "refs/heads/fr-queue"
FORGE_PARITY = "gh#611"
PROTECTION_CODES = ("GH006", "GH013")
"""GitHub's words for a push its protection refused: classic protection (`GH006`) and a
ruleset (`GH013`). R34's held reason names its two remedies for either."""


def slot_ref(scope: str, slot: int) -> str:
    """Slot *slot*'s branch, `refs/heads/fr-queue/<scope-id>/slot-<k>` (R4)."""
    return f"{SLOT_PREFIX}/{scope}/slot-{slot}"


@dataclass(frozen=True)
class EntryInput:
    """One entry as the executor builds it: its key and ref, its PR, the head the
    combination is built from, and the batch's bump (None: no version slot, R6)."""

    key: str
    ref: QueueEntryRef
    pr: int
    title: str
    head: str
    head_ref: str
    bump: Bump | None = None


@dataclass(frozen=True)
class Built:
    """Slot *slot* now holds combination *sha* (tree *tree*): *entry* on *parent*, the
    queue started from *base*."""

    slot: int
    sha: str
    tree: str
    entry: EntryInput
    parent: str
    base: str
    patch_id: str


# ------------------------------------------------------------------ building (§C)


def _subject(entry: EntryInput, method: Method) -> str:
    """R5: the subject the forge itself would write."""
    if method == "merge":
        return f"Merge pull request #{entry.pr} from {entry.head_ref}"
    return f"{entry.title} (#{entry.pr})"


def _slot_version(wt: Worktree, version: VersionBlock | None, entry: EntryInput) -> str | None:
    """The version the entry's commit carries: the commit it is built on, bumped by the
    batch's level (R6, `fr.triage.batch_version.slot_versions` one step at a time)."""
    if version is None or entry.bump is None:
        return None
    text = wt.show("HEAD", version.source.file)
    if text is None:
        raise MergeStopError(f"{version.source.file} does not exist at the combination")
    return bump_version(read_source(text, version.source), entry.bump)


def _apply_slot(
    wt: Worktree, version: VersionBlock | None, slot: str | None, relock: bool
) -> None:
    if version is None:
        return
    if slot is not None:
        text = wt.read(version.source.file)
        if text is None or read_source(text, version.source) != slot:
            wt.run(version.set_, version=slot)
            relock = True
    if relock and version.relock:
        wt.run(version.relock)


def _conflict(entry: EntryInput, paths: Sequence[str], where: Path) -> MergeConflictError:
    return MergeConflictError(
        f"PR #{entry.pr} ({entry.key}) conflicts with the combination ahead of it in a "
        f"change the queue will not resolve: {', '.join(paths)} (only a version file whose "
        "PR change is the version alone is resolved)",
        batch=entry.key, head=entry.head, paths=paths,
    )  # fmt: skip


def _resolve(
    wt: Worktree,
    version: VersionBlock | None,
    entry: EntryInput,
    conflicted: list[str],
    base: str,
    abort: Callable[[], None],
) -> bool:
    """R6: take the combination's side of the version files the PR changed the version
    alone in (and of a lockfile with a relock); anything else is a `MergeConflictError`.
    Whether a lockfile was taken (so a relock is owed)."""
    refused = unresolvable(version, wt.show, base, entry.head, conflicted)
    if refused:
        abort()
        raise _conflict(entry, refused, wt.path)
    wt.take_ours(conflicted)
    return any(is_lockfile(p) for p in conflicted)


def _combine(
    checkout: Checkout,
    wt: Worktree,
    prev: str,
    entry: EntryInput,
    method: Method,
    version: VersionBlock | None,
) -> tuple[str, str]:
    """The tree of *entry* on *prev*, staged in *wt*, and the parents its commit takes;
    for `rebase` the replayed tip itself is returned as the only "parent" (its tree and
    commit are made already)."""
    files = version.files if version else []
    base = checkout.merge_base(prev, entry.head)
    slot = _slot_version(wt, version, entry)
    if method == "rebase":
        for sha in checkout.replayed(base, entry.head):
            conflicted = wt.cherry_pick(sha)
            if conflicted:
                relock = _resolve(wt, version, entry, conflicted, base, wt.abort_pick)
                wt.continue_pick()
                if relock and version and version.relock:
                    wt.run(version.relock)
        _apply_slot(wt, version, slot, False)
        tip = wt.amend(files) if version and slot else wt.head()
        return "", tip
    conflicted = wt.merge(entry.head)
    relock = _resolve(wt, version, entry, conflicted, base, wt.abort_merge) if conflicted else False
    _apply_slot(wt, version, slot, relock)
    wt.stage(files)
    return wt.write_tree(), ""


def _fresh_commit(
    wt: Worktree, tree: str, parents: Sequence[str], message: str, avoid: set[str]
) -> str:
    """A commit of *tree* on *parents* whose sha is none of *avoid* (R13: a rebuild of the
    same tree is a new commit, so CI runs on it again), by a later committer time."""
    sha = wt.commit_tree(tree, parents, message)
    when = wt.commit_date(sha)
    while sha in avoid:
        when += 1
        sha = wt.commit_tree(tree, parents, message, date=f"@{when} +0000")
    return sha


def build(
    checkout: Checkout,
    base: str,
    entries: Sequence[EntryInput],
    method: Method,
    version: VersionBlock | None,
    *,
    scope: str,
    slots: Sequence[int],
    scratch: Path,
    queue_base: str | None = None,
    record: Callable[[QueueBuiltEvent], None] | None = None,
    leases: Mapping[int, str | None] | None = None,
    now: Callable[[], datetime] | None = None,
) -> list[Built]:
    """Build *entries* in order on *base* (the queue's base, or the combination ahead),
    entry i into slot *slots*[i], in *method* (R4, R5, R6): each commit on the one before
    it, so slot k holds base + 1..k. Each is recorded (*record*, a `queue_built`) and
    then pushed to its slot, leased on the sha the slot held (*leases*, else read from
    origin now). A slot lease that fails raises `LeaseLostError`; a real conflict raises
    `MergeConflictError` after the entries ahead of it were built and pushed.

    *queue_base* is the queue's `main` (default: *base*). No PR branch is touched."""
    if len(slots) < len(entries):
        raise MergeStopError(f"{len(entries)} entries to build into {len(slots)} slot(s)")
    queue_base = queue_base or base
    clock = now or _utcnow
    held = dict(leases) if leases is not None else {
        s: checkout.remote_sha(slot_ref(scope, s)) for s in slots[: len(entries)]
    }  # fmt: skip
    where = scratch / f"build-{scope}"
    wt = checkout.add_worktree(where, base)
    out: list[Built] = []
    prev = base
    try:
        for entry, slot in zip(entries, slots, strict=False):
            wt.reset_hard(prev)
            tree, tip = _combine(checkout, wt, prev, entry, method, version)
            avoid = {s for s in held.values() if s}
            if tip:  # rebase: replayed already
                sha = tip if tip not in avoid else _fresh_commit(
                    wt, checkout.tree_of(tip), checkout.parents(tip), checkout.message(tip),
                    avoid)  # fmt: skip
            else:
                parents = (prev, entry.head) if method == "merge" else (prev,)
                sha = _fresh_commit(wt, tree, parents, _subject(entry, method), avoid)
            wt.reset_hard(sha)
            built = Built(
                slot=slot, sha=sha, tree=checkout.tree_of(sha), entry=entry, parent=prev,
                base=queue_base, patch_id=_patch_id(checkout, entry.head, queue_base),
            )  # fmt: skip
            if record is not None:  # recorded BEFORE the push: `resume` re-pushes it
                record(built_event(built, clock()))
            ref = slot_ref(scope, slot)
            checkout.push_leased([(sha, ref)], {ref: held.get(slot)}, atomic=False)
            out.append(built)
            prev = sha
    finally:
        checkout.remove_worktree(where)
    return out


def _patch_id(checkout: Checkout, head: str, base: str) -> str:
    try:
        return checkout.patch_id(head, base)
    except GitError:
        return ""


def _utcnow() -> datetime:
    from datetime import UTC

    return datetime.now(UTC)


def built_event(built: Built, at: datetime) -> QueueBuiltEvent:
    """The `queue_built` event of *built* (R24), with the commit it was built on."""
    return QueueBuiltEvent(
        kind="queue_built", at=at, slot=built.slot, sha=built.sha, entry=built.entry.ref,
        head=built.entry.head, patch_id=built.patch_id, base=built.base, parent=built.parent,
    )  # fmt: skip


# ------------------------------------------------------------------ landing (§D)


@dataclass(frozen=True)
class Landing:
    """One entry of a landing: its PR's head ref, the head its combination was built from
    and the entry's own commit in the combination (R10)."""

    key: str
    ref: QueueEntryRef
    pr: int
    head_ref: str
    head: str
    commit: str


@dataclass(frozen=True)
class LandResult:
    """What a landing did: `landed` (main is *main*), `lease` (a lease failed, nothing
    moved: rebuilt next pass), `held` (the repo cannot land this way, R22, R34) or
    `stopped` (a forge merge refused or left an untested tree, R11)."""

    outcome: Literal["landed", "lease", "held", "stopped"]
    main: str = ""
    detail: str = ""


def landings_of(built: Sequence[Built]) -> list[Landing]:
    """The landing of the combinations *built*, front first."""
    return [Landing(b.entry.key, b.entry.ref, b.entry.pr, b.entry.head_ref, b.entry.head, b.sha)
            for b in built]  # fmt: skip


class PrOf(Protocol):
    def __call__(self, key: str) -> tuple[int, str] | None: ...


def landings_from(record: QueueRecord, tip: str, pr_of: PrOf) -> list[Landing]:
    """The landing of combination *tip* as *record*'s events rebuild it (R24): each
    combination from the queue's base to *tip*, by their parents, with each entry's PR
    number and head ref from *pr_of* (None: unknown, so nothing lands)."""
    rep = replay(record)
    by_sha = {c.sha: c for c in rep.combos.values()}
    chain = []
    at = by_sha.get(tip)
    while at is not None:
        chain.append(at)
        at = by_sha.get(at.parent)
    chain.reverse()
    out: list[Landing] = []
    refs = _refs(record)
    for combo in chain:
        key = combo.chain[-1]
        known = pr_of(key)
        if known is None:
            return []
        out.append(Landing(key, refs[key], known[0], known[1], combo.heads[-1], combo.sha))
    return out


def _refs(record: QueueRecord) -> dict[str, QueueEntryRef]:
    out: dict[str, QueueEntryRef] = {}
    for event in record.events:
        ref = getattr(event, "entry", None)
        if isinstance(ref, QueueEntryRef):
            out[entry_key(ref)] = ref
    return out


def land_event(landings: Sequence[Landing], main: str, at: datetime) -> QueueLandEvent:
    return QueueLandEvent(kind="queue_land", at=at, main=main,
                          entries=[x.ref for x in landings])  # fmt: skip


def protection_reason(words: str) -> str:
    """R34's held reason for a push the default branch's protection refused."""
    return (
        f"the default branch refused the queue's push ({words.strip()}). Under `queue.land: "
        "push` it must accept the driver's direct push: a ruleset with no \"require a pull "
        "request\" rule (a tested combination's required checks already passed), or a bypass "
        "identity dedicated to the driver; fr never makes your own credential a bypass actor. "
        "Or set `queue.land: merge` in .fr/triage.yaml to land through the forge's merge API"
    )


def refusal_reason(exc: PushRefusedError | AtomicUnsupportedError) -> str:
    """Why a landing push the remote refused holds the queue (R22, R34)."""
    words = str(exc)
    if isinstance(exc, AtomicUnsupportedError):
        return (
            "the remote refuses `git push --atomic`, and the queue never lands by a partial "
            "push (R22): a PR branch would hold another PR's change. Land through the forge "
            "with `queue.land: merge` in .fr/triage.yaml"
        )
    if any(code in words for code in PROTECTION_CODES):
        return protection_reason(words)
    return f"the remote refused the queue's landing push: {words}"


def land_push(
    checkout: Checkout,
    *,
    default: str,
    base: str,
    landings: Sequence[Landing],
    method: Method,
    record: Callable[[QueueLandEvent], None] | None = None,
    now: Callable[[], datetime] | None = None,
) -> LandResult:
    """R10: ONE `git push --atomic` that moves *default* by fast-forward to the last
    entry's commit, leased on *base*, and every landed PR's head ref, leased on the head
    its combination was built from: under `squash` and `rebase` to the PR's own commit in
    the combination, under `merge` unchanged (so a session push since the build still
    fails the lease). Nothing moves unless everything does. *record* gets the
    `queue_land` after a successful landing."""
    if not landings:
        return LandResult("stopped", detail="nothing to land")
    tip = landings[-1].commit
    main_ref = f"refs/heads/{default}"
    refspecs = [(tip, main_ref)]
    leases: dict[str, str | None] = {main_ref: base}
    for x in landings:
        ref = f"refs/heads/{x.head_ref}"
        refspecs.append((x.head if method == "merge" else x.commit, ref))
        leases[ref] = x.head
    try:
        checkout.push_leased(refspecs, leases, atomic=True)
    except LeaseLostError as exc:
        return LandResult("lease", detail=f"a lease failed, nothing landed: {exc}")
    except (AtomicUnsupportedError, PushRefusedError) as exc:
        return LandResult("held", detail=refusal_reason(exc))
    if record is not None:
        record(land_event(landings, tip, (now or _utcnow)()))
    return LandResult("landed", main=tip)


class MergingForge(Protocol):
    def pr_merge(self, repo: str, number: int, *, head_sha: str, method: str) -> None: ...


def land_merge(
    client: MergingForge,
    checkout: Checkout,
    repo: str,
    *,
    default: str,
    tip: str,
    landings: Sequence[Landing],
    method: Method,
    record: Callable[[QueueLandEvent], None] | None = None,
    now: Callable[[], datetime] | None = None,
) -> LandResult:
    """R11: merge each landed PR through the forge's merge API at its pinned head, in
    queue order, with *method*; then `main`'s tree must equal the tested combination's
    (*tip*). A refusal stops at that PR; a mismatch stops the queue. Neither is ever
    retried in a way that lands an untested tree. What did merge is recorded (*record*)
    as landed, at the `main` the forge left."""
    done: list[Landing] = []
    stop = ""
    for x in landings:
        try:
            client.pr_merge(repo, x.pr, head_sha=x.head, method=method)
        except FORGE_ERRORS as exc:
            stop = f"the forge refused to merge PR #{x.pr} ({x.key}): {exc}"
            break
        done.append(x)
    main = ""
    if done:
        checkout.refresh_remote_branch(default)
        main = checkout.rev_parse(f"origin/{default}")
        if record is not None:
            record(land_event(done, main, (now or _utcnow)()))
    if stop:
        return LandResult("stopped", main=main, detail=f"{stop}; the queue stops here")
    if checkout.tree_of(main) != checkout.tree_of(tip):
        return LandResult(
            "stopped", main=main,
            detail=f"{default}'s tree after the forge merges ({main[:12]}) is not the tested "
            f"combination's ({tip[:12]}); the queue stops and lands nothing more",
        )  # fmt: skip
    return LandResult("landed", main=main)


class ViewingForge(Protocol):
    def pr_view(self, repo: str, number: int) -> dict[str, Any]: ...


def read_back(client: ViewingForge, repo: str, prs: Iterable[int]) -> tuple[int, ...]:
    """R35: the landed PRs the forge does not read `MERGED` yet (an unreadable one
    included: unknown is not merged)."""
    out: list[int] = []
    for number in prs:
        try:
            state = client.pr_view(repo, number).get("state")
        except FORGE_ERRORS:
            state = None
        if state != "MERGED":
            out.append(number)
    return tuple(out)


def forge_refusal(client: object) -> str | None:
    """R35: the forges whose client implements what the queue needs are the GitHub ones;
    a glab or tea client is held, naming gh#611."""
    if isinstance(client, UnsupportedBatchOps):
        return (
            f"the merge queue needs commit checks, PR views, merges, label and comment edits, "
            f"which the {client.backend} client does not implement ({FORGE_PARITY}); this "
            "repo's merges are held"
        )
    return None
