"""OpenCode 2's store — the ONE adapter both readers read through (spec
2026-10-20-opencode-2-support R13, R14, §C, §D).

`fr.run.observed.OpenCodeSession` (the transcript gates) and
`fr.usage.readers.opencode` (cost) both take their rows, their tool items and
their store-version answer from here, so a gate and a usage report can never
disagree about what a session did.

OpenCode 2 writes `session_v2` (one row per session, `parent_id` for a
subagent) and `session_message` (one row per message: `type` is the role,
`data` the JSON body, `seq` its order). An assistant message's
`data.content[]` holds `reasoning`, `text` and `tool` items; a tool item is
`{type: "tool", id, name, time: {created, ran?, completed?},
state: {status, input, metadata, content: [{type: "text", text}], error?}}`.
The legacy `session`/`message`/`part` tables still exist in a 2.x store but
receive nothing; they are read here for one thing only — telling a 1.x
session (`v1-only`) apart from a session the store never held (`absent`).
"""

from __future__ import annotations

import datetime as _dt
import json
import sqlite3
from collections.abc import Iterable, Mapping
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

SHELL_TOOL: Final = "shell"
DISPATCH_TOOL: Final = "subagent"
QUESTION_TOOL: Final = "question"
READ_TOOL: Final = "read"

TOOL_ALIASES: Final[Mapping[str, str]] = {"bash": SHELL_TOOL, "task": DISPATCH_TOOL}
"""THE alias table (R13): OpenCode 1.x tool names, still carried by migrated
`session_message` rows, onto their 2.x names. Every reader canonicalises
through `canonical_tool`; nothing else lists these names."""


def canonical_tool(name: str) -> str:
    return TOOL_ALIASES.get(name, name)


StoreVersion = Literal["v2", "v1-only", "absent", "unreadable"]

V1_ONLY_REASON: Final = (
    "it is an OpenCode 1.x session (present only in the legacy `session` table) — "
    "upgrade opencode; super-fr supports 2.0 only"
)
"""R14's wording for a `v1-only` answer, shared by `why_unobservable` and the
usage reader."""


def open_ro(db: Path) -> sqlite3.Connection:
    """`db` opened read-only; raises `sqlite3.Error` when it does not exist."""
    return sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True)


