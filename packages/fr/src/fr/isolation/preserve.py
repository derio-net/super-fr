"""Preserve fr's own records across a worktree teardown (#575, spec §3.D).

A run cursor lives INSIDE its workspace, usually uncommitted, so a `down
--force` used to take the run with it. This module keeps a copy beside the
isolation state, in the repo's git common dir — repo-scoped, reachable from
every worktree and from gc's host-wide sweep through `state.repo_root`:

    <git-common-dir>/fr/preserved/<sanitized-branch>/
      teardown.json   # the tombstone — written only after a VERIFIED removal
      files/<repo-relative path>
      staging/        # stage()'s copies until commit() promotes them
        stage.json    # what was staged, and whether removal was attempted
        files/<repo-relative path>

Two-phase by design: `stage` copies before anything is destroyed (and raises
if it cannot, so the down aborts with the workspace intact); `commit` records
the teardown only once the worktree is verifiably gone. Between the two,
`mark_removal_attempted` flips `stage.json`, and from then on staging/ is the
ONLY copy of what the removal may already have destroyed: it is never wiped,
a retry merges into it, and `restore` points at it if nothing promoted it
(phase-4 review p4-f2/f4).

`restore` runs when `up` CREATES a worktree for an EXISTING branch, never when
it reuses one or cold-starts a new branch of the same name (p4-f5). It is
guarded: nothing is restored onto a branch that does not descend from the
torn-down head (or whose head is gone, p4-f8), and a file changed since is a
reported conflict, never overwritten. A tombstone that was restored is
history: the next teardown starts a fresh one (p4-f1).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, TypeGuard

import yaml

from fr.artifacts.atomic import write_text_atomic
from fr.isolation.types import IsolationError, IsolationState, _git_common_dir, _sanitize

Runner = Callable[..., "subprocess.CompletedProcess[str]"]

RECORDS_PREFIX = "docs/superpowers/"
RUNS_DIR = Path("docs") / "superpowers" / "runs"
TOMBSTONE = "teardown.json"
STAGE_JSON = "stage.json"
VERSION = 1
NO_PRESERVE = "--no-preserve"
# Never copied from inside an ignored match, and a cap on what ignored files
# may add in total — an ignored tree is often a cache, not a record (p4-n6).
CACHE_DIRS = frozenset(
    {".venv", "__pycache__", "node_modules", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
)
IGNORED_CAP_BYTES = 50 * 1024 * 1024


# ------------------------------------------------------------------ records


@dataclass(frozen=True)
class BranchRun:
    """One run file of this branch, as far as raw YAML can tell."""

    id: str
    cursor: str
    active: bool
    file: str  # repo-relative
    unreadable: bool = False

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.id,
            "cursor": self.cursor,
            "active": self.active,
            "file": self.file,
        }
        if self.unreadable:
            out["unreadable"] = True
        return out

    @classmethod
    def from_json(cls, data: Any) -> BranchRun | None:
        if not isinstance(data, dict) or not isinstance(data.get("id"), str):
            return None
        return cls(
            id=data["id"],
            cursor=str(data.get("cursor") or "?"),
            active=bool(data.get("active", True)),
            file=str(data.get("file") or ""),
            unreadable=bool(data.get("unreadable", False)),
        )


@dataclass(frozen=True)
class PreservedFile:
    path: str  # repo-relative
    base_blob: str | None  # HEAD blob at teardown; None when untracked there
    # False only for a run file copied although it is committed and unchanged
    # (p4-f3): kept so a restore has it, but alone it is no reason for a tombstone.
    changed: bool = True


@dataclass
class PreserveRecord:
    """What `stage` copied, awaiting `commit` after the verified removal."""

    root: Path  # preserved dir for this branch
    branch: str
    worktree: Path
    head: str | None
    runs: list[BranchRun] = field(default_factory=list)
    files: list[PreservedFile] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)  # non-regular entries (p4-f7)

    @property
    def staging(self) -> Path:
        return self.root / "staging"

    @property
    def worthwhile(self) -> bool:
        """A tombstone is written only for a changed file, a deletion or an
        ACTIVE run — never for a clean down or a gc reap (p4-f11)."""
        return (
            any(f.changed for f in self.files)
            or bool(self.deleted)
            or any(r.active for r in self.runs)
        )

    def unpreserved_runs(self) -> list[str]:
        """Active runs whose file did not make it into the record (p4-f3)."""
        copied = {f.path for f in self.files}
        return [r.id for r in self.runs if r.active and r.file not in copied]


@dataclass
class TeardownReport:
    """What `down` ended and where its record went (spec §3.D.3)."""

    branch: str = ""
    preserved_dir: Path | None = None
    ended_runs: list[tuple[str, str]] = field(default_factory=list)
    # Why nothing was preserved, when something should have been: NO_PRESERVE,
    # or a failed commit naming the staging dir that still holds the copies.
    reason: str | None = None
    preserved_files: int = 0
    skipped: list[str] = field(default_factory=list)
    unpreserved_runs: list[str] = field(default_factory=list)


@dataclass
class RestoreResult:
    restored: list[str] = field(default_factory=list)
    # Recorded deletions still present in the checkout: reported, never
    # re-applied — restore never deletes (p4-d1).
    not_redeleted: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    refused: str | None = None  # the notice, when a guard declined to restore


# ------------------------------------------------------------ run discovery


def _unreadable(path: Path, worktree: Path) -> BranchRun:
    return BranchRun(
        id=path.stem, cursor="?", active=True, file=_rel(path, worktree), unreadable=True
    )


def _rel(path: Path, worktree: Path) -> str:
    try:
        return path.relative_to(worktree).as_posix()
    except ValueError:
        return str(path)


def branch_runs(worktree: Path, branch: str) -> list[BranchRun]:
    """This branch's run files under `docs/superpowers/runs/`, read with plain
    `yaml.safe_load` — never the live `extra="forbid"` model, so an old stamp or
    a half-written file still reads. NEVER raises.

    Kept: files whose `branch:` equals `branch` (a checkout carries other
    branches' finished runs — not this workspace's). A file that cannot be read
    or parsed, or is not shaped like a run (no mapping, no `branch`, `steps` not
    a mapping), is kept as active and `unreadable`: unknown is not "finished".
    """
    try:
        paths = sorted((Path(worktree) / RUNS_DIR).glob("*.yaml"))
    except OSError:
        return []
    runs: list[BranchRun] = []
    for path in paths:
        try:
            data = yaml.safe_load(path.read_text())
        except Exception:
            runs.append(_unreadable(path, worktree))
            continue
        if not isinstance(data, dict) or "branch" not in data:
            runs.append(_unreadable(path, worktree))
            continue
        if data.get("branch") != branch:
            continue
        steps = data.get("steps")
        if not isinstance(steps, dict) or not all(isinstance(s, dict) for s in steps.values()):
            runs.append(_unreadable(path, worktree))
            continue
        run_id = data.get("run")
        cursor = data.get("cursor")
        runs.append(
            BranchRun(
                id=run_id if isinstance(run_id, str) and run_id else path.stem,
                cursor=cursor if isinstance(cursor, str) and cursor else "?",
                active=any(s.get("state") != "done" for s in steps.values()),
                file=_rel(path, worktree),
            )
        )
    return runs


def runs_line(runs: list[BranchRun]) -> str:
    """`holds run <id> at step <cursor>`, one line per ACTIVE run ('' if none)."""
    lines = []
    for r in runs:
        if not r.active:
            continue
        line = f"holds run {r.id} at step {r.cursor}"
        if r.unreadable:
            line += f" (unreadable run file {r.file})"
        lines.append(line)
    return "\n".join(lines)


def name_runs(runs: list[BranchRun], refusal: str) -> str:
    """Prefix a refusal with the active runs it would end (spec §3.D.1). The
    one helper both `_down_worktree_tail` and `down_refusal` go through."""
    line = runs_line(runs)
    return f"{line}\n{refusal}" if line else refusal


# ------------------------------------------------------------------ storage


def preserved_dir(repo_root: Path, branch: str) -> Path:
    """Keyed on the WORKSPACE's repo (`state.repo_root`), never the caller's:
    gc sweeps other repos' workspaces from whichever repo triggered it."""
    return _git_common_dir(repo_root) / "fr" / "preserved" / _sanitize(branch)


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _safe(path: Any) -> TypeGuard[str]:
    """A repo-relative path under docs/superpowers/ that cannot escape the
    worktree — anything else read from disk is refused (p4-f15)."""
    if not isinstance(path, str) or not path.startswith(RECORDS_PREFIX):
        return False
    p = PurePosixPath(path)
    return not p.is_absolute() and ".." not in p.parts


