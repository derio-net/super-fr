"""`Worktree.archive_moves` against a real repository (wave-merge-queue R16, p6-r7): the paths
`fr archive --branch` moves are the archive's own classification of what the merged branch
changed, so a spec file moves and an acceptance fragment, which no archive moves, does not."""

from __future__ import annotations

import subprocess
from pathlib import Path

from fr.triage.gitseam import Worktree


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def test_the_moves_are_the_archives_classification_of_the_merged_branch(tmp_path: Path) -> None:
    bare = tmp_path / "origin.git"
    _git(tmp_path, "init", "--quiet", "--bare", "--initial-branch=main", str(bare))
    work = tmp_path / "work"
    _git(tmp_path, "clone", "--quiet", str(bare), str(work))
    for k, v in (("user.name", "t"), ("user.email", "t@example.com"), ("commit.gpgsign", "false")):
        _git(work, "config", k, v)
    _git(work, "checkout", "--quiet", "-b", "main")
    (work / "a.txt").write_text("a\n")
    _git(work, "add", ".")
    _git(work, "commit", "--quiet", "-m", "seed")
    _git(work, "push", "--quiet", "origin", "main")
    _git(work, "checkout", "--quiet", "-b", "feat/x")
    files = {
        "docs/superpowers/specs/2026-10-01-x-design.md": "spec\n",
        "docs/superpowers/plans/2026-10-01-x/_meta.yaml": "p\n",
        "docs/superpowers/journals/plans/2026-10-01-x.md": "j\n",
        "docs/superpowers/runs/r-x.yaml": "r\n",
        "docs/acceptance/features/2026-10-01-x-design.yaml": "f\n",
        "src.py": "code\n",
    }
    for rel, text in files.items():
        (work / rel).parent.mkdir(parents=True, exist_ok=True)
        (work / rel).write_text(text)
    _git(work, "add", "--all")
    _git(work, "commit", "--quiet", "-m", "feature")
    _git(work, "push", "--quiet", "origin", "feat/x")
    _git(work, "checkout", "--quiet", "main")
    _git(work, "merge", "--quiet", "--no-ff", "-m", "merge", "feat/x")
    _git(work, "push", "--quiet", "origin", "main")

    moves = Worktree(work).archive_moves("feat/x", "origin/main")
    assert moves is not None and sorted(moves) == [
        "docs/superpowers/journals/plans/2026-10-01-x.md",
        "docs/superpowers/plans/2026-10-01-x",
        "docs/superpowers/runs/r-x.yaml",
        "docs/superpowers/specs/2026-10-01-x-design.md",
    ]  # no fragment, no source file
