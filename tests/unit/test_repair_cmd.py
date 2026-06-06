"""`vk repair` CLI — dry-run default, --yes writes, loud warnings."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from fr.cli import app
from typer.testing import CliRunner

SLUG = "2026-05-10-x"


def _repo(tmp_path: Path) -> Path:
    sp = tmp_path / "docs" / "superpowers"
    for d in ("plans", "implemented/plans", "specs", "implemented/specs"):
        (sp / d).mkdir(parents=True)
    return tmp_path


def _spec_with_legacy_cell(repo: Path) -> Path:
    (repo / "docs/superpowers/implemented/plans" / SLUG).mkdir()
    spec = repo / "docs/superpowers/specs/2026-05-10-fixture.md"
    spec.write_text(
        "# Fixture\n\n## Implementation Plans\n\n"
        "| Plan | Repo | File | Depends on |\n"
        "|---|---|---|---|\n"
        f"| Plan X | `derio-net/test` | `docs/superpowers/archived-plans/{SLUG}/` | — |\n"
    )
    return spec


def _git_seed(repo: Path) -> None:
    for cmd in (
        ["git", "init", "-q"],
        ["git", "add", "-A"],
        [
            "git",
            "-c",
            "user.email=t@t",
            "-c",
            "user.name=t",
            "commit",
            "-qm",
            "seed",
            "--allow-empty",
        ],
    ):
        subprocess.run(cmd, cwd=repo, check=True)


def _invoke(monkeypatch, repo: Path, argv: list[str]):
    monkeypatch.chdir(repo)
    monkeypatch.setenv("VK_REPO_ROOT", str(repo))
    return CliRunner().invoke(app, argv)


def test_repair_dry_run_default_writes_nothing(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    spec = _spec_with_legacy_cell(repo)
    _git_seed(repo)
    before = spec.read_text()
    result = _invoke(monkeypatch, repo, ["repair"])
    assert result.exit_code == 0, result.output
    assert spec.read_text() == before
    assert SLUG in result.output  # the planned rewrite is reported
    assert "--yes" in result.output  # nudge to apply


def test_repair_yes_writes(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    spec = _spec_with_legacy_cell(repo)
    _git_seed(repo)
    result = _invoke(monkeypatch, repo, ["repair", "--yes"])
    assert result.exit_code == 0, result.output
    assert f"`{SLUG}`" in spec.read_text()
    assert "archived-plans" not in spec.read_text()


def test_repair_warns_loudly_on_unresolvable(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    spec = repo / "docs/superpowers/specs/2026-05-10-fixture.md"
    spec.write_text(
        "# Fixture\n\n## Implementation Plans\n\n"
        "| Plan | Repo | File | Depends on |\n"
        "|---|---|---|---|\n"
        "| Plan X | `derio-net/test` | `docs/superpowers/archived-plans/2026-05-10-gone/` | — |\n"
    )
    _git_seed(repo)
    result = _invoke(monkeypatch, repo, ["repair", "--yes"])
    assert result.exit_code == 0, result.output  # a report, not a gate
    combined = result.output + (result.stderr or "")
    assert "2026-05-10-gone" in combined
    assert "does not resolve" in combined


def test_repair_json_format(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    _spec_with_legacy_cell(repo)
    _git_seed(repo)
    result = _invoke(monkeypatch, repo, ["repair", "--format", "json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["applied"] is False
    assert len(payload["rewrites"]) == 1
    assert payload["rewrites"][0]["new"] == f"`{SLUG}`"
    assert payload["warnings"] == []


def test_repair_dirty_tree_refusal_with_yes(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    spec = _spec_with_legacy_cell(repo)
    _git_seed(repo)
    spec.write_text(spec.read_text() + "\ndirty\n")  # uncommitted change
    result = _invoke(monkeypatch, repo, ["repair", "--yes"])
    assert result.exit_code == 2
    assert "dirty" in (result.output + (result.stderr or "")).lower()


def test_repair_legacy_layout_hard_stop(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    (repo / "docs/superpowers/archived-plans").mkdir()
    _git_seed(repo)
    result = _invoke(monkeypatch, repo, ["repair"])
    assert result.exit_code == 2
    assert "legacy layout" in (result.output + (result.stderr or "")).lower()


def test_repair_noop_reports_clean(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    (repo / "docs/superpowers/implemented/plans" / SLUG).mkdir()
    spec = repo / "docs/superpowers/specs/2026-05-10-fixture.md"
    spec.write_text(
        "# Fixture\n\n## Implementation Plans\n\n"
        "| Plan | Repo | File | Depends on |\n"
        "|---|---|---|---|\n"
        f"| Plan X | `derio-net/test` | `{SLUG}` | — |\n"
    )
    _git_seed(repo)
    result = _invoke(monkeypatch, repo, ["repair"])
    assert result.exit_code == 0
    assert "nothing to repair" in result.output.lower()
