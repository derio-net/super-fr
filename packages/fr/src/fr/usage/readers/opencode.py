"""OpenCode: `~/.local/share/opencode/opencode.db` (`session`, `message`, `part`).

Opened read-only (`mode=ro` URI), so a missing database is an error — never a
new empty file — and nothing here can write the harness's own store. One
session's record includes its child sessions (a `task` subagent is a child
session, `parent_id` = the session), each message tagged with its agent.

Dollars are OpenCode's own per-message `data.cost`, summed: `exact` only when
every priced message is billed, `estimated` when any is Copilot-routed
(`ESTIMATED_PROVIDERS`). A session whose
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


def _brief(part: Mapping[str, Any], session: str) -> tuple[str, int] | None:
    """`(child session, prompt chars)` of a `task` dispatch this session made —
    `state.input.prompt`, keyed by `state.metadata.sessionId` (else the part's
    `callID`). A task a child session dispatched is not this session's brief."""
    if part.get("tool") != "task":
        return None
    state = part.get("state")
    state = state if isinstance(state, Mapping) else {}
    raw_input = state.get("input")
    prompt = raw_input.get("prompt") if isinstance(raw_input, Mapping) else None
    if not isinstance(prompt, str):
        return None
    raw_meta = state.get("metadata")
    meta: Mapping[str, Any] = raw_meta if isinstance(raw_meta, Mapping) else {}
    parent = meta.get("parentSessionId")
    if isinstance(parent, str) and parent != session:
        return None
    key = meta.get("sessionId") if isinstance(meta.get("sessionId"), str) else part.get("callID")
    return (key, len(prompt)) if isinstance(key, str) else None


ESTIMATED_PROVIDERS: Final = ("github-copilot",)
"""Providers whose per-message `cost` is OpenCode's own estimate, not a bill:
Copilot charges by subscription, so the figure is priced from tokens (spec
§5.A.2). Matched as a prefix (`github-copilot-enterprise` too)."""


def _estimated(provider: object) -> bool:
    return isinstance(provider, str) and provider.startswith(ESTIMATED_PROVIDERS)


def read(source: Path, session: str | None = None) -> UsageRecord:
    """Session `session` of the database at `source`. Never raises."""
    if not session:
        return unavailable("", HARNESS, "no session id given")
    try:
        return _read(Path(source), session)
    except sqlite3.Error as exc:
        return unavailable(session, HARNESS, f"OpenCode database unreadable: {exc}")
    except Exception as exc:  # noqa: BLE001 — a reader reports, it never raises
        return unavailable(session, HARNESS, f"{type(exc).__name__}: {exc}")


def _read(source: Path, session: str) -> UsageRecord:
    with closing(open_ro(source)) as con:
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
    calls: dict[str, list[ToolCall]] = {}
    briefs: dict[str, int] = {}
    for message_id, raw in parts:
        part = _json(raw)
        call = _tool_call(part)
        if call is not None:
            calls.setdefault(message_id, []).append(call)
            brief = _brief(part, session)
            if brief is not None:
                briefs[brief[0]] = brief[1]
    messages: list[Message] = []
    total = 0.0
    exact = True
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
            exact = exact and not _estimated(data.get("providerID"))
    if total > 0:
        return UsageRecord(
            session=session,
            harness=HARNESS,
            messages=tuple(messages),
            cost=Cost(usd=total, source="exact" if exact else "estimated", by_model=by_model),
            briefs=briefs,
        )
    return UsageRecord(session=session, harness=HARNESS, messages=tuple(messages), briefs=briefs)
