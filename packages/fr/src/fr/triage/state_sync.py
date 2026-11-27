"""Move a scope's durable triage state between its state directory and a repo
(spec 2026-10-05-triage-pages-goal, R12, §H).

The durable state is what an agent or the engine authored and cannot recollect:
the three YAML files, each page's manifest directory (manifest and fragment files),
the stored snapshots and the authored fragment sources. Facts files and the rendered
pages are rebuilt from the forge and never travel, in either direction.

Copies keep the source's mode and mtime (as `shutil.copy2` did) and never delete a
destination file.
A destination file byte-identical to its source is skipped as `identical`: it is
neither copied nor overwritten. Import skips a state file whose mtime is newer than
the repo copy's unless forced. That check reads file mtimes only, and git keeps none:
a fresh checkout or pull stamps every file with the time it was written, so the repo
copy looks newer than anything edited before it and an edited state file is
overwritten (p4-r5). Export before you pull, or compare first.

A symlink is never followed, in either direction and at any depth, and a destination
that is (or sits under) a symlink is never written through: export feeds a commit the
driver pushes, and import reads a cloned repo (p4-sec-symlink-follow). Both are
skipped and reported. The copy itself opens every component with `O_NOFOLLOW` from
its parent's descriptor, so a path swapped for a symlink after those checks is
skipped the same way rather than followed (gh#1003).

The repo-side root is `<base>/<rel>`, and only *rel* (the parts fr appends: the scope
name, the configured export path) is checked by `contained`: no `..`, no symlinked
component, nothing that resolves outside *base* (p4-sec-root-symlink-traversal). The
base itself is trusted as given: on macOS `/var` and `/tmp` are symlinks.

The repo-side root is named by the scope NAME, which every host's scope of one repo
shares; only the scope id tells them apart. So export stamps the root with the scope id
that wrote it (`OWNER_FILE`) and refuses a root another scope id stamped unless told to
take it over: a second scope's export would otherwise replace the first's judgements,
origins and snapshots (gh#1101). The stamp is not durable state; import never reads it.

Every export also writes `RECORD_FILE` beside the stamp: JSON naming each durable file it
left equal to the state's copy with that copy's sha256 (spec 2026-11-27-export-drift R1).
The next export compares the repo-side root with it, so a file someone edited, deleted or
added in the repo since is drift, and the export refuses before a byte moves instead of
reverting the edit (R2, R3); `force` overwrites. With no record nothing is drift, and the
first export writes one. Like the stamp, it is not durable state: import never copies it.
A targeted import (`only`) takes in named paths alone, removing a named one the repo lacks
(R5), so a direct edit in the repo can reach the state before the next export.
"""

from __future__ import annotations

import errno
import filecmp
import hashlib
import json
import os
import shlex
import shutil
import stat
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import NamedTuple

from fr.triage.errors import TriageError
from fr.triage.merge_stops import MergeStop, export_drift_stop_key, record_stop

# The export set: a subset of `fr.triage.state_ref.REF_FILES` (the state ref carries more:
# merge stops, the lease, durable settings, the cloud mailbox), pinned by test_triage_state_ref.
DURABLE_FILES = ("judgements.yaml", "origins.yaml", "subsystems.yaml")
DURABLE_DIRS = (
    "board",  # the old fragment directory of Backlog and Issues, still a fallback input
    "backlog",
    "issues",
    "origins",
    "architecture",
    "history",
    "snapshots",
    "authored-src",
)
_SKIPPED_PARTS = frozenset({"__pycache__"})
SYMLINK = "symlink, not followed"
SYMLINK_DEST = "the destination is a symlink, not written through"
NEWER = "newer in the state directory; --force overwrites it"
IDENTICAL = "identical"
OWNER_FILE = "exported-by"  # the scope id that exports into this root (gh#1101)
RECORD_FILE = "exported-files"  # what the last export left equal to the state (R1)
_RECORD_SCHEMA = 1


class BadRecord(TriageError):  # noqa: N818 - a refusal, beside TriageError
    """The repo-side record is a symlink, not a regular file, or does not parse (R3)."""

    def __init__(self, path: Path, why: str) -> None:
        self.why, self.root = why, path.parent
        super().__init__(f"{path} {why}; `fr triage state export --force` rewrites it")


class Drift(NamedTuple):
    """A durable path the repo changed since the last export (R2)."""

    path: str  # POSIX, relative to the repo-side root
    kind: str  # changed | deleted | added


