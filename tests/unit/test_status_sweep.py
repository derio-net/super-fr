"""`fr status` with no PLAN_DIR — read-only repo-wide sweep that surfaces
archivable ("merged-but-unarchived") plans (#334).

Complements test_status_cmd.py (the per-plan report). The sweep is gh-free:
it consumes fr.archive.completed_unarchived_plans, so it needs no GitHub
observation and stays allowlist-safe / exit-0."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from fr.cli import app
from fr.commands import status_cmd
from typer.testing import CliRunner

from tests.unit.fakes import FakeGhClient

FIXTURE = Path(__file__).parent / "fixtures" / "v2_plan_minimal"


def _add_plan(repo: Path, slug: str, *, complete: bool) -> None:
    plan_dir = repo / "docs" / "superpowers" / "plans" / slug
    shutil.copytree(FIXTURE, plan_dir)
    import yaml as _yaml

    meta = _yaml.safe_load((plan_dir / "_meta.yaml").read_text())
    meta["plan"] = slug
    (plan_dir / "_meta.yaml").write_text(_yaml.safe_dump(meta, sort_keys=False))
    if complete:
        phase = plan_dir / "01.yaml"
        phase.write_text(phase.read_text().replace('state: " "', "state: x"))


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "docs" / "superpowers" / "plans").mkdir(parents=True)
    (tmp_path / "docs" / "superpowers" / "implemented" / "plans").mkdir(parents=True)
    _add_plan(tmp_path, "2026-05-01-done", complete=True)
    _add_plan(tmp_path, "2026-05-02-wip", complete=False)
    for cmd in (
        ["git", "init", "-q"],
        ["git", "add", "-A"],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "x"],
    ):
        subprocess.run(cmd, cwd=tmp_path, check=True)
    return tmp_path


def _invoke(monkeypatch, tmp_path, argv):
    monkeypatch.setattr(status_cmd, "_make_gh_client", lambda: FakeGhClient())
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    return CliRunner().invoke(app, argv)


def test_sweep_text_lists_archivable_and_nudges(tmp_path, monkeypatch):
    _repo(tmp_path)
    result = _invoke(monkeypatch, tmp_path, ["status"])
    assert result.exit_code == 0, result.output
    assert "2026-05-01-done" in result.output
    assert "fr archive --all" in result.output
    # In-progress plan is surfaced too, not silently dropped.
    assert "2026-05-02-wip" in result.output


def test_sweep_json_shape(tmp_path, monkeypatch):
    _repo(tmp_path)
    result = _invoke(monkeypatch, tmp_path, ["status", "--format", "json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["archivable"] == ["2026-05-01-done"]
    assert payload["in_progress"] == ["2026-05-02-wip"]


def test_sweep_clean_repo_no_archivable(tmp_path, monkeypatch):
    (tmp_path / "docs" / "superpowers" / "plans").mkdir(parents=True)
    _add_plan(tmp_path, "2026-05-03-wip", complete=False)
    for cmd in (
        ["git", "init", "-q"],
        ["git", "add", "-A"],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "x"],
    ):
        subprocess.run(cmd, cwd=tmp_path, check=True)
    result = _invoke(monkeypatch, tmp_path, ["status", "--format", "json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["archivable"] == []


def test_sweep_never_calls_gh_mutations(tmp_path, monkeypatch):
    """The sweep stays allowlist-safe: gh-free, no mutation attempts."""
    _repo(tmp_path)
    gh = FakeGhClient()
    monkeypatch.setattr(status_cmd, "_make_gh_client", lambda: gh)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    result = CliRunner().invoke(app, ["status"])
    assert result.exit_code == 0, result.output
    assert gh.attempted_mutations == 0


def test_single_plan_path_unchanged(tmp_path, monkeypatch):
    """Passing a PLAN_DIR still runs the per-plan report (regression guard)."""
    _repo(tmp_path)
    result = _invoke(
        monkeypatch,
        tmp_path,
        ["status", "docs/superpowers/plans/2026-05-01-done"],
    )
    assert result.exit_code == 0, result.output
    assert "phase 1" in result.output
