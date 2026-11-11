"""Text and JSON output for `fr docs` (spec 2026-11-11-docs-currency R3, R7)."""

from __future__ import annotations

import json
from collections.abc import Sequence

from fr.docs.check import Finding
from fr.docs.model import Page, PageError

_FIXES = (
    "  fix it one of two ways:\n"
    "    - edit the page so it describes the change; or\n"
    "    - if the page is still true, update its `reviewed` stamp (`reviewed: <date> <note>`)"
)


def findings_text(findings: Sequence[Finding]) -> str:
    """One block per finding; a stale page names the paths and both fixes."""
    blocks: list[str] = []
    for f in findings:
        if f.kind == "stale":
            lines = [f"stale: {f.page} covers paths this change touched:"]
            lines += [f"    {p}" for p in f.paths]
            lines.append(_FIXES)
            blocks.append("\n".join(lines))
        elif f.kind == "uncovered":
            blocks.append(f"uncovered: {f.message}")
        else:
            blocks.append(f"{f.kind}: {f.message}")
    return "\n".join(blocks)


def status_text(pages: Sequence[Page], errors: Sequence[PageError]) -> str:
    lines: list[str] = []
    for p in pages:
        lines.append(p.path)
        lines.append(f"  covers:   {', '.join(p.covers) if p.covers else '(none)'}")
        lines.append(f"  reviewed: {p.reviewed}")
    lines += [f"{e.path}: {e.message}" for e in errors]
    return "\n".join(lines) if lines else "no pages"


def status_json(pages: Sequence[Page], errors: Sequence[PageError]) -> str:
    data = {
        "pages": [
            {"path": p.path, "covers": list(p.covers), "reviewed": p.reviewed} for p in pages
        ],
        "errors": [{"path": e.path, "message": e.message} for e in errors],
    }
    return json.dumps(data, indent=2)
