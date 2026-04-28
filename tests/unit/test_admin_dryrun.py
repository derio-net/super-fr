"""Tests for dry-run rendering — verify the table contains expected rows."""

import pytest
from typer.testing import CliRunner

from vk import gh, labels
from vk.commands.admin_cmd import admin_app

runner = CliRunner()


def _patch_minimal_repo(
    monkeypatch: pytest.MonkeyPatch,
    existing_labels: list[dict],
) -> None:
    monkeypatch.setattr(gh, "list_repos", lambda *, owner: [{"name": "r"}])
    monkeypatch.setattr(gh, "list_labels", lambda *, repo: existing_labels)
    monkeypatch.setattr(gh, "count_issues_with_label", lambda *, repo, name: 0)


class TestDryRunRendersActions:
    def test_create_appears_when_label_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_minimal_repo(monkeypatch, existing_labels=[])
        result = runner.invoke(
            admin_app,
            ["labels-sync", "--owner", "o", "--repo", "r", "--dry-run"],
        )
        assert result.exit_code == 0
        for ld in (labels.VK_READY, labels.IN_PROGRESS, labels.PR_READY):
            assert ld.name in result.stdout
            assert "create" in result.stdout

    def test_unchanged_when_correct(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_minimal_repo(
            monkeypatch,
            existing_labels=[
                {"name": ld.name, "color": ld.color, "description": ld.description}
                for ld in labels.LIFECYCLE.values()
            ],
        )
        result = runner.invoke(
            admin_app,
            ["labels-sync", "--owner", "o", "--repo", "r", "--dry-run"],
        )
        assert result.exit_code == 0
        assert "unchanged" in result.stdout.lower() or "= already correct" in result.stdout.lower()
