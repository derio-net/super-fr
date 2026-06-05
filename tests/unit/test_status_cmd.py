"""`vk status` — read-only, allowlistable report (2026-06-05 spec, Phase 4).

The structural guarantee under test: status NEVER calls a gh mutation
method (that is what makes `vk status*` safe to allowlist), and its read
path is the same `build_plan_report` apply uses, so the two can't drift.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from typer.testing import CliRunner

from tests.unit.fakes import FakeGhClient
from vk.cli import app
from vk.commands import status_cmd

FIXTURE = Path(__file__).parent / "fixtures" / "v2_plan_minimal"

_MUTATION_METHODS = {
    "create_issue",
    "edit_issue_labels",
    "edit_issue_state",
    "edit_issue_body",
    "ensure_labels",
}


def _plan_repo(tmp_path: Path, *, tick: bool = False, tracking: str | None = None) -> Path:
    plan_dir = tmp_path / "docs" / "superpowers" / "plans" / "2026-05-09-fixture-minimal"
    shutil.copytree(FIXTURE, plan_dir)
    if tick:
        phase = plan_dir / "01.yaml"
        phase.write_text(phase.read_text().replace('state: " "', "state: x"))
    if tracking:
        phase = plan_dir / "01.yaml"
        phase.write_text(
            phase.read_text().replace("tracking_issue: null", f"tracking_issue: {tracking}")
        )
    for cmd in (
        ["git", "init", "-q"],
        ["git", "add", "-A"],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "x"],
    ):
        subprocess.run(cmd, cwd=tmp_path, check=True)
    return plan_dir


def _invoke(monkeypatch, tmp_path, gh, argv):
    monkeypatch.setattr(status_cmd, "_make_gh_client", lambda: gh)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    return CliRunner().invoke(app, argv)


def test_status_reports_header_table_and_refusal(tmp_path, monkeypatch):
    plan_dir = _plan_repo(tmp_path, tick=True)
    gh = FakeGhClient()
    result = _invoke(monkeypatch, tmp_path, gh, ["status", str(plan_dir.relative_to(tmp_path))])
    assert result.exit_code == 0, result.output
    # Factual header line.
    assert "created 2026-05-09 (" in result.output
    assert "1/1 steps" in result.output
    assert "never dispatched" in result.output
    # Per-phase table line: ticks + no tracking issue + would-refuse.
    assert "phase 1" in result.output
    assert "would refuse" in result.output
    # Archive nudge — the gate passes (undispatched + locally complete).
    assert "vk archive" in result.output
    # Drift warning from the renderer surfaces here.
    assert "never dispatched —" in result.output or "warnings" in result.output


def test_status_never_calls_mutation_methods(tmp_path, monkeypatch):
    """The allowlistability guarantee, as a test."""
    plan_dir = _plan_repo(tmp_path, tick=True)
    gh = FakeGhClient()
    result = _invoke(monkeypatch, tmp_path, gh, ["status", str(plan_dir.relative_to(tmp_path))])
    assert result.exit_code == 0
    called = {name for name, _ in gh.calls}
    assert not (called & _MUTATION_METHODS), f"status mutated: {called & _MUTATION_METHODS}"
    assert gh.attempted_mutations == 0


def test_status_surfaces_reverse_drift(tmp_path, monkeypatch):
    """Issue closed upstream while the plan is incomplete (content-factory
    case) — the renderer's error-severity warning must print."""
    repo = "derio-net/superpowers-for-vk"
    plan_dir = _plan_repo(tmp_path, tick=False, tracking=f"https://github.com/{repo}/issues/42")
    gh = FakeGhClient()
    gh.add_issue(repo, 42, state="CLOSED")
    result = _invoke(monkeypatch, tmp_path, gh, ["status", str(plan_dir.relative_to(tmp_path))])
    assert result.exit_code == 0, result.output
    assert "Issue closed but plan is incomplete" in result.output


def test_status_exit_5_on_parse_error(tmp_path, monkeypatch):
    bad = tmp_path / "docs" / "superpowers" / "plans" / "broken"
    bad.mkdir(parents=True)
    (bad / "_meta.yaml").write_text("schema_version: 2\n")  # missing required fields
    gh = FakeGhClient()
    result = _invoke(monkeypatch, tmp_path, gh, ["status", str(bad.relative_to(tmp_path))])
    assert result.exit_code == 5, result.output


def test_status_json_mirrors_apply_shape(tmp_path, monkeypatch):
    import json

    plan_dir = _plan_repo(tmp_path, tick=True)
    gh = FakeGhClient()
    result = _invoke(
        monkeypatch,
        tmp_path,
        gh,
        ["status", str(plan_dir.relative_to(tmp_path)), "--format", "json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    report = payload["plans"][0]
    for key in ("plan", "mutations", "suppressed", "warnings", "phases"):
        assert key in report, f"missing {key}"
    assert report["suppressed"][0]["phase_number"] == 1
