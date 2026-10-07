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


class TestIssueComments:
    """Comment ids and comment edits (spec 2026-10-06-triage-claims §3.C, R12)."""

    def test_list_issue_comments_parses_the_id_from_the_url(self, monkeypatch):
        raw = {
            "comments": [
                {
                    "author": {"login": "a"},
                    "body": "x",
                    "createdAt": "2026-10-06T10:00:00Z",
                    "url": "https://github.com/o/r/issues/7#issuecomment-123",
                },
                {"author": {"login": "b"}, "body": "y", "createdAt": "2026-10-06T11:00:00Z"},
                {
                    "author": {"login": "c"},
                    "body": "z",
                    "createdAt": "2026-10-06T12:00:00Z",
                    "url": "https://github.com/o/r/issues/7",
                },
            ]
        }
        monkeypatch.setattr(
            _gh, "_run_gh", _fake_run_gh_factory({("issue", "view"): json.dumps(raw)})
        )
        got = RealGhClient().list_issue_comments("o/r", 7)
        assert [c["id"] for c in got] == [123, None, None]
        assert got[0] == {
            "association": "",
            "author": "a",
            "body": "x",
            "created_at": "2026-10-06T10:00:00Z",
            "id": 123,
        }

    def test_edit_issue_comment_patches_the_comment(self, monkeypatch):
        calls: list[list[str]] = []

        def _run(args: list[str]) -> str:
            calls.append(list(args))
            return "{}"

        monkeypatch.setattr(_gh, "_run_gh", _run)
        RealGhClient().edit_issue_comment("o/r", 123, "new body")
        assert calls == [
            ["api", "-X", "PATCH", "repos/o/r/issues/comments/123", "-f", "body=new body"]
        ]


# ----------------------------------------- batch adopt's PR supersede (spec 2026-10-06 §C)

_GH_FIXTURES = __import__("pathlib").Path(__file__).resolve().parent.parent / "fixtures" / "gh"
_ADOPT_REPO = "derio-net/super-fr"


class _Recorder:
    """`_run_gh` stand-in answering from the live captures in tests/fixtures/gh."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, args: list[str]) -> str:
        self.calls.append(list(args))
        if args[:2] == ["pr", "create"]:
            return (_GH_FIXTURES / "pr-create-draft.stdout").read_text()
        if args[:2] == ["pr", "view"]:
            return (_GH_FIXTURES / "pr-view-adopt.json").read_text()
        return ""  # `pr close` and `api -X DELETE` print nothing on stdout (captured)


@pytest.fixture
def recorder(monkeypatch: pytest.MonkeyPatch) -> _Recorder:
    fake = _Recorder()
    monkeypatch.setattr(_gh, "_run_gh", fake)
    return fake


def _flag(call: list[str], flag: str) -> str:
    return call[call.index(flag) + 1]


class TestAdoptPrOperations:
    @pytest.mark.parametrize("draft", [True, False])
    def test_create_pr_issues_gh_pr_create_and_parses_number_and_url(
        self, recorder: _Recorder, draft: bool
    ) -> None:
        got = RealGhClient().create_pr(
            _ADOPT_REPO, head="feat/batch-x", base="main", title="T", body="B", draft=draft
        )
        assert got == {"number": 1044, "url": "https://github.com/derio-net/super-fr/pull/1044"}
        (call,) = recorder.calls
        assert call[:4] == ["pr", "create", "--repo", _ADOPT_REPO]
        assert (_flag(call, "--head"), _flag(call, "--base")) == ("feat/batch-x", "main")
        assert (_flag(call, "--title"), _flag(call, "--body")) == ("T", "B")
        assert ("--draft" in call) is draft

    def test_pr_create_still_opens_a_ready_pr_and_returns_its_number(
        self, recorder: _Recorder
    ) -> None:
        got = RealGhClient().pr_create(_ADOPT_REPO, head="h", base="main", title="t", body="b")
        assert got == 1044
        assert "--draft" not in recorder.calls[0]

    def test_close_pr_issues_gh_pr_close(self, recorder: _Recorder) -> None:
        assert RealGhClient().close_pr(_ADOPT_REPO, 1044) is None
        assert recorder.calls == [["pr", "close", "1044", "--repo", _ADOPT_REPO]]

    def test_delete_branch_deletes_the_ref_through_the_api(self, recorder: _Recorder) -> None:
        assert RealGhClient().delete_branch(_ADOPT_REPO, "feat/hand-started") is None
        assert recorder.calls == [
            [
                "api",
                "-X",
                "DELETE",
                f"repos/{_ADOPT_REPO}/git/refs/heads/feat/hand-started",
            ]
        ]

    def test_pr_view_carries_title_and_body(self, recorder: _Recorder) -> None:
        got = RealGhClient().pr_view(_ADOPT_REPO, 1044)
        assert got["title"] == "scratch: fr batch adopt capture (closed immediately)"
        assert got["body"].startswith("Live capture of `gh pr create --draft`")
        assert got["draft"] is True and got["base_ref"] == "main"
        fields = _flag(recorder.calls[0], "--json").split(",")
        assert {"title", "body"} <= set(fields)
