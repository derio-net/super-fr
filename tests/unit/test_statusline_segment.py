"""fr-statusline-segment.sh — golden outputs, contract v2 (spec 2026-09-14 §5.A).

The segment answers two questions for a status line: which branch is this
session working on, and is it inside an fr-isolation workspace? ``--format
plain`` (the default) prints exactly three plain lines:

1. the state — ``fr`` or ``none``;
2. ``branch: <b>`` or ``no branch``;
3. ``worktree: <abs path>`` or ``no fr-isolation``.

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
import time
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
GREEN = "\x1b[32m"
PURPLE = "\x1b[35m"
RESET = "\x1b[0m"


# cwd is not a git repo: the "none" rows, exit 0.
def test_not_a_git_repo(world: World, tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    assert _plain(world.run(plain)) == NONE


# cwd does not exist at all: still the "none" rows, exit 0.
def test_missing_cwd(world: World, tmp_path: Path) -> None:
    assert _plain(world.run(tmp_path / "nope")) == NONE


# Bound session from the base clone: the binding wins.
def test_bound_from_base_clone(world: World) -> None:
    world.bind()
    assert _plain(world.run(world.repo)) == ("fr", "branch: feat/x", f"worktree: {world.featx}")


# A binding wins even when the cwd is not a repo.
def test_bound_from_non_repo_cwd(world: World, tmp_path: Path) -> None:
    world.bind()
    plain = tmp_path / "plain"
    plain.mkdir()
    assert _plain(world.run(plain)) == ("fr", "branch: feat/x", f"worktree: {world.featx}")


# A stale binding (worktree directory gone) falls back to the cwd rule.
def test_stale_binding_ignored(world: World) -> None:
    world.bind()
    shutil.rmtree(world.featx)
    assert _plain(world.run(world.repo)) == ("none", "branch: main", "no fr-isolation")


# Unbound base clone: the cwd branch, no fr, other sessions' workspaces NOT named.
def test_unbound_base_clone(world: World) -> None:
    assert _plain(world.run(world.repo)) == ("none", "branch: main", "no fr-isolation")


# Unbound, cwd inside the fr workspace (and in a subdirectory of it).
def test_unbound_inside_fr_workspace(world: World) -> None:
    expected = ("fr", "branch: feat/x", f"worktree: {world.featx}")
    assert _plain(world.run(world.featx, sid=None)) == expected
    sub = world.featx / "sub"
    sub.mkdir()
    assert _plain(world.run(sub, sid=None)) == expected


# A subdirectory of the base clone still resolves the repo.
def test_base_clone_subdirectory(world: World) -> None:
    sub = world.repo / "sub"
    sub.mkdir()
    assert _plain(world.run(sub)) == ("none", "branch: main", "no fr-isolation")


# A plain linked worktree is not fr.
def test_plain_linked_worktree(world: World) -> None:
    assert _plain(world.run(world.blog)) == ("none", "branch: docs/blog", "no fr-isolation")


# A native detached agent worktree: no branch, not fr.
def test_detached_agent_worktree(world: World) -> None:
    agent = world.repo / ".claude" / "worktrees" / "agent-1"
    _git(world.repo, "worktree", "add", "-q", "--detach", str(agent))
    assert _plain(world.run(agent)) == NONE


def test_missing_session_id_is_unbound(world: World) -> None:
    world.bind()
    assert _plain(world.run(world.repo, sid=None)) == ("none", "branch: main", "no fr-isolation")


def test_unknown_session_id_is_unbound(world: World) -> None:
    world.bind()
    assert _plain(world.run(world.repo, sid="sess-gone"))[0] == "none"


# A path-like session id never escapes the sessions dir.
def test_path_like_session_id_is_unbound(world: World) -> None:
    world.bind()
    assert _plain(world.run(world.repo, sid="../sessions/sess-1"))[0] == "none"


# --cwd reads no stdin: a stdin left OPEN must not hang.
def test_cwd_flag_reads_no_stdin(world: World) -> None:
    proc = subprocess.Popen(
        ["bash", str(SCRIPT), "--cwd", str(world.featx)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=world.env(),
    )
    try:
        assert proc.wait(timeout=5) == 0
        assert proc.stdout is not None
        out = proc.stdout.read()
    finally:
        assert proc.stdin is not None
        proc.stdin.close()
        proc.kill()
    assert out == f"fr\nbranch: feat/x\nworktree: {world.featx}\n"


def test_ansi_colours(world: World) -> None:
    world.bind()
    assert world.run(world.repo, "sess-1", "--format", "ansi").stdout == (
        f"{GREEN}branch: feat/x{RESET}\n{GREEN}worktree: {world.featx}{RESET}\n"
    )
    assert world.run(world.repo, None, "--format", "ansi").stdout == (
        f"{PURPLE}branch: main{RESET}\n{PURPLE}no fr-isolation{RESET}\n"
    )


def test_oneline(world: World, tmp_path: Path) -> None:
    world.bind()
    assert world.run(world.repo, "sess-1", "--format", "oneline").stdout == "fr:feat/x\n"
    assert world.run(world.repo, None, "--format", "oneline").stdout == "main\n"
    out = world.run(world.blog, None, "--cwd", str(tmp_path), "--format", "oneline").stdout
    assert out == "no branch\n"
    assert len(out.strip()) <= 40
    assert "\x1b" not in out


def test_unknown_format_falls_back_to_plain(world: World) -> None:
    assert _plain(world.run(world.repo, None, "--format", "bogus"))[0] == "none"


# Timing guard: CI gets a generous 0.5 s so a slow runner never flakes, but a
# stray fr call (4 s) fails.
def test_runs_well_under_budget(world: World) -> None:
    world.bind()
    world.run(world.repo)  # warm caches
    t0 = time.perf_counter()
    _plain(world.run(world.repo))
    assert time.perf_counter() - t0 < 0.5


# The script must never reach for the fr CLI: a trap fr first on PATH must not
# be invoked (and would blow the timing budget if it were).
def test_never_invokes_fr(world: World, tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    trap = bin_dir / "fr"
    trap.write_text('#!/bin/bash\necho TRAPPED >> "$FR_TRAP"\nexit 1\n')
    trap.chmod(0o755)
    log = tmp_path / "trap.log"
    world.bind()
    _plain(
        world.run(
            world.repo,
            PATH=f"{bin_dir}:{os.environ.get('PATH', '')}",
            FR_TRAP=str(log),
        )
    )
    assert not log.exists()
