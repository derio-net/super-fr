"""Where a scope's working state lives: `~/.cache/fr/triage/<scope>/`, a git repository of
its own (spec 2026-11-19-event-driven-a-la-carte R17, R18, §G).

**The cache repository (R17).** `fr.triage.model.state_dir` returns the cache directory, and
its first use runs `git init` there with an `info/exclude` that ignores everything: the
repository holds the state ref's objects (`fr.triage.state_ref`), so a scope syncs with its
state repo from any working directory, a product clone or none. A cache that holds state an
fr below S1 wrote (files and no `.git`) is never made a repository in place: only the move
below turns it into one, and from anywhere else fr refuses (`refuse_older`, decision
p6-older-cache-from-outside).

**The move (R18).** An fr below S1 kept the state in `<clone>/.fr/triage-state/<scope>/`.
The first S1 use from that clone moves it, under the scope's move lock (one mover per
scope on the host, exclusive; every S1 command that prepares the state directory holds it
shared, so no S1 writer writes while a move runs, review p6-r7):

1. a `drive.lock` in the cache naming a live process refuses ("stop the driver first").
   Every fr writes that lock there, so an fr below S1 that is driving is seen too; the
   mover then holds the lock itself, so no driver starts while it moves;
2. a cache that already holds state an fr below S1 wrote (no `.git`: a host that triaged
   before cloud triage) is renamed `<scope>.pre-s1`, and the clone's copy moves in;
3. the worktrees registered under the copy (`merge/`, `closeout/`, `queue/`, `export/`,
   `probe/`, at any depth) are not moved: one with local changes or commits no remote
   holds refuses the move, naming it; a clean one is removed with a plain `git worktree
   remove` (never forced, review p6-r4) and pruned; the queue recreates them;
4. the clone's `info/exclude` line `STATE_EXCLUDE` is removed once no scope's copy is
   left in this checkout and no other worktree of the clone holds a `.fr/triage-state/`
   (review p6-r3);
5. a clone copy met when the cache is already an S1 state (another clone, or a copy an
   older fr re-created) is compared with it on every file but the worktree scratch, the
   locks, `facts.json` and the pages (review p6-r1): the durable files (`REF_FILES`) must
   be identical, present or absent alike, and every other file the two both hold too;
   a file only the copy holds is carried into the cache; then the copy is retired. Any
   difference refuses, naming the files and both directories.

**Never the only copy.** The clone's copy is copied to a staging directory beside the cache,
verified file by file, made a repository, renamed into place (after re-checking that the
cache did not change meanwhile) and verified again; only then is the clone's copy renamed
aside and deleted. A crash at any point leaves the clone's copy whole, or the installed
cache whole, and the next command converges: an installed cache meets the clone's copy as
rule 5, identical, and removes it.

**The tombstone (decision p6-rc6-tombstone).** A retired copy leaves a regular file at its
path, `<clone>/.fr/triage-state/<scope>`, naming the cache. An fr below S1 resolves its
state directory there, finds it exists (so it imports nothing) and fails on its first read
(`cannot read judgements: Not a directory`), loudly, instead of re-creating a copy from the
cache's durable files. S1 recognises the tombstone and passes it by. A crash between the
copy's retirement and the tombstone's write leaves neither, and an older fr may then
re-create a copy: the next S1 command meets it as rule 5, carrying the files the cache lacks
and refusing on any divergence, so nothing is lost silently.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import sys
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import IO, Final

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
SCRATCH_DIRS: Final = ("merge", "closeout", "queue", "export", "probe")
"""The state directory's worktree scratch (rule 3): never moved, never compared."""
TOMBSTONE: Final = "fr-triage-state-moved"
"""The first line of the file a retired clone copy leaves at its path."""

PROTECTED_SOURCES: list[Path] = []
"""Clones whose copy is never moved: a test seam (`tests/conftest.py` names the checkout
under test and its main checkout), so a suite run from a real clone never moves that clone's
state into a sandbox home. Empty in production."""
PROTECTED_SOURCES_ENV: Final = "FR_TRIAGE_PROTECTED_SOURCES"
"""The same seam for a child process (lens review l-tests-r3): clones joined by
`os.pathsep`, read at every move, so an `fr` a test starts inherits the suite's protection.
Unset in production."""


