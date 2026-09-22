"""State, profiles, and the Target protocol for fr isolation."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Literal, Protocol

import yaml
from pydantic import BaseModel, Field, ValidationError

from fr.artifacts.atomic import write_text_atomic


def _home() -> Path:
    return Path(os.environ.get("HOME", str(Path.home())))


IsolationMode = Literal["devcontainer", "worktree", "external"]
"""Which isolation target owns a workspace (spec 2026-09-23 §3.C, gh#569)."""


class IsolationError(Exception):
    """User-facing isolation failure; CLI maps it to exit 2."""


class SessionBinding(BaseModel):
    """One agent session attached to a workspace (spec 2026-09-04 §5.A)."""

    session_id: str
    harness: str = "unknown"  # claude | hermes | opencode | unknown
    attached_at: str  # ISO-8601 UTC

    model_config = {"frozen": True}


class IsolationState(BaseModel):
    """Everything needed to re-address an isolation workspace later."""

    repo_root: Path
    branch: str
    worktree: Path
    profile: str
    # The mode that created this workspace, written by each target's `up`
    # (spec 2026-09-23 §3.C). An older fr on PATH may drop it when it rewrites
    # the file (sessions.attach -> save_state), so `recorded_mode`'s legacy
    # inference from `profile` is permanent, not a transitional fallback.
    target: IsolationMode | None = None
    created_at: str
    # Sessions bound to this workspace (spec 2026-09-04 §5.A). Default keeps
    # pre-feature state files loadable; frozen models still `model_copy(update=)`.
    sessions: list[SessionBinding] = Field(default_factory=list)

    model_config = {"frozen": True}


def recorded_mode(state: IsolationState) -> IsolationMode:
    """The mode a workspace was created in, read from its state alone.

    Pure: never consults the environment. ``state.target`` wins when recorded;
    otherwise infer from the legacy profile sentinels (``host`` -> worktree,
    ``external`` -> external, anything else -> devcontainer).
    """
    if state.target is not None:
        return state.target
    if state.profile == "host":
        return "worktree"
    if state.profile == "external":
        return "external"
    return "devcontainer"


def _sanitize(branch: str) -> str:
    return branch.replace("/", "__")


def _git_common_dir(repo_root: Path) -> Path:
    """Shared .git dir, resolved for main checkouts AND linked worktrees.

    In a linked worktree <repo>/.git is a gitfile (a `gitdir:` pointer), not a
    dir; `--git-common-dir` returns the real shared dir (<main>/.git) that all
    worktrees of the repo share — the correct key for isolation state (state is
    repo+branch, not per-worktree). For a main checkout it returns ".git", so
    this is byte-identical to the legacy literal there. #292

    Resolves its own input so the result is caller-independent: an unresolved
    vs resolved (or symlinked, e.g. macOS /tmp -> /private/tmp) repo_root key
    to the SAME state dir, instead of two string-distinct paths to one inode.
    """
    repo_root = Path(repo_root).resolve()
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--git-common-dir"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Not a git repo (e.g. a bare tmp path in a unit test) — degrade to the
        # legacy literal; there is no worktree to be blind to here.
        return repo_root / ".git"
    p = Path(out)
    return p if p.is_absolute() else (repo_root / p)


def repo_cache_name(repo_root: Path) -> str:
    """Folder under ~/.cache/fr/worktrees for this repo: the MAIN checkout's
    basename, resolved through the git common dir, so `up` from inside a
    linked worktree (native agent worktree, nested fr worktree) files under the
    repo — never under `agent-…` or a branch slug (spec 2026-09-04 §5.C).

    Bare / `--separate-git-dir` layouts (common dir not named ".git") and
    non-git paths fall back to the basename of `repo_root` itself."""
    common = _git_common_dir(repo_root)
    return common.parent.name if common.name == ".git" else Path(repo_root).name


def state_dir(repo_root: Path) -> Path:
    return _git_common_dir(repo_root) / "fr" / "isolation"


def state_path(repo_root: Path, branch: str) -> Path:
    return state_dir(repo_root) / f"{_sanitize(branch)}.json"


def save_state(state: IsolationState) -> Path:
    p = state_path(state.repo_root, state.branch)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(state.model_dump_json(indent=2) + "\n")
    return p


def delete_state(repo_root: Path, branch: str) -> None:
    (state_dir(repo_root) / f"{_sanitize(branch)}.json").unlink(missing_ok=True)


def load_state(repo_root: Path, branch: str) -> IsolationState | None:
    p = state_path(repo_root, branch)
    if not p.is_file():
        return None
    return IsolationState.model_validate_json(p.read_text())


def list_states(repo_root: Path) -> list[IsolationState]:
    """Every readable state record for the repo.

    A record this fr cannot validate (e.g. a newer fr's unknown `target` mode)
    is skipped and named on stderr rather than raised: one foreign file must not
    blind `status`/`gc` to every other workspace. `load_state` stays strict, so
    the workspace that file describes still fails closed when addressed.
    """
    d = state_dir(repo_root)
    if not d.is_dir():
        return []
    states: list[IsolationState] = []
    for f in sorted(d.glob("*.json")):
        try:
            states.append(IsolationState.model_validate_json(f.read_text()))
        except ValidationError as err:
            print(
                f"warning: skipping unreadable isolation state {f} "
                f"({err.error_count()} validation error(s)) — written by a newer fr?",
                file=sys.stderr,
            )
    return states


def sentinel_dir() -> Path:
    """Directory holding pipeline session sentinels.

    Shared contract with the two bash hooks: fr-pipeline-sentinel.sh writes one
    `<session_id>.json` here per active fr-goal / fr-brainstorming / fr-execute
    session ({"repo_root": ...}); fr-isolation-guard.sh reads it to gate
    base-repo commands. `$FR_SENTINEL_DIR` overrides the default (both hooks
    honour the same env var).

    A sentinel may carry an optional `workspaces` list (see
    `stamp_sentinel_workspace`): the workspaces the session bound in this repo,
    each relative to `~/.cache/fr`.
    """
    return Path(os.environ.get("FR_SENTINEL_DIR", str(_home() / ".cache" / "fr" / "sentinels")))


_LOCK_STALE_SECONDS = 60.0
_LOCK_WAIT_SECONDS = 60.0


@contextmanager
def _sentinel_lock(sentinel: Path) -> Iterator[bool]:
    """The lock every sentinel writer shares; yields whether it is HELD.

    Same protocol and path as `fr_sentinel_lock` in
    hooks/lib/fr-isolation-decision.sh (the skill-load hook and the guard's
    heal) — the two MUST agree, and that file's comment is the full rationale.
    In short: `<sentinel>.lock/` holding an `owner` PID; broken only when the
    holder is dead (or ownerless and older than 60s), NEVER while it lives —
    the first version broke any lock after ~5s and so let a bind and the
    guard's heal interleave into deleting a live pipeline's sentinel. A caller
    that is not handed the lock must take its own fail-closed action rather than
    write. Release is owner-checked.
    """
    lock = sentinel.with_name(sentinel.name + ".lock")
    held = _acquire(lock)
    try:
        yield held
    finally:
        if held and _owner(lock) == os.getpid():
            try:
                (lock / "owner").unlink(missing_ok=True)
                os.rmdir(lock)
            except OSError:
                pass


def _owner(lock: Path) -> int | None:
    try:
        text = (lock / "owner").read_text().strip()
    except OSError:
        return None
    return int(text) if text.isdigit() else None


def _abandoned(lock: Path) -> bool:
    pid = _owner(lock)
    if pid is None:
        try:
            return time.time() - lock.stat().st_mtime > _LOCK_STALE_SECONDS
        except OSError:
            return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    except OSError:
        return False  # exists but not ours to signal: alive
    return False


def _acquire(lock: Path) -> bool:
    """Take `lock`, or return False: when a LIVE holder keeps it past the wait
    budget, or when `mkdir` fails for any reason but "exists" (read-only or
    full disk, no sentinel dir) — which used to raise out of `attach`."""
    deadline = time.monotonic() + _LOCK_WAIT_SECONDS
    while True:
        try:
            os.mkdir(lock)
        except FileExistsError:
            pass
        except OSError:
            return False
        else:
            try:
                (lock / "owner").write_text(f"{os.getpid()}\n")
            except OSError:
                pass
            return True
        if _abandoned(lock):
            try:
                (lock / "owner").unlink(missing_ok=True)
                os.rmdir(lock)
            except OSError:
                pass
            continue
        if time.monotonic() > deadline:
            return False
        time.sleep(0.05)


def stamp_sentinel_workspace(session_id: str, worktree: Path) -> None:
    """Record a bound workspace in this session's sentinel, if one exists.

    A sentinel is in one of three states, decided from its `workspaces` list:
    *fresh* (absent or empty — armed, never healed), *live* (at least one entry
    names a surviving linked worktree of the repo) or *orphaned* (entries exist
    and NONE survives — the guard retires it). It is a SET because a session may
    bind more than one workspace of its repo (`fr isolation exec --branch
    <other>` rebinds): a single, replaced stamp let the other workspace's
    teardown disarm this session's live pipeline (adversarial review C1).
    Entries are RELATIVE to `~/.cache/fr`, so they carry no home path (the
    sentinel's `repo_root`, written by the hook, always has). This call adds
    `worktree` if absent and prunes entries whose directory is gone — a dead
    entry never changes the verdict, so dropping it only keeps the file small.

    Not stamped (the sentinel keeps what it had): a worktree outside the cache
    dir; a missing or malformed sentinel; and a worktree of ANOTHER repo. A
    session holding a pipeline in repo A may enter repo B's isolation (`cd <B>
    && fr isolation up`, #421); B's worktree in A's sentinel could never be
    listed by A, and would read as orphaned once A's own entries went. Unknown
    ownership (unreadable repo) is treated as foreign. The write is atomic.
    """
    if not session_id or "/" in session_id or session_id in (".", ".."):
        return
    f = sentinel_dir() / f"{session_id}.json"
    if not f.is_file():
        return
    rel = _cache_relative(worktree)
    if rel is None:
        return
    with _sentinel_lock(f) as held:
        if not held:
            return  # a live writer holds it: skip the record rather than race it
        try:
            data = json.loads(f.read_text())
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(data, dict) or not isinstance(data.get("repo_root"), str):
            return
        if _git_common_dir(Path(data["repo_root"])).resolve() != (
            _git_common_dir(Path(worktree)).resolve()
        ):
            return
        kept = [w for w in _workspaces(data) if w == rel or _cache_dir(w).is_dir()]
        data["workspaces"] = kept if rel in kept else [*kept, rel]
        try:
            write_text_atomic(f, json.dumps(data))
        except OSError:
            pass  # unwritable sentinel dir: stays as it was (armed)


def _workspaces(data: dict[str, Any]) -> list[str]:
    raw = data.get("workspaces")
    return [w for w in raw if isinstance(w, str) and w] if isinstance(raw, list) else []


def _cache_root() -> Path:
    return _home() / ".cache" / "fr"


def _cache_dir(rel: str) -> Path:
    return _cache_root() / rel


def _cache_relative(worktree: Path) -> str | None:
    """`worktree` relative to `~/.cache/fr` (posix), or None when outside it.

    The UNRESOLVED path is tried first: fr stores worktrees as
    `~/.cache/fr/worktrees/...` literally, and when `worktrees` is itself a
    symlink to another volume the resolved path is no longer under the cache
    (review L1). The resolved form covers a symlinked HOME the other way round.
    """
    for wt, root in (
        (Path(worktree), _cache_root()),
        (Path(worktree).resolve(), _cache_root().resolve()),
    ):
        try:
            rel = wt.relative_to(root)
        except ValueError:
            continue
        if ".." not in rel.parts and rel.parts:
            return rel.as_posix()
    return None


def clear_workspace_sentinels(
    repo_root: Path, worktree: Path, session_ids: Iterable[str] = ()
) -> int:
    """Retire the sentinels whose pipeline lived in `worktree`; return the count.

    Called by `fr isolation down` after a SUCCESSFUL teardown (the bash guard,
    which runs before the command, no longer retires anything on `down` —
    review H2). A sentinel naming `repo_root` is affected when `worktree` is in
    its `workspaces` or its session was bound to it (`session_ids`, which covers
    a sentinel that was never stamped). An affected sentinel loses that entry,
    and is removed only if NO other workspace of its survives — a session that
    also holds a live workspace still has a live pipeline (review C1).

    Everything else is left alone, in particular another session's FRESH
    sentinel: the old "zero workspaces remain → clear the repo" rule removed
    exactly that, silently disarming a pipeline whose workspace did not exist
    yet (#472, third mechanism). Malformed files are skipped.
    """
    d = sentinel_dir()
    if not d.is_dir():
        return 0
    target = str(Path(repo_root).resolve())
    rel = _cache_relative(worktree)
    ids = set(session_ids)
    removed = 0
    for f in sorted(d.glob("*.json")):
        with _sentinel_lock(f) as held:
            if held:  # a live writer holds it: leave it armed
                removed += _clear_one(f, target, rel, ids)
    return removed


def _clear_one(f: Path, target: str, rel: str | None, ids: set[str]) -> int:
    try:
        data = json.loads(f.read_text())
    except (OSError, json.JSONDecodeError):
        return 0
    if not isinstance(data, dict):
        return 0
    root = data.get("repo_root")
    if not isinstance(root, str) or str(Path(root).resolve()) != target:
        return 0
    entries = _workspaces(data)
    if not ((rel is not None and rel in entries) or f.stem in ids):
        return 0
    survivors = [w for w in entries if w != rel and _cache_dir(w).is_dir()]
    if survivors:
        data["workspaces"] = survivors
        write_text_atomic(f, json.dumps(data))
        return 0
    f.unlink(missing_ok=True)
    return 1


def clear_repo_sentinels(repo_root: Path) -> int:
    """Remove pipeline sentinels pointing at `repo_root`; return the count.

    The explicit "drop session state" lever behind `fr isolation down --all`
    (#341 Task 2A). Foreign-repo sentinels are left alone; a malformed /
    unreadable file is skipped, never removed (it isn't ours to interpret). The
    guard's own self-heal (fail open + clear when THIS session's stamped
    workspace is gone — see `stamp_sentinel_workspace`) is the lazy, per-session
    backstop; this is the eager, repo-wide path, and the difference is the
    blast radius: `--all` retires every session's sentinel for the repo.
    """
    d = sentinel_dir()
    if not d.is_dir():
        return 0
    target = str(Path(repo_root).resolve())
    removed = 0
    for f in sorted(d.glob("*.json")):
        try:
            data = json.loads(f.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        root = data.get("repo_root") if isinstance(data, dict) else None
        if root and str(Path(root).resolve()) == target:
            with _sentinel_lock(f) as held:
                if not held:
                    continue
                f.unlink(missing_ok=True)
            removed += 1
    return removed


def discover_profiles(repo_root: Path) -> list[str]:
    base = repo_root / ".devcontainer"
    return sorted(p.parent.name for p in base.glob("*/devcontainer.json"))


def profiles_config(repo_root: Path) -> dict[str, Any]:
    cfg = repo_root / ".devcontainer" / "fr-profiles.yaml"
    if cfg.is_file():
        return yaml.safe_load(cfg.read_text()) or {}
    return {}


def secrets_env_file(repo_name: str, profile: str) -> Path:
    """Canonical (fr) host-side secrets env-file for a repo/profile."""
    return _home() / ".config" / "fr" / "secrets" / repo_name / f"{profile}.env"


def harden_secret_file(env_file: Path) -> None:
    """Make a host secrets env-file private: 0600 on the file, 0700 on its dir
    chain up to (and including) the ``~/.config/<store>`` secrets root.

    Called after every scaffold / ensure so the store is never world-readable —
    a 0644 store under 0755 dirs once exposed a live cluster-admin kube token —
    and so pre-existing loose perms self-heal on the next isolation run. Errors
    (e.g. a not-yet-created file) are swallowed: hardening is best-effort.
    """
    if env_file.is_file():
        env_file.chmod(0o600)
    d = env_file.parent
    for _ in range(4):  # <repo>/, secrets/, <store>/ — bounded; never past .config
        try:
            d.chmod(0o700)
        except OSError:
            pass
        if d.parent.name == ".config" or d.parent == d:
            break
        d = d.parent


def resolve_profile(repo_root: Path, name: str | None) -> str:
    """Resolve the requested (or default) profile, or explain how to get one.

    Hard requirement by design: no devcontainer profile → refuse with a
    pointer at fr-init. There is no unisolated fallback.
    """
    available = discover_profiles(repo_root)
    if not available:
        raise IsolationError(
            "no devcontainer profiles found (.devcontainer/<profile>/devcontainer.json). "
            "Run the fr-init skill to scaffold one — isolation never degrades to unisolated."
        )
    if name is None:
        default = profiles_config(repo_root).get("default")
        if default and default in available:
            return str(default)
        if len(available) == 1:
            return available[0]
        raise IsolationError(
            f"multiple profiles ({', '.join(available)}) and no default in "
            ".devcontainer/fr-profiles.yaml — pass --profile or set a default via fr-init."
        )
    if name not in available:
        raise IsolationError(f"unknown profile {name!r}; available: {', '.join(available)}")
    return name


class Target(Protocol):
    """Pluggable isolation backend (local worktree+devcontainer now; remote later)."""

    def up(
        self,
        profile: str | None,
        branch: str,
        path: Path | None = None,
        base: str | None = None,
        no_fetch: bool = False,
    ) -> IsolationState: ...

    def exec(self, state: IsolationState, argv: list[str]) -> int: ...

    def restart(self, state: IsolationState, force: bool = False) -> str: ...

    def stats(self, state: IsolationState) -> dict[str, str] | None: ...

    def status(self, state: IsolationState) -> dict[str, Any]: ...

    def down(self, state: IsolationState, force: bool = False) -> None: ...
