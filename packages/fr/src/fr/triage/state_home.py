"""Where a scope's working state lives: `~/.cache/fr/triage/<scope>/`, a git repository of
its own (spec 2026-11-19-event-driven-a-la-carte R17, R18, §G).

**The cache repository (R17).** `fr.triage.model.state_dir` returns the cache directory, and
its first use runs `git init` there with an `info/exclude` that ignores everything: the
repository holds the state ref's objects (`fr.triage.state_ref`), so a scope syncs with its
state repo from any working directory, a product clone or none.

**The move (R18).** An fr below S1 kept the state in `<clone>/.fr/triage-state/<scope>/`.
The first S1 use from that clone moves it, under the scope's move lock (one mover per
scope on the host; a second waits, then finds nothing left to move):

1. a `drive.lock` in the cache naming a live process refuses ("stop the driver first").
   Every fr writes that lock there, so an fr below S1 that is driving is seen too; the
   mover then holds the lock itself, so no driver starts while it moves;
2. a cache that already holds state an fr below S1 wrote (no `.git`: a host that triaged
   before cloud triage) is renamed `<scope>.pre-s1`, and the clone's copy moves in;
3. `merge/` is not moved: its worktrees are registered in the product clone, so each is
   removed (`git worktree remove --force`) and pruned; the queue recreates them;
4. the clone's `info/exclude` line `STATE_EXCLUDE` is removed once no scope's copy is left;
5. a clone copy met when the cache is already an S1 state (another clone, or a copy an
   older fr re-created) is compared with it on the durable files (`REF_FILES`): identical,
   it is removed; different, fr refuses and names both directories.

**Never the only copy.** The clone's copy is copied to a staging directory beside the cache,
verified file by file, made a repository, renamed into place and verified again; only then
is the clone's copy renamed aside and deleted. A crash at any point leaves the clone's copy
whole, or the installed cache whole, and the next command converges: an installed cache
meets the clone's copy as rule 5, identical, and removes it.

**Mixed fr versions on one host** are not supported. An fr below S1 that runs after the move
finds no clone copy and imports the cache's durable files into a new one; the next S1 command
refuses (rule 1 while its driver runs, rule 5 after), so the divergence is loud, never
silent. Restart a running driver with the new fr after upgrading.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import time
import uuid
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Final

from fr.config.space import PRODUCT_TRIAGE_STATE
from fr.triage import gitseam
from fr.triage.drive_lock import DRIVE_LOCK, lock_holder, lock_text
from fr.triage.errors import TriageError

PRE_S1: Final = ".pre-s1"
"""The suffix an older cache copy is set aside under (rule 2)."""
MOVE_WAIT_SECONDS: Final = 60.0
"""How long a mover waits for another one of the same scope before it refuses."""
_STAGE, _ASIDE, _GONE = ".s1-stage-", ".s1-aside-", ".s1-moved-"
"""Infixes of the hidden directories a move makes beside the cache and the clone's copy."""

PROTECTED_SOURCES: list[Path] = []
"""Clones whose copy is never moved: a test seam (`tests/conftest.py` names the checkout
under test and its main checkout), so a suite run from a real clone never moves that clone's
state into a sandbox home. Empty in production."""


def _say(line: str) -> None:
    print(line, file=sys.stderr, flush=True)


def ensure_repo(cache: Path) -> None:
    """The cache directory as a git repository (R17); nothing when it already is one."""
    gitseam.init_state_repo(cache)


def clone_copy(root: Path, name: str) -> Path:
    """`<root>/.fr/triage-state/<name>`: where an fr below S1 kept a scope's state."""
    return root / PRODUCT_TRIAGE_STATE / name


