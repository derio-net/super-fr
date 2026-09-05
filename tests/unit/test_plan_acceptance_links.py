"""Phase 6 — plan-level acceptance linkage (spec decision 2).

PhaseHeader gains `acceptance: [row-ids]`; self-review enforces linkage;
`fr plan edit --complete-phase` nudges on unflipped rows; `fr status` gains
an acceptance section.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml
from fr.cli import app
from fr.commands import status_cmd
from fr.parser import parse as parse_plan
from fr.plan_ops import PhaseSpec, create, self_review
from typer.testing import CliRunner

from tests.unit.fakes import FakeGhClient

runner = CliRunner()

FIXTURE = Path(__file__).parent / "fixtures" / "v2_plan_minimal"

MATRIX = """\
org: derio-net
repo: own
rows:
  - id: row-a
    capability: "Cap"
    acceptance: "A"
    origin: []
    levels: {}
    status: not-implemented
    notes: ""
  - id: row-b
    capability: "Cap"
    acceptance: "B"
    origin: []
    levels: {}
    status: skipped
    notes: ""
"""


def _repo(tmp_path: Path, *, matrix: bool = True) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "docs" / "superpowers" / "specs").mkdir(parents=True)
    (tmp_path / "docs" / "superpowers" / "plans").mkdir()
    if matrix:
        (tmp_path / "docs" / "acceptance").mkdir(parents=True)
        (tmp_path / "docs" / "acceptance" / "matrix.yaml").write_text(MATRIX)
    return tmp_path


def _spec(repo: Path, *, test_plan: bool = True) -> Path:
    p = repo / "docs" / "superpowers" / "specs" / "2026-07-04-toy.md"
    body = "# Toy\n\n"
    if test_plan:
        body += "## Test Plan\n\n1. walk\n\n"
    body += "## Implementation Plans\n\n| Plan | Repo | File | Depends on |\n|--|--|--|--|\n"
    p.write_text(body)
    return p


def _create_plan(repo: Path, acceptance: tuple[str, ...] = ()) -> Path:
    plan = create(
        repo_root=repo,
        slug="2026-07-04-toy",
        spec="docs/superpowers/specs/2026-07-04-toy.md",
        target_repo="derio-net/own",
        fr_version=">=3.0.0,<5.0.0",
        phases=[
            PhaseSpec(
                number=1,
                title="One",
                tag="agentic",
                acceptance=acceptance,
                tasks=({"number": 1, "title": "t", "steps": [{"id": "P1.T1.S1", "text": "s"}]},),
            )
        ],
        prose="# toy\n",
    )
    return plan.dir


# ── T1: schema + round-trip ────────────────────────────────────────────────


def test_phase_header_parses_acceptance(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _spec(repo)
    plan_dir = _create_plan(repo, acceptance=("row-a", "row-b"))
    plan = parse_plan(plan_dir)
    assert plan.phases[0].phase.acceptance == ("row-a", "row-b")


def test_phase_header_acceptance_defaults_empty(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _spec(repo)
    plan_dir = _create_plan(repo)
    plan = parse_plan(plan_dir)
    assert plan.phases[0].phase.acceptance == ()
    # empty ⇒ key omitted, existing plans stay byte-stable
    assert "acceptance" not in (plan_dir / "01.yaml").read_text()


def test_tick_round_trips_acceptance_key(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _spec(repo)
    plan_dir = _create_plan(repo, acceptance=("row-a",))
    result = runner.invoke(app, ["plan", "edit", str(plan_dir), "--tick", "P1.T1.S1"])
    assert result.exit_code == 0, result.output
    doc = yaml.safe_load((plan_dir / "01.yaml").read_text())
    assert doc["phase"]["acceptance"] == ["row-a"]


def test_create_phases_file_passes_acceptance(tmp_path: Path, monkeypatch) -> None:
    repo = _repo(tmp_path)
    _spec(repo)
    phases_file = tmp_path / "phases.yaml"
    phases_file.write_text(
        "- number: 1\n  title: One\n  acceptance: [row-a]\n"
        "  tasks:\n    - number: 1\n      title: t\n"
        "      steps:\n        - id: P1.T1.S1\n          text: s\n"
    )
    monkeypatch.chdir(repo)
    result = runner.invoke(
        app,
        [
            "plan",
            "create",
            "--slug",
            "2026-07-04-toy",
            "--target-repo",
            "derio-net/own",
            "--spec",
            "docs/superpowers/specs/2026-07-04-toy.md",
            "--phases-file",
            str(phases_file),
        ],
    )
    assert result.exit_code == 0, result.output
    doc = yaml.safe_load(
        (repo / "docs" / "superpowers" / "plans" / "2026-07-04-toy" / "01.yaml").read_text()
    )
    assert doc["phase"]["acceptance"] == ["row-a"]


# ── T2: self-review lints ──────────────────────────────────────────────────


def _issues(repo: Path, plan_dir: Path) -> list:
    return self_review(parse_plan(plan_dir))


def test_self_review_errors_zero_links_with_matrix(tmp_path: Path) -> None:
    repo = _repo(tmp_path, matrix=True)
    _spec(repo, test_plan=True)
    plan_dir = _create_plan(repo)
    issues = _issues(repo, plan_dir)
    errors = [i for i in issues if i.severity == "error"]
    assert any("no acceptance rows linked" in i.message for i in errors)


def test_self_review_warns_zero_links_without_matrix(tmp_path: Path) -> None:
    repo = _repo(tmp_path, matrix=False)
    _spec(repo, test_plan=True)
    plan_dir = _create_plan(repo)
    issues = _issues(repo, plan_dir)
    assert not any(i.severity == "error" and "acceptance" in i.message for i in issues)
    warns = [i for i in issues if i.severity == "warn"]
    assert any("fr acceptance init" in i.message for i in warns)


def test_self_review_errors_unknown_row_id(tmp_path: Path) -> None:
    repo = _repo(tmp_path, matrix=True)
    _spec(repo, test_plan=True)
    plan_dir = _create_plan(repo, acceptance=("row-a", "row-ghost"))
    issues = _issues(repo, plan_dir)
    errors = [i for i in issues if i.severity == "error"]
    assert any("row-ghost" in i.message and "phase 1" in i.message for i in errors)


def test_self_review_passes_with_valid_links(tmp_path: Path) -> None:
    repo = _repo(tmp_path, matrix=True)
    _spec(repo, test_plan=True)
    plan_dir = _create_plan(repo, acceptance=("row-a",))
    meta = plan_dir / "_meta.yaml"  # acceptance: requires the 3.7.0 floor
    meta.write_text(meta.read_text().replace(">=3.0.0,<5.0.0", ">=3.7.0,<5.0.0"))
    issues = _issues(repo, plan_dir)
    assert not any("acceptance" in i.message for i in issues), issues


def test_self_review_spec_without_test_plan_exempt(tmp_path: Path) -> None:
    repo = _repo(tmp_path, matrix=True)
    _spec(repo, test_plan=False)
    plan_dir = _create_plan(repo)
    issues = _issues(repo, plan_dir)
    assert not any("acceptance" in i.message for i in issues), issues


def test_self_review_warns_low_fr_version_floor(tmp_path: Path) -> None:
    """Review finding (#352): `acceptance:` is a schema-version event — a plan
    that uses it while its fr_version admits a pre-acceptance fr would pass
    the version gate on old tooling and die on a raw pydantic error."""
    repo = _repo(tmp_path, matrix=True)
    _spec(repo, test_plan=True)
    plan_dir = _create_plan(repo, acceptance=("row-a",))  # default floor >=3.0.0
    issues = _issues(repo, plan_dir)
    warns = [i for i in issues if i.severity == "warn"]
    assert any("fr_version" in i.message and "3.7.0" in i.message for i in warns)


def test_self_review_no_version_warn_with_raised_floor(tmp_path: Path) -> None:
    repo = _repo(tmp_path, matrix=True)
    _spec(repo, test_plan=True)
    plan_dir = _create_plan(repo, acceptance=("row-a",))
    meta = plan_dir / "_meta.yaml"
    meta.write_text(meta.read_text().replace(">=3.0.0,<5.0.0", ">=3.7.0,<5.0.0"))
    issues = _issues(repo, plan_dir)
    assert not any("fr_version" in i.message for i in issues), issues


# ── T3: complete-phase nudge ───────────────────────────────────────────────


def test_complete_phase_warns_on_unflipped_rows(tmp_path: Path) -> None:
    repo = _repo(tmp_path, matrix=True)
    _spec(repo)
    plan_dir = _create_plan(repo, acceptance=("row-a", "row-b"))
    runner.invoke(app, ["plan", "edit", str(plan_dir), "--tick", "P1.T1.S1"])
    result = runner.invoke(
        app, ["plan", "edit", str(plan_dir), "--complete-phase", "1", "--note", "done"]
    )
    assert result.exit_code == 0, result.output
    assert "marked complete" in result.output
    assert "row-a" in result.output  # not-implemented → nudge
    assert "row-b" not in result.output  # skipped is a legitimate landing


def test_complete_phase_silent_without_acceptance(tmp_path: Path) -> None:
    repo = _repo(tmp_path, matrix=True)
    _spec(repo)
    plan_dir = _create_plan(repo)
    runner.invoke(app, ["plan", "edit", str(plan_dir), "--tick", "P1.T1.S1"])
    result = runner.invoke(
        app, ["plan", "edit", str(plan_dir), "--complete-phase", "1", "--note", "done"]
    )
    assert result.exit_code == 0, result.output
    assert "not-implemented" not in result.output


def test_complete_phase_broken_matrix_does_not_block(tmp_path: Path) -> None:
    repo = _repo(tmp_path, matrix=True)
    (repo / "docs" / "acceptance" / "matrix.yaml").write_text("rows: {broken\n")
    _spec(repo)
    plan_dir = _create_plan(repo, acceptance=("row-a",))
    runner.invoke(app, ["plan", "edit", str(plan_dir), "--tick", "P1.T1.S1"])
    result = runner.invoke(
        app, ["plan", "edit", str(plan_dir), "--complete-phase", "1", "--note", "done"]
    )
    assert result.exit_code == 0, result.output
    assert "marked complete" in result.output


# ── T4: fr status acceptance section ───────────────────────────────────────


def _status_repo(tmp_path: Path, *, matrix: bool) -> Path:
    plan_dir = tmp_path / "docs" / "superpowers" / "plans" / "2026-05-09-fixture-minimal"
    shutil.copytree(FIXTURE, plan_dir)
    if matrix:
        (tmp_path / "docs" / "acceptance").mkdir(parents=True)
        (tmp_path / "docs" / "acceptance" / "matrix.yaml").write_text(MATRIX)
    for cmd in (
        ["git", "init", "-q"],
        ["git", "add", "-A"],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "x"],
    ):
        subprocess.run(cmd, cwd=tmp_path, check=True)
    return plan_dir


def _status(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, plan_dir: Path):
    monkeypatch.setattr(status_cmd, "_make_gh_client", lambda: FakeGhClient())
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    return runner.invoke(app, ["status", str(plan_dir.relative_to(tmp_path))])


def test_status_shows_acceptance_section(tmp_path: Path, monkeypatch) -> None:
    plan_dir = _status_repo(tmp_path, matrix=True)
    result = _status(monkeypatch, tmp_path, plan_dir)
    assert result.exit_code == 0, result.output
    flat = " ".join(result.output.split())  # rich soft-wraps human output
    assert "Acceptance" in flat
    assert "2 open" in flat
    assert "fr acceptance status" in flat


def test_status_no_section_without_matrix(tmp_path: Path, monkeypatch) -> None:
    plan_dir = _status_repo(tmp_path, matrix=False)
    result = _status(monkeypatch, tmp_path, plan_dir)
    assert result.exit_code == 0, result.output
    assert "Acceptance" not in result.output
