"""The board's decision views, as pure functions of the facts (wave-driver R18, R19, R16).

**Needs you now** and **Next up** are computed from the SAME inputs the driver reads, so
the two cannot disagree about what is waiting: this module builds a driver `Snapshot`
from `facts.json` alone (`drive_snapshot`) and runs `batch_drive.drive_pass` over it.
What the driver would do (`dispatch`, `warn`, `foreign`, `blocked`) is read off its actions, never
re-derived; only what the driver cannot see offline (a draft PR that is green, a stale
dispatch, a `post_merge` that never succeeded, an unplaced issue) is computed here, and
every one of those reads the facts and the driver's own `checks_verdict`.

There is no clock: "now" is `facts.collected_at`, so a board is a function of its inputs.

R18 also names "a batch waiting on an operator answer". No such signal exists in the
facts or in the driver's snapshot (the run cursor that would show an operator gate is
not collected), so no row of that kind is produced — it is not invented
(journal decision `p4-operator-answer-not-derivable`).
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from fr.labels import APPROVED_FR
from fr.triage.approval import ApprovalVerdict, Void, approval_verdict, is_approved, voided_at
from fr.triage.batch import (
    QueueEntry,
    batch_item_id,
    batch_pr,
    batch_repo,
    derive_batch_stage,
    foreign_batch_prs,
    is_open,
    pr_open_queue,
)
from fr.triage.batch_drive import (
    ARCHIVE_WAIT,
    AWAITING_LIVE_HOLD,
    CLOSEOUT_FALLBACK,
    DEFAULT_MAX_INFLIGHT,
    IN_FLIGHT,
    LANDED,
    REFUSALS_BEFORE_NEED,
    LivePr,
    Snapshot,
    checks_verdict,
    closeout_event,
    closeout_item_id,
    drive_pass,
    enqueue_refusals,
    fact_ledger_unknown,
    fact_ledgers,
    held_archive_conflict,
    held_conflict,
    last_enqueue,
)
from fr.triage.batch_drive import _dispatch_key as dispatch_key
from fr.triage.batch_drive import (
    finished_waves as finished_waves,
)
from fr.triage.check import batch_awaits_live, classify, is_set_apart, stale_dispatches
from fr.triage.lanes import gated_pr_lane, lane_of, live_stops, unlisted_gated_prs
from fr.triage.merge_stops import MergeStop
from fr.triage.mergeability import conflicting
from fr.triage.model import (
    Batch,
    CloseoutHandbackEvent,
    Facts,
    Judgement,
    Judgements,
    PullRequest,
    RedHandbackEvent,
    Severity,
)

CX_RANK = {"XS": 0, "S": 1, "S-M": 2, "M": 3, "L": 4, "-": 5}

UNWAVED = "none"
"""The key of the pane that holds batches with no `wave`."""


def _parse(stamp: str | None) -> datetime | None:
    if not stamp:
        return None
    try:
        parsed = datetime.fromisoformat(stamp)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def collected(facts: Facts) -> datetime:
    """The board's "now": when the facts were collected. Never a clock."""
    parsed = _parse(facts.collected_at)
    if parsed is None:
        raise ValueError(f"facts.collected_at is not an aware timestamp: {facts.collected_at!r}")
    return parsed


# ------------------------------------------------------------- the driver's view


