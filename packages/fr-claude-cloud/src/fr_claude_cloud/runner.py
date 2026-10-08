"""The `claude-cloud` runner (stub: phase 5 task 1)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from fr_dispatch.protocols import CloseOutcome
from fr_dispatch.work_item import WorkItem


class ClaudeCloudRunner:
    name = "claude-cloud"
    capabilities: frozenset[str] = frozenset({"git", "tests", "scm", "network"})
    units: frozenset[str] = frozenset({"run"})

    def __init__(self) -> None:
        self._requests: list[dict[str, Any]] = []
        self._state: Path | None = None

    @classmethod
    def from_env(cls) -> ClaudeCloudRunner:
        return cls()

    def preflight(self, items: Sequence[WorkItem]) -> str | None:
        return None

    def refresh(self) -> None:
        return None

    def slot_budget(self) -> int:
        return 1

    def existing_dispatches(self, items: Sequence[WorkItem]) -> set[str]:
        return set()

    def can_dispatch(self, item: WorkItem) -> bool:
        return item.unit in self.units

    def dispatch(self, item: WorkItem) -> str:
        rid = f"{item.id}:dispatch:1"
        self._requests.append({"id": rid, "kind": "dispatch", "item": item.id, **item.payload})
        return f"pending:{rid}"

    def close(self, item: WorkItem) -> CloseOutcome:
        return "absent"

    def open_mailbox(self, state_dir: Any, statuses: Any) -> None:
        self._state = Path(state_dir)

    def outbox(self) -> list[dict[str, Any]]:
        return list(self._requests)

    def record_results(self, results: list[dict[str, Any]]) -> list[str]:
        return []
