"""`ClientDebtForge` over a fake client (spec 2026-10-11-debt-engine §A)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fr.debt.engine import PartialIssuesError
from fr.debt.forge import ISSUE_LIMIT, ClientDebtForge


class FakeClient:
    def __init__(self, issues: list[dict[str, Any]], pr: dict[str, Any] | None = None) -> None:
        self.issues = issues
        self.pr = pr
        self.calls: list[Any] = []

    def list_issues(self, repo: str, state: str, limit: int, fields: str | None = None) -> Any:
        self.calls.append((repo, state, limit, fields))
        return self.issues

    def pr_for_branch(self, branch: str, *, cwd: Path) -> dict[str, Any] | None:
        self.calls.append(("pr", branch, cwd))
        return self.pr


def _forge(client: FakeClient) -> ClientDebtForge:
    return ClientDebtForge(client, cwd=Path("/x"), repo="o/r")  # type: ignore[arg-type]


def test_only_owed_labelled_issues_are_kept_with_a_qualified_ref() -> None:
    client = FakeClient(
        [
            {"number": 1, "title": "a", "body": "b", "labels": [{"name": "fr:owed"}]},
            {"number": 2, "title": "c", "body": None, "labels": ["fr:awaiting-live"]},
            {"number": 3, "title": "d", "body": "x", "labels": [{"name": "bug"}]},
            {"number": 4, "title": "e", "body": "x"},
        ]
    )
    got = _forge(client).owed_issues()
    assert [(i["ref"], i["body"], i["labels"]) for i in got] == [
        ("o/r#1", "b", ["fr:owed"]),
        ("o/r#2", "", ["fr:awaiting-live"]),
    ]
    assert client.calls[0][:2] == ("o/r", "open")


def test_a_full_page_is_reported_partial_with_what_was_read() -> None:
    issues = [
        {"number": n, "title": "t", "body": "", "labels": [{"name": "fr:owed"}]}
        for n in range(ISSUE_LIMIT)
    ]
    with pytest.raises(PartialIssuesError) as e:
        _forge(FakeClient(issues)).owed_issues()
    assert len(e.value.items) == ISSUE_LIMIT and "partial" in str(e.value)


def test_pr_for_branch_passes_the_checkout_directory() -> None:
    client = FakeClient([], pr={"state": "OPEN", "updatedAt": "t"})
    assert _forge(client).pr_for_branch("feat/x") == {"state": "OPEN", "updatedAt": "t"}
    assert client.calls == [("pr", "feat/x", Path("/x"))]
