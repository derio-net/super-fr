"""`batch merge`: reconcile, refusals and execution (spec 2026-09-25-triage-batches §3.D, §3.F).

The order is `fr.triage.batch.merge_order`; this module turns it into a queue
of `Slot`s (reconcile) and merges them one at a time (execution). Every forge
operation is a `GhClient` adapter call (§3.J) and every git operation goes
through the checkout / worktree seam (`fr.triage.gitseam`), both passed in, so
this module runs no process itself and tests drive it with fakes.

Queue progress is never stored: the plan re-reads each PR, so a PR that merged
on an earlier run drops out and a re-run resumes at the first unmerged batch.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol

from fr.ghclient import MERGE_METHODS, BaseRules, GhClient, UnsupportedForgeOperation
from fr.hostclient import FORGE_ERRORS
from fr.labels import APPROVED_FR
from fr.triage.approval import Approved, Void, approval_verdict
from fr.triage.batch import MergeStep, QueueEntry, merge_order, with_forecast
from fr.triage.batch_dispatch import TRIAGE_CONFIG_PATH
from fr.triage.batch_drive import ChecksVerdict, checks_verdict
from fr.triage.batch_version import (
    all_version_files,
    is_above,
    is_lockfile,
    only_version_changed,
    only_versions_bumped,
    read_source,
    slot_versions,
)
from fr.triage.errors import TriageError
from fr.triage.model import BatchEvent, UpdateEvent, VersionBlock

FAILING_BUCKETS = frozenset({"fail", "cancel"})
# One commit on main as `CheckoutSeam.commits_behind` reports it: its sha and its
# (status, path) changes against its first parent, a rename split into D + A.
BaseCommit = tuple[str, tuple[tuple[str, str], ...]]
# Close-out and archive merges move a run's artifacts and nothing else (gh#927).
ARCHIVE_PREFIX = "docs/superpowers/"
# The acceptance matrix cites specs and plans by path, which an archive merge moves:
# a PR changing it overlaps every archive merge, though no path is shared (gh#937).
CITES_ARCHIVE_PREFIX = "docs/acceptance/"
# Change fragments: a release commit deletes the ones it consumed.
FRAGMENT_PREFIX = ".changes/"
# Update-push-wait rounds per PR before merge gives up on a moving main.
MAX_UPDATES = 3


class MergeStopError(TriageError):
    """The queue stops here (exit 1): the message says why and what to do."""


class HeadMovedError(MergeStopError):
    """The PR's head moved since the plan was made. A driver stops a merge train on
    it (R3); any other `MergeStopError` is a refusal it steps over (R4)."""


class MergeConflictError(MergeStopError):
    """A real conflict: merge refused to resolve *paths* bringing *batch*'s PR at *head*
    up to date (spec 2026-10-06-verification-strategies §G; R19). Not a moved head, so a
    driver steps over it; it hands the conflict back to the batch's session."""

    def __init__(self, message: str, *, batch: str, head: str, paths: Sequence[str]) -> None:
        super().__init__(message)
        self.batch, self.head, self.paths = batch, head, tuple(paths)


class WorktreeSeam(Protocol):
    path: Path

    def merge(self, ref: str) -> list[str]: ...
    def merge_base(self, ref: str) -> str: ...
    def show(self, ref: str, file: str) -> str | None: ...
    def take_theirs(self, paths: list[str]) -> None: ...
    def abort_merge(self) -> None: ...
    def read(self, file: str) -> str | None: ...
    def run(self, command: str, **fields: str) -> None: ...
    def commit_all(self, message: str, version_files: list[str]) -> str | None: ...
    def push(self, branch: str) -> None: ...


class CheckoutSeam(Protocol):
    path: Path

    def fetch(self) -> None: ...
    def default_branch(self) -> str: ...
    def show(self, ref: str, file: str) -> str | None: ...
    def is_ancestor(self, ancestor: str, descendant: str) -> bool: ...
    def commits_behind(self, head: str, ref: str) -> tuple[BaseCommit, ...]: ...
    def changed_paths(self, ref: str, head: str) -> frozenset[str]: ...
    def add_worktree(self, where: Path, ref: str) -> Any: ...
    def remove_worktree(self, where: Path) -> None: ...
    def rev_parse(self, ref: str) -> str: ...


