"""The spec's "Implementation Plans" table: validate it, add the section, append a row
(moved from `fr.plan_ops`, spec 2026-11-27-plan-ops-split R5).

Called by `fr.plan_ops.create`, `fr.plan_rework.rework_create` and `fr.migrate`.
"""

from __future__ import annotations

import re
from pathlib import Path

from fr.artifacts.atomic import write_text_atomic
from fr.plan_errors import PlanEditError

_SPEC_TABLE_HEADER_RE = re.compile(r"^## Implementation Plans\s*$", re.MULTILINE)

# `_append_spec_row` writes `| name | \`repo\` | \`file\` | depends_on |` into
# columns 2-4 unconditionally — it never reads the header text. A table whose
# header labels those columns differently (e.g. a hand-authored spec with
# `Phases | Status | Created`) still accepts the append silently, producing a
# table that lies about what each column holds. Both entry points below check
# the header names against this contract before writing.
_CANONICAL_HEADER_LINE = "| Plan | Repo | File | Depends on |"
_CANONICAL_HEADER_CELLS = tuple(
    c.strip().lower() for c in _CANONICAL_HEADER_LINE.strip("|").split("|")
)
_CANONICAL_HEADER_SEPARATOR = (
    "|" + "|".join("-" * (len(c) + 2) for c in _CANONICAL_HEADER_CELLS) + "|"
)


def _header_hint() -> str:
    """The one phrase every table error uses to name the header it wants."""
    return f"expected '{_CANONICAL_HEADER_LINE}' followed by its separator row"


def _first_table_line(text: str, m: re.Match[str]) -> str | None:
    """First pipe-delimited line after the heading match, or None."""
    after = text[m.end() :]
    for line in after.splitlines():
        stripped = line.strip()
        if stripped.startswith("|"):
            return stripped
    return None


def _check_table_header(spec_path: Path, text: str, m: re.Match[str]) -> None:
    header_line = _first_table_line(text, m)
    if header_line is None:
        raise PlanEditError(
            f"{spec_path}: '## Implementation Plans' has no table to append to; {_header_hint()}."
        )
    cells = tuple(c.strip().lower() for c in header_line.strip("|").split("|"))
    if cells != _CANONICAL_HEADER_CELLS:
        raise PlanEditError(
            f"{spec_path}: '## Implementation Plans' table header is {header_line!r}, "
            f"{_header_hint()}. fr plan create appends rows "
            f"assuming those exact column semantics — a differently-labeled header would "
            f"silently mislabel the row it writes. Fix the header before scaffolding a plan."
        )


def _ensure_section_text(text: str) -> str:
    """Return `text` with the canonical `## Implementation Plans` header appended.

    Pure. Blank-line separated from any prose; the caller must only use it when
    the section is absent. `fr.migrate._ensure_spec_plan_row` shares it.
    """
    sep = "" if text.endswith("\n\n") else ("\n" if text.endswith("\n") else "\n\n")
    return (
        f"{text}{sep}## Implementation Plans\n\n"
        f"{_CANONICAL_HEADER_LINE}\n{_CANONICAL_HEADER_SEPARATOR}\n"
    )


def _validate_spec_section(spec_path: Path) -> None:
    """Pre-flight: confirm an existing Implementation Plans table is appendable.

    Read-only. A missing section is accepted — `create` writes it right before
    appending the row. A present-but-malformed table raises the same errors
    `_append_spec_row` would, BEFORE any folder is created (#133).
    """
    text = spec_path.read_text()
    m = _SPEC_TABLE_HEADER_RE.search(text)
    if not m:
        return
    _check_table_header(spec_path, text, m)


def _append_spec_row(
    spec_path: Path,
    *,
    plan_name: str,
    repo: str,
    file: str,
    depends_on: str,
) -> None:
    """Append a row to the spec's `## Implementation Plans` table.

    Idempotent: if a row with `file == file` already exists, no-op.
    """
    text = spec_path.read_text()
    m = _SPEC_TABLE_HEADER_RE.search(text)
    if not m:
        raise PlanEditError(
            f"{spec_path}: no '## Implementation Plans' section found. "
            f"Add the section with a table header; {_header_hint()}."
        )
    _check_table_header(spec_path, text, m)

    # Find end of the table (last consecutive "|" line after the header).
    after = text[m.end() :]
    lines = after.splitlines(keepends=True)
    abs_offset = m.end()
    saw_pipe = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|"):
            saw_pipe = True
            abs_offset += len(line)
        elif saw_pipe and stripped == "":
            break
        else:
            abs_offset += len(line)
    if not saw_pipe:
        raise PlanEditError(
            f"{spec_path}: '## Implementation Plans' has no table to append to; {_header_hint()}."
        )

    # Idempotence check is scoped to the TABLE region only. Scanning the whole
    # spec (the pre-2026-07-24 behavior) let any backticked slug mention in the
    # prose — e.g. a `**Slug:** `<slug>`` header, exactly what fr-goal writes —
    # match, so the row was silently never appended while `create` reported
    # success (and the empty table then broke `fr archive`'s spec-sweep).
    table_region = text[m.end() : abs_offset]
    if f"`{file}`" in table_region or f"| {file} |" in table_region:
        return  # already present

    new_row = f"| {plan_name} | `{repo}` | `{file}` | {depends_on} |\n"
    new_text = text[:abs_offset] + new_row + text[abs_offset:]
    write_text_atomic(spec_path, new_text)
