"""Tests for the production GlabClient (`fr.real_glabclient.RealGlabClient`).

GitLab's OWN raw shapes (REST + `glab api`) — deliberately NOT reusing
GitHub's GraphQL-shaped fixtures from test_real_ghclient.py, which don't
generalize (per the design doc's research). We monkeypatch
`fr.glab._run_glab` to return canned JSON and assert the coercion logic
without spawning real subprocesses.
"""

from __future__ import annotations

import json

import pytest
from fr import glab as _glab
from fr.real_glabclient import RealGlabClient, _coerce_ci_state


def _fake_run_glab_factory(returns: dict[tuple[str, ...], str]):
    """Build a `_run_glab` stand-in that dispatches by argv prefix."""

    def _run(args: list[str]) -> str:
        for prefix, value in returns.items():
            if tuple(args[: len(prefix)]) == prefix:
                return value
        raise AssertionError(f"unexpected glab call: {args}")

    return _run


class TestViewIssue:
    def test_coerces_opened_state_and_plain_string_labels(self, monkeypatch):
        """GitLab's REST/CLI issue shape uses lowercase opened/closed and
        labels as a plain string array (NOT [{name: ...}] like GitHub)."""
        response = {
            "state": "opened",
            "labels": ["fr:ready", "phase:1"],
            "assignees": [{"username": "alice"}],
            "description": "the body",
        }
        monkeypatch.setattr(
            _glab,
            "_run_glab",
            _fake_run_glab_factory({("issue", "view"): json.dumps(response)}),
        )
        info = RealGlabClient().view_issue("group/proj", 42)
        assert info["state"] == "OPEN"
        assert info["labels"] == ["fr:ready", "phase:1"]
        assert info["assignees"] == ["alice"]
        assert info["body"] == "the body"

    def test_coerces_closed_state(self, monkeypatch):
        response = {"state": "closed", "labels": [], "assignees": [], "description": ""}
        monkeypatch.setattr(
            _glab,
            "_run_glab",
            _fake_run_glab_factory({("issue", "view"): json.dumps(response)}),
        )
        info = RealGlabClient().view_issue("group/proj", 42)
        assert info["state"] == "CLOSED"
        assert info["labels"] == []
        assert info["assignees"] == []
        assert info["body"] == ""


class TestListLinkedPrs:
    def test_coerces_merged_mr_to_closed(self, monkeypatch):
        response = json.dumps(
            [
                {
                    "web_url": "https://gitlab.com/group/proj/-/merge_requests/1",
                    "state": "merged",
                    "draft": False,
                    "pipeline": {"status": "success"},
                }
            ]
        )
        monkeypatch.setattr(
            _glab,
            "_run_glab",
            _fake_run_glab_factory({("api",): response}),
        )
        prs = RealGlabClient().list_linked_prs("group/proj", 42)
        assert len(prs) == 1
        assert prs[0]["state"] == "CLOSED"
        assert prs[0]["merged"] is True
        assert prs[0]["draft"] is False
        assert prs[0]["ci"] == "PASS"
        assert prs[0]["url"] == "https://gitlab.com/group/proj/-/merge_requests/1"

    def test_passes_through_opened_state(self, monkeypatch):
        response = json.dumps(
            [
                {
                    "web_url": "https://gitlab.com/group/proj/-/merge_requests/2",
                    "state": "opened",
                    "draft": True,
                    "pipeline": {"status": "running"},
                }
            ]
        )
        monkeypatch.setattr(
            _glab,
            "_run_glab",
            _fake_run_glab_factory({("api",): response}),
        )
        prs = RealGlabClient().list_linked_prs("group/proj", 42)
        assert prs[0]["state"] == "OPEN"
        assert prs[0]["merged"] is False
        assert prs[0]["draft"] is True
        assert prs[0]["ci"] == "PENDING"

    def test_missing_pipeline_maps_to_none_ci(self, monkeypatch):
        response = json.dumps(
            [{"web_url": "https://gitlab.com/g/p/-/merge_requests/3", "state": "opened"}]
        )
        monkeypatch.setattr(_glab, "_run_glab", _fake_run_glab_factory({("api",): response}))
        prs = RealGlabClient().list_linked_prs("group/proj", 42)
        assert prs[0]["ci"] == "NONE"
        assert prs[0]["draft"] is False

    def test_returns_empty_on_glab_error(self, monkeypatch):
        """Soft-fail: an unreachable MR query shouldn't blow up `fr apply`."""

        def _raise(args):
            raise _glab.GlabError("transient failure")

        monkeypatch.setattr(_glab, "_run_glab", _raise)
        assert RealGlabClient().list_linked_prs("group/proj", 42) == []

    def test_url_encodes_repo_for_api_path(self, monkeypatch):
        captured: list[list[str]] = []

        def fake(args: list[str]) -> str:
            captured.append(args)
            return "[]"

        monkeypatch.setattr(_glab, "_run_glab", fake)
        RealGlabClient().list_linked_prs("group/subgroup/proj", 42)
        api_arg = captured[0][1]
        assert "group%2Fsubgroup%2Fproj" in api_arg
        assert "issues/42/related_merge_requests" in api_arg


