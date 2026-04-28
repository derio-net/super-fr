"""Tests for the repo-enumeration helper used by vk admin labels-sync."""

import pytest

from vk import gh
from vk.commands.admin_cmd import _resolve_target_repos


class TestResolveTargetReposExplicit:
    def test_single_repo_skips_listing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        called = {"n": 0}

        def fake_list(*, owner: str) -> list:
            called["n"] += 1
            return []

        monkeypatch.setattr(gh, "list_repos", fake_list)
        result = _resolve_target_repos(owner="derio-net", repo="frank")
        assert result == ["derio-net/frank"]
        assert called["n"] == 0  # never called list_repos


class TestResolveTargetReposOrgWide:
    def test_lists_all_non_archived(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            gh, "list_repos", lambda *, owner: [{"name": "frank"}, {"name": "willikins"}]
        )
        result = _resolve_target_repos(owner="derio-net", repo=None)
        assert result == ["derio-net/frank", "derio-net/willikins"]
