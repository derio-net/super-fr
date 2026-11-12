"""The `matrix` kind's name-anchor repair (gh#531).

A `#L<n>` anchor into a Python file is refused at authoring and reported by
`fr acceptance check` (`fr.acceptance.anchors`). Every matrix written before
that rule may carry some, so this repair converts them mechanically: a line
that sits inside a test today becomes that test's name
(`tests/x.py#L42` → `tests/x.py#test_y`, or `#TestX::test_y`).

It is a repair, not a schema migration: the ref grammar is unchanged — a
fragment was always free text, and name anchors were already in use — only the
constraint on what a `.py` fragment may say moved. So the stamp stays put.

What it leaves alone, so its predicate stays false once applied: refs into a
sibling repo (this checkout cannot read them), a file that is missing or does
not parse, and a line that sits in no test — module level, or inside a helper
(an anchor that has already slid off its test: naming the helper would
certify the slide, so a human re-points it). `check` keeps reporting those,
with the reason.

It rewrites `matrix.yaml` textually — every occurrence of an exact ref string,
so a note that quotes the ref moves with it. It reads through the frozen
`MatrixV5` and renders no report (review p2-r3): the split deletes them.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

from fr.artifacts.atomic import write_text_atomic
from fr.artifacts.runner import Repair

REPAIR_NAME = "matrix-name-anchors"
_LINE_ANCHOR_HINT = re.compile(r"\.py#L\d")

__all__ = ["MATRIX_NAME_ANCHORS_REPAIR", "REPAIR_NAME", "conversions"]


def _root(path: Path) -> Path:
    """`<root>/docs/acceptance/matrix.yaml` → `<root>` (the kind's locator)."""
    return path.parents[2]


def conversions(path: Path) -> dict[str, str]:
    """Every own-repo line-anchor ref into Python this checkout can name,
    mapped to its name-anchored replacement. Empty when there is nothing to do
    — including a matrix that does not parse, which is not this repair's to
    report (`fr validate artifacts` does)."""
    from fr.acceptance.anchors import collected_node_at, is_python, line_of
    from fr.acceptance.check import resolve_identity

    # Frozen reader (review p2-r3): the matrix this converts is a v5 file, and the
    # live `Matrix` is the fold's. A pre-v5 matrix still carrying `skipped` fails
    # it, so this returns {} until the 4 -> 5 hop (`matrix_status_split`) has run.
    from fr.acceptance.legacy import LEVELS_V5, MatrixV5Error, parse_matrix_v5_body
    from fr.acceptance.model import AcceptanceError, Matrix, same_repo, split_ref

    root = _root(path)
    try:
        text = path.read_text()
    except OSError:
        return {}
    if not _LINE_ANCHOR_HINT.search(text):
        return {}  # the gate asks before every command: skip the parse and git
    try:
        matrix = parse_matrix_v5_body(text)
        own = resolve_identity(Matrix(org=matrix.org, repo=matrix.repo), root)[1]
    except (MatrixV5Error, AcceptanceError, OSError, ValueError):
        return {}
    out: dict[str, str] = {}
    sources: dict[str, str | None] = {}
    for row in matrix.rows:
        refs = (*row.origin, *(r for lv in LEVELS_V5 for r in row.levels[lv]))
        for ref in refs:
            try:
                repo, rel, frag = split_ref(ref)
            except AcceptanceError:
                continue
            line = line_of(frag)
            if not same_repo(repo, own) or line is None or not is_python(rel) or ref in out:
                continue
            if rel not in sources:
                try:
                    sources[rel] = (root / rel).read_text()
                except (OSError, UnicodeDecodeError):
                    sources[rel] = None
            source = sources[rel]
            name = collected_node_at(source, line) if source is not None else None
            if name is not None:
                out[ref] = f"{repo}:{rel}#{name}"
    return out


def _applies(path: Path) -> bool:
    return bool(conversions(path))


def _fn(path: Path) -> Iterable[Path]:
    from fr.acceptance.legacy import parse_matrix_v5_body

    text = path.read_text()
    for old, new in conversions(path).items():
        # Whole refs only: `#L1` must not match inside `#L10` or `#L1-L5`, and
        # own repo `fr` must not match inside a sibling's `super-fr:…`.
        pattern = r"(?<![\w.-])" + re.escape(old) + r"(?![\w-])"
        text = re.sub(pattern, new.replace("\\", "\\\\"), text)
    parse_matrix_v5_body(text)  # refuse to write a matrix that no longer reads
    # No committed report is rendered (review p2-r1/p2-r3): the split that follows
    # deletes them, and rendering would need the live model.
    write_text_atomic(path, text)
    return []


MATRIX_NAME_ANCHORS_REPAIR = Repair(
    kind="matrix",
    name=REPAIR_NAME,
    applies=_applies,
    fn=_fn,
    description="matrix: convert `#L<n>` anchors into Python to the test names they sit in",
)

# Not registered since the matrix kind retired (spec 2026-11-04-repo-feature-settings
# R19): its last hop deletes the matrix, so no repair could run after it, and the
# split (`fr.artifacts.matrix_fragments`) applies `conversions` itself. The repair
# object stays for its own tests and as the definition of the conversion.