@dataclass(frozen=True)
class Slot:
    """One queued PR as the plan printed it: the head it will merge and the
    version it must carry there."""

    step: MergeStep
    head: str
    slot: str | None  # None when the repo declares no version block


@dataclass
class MergeContext:
    client: GhClient
    checkout: CheckoutSeam
    repo: str
    version: VersionBlock | None
    scratch_root: Path
    method: str
    say: Callable[[str], None]
    # The check wait's bounds, in seconds: poll interval and give-up.
    interval: float = 30.0
    timeout: float = 3600.0
    sleep: Callable[[float], None] = time.sleep
    # The repo declares `ci none` on its default branch (R4): green on non-draft alone.
    ci_none: bool = False
    scratch: set[Path] = field(default_factory=set)  # worktrees this run created
    # Called as (pr, head_before, head_after, base) after each update push, so the
    # caller records it through the one judgements writer (merge-train-safety §B, R8).
    on_update: Callable[[int, str, str, str], None] | None = None
    # batch id -> the events this context recorded or was told of after the batch was
    # read (an approval settled this run, an update pushed): the gate reads them too.
    recorded: dict[str, list[BatchEvent]] = field(default_factory=dict)
    # The base branch's rules, read once per repo per pass (batch merge: per command),
    # merge-train-safety §D, R12.
    rules: BaseRules = field(default_factory=BaseRules)
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))

    @property
    def strict_checks(self) -> bool:
        """R14: the base requires PRs to be up to date, so no commit on it is routine."""
        return self.rules.strict_checks

    @property
    def main(self) -> str:
        return f"origin/{self.checkout.default_branch()}"

    def version_at(self, ref: str) -> str | None:
        if self.version is None:
            return None
        text = self.checkout.show(ref, self.version.source.file)
        if text is None:
            raise MergeStopError(f"{self.version.source.file} does not exist at {ref}")
        return read_source(text, self.version.source)


# ------------------------------------------------------------------ planning


def choose_method(
    explicit: str | None, methods: dict[str, Any], *, configured: str | None = None
) -> str:
    """The merge method (spec §3.F step 2): *explicit*, else the repo's default,
    else *configured* (`.fr/triage.yaml`'s `merge_method`, cloud-triage §A: REST
    names no default), else the one method the repo allows.

    *methods* is `GhClient.repo_merge_methods`: `{default, allowed}`. An
    explicit or configured method the repo disallows is refused here, before
    anything merges, rather than by the forge mid-queue (review r3-f4).
    """
    allowed = sorted(str(m) for m in methods.get("allowed") or [] if m in MERGE_METHODS)
    if not allowed:
        raise TriageError("the repo allows no merge method fr knows (merge, squash, rebase)")
    if explicit is not None:
        if explicit not in allowed:
            raise TriageError(
                f"--method {explicit}: the repo does not allow it (allowed: {', '.join(allowed)})"
            )
        return explicit
    default = methods.get("default")
    if default in allowed:
        return str(default)
    if configured is not None:
        if configured not in allowed:
            raise TriageError(
                f"merge_method: {configured} in {TRIAGE_CONFIG_PATH}: the repo does not allow it "
                f"(allowed: {', '.join(allowed)}); change it, or give --method"
            )
        return configured
    if len(allowed) == 1:
        return allowed[0]
    raise TriageError(
        "the repo names no default merge method you may use; set `merge_method` in "
        f"{TRIAGE_CONFIG_PATH} or give --method ({', '.join(allowed)})"
    )


def plan_queue(
    ctx: MergeContext, entries: Sequence[QueueEntry]
) -> tuple[list[Slot], list[MergeStep]]:
    """Re-read every PR, drop the merged ones, order the rest and reconcile slots.

    Returns the queue and the steps already merged (reported, never re-run).
    """
    ctx.checkout.fetch()
    live: list[QueueEntry] = []
    heads: dict[str, str] = {}
    merged: list[MergeStep] = []
    for e in entries:
        view = ctx.client.pr_view(ctx.repo, e.pr.number)
        if view.get("state") == "MERGED":
            merged.extend(with_forecast([e]))
            continue
        live.append(e)
        heads[e.batch.id] = str(view.get("head_oid") or e.pr.head_oid)
    steps = with_forecast(merge_order(live))
    main_version = ctx.version_at(ctx.main)
    slots: list[str | None] = (
        list(slot_versions(main_version, [s.batch.bump for s in steps]))
        if main_version is not None
        else [None] * len(steps)
    )
    return [Slot(s, heads[s.batch.id], v) for s, v in zip(steps, slots, strict=True)], merged


