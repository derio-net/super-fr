"""Tests for fake test doubles (FakeGhClient H5)."""

import pytest

from tests.unit.fakes import FakeGhClient, FakeGhError


def test_fake_gh_client_rejects_unensured_labels_on_edit():  # H5
    gh = FakeGhClient()
    gh.add_issue("derio-net/repo-a", 1)
    with pytest.raises(FakeGhError, match="label not found"):
        gh.edit_issue_labels(
            "derio-net/repo-a",
            1,
            add=frozenset({"fr:ready"}),
            remove=frozenset(),
        )


def test_fake_gh_client_rejects_unensured_labels_on_create():  # H5
    gh = FakeGhClient()
    with pytest.raises(FakeGhError, match="label not found"):
        gh.create_issue(
            "derio-net/repo-a",
            title="t",
            body="b",
            labels=frozenset({"fr:ready"}),
        )


def test_fake_gh_client_accepts_labels_after_ensure():  # H5
    gh = FakeGhClient()
    gh.ensure_labels("derio-net/repo-a", ["fr:ready"])
    gh.create_issue(
        "derio-net/repo-a",
        title="t",
        body="b",
        labels=frozenset({"fr:ready"}),
    )
