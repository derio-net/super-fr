"""Integration tests for ``vk plan rework-add``."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from vk.cli import app
from vk.plan.rework import parse_origin_table

FIXTURES = Path(__file__).parent.parent / "fixtures/rework"


def _rework_file(tmp_path: Path, fixture: str = "rework_empty.md") -> Path:
    target = tmp_path / "docs/superpowers/plans/2026-04-08-foo-rework-1.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(FIXTURES / fixture, target)
    return target


def test_rework_add_happy_path(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    path = _rework_file(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "plan",
            "rework-add",
            str(path),
            "--item",
            "Ship the docs",
            "--source",
            "PR #42",
            "--track",
            "development",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    assert "Added Origin row #1" in result.stdout
    rows = parse_origin_table(path)
    assert len(rows) == 1
    assert rows[0].item == "Ship the docs"
    assert rows[0].track == "development"


def test_rework_add_canonical_track_no_warn(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    path = _rework_file(tmp_path)
    runner = CliRunner()
    for tok in ("development", "operations", "decision"):
        result = runner.invoke(
            app,
            [
                "plan",
                "rework-add",
                str(path),
                "--item",
                "x",
                "--source",
                "y",
                "--track",
                tok,
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert "not a canonical token" not in result.stderr


def test_rework_add_non_canonical_track_warns(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    path = _rework_file(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "plan",
            "rework-add",
            str(path),
            "--item",
            "x",
            "--source",
            "y",
            "--track",
            "research",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert "not a canonical token" in result.stderr


@pytest.mark.parametrize(
    "item,source,track",
    [
        ("", "y", "development"),
        ("   ", "y", "development"),
        ("x", "", "development"),
        ("x", "y", "   "),
    ],
)
def test_rework_add_empty_flag_exits_2(tmp_path: Path, monkeypatch, item, source, track) -> None:
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    path = _rework_file(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "plan",
            "rework-add",
            str(path),
            "--item",
            item,
            "--source",
            source,
            "--track",
            track,
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 2
    assert "is required and must be non-empty" in result.stderr


def test_rework_add_newline_rejected(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    path = _rework_file(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "plan",
            "rework-add",
            str(path),
            "--item",
            "line1\nline2",
            "--source",
            "y",
            "--track",
            "development",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 2
    assert "must not contain newlines" in result.stderr


def test_rework_add_pipe_escape_roundtrip(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    path = _rework_file(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "plan",
            "rework-add",
            str(path),
            "--item",
            "wire | pipe",
            "--source",
            "y",
            "--track",
            "development",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    # File contains escaped pipe.
    assert r"wire \| pipe" in path.read_text()
    # Round-trip unescapes.
    assert parse_origin_table(path)[0].item == "wire | pipe"


def test_rework_add_missing_origin_exits_2(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    path = tmp_path / "docs/superpowers/plans/2026-04-08-foo-rework-1.md"
    path.parent.mkdir(parents=True)
    path.write_text("# No Origin here\n\n**Status:** Not Started\n**Goal:** g\n")
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "plan",
            "rework-add",
            str(path),
            "--item",
            "x",
            "--source",
            "y",
            "--track",
            "development",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 2
    assert "no ## Origin section" in result.stderr


def test_rework_add_malformed_origin_exits_2(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    path = _rework_file(tmp_path, "rework_malformed_origin.md")
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "plan",
            "rework-add",
            str(path),
            "--item",
            "x",
            "--source",
            "y",
            "--track",
            "development",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 2
    assert "Origin table header malformed" in result.stderr
