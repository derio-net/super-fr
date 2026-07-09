"""Tests for the production TeaClient (`fr.real_teaclient.RealTeaClient`).

Gitea's OWN raw shapes (verified against Gitea's live swagger spec,
gitea.com/swagger.v1.json) — closer to GitHub's than GitLab's in several
respects (labels are full objects, not plain strings; contents API is
base64-encoded the same way), but with real differences of its own (label
color needs a leading `#` on write; no dedicated "related PRs" endpoint).
We monkeypatch `fr.tea._run_tea` to return canned JSON.
"""

from __future__ import annotations

import json

import pytest
from fr import tea as _tea
from fr.real_teaclient import RealTeaClient


def _fake_run_tea_factory(returns: dict[tuple[str, ...], str]):
    def _run(args: list[str]) -> str:
        for prefix, value in returns.items():
            if tuple(args[: len(prefix)]) == prefix:
                return value
        raise AssertionError(f"unexpected tea call: {args}")

    return _run


class TestViewIssue:
    def test_coerces_label_and_assignee_objects_to_names(self, monkeypatch):
        """Gitea's Issue.labels is an array of full Label objects (like
        GitHub's), NOT plain strings (like GitLab's) — verified against
        the live swagger Issue schema."""
        response = {
            "state": "open",
            "labels": [{"name": "fr:ready", "color": "0e8ae6"}, {"name": "phase:1"}],
            "assignees": [{"login": "alice"}],
            "body": "the body",
        }
        monkeypatch.setattr(
            _tea, "_run_tea", _fake_run_tea_factory({("issues",): json.dumps(response)})
        )
        info = RealTeaClient().view_issue("owner/repo", 42)
        assert info["state"] == "OPEN"
        assert info["labels"] == ["fr:ready", "phase:1"]
        assert info["assignees"] == ["alice"]
        assert info["body"] == "the body"

    def test_coerces_closed_state(self, monkeypatch):
        response = {"state": "closed", "labels": [], "assignees": [], "body": ""}
        monkeypatch.setattr(
            _tea, "_run_tea", _fake_run_tea_factory({("issues",): json.dumps(response)})
        )
        info = RealTeaClient().view_issue("owner/repo", 42)
        assert info["state"] == "CLOSED"


class TestListLinkedPrs:
    """list_linked_prs has no dedicated endpoint — implemented via the
    issue's timeline, filtering events whose ref_issue is a PR (has a
    non-null pull_request sub-object). Verified structurally against
    Gitea's live swagger: TimelineComment.ref_issue -> Issue,
    Issue.pull_request -> PullRequestMeta (draft/merged/merged_at/html_url)."""

    def test_filters_to_pr_references_only(self, monkeypatch):
        timeline = json.dumps(
            [
                {"type": "comment", "ref_issue": None},  # plain comment, no ref
                {
                    "type": "pull_ref",
                    "ref_issue": {
                        "html_url": "https://gitea.example.com/o/r/pulls/7",
                        "state": "open",
                        "pull_request": {"draft": True, "merged": False},
                    },
                },
                {
                    "type": "pull_ref",
                    "ref_issue": {
                        "html_url": "https://gitea.example.com/o/r/issues/8",
                        "state": "closed",
                        "pull_request": None,  # a referencing ISSUE, not a PR — excluded
                    },
                },
            ]
        )
        monkeypatch.setattr(
            _tea, "_run_tea", _fake_run_tea_factory({("api",): timeline})
        )
        prs = RealTeaClient().list_linked_prs("owner/repo", 3)
        assert len(prs) == 1
        assert prs[0]["url"] == "https://gitea.example.com/o/r/pulls/7"
        assert prs[0]["state"] == "OPEN"
        assert prs[0]["draft"] is True
        assert prs[0]["merged"] is False
        assert prs[0]["ci"] == "NONE"  # deliberate scope limit — see module docstring

    def test_merged_pr_maps_to_closed(self, monkeypatch):
        timeline = json.dumps(
            [
                {
                    "type": "pull_ref",
                    "ref_issue": {
                        "html_url": "https://gitea.example.com/o/r/pulls/9",
                        "state": "closed",
                        "pull_request": {"draft": False, "merged": True},
                    },
                }
            ]
        )
        monkeypatch.setattr(_tea, "_run_tea", _fake_run_tea_factory({("api",): timeline}))
        prs = RealTeaClient().list_linked_prs("owner/repo", 3)
        assert prs[0]["state"] == "CLOSED"
        assert prs[0]["merged"] is True

    def test_dedupes_by_url_across_multiple_events(self, monkeypatch):
        """The same PR can generate more than one timeline event
        referencing the issue — results must be deduplicated by URL."""
        pr = {
            "html_url": "https://gitea.example.com/o/r/pulls/7",
            "state": "open",
            "pull_request": {"draft": False, "merged": False},
        }
        timeline = json.dumps(
            [{"type": "pull_ref", "ref_issue": pr}, {"type": "pull_ref", "ref_issue": pr}]
        )
        monkeypatch.setattr(_tea, "_run_tea", _fake_run_tea_factory({("api",): timeline}))
        prs = RealTeaClient().list_linked_prs("owner/repo", 3)
        assert len(prs) == 1

    def test_returns_empty_on_tea_error(self, monkeypatch):
        def _raise(args):
            raise _tea.TeaError("transient failure")

        monkeypatch.setattr(_tea, "_run_tea", _raise)
        assert RealTeaClient().list_linked_prs("owner/repo", 3) == []