def _tables(con: sqlite3.Connection) -> set[str]:
    return {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


def store_version(db: Path, session: str) -> StoreVersion:
    """Where `session` lives in the store at `db` (R14): `v2` (a `session_v2`
    row), `v1-only` (only a legacy `session` row — an OpenCode 1.x session, or a
    1.x store with no `session_v2` at all), `absent` (a store that holds neither),
    `unreadable` (missing, locked, or not an OpenCode store at all). Never raises."""
    try:
        with closing(open_ro(db)) as con:
            tables = _tables(con)
            if "session_v2" not in tables and "session" not in tables:
                return "unreadable"
            if (
                "session_v2" in tables
                and con.execute("SELECT 1 FROM session_v2 WHERE id = ?", (session,)).fetchone()
            ):
                return "v2"
            if (
                "session" in tables
                and con.execute("SELECT 1 FROM session WHERE id = ?", (session,)).fetchone()
            ):
                return "v1-only"
            return "absent"
    except sqlite3.Error:
        return "unreadable"


def query(db: Path, sql: str, params: tuple[object, ...]) -> list[tuple[Any, ...]] | None:
    """Rows of one read-only query; `None` when the store cannot be read."""
    try:
        with closing(open_ro(db)) as con:
            return con.execute(sql, params).fetchall()
    except sqlite3.Error:
        return None


# --- the row/field mapping ----------------------------------------------------

MESSAGE_COLUMNS: Final = "m.id, m.session_id, m.type, m.time_created, m.data"
SESSION_KNOWN: Final = "SELECT 1 FROM session_v2 WHERE id = ?"
SESSION_PARENT: Final = "SELECT parent_id FROM session_v2 WHERE id = ?"
SESSION_CHILDREN: Final = "SELECT id FROM session_v2 WHERE parent_id = ?"
ANY_SESSION: Final = "SELECT 1 FROM session_v2 LIMIT 1"
ACTIVE_SINCE: Final = "SELECT 1 FROM session_message WHERE time_updated >= ? LIMIT 1"
MESSAGES_OF: Final = (
    f"SELECT {MESSAGE_COLUMNS} FROM session_message m WHERE m.session_id = ? "
    "ORDER BY m.seq, m.time_created, m.id"
)
MESSAGES_OF_SINCE: Final = (
    f"SELECT {MESSAGE_COLUMNS} FROM session_message m "
    "WHERE m.session_id = ? AND m.time_updated >= ? ORDER BY m.seq, m.time_created, m.id"
)
TOP_LEVEL_MESSAGES_SINCE: Final = (
    f"SELECT {MESSAGE_COLUMNS} FROM session_message m JOIN session_v2 s ON s.id = m.session_id "
    "WHERE s.parent_id IS NULL AND m.time_updated >= ? ORDER BY m.time_created, m.seq, m.id"
)
TREE_MESSAGES: Final = (
    f"SELECT {MESSAGE_COLUMNS} FROM session_message m JOIN session_v2 s ON s.id = m.session_id "
    "WHERE s.id = ? OR s.parent_id = ? ORDER BY m.time_created, m.seq, m.id"
)


def mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def loads(raw: object) -> Mapping[str, Any]:
    """`raw` parsed as a JSON object, `{}` when it does not parse. Only for a
    field whose absence is harmless; a message row's `data` goes through
    `parse_data`, which keeps "unreadable" apart from "empty" (p4-r2)."""
    parsed = parse_data(raw)
    return {} if parsed is None else parsed


def parse_data(raw: object) -> Mapping[str, Any] | None:
    """`raw` as a JSON object, or `None` when it is not one — a row fr could
    not read, never silently a row that holds nothing (R14, p4-r2)."""
    try:
        data = json.loads(raw) if isinstance(raw, str | bytes) else None
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return data if isinstance(data, Mapping) else None


def ms_to_dt(ms: object) -> _dt.datetime | None:
    if not isinstance(ms, int | float) or isinstance(ms, bool):
        return None
    return _dt.datetime.fromtimestamp(ms / 1000, tz=_dt.UTC)


@dataclass(frozen=True)
class StoredMessage:
    """One `session_message` row, `data` parsed once."""

    id: str
    session: str
    type: str
    created_ms: int | None
    data: Mapping[str, Any]
    unreadable: bool = False
    """`data` did not parse as a JSON object: `data` is `{}` only so code that
    reads around it does not crash — every reader that sums or observes must
    check this flag and degrade (p4-r2), never treat the row as empty."""

    @property
    def content(self) -> list[Mapping[str, Any]]:
        items = self.data.get("content")
        return [i for i in items if isinstance(i, Mapping)] if isinstance(items, list) else []


def stored_message(row: tuple[Any, ...]) -> StoredMessage:
    mid, owner, kind, created, raw = row
    return StoredMessage(
        id=str(mid),
        session=str(owner),
        type=str(kind),
        created_ms=created if isinstance(created, int) else None,
        data=parsed if (parsed := parse_data(raw)) is not None else {},
        unreadable=parsed is None,
    )


@dataclass(frozen=True)
class ToolItem:
    """One `tool` item of a message's `data.content[]` — the ONE place the
    shell, read, question and dispatch readers take a call's name, status,
    input, metadata, output and times from."""

    session: str
    message: str
    tool: str
    """Canonical (2.x) name: `bash` reads as `shell`, `task` as `subagent`."""
    call_id: str | None
    status: str | None
    input: Mapping[str, Any]
    metadata: Mapping[str, Any]
    output: str | None
    began: _dt.datetime | None
    ended: _dt.datetime | None


def _text_of(items: object) -> str | None:
    if not isinstance(items, list):
        return None
    texts = [
        i["text"]
        for i in items
        if isinstance(i, Mapping) and i.get("type") == "text" and isinstance(i.get("text"), str)
    ]
    return "".join(texts) if texts else None


def tool_item(message: StoredMessage, item: Mapping[str, Any]) -> ToolItem | None:
    """`item` as a `ToolItem`, or `None` when it is not a tool item. `began` is
    `time.ran`, else `time.created`, else the message's; `ended` is
    `time.completed`; output is `state.content[].text`, else
    `state.metadata.output`."""
    if item.get("type") != "tool":
        return None
    name = item.get("name")
    if not isinstance(name, str):
        return None
    state = mapping(item.get("state"))
    times = mapping(item.get("time"))
    metadata = mapping(state.get("metadata"))
    output = _text_of(state.get("content"))
    if output is None and isinstance(metadata.get("output"), str):
        output = metadata["output"]
    call_id = item.get("id")
    status = state.get("status")
    return ToolItem(
        session=message.session,
        message=message.id,
        tool=canonical_tool(name),
        call_id=call_id if isinstance(call_id, str) else None,
        status=status if isinstance(status, str) else None,
        input=mapping(state.get("input")),
        metadata=metadata,
        output=output,
        began=ms_to_dt(times.get("ran"))
        or ms_to_dt(times.get("created"))
        or ms_to_dt(message.created_ms),
        ended=ms_to_dt(times.get("completed")),
    )


def tool_items(messages: Iterable[StoredMessage]) -> list[ToolItem]:
    out: list[ToolItem] = []
    for message in messages:
        for item in message.content:
            found = tool_item(message, item)
            if found is not None:
                out.append(found)
    return out


def final_text(messages: Iterable[StoredMessage]) -> str | None:
    """The last non-empty `text` item of the last assistant message holding one."""
    for message in reversed(list(messages)):
        if message.type != "assistant":
            continue
        for item in reversed(message.content):
            text = item.get("text")
            if item.get("type") == "text" and isinstance(text, str) and text:
                return text
    return None


def dispatch_child(item: ToolItem) -> str | None:
    """The child session a dispatch item opened: 2.x `metadata.sessionID`,
    1.x-migrated `metadata.sessionId`."""
    for key in ("sessionID", "sessionId"):
        value = item.metadata.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def dispatch_parent(item: ToolItem) -> str:
    """The session that made the dispatch: a 1.x-migrated item's own
    `parentSessionId` claim, else the session whose message carries it."""
    claimed = item.metadata.get("parentSessionId")
    return claimed if isinstance(claimed, str) else item.session


def dispatch_agent(item: ToolItem) -> str | None:
    for key in ("agent", "subagent_type"):
        value = item.input.get(key)
        if isinstance(value, str):
            return value
    return None


def dispatch_prompt(item: ToolItem) -> str | None:
    prompt = item.input.get("prompt")
    return prompt if isinstance(prompt, str) else None