def settle(name: str, root: Path, cache: Path, *, say: Callable[[str], None] = _say) -> None:
    """Move the clone at *root*'s copy of scope *name* into *cache* (R18's five rules; see
    the module docstring). Nothing when the clone holds none. Raises `TriageError` on a
    refusal, with both copies as they were."""
    copy = clone_copy(root, name)
    if not copy.parent.is_dir():
        return
    if not copy.is_dir() or copy.is_symlink():
        _tidy(root, copy.parent)
        return
    if any(_same(root, p) for p in PROTECTED_SOURCES):
        raise TriageError(f"{copy} is in a protected clone: its triage state is never moved")
    with _move_lock(cache):
        if copy.is_dir() and not copy.is_symlink():
            _move(name, root, copy, cache, say)
        _tidy(root, copy.parent)


def _same(a: Path, b: Path) -> bool:
    try:
        return Path(a).resolve() == Path(b).resolve()
    except OSError:
        return False


def _move(name: str, root: Path, copy: Path, cache: Path, say: Callable[[str], None]) -> None:
    _clear_leftovers(cache.parent, cache.name)
    release = _hold_driver_lock(cache)
    try:
        if _kind(cache) == "s1":
            _compare(copy, cache)  # rule 5: identical, or a refusal naming both
            _retire(root, copy)
            say(f"fr triage: removed {copy}: it holds the same durable state as {cache}")
            return
        aside = _install(copy, cache)
        _retire(root, copy)
        kept = f"; the cache's older copy is kept at {aside}" if aside is not None else ""
        say(
            f"fr triage: moved the triage state of {name} from {copy} to {cache} "
            f"(.fr/ holds configuration only){kept}. An fr below S1 still reads {copy}: "
            "restart any running `fr triage batch drive` with this fr, and run no older fr "
            "on this host."
        )
    finally:
        release()


# --- the lock ------------------------------------------------------------------------


def _lock_root() -> Path:
    from fr.isolation.types import _home

    return Path(os.environ.get("FR_TRIAGE_LOCK_DIR") or _home() / ".cache" / "fr" / "triage-locks")


@contextmanager
def _move_lock(cache: Path) -> Iterator[None]:
    """The scope's move lock (an OS file lock beside the replacement locks): one mover per
    scope on this host. A second waits up to `MOVE_WAIT_SECONDS`, then refuses."""
    from fr.file_lock import FileLockError, exclusive_file_lock

    path = _lock_root() / f"move-{cache.name}.lock"
    deadline = time.monotonic() + MOVE_WAIT_SECONDS
    while True:
        try:
            with exclusive_file_lock(path):
                yield
                return
        except FileLockError as exc:
            if str(exc) != "locked":
                raise TriageError(f"cannot take {path}: {exc}") from exc
            if time.monotonic() > deadline:
                raise TriageError(
                    f"another fr has been moving this scope's triage state for "
                    f"{MOVE_WAIT_SECONDS:g}s ({path}); run the command again"
                ) from exc
            time.sleep(0.1)


def _hold_driver_lock(cache: Path) -> Callable[[], None]:
    """Rule 1, and the mover's hold: take `<cache>/drive.lock` for this process, or refuse
    while a live process holds it. A stale lock is replaced. The returned release removes
    this process's lock wherever the move left it (the cache, or the set-aside copy)."""
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / DRIVE_LOCK
    mine = json.dumps({"pid": os.getpid(), "started": "moving triage state (S1 R18)"})
    for _ in range(5):
        private = cache / f".{DRIVE_LOCK}.{os.getpid()}.{uuid.uuid4().hex}"
        private.write_text(mine, encoding="utf-8")
        try:
            os.link(private, path)
            break
        except FileExistsError:
            pass
        finally:
            private.unlink(missing_ok=True)
        held = lock_text(path)
        if held is None:
            continue
        holder = lock_holder(path, held)
        if holder is not None:
            raise TriageError(
                f"{path} names a live driver ({holder}): stop the driver first, then run the "
                "command again; the triage state moves out of the clone only while no driver "
                "runs (S1 R18)"
            )
        stale = cache / f".{DRIVE_LOCK}.stale.{uuid.uuid4().hex}"
        try:
            os.replace(path, stale)
        except FileNotFoundError:
            continue
        stale.unlink(missing_ok=True)
    else:
        raise TriageError(f"cannot take {path}: another process keeps re-creating it")

    def release() -> None:
        for where in (cache, *cache.parent.glob(f"{cache.name}{PRE_S1}*")):
            lock = where / DRIVE_LOCK
            if lock_text(lock) == mine:
                lock.unlink(missing_ok=True)

    return release


