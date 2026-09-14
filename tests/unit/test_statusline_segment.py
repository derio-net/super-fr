"""fr-statusline-segment.sh — golden outputs, contract v2 (spec 2026-09-14 §5.A).

The segment answers two questions for a status line: which branch is this
session working on, and is it inside an fr-isolation workspace? ``--format
plain`` (the default) prints exactly three plain lines:

1. the state — ``fr`` | ``none``;
2. ``branch: <b>`` | ``no branch``;
3. ``worktree: <abs path>`` | ``no fr-isolation``.

Input is Claude Code status-line JSON on stdin, or ``--cwd <dir>``, which
reads NO stdin (Hermes runs the command without JSON). ``--format ansi``
prints rows 2-3 coloured (green ``fr``, purple ``none``); ``--format oneline``
prints ``fr:<branch>`` | ``<branch>`` for a 40-char slot. Shell + jq + git
only — the fr CLI is never invoked (4 s). Filed under the acceptance level
``int`` (subprocess; see journal 62c39ba6fb84).

Fixture: a repo ``home/Docs/acme`` (branch main) with two linked worktrees —
``home/Docs/acme/.worktrees/blog`` (docs/blog, a plain git worktree) and
``home/.cache/fr/worktrees/acme/feat__x`` (feat/x, an fr workspace with a
state file) — and, per case, a session index written by ``sessions.attach``.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest
from fr.isolation import sessions
from fr.isolation.types import IsolationState, save_state

pytestmark = pytest.mark.skipif(shutil.which("jq") is None, reason="segment script requires jq")

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "plugins" / "super-fr" / "scripts" / "fr-statusline-segment.sh"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@dataclass
class World:
    home: Path
    repo: Path
    blog: Path
    featx: Path
    sessions_dir: Path

    def bind(self, sid: str = "sess-1") -> None:
        sessions.attach(self.repo, "feat/x", sid, "claude")

    def env(self, **extra: str) -> dict[str, str]:
        env = {**os.environ, "HOME": str(self.home), "FR_SESSIONS_DIR": str(self.sessions_dir)}
        env.pop("STATUSLINE_WT_WIDTH", None)
        env.update(extra)
        return env

    def run(
        self, cwd: Path | str, sid: str | None = "sess-1", *args: str, **extra: str
    ) -> subprocess.CompletedProcess[str]:
        payload: dict[str, object] = {"workspace": {"current_dir": str(cwd)}, "cwd": str(cwd)}
        if sid is not None:
            payload["session_id"] = sid
        return subprocess.run(
            ["bash", str(SCRIPT), *args],
            input=json.dumps(payload),
            env=self.env(**extra),
            capture_output=True,
            text=True,
            check=False,
        )


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> World:
    home = tmp_path.resolve() / "home"
    repo = home / "Docs" / "acme"
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    _git(repo, "commit", "-q", "--allow-empty", "-m", "init")
    blog = repo / ".worktrees" / "blog"
    _git(repo, "worktree", "add", "-q", "-b", "docs/blog", str(blog))
    featx = home / ".cache" / "fr" / "worktrees" / "acme" / "feat__x"
    _git(repo, "worktree", "add", "-q", "-b", "feat/x", str(featx))
    save_state(
        IsolationState(
            repo_root=repo,
            branch="feat/x",
            worktree=featx,
            profile="host",
            created_at="2026-09-05T00:00:00+00:00",
        )
    )
    sessions_dir = home / ".cache" / "fr" / "sessions"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("FR_SESSIONS_DIR", str(sessions_dir))
    return World(home=home, repo=repo, blog=blog, featx=featx, sessions_dir=sessions_dir)


def _plain(res: subprocess.CompletedProcess[str]) -> tuple[str, str, str]:
    assert res.returncode == 0, res.stderr
    assert res.stdout.endswith("\n"), res.stdout
    lines = res.stdout[:-1].split("\n")
    assert len(lines) == 3, f"plain output must be exactly three lines: {res.stdout!r}"
    return lines[0], lines[1], lines[2]


NONE = ("none", "no branch", "no fr-isolation")


# cwd is not a git repo: the "none" rows, exit 0.
def test_not_a_git_repo(world: World, tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    assert _plain(world.run(plain)) == NONE


# cwd does not exist at all: still the "none" rows, exit 0.
def test_missing_cwd(world: World, tmp_path: Path) -> None:
    assert _plain(world.run(tmp_path / "nope")) == NONE
