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
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal, Protocol

import yaml

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
    QueueBlock,
    QueueBuiltEvent,
    QueueDrainEvent,
    QueueEjectEvent,
    QueueEntryRef,
    QueueEvent,
    QueueLandEvent,
    QueueOpenEvent,
    QueueRecord,
    VersionBlock,
)
from fr.triage.wave_queue import (
    BuildConflict,
    QueueAction,
    QueueConfig,
    QueuePlan,
    SlotCheck,
    entry_key,
    replay,
)

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


def _apply_slot(wt: Worktree, version: VersionBlock | None, slot: str | None, relock: bool) -> None:
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


# ------------------------------------------------------------------ config and refusals (R7)


def queue_config(block: QueueBlock) -> QueueConfig:
    """`.fr/triage.yaml`'s `queue:` block as the planner reads it."""
    return QueueConfig(
        ci=block.ci, depth=block.depth, land=block.land,
        check_wait_minutes=block.check_wait_minutes, release=block.release,
        release_workflow=block.release_workflow, release_wait_hours=block.release_wait_hours,
        stall_hours=block.stall_hours,
    )  # fmt: skip


def queue_refusal(block: QueueBlock, *, ci_none: bool) -> str | None:
    """R7, R20: why the driver refuses to run *block*'s queue, None when it may. *ci_none*:
    the repo's services say `ci none` on its default branch."""
    if block.ci is None:
        return (
            "the merge queue needs `queue.ci` in .fr/triage.yaml: add `ci: push` under "
            "`queue:` once every workflow that reports a required check runs on pushes to "
            "fr-queue/**, or `ci: none` in a repo whose services report `ci none`"
        )
    if block.ci == "none" and not ci_none:
        return (
            "`queue.ci: none` in .fr/triage.yaml, but this repo's services do not report "
            "`ci none`: its required checks must run on the combinations. Set `ci: push` and "
            "run them on pushes to fr-queue/**"
        )
    return None


def held_plan(plan: QueuePlan, reason: str) -> QueuePlan:
    """*plan* replaced by one `queue-held` that says *reason* (R7, R22, R34, R35)."""
    action = QueueAction("queue-held", plan.repo, f"{plan.repo}'s merge queue is held: {reason}")
    return QueuePlan(plan.repo, plan.phase, plan.wave, (action,), plan.entries, plan.waiting)


def pause_landings(plan: QueuePlan, reason: str | None) -> QueuePlan:
    """*plan* with no landing, and a Need saying *reason* (R33, R35): the queue still builds
    and tests, but lands nothing until *reason* clears. *plan* itself when *reason* is None."""
    if reason is None:
        return plan
    kept = tuple(a for a in plan.actions if a.kind != "queue-land")
    need = QueueAction("queue-need", plan.repo,
                       f"{plan.repo}'s queue lands nothing until this clears: {reason}",
                       wave=plan.wave)  # fmt: skip
    return replace(plan, actions=(*kept, need))


# ------------------------------------------------------------------ checks (R7)

_FAILED = frozenset({"failure", "cancelled", "timed_out", "action_required", "startup_failure",
                     "stale", "error"})  # fmt: skip


def gate_checks_of(text: str | None) -> list[str] | None:
    """The gate-check names `.fr/ci.yaml`'s *text* declares, None when it declares none
    (or is not that file's shape): the base's required checks then decide."""
    if text is None:
        return None
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        return None
    names = data.get("gate_checks") if isinstance(data, dict) else None
    if not isinstance(names, list) or not names:
        return None
    out = [n.strip() for n in names if isinstance(n, str) and n.strip()]
    return out or None


def _state(check: Mapping[str, Any]) -> Literal["pass", "fail", "pending"]:
    if check.get("status") != "completed":
        return "pending"
    return "fail" if str(check.get("conclusion") or "").lower() in _FAILED else "pass"


