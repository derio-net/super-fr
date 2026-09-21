"""`check` — the four sets that make triage debt visible (spec §3.F).

Pure: facts and judgements in, sets out. The command only formats them.

- **unranked** — an open issue with no judgement;
- **settled** — judged, and now `closed` or `merged`;
- **orphaned** — a judgement whose issue collect could not find at all;
- **unreachable** — a judgement whose issue the forge would not show
  (`Facts.unviewed`) or whose repo was `Facts.skipped`. Never orphaned: pruning
  a judgement over a transient failure would destroy the ranking
  (review r-p2-check-sets).

Every key comparison goes through `fr.triage.model.normalize_key` (or
`issue_key`, which is built on it). There is no second normaliser here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fr.triage.model import Facts, Issue, Judgements, issue_key, normalize_key

SETTLED_STAGES = frozenset({"closed", "merged"})


@dataclass(frozen=True)
class Unreachable:
    key: str
    reason: str


@dataclass(frozen=True)
class CheckResult:
    unranked: list[Issue]
    settled: list[Issue]
    orphaned: list[str]
    unreachable: list[Unreachable]

    def to_json(self) -> dict[str, Any]:
        def row(i: Issue) -> dict[str, Any]:
            return {"key": i.key, "title": i.title, "stage": i.stage, "url": i.url}

        return {
            "unranked": [row(i) for i in self.unranked],
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
    return None


def classify(facts: Facts, judgements: Judgements) -> CheckResult:
    """Sort every issue and judgement into the four sets (spec §3.F)."""
    judged = {normalize_key(k) for k in judgements.issues}
    found = {i.key: i for i in facts.issues}
    unranked = [i for i in facts.issues if i.state == "open" and i.key not in judged]
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
        unranked=unranked, settled=settled, orphaned=orphaned, unreachable=unreachable
    )
