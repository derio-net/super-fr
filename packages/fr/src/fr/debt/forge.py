"""A `DebtForge` over the `GhClient` adapter (spec 2026-10-11-debt-engine §A).

Reads only. A forge that cannot do an operation raises the adapter's own
unsupported error, which `compute` reports as the forge being unavailable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fr.debt.engine import PartialIssuesError
from fr.ghclient import GhClient

OWED_LABELS = ("fr:owed", "fr:awaiting-live")
ISSUE_FIELDS = "number,title,body,labels"
ISSUE_LIMIT = 200


def _label_names(issue: dict[str, Any]) -> list[str]:
    out = []
    for lab in issue.get("labels") or []:
        out.append(str(lab.get("name", "")) if isinstance(lab, dict) else str(lab))
    return out


class ClientDebtForge:
    def __init__(self, client: GhClient, *, cwd: Path, repo: str) -> None:
        self._client = client
        self._cwd = cwd
        self._repo = repo

    def pr_for_branch(self, branch: str) -> dict[str, Any] | None:
        return self._client.pr_for_branch(branch, cwd=self._cwd)

    def owed_issues(self) -> list[dict[str, Any]]:
        raw = self._client.list_issues(self._repo, "open", ISSUE_LIMIT, ISSUE_FIELDS)
        out = []
        for i in raw:
            labels = _label_names(i)
            if any(lab in OWED_LABELS for lab in labels):
                out.append(
                    {
                        "ref": f"{self._repo}#{i.get('number')}",
                        "title": i.get("title", ""),
                        "body": i.get("body") or "",
                        "labels": labels,
                    }
                )
        if len(raw) >= ISSUE_LIMIT:
            raise PartialIssuesError(
                out,
                f"partial: only the first {ISSUE_LIMIT} open issues were scanned for owed labels",
            )
        return out
