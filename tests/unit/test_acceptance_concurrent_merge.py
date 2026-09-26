"""Two branches that each `fr acceptance add` a row merge cleanly (spec
2026-09-26-version-bump-churn §3.H + §3.I, §7 item 8).

The shape this pins is the one that made every concurrent `add` a conflict:
both sides appended at the end of `matrix.yaml`, and every committed report
carried the row count, the status-count tiles and the sharp-line panels — a
second copy of each row that any two additions collided in. With insert by
capability and per-row-only committed reports, rows added to DIFFERENT
capabilities touch disjoint regions of all four files.

Runs in a throwaway git repo under `tmp_path`; the repo under test is never
touched.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.cli import app
from typer.testing import CliRunner

from tests.unit.acceptance_helpers import MATRIX_HEADER, make_repo, row

runner = CliRunner()

MATRIX = "docs/acceptance/matrix.yaml"
FILES = (
    MATRIX,
    "docs/acceptance/report_local.html",
    "docs/acceptance/report_linked.html",
    "docs/acceptance/report_linked.md",
)


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=False)


def _ok(root: Path, *args: str) -> str:
    res = _git(root, *args)
    assert res.returncode == 0, f"git {' '.join(args)}: {res.stderr}"
    return res.stdout


def _fr(*args: str) -> None:
    res = runner.invoke(app, ["acceptance", *args])
    assert res.exit_code == 0, res.output


def _add(root: Path, row_id: str, capability: str) -> None:
    _fr(
        "add",
        "--id",
        row_id,
        "--capability",
        capability,
        "--acceptance",
        f"Operator can {row_id}",
        "--origin",
        "own:docs/superpowers/specs/s.md",
        "--status",
        "not-implemented",
        "--notes",
        f"added on the {row_id} branch",
    )
    # The engine commits its own write; commit anything it left behind so the
    # branch is exactly what a PR would carry.
    if _ok(root, "status", "--porcelain"):
        _ok(root, "add", "-A")
        _ok(root, "commit", "-qm", f"add {row_id}")


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    gitconfig = tmp_path / "gitconfig"
    gitconfig.write_text("")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(gitconfig))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    alpha = row(id="alpha-1").replace('"Cap"', '"Alpha"')
    beta = row(id="beta-1").replace('"Cap"', '"Beta"')
    root = make_repo(tmp_path, alpha + beta, git=False, header=MATRIX_HEADER)
    monkeypatch.setenv("VK_REPO_ROOT", str(root))
    _ok(root, "init", "-q", "-b", "main")
    _ok(root, "config", "user.email", "t@example.com")
    _ok(root, "config", "user.name", "t")
    _ok(root, "config", "commit.gpgsign", "false")
    _fr("report", "--deterministic")
    _ok(root, "add", "-A")
    _ok(root, "commit", "-qm", "base")
    return root


def test_adds_to_different_capabilities_merge_without_conflict(repo: Path) -> None:
    _ok(repo, "checkout", "-q", "-b", "a")
    _add(repo, "alpha-2", "Alpha")
    _ok(repo, "checkout", "-q", "main")
    _ok(repo, "checkout", "-q", "-b", "b")
    _add(repo, "beta-2", "Beta")

    # Both sides really did change every one of the four files.
    for branch in ("a", "b"):
        changed = set(_ok(repo, "diff", "--name-only", "main", branch).split())
        assert set(FILES) <= changed, (branch, changed)

    _ok(repo, "checkout", "-q", "a")
    merge = _git(repo, "merge", "--no-edit", "b")
    conflicted = set(_ok(repo, "diff", "--name-only", "--diff-filter=U").split())
    assert merge.returncode == 0 and not conflicted, merge.stdout + merge.stderr

    matrix = (repo / MATRIX).read_text()
    assert "alpha-2" in matrix and "beta-2" in matrix
    # The merged reports are exactly what a fresh render of the merged matrix
    # produces — `check` gates their freshness.
    _fr("report", "--check")
    _fr("check")