def protected_sources() -> list[Path]:
    """The clones whose copy is never moved: `PROTECTED_SOURCES` and every absolute path
    `FR_TRIAGE_PROTECTED_SOURCES` names."""
    named = os.environ.get(PROTECTED_SOURCES_ENV, "").split(os.pathsep)
    return [*PROTECTED_SOURCES, *(Path(p) for p in named if os.path.isabs(p))]


def _say(line: str) -> None:
    print(line, file=sys.stderr, flush=True)


def ensure_repo(cache: Path) -> None:
    """The cache directory as a git repository (R17); nothing when it already is one.
    Refuses (`refuse_older`) a cache an fr below S1 wrote: only the move makes it one."""
    refuse_older(cache)
    gitseam.init_state_repo(cache)


def refuse_older(cache: Path, root: Path | None = None) -> None:
    """Refuse (`TriageError`) while *cache* holds state an fr below S1 wrote (files and no
    repository): making it a repository in place would adopt a copy that may be older than
    a clone's (review p6-r2). Only the R18 move, run from the clone whose
    `.fr/triage-state/` holds the live state, sets it aside (`.pre-s1`) and installs the
    clone's copy. *root* is the clone of the working directory, if any (it holds no copy)."""
    if _kind(cache) != "older":
        return
    name = cache.name
    here = (
        f"{root} holds no copy of it ({clone_copy(root, name)} is absent)"
        if root is not None
        else "the working directory is in no clone"
    )
    raise TriageError(
        f"{cache} holds triage state an fr below S1 wrote, and {here}: fr will not make it "
        f"the S1 state in place, because a clone may hold a newer copy. Run the command from "
        f"the clone whose .fr/triage-state/{name}/ holds the live state (the move keeps this "
        f"copy as {cache.name}{PRE_S1}). If no clone holds one, this cache is the live "
        f"state: stop any driver, then `mkdir -p <clone>/.fr/triage-state && mv {cache} "
        f"<clone>/.fr/triage-state/{name}` and run the command from that clone; or pass "
        f"--dir {cache} to use it as it is, unsynced (S1 R18)"
    )


def clone_copy(root: Path, name: str) -> Path:
    """`<root>/.fr/triage-state/<name>`: where an fr below S1 kept a scope's state."""
    return root / PRODUCT_TRIAGE_STATE / name


def is_tombstone(path: Path) -> bool:
    """Whether *path* is the regular file a retired clone copy leaves (never a link)."""
    if path.is_symlink() or not path.is_file():
        return False
    try:
        with path.open("rb") as fh:
            return fh.readline().rstrip(b"\r\n") == TOMBSTONE.encode()
    except OSError:
        return False


def settle(name: str, root: Path, cache: Path, *, say: Callable[[str], None] = _say) -> None:
    """Move the clone at *root*'s copy of scope *name* into *cache* (R18's five rules; see
    the module docstring). Nothing when the clone holds none, or only the tombstone a move
    left. Raises `TriageError` on a refusal, with both copies as they were.

    Nothing destructive runs through a link: `.fr`, `.fr/triage-state` and the scope's
    directory must each be a real directory inside the clone (`fr.config.space.link_problem`,
    lstat at every step), and a copy that is, holds or sits in the cache, or a cache that
    lies inside the clone, is refused (`_overlap`). Checked before any rename, delete, tidy
    or worktree removal."""
    copy = clone_copy(root, name)
    _refuse_links(root, copy.parent)
    if not copy.parent.is_dir():
        return
    if not (copy.exists() or copy.is_symlink()) or is_tombstone(copy):
        _tidy(root, copy.parent, say)
        return
    _refuse_links(root, copy)
    if not copy.is_dir():
        if is_tombstone(copy):  # another mover finished between the two checks
            _tidy(root, copy.parent, say)
            return
        raise TriageError(f"{copy} is not a directory: fr does not move or delete it")
    if any(_same(root, p) for p in protected_sources()):
        raise TriageError(f"{copy} is in a protected clone: its triage state is never moved")
    why = _overlap(root, copy, cache)
    if why is not None:
        raise TriageError(f"{why}: fr does not move the triage state (S1 R18)")
    with _move_lock(cache):
        if copy.is_dir() and not copy.is_symlink():
            _move(name, root, copy, cache, say)
        _tidy(root, copy.parent, say)


