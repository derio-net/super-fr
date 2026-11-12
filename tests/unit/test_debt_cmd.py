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

from tests.unit.acceptance_helpers import write_matrix_fragments

runner = CliRunner()


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    rows = [
        {"id": "a", "capability": "c", "acceptance": "does a", "status": "unwired"},
        {"id": "b", "capability": "c", "acceptance": "does b", "status": "ci"},
    ]
    write_matrix_fragments(
        tmp_path, yaml.safe_dump({"schema_version": 5, "org": "o", "repo": "r", "rows": rows})
    )
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


def test_tracking_none_means_git_only_and_says_why(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import types

    monkeypatch.setattr(
        "fr.services.resolve.resolve_tracking", lambda *_a, **_k: types.SimpleNamespace(type="none")
    )
    forge, why = debt_cmd._forge(repo)
    assert forge is None and why.startswith("tracking: none")
    r = runner.invoke(app, ["debt", "--json"])
    assert r.exit_code == 0, r.output
    report = DebtReport.model_validate(json.loads(r.output))
    assert report.sources["forge"].why.startswith("tracking: none")


def test_p3_r7_forge_issues_off_keeps_the_forge_reads(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R9: reads are never gated. `forge.issues: off` stops `fr debt issue` writing; the
    report still reads the forge."""
    import types

    from fr.settings.model import parse_settings

    quiet = parse_settings({"forge": {"issues": "off"}}, source="test")
    monkeypatch.setattr(
        "fr.settings.load_settings", lambda _root: types.SimpleNamespace(settings=quiet)
    )
    monkeypatch.setattr(
        "fr.services.resolve.resolve_tracking",
        lambda *_a, **_k: types.SimpleNamespace(type="github"),
    )
    monkeypatch.setattr("fr._hosts.origin_slug", lambda _root: "o/r")
    monkeypatch.setattr("fr.commands.archive_cmd._make_gh_client", lambda: object())
    forge, why = debt_cmd._forge(repo)
    assert forge is not None and why == ""


def test_a_repo_without_a_remote_says_so_rather_than_offline(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import types

    monkeypatch.setattr(
        "fr.services.resolve.resolve_tracking",
        lambda *_a, **_k: types.SimpleNamespace(type="github"),
    )
    forge, why = debt_cmd._forge(repo)
    assert forge is None and "origin" in why


def test_an_unreadable_matrix_does_not_drop_the_forge(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import types

    write_matrix_fragments(repo, "not: [valid")
    monkeypatch.setattr(
        "fr.services.resolve.resolve_tracking",
        lambda *_a, **_k: types.SimpleNamespace(type="github"),
    )
    monkeypatch.setattr("fr._hosts.origin_slug", lambda _root: "o/r")
    monkeypatch.setattr(debt_cmd, "_make_gh_client", lambda: object(), raising=False)
    monkeypatch.setattr("fr.commands.archive_cmd._make_gh_client", lambda: object())
    forge, why = debt_cmd._forge(repo)
    assert forge is not None and why == ""
