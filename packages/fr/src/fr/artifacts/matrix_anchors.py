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
so a note that quotes the ref moves with it — and then regenerates the
committed reports that render it, when the repo commits them, returning those
as companions so they land in the same commit.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

from fr.artifacts.atomic import write_text_atomic
from fr.artifacts.runner import MIGRATIONS, Repair

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
    from fr.acceptance.model import AcceptanceError, parse_matrix, split_ref

    root = _root(path)
    try:
        text = path.read_text()
    except OSError:
        return {}
    if not _LINE_ANCHOR_HINT.search(text):
        return {}  # the gate asks before every command: skip the parse and git
    try:
        matrix = parse_matrix(text)
        own = resolve_identity(matrix, root)[1]
    except (AcceptanceError, OSError, ValueError):
        return {}
    out: dict[str, str] = {}
    sources: dict[str, str | None] = {}
    for row in matrix.rows:
        for ref in row.refs():
            try:
                repo, rel, frag = split_ref(ref)
            except AcceptanceError:
                continue
            line = line_of(frag)
            if repo != own or line is None or not is_python(rel) or ref in out:
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


def _report_paths(path: Path) -> list[Path]:
    from fr.acceptance.report import REPORT_SET

    root = _root(path)
    return [root / rel for rel in REPORT_SET]


def _applies(path: Path) -> bool:
    return bool(conversions(path))


def _fn(path: Path) -> Iterable[Path]:
    from fr.acceptance.model import parse_matrix
    from fr.acceptance.report import render_committed_set

    text = path.read_text()
    for old, new in conversions(path).items():
        # Whole refs only: `#L1` must not match inside `#L10` or `#L1-L5`, and
        # own repo `fr` must not match inside a sibling's `super-fr:…`.
        pattern = r"(?<![\w.-])" + re.escape(old) + r"(?![\w-])"
        text = re.sub(pattern, new.replace("\\", "\\\\"), text)
    matrix = parse_matrix(text)  # refuse to write a matrix that no longer reads
    root = _root(path)
    # Everything is rendered before a byte moves: a render that fails leaves
    # the matrix untouched, so the repair still applies and retries next run.
    reports: dict[Path, str] = {}
    if any(p.exists() for p in _report_paths(path)):
        reports = {root / rel: html for rel, html in render_committed_set(matrix, root).items()}
    write_text_atomic(path, text)
    wrote: list[Path] = []
    for target, rendered in reports.items():
        if not target.exists() or target.read_text() != rendered:
            write_text_atomic(target, rendered)
            wrote.append(target)
    return wrote


MATRIX_NAME_ANCHORS_REPAIR = Repair(
    kind="matrix",
    name=REPAIR_NAME,
    applies=_applies,
    fn=_fn,
    description="matrix: convert `#L<n>` anchors into Python to the test names they sit in",
    companions=_report_paths,
)

MIGRATIONS.register(MATRIX_NAME_ANCHORS_REPAIR)
