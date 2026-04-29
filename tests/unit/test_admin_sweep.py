"""Behavioral tests for vk admin labels-sync sweep semantics.

Covers: per-repo error accumulation, --yes activating apply path,
and empty repo list exit.
"""

import pytest
from typer.testing import CliRunner

from vk import gh
from vk.commands.admin_cmd import admin_app

runner = CliRunner()


class TestPerRepoErrorAccumulation:
    """Per-repo errors must be non-blocking — spec requirement."""

    def test_one_failing_repo_does_not_abort_others(self, monkeypatch: pytest.MonkeyPatch) -> None:
        repos = [{"name": "good1"}, {"name": "bad"}, {"name": "good2"}]
        monkeypatch.setattr(gh, "list_repos", lambda *, owner: repos)

        def fake_list_labels(*, repo: str) -> list[dict]:
            if repo.endswith("/bad"):
                raise gh.GhError("HTTP 403", stderr="HTTP 403", returncode=1)
            return []

        monkeypatch.setattr(gh, "list_labels", fake_list_labels)
        result = runner.invoke(admin_app, ["labels-sync", "--owner", "o", "--dry-run"])
        # Bad repo error must be reported
        combined = result.stdout + (result.stderr or "")
        assert "bad" in combined
        # Exit code must be non-zero because one repo failed
        assert result.exit_code != 0
        # Good repos must still appear in output (not aborted)
        assert "o/good1" in result.stdout
        assert "o/good2" in result.stdout

    def test_remove_defaults_gh_error_is_non_blocking(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """GhError inside count_issues_with_label must not abort the sweep."""
        repos = [{"name": "good"}, {"name": "bad"}]
        monkeypatch.setattr(gh, "list_repos", lambda *, owner: repos)
        # Both repos have a default label present so count_issues_with_label fires
        monkeypatch.setattr(
            gh,
            "list_labels",
            lambda *, repo: [{"name": "bug", "color": "d73a4a", "description": None}],
        )

        def fake_count(*, repo: str, name: str) -> int:
            if repo.endswith("/bad"):
                raise gh.GhError("HTTP 403", stderr="HTTP 403", returncode=1)
            return 0

        monkeypatch.setattr(gh, "count_issues_with_label", fake_count)

        result = runner.invoke(
            admin_app,
            ["labels-sync", "--owner", "o", "--remove-defaults", "--dry-run"],
        )
        # good repo must still appear despite bad repo failing count_issues
        assert "o/good" in result.stdout
        assert result.exit_code != 0

    def test_all_repos_succeed_exit_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(gh, "list_repos", lambda *, owner: [{"name": "r"}])
        monkeypatch.setattr(gh, "list_labels", lambda *, repo: [])
        result = runner.invoke(admin_app, ["labels-sync", "--owner", "o", "--dry-run"])
        assert result.exit_code == 0


class TestYesFlag:
    def test_yes_flag_enters_apply_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """--yes must bypass dry-run and hit the apply path (NotImplementedError stub)."""
        monkeypatch.setattr(gh, "list_repos", lambda *, owner: [{"name": "r"}])
        monkeypatch.setattr(gh, "list_labels", lambda *, repo: [])
        result = runner.invoke(admin_app, ["labels-sync", "--owner", "o", "--repo", "r", "--yes"])
        # Apply mode is stubbed for Phase 3; confirm --yes reaches it
        assert isinstance(result.exception, NotImplementedError)


class TestEmptyRepoList:
    def test_no_repos_found_exits_nonzero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(gh, "list_repos", lambda *, owner: [])
        result = runner.invoke(admin_app, ["labels-sync", "--owner", "o"])
        assert result.exit_code != 0
        combined = result.stdout + (result.stderr or "")
        assert "No repos found" in combined
