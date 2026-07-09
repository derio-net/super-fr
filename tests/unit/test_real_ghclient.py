"""Tests for the production GhClient (`vk.real_ghclient.RealGhClient`).

The wire-level shaping (gh CLI subprocess, GraphQL response → observe
contract) is the seam where bugs hide. We monkeypatch `vk.gh._run_gh`
to return canned JSON and assert the coercion logic without spawning
real subprocesses.
"""

from __future__ import annotations

import json

import pytest
from fr import gh as _gh
from fr.real_ghclient import RealGhClient, _coerce_ci_state


def _fake_run_gh_factory(returns: dict[tuple[str, ...], str]):
    """Build a `_run_gh` stand-in that dispatches by argv prefix."""

    def _run(args: list[str]) -> str:
        for prefix, value in returns.items():
            if tuple(args[: len(prefix)]) == prefix:
                return value
        raise AssertionError(f"unexpected gh call: {args}")

    return _run


class TestListLinkedPrs:
    def test_coerces_merged_state_to_closed(self, monkeypatch):
        """GraphQL returns state=MERGED; observe contract demands OPEN/CLOSED.
        The `merged` boolean preserves the distinction."""
        graphql_response = {
            "data": {
                "repository": {
                    "issue": {
                        "closedByPullRequestsReferences": {
                            "nodes": [
                                {
                                    "url": "https://github.com/x/y/pull/1",
                                    "state": "MERGED",
                                    "merged": True,
                                    "isDraft": False,
                                    "statusCheckRollup": {"state": "SUCCESS"},
                                }
                            ]
                        }
                    }
                }
            }
        }
        monkeypatch.setattr(
            _gh,
            "_run_gh",
            _fake_run_gh_factory({("api", "graphql"): json.dumps(graphql_response)}),
        )
        prs = RealGhClient().list_linked_prs("derio-net/x", 42)
        assert len(prs) == 1
        assert prs[0]["state"] == "CLOSED"  # coerced from MERGED
        assert prs[0]["merged"] is True
        assert prs[0]["ci"] == "PASS"

    def test_passes_through_open_state(self, monkeypatch):
        graphql_response = {
            "data": {
                "repository": {
                    "issue": {
                        "closedByPullRequestsReferences": {
                            "nodes": [
                                {
                                    "url": "https://github.com/x/y/pull/2",
                                    "state": "OPEN",
                                    "merged": False,
                                    "isDraft": True,
                                    "statusCheckRollup": {"state": "PENDING"},
                                }
                            ]
                        }
                    }
                }
            }
        }
        monkeypatch.setattr(
            _gh,
            "_run_gh",
            _fake_run_gh_factory({("api", "graphql"): json.dumps(graphql_response)}),
        )
        prs = RealGhClient().list_linked_prs("derio-net/x", 42)
        assert prs[0]["state"] == "OPEN"
        assert prs[0]["draft"] is True
        assert prs[0]["ci"] == "PENDING"

    def test_returns_empty_on_gh_error(self, monkeypatch):
        """Soft-fail: an unreachable PR query shouldn't blow up `fr apply`."""

        def _raise(args):
            raise _gh.GhError("transient failure")

        monkeypatch.setattr(_gh, "_run_gh", _raise)
        assert RealGhClient().list_linked_prs("derio-net/x", 42) == []


class TestCoerceCIState:
    @pytest.mark.parametrize(
        ("rollup", "expected"),
        [
            ("SUCCESS", "PASS"),
            ("FAILURE", "FAIL"),
            ("ERROR", "FAIL"),
            ("TIMED_OUT", "FAIL"),
            ("CANCELLED", "FAIL"),
            ("ACTION_REQUIRED", "FAIL"),
            ("PENDING", "PENDING"),
            ("EXPECTED", "PENDING"),
            ("QUEUED", "PENDING"),
            ("IN_PROGRESS", "PENDING"),
            ("", "NONE"),
            ("UNKNOWN_NEW_STATE", "NONE"),
        ],
    )
    def test_mapping(self, rollup, expected):
        assert _coerce_ci_state(rollup) == expected


class TestViewIssue:
    def test_coerces_label_and_assignee_dicts_to_names(self, monkeypatch):
        """gh returns labels/assignees as `[{name|login: ..., ...}]`;
        observe contract is plain string lists."""
        gh_response = {
            "state": "OPEN",
            "labels": [{"name": "fr:ready", "color": "0E8AE6"}, {"name": "phase:1"}],
            "assignees": [{"login": "alice"}],
            "body": "the body",
        }
        monkeypatch.setattr(
            _gh,
            "_run_gh",
            _fake_run_gh_factory({("issue", "view"): json.dumps(gh_response)}),
        )
        info = RealGhClient().view_issue("derio-net/x", 42)
        assert info["state"] == "OPEN"
        assert info["labels"] == ["fr:ready", "phase:1"]
        assert info["assignees"] == ["alice"]
        assert info["body"] == "the body"

    def test_handles_missing_optional_fields(self, monkeypatch):
        gh_response = {"state": "CLOSED"}
        monkeypatch.setattr(
            _gh,
            "_run_gh",
            _fake_run_gh_factory({("issue", "view"): json.dumps(gh_response)}),
        )
        info = RealGhClient().view_issue("derio-net/x", 42)
        assert info["state"] == "CLOSED"
        assert info["labels"] == []
        assert info["assignees"] == []
        assert info["body"] == ""


class TestPrStatusByUrl:
    """gh accepts a bare PR URL directly (`gh pr view <url>`) — confirmed
    against real gh usage; the other two backends' adapters cannot do the
    same (see test_real_glabclient.py / test_real_teaclient.py)."""

    def test_open_non_draft(self, monkeypatch):
        monkeypatch.setattr(
            _gh,
            "_run_gh",
            _fake_run_gh_factory({("pr", "view"): json.dumps({"state": "OPEN", "isDraft": False})}),
        )
        result = RealGhClient().pr_status_by_url("https://github.com/o/r/pull/1")
        assert result == {"state": "OPEN", "draft": False}

    def test_merged(self, monkeypatch):
        monkeypatch.setattr(
            _gh,
            "_run_gh",
            _fake_run_gh_factory(
                {("pr", "view"): json.dumps({"state": "MERGED", "isDraft": False})}
            ),
        )
        result = RealGhClient().pr_status_by_url("https://github.com/o/r/pull/1")
        assert result == {"state": "MERGED", "draft": False}

    def test_returns_none_on_error(self, monkeypatch):
        def _raise(args):
            raise _gh.GhError("not found")

        monkeypatch.setattr(_gh, "_run_gh", _raise)
        assert RealGhClient().pr_status_by_url("https://github.com/o/r/pull/999") is None
