"""The `spec` kind's Test Plan heading repair (super-fr#1315).

`## Test Plan` is a keyword heading: `fr.spec.find_test_plan_heading` reads
exactly that line, and every reader now refuses a near-miss rather than reading
it as "no Test Plan". A live spec written before the contract was stated often
numbers the heading like its other sections (`## 6. Test Plan (post-merge,
operator-driven)`). This repair renames such a heading to `## Test Plan` and
keeps a trailing parenthetical as the section's first line, so nothing the
writer said is lost.

A `Repair`, not a `SchemaMigration`: the spec's shape has not moved — fr always
read exactly `## Test Plan`; only the constraint is now enforced. The stamp is
untouched.

Every heading `find_test_plan_heading` refuses is repaired (`#`, `##` or `###`;
a `####` is not a candidate). A `#` or `###` heading is also moved to level two,
so its neighbouring headings move with it (spec 2026-11-08-sweep-fixes R9):

- promoting `###`: every heading from the Test Plan to the next `#` or `##`
  heading moves up one level, so a `### Coverage` after it stays a sibling;
- demoting `#`: every heading from the Test Plan to the next `#` heading, or to
  the next `##` heading fr reads by keyword (`## Verification`,
  `## Implementation Plans`, `## Requirements`, which stays and ends the
  section), moves down one level; a `######` stays at level six.

Code fences are respected. Archived specs are never located, so never rewritten.
"""

from __future__ import annotations

import re
from pathlib import Path

from fr.artifacts.atomic import write_text_atomic
from fr.artifacts.runner import MIGRATIONS, Repair
from fr.spec import FENCE_RE, TEST_PLAN_HEADING, TestPlanHeading, find_test_plan_heading

REPAIR_NAME = "test-plan-heading"

_SUFFIX_RE = re.compile(r"\s*(\([^()]*\))$")
_HEADING_RE = re.compile(r"^(#{1,6})(?=\s+\S)")
_KEYWORD_RE = re.compile(r"^##\s+(Verification|Implementation Plans|Requirements)\s*$")


def _shift_region(lines: list[str], start: int, level: int) -> None:
    """Move the headings after line *start* (the Test Plan heading, at *level*) so the
    heading itself can sit at level two. Edits *lines* in place, fences tracked."""
    delta = 2 - level
    fenced = False
    for i in range(start + 1, len(lines)):
        line = lines[i]
        if FENCE_RE.match(line):
            fenced = not fenced
            continue
        if fenced:
            continue
        m = _HEADING_RE.match(line)
        if m is None:
            continue
        n = len(m.group(1))
        if delta > 0:  # demoting: stop at a `#` or a keyword `##`
            if n == 1 or _KEYWORD_RE.match(line.rstrip("\r\n")):
                return
            new = min(n + delta, 6)
        else:  # promoting: stop at a `#` or `##`
            if n <= 2:
                return
            new = n + delta
        lines[i] = "#" * new + line[n:]


def _renamable(text: str) -> TestPlanHeading | None:
    heading = find_test_plan_heading(text)
    if heading is None or heading.exact:
        return None
    return heading


def _applies(path: Path) -> bool:
    return _renamable(path.read_text()) is not None


def _fn(path: Path) -> None:
    text = path.read_bytes().decode("utf-8")  # no newline translation: CRLF stays CRLF
    heading = _renamable(text)
    if heading is None:
        return
    lines = text.splitlines(keepends=True)
    level = len(_HEADING_RE.match(heading.text).group(1))  # type: ignore[union-attr]
    if level != 2:
        _shift_region(lines, heading.line, level)
    raw = lines[heading.line]
    ending = raw[len(raw.rstrip("\r\n")) :] or "\n"
    new = [TEST_PLAN_HEADING + ending]
    suffix = _SUFFIX_RE.search(heading.text)
    if suffix is not None:
        new += [ending, f"_{suffix.group(1)}_" + ending]
    lines[heading.line : heading.line + 1] = new
    write_text_atomic(path, "".join(lines))


SPEC_TEST_PLAN_HEADING_REPAIR = Repair(
    kind="spec",
    name=REPAIR_NAME,
    applies=_applies,
    fn=_fn,
    description=(
        "spec: rename a near-miss Test Plan heading (`## 6. Test Plan (…)`, at level "
        f'one to three) to "{TEST_PLAN_HEADING}"; for a `#` or `###` heading the '
        "neighbouring headings move one level with it"
    ),
)

MIGRATIONS.register(SPEC_TEST_PLAN_HEADING_REPAIR)