def describe(index: int, slot: Slot) -> str:
    """One line of the printed plan: PR, versions, and the shared-file forecast."""
    step = slot.step
    parts = [f"{index}. batch {step.batch.id}", f"PR #{step.pr.number}", f"head {slot.head[:12]}"]
    if slot.slot is not None:
        parts.append(f"version {step.reserved_version or '?'} -> slot {slot.slot}")
    parts.append(f"shares: {', '.join(step.shared)}" if step.shared else "shares: nothing later")
    return "  ".join(parts)


# ----------------------------------------------------------------- execution


def run_queue(ctx: MergeContext, queue: Sequence[Slot]) -> None:
    """Merge each slot in order; the first `MergeStopError` stops the queue. A PR the
    approval gate holds stops it too: `batch merge` filters unapproved batches out
    before it gets here, so one arriving is a label removed under the run."""
    previous: str | None = None
    for slot in queue:
        held = merge_one(ctx, slot, previous)
        if held is not None:
            pr = slot.step.pr
            why = held.reason or f"awaits the {APPROVED_FR.name} label"
            raise MergeStopError(f"PR #{pr.number} (batch {slot.step.batch.id}) {why}")
        previous = slot.step.batch.id


def pr_checks_verdict(
    client: GhClient, repo: str, number: int, *, ci_none: bool
) -> tuple[ChecksVerdict, tuple[str, ...]]:
    """R4 on the PR's head as the forge reports it now: the required checks when
    the branch has any, else every check; nothing reported is pending (gh#880).
    The one rule the driver pass, `batch merge` and the archive step merge by."""
    if ci_none:
        return checks_verdict([], {}, ci_none=True)
    required = client.pr_required_checks(repo, number)
    every = {} if required else _counts(client.pr_checks(repo, number))
    return checks_verdict(required, every, ci_none=False)


def live_checks(ctx: MergeContext, number: int) -> tuple[ChecksVerdict, tuple[str, ...]]:
    """`pr_checks_verdict` for the context's repo."""
    return pr_checks_verdict(ctx.client, ctx.repo, number, ci_none=ctx.ci_none)


def _counts(checks: Sequence[dict[str, Any]]) -> dict[str, int]:
    """`pr_checks` buckets as the `pass`/`fail`/`pending` counts R4 reads; a
    skipped check passes, as in the collected counts."""
    counts = {"pass": 0, "fail": 0, "pending": 0}
    for c in checks:
        bucket = c.get("bucket")
        counts[
            "fail" if bucket in FAILING_BUCKETS else "pending" if bucket == "pending" else "pass"
        ] += 1
    return counts


def _checks(ctx: MergeContext, number: int) -> None:
    """Stop unless the checks are green by R4, waiting in the foreground (d5) while
    they are pending, a head with no check yet included (gh#947)."""
    waited = 0.0
    verdict, names = live_checks(ctx, number)
    while verdict == "pending" and waited + ctx.interval <= ctx.timeout:
        ctx.sleep(ctx.interval)
        waited += ctx.interval
        verdict, names = live_checks(ctx, number)
    if verdict != "green":
        raise MergeStopError(f"PR #{number}: checks {verdict}: {', '.join(names)}")