def _refuse_links(root: Path, path: Path) -> None:
    from fr.config.space import link_problem

    why = link_problem(root, path)
    if why is not None:
        raise TriageError(f"{why}: fr does not move or delete triage state through it (S1 R18)")


def _overlap(root: Path, copy: Path, cache: Path) -> str | None:
    """Why the clone copy and the cache may not be moved one into the other, or None: the
    same directory, one inside the other, or a cache inside the clone the copy is retired
    from. Resolved paths are compared."""
    c, k, r = copy.resolve(), cache.resolve(), root.resolve()
    if c == k:
        return f"{copy} is the same directory as the cache {cache}"
    if k.is_relative_to(c) or c.is_relative_to(k):
        return f"{copy} and the cache {cache} lie one inside the other"
    if k.is_relative_to(r):
        return f"the cache {cache} lies inside the clone {root}"
    return None


def _same(a: Path, b: Path) -> bool:
    try:
        return Path(a).resolve() == Path(b).resolve()
    except OSError:
        return False


def _move(name: str, root: Path, copy: Path, cache: Path, say: Callable[[str], None]) -> None:
    _clear_leftovers(cache.parent, cache.name)
    trees = _worktrees_under(root, copy)  # rule 3's refusal, before anything moves
    skip = _Skip.under(copy, trees)
    release = _hold_driver_lock(cache)
    try:
        if _kind(cache) == "s1":
            carried = _reconcile(copy, cache, skip)  # rule 5: identical, or a refusal
            _retire(root, copy, cache, trees)
            also = f"; carried {', '.join(carried)} into it" if carried else ""
            say(f"fr triage: removed {copy}: {cache} holds the same triage state{also}")
            return
        aside = _install(copy, cache, skip)
        _retire(root, copy, cache, trees)
        kept = f"; the cache's older copy is kept at {aside}" if aside is not None else ""
        say(
            f"fr triage: moved the triage state of {name} from {copy} to {cache} "
            f"(.fr/ holds configuration only){kept}. {copy} is now a marker an fr below S1 "
            "fails on: upgrade every fr on this host, and restart any `fr triage batch drive` "
            "with this fr before the next fr command."
        )
    finally:
        release()


# --- the locks -----------------------------------------------------------------------


def _lock_root() -> Path:
    from fr.isolation.types import _home

    return Path(os.environ.get("FR_TRIAGE_LOCK_DIR") or _home() / ".cache" / "fr" / "triage-locks")


def _move_lock_path(cache: Path) -> Path:
    return _lock_root() / f"move-{cache.name}.lock"


_SHARED: dict[str, IO[str]] = {}
"""The move locks this process holds shared, by path, open until `release_shared` or exit."""


def hold_shared(cache: Path) -> None:
    """Hold the scope's move lock shared for the rest of this process (review p6-r7): every
    S1 command that prepares the state directory writes into it afterwards, and a mover
    (exclusive) waits until no such command runs. Waits up to `MOVE_WAIT_SECONDS` for a
    running move, then refuses. Nothing when this process holds it already."""
    path = _move_lock_path(cache)
    if str(path) in _SHARED:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a")
    deadline = time.monotonic() + MOVE_WAIT_SECONDS
    while True:
        try:
            fcntl.flock(handle, fcntl.LOCK_SH | fcntl.LOCK_NB)
            break
        except BlockingIOError:
            if time.monotonic() > deadline:
                handle.close()
                raise TriageError(
                    f"another fr has been moving this scope's triage state for "
                    f"{MOVE_WAIT_SECONDS:g}s ({path}); run the command again"
                ) from None
            time.sleep(0.1)
    _SHARED[str(path)] = handle


def release_shared() -> None:
    """Drop every shared move lock this process holds (a test seam; exit does it too)."""
    while _SHARED:
        _, handle = _SHARED.popitem()
        handle.close()


