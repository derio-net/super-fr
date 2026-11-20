"""A real git world for the wave merge queue's executor (spec 2026-11-19-wave-merge-queue).

A bare origin stands in for the forge's git side, with a `main` holding a version
manifest and one branch per PR; `FakeForge` is the forge's API side, reading every PR's
head and its merged state from the bare origin (merged = its head is reachable from
`main`, as GitHub and GitLab decide after a push). Every git operation the executor
performs is real.
"""

from __future__ import annotations

import shlex
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fr.triage.gitseam import Checkout
from fr.triage.model import QueueEntryRef, VersionBlock
from fr.triage.queue_exec import EntryInput

REPO = "example-org/demo"
SCOPE = "example-org--demo"

SETV = """\
import pathlib, re, sys
p = pathlib.Path("pyproject.toml")
p.write_text(re.sub(r'^version = "[^"]*"', f'version = "{sys.argv[1]}"', p.read_text(), flags=re.M))
"""


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def identity(repo: Path) -> None:
    for key, value in (
        ("user.name", "test"),
        ("user.email", "test@example.com"),
        ("commit.gpgsign", "false"),
    ):
        git(repo, "config", key, value)


def version_block() -> VersionBlock:
    return VersionBlock.model_validate(
        {
            "source": {"file": "pyproject.toml", "key": "project.version"},
            "files": ["pyproject.toml"],
            "set": f"{shlex.quote(sys.executable)} scripts/setv.py {{version}}",
        }
    )


@dataclass
class World:
    origin: Path
    seed: Path
    clone: Path
    scratch: Path
    prs: dict[int, str] = field(default_factory=dict)  # number -> branch
    titles: dict[int, str] = field(default_factory=dict)

    @property
    def checkout(self) -> Checkout:
        return Checkout(self.clone)

    def remote(self, ref: str) -> str:
        return git(self.origin, "rev-parse", ref)

    def main(self) -> str:
        return self.remote("refs/heads/main")

    def head(self, number: int) -> str:
        return self.remote(f"refs/heads/{self.prs[number]}")

    def pr(
        self,
        number: int,
        files: dict[str, str],
        *,
        title: str | None = None,
        version: str | None = None,
        commits: int = 1,
    ) -> None:
        """A PR branch `feat/pr-<n>` cut from main, writing *files* (and *version*) over
        *commits* commits."""
        branch = f"feat/pr-{number}"
        git(self.seed, "fetch", "--quiet", "origin")
        git(self.seed, "checkout", "--quiet", "-B", branch, "origin/main")
        items = list(files.items())
        for i in range(commits):
            part = items[i::commits]
            for path, text in part:
                target = self.seed / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text)
            if version is not None and i == commits - 1:
                set_version(self.seed, version)
            git(self.seed, "add", "--all")
            git(self.seed, "commit", "--quiet", "--allow-empty", "-m", f"pr {number} part {i}")
        git(self.seed, "push", "--quiet", "--force", "origin", f"{branch}:{branch}")
        git(self.seed, "checkout", "--quiet", "--detach")
        self.prs[number] = branch
        self.titles[number] = title or f"change {number}"

    def push_to(self, number: int, files: dict[str, str]) -> str:
        """A session's push to PR *number*'s branch."""
        branch = self.prs[number]
        git(self.seed, "fetch", "--quiet", "origin")
        git(self.seed, "checkout", "--quiet", "-B", branch, f"origin/{branch}")
        for path, text in files.items():
            (self.seed / path).write_text(text)
        git(self.seed, "commit", "--quiet", "-am", f"session edit of {number}")
        git(self.seed, "push", "--quiet", "origin", f"{branch}:{branch}")
        git(self.seed, "checkout", "--quiet", "--detach")
        return self.head(number)

    def move_main(self, files: dict[str, str]) -> str:
        """A push to main the queue did not make."""
        git(self.seed, "fetch", "--quiet", "origin")
        git(self.seed, "checkout", "--quiet", "-B", "main", "origin/main")
        for path, text in files.items():
            (self.seed / path).write_text(text)
        git(self.seed, "add", "--all")
        git(self.seed, "commit", "--quiet", "-m", "foreign")
        git(self.seed, "push", "--quiet", "origin", "main")
        git(self.seed, "checkout", "--quiet", "--detach")
        return self.main()

    def entry(self, number: int, *, bump: str | None = None) -> EntryInput:
        return EntryInput(
            key=f"b{number}", ref=QueueEntryRef(batch=f"b{number}"), pr=number,
            title=self.titles[number], head=self.head(number), head_ref=self.prs[number],
            bump=bump,  # type: ignore[arg-type]
        )  # fmt: skip

    def fetch(self) -> None:
        git(self.clone, "fetch", "--quiet", "--prune", "origin")


