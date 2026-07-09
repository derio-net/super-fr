"""Tests for fr_vk._cardref — consolidated VK card-title tag parsing.

Replaces 5+ independent regex copies across pr_state.py/workspaces.py/
dispatch.py (see docs/superpowers/specs/
2026-07-09-multi-backend-git-host-adapters-design.md §2). The wire format
stays "{tag}#{n}: [{repo}]" — existing GitHub cards must keep parsing
unchanged (backward compatibility for cards already on production VK
boards is load-bearing, not optional).
"""

from __future__ import annotations

from fr_vk._cardref import BACKEND_FOR_TAG, TAG_FOR_BACKEND, build_card_title, parse_card_title


class TestParseCardTitle:
    def test_existing_github_card_parses_unchanged(self) -> None:
        assert parse_card_title("gh#42: [owner/repo]") == ("gh", "owner/repo", 42)

    def test_gitlab_card(self) -> None:
        assert parse_card_title("gl#7: [group/proj]") == ("gl", "group/proj", 7)

    def test_gitea_card(self) -> None:
        assert parse_card_title("gt#3: [owner/repo]") == ("gt", "owner/repo", 3)

    def test_nested_gitlab_group_repo(self) -> None:
        assert parse_card_title("gl#7: [group/subgroup/proj]") == (
            "gl",
            "group/subgroup/proj",
            7,
        )

    def test_title_with_trailing_free_text_still_parses_prefix(self) -> None:
        """The renderer's title is `{tag}#{n}: [{repo}]` at minimum, but
        historically callers only anchor the prefix — a free-text suffix
        must not break the parse."""
        assert parse_card_title("gh#42: [owner/repo] extra operator text") == (
            "gh",
            "owner/repo",
            42,
        )

    def test_non_matching_title_returns_none(self) -> None:
        assert parse_card_title("just a normal card title") is None

    def test_empty_title_returns_none(self) -> None:
        assert parse_card_title("") is None


class TestBuildCardTitle:
    def test_github_default_tag(self) -> None:
        assert build_card_title("github", "owner/repo", 42) == "gh#42: [owner/repo]"

    def test_gitlab_tag(self) -> None:
        assert build_card_title("gitlab", "group/proj", 7) == "gl#7: [group/proj]"

    def test_gitea_tag(self) -> None:
        assert build_card_title("gitea", "owner/repo", 3) == "gt#3: [owner/repo]"

    def test_round_trips_through_parse(self) -> None:
        title = build_card_title("gitlab", "group/subgroup/proj", 9)
        assert parse_card_title(title) == ("gl", "group/subgroup/proj", 9)


def test_tag_and_backend_maps_are_inverses() -> None:
    assert BACKEND_FOR_TAG == {v: k for k, v in TAG_FOR_BACKEND.items()}
    assert TAG_FOR_BACKEND == {"github": "gh", "gitlab": "gl", "gitea": "gt"}
