"""The code tree a suite log covers — spec 2026-09-29-fr-goal-light-path §D (R6).

A phase unit may record the full-suite log its holder ran; `deliver` may then
say `tests: reuse` instead of running the suite again, but only while HEAD's
CODE tree still equals the tree that log covered. "Code" is everything except
fr's own artifact trees (`FR_ARTIFACT_PREFIXES`), because `fr run resolve`
itself commits runs, records, journals and the matrix between the suite run
and `deliver` — counting those would make reuse impossible by construction.

Pure git plumbing, no fr state: every function takes the repo root and shells
out to `git` through `fr.git.git_answer` (C-locale, prompt-free, time-boxed).
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Iterable
from pathlib import Path

from fr.git import GitUnavailableError, git_answer, remote_default_ref

FR_ARTIFACT_PREFIXES: tuple[str, ...] = ("docs/superpowers/", "docs/acceptance/")
"""The repo-relative prefixes that are fr's artifact trees, not code.

Runs, step records, journals, plans and specs live under `docs/superpowers/`;
the acceptance matrix and its three committed reports under `docs/acceptance/`.
`resolve` writes them after a suite has run, so they are left out of the code
tree.

THE STATED LIMIT (spec §D): a change under these prefixes that breaks a test —
`test_validate_artifacts` over the repo's own artifacts, say — is not seen as a
tree change, so a reused log can vouch for it. CI still runs the suite on the
PR, so that cannot merge red; it can only reach a draft PR the ready-guard
holds.
"""


ISOLATION_MARKER = ".fr-isolation"
"""The workspace marker `fr isolation up` writes at the toplevel. It is
excluded through `info/exclude` in a real workspace, but it is fr's, never
code, so it is not counted even where that exclusion is missing."""


def is_code_path(path: str) -> bool:
    """`path` (repo-relative, `/`-separated) is code — not an fr artifact."""
    return path != ISOLATION_MARKER and not path.startswith(FR_ARTIFACT_PREFIXES)


def _out(repo: Path, *args: str) -> str:
    res = git_answer(repo, *args)
    if res.returncode != 0:
        raise GitUnavailableError(f"`git {' '.join(args)}` failed: {res.stderr.strip()}")
    return res.stdout


def _nul_split(raw: str) -> list[str]:
    return [p for p in raw.split("\0") if p]


def code_tree(repo: Path, rev: str = "HEAD") -> str:
    """sha256 over `git ls-tree -r <rev>`, fr's artifact trees removed.

    Committed content only: an uncommitted edit does not move it, which is why
    `deliver`'s reuse also demands `dirty_code_paths` be empty."""
    entries = _nul_split(_out(repo, "ls-tree", "-r", "-z", "--full-tree", rev))
    kept = [e for e in entries if is_code_path(e.partition("\t")[2])]
    return hashlib.sha256("\0".join(kept).encode()).hexdigest()


def dirty_code_paths(repo: Path) -> list[str]:
    """Uncommitted code paths — modified, staged, deleted or untracked (not
    ignored), sorted."""
    raw = _out(repo, "status", "--porcelain=v1", "-z", "--no-renames", "--untracked-files=all")
    paths = {entry[3:] for entry in _nul_split(raw) if len(entry) > 3}
    return sorted(p for p in paths if is_code_path(p))


def default_merge_base(repo: Path) -> str | None:
    """The merge-base of HEAD and the remote default branch, or `None` when no
    remote default branch resolves (a repo with no remote, two remotes and no
    `checkout.defaultRemote`, ...) or the two share no history."""
    found = remote_default_ref(repo)
    if not isinstance(found, str):
        return None
    res = git_answer(repo, "merge-base", "HEAD", found)
    if res.returncode != 0:
        return None
    return res.stdout.strip() or None


def changed_code_paths(repo: Path, since: str | None) -> list[str]:
    """Code paths that differ from commit `since` — committed on HEAD or still
    uncommitted — sorted. `since=None` (no merge-base could be found) counts
    every tracked code path: failing toward stricter, never toward "nothing
    changed"."""
    if since is None:
        committed = _nul_split(_out(repo, "ls-files", "-z"))
    else:
        committed = _nul_split(
            _out(repo, "diff", "-z", "--no-renames", "--name-only", since, "HEAD")
        )
    return sorted({p for p in committed if is_code_path(p)} | set(dirty_code_paths(repo)))


def _deleted_code_paths(repo: Path, since: str | None) -> list[str]:
    """Code paths present at `since` (HEAD when `None`) and absent from the
    working tree now — deleted or renamed away, committed or not."""
    raw = _out(
        repo, "diff", "-z", "--no-renames", "--name-only", "--diff-filter=D", since or "HEAD"
    )
    return [p for p in _nul_split(raw) if is_code_path(p)]


def _dir_label(root: Path, directory: Path) -> str:
    rel = directory.relative_to(root).as_posix()
    return "./" if rel == "." else f"{rel}/"


def newest_code_mtime(
    repo: Path, base: str | None, *, ignore: Iterable[Path] = ()
) -> tuple[float, str] | None:
    """`(mtime, label)` of the newest thing a suite log must postdate, or
    `None` when the checkout tracks no code at all (review r2-2).

    Counted, each by its `lstat` mtime:

    - every TRACKED code path — not only those that differ from `base`, so an
      edit restored to the base's bytes after the suite ran is still seen;
    - every directory that directly holds a tracked code path — a create,
      unlink or rename inside it moves the directory's mtime even where the
      file's own does not (a rename keeps it);
    - the nearest surviving ancestor directory of every code path deleted or
      renamed away since `base` (HEAD when `None`), which is where that
      unlink shows once the file, and perhaps its directory, is gone.

    One `git ls-files`, one `git diff`, then stats: O(tracked files). fr's
    artifact trees are not code (`is_code_path`); `ignore` names files that
    are not code the suite tested (the suite's own log, when it sits in the
    worktree). A directory is labelled `<dir>/`, the repo root `./`.
    """
    root = repo.resolve()
    skipped = {p.resolve() for p in ignore}
    candidates: dict[Path, str] = {}
    for rel in _nul_split(_out(repo, "ls-files", "-z")):
        if not is_code_path(rel):
            continue
        path = root / rel
        if path not in skipped:
            candidates[path] = rel
        parent = path.parent
        candidates.setdefault(parent, _dir_label(root, parent))
    for rel in _deleted_code_paths(repo, base):
        parent = (root / rel).parent
        while parent != root and not parent.is_dir():
            parent = parent.parent
        candidates.setdefault(parent, _dir_label(root, parent))
    newest: tuple[float, str] | None = None
    for path, label in candidates.items():
        try:
            mtime = os.lstat(path).st_mtime
        except OSError:
            continue  # deleted in the working tree: its directory carries it
        if newest is None or mtime > newest[0]:
            newest = (mtime, label)
    return newest


def code_paths_since_tree(repo: Path, tree: str, *, limit: int = 200) -> list[str] | None:
    """The code paths that differ between the newest commit (of HEAD's last
    `limit`) whose code tree is `tree` and the working tree — committed since
    or uncommitted — sorted. `None` when no such commit is found: the tree is
    only a hash, so the paths can be named only through a commit that has it.
    """
    revs = _out(repo, "rev-list", f"--max-count={limit}", "HEAD").split()
    for rev in revs:
        if code_tree(repo, rev) == tree:
            return changed_code_paths(repo, rev)
    return None
