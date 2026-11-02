"""`GhClient.list_merged_prs_by_label` (spec 2026-11-01-gate-backfill §I, R13): the merged
PRs of a repo carrying one label, as `PR_LIST_FIELDS` plus `labels`."""

from __future__ import annotations

import json
from typing import Any

import pytest
from fr import gh
from fr.ghclient import UnsupportedForgeOperation
from fr.hostclient import client_for_backend
from fr.real_ghrestclient import RealGhRestClient
from fr.triage.errors import ForgeError

REPO = "example-org/alpha"


def test_the_cli_path_asks_for_merged_prs_with_the_label_and_the_list_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[list[str]] = []

    def fake(args: list[str]) -> str:
        seen.append(args)
        return json.dumps([{"number": 3}])

    monkeypatch.setattr(gh, "_run_gh", fake)
    got = gh.list_merged_prs_by_label(repo=REPO, label="gate:tester", limit=40)
    assert got == [{"number": 3}]
    assert seen == [
        [
            *("pr", "list", "--repo", REPO, "--state", "merged"),
            *("--label", "gate:tester", "--limit", "40"),
            *("--json", gh.PR_LIST_FIELDS + ",labels"),
        ]
    ]


def _issue(number: int, merged: bool, labels: list[str]) -> dict[str, Any]:
    return {
        "number": number,
        "title": f"PR {number}",
        "state": "closed",
        "created_at": "2026-10-01T00:00:00Z",
        "html_url": f"https://github.com/{REPO}/pull/{number}",
        "user": {"login": "operator"},
        "labels": [{"name": n} for n in labels],
        "pull_request": {"merged_at": "2026-10-02T00:00:00Z" if merged else None},
    }


def test_the_rest_path_keeps_only_merged_pulls_of_the_issues_route() -> None:
    calls: list[list[str]] = []
    answers = [
        _issue(1, True, ["gate:tester"]),
        _issue(2, False, ["gate:tester"]),  # closed unmerged
        {**_issue(3, True, ["gate:tester"]), "pull_request": None},  # a plain issue
    ]

    def run(argv: list[str]) -> str:
        calls.append(argv)
        return json.dumps(answers)

    client = RealGhRestClient(run=run)
    got = client.list_merged_prs_by_label(REPO, "gate:tester", 10)
    assert [p["number"] for p in got] == [1]
    assert got[0]["state"] == "MERGED"
    assert got[0]["url"] == f"https://github.com/{REPO}/pull/1"
    assert got[0]["labels"] == [{"name": "gate:tester"}]
    assert got[0]["closingIssuesReferences"] == []
    assert "labels=gate%3Atester" in calls[0][1] and "state=closed" in calls[0][1]
    assert all(a[0] == "api" for a in calls)


@pytest.mark.parametrize("backend", ["gitlab", "gitea"])
def test_glab_and_tea_raise_unsupported(backend: str) -> None:
    client = client_for_backend(backend)  # type: ignore[arg-type]
    with pytest.raises(UnsupportedForgeOperation):
        client.list_merged_prs_by_label(REPO, "gate:tester", 5)


def test_client_forge_maps_the_failure_to_a_forge_error() -> None:
    from fr.triage.collect import ClientForge

    forge = ClientForge(client_for_backend("gitlab"))  # type: ignore[arg-type]
    with pytest.raises(ForgeError, match="list_merged_prs_by_label"):
        forge.list_merged_prs_by_label(repo=REPO, label="gate:tester", limit=5)
