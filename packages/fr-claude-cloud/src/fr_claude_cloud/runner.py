"""The `claude-cloud` runner: the runner protocol as a mailbox (cloud-triage R14, R15, §F).

Every method that would act on a session writes a request instead and returns a
pending result, because only the driver session's agent can call the session tools:

- `dispatch` returns `pending:<request id>`; the batch's dispatch event carries it, so
  the batch is in flight, and `existing_dispatches` holds the item while the request is
  pending, so it is never dispatched twice;
- `close` returns `busy` while its archive request (or the item's dispatch) is pending;
- `message` writes a message request carrying its own id (the agent skips one it has
  already sent); a refused one is asked again on the next pass.

Beside `Runner` it implements `fr.triage.driver.Mailbox` (`open_mailbox`, `outbox`,
`record_results`), `SessionCloser`, `SessionInspector`, `SessionMessenger` and
`SessionNotes`. It implements neither `SessionRestarter` nor `SessionAdopter`: re-homing
is its restart (R17), and it ignores the herdr-only `group` a driver's item carries.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from fr_dispatch.protocols import CloseOutcome, SessionStatus
from fr_dispatch.work_item import WorkItem

from fr_claude_cloud.mailbox import Mailbox

HARNESSES = frozenset({"claude"})  # a cloud session runs Claude Code, nothing else


class ClaudeCloudRunner:
    """A run-unit runner whose sessions the cloud driver's agent creates and archives."""

    name = "claude-cloud"
    capabilities: frozenset[str] = frozenset({"git", "tests", "scm", "network"})
    units: frozenset[str] = frozenset({"run"})

    def __init__(self, state_dir: Path | None = None) -> None:
        self._box = Mailbox(state_dir)

    @classmethod
    def from_env(cls) -> ClaudeCloudRunner:
        """Built from nothing: the driver opens it on the scope's state directory."""
        return cls()

    # ------------------------------------------------- fr.triage.driver.Mailbox

    def open_mailbox(self, state_dir: Any, statuses: Any) -> None:
        """Load the scope's pending requests and recorded sessions from *state_dir*, and
        take in the sessions the agent listed or read (*statuses*, the `--statuses` JSON)."""
        self._box = Mailbox(Path(state_dir), statuses)

    def outbox(self) -> list[dict[str, Any]]:
        """Every pending request, plus a `status` request per recorded session."""
        return self._box.outbox()

    def record_results(self, results: list[dict[str, Any]]) -> list[str]:
        """Apply the agent's results; the ids applied (one no request names is not)."""
        return self._box.record(results)

    # ------------------------------------------------------------------ Runner

    def preflight(self, items: Sequence[WorkItem]) -> str | None:
        return None  # no backend to reach: the agent executes the requests

    def refresh(self) -> None:
        return None

    def slot_budget(self) -> int:
        # The wave driver's in-flight cap decides; this exists for `tick` compatibility.
        return 1

    def existing_dispatches(self, items: Sequence[WorkItem]) -> set[str]:
        """Items with a pending dispatch, a recorded session (`sessions.yaml`), or a
        session the agent last listed under the item's tag."""
        return self._box.held(i.id for i in items)

    def can_dispatch(self, item: WorkItem) -> bool:
        return item.unit in self.units and item.payload.get("harness", "claude") in HARNESSES

    def dispatch(self, item: WorkItem) -> str:
        pending = self._box.pending(item.id, "dispatch")
        if pending is None:
            payload = item.payload
            pending = self._box.add(
                item.id,
                "dispatch",
                tag=item.id,
                repo=item.repo,
                branch=payload.get("branch"),
                model=payload.get("model"),
                prompt=payload.get("brief"),
            )
        return f"pending:{pending['id']}"

    # ------------------------------------------------------- session protocols

    def close(self, item: WorkItem) -> CloseOutcome:
        if self._box.pending(item.id, "close") is not None:
            return "busy"
        session = self._box.session_id(item.id)
        if session is not None:
            self._box.add(item.id, "close", session=session)
            return "busy"
        if self._box.pending(item.id, "dispatch") is not None:
            return "busy"  # its session does not exist yet
        return "absent"

    def session_statuses(self, items: Sequence[WorkItem]) -> dict[str, SessionStatus]:
        return {i.id: self._box.status(i.id) for i in items}

    def session_notes(self, items: Sequence[WorkItem]) -> dict[str, str]:
        """A blocked session's `needs_action` text, by item id (R15)."""
        return {i.id: note for i in items if (note := self._box.note(i.id))}

    def message(self, item: WorkItem, text: str) -> None:
        session = self._box.session_id(item.id)
        if session is None:
            raise ValueError(f"{item.id} has no session to message")
        self._box.message(item.id, session, text)

    def rehome(self, item: WorkItem, brief: str) -> str:
        """Ask the agent to move *item*'s session to a new one started with *brief*
        (R17); returns the pending handle."""
        session = self._box.session_id(item.id)
        if session is None:
            raise ValueError(f"{item.id} has no session to re-home")
        pending = self._box.pending(item.id, "rehome")
        if pending is None:
            recorded = self._box.session_of(item.id) or {}
            pending = self._box.add(
                item.id,
                "rehome",
                session=session,
                tag=item.id,
                repo=recorded.get("repo") or item.repo,
                branch=recorded.get("branch") or item.payload.get("branch"),
                model=item.payload.get("model"),
                prompt=brief,
            )
        return f"pending:{pending['id']}"
