"""`fr`, with a stub `claude-cloud` runner injected (cloud-triage p4-r6).

`fr triage drive pass` refuses when the cloud runner cannot be loaded or keeps no
mailbox, and the real `claude-cloud` package (phase 5) is not installed yet. So the
scenario runs the INSTALLED fr through this file, with that fr's own interpreter, and the
runner is injected the way the driver adapter's unit tests inject theirs: by replacing
`triage_batch_cmd.load_runner`, never by an entry point. The stub dispatches nothing on
its own and keeps a mailbox: each dispatch is a pending request until it is recorded.
Usage: <fr's python> stub_cloud.py <fr arguments...>
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from typing import Any

import fr.cli
from fr.commands import triage_batch_cmd

CLOUD = "claude-cloud"


class StubCloud:
    name = CLOUD
    capabilities = frozenset({"git"})

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []

    def preflight(self, items: Sequence[Any]) -> str | None:
        return None

    def refresh(self) -> None:
        return None

    def slot_budget(self) -> int:
        return 1

    def existing_dispatches(self, items: Sequence[Any]) -> set[str]:
        return set()

    def can_dispatch(self, item: Any) -> bool:
        return True

    def dispatch(self, item: Any) -> str | None:
        rid = f"{item.id}:dispatch:1"
        self.requests.append({"id": rid, "kind": "dispatch", "item": item.id})
        return f"pending:{rid}"

    # fr.triage.driver.Mailbox
    def open_mailbox(self, state_dir: Any, statuses: Any) -> None:
        return None

    def outbox(self) -> list[dict[str, Any]]:
        return list(self.requests)

    def record_results(self, results: list[dict[str, Any]]) -> list[str]:
        mine = {r["id"] for r in self.requests}
        return [str(r["id"]) for r in results if r.get("id") in mine]


_real = triage_batch_cmd.load_runner
_stub = StubCloud()


def _load(name: str) -> Any:
    return _stub if name == CLOUD else _real(name)


triage_batch_cmd.load_runner = _load  # type: ignore[assignment]
sys.argv[0] = "fr"
fr.cli.app(prog_name="fr")
