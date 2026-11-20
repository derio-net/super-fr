"""R17: `batch_merge.trial_conflicts` — a trial merge of a PR head with the default branch
in a scratch worktree that is always removed, under the merge's own resolution rules."""

from __future__ import annotations

import subprocess
from pathlib import Path

from fr.triage.batch_merge import trial_conflicts
from fr.triage.gitseam import Checkout
from fr.triage.model import VersionBlock, VersionSource


def _git(cwd: Path, *args: str) -> str:
    out = subprocess.run(  # noqa: S603 - a sandboxed scratch repo
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=cwd, check=True, capture_output=True, text=True,
    )  # fmt: skip
    return out.stdout.strip()


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "clone"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / "a.txt").write_text("one\ntwo\nthree\n")
    (repo / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "1.0.0"\n')
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    return repo


def _scratch_gone(repo: Path, root: Path) -> bool:
    listing = _git(repo, "worktree", "list", "--porcelain")
    return str(root) not in listing and not any(root.glob("*"))


def test_a_real_content_conflict_returns_its_path_and_leaves_no_worktree(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _git(repo, "switch", "-qc", "pr")
    (repo / "a.txt").write_text("one\nPR\nthree\n")
    _git(repo, "commit", "-qam", "pr")
    head = _git(repo, "rev-parse", "HEAD")
    _git(repo, "switch", "-q", "main")
    (repo / "a.txt").write_text("one\nMAIN\nthree\n")
    _git(repo, "commit", "-qam", "main")
    root = tmp_path / "probe"
    assert trial_conflicts(Checkout(repo), "main", None, head, scratch_root=root) == ["a.txt"]
    assert _scratch_gone(repo, root)
    assert _git(repo, "status", "--porcelain") == ""  # the clone itself is untouched


def _version_block() -> VersionBlock:
    return VersionBlock(
        source=VersionSource(file="pyproject.toml", key="project.version"),
        files=["pyproject.toml"],
        set="true",
    )


def test_a_version_only_conflict_is_resolved_not_reported(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _git(repo, "switch", "-qc", "pr")
    (repo / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "1.1.0"\n')
    _git(repo, "commit", "-qam", "pr bumps")
    head = _git(repo, "rev-parse", "HEAD")
    _git(repo, "switch", "-q", "main")
    (repo / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "1.0.1"\n')
    _git(repo, "commit", "-qam", "main bumps")
    root = tmp_path / "probe"
    assert trial_conflicts(Checkout(repo), "main", _version_block(), head, scratch_root=root) == []
    assert _scratch_gone(repo, root)
    # the same conflict without a declared version block is a real one
    assert trial_conflicts(Checkout(repo), "main", None, head, scratch_root=root) == [
        "pyproject.toml"
    ]
    assert _scratch_gone(repo, root)