@contextmanager
def _move_lock(cache: Path) -> Iterator[None]:
    """The scope's move lock (an OS file lock beside the replacement locks), exclusive: one
    mover per scope on this host, and no S1 command holding it shared. A shared hold of this
    process's own is dropped first (the caller takes it again after the move). A second
    mover waits up to `MOVE_WAIT_SECONDS`, then refuses."""
    from fr.file_lock import FileLockError, exclusive_file_lock

    path = _move_lock_path(cache)
    mine = _SHARED.pop(str(path), None)
    if mine is not None:
        mine.close()
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
                    f"another fr has been moving or using this scope's triage state for "
                    f"{MOVE_WAIT_SECONDS:g}s ({path}); stop it, or run the command again "
                    "when it is done"
                ) from exc
            time.sleep(0.1)


def _hold_driver_lock(cache: Path) -> Callable[[], None]:
    """Rule 1, and the mover's hold: take `<cache>/drive.lock` for this process, or refuse
    while a live process holds it. A stale lock is replaced, and a lock another starter
    took over meanwhile is put back (as `drive_lock` does, review p6-r6). The returned
    release removes this process's lock wherever the move left it (the cache, or the
    set-aside copy)."""
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
        if lock_text(stale) != held:  # another starter took it over meanwhile
            try:
                os.link(stale, path)  # put theirs back
            except FileExistsError:
                pass
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
    return name == DRIVE_LOCK or name.startswith(f".{DRIVE_LOCK}") or name.endswith(".lock")


def _kind(cache: Path) -> str:
    """`empty` (absent, or only locks and a repository), `s1` (state an S1 fr keeps: a
    repository holding files) or `older` (files and no repository: an fr below S1's)."""
    if not cache.is_dir():
        return "empty"
    names = [p.name for p in cache.iterdir() if p.name != ".git" and not _lockish(p.name)]
    if not names:
        return "empty"
    return "s1" if (cache / ".git").is_dir() else "older"


class _Skip:
    """What a move leaves out of a state directory: the repository, the locks, the worktree
    scratch directories and every worktree registered under the copy (*rels*, relative to
    it, any depth). With *generated*, `facts.json` and the pages too (rule 5 does not
    compare them)."""

    def __init__(self, rels: frozenset[str] = frozenset(), *, generated: bool = False) -> None:
        self.rels, self.generated = rels, generated

    @classmethod
    def under(cls, copy: Path, trees: list[Path]) -> _Skip:
        base = copy.resolve()
        return cls(frozenset(t.resolve().relative_to(base).as_posix() for t in trees))

    def with_generated(self) -> _Skip:
        return _Skip(self.rels, generated=True)

    def __call__(self, rel: str) -> bool:
        top, _, rest = rel.partition("/")
        if top == ".git" or (not rest and _lockish(top)) or top in SCRATCH_DIRS:
            return True
        if self.generated and not rest and (top == "facts.json" or top.endswith(".html")):
            return True
        return rel in self.rels


def _keep_all(rel: str) -> bool:
    return rel.partition("/")[0] == ".git" or ("/" not in rel and _lockish(rel))


Inventory = dict[str, tuple[str, str]]


def _inventory(path: Path, *, skip: Callable[[str], bool] = _keep_all) -> Inventory:
    """Every file and directory below *path* as `rel -> (kind, digest)`: a regular file by
    its sha256, a symlink by its target (never followed), a directory as `dir`. A path
    *skip* names is left out with everything below it."""
    out: Inventory = {}
    for dirpath, dirnames, filenames in os.walk(path, followlinks=False):
        here = Path(dirpath)
        rel_dir = here.relative_to(path)

        def rel_of(name: str, rel_dir: Path = rel_dir) -> str:
            return (rel_dir / name).as_posix()

        dirnames[:] = [d for d in dirnames if not skip(rel_of(d))]
        links = [d for d in dirnames if (here / d).is_symlink()]
        for name in [*filenames, *links]:
            rel = rel_of(name)
            if skip(rel):
                continue
            full = here / name
            if full.is_symlink():
                out[rel] = ("link", os.readlink(full))
            else:
                out[rel] = ("file", hashlib.sha256(full.read_bytes()).hexdigest())
        dirnames[:] = [d for d in dirnames if d not in links]
        for d in dirnames:
            out[rel_of(d)] = ("dir", "")
    return out