class TestEditIssueState:
    def test_closed_calls_close_issue(self, monkeypatch):
        captured: list[tuple[str, int]] = []
        monkeypatch.setattr(
            _tea, "close_issue", lambda *, repo, number: captured.append((repo, number))
        )
        RealTeaClient().edit_issue_state("owner/repo", 42, state="CLOSED")
        assert captured == [("owner/repo", 42)]

    def test_open_calls_reopen_issue(self, monkeypatch):
        captured: list[tuple[str, int]] = []
        monkeypatch.setattr(
            _tea, "reopen_issue", lambda *, repo, number: captured.append((repo, number))
        )
        RealTeaClient().edit_issue_state("owner/repo", 42, state="OPEN")
        assert captured == [("owner/repo", 42)]

    def test_unknown_state_raises(self):
        with pytest.raises(ValueError, match="unknown issue state"):
            RealTeaClient().edit_issue_state("owner/repo", 42, state="WEIRD")


class TestCommentIssue:
    def test_uses_comments_add_subcommand(self, monkeypatch):
        captured: list[list[str]] = []
        monkeypatch.setattr(_tea, "_run_tea", lambda args: captured.append(args) or "")
        RealTeaClient().comment_issue("owner/repo", 42, "hello")
        assert captured == [["comments", "add", "42", "hello", "--repo", "owner/repo"]]


class TestThinPassThroughs:
    def test_create_issue_delegates(self, monkeypatch):
        monkeypatch.setattr(
            _tea, "create_issue", lambda **kw: "https://gitea.example.com/o/r/issues/9"
        )
        url = RealTeaClient().create_issue(
            "owner/repo", title="T", body="B", labels=frozenset({"fr:ready"})
        )
        assert url == "https://gitea.example.com/o/r/issues/9"

    def test_edit_issue_labels_delegates_to_swap(self, monkeypatch):
        captured: list[dict] = []
        monkeypatch.setattr(_tea, "swap_issue_labels", lambda **kw: captured.append(kw))
        RealTeaClient().edit_issue_labels(
            "owner/repo", 42, add=frozenset({"pr-ready"}), remove=frozenset({"fr:ready"})
        )
        assert captured == [
            {"repo": "owner/repo", "number": 42, "add": ["pr-ready"], "remove": ["fr:ready"]}
        ]

    def test_edit_issue_body_delegates(self, monkeypatch):
        captured: list[dict] = []
        monkeypatch.setattr(_tea, "edit_issue_body", lambda **kw: captured.append(kw))
        RealTeaClient().edit_issue_body("owner/repo", 42, "new body")
        assert captured == [{"repo": "owner/repo", "number": 42, "body": "new body"}]

    def test_ensure_labels_delegates(self, monkeypatch):
        from fr.labels import LabelDef

        captured: list[dict] = []
        monkeypatch.setattr(_tea, "ensure_labels", lambda **kw: captured.append(kw))
        defs = [LabelDef("fr:ready", "0E8AE6", "queued")]
        RealTeaClient().ensure_labels("owner/repo", defs)
        assert captured == [{"repo": "owner/repo", "labels": defs}]