def slot_check(
    checks: Sequence[Mapping[str, Any]],
    required: Sequence[str],
    *,
    built_at: datetime,
    now: datetime,
    wait_minutes: int,
) -> tuple[SlotCheck, tuple[str, ...]]:
    """R7: a combination's verdict from `commit_checks` on its own sha, under the same
    required-checks rule as a PR (`checks_verdict`): the *required* names when the repo has
    any, else every check; nothing reported is pending, never green. With it, the
    required checks that have not reported `wait_minutes` after the build: each a Need."""
    if required:
        by_name: dict[str, list[Mapping[str, Any]]] = {}
        for c in checks:
            by_name.setdefault(str(c.get("name")), []).append(c)
        failing = tuple(
            sorted(n for n in required if any(_state(c) == "fail" for c in by_name.get(n, [])))
        )
        missing = tuple(sorted(n for n in required if n not in by_name))
        pending = [n for n in required
                   if n in by_name and any(_state(c) == "pending" for c in by_name[n])]  # fmt: skip
        late = missing if now - built_at >= timedelta(minutes=wait_minutes) else ()
        if failing:
            return SlotCheck("failing", failing), late
        if missing or pending:
            return SlotCheck("pending"), late
        return SlotCheck("green"), ()
    states = [_state(c) for c in checks]
    if "fail" in states:
        names = tuple(sorted(str(c.get("name")) for c in checks if _state(c) == "fail"))
        return SlotCheck("failing", names), ()
    if not states or "pending" in states:
        return SlotCheck("pending"), ()
    return SlotCheck("green"), ()


class ChecksForge(Protocol):
    def commit_checks(self, repo: str, sha: str) -> list[dict[str, Any]]: ...
    def required_check_names(self, repo: str, base: str) -> list[str]: ...


def required_names(client: ChecksForge, checkout: Checkout, repo: str, default: str) -> list[str]:
    """The checks that gate *default* (R7): `.fr/ci.yaml`'s `gate_checks` at
    `origin/<default>`, else the base's `required_check_names`."""
    declared = gate_checks_of(checkout.show(f"origin/{default}", ".fr/ci.yaml"))
    return declared if declared is not None else list(client.required_check_names(repo, default))


def read_slots(
    client: ChecksForge,
    repo: str,
    record: QueueRecord,
    required: Sequence[str],
    *,
    now: datetime,
    wait_minutes: int,
) -> tuple[dict[str, SlotCheck], list[str]]:
    """Each standing combination of *record* (sha -> its verdict), and a Need per required
    check that never reported on one of them in time, naming it (R7)."""
    built_at = {e.sha: e.at for e in record.events if isinstance(e, QueueBuiltEvent)}
    out: dict[str, SlotCheck] = {}
    needs: list[str] = []
    for combo in replay(record).combos.values():
        verdict, late = slot_check(
            client.commit_checks(repo, combo.sha), required,
            built_at=built_at.get(combo.sha, now), now=now, wait_minutes=wait_minutes,
        )  # fmt: skip
        out[combo.sha] = verdict
        if late:
            needs.append(
                f"{repo}: required check{'s' if len(late) > 1 else ''} {', '.join(late)} did "
                f"not report on combination {combo.sha[:12]} within {wait_minutes} min: the "
                "workflow that reports it does not run on pushes to fr-queue/**; add "
                "`push: branches: ['fr-queue/**']` to it"
            )
    return out, needs


# ------------------------------------------------------------------ post_merge (R33)


def last_landing(record: QueueRecord) -> QueueLandEvent | None:
    return next((e for e in reversed(record.events) if isinstance(e, QueueLandEvent)), None)


def post_merge_owed(record: QueueRecord, batches: Iterable[Batch]) -> tuple[str, ...]:
    """R33: the batches of *record*'s last landing with no `post_merge` recorded since it;
    while any is, `post_merge` runs (once, for the whole landing) and nothing more lands."""
    land = last_landing(record)
    if land is None:
        return ()
    by_id = {b.id: b for b in batches}
    owed: list[str] = []
    for ref in land.entries:
        batch = by_id.get(ref.batch or "")
        if batch is None:
            continue
        if not any(isinstance(e, PostMergeEvent) and e.at >= land.at for e in batch.events):
            owed.append(batch.id)
    return tuple(owed)


# ------------------------------------------------------------------ the executor (§A)


class QueueWriter(Protocol):
    """Appends *event* to this scope's current queue record of the repo, through the one
    judgements writer; a `queue_open` starts a new record for *wave* at *base* (R24)."""

    def __call__(self, event: QueueEvent, *, wave: int | None = None, base: str = "") -> None: ...


@dataclass
class QueuePorts:
    """What the executor acts through: the repo's clone and forge client, its merge method
    and version block, the queue's config, a scratch directory under the state directory,
    the one writer, each entry as it is built now (*entry_of*) and its PR (*pr_of*:
    number and head ref), the repo's `post_merge` for a landing (None: none; it returns
    the failure, None on success, and records `post_merge` on every batch), and the
    hand-back of an ejected entry (its line)."""

    checkout: Checkout
    client: Any
    repo: str
    scope: str
    default: str
    method: Method
    version: VersionBlock | None
    config: QueueConfig
    scratch: Path
    record: QueueWriter
    entry_of: Callable[[str], EntryInput | None]
    pr_of: PrOf
    post_merge: Callable[[tuple[str, ...]], str | None] | None = None
    hand_back: Callable[[QueueAction], str] | None = None
    now: Callable[[], datetime] = _utcnow


