"""`check` — the issue sets plus unranked PRs that make triage debt visible (spec §3.F).

Pure: facts and judgements in, sets out. The command only formats them.

- **unranked** — an open issue with no judgement;
- **settled** — judged, and now `closed` or `merged`; a judged PR that is now
  closed or merged is settled too (`settled_prs`, gh#902);
- **orphaned** — a judgement whose key names no repo collect read: a typo'd or
  renamed repo, or one outside the scope. That is the ONLY meaning, so it is the
  only set whose members are safe to fix or remove without asking the forge again;
- **unreachable** — a judgement collect could not settle either way: the forge
  would not show its issue (`Facts.unviewed`, whose reason may say the issue does
  not exist — a deleted issue or a typo'd number), its repo was `Facts.skipped`,
  or its key names a collected repo but was added after the last collect. Never
  orphaned: pruning a judgement over a transient failure, or over stale facts,
  would destroy the ranking (reviews r-p2-check-sets, phase-4 C1/C2);
- **unplaced** — an open issue (judged or not) in no open batch, in no feature
  group and not parked (wave-driver R9). The still-open members of a cancelled,
  merged, partial or abandoned batch are unplaced: that batch is no longer open;
- **no severity** — an open, judged issue whose judgement carries no `severity`
  (triage-pages-goal R11);
- **duplicate unknown** — a judged issue whose `duplicate_of` names an issue the facts
  do not hold;
- **stale dispatch** — an open issue labelled `fr:in-progress` whose fr-batch
  marker comment is older than the repo's `stale_dispatch_days` (default 3)
  with no open or merged linked PR — a closed-unmerged one is not progress
  (spec 2026-09-25-triage-batches §3.E). The age is measured from the
  marker's forge `createdAt` to `collected_at`, so every machine agrees and no
  clock is read; a marker time that cannot be read is skipped, never raised.
  Reported, never acted on;
- **awaiting live** — an open issue labelled `fr:awaiting-live`: its fix has merged
  and a post-merge acceptance row still waits for its walk (spec
  2026-10-06-verification-strategies §F, R18). It is not ranked or proposed as work,
  so it is in neither unranked, unplaced nor stale dispatch, and the board shows it
  in a group of its own.

Every key comparison goes through `fr.triage.model.normalize_key` (or
`issue_key`, which is built on it). There is no second normaliser here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from fr.labels import FR_AWAITING_LIVE, FR_IN_PROGRESS
from fr.triage.batch import is_open
from fr.triage.model import Facts, Issue, Judgements, PullRequest, issue_key, normalize_key

SETTLED_STAGES = frozenset({"closed", "merged"})

JUDGED_AFTER_COLLECT = "judged after the last collect; run `fr triage collect` again to settle it"
"""Reason for a key in a collected repo that the last collect never viewed.

`check` reads the facts of the LAST collect, and collect only views the judged
keys it knew about. A key added since is absent because the facts predate it,
which says nothing about whether its issue exists (phase-4 review C2)."""


@dataclass(frozen=True)
class Unreachable:
    key: str
    reason: str


@dataclass(frozen=True)
class Stale:
    key: str
    title: str
    url: str
    marker_at: str
    days: int  # whole days between the marker and the collect


@dataclass(frozen=True)
class CheckResult:
    unranked: list[Issue]
    unranked_prs: list[PullRequest]
    settled: list[Issue]
    orphaned: list[str]
    unreachable: list[Unreachable]
    stale: list[Stale] = field(default_factory=list)
    unplaced: list[Issue] = field(default_factory=list)
    settled_prs: list[PullRequest] = field(default_factory=list)
    no_severity: list[Issue] = field(default_factory=list)
    duplicate_unknown: list[str] = field(default_factory=list)
    # Judgements whose `duplicate_of` target is itself a duplicate: a chain or a cycle
    # leaves no original on the board for its members (review p3-r2).
    duplicate_chained: list[str] = field(default_factory=list)
    awaiting_live: list[Issue] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        def row(i: Issue) -> dict[str, Any]:
            return {"key": i.key, "title": i.title, "stage": i.stage, "url": i.url}

        def pr_row(pr: PullRequest) -> dict[str, Any]:
            return {
                "key": issue_key(pr.repo, pr.number),
                "number": pr.number,
                "title": pr.title,
                "state": pr.state,
                "url": pr.url,
            }

        return {
            "unranked": [row(i) for i in self.unranked],
            "unranked_prs": [pr_row(pr) for pr in self.unranked_prs],
            "settled": [row(i) for i in self.settled],
            "settled_prs": [pr_row(pr) for pr in self.settled_prs],
            "orphaned": list(self.orphaned),
            "unreachable": [{"key": u.key, "reason": u.reason} for u in self.unreachable],
            "unplaced": [row(i) for i in self.unplaced],
            "no_severity": [row(i) for i in self.no_severity],
            "duplicate_unknown": list(self.duplicate_unknown),
            "duplicate_chained": list(self.duplicate_chained),
            "awaiting_live": [row(i) for i in self.awaiting_live],
            "stale_dispatch": [
                {
                    "key": s.key,
                    "title": s.title,
                    "url": s.url,
                    "marker_at": s.marker_at,
                    "days": s.days,
                }
                for s in self.stale
            ],
        }


def _unreachable_reason(key: str, facts: Facts) -> str | None:
    """Why *key*'s issue could not be reached, or None if nothing explains it."""
    for u in facts.unviewed:
        if normalize_key(u.key) == key:
            return u.reason
    _, _, number = key.rpartition("#")
    if number.isdigit():
        for s in facts.skipped:
            if issue_key(s.repo, int(number)) == key:
                return s.reason
        for repo in facts.collected:
            if issue_key(repo, int(number)) == key:
                return JUDGED_AFTER_COLLECT
    return None


