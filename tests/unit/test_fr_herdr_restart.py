"""fr_herdr.restart — live-fixture smoke test first, then the engine (spec 2026-10-06 §A)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "herdr" / "restart"


def _load(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((FIXTURES / name).read_text())
    return data


def test_live_fixtures_load() -> None:
    agents = _load("agent-list.json")["result"]["agents"]
    claude = [a for a in agents if a["agent"] == "claude"]
    assert claude
    for a in claude:
        assert a["agent_status"] in {"idle", "working", "done", "blocked"}
        assert a["agent_session"]["value"]
        assert a["pane_id"]
        assert "name" in a or True  # absent on an unnamed pane
    assert any("name" in a for a in claude) and any("name" not in a for a in claude)

    for name in ("process-info.json", "process-info-model-flag.json"):
        procs = _load(name)["result"]["process_info"]["foreground_processes"]
        assert any(p.get("argv", [""])[0] == "claude" for p in procs)
        assert any("argv" not in p for p in procs) or name.endswith("flag.json")
        assert all("cwd" in p for p in procs)

    for name in (
        "screen-suggestion.json",
        "screen-placeholder.json",
        "screen-empty.json",
        "screen-draft.json",
        "screen-background.json",
    ):
        raw = _load(name)["raw"]
        assert any(line.startswith("❯") for line in raw.splitlines()), name

    taken = _load("agent-start-name-taken.json")
    assert taken["error"]["code"] == "agent_name_taken"
    reuse = _load("agent-start-reuse.json")["result"]["agent"]
    assert reuse["name"] and reuse["agent_session"]["value"]
