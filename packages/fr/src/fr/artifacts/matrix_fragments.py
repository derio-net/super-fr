"""The `matrix` kind's last hop, 5 -> 6: the split into fragments (spec
`2026-11-04-repo-feature-settings-design.md` R19).

`docs/acceptance/matrix.yaml` is split by origin spec into one fragment per
feature, `docs/acceptance/features/<spec-slug>.yaml` (`fr.acceptance.fragment`):

- every row's origin and level refs go through `fr.acceptance.logical.to_logical`,
  so a spec or plan path becomes `spec:<slug>[#R<n>]` / `plan:<slug>` (refs into
  another repo keep their path);
- a row whose converted origins name exactly one spec lands in that spec's
  fragment; one naming none (a debug journal, code) or more than one goes to
  `legacy.yaml`;
- every fragment carries `repo: <org>/<repo>`, the matrix's identity (spec
  journal decision `fragment-repo-identity`);
- the matrix and its committed reports (those git tracks) are deleted: the
  effective matrix is now a fold (`fr.acceptance.fold`), and reports are derived
  (R20). An untracked report is the user's and is left alone.

The kind is RETIRED by this hop (`SchemaMigration.retires`): the runner writes no
stamp and checks the matrix is gone. Per `.claude/rules/artifact-versioning.md`:

1. **Frozen reader.** The body is read with `fr.acceptance.legacy.MatrixV5`
   only, never the live model.
2. **Built in memory, written once.** Every fragment text is rendered and parsed
   back (`parse_fragment`), and the whole set — with any fragment already on
   disk — is folded in memory and compared row for row with the matrix, before
   the first `write_text_atomic`. A matrix that cannot be split is left
   byte-identical and reported as that artifact's failure.
3. **Fragments already here** (review p2-r4) are never overwritten: the split
   carries over only what their fold lacks. A row whose id the fold does not
   know goes to its fragment by the same one-spec rule (inserted into one that
   exists, keeping its bytes, or a new one); a row the fold holds identically is
   dropped; a row the fold holds DIFFERENTLY refuses the matrix, byte-identical,
   naming every such id. This is both the crash window (a run that died after
   writing the fragments carries nothing over and finishes by deleting the
   matrix) and an in-flight branch that kept editing matrix.yaml after main split.
"""

from __future__ import annotations

from pathlib import Path

from fr.artifacts.atomic import write_text_atomic
from fr.artifacts.matrix_strategies import UnconvertibleMatrixError
from fr.artifacts.matrix_verify import UnreadableMatrixError
from fr.artifacts.paths import KIND_DIRS, kind_dir, space_for
from fr.artifacts.runner import MIGRATIONS, SchemaMigration

MIGRATION_NAME = "acceptance-fragments"

__all__ = ["MATRIX_FRAGMENTS_MIGRATION", "MIGRATION_NAME", "split_matrix", "split_texts"]

_DELETED_REPORTS: tuple[str, ...] = (
    f"{KIND_DIRS['acceptance']}/report_local.html",
    f"{KIND_DIRS['acceptance']}/report_linked.html",
    f"{KIND_DIRS['acceptance']}/report_linked.md",
    f"{KIND_DIRS['acceptance']}/report.github.html",
)
"""The committed reports R19 deletes — named here, not read from `fr.acceptance.report`,
because they are what a v5 repo carried, whatever the report module writes later."""


def _root(path: Path) -> Path:
    """`<root>/docs/acceptance/matrix.yaml` → `<root>` (the kind's locator)."""
    return path.parents[2]


def _identity(org: str | None, repo: str | None, root: Path) -> str:
    from fr.acceptance.check import resolve_identity
    from fr.acceptance.model import AcceptanceError, Matrix

    try:
        o, r = resolve_identity(Matrix(org=org, repo=repo), root)
    except AcceptanceError as e:
        raise UnconvertibleMatrixError(
            f"every fragment carries `repo: <org>/<repo>`, and this matrix names none: {e}. "
            "Add `org:` and `repo:` to matrix.yaml, then re-run `fr migrate artifacts --yes`. "
            "Left on version 5, byte-identical."
        ) from e
    return f"{o}/{r}"


