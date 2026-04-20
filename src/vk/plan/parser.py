"""Plan parser — regex-driven, supports both flat and phased formats.

Produces a frozen Plan AST from a markdown file.  Body content between
headers is preserved as raw strings for lossless round-trip.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal, cast

from vk.plan.format import PlanFormat, detect
from vk.plan.models import Phase, Plan, Step, Task

_TagType = Literal["manual", "agentic"]

# --- Header field patterns ---

_RE_TITLE = re.compile(r"^# (.+)$", re.MULTILINE)
_RE_SPEC = re.compile(r"^\*\*Spec:\*\*\s*`([^`]+)`", re.MULTILINE)
_RE_STATUS = re.compile(r"^\*\*Status:\*\*\s*(.+)$", re.MULTILINE)
_RE_GOAL = re.compile(r"^\*\*Goal:\*\*\s*(.+)$", re.MULTILINE)

# --- Structural patterns ---

_RE_PHASE = re.compile(r"^## Phase (\d+):\s*(.+?)(?:\s+\[(agentic|manual)\])?\s*$", re.MULTILINE)
_RE_TASK = re.compile(r"^### Task (\d+):\s*(.+?)(?:\s+\[(agentic|manual)\])?\s*$", re.MULTILINE)
# Step header: the bold ``**Step N: title**`` may be followed by trailing prose
# on the same line — common in real-world plans that write
# ``**Step 1: Create \`foo\`** documenting the role.``  Group 4 captures that
# trailing text so _parse_steps can merge it into the title instead of
# silently dropping the whole step.
_RE_STEP = re.compile(
    r"^- \[([x \-])\] \*\*Step (\d+(?:\.\d+)*):\s*(.+?)\*\*[ \t]*(.*?)[ \t]*$",
    re.MULTILINE,
)
_RE_TRACKING = re.compile(r"^<!-- Tracking:\s*(https?://\S+)\s*-->", re.MULTILINE)
_RE_FILE_MENTION = re.compile(
    r"^- (Create|Edit|Test|Delete|Move|Rename|Modify):\s*`([^`]+)`", re.MULTILINE
)
# Lines the plan header already captures as structured fields — everything
# else in the header block is retained as ``Plan.preamble``.
_RE_HEADER_STRUCTURED_LINE = re.compile(
    r"^(# .+|\*\*Spec:\*\*.+|\*\*Status:\*\*.+|\*\*Goal:\*\*.+)$",
    re.MULTILINE,
)


def parse_plan(path: Path) -> Plan:
    """Parse a plan markdown file into a frozen Plan AST.

    Raises FileNotFoundError if path does not exist.
    Raises ValueError if the file is not a valid vk plan.
    """
    text = path.read_text(encoding="utf-8")
    fmt = detect(text)

    title = _extract(text, _RE_TITLE, "Untitled Plan")
    spec = _extract_optional(text, _RE_SPEC)
    status = _extract(text, _RE_STATUS, "Not Started")
    goal = _extract(text, _RE_GOAL, "")
    preamble = _extract_preamble(text)

    if fmt is PlanFormat.PHASED:
        phases = _parse_phases(text)
        return Plan(
            title=title,
            spec=spec,
            status=status,
            goal=goal,
            format=fmt,
            phases=tuple(phases),
            tasks=(),
            preamble=preamble,
        )
    else:
        tasks = _parse_tasks(text)
        return Plan(
            title=title,
            spec=spec,
            status=status,
            goal=goal,
            format=fmt,
            phases=(),
            tasks=tuple(tasks),
            preamble=preamble,
        )


def _extract(text: str, pattern: re.Pattern[str], default: str) -> str:
    m = pattern.search(text)
    return m.group(1).strip() if m else default


def _extract_optional(text: str, pattern: re.Pattern[str]) -> str | None:
    m = pattern.search(text)
    return m.group(1).strip() if m else None


def _extract_preamble(text: str) -> str:
    """Capture header content that isn't one of title/spec/status/goal.

    Everything between the first line and the first ``---`` divider is
    considered the header block.  The recognized structured fields
    (``# Title``, ``**Spec:**``, ``**Status:**``, ``**Goal:**``) are filtered
    out; the remainder is returned verbatim with leading/trailing blank lines
    trimmed.
    """
    divider_idx = text.find("\n---")
    header_block = text[:divider_idx] if divider_idx != -1 else text
    remainder = _RE_HEADER_STRUCTURED_LINE.sub("", header_block)
    # Collapse runs of 3+ blank lines that structured-field removal created.
    remainder = re.sub(r"\n{3,}", "\n\n", remainder)
    return remainder.strip("\n")


def _parse_phases(text: str) -> list[Phase]:
    """Parse all phases from phased-format markdown."""
    phase_matches = list(_RE_PHASE.finditer(text))
    phases: list[Phase] = []

    for i, pm in enumerate(phase_matches):
        start = pm.end()
        end = phase_matches[i + 1].start() if i + 1 < len(phase_matches) else len(text)
        section = text[start:end]

        tracking_match = _RE_TRACKING.search(section)
        tracking_url = tracking_match.group(1) if tracking_match else None

        tasks = _parse_tasks(section)
        phases.append(
            Phase(
                number=int(pm.group(1)),
                title=pm.group(2).strip(),
                tag=cast(_TagType, pm.group(3) or "agentic"),
                tasks=tuple(tasks),
                tracking_url=tracking_url,
            )
        )

    return phases


def _parse_tasks(text: str) -> list[Task]:
    """Parse all tasks from a section of markdown."""
    task_matches = list(_RE_TASK.finditer(text))
    tasks: list[Task] = []

    for i, tm in enumerate(task_matches):
        start = tm.end()
        end = task_matches[i + 1].start() if i + 1 < len(task_matches) else len(text)
        section = text[start:end]

        # Don't cross into the next phase
        next_phase = _RE_PHASE.search(section)
        if next_phase:
            section = section[: next_phase.start()]

        steps = _parse_steps(section)
        file_mentions = _parse_files(section)
        tasks.append(
            Task(
                number=int(tm.group(1)),
                title=tm.group(2).strip(),
                tag=cast(_TagType, tm.group(3)) if tm.group(3) else None,
                steps=tuple(steps),
                files_mentioned=tuple(path for _verb, path in file_mentions),
                file_mention_verbs=tuple(verb for verb, _path in file_mentions),
            )
        )

    return tasks


def _parse_steps(text: str) -> list[Step]:
    """Parse all steps from a task section.

    The step regex also captures any trailing prose on the same line as the
    bold ``**Step N: title**`` header.  When present, the trailing text is
    merged into the step title — otherwise every loose-format step would be
    silently dropped (see ``tests/unit/test_plan_loose_format.py``).
    """
    step_matches = list(_RE_STEP.finditer(text))
    steps: list[Step] = []

    for i, sm in enumerate(step_matches):
        start = sm.end()
        end = step_matches[i + 1].start() if i + 1 < len(step_matches) else len(text)
        body = text[start:end].strip()

        state_char = sm.group(1)
        state = state_char if state_char in (" ", "x", "-") else " "

        bold_title = sm.group(3).strip()
        trailing = sm.group(4).strip()
        title = f"{bold_title} {trailing}".strip() if trailing else bold_title

        raw_label = sm.group(2)
        # For dotted labels (``"0.1"``), the leading integer is what downstream
        # callers actually use for ordering; the full token is kept in ``label``.
        number = int(raw_label.split(".", 1)[0])
        label = raw_label if "." in raw_label else None

        steps.append(
            Step(
                number=number,
                title=title,
                body=body,
                state=state,  # type: ignore[arg-type]
                label=label,
            )
        )

    return steps


def _parse_files(text: str) -> list[tuple[str, str]]:
    r"""Extract ``(verb, path)`` pairs from the ``**Files:**`` block.

    Preserving the verb (Create/Edit/Test/Delete/Move/Rename/Modify) is what
    keeps ``- Test: \`cmd\``` round-tripping instead of collapsing to a
    fake ``- Create: \`cmd\``` on write.
    """
    return [(m.group(1), m.group(2)) for m in _RE_FILE_MENTION.finditer(text)]
