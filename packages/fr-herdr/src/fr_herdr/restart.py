"""Restart idle Claude panes in place (spec 2026-10-06-driver-sessions-design §A).

`post_merge` rebuilds the tool env, so every other Claude session keeps the plugins it
loaded at start-up. This module restarts the idle ones on `--resume`, in the same pane,
with the same herdr agent name and launch flags.

The decisions are pure and kept apart from the herdr calls: `classify` (R2, the first
failing check names the reason), `kept_args` (which launch flags survive a restart),
`has_draft` and `has_background_work` (what the screen says), `transcript_path`.

The herdr surfaces parsed here are recorded from live herdr 0.9.1 under
`tests/fixtures/herdr/restart/` (see its README). Two things it found that the spec's
first draft did not know: `← N agent` is on the status line of every idle Claude, so it
is not evidence of background work (`N shells`, `N monitors` and the agent panel are);
and herdr accepts the pane's own agent name again right after `/exit`.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Collection

IDLE_STATUSES = frozenset({"idle", "done"})

# flag -> how many values follow it: 0, 1, or "*" (every following non-flag token)
_KEPT: dict[str, int | str] = {
    "--model": 1,
    "--permission-mode": 1,
    "--dangerously-skip-permissions": 0,
    "--add-dir": "*",
    "--settings": 1,
    "--mcp-config": "*",
    "--plugin-dir": 1,
    "--agent": 1,
}
# The flags a restart replaces: the relaunch carries its own `--resume <id>`.
_DROPPED: dict[str, int | str] = {
    "--resume": "?",
    "-r": "?",
    "--continue": 0,
    "-c": 0,
    "--session-id": 1,
}


@dataclass(frozen=True)
class Skip:
    """A pane that is not restarted, and why (R2). No key is ever sent to it."""

    pane_id: str
    reason: str


@dataclass(frozen=True)
class Plan:
    """A pane that will be restarted."""

    pane_id: str
    name: str | None
    session_id: str
    cwd: str
    kept: tuple[str, ...]


@dataclass(frozen=True)
class UnknownFlag:
    """A launch argument a restart cannot carry over (a flag outside the kept set, or a
    positional): the pane is skipped rather than resumed without it (sr-14)."""

    flag: str


def kept_args(argv: list[str]) -> list[str] | UnknownFlag:
    """The launch flags (with their values) a relaunch repeats; `argv[0]` is `claude`."""
    kept: list[str] = []
    rest = argv[1:]
    i = 0
    while i < len(rest):
        token = rest[i]
        i += 1
        flag, eq, _value = token.partition("=")
        if not token.startswith("-"):
            return UnknownFlag(token)
        table = _KEPT if flag in _KEPT else _DROPPED if flag in _DROPPED else None
        if table is None:
            return UnknownFlag(flag)
        arity = table[flag]
        values: list[str] = []
        if not eq:
            if arity == 1 and i < len(rest):
                values, i = [rest[i]], i + 1
            elif arity in ("*", "?"):
                while i < len(rest) and not rest[i].startswith("-"):
                    values.append(rest[i])
                    i += 1
                    if arity == "?":
                        break
        if table is _KEPT:
            kept.append(token)
            kept.extend(values)
    return kept


def transcript_path(cwd: str, session_id: str) -> Path:
    """`<CLAUDE_CONFIG_DIR or ~/.claude>/projects/<slug>/<id>.jsonl`, where the slug is
    the cwd with every character outside `[A-Za-z0-9]` replaced by `-`: the one
    directory `claude --resume` searches from that cwd (never a glob over projects)."""
    config = os.environ.get("CLAUDE_CONFIG_DIR")
    root = Path(config) if config else Path.home() / ".claude"
    return root / "projects" / re.sub(r"[^A-Za-z0-9]", "-", cwd) / f"{session_id}.jsonl"


_SGR = re.compile(r"\x1b\[([0-9;:]*)m")
_ANSI = re.compile(r"\x1b\[[0-9;:?]*[A-Za-z]")


def _live_prompt_index(lines: list[str]) -> int | None:
    for idx in range(len(lines) - 1, -1, -1):
        if lines[idx].startswith("❯"):
            return idx
    return None


def has_draft(screen: str) -> bool:
    """True when the live prompt line holds text that is not rendered faint (SGR 2).

    Claude draws its prompt suggestion faint right after the prompt
    (`❯\\xa0ESC[0mESC[2m<text>`), which a plain-text read cannot tell from typed input.
    """
    lines = screen.split("\n")
    idx = _live_prompt_index(lines)
    if idx is None:
        return False
    rest = lines[idx][1:]
    faint = False
    pos = 0
    for match in _SGR.finditer(rest):
        if _visible(rest[pos : match.start()]) and not faint:
            return True
        faint = _next_faint(faint, match.group(1))
        pos = match.end()
    return bool(_visible(rest[pos:])) and not faint


def _visible(text: str) -> str:
    return _ANSI.sub("", text).replace("\xa0", "").strip()


def _next_faint(faint: bool, params: str) -> bool:
    """The faint (SGR 2) state after one `ESC[<params>m`; a colour's operands are skipped,
    so the `2` in `38;2;r;g;b` is never read as "faint"."""
    codes = re.split(r"[;:]", params)
    i = 0
    while i < len(codes):
        code = codes[i] or "0"
        i += 1
        if code in ("38", "48"):
            mode = codes[i] if i < len(codes) else ""
            i += 1 + (3 if mode == "2" else 1 if mode == "5" else 0)
        elif code in ("0", "22"):
            faint = False
        elif code == "2":
            faint = True
    return faint


_SHELLS = re.compile(r"\b\d+ (?:shells?|monitors?)\b")
_AGENTS = re.compile(r"← (\d+) agents?\b")
_PANEL_ROW = re.compile(r"^\s*◯\s")


def has_background_work(screen: str) -> bool:
    """The status line under the prompt names running shells or monitors, or the agent
    panel lists a subagent. `← 1 agent` alone is on every idle Claude, so only a count
    above one counts."""
    lines = screen.split("\n")
    idx = _live_prompt_index(lines)
    below = [_ANSI.sub("", line) for line in lines[(idx or 0) :]]
    for line in below:
        if _SHELLS.search(line) or _PANEL_ROW.match(line):
            return True
        found = _AGENTS.search(line)
        if found and int(found.group(1)) > 1:
            return True
    return False


def classify(
    *,
    agent: dict[str, Any],
    screen: str,
    argv: list[str] | None,
    cwd: str,
    transcript_exists: bool,
    self_pane: str | None,
    excluded: Collection[str],
) -> Skip | Plan:
    """R2 in a fixed order; the first failing check names the reason."""
    pane = str(agent["pane_id"])
    status = str(agent.get("agent_status"))
    if status not in IDLE_STATUSES:
        return Skip(pane, f"status {status}")
    session = agent.get("agent_session") or {}
    session_id = session.get("value")
    if not session_id:
        return Skip(pane, "no-session")
    if argv is None:
        return Skip(pane, "no-process")
    if not transcript_exists:
        return Skip(pane, "no-transcript")
    kept = kept_args(argv)
    if isinstance(kept, UnknownFlag):
        return Skip(pane, f"unknown-flag {kept.flag}")
    if has_draft(screen):
        return Skip(pane, "draft")
    if has_background_work(screen):
        return Skip(pane, "background-work")
    if self_pane and pane == self_pane:
        return Skip(pane, "self")
    if pane in excluded:
        return Skip(pane, "excluded")
    return Plan(pane, agent.get("name") or None, str(session_id), cwd, tuple(kept))