# -------------------------------------------------------------------- stage


def _porcelain(run: Runner, worktree: Path) -> list[tuple[str, str, str | None]] | None:
    """(XY, path, rename-source) per `git status --porcelain=v1 -z -uall
    --ignored=matching` entry under docs/superpowers/ — ignored entries too, so
    a gitignored cursor is not silently left behind (p4-f3). None when git
    status fails (the caller falls back to a git-less copy, p4-f10)."""
    try:
        res = run(
            [
                "git",
                "status",
                "--porcelain=v1",
                "-z",
                "-uall",
                "--ignored=matching",
                "--",
                RECORDS_PREFIX.rstrip("/"),
            ],
            cwd=worktree,
        )
    except UnicodeDecodeError as e:
        raise IsolationError(
            f"could not read {worktree}'s changes under docs/superpowers/ (a path git "
            f"reports is not UTF-8: {e}) — nothing was torn down. Rename it and retry, or "
            "discard fr's records with `fr isolation down --force --no-preserve`."
        ) from e
    if res.returncode != 0:
        return None
    tokens = (res.stdout or "").split("\0")
    out: list[tuple[str, str, str | None]] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        i += 1
        if len(tok) < 4:
            continue
        xy, path, source = tok[:2], tok[3:], None
        if xy[0] in "RC" and i < len(tokens):
            source = tokens[i]  # under -z the source FOLLOWS the destination
            i += 1
            if xy[0] == "C":
                source = None  # a copy keeps its source
        out.append((xy, path, source))
    return out


