"""Tests for fake test doubles (FakeGhClient H5, FakeMcpClient B4)."""

import pytest

from tests.unit.fakes import FakeGhClient, FakeGhError


def test_fake_gh_client_rejects_unensured_labels_on_edit():  # H5
    gh = FakeGhClient()
    gh.add_issue("derio-net/repo-a", 1)
    with pytest.raises(FakeGhError, match="label not found"):
        gh.edit_issue_labels(
            "derio-net/repo-a",
            1,
            add=frozenset({"vk-ready"}),
            remove=frozenset(),
        )


def test_fake_gh_client_rejects_unensured_labels_on_create():  # H5
    gh = FakeGhClient()
    with pytest.raises(FakeGhError, match="label not found"):
        gh.create_issue(
            "derio-net/repo-a",
            title="t",
            body="b",
            labels=frozenset({"vk-ready"}),
        )


def test_fake_gh_client_accepts_labels_after_ensure():  # H5
    gh = FakeGhClient()
    gh.ensure_labels("derio-net/repo-a", ["vk-ready"])
    gh.create_issue(
        "derio-net/repo-a",
        title="t",
        body="b",
        labels=frozenset({"vk-ready"}),
    )


# --- FakeMcpClient tests (B4) ---


def test_fake_mcp_client_implements_protocol():  # B4
    from tests.unit.fakes import FakeMcpClient

    fc = FakeMcpClient()
    assert hasattr(fc, "create_issue")
    assert hasattr(fc, "update_issue")
    assert hasattr(fc, "start_workspace")
    assert hasattr(fc, "update_workspace")
    assert hasattr(fc, "list_repos")
    assert hasattr(fc, "link_workspace_issue")
    assert fc.calls == []


def test_fake_mcp_client_records_calls():  # B4
    from tests.unit.fakes import FakeMcpClient

    fc = FakeMcpClient()
    fc.create_issue(title="t", description="d")
    assert fc.calls == [("create_issue", {"title": "t", "description": "d"})]


def test_fake_mcp_client_failure_injection():  # B4
    from tests.unit.fakes import FakeMcpClient

    fc = FakeMcpClient(fail_on_call=1)
    fc.create_issue(title="t", description="d")  # call 0 — succeeds
    with pytest.raises(Exception, match="injected"):
        fc.update_issue("card-1", status="In progress")  # call 1 — fails