# --- what the cache holds --------------------------------------------------------------


def _lockish(name: str) -> bool:
    return name == DRIVE_LOCK or name.startswith(f".{DRIVE_LOCK}")


def _kind(cache: Path) -> str:
    """`empty` (absent, or only a lock and a repository), `s1` (state an S1 fr keeps: a
    repository holding files) or `older` (files and no repository: an fr below S1's)."""
    if not cache.is_dir():
        return "empty"
    names = [p.name for p in cache.iterdir() if p.name != ".git" and not _lockish(p.name)]
    if not names:
        return "empty"
    return "s1" if (cache / ".git").is_dir() else "older"


Inventory = dict[str, tuple[str, str]]


def _inventory(path: Path, *, top_skip: Iterable[str] = ()) -> Inventory:
    """Every file below *path* as `rel -> (kind, digest)`: a regular file by its sha256, a
    symlink by its target (never followed). A top-level name in *top_skip*, a lock and the
    repository are left out."""
    skip = set(top_skip) | {".git"}
    out: Inventory = {}
    for dirpath, dirnames, filenames in os.walk(path, followlinks=False):
        here = Path(dirpath)
        rel_dir = here.relative_to(path)
        if rel_dir == Path("."):
            dirnames[:] = [d for d in dirnames if d not in skip and not _lockish(d)]
            filenames = [f for f in filenames if f not in skip and not _lockish(f)]
        links = [d for d in dirnames if (here / d).is_symlink()]
        for name in [*filenames, *links]:
            full = here / name
            rel = (rel_dir / name).as_posix()
            if full.is_symlink():
                out[rel] = ("link", os.readlink(full))
            else:
                out[rel] = ("file", hashlib.sha256(full.read_bytes()).hexdigest())
        dirnames[:] = [d for d in dirnames if d not in links]
    return out


def _durable(path: Path) -> dict[str, str]:
    from fr.triage.state_ref import ref_entries

    return {rel: hashlib.sha256((path / rel).read_bytes()).hexdigest() for rel in ref_entries(path)}


def _compare(copy: Path, cache: Path) -> None:
    mine, theirs = _durable(copy), _durable(cache)
    if mine == theirs:
        return
    differ = sorted(k for k in mine.keys() | theirs.keys() if mine.get(k) != theirs.get(k))
    shown = ", ".join(differ[:5]) + (f" and {len(differ) - 5} more" if len(differ) > 5 else "")
    raise TriageError(
        f"{copy} and {cache} both hold this scope's triage state and differ in {shown}: an fr "
        "below S1 may still be writing the clone's copy. Stop it, keep the copy you want (move "
        "the other one aside) and run the command again (S1 R18)"
    )


# --- the steps ---------------------------------------------------------------------------


def _clear_leftovers(parent: Path, name: str) -> None:
    """A crashed move's staging and set-aside directories (never the only copy: the clone's
    copy is still whole whenever one is left)."""
    for leftover in (*parent.glob(f".{name}{_STAGE}*"), *parent.glob(f".{name}{_ASIDE}*")):
        shutil.rmtree(leftover, ignore_errors=True)