def _blob(run: Runner, worktree: Path, rev: str, path: str) -> str | None:
    res = run(["git", "rev-parse", "--verify", "--quiet", f"{rev}:{path}"], cwd=worktree)
    return (res.stdout.strip() or None) if res.returncode == 0 else None


def _head(run: Runner, worktree: Path) -> str | None:
    res = run(["git", "rev-parse", "--verify", "--quiet", "HEAD"], cwd=worktree)
    return (res.stdout.strip() or None) if res.returncode == 0 else None


def _hash_object(run: Runner, worktree: Path, path: str) -> str | None:
    res = run(["git", "hash-object", "--", path], cwd=worktree)
    return (res.stdout.strip() or None) if res.returncode == 0 else None


class _Collector:
    """Accumulates the paths a stage will copy, delete-record or skip."""

    def __init__(self, worktree: Path) -> None:
        self.worktree = worktree
        self.files: dict[str, str | None] = {}  # path -> base_blob
        self.unchanged: set[str] = set()
        self.deleted: list[str] = []
        self.skipped: list[str] = []
        self.ignored_bytes = 0

    def add(self, path: str, base_blob: str | None, ignored: bool = False) -> None:
        p = self.worktree / path
        if p.is_symlink() or not p.is_file():
            if path not in self.skipped:
                self.skipped.append(path)
            return
        if ignored and path not in self.files:
            size = p.stat().st_size
            if self.ignored_bytes + size > IGNORED_CAP_BYTES:
                self.skipped.append(f"{path} (over the 50 MB cap for ignored files)")
                return
            self.ignored_bytes += size
        self.files.setdefault(path, base_blob)
        self.skipped = [s for s in self.skipped if not s.startswith(f"{path} (")]

    def walk(self, rel_dir: str, blob: Callable[[str], str | None], ignored: bool = False) -> None:
        """Every regular file under `rel_dir`, never following a link, never
        descending into a nested repository (p4-f7) or a cache dir (p4-n6)."""
        top = self.worktree / rel_dir
        if (top / ".git").exists() or top.name in CACHE_DIRS:
            self.skipped.append(rel_dir.rstrip("/") + "/")
            return
        for dirpath, dirnames, filenames in os.walk(top, followlinks=False):
            here = Path(dirpath)
            for d in list(dirnames):
                sub = here / d
                if sub.is_symlink() or (sub / ".git").exists() or d in CACHE_DIRS:
                    dirnames.remove(d)
                    self.skipped.append(_rel_posix(sub, self.worktree) + "/")
            for name in sorted(filenames):
                rel = _rel_posix(here / name, self.worktree)
                self.add(rel, blob(rel), ignored=ignored)


