"""Tests for FakeGhClient label-enforcement (spec Group H5).

The plan (P1.T1.S3) called for a single test function; the implementation
splits it into three for cleaner failure isolation. All three functions
cover H5 from the acceptance test spec.
"""

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
