"""The `labels` filter through the forge chain, and facts schema 9 (board-truth §B, R2)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fr import gh as _gh
from fr.ghclient import UnsupportedForgeOperation
from fr.real_ghclient import ORIGINS_ISSUE_LIST_FIELDS, RealGhClient
from fr.real_ghrestclient import RealGhRestClient
from fr.real_glabclient import RealGlabClient
from fr.real_teaclient import RealTeaClient
from fr.triage.collect import ClientForge
from fr.triage.model import FACTS_READS, FACTS_SCHEMA, Facts, StaleInProgress, load_facts

from tests.unit.github_rest_support import REPO, R, parse_api


def test_gh_issue_list_passes_each_label_and_the_origins_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[list[str]] = []
    monkeypatch.setattr(_gh, "_rest", lambda: None)
    monkeypatch.setattr(_gh, "_run_gh", lambda args: seen.append(args) or "[]")
    _gh.list_issues(
        repo="o/r",
        state="closed",
        limit=5,
        fields=ORIGINS_ISSUE_LIST_FIELDS,
        labels=["fr:in-progress"],
    )
    (argv,) = seen
    assert argv[argv.index("--label") + 1] == "fr:in-progress"
    assert "closedAt" in argv[argv.index("--json") + 1].split(",")


def test_gh_issue_list_without_labels_has_no_label_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[list[str]] = []
    monkeypatch.setattr(_gh, "_rest", lambda: None)
    monkeypatch.setattr(_gh, "_run_gh", lambda args: seen.append(args) or "[]")
    _gh.list_issues(repo="o/r", state="open", limit=5)
    assert "--label" not in seen[0]


def test_rest_issue_route_carries_the_url_encoded_labels() -> None:
    routes: list[str] = []

    def run(argv: list[str]) -> str:
        routes.append(parse_api(argv)[2])
        return "[]"

    RealGhRestClient(run=run).list_issues(REPO, "closed", 5, labels=["fr:in-progress"])
    assert routes == [f"{R}/issues?state=closed&labels=fr%3Ain-progress&per_page=100&page=1"]


class _Spy:
    def __init__(self) -> None:
        self.kw: dict[str, Any] = {}

    def list_issues(
        self, repo: str, state: str, limit: int, fields: str | None = None, labels: Any = None
    ) -> list[dict[str, Any]]:
        self.kw = {"repo": repo, "state": state, "limit": limit, "fields": fields, "labels": labels}
        return []


def test_client_forge_passes_labels_through() -> None:
    spy = _Spy()
    ClientForge(spy).list_issues(  # type: ignore[arg-type]
        repo="o/r", state="closed", limit=3, fields="number", labels=["fr:in-progress"]
    )
    assert spy.kw["labels"] == ["fr:in-progress"]


def test_real_gh_client_hands_labels_to_gh(monkeypatch: pytest.MonkeyPatch) -> None:
    got: dict[str, Any] = {}
    monkeypatch.setattr(_gh, "list_issues", lambda **kw: got.update(kw) or [])
    RealGhClient().list_issues("o/r", "closed", 4, labels=["fr:in-progress"])
    assert got["labels"] == ["fr:in-progress"]


@pytest.mark.parametrize("client", [RealGlabClient, RealTeaClient])
def test_glab_and_tea_still_refuse_the_issue_list(client: Any) -> None:
    with pytest.raises(UnsupportedForgeOperation):
        client().list_issues("o/r", "closed", 4, labels=["fr:in-progress"])


def _doc(**extra: Any) -> dict[str, Any]:
    return {
        "scope": "derio-net--super-fr",
        "kind": "repo",
        "collected_at": "2026-10-12T00:00:00Z",
        "repos": ["derio-net/super-fr"],
        "issues": [],
        **extra,
    }


def test_schema_9_round_trips_stale_in_progress_and_config_ignored(tmp_path: Path) -> None:
    assert FACTS_SCHEMA == 13 and FACTS_READS == (3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13)
    facts = Facts(
        schema=FACTS_SCHEMA,
        **_doc(),
        stale_in_progress=[
            StaleInProgress(
                key="super-fr#7",
                title="t",
                url="https://github.com/derio-net/super-fr/issues/7",
                closed_at="2026-10-01T00:00:00Z",
                state="stale",
            )
        ],
        config_ignored={"derio-net/super-fr": ["nonsense"]},
    )
    path = tmp_path / "facts.json"
    path.write_text(json.dumps(facts.to_json()), encoding="utf-8")
    assert json.loads(path.read_text())["schema"] == 13
    assert load_facts(path) == facts


def test_a_schema_8_file_reads_with_both_fields_empty(tmp_path: Path) -> None:
    path = tmp_path / "facts.json"
    path.write_text(json.dumps({"schema": 8, **_doc()}), encoding="utf-8")
    facts = load_facts(path)
    assert facts.stale_in_progress == [] and facts.config_ignored == {}
