"""Shared fixtures of the gate-backfill unit tests: real git histories in `tmp_path`, a fake
forge, and a fixed clock. Names are fictional (`example-org/widgets`)."""

from __future__ import annotations

import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)
REPO = "example-org/widgets"
SP = "docs/superpowers"
OWED_LABEL = {"name": "fr:owed"}
ME = "fr-bot"
STRANGER = "someone-else"


def git(repo: Path, *args: str, env: dict[str, str] | None = None) -> str:
    done = subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@e", "-c", "user.name=t",
         "-c", "commit.gpgsign=false", *args],
        check=True, capture_output=True, text=True, env={**os.environ, **(env or {})},
    )  # fmt: skip
    return done.stdout.strip()


def commit_at(repo: Path, msg: str, iso: str) -> str:
    """Commit everything at *iso*; returns the new sha."""
    env = {"GIT_AUTHOR_DATE": iso, "GIT_COMMITTER_DATE": iso}
    git(repo, "add", "-A", env=env)
    git(repo, "commit", "-q", "--allow-empty", "-m", msg, env=env)
    return git(repo, "rev-parse", "HEAD")


def make_repo(tmp_path: Path, name: str = "widgets") -> Path:
    """A repo on `main` with a bare `origin` and the example-org matrix identity."""
    repo = tmp_path / name
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    (repo / "README").write_text("x\n")
    write_matrix(repo, [])
    commit_at(repo, "init", "2026-01-01T00:00:00+00:00")
    bare = tmp_path / f"{name}.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
    git(repo, "remote", "add", "origin", str(bare))
    publish(repo)
    return repo


def publish(repo: Path) -> None:
    git(repo, "push", "-q", "origin", "HEAD:refs/heads/main")
    git(repo, "fetch", "-q", "origin")


def write_matrix(repo: Path, rows: list[dict[str, Any]]) -> None:
    org, name = REPO.split("/")
    p = repo / "docs" / "acceptance" / "matrix.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump({"schema_version": 5, "org": org, "repo": name, "rows": rows}))


def row(i: str, status: str, **kw: Any) -> dict[str, Any]:
    return {"id": i, "capability": "c", "acceptance": f"does {i}", "status": status, **kw}


def issue(
    number: int,
    title: str = "",
    body: str = "",
    labels: tuple[str, ...] = ("fr:owed",),
    author: str = ME,
) -> dict[str, Any]:
    return {
        "ref": f"{REPO}#{number}", "number": number, "title": title, "body": body,
        "labels": list(labels), "author": {"login": author},
    }  # fmt: skip


class FakeForge:
    """The `BackfillForge` port over plain dicts. Every read is recorded in `calls`."""

    def __init__(self) -> None:
        self.issues: list[dict[str, Any]] = []
        self.prs: dict[int, dict[str, Any]] = {}
        self.by_head: dict[str, list[int]] = {}
        self.linked: dict[int, list[int]] = {}
        self.by_commit: dict[str, list[int]] = {}
        self.commit_error: Exception | None = None
        self.calls: list[tuple[str, Any]] = []

    def add_pr(self, number: int, state: str = "MERGED", **kw: Any) -> None:
        self.prs[number] = {"state": state, "number": number, "labels": [], **kw}

    def pr_for_branch(self, branch: str) -> dict[str, Any] | None:
        return None

    def owed_issues(self) -> list[dict[str, Any]]:
        return [i for i in self.issues if "fr:owed" in i["labels"]]

    def open_issues(self) -> list[dict[str, Any]]:
        self.calls.append(("open_issues", None))
        return list(self.issues)

    def viewer_login(self) -> str:
        return ME

    def pr_view(self, number: int) -> dict[str, Any]:
        self.calls.append(("pr_view", number))
        return dict(self.prs[number])

    def prs_by_head(self, branch: str) -> list[dict[str, Any]]:
        self.calls.append(("prs_by_head", branch))
        return [dict(self.prs[n]) for n in self.by_head.get(branch, [])]

    def linked_prs(self, issue_number: int) -> list[dict[str, Any]]:
        self.calls.append(("linked_prs", issue_number))
        return [dict(self.prs[n]) for n in self.linked.get(issue_number, [])]

    def prs_for_commit(self, sha: str) -> list[dict[str, Any]]:
        self.calls.append(("prs_for_commit", sha))
        if self.commit_error is not None:
            raise self.commit_error
        return [dict(self.prs[n]) for n in self.by_commit.get(sha, [])]