def merge_one(ctx: MergeContext, slot: Slot, previous: str | None) -> MergeAttempt | None:
    """Steps 1-4 of spec §3.F for one PR; the gate's `unapproved`/`unready` attempt when
    the approval gate holds it (merge-train-safety §A), else None."""
    pr, batch = slot.step.pr, slot.step.batch
    expected = slot.head
    for _ in range(MAX_UPDATES + 1):
        view = ctx.client.pr_view(ctx.repo, pr.number)  # step 1: re-read
        if view.get("state") == "MERGED":
            ctx.say(f"{batch.id}: already merged (PR #{pr.number})")
            return None
        if view.get("state") == "OPEN":
            held = _approved_and_ready(ctx, slot, view, wait=True)
            if held is not None:
                return held
        head = _open_head(ctx, slot, view, expected)
        _checks(ctx, pr.number)
        new = _land(ctx, slot, head, previous)
        if new is None:
            return None
        expected = new
        _checks(ctx, pr.number)
    raise MergeStopError(
        f"PR #{pr.number} (batch {batch.id}): still behind or off its slot after "
        f"{MAX_UPDATES} updates; main keeps moving — re-run later"
    )


def _open_head(ctx: MergeContext, slot: Slot, view: dict[str, Any], expected: str) -> str:
    """The head of an OPEN, non-draft PR whose head is still *expected*, else a stop."""
    pr, batch = slot.step.pr, slot.step.batch
    if view.get("state") != "OPEN":
        raise MergeStopError(f"PR #{pr.number} (batch {batch.id}) is {view.get('state')}")
    if view.get("draft"):
        raise MergeStopError(f"PR #{pr.number} (batch {batch.id}) is a draft; mark it ready")
    head = str(view.get("head_oid"))
    if head != expected:
        raise HeadMovedError(
            f"PR #{pr.number} (batch {batch.id}): head moved since the plan was printed "
            f"({expected[:12]} -> {head[:12]}); re-run to re-plan"
        )
    return head


def _land(ctx: MergeContext, slot: Slot, head: str, previous: str | None) -> str | None:
    """Steps 2-3: merge a PR that is current and on its slot (returns None), else push
    the update that brings it there (returns the new head)."""
    ctx.checkout.fetch()
    behind = not ctx.checkout.is_ancestor(ctx.main, head) and (
        ctx.strict_checks or not _behind_only_routinely(ctx, head)  # R14: strict has no exemption
    )
    head_version = ctx.version_at(head)
    wrong_slot = slot.slot is not None and head_version != slot.slot
    if not behind and not wrong_slot:
        _merge(ctx, slot, head, head_version)  # step 2
        return None
    return _update(ctx, slot, head, behind, previous)  # step 3


def routine_commit(
    changes: Sequence[tuple[str, str]], show: Callable[[str, str], str | None], sha: str = ""
) -> bool:
    """Whether a commit on main cannot change what a PR's CI proved (gh#927),
    judged by the files it changes, never by its subject line:

    - a close-out / archive merge: every path under `docs/superpowers/`;
    - a release commit: it deletes at least one `.changes/` fragment, and every
      other file it changes only moves one version up (`only_versions_bumped`).
      The fragment is what tells a release from a version-shaped edit elsewhere,
      a pinned tool in a workflow or a constant in source (review).

    A commit that changed nothing knowable is not routine, nor is a file whose
    content did not change (a mode flip shows as `M` with equal bytes).
    """
    if not changes:
        return False
    if _is_archive(changes):
        return True
    consumed = False
    pairs: list[tuple[str, str]] = []
    for status, path in changes:
        if path.startswith(FRAGMENT_PREFIX) and status == "D":
            consumed = True
            continue
        before, after = show(f"{sha}^", path), show(sha, path)
        if status != "M" or before is None or after is None or before == after:
            return False
        pairs.append((before, after))
    return consumed and bool(pairs) and only_versions_bumped(pairs)


def _behind_only_routinely(ctx: MergeContext, head: str) -> bool:
    """Whether every commit main has that *head* lacks is routine and touches no
    path the PR changed, so the PR merges as it is instead of being updated.

    The overlap rule keeps the forge's merge conflict-free and the PR's own change
    to a file from landing on a version of it the PR's CI never saw. A PR that
    changes the acceptance matrix overlaps every archive merge, whose moves can
    leave its refs dangling (gh#937).
    """
    commits = ctx.checkout.commits_behind(head, ctx.main)
    if not commits:
        return False
    touched = ctx.checkout.changed_paths(ctx.main, head)
    cites = any(path.startswith(CITES_ARCHIVE_PREFIX) for path in touched)
    return all(
        routine_commit(changes, ctx.checkout.show, sha)
        and not touched.intersection(path for _, path in changes)
        and not (cites and _is_archive(changes))
        for sha, changes in commits
    )


