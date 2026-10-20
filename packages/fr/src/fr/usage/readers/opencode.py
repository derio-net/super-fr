"""OpenCode 2: `opencode.db` (`session_v2`, `session_message`) — located by
`fr.run.telemetry.OpenCodeReader.database` (`$XDG_DATA_HOME/opencode/`, else
`~/.local/share/opencode/`), read through the one adapter the run reader also
uses, `fr.run.opencode_store` (spec 2026-10-20-opencode-2-support R13, R14, §D).

Opened read-only (`mode=ro` URI), so a missing database is an error — never a
new empty file — and nothing here can write the harness's own store. One
session's record includes its child sessions (a subagent is a child session,
`parent_id` = the session), each message tagged with its agent. A session the
store holds only in OpenCode 1.x's legacy tables is `unavailable` with R14's
reason: never zeros, never an empty record.

Dollars are OpenCode's own per-message `data.cost`, summed: `exact` only when
every priced message is billed, `estimated` when any is Copilot-routed
(`ESTIMATED_PROVIDERS`). A session whose
messages all cost `$0` (a free model) has no dollar figure: `source: none`,
rendered `—` — a free model did not cost nothing on a meter fr can read, it
reported no meter at all.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from fr.run.opencode_store import (
    DISPATCH_TOOL,
    TREE_MESSAGES,
    V1_ONLY_REASON,
    ToolItem,
    dispatch_child,
    dispatch_parent,
    dispatch_prompt,
    mapping,
    open_ro,
    store_version,
    stored_message,
    tool_items,
)
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


__all__ = ["HARNESS", "ESTIMATED_PROVIDERS", "open_ro", "read", "tokens_of"]


def _iso(ms: object) -> str | None:
    if not isinstance(ms, int | float) or isinstance(ms, bool):
        return None
    return datetime.fromtimestamp(ms / 1000, tz=UTC).isoformat()


def _tool_call(item: ToolItem) -> ToolCall:
    target = next((item.input[k] for k in _TARGET_KEYS if isinstance(item.input.get(k), str)), "")
    return ToolCall(name=item.tool, target=target)


def _brief(item: ToolItem, session: str) -> tuple[str, int] | None:
    """`(child session, prompt chars)` of a dispatch this session made —
    `state.input.prompt`, keyed by the child session (else the item's `id`). A
    dispatch a child session made is not this session's brief."""
    if item.tool != DISPATCH_TOOL:
        return None
    prompt = dispatch_prompt(item)
    if prompt is None or dispatch_parent(item) != session:
        return None
    key = dispatch_child(item) or item.call_id
    return (key, len(prompt)) if key is not None else None


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
    version = store_version(source, session)
    if version == "v1-only":
        return unavailable(session, HARNESS, f"session {session}: {V1_ONLY_REASON}")
    if version == "unreadable":
        return unavailable(session, HARNESS, "OpenCode database unreadable")
    if version == "absent":
        return unavailable(session, HARNESS, "session not in the OpenCode database")
    with closing(open_ro(source)) as con:
        rows = con.execute(TREE_MESSAGES, (session, session)).fetchall()
    stored = [stored_message(row) for row in rows]
    bad = [m.id for m in stored if m.unreadable]
    if bad:
        # p4-r2: a partial sum labelled `exact` hides what could not be read.
        return unavailable(
            session,
            HARNESS,
            f"OpenCode message row(s) {', '.join(bad)} have unreadable data, so the "
            "session's cost, tokens and tool calls cannot be read whole",
        )
    calls: dict[str, list[ToolCall]] = {}
    briefs: dict[str, int] = {}
    for item in tool_items(stored):
        calls.setdefault(item.message, []).append(_tool_call(item))
        brief = _brief(item, session)
        if brief is not None:
            briefs[brief[0]] = brief[1]
    messages: list[Message] = []
    total = 0.0
    exact = True
    by_model: dict[str, float] = {}
    for message in stored:
        if message.type != "assistant":
            continue
        own = message.session == session
        data = message.data
        model_of: Mapping[str, Any] = mapping(data.get("model"))
        model = str(model_of.get("id") or "unknown")
        messages.append(
            Message(
                ts=_iso(data_time(data) or message.created_ms),
                model=model,
                tokens=tokens_of(data),
                tool_calls=tuple(calls.get(message.id, ())),
                agent="main" if own else str(data.get("agent") or "subagent"),
                agent_id=None if own else message.session,
            )
        )
        cost = data.get("cost")
        if isinstance(cost, int | float) and not isinstance(cost, bool) and cost > 0:
            total += float(cost)
            by_model[model] = by_model.get(model, 0.0) + float(cost)
            exact = exact and not _estimated(model_of.get("providerID"))
    if total > 0:
        return UsageRecord(
            session=session,
            harness=HARNESS,
            messages=tuple(messages),
            cost=Cost(usd=total, source="exact" if exact else "estimated", by_model=by_model),
            briefs=briefs,
        )
    return UsageRecord(session=session, harness=HARNESS, messages=tuple(messages), briefs=briefs)


def data_time(data: Mapping[str, Any]) -> object:
    """`data.time.created` — when the message began."""
    return mapping(data.get("time")).get("created")
