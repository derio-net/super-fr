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


def is_code_path(path: str) -> bool:
    """`path` (repo-relative, `/`-separated) is code — not an fr artifact."""
    return not path.startswith(FR_ARTIFACT_PREFIXES)


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


def newest_code_mtime(
    repo: Path, base: str | None, *, ignore: Iterable[Path] = ()
) -> tuple[float, str] | None:
    """`(mtime, path)` of the most recently modified code path that differs
    from `base` (see `changed_code_paths`), or `None` when none does. A path
    deleted on disk has no mtime and is skipped; `ignore` names files that are
    not code the suite tested (the suite's own log, when it sits in the
    worktree)."""
    skipped = {p.resolve() for p in ignore}
    newest: tuple[float, str] | None = None
    for rel in changed_code_paths(repo, base):
        path = repo / rel
        if path.resolve() in skipped:
            continue
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if newest is None or mtime > newest[0]:
            newest = (mtime, rel)
    return newest
