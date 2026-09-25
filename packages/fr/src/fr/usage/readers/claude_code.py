"""Claude Code: `<project>/<session>.jsonl` + `<session>/subagents/*.jsonl`.

Built on `fr.run.telemetry`'s transcript primitives rather than beside them:
`_read_records` (tolerant JSONL, explicit UTF-8), `message_groups` (the #597
dedupe — first record per `message.id` wins its usage, and the message's later
records still contribute their tool_use blocks) and `_is_real_model` (a
`<synthetic>` filler served nothing).

Dollars are the harness's own: the LAST `cost-state` record of the main
transcript (`totalCostUSD`, `modelUsage[*].costUSD`), which covers the whole
session, subagents included. A session with no `cost-state` has `source:
none` — its tokens are real, its dollars unknown.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

from fr.run import telemetry
from fr.usage.model import Cost, Message, Tokens, ToolCall, UsageRecord, unavailable

HARNESS: Final = "claude-code"

_TARGET_KEYS = ("command", "file_path", "path", "notebook_path")
"""The one input field a tool call acted on, in the order tools name it."""

_CONTEXT_SUFFIX = re.compile(r"\[[^\]]*\]$")


def normalize_model(model: str) -> str:
    """`claude-opus-5[1m]` -> `claude-opus-5`: cost-state keys carry the context
    window, message records do not, and the two must join."""
    return _CONTEXT_SUFFIX.sub("", model)


def _count(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def tokens_of(usage: Mapping[str, Any]) -> Tokens:
    """A Claude usage block as fr's five figures.

    The cache write splits by TTL when `cache_creation` says so; an older block
    without the split books the whole write at the 1-hour rate — the audit's
    convention, and the conservative reading (Claude Code's default TTL)."""
    split = usage.get("cache_creation")
    split = split if isinstance(split, Mapping) else {}
    one_h, five_m = split.get("ephemeral_1h_input_tokens"), split.get("ephemeral_5m_input_tokens")
    if one_h is None and five_m is None:
        one_h, five_m = usage.get("cache_creation_input_tokens"), 0
    return Tokens(
        input=_count(usage.get("input_tokens")),
        cache_write_5m=_count(five_m),
        cache_write_1h=_count(one_h),
        cache_read=_count(usage.get("cache_read_input_tokens")),
        output=_count(usage.get("output_tokens")),
    )


def _tool_calls(records: list[dict[str, Any]]) -> tuple[ToolCall, ...]:
    calls: list[ToolCall] = []
    for record in records:
        content = record["message"].get("content")
        for block in content if isinstance(content, list) else ():
            if not isinstance(block, Mapping) or block.get("type") != "tool_use":
                continue
            raw = block.get("input")
            inp: Mapping[str, Any] = raw if isinstance(raw, Mapping) else {}
            target = next((inp[k] for k in _TARGET_KEYS if isinstance(inp.get(k), str)), "")
            calls.append(ToolCall(name=str(block.get("name") or ""), target=target))
    return tuple(calls)


def _messages(records: list[dict[str, Any]], agent: str) -> list[Message]:
    out: list[Message] = []
    for first, usage, blocks in telemetry.message_groups(records):
        model = first["message"].get("model")
        if not telemetry._is_real_model(model):
            continue
        ts = first.get("timestamp")
        out.append(
            Message(
                ts=ts if isinstance(ts, str) else None,
                model=normalize_model(model),
                tokens=tokens_of(usage),
                tool_calls=_tool_calls(blocks),
                agent=agent,
            )
        )
    return out


def _cost(records: list[dict[str, Any]]) -> Cost:
    states = [r for r in records if r.get("type") == "cost-state"]
    if not states:
        return Cost()
    state = states[-1]
    total = state.get("totalCostUSD")
    if not isinstance(total, int | float) or isinstance(total, bool):
        return Cost()
    by_model: dict[str, float] = {}
    usage = state.get("modelUsage")
    for model, figures in usage.items() if isinstance(usage, Mapping) else ():
        value = figures.get("costUSD") if isinstance(figures, Mapping) else None
        if isinstance(value, int | float) and not isinstance(value, bool):
            key = normalize_model(str(model))
            by_model[key] = by_model.get(key, 0.0) + float(value)
    return Cost(usd=float(total), source="exact", by_model=by_model)


def _agent_type(stream: Path) -> str:
    meta = stream.with_name(stream.name[: -len(".jsonl")] + ".meta.json")
    try:
        data = json.loads(meta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "subagent"
    kind = data.get("agentType") if isinstance(data, dict) else None
    return kind if isinstance(kind, str) and kind else "subagent"


def read(source: Path, session: str | None = None) -> UsageRecord:
    """The session whose main transcript is `source` (`session` is its file
    name; the argument exists for the shared protocol). Never raises."""
    path = Path(source)
    session = path.name.removesuffix(".jsonl")
    try:
        records = telemetry._read_records(path)
        if records is None:
            return unavailable(session, HARNESS, f"unreadable transcript: {path.name}")
        messages = _messages(records, "main")
        subagents = telemetry.session_dir(path) / "subagents"
        for stream in sorted(subagents.glob("*.jsonl")) if subagents.is_dir() else ():
            sub_records = telemetry._read_records(stream)
            if sub_records is None:
                return unavailable(
                    session, HARNESS, f"unreadable subagent transcript: {stream.name}"
                )
            messages.extend(_messages(sub_records, _agent_type(stream)))
        return UsageRecord(
            session=session, harness=HARNESS, messages=tuple(messages), cost=_cost(records)
        )
    except Exception as exc:  # noqa: BLE001 — a reader reports, it never raises
        return unavailable(session, HARNESS, f"{type(exc).__name__}: {exc}")
