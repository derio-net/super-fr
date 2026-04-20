"""Plan AST — frozen dataclasses for the plan document model.

Supports both flat (Task > Step) and phased (Phase > Task > Step) formats.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from vk.plan.format import PlanFormat

CheckboxState = Literal[" ", "x", "-"]  # unchecked, done, skipped


@dataclass(frozen=True)
class Step:
    """A single checkbox step within a task.

    ``number`` is the integer portion (used for ordering/arithmetic).
    ``label`` is the raw token as written — including dotted forms like
    ``"0.1"`` or ``"1.10"`` — which some plans use.  When ``label`` is set,
    the writer emits it verbatim; otherwise it falls back to ``number``.
    """

    number: int
    title: str
    body: str
    state: CheckboxState
    label: str | None = None


@dataclass(frozen=True)
class Task:
    """A task containing ordered steps.

    In flat format, tasks are top-level and carry ``[manual]``/``[agentic]`` tags.
    In phased format, tasks are nested under phases and inherit the phase tag.

    ``file_mention_verbs`` is aligned 1:1 with ``files_mentioned`` when
    populated (e.g. by the parser), so that ``- Edit: path`` and ``- Test: path``
    round-trip with their verb instead of collapsing to ``Create:``.  Empty
    tuple = treat every entry as ``Create``.
    """

    number: int
    title: str
    tag: Literal["manual", "agentic"] | None
    steps: tuple[Step, ...]
    files_mentioned: tuple[str, ...]
    file_mention_verbs: tuple[str, ...] = ()


@dataclass(frozen=True)
class Phase:
    """A phase containing ordered tasks.  Only used in phased format."""

    number: int
    title: str
    tag: Literal["manual", "agentic"]
    tasks: tuple[Task, ...]
    tracking_url: str | None


@dataclass(frozen=True)
class Plan:
    """Root AST node for a parsed plan file.

    ``preamble`` is the block of free-form content between the recognized
    header fields (title/spec/status/goal) and the first ``---`` divider —
    typically ``**Architecture:**``, ``**Tech Stack:**``, blockquotes, or
    operator notes.  It is preserved verbatim so ``vk plan convert`` doesn't
    silently delete author-written context on round-trip.
    """

    title: str
    spec: str | None
    status: str
    goal: str
    format: PlanFormat
    phases: tuple[Phase, ...]  # populated in phased format
    tasks: tuple[Task, ...]  # populated in flat format
    preamble: str = ""

    @property
    def all_tasks(self) -> tuple[Task, ...]:
        """Return all tasks regardless of format.

        Flat: returns ``self.tasks`` directly.
        Phased: flattens tasks from all phases in order.
        """
        if self.format is PlanFormat.FLAT:
            return self.tasks
        return tuple(t for p in self.phases for t in p.tasks)