def drift_text(
    drift: Sequence[Drift],
    *,
    import_argv: Sequence[str],
    force_argv: Sequence[str],
    at: str | None = None,
) -> str:
    """The one operator text for *drift* (R3, R4): the paths with their kinds, then the
    import that keeps the repo's edit (one `--only` per path, *import_argv* first) and the
    forced export that keeps the state's; *at*, a default-branch sha the checkout must be at
    or after. Every argument is shell-quoted. One line, so a Need row can carry it."""
    listed = ", ".join(f"{d.kind} {shlex.quote(d.path)}" for d in drift)
    only = [arg for d in drift for arg in ("--only", d.path)]
    where = "in a checkout of the default branch" + (f" at or after {at}" if at else "")
    return (
        f"changed in the repo since the last export: {listed}. To keep the repo's edit, run "
        f"`{shlex.join([*import_argv, *only])}` {where}, then export again; to keep the "
        f"state's version, run `{shlex.join(force_argv)}`, which overwrites them"
    )


class ExportDrift(TriageError):  # noqa: N818 - a refusal, beside TriageError
    """An export that would overwrite a repo-side edit, refused before any write (R3)."""

    def __init__(self, drift: tuple[Drift, ...], *, base: Path, root: Path) -> None:
        self.drift, self.root = drift, root
        super().__init__(
            f"{root} was "
            + drift_text(
                drift,
                import_argv=["fr", "triage", "state", "import", "--from", str(base)],
                force_argv=["fr", "triage", "state", "export", "--to", str(base), "--force"],
            )
        )


class Skipped(NamedTuple):
    path: str  # POSIX, relative to the root it was read from
    reason: str


@dataclass(frozen=True)
class SyncReport:
    """The relative paths copied, and those left alone with the reason."""

    copied: tuple[str, ...]
    skipped: tuple[Skipped, ...]
    removed: tuple[str, ...] = ()  # a targeted import's named paths the repo lacks (R5)


def _check_plain(base: Path, rel: str) -> list[str]:
    """*rel*'s parts, refused (`TriageError`) when it is absolute or has an empty, `.` or
    `..` part."""
    parts = rel.replace("\\", "/").split("/")
    if not rel or rel.startswith(("/", "\\")) or any(p in ("", ".", "..") for p in parts):
        raise TriageError(f"{rel!r} must be a plain relative path under {base}")
    return parts


def contained(base: Path, rel: str) -> Path:
    """`base / rel`, refused (`TriageError`, naming the path) when *rel* is absolute,
    has an empty, `.` or `..` part, has an existing component under *base* that is a
    symlink (the last one included), or resolves outside `base.resolve()`."""
    parts = _check_plain(base, rel)
    path = base
    for part in parts:
        path = path / part
        if path.is_symlink():
            raise TriageError(f"{path} is a symlink; refusing to read or write through it")
    target = base / "/".join(parts)
    root = base.resolve()
    if not target.resolve().is_relative_to(root):
        raise TriageError(f"{target} resolves outside {base}; refusing it")
    return target


def check_scope_name(name: str) -> str:
    """*name* when it is one plain path part (no separator, not `.` or `..`): the scope
    names the repo-side directory, so it must never step out of it."""
    if not name or name in (".", "..") or "/" in name or "\\" in name:
        raise TriageError(f"scope name {name!r} is not a single plain path part")
    return name


def _walk(root: Path, rel: PurePosixPath) -> Iterator[tuple[str, bool]]:
    """(path, is_symlink) for every regular file and symlink under *root*/*rel*, never
    descending into a symlinked directory (`os.scandir` with `follow_symlinks=False`)."""
    try:
        entries = sorted(os.scandir(root / rel), key=lambda e: e.name)
    except FileNotFoundError:
        return
    for entry in entries:
        if entry.name in _SKIPPED_PARTS:
            continue
        child = rel / entry.name
        if entry.is_symlink():
            yield child.as_posix(), True
        elif entry.is_dir(follow_symlinks=False):
            yield from _walk(root, child)
        elif entry.is_file(follow_symlinks=False):
            yield child.as_posix(), False