def split_texts(text: str, root: Path) -> dict[str, str]:
    """The fragment texts (repo-relative path → text) the split of a v5 matrix
    *text* writes, validated; raises leaving nothing written."""
    from fr.acceptance.edit import insert_row, render_fragment
    from fr.acceptance.fold import fold_texts
    from fr.acceptance.fragment import (
        FRAGMENTS_DIR,
        LEGACY_FEATURE,
        fragment_slug_for_spec,
        parse_fragment,
    )
    from fr.acceptance.legacy import MatrixV5Error, parse_matrix_v5
    from fr.acceptance.logical import parse_logical, to_logical
    from fr.acceptance.model import AcceptanceError, Row
    from fr.artifacts.matrix_anchors import conversions

    try:
        old = parse_matrix_v5(text)
    except MatrixV5Error as e:
        raise UnreadableMatrixError(
            f"not a readable v5 matrix, so fr will not split it ({e}). Fix the file by hand "
            "— it is left on its current version and will be retried."
        ) from e
    repo = _identity(old.org, old.repo, root)
    own = repo.partition("/")[2]
    anchors = conversions(kind_dir("acceptance", space_for(root)) / "matrix.yaml")

    def convert(ref: str) -> str:
        return to_logical(anchors.get(ref, ref), own_repo=own)

    by_feature: dict[str, list[Row]] = {}
    expected: dict[str, dict[str, object]] = {}
    for v5 in old.rows:
        data = v5.model_dump()
        data["origin"] = [convert(o) for o in v5.origin]
        data["levels"] = {lv: [convert(r) for r in refs] for lv, refs in v5.levels.items()}
        try:
            row = Row.model_validate(data)
        except ValueError as e:
            raise UnconvertibleMatrixError(
                f"row {v5.id} does not read as a fragment row once its refs are logical "
                f"({e}). Left on version 5, byte-identical."
            ) from e
        specs = {parse_logical(o).slug for o in row.origin if o.startswith("spec:")}
        feature = (
            fragment_slug_for_spec(f"{next(iter(specs))}.md")
            if len(specs) == 1
            else (LEGACY_FEATURE)
        )
        by_feature.setdefault(feature, []).append(row)
        expected[row.id] = row.model_dump()

    folder = root / FRAGMENTS_DIR
    on_disk = (
        {f"{FRAGMENTS_DIR.as_posix()}/{p.name}": p.read_text() for p in folder.glob("*.yaml")}
        if folder.is_dir()
        else {}
    )
    # Review p2-r4: fragments already here (a branch that merged a split main, or
    # a run that died after writing them) are never overwritten. The split carries
    # over only what their fold lacks: a row it does not know is added, one it
    # holds identically is dropped, one it holds DIFFERENTLY is refused by id.
    try:
        here = fold_texts(on_disk) if on_disk else None
    except AcceptanceError as e:
        raise UnconvertibleMatrixError(
            f"the fragments already here do not fold ({e}), so fr cannot tell which rows of "
            "matrix.yaml they lack. Left on version 5, byte-identical."
        ) from e
    known = {r.id: r.model_dump() for r in here.matrix.rows} if here else {}
    # A row the fragments already DEFINE is accounted for when matrix.yaml holds
    # its definition untouched: every open branch's matrix.yaml carries the copy
    # it had before the split, and amendments made since (a reword, a retire) are
    # the fragments' to apply, not a disagreement (pr1408-r4, found merging main
    # into the PR that introduced the split). Only a copy that matches neither the
    # definition nor the folded row is the branch's own edit, and is refused.
    defined: dict[str, dict[str, object]] = {}
    for rel, frag_text in on_disk.items():
        for drow in parse_fragment(frag_text, source=rel).rows:
            defined[drow.id] = drow.model_dump()

    def accounted(rid: str) -> bool:
        return expected[rid] == defined.get(rid) or expected[rid] == known.get(rid)

    # Review pr1408-r4: a row the fragments RETIRED (an amendment on the default
    # branch) that matrix.yaml holds EDITED would be carried over as a new row and
    # collide with its own definition. Name it and the fix instead.
    retired_ids = {r.id for r in here.retired} if here else set()
    stale_rows = sorted(
        r.id
        for rows in by_feature.values()
        for r in rows
        if r.id in retired_ids and not accounted(r.id)
    )
    if stale_rows:
        raise UnconvertibleMatrixError(
            f"matrix.yaml still holds {len(stale_rows)} edited row(s) the fragments already "
            f"here retired: {', '.join(stale_rows)}. A retired row is never carried back. Delete "
            "those rows from matrix.yaml, then run `fr migrate artifacts --yes` (`uv run fr …` "
            "inside an fr checkout); if the branch still needs one, add it as a new row under "
            "a new id with `fr acceptance add`. Left on version 5, byte-identical."
        )
    differing = sorted(
        r.id for rows in by_feature.values() for r in rows if r.id in known and not accounted(r.id)
    )
    if differing:
        raise UnconvertibleMatrixError(
            f"matrix.yaml and the fragments already here disagree on {len(differing)} row(s): "
            f"{', '.join(differing)}. fr will not merge them silently. Finish the migration "
            "without the edit (put those rows back as the fragments hold them, or delete them "
            "from matrix.yaml), run `fr migrate artifacts --yes`, then re-apply the change "
            "with `fr acceptance set-status` (`uv run fr …` inside an fr checkout). "
            "Left on version 5, byte-identical."
        )
    out: dict[str, str] = {}
    for feature, rows in sorted(by_feature.items()):
        lacking = [r for r in rows if r.id not in known and r.id not in defined]
        if not lacking:
            continue
        rel = f"{FRAGMENTS_DIR.as_posix()}/{feature}.yaml"
        if rel in on_disk:
            text_out = on_disk[rel]
            for r in lacking:
                text_out = insert_row(text_out, r)
            out[rel] = text_out
        else:
            out[rel] = render_fragment(feature, repo, lacking)
    try:
        effective = fold_texts({**on_disk, **out})
    except AcceptanceError as e:
        raise UnconvertibleMatrixError(
            f"the split does not fold with the fragments already here ({e}). "
            "Left on version 5, byte-identical."
        ) from e
    got = {r.id: r.model_dump() for r in effective.matrix.rows}
    # Only the rows this split carries over are checked against the result; one the
    # fragments already define folds to whatever their amendments make of it.
    lost = sorted(
        rid for rid, want in expected.items() if rid not in defined and got.get(rid) != want
    )
    if lost:
        raise UnconvertibleMatrixError(
            f"the split would not carry these rows over unchanged: {', '.join(lost)}. "
            "Left on version 5, byte-identical."
        )
    return out


