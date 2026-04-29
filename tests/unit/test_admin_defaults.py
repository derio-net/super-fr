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
        # "bug" has 5 Issues attached — must produce no remove action at all
        assert actions == []

    def test_non_default_label_ignored(self, monkeypatch: pytest.MonkeyPatch) -> None:
        existing = [_existing("custom-label")]
        monkeypatch.setattr(gh, "count_issues_with_label", lambda *, repo, name: 0)
        actions = _default_label_actions(repo="o/r", existing=existing)
        assert actions == []

    def test_default_label_matched_case_insensitively(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # GitHub creates defaults as lowercase, but defensive matching should
        # treat "Bug" and "bug" as the same default label.
        existing = [_existing("Bug")]
        monkeypatch.setattr(gh, "count_issues_with_label", lambda *, repo, name: 0)
        actions = _default_label_actions(repo="o/r", existing=existing)
        assert len(actions) == 1
        assert actions[0].kind == "remove"
        assert actions[0].name == "Bug"  # original casing preserved in action

    def test_null_description_handled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # GitHub returns {"description": null} for labels with no description.
        existing = [{"name": "bug", "color": "d73a4a", "description": None}]
        monkeypatch.setattr(gh, "count_issues_with_label", lambda *, repo, name: 0)
        actions = _default_label_actions(repo="o/r", existing=existing)
        assert len(actions) == 1
        assert actions[0].old_desc == ""  # None coerced to ""
