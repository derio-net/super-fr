"""Tests for apply mode — verifies gh calls dispatch correctly."""

import pytest
from typer.testing import CliRunner

from vk import gh
from vk.commands.admin_cmd import admin_app

runner = CliRunner()


def _stub(
    monkeypatch: pytest.MonkeyPatch,
    existing_labels: list[dict],
    ensure_calls: list[dict],
    delete_calls: list[dict],
) -> None:
    monkeypatch.setattr(gh, "list_repos", lambda *, owner: [{"name": "r"}])
    monkeypatch.setattr(gh, "list_labels", lambda *, repo: existing_labels)
    monkeypatch.setattr(gh, "count_issues_with_label", lambda *, repo, name: 0)

    def fake_ensure(*, repo, name, color="", description=""):
        ensure_calls.append(
            {"repo": repo, "name": name, "color": color, "description": description}
        )

    monkeypatch.setattr(gh, "ensure_label", fake_ensure)

    def fake_delete(*, repo, name):
        delete_calls.append({"repo": repo, "name": name})

    monkeypatch.setattr(gh, "delete_label", fake_delete)


class TestApplyCreatesMissingLabels:
    def test_yes_flag_invokes_ensure_label_for_creates(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ensure_calls: list[dict] = []
        delete_calls: list[dict] = []
        _stub(
            monkeypatch,
            existing_labels=[],
            ensure_calls=ensure_calls,
            delete_calls=delete_calls,
        )
        result = runner.invoke(
            admin_app,
            ["labels-sync", "--owner", "o", "--repo", "r", "--yes"],
        )
        assert result.exit_code == 0
        names_called = {c["name"] for c in ensure_calls}
        assert names_called == {"vk-ready", "manual", "in-progress", "pr-ready"}


class TestApplyRemovesUnusedDefaults:
    def test_remove_defaults_invokes_delete_label(self, monkeypatch: pytest.MonkeyPatch) -> None:
        ensure_calls: list[dict] = []
        delete_calls: list[dict] = []
        _stub(
            monkeypatch,
            existing_labels=[{"name": "bug", "color": "d73a4a", "description": ""}],
            ensure_calls=ensure_calls,
            delete_calls=delete_calls,
        )
        result = runner.invoke(
            admin_app,
            [
                "labels-sync",
                "--owner",
                "o",
                "--repo",
                "r",
                "--remove-defaults",
                "--yes",
            ],
        )
        assert result.exit_code == 0
        assert {"repo": "o/r", "name": "bug"} in delete_calls


class TestApplyPerRepoErrorIsNonFatal:
    def test_one_repo_error_does_not_abort_others(self, monkeypatch: pytest.MonkeyPatch) -> None:
        repos = [{"name": "good"}, {"name": "bad"}, {"name": "good2"}]
        monkeypatch.setattr(gh, "list_repos", lambda *, owner: repos)

        def fake_list_labels(*, repo: str) -> list[dict]:
            if repo.endswith("/bad"):
                raise gh.GhError("HTTP 403", stderr="HTTP 403", returncode=1)
            return []

        monkeypatch.setattr(gh, "list_labels", fake_list_labels)
        monkeypatch.setattr(gh, "count_issues_with_label", lambda *, repo, name: 0)
        monkeypatch.setattr(gh, "ensure_label", lambda **kw: None)
        monkeypatch.setattr(gh, "delete_label", lambda **kw: None)

        result = runner.invoke(
            admin_app,
            ["labels-sync", "--owner", "o", "--yes"],
        )
        # Non-zero because one repo failed
        assert result.exit_code != 0
        # Error goes to stderr; combine streams to check the message
        combined = result.stdout + (result.stderr or "")
        assert "bad" in combined
        # o/good and o/good2 must still have been processed (loop continued
        # past the failing repo) — their per-repo summary lines confirm it
        assert "o/good:" in result.stdout
        assert "o/good2:" in result.stdout
