"""OpenCode: `~/.local/share/opencode/opencode.db` (`session`, `message`, `part`).

Opened read-only (`mode=ro` URI), so a missing database is an error — never a
new empty file — and nothing here can write the harness's own store. One
session's record includes its child sessions (a `task` subagent is a child
session, `parent_id` = the session), each message tagged with its agent.

Dollars are OpenCode's own per-message `data.cost`, summed. A session whose
messages all cost `$0` (a free model) has no dollar figure: `source: none`,
rendered `—` — a free model did not cost nothing on a meter fr can read, it
reported no meter at all.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from fr.usage.model import Cost, Message, Tokens, ToolCall, UsageRecord, unavailable

HARNESS: Final = "opencode"

_TARGET_KEYS = ("command", "filePath", "file_path", "path")


def _count(value: object) -> int:
    """A token count, or 0 — a boolean is not a count."""
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def tokens_of(data: Mapping[str, Any]) -> Tokens:
    """One assistant message's `data.tokens` as fr's five figures.

    `output + reasoning` -> `output` (reasoning is billed as output);
    `cache.write` -> the 5-minute write (OpenCode records no TTL split, and the
    API's default TTL is 5 minutes); `tokens.total` is not read — it is the sum
    of the others. A missing or non-integer field counts 0.
    """
    raw = data.get("tokens")
    tokens: Mapping[str, Any] = raw if isinstance(raw, Mapping) else {}
    raw_cache = tokens.get("cache")
    cache: Mapping[str, Any] = raw_cache if isinstance(raw_cache, Mapping) else {}
    return Tokens(
        input=_count(tokens.get("input")),
        cache_write_5m=_count(cache.get("write")),
        cache_read=_count(cache.get("read")),
        output=_count(tokens.get("output")) + _count(tokens.get("reasoning")),
    )


def open_ro(db: Path) -> sqlite3.Connection:
    """`db` opened read-only; raises `sqlite3.Error` when it does not exist."""
    return sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True)


def _json(raw: object) -> Mapping[str, Any]:
    try:
        data = json.loads(raw) if isinstance(raw, str | bytes) else None
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, Mapping) else {}


def _iso(ms: object) -> str | None:
    if not isinstance(ms, int | float) or isinstance(ms, bool):
        return None
    return datetime.fromtimestamp(ms / 1000, tz=UTC).isoformat()


def _tool_call(part: Mapping[str, Any]) -> ToolCall | None:
    if part.get("type") != "tool":
        return None
    state = part.get("state")
    raw = state.get("input") if isinstance(state, Mapping) else None
    inp: Mapping[str, Any] = raw if isinstance(raw, Mapping) else {}
    target = next((inp[k] for k in _TARGET_KEYS if isinstance(inp.get(k), str)), "")
    return ToolCall(name=str(part.get("tool") or ""), target=target)


def read(source: Path, session: str | None = None) -> UsageRecord:
    """Session `session` of the database at `source`. Never raises."""
    if not session:
        return unavailable("", HARNESS, "no session id given")
    try:
        with closing(open_ro(Path(source))) as con:
            if con.execute("SELECT 1 FROM session WHERE id = ?", (session,)).fetchone() is None:
                return unavailable(session, HARNESS, "session not in the OpenCode database")
            rows = con.execute(
                "SELECT m.id, m.session_id, m.time_created, m.data FROM message m JOIN session s "
                "ON s.id = m.session_id WHERE s.id = ? OR s.parent_id = ? "
                "ORDER BY m.time_created, m.id",
                (session, session),
            ).fetchall()
            parts = con.execute(
                "SELECT p.message_id, p.data FROM part p JOIN session s ON s.id = p.session_id "
                "WHERE s.id = ? OR s.parent_id = ? ORDER BY p.time_created, p.id",
                (session, session),
            ).fetchall()
    except sqlite3.Error as exc:
        return unavailable(session, HARNESS, f"OpenCode database unreadable: {exc}")
    calls: dict[str, list[ToolCall]] = {}
    for message_id, raw in parts:
        call = _tool_call(_json(raw))
        if call is not None:
            calls.setdefault(message_id, []).append(call)
    messages: list[Message] = []
    total = 0.0
    by_model: dict[str, float] = {}
    for message_id, owner, created, raw in rows:
        data = _json(raw)
        if data.get("role") != "assistant":
            continue
        model = str(data.get("modelID") or "unknown")
        messages.append(
            Message(
                ts=_iso(created),
                model=model,
                tokens=tokens_of(data),
                tool_calls=tuple(calls.get(message_id, ())),
                agent="main" if owner == session else str(data.get("agent") or "subagent"),
            )
        )
        cost = data.get("cost")
        if isinstance(cost, int | float) and not isinstance(cost, bool) and cost > 0:
            total += float(cost)
            by_model[model] = by_model.get(model, 0.0) + float(cost)
    if total > 0:
        return UsageRecord(
            session=session,
            harness=HARNESS,
            messages=tuple(messages),
            cost=Cost(usd=total, source="exact", by_model=by_model),
        )
    return UsageRecord(session=session, harness=HARNESS, messages=tuple(messages))