class TestContentsApi:
    def test_file_exists_true_on_success(self, monkeypatch):
        monkeypatch.setattr(
            _tea, "_run_tea", lambda args: json.dumps({"content": "eA==", "type": "file"})
        )
        assert RealTeaClient().file_exists("owner/repo", "docs/x.md") is True

    def test_file_exists_false_on_error(self, monkeypatch):
        def _raise(args):
            raise _tea.TeaError("404")

        monkeypatch.setattr(_tea, "_run_tea", _raise)
        assert RealTeaClient().file_exists("owner/repo", "docs/missing.md") is False

    def test_read_file_decodes_base64_content(self, monkeypatch):
        import base64

        encoded = base64.b64encode(b"hello world").decode("ascii")
        monkeypatch.setattr(
            _tea,
            "_run_tea",
            lambda args: json.dumps({"content": encoded, "encoding": "base64", "type": "file"}),
        )
        assert RealTeaClient().read_file("owner/repo", "docs/x.md") == "hello world"

    def test_list_dir_returns_names(self, monkeypatch):
        response = json.dumps(
            [
                {"name": "01.yaml", "type": "file"},
                {"name": "02.yaml", "type": "file"},
            ]
        )
        monkeypatch.setattr(_tea, "_run_tea", lambda args: response)
        assert RealTeaClient().list_dir("owner/repo", "docs/plan") == ["01.yaml", "02.yaml"]

    def test_list_dir_empty_on_error(self, monkeypatch):
        def _raise(args):
            raise _tea.TeaError("404")

        monkeypatch.setattr(_tea, "_run_tea", _raise)
        assert RealTeaClient().list_dir("owner/repo", "docs/missing") == []


class TestPrStatusByUrl:
    """tea's `pulls` command doesn't take a bare URL either (same
    reasoning as GitLab's `mr view`) — parse (repo, index) from the URL,
    then query by index."""

    def test_parses_url_and_calls_pulls_by_index(self, monkeypatch):
        captured: list[list[str]] = []

        def fake(args: list[str]) -> str:
            captured.append(args)
            return json.dumps({"state": "open", "merged": False, "draft": False})

        monkeypatch.setattr(_tea, "_run_tea", fake)
        result = RealTeaClient().pr_status_by_url(
            "https://gitea.example.com/owner/repo/pulls/7"
        )
        assert result == {"state": "OPEN", "draft": False}
        assert captured == [["pulls", "7", "--repo", "owner/repo", "--output", "json"]]

    def test_merged_state(self, monkeypatch):
        monkeypatch.setattr(
            _tea,
            "_run_tea",
            lambda args: json.dumps({"state": "closed", "merged": True, "draft": False}),
        )
        result = RealTeaClient().pr_status_by_url(
            "https://gitea.example.com/owner/repo/pulls/7"
        )
        assert result == {"state": "MERGED", "draft": False}

    def test_closed_unmerged_state(self, monkeypatch):
        monkeypatch.setattr(
            _tea,
            "_run_tea",
            lambda args: json.dumps({"state": "closed", "merged": False, "draft": False}),
        )
        result = RealTeaClient().pr_status_by_url(
            "https://gitea.example.com/owner/repo/pulls/7"
        )
        assert result == {"state": "CLOSED", "draft": False}

    def test_returns_none_on_error(self, monkeypatch):
        def _raise(args):
            raise _tea.TeaError("not found")

        monkeypatch.setattr(_tea, "_run_tea", _raise)
        assert (
            RealTeaClient().pr_status_by_url("https://gitea.example.com/owner/repo/pulls/999")
            is None
        )

    def test_returns_none_on_unparseable_url(self):
        assert RealTeaClient().pr_status_by_url("https://example.com/not/a/pr") is None
