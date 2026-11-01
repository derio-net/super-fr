"""Reap the `agent-*` subagent worktrees Claude Code never removes (gh#1270).

`fr-worktree-create.sh` is a registered WorktreeCreate hook, so it replaces
Claude Code's native worktree creation, and the native lifecycle goes with it:
Claude takes no lock while the subagent runs and, measured on Claude Code
2.1.316, never fires WorktreeRemove for a subagent. Nothing removed them; frank
piled up 31 (4 nested) before Claude refused new isolated dispatches.

The hook now files them under `~/.cache/fr/agent-worktrees/<repo-key>/<name>`
and locks each with the Claude process's pid. This sweep, part of `fr isolation
gc`, removes one only when ALL of these hold, and reports every other one:

- no live session holds it: an `fr-agent pid=<N>` lock whose pid is alive is a
  running subagent; any other lock is someone else's and is respected. The pid
  is the PARENT session's, which can outlive its subagents by days (a driver, a
  coordinator) or be reused once it exits, so past `AGENT_MAX_LOCK_AGE_SECONDS`
  a live lock no longer protects;
- it is at least `AGENT_MIN_AGE_SECONDS` old, even with a dead lock pid (that
  pid is the hook's parent; the age is the backstop if it is ever not Claude);
- `git status --porcelain` is empty (untracked files count; ignored ones don't);
- every commit on its HEAD is reachable from a branch, tag or remote ref.
  Ancestry, never PR state: removing the checkout loses nothing a ref keeps.

Host-wide, like the rest of gc: candidates are the `agent-*` worktrees, cached
or legacy in-repo `.claude/worktrees/agent-*` (nested ones removed child first),
of the invoking repo and of every repo with a worktree in the cache. A
directory deleted under fr's own dead lock is unlocked and pruned, since `git
worktree prune` never prunes a locked entry.
"""

from __future__ import annotations

import fcntl
import os
import re
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import IO

from .local import GcAction, _home

AGENT_MIN_AGE_SECONDS = 24 * 3600
AGENT_MAX_LOCK_AGE_SECONDS = 72 * 3600
AGENT_NAME = re.compile(r"^agent-[0-9a-z]+$")
FR_LOCK = re.compile(r"^fr-agent pid=(\d+)\b")
VERDICT = "agent-worktree"


def agent_cache_root() -> Path:
    """Where fr-worktree-create.sh files `agent-*` worktrees. Kept beside, not
    inside, `~/.cache/fr/worktrees`, whose every `<repo>/<child>` gc reads as an
    fr workspace."""
    return _home() / ".cache" / "fr" / "agent-worktrees"


@dataclass(frozen=True)
class _Entry:
    path: Path
    common: Path
    lock: str | None  # None: unlocked; "" : locked with no reason


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(cwd), *args], capture_output=True, text=True, check=False
    )