def set_version(root: Path, version: str) -> None:
    text = (root / "pyproject.toml").read_text()
    lines = [f'version = "{version}"' if ln.startswith("version = ") else ln
             for ln in text.splitlines()]  # fmt: skip
    (root / "pyproject.toml").write_text("\n".join(lines) + "\n")


def world(tmp_path: Path) -> World:
    origin = tmp_path / "origin.git"
    git(tmp_path, "init", "--quiet", "--bare", "--initial-branch=main", str(origin))
    seed = tmp_path / "seed"
    git(tmp_path, "clone", "--quiet", str(origin), str(seed))
    identity(seed)
    git(seed, "checkout", "--quiet", "-b", "main")
    (seed / "pyproject.toml").write_text('[project]\nname = "demo"\nversion = "1.0.0"\n')
    (seed / "a.txt").write_text("alpha\n")
    (seed / "scripts").mkdir()
    (seed / "scripts" / "setv.py").write_text(SETV)
    git(seed, "add", "--all")
    git(seed, "commit", "--quiet", "-m", "seed")
    git(seed, "push", "--quiet", "origin", "main")
    clone = tmp_path / "clone"
    git(tmp_path, "clone", "--quiet", str(origin), str(clone))
    identity(clone)
    return World(origin=origin, seed=seed, clone=clone, scratch=tmp_path / "state" / "queue")


class FakeForge:
    """The forge's API side over a bare origin: a PR reads MERGED once its head is
    reachable from main (R35's property), unless *sticky* keeps it OPEN (a forge that
    did not notice). `pr_merge` merges at the pinned head in a worker clone."""

    def __init__(self, w: World, worker: Path) -> None:
        self.w, self.worker = w, worker
        self.merges: list[tuple[int, str, str]] = []
        self.sticky: set[int] = set()
        self.refuse: dict[int, str] = {}
        self.checks: dict[str, list[dict[str, Any]]] = {}
        self.required: list[str] = []
        self.main_after_merge: str | None = None  # a file a "forge" merge adds (mismatch)

    def pr_view(self, repo: str, number: int) -> dict[str, Any]:
        head = self.w.head(number)
        merged = number not in self.sticky and subprocess.run(
            ["git", "merge-base", "--is-ancestor", head, "refs/heads/main"], cwd=self.w.origin
        ).returncode == 0
        return {"state": "MERGED" if merged else "OPEN", "head_oid": head,
                "head_ref": self.w.prs[number], "title": self.w.titles[number]}  # fmt: skip

    def pr_merge(self, repo: str, number: int, *, head_sha: str, method: str) -> None:
        if number in self.refuse:
            raise RuntimeError(self.refuse[number])
        assert self.w.head(number) == head_sha, "--match-head-commit"
        self.merges.append((number, head_sha, method))
        git(self.worker, "fetch", "--quiet", "origin")
        git(self.worker, "checkout", "--quiet", "-B", "main", "origin/main")
        if method == "squash":
            git(self.worker, "merge", "--quiet", "--squash", head_sha)
            git(self.worker, "commit", "--quiet", "-m", f"{self.w.titles[number]} (#{number})")
        else:
            git(self.worker, "merge", "--quiet", "--no-ff", "-m",
                f"Merge pull request #{number} from {self.w.prs[number]}", head_sha)  # fmt: skip
        if self.main_after_merge is not None:
            (self.worker / self.main_after_merge).write_text("forge drift\n")
            git(self.worker, "add", "--all")
            git(self.worker, "commit", "--quiet", "-m", "forge drift")
        git(self.worker, "push", "--quiet", "origin", "main")

    def commit_checks(self, repo: str, sha: str) -> list[dict[str, Any]]:
        return self.checks.get(sha, [])

    def required_check_names(self, repo: str, base: str) -> list[str]:
        return list(self.required)


def forge(w: World, tmp_path: Path) -> FakeForge:
    worker = tmp_path / "worker"
    git(tmp_path, "clone", "--quiet", str(w.origin), str(worker))
    identity(worker)
    return FakeForge(w, worker)
