"""Preserve fr's own records across a worktree teardown (#575, spec §3.D).

A run cursor lives INSIDE its workspace, usually uncommitted, so a `down
--force` used to take the run with it. This module keeps a copy beside the
isolation state, in the repo's git common dir — repo-scoped, reachable from
every worktree and from gc's host-wide sweep through `state.repo_root`:

    <git-common-dir>/fr/preserved/<sanitized-branch>/
      teardown.json   # the tombstone — written only after a VERIFIED removal
      files/<repo-relative path>
      staging/        # stage()'s copies until commit() promotes them

Two-phase by design: `stage` copies before anything is destroyed (and raises
if it cannot, so the down aborts with the workspace intact), `commit` records
the teardown only once the worktree is verifiably gone. A down that fails in
between leaves staged copies but never a tombstone claiming a teardown that
did not happen.

`restore` runs when `up` CREATES a worktree for the branch, never when it
reuses one. It is guarded: nothing is restored onto a branch that does not
descend from the torn-down head, and a file changed since is a reported
conflict, never overwritten.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from fr.artifacts.atomic import write_text_atomic
from fr.isolation.types import IsolationError, IsolationState, _git_common_dir, _sanitize

Runner = Callable[..., "subprocess.CompletedProcess[str]"]

RECORDS_PREFIX = "docs/superpowers/"
RUNS_DIR = Path("docs") / "superpowers" / "runs"
TOMBSTONE = "teardown.json"
VERSION = 1


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


@dataclass(frozen=True)
class PreservedFile:
    path: str  # repo-relative
    base_blob: str | None  # HEAD blob at teardown; None when untracked there


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

    @property
    def empty(self) -> bool:
        return not (self.runs or self.files or self.deleted)


@dataclass
class TeardownReport:
    """What `down` ended and where its record went (spec §3.D.3)."""

    branch: str = ""
    preserved_dir: Path | None = None
    ended_runs: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class RestoreResult:
    restored: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    refused: str | None = None  # the descendant-guard notice, when it fired


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


def _load_tombstone(root: Path) -> dict[str, Any] | None:
    try:
        data = json.loads((root / TOMBSTONE).read_text())
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _write_tombstone(root: Path, data: dict[str, Any]) -> None:
    write_text_atomic(root / TOMBSTONE, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# -------------------------------------------------------------------- stage


def _porcelain(run: Runner, worktree: Path) -> list[tuple[str, str]]:
    """(XY, path) per `git status --porcelain=v1 -z -uall` entry. A rename or
    copy counts under its NEW path; its source token is consumed and dropped."""
    res = run(["git", "status", "--porcelain=v1", "-z", "-uall"], cwd=worktree)
    if res.returncode != 0:
        raise IsolationError(
            f"could not read {worktree}'s changes to preserve fr's records under "
            f"docs/superpowers/ (git status failed: {(res.stderr or res.stdout or '').strip()}) "
            "— nothing was torn down. Fix the tree and retry, or discard them with "
            "`fr isolation down --force --no-preserve`."
        )
    tokens = (res.stdout or "").split("\0")
    out: list[tuple[str, str]] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        i += 1
        if len(tok) < 4:
            continue
        xy, path = tok[:2], tok[3:]
        if xy[0] in "RC":
            i += 1  # the source path follows the destination under -z
        out.append((xy, path))
    return out


def _blob(run: Runner, worktree: Path, rev: str, path: str) -> str | None:
    res = run(["git", "rev-parse", "--verify", "--quiet", f"{rev}:{path}"], cwd=worktree)
    return res.stdout.strip() or None if res.returncode == 0 else None


def _head(run: Runner, worktree: Path) -> str | None:
    res = run(["git", "rev-parse", "--verify", "--quiet", "HEAD"], cwd=worktree)
    return res.stdout.strip() or None if res.returncode == 0 else None


def stage(
    state: IsolationState, run: Runner, runs: list[BranchRun] | None = None
) -> PreserveRecord:
    """Copy every changed or untracked path under `docs/superpowers/` into the
    branch's `staging/` dir, with its HEAD blob. Writes NO tombstone — that is
    `commit`'s, after the verified removal. Raises `IsolationError` when it
    cannot copy: the caller aborts the down with the workspace intact."""
    root = preserved_dir(state.repo_root, state.branch)
    worktree = Path(state.worktree)
    if runs is None:
        runs = branch_runs(worktree, state.branch)
    if not worktree.is_dir():
        return PreserveRecord(root, state.branch, worktree, None, runs=list(runs))
    record = PreserveRecord(root, state.branch, worktree, _head(run, worktree), runs=list(runs))
    for xy, path in _porcelain(run, worktree):
        if not path.startswith(RECORDS_PREFIX):
            continue
        if "D" in xy and not (worktree / path).exists():
            record.deleted.append(path)
            continue
        record.files.append(PreservedFile(path, _blob(run, worktree, "HEAD", path)))
    if not (record.files or record.deleted) and not record.runs:
        return record
    staging = root / "staging"
    try:
        if staging.exists():
            shutil.rmtree(staging)
        for f in record.files:
            dst = staging / f.path
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(worktree / f.path, dst)
    except OSError as e:
        raise IsolationError(
            f"could not preserve {state.branch}'s records under docs/superpowers/ ({e}) — "
            "nothing was torn down. Free the space or fix the tree and retry, or discard "
            f"them with `fr isolation down --branch {state.branch} --force --no-preserve`."
        ) from e
    return record


# ------------------------------------------------------------------- commit


def commit(record: PreserveRecord, forced: bool) -> Path | None:
    """Promote the staged copies and write the tombstone — call ONLY after the
    worktree removal is verified. A second teardown of the branch merges: newer
    copies win, runs are unioned, the new `head` is recorded. Returns the
    preserved dir, or None when there was nothing to record."""
    if record.empty:
        return None
    root = record.root
    prior = _load_tombstone(root) or {}
    files: dict[str, str | None] = {
        f["path"]: f.get("base_blob")
        for f in prior.get("files", [])
        if isinstance(f, dict) and isinstance(f.get("path"), str)
    }
    deleted = {p for p in prior.get("deleted", []) if isinstance(p, str)}
    runs: dict[str, dict[str, Any]] = {
        r["id"]: r for r in prior.get("runs", []) if isinstance(r, dict) and "id" in r
    }
    staging = root / "staging"
    for f in record.files:
        dst = root / "files" / f.path
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(staging / f.path, dst)
        files[f.path] = f.base_blob
        deleted.discard(f.path)
    for path in record.deleted:
        deleted.add(path)
        files.pop(path, None)
        (root / "files" / path).unlink(missing_ok=True)
    for r in record.runs:
        runs[r.id] = r.to_json()
    shutil.rmtree(staging, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    _write_tombstone(
        root,
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
    return root


# ------------------------------------------------------------------ restore


def _hash_object(run: Runner, worktree: Path, path: str) -> str | None:
    res = run(["git", "hash-object", "--", path], cwd=worktree)
    return res.stdout.strip() or None if res.returncode == 0 else None


def _same_bytes(a: Path, b: Path) -> bool:
    try:
        return hashlib.sha256(a.read_bytes()).digest() == hashlib.sha256(b.read_bytes()).digest()
    except OSError:
        return False


def _short(sha: str | None) -> str:
    return (sha or "?")[:12]


def restore(repo_root: Path, branch: str, worktree: Path, run: Runner) -> RestoreResult | None:
    """Copy a torn-down branch's preserved records back into a FRESHLY CREATED
    worktree (spec §3.D.4). None when there is no unrestored tombstone. Every
    line goes to stderr: `--print-path` and `fr run start` own stdout."""
    root = preserved_dir(repo_root, branch)
    tomb = _load_tombstone(root)
    if tomb is None or tomb.get("restored_at"):
        return None
    worktree = Path(worktree)
    result = RestoreResult()
    old_head = tomb.get("head")
    new_head = _head(run, worktree)
    if isinstance(old_head, str) and old_head:
        ancestor = run(["git", "merge-base", "--is-ancestor", old_head, "HEAD"], cwd=worktree)
        if ancestor.returncode != 0:
            result.refused = (
                f"isolation: NOT restoring the preserved records at {root} — {branch} is now "
                f"{_short(new_head)}, which does not descend from {_short(old_head)} (the "
                "commit it was torn down at), so the branch was re-created unrelated to it. "
                "The record stays there; copy what you need by hand."
            )
            print(result.refused, file=sys.stderr)
            return result
    for entry in tomb.get("files", []):
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            continue
        path, base = entry["path"], entry.get("base_blob")
        src, dst = root / "files" / path, worktree / path
        if not src.is_file():
            continue
        if not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            result.restored.append(path)
        elif _same_bytes(src, dst):
            continue
        elif base and _hash_object(run, worktree, path) == base:
            shutil.copy2(src, dst)
            result.restored.append(path)
        else:
            result.conflicts.append(path)
    for path in tomb.get("deleted", []):
        if not isinstance(path, str):
            continue
        dst = worktree / path
        base = _blob(run, worktree, old_head, path) if isinstance(old_head, str) else None
        if dst.is_file() and base and _hash_object(run, worktree, path) == base:
            dst.unlink()
            result.removed.append(path)
    tomb["restored_at"] = _now()
    _write_tombstone(root, tomb)
    active = [r for r in tomb.get("runs", []) if isinstance(r, dict) and r.get("active")]
    which = ", ".join(f"run {r.get('id')} at {r.get('cursor')}" for r in active)
    n = len(result.restored)
    print(
        f"isolation: restored {n} preserved file(s)" + (f" ({which})" if which else ""),
        file=sys.stderr,
    )
    for path in result.conflicts:
        print(
            f"isolation: preserved {path} conflicts with the checkout — left in place; "
            f"the preserved copy stays at {root / 'files' / path}",
            file=sys.stderr,
        )
    return result