def _common_dir(path: Path) -> Path | None:
    r = _git(path, "rev-parse", "--path-format=absolute", "--git-common-dir")
    return Path(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else None


def _entries(common: Path) -> list[_Entry]:
    r = _git(common, "worktree", "list", "--porcelain")
    if r.returncode != 0:
        return []
    out: list[_Entry] = []
    for block in r.stdout.split("\n\n"):
        path: Path | None = None
        lock: str | None = None
        for line in block.splitlines():
            if line.startswith("worktree "):
                path = Path(line[len("worktree ") :])
            elif line == "locked":
                lock = ""
            elif line.startswith("locked "):
                lock = line[len("locked ") :]
        if path is not None:
            out.append(_Entry(path, common, lock))
    return out


def _is_agent(path: Path, cache: Path) -> bool:
    if not AGENT_NAME.match(path.name):
        return False
    legacy = path.parent.name == "worktrees" and path.parent.parent.name == ".claude"
    try:
        cached = path.resolve().parent.parent == cache.resolve()
    except OSError:
        cached = False
    return legacy or cached


def _candidates(repo_root: Path) -> list[_Entry]:
    cache = agent_cache_root()
    commons: set[Path] = set()
    own = _common_dir(repo_root) if repo_root.is_dir() else None
    if own is not None:
        commons.add(own)
    if cache.is_dir():
        for key in cache.iterdir():
            if not key.is_dir():
                continue
            for wt in key.iterdir():
                if wt.is_dir() and AGENT_NAME.match(wt.name):
                    c = _common_dir(wt)
                    if c is not None:
                        commons.add(c)
    seen: set[Path] = set()
    found: list[_Entry] = []
    for common in sorted(commons):
        for e in _entries(common):
            key_path = e.path.resolve() if e.path.exists() else e.path
            if key_path in seen or not _is_agent(e.path, cache):
                continue
            seen.add(key_path)
            found.append(e)
    # Deepest first: a nested legacy worktree must go before the one holding it.
    return sorted(found, key=lambda e: (-len(e.path.parts), str(e.path)))


def _age(path: Path, now: float) -> float:
    for p in (path / ".git", path):
        try:
            return now - p.stat().st_mtime
        except OSError:
            continue
    return 0.0


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, owned by someone else
    return True


def _hold(e: _Entry, now: float, pid_alive: Callable[[int], bool]) -> tuple[str, str] | None:
    """(action, detail) when the worktree must stay, else None."""
    m = FR_LOCK.match(e.lock) if e.lock is not None else None
    if e.lock is not None and m is None:
        return ("skipped", f"locked: {e.lock or 'no reason given'}")
    pid = int(m.group(1)) if m is not None else None
    live = pid is not None and pid_alive(pid)
    if not e.path.is_dir():
        if live:
            return ("skipped", f"directory gone; session pid {pid} is alive")
        return None  # unlock + prune: nothing on disk to lose
    age = _age(e.path, now)
    if live and age < AGENT_MAX_LOCK_AGE_SECONDS:
        return ("skipped", f"running: session pid {pid} is alive")
    if age < AGENT_MIN_AGE_SECONDS:
        return ("skipped", f"younger than {AGENT_MIN_AGE_SECONDS // 3600}h")
    status = _git(e.path, "status", "--porcelain")
    if status.returncode != 0:
        return ("warned", f"git status failed, kept: {status.stderr.strip()}")
    if status.stdout.strip():
        return ("warned", "uncommitted or untracked changes, kept")
    lost = _git(e.path, "rev-list", "-n1", "HEAD", "--not", "--branches", "--tags", "--remotes")
    if lost.returncode != 0:
        return ("warned", f"cannot check ancestry, kept: {lost.stderr.strip()}")
    if lost.stdout.strip():
        return ("warned", "commits no branch, tag or remote reaches, kept")
    return None


def _log(line: str) -> None:
    log = agent_cache_root() / "reap.log"
    try:
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a") as fh:
            fh.write(f"{datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')} {line}\n")
    except OSError:
        pass  # the GcAction report still carries it


def _remove(e: _Entry) -> str | None:
    """Remove one worktree; the error text on failure."""
    if e.lock is not None:
        _git(e.common, "worktree", "unlock", str(e.path))
    if not e.path.is_dir():
        r = _git(e.common, "worktree", "prune")
        return None if r.returncode == 0 else (r.stderr.strip() or "git worktree prune failed")
    r = _git(e.common, "worktree", "remove", str(e.path))
    if r.returncode != 0:
        return r.stderr.strip() or "git worktree remove failed"
    parent = e.path.parent
    if parent.parent.resolve() == agent_cache_root().resolve():
        try:
            parent.rmdir()  # only when empty
        except OSError:
            pass
    return None


def sweep_agent_worktrees(
    repo_root: Path,
    *,
    dry_run: bool,
    now: float | None = None,
    pid_alive: Callable[[int], bool] = _pid_alive,
) -> list[GcAction]:
    """Classify and (unless `dry_run`) reap finished subagent worktrees. Never
    raises for one worktree: each failure is that worktree's `reap-failed`."""
    t = time.time() if now is None else now
    lock = _sweep_lock()
    if lock is None:
        return []  # another sweep is running; the next dispatch or gc re-runs it
    try:
        return _sweep(repo_root, dry_run, t, pid_alive)
    finally:
        lock.close()


def _sweep_lock() -> IO[str] | None:
    """Non-blocking flock: every agent dispatch fires a sweep, so concurrent
    ones are routine; the loser simply returns."""
    path = agent_cache_root() / ".sweep.lock"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fh = open(path, "w")  # noqa: SIM115 — held for the sweep, closed by the caller
    except OSError:
        return None
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return None
    return fh


def _sweep(
    repo_root: Path, dry_run: bool, t: float, pid_alive: Callable[[int], bool]
) -> list[GcAction]:
    out: list[GcAction] = []
    for e in _candidates(repo_root):
        held = _hold(e, t, pid_alive)
        if held is not None:
            action = "would-skip" if dry_run and held[0] == "skipped" else held[0]
            out.append(GcAction(str(e.path), None, VERDICT, action, held[1]))
            continue
        if dry_run:
            out.append(GcAction(str(e.path), None, VERDICT, "would-reap", "finished and clean"))
            continue
        err = _remove(e)
        if err is None:
            _log(f"reaped {e.path} (repo {e.common})")
            out.append(GcAction(str(e.path), None, VERDICT, "reaped", "finished and clean"))
        else:
            _log(f"reap-failed {e.path}: {err}")
            out.append(GcAction(str(e.path), None, VERDICT, "reap-failed", err))
    return out
