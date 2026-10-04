"""The routine-commit reads of `fr.triage.gitseam.Checkout` against real git (gh#927).

A PR branch forks from main; main then gains a release commit (versions bumped
across TOML, JSON and a lockfile, its `.changes/` fragment deleted), a
close-out merge (an artifact moved into `docs/superpowers/implemented/`) and,
in the last test, a code change. The reads must report exactly those commits
with their files, and `_behind_only_routinely` must judge them as the driver
would.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from fr.triage.batch_merge import MergeContext, _behind_only_routinely
from fr.triage.gitseam import Checkout


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def _write(root: Path, files: dict[str, str]) -> None:
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text)


def _commit(root: Path, message: str) -> None:
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", message)


def _manifests(version: str) -> dict[str, str]:
    return {
        "pyproject.toml": f'[project]\nname = "demo"\nversion = "{version}"\n',
        "package.json": json.dumps({"name": "demo", "version": version}, indent=2) + "\n",
        "uv.lock": f'[[package]]\nname = "demo"\nversion = "{version}"\nsource = 1\n',
    }


def _world(tmp_path: Path) -> tuple[Checkout, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    for key, value in (("user.name", "t"), ("user.email", "t@example.com")):
        _git(repo, "config", key, value)
    _git(repo, "config", "commit.gpgsign", "false")
    _write(
        repo,
        {
            **_manifests("1.0.0"),
            "a.py": "a = 1\n",
            "docs/superpowers/journals/debug/x.md": "# x\n",
            ".changes/feat-x.yaml": "bump: patch\nsummary: x\n",
        },
    )
    _commit(repo, "seed")
    _git(repo, "switch", "-q", "-c", "pr")
    _write(repo, {"a.py": "a = 2\n"})
    _commit(repo, "the PR")
    _git(repo, "switch", "-q", "main")
    _write(repo, _manifests("1.0.1"))
    (repo / ".changes/feat-x.yaml").unlink()
    _commit(repo, "release: v1.0.1")
    _git(repo, "mv", "docs/superpowers/journals", "docs/superpowers/implemented")
    _commit(repo, "chore: close out feat/x")
    _git(tmp_path, "clone", "-q", str(repo), "clone")  # origin/HEAD is what ctx.main reads
    return Checkout(tmp_path / "clone"), repo


def _ctx(checkout: Checkout) -> MergeContext:
    return MergeContext(
        client=None,  # type: ignore[arg-type]
        checkout=checkout,
        repo="example-org/demo",
        version=None,
        scratch_root=Path("/nonexistent"),
        method="squash",
        say=lambda line: None,
    )


def test_the_reads_report_the_commits_main_gained_with_their_files(tmp_path: Path) -> None:
    checkout, _ = _world(tmp_path)
    (_, archive), (_, release) = checkout.commits_behind("origin/pr", "origin/main")
    assert sorted(release) == [
        ("D", ".changes/feat-x.yaml"),
        ("M", "package.json"),
        ("M", "pyproject.toml"),
        ("M", "uv.lock"),
    ]
    assert sorted(archive) == [
        ("A", "docs/superpowers/implemented/debug/x.md"),
        ("D", "docs/superpowers/journals/debug/x.md"),
    ]
    assert checkout.changed_paths("origin/main", "origin/pr") == {"a.py"}


def test_a_pr_behind_only_by_a_release_and_a_close_out_is_routinely_behind(
    tmp_path: Path,
) -> None:
    checkout, _ = _world(tmp_path)
    assert _behind_only_routinely(_ctx(checkout), "origin/pr")


def test_one_code_commit_on_main_makes_it_a_real_behind(tmp_path: Path) -> None:
    checkout, repo = _world(tmp_path)
    _write(repo, {"b.py": "b = 1\n"})
    _commit(repo, "feat: b")
    checkout.fetch()
    assert not _behind_only_routinely(_ctx(checkout), "origin/pr")
