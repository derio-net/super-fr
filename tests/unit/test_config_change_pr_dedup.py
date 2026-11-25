"""A configuration change is named by its kind, and a change whose pull request is already
open, or was closed unmerged, is not proposed again on every command (review finding
p4-r12; spec 2026-11-19-event-driven-a-la-carte §B).

Origins are LOCAL bare repos; the forge is the `fr.config.change.open_pr` and
`fr.config.change.prs_for_head` seams.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fr.config import change
from fr.config import migrate as m
from fr.settings import SettingsError

from tests.unit.test_migration_config_kinds import _quiet

TEXT = "opencode:\n  hard: m\n"


@pytest.fixture(autouse=True)
def _home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("FR_CONFIG_REPROPOSE", raising=False)


def _forge(monkeypatch: pytest.MonkeyPatch, existing: list[dict[str, Any]]) -> list[str]:
    opened: list[str] = []
    asked: list[str] = []

    def fake_open(remote: str, head: str, base: str, title: str, body: str) -> str:
        opened.append(head)
        return "https://example.com/pr/new"

    def fake_state(remote: str, head: str) -> list[dict[str, Any]]:
        asked.append(head)
        return existing

    monkeypatch.setattr(change, "open_pr", fake_open)
    monkeypatch.setattr(change, "prs_for_head", fake_state)
    return opened


def _root(tmp_path: Path) -> Path:
    root = _quiet(tmp_path)
    assert m.ensure_space(root)
    return root


def test_the_change_branch_names_the_kind() -> None:
    assert change.change_branch(".fr/settings.yaml", "x").startswith("fr-config-change/settings-")
    assert change.change_branch(".fr/models.yaml", "x").startswith("fr-config-change/models-")
    mine = change.change_branch("t/.fr/workflows/mine.yaml", "x")
    assert mine.startswith("fr-config-change/workflows-mine-")
    assert change.change_branch(".fr/models.yaml", "x") != change.change_branch(
        ".fr/models.yaml", "y"
    )


def test_an_open_pull_request_for_the_same_content_is_reused_not_reproposed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    opened = _forge(monkeypatch, [{"state": "OPEN", "url": "https://example.com/pr/7"}])
    url = m.QuietWriter(root).propose(".fr/models.yaml", TEXT, "chore(fr): models")
    assert url == "https://example.com/pr/7" and opened == []


def test_a_closed_unmerged_pull_request_refuses_naming_it_and_how_to_repropose(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    opened = _forge(monkeypatch, [{"state": "CLOSED", "url": "https://example.com/pr/7"}])
    with pytest.raises(SettingsError, match="--repropose") as refused:
        m.QuietWriter(root).propose(".fr/models.yaml", TEXT, "chore(fr): models")
    assert "https://example.com/pr/7" in str(refused.value) and opened == []

    monkeypatch.setenv("FR_CONFIG_REPROPOSE", "1")
    url = m.QuietWriter(root).propose(".fr/models.yaml", TEXT, "chore(fr): models")
    assert url == "https://example.com/pr/new" and len(opened) == 1


def test_a_merged_or_absent_pull_request_proposes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    opened = _forge(monkeypatch, [{"state": "MERGED", "url": "https://example.com/pr/7"}])
    assert m.QuietWriter(root).propose(".fr/models.yaml", TEXT, "m") == "https://example.com/pr/new"
    assert len(opened) == 1


def test_the_migrate_command_takes_repropose(tmp_path: Path) -> None:
    from fr.cli import app
    from typer.testing import CliRunner

    done = CliRunner().invoke(app, ["migrate", "artifacts", "--help"])
    assert "--repropose" in done.output