def _reconcile(copy: Path, cache: Path, skip: _Skip) -> list[str]:
    """Rule 5 (review p6-r1): compare *copy* with the S1 *cache* on every file but the
    scratch, the locks, `facts.json` and the pages. The durable files must match, present
    or absent alike; every other file both hold must match. Anything else refuses, naming
    the files. A file or directory only the copy holds is carried into the cache (each
    file written beside its target and linked in, never over a file). The carried paths."""
    from fr.triage.state_ref import ref_entries

    compared = skip.with_generated()
    mine, theirs = _inventory(copy, skip=compared), _inventory(cache, skip=compared)
    durable = set(ref_entries(copy)) | set(ref_entries(cache))
    differ = sorted(
        {rel for rel in mine.keys() & theirs.keys() if mine[rel] != theirs[rel]}
        | {rel for rel in durable if mine.get(rel) != theirs.get(rel)}
    )
    if differ:
        shown = ", ".join(differ[:5]) + (f" and {len(differ) - 5} more" if len(differ) > 5 else "")
        raise TriageError(
            f"{copy} and {cache} both hold this scope's triage state and differ in {shown}: "
            "an fr below S1 may still be writing the clone's copy. Stop it, keep the copy you "
            "want (move the other one aside) and run the command again (S1 R18)"
        )
    carried = sorted(mine.keys() - theirs.keys())
    for rel in carried:  # parents sort before their children
        _carry(copy / rel, cache / rel, mine[rel])
    if not (mine.items() <= _inventory(cache, skip=compared).items()):
        raise TriageError(f"{cache} did not verify after carrying {copy}'s files; {copy} is kept")
    return carried


def _carry(src: Path, dst: Path, entry: tuple[str, str]) -> None:
    kind = entry[0]
    if kind == "dir":
        dst.mkdir(exist_ok=True)
        return
    tmp = dst.parent / f".{dst.name}{_STAGE}{uuid.uuid4().hex}"
    try:
        if kind == "link":
            tmp.symlink_to(os.readlink(src))
        else:
            shutil.copy2(src, tmp)
        os.link(tmp, dst, follow_symlinks=False)  # never over a file another writer made
    except FileExistsError as exc:
        raise TriageError(
            f"{dst} appeared while {src} was carried into it; nothing was overwritten: run "
            "the command again (S1 R18)"
        ) from exc
    finally:
        tmp.unlink(missing_ok=True)


# --- the steps ---------------------------------------------------------------------------


def _clear_leftovers(parent: Path, name: str) -> None:
    """A crashed move's staging and set-aside directories (never the only copy: the clone's
    copy is still whole whenever one is left)."""
    for leftover in (*parent.glob(f".{name}{_STAGE}*"), *parent.glob(f".{name}{_ASIDE}*")):
        shutil.rmtree(leftover, ignore_errors=True)


def _install(copy: Path, cache: Path, skip: _Skip) -> Path | None:
    """Copy *copy* (but what *skip* names) to a staging directory, verify it, make it a
    repository and rename it into *cache*: an empty cache is set aside and deleted, an older
    copy is kept as `<scope>.pre-s1` (rule 2). Right before the rename the cache's kind and
    inventory are read again and must be what they were when the move began (review p6-r7).
    Verified again in place. The set-aside older copy, or None."""
    parent = cache.parent
    seen = (_kind(cache), _inventory(cache))
    stage = parent / f".{cache.name}{_STAGE}{uuid.uuid4().hex}"
    want = _inventory(copy, skip=skip)

    def ignore(d: str, names: list[str]) -> list[str]:
        rel_dir = Path(d).relative_to(copy)
        return [n for n in names if skip((rel_dir / n).as_posix())]

    try:
        shutil.copytree(copy, stage, symlinks=True, ignore=ignore)
        if _inventory(stage) != want:
            raise TriageError(f"the copy of {copy} in {stage} did not verify; nothing was moved")
        gitseam.init_state_repo(stage)
        held = cache / DRIVE_LOCK
        if lock_text(held) is not None:
            shutil.copy2(held, stage / DRIVE_LOCK)  # the mover's hold moves in with it
        if (_kind(cache), _inventory(cache)) != seen:
            raise TriageError(
                f"{cache} changed while the triage state was being moved into it; {copy} is "
                "unchanged: stop whatever writes it, then run the command again (S1 R18)"
            )
        older = seen[0] == "older"
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


