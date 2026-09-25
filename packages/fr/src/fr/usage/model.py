"""The normalized shape every harness reader produces (spec §5.A).

Frozen, closed-world pydantic models, like the rest of fr. A `UsageRecord` is
per SESSION: its `messages` are the deduplicated assistant messages of that
session (main thread and, where the harness keeps them apart, its subagents),
and its `cost` is the harness's own figure for the whole session.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

WEIGHTS: dict[str, float] = {
    "input": 1.0,
    "cache_write_5m": 1.25,
    "cache_write_1h": 2.0,
    "cache_read": 0.1,
    "output": 5.0,
}
"""Price RATIOS relative to base input — the only pricing fr knows (spec §5.A.2).

They split a harness's dollar figure across messages; they never produce a
dollar figure of their own, so no list price is ever invented."""


class Tokens(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    input: int = 0
    cache_write_5m: int = 0
    cache_write_1h: int = 0
    cache_read: int = 0
    output: int = 0

    def weighted(self) -> float:
        """Price-weighted units: the share of a model's dollars this message earns."""
        return float(sum(getattr(self, key) * ratio for key, ratio in WEIGHTS.items()))


class ToolCall(BaseModel):
    """One tool invocation: its name and the command or path it acted on."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    target: str = ""


class Message(BaseModel):
    """One assistant message, counted once however many records carried it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ts: str | None = None
    model: str
    tokens: Tokens
    tool_calls: tuple[ToolCall, ...] = ()
    agent: str = "main"
    """`main` for the session's own thread, else the subagent's type."""


class Cost(BaseModel):
    """The harness's dollar figure. `none` means no figure — rendered `—`, never 0."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    usd: float | None = None
    source: Literal["exact", "estimated", "none"] = "none"
    by_model: dict[str, float] = {}
    """Per-model harness dollars, when the harness splits them — what `rollup`
    divides by price-weighted tokens. Empty means only the total is known."""


class UsageRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    session: str
    harness: Literal["claude-code", "opencode", "hermes"]
    role: Literal["main", "subagent"] = "main"
    messages: tuple[Message, ...] = ()
    cost: Cost = Cost()
    unavailable: str | None = None
    """Why this session could not be read. Set means: nothing here is a measurement."""
    attribution: Literal["exact", "coarse"] = "exact"
    """`coarse` when the harness keeps too little per message to split usage
    by tool call faithfully (Hermes: one token count per message)."""


def unavailable(session: str, harness: str, reason: str) -> UsageRecord:
    """A record that says it could not be read — never a record of zeros."""
    return UsageRecord.model_validate(
        {"session": session, "harness": harness, "unavailable": reason}
    )
