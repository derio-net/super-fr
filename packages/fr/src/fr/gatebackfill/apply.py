"""`fr gate backfill --yes`: apply the reviewed plan file to the forge (spec
2026-11-01-gate-backfill §F, §G; R6-R10, R15).

Forge writes go only through the `GhClient` the command obtained, one method per verb in
`_Writer`, which also owns the lazy label bookkeeping (#1268's rule: a label is ensured right
before the first write that uses it, never in a dry run). The engine reads the forge only for
the facts an idempotent write needs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fr.archive_followups import owned_owed_key
from fr.gatebackfill import trackers
from fr.gatebackfill.model import BackfillError, PlanEntry, PlanFile
from fr.ghclient import GhClient, UnsupportedForgeOperation
from fr.hostclient import FORGE_ERRORS, forge_error_kind
from fr.labels import FR_AWAITING_LIVE, FR_OWED, LabelDef, gate_label

OPEN_FIELDS = "number,title,body,labels,author"
OPEN_LIMIT = 500
_FAILURES: tuple[type[Exception], ...] = (*FORGE_ERRORS, UnsupportedForgeOperation)
_ISSUE_URL = re.compile(r"/(\d+)/?$")
_REF = re.compile(r"^(?P<repo>[\w.-]+/[\w.-]+)#(?P<n>\d+)$")


class ApplyRefusedError(BackfillError):
    """The plan cannot be applied at all: nothing was written."""


@dataclass
class EntryResult:
    key: str
    actions: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    """Informational lines; never a write, so `ApplyReport.writes` does not count them."""
    skipped: str | None = None
    error: str | None = None
    discharge: str | None = None

    def line(self) -> str:
        if self.error:
            return f"  {self.key}: FAILED: {self.error}"
        if self.skipped:
            return f"  {self.key}: skipped: {self.skipped}"
        if self.discharge:
            return f"  {self.key}: {self.discharge}"
        said = "; ".join([*self.actions, *self.notes])
        return f"  {self.key}: {said or 'nothing to do'}"


@dataclass
class ApplyReport:
    results: list[EntryResult] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.error)

    @property
    def writes(self) -> int:
        return sum(len(r.actions) for r in self.results)

    def lines(self) -> list[str]:
        return [*self.notes, *(r.line() for r in self.results)]


class _Writer:
    """Every forge write of an apply, with each label ensured once, just before first use."""

    def __init__(self, client: GhClient, repo: str) -> None:
        self.client, self.repo = client, repo
        self._ensured: set[str] = set()

    def _ensure(self, labels: list[LabelDef]) -> None:
        for lab in labels:
            if lab.name not in self._ensured:
                self.client.ensure_labels(self.repo, [lab])
                self._ensured.add(lab.name)

    def pr_label(self, pr: int, label: LabelDef) -> None:
        self._ensure([label])
        self.client.edit_pr_labels(self.repo, pr, add=frozenset({label.name}), remove=frozenset())

    def issue_labels(self, number: int, labels: list[LabelDef]) -> None:
        self._ensure(labels)
        self.client.edit_issue_labels(
            self.repo, number, add=frozenset(lab.name for lab in labels), remove=frozenset()
        )

    def create_issue(self, title: str, body: str, labels: list[LabelDef]) -> str:
        self._ensure(labels)
        url = self.client.create_issue(
            self.repo, title=title, body=body, labels=frozenset(lab.name for lab in labels)
        )
        m = _ISSUE_URL.search(str(url))
        if not m:
            raise BackfillError(f"the forge returned no issue reference ({url!r})")
        return f"{self.repo}#{m.group(1)}"

    def rewrite_body(self, number: int, body: str) -> None:
        self.client.edit_issue_body(self.repo, number, body)

    def comment(self, number: int, body: str) -> None:
        self.client.comment_issue(self.repo, number, body)

    def close(self, number: int, comment: str) -> None:
        self.client.close_issue(self.repo, number, comment)


def _names(issue: dict[str, Any]) -> set[str]:
    return {
        str(lab.get("name", "")) if isinstance(lab, dict) else str(lab)
        for lab in issue.get("labels") or []
    }


class _Apply:
    def __init__(
        self, root: Path, client: GhClient, repo: str, tracking: str, report: ApplyReport
    ) -> None:
        self.root, self.client, self.repo, self.tracking = root, client, repo, tracking
        self.report = report
        self.w = _Writer(client, repo)
        self.me = ""
        self.open: list[dict[str, Any]] = []
        self._runs: dict[str, list[str]] | None = None

    def run_for(self, head_ref: str) -> str | None:
        """The run naming *head_ref*; the cursors are read once per apply (p2-r8)."""
        if self._runs is None:
            self._runs = trackers.runs_by_head(self.root)
        return trackers.run_for_head(self.root, head_ref, index=self._runs)

    def read(self) -> None:
        """The facts every tracker decision needs; read before the first write."""
        if self.tracking == "none":
            return
        self.me = self.client.viewer_login()
        self.open = self.client.list_issues(self.repo, "open", OPEN_LIMIT, OPEN_FIELDS)
        if len(self.open) >= OPEN_LIMIT:
            raise ApplyRefusedError(
                f"{len(self.open)} open issues is the read cap: fr cannot be sure no tracker "
                "exists yet, and would file duplicates"
            )

    def owned_all(self, key: str) -> list[dict[str, Any]]:
        hits = [i for i in self.open if owned_owed_key(i, self.me) == key]
        return sorted(hits, key=lambda i: int(i["number"]))

    def owned(self, key: str) -> dict[str, Any] | None:
        hits = self.owned_all(key)
        return hits[0] if hits else None

    def _authored(self, comments: list[dict[str, Any]]) -> list[str]:
        return [str(c.get("body") or "") for c in comments if c.get("author") == self.me]

    # --- one entry -------------------------------------------------------------------------

    def entry(self, e: PlanEntry, fresh: PlanEntry | None) -> EntryResult | None:
        kind, adopt_ref = e.decision_kind, e.adopt_ref
        if kind not in ("owed", "adopt"):
            return None
        res = EntryResult(e.key)
        if fresh is None:
            res.skipped = "no longer owed (not a candidate any more)"
            return res
        if e.pr is None or e.gate is None:
            res.skipped = "no delivering PR" if e.pr is None else "no gate: set gate: in the plan"
            return res
        if fresh.pr is None or fresh.pr.number != e.pr.number:
            now = f"#{fresh.pr.number}" if fresh.pr else "none"
            res.skipped = f"delivering PR re-resolves to {now}, plan recorded #{e.pr.number}"
            return res
        if fresh.gate != e.computed_gate:
            res.skipped = f"gate re-resolves to {fresh.gate}, plan recorded {e.computed_gate}"
            return res
        try:
            self._apply(e, adopt_ref, res)
        except _FAILURES as exc:
            res.error = str(exc)
        except BackfillError as exc:
            res.error = str(exc)
        return res

    def _target(self, e: PlanEntry, ref: str) -> tuple[dict[str, Any] | None, str]:
        """`(open adopt target, why not)`; an fr-owned tracker is never one (R8, R15)."""
        m = _REF.match(ref)
        if m is None or m.group("repo").lower() != self.repo.lower():
            return None, f"adopt target {ref} is not in {self.repo}"
        n = int(m.group("n"))
        for i in self.open:
            if i.get("number") == n:
                if owned_owed_key(i, self.me) is not None:
                    return None, f"adopt target {ref} is an fr-owned tracker"
                return i, ""
        try:
            state = str(self.client.view_issue(self.repo, n).get("state") or "").upper()
        except _FAILURES as exc:
            if forge_error_kind(exc) != "info":
                raise  # only a not-found reads as "does not exist"; the rest is the entry's error
            return None, f"adopt target {ref} does not exist"
        if state == "CLOSED":
            return None, f"adopt target {ref} is closed"
        return None, f"adopt target {ref} is not among the open issues"

    def _apply(self, e: PlanEntry, adopt_ref: str | None, res: EntryResult) -> None:
        assert e.pr is not None and e.gate is not None
        pr, gate = e.pr.number, e.gate
        tracked = self.tracking != "none"
        issue_state = ""
        if tracked and e.issue is not None:
            issue_state = str(self.client.view_issue(self.repo, e.issue).get("state") or "").upper()
        target: dict[str, Any] | None = None
        existing = self.owned(e.key) if tracked else None
        if tracked and adopt_ref is not None:
            target, why = self._target(e, adopt_ref)
            if target is None:
                res.skipped = why
                return
        elif tracked and existing is not None:
            marker = trackers.fr_gate_marker(str(existing.get("body") or ""))
            if marker is not None and marker != (gate, pr):
                res.skipped = (
                    f"fr-owned tracker {self.repo}#{existing['number']} names gate:{marker[0]} "
                    f"pr:{marker[1]}, not gate:{gate} pr:{pr}; fix the plan entry's gate or "
                    "close the tracker, then re-run"
                )
                return
        own_open = tracked and adopt_ref is None and e.issue is not None and issue_state == "OPEN"
        own_open = own_open and e.key.startswith("issue:")
        if own_open:
            res.skipped = (
                f"{e.key} is itself open: adopt it (decision: adopt {e.key.removeprefix('issue:')})"
                " or give the manifest entry an issue:"
            )
            return
        view = self.client.pr_view(self.repo, pr)
        if str(view.get("state") or "") != "MERGED":
            res.skipped = f"PR #{pr} is {view.get('state') or 'unknown'}, not merged"
            return
        labels = {str(n) for n in view.get("labels") or []}
        if gate_label(gate, passed=True).name in labels:
            res.discharge = (
                f"PR #{pr} already passed {gate}; discharge the key itself:\n    "
                + trackers.discharge_command(e.key, repo_root=self.root).replace("\n", "\n    ")
            )
            return
        if gate_label(gate).name not in labels:
            self.w.pr_label(pr, gate_label(gate))
            res.actions.append(f"PR #{pr}: + {gate_label(gate).name}")
        if not tracked:
            return
        run_id = self.run_for(str(view.get("head_ref") or ""))
        extra = [FR_AWAITING_LIVE] if e.walk_only else []
        if target is not None:
            ref = self._adopt(e, target, pr, gate, run_id, extra, res)
        else:
            ref = self._own(e, existing, pr, gate, run_id, extra, res)
        if issue_state == "CLOSED" and e.issue is not None:
            self._link(e, ref, res)

    def _own(
        self, e: PlanEntry, existing: dict[str, Any] | None, pr: int, gate: str,
        run_id: str | None, extra: list[LabelDef], res: EntryResult,
    ) -> str:  # fmt: skip
        body = trackers.tracker_body(e.key, e.title or e.key, gate, pr, run_id=run_id)
        if existing is None:
            ref = self.w.create_issue(f"Owed: {e.title or e.key}", body, [FR_OWED, *extra])
            res.actions.append(f"filed tracker {ref}")
            return ref
        n = int(existing["number"])
        ref = f"{self.repo}#{n}"
        if trackers.fr_gate_marker(str(existing.get("body") or "")) is None:
            self.w.rewrite_body(n, body)
            res.actions.append(f"rewrote tracker {ref}")
        missing = [lab for lab in extra if lab.name not in _names(existing)]
        if missing:
            self.w.issue_labels(n, missing)
            res.actions.append(f"{ref}: + {', '.join(lab.name for lab in missing)}")
        return ref

    def _adopt(
        self, e: PlanEntry, target: dict[str, Any], pr: int, gate: str,
        run_id: str | None, extra: list[LabelDef], res: EntryResult,
    ) -> str:  # fmt: skip
        n = int(target["number"])
        ref = f"{self.repo}#{n}"
        want = (e.key, gate, pr)
        comments = self.client.list_issue_comments(self.repo, n)
        if not any(trackers.fr_adopt_marker(b) == want for b in self._authored(comments)):
            self.w.comment(n, trackers.adopt_comment(e.key, gate, pr, run_id=run_id))
            res.actions.append(f"commented on {ref}")
        missing = [lab for lab in [FR_OWED, *extra] if lab.name not in _names(target)]
        if missing:
            self.w.issue_labels(n, missing)
            res.actions.append(f"{ref}: + {', '.join(lab.name for lab in missing)}")
        for dup in self.owned_all(e.key):
            if dup.get("number") != n:
                self.w.close(int(dup["number"]), f"Duplicate of {ref}; tracking moved there.")
                res.actions.append(f"closed duplicate {self.repo}#{dup['number']}")
        return ref

    def _link(self, e: PlanEntry, ref: str, res: EntryResult) -> None:
        assert e.issue is not None
        if ref == f"{self.repo}#{e.issue}":
            return
        marker = trackers.link_marker(e.key, ref)
        comments = self.client.list_issue_comments(self.repo, e.issue)
        if any(b.rstrip().endswith(marker) for b in self._authored(comments)):
            return
        self.w.comment(e.issue, trackers.link_comment(e.key, ref))
        res.actions.append(f"linked closed issue #{e.issue} to {ref}")


def apply_plan(
    repo_root: Path,
    plan: PlanFile | None,
    candidates: list[PlanEntry],
    client: GhClient,
    *,
    repo: str,
    tracking: str,
) -> ApplyReport:
    """Apply *plan*'s `owed` / `adopt` decisions. *candidates* are the entries re-resolved NOW
    (delivering PR and gate); what is applied is what the plan recorded, and an entry whose
    re-resolution differs is skipped. Raises `ApplyRefusedError` before any write when the plan is
    missing or names another repo; a forge error is recorded on its entry and the rest go on."""
    if plan is None:
        raise ApplyRefusedError("no plan file: run the dry run first and review it")
    if plan.repo.lower() != repo.lower():
        raise ApplyRefusedError(f"the plan file names {plan.repo}, not {repo}")
    report = ApplyReport()
    run = _Apply(repo_root, client, repo, tracking, report)
    try:
        run.read()
    except _FAILURES as exc:
        raise ApplyRefusedError(f"cannot read the forge: {exc}") from exc
    fresh = {c.key: c for c in candidates}
    seen: set[str] = set()
    for e in sorted(plan.entries, key=lambda x: x.key):
        if e.key in seen:
            continue
        seen.add(e.key)
        res = run.entry(e, fresh.get(e.key))
        if res is not None:
            report.results.append(res)
    for key in sorted(set(fresh) - {e.key for e in plan.entries}):
        report.notes.append(
            f"  {key}: a new candidate, not in the plan: dry-run again to decide it"
        )
    return report
