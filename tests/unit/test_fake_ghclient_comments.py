"""The fake GhClient serves comment ids and records edits (triage-claims §3.C)."""

from __future__ import annotations

from tests.unit.fakes import FakeGhClient


def test_the_fake_serves_ids_and_edits_in_place() -> None:
    gh = FakeGhClient()
    gh.add_issue("o/r", 1)
    gh.comment_issue("o/r", 1, "a")
    gh.comment_issue("o/r", 1, "b")
    first, second = gh.list_issue_comments("o/r", 1)
    assert isinstance(first["id"], int) and second["id"] > first["id"]
    gh.edit_issue_comment("o/r", first["id"], "a2")
    assert [c["body"] for c in gh.list_issue_comments("o/r", 1)] == ["a2", "b"]
    assert (
        "edit_issue_comment",
        {"repo": "o/r", "comment_id": first["id"], "body": "a2"},
    ) in gh.calls
