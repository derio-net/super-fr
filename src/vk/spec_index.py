"""Spec index — read/create/update the Implementation Plans markdown table.

Each spec file may contain a ``## Implementation Plans`` section with a
markdown table tracking sub-project plans, their statuses, and dependencies.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class IndexEntry:
    """A row in the Implementation Plans table."""

    plan: str
    repo: str
    file: str
    status: str
    depends_on: str


_RE_INDEX_HEADER = re.compile(r"^## Implementation Plans\s*$", re.MULTILINE)
_RE_TABLE_ROW = re.compile(
    r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|",
    re.MULTILINE,
)


def read_index(spec_path: Path) -> list[IndexEntry]:
    """Read implementation plan entries from a spec file.

    Returns an empty list if the file doesn't exist or has no index section.
    """
    if not spec_path.exists():
        return []

    text = spec_path.read_text(encoding="utf-8")
    header_match = _RE_INDEX_HEADER.search(text)
    if not header_match:
        return []

    section = text[header_match.end() :]

    entries: list[IndexEntry] = []
    for m in _RE_TABLE_ROW.finditer(section):
        plan, repo, file_col, status, depends = (
            m.group(1).strip(),
            m.group(2).strip(),
            m.group(3).strip(),
            m.group(4).strip(),
            m.group(5).strip(),
        )
        if plan in ("Plan", "---", "------") or plan.startswith("-"):
            continue
        file_col = file_col.strip("`")
        entries.append(
            IndexEntry(plan=plan, repo=repo, file=file_col, status=status, depends_on=depends)
        )

    return entries


def upsert_entry(spec_path: Path, entry: IndexEntry) -> None:
    """Add or update an entry in the spec's Implementation Plans table.

    Creates the section and table if they don't exist.
    Updates the row if a matching plan name already exists.
    """
    text = spec_path.read_text(encoding="utf-8")
    header_match = _RE_INDEX_HEADER.search(text)

    if not header_match:
        table = _build_table([entry])
        if not text.endswith("\n"):
            text += "\n"
        text += f"\n## Implementation Plans\n\n{table}\n"
        spec_path.write_text(text, encoding="utf-8")
        return

    section_start = header_match.end()

    next_section = re.search(r"^## ", text[section_start:], re.MULTILINE)
    section_end = section_start + next_section.start() if next_section else len(text)

    existing = read_index(spec_path)

    found = False
    for i, e in enumerate(existing):
        if e.plan == entry.plan:
            existing[i] = entry
            found = True
            break
    if not found:
        existing.append(entry)

    table = _build_table(existing)
    new_text = text[:section_start] + f"\n{table}\n" + text[section_end:]
    spec_path.write_text(new_text, encoding="utf-8")


def _build_table(entries: list[IndexEntry]) -> str:
    """Build a markdown table from index entries."""
    lines = [
        "| Plan | Repo | File | Status | Depends on |",
        "|------|------|------|--------|------------|",
    ]
    for e in entries:
        lines.append(f"| {e.plan} | {e.repo} | `{e.file}` | {e.status} | {e.depends_on} |")
    return "\n".join(lines)