def durable_entries(root: Path) -> Iterator[tuple[str, bool]]:
    """Every durable file or symlink under *root*: (POSIX path relative to it, whether
    it is a symlink). A symlink is reported, never followed, at any depth: a durable
    file or directory that is itself a symlink included. Anything else (a socket, a
    fifo) is not durable state and is left out."""
    for name in DURABLE_FILES:
        path = root / name
        if path.is_symlink():
            yield name, True
        elif path.is_file():
            yield name, False
    for name in DURABLE_DIRS:
        path = root / name
        if path.is_symlink():
            yield name, True
        elif path.is_dir():
            yield from _walk(root, PurePosixPath(name))


def _symlinked_dest(dest: Path, rel: str) -> bool:
    """Whether the target, or any directory between *dest* and it, is a symlink."""
    path = dest
    for part in PurePosixPath(rel).parts:
        path = path / part
        if path.is_symlink():
            return True
    return False


def _same(a: Path, b: Path) -> bool:
    try:
        return filecmp.cmp(a, b, shallow=False)
    except OSError:
        return False  # unreadable: never "identical"; the copy reports the error


class _SymlinkError(Exception):
    """A path component turned out to be a symlink when it was opened."""


def _open(name: str, flags: int, *, dir_fd: int, mode: int = 0o777) -> int:
    """`os.open` of *name* under *dir_fd* with `O_NOFOLLOW`: `_SymlinkError` when the
    refusal was a symlink, the `OSError` itself otherwise."""
    try:
        return os.open(name, flags | os.O_NOFOLLOW | os.O_CLOEXEC, mode, dir_fd=dir_fd)
    except OSError as exc:
        try:
            link = stat.S_ISLNK(os.lstat(name, dir_fd=dir_fd).st_mode)
        except OSError:
            raise exc from None
        if link:
            raise _SymlinkError(name) from None
        raise


def _open_dir(root: Path, parts: tuple[str, ...], *, create: bool) -> int:
    """A descriptor for `root/<parts>`, each part opened from its parent's descriptor
    and never through a symlink; *create* makes the missing ones, *root* included.
    *root* is trusted as given, like the base `contained` leaves alone."""
    if create:
        root.mkdir(parents=True, exist_ok=True)
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for part in parts:
            if create:
                try:
                    os.mkdir(part, dir_fd=fd)
                except FileExistsError:
                    pass
            child = _open(part, os.O_RDONLY | os.O_DIRECTORY, dir_fd=fd)
            os.close(fd)
            fd = child
    except BaseException:
        os.close(fd)
        raise
    return fd


def _open_file(root: Path, rel: str) -> int:
    """A read descriptor for `root/rel`, every component opened with `O_NOFOLLOW` from its
    parent's descriptor: `_SymlinkError` when one is a symlink, `FileNotFoundError` (or
    another `OSError`) as `os.open` raises it."""
    *dirs, name = PurePosixPath(rel).parts
    parent = _open_dir(root, tuple(dirs), create=False)
    try:  # O_NONBLOCK: a fifo swapped in must not hang the open
        return _open(name, os.O_RDONLY | os.O_NONBLOCK, dir_fd=parent)
    finally:
        os.close(parent)


def _read(root: Path, rel: str) -> bytes | None:
    """The bytes of `root/rel` through `_open_file`; None when it (or a directory above it)
    is absent. `_SymlinkError` for a symlink, `OSError(EINVAL)` for a non-regular file."""
    try:
        fd = _open_file(root, rel)
    except FileNotFoundError, NotADirectoryError:
        return None
    with os.fdopen(fd, "rb") as reader:
        if not stat.S_ISREG(os.fstat(reader.fileno()).st_mode):
            raise OSError(errno.EINVAL, "not a regular file")
        return reader.read()


def _hash(root: Path, rel: str) -> str | None:
    """The sha256 of `root/rel` read through descriptors; None when absent or a symlink.
    A file that cannot be read is a `TriageError` naming it."""
    try:
        data = _read(root, rel)
    except _SymlinkError:
        return None
    except OSError as exc:
        raise TriageError(f"cannot read {root / rel}: {exc.strerror or exc}") from exc
    return None if data is None else hashlib.sha256(data).hexdigest()


def _record_path(rel: object) -> bool:
    """Whether a record key is a plain relative path to a durable file."""
    if not isinstance(rel, str) or not rel or rel.startswith("/"):
        return False
    parts = rel.split("/")
    if any(p in ("", ".", "..") for p in parts):
        return False
    return rel in DURABLE_FILES or (len(parts) > 1 and parts[0] in DURABLE_DIRS)


