"""The approval gate's facts, events and pure verdict (spec 2026-10-11-merge-train-safety
§A "Facts and the label", "The verdict", §B; R1, R2, R8).

Everything here is pure: facts, judgements and events are built in memory.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fr.labels import APPROVED_FR
from fr.triage.approval import (
    Approved,
    First,
    Unlabelled,
    Void,
    approval_verdict,
)
from fr.triage.model import (
    FACTS_READS,
    FACTS_SCHEMA,
    JUDGEMENTS_READS,
    JUDGEMENTS_SCHEMA,
    SCHEMA_9_EVENTS,
    ApprovalEvent,
    EnqueueEvent,
    Judgements,
    PullRequest,
    RedHandbackEvent,
    UpdateEvent,
    load_facts,
)
from pydantic import ValidationError

T0 = datetime(2026, 10, 11, 12, 0, tzinfo=UTC)


def _at(minutes: int) -> datetime:
    return T0 + timedelta(minutes=minutes)


def _approval(pr: int, head: str, *, voided_at: str | None = None, at: int = 0) -> ApprovalEvent:
    return ApprovalEvent(kind="approval", at=_at(at), pr=pr, head=head, voided_at=voided_at)


def _update(pr: int, before: str, after: str, *, base: str = "b0", at: int = 1) -> UpdateEvent:
    return UpdateEvent(
        kind="update", at=_at(at), pr=pr, head_before=before, head_after=after, base=base
    )


LABELS = [APPROVED_FR.name]


# ------------------------------------------------------------------ the label


def test_the_approval_label_is_green_and_names_its_purpose() -> None:
    assert APPROVED_FR.name == "approved-fr"
    assert APPROVED_FR.color == "0E8A16"
    assert "approval" in APPROVED_FR.description.lower()


# ------------------------------------------------------------------ facts


def test_a_pull_request_never_read_for_labels_carries_none() -> None:
    pr = PullRequest(repo="o/r", number=1, title="t", state="OPEN", is_draft=False, url="u")
    assert pr.labels is None
    assert PullRequest(**{**pr.model_dump(), "labels": ["x"]}).labels == ["x"]


def test_facts_schema_is_10_and_reads_3_to_10() -> None:
    assert FACTS_SCHEMA == 12
    assert FACTS_READS == (3, 4, 5, 6, 7, 8, 9, 10, 11, 12)


def test_a_schema_8_facts_file_reads_labels_as_none(tmp_path: Path) -> None:
    doc: dict[str, Any] = {
        "schema": 8,
        "scope": "o/r",
        "kind": "repo",
        "collected_at": "2026-10-11T12:00:00Z",
        "repos": ["o/r"],
        "issues": [],
        "batch_prs": [
            {
                "repo": "o/r",
                "number": 4,
                "title": "t",
                "state": "OPEN",
                "is_draft": True,
                "url": "u",
                "head_oid": "abc",
            }
        ],
    }
    path = tmp_path / "facts.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    facts = load_facts(path)
    assert facts.schema_ == 8
    assert facts.batch_prs[0].labels is None


# ------------------------------------------------------------------ events


def test_judgements_schema_is_9_and_reads_1_to_9() -> None:
    assert JUDGEMENTS_SCHEMA == 11
    assert JUDGEMENTS_READS == (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11)
    assert SCHEMA_9_EVENTS == {"update", "approval", "red_handback", "enqueue"}


def _judgements(schema: int, event: dict[str, Any]) -> Judgements:
    return Judgements.model_validate(
        {
            "schema": schema,
            "tiers": [{"n": 1, "title": "Now"}],
            "issues": {"super-fr#1": {"tier": 1}},
            "batches": [
                {
                    "id": "b",
                    "title": "t",
                    "ids": ["super-fr#1"],
                    "events": [
                        {
                            "kind": "dispatch",
                            "at": "2026-10-11T11:00:00Z",
                            "runner": "herdr",
                            "handle": "h",
                            "branch": "feat/b",
                        },
                        event,
                    ],
                }
            ],
        }
    )


_EVENTS: list[dict[str, Any]] = [
    {"kind": "update", "at": "2026-10-11T12:00:00Z", "pr": 4, "head_before": "a",
     "head_after": "b", "base": "m"},
    {"kind": "approval", "at": "2026-10-11T12:00:00Z", "pr": 4, "head": "a"},
    {"kind": "approval", "at": "2026-10-11T12:00:00Z", "pr": 4, "head": "a", "voided_at": "c"},
    {"kind": "red_handback", "at": "2026-10-11T12:00:00Z", "pr": 4, "head": "a",
     "checks": ["test"], "delivered": "session"},
    {"kind": "red_handback", "at": "2026-10-11T12:00:00Z", "pr": 4, "head": "a",
     "checks": [], "delivered": "none"},
    {"kind": "enqueue", "at": "2026-10-11T12:00:00Z", "pr": 4, "head": "a", "base": "m"},
]  # fmt: skip


@pytest.mark.parametrize("event", _EVENTS, ids=lambda e: f"{e['kind']}")
def test_a_schema_9_file_carries_each_new_event(event: dict[str, Any]) -> None:
    judgements = _judgements(9, event)
    (got,) = judgements.batches[0].events[1:]
    assert got.kind == event["kind"]
    assert isinstance(got, UpdateEvent | ApprovalEvent | RedHandbackEvent | EnqueueEvent)


@pytest.mark.parametrize("event", _EVENTS, ids=lambda e: f"{e['kind']}")
def test_a_schema_8_file_carrying_a_new_event_is_refused(event: dict[str, Any]) -> None:
    with pytest.raises(ValidationError, match="need schema 9"):
        _judgements(8, event)


def test_a_red_handback_delivery_is_session_or_none() -> None:
    bad = {**_EVENTS[3], "delivered": "fresh"}
    with pytest.raises(ValidationError):
        _judgements(9, bad)


# ------------------------------------------------------------------ the verdict


def test_no_label_is_unlabelled_whatever_was_recorded() -> None:
    events = [_approval(4, "a")]
    assert approval_verdict(events, 4, "a", []) == Unlabelled()
    assert approval_verdict(events, 4, "a", None) == Unlabelled()
    assert approval_verdict(events, 4, "a", ["other"]) == Unlabelled()


def test_a_label_with_no_recorded_approval_is_first_at_the_current_head() -> None:
    assert approval_verdict([], 4, "a", LABELS) == First("a")


def test_an_approval_of_another_pr_does_not_count() -> None:
    assert approval_verdict([_approval(5, "a")], 4, "a", LABELS) == First("a")


def test_a_label_whose_last_approval_was_voided_is_first_again() -> None:
    events = [_approval(4, "a"), _approval(4, "a", voided_at="c", at=2)]
    assert approval_verdict(events, 4, "c", LABELS) == First("c")


def test_the_approved_head_itself_is_approved() -> None:
    assert approval_verdict([_approval(4, "a")], 4, "a", LABELS) == Approved("a")


def test_a_chain_of_fr_updates_from_the_approved_head_stays_approved() -> None:
    events = [
        _approval(4, "a"),
        _update(4, "a", "b", at=1),
        _update(5, "b", "x", at=2),  # another PR's update does not move this chain
        _update(4, "b", "c", at=3),
    ]
    assert approval_verdict(events, 4, "b", LABELS) == Approved("a")
    assert approval_verdict(events, 4, "c", LABELS) == Approved("a")


def test_an_update_recorded_before_the_approval_does_not_extend_it() -> None:
    events = [_update(4, "a", "b", at=0), _approval(4, "a", at=1)]
    assert approval_verdict(events, 4, "b", LABELS) == Void("a")


def test_a_head_the_chain_does_not_reach_is_void() -> None:
    events = [_approval(4, "a"), _update(4, "a", "b", at=1)]
    assert approval_verdict(events, 4, "z", LABELS) == Void("a")


def test_an_update_that_starts_from_a_foreign_head_breaks_the_chain() -> None:
    events = [_approval(4, "a"), _update(4, "q", "b", at=1)]
    assert approval_verdict(events, 4, "b", LABELS) == Void("a")


# ------------------------------------------------------------------ collectors


def test_parse_prs_reads_labels_only_from_a_record_that_carries_them() -> None:
    from fr.triage.collect import parse_prs

    base = {
        "number": 4,
        "title": "t",
        "state": "OPEN",
        "isDraft": False,
        "url": "u",
        "closingIssuesReferences": [],
    }
    ((with_labels, _),) = parse_prs("o/r", [{**base, "labels": [{"name": "approved-fr"}]}])
    ((without, _),) = parse_prs("o/r", [base])
    assert with_labels.labels == ["approved-fr"]
    assert without.labels is None


def test_the_graphql_open_pr_list_asks_for_labels() -> None:
    from fr.gh import OPEN_PR_LIST_FIELDS, PR_LIST_FIELDS

    assert "labels" in OPEN_PR_LIST_FIELDS.split(",")
    assert "labels" not in PR_LIST_FIELDS.split(",")  # a closed PR's labels are never read


def test_the_rest_open_pr_list_carries_labels() -> None:
    from fr.real_ghrestclient import RealGhRestClient

    from tests.unit.github_rest_support import REPO, FixtureGh

    (record,) = RealGhRestClient(run=FixtureGh()).list_open_prs(REPO, 1)
    assert record["labels"] == []  # the captured #1080 carries none