def _install(copy: Path, cache: Path) -> Path | None:
    """Copy *copy* (but `merge/`) to a staging directory, verify it, make it a repository and
    rename it into *cache*: an empty cache is set aside and deleted, an older copy is kept as
    `<scope>.pre-s1` (rule 2). Verified again in place. The set-aside older copy, or None."""
    parent = cache.parent
    stage = parent / f".{cache.name}{_STAGE}{uuid.uuid4().hex}"
    want = _inventory(copy, top_skip=("merge",))
    try:
        shutil.copytree(
            copy,
            stage,
            symlinks=True,
            ignore=lambda d, names: ["merge"] if Path(d) == copy else [],
        )
        if _inventory(stage) != want:
            raise TriageError(f"the copy of {copy} in {stage} did not verify; nothing was moved")
        gitseam.init_state_repo(stage)
        held = cache / DRIVE_LOCK
        if lock_text(held) is not None:
            shutil.copy2(held, stage / DRIVE_LOCK)  # the mover's hold moves in with it
        older = _kind(cache) == "older"
        aside = _free(parent, f"{cache.name}{PRE_S1}") if older else None
        trash = parent / f".{cache.name}{_ASIDE}{uuid.uuid4().hex}"
        if cache.exists():
            os.rename(cache, aside or trash)
        try:
            os.rename(stage, cache)
        except OSError as exc:
            if aside is not None and not cache.exists():
                os.rename(aside, cache)
            raise TriageError(
                f"{cache} was re-created while the triage state moved into it ({exc}); "
                f"{copy} is unchanged: run the command again"
            ) from exc
        shutil.rmtree(trash, ignore_errors=True)
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    if _inventory(cache) != want:
        raise TriageError(f"{cache} did not verify against {copy} after the move; {copy} is kept")
    return aside


def _free(parent: Path, base: str) -> Path:
    """`<parent>/<base>`, or `<base>-2`, `-3`... when an earlier move already used it."""
    n, candidate = 1, parent / base
    while candidate.exists() or candidate.is_symlink():
        n += 1
        candidate = parent / f"{base}-{n}"
    return candidate


def _retire(root: Path, copy: Path) -> None:
    """Rule 3, then the clone's copy goes: each `merge/` worktree removed and pruned, the copy
    renamed aside (one atomic step, so a crash never leaves half of it) and deleted."""
    merge = copy / "merge"
    if merge.is_dir() and not merge.is_symlink():
        for scratch in sorted(merge.iterdir()):
            if scratch.is_dir() and not scratch.is_symlink():
                gitseam.remove_worktree(scratch)
    gone = copy.parent / f".{copy.name}{_GONE}{uuid.uuid4().hex}"
    os.rename(copy, gone)
    shutil.rmtree(gone, ignore_errors=True)
    gitseam.prune_worktrees(root)


def _tidy(root: Path, parent: Path) -> None:
    """Rule 4: a retired copy left by a crash is deleted, and once no scope's copy is left
    the exclude line goes, then the empty directory."""
    for gone in parent.glob(f".*{_GONE}*"):
        shutil.rmtree(gone, ignore_errors=True)
    try:
        left = list(parent.iterdir())
    except FileNotFoundError:
        return
    if left:
        return
    gitseam.remove_excluded(root, _state_exclude())
    try:
        parent.rmdir()
    except OSError:
        pass


def _state_exclude() -> str:
    from fr.triage.model import STATE_EXCLUDE

    return STATE_EXCLUDE


# --- R19: the stealth workspace's tracking repo -----------------------------------------


def stealth_tracking(start: Path) -> tuple[bool, str | None]:
    """Whether the clone holding *start* is a stealth workspace, and its tracking repo as
    `OWNER/REPO` (spec 2026-11-19 R19): None for a tracking repo that is no forge repo (a
    local path), which cannot hold a state ref. `(False, None)` outside a stealth workspace.
    A stealth marker without its tracking ref is refused (`TriageError`): under stealth the
    one-repo rule would push the state to the product repo, which stealth keeps clean."""
    from fr._hosts import slug_from_url
    from fr.placement.stealth import is_local, marker_tracking
    from fr.settings import SettingsError

    root = gitseam.toplevel(start) if start.is_dir() else None
    if root is None:
        return False, None
    try:
        found = marker_tracking(root)
    except SettingsError as exc:
        raise TriageError(str(exc)) from exc
    if found is None:
        return False, None
    ref, _ = found
    if is_local(ref.repo):
        return True, None
    slug = slug_from_url(ref.repo)
    return True, (slug if slug and slug.count("/") == 1 else None)