def _worktrees_under(root: Path, copy: Path) -> list[Path]:
    """Rule 3's refusal: every worktree registered in *root*'s repository whose path lies
    under *copy*, at any depth. One that is not safe to remove (`gitseam.worktree_unsafe`)
    refuses the move, naming each; the rest are returned, to be removed by `_retire`."""
    base = copy.resolve()
    try:
        registered = gitseam.worktree_paths(root)
    except gitseam.GitError as exc:
        raise TriageError(
            f"cannot list the worktrees of {root} ({exc}): fr does not move {copy} while it "
            "cannot tell which of them lie inside it (S1 R18)"
        ) from exc
    trees = [t for t in registered if t.resolve() != base and t.resolve().is_relative_to(base)]
    present = [t for t in trees if t.is_dir()]
    unsafe = [(t, why) for t in present if (why := gitseam.worktree_unsafe(t)) is not None]
    if unsafe:
        named = "; ".join(f"{t} ({why})" for t, why in unsafe)
        raise TriageError(
            f"{copy} holds worktrees of {root} that are not safe to remove: {named}. Keep what "
            f"you need, then remove each with `git worktree remove <path>` (run in {root}) and "
            "run the command again; nothing was moved (S1 R18)"
        )
    return present


def _retire(root: Path, copy: Path, cache: Path, trees: list[Path]) -> None:
    """Rule 3, then the clone's copy goes: each clean worktree under it removed (never
    forced), the copy renamed aside (one atomic step, so a crash never leaves half of it),
    the tombstone written at its path, the copy deleted, the worktrees pruned."""
    for tree in sorted(trees, key=lambda t: len(t.parts), reverse=True):
        try:
            gitseam.remove_clean_worktree(tree, root)
        except gitseam.GitError as exc:
            raise TriageError(
                f"git would not remove the worktree {tree} ({exc}); {cache} holds the state "
                f"and {copy} is kept: remove it yourself, then run the command again"
            ) from exc
    gone = copy.parent / f".{copy.name}{_GONE}{uuid.uuid4().hex}"
    os.rename(copy, gone)
    _write_tombstone(copy, cache)
    shutil.rmtree(gone, ignore_errors=True)
    gitseam.prune_worktrees(root)


def _write_tombstone(copy: Path, cache: Path) -> None:
    tmp = copy.parent / f".{copy.name}{_STAGE}{uuid.uuid4().hex}"
    tmp.write_text(
        f"{TOMBSTONE}\n"
        f"This scope's triage state moved to {cache} (spec 2026-11-19-event-driven-a-la-carte "
        "R18). This file stops an fr below S1 from re-creating a copy here: it fails on it "
        "instead. Upgrade fr; an S1 fr passes this file by.\n",
        encoding="utf-8",
    )
    os.rename(tmp, copy)


def _tidy(root: Path, parent: Path, say: Callable[[str], None] = _say) -> None:
    """Rule 4: a retired copy left by a crash is deleted, and once no scope's copy (nor a
    tombstone) is left the exclude line goes, then the empty directory, unless another
    worktree of the clone still holds a `.fr/triage-state/` (review p6-r3): the exclude
    line is the shared `info/exclude`'s, and keeps that one out of git too."""
    for gone in parent.glob(f".*{_GONE}*"):
        shutil.rmtree(gone, ignore_errors=True)
    try:
        left = list(parent.iterdir())
    except FileNotFoundError:
        return
    if left:
        return
    try:
        others = [
            t for t in gitseam.worktree_paths(root)
            if not _same(t, root) and (t / PRODUCT_TRIAGE_STATE).is_dir()
        ]  # fmt: skip
    except gitseam.GitError as exc:
        say(f"fr triage: kept the {_state_exclude()} line of info/exclude: {exc}")
        return
    if others:
        say(
            f"fr triage: kept the {_state_exclude()} line of the shared info/exclude: "
            f"{', '.join(str(t / PRODUCT_TRIAGE_STATE) for t in others)} still exists"
        )
    else:
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