def _aware(stamp: str | None) -> datetime | None:
    """*stamp* as an aware datetime; None when it is missing, unparseable or naive.

    `check` always exits 0 (review r2p-f13), so a time it cannot compare is
    skipped rather than raised.
    """
    if not stamp:
        return None
    try:
        parsed = datetime.fromisoformat(stamp)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def stale_dispatches(facts: Facts) -> list[Stale]:
    """The stale-dispatch set: see the module docstring."""
    collected = _aware(facts.collected_at)
    if collected is None:
        return []
    out: list[Stale] = []
    for i in facts.issues:
        # Only an OPEN or MERGED linked PR is progress; one closed unmerged is
        # not, so it does not hide a stale dispatch (review r2p-f13).
        if (
            i.state != "open"
            or any(p.state in {"OPEN", "MERGED"} for p in i.prs)
            or FR_IN_PROGRESS.name not in i.labels
            # Its fix merged through a Refs PR, which links no closing PR: it awaits
            # its live walk, which is not a stale dispatch (spec §F, R18).
            or is_awaiting_live(i)
        ):
            continue
        marker = _aware(i.dispatch_marker_at)
        if marker is None:
            continue
        age = collected - marker
        if age > timedelta(days=facts.config_for(i.repo).stale_dispatch_days):
            out.append(
                Stale(
                    key=i.key,
                    title=i.title,
                    url=i.url,
                    marker_at=i.dispatch_marker_at or "",
                    days=age.days,
                )
            )
    return out


def is_awaiting_live(issue: Issue) -> bool:
    """Whether `issue` is open and carries `fr:awaiting-live`."""
    return issue.state == "open" and FR_AWAITING_LIVE.name in issue.labels


def awaiting_live_issues(facts: Facts) -> list[Issue]:
    """The awaiting-live set: see the module docstring."""
    return [i for i in facts.issues if is_awaiting_live(i)]


def unplaced_issues(facts: Facts, judgements: Judgements) -> list[Issue]:
    """The unplaced set: see the module docstring."""
    placed: set[str] = set()
    for batch in judgements.batches:
        if is_open(batch, facts):
            placed.update(batch.ids)
    for feature in judgements.features:
        placed.update(feature.ids)
    placed.update(k for k, j in judgements.issues.items() if j.kind == "parked" or j.duplicate_of)
    return [
        i
        for i in facts.issues
        if i.state == "open" and i.key not in placed and not is_awaiting_live(i)
    ]


def classify(facts: Facts, judgements: Judgements) -> CheckResult:
    """Sort issues into their sets and report open PRs without a judgement."""
    judged = {normalize_key(k) for k in judgements.issues}
    found = {i.key: i for i in facts.issues}
    unranked = [
        i
        for i in facts.issues
        if i.state == "open" and i.key not in judged and not is_awaiting_live(i)
    ]
    unranked_prs = [
        pr for pr in facts.prs if pr.state == "OPEN" and issue_key(pr.repo, pr.number) not in judged
    ]
    settled = [found[k] for k in sorted(judged & found.keys()) if found[k].stage in SETTLED_STAGES]
    orphaned: list[str] = []
    unreachable: list[Unreachable] = []
    # A judgement may name a PR (open PRs are ranked under the same key); one the
    # facts carry is found, never orphaned or unreachable (gh#902).
    prs = [
        *facts.prs,
        *facts.batch_prs,
        *facts.judged_prs,
        *(p for i in facts.issues for p in i.prs),
    ]
    found_prs = {issue_key(p.repo, p.number) for p in prs}
    settled_prs = sorted(
        (
            p
            for p in facts.judged_prs
            if p.state != "OPEN" and issue_key(p.repo, p.number) in judged
        ),
        key=lambda p: issue_key(p.repo, p.number),
    )
    for key in sorted(judged - found.keys() - found_prs):
        reason = _unreachable_reason(key, facts)
        if reason is None:
            orphaned.append(key)
        else:
            unreachable.append(Unreachable(key=key, reason=reason))
    return CheckResult(
        unranked=unranked,
        unranked_prs=unranked_prs,
        settled=settled,
        orphaned=orphaned,
        unreachable=unreachable,
        stale=stale_dispatches(facts),
        unplaced=unplaced_issues(facts, judgements),
        no_severity=[
            i
            for i in facts.issues
            if i.state == "open" and i.key in judged and judgements.issues[i.key].severity is None
        ],
        duplicate_unknown=sorted(
            k
            for k, j in judgements.issues.items()
            if j.duplicate_of and j.duplicate_of not in found
        ),
        duplicate_chained=sorted(
            k
            for k, j in judgements.issues.items()
            if j.duplicate_of
            and (t := judgements.issues.get(j.duplicate_of)) is not None
            and t.duplicate_of
        ),
        settled_prs=settled_prs,
        awaiting_live=awaiting_live_issues(facts),
    )
