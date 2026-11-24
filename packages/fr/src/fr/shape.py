"""Design shapes: the picture of a change a spec and a PR carry.

Spec 2026-11-24-show-me-visuals R6: a **shape block** is Markdown whose content
holds at least one fenced code block, or exactly one non-blank line
``none — <reason>`` (a hyphen is accepted for the dash) with a non-empty
reason. This module owns that grammar — every check calls
:func:`shape_block_problem` — plus the reader of a spec's ``## Design shape``
section (R7) and the locator of a run's shape file (R9), which sits beside the
run's cursor exactly as the durable PR body does.
"""

from __future__ import annotations

import re
from pathlib import Path

from fr.spec import FENCE_RE

SHAPE_FILE_SUFFIX = ".shape.md"
"""``docs/superpowers/runs/<run-id>.shape.md``: the run's shape file (R9)."""

DESIGN_SHAPE_HEADING = "## Design shape"

TWO_FORMS = (
    "A shape block is either Markdown holding at least one fenced code block "
    "(``` or ~~~, e.g. a tree, a `diff` or `mermaid`), or exactly one line "
    "`none — <reason>` with a non-empty reason."
)
"""Both valid forms in one sentence, named by every refusal (R8, R11)."""

_NONE_LINE = re.compile(r"^none\s*[—-]\s*(.*)$")
_H2 = re.compile(r"^##\s")


def _fence_states(lines: list[str]) -> tuple[list[tuple[str, bool, bool]], bool]:
    """``(line, in_fence, is_fence_line)`` per line, and whether the text ends
    inside a fence. A fence closes only on a line of the same character, at
    least as long as the opener, with no info string (CommonMark); the opener's
    run is read beyond ``FENCE_RE``'s three characters."""
    fence: str | None = None
    out: list[tuple[str, bool, bool]] = []
    for line in lines:
        if FENCE_RE.match(line):
            stripped = line.strip()
            char = stripped[0]
            run = stripped[: len(stripped) - len(stripped.lstrip(char))]
            if fence is None:
                fence = run
                out.append((line, True, True))
                continue
            if char == fence[0] and len(run) >= len(fence) and not stripped[len(run) :].strip():
                fence = None
                out.append((line, True, True))
                continue
        out.append((line, fence is not None, False))
    return out, fence is not None


def shape_block_problem(text: str) -> str | None:
    """``None`` when *text* is a shape block (R6), else a one-line reason."""
    states, unclosed = _fence_states(text.splitlines())
    if unclosed:
        return "a fenced code block is never closed"
    if any(is_fence for _line, _in, is_fence in states):
        return None  # every fence line opened or closed a block, and none is left open
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return "it is empty"
    none = _NONE_LINE.match(lines[0])
    if none is None:
        return "it holds no fenced code block and is not a `none — <reason>` line"
    if not none.group(1).strip():
        return "its `none —` line gives no reason"
    if len(lines) > 1:
        return "a `none — <reason>` shape must be its only non-blank line"
    return None


def is_shape_block(text: str) -> bool:
    """True when *text* is a shape block (R6)."""
    return shape_block_problem(text) is None


def design_shape_section(spec_text: str) -> str | None:
    """The body under the spec's ``## Design shape`` heading, up to the next
    ``## `` heading outside a fence; ``None`` when the heading is absent (R7).
    A heading inside a fenced block neither opens nor ends the section."""
    body: list[str] | None = None
    for line, in_fence, _is_fence in _fence_states(spec_text.splitlines())[0]:
        if not in_fence and _H2.match(line):
            if body is not None:
                break
            if line.rstrip() == DESIGN_SHAPE_HEADING:
                body = []
            continue
        if body is not None:
            body.append(line)
    return None if body is None else "\n".join(body)


def shape_path(repo_root: Path, run_id: str) -> Path:
    """The run's shape file, beside its cursor and its durable PR body (R9)."""
    from fr.run.model import run_path

    return run_path(repo_root, run_id).with_name(f"{run_id}{SHAPE_FILE_SUFFIX}")