def drive_snapshot(
    facts: Facts,
    judgements: Judgements,
    *,
    max_inflight: int = DEFAULT_MAX_INFLIGHT,
    ci_none: Collection[str] = (),
) -> Snapshot:
    """The snapshot the driver would decide from, built from the facts alone: each
    open batch PR as the facts show it (no forge read), every stage derived, the
    release commit unknown (so a close-out falls back to the ten-minute rule). A PR of
    a repo in *ci_none* (its default branch declares `ci none`, known only from a
    clone) is green on its checks as the driver judges it (R4, p1-r2)."""
    batches = judgements.batches
    repos = {b.id: r for b in batches if (r := batch_repo(b, facts)) is not None}
    stages = {b.id: derive_batch_stage(b, facts) for b in batches}
    queue = tuple(pr_open_queue(batches, facts, judgements.issues))
    live: dict[str, LivePr] = {}
    for entry in queue:
        none = repos.get(entry.batch.id) in ci_none
        verdict, failing = checks_verdict([], entry.pr.checks or {}, ci_none=none)
        live[entry.batch.id] = LivePr(
            number=entry.pr.number,
            state=entry.pr.state,
            draft=entry.pr.is_draft,
            head=entry.pr.head_oid,
            checks=verdict,
            failing=failing,
            head_ref=entry.pr.head_ref,
            trusted=True,  # the queue holds `batch_pr`s only (gh#936)
            labels=tuple(entry.pr.labels) if entry.pr.labels is not None else None,
        )
    merged_at: dict[str, datetime] = {}
    for b in batches:
        if stages[b.id] in LANDED and closeout_event(b) is None:
            pr = batch_pr(b, facts)
            when = _parse(pr.merged_at if pr else None)
            if when is not None:
                merged_at[b.id] = when
    return Snapshot(
        batches=tuple(batches),
        stages=stages,
        queue=queue,
        live=live,
        repos=repos,
        now=collected(facts),
        max_inflight=max_inflight,
        merged_at=merged_at,
        foreign={b.id: found for b in batches if (found := tuple(foreign_batch_prs(b, facts)))},
        awaiting=frozenset(b.id for b in batches if batch_awaits_live(b, facts)),
        approvals=fact_approvals(queue),
        queue_inferred=True,
        ledgers=fact_ledgers(batches, facts, stages),  # labels only: no clone (R13)
        ledger_unknown=fact_ledger_unknown(batches, facts, stages),
        post_merge_repos=frozenset(
            r for r in set(repos.values()) if facts.config_for(r).post_merge
        ),
        closeouts=tuple(judgements.closeouts),  # the driver's and the board's one source
    )


def fact_approvals(queue: Iterable[QueueEntry]) -> dict[str, ApprovalVerdict]:
    """Each queued batch's approval verdict from the collected labels and its events
    (merge-train-safety §A "The walk"): the board and `drive --plan` read no forge. A
    PR whose labels were never read (facts before schema 9) is unlabelled."""
    return {
        e.batch.id: approval_verdict(e.batch.events, e.pr.number, e.pr.head_oid, e.pr.labels)
        for e in queue
    }


# ------------------------------------------------------------------ needs you now


@dataclass(frozen=True)
class Need:
    # approve-pr | failing-ci | foreign-pr | blocked-batch | post-merge | stale-dispatch
    # | needs-developer | needs-reviewer | needs-tester | needs-devops (the board's lanes)
    # | ledger-unread (a landed batch whose gate labels could not be read)
    # | gated-unread (a repo whose gate-labelled merged PRs could not be listed)
    # | closeout-held (a landed batch the close-out verb held, exit-gates R15)
    # | closeout-pr-closed | closeout-needs-review | closeout-unrecorded | closeout-reopened
    #   (a collected close-out PR the driver will not merge unasked, R15)
    # | closeout-stuck (a collected close-out PR whose one hand-back is spent, R27)
    # | unplaced | merge-conflict | session-blocked | red-pr | queue-ejected | enqueue-refused
    # | archive-conflict
    kind: str
    ref: str  # the batch id, `<owner/repo>#<n>` (a gated PR), or issue key the row names
    text: str
    href: str | None  # an https URL, or `#batch-<id>` on the page itself


NEED_LABELS = {
    "approve-pr": "Label a green PR approved-fr",
    "red-pr": "Red PR its session cannot fix",
    "queue-ejected": "PR ejected from the merge queue",
    "enqueue-refused": "PR the merge queue refuses",
    "failing-ci": "Failing CI",
    "foreign-pr": "Foreign PR on a batch branch",
    "blocked-batch": "Blocked batch",
    "post-merge": "post_merge not done",
    "stale-dispatch": "Stale dispatch",
    "unplaced": "Unplaced issue",
    "merge-conflict": "Merge conflict",
    "archive-conflict": "Archive PR conflict",
    "session-blocked": "Session blocked",
    "ledger-unread": "Gate labels unread",
    "gated-unread": "Gate labels unread",
    "closeout-held": "Close-out held: Test Plan outcome owed",
    "closeout-stuck": "Close-out PR stuck",
    "closeout-pr-closed": "Close-out PR closed unmerged",
    "closeout-needs-review": "Close-out PR needs review",
    "closeout-unrecorded": "Close-out pushed with nothing recorded",
    "closeout-reopened": "Close-out PR reopened",
    "needs-developer": "Needs you · Developer",
    "needs-reviewer": "Needs you · Reviewer",
    "needs-tester": "Needs you · Tester",
    "needs-devops": "Needs you · DevOps",
}


