from __future__ import annotations

import json

import pytest
from fr.triage.collect import collect_facts
from fr.triage.errors import ForgeError, TriageError
from fr.triage.model import Scope, load_facts

from tests.unit.triage_fixtures import NOW, FakeForge

SCOPE = Scope(kind="repo", target="example.com/repo")


def _pr(
    number: int,
    *,
    checks: list[dict] | None = None,
    refs: list[dict] | None = None,
    mergeable: str = "MERGEABLE",
) -> dict:
    return {
        "number": number,
        "title": f"PR {number}",
        "state": "OPEN",
        "isDraft": False,
        "mergedAt": None,
        "url": f"https://example.com/pr/{number}",
        "headRefName": "topic",
        "closingIssuesReferences": refs or [],
        "files": [],
        "statusCheckRollup": checks or [],
        "mergeable": mergeable,
        "mergeStateStatus": "CLEAN",
        "reviewDecision": "APPROVED",
    }


def test_open_prs_use_a_separate_bulk_call_and_reduce_checks() -> None:
    linked = {"repository": {"owner": {"login": "example.com"}, "name": "repo"}, "number": 7}
    forge = FakeForge(
        issues={"example.com/repo": [{"number": 7, "title": "issue", "labels": [], "url": "u"}]},
        prs={
            "example.com/repo": [
                _pr(
                    1, checks=[{"conclusion": "SUCCESS"}, {"conclusion": "FAILURE"}], refs=[linked]
                ),
                _pr(2, checks=[{"conclusion": "PENDING"}], mergeable="UNKNOWN"),
            ]
        },
    )
    facts = collect_facts(forge, SCOPE, now=NOW)
    assert forge.called("list_prs") == [{"repo": "example.com/repo", "state": "all", "limit": 200}]
    assert forge.called("list_open_prs") == [{"repo": "example.com/repo", "limit": 200}]
    assert facts.issues[0].prs[0].number == 1
    assert [p.number for p in facts.prs] == [2]
    assert facts.prs[0].checks == {"pass": 0, "fail": 0, "pending": 1}
    assert facts.prs[0].mergeable == "UNKNOWN"


def test_schema_one_facts_are_refused_with_collect_remedy(tmp_path) -> None:
    path = tmp_path / "facts.json"
    path.write_text(json.dumps({"schema": 1}), encoding="utf-8")
    with pytest.raises(TriageError, match=r"facts\.json.*re-run collect"):
        load_facts(path)


def test_captured_open_pr_shape_parses_with_summary_and_unknown_merge() -> None:
    from pathlib import Path

    from fr.triage.collect import parse_prs

    fixture = (
        Path(__file__).resolve().parent.parent / "fixtures" / "triage" / "super-fr-open-prs.json"
    )
    raw = json.loads(fixture.read_text(encoding="utf-8"))
    ((pr, refs),) = parse_prs("derio-net/super-fr", raw)

    assert pr.state == "OPEN"
    assert pr.checks == {"pass": len(raw[0]["statusCheckRollup"]), "fail": 0, "pending": 0}
    assert pr.mergeable == raw[0]["mergeable"]
    assert pr.merge_state == raw[0]["mergeStateStatus"]
    assert pr.review is None  # captured reviewDecision is "" (no review)
    assert refs == []


def test_same_pr_number_in_two_repos_dedupes_per_repo() -> None:
    org = Scope(kind="org", target="example.com")
    linked = {"repository": {"owner": {"login": "example.com"}, "name": "alpha"}, "number": 9}
    forge = FakeForge(
        issues={
            "example.com/alpha": [{"number": 9, "title": "issue", "labels": [], "url": "u"}],
            "example.com/beta": [],
        },
        prs={
            "example.com/alpha": [_pr(5, refs=[linked])],
            "example.com/beta": [_pr(5)],
        },
        repos=[{"name": "alpha", "isArchived": False}, {"name": "beta", "isArchived": False}],
    )
    facts = collect_facts(forge, org, now=NOW)

    assert [(p.repo, p.number) for p in facts.prs] == [("example.com/beta", 5)]


