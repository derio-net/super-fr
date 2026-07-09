"""fr._urls — shared URL parsing, now across GitHub/Gitea's `/issues/N` shape
and GitLab's `/-/issues/N` shape (see docs/superpowers/specs/
2026-07-09-multi-backend-git-host-adapters-design.md §2)."""

from __future__ import annotations

import pytest
from fr._urls import is_cross_repo_spec, issue_number, parse_issue_url


class TestParseIssueUrl:
    def test_github_shape(self) -> None:
        assert parse_issue_url("https://github.com/owner/repo/issues/142") == ("owner/repo", 142)

    def test_gitea_shape_matches_github(self) -> None:
        """Gitea's Issue URLs mirror GitHub's shape exactly — no `-/` infix."""
        assert parse_issue_url("https://gitea.example.com/owner/repo/issues/7") == (
            "owner/repo",
            7,
        )

    def test_gitea_com_shape(self) -> None:
        assert parse_issue_url("https://gitea.com/owner/repo/issues/3") == ("owner/repo", 3)

    def test_gitlab_shape_with_dash_infix(self) -> None:
        assert parse_issue_url("https://gitlab.example.com/group/proj/-/issues/42") == (
            "group/proj",
            42,
        )

    def test_gitlab_com_shape_with_dash_infix(self) -> None:
        assert parse_issue_url("https://gitlab.com/group/proj/-/issues/42") == ("group/proj", 42)

    def test_gitlab_nested_group_shape(self) -> None:
        """GitLab subgroups nest arbitrarily (group/subgroup/proj) — the
        repo-capturing group must not be greedy-limited to exactly one slash."""
        assert parse_issue_url(
            "https://gitlab.com/group/subgroup/proj/-/issues/9"
        ) == ("group/subgroup/proj", 9)

    def test_not_an_issue_url_raises(self) -> None:
        with pytest.raises(ValueError, match="not a tracking issue url"):
            parse_issue_url("https://example.com/not/an/issue")


class TestIssueNumber:
    def test_github_shape(self) -> None:
        assert issue_number("https://github.com/owner/repo/issues/142") == 142

    def test_gitlab_shape(self) -> None:
        assert issue_number("https://gitlab.com/group/proj/-/issues/42") == 42

    def test_gitea_shape(self) -> None:
        assert issue_number("https://gitea.example.com/owner/repo/issues/7") == 7

    def test_none_input(self) -> None:
        assert issue_number(None) is None

    def test_non_matching_url(self) -> None:
        assert issue_number("https://example.com/nope") is None


def test_is_cross_repo_spec_unaffected() -> None:
    """Regression guard — this function is untouched by the URL-shape work."""
    assert is_cross_repo_spec("owner/repo:docs/x.md") is True
    assert is_cross_repo_spec("docs/x.md") is False
