"""`drive-pages.json`: what the wave driver remembers between passes about the pages it
renders (spec 2026-11-18-triage-pages-ux R6, R7).

It is the previous page-writing pass's unfinished wave set and whether a wave finish is
still owed a snapshot (a pass whose Backlog write failed). A new process (a host restart,
the cloud driver's next wake) reads it back, so a wave finished while no driver ran still
snapshots once. It holds no measurement: Architecture's line counts stay in the process that
took them (they name commits of a repo that may be private), and a new process measures on
its first page-writing pass.
It lives in the scope's state directory and travels in the state ref
(`state_ref.REF_FILES`), like the lease. A file fr cannot read is no memory, never a crash:
the next pass then takes its first-pass decisions again.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from fr.artifacts.atomic import write_text_atomic

PAGES_FILE = "drive-pages.json"
SCHEMA = 1


@dataclass(frozen=True)
class PagesMemory:
    unfinished: frozenset[str]
    owed: bool = False


_KEYS = {"schema", "unfinished", "owed"}
_OLD_KEYS = {"measured"}  # an earlier fr also wrote Architecture's measurement: ignored


def load_memory(state_dir: Path) -> PagesMemory | None:
    """The remembered pass, or None when there is none, it cannot be read or it is not
    exactly the shape fr writes (the file travels in a state repo, so nothing in it is
    trusted): schema 1, `unfinished` a list of strings, `owed` a bool, no other key."""
    try:
        data = json.loads((state_dir / PAGES_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or not _KEYS <= data.keys() <= _KEYS | _OLD_KEYS:
        return None
    unfinished, owed = data["unfinished"], data["owed"]
    if (
        type(data["schema"]) is not int
        or data["schema"] != SCHEMA
        or not isinstance(unfinished, list)
        or not all(isinstance(w, str) for w in unfinished)
        or not isinstance(owed, bool)
    ):
        return None
    return PagesMemory(frozenset(unfinished), owed)


def save_memory(state_dir: Path, memory: PagesMemory) -> None:
    """Write *memory* atomically."""
    body = {"schema": SCHEMA, "unfinished": sorted(memory.unfinished), "owed": memory.owed}
    write_text_atomic(state_dir / PAGES_FILE, json.dumps(body, indent=2) + "\n")
