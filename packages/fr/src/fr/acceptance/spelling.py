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

from collections import Counter
from collections.abc import Mapping
from pathlib import PurePosixPath

from fr.acceptance.fragment import Fragment
from fr.acceptance.model import AcceptanceError

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
    if primary is None:
        return design.model_copy(update={"feature": slug})
    if primary.repo != design.repo:
        raise SpellingConflictError(
            f"{slug}: the two spellings disagree on `repo:` ({primary.repo} and {design.repo})"
        )
    rows = {r.id: r for r in primary.rows}
    extra_rows = []
    for row in design.rows:
        held = rows.get(row.id)
        if held is None:
            extra_rows.append(row)
        elif held != row:
            raise SpellingConflictError(
                f"{slug}: row {row.id} is defined differently in {slug}.yaml and "
                f"{slug}{DESIGN_SUFFIX}.yaml; reconcile it by hand, then migrate"
            )
    already = Counter(primary.amendments)
    extra_amendments = []
    for amendment in design.amendments:
        if already[amendment] > 0:
            already[amendment] -= 1
            continue
        extra_amendments.append(amendment)
    return primary.model_copy(
        update={
            "rows": (*primary.rows, *extra_rows),
            "amendments": (*primary.amendments, *extra_amendments),
        }
    )


def by_one_spelling(frags: Mapping[str, Fragment]) -> dict[str, Fragment]:
    """*frags* (fragment path → fragment) with every `<slug>-design.yaml` read as
    `<slug>.yaml`, merged with a `<slug>.yaml` beside it by `merge_spellings`."""
    out = {path: f for path, f in frags.items() if _old_spelling(path, f) is None}
    for path, frag in sorted(frags.items()):
        slug = _old_spelling(path, frag)
        if slug is None:
            continue
        target = str(PurePosixPath(path).with_name(f"{slug}.yaml"))
        out[target] = merge_spellings(out.get(target), frag, slug)
    return dict(sorted(out.items()))


def _old_spelling(path: str, frag: Fragment) -> str | None:
    return design_slug(PurePosixPath(path).name, frag.feature)
