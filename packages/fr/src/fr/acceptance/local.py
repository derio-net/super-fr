"""The `local` acceptance status (spec 2026-11-14-acceptance-local-status).

A `local` row is verified by an automated test anyone can run on any checkout, which
no CI runs. This module is the one definition of why a `local` row is debt
(`local_debt`, R3/R5) and of why a row cannot be set `local` (`local_error`, R2/R3).
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterable, Mapping
from pathlib import Path

from fr.acceptance.model import LEVELS, AcceptanceError, Row, same_repo, split_ref

PROMOTE = "promote to ci"
UNSTAMPED = "unstamped"


def level_ref_paths(row: Row) -> tuple[str, ...]:
    """The repo paths *row*'s level refs name, sorted and unique — the one computation
    `local_debt`, `local_error` and `deliver`'s stamp share (a stamp has one `files`
    entry per path). A ref fr cannot read as `<repo>:<path>` names no path."""
    from fr.acceptance.logical import is_logical

    paths: set[str] = set()
    for lv in LEVELS:
        for ref in row.levels.get(lv, ()):
            if is_logical(ref):
                continue
            try:
                _, path, _ = split_ref(ref)
            except AcceptanceError:
                continue
            paths.add(path)
    return tuple(sorted(paths))


def head_blobs(product_root: Path, paths: Iterable[str]) -> dict[str, str]:
    """path → HEAD blob sha of the product checkout, for those of *paths* HEAD holds.

    One batched `git ls-tree` (spec §A): HEAD is the source, never the index or the
    working tree (review sr-r12). A checkout git cannot read holds nothing."""
    wanted = sorted(set(paths))
    if not wanted:
        return {}
    out = subprocess.run(
        ["git", "ls-tree", "-r", "-z", "HEAD", "--", *wanted],
        cwd=product_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if out.returncode != 0:
        return {}
    blobs: dict[str, str] = {}
    for entry in out.stdout.split("\0"):
        meta, sep, path = entry.partition("\t")
        parts = meta.split()
        if sep and len(parts) == 3 and parts[1] == "blob":
            blobs[path] = parts[2]
    return blobs


def stale_path(row: Row, blobs: Mapping[str, str]) -> str | None:
    """The first path that makes stamped *row* stale (R5), or None when it is fresh:
    a path its refs name and its stamp does not (or the reverse), or a stamped file
    missing at HEAD or whose HEAD blob differs."""
    assert row.local is not None
    paths = set(level_ref_paths(row))
    differ = sorted(paths ^ set(row.local.files))
    if differ:
        return differ[0]
    for path, sha in sorted(row.local.files.items()):
        if blobs.get(path) != sha:
            return path
    return None


def local_debt(rows: Iterable[Row], product_root: Path, *, ci_active: bool) -> dict[str, str]:
    """row id → why that `local` row is debt: `promote to ci` (R3), `unstamped` or
    `stale: <path>` (R5). Fresh rows and rows of any other status are absent.

    *rows* come from the fold (wherever the placement keeps the fragments); the blobs
    come from *product_root*, read once for every row."""
    local = [r for r in rows if r.status == "local"]
    if ci_active:
        return {r.id: PROMOTE for r in local}
    out = {r.id: UNSTAMPED for r in local if r.local is None}
    stamped = [r for r in local if r.local is not None]
    blobs = head_blobs(product_root, (p for r in stamped if r.local for p in r.local.files))
    for r in stamped:
        if (path := stale_path(r, blobs)) is not None:
            out[r.id] = f"stale: {path}"
    return out


def ref_problem(row_id: str, ref: str, base: Path) -> str | None:
    """Why *ref* does not resolve in *base*, or None: `fr.acceptance.check`'s own
    resolution, returning instead of reporting, where a warning (an archived twin)
    counts as unresolved (R2)."""
    from fr.acceptance.check import CheckResult, _resolve_ref

    result = CheckResult()
    _resolve_ref(row_id, ref, base, result)
    problems = result.errors + result.warnings
    return problems[0] if problems else None


def local_error(row: Row, root: Path, *, own: str | None = None) -> str | None:
    """Why *row* cannot be set `local`, or None (R2, R3): it names no level ref, a
    level ref is not a path in this repo (*own*, the repo name; resolved from the
    origin remote when omitted), a ref does not resolve to an existing file and test,
    or the repo has CI."""
    from fr.acceptance.logical import is_logical

    refs = [ref for lv in LEVELS for ref in row.levels.get(lv, ())]
    if not refs:
        return (
            f"row {row.id}: status local needs a level ref (unit, api, int or ui) naming "
            "the test that verifies it — add `--level unit=<repo>:<path>#<test>`"
        )
    if own is None:
        from fr.acceptance.check import resolve_identity
        from fr.acceptance.model import Matrix

        try:
            own = resolve_identity(Matrix(), root)[1]
        except AcceptanceError as e:
            return f"row {row.id}: status local: {e}"
    for ref in refs:
        if is_logical(ref):
            return f"row {row.id}: status local needs a test path in this repo, not {ref}"
        try:
            repo, _, _ = split_ref(ref)
        except AcceptanceError as e:
            return f"row {row.id}: {e}"
        if not same_repo(repo, own):
            return (
                f"row {row.id}: status local needs every level ref in this repo ({own}:), "
                f"but {ref} names another repo"
            )
        if (why := ref_problem(row.id, ref, root)) is not None:
            return f"{why} — status local needs every level ref to name an existing test"
    from fr.acceptance.ci import ci_active

    if ci_active(root):
        return (
            f"row {row.id}: status local is for a repo with no CI, and this repo has CI — "
            "use `ci` when CI runs the test, or `unwired` while it does not"
        )
    return None