def test_open_pr_anchor_uses_spec_before_debug_and_reads_its_head_body() -> None:
    pr = _pr(2)
    pr["headRefName"] = "feature/spec"
    pr["files"] = [
        {"path": "docs/superpowers/journals/debug/incident.md"},
        {"path": "docs/superpowers/specs/intent.md"},
    ]
    forge = FakeForge(
        issues={"example.com/repo": []},
        prs={"example.com/repo": [pr]},
        file_bodies={
            ("example.com/repo", "docs/superpowers/specs/intent.md", "feature/spec"): "intent"
        },
    )

    got = collect_facts(forge, SCOPE, now=NOW).prs[0]

    assert (got.anchor, got.anchor_path, got.anchor_body, got.anchor_reason) == (
        "spec",
        "docs/superpowers/specs/intent.md",
        "intent",
        None,
    )
    assert forge.called("read_file_at_ref") == [
        {
            "repo": "example.com/repo",
            "path": "docs/superpowers/specs/intent.md",
            "ref": "feature/spec",
        }
    ]


def test_open_pr_anchor_accepts_debug_journal_and_plan_meta_spec_ref() -> None:
    debug = _pr(2)
    debug["files"] = [{"path": "docs/superpowers/journals/debug/incident.md"}]
    meta = _pr(3)
    meta["files"] = [{"path": "docs/superpowers/plans/intent/_meta.yaml"}]
    forge = FakeForge(
        issues={"example.com/repo": []},
        prs={"example.com/repo": [debug, meta]},
        file_bodies={
            ("example.com/repo", "docs/superpowers/journals/debug/incident.md", "topic"): "symptom",
            (
                "example.com/repo",
                "docs/superpowers/plans/intent/_meta.yaml",
                "topic",
            ): "spec: docs/superpowers/specs/intent.md\n",
        },
    )

    prs = collect_facts(forge, SCOPE, now=NOW).prs

    assert [(p.anchor, p.anchor_path) for p in prs] == [
        ("debug", "docs/superpowers/journals/debug/incident.md"),
        ("spec", "docs/superpowers/specs/intent.md"),
    ]


def test_open_pr_anchor_is_unanchored_without_a_matching_file_or_after_forge_error() -> None:
    none = _pr(2)
    none["files"] = [{"path": "src/engine.py"}]
    broken = _pr(3)
    broken["files"] = [{"path": "docs/superpowers/specs/intent.md"}]
    forge = FakeForge(
        issues={"example.com/repo": []},
        prs={"example.com/repo": [none, broken]},
        file_bodies={
            ("example.com/repo", "docs/superpowers/specs/intent.md", "topic"): ForgeError(
                "HTTP 502"
            )
        },
    )

    prs = collect_facts(forge, SCOPE, now=NOW).prs

    assert [(p.anchor, p.anchor_reason) for p in prs] == [
        ("unanchored", "no matching intent file"),
        ("unanchored", "HTTP 502"),
    ]
    assert forge.called("read_file_at_ref") == [
        {"repo": "example.com/repo", "path": "docs/superpowers/specs/intent.md", "ref": "topic"}
    ]


def test_open_pr_anchor_body_is_capped_and_cross_repo_closing_ref_is_not_an_anchor() -> None:
    pr = _pr(2, refs=[{"repository": {"owner": {"login": "other"}, "name": "repo"}, "number": 8}])
    pr["files"] = [{"path": "docs/superpowers/specs/intent.md"}]
    forge = FakeForge(
        issues={"example.com/repo": []},
        prs={"example.com/repo": [pr]},
        file_bodies={("example.com/repo", "docs/superpowers/specs/intent.md", "topic"): "x" * 2001},
    )

    got = collect_facts(forge, SCOPE, now=NOW).prs[0]

    assert got.anchor == "spec"
    assert len(got.anchor_body) == 2000


def test_closing_issue_anchor_wins_before_file_anchors() -> None:
    pr = _pr(
        2,
        refs=[{"repository": {"owner": {"login": "example.com"}, "name": "repo"}, "number": 8}],
    )
    pr["files"] = [{"path": "docs/superpowers/specs/intent.md"}]
    forge = FakeForge(
        issues={"example.com/repo": [{"number": 8, "title": "issue", "labels": [], "url": "u"}]},
        prs={"example.com/repo": [pr]},
    )

    facts = collect_facts(forge, SCOPE, now=NOW)

    assert facts.prs == []
    assert facts.issues[0].prs[0].anchor == "issue"
    assert forge.called("read_file_at_ref") == []
