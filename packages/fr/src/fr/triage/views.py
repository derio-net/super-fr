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

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from fr.triage.batch import (
    batch_pr,
    batch_repo,
    derive_batch_stage,
    foreign_batch_prs,
    pr_open_queue,
)
from fr.triage.batch_drive import (
    CLOSEOUT_FALLBACK,
    DEFAULT_MAX_INFLIGHT,
    IN_FLIGHT,
    LANDED,
    LivePr,
    Snapshot,
    checks_verdict,
    closeout_event,
    drive_pass,
)
from fr.triage.batch_drive import _dispatch_key as dispatch_key
from fr.triage.batch_drive import (
    finished_waves as finished_waves,
)
from fr.triage.check import classify, stale_dispatches
from fr.triage.model import Batch, Facts, Judgement, Judgements, PullRequest, Severity

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
    facts: Facts, judgements: Judgements, *, max_inflight: int = DEFAULT_MAX_INFLIGHT
) -> Snapshot:
    """The snapshot the driver would decide from, built from the facts alone: each
    open batch PR as the facts show it (no forge read), every stage derived, the
    release commit unknown (so a close-out falls back to the ten-minute rule)."""
    batches = judgements.batches
    repos = {b.id: r for b in batches if (r := batch_repo(b, facts)) is not None}
    stages = {b.id: derive_batch_stage(b, facts) for b in batches}
    queue = tuple(pr_open_queue(batches, facts, judgements.issues))
    live: dict[str, LivePr] = {}
    for entry in queue:
        verdict, failing = checks_verdict([], entry.pr.checks or {}, ci_none=False)
        live[entry.batch.id] = LivePr(
            number=entry.pr.number,
            state=entry.pr.state,
            draft=entry.pr.is_draft,
            head=entry.pr.head_oid,
            checks=verdict,
            failing=failing,
            head_ref=entry.pr.head_ref,
            trusted=True,  # the queue holds `batch_pr`s only (gh#936)
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
    )


# ------------------------------------------------------------------ needs you now


@dataclass(frozen=True)
class Need:
    # ready-pr | failing-ci | foreign-pr | blocked-batch | post-merge | stale-dispatch | unplaced
    kind: str
    ref: str  # the batch id, `PR #n`, or issue key the row names
    text: str
    href: str | None  # an https URL, or `#batch-<id>` on the page itself


NEED_LABELS = {
    "ready-pr": "Ready a green draft",
    "failing-ci": "Failing CI",
    "foreign-pr": "Foreign PR on a batch branch",
    "blocked-batch": "Blocked batch",
    "post-merge": "post_merge not done",
    "stale-dispatch": "Stale dispatch",
    "unplaced": "Unplaced issue",
}


def _all_prs(facts: Facts) -> list[PullRequest]:
    seen: set[tuple[str, int]] = set()
    out: list[PullRequest] = []
    for pr in [*facts.prs, *facts.batch_prs, *(p for i in facts.issues for p in i.prs)]:
        if (pr.repo, pr.number) not in seen:
            seen.add((pr.repo, pr.number))
            out.append(pr)
    return out


def needs_you(facts: Facts, judgements: Judgements) -> list[Need]:
    """Everything waiting on the operator, from the facts the driver reads."""
    snap = drive_snapshot(facts, judgements)
    plan = drive_pass(snap)
    by_id = {b.id: b for b in judgements.batches}
    batch_of_pr = {
        (pr.repo, pr.number): b.id
        for b in judgements.batches
        if (pr := batch_pr(b, facts)) is not None
    }
    foreign = {
        (found.pr.repo, found.pr.number): found for found_all in snap.foreign.values()
        for found in found_all
    }  # fmt: skip
    out: list[Need] = []

    for pr in _all_prs(facts):
        if pr.state != "OPEN" or not pr.is_draft or (pr.repo, pr.number) in foreign:
            continue  # a foreign PR is never one to ready (gh#936)
        verdict, _ = checks_verdict([], pr.checks or {}, ci_none=False)
        if verdict != "green":
            continue
        bid = batch_of_pr.get((pr.repo, pr.number))
        ref = bid or f"PR #{pr.number}"
        out.append(
            Need("ready-pr", ref, f"PR #{pr.number} is a draft and its checks are green: ready it",
                 pr.url)
        )  # fmt: skip

    for action in plan.actions:
        if action.kind == "warn":
            failing_pr = batch_pr(by_id[action.batch], facts)
            out.append(
                Need("failing-ci", action.batch, action.detail,
                     failing_pr.url if failing_pr else None)
            )  # fmt: skip
    for action in plan.actions:
        if action.kind == "foreign":
            found_pr = next(
                f.pr for f in snap.foreign.get(action.batch, ()) if f.pr.number == action.pr
            )
            out.append(Need("foreign-pr", action.batch, action.detail, found_pr.url))
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

    for s in stale_dispatches(facts):
        out.append(
            Need("stale-dispatch", s.key,
                 f"{s.key} was dispatched {s.days} days before the last collect and has no PR",
                 s.url)
        )  # fmt: skip
    for i in classify(facts, judgements).unplaced:
        out.append(Need("unplaced", i.key, f"{i.key} {i.title}: in no batch, feature or parked",
                        i.url))  # fmt: skip
    return out


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

    blocked = {a.batch for a in plan.actions if a.kind == "blocked"}
    in_flight = sum(1 for b in judgements.batches if snap.stages.get(b.id) in IN_FLIGHT)
    for b in sorted(judgements.batches, key=dispatch_key):
        if snap.stages.get(b.id) != "proposed" or b.id in started or b.id in blocked:
            continue
        unmerged = [d for d in b.after if snap.stages.get(d) != "merged"]
        if unmerged:
            reason = f"waits for {', '.join(unmerged)} to merge"
        else:
            reason = f"the in-flight cap holds it ({in_flight} of {max_inflight} in flight)"
        rows.append(row(b, reason, True))

    for feature in sorted(judgements.features, key=lambda f: (f.rank, f.title)):
        open_ids = [i.key for i in facts.issues if i.state == "open" and i.key in feature.ids]
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


def preselected_wave(
    facts: Facts, judgements: Judgements, among: Collection[str] | None = None
) -> int | None:
    """The most recent wave (R16): the highest wave number with a batch not yet merged,
    else the highest. A cancelled batch never merges, so it does not hold a wave open.
    With *among* (wave keys), only those waves are considered: the board passes the
    unfinished ones, the history page the finished ones (triage-pages-goal R8)."""
    waved = [
        (b.wave, derive_batch_stage(b, facts))
        for b in judgements.batches
        if b.wave is not None and (among is None or str(b.wave) in among)
    ]
    if not waved:
        return None
    live = [n for n, stage in waved if stage not in {"merged", "cancelled"}]
    return max(live) if live else max(n for n, _ in waved)


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