def queue_needs(snap: Snapshot) -> list[Need]:
    """What the driver recorded about a PR it enqueued, as needs (merge-train-safety §D):
    one that left the merge queue unmerged with the base unmoved (`ejected`), and one the
    forge refused to enqueue twice at its current head (`refused`). Read from the events,
    like `red-pr`, so the facts-only board shows them too."""
    out: list[Need] = []
    for entry in snap.queue:
        live = snap.live.get(entry.batch.id)
        if live is None or live.state != "OPEN":
            continue
        event = last_enqueue(entry.batch, live.number)
        if event is None or event.head != live.head:
            continue
        if event.outcome == "ejected":
            out.append(
                Need("queue-ejected", entry.batch.id,
                     f"PR #{live.number} left the merge queue unmerged", entry.pr.url)
            )  # fmt: skip
        elif event.outcome == "refused":
            refused = enqueue_refusals(entry.batch, live.number, live.head)
            if len(refused) >= REFUSALS_BEFORE_NEED:
                why = f": {event.detail}" if event.detail else ""
                out.append(
                    Need("enqueue-refused", entry.batch.id,
                         f"PR #{live.number} cannot be put in the merge queue{why}", entry.pr.url)
                )  # fmt: skip
    return out


def gated_unread_needs(facts: Facts) -> list[Need]:
    """One `gated-unread` Need per repo whose gate-labelled merged PRs could not be read
    (gate-backfill R13); a backend that cannot list PRs by label at all (glab, tea) is a
    permanent absence, so it folds into ONE Need per backend naming the repos it covers.
    The board's notes print these same texts, so an unread repo never looks like an empty lane."""
    out: list[Need] = []
    unsupported: dict[str, list[str]] = {}
    for u in facts.gated_unread:
        if (backend := u.unsupported_backend) is not None:
            unsupported.setdefault(backend, []).append(u.repo)  # permanent: one Need a backend
        else:
            out.append(Need("gated-unread", u.repo, u.describe(), None))
    for backend, repos in unsupported.items():
        n = len(repos)
        out.append(
            Need("gated-unread", backend,
                 f"gate-labelled PRs not read: this forge ({backend}) cannot list PRs by label "
                 f"({n} repo{'s' if n != 1 else ''}: {', '.join(sorted(repos))})", None)
        )  # fmt: skip
    return out


