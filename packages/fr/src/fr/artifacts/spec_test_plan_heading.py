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

Only a `##` near-miss is renamed. A `#` or `###` one sits at a different level,
and promoting it would change which sections it swallows; `fr validate
artifacts` reports it for a human to fix. Archived specs are never located, so
never rewritten.
"""

from __future__ import annotations

import re
from pathlib import Path

from fr.artifacts.atomic import write_text_atomic
from fr.artifacts.runner import MIGRATIONS, Repair
from fr.spec import TEST_PLAN_HEADING, TestPlanHeading, find_test_plan_heading

REPAIR_NAME = "test-plan-heading"

_SUFFIX_RE = re.compile(r"\s*(\([^()]*\))$")


def _renamable(text: str) -> TestPlanHeading | None:
    heading = find_test_plan_heading(text)
    if heading is None or heading.exact or not heading.text.startswith("## "):
        return None
    return heading


def _applies(path: Path) -> bool:
    return _renamable(path.read_text()) is not None


def _fn(path: Path) -> None:
    text = path.read_text()
    heading = _renamable(text)
    if heading is None:
        return
    lines = text.splitlines(keepends=True)
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
        "spec: rename a near-miss Test Plan heading (`## 6. Test Plan (…)`) to "
        f'"{TEST_PLAN_HEADING}"'
    ),
)

MIGRATIONS.register(SPEC_TEST_PLAN_HEADING_REPAIR)
