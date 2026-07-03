"""`fr spec status` default-on gh resolution + `--no-gh` opt-out (#339)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from fr.commands import spec_cmd
from typer.testing import CliRunner

from tests.unit.fakes import FakeGhClient


def _phase_yaml(number: int, steps: dict[str, str], completion_at: str | None = None) -> str:
    doc = {
        "schema_version": 2,
        "phase": {
            "number": number,
            "title": f"phase {number}",
            "tag": "agentic",
            "depends_on": [],
            "tracking_issue": None,
        },
        "tasks": [
            {"number": 1, "title": "task", "steps": [{"id": sid, "text": "x"} for sid in steps]}
        ],
        "state": {
            "steps": {
                sid: {"state": st, "ticked_at": None, "note": None} for sid, st in steps.items()
            },
            "completion": {"at": completion_at, "note": None, "observed_prs": []},
        },
    }
    return yaml.safe_dump(doc, sort_keys=False)


def _repo_with_crossrepo_spec(tmp_path: Path) -> Path:
    (tmp_path / "docs" / "superpowers" / "plans").mkdir(parents=True)
    specs = tmp_path / "docs" / "superpowers" / "specs"
    specs.mkdir()
    (specs / "s.md").write_text(
        "# S\n\n## Implementation Plans\n\n"
        "| Plan | Repo | File | Depends on |\n"
        "|------|------|------|------------|\n"
        "| Remote plan | `owner/repo` | `docs/superpowers/plans/myplan/` | — |\n"
    )
    return tmp_path


def _preloaded_gh() -> FakeGhClient:
    gh = FakeGhClient()
    base = "docs/superpowers/implemented/plans/myplan"
    gh.remote_tree = {
        ("owner/repo", f"{base}/_meta.yaml"): "schema_version: 2\n",
        ("owner/repo", f"{base}/01.yaml"): _phase_yaml(
            1, {"P1.T1.S1": "x"}, "2026-07-03T00:00:00Z"
        ),
    }
    return gh


def test_default_resolves_crossrepo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo_with_crossrepo_spec(tmp_path)
    monkeypatch.chdir(repo)
    monkeypatch.setattr(spec_cmd, "_make_gh_client", lambda: _preloaded_gh())
    from fr.cli import app

    result = CliRunner().invoke(app, ["spec", "status", "docs/superpowers/specs/s.md"])
    assert result.exit_code == 0, result.output
    assert "Complete" in result.output


def test_no_gh_skips_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo_with_crossrepo_spec(tmp_path)
    monkeypatch.chdir(repo)
    made: list[bool] = []

    def factory() -> FakeGhClient:
        made.append(True)
        return _preloaded_gh()

    monkeypatch.setattr(spec_cmd, "_make_gh_client", factory)
    from fr.cli import app

    result = CliRunner().invoke(app, ["spec", "status", "docs/superpowers/specs/s.md", "--no-gh"])
    assert result.exit_code == 0, result.output
    assert made == []  # factory never called under --no-gh
    assert "Unreachable" in result.output