def _deleted(path: Path) -> list[Path]:
    """The committed reports the split deletes: those of `_DELETED_REPORTS` git
    TRACKS (review p2-r2). An untracked one is the user's file (an ad-hoc render),
    so it is left alone and never listed — listing it would hand the commit a path
    git never knew. Outside a git checkout nothing is tracked, so nothing goes."""
    from fr.git import GitUnavailableError, git_answer

    root = _root(path)
    try:
        listed = git_answer(root, "ls-files", "-z", "--", *_DELETED_REPORTS)
    except GitUnavailableError:
        return []
    if listed.returncode != 0:
        return []
    tracked = set(listed.stdout.split("\0"))
    return [root / rel for rel in _DELETED_REPORTS if rel in tracked]


def _companions(path: Path) -> list[Path]:
    """Every file the split may write or delete beside the matrix, named before it
    runs so the uncommitted-changes veto covers them. When the split cannot name its
    own (a pre-v5 body the frozen reader refuses until the earlier hops run, or one
    it will refuse anyway), every fragment already here is named instead (review
    pr1408-r9): a fragment that does not exist yet holds no uncommitted change."""
    from fr.acceptance.fragment import FRAGMENTS_DIR

    root = _root(path)
    try:
        written = [root / rel for rel in split_texts(path.read_text(), root)]
    except Exception:
        written = sorted((root / FRAGMENTS_DIR).glob("*.yaml"))
    return [*written, *_deleted(path)]


def split_matrix(path: Path) -> list[Path]:
    """Split *path* into fragments, delete it and its committed reports, or raise
    leaving every file untouched. Returns the fragments written and the reports
    deleted (the runner records *path* itself as removed)."""
    root = _root(path)
    try:
        text = path.read_text()
    except OSError as e:
        raise UnreadableMatrixError(f"{path}: cannot read: {e}") from e
    try:
        texts = split_texts(text, root)
    except (UnreadableMatrixError, UnconvertibleMatrixError) as e:
        raise type(e)(f"{path}: {e}") from e
    changed: list[Path] = []
    for rel, body in texts.items():
        target = root / rel
        if not target.exists() or target.read_text() != body:
            target.parent.mkdir(parents=True, exist_ok=True)
            write_text_atomic(target, body)
        changed.append(target)
    for report in _deleted(path):
        if report.exists():
            report.unlink()
            changed.append(report)
    path.unlink()
    return changed


MATRIX_FRAGMENTS_MIGRATION = SchemaMigration(
    kind="matrix",
    from_version=5,
    to_version=6,
    fn=split_matrix,
    description=f"matrix: split into per-feature fragments under "
    f"{KIND_DIRS['acceptance-fragment']}/ "
    "with logical refs; the matrix and its committed reports are deleted (kind retired)",
    companions=_companions,
    retires=True,
)

MIGRATIONS.register(MATRIX_FRAGMENTS_MIGRATION)