def _is_archive(changes: Sequence[tuple[str, str]]) -> bool:
    return bool(changes) and all(path.startswith(ARCHIVE_PREFIX) for _, path in changes)


MergeReadiness = Literal[
    "merged", "updated", "already-merged", "failing", "pending", "unapproved", "unready"
]


@dataclass(frozen=True)
class MergeAttempt:
    """What one non-blocking `merge_ready` call did, and for `failing`/`pending`
    which checks, so the caller can report them once; for `unready`, why."""

    outcome: MergeReadiness
    head: str = ""
    checks: tuple[str, ...] = ()
    reason: str = ""


def pre_merge_hold(labels: Iterable[object] | None, number: int = 0) -> str | None:
    """Why a PR's labels hold its merge (spec 2026-10-22-fr-ops R14), else None: a
    `PRE_MERGE_HOLD_GATES` gate held without its `-passed` label. The DevOps stage
    owns that merge."""
    from fr.labels import awaiting_devops, pre_merge_held

    return awaiting_devops(number) if pre_merge_held(labels) else None


def _approved_and_ready(
    ctx: MergeContext, slot: Slot, view: dict[str, Any], *, wait: bool
) -> MergeAttempt | None:
    """The one approval gate both merge paths pass (merge-train-safety §A "Merging"):
    None when the OPEN PR in *view* carries a valid approval and is (now) ready, else
    the attempt that holds it. A draft with a valid approval and green checks is
    marked ready here, and *view* is updated to say so; *wait* blocks on its checks
    as `merge_one` does, else a non-green draft returns its checks' outcome."""
    pr, batch = slot.step.pr, slot.step.batch
    head = str(view.get("head_oid") or "")
    hold = pre_merge_hold(view.get("labels"), pr.number)
    if hold is not None:
        return MergeAttempt("unapproved", head=head, reason=hold)
    events = [*batch.events, *ctx.recorded.get(batch.id, [])]
    verdict = approval_verdict(events, pr.number, head, view.get("labels"))
    if isinstance(verdict, Void):
        why = (
            f"was approved at {verdict.approved_head[:12]}, but its head moved to {head[:12]}; "
            f"the {APPROVED_FR.name} label is void"
        )
        return MergeAttempt("unapproved", head=head, reason=why)
    if not isinstance(verdict, Approved):
        return MergeAttempt("unapproved", head=head)
    if not view.get("draft"):
        return None
    if wait:
        _checks(ctx, pr.number)
    else:
        checks, names = live_checks(ctx, pr.number)
        if checks != "green":
            return MergeAttempt(checks, head=head, checks=names)
    try:
        ctx.client.pr_ready(ctx.repo, pr.number)
    except UnsupportedForgeOperation as exc:
        return MergeAttempt("unready", head=head, reason=f"cannot be marked ready: {exc}")
    except FORGE_ERRORS as exc:  # a refusal, in the forge's own words (p1-r1)
        return MergeAttempt(
            "unready", head=head, reason=f"cannot be marked ready: the forge refused: {exc}"
        )
    # Head-pinned (p1-r7): a push that landed while it was readied is not approved.
    now = str(ctx.client.pr_view(ctx.repo, pr.number).get("head_oid") or "")
    if now != head:
        why = (
            f"head moved to {now[:12]} while it was marked ready; the {APPROVED_FR.name} "
            f"approval at {verdict.approved_head[:12]} does not cover it"
        )
        return MergeAttempt("unapproved", head=now, reason=why)
    ctx.say(f"PR #{pr.number}: marked ready (approved at {verdict.approved_head[:12]})")
    view["draft"] = False
    return None


