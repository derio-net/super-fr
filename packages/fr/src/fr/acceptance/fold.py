"""The effective acceptance matrix: a fold over fragments (spec 2026-11-04 R17).

The effective matrix is never stored. It is derived from the fragments under
`docs/acceptance/features/` (`fr.acceptance.fragment`):

1. **Merged.** Every fragment at the default ref's tip contributes its rows. Its
   amendments apply in the order of the first-parent commit of the default ref that
   introduced each one (one `git log --first-parent --reverse` over the fragments);
   ties inside one commit break by feature slug, then list index.
2. **Pending.** A branch's view then adds its own entries not yet on the default
   ref: the working tree's rows and amendments the merged fragments do not carry,
   by feature slug then list index. An abandoned branch's entries are in no tree the
   fold reads, so they never apply.

Each amendment names the row revision it was written against (`base`); the revision
is the count of amendments applied to the row. A stale base still applies, and marks
the row **contested** until the next amendment based on the then-current revision.

Git is reached through one injectable runner (`git_runner`), and blobs are read in
`git cat-file --batch` calls, so the call count is constant in history length. The
default ref comes from `fr.git.remote_default_ref`, the helper `fr.settings.load`
resolves it with; with no default ref (no remote, or one never fetched) HEAD's
first-parent history stands in for it, and the result says so in `notices`.
"""

from __future__ import annotations

import copy
import hashlib
import os
import subprocess
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from fr.acceptance.fragment import FRAGMENTS_DIR, Amendment, Fragment, parse_fragment
from fr.acceptance.model import LEVELS, AcceptanceError, Matrix, Row

GitRunner = Callable[[Sequence[str], bytes | None], "subprocess.CompletedProcess[bytes]"]
"""`(git args, stdin) -> completed process`, run in the repo being folded."""

FRAGMENTS_REL = FRAGMENTS_DIR.as_posix()
GIT_TIMEOUT_SECONDS = 60.0


class FoldError(AcceptanceError):
    """The fragments cannot be folded: a row defined twice, an unknown row, a git failure."""


class FoldHistoryError(FoldError):
    """The history the fold needs is not in this clone (a shallow checkout)."""


@dataclass(frozen=True)
class Effective:
    """The effective matrix and what the fold learned on the way."""

    matrix: Matrix
    revisions: dict[str, int]
    """Row id -> the count of amendments applied to it."""
    contested: frozenset[str]
    """Rows whose last applied amendment had a stale base (R17): debt."""
    owners: dict[str, str]
    """Row id -> the feature whose fragment created it."""
    retired: tuple[Row, ...]
    pending: tuple[Amendment, ...]
    """The branch's own amendments, applied after every merged one."""
    notices: tuple[str, ...]