def _rel_posix(path: Path, worktree: Path) -> str:
    return path.relative_to(worktree).as_posix()


def _collect(run: Runner, worktree: Path, runs: list[BranchRun]) -> _Collector:
    c = _Collector(worktree)
    entries = _porcelain(run, worktree)
    if entries is None:
        # git cannot read the tree (p4-f10): copy docs/superpowers/ wholesale,
        # base_blob null, so a restore only fills absent paths or reports a
        # conflict — never overwrites on a guess.
        if (worktree / RECORDS_PREFIX).is_dir():
            c.walk(RECORDS_PREFIX, lambda _p: None, ignored=True)
        return c
    for xy, path, source in entries:
        if source is not None and source.startswith(RECORDS_PREFIX):
            if not (worktree / source).exists():
                c.deleted.append(source)  # a rename's source half (p4-f6)
        if not path.startswith(RECORDS_PREFIX):
            continue
        ignored = xy == "!!"
        if path.endswith("/"):
            c.walk(path, lambda p: _blob(run, worktree, "HEAD", p), ignored=ignored)
            continue
        target = worktree / path
        if "D" in xy and not target.exists() and not target.is_symlink():
            c.deleted.append(path)
            continue
        c.add(path, None if ignored else _blob(run, worktree, "HEAD", path), ignored=ignored)
    # Every run file of the branch, listed or not — a cursor a status did not
    # show (ignored, or committed and unchanged) is still the run (p4-f3).
    for r in runs:
        if r.file in c.files or not _safe(r.file):
            continue
        base = _blob(run, worktree, "HEAD", r.file)
        c.add(r.file, base)
        if r.file in c.files and base and _hash_object(run, worktree, r.file) == base:
            c.unchanged.add(r.file)
    return c


def stage(
    state: IsolationState, run: Runner, runs: list[BranchRun] | None = None
) -> PreserveRecord:
    """Copy every changed, untracked or ignored path under `docs/superpowers/`
    (plus every run file of the branch) into `staging/`, with its HEAD blob.
    Writes NO tombstone — that is `commit`'s, after the verified removal.
    Raises `IsolationError` when it cannot copy: the caller aborts the down
    with the workspace intact.

    A staging/ whose removal was ATTEMPTED is a previous down's only copy of
    what that removal may have destroyed (p4-f2): it is never wiped. This
    stage merges into it: where the path still exists in the tree, the tree
    wins; an earlier entry survives only for a path now absent or unreadable
    (p4-n2), and no deletion is added that the first attempt did not record
    (a half-removed tree reads as deletions). stage.json is written for every
    preserving down, a clean tree included (p4-n1)."""
    root = preserved_dir(state.repo_root, state.branch)
    worktree = Path(state.worktree)
    if runs is None:
        runs = branch_runs(worktree, state.branch)
    staging = root / "staging"
    prior = _load_json(staging / STAGE_JSON)
    retry = bool(prior and prior.get("removal_attempted"))

    c = _collect(run, worktree, runs) if worktree.is_dir() else _Collector(worktree)
    head = _head(run, worktree) if worktree.is_dir() else None
    record = PreserveRecord(
        root,
        state.branch,
        worktree,
        head,
        runs=list(runs),
        files=[
            PreservedFile(p, b, changed=p not in c.unchanged) for p, b in sorted(c.files.items())
        ],
        deleted=sorted(set(c.deleted)),
        skipped=c.skipped,
    )
    current = set(c.files)
    if retry and prior is not None:
        _merge_prior(record, prior, current)
    if not retry and staging.exists():
        shutil.rmtree(staging)  # nothing was destroyed after it: safe to redo
    # stage.json is written for EVERY preserving down — a clean tree too — so
    # the removal is always marked and a retry never mistakes a half-removed
    # tree for fresh work (p4-n1).
    try:
        for f in record.files:
            if f.path not in current:
                continue  # an earlier attempt's copy: kept, never re-copied (p4-n2)
            src = worktree / f.path
            dst = staging / "files" / f.path
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst, follow_symlinks=False)
        _write_stage(record, removal_attempted=retry)
    except OSError as e:
        raise IsolationError(
            f"could not preserve {state.branch}'s records under docs/superpowers/ ({e}) — "
            "nothing was torn down. Free the space or fix the tree and retry, or discard "
            f"them with `fr isolation down --branch {state.branch} --force --no-preserve`."
        ) from e
    return record