def merge_ready(ctx: MergeContext, slot: Slot, previous: str | None) -> MergeAttempt:
    """`merge_one` without the wait (wave-driver §B): merge the PR only if it carries a
    valid approval (marking an approved draft ready first, merge-train-safety §A) and
    its checks are already green by R4 (`live_checks`), else say why not.

    A PR behind its base or off its version slot gets the same update `merge_one`
    gives it and is left for a later call: it never waits for the new head's checks.
    A closed PR, a moved head or a forge refusal is a `MergeStopError`, as there.
    """
    pr, batch = slot.step.pr, slot.step.batch
    view = ctx.client.pr_view(ctx.repo, pr.number)
    if view.get("state") == "MERGED":
        return MergeAttempt("already-merged")
    if view.get("state") == "OPEN":
        held = _approved_and_ready(ctx, slot, view, wait=False)
        if held is not None:
            return held
    head = _open_head(ctx, slot, view, slot.head)
    verdict, names = live_checks(ctx, pr.number)
    if verdict != "green":
        return MergeAttempt(verdict, head=head, checks=names)
    new = _land(ctx, slot, head, previous)
    if new is not None:
        ctx.say(f"{batch.id}: updated; checks run again")
    return MergeAttempt("merged" if new is None else "updated", head=new or head)


def update_failing(ctx: MergeContext, slot: Slot) -> MergeAttempt:
    """R9: bring a red PR up to date with its base once more, the green-checks
    precondition waived (an fr-made head whose checks failed against an older base).
    The approval is not read: nothing here merges, and the update is recorded like any
    other, so the approval carries over it. A moved head is a `HeadMovedError`."""
    pr = slot.step.pr
    ctx.checkout.fetch()
    view = ctx.client.pr_view(ctx.repo, pr.number)
    head = _open_head_unready(ctx, slot, view)
    return MergeAttempt("updated", head=_update(ctx, slot, head, True, None))


def _open_head_unready(ctx: MergeContext, slot: Slot, view: dict[str, Any]) -> str:
    """The head of an OPEN PR (a draft included) that is still the slot's, else a stop."""
    pr, batch = slot.step.pr, slot.step.batch
    if view.get("state") != "OPEN":
        raise MergeStopError(f"PR #{pr.number} (batch {batch.id}) is {view.get('state')}")
    head = str(view.get("head_oid"))
    if head != slot.head:
        raise HeadMovedError(
            f"PR #{pr.number} (batch {batch.id}): head moved since it was judged "
            f"({slot.head[:12]} -> {head[:12]}); judged again next pass"
        )
    return head


def _merge(ctx: MergeContext, slot: Slot, head: str, head_version: str | None) -> None:
    pr = slot.step.pr
    main_version = ctx.version_at(ctx.main)
    if head_version is not None and main_version is not None:
        if not is_above(head_version, main_version):
            raise MergeStopError(
                f"PR #{pr.number} (batch {slot.step.batch.id}) carries {head_version}, "
                f"not above main's {main_version}; re-run to re-plan"
            )
    try:
        ctx.client.pr_merge(ctx.repo, pr.number, head_sha=head, method=ctx.method)
    except FORGE_ERRORS as exc:  # a protection refusal, in the forge's own words
        # Unless a push landed after `_open_head`: the head-SHA guard refused it, and
        # the train stops and re-plans next pass (gh#962). Told by the re-read head,
        # never by the refusal's wording, which differs per forge.
        try:
            moved = str(ctx.client.pr_view(ctx.repo, pr.number).get("head_oid"))
        except FORGE_ERRORS:
            moved = head  # unknown: report the refusal as it came
        if moved != head:
            raise HeadMovedError(
                f"PR #{pr.number} (batch {slot.step.batch.id}): head moved before the merge "
                f"({head[:12]} -> {moved[:12]}); re-run to re-plan"
            ) from exc
        raise MergeStopError(f"PR #{pr.number}: the forge refused the merge: {exc}") from exc
    ctx.say(f"merged PR #{pr.number} (batch {slot.step.batch.id}) at {head[:12]}")
    where = scratch_path(ctx, slot)
    if where in ctx.scratch or where.exists():
        ctx.checkout.remove_worktree(where)  # step 4: only after a successful merge
        ctx.scratch.discard(where)


def scratch_path(ctx: MergeContext, slot: Slot) -> Path:
    """`<state dir>/merge/<branch>/`: outside every repo on purpose (§3.F)."""
    return ctx.scratch_root / slot.step.pr.head_ref


