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
_RE_STEP = re.compile(r"^- \[([x \-])\] \*\*Step (\d+):\s*(.+?)\*\*\s*$", re.MULTILINE)
_RE_TRACKING = re.compile(r"^<!-- Tracking:\s*(https?://\S+)\s*-->", re.MULTILINE)
_RE_FILE_MENTION = re.compile(
    r"^- (?:Create|Edit|Test|Delete|Move|Rename|Modify):\s*`([^`]+)`", re.MULTILINE
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
        )


def _extract(text: str, pattern: re.Pattern[str], default: str) -> str:
    m = pattern.search(text)
    return m.group(1).strip() if m else default


def _extract_optional(text: str, pattern: re.Pattern[str]) -> str | None:
    m = pattern.search(text)
    return m.group(1).strip() if m else None


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
        files = _parse_files(section)
        tasks.append(
            Task(
                number=int(tm.group(1)),
                title=tm.group(2).strip(),
                tag=cast(_TagType, tm.group(3)) if tm.group(3) else None,
                steps=tuple(steps),
                files_mentioned=tuple(files),
            )
        )

    return tasks


def _parse_steps(text: str) -> list[Step]:
    """Parse all steps from a task section."""
    step_matches = list(_RE_STEP.finditer(text))
    steps: list[Step] = []

    for i, sm in enumerate(step_matches):
        start = sm.end()
        end = step_matches[i + 1].start() if i + 1 < len(step_matches) else len(text)
        body = text[start:end].strip()

        state_char = sm.group(1)
        state = state_char if state_char in (" ", "x", "-") else " "

        steps.append(
            Step(
                number=int(sm.group(2)),
                title=sm.group(3).strip(),
                body=body,
                state=state,  # type: ignore[arg-type]
            )
        )

    return steps


def _parse_files(text: str) -> list[str]:
    """Extract file mentions from a task section."""
    return [m.group(1) for m in _RE_FILE_MENTION.finditer(text)]
