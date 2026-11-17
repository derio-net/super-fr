"""The merged-row rule reads a merged `<slug>-design.yaml` as its one spelling (spec
2026-11-17-batch-acceptance-edits R17, §F; derio-net/super-fr#1461).

The default ref holds a fragment as `<slug>-design.yaml`; on the branch the repair has
renamed it to `<slug>.yaml`. `merged_row_edits` and `fr acceptance check` compare the
two row and amendment by id, so the rename is no edit, and a real edit still is."""

from __future__ import annotations

import subprocess
from pathlib import Path

import fr.artifacts  # noqa: F401  (registration rides on the package import)
import pytest
from fr.acceptance.amend import merged_row_edits, outside_merged_row_edits
from fr.acceptance.fold import clear_fold_cache, default_ref_fold
from fr.artifacts.commit import commit_migration
from fr.artifacts.runner import run_migrations
from fr.cli import app
from typer.testing import CliRunner

from tests.unit.acceptance_helpers import FRAGMENTS_REL

SLUG = "2026-01-01-alpha"
UNIT = "widget:tests/test_w.py#test_w"


def _row(rid: str, acceptance: str) -> str:
    return (
        f"  - id: {rid}\n"
        "    capability: Widget\n"
        f"    acceptance: {acceptance}\n"
        "    origin:\n"
        f"    - spec:{SLUG}#R1\n"
        "    levels:\n"
        "      unit:\n"
        f"      - {UNIT}\n"
        "    status: unwired\n"
        "    notes: a test exists\n"
    )


def _amend(rid: str, notes: str) -> str:
    return (
        f"  - row: {rid}\n"
        "    op: set-status\n"
        "    base: 0\n"
        "    status: unwired\n"
        f"    notes: {notes}\n"
        "    why: because\n"
    )


def _frag(feature: str, rows: str, amendments: str = "") -> str:
    text = f"schema_version: 2\nfeature: {feature}\nrepo: acme/widget\nrows:\n{rows}"
    return text + (f"amendments:\n{amendments}" if amendments else "")


DESIGN = _frag(f"{SLUG}-design", _row("r", "r works"), _amend("r", "still a unit test"))
OWN = _frag(SLUG, _row("a", "a works"), _amend("a", "a note"))


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=True
    ).stdout


def _merged(tmp_path: Path, files: dict[str, str]) -> Path:
    """origin/main holds *files* as fragments; the branch `feat/b` has run the repair
    and committed it."""
    bare = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True)
    root = tmp_path / "widget"
    (root / "docs" / "superpowers" / "specs").mkdir(parents=True)
    (root / "docs" / "superpowers" / "specs" / f"{SLUG}-design.md").write_text(
        "# Alpha\n\nR1. r works.\n\n## Test Plan\n\n1. x\n"
    )
    (root / "tests").mkdir()
    (root / "tests" / "test_w.py").write_text("def test_w():\n    pass\n")
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / ".github" / "workflows" / "ci.yml").write_text("on: push\n")
    (root / FRAGMENTS_REL).mkdir(parents=True)
    for name, text in files.items():
        (root / FRAGMENTS_REL / name).write_text(text)
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    _git(root, "remote", "add", "origin", str(bare))
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "feat: alpha")
    _git(root, "push", "-q", "-u", "origin", "main")
    _git(root, "fetch", "-q", "origin")
    _git(root, "remote", "set-head", "origin", "main")
    _git(root, "checkout", "-q", "-b", "feat/b")
    report = run_migrations(root, dry_run=False)
    assert report.ok, report.failed
    assert commit_migration(root, report).committed
    assert not (root / FRAGMENTS_REL / f"{SLUG}-design.yaml").exists()
    clear_fold_cache()
    return root


def _edits(root: Path) -> list[str]:
    clear_fold_cache()
    return merged_row_edits(root, default_ref_fold(root), "origin/main")


def _check(root: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FR_REPO_ROOT", str(root))
    clear_fold_cache()
    return CliRunner().invoke(app, ["acceptance", "check", "--no-fetch"])


TIPS = {
    "design-only": {f"{SLUG}-design.yaml": DESIGN},
    "both-spellings": {f"{SLUG}.yaml": OWN, f"{SLUG}-design.yaml": DESIGN},
}


@pytest.mark.parametrize("tip", list(TIPS), ids=list(TIPS))
def test_a_renamed_design_fragment_is_no_merged_row_edit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tip: str
) -> None:
    root = _merged(tmp_path, TIPS[tip])
    assert _edits(root) == []
    assert outside_merged_row_edits(root) == []
    res = _check(root, monkeypatch)
    assert res.exit_code == 0, res.output


@pytest.mark.parametrize("tip", list(TIPS), ids=list(TIPS))
def test_a_real_edit_of_a_renamed_row_is_still_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tip: str
) -> None:
    root = _merged(tmp_path, TIPS[tip])
    path = root / FRAGMENTS_REL / f"{SLUG}.yaml"
    path.write_text(path.read_text().replace("acceptance: r works", "acceptance: r is fine"))
    found = _edits(root)
    assert any("row r edited in place" in e for e in found), found
    res = _check(root, monkeypatch)
    assert res.exit_code != 0, res.output