def read_record(root: Path) -> dict[str, str] | None:
    """The record's files (path -> sha256) in the repo-side *root*; None when it has none.
    `BadRecord`, naming the file, when it is a symlink, not a regular file, or does not
    hold `{"schema": 1, "files": {<durable path>: <sha256>}}`."""
    path = root / RECORD_FILE
    try:
        data = _read(root, RECORD_FILE)
    except _SymlinkError:
        raise BadRecord(path, "is a symlink, not read") from None
    except OSError as exc:
        raise BadRecord(path, f"cannot be read ({exc.strerror or exc})") from exc
    if data is None:
        return None
    try:
        body = json.loads(data.decode("utf-8"))
    except UnicodeDecodeError, ValueError:
        raise BadRecord(path, "is not JSON") from None
    files = body.get("files") if isinstance(body, dict) else None
    if (
        not isinstance(body, dict)
        or body.get("schema") != _RECORD_SCHEMA
        or not isinstance(files, dict)
        or not all(_record_path(k) and isinstance(v, str) for k, v in files.items())
    ):
        raise BadRecord(path, f"is not a schema {_RECORD_SCHEMA} export record")
    return dict(files)


def stop_on(
    exc: ExportDrift | BadRecord,
    target: Path,
    repo: str,
    *,
    scope_args: Sequence[str],
    path: str,
    at: str,
) -> str:
    """Record the driver's `export-drift:<repo>` stop in the state directory *target* and
    return its reason (R4): the whole operator text, for *repo*'s export into *path*
    refused at default-branch sha *at*. The commands carry the driver's own scope options
    (*scope_args*), each argument quoted. The driver never forces."""
    text = drift_stop_text(exc, scope_args=scope_args or ["--repo", repo], path=path, at=at)
    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    record_stop(target, export_drift_stop_key(repo), MergeStop(at, text, stamp))
    return text


def drift_stop_text(
    exc: ExportDrift | BadRecord, *, scope_args: Sequence[str], path: str, at: str
) -> str:
    """`stop_on`'s reason: for drift, `drift_text` with the driver's commands; for a bad
    record, the record named with its fault and the forced export that rewrites it."""
    rel = f"{path}/{exc.root.name}"
    force = ["fr", "triage", "state", "export", *scope_args, "--to", path, "--force"]
    if isinstance(exc, ExportDrift):
        imp = ["fr", "triage", "state", "import", *scope_args, "--from", path]
        return f"{rel} was " + drift_text(exc.drift, import_argv=imp, force_argv=force, at=at)
    return (
        f"{rel}/{RECORD_FILE} {exc.why}: mend or remove it in a checkout of the default "
        f"branch at or after {at}, or run `{shlex.join(force)}` there, which rewrites it"
    )


def find_drift(state_dir: Path, root: Path, record: Mapping[str, str]) -> tuple[Drift, ...]:
    """Every durable path whose repo copy differs from the state's and that the repo
    changed (the record names another sha256), deleted (the record names it, the state
    has it) or added (the record does not name it) since the export *record* describes
    (R2). A symlink on either side, or under one in the repo, is left out: the copy skips
    it and reports it."""
    state, repo = dict(durable_entries(state_dir)), dict(durable_entries(root))
    out: list[Drift] = []
    for rel in sorted({*state, *repo, *record}):
        if state.get(rel) or repo.get(rel) or _symlinked_dest(root, rel):
            continue
        if _symlinked_dest(state_dir, rel):
            continue
        mine, theirs = _hash(root, rel), _hash(state_dir, rel)
        if mine == theirs:
            continue
        known = record.get(rel)
        if known is None:
            kind = "added" if mine is not None else None
        elif mine is None:
            kind = "deleted" if theirs is not None else None
        else:
            kind = "changed" if mine != known else None
        if kind is not None:
            out.append(Drift(rel, kind))
    return tuple(out)


