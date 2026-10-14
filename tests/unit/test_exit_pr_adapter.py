"""PR-level label and comment adapter methods — spec 2026-10-14 exit-gates R7, §B."""

from __future__ import annotations

import inspect

import pytest
from fr import gh as _gh
from fr.ghclient import GhClient, UnsupportedBatchOps, UnsupportedForgeOperation
from fr.real_ghclient import RealGhClient
from fr.real_ghrestclient import RealGhRestClient
from fr.real_glabclient import RealGlabClient
from fr.real_teaclient import RealTeaClient

from tests.unit.fakes import FakeGhClient
from tests.unit.github_rest_support import REPO, FixtureGh, R, parse_api


def test_the_protocol_declares_both_pr_methods() -> None:
    assert list(inspect.signature(GhClient.edit_pr_labels).parameters) == [
        "self", "repo", "pr", "add", "remove",
    ]  # fmt: skip
    assert list(inspect.signature(GhClient.comment_pr).parameters) == ["self", "repo", "pr", "body"]


def test_the_gh_client_writes_through_the_issue_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(_gh, "_run_gh", lambda args: calls.append(list(args)) or "")
    client = RealGhClient()
    client.edit_pr_labels(REPO, 7, add=frozenset({"gate:tester"}), remove=frozenset({"x"}))
    client.comment_pr(REPO, 7, "hi")
    assert calls[0][:3] == ["issue", "edit", "7"]
    assert "gate:tester" in calls[0] and "x" in calls[0]
    assert calls[1][:3] == ["issue", "comment", "7"]


def test_the_rest_client_writes_through_the_issue_endpoints() -> None:
    fake = FixtureGh(
        writes={
            ("POST", f"{R}/issues/7/labels"): "[]",
            ("POST", f"{R}/issues/7/comments"): "{}",
        }
    )
    client = RealGhRestClient(run=fake)
    client.edit_pr_labels(REPO, 7, add=frozenset({"a"}), remove=frozenset())
    client.comment_pr(REPO, 7, "hi")
    routes = [parse_api(a)[:3:2] for a in fake.calls]
    assert routes == [("POST", f"{R}/issues/7/labels"), ("POST", f"{R}/issues/7/comments")]


@pytest.mark.parametrize("cls", [RealGlabClient, RealTeaClient, UnsupportedBatchOps])
def test_glab_and_tea_cannot_label_a_pr(cls: type) -> None:
    client = cls()
    with pytest.raises(UnsupportedForgeOperation, match="edit_pr_labels"):
        client.edit_pr_labels(REPO, 7, add=frozenset(), remove=frozenset())
    with pytest.raises(UnsupportedForgeOperation, match="comment_pr"):
        client.comment_pr(REPO, 7, "x")


def test_the_fake_implements_both() -> None:
    fake = FakeGhClient()
    fake.edit_pr_labels(REPO, 7, add=frozenset({"a"}), remove=frozenset({"b"}))
    fake.comment_pr(REPO, 7, "hi")
    assert [c[0] for c in fake.calls] == ["edit_pr_labels", "comment_pr"]