def git_runner(root: Path) -> GitRunner:
    """The default runner: one prompt-free, C-locale git call in *root*."""
    from fr.git import _GIT_ENV, git_argv

    def run(args: Sequence[str], stdin: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
        try:
            return subprocess.run(
                git_argv(root, *args),
                cwd=root,
                input=stdin,
                capture_output=True,
                timeout=GIT_TIMEOUT_SECONDS,
                env={**os.environ, **_GIT_ENV},
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as e:
            raise FoldError(f"cannot run `git {' '.join(args)}`: {e}") from e

    return run


_CACHE: dict[tuple[str, str, str, bool], Effective] = {}
_CACHE_MAX = 64


def clear_fold_cache() -> None:
    """Forget every memoised fold (tests; a long-lived process that rewrites history)."""
    _CACHE.clear()


def _checked(done: subprocess.CompletedProcess[bytes], what: str) -> bytes:
    if done.returncode != 0:
        raise FoldError(f"git {what} failed: {done.stderr.decode(errors='replace').strip()}")
    return done.stdout


def _merged_ref(root: Path, ref: str | None) -> tuple[str, str | None]:
    """(the ref whose first-parent history is "merged", a notice or None)."""
    if ref is not None:
        return ref, None
    from fr.git import GitRefusal, GitUnavailableError, remote_default_ref

    try:
        named = remote_default_ref(root)
    except GitUnavailableError as e:
        raise FoldError(f"cannot establish the default branch: {e}") from e
    if isinstance(named, GitRefusal):
        raise FoldError(f"cannot establish the default branch: {named.reason}")
    if named is None:
        return "HEAD", (
            "no default ref (no remote, or none fetched): HEAD's first-parent history "
            "stands in for the merged history"
        )
    return f"refs/remotes/{named}", None


def _cat(run: GitRunner, specs: Sequence[str]) -> list[str | None]:
    """Each `<rev>:<path>` (or blob sha) in one `git cat-file --batch`; None when missing."""
    if not specs:
        return []
    out = _checked(run(["cat-file", "--batch"], ("\n".join(specs) + "\n").encode()), "cat-file")
    found: list[str | None] = []
    pos = 0
    for _ in specs:
        nl = out.index(b"\n", pos)
        header = out[pos:nl].decode(errors="replace")
        pos = nl + 1
        if header.endswith((" missing", " ambiguous")):
            found.append(None)
            continue
        size = int(header.rsplit(" ", 1)[1])
        found.append(out[pos : pos + size].decode())
        pos += size + 1
    return found


def _is_fragment_path(path: str) -> bool:
    parent, _, name = path.rpartition("/")
    return parent == FRAGMENTS_REL and name.endswith(".yaml")


def _tip_fragments(run: GitRunner, sha: str) -> dict[str, Fragment]:
    listed = _checked(run(["ls-tree", "-z", sha, "--", f"{FRAGMENTS_REL}/"], None), "ls-tree")
    blobs: list[tuple[str, str]] = []
    for entry in listed.decode().split("\0"):
        if not entry:
            continue
        meta, _, path = entry.partition("\t")
        _, kind, blob = meta.split(" ")
        if kind == "blob" and _is_fragment_path(path):
            blobs.append((path, blob))
    texts = _cat(run, [blob for _, blob in blobs])
    return {
        path: parse_fragment(text, source=path)
        for (path, _), text in zip(blobs, texts, strict=True)
        if text is not None
    }


def _amendment_count(text: str | None) -> int:
    """How many amendments a historical blob carries; lenient, because an old
    revision is only counted, never validated."""
    if text is None:
        return 0
    import yaml

    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        return 0
    amendments = data.get("amendments") if isinstance(data, dict) else None
    return len(amendments) if isinstance(amendments, list) else 0


def _introductions(
    run: GitRunner, sha: str, fragments: dict[str, Fragment]
) -> dict[tuple[str, int], int]:
    """(fragment path, amendment index) -> the position, in the default ref's
    first-parent history, of the commit that introduced that amendment."""
    shallow = _checked(run(["rev-parse", "--is-shallow-repository"], None), "rev-parse")
    if shallow.decode().strip() == "true":
        raise FoldHistoryError(
            "this clone is shallow, and ordering acceptance amendments needs the default "
            "branch's full history: fetch it (`git fetch --unshallow`), or check out with "
            "`fetch-depth: 0` in CI"
        )
    log = _checked(
        run(
            [
                "log",
                "-m",
                "--first-parent",
                "--reverse",
                "--format=commit %H",
                "--name-only",
                sha,
                "--",
                f"{FRAGMENTS_REL}/",
            ],
            None,
        ),
        "log",
    ).decode()
    commits: list[str] = []
    touched: dict[str, list[int]] = {}
    for line in log.splitlines():
        if line.startswith("commit "):
            commits.append(line.removeprefix("commit ").strip())
        elif line and commits and line in fragments:
            positions = touched.setdefault(line, [])
            if not positions or positions[-1] != len(commits) - 1:
                positions.append(len(commits) - 1)
    amended = [p for p, f in fragments.items() if f.amendments]
    specs = [(path, pos) for path in amended for pos in touched.get(path, [])]
    texts = _cat(run, [f"{commits[pos]}:{path}" for path, pos in specs])
    counts = [_amendment_count(t) for t in texts]
    out: dict[tuple[str, int], int] = {}
    last = max(len(commits) - 1, 0)
    for path in amended:
        history = [(pos, n) for (q, pos), n in zip(specs, counts, strict=True) if q == path]
        for k in range(len(fragments[path].amendments)):
            out[(path, k)] = next((pos for pos, n in history if n > k), last)
    return out


def _working_fragments(root: Path) -> dict[str, str]:
    folder = root / FRAGMENTS_DIR
    if not folder.is_dir():
        return {}
    return {
        f"{FRAGMENTS_REL}/{p.name}": p.read_text(encoding="utf-8")
        for p in sorted(folder.glob("*.yaml"))
        if p.is_file()
    }


def _apply(row: Row, amendment: Amendment) -> Row:
    if amendment.op == "reword":
        update: dict[str, object] = {}
        if amendment.acceptance is not None:
            update["acceptance"] = amendment.acceptance
        if amendment.capability is not None:
            update["capability"] = amendment.capability
        return row.model_copy(update=update)
    if amendment.op == "set-status":
        walks = row.walks + ((amendment.walk,) if amendment.walk is not None else ())
        issues = tuple(dict.fromkeys(row.issues + amendment.issues))
        return row.model_copy(
            update={
                "status": amendment.status,
                "notes": amendment.notes,
                "walks": walks,
                "issues": issues,
            }
        )
    if amendment.op == "add-level" or amendment.op == "drop-level":
        levels = {lv: tuple(row.levels.get(lv, ())) for lv in LEVELS}
        refs = levels[amendment.level]
        if amendment.op == "add-level":
            levels[amendment.level] = refs if amendment.ref in refs else (*refs, amendment.ref)
        else:
            levels[amendment.level] = tuple(r for r in refs if r != amendment.ref)
        return row.model_copy(update={"levels": levels})
    return row.model_copy(update={"notes": amendment.notes})  # retire


def fold(
    repo_root: Path,
    *,
    ref: str | None = None,
    include_pending: bool = True,
    runner: GitRunner | None = None,
) -> Effective:
    """The effective matrix of *repo_root*.

    *ref* overrides the merged history (default: the default ref, else HEAD);
    *include_pending* adds the working tree's own entries after every merged one.
    Memoised per process on (repo, the ref's commit, the working tree's fragments);
    every call returns its own deep copy."""
    root = Path(repo_root)
    run = runner or git_runner(root)
    merged_ref, notice = _merged_ref(root, ref)
    done = run(["rev-parse", "--verify", "--quiet", f"{merged_ref}^{{commit}}"], None)
    sha = done.stdout.decode().strip() if done.returncode == 0 else ""
    if not sha and merged_ref != "HEAD":
        raise FoldError(f"{merged_ref} does not name a commit")
    working = _working_fragments(root) if include_pending else {}
    digest = hashlib.sha256()
    for path, text in working.items():
        digest.update(f"{path}\0{text}\0".encode())
    key = (str(root.resolve()), sha, digest.hexdigest(), include_pending)
    if key not in _CACHE:
        if len(_CACHE) >= _CACHE_MAX:
            _CACHE.clear()
        _CACHE[key] = _fold(run, sha, working, notice)
    return copy.deepcopy(_CACHE[key])


def _fold(run: GitRunner, sha: str, working: dict[str, str], notice: str | None) -> Effective:
    notices = [notice] if notice else []
    merged = _tip_fragments(run, sha) if sha else {}
    amended = any(f.amendments for f in merged.values())
    intro = _introductions(run, sha, merged) if amended else {}

    rows: dict[str, tuple[Row, str, int]] = {}  # id -> (row, defining path, index)
    owners: dict[str, str] = {}

    def define(row: Row, path: str, index: int, feature: str) -> None:
        if row.id in rows:
            raise FoldError(f"row {row.id} is defined by both {rows[row.id][1]} and {path}")
        rows[row.id] = (row, path, index)
        owners[row.id] = feature

    for path in sorted(merged):
        for i, row in enumerate(merged[path].rows):
            define(row, path, i, merged[path].feature)

    ordered = sorted(
        (
            (intro[(path, k)], frag.feature, k, a, path)
            for path, frag in merged.items()
            for k, a in enumerate(frag.amendments)
        ),
        key=lambda t: (t[0], t[1], t[2]),
    )
    queue: list[tuple[Amendment, str]] = [(a, path) for _, _, _, a, path in ordered]

    pending: list[tuple[str, int, Amendment, str]] = []
    pending_rows: list[tuple[Row, str, int, str]] = []
    repos = {path: frag.repo for path, frag in merged.items()}
    for path, text in working.items():
        frag = parse_fragment(text, source=path)
        repos[path] = frag.repo
        for i, row in enumerate(frag.rows):
            known = rows.get(row.id)
            if known is not None and known[1] == path:
                if known[0] != row:
                    notices.append(
                        f"{path}: row {row.id} differs from the merged one; a merged row "
                        "changes only by amendment, so the merged definition is kept"
                    )
                continue
            pending_rows.append((row, path, i, frag.feature))
        base = merged.get(path)
        already = Counter(base.amendments if base else ())
        for k, a in enumerate(frag.amendments):
            if already[a] > 0:
                already[a] -= 1
                continue
            pending.append((frag.feature, k, a, path))
    for row, path, i, feature in pending_rows:
        define(row, path, i, feature)
    pending.sort(key=lambda t: (t[0], t[1]))
    queue += [(a, path) for _, _, a, path in pending]

    if len(set(repos.values())) > 1:
        listed = ", ".join(f"{p} ({r})" for p, r in sorted(repos.items()))
        raise FoldError(f"fragments disagree on `repo:`: {listed}")

    state = {rid: row for rid, (row, _, _) in rows.items()}
    revisions = dict.fromkeys(state, 0)
    contested: set[str] = set()
    retired: dict[str, Row] = {}
    for amendment, path in queue:
        rid = amendment.row
        if rid in retired:
            raise FoldError(f"{path}: amendment {amendment.op} names retired row {rid}")
        if rid not in state:
            raise FoldError(f"{path}: amendment {amendment.op} names unknown row {rid}")
        if amendment.base != revisions[rid]:
            contested.add(rid)
        else:
            contested.discard(rid)
        revisions[rid] += 1
        state[rid] = _apply(state[rid], amendment)
        if amendment.op == "retire":
            retired[rid] = state.pop(rid)
            contested.discard(rid)

    def order(rid: str) -> tuple[str, str, int]:
        return (state[rid].capability, owners[rid], rows[rid][2])

    identity = next(iter(repos.values()), None)
    org, _, name = identity.partition("/") if identity else ("", "", "")
    matrix = Matrix(
        org=org or None,
        repo=name or None,
        rows=tuple(state[rid] for rid in sorted(state, key=order)),
    )
    return Effective(
        matrix=matrix,
        revisions=revisions,
        contested=frozenset(contested),
        owners=owners,
        retired=tuple(retired.values()),
        pending=tuple(a for _, _, a, _ in pending),
        notices=tuple(notices),
    )
