"""A feature's one fragment spelling (spec 2026-11-17-batch-acceptance-edits §F,
derio-net/super-fr#1461).

Fragments written before #1451 are `<slug>-design.yaml` with `feature: <slug>-design`;
every writer since creates `<slug>.yaml`, so one feature can hold two fragments. Both
the `fr.artifacts.fragment_design_name` repair and the merged-row rule
(`fr.acceptance.amend`) read the pair as one fragment, `<slug>.yaml`, by the one merge
rule here: `<slug>.yaml`'s rows and amendments first, then the `-design` file's, an
entry identical in both kept once, and a row id the two define differently refused.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from pathlib import PurePosixPath

from fr.acceptance.fragment import Amendment, Fragment
from fr.acceptance.model import AcceptanceError, Row

DESIGN_SUFFIX = "-design"


class SpellingConflictError(AcceptanceError):
    """The two spellings of one feature's fragment disagree on an entry."""


def design_slug(name: str, feature: str) -> str | None:
    """The slug a fragment file *name* (`<slug>-design.yaml`) whose `feature:` is its
    stem is the old spelling of, else None."""
    p = PurePosixPath(name)
    if p.suffix != ".yaml" or not p.stem.endswith(DESIGN_SUFFIX) or feature != p.stem:
        return None
    return p.stem.removesuffix(DESIGN_SUFFIX)


def merge_spellings(primary: Fragment | None, design: Fragment, slug: str) -> Fragment:
    """*design* (the `-design` spelling) read as feature *slug*, merged into *primary*
    (`<slug>.yaml`, when it exists) by the one rule. Raises `SpellingConflictError`
    naming the id when the two hold one row differently, or disagree on `repo:`."""
    return _merge(primary, design, slug)[0]


def _merge(primary: Fragment | None, design: Fragment, slug: str) -> tuple[Fragment, list[int]]:
    """`merge_spellings`, and where each of *design*'s amendments sits in the result
    (an identical one kept once sits where *primary*'s copy does)."""
    if primary is None:
        return design.model_copy(update={"feature": slug}), list(range(len(design.amendments)))
    if primary.repo != design.repo:
        raise SpellingConflictError(
            f"{slug}: the two spellings disagree on `repo:` ({primary.repo} and {design.repo})"
        )
    rows = {r.id: r for r in primary.rows}
    extra_rows: list[Row] = []
    for row in design.rows:
        held = rows.get(row.id)
        if held is None:
            extra_rows.append(row)
        elif held != row:
            raise SpellingConflictError(
                f"{slug}: row {row.id} is defined differently in {slug}.yaml and "
                f"{slug}{DESIGN_SUFFIX}.yaml; reconcile it by hand, then migrate"
            )
    copies: dict[object, list[int]] = {}
    for k, a in enumerate(primary.amendments):
        copies.setdefault(a, []).append(k)
    extra_amendments: list[Amendment] = []
    positions: list[int] = []
    for amendment in design.amendments:
        free = copies.get(amendment)
        if free:
            positions.append(free.pop(0))
            continue
        positions.append(len(primary.amendments) + len(extra_amendments))
        extra_amendments.append(amendment)
    merged = primary.model_copy(
        update={
            "rows": (*primary.rows, *extra_rows),
            "amendments": (*primary.amendments, *extra_amendments),
        }
    )
    return merged, positions


Position = tuple[str, int]
"""(fragment path, amendment index)."""


def respell(
    frags: Mapping[str, Fragment], *, keep: Collection[str] = ()
) -> tuple[dict[str, Fragment], dict[Position, Position]]:
    """*frags* (fragment path → fragment) with every `<slug>-design.yaml` not in *keep*
    read as `<slug>.yaml`, merged with a `<slug>.yaml` beside it by the one rule; and
    where each moved amendment now sits. A pair in conflict is read as it is (the
    repair, not a reader, reports it); every other pair is still respelled, so one
    conflict never makes another feature's rename read as a removal."""
    out = {p: f for p, f in frags.items() if p in keep or _old_spelling(p, f) is None}
    moved: dict[Position, Position] = {}
    for path, frag in sorted(frags.items()):
        slug = _old_spelling(path, frag)
        if slug is None or path in keep:
            continue
        target = str(PurePosixPath(path).with_name(f"{slug}.yaml"))
        try:
            out[target], positions = _merge(out.get(target), frag, slug)
        except SpellingConflictError:
            out[path] = frag  # this pair as it is; `<slug>.yaml` stays as it was
            continue
        moved.update({(path, k): (target, j) for k, j in enumerate(positions)})
    return dict(sorted(out.items())), moved


def by_one_spelling(
    frags: Mapping[str, Fragment], *, keep: Collection[str] = ()
) -> dict[str, Fragment]:
    """*frags* read by their one spelling (`respell`, without the positions)."""
    return respell(frags, keep=keep)[0]


def spelling_target(path: str, frag: Fragment) -> str | None:
    """The `<slug>.yaml` a `<slug>-design.yaml` at *path* is the old spelling of."""
    slug = _old_spelling(path, frag)
    return None if slug is None else str(PurePosixPath(path).with_name(f"{slug}.yaml"))


def renamed_keep(frags: Mapping[str, Fragment], present: Collection[str]) -> set[str]:
    """The *keep* set for `respell` of merged *frags* against a branch holding the
    fragment paths *present*: every path but a `<slug>-design.yaml` the branch renamed
    (it holds `<slug>.yaml` and no longer holds the `-design` file; review p1-r2). An
    unrepaired tip, or a fold with no branch, is read as it is."""
    keep: set[str] = set()
    for path, frag in frags.items():
        target = spelling_target(path, frag)
        if target is None or path in present or target not in present:
            keep.add(path)
    return keep


def _old_spelling(path: str, frag: Fragment) -> str | None:
    return design_slug(PurePosixPath(path).name, frag.feature)