def needs_you(
    facts: Facts,
    judgements: Judgements,
    session_notes: Mapping[str, str] | None = None,
    *,
    ci_none: Collection[str] = (),
    stops: Mapping[str, MergeStop] | None = None,
) -> list[Need]:
    """Everything waiting on the operator, from the facts the driver reads. *session_notes*
    are blocked sessions' own notes by item id, from a runner that gives them
    (`SessionNotes`, cloud-triage R15); each is one row, and without them nothing is.
    *stops* are the driver's recorded merge stops (`merge_stops.load_stops`): a
    conflicting export PR's, keyed `export:<repo>`, is a row (merge-truth R12)."""
    snap = drive_snapshot(facts, judgements, ci_none=ci_none)
    plan = drive_pass(snap)
    by_id = {b.id: b for b in judgements.batches}
    foreign = {
        (found.pr.repo, found.pr.number): found for found_all in snap.foreign.values()
        for found in found_all
    }  # fmt: skip
    out: list[Need] = []

    # The approval gate (merge-train-safety §A, R5): a green batch PR, draft or not,
    # merges only once the operator labels it; a voided label is asked for again.
    for entry in snap.queue:
        pr = entry.pr
        if pr.state != "OPEN" or (pr.repo, pr.number) in foreign:
            continue  # a foreign PR is never one to approve (gh#936)
        live = snap.live.get(entry.batch.id)  # its checks as the driver judges them (R4)
        verdict = live.checks if live is not None else "pending"
        approval = snap.approvals.get(entry.batch.id)
        if verdict != "green" or (approval is not None and is_approved(approval)):
            continue
        was = (
            approval.approved_head
            if isinstance(approval, Void)
            else voided_at(entry.batch.events, pr.number)
        )
        text = (
            f"PR #{pr.number} changed since you approved it at {was[:12]}: re-label to merge"
            if was is not None
            else f"PR #{pr.number} is green: label it {APPROVED_FR.name} to merge"
        )
        out.append(Need("approve-pr", entry.batch.id, text, pr.url))

    out.extend(queue_needs(snap))
    for action in plan.actions:
        if action.kind == "warn" and not action.ejected:
            if action.detail.startswith(ARCHIVE_WAIT):
                continue  # an archive PR's waiting line (merge-truth R9), never a Need
            failing_pr = batch_pr(by_id[action.batch], facts)
            url = failing_pr.url if failing_pr else None
            # R11: a red hand-back delivered at this head means its session has it in hand,
            # so no `failing-ci` need; one nobody could take is a `red-pr` need instead.
            covering = [
                e for e in by_id[action.batch].events
                if action.red and isinstance(e, RedHandbackEvent)
                and (e.pr, e.head) == (action.pr, action.head)
            ]  # fmt: skip
            if covering and covering[-1].delivered == "session":
                continue
            if covering:
                out.append(
                    Need("red-pr", action.batch,
                         f"PR #{action.pr} is red at {action.head[:12]} "
                         f"({', '.join(action.checks) or 'checks failing'}) and no session "
                         "can take it", url)
                )  # fmt: skip
                continue
            out.append(Need("failing-ci", action.batch, action.detail, url))
    for action in plan.actions:
        if action.kind == "foreign":
            found_pr = next(
                f.pr for f in snap.foreign.get(action.batch, ()) if f.pr.number == action.pr
            )
            out.append(Need("foreign-pr", action.batch, action.detail, found_pr.url))
    stuck: set[str] = set()  # one row per collected close-out, not per member
    for action in plan.actions:
        if action.kind == "closeout-held":
            out.append(Need("closeout-held", action.batch, f"batch {action.batch}: "
                            f"{action.detail}", f"#batch-{action.batch}"))  # fmt: skip
        elif action.kind in ("closeout-pr-closed", "closeout-needs-review",
                             "closeout-unrecorded", "closeout-reopened"):  # fmt: skip
            out.append(Need(action.kind, action.batch, action.detail, f"#batch-{action.batch}"))
        elif action.kind == "closeout-stuck" and action.key not in stuck:
            stuck.add(action.key)
            out.append(Need("closeout-stuck", action.batch, action.detail,
                            f"#batch-{action.batch}"))  # fmt: skip
    for b in judgements.batches:  # R27, from the events: no session could take it
        event = closeout_event(b)
        if event is None or event.archived is not None:
            continue
        for e in b.events:
            if isinstance(e, CloseoutHandbackEvent) and e.delivered == "none":
                if e.item not in stuck:
                    stuck.add(e.item)
                    text = (f"close-out PR #{e.pr} ({e.reason}) was handed back with no "
                            f"session to take it: fix it on {event.archive}")  # fmt: skip
                    out.append(Need("closeout-stuck", b.id, text, f"#batch-{b.id}"))
    for action in plan.actions:
        if action.kind == "blocked":
            out.append(
                Need("blocked-batch", action.batch, f"{action.batch} {action.detail}",
                     f"#batch-{action.batch}")
            )  # fmt: skip

    for b in judgements.batches:
        repo = snap.repos.get(b.id)
        # Only a batch with a `wave` is one the driver handles by default; an older
        # batch merged by hand would otherwise carry this row forever.
        if (
            b.wave is None
            or snap.stages.get(b.id) not in LANDED
            or repo is None
            or closeout_event(b) is not None
            or any(e.kind == "post_merge" for e in b.events)
            or not facts.config_for(repo).post_merge
        ):
            continue
        merged = snap.merged_at.get(b.id)
        if merged is None or snap.now - merged < CLOSEOUT_FALLBACK:
            continue
        out.append(
            Need("post-merge", b.id,
                 f"batch {b.id} merged {merged.isoformat()} and its post_merge has not "
                 "succeeded (it failed, or no driver is running)", f"#batch-{b.id}")
        )  # fmt: skip

    for b in judgements.batches:
        held = held_conflict(b)
        if held is None or not is_open(b, facts):
            continue
        out.append(
            Need("merge-conflict", b.id,
                 f"batch {b.id} conflicts at {held.head} in {', '.join(held.paths)}, and its "
                 "hand-backs are spent: resolve it, or dispatch or cancel the batch",
                 f"#batch-{b.id}")
        )  # fmt: skip

    out.extend(archive_conflict_needs(facts, judgements, snap.repos, stops or {}))

    # The four Needs-you lanes (exit-gates R17): one Need per card the board puts in one,
    # from the same `lane_of`, so "Needs you now" and the columns agree.
    held_stops = live_stops(judgements.batches, facts, stops or {})
    has_row = {n.ref for n in out if n.kind in ("approve-pr", "failing-ci", "red-pr")}  # p5-r3
    for b in judgements.batches:
        if b.id in snap.ledger_unknown:  # p5-r2: not a lane; the close-out waits on it
            out.append(
                Need("ledger-unread", b.id,
                     f"batch {b.id}: its merged PR's gate labels could not be read, so the "
                     "close-out waits; the next collect retries", f"#batch-{b.id}")
            )  # fmt: skip
        placed = lane_of(b, facts, held_stops.get(b.id))
        if placed is None or (placed.lane == "needs-reviewer" and b.id in has_row):
            continue
        lane_pr = batch_pr(b, facts)
        text = f"batch {b.id}: {placed.reason}"
        if lane_pr is not None and conflicting(lane_pr.mergeable, lane_pr.merge_state):
            text += f" (PR #{lane_pr.number} is also conflicting)"
        out.append(Need(placed.lane, b.id, text, f"#batch-{b.id}"))

    for g in unlisted_gated_prs(judgements.batches, facts, held_stops):
        placed = gated_pr_lane(g)
        if placed is not None:
            out.append(
                Need(placed.lane, f"{g.repo}#{g.number}", f"{g.repo} PR #{g.number}: "
                     f"{placed.reason}", g.url)
            )  # fmt: skip
    out.extend(gated_unread_needs(facts))

    for s in stale_dispatches(facts):
        out.append(
            Need("stale-dispatch", s.key,
                 f"{s.key} was dispatched {s.days} days before the last collect and has no PR",
                 s.url)
        )  # fmt: skip
    for i in classify(facts, judgements).unplaced:
        out.append(Need("unplaced", i.key, f"{i.key} {i.title}: in no batch, feature or parked",
                        i.url))  # fmt: skip
    for b in judgements.batches:
        repo = snap.repos.get(b.id)
        if repo is None or not session_notes:
            continue
        for item, what in (
            (batch_item_id(repo, b.id), "session"),
            (closeout_item_id(repo, b.id), "close-out session"),
        ):
            if note := session_notes.get(item):
                out.append(
                    Need("session-blocked", b.id, f"batch {b.id}'s {what} is blocked: {note}",
                         f"#batch-{b.id}")
                )  # fmt: skip
    return out