def _gone(worktree: Path, path: str) -> bool:
    """Absent or unreadable in the tree — the only case in which an earlier
    attempt's entry still speaks for the path (p4-n2)."""
    p = worktree / path
    return p.is_symlink() or not p.is_file()


def _merge_prior(record: PreserveRecord, prior: dict[str, Any], current: set[str]) -> None:
    """Fold an earlier, removal-attempted stage into this one. Where the path
    still exists in the tree the tree wins and the earlier entry is dropped —
    a retry on an intact tree must not resurrect what the operator has since
    settled (p4-n2). Each kept snapshot keeps its own base_blob.

    A copy may sit in `files/` rather than staging/ when a commit crashed
    between its promotions and the tombstone write: accepted when no tombstone
    lists it (p4-n5)."""
    worktree = record.worktree
    listed = {
        f.get("path")
        for f in (_load_json(record.root / TOMBSTONE) or {}).get("files", [])
        if isinstance(f, dict)
    }
    for entry in prior.get("files", []):
        if not isinstance(entry, dict) or not _safe(entry.get("path")):
            continue
        path = entry["path"]
        if path in current or not _gone(worktree, path):
            continue
        staged = (record.staging / "files" / path).is_file()
        promoted = (record.root / "files" / path).is_file() and path not in listed
        if staged or promoted:
            record.files.append(
                PreservedFile(path, entry.get("base_blob"), bool(entry.get("changed", True)))
            )
    record.files.sort(key=lambda f: f.path)
    # Deletions: the first attempt's only, and only while still absent.
    record.deleted = sorted(
        p for p in prior.get("deleted", []) if _safe(p) and not (worktree / p).exists()
    )
    known = {r.id for r in record.runs}
    for data in prior.get("runs", []):
        r = BranchRun.from_json(data)
        if r is not None and r.id not in known and (not r.file or _gone(worktree, r.file)):
            record.runs.append(r)
    if record.head is None and isinstance(prior.get("head"), str):
        record.head = prior["head"]


def _write_stage(record: PreserveRecord, removal_attempted: bool) -> None:
    _write_json(
        record.staging / STAGE_JSON,
        {
            "version": VERSION,
            "branch": record.branch,
            "worktree": str(record.worktree),
            "head": record.head,
            "removal_attempted": removal_attempted,
            "runs": [r.to_json() for r in record.runs],
            "files": [
                {"path": f.path, "base_blob": f.base_blob, "changed": f.changed}
                for f in record.files
            ],
            "deleted": record.deleted,
            "skipped": record.skipped,
        },
    )


def mark_removal_attempted(record: PreserveRecord) -> None:
    """Called just before `git worktree remove`: from here on staging/ may be
    the only copy, so it is protected (never wiped, merged on retry). Creates
    stage.json if the stage wrote none (p4-n1)."""
    _write_stage(record, removal_attempted=True)


# ------------------------------------------------------------------- commit


def _default_run(argv: list[str], cwd: Path | None = None, **_kw: Any) -> Any:
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True)


def _is_ancestor(run: Runner, root: Path, older: str, newer: str) -> bool:
    common = root.parent.parent.parent  # <common>/fr/preserved/<branch>
    res = run(["git", f"--git-dir={common}", "merge-base", "--is-ancestor", older, newer])
    return res.returncode == 0


