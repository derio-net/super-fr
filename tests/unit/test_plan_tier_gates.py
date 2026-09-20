"""Phase 2 of 2026-09-20-phases-file-tier-reaches-dispatch: self-review learns
the two gates `acceptance`/`skeleton` already have (spec decision D2).

- Floor probe: a plan that carries `tier` while `fr_version` admits a
  pre-3.12.0 fr warns (mirrors the 3.7.0 `acceptance:` probe exactly).
- Untiered warning: an agentic phase with no `tier` warns; a manual phase
  with no `tier` is silent (manual phases are never dispatched to a model).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from fr.cli import app
from fr.parser import parse as parse_plan
from fr.plan_ops import self_review
from typer.testing import CliRunner

runner = CliRunner()


def _repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "docs" / "superpowers" / "specs").mkdir(parents=True)
    (tmp_path / "docs" / "superpowers" / "plans").mkdir()
    return tmp_path


def _spec(repo: Path) -> Path:
    p = repo / "docs" / "superpowers" / "specs" / "2026-07-04-toy.md"
    p.write_text(
        "# Toy\n\n## Implementation Plans\n\n| Plan | Repo | File | Depends on |\n|--|--|--|--|\n"
    )
    return p


def _create_plan(repo: Path, monkeypatch, phases_yaml: str) -> Path:
    """Scaffold a plan via the real CLI's `--phases-file`, phase 1's ingestion
    path — the only way this test could exist."""
    phases_file = repo / "phases.yaml"
    phases_file.write_text(phases_yaml)
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
    return repo / "docs" / "superpowers" / "plans" / "2026-07-04-toy"


def _issues(plan_dir: Path) -> list:
    return self_review(parse_plan(plan_dir))


TIERED_PHASES = (
    "- number: 1\n  title: One\n  tier: standard\n"
    "  tasks:\n    - number: 1\n      title: t\n"
    "      steps:\n        - id: P1.T1.S1\n          text: s\n"
)


# ── Task 1: fr_version floor probe ──────────────────────────────────────────


def test_self_review_warns_tier_below_floor(tmp_path: Path, monkeypatch) -> None:
    repo = _repo(tmp_path)
    _spec(repo)
    plan_dir = _create_plan(repo, monkeypatch, TIERED_PHASES)  # default floor >=3.0.0
    issues = _issues(plan_dir)
    warns = [i for i in issues if i.severity == "warn"]
    assert any("fr_version" in i.message and "3.12.0" in i.message for i in warns), issues


def test_self_review_no_tier_version_warn_with_raised_floor(tmp_path: Path, monkeypatch) -> None:
    repo = _repo(tmp_path)
    _spec(repo)
    plan_dir = _create_plan(repo, monkeypatch, TIERED_PHASES)
    meta = plan_dir / "_meta.yaml"
    meta.write_text(meta.read_text().replace(">=3.0.0,<5.0.0", ">=3.12.0,<5.0.0"))
    issues = _issues(plan_dir)
    assert not any("3.12.0" in i.message and "admits a pre" in i.message for i in issues), issues


# ── Task 2: untiered agentic-phase warning ─────────────────────────────────


def test_self_review_warns_untiered_agentic_phase(tmp_path: Path, monkeypatch) -> None:
    repo = _repo(tmp_path)
    _spec(repo)
    phases = (
        "- number: 1\n  title: One\n"
        "  tasks:\n    - number: 1\n      title: t\n"
        "      steps:\n        - id: P1.T1.S1\n          text: s\n"
    )
    plan_dir = _create_plan(repo, monkeypatch, phases)
    issues = _issues(plan_dir)
    warns = [i for i in issues if i.severity == "warn"]
    assert any("phase 1" in i.message and "tier" in i.message for i in warns), issues


def test_self_review_silent_for_untiered_manual_phase(tmp_path: Path, monkeypatch) -> None:
    repo = _repo(tmp_path)
    _spec(repo)
    phases = (
        "- number: 1\n  title: One\n  tag: manual\n"
        "  tasks:\n    - number: 1\n      title: t\n"
        "      steps:\n        - id: P1.T1.S1\n          text: s\n"
    )
    plan_dir = _create_plan(repo, monkeypatch, phases)
    issues = _issues(plan_dir)
    assert not any("tier" in i.message for i in issues), issues


def test_self_review_silent_for_tiered_agentic_phase(tmp_path: Path, monkeypatch) -> None:
    repo = _repo(tmp_path)
    _spec(repo)
    plan_dir = _create_plan(repo, monkeypatch, TIERED_PHASES)
    meta = plan_dir / "_meta.yaml"
    meta.write_text(meta.read_text().replace(">=3.0.0,<5.0.0", ">=3.12.0,<5.0.0"))
    issues = _issues(plan_dir)
    assert not any("no tier" in i.message or "declares no" in i.message for i in issues), issues