def _copy(src: Path, dest: Path, rel: str) -> str | None:
    """Copy `src/rel` to `dest/rel` from descriptors, keeping the source's mode and
    times as `shutil.copy2` did; the skip reason when a component is a symlink by the
    time it is opened, None once copied. The checks before it read the tree by name,
    so a path swapped after them must still never be followed (gh#1003)."""
    *dirs, name = PurePosixPath(rel).parts
    try:
        source = _open_file(src, rel)
    except _SymlinkError:
        return SYMLINK
    with os.fdopen(source, "rb") as reader:
        info = os.fstat(reader.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise OSError(errno.EINVAL, "not a regular file")
        try:
            parent = _open_dir(dest, tuple(dirs), create=True)
            try:
                target = _open(
                    name, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, dir_fd=parent, mode=0o600
                )
            finally:
                os.close(parent)
        except _SymlinkError:
            return SYMLINK_DEST
        with os.fdopen(target, "wb") as writer:
            shutil.copyfileobj(reader, writer)
            writer.flush()
            os.fchmod(writer.fileno(), stat.S_IMODE(info.st_mode))
            os.utime(writer.fileno(), ns=(info.st_atime_ns, info.st_mtime_ns))
    return None


def _remove(dest: Path, rel: str) -> str | None:
    """Unlink `dest/rel` from its parent's `O_NOFOLLOW` descriptor; the skip reason when a
    directory above it is a symlink, None once removed (or already gone)."""
    *dirs, name = PurePosixPath(rel).parts
    try:
        parent = _open_dir(dest, tuple(dirs), create=False)
    except _SymlinkError:
        return SYMLINK_DEST
    except FileNotFoundError, NotADirectoryError:
        return None
    try:
        if stat.S_ISLNK(os.lstat(name, dir_fd=parent).st_mode):
            return SYMLINK_DEST
        os.unlink(name, dir_fd=parent)  # a name swapped for a link: the link goes, not its target
    except FileNotFoundError:
        pass
    finally:
        os.close(parent)
    return None


def _sync(
    src: Path, dest: Path, *, keep_newer: bool, selected: frozenset[str] | None = None
) -> SyncReport:
    """Copy *src*'s durable entries over *dest*. With *selected* (a targeted import, R5),
    only those paths: each copied whatever its mtime, and each *dest* has but *src* lacks
    removed; without it, nothing is ever removed."""
    copied: list[str] = []
    skipped: list[Skipped] = []
    removed: list[str] = []
    entries = list(durable_entries(src))
    for rel, link in entries:
        if selected is not None and rel not in selected:
            continue
        source, target = src / rel, dest / rel
        if link:
            skipped.append(Skipped(rel, SYMLINK))
            continue
        if _symlinked_dest(dest, rel):
            skipped.append(Skipped(rel, SYMLINK_DEST))
            continue
        if target.is_file() and _same(source, target):
            skipped.append(Skipped(rel, IDENTICAL))
            continue
        if keep_newer and target.is_file() and target.stat().st_mtime > source.stat().st_mtime:
            skipped.append(Skipped(rel, NEWER))
            continue
        try:
            refused = _copy(src, dest, rel)
        except OSError as exc:  # p4-r10: a clean refusal naming the file, never a traceback
            why = exc.strerror or type(exc).__name__
            raise TriageError(f"cannot copy {rel} to {dest}: {why}") from exc
        if refused:
            skipped.append(Skipped(rel, refused))
            continue
        copied.append(rel)
    if selected is not None:
        have = {rel for rel, _ in entries}
        for rel, link in durable_entries(dest):
            if rel not in selected or rel in have or _symlinked_dest(src, rel):
                continue
            try:
                refused = None if not link else SYMLINK_DEST
                refused = refused or _remove(dest, rel)
            except OSError as exc:
                why = exc.strerror or type(exc).__name__
                raise TriageError(f"cannot remove {rel} from {dest}: {why}") from exc
            if refused:
                skipped.append(Skipped(rel, refused))
            else:
                removed.append(rel)
    return SyncReport(copied=tuple(copied), skipped=tuple(skipped), removed=tuple(removed))


def _stamp(root: Path, owner: str, *, take_over: bool) -> bool:
    """Check the root's `OWNER_FILE` against *owner* before anything is copied; whether
    it must be (re)written. A root with no stamp is claimed. Refused (`TriageError`)
    when another scope id stamped it and not *take_over*, or when the stamp is a
    symlink or under one."""
    if _symlinked_dest(root, OWNER_FILE):
        raise TriageError(f"{root / OWNER_FILE} is a symlink; refusing to read or write it")
    path = root / OWNER_FILE
    try:
        current = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return True
    except OSError as exc:
        raise TriageError(f"cannot read {path}: {exc.strerror or exc}") from exc
    if current == owner:
        return False
    if not take_over:
        raise TriageError(
            f"{root} is exported by scope {current or '(empty stamp)'}, not this scope "
            f"{owner}: a repo keeps one scope's export, and this one would replace it. "
            "Export from that scope, or hand the directory to this one with "
            "`fr triage state export --take-over`"
        )
    return True


def _write_root_file(root: Path, name: str, data: bytes, *, replace_link: bool = False) -> None:
    """Write *name* in *root* from the root's descriptor with `O_NOFOLLOW`: a name swapped
    for a symlink is refused (`TriageError`), or unlinked first when *replace_link*."""
    parent = _open_dir(root, (), create=True)
    try:
        try:
            fd = _open(name, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, dir_fd=parent, mode=0o644)
        except _SymlinkError:
            if not replace_link:
                raise TriageError(f"{root / name} is a symlink; refusing to write it") from None
            os.unlink(name, dir_fd=parent)  # the link itself, never what it points at
            fd = _open(name, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, dir_fd=parent, mode=0o644)
    except _SymlinkError:
        raise TriageError(f"{root / name} is a symlink; refusing to write it") from None
    except OSError as exc:
        raise TriageError(f"cannot write {root / name}: {exc.strerror or exc}") from exc
    finally:
        os.close(parent)
    with os.fdopen(fd, "wb") as writer:
        writer.write(data)


def _record_bytes(root: Path, report: SyncReport) -> bytes:
    """The record of *report*: every path it copied or found identical, hashed from *root*."""
    equal = [*report.copied, *(s.path for s in report.skipped if s.reason == IDENTICAL)]
    files = {rel: digest for rel in sorted(equal) if (digest := _hash(root, rel)) is not None}
    body = {"schema": _RECORD_SCHEMA, "files": files}
    return (json.dumps(body, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _old_record(root: Path) -> bytes | None:
    try:
        return _read(root, RECORD_FILE)
    except _SymlinkError, OSError:
        return None  # unreadable: rewritten (only `force` gets here with a bad record)


def export_state(
    state_dir: Path,
    base: Path,
    rel: str,
    *,
    owner: str,
    take_over: bool = False,
    force: bool = False,
) -> SyncReport:
    """Copy *state_dir*'s durable state into the repo-side root `contained(base, rel)`
    (`<dir>/<scope>/`), overwriting what is there, stamp it with *owner*, the exporting
    scope's id, and write the record of what it left equal to the state (R1). Refused
    before a byte moves when another scope id stamped the root, unless *take_over*, and,
    unless *force*, when the record is bad (`BadRecord`) or the repo changed a file since
    it was written (`ExportDrift`, R2, R3)."""
    root = contained(base, rel)
    restamp = _stamp(root, owner, take_over=take_over)
    if not force and (recorded := read_record(root)) is not None:
        if drift := find_drift(state_dir, root, recorded):
            raise ExportDrift(drift, base=base, root=root)
    report = _sync(state_dir, root, keep_newer=False)
    copied = list(report.copied)
    if restamp:
        _write_root_file(root, OWNER_FILE, f"{owner}\n".encode())
        copied.append(OWNER_FILE)
    record = _record_bytes(root, report)
    if _old_record(root) != record:
        _write_root_file(root, RECORD_FILE, record, replace_link=force)
        copied.append(RECORD_FILE)
    return SyncReport(copied=tuple(copied), skipped=report.skipped)


def _select(root: Path, state_dir: Path, only: Sequence[str]) -> frozenset[str]:
    """The durable paths *only* names: each path itself, or every durable entry below it
    as a directory, of the repo-side *root* or the state. Refused (`TriageError`) before
    anything moves when one is not plain or names no durable entry on either side."""
    known = [rel for tree in (root, state_dir) for rel, _ in durable_entries(tree)]
    selected: set[str] = set()
    for path in only:
        _check_plain(root, path)
        hit = {rel for rel in known if rel == path or rel.startswith(f"{path}/")}
        if not hit:
            raise TriageError(f"{path!r} names no durable file under {root} or {state_dir}")
        selected |= hit
    return frozenset(selected)


def import_state(
    base: Path, rel: str, state_dir: Path, *, force: bool, only: Sequence[str] | None = None
) -> SyncReport:
    """Copy the repo-side root `contained(base, rel)` into *state_dir*; a state file
    newer than its copy is skipped unless *force*. With *only* (R5), the named paths alone:
    each copied even over a newer state file, and each the repo lacks removed from the
    state; no other state file is read or changed."""
    root = contained(base, rel)
    if only is None:
        return _sync(root, state_dir, keep_newer=not force)
    return _sync(root, state_dir, keep_newer=False, selected=_select(root, state_dir, only))