def commit(record: PreserveRecord, forced: bool, run: Runner = _default_run) -> Path | None:
    """Promote the staged copies (`os.replace`) and write the tombstone — call
    ONLY after the worktree removal is verified. The tombstone is written
    atomically BEFORE staging/ is removed (p4-f9).

    An UNRESTORED prior tombstone merges (newer copies win, runs unioned, the
    new `head` recorded). A RESTORED one is history — its content went back
    into the worktree and may since have been committed over — so this starts
    fresh rather than re-applying it on the next `up` (p4-f1). Returns the
    preserved dir, or None when there was nothing worth recording."""
    root = record.root
    staging = record.staging
    if not record.worthwhile:
        shutil.rmtree(staging, ignore_errors=True)
        try:
            root.rmdir()  # only when empty
        except OSError:
            pass
        return None
    prior = _load_json(root / TOMBSTONE)
    prior_head = prior.get("head") if prior else None
    if record.head is None and isinstance(prior_head, str) and prior_head:
        record.head = prior_head  # a git-less teardown keeps the lineage (p4-n4)
    # Fresh unless the prior tombstone is unrestored AND of this lineage: a
    # null head, or one this teardown's head does not descend from, is not
    # something to merge into (p4-n3).
    fresh = (
        prior is None
        or bool(prior.get("restored_at"))
        or not (isinstance(prior_head, str) and prior_head)
        or record.head is None
        or not _is_ancestor(run, root, prior_head, record.head)
    )
    old_files = root / "files.old"
    if fresh:
        prior = {}
        if old_files.exists():
            shutil.rmtree(old_files)
        if (root / "files").exists():
            os.replace(root / "files", old_files)
    assert prior is not None
    files: dict[str, str | None] = {
        f["path"]: f.get("base_blob")
        for f in prior.get("files", [])
        if isinstance(f, dict) and _safe(f.get("path"))
    }
    deleted = {p for p in prior.get("deleted", []) if _safe(p)}
    runs: dict[str, dict[str, Any]] = {
        r["id"]: r for r in prior.get("runs", []) if isinstance(r, dict) and "id" in r
    }
    for f in record.files:
        dst = root / "files" / f.path
        src = staging / "files" / f.path
        if not src.is_file() and fresh and (old_files / f.path).is_file():
            src = old_files / f.path  # promoted by an earlier, interrupted commit
        if src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            os.replace(src, dst)
        files[f.path] = f.base_blob
        deleted.discard(f.path)
    for path in record.deleted:
        deleted.add(path)
        files.pop(path, None)
        (root / "files" / path).unlink(missing_ok=True)
    for r in record.runs:
        runs[r.id] = r.to_json()
    _write_json(
        root / TOMBSTONE,
        {
            "version": VERSION,
            "branch": record.branch,
            "worktree": str(record.worktree),
            "torn_down_at": _now(),
            "forced": forced,
            "head": record.head,
            "runs": list(runs.values()),
            "files": [{"path": p, "base_blob": b} for p, b in sorted(files.items())],
            "deleted": sorted(deleted),
        },
    )
    shutil.rmtree(old_files, ignore_errors=True)
    shutil.rmtree(staging, ignore_errors=True)
    return root


# ------------------------------------------------------------------ restore


def _same_bytes(a: Path, b: Path) -> bool:
    try:
        return hashlib.sha256(a.read_bytes()).digest() == hashlib.sha256(b.read_bytes()).digest()
    except OSError:
        return False


def _short(sha: str | None) -> str:
    return (sha or "?")[:12]


def _decline(root: Path, tomb: dict[str, Any], result: RestoreResult, why: str) -> RestoreResult:
    """Restore declined: move the whole preserved dir aside to
    `<branch>@<UTC>` with `declined_at` stamped, so no later teardown of the
    same name merges it back (p4-n3), and say where it went."""
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    aside = root.parent / f"{root.name}@{stamp}"
    n = 1
    while aside.exists():
        n += 1
        aside = root.parent / f"{root.name}@{stamp}-{n}"
    try:
        os.replace(root, aside)
        tomb["declined_at"] = _now()
        _write_json(aside / TOMBSTONE, tomb)
    except OSError:
        aside = root
    notice = (
        f"isolation: NOT restoring the preserved records — {why}. They were moved to "
        f"{aside}; if they belong here: cp -R {aside / 'files'}/. <worktree>/"
    )
    result.refused = notice
    print(notice, file=sys.stderr)
    return result


def _inside(worktree: Path, dst: Path) -> bool:
    try:
        return dst.resolve().is_relative_to(worktree.resolve())
    except OSError:
        return False


