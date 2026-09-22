"""`check` — the issue sets plus unranked PRs that make triage debt visible (spec §3.F).

Pure: facts and judgements in, sets out. The command only formats them.

- **unranked** — an open issue with no judgement;
- **settled** — judged, and now `closed` or `merged`;
- **orphaned** — a judgement whose key names no repo collect read: a typo'd or
  renamed repo, or one outside the scope. That is the ONLY meaning, so it is the
  only set whose members are safe to fix or remove without asking the forge again;
- **unreachable** — a judgement collect could not settle either way: the forge
  would not show its issue (`Facts.unviewed`, whose reason may say the issue does
  not exist — a deleted issue or a typo'd number), its repo was `Facts.skipped`,
  or its key names a collected repo but was added after the last collect. Never
  orphaned: pruning a judgement over a transient failure, or over stale facts,
  would destroy the ranking (reviews r-p2-check-sets, phase-4 C1/C2).

Every key comparison goes through `fr.triage.model.normalize_key` (or
`issue_key`, which is built on it). There is no second normaliser here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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
class CheckResult:
    unranked: list[Issue]
    unranked_prs: list[PullRequest]
    settled: list[Issue]
    orphaned: list[str]
    unreachable: list[Unreachable]

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
            "orphaned": list(self.orphaned),
            "unreachable": [{"key": u.key, "reason": u.reason} for u in self.unreachable],
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


def classify(facts: Facts, judgements: Judgements) -> CheckResult:
    """Sort issues into their four sets and report open PRs without a judgement."""
    judged = {normalize_key(k) for k in judgements.issues}
    found = {i.key: i for i in facts.issues}
    unranked = [i for i in facts.issues if i.state == "open" and i.key not in judged]
    unranked_prs = [
        pr for pr in facts.prs if pr.state == "OPEN" and issue_key(pr.repo, pr.number) not in judged
    ]
    settled = [found[k] for k in sorted(judged & found.keys()) if found[k].stage in SETTLED_STAGES]
    orphaned: list[str] = []
    unreachable: list[Unreachable] = []
    for key in sorted(judged - found.keys()):
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
    )
