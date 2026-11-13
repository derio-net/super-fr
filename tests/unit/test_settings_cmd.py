"""`fr settings init|show|check` (spec R3)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from fr.cli import app
from fr.settings.model import parse_settings
from typer.testing import CliRunner

from tests.unit.settings_repo import land_on_main, make_repo

runner = CliRunner()


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = make_repo(tmp_path)
    monkeypatch.setenv("FR_REPO_ROOT", str(root))
    return root


def test_init_writes_every_key_commented_out_at_its_default(repo: Path) -> None:
    result = runner.invoke(app, ["settings", "init"])
    assert result.exit_code == 0, result.output
    text = (repo / ".fr" / "settings.yaml").read_text()
    live = [ln for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    assert live == []
    assert parse_settings(yaml.safe_load(text), source="x") == parse_settings({}, source="x")
    for key in (
        "schema",
        "placement",
        "acceptance",
        "test_plan",
        "gates",
        "labels",
        "comments",
        "issues",
        "pr_body",
        "report_comment",
        "push",
        "pr",
        "history",
        "with_issue",
        "without_issue",
    ):
        assert f"{key}:" in text, key
    assert "Allowed: off, on" in text
    assert "Allowed: full, minimal" in text
    assert "Default:" in text and "Off:" in text


def test_the_commented_file_uncommented_still_parses_to_the_defaults(repo: Path) -> None:
    runner.invoke(app, ["settings", "init"])
    text = (repo / ".fr" / "settings.yaml").read_text()
    lines = [
        ln[1:] if ln.startswith("#") and not ln.startswith("##") else ln for ln in text.splitlines()
    ]
    assert parse_settings(yaml.safe_load("\n".join(lines)), source="x") == parse_settings(
        {}, source="x"
    )


def test_init_does_not_commit_and_refuses_to_overwrite(repo: Path) -> None:
    runner.invoke(app, ["settings", "init"])
    again = runner.invoke(app, ["settings", "init"])
    assert again.exit_code == 2
    assert "--force" in again.output
    forced = runner.invoke(app, ["settings", "init", "--force"])
    assert forced.exit_code == 0


def test_show_prints_key_value_source(repo: Path) -> None:
    land_on_main(repo, "git:\n  push: ask\n")
    result = runner.invoke(app, ["settings", "show"])
    assert result.exit_code == 0, result.output
    row = next(ln for ln in result.output.splitlines() if "git.push" in ln)
    assert "ask" in row and "repo" in row
    row = next(ln for ln in result.output.splitlines() if "git.pr " in ln or "git.pr\t" in ln)
    assert "default" in row


def test_show_json(repo: Path) -> None:
    land_on_main(repo, "git:\n  push: ask\n")
    result = runner.invoke(app, ["settings", "show", "--json"])
    data = json.loads(result.output)
    assert data["git.push"] == {"value": "ask", "source": "repo"}
    assert data["forge.labels"] == {"value": "on", "source": "default"}


def test_show_notes_a_pending_edit(repo: Path) -> None:
    (repo / ".fr").mkdir()
    (repo / ".fr" / "settings.yaml").write_text("git:\n  push: ask\n")
    result = runner.invoke(app, ["settings", "show"])
    assert "no effect until it lands" in result.output.replace("\n", " ")


def test_show_refuses_a_bad_file(repo: Path) -> None:
    land_on_main(repo, "forge:\n  nope: on\n")
    result = runner.invoke(app, ["settings", "show"])
    assert result.exit_code == 2
    assert "forge.nope" in result.output


def test_check_exits_0_when_coherent_and_2_listing_problems(repo: Path) -> None:
    assert runner.invoke(app, ["settings", "check"]).exit_code == 0
    land_on_main(repo, "forge:\n  comments: off\n  report_comment: on\n")
    result = runner.invoke(app, ["settings", "check"])
    assert result.exit_code == 2
    assert "report_comment" in result.output


def test_check_refuses_stealth_in_repo_settings(repo: Path) -> None:
    land_on_main(repo, "placement: stealth\n")
    result = runner.invoke(app, ["settings", "check"])
    assert result.exit_code == 2
    assert "chosen per run" in " ".join(result.output.split())


def test_settings_is_read_only_for_the_migration_gate() -> None:
    from fr.artifacts import trigger

    assert "settings" in trigger.READ_ONLY_COMMANDS


def test_show_does_not_truncate_long_values(repo: Path) -> None:
    long = "{type}(" + "{scope}" * 12 + "): {summary} (#{issue})"
    land_on_main(repo, f"git:\n  commit:\n    with_issue: '{long}'\n")
    result = runner.invoke(app, ["settings", "show"])
    assert result.exit_code == 0, result.output
    assert long in result.output.replace("\n", "")


def test_show_names_the_policy_source(repo: Path) -> None:
    result = runner.invoke(app, ["settings", "show"])
    assert result.exit_code == 0, result.output
    assert "policy source: remote (refs/remotes/origin/main)" in result.output