def restore(
    repo_root: Path, branch: str, worktree: Path, run: Runner, *, new_branch: bool = False
) -> RestoreResult | None:
    """Copy a torn-down branch's preserved records back into a FRESHLY CREATED
    worktree (spec §3.D.4). None when there is no unrestored tombstone. Every
    line goes to stderr: `--print-path` and `fr run start` own stdout.

    `new_branch` — `up` cold-started a brand-new branch that merely reuses the
    name: nothing is restored, the notice says where the records are (p4-f5)."""
    root = preserved_dir(repo_root, branch)
    worktree = Path(worktree)
    stage_state = _load_json(root / "staging" / STAGE_JSON)
    if stage_state and stage_state.get("removal_attempted"):
        print(
            f"isolation: an unfinished teardown of {branch} left fr's records at "
            f"{root / 'staging' / 'files'} (never promoted, so NOT restored) — copy what "
            f"belongs here, or the next `fr isolation down --branch {branch}` merges them.",
            file=sys.stderr,
        )
    tomb = _load_json(root / TOMBSTONE)
    if tomb is None or tomb.get("restored_at"):
        return None
    result = RestoreResult()
    torn = tomb.get("torn_down_at", "?")
    if new_branch:
        return _decline(
            root,
            tomb,
            result,
            f"{branch} was created as a NEW branch, unrelated to the {branch} torn down {torn}",
        )
    old_head = tomb.get("head")
    if not (isinstance(old_head, str) and old_head):
        return _decline(root, tomb, result, "the teardown recorded no commit (null head)")
    exists = run(["git", "cat-file", "-e", f"{old_head}^{{commit}}"], cwd=worktree)
    if exists.returncode != 0:
        return _decline(
            root,
            tomb,
            result,
            f"the commit {branch} was torn down at ({_short(old_head)}) no longer exists "
            "in this repo, so fr cannot tell whether they still apply",
        )
    ancestor = run(["git", "merge-base", "--is-ancestor", old_head, "HEAD"], cwd=worktree)
    if ancestor.returncode != 0:
        return _decline(
            root,
            tomb,
            result,
            f"{branch} is now {_short(_head(run, worktree))}, which does not descend from "
            f"{_short(old_head)} (the commit it was torn down at)",
        )
    for entry in tomb.get("files", []):
        path = entry.get("path") if isinstance(entry, dict) else None
        if not _safe(path):
            print(
                f"isolation: ignoring preserved path outside docs/superpowers/: {path!r}",
                file=sys.stderr,
            )
            continue
        base = entry.get("base_blob")
        src, dst = root / "files" / path, worktree / path
        if not src.is_file():
            continue
        if not _inside(worktree, dst):
            print(
                f"isolation: refusing to restore {path}: it resolves outside the worktree "
                f"(a symlink in the checkout); the preserved copy stays at {src}",
                file=sys.stderr,
            )
            continue
        if not dst.exists() and not dst.is_symlink():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            result.restored.append(path)
        elif _same_bytes(src, dst):
            continue
        elif base and dst.is_file() and _hash_object(run, worktree, path) == base:
            shutil.copy2(src, dst)
            result.restored.append(path)
        else:
            result.conflicts.append(path)
    # Restore NEVER deletes (p4-d1): a recorded deletion that is present in
    # the checkout is reported, and the operator decides.
    for path in tomb.get("deleted", []):
        if not _safe(path):
            print(
                f"isolation: ignoring preserved path outside docs/superpowers/: {path!r}",
                file=sys.stderr,
            )
            continue
        if (worktree / path).exists():
            result.not_redeleted.append(path)
    tomb["restored_at"] = _now()
    _write_json(root / TOMBSTONE, tomb)
    active = [r for r in tomb.get("runs", []) if isinstance(r, dict) and r.get("active")]
    which = ", ".join(f"run {r.get('id')} at {r.get('cursor')}" for r in active)
    if result.restored:  # never a "restored 0" line (p4-f11)
        print(
            f"isolation: restored {len(result.restored)} preserved file(s)"
            + (f" ({which})" if which else ""),
            file=sys.stderr,
        )
    if result.not_redeleted:
        print(
            f"isolation: {len(result.not_redeleted)} path(s) deleted before teardown were "
            f"not re-deleted: {', '.join(result.not_redeleted)}",
            file=sys.stderr,
        )
    for path in result.conflicts:
        print(
            f"isolation: preserved {path} conflicts with the checkout — left in place; "
            f"the preserved copy stays at {root / 'files' / path}",
            file=sys.stderr,
        )
    return result