class QueueExecutor:
    """Executes one repo's `QueuePlan` (§A). It keeps only the conflicts met building an
    entry (the planner's `QueueSnapshot.conflicts`), which a restarted driver meets again
    on its next build; everything else is read back from the events and the remote."""

    def __init__(self, ports: QueuePorts) -> None:
        self.ports = ports
        self.conflicts: dict[str, BuildConflict] = {}

    # ---------------------------------------------------------- resumption (R24)

    def main_now(self) -> str:
        return self.ports.checkout.remote_sha(f"refs/heads/{self.ports.default}") or ""

    def resume(self, record: QueueRecord | None) -> list[str]:
        """R24: finish what a driver killed mid-pass left. A combination recorded but not
        pushed to its slot is pushed now; a landing pushed but not recorded (`main` is a
        recorded combination's sha) is recorded, never pushed again."""
        if record is None or not any(isinstance(e, QueueOpenEvent) for e in record.events):
            return []
        p, rep, lines = self.ports, replay(record), []
        main = self.main_now()
        landed = {e.main for e in record.events if isinstance(e, QueueLandEvent)}
        combo = next((c for c in rep.combos.values() if c.sha == main), None)
        if main and main != rep.base and combo is not None and main not in landed:
            refs = _refs(record)
            entries = [refs.get(k) or QueueEntryRef(batch=k) for k in combo.chain]
            p.record(QueueLandEvent(kind="queue_land", at=p.now(), main=main, entries=entries))
            lines.append(
                f"queue-land {p.repo}: {', '.join(combo.chain)} had landed at "
                f"{main[:12]} before the driver stopped: recorded, not pushed again"
            )
            return lines
        for c in rep.combos.values():
            ref = slot_ref(p.scope, c.slot)
            held = p.checkout.remote_sha(ref)
            if held == c.sha or not p.checkout.has_commit(c.sha):
                continue
            try:
                p.checkout.push_leased([(c.sha, ref)], {ref: held}, atomic=False)
            except GitError as exc:
                lines.append(f"queue-build {p.repo}: slot {c.slot} was not re-pushed: {exc}")
                continue
            lines.append(f"queue-build {p.repo}: slot {c.slot} re-pushed at {c.sha[:12]} "
                         "(recorded before the driver stopped)")  # fmt: skip
        return lines

    # ---------------------------------------------------------- gating (R33, R35)

    def gate(
        self, plan: QueuePlan, record: QueueRecord | None, batches: Iterable[Batch]
    ) -> QueuePlan:
        """Before any landing: the last landing's `post_merge`, run once if it is owed
        (R33), and its PRs read back from the forge (R35). Either one unfinished pauses
        the landings with a Need."""
        if record is None or plan.phase != "open":
            return plan
        p = self.ports
        owed = post_merge_owed(record, batches) if p.post_merge is not None else ()
        if owed and p.post_merge is not None:
            failed = p.post_merge(owed)
            if failed is not None:
                return pause_landings(
                    plan,
                    f"post_merge failed after the landing of "
                    f"{', '.join(owed)}: {failed}; it runs again next pass",
                )
        if not any(a.kind == "queue-land" for a in plan.actions):
            return plan
        land = last_landing(record)
        if land is None:
            return plan
        numbers = [known[0] for ref in land.entries if (known := p.pr_of(entry_key(ref)))]
        unmerged = read_back(p.client, p.repo, numbers)
        if unmerged:
            prs = ", ".join(f"#{n}" for n in unmerged)
            return pause_landings(plan, f"the forge did not mark {prs} merged after the "
                                  "queue landed it; check the PR (on Gitea, enable "
                                  "\"autodetect manual merge\")")  # fmt: skip
        return plan

    # ---------------------------------------------------------- executing (§C, §D)

    def execute(self, plan: QueuePlan, record: QueueRecord | None) -> list[str]:
        """Run *plan*'s writes in order, one line each."""
        lines: list[str] = []
        landed: str | None = None
        failed_tip: str | None = None
        for action in plan.actions:
            line = f"{action.kind} {action.repo}: {action.detail}"
            if action.kind in ("queue-held", "queue-need", "queue-warn"):
                continue
            if action.kind == "queue-open":
                base = self.main_now()
                self.ports.record(QueueOpenEvent(kind="queue_open", at=self.ports.now()),
                                  wave=action.wave, base=base)  # fmt: skip
                lines.append(f"{line}: opened at {base[:12]}")
            elif action.kind in ("queue-build", "queue-rebuild") and record is not None:
                if failed_tip is not None and action.base == failed_tip:
                    lines.append(f"{line}: not built, the landing it builds on did not land")
                    continue
                queue_base = action.base if action.kind == "queue-rebuild" else (
                    landed or replay(record).base)  # fmt: skip
                lines.append(f"{line}: {self._build(action, queue_base)}")
            elif action.kind == "queue-land" and record is not None:
                outcome, said = self._land(action, record)
                if outcome.outcome == "landed":
                    landed = outcome.main
                else:
                    failed_tip = action.sha
                lines.append(f"{line}: {said}")
            elif action.kind == "queue-eject" and record is not None:
                lines.append(f"{line}: {self._eject(action, record)}")
            elif action.kind == "queue-drain":
                self.ports.record(QueueDrainEvent(kind="queue_drain", at=self.ports.now(),
                                                  main=action.sha or None))  # fmt: skip
                lines.append(f"{line}: drained")
            else:  # queue-hold, queue-cleared: the hold handshake
                lines.append(f"{line}: planned, not executed (the hold is not written yet)")
        return lines

    def _build(self, action: QueueAction, queue_base: str) -> str:
        p = self.ports
        inputs = [p.entry_of(k) for k in action.entries]
        if any(i is None for i in inputs):
            return "not built: an entry's PR is not readable now"
        try:
            built = build(
                p.checkout, action.base, [i for i in inputs if i is not None], p.method,
                p.version, scope=p.scope, slots=action.slots, scratch=p.scratch,
                queue_base=queue_base, record=p.record, now=p.now,
            )  # fmt: skip
        except MergeConflictError as exc:
            self.conflicts[exc.batch] = BuildConflict(exc.head, exc.paths)
            return f"{exc.batch} conflicts in {', '.join(exc.paths)}: it leaves the queue"
        except LeaseLostError:
            return "a slot moved under the build; built again next pass"
        except (MergeStopError, GitError) as exc:
            return f"not built: {exc}"
        for b in built:
            self.conflicts.pop(b.entry.key, None)
        return "built " + ", ".join(f"slot-{b.slot} {b.sha[:12]}" for b in built)

    def _land(self, action: QueueAction, record: QueueRecord) -> tuple[LandResult, str]:
        p = self.ports
        landings = landings_from(record, action.sha, p.pr_of)
        if not landings:
            return LandResult("stopped"), "not landed: an entry's PR is not readable now"
        if p.config.land == "merge":
            result = land_merge(
                p.client,
                p.checkout,
                p.repo,
                default=p.default,
                tip=action.sha,
                landings=landings,
                method=p.method,
                record=p.record,
                now=p.now,
            )
        else:
            result = land_push(
                p.checkout,
                default=p.default,
                base=replay(record).base,
                landings=landings,
                method=p.method,
                record=p.record,
                now=p.now,
            )
        if result.outcome == "lease":
            return result, "a lease failed: nothing landed, the queue is rebuilt next pass"
        if result.outcome != "landed":
            return result, f"held: {result.detail}" if result.outcome == "held" else (
                f"stopped: {result.detail}")  # fmt: skip
        said = f"landed at {result.main[:12]}"
        keys = tuple(x.key for x in landings if x.ref.batch is not None)
        if p.post_merge is not None and keys:  # R33: once per landing, right after it
            failed = p.post_merge(keys)
            said += "; post_merge ran" if failed is None else f"; post_merge failed: {failed}"
        unmerged = read_back(p.client, p.repo, [x.pr for x in landings])
        if unmerged:
            said += "; the forge did not mark " + ", ".join(f"#{n}" for n in unmerged) + " merged"
        return result, said

    def _eject(self, action: QueueAction, record: QueueRecord) -> str:
        p = self.ports
        key = action.entries[0]
        ref = _refs(record).get(key) or QueueEntryRef(batch=key)
        reason: Literal["conflict", "red", "operator"] = (
            "conflict" if action.reason == "conflict" else "red")  # fmt: skip
        p.record(QueueEjectEvent(kind="queue_eject", at=p.now(), entry=ref, reason=reason,
                                 detail=action.detail, head=action.head or None))  # fmt: skip
        self.conflicts.pop(key, None)
        if p.hand_back is None:
            return "ejected"
        return f"ejected; {p.hand_back(action)}"
