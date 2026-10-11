"""`fr debt` and the digest it feeds (spec 2026-10-11-debt-engine R1, R25)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import yaml
from fr.artifacts import trigger
from fr.cli import app
from fr.commands import debt_cmd
from fr.debt.model import DebtReport
from typer.testing import CliRunner

runner = CliRunner()


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    m = tmp_path / "docs" / "acceptance" / "matrix.yaml"
    m.parent.mkdir(parents=True)
    rows = [
        {"id": "a", "capability": "c", "acceptance": "does a", "status": "unwired"},
        {"id": "b", "capability": "c", "acceptance": "does b", "status": "ci"},
    ]
    m.write_text(yaml.safe_dump({"schema_version": 5, "org": "o", "repo": "r", "rows": rows}))
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    monkeypatch.setenv("FR_SKIP_MIGRATION", "1")
    monkeypatch.setattr(debt_cmd, "_now", lambda: datetime(2026, 10, 11, tzinfo=UTC))
    return tmp_path


def test_text_report(repo: Path) -> None:
    r = runner.invoke(app, ["debt", "--offline"])
    assert r.exit_code == 0, r.output
    assert "Acceptance:" in r.output and "a [unwired]" in r.output


def test_json_validates_as_a_debt_report(repo: Path) -> None:
    r = runner.invoke(app, ["debt", "--json", "--offline"])
    assert r.exit_code == 0, r.output
    report = DebtReport.model_validate(json.loads(r.output))
    assert report.acceptance.by_status == {"unwired": 1, "ci": 1}
    assert report.sources["forge"].state == "unavailable"


def test_offline_never_builds_a_forge(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(_root: Path) -> Any:
        raise AssertionError("forge touched offline")

    monkeypatch.setattr(debt_cmd, "_forge", boom)
    assert runner.invoke(app, ["debt", "--offline"]).exit_code == 0


def test_a_bad_config_is_a_usage_error(repo: Path) -> None:
    (repo / ".fr").mkdir()
    (repo / ".fr" / "debt.yaml").write_text("nope: 1\n")
    r = runner.invoke(app, ["debt", "--offline"])
    assert r.exit_code == 2 and "nope" in r.output


def test_debt_is_a_read_only_command() -> None:
    assert "debt" in trigger.READ_ONLY_COMMANDS


def test_digest_renders_the_acceptance_section_with_the_legacy_marker(repo: Path) -> None:
    r = runner.invoke(app, ["acceptance", "digest"])
    assert r.exit_code == 0, r.output
    assert r.output.startswith("## Acceptance debt")
    assert "| a | unwired |" in r.output
    assert "<!-- fr-acceptance-digest -->" in r.output