def archive_conflict_needs(
    facts: Facts,
    judgements: Judgements,
    repos: Mapping[str, str],
    stops: Mapping[str, MergeStop],
) -> list[Need]:
    """merge-truth R12: an archive PR whose hand-backs are spent (a held `archive_conflict`
    event whose head is still the PR's, as far as the facts show it), and an export PR
    the driver stopped on for a conflict. Never a `failing-ci` or `merge-conflict` row."""
    out: list[Need] = []
    known = {(p.repo, p.number): p for p in (*facts.prs, *(q for i in facts.issues for q in i.prs))}
    for b in judgements.batches:
        held = held_archive_conflict(b)
        repo = repos.get(b.id)
        if held is None or repo is None:
            continue
        found = known.get((repo, held.pr))
        if found is not None and (found.state != "OPEN" or found.head_oid != held.head):
            continue  # merged, closed, or a new head: no longer this conflict
        out.append(
            Need("archive-conflict", b.id,
                 f"batch {b.id}'s archive PR #{held.pr} conflicts at {held.head[:12]}, and its "
                 "hand-backs are spent: merge the default branch into it",
                 found.url if found is not None else f"#batch-{b.id}")
        )  # fmt: skip
    for key, stop in sorted(stops.items()):
        if key.startswith("export:") and "conflicts" in stop.reason:
            repo = key.removeprefix("export:")
            if not _export_stop_live(repo, stop, facts, judgements, known):
                continue  # merged, closed, or a new head: no longer this conflict
            out.append(
                Need("archive-conflict", repo,
                     f"{repo}'s {stop.reason} with the default branch: merge it in, or "
                     "close the PR", None)
            )  # fmt: skip
    return out


