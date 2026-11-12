"""Logical references to fr artifacts (spec 2026-11-04-repo-feature-settings R18).

A row cites fr's own artifacts logically — `spec:<slug>[#<anchor>]` (R18 names
`spec:<slug>#R<n>`) and `plan:<slug>` — so a placement move or an archive never
rewrites a row. Only those two kinds are logical (spec journal decision
`logical-ref-forms`): journal and code refs keep their `<repo>:<path>[#frag]` form.

A logical ref's `<slug>` never contains `/`, which a code ref's path almost always
does; `is_logical` decides on the prefix alone.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from fr.acceptance.model import AcceptanceError, Matrix, same_repo, split_ref

LOGICAL_KINDS: tuple[str, ...] = ("spec", "plan")

SPEC_DIRS: tuple[str, ...] = ("docs/superpowers/specs/", "docs/superpowers/implemented/specs/")
PLAN_DIRS: tuple[str, ...] = ("docs/superpowers/plans/", "docs/superpowers/implemented/plans/")

_SLUG_RE = re.compile(r"^[^/:#\s]+$")


@dataclass(frozen=True)
class LogicalRef:
    kind: str
    slug: str
    anchor: str = ""

    def __str__(self) -> str:
        return f"{self.kind}:{self.slug}" + (f"#{self.anchor}" if self.anchor else "")


def is_logical(ref: str) -> bool:
    """Whether *ref* is written in a logical form (`spec:` or `plan:`)."""
    kind, sep, _ = ref.partition(":")
    return bool(sep) and kind in LOGICAL_KINDS


def parse_logical(ref: str) -> LogicalRef:
    """`spec:<slug>[#anchor]` / `plan:<slug>[#anchor]` → `LogicalRef`, or `AcceptanceError`."""
    kind, sep, rest = ref.partition(":")
    if not sep or kind not in LOGICAL_KINDS:
        raise AcceptanceError(f"not a logical ref ({'|'.join(LOGICAL_KINDS)}:<slug>): {ref!r}")
    slug, hashed, anchor = rest.partition("#")
    if not _SLUG_RE.match(slug) or (hashed and not anchor):
        raise AcceptanceError(f"logical ref must be '{kind}:<slug>[#<anchor>]': {ref!r}")
    return LogicalRef(kind, slug, anchor)


def to_logical(ref: str, *, own_repo: str | None = None) -> str:
    """The logical form of a path ref to a spec or a plan folder; any other ref unchanged.

    `<repo>:docs/superpowers/[implemented/]specs/<stem>.md[#frag]` becomes
    `spec:<stem minus -design>[#frag]`; `<repo>:docs/superpowers/[implemented/]plans/<slug>[/]`
    becomes `plan:<slug>`. A ref to a file inside a plan folder, a journal, or code keeps
    its path. With *own_repo*, a ref naming another repo keeps its path too: a logical
    ref has no repo, so converting it would point it at this one."""
    if is_logical(ref):
        return ref
    try:
        repo, path, frag = split_ref(ref)
    except AcceptanceError:
        return ref
    if own_repo is not None and not same_repo(repo, own_repo):
        return ref
    from fr.acceptance.fragment import fragment_slug_for_spec

    for base in SPEC_DIRS:
        rest = path.removeprefix(base)
        if rest != path and "/" not in rest and rest.endswith(".md"):
            return str(LogicalRef("spec", fragment_slug_for_spec(rest), frag))
    for base in PLAN_DIRS:
        rest = path.removeprefix(base).rstrip("/")
        if rest != path.rstrip("/") and rest and "/" not in rest and not frag:
            return str(LogicalRef("plan", rest))
    return ref


def candidates(ref: LogicalRef) -> tuple[str, ...]:
    if ref.kind == "spec":
        return tuple(
            f"{base}{ref.slug}{suffix}" for base in SPEC_DIRS for suffix in ("-design.md", ".md")
        )
    return tuple(f"{base}{ref.slug}" for base in PLAN_DIRS)


def _resolve(ref: str, repo_root: Path) -> tuple[Path | None, str | None]:
    try:
        logical = parse_logical(ref)
    except AcceptanceError as e:
        return None, str(e)
    root = Path(repo_root)
    for rel in candidates(logical):
        target = root / rel
        if target.is_dir() if logical.kind == "plan" else target.is_file():
            return Path(PurePosixPath(rel)), None
    tried = ", ".join(candidates(logical))
    return None, f"{ref}: no {logical.kind} {logical.slug!r} in this repo (looked for {tried})"


def resolve_logical(ref: str, repo_root: Path) -> Path | None:
    """The repo-relative path a logical ref names, or None (`resolution_problem` says why).

    Until plan 3 this reads `repo` paths only (R18): a live spec
    (`specs/<slug>-design.md`, else `specs/<slug>.md`), else its archived twin under
    `implemented/`; a plan folder, live or archived. Plan 3 swaps in R1's resolver
    behind this one function, so no caller changes."""
    return _resolve(ref, repo_root)[0]


def resolution_problem(ref: str, repo_root: Path) -> str | None:
    """Why *ref* does not resolve, or None when it does."""
    return _resolve(ref, repo_root)[1]


def as_path_ref(ref: str, repo_root: Path, own_repo: str) -> str:
    """*ref* as a `<own_repo>:<path>[#anchor]` path ref when it is logical, else *ref*.

    For readers that link or open the file a ref names (reports, the link checks):
    the resolved path when the artifact exists, else the first place it was looked
    for, so an existence check reports it missing rather than skipping it."""
    if not is_logical(ref):
        return ref
    try:
        logical = parse_logical(ref)
    except AcceptanceError:
        return ref
    found = resolve_logical(ref, repo_root)
    rel = found.as_posix() if found is not None else candidates(logical)[0]
    return f"{own_repo}:{rel}" + (f"#{logical.anchor}" if logical.anchor else "")


def path_view(matrix: Matrix, repo_root: Path, own_repo: str) -> Matrix:
    """*matrix* with every logical ref replaced by `as_path_ref`'s path ref — an
    in-memory view for path-shaped readers, never written back (R18: a placement
    move never rewrites a row)."""
    from fr.acceptance.model import LEVELS

    def conv(refs: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(as_path_ref(r, repo_root, own_repo) for r in refs)

    rows = tuple(
        row.model_copy(
            update={
                "origin": conv(row.origin),
                "levels": {lv: conv(tuple(row.levels.get(lv, ()))) for lv in LEVELS},
            }
        )
        for row in matrix.rows
    )
    return matrix.model_copy(update={"rows": rows})


def origin_spec_path(origin: str, repo_root: Path) -> str | None:
    """The repo-relative spec file *origin* names when it names one, or None: a
    logical `spec:<slug>` resolved in this repo (live, else archived), or a path
    origin's own `.md` path (not checked for existence)."""
    if is_logical(origin):
        try:
            if parse_logical(origin).kind != "spec":
                return None
        except AcceptanceError:
            return None
        found = resolve_logical(origin, repo_root)
        return found.as_posix() if found is not None else None
    try:
        _, path, _ = split_ref(origin)
    except AcceptanceError:
        return None
    return path if path.endswith(".md") else None
