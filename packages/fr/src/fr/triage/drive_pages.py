"""`drive-pages.json`: what the wave driver remembers between passes about the pages it
renders (spec 2026-11-18-triage-pages-ux R6, R7).

It is the previous page-writing pass's unfinished wave set, whether a wave finish is still
owed a snapshot (a pass whose Backlog write failed), and Architecture's last measurement. A
new process (a host restart, the cloud driver's next wake) reads it back, so a wave finished
while no driver ran still snapshots once, and a measurement is not taken again for nothing.
It lives in the scope's state directory and travels in the state ref
(`state_ref.REF_FILES`), like the lease. A file fr cannot read is no memory, never a crash:
the next pass then takes its first-pass decisions again.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from fr.artifacts.atomic import write_text_atomic
from fr.triage.architecture import Measure, Measured

PAGES_FILE = "drive-pages.json"
SCHEMA = 1


@dataclass(frozen=True)
class PagesMemory:
    unfinished: frozenset[str]
    owed: bool = False
    measured: dict[str, Measured] | None = None


def _measure(raw: Any) -> Measure | None:
    return None if raw is None else Measure(**raw)


def load_memory(state_dir: Path) -> PagesMemory | None:
    """The remembered pass, or None when there is none or it cannot be read."""
    try:
        data = json.loads((state_dir / PAGES_FILE).read_text(encoding="utf-8"))
        if data.get("schema") != SCHEMA:
            return None
        raw = data.get("measured")
        measured = (
            None
            if raw is None
            else {
                name: Measured(then=_measure(m["then"]), now=_measure(m["now"]))
                for name, m in raw.items()
            }
        )
        return PagesMemory(
            unfinished=frozenset(str(w) for w in data["unfinished"]),
            owed=bool(data["owed"]),
            measured=measured,
        )
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


def save_memory(state_dir: Path, memory: PagesMemory) -> None:
    """Write *memory* atomically."""
    body = {
        "schema": SCHEMA,
        "unfinished": sorted(memory.unfinished),
        "owed": memory.owed,
        "measured": None
        if memory.measured is None
        else {name: asdict(m) for name, m in memory.measured.items()},
    }
    write_text_atomic(state_dir / PAGES_FILE, json.dumps(body, indent=2) + "\n")