def _export_stop_live(
    repo: str,
    stop: MergeStop,
    facts: Facts,
    judgements: Judgements,
    known: Mapping[tuple[str, int], PullRequest],
) -> bool:
    """An export conflict stop holds while *repo*'s recorded export PR is unmerged and
    unclosed at the stopped head, and the facts (when they carry it) show it open at
    that head (p2-r3)."""
    for e in judgements.exports:
        if e.repo != repo or e.pr is None or e.merged or e.closed or e.head != stop.head:
            continue
        found = known.get((repo, e.pr))
        if found is None or (found.state == "OPEN" and found.head_oid == stop.head):
            return True
    return False


# ---------------------------------------------------------------------- next up


@dataclass(frozen=True)
class NextRow:
    kind: str  # batch | feature
    ref: str  # the batch id or the feature title
    title: str
    tier: int | None
    size: str
    deps: tuple[str, ...]
    reason: str
    waiting: bool = False  # a batch the driver would NOT start this pass
    severity: Severity | None = None  # the most severe member's (R11)


def size_of(keys: Sequence[str], issues: Mapping[str, Judgement]) -> str:
    """The largest size among the judged members; `-` when none carries one."""
    sizes = [issues[k].cx for k in keys if k in issues and issues[k].cx != "-"]
    return max(sizes, key=CX_RANK.__getitem__, default="-")


SEVERITY_RANK: dict[str, int] = {"low": 1, "med": 2, "high": 3}


def max_severity(keys: Sequence[str], issues: Mapping[str, Judgement]) -> Severity | None:
    """The most severe member severity (`high > med > low`); None when none carries one."""
    found = [s for k in keys if k in issues and (s := issues[k].severity) is not None]
    return max(found, key=SEVERITY_RANK.__getitem__, default=None)


def batch_tier(keys: Sequence[str], issues: Mapping[str, Judgement]) -> int | None:
    """The lowest tier among the judged members; None when none carries a judgement."""
    tiers = [issues[k].tier for k in keys if k in issues]
    return min(tiers) if tiers else None


def next_up(
    facts: Facts, judgements: Judgements, *, max_inflight: int = DEFAULT_MAX_INFLIGHT
) -> list[NextRow]:
    """What would start next, in the driver's order: the batches its plan dispatches,
    then the proposed batches it would hold (and why), then the ranked features that
    still have open issues."""
    snap = drive_snapshot(facts, judgements, max_inflight=max_inflight)
    plan = drive_pass(snap)
    by_id = {b.id: b for b in judgements.batches}
    issues = judgements.issues
    started = [a.batch for a in plan.actions if a.kind == "dispatch"]
    rows: list[NextRow] = []

    def row(b: Batch, reason: str, waiting: bool) -> NextRow:
        return NextRow(
            "batch",
            b.id,
            b.title,
            batch_tier(b.ids, issues),
            size_of(b.ids, issues),
            tuple(b.after),
            reason,
            waiting,
            max_severity(b.ids, issues),
        )

    for bid in started:
        b = by_id[bid]
        order = f", merge order {b.order}" if b.order is not None else ""
        deps = f", after {', '.join(b.after)} merged" if b.after else ", no dependencies"
        wave = f"wave {b.wave}" if b.wave is not None else "no wave"
        rows.append(row(b, f"{wave}{order}{deps}", False))

    # The driver's own hold is the one rule (spec §F, R18): a batch that awaits a live
    # walk is no work, so it is neither started nor waiting.
    skipped = {
        a.batch
        for a in plan.actions
        if a.kind == "blocked" or (a.kind == "held" and a.detail == AWAITING_LIVE_HOLD)
    }
    in_flight = sum(1 for b in judgements.batches if snap.stages.get(b.id) in IN_FLIGHT)
    for b in sorted(judgements.batches, key=dispatch_key):
        if snap.stages.get(b.id) != "proposed" or b.id in started or b.id in skipped:
            continue
        unmerged = [d for d in b.after if snap.stages.get(d) != "merged"]
        if unmerged:
            reason = f"waits for {', '.join(unmerged)} to merge"
        else:
            reason = f"the in-flight cap holds it ({in_flight} of {max_inflight} in flight)"
        rows.append(row(b, reason, True))

    for feature in sorted(judgements.features, key=lambda f: (f.rank, f.title)):
        open_ids = [
            i.key
            for i in facts.issues
            if i.state == "open" and i.key in feature.ids and not is_set_apart(i, facts)
        ]
        if not open_ids:
            continue
        why = (f": {feature.why}" if feature.why else "") + (
            f" (start: {feature.start})" if feature.start else ""
        )
        rows.append(
            NextRow(
                "feature",
                feature.title,
                feature.title,
                batch_tier(feature.ids, issues),
                size_of(feature.ids, issues),
                (),
                f"feature rank {feature.rank}{why}",
                False,
                max_severity(feature.ids, issues),
            )  # fmt: skip
        )
    return rows


