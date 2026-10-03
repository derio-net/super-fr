"""A fixture of fifteen issues for the defect-origins tests (wave-driver R10).

Fictional owner and repo (`example-org/widgets`). The raw rows are `gh` shaped; the
expected figures are worked out BY HAND in `test_triage_origins.py`, never by the code
under test. Columns: number, created, closed (None = open), reason, category, source,
related PR.
"""

# ruff: noqa: E501
from __future__ import annotations

from typing import Any

REPO = "example-org/widgets"
SINCE = "2026-09-01"

# (n, created, closed, state reason, category, source, pr)
ROWS: list[tuple[int, str, str | None, str, str, str, str | None]] = [
    (1, "2026-09-01T08:00:00Z", "2026-09-01T14:00:00Z", "COMPLETED", "latent", "pipeline", None),
    (2, "2026-09-01T10:00:00Z", "2026-09-02T10:00:00Z", "COMPLETED", "regression", "pipeline", "example-org/widgets#101"),
    (3, "2026-09-01T12:00:00Z", None, "", "new-feature", "recording", "example-org/widgets#102"),
    (4, "2026-09-02T09:00:00Z", "2026-09-02T11:00:00Z", "COMPLETED", "leftover", "pipeline", "example-org/widgets#102"),
    (5, "2026-09-02T15:00:00Z", "2026-09-04T15:00:00Z", "COMPLETED", "gap", "hand", None),
    (6, "2026-09-02T16:00:00Z", "2026-09-02T17:00:00Z", "NOT_PLANNED", "duplicate", "hand", None),
    (7, "2026-09-04T08:00:00Z", "2026-09-04T20:00:00Z", "COMPLETED", "new-feature", "pipeline", "example-org/widgets#103"),
    (8, "2026-09-04T09:00:00Z", None, "", "leftover", "recording", "example-org/widgets#103"),
    (9, "2026-09-04T10:00:00Z", "2026-09-05T10:00:00Z", "COMPLETED", "latent", "hand", None),
    (10, "2026-09-05T07:00:00Z", "2026-09-05T10:00:00Z", "COMPLETED", "regression", "pipeline", "example-org/widgets#101"),
    (11, "2026-09-05T08:00:00Z", None, "", "new-feature", "pipeline", "example-org/widgets#102"),
    (12, "2026-09-05T09:00:00Z", "2026-09-06T09:00:00Z", "COMPLETED", "leftover", "pipeline", "example-org/widgets#103"),
    (13, "2026-09-05T10:00:00Z", None, "", "gap", "recording", None),
    (14, "2026-09-05T11:00:00Z", "2026-09-05T12:00:00Z", "NOT_PLANNED", "duplicate", "pipeline", None),
    (15, "2026-09-05T12:00:00Z", "2026-09-05T18:00:00Z", "COMPLETED", "latent", "hand", None),
]  # fmt: skip


def raw_issue(n: int, created: str, closed: str | None, reason: str) -> dict[str, Any]:
    return {
        "number": n,
        "title": f"Widget defect {n}",
        "labels": [{"name": "bug"}],
        "createdAt": created,
        "url": f"https://github.com/{REPO}/issues/{n}",
        "body": "",
        "state": "CLOSED" if closed else "OPEN",
        "closedAt": closed,
        "stateReason": reason,
    }


def raw_pr(n: int, merged: bool, closes: list[int]) -> dict[str, Any]:
    return {
        "number": n,
        "title": f"Widget change {n}",
        "state": "MERGED" if merged else "CLOSED",
        "isDraft": False,
        "createdAt": "2026-09-01T00:00:00Z",
        "mergedAt": "2026-09-01T01:00:00Z" if merged else None,
        "url": f"https://github.com/{REPO}/pull/{n}",
        "headRefName": f"feat/change-{n}",
        "closingIssuesReferences": [
            {"number": c, "repository": {"name": "widgets", "owner": {"login": "example-org"}}}
            for c in closes
        ],
    }


class OriginsForge:
    """Serves the fifteen issues plus one filed before the window, and three PRs."""

    def __init__(self) -> None:
        self.issues = [raw_issue(n, c, cl, r) for n, c, cl, r, *_ in ROWS]
        self.issues.append(raw_issue(99, "2026-08-31T23:00:00Z", None, ""))  # before SINCE
        self.prs = [
            raw_pr(301, True, [1]),
            raw_pr(302, True, [2, 10]),
            raw_pr(303, False, [4]),  # closed unmerged: never "closed it"
        ]
        self.calls: list[tuple[str, str]] = []

    def list_repos(self, *, owner: str, limit: int) -> list[dict[str, Any]]:
        return [{"name": "widgets", "isArchived": False}]

    def list_issues(
        self, *, repo: str, state: str, limit: int, fields: str | None = None
    ) -> list[dict[str, Any]]:
        self.calls.append(("list_issues", state))
        return self.issues

    def list_prs(self, *, repo: str, state: str, limit: int) -> list[dict[str, Any]]:
        self.calls.append(("list_prs", state))
        return self.prs


def classification_yaml(*, skip: tuple[int, ...] = (), extra: str = "", causes: str = "") -> str:
    lines = ["schema: 1", "issues:"]
    for n, _c, _cl, _r, cat, src, pr in ROWS:
        if n in skip:
            continue
        lines += [
            f"  widgets#{n}:",
            f"    category: {cat}",
            f"    source: {src}",
            "    severity: med",
            f"    reason: reason for {n}",
        ]
        if pr:
            lines.append(f"    pr: {pr}")
    return "\n".join(lines) + "\n" + extra + causes
