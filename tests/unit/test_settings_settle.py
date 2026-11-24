"""`git.settle` in the settings model (spec 2026-11-23-pr-readiness-wait R1)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fr.cli import app
from fr.settings import SettingsError
from fr.settings.model import SETTLE_MODES, parse_settings
from typer.testing import CliRunner

from tests.unit.settings_repo import make_repo

runner = CliRunner()


def test_both_settle_keys_default_to_fix() -> None:
    s = parse_settings({}, source="x")
    assert s.git.settle.conflicts == "fix"
    assert s.git.settle.ci == "fix"


def test_the_settle_modes_are_stated_once() -> None:
    assert frozenset({"off", "report", "fix"}) == SETTLE_MODES


@pytest.mark.parametrize("mode", ["off", "report", "fix"])
@pytest.mark.parametrize("key", ["conflicts", "ci"])
def test_every_settle_mode_parses(key: str, mode: str) -> None:
    s = parse_settings({"git": {"settle": {key: mode}}}, source="x")
    assert getattr(s.git.settle, key) == mode


@pytest.mark.parametrize("value", ["on", "wait", "", 1, True, False, None])
@pytest.mark.parametrize("key", ["conflicts", "ci"])
def test_any_other_settle_value_is_refused_naming_the_key(key: str, value: Any) -> None:
    with pytest.raises(SettingsError, match=rf"git\.settle\.{key}"):
        parse_settings({"git": {"settle": {key: value}}}, source=".fr/settings.yaml")


def test_an_unknown_settle_key_is_refused() -> None:
    with pytest.raises(SettingsError, match=r"git\.settle\.bogus"):
        parse_settings({"git": {"settle": {"bogus": "fix"}}}, source="x")


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = make_repo(tmp_path)
    monkeypatch.setenv("FR_REPO_ROOT", str(root))
    return root


def test_show_json_lists_both_settle_keys_at_their_default(repo: Path) -> None:
    result = runner.invoke(app, ["settings", "show", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["git.settle.conflicts"] == {"value": "fix", "source": "default"}
    assert data["git.settle.ci"] == {"value": "fix", "source": "default"}


def test_init_documents_both_settle_keys_with_their_allowed_values(repo: Path) -> None:
    result = runner.invoke(app, ["settings", "init"])
    assert result.exit_code == 0, result.output
    text = (repo / ".fr" / "settings.yaml").read_text()
    assert "settle:" in text
    assert "conflicts: fix" in text and "ci: fix" in text
    assert "Allowed: fix, off, report" in text
