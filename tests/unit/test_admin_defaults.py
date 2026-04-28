"""Tests for default-label removal logic."""

import pytest

from vk import gh
from vk.commands.admin_cmd import _default_label_actions


def _existing(name: str) -> dict:
    return {"name": name, "color": "ededed", "description": ""}


class TestDefaultLabelActions:
    def test_default_with_zero_issues_yields_remove(self, monkeypatch: pytest.MonkeyPatch) -> None:
        existing = [_existing("bug"), _existing("documentation")]
        monkeypatch.setattr(gh, "count_issues_with_label", lambda *, repo, name: 0)
        actions = _default_label_actions(repo="o/r", existing=existing)
        kinds = {a.kind for a in actions}
        assert kinds == {"remove"}
        assert {a.name for a in actions} == {"bug", "documentation"}

    def test_default_with_issues_skipped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        existing = [_existing("bug")]
        monkeypatch.setattr(gh, "count_issues_with_label", lambda *, repo, name: 5)
        actions = _default_label_actions(repo="o/r", existing=existing)
        assert all(a.kind != "remove" for a in actions)

    def test_non_default_label_ignored(self, monkeypatch: pytest.MonkeyPatch) -> None:
        existing = [_existing("custom-label")]
        monkeypatch.setattr(gh, "count_issues_with_label", lambda *, repo, name: 0)
        actions = _default_label_actions(repo="o/r", existing=existing)
        assert actions == []