class TestCoerceCIState:
    @pytest.mark.parametrize(
        ("status", "expected"),
        [
            ("success", "PASS"),
            ("failed", "FAIL"),
            ("canceled", "FAIL"),
            ("running", "PENDING"),
            ("pending", "PENDING"),
            ("created", "PENDING"),
            ("skipped", "NONE"),
            ("", "NONE"),
            ("some_unknown_future_state", "NONE"),
        ],
    )
    def test_mapping(self, status, expected):
        assert _coerce_ci_state(status) == expected


class TestEditIssueState:
    def test_closed_calls_close_issue(self, monkeypatch):
        captured: list[tuple[str, int]] = []
        monkeypatch.setattr(
            _glab, "close_issue", lambda *, repo, number: captured.append((repo, number))
        )
        RealGlabClient().edit_issue_state("group/proj", 42, state="CLOSED")
        assert captured == [("group/proj", 42)]

    def test_open_calls_reopen_issue(self, monkeypatch):
        captured: list[tuple[str, int]] = []
        monkeypatch.setattr(
            _glab, "reopen_issue", lambda *, repo, number: captured.append((repo, number))
        )
        RealGlabClient().edit_issue_state("group/proj", 42, state="OPEN")
        assert captured == [("group/proj", 42)]

    def test_unknown_state_raises(self):
        with pytest.raises(ValueError, match="unknown issue state"):
            RealGlabClient().edit_issue_state("group/proj", 42, state="WEIRD")


class TestCommentIssue:
    def test_uses_note_subcommand(self, monkeypatch):
        """glab's comment command is `issue note`, not `issue comment`."""
        captured: list[list[str]] = []
        monkeypatch.setattr(_glab, "_run_glab", lambda args: captured.append(args) or "")
        RealGlabClient().comment_issue("group/proj", 42, "hello")
        assert captured == [["issue", "note", "42", "--repo", "group/proj", "--message", "hello"]]


class TestThinPassThroughs:
    """create_issue / edit_issue_labels / edit_issue_body / ensure_labels
    just delegate to fr.glab's functions — cheap regression guards."""

    def test_create_issue_delegates(self, monkeypatch):
        monkeypatch.setattr(_glab, "create_issue", lambda **kw: "https://gitlab.com/g/p/-/issues/9")
        url = RealGlabClient().create_issue(
            "group/proj", title="T", body="B", labels=frozenset({"fr:ready"})
        )
        assert url == "https://gitlab.com/g/p/-/issues/9"

    def test_edit_issue_labels_delegates_to_swap(self, monkeypatch):
        captured: list[dict] = []
        monkeypatch.setattr(_glab, "swap_issue_labels", lambda **kw: captured.append(kw))
        RealGlabClient().edit_issue_labels(
            "group/proj", 42, add=frozenset({"pr-ready"}), remove=frozenset({"fr:ready"})
        )
        assert captured == [
            {"repo": "group/proj", "number": 42, "add": ["pr-ready"], "remove": ["fr:ready"]}
        ]

    def test_edit_issue_body_delegates(self, monkeypatch):
        captured: list[dict] = []
        monkeypatch.setattr(_glab, "edit_issue_body", lambda **kw: captured.append(kw))
        RealGlabClient().edit_issue_body("group/proj", 42, "new body")
        assert captured == [{"repo": "group/proj", "number": 42, "body": "new body"}]

    def test_ensure_labels_delegates(self, monkeypatch):
        from fr.labels import LabelDef

        captured: list[dict] = []
        monkeypatch.setattr(_glab, "ensure_labels", lambda **kw: captured.append(kw))
        defs = [LabelDef("fr:ready", "0E8AE6", "queued")]
        RealGlabClient().ensure_labels("group/proj", defs)
        assert captured == [{"repo": "group/proj", "labels": defs}]