# ------------------------------------------------------------------------ waves


def waves(judgements: Judgements) -> dict[str, list[Batch]]:
    """Batches grouped by wave in wave order; the batches with no wave come last under
    `UNWAVED`. Within a wave: merge order, then id."""
    grouped: dict[str, list[Batch]] = {}
    for b in sorted(judgements.batches, key=dispatch_key):
        grouped.setdefault(str(b.wave) if b.wave is not None else UNWAVED, []).append(b)
    return grouped


def batch_stages(facts: Facts, judgements: Judgements) -> dict[str, str]:
    """Every batch's derived stage, by batch id: the *stages* `finished_waves` takes."""
    return {b.id: derive_batch_stage(b, facts) for b in judgements.batches}


def unfinished_waves(facts: Facts, judgements: Judgements) -> set[str]:
    """The wave keys that still show on the board: every wave minus the finished ones."""
    done = finished_waves(judgements.batches, batch_stages(facts, judgements))
    return {str(b.wave) for b in judgements.batches if b.wave is not None} - done


def cancelled_waves(batches: Iterable[Batch], stages: Mapping[str, str]) -> frozenset[str]:
    """The finished waves that delivered nothing: every batch in them `cancelled` or
    `abandoned` (gh#1000). `finished_waves` counts them finished, rightly, since nothing
    in them will merge; the pages name them so they never pass for delivered work."""
    batches = list(batches)
    delivered = {
        str(b.wave)
        for b in batches
        if b.wave is not None and stages.get(b.id) not in {"cancelled", "abandoned"}
    }
    return finished_waves(batches, stages) - delivered


def preselected_wave(
    facts: Facts, judgements: Judgements, among: Collection[str] | None = None
) -> int | None:
    """The most recent wave (R16): the highest wave number with a batch not yet merged,
    else the highest. A cancelled batch never merges, so it does not hold a wave open.
    With *among* (wave keys), only those waves are considered: the board passes the
    unfinished ones, the history page the finished ones (triage-pages-goal R8)."""
    waved = [
        (b.wave, derive_batch_stage(b, facts), b)
        for b in judgements.batches
        if b.wave is not None and (among is None or str(b.wave) in among)
    ]
    if not waved:
        return None
    # A planned batch whose members all await their live walk is no work: the driver
    # holds it (`AWAITING_LIVE_HOLD`), so it holds no wave open either. A merged one
    # needs no such rule, since its awaiting members count as closed.
    live = [
        n
        for n, stage, b in waved
        if stage not in {"merged", "cancelled"} and not batch_awaits_live(b, facts)
    ]
    return max(live) if live else max(n for n, _, _ in waved)


def kind_counts(facts: Facts, judgements: Judgements) -> dict[str, int]:
    """Open issues by `kind`; a judged issue with no `kind`, and an unjudged one, are
    `unkinded`."""
    counts = {"defect": 0, "feature": 0, "parked": 0, "unkinded": 0}
    for i in facts.issues:
        if i.state != "open":
            continue
        j = judgements.issues.get(i.key)
        counts[j.kind if j is not None and j.kind is not None else "unkinded"] += 1
    return counts
