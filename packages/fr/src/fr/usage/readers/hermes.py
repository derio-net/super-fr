"""Hermes: `~/.hermes/state.db` (`sessions`, `messages`, `session_model_usage`).

**Coarser than the other two** (spec §5.A.3). Hermes keeps ONE `token_count`
per message and its tool calls as JSON, so a message's usage cannot be split
into input/cache/output. Each message's `token_count` is carried as `input`
(ratio 1), which makes the price-weighted split degenerate to a
token-count-weighted one — the record says so with `attribution: coarse`.

Dollars: `sessions.actual_cost_usd` when Hermes has it (`exact`), else
`estimated_cost_usd` (`estimated`), summed over the session and its delegate
children; per-model figures from `session_model_usage`. An ACP session stores
zero tokens everywhere (hermes-agent#6775): that is recorded as `unavailable`,
never as a session that cost nothing.
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
from fr.usage.readers.opencode import open_ro

HARNESS: Final = "hermes"

ACP_ZERO_TOKENS = "hermes records zero tokens for this session (ACP sessions, hermes-agent#6775)"

_TARGET_KEYS = ("command", "path", "file_path", "code")


def _number(value: object) -> float | None:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


def _tool_calls(raw: object) -> tuple[ToolCall, ...]:
    try:
        calls = json.loads(raw) if isinstance(raw, str) and raw else []
    except json.JSONDecodeError:
        return ()
    out: list[ToolCall] = []
    for call in calls if isinstance(calls, list) else ():
        if not isinstance(call, Mapping):
            continue
        fn = call.get("function")
        spec: Mapping[str, Any] = fn if isinstance(fn, Mapping) else call
        args = spec.get("arguments")
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}
        inp: Mapping[str, Any] = args if isinstance(args, Mapping) else {}
        target = next((inp[k] for k in _TARGET_KEYS if isinstance(inp.get(k), str)), "")
        out.append(ToolCall(name=str(spec.get("name") or ""), target=target))
    return tuple(out)


def read(source: Path, session: str | None = None) -> UsageRecord:
    """Session `session` of the Hermes database at `source`. Never raises."""
    if not session:
        return unavailable("", HARNESS, "no session id given")
    try:
        with closing(open_ro(Path(source))) as con:
            sessions = con.execute(
                "SELECT id, model, input_tokens, output_tokens, cache_read_tokens, "
                "cache_write_tokens, estimated_cost_usd, actual_cost_usd FROM sessions "
                "WHERE id = ? OR parent_session_id = ?",
                (session, session),
            ).fetchall()
            if not any(row[0] == session for row in sessions):
                return unavailable(session, HARNESS, "session not in the Hermes database")
            messages = con.execute(
                "SELECT m.session_id, m.timestamp, m.token_count, m.tool_calls FROM messages m "
                "JOIN sessions s ON s.id = m.session_id "
                "WHERE (s.id = ? OR s.parent_session_id = ?) AND m.role = 'assistant' "
                "ORDER BY m.timestamp, m.id",
                (session, session),
            ).fetchall()
            per_model = con.execute(
                "SELECT u.model, SUM(u.estimated_cost_usd), SUM(u.actual_cost_usd) "
                "FROM session_model_usage u JOIN sessions s ON s.id = u.session_id "
                "WHERE s.id = ? OR s.parent_session_id = ? GROUP BY u.model",
                (session, session),
            ).fetchall()
    except sqlite3.Error as exc:
        return unavailable(session, HARNESS, f"Hermes database unreadable: {exc}")

    session_tokens = sum(int(v or 0) for row in sessions for v in row[2:6])
    message_tokens = sum(int(row[2] or 0) for row in messages)
    if session_tokens == 0 and message_tokens == 0:
        return unavailable(session, HARNESS, ACP_ZERO_TOKENS)

    models = {row[0]: str(row[1] or "unknown") for row in sessions}
    actual = [_number(row[7]) for row in sessions]
    estimated = [_number(row[6]) for row in sessions]
    if all(v is not None for v in actual):
        cost = Cost(
            usd=sum(v for v in actual if v is not None),
            source="exact",
            by_model={m: float(a or 0) for m, _e, a in per_model},
        )
    elif all(v is not None for v in estimated):
        cost = Cost(
            usd=sum(v for v in estimated if v is not None),
            source="estimated",
            by_model={m: float(e or 0) for m, e, _a in per_model},
        )
    else:
        cost = Cost()

    out = [
        Message(
            ts=datetime.fromtimestamp(float(ts), tz=UTC).isoformat() if ts is not None else None,
            model=models.get(owner, "unknown"),
            tokens=Tokens(input=int(count or 0)),
            tool_calls=_tool_calls(calls),
            agent="main" if owner == session else "delegate",
        )
        for owner, ts, count, calls in messages
    ]
    return UsageRecord(
        session=session, harness=HARNESS, messages=tuple(out), cost=cost, attribution="coarse"
    )