class TestContentsApi:
    def test_file_exists_true_on_success(self, monkeypatch):
        monkeypatch.setattr(_glab, "_run_glab", lambda args: json.dumps({"content": "eA=="}))
        assert RealGlabClient().file_exists("group/proj", "docs/x.md") is True

    def test_file_exists_false_on_error(self, monkeypatch):
        def _raise(args):
            raise _glab.GlabError("404")

        monkeypatch.setattr(_glab, "_run_glab", _raise)
        assert RealGlabClient().file_exists("group/proj", "docs/missing.md") is False

    def test_read_file_decodes_base64_content(self, monkeypatch):
        import base64

        encoded = base64.b64encode(b"hello world").decode("ascii")
        monkeypatch.setattr(
            _glab, "_run_glab", lambda args: json.dumps({"content": encoded, "encoding": "base64"})
        )
        assert RealGlabClient().read_file("group/proj", "docs/x.md") == "hello world"

    def test_list_dir_returns_names(self, monkeypatch):
        response = json.dumps(
            [
                {"name": "01.yaml", "type": "blob"},
                {"name": "02.yaml", "type": "blob"},
            ]
        )
        monkeypatch.setattr(_glab, "_run_glab", lambda args: response)
        assert RealGlabClient().list_dir("group/proj", "docs/plan") == ["01.yaml", "02.yaml"]

    def test_list_dir_empty_on_error(self, monkeypatch):
        def _raise(args):
            raise _glab.GlabError("404")

        monkeypatch.setattr(_glab, "_run_glab", _raise)
        assert RealGlabClient().list_dir("group/proj", "docs/missing") == []


class TestPrStatusByUrl:
    """`glab mr view` does NOT take a bare URL (its usage is `{<id> |
    <branch>}` per its own `--help`, verified directly against the
    installed binary) — the adapter must parse the MR url into (repo, iid)
    itself first, then call `glab mr view <iid> -R <repo>`."""

    def test_parses_url_and_calls_mr_view_by_iid(self, monkeypatch):
        captured: list[list[str]] = []

        def fake(args: list[str]) -> str:
            captured.append(args)
            return json.dumps({"state": "opened", "draft": False})

        monkeypatch.setattr(_glab, "_run_glab", fake)
        result = RealGlabClient().pr_status_by_url(
            "https://gitlab.com/group/proj/-/merge_requests/7"
        )
        assert result == {"state": "OPEN", "draft": False}
        assert captured == [["mr", "view", "7", "--repo", "group/proj", "--output", "json"]]

    def test_nested_group_url(self, monkeypatch):
        captured: list[list[str]] = []

        def fake(args: list[str]) -> str:
            captured.append(args)
            return json.dumps({"state": "opened", "draft": False})

        monkeypatch.setattr(_glab, "_run_glab", fake)
        RealGlabClient().pr_status_by_url(
            "https://gitlab.com/group/subgroup/proj/-/merge_requests/3"
        )
        assert captured[0][:5] == ["mr", "view", "3", "--repo", "group/subgroup/proj"]

    def test_merged_state(self, monkeypatch):
        monkeypatch.setattr(
            _glab, "_run_glab", lambda args: json.dumps({"state": "merged", "draft": False})
        )
        result = RealGlabClient().pr_status_by_url(
            "https://gitlab.com/group/proj/-/merge_requests/7"
        )
        assert result == {"state": "MERGED", "draft": False}

    def test_closed_unmerged_state(self, monkeypatch):
        monkeypatch.setattr(
            _glab, "_run_glab", lambda args: json.dumps({"state": "closed", "draft": False})
        )
        result = RealGlabClient().pr_status_by_url(
            "https://gitlab.com/group/proj/-/merge_requests/7"
        )
        assert result == {"state": "CLOSED", "draft": False}

    def test_returns_none_on_error(self, monkeypatch):
        def _raise(args):
            raise _glab.GlabError("not found")

        monkeypatch.setattr(_glab, "_run_glab", _raise)
        assert (
            RealGlabClient().pr_status_by_url("https://gitlab.com/group/proj/-/merge_requests/999")
            is None
        )

    def test_returns_none_on_unparseable_url(self):
        assert RealGlabClient().pr_status_by_url("https://example.com/not/an/mr") is None
