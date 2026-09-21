"""Two limits #534 stated and did not fix (spec 2026-09-21 §2.F), now closed.

1. The 48h GC keys on mtime, and nothing refreshed a live sentinel. A pipeline
   that ran 48h without loading a skill or binding a workspace was deleted by
   ANY session's next skill load — its guard silently gone. The guard now
   refreshes the mtime on every Bash call it sees for the session, so the age
   means "time since this session last did anything", and only abandoned
   sessions expire.

2. Every writer of a sentinel read-modified-renamed it with no coordination:
   the skill-load hook, `attach` (the bind), `down`'s clear and the guard's own
   heal. Interleaved, one erased the other's update — and because the heal asks
   "does ANY recorded workspace survive?", a lost entry can fail OPEN (the
   sentinel is retired while the lost workspace is live). They now share one
   lock: a `<sentinel>.lock` directory, created with `mkdir` (atomic, and the
   one primitive bash on macOS and Python both have), broken when stale.

The lock tests hold the lock themselves and prove each writer WAITS for it —
the property that makes interleaving impossible — rather than trying to win a
real race, which would be a test that passes by luck.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from fr.isolation.types import IsolationState, save_state, stamp_sentinel_workspace

pytestmark = pytest.mark.skipif(shutil.which("jq") is None, reason="hook scripts require jq")

HOOKS = Path(__file__).resolve().parents[2] / "plugins" / "super-fr" / "hooks"
SESSION = "sess-1"
HOURS_49 = 49 * 3600


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@example.com", "-c", "user.name=t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


class World:
    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.home = tmp_path / "home"
        self.home.mkdir()
        self.sentinels = tmp_path / "sentinels"
        monkeypatch.setenv("HOME", str(self.home))
        monkeypatch.setenv("FR_SENTINEL_DIR", str(self.sentinels))
        monkeypatch.setenv("FR_SESSIONS_DIR", str(tmp_path / "sessions"))
        bindir = str(Path(sys.executable).parent)
        monkeypatch.setenv("PATH", bindir + os.pathsep + os.environ.get("PATH", ""))
        self.env = {**os.environ}

    def sentinel(self, session: str = SESSION) -> Path:
        return self.sentinels / f"{session}.json"

    def lock(self, session: str = SESSION) -> Path:
        return self.sentinels / f"{session}.json.lock"

    def repo(self, name: str = "proj") -> Path:
        repo = self.home / "src" / name
        repo.mkdir(parents=True)
        _git(repo, "init", "-q", "-b", "main")
        _git(repo, "commit", "-q", "--allow-empty", "-m", "init")
        return repo

    def worktree(self, repo: Path, branch: str) -> Path:
        wt = self.home / ".cache" / "fr" / "worktrees" / repo.name / branch.replace("/", "__")
        wt.parent.mkdir(parents=True, exist_ok=True)
        _git(repo, "worktree", "add", "-q", str(wt), "-b", branch)
        save_state(
            IsolationState(
                repo_root=repo,
                branch=branch,
                worktree=wt,
                profile="host",
                created_at="2026-09-22T00:00:00+00:00",
            )
        )
        return wt

    def _hook(self, name: str, payload: dict[str, object]) -> subprocess.Popen[str]:
        proc = subprocess.Popen(
            ["bash", str(HOOKS / name)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=self.env,
        )
        assert proc.stdin is not None
        proc.stdin.write(json.dumps(payload))
        proc.stdin.close()
        return proc

    def load_skill(self, repo: Path, session: str = SESSION) -> subprocess.Popen[str]:
        return self._hook(
            "fr-pipeline-sentinel.sh",
            {
                "session_id": session,
                "cwd": str(repo),
                "tool_name": "Skill",
                "tool_input": {"skill": "super-fr:fr-goal"},
            },
        )

    def guard(self, command: str, cwd: Path, session: str = SESSION) -> subprocess.Popen[str]:
        return self._hook(
            "fr-isolation-guard.sh",
            {
                "session_id": session,
                "cwd": str(cwd),
                "tool_name": "Bash",
                "tool_input": {"command": command},
            },
        )

    def bind(self, command: str, cwd: Path) -> subprocess.Popen[str]:
        return self._hook(
            "fr-session-bind.sh",
            {
                "session_id": SESSION,
                "cwd": str(cwd),
                "tool_name": "Bash",
                "tool_input": {"command": command},
            },
        )

    def workspaces(self) -> list[str]:
        return list(json.loads(self.sentinel().read_text()).get("workspaces", []))


def done(proc: subprocess.Popen[str], timeout: float = 20) -> str:
    out, err = proc.communicate(timeout=timeout)
    assert proc.returncode == 0, err
    return out


def _age(path: Path, seconds: float) -> None:
    t = time.time() - seconds
    os.utime(path, (t, t))


@pytest.fixture()
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> World:
    return World(tmp_path, monkeypatch)


# --- 1. liveness: an active session's sentinel never expires --------------------


class TestActivityKeepsTheSentinelAlive:
    def test_any_bash_call_refreshes_the_sentinel(self, world: World) -> None:
        repo = world.repo()
        done(world.load_skill(repo))
        _age(world.sentinel(), HOURS_49)
        done(world.guard("ls", repo))
        assert time.time() - world.sentinel().stat().st_mtime < 60

    def test_a_call_from_the_worktree_counts_too(self, world: World) -> None:
        """Most of a pipeline's commands run in its worktree, where the guard
        exits early (not the base repo). That is still activity."""
        repo = world.repo()
        wt = world.worktree(repo, "feat/x")
        done(world.load_skill(repo))
        _age(world.sentinel(), HOURS_49)
        done(world.guard("git status", wt))
        assert time.time() - world.sentinel().stat().st_mtime < 60

    def test_an_active_pipeline_survives_another_sessions_gc(self, world: World) -> None:
        repo = world.repo()
        done(world.load_skill(repo))
        _age(world.sentinel(), HOURS_49)
        done(world.guard("ls", repo))  # the session is still working
        done(world.load_skill(repo, session="other"))  # its GC sweeps the dir
        assert world.sentinel().exists()
        assert done(world.guard("ls", repo)), "still armed: a deny was printed"

    def test_an_abandoned_sentinel_still_expires(self, world: World) -> None:
        repo = world.repo()
        done(world.load_skill(repo))
        _age(world.sentinel(), HOURS_49)
        done(world.load_skill(repo, session="other"))
        assert not world.sentinel().exists()

    def test_the_refresh_never_creates_a_sentinel(self, world: World) -> None:
        """`touch -c`: a sentinel retired between the guard's existence check and
        its refresh must stay retired, not reappear empty."""
        repo = world.repo()
        world.sentinels.mkdir()
        done(world.guard("ls", repo))
        assert not world.sentinel().exists()


# --- 2. one lock for every writer -----------------------------------------------


def _hold_lock(world: World) -> Path:
    lock = world.lock()
    lock.mkdir(parents=True)
    return lock


def _still_running(proc: subprocess.Popen[str], after: float = 0.6) -> bool:
    time.sleep(after)
    return proc.poll() is None


class TestEveryWriterWaitsForTheLock:
    def test_the_skill_load_hook_waits(self, world: World) -> None:
        repo = world.repo()
        done(world.load_skill(repo))
        before = world.sentinel().read_bytes()
        lock = _hold_lock(world)
        proc = world.load_skill(repo)
        assert _still_running(proc), "wrote without the lock"
        assert world.sentinel().read_bytes() == before
        lock.rmdir()
        done(proc)
        assert not lock.exists(), "released after the write"

    def test_the_bind_waits(self, world: World) -> None:
        repo = world.repo()
        done(world.load_skill(repo))
        wt = world.worktree(repo, "feat/x")
        lock = _hold_lock(world)
        t = threading.Thread(target=stamp_sentinel_workspace, args=(SESSION, wt))
        t.start()
        time.sleep(0.6)
        assert t.is_alive(), "stamped without the lock"
        assert world.workspaces() == []
        lock.rmdir()
        t.join(timeout=20)
        assert world.workspaces() == ["worktrees/proj/feat__x"]

    def test_the_guards_heal_waits_and_rechecks(self, world: World) -> None:
        """The heal is a writer too (it deletes). It must decide under the lock:
        a bind that lands while it waits can turn 'orphaned' back into 'live'."""
        repo = world.repo()
        done(world.load_skill(repo))
        gone = world.worktree(repo, "feat/gone")
        stamp_sentinel_workspace(SESSION, gone)
        _git(repo, "worktree", "remove", "--force", str(gone))  # orphaned now

        lock = _hold_lock(world)
        proc = world.guard("ls", repo)
        assert _still_running(proc)
        live = world.worktree(repo, "feat/live")  # the bind that won the race
        data = json.loads(world.sentinel().read_text())
        data["workspaces"] = ["worktrees/proj/feat__gone", "worktrees/proj/feat__live"]
        world.sentinel().write_text(json.dumps(data))
        lock.rmdir()
        out = done(proc)
        assert world.sentinel().exists(), "healed on a stale read"
        assert live.is_dir() and '"deny"' in out

    def test_a_stale_lock_is_broken(self, world: World) -> None:
        """A writer that died holding the lock must not wedge the session."""
        repo = world.repo()
        lock = _hold_lock(world)
        _age(lock, 120)
        started = time.monotonic()
        done(world.load_skill(repo))
        assert time.monotonic() - started < 5
        assert world.sentinel().exists() and not lock.exists()

    def test_the_real_bind_path_and_a_reload_do_not_lose_an_entry(self, world: World) -> None:
        """Both writers at once, through the real hooks, many times. Not the
        proof (the waiting tests are); a smoke test that the protocol holds."""
        repo = world.repo()
        done(world.load_skill(repo))
        for i in range(8):
            world.worktree(repo, f"feat/w{i}")
            bind = world.bind(f"fr isolation up --branch feat/w{i}", repo)
            load = world.load_skill(repo)
            done(bind)
            done(load)
        assert sorted(world.workspaces()) == sorted(f"worktrees/proj/feat__w{i}" for i in range(8))


# --- the happy path's other ending, end to end ----------------------------------


def test_down_through_the_real_cli_retires_the_sentinel(world: World) -> None:
    """#534 pinned `down`'s clear at the CLI level with a fake runner only."""
    repo = world.repo()
    done(world.load_skill(repo))
    wt = world.worktree(repo, "feat/x")
    done(world.bind("fr run start fr-goal --branch feat/x", repo))
    assert world.workspaces() == ["worktrees/proj/feat__x"]
    res = subprocess.run(
        ["fr", "isolation", "down", "--repo", str(repo), "--branch", "feat/x", "--force"],
        cwd=repo,
        env={**world.env, "FR_ISOLATION_TARGET": "worktree"},  # docker-less host mode
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, res.stdout + res.stderr
    assert not wt.exists()
    assert not world.sentinel().exists()
