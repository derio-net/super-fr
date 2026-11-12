"""A repo with a default branch on a remote, for the lens tests (spec
2026-11-12-review-lenses R6, R7): `origin/main` holds `base_config` as
`.fr/lenses.yaml` (or no file), and the clone is on a feature branch."""

from __future__ import annotations

import subprocess
from pathlib import Path

ID = ["-c", "user.email=t@example.com", "-c", "user.name=t", "-c", "commit.gpgsign=false"]


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *ID, "-C", str(root), *args], check=True, capture_output=True, text=True
    ).stdout


def commit_all(root: Path, message: str = "work") -> None:
    git(root, "add", "-A")
    if git(root, "status", "--porcelain").strip():
        git(root, "commit", "-qm", message, "--no-verify")


def lens_repo(tmp_path: Path, base_config: str | None = None, branch: str = "feat/x") -> Path:
    remote = tmp_path / "origin.git"
    root = tmp_path / "work"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    (root / "README.md").write_text("# x\n")
    if base_config is not None:
        (root / ".fr").mkdir()
        (root / ".fr" / "lenses.yaml").write_text(base_config)
    commit_all(root, "base")
    git(root, "remote", "add", "origin", str(remote))
    git(root, "push", "-q", "origin", "main")
    git(root, "fetch", "-q", "origin")
    git(root, "remote", "set-head", "origin", "main")
    git(root, "switch", "-q", "-c", branch)
    return root
