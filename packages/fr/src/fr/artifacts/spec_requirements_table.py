"""The `spec` kind's 1 -> 2 migration: a live spec's `## Requirements` list
becomes the two-column `| ID | Requirement |` table (spec
`2026-11-26-spec-requirements-table-design.md` R4-R6).

The `R<n>.` list renders as one run-on paragraph in every Markdown previewer;
the table renders as rows. The rewrite:

- takes the list's layout from `fr.requirements.list_layout`, the walk the
  reader itself uses, so the two cannot disagree on which lines belong to a
  requirement (continuation lines are joined with single spaces);
- keeps every line outside the requirement and continuation lines byte for
  byte, adds one blank line before and after the table where none is, writes
  the table's lines in the file's own line ending, and escapes `|` as `\\|`;
- builds the new text in memory, round-trips it (the requirements parsed from
  the new text equal those of the old, id for id and text for text), and only
  then writes once, through `write_text_atomic`. The runner writes the stamp.

A spec it cannot convert — prose between requirements, a `RequirementsError`
(an id-like line such as `R9a.`), or a failed round trip — raises before a
byte moves, so the file stays byte-identical and unstamped, and the error
names the file, the line, the cause and the hand fix. Every other spec still
migrates.

A section that is already a two-column table, a pre-5.0 three-column table, a
section with no requirement line and a spec with no section are left alone:
the runner only stamps them. That also covers the crash window between this
`fn` writing the body and the runner writing the stamp: on the next run the
body reads as a table, so only the stamp is written.

Archived specs are never located: the kind's locator is
`docs/superpowers/specs/*.md` only.
"""

from __future__ import annotations

from pathlib import Path

from fr.artifacts.atomic import write_text_atomic
from fr.artifacts.runner import MIGRATIONS, SchemaMigration
from fr.artifacts.text import read_utf8
from fr.requirements import RequirementsError, list_layout, parse_requirements

_HEADER = "| ID | Requirement |"
_DELIMITER = "|----|-------------|"


class SpecRewriteRefusedError(ValueError):
    """The rewrite cannot convert this spec; its message is the R5 report."""


def _refuse(path: Path, line: int, cause: str, fix: str) -> SpecRewriteRefusedError:
    return SpecRewriteRefusedError(f"{path}:{line}: {cause} — {fix}")


def _row(rid: str, text: str) -> str:
    """One table row, a literal `|` escaped."""
    return f"| {rid} | {text.replace('|', chr(92) + '|')} |"


def _ending(line: str) -> str:
    return line[len(line.rstrip("\r\n")) :] or "\n"


def _is_blank(line: str) -> bool:
    return not line.strip()


def build(path: Path, text: str) -> str | None:
    """The rewritten text, `None` when the spec is only stamped. Raises
    `SpecRewriteRefusedError` with the R5 message; writes nothing."""
    try:
        layout = list_layout(text)
        if layout is None or not layout.items:
            return None
        old_reqs = parse_requirements(text)
    except RequirementsError as e:
        message = str(e)
        raise _refuse(
            path,
            _line_of(message),
            message.partition(": ")[2] or message,
            "fix the requirement id in the spec, then re-run fr migrate artifacts --yes",
        ) from e
    if layout.prose:
        raise _refuse(
            path,
            layout.prose[0],
            "prose between requirements",
            "move the prose out of the requirements list, then re-run fr migrate artifacts --yes",
        )
    lines = text.splitlines(keepends=True)
    first = layout.base + layout.start
    last = layout.base + layout.end
    nl = _ending(lines[first])
    before, after = lines[:first], lines[last + 1 :]  # the heading precedes `first`
    table = [_HEADER + nl, _DELIMITER + nl, *(_row(i.id, i.text) + nl for i in layout.items)]
    if before and not _is_blank(before[-1]):
        table.insert(0, nl)
    if after and not _is_blank(after[0]):
        table.append(nl)
    new = "".join([*before, *table, *after])
    try:
        new_reqs = parse_requirements(new)
    except RequirementsError as e:
        raise _refuse(path, layout.items[0].line_no, f"round trip failed: {e}", _JOIN_FIX) from e
    if new_reqs != old_reqs:
        bad = next(
            (
                i.line_no
                for i, a, b in zip(layout.items, old_reqs.items, new_reqs.items, strict=False)
                if a != b
            ),
            layout.items[0].line_no,
        )
        raise _refuse(
            path, bad, "round trip failed: the table reads to other requirements", _JOIN_FIX
        )
    return new


_JOIN_FIX = (
    "join the requirement's lines into one line in the spec, then re-run fr migrate artifacts --yes"
)


def _line_of(message: str) -> int:
    """The line a `RequirementsError` names (`line N: ...`), else 0."""
    head = message.partition(":")[0]
    return int(head[5:]) if head.startswith("line ") and head[5:].isdigit() else 0


def _rewrite(path: Path) -> None:
    text = read_utf8(path)  # no newline translation: CRLF stays CRLF
    new = build(path, text)
    if new is not None and new != text:
        write_text_atomic(path, new)


SPEC_REQUIREMENTS_TABLE = SchemaMigration(
    kind="spec",
    from_version=1,
    to_version=2,
    fn=_rewrite,
    description="spec: Requirements list -> | ID | Requirement | table",
)

MIGRATIONS.register(SPEC_REQUIREMENTS_TABLE)
