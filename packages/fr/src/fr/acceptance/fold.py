"""The effective acceptance matrix: a fold over fragments (spec 2026-11-04 R17).

The effective matrix is never stored. It is derived from the fragments under
`docs/acceptance/features/` (`fr.acceptance.fragment`):

1. **Merged.** Every fragment at the default ref's tip contributes its rows. Its
   amendments apply in the order of the first-parent commit of the default ref that
   introduced each one (one `git log --first-parent --reverse` over the fragments);
   ties inside one commit (a merge commit, a squash) break by `base`, then feature
   slug, then list index, so a branch's own sequence on one row across fragments
   applies in the order it was written (plan journal `fold-ties-break-by-base`).
2. **Pending.** A branch's view then adds its own entries not yet on the default
   ref: the working tree's rows and amendments the merged fragments do not carry,
   ordered as one merge commit will order them (by `base`, feature slug, list
   index). An abandoned branch's entries are in no tree the
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
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING

from fr.acceptance.fragment import FRAGMENTS_DIR, Amendment, Fragment, SetStatus, parse_fragment
from fr.acceptance.model import LEVELS, AcceptanceError, LocalStamp, Matrix, Row

if TYPE_CHECKING:
    from fr.artifacts.paths import ArtifactSpace
    from fr.placement.merged import MergedView

GitRunner = Callable[[Sequence[str], bytes | None], "subprocess.CompletedProcess[bytes]"]
"""`(git args, stdin) -> completed process`, run in the repo being folded."""

FRAGMENTS_REL = FRAGMENTS_DIR.as_posix()
GIT_TIMEOUT_SECONDS = 60.0


class FoldError(AcceptanceError):
    """The fragments cannot be folded: a row defined twice, a pending amendment naming
    an unknown row, a git failure."""


class FoldHistoryError(FoldError):
    """The history the fold needs is not in this clone (a shallow checkout)."""


@dataclass(frozen=True)
class StalePending:
    """A branch's own amendment written against a revision its row has moved past
    (R17's stale base): refused before merge by `check` and `deliver`."""

    row: str
    op: str
    base: int
    revision: int
    """The row's revision when this amendment applies: what `base` should be."""
    path: str
    index: int
    """The amendment's position in its fragment's `amendments:` list."""


@dataclass(frozen=True)
class Effective:
    """The effective matrix and what the fold learned on the way."""

    matrix: Matrix
    revisions: dict[str, int]
    """Row id -> the count of amendments applied to it."""
    contested: frozenset[str]
    """Rows, live or retired, whose last amendment had a stale base (R17): debt."""
    owners: dict[str, str]
    """Row id -> the feature whose fragment created it."""
    retired: tuple[Row, ...]
    pending: tuple[Amendment, ...]
    """The branch's own amendments, applied after every merged one."""
    notices: tuple[str, ...]
    stale_pending: tuple[StalePending, ...] = ()
    """The branch's own amendments whose `base` is not the row's revision when they
    apply (R17): `check` and `deliver` refuse them."""


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


def _amendment_list(text: str | None) -> list[object]:
    """The raw `amendments:` entries of a historical blob; lenient, because an old
    revision is only compared, never validated."""
    if text is None:
        return []
    import yaml

    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        return []
    amendments = data.get("amendments") if isinstance(data, dict) else None
    return amendments if isinstance(amendments, list) else []


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
    lists = [_amendment_list(t) for t in texts]
    out: dict[tuple[str, int], int] = {}
    last = max(len(commits) - 1, 0)
    for path in amended:
        history = [(pos, got) for (q, pos), got in zip(specs, lists, strict=True) if q == path]
        tip = history[-1][1] if history else []
        for k in range(len(fragments[path].amendments)):
            # By value, not list position (review pr1408-r8): the (n+1)-th copy of
            # an entry was introduced by the first commit holding n+1 copies of it.
            entry = tip[k] if k < len(tip) else None
            nth = tip[:k].count(entry)
            out[(path, k)] = next((pos for pos, got in history if got.count(entry) > nth), last)
    return out


def _working_fragments(root: Path) -> dict[str, str]:
    """The fragments below *root*, an artifact root (the checkout, or a quiet feature's)."""
    from fr.artifacts.paths import below

    folder = below(root, "acceptance-fragment")
    if not folder.is_dir():
        return {}
    return {
        f"{FRAGMENTS_REL}/{p.name}": p.read_text(encoding="utf-8")
        for p in sorted(folder.glob("*.yaml"))
        if p.is_file()
    }


def _stamp_after(amendment: SetStatus) -> LocalStamp | None:
    """The row's `local` stamp after *amendment* (spec 2026-11-14-acceptance-local-status
    §A): a set-status to `local` replaces it with its own, `None` when it carries none,
    so an earlier stamp never survives a re-set; any other status drops it."""
    return amendment.local if amendment.status == "local" else None


def apply_amendment(row: Row, amendment: Amendment) -> Row:
    """*row* with *amendment* applied (R16 op semantics, plan journal `fold-op-semantics`)."""
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
        update = {
            "status": amendment.status,
            "notes": amendment.notes,
            "walks": walks,
            "issues": issues,
            "local": _stamp_after(amendment),
        }
        if amendment.verify is not None:
            update["verify"] = amendment.verify
        if amendment.scenario is not None:
            update["scenario"] = amendment.scenario
        return row.model_copy(update=update)
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
        _CACHE[key] = _fold(run, sha, working)
    result = copy.deepcopy(_CACHE[key])
    # The merged-ref notice depends on how *ref* was resolved, not on the commit the
    # key names, so it is added per call, never cached (an explicit `ref="HEAD"` at
    # the same sha as a no-remote fallback must not inherit its notice).
    if notice:
        result = replace(result, notices=(notice, *result.notices))
    return result


def fold_texts(working: dict[str, str]) -> Effective:
    """The fold of *working* (repo-relative fragment path → text) alone, as pending
    entries over no merged history: no git, no disk. What a migration validates the
    fragments it is about to write against (R19)."""

    def no_git(args: Sequence[str], stdin: bytes | None) -> subprocess.CompletedProcess[bytes]:
        raise FoldError(f"an in-memory fold runs no git (asked for `git {' '.join(args)}`)")

    return _fold(no_git, "", dict(sorted(working.items())))


def has_fragments(repo_root: Path) -> bool:
    """Whether *repo_root*'s working tree holds at least one fragment: the one
    "this repo keeps acceptance rows" test every reader and hook shares (R19)."""
    from fr.artifacts.paths import search_roots

    # Under quiet and stealth every feature root: the repo keeps rows when any feature does.
    return any(
        (top / FRAGMENTS_DIR).is_dir()
        and any(p.is_file() for p in (top / FRAGMENTS_DIR).glob("*.yaml"))
        for top in search_roots(Path(repo_root), FRAGMENTS_REL)
    )


def load_effective(repo_root: Path, *, ref: str | None = None) -> Matrix:
    """The effective matrix (`effective(...).matrix`); see `effective`."""
    return effective(repo_root, ref=ref).matrix


def default_ref_fold(repo_root: Path) -> Effective | None:
    """The fold of the default ref's history alone, or None when the repo has no
    default ref (no remote, or none fetched): then no row is merged ON a default
    ref, so nothing is held to "a merged row changes only by amendment" (R16)."""
    from fr.git import GitRefusal, GitUnavailableError, remote_default_ref

    if _quiet_root(Path(repo_root)) is not None:
        return None  # R23: a quiet product default ref holds no row (merged status: R25)
    try:
        named = remote_default_ref(Path(repo_root))
    except GitUnavailableError:
        return None
    if named is None or isinstance(named, GitRefusal):
        return None
    return fold(Path(repo_root), ref=f"refs/remotes/{named}", include_pending=False)


def effective(repo_root: Path, *, ref: str | None = None) -> Effective:
    """The fold of *repo_root*: what every reader of acceptance rows reads (spec
    2026-11-04 R17). Every failure is an `AcceptanceError`.

    With *ref*, the fold of that ref's history alone (no pending entries). Without
    it: an empty fold when the working tree has no fragment; the working tree's
    fragments folded in memory when *repo_root* is not the top of a git work tree
    (a bare fixture, an exported tree); else the full fold."""
    root = Path(repo_root)
    froot = _quiet_root(root)
    if froot is not None:
        # Under quiet and stealth the product's default ref holds no fragment (R23, R24):
        # a feature's merged status and order come from its code branch's merge (R17).
        if ref is not None:
            return _empty()
        return _outside_fold(root)
    if ref is not None:
        return fold(root, ref=ref, include_pending=False)
    working = _working_fragments(root)
    if not working:
        return _empty()
    from fr.git import GitUnavailableError, git_answer

    try:
        top = git_answer(root, "rev-parse", "--show-toplevel")
    except GitUnavailableError:
        return fold_texts(working)
    if top.returncode != 0 or Path(top.stdout.strip()).resolve() != root.resolve():
        # Not a work tree, or a directory inside another repo's: the working tree's
        # fragments are all there is.
        return fold_texts(working)
    return fold(root)


def quiet_root(root: Path) -> Path | None:
    """This checkout's feature root when it is not the checkout itself (quiet or
    stealth), else None: the test a reader of the product's own git history asks
    before trusting it to hold fragments."""
    return _quiet_root(root)


def _quiet_root(root: Path) -> Path | None:
    """This checkout's feature root when it is not the checkout itself (quiet), else None."""
    from fr.artifacts.paths import artifact_root

    froot = artifact_root(root)
    return None if froot.resolve() == root.resolve() else froot


def _empty() -> Effective:
    return Effective(
        matrix=Matrix(),
        revisions={},
        contested=frozenset(),
        owners={},
        retired=(),
        pending=(),
        notices=(),
    )


def fold_outside_with(root: Path, own: dict[str, str]) -> Effective:
    """The quiet/stealth fold of *root* with this branch's own fragments replaced by
    *own* (fragment path -> text, relative to its feature root): what a writer validates
    the fragments it is about to write against, since another merged feature's row is
    only known to the fold across features (R16, R17)."""
    return _outside_fold(root, own)


def fold_of_space(root: Path, space: ArtifactSpace) -> Effective:
    """The quiet/stealth fold of the MERGED features below *space* (a placement root with
    no feature of its own), judged against *root*'s default ref: what `fr placement move`
    verifies a destination with before its switch makes it the placement (R27)."""
    return _outside_fold(root, space=space)


def _outside_fold(
    root: Path, own_texts: dict[str, str] | None = None, *, space: ArtifactSpace | None = None
) -> Effective:
    """The fold under quiet and stealth (R17's clause): every MERGED feature's fragments,
    their amendments in the order `fr.placement.merged` gives the features (the
    first-parent commit of the product's default ref that introduced each), then this
    branch's own entries. A feature never merged contributes to its own branch's view
    only. Keys are `features/<id>/<fragment path>`, so two features' fragments never
    share one.

    A merged feature's fragments are FROZEN at its merge (review p5-r5): read from the
    last pushed fr commit of its path at or before the merge commit
    (`merged.frozen_commit`), never from a worktree, so neither a later amendment nor an
    unpushed local change counts as merged. This branch's own feature, merged or not,
    adds its working tree as pending on top: an amendment made after the merge is
    pending (and stale-checked), an in-place edit of a merged row is kept out with the
    "differs from the merged one" notice."""
    from fr.artifacts.paths import FEATURES_DIR, feature_root, space_for

    space = space if space is not None else space_for(root)
    view, frozen, notices = _merged_outside(root, space)

    def own() -> dict[str, str]:
        if own_texts is not None:
            return dict(sorted(own_texts.items()))
        return _working_fragments(feature_root(space))

    merged: dict[str, Fragment] = {}
    intro: dict[tuple[str, int], int] = {}
    for feature in view.features:
        for path, text in frozen.get(feature.feature, {}).items():
            key = f"{FEATURES_DIR}/{feature.feature}/{path}"
            frag = parse_fragment(text, source=key)
            merged[key] = frag
            for k in range(len(frag.amendments)):
                intro[(key, k)] = feature.position
    working: dict[str, str] = {}
    if space.feature is not None:
        working = {f"{FEATURES_DIR}/{space.feature}/{path}": text for path, text in own().items()}
    if not merged and not working:
        return replace(_empty(), notices=notices)
    result = _fold_from(merged, intro, working)
    return replace(result, notices=(*notices, *result.notices))


def _merged_outside(
    root: Path, space: ArtifactSpace
) -> tuple[MergedView, dict[str, dict[str, str]], tuple[str, ...]]:
    """(the merged view, feature id -> its frozen fragment texts, the notices)."""
    from fr.placement.merged import files_at, frozen_commit, merged_features

    placement = space.placement
    view = merged_features(space, root)
    notices = list(view.notices)
    frozen: dict[str, dict[str, str]] = {}
    for feature in view.features:
        commit, why = frozen_commit(feature, placement, root)
        if why:
            notices.append(why)
        texts = files_at(feature.root, placement, commit, FRAGMENTS_REL) if commit else {}
        frozen[feature.feature] = {p: t for p, t in sorted(texts.items()) if _is_fragment_path(p)}
    return view, frozen, tuple(notices)


def own_merged_fragments(root: Path) -> tuple[dict[str, str], dict[str, str], str] | None:
    """Under quiet and stealth, when this branch's own feature is merged: (its fragments
    frozen at the merge, its working ones, the default ref), keyed relative to the
    feature root. None otherwise. What `check`'s in-place-edit refusal reads (R16)."""
    from fr.artifacts.paths import feature_root, space_for

    if _quiet_root(root) is None:
        return None
    space = space_for(root)
    if space.feature is None:
        return None
    view, frozen, _ = _merged_outside(root, space)
    if view.get(space.feature) is None or view.ref is None:
        return None
    ref = view.ref.removeprefix("refs/remotes/")
    return frozen.get(space.feature, {}), _working_fragments(feature_root(space)), ref


def _fold(run: GitRunner, sha: str, working: dict[str, str]) -> Effective:
    merged = _tip_fragments(run, sha) if sha else {}
    amended = any(f.amendments for f in merged.values())
    intro = _introductions(run, sha, merged) if amended else {}
    return _fold_from(merged, intro, working)


def _fold_from(
    merged: dict[str, Fragment],
    intro: dict[tuple[str, int], int],
    working: dict[str, str],
) -> Effective:
    """The fold of *merged* fragments (their amendments ordered by *intro*, the
    introducing position of each `(path, index)`) and the branch's *working* ones."""
    notices: list[str] = []
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
        key=lambda t: (t[0], t[3].base, t[1], t[2]),
    )
    # (amendment, its fragment, whether it is merged, its index in the fragment)
    queue: list[tuple[Amendment, str, bool, int]] = [
        (a, path, True, k) for _, _, k, a, path in ordered
    ]

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
    # Ordered as the merge of this branch will order them (one commit, a tie):
    # base, then feature slug, then list index (plan journal `fold-ties-break-by-base`).
    pending.sort(key=lambda t: (t[2].base, t[0], t[1]))
    queue += [(a, path, False, k) for _, k, a, path in pending]

    if len(set(repos.values())) > 1:
        listed = ", ".join(f"{p} ({r})" for p, r in sorted(repos.items()))
        raise FoldError(f"fragments disagree on `repo:`: {listed}")

    state = {rid: row for rid, (row, _, _) in rows.items()}
    revisions = dict.fromkeys(state, 0)
    contested: set[str] = set()
    retired: dict[str, Row] = {}
    stale: list[StalePending] = []
    for amendment, path, is_merged, index in queue:
        rid = amendment.row
        if rid not in state and rid not in retired:
            if not is_merged:
                raise FoldError(f"{path}: amendment {amendment.op} names unknown row {rid}")
            # A merged entry is immutable, so raising here would leave every reader of
            # the default ref broken with no legal fix: an unknown row has nothing to
            # mark, so it is a notice and the fold goes on.
            notices.append(
                f"{path}: merged amendment {amendment.op} names unknown row {rid}; not applied"
            )
            continue
        # A retired row keeps R17's base rule (plan journal
        # `fold-retired-rows-keep-the-base-rule`): every amendment naming it, pending
        # or merged, is checked like one on a live row, so a contested retired row is
        # cleared by the next correctly based amendment, and a stale retire is visible.
        stale_base = amendment.base != revisions[rid]
        if stale_base:
            contested.add(rid)
            if not is_merged:
                stale.append(
                    StalePending(
                        row=rid,
                        op=amendment.op,
                        base=amendment.base,
                        revision=revisions[rid],
                        path=path,
                        index=index,
                    )
                )
        else:
            contested.discard(rid)
        revisions[rid] += 1
        if rid in retired:
            if stale_base:
                # R17 "merged anyway" on a row retired meanwhile: counted, contested,
                # and not applied to the retired snapshot.
                notices.append(
                    f"{path}: amendment {amendment.op} names retired row {rid} with a "
                    f"stale base; not applied"
                )
            else:
                retired[rid] = apply_amendment(retired[rid], amendment)
            continue
        state[rid] = apply_amendment(state[rid], amendment)
        if amendment.op == "retire":
            retired[rid] = state.pop(rid)

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
        stale_pending=tuple(stale),
    )
