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
        assert parse_issue_url("https://gitlab.com/group/subgroup/proj/-/issues/9") == (
            "group/subgroup/proj",
            9,
        )

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


class TestGitLabWorkItemUrls:
    """GitLab's work-items migration: its API returns an Issue's `web_url` as
    `.../-/work_items/N`, not `.../-/issues/N`.

    Captured live 2026-09-19 against a self-hosted GitLab, and verified
    against the REST API directly rather than off glab's stdout:
    `GET projects/:id/issues` reports `type: ISSUE` with
    `web_url: .../-/work_items/2`. So this is GitLab's shape, not a glab
    quirk, and gitlab.com is affected equally.

    Before this was handled, `fr apply` against any GitLab repo worked
    exactly ONCE: the first run created the Issues, and every run after it
    died in `observe` re-reading the tracking_issue URLs it had itself
    stored (gh-486 phase 7, found by the live walk that unit tests
    structurally could not perform).
    """

    LIVE = "https://gitlab.local.gebit.de/IDermitzakis/devops-scripts/-/work_items/1"

    def test_the_url_gitlab_actually_returns_parses(self) -> None:
        assert parse_issue_url(self.LIVE) == ("IDermitzakis/devops-scripts", 1)

    def test_a_subgrouped_work_item_url_parses(self) -> None:
        assert parse_issue_url("https://gitlab.corp/group/sub/proj/-/work_items/42") == (
            "group/sub/proj",
            42,
        )

    def test_the_number_helper_reads_a_work_item_url(self) -> None:
        assert issue_number(self.LIVE) == 1
        assert issue_number("https://gitlab.corp/g/p/-/work_items/42/") == 42

    def test_the_classic_issues_shape_is_untouched(self) -> None:
        """GitHub, Gitea and older GitLab must keep working."""
        assert parse_issue_url("https://github.com/o/r/issues/7") == ("o/r", 7)
        assert parse_issue_url("https://gitlab.corp/g/p/-/issues/7") == ("g/p", 7)
        assert issue_number("https://github.com/o/r/issues/7") == 7

    def test_a_repo_named_work_items_is_not_a_route(self) -> None:
        """A repo NAMED `work_items` must not be read as the route — the same
        anchoring lesson as `_hosts._URL_SHAPES` (finding f11)."""
        assert parse_issue_url("https://github.com/o/work_items/issues/3") == (
            "o/work_items",
            3,
        )