def _update_message(
    ctx: MergeContext, slot: str | None, *, behind: bool, previous: str | None
) -> str:
    """Spec §3.F step 3's commit message."""
    default = ctx.main.removeprefix("origin/")
    if behind and slot is not None:
        after = f"batch {previous}" if previous else default
        return f"chore: take reserved version {slot} after {after}"
    if behind:
        return f"chore: update from {default}"
    return f"chore: re-slot version to {slot}"


def _unresolvable(ctx: MergeContext, wt: WorktreeSeam, conflicted: list[str]) -> list[str]:
    """The conflicted paths merge may NOT resolve by taking main's side, and
    whether a relock must regenerate a lockfile it did take (spec §3.F step 3).

    `git checkout --theirs` replaces the WHOLE file, so a declared version file
    is taken only when the PR's own change to it, from the merge base, is the
    version and nothing else (review r3-f2): then `set` re-applies the slot and
    nothing the PR wrote is lost. A lockfile the PR changed further is taken
    only when a `relock` is declared to regenerate it from the manifests.
    Everything else is a real conflict.
    """
    version = ctx.version
    if version is None:
        return list(conflicted)
    base = wt.merge_base(ctx.main)
    old_text, new_text = wt.show(base, version.source.file), wt.show("HEAD", version.source.file)
    if old_text is None or new_text is None:
        return list(conflicted)
    old, new = read_source(old_text, version.source), read_source(new_text, version.source)
    out: list[str] = []
    for path in conflicted:
        if not all_version_files([path], version.files):
            out.append(path)
            continue
        before, after = wt.show(base, path), wt.show("HEAD", path)
        if (
            before is not None
            and after is not None
            and only_version_changed(before, after, old, new)
        ):
            continue
        if is_lockfile(path) and version.relock:
            continue
        out.append(path)
    return out


def _update(ctx: MergeContext, slot: Slot, head: str, behind: bool, previous: str | None) -> str:
    """Step 3: bring the PR branch up to date and onto its slot; the new head."""
    pr = slot.step.pr
    where = scratch_path(ctx, slot)
    wt: WorktreeSeam = ctx.checkout.add_worktree(where, head)
    ctx.scratch.add(where)
    relock = False
    if behind:
        conflicted = wt.merge(ctx.main)
        if conflicted:
            refused = _unresolvable(ctx, wt, conflicted)
            if refused:
                wt.abort_merge()
                raise MergeConflictError(
                    f"PR #{pr.number} (batch {slot.step.batch.id}) conflicts with {ctx.main} "
                    f"in a change merge will not resolve: {', '.join(refused)} (only a version "
                    "file whose PR change is the version alone is resolved). The scratch "
                    f"worktree is kept for inspection at {where}",
                    batch=slot.step.batch.id,
                    head=head,
                    paths=refused,
                )
            wt.take_theirs(conflicted)
            relock = any(is_lockfile(p) for p in conflicted)
    if ctx.version is not None and slot.slot is not None:
        text = wt.read(ctx.version.source.file)
        current = read_source(text, ctx.version.source) if text is not None else None
        if current != slot.slot:
            wt.run(ctx.version.set_, version=slot.slot)
            relock = True
        if relock and ctx.version.relock:
            wt.run(ctx.version.relock)
    message = _update_message(ctx, slot.slot, behind=behind, previous=previous)
    new = wt.commit_all(message, ctx.version.files if ctx.version else [])
    if new is None:
        raise MergeStopError(f"PR #{pr.number}: the update produced no change to push")
    # Recorded BEFORE the push (p1-r6): a push that fails leaves a spare event for a
    # head nobody pushed, which is harmless; a recorded-after one could be lost, and the
    # next settle would void a valid approval over fr's own update.
    base = ctx.checkout.rev_parse(ctx.main)  # fetched by `_land` before this update
    ctx.recorded.setdefault(slot.step.batch.id, []).append(
        UpdateEvent(
            kind="update", at=ctx.now(), pr=pr.number, head_before=head, head_after=new, base=base
        )
    )
    if ctx.on_update is not None:
        ctx.on_update(pr.number, head, new, base)
    wt.push(pr.head_ref)
    ctx.say(f"PR #{pr.number}: pushed {new[:12]} ({message}); waiting for its checks")
    return new
