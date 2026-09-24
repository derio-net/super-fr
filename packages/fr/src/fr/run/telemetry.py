"""Measured tokens from a harness's own transcript — spec §5.C (V2 telemetry).

Two jobs, kept apart on purpose:

1. **Reading** — parse one transcript file into token numbers. It takes a
   path, selects `type == "assistant"` records, PROJECTS `message.usage` onto
   the four named keys, and returns a sum. It knows nothing about phases,
   runs, agents or fr-goal.
2. **Attributing** — decide which transcript belongs to one ATTEMPT of a
   dispatched unit. It takes the four facts the run cursor records about that
   attempt — `(session, agent)` and its `[dispatched, returned]` window — and
   returns at most one dispatch. This half is the fr-goal-shaped one.

`measure_attempt` is the only place they meet, and `select_for_attempt` is the
only place the attribution RULE lives (spec §4.D / §4.D.1):

- a CLAIMED attempt is selected by its agent id, which is also the
  transcript's filename, so overlapping dispatches — two phases in parallel,
  or `advance --redispatch` racing a slow return — neither lose nor swap their
  measurements;
- an UNCLAIMED one falls back to the time window, and **only** when the
  attempt's recorded session is the session this process is in. A window from
  another session can contain exactly one unrelated subagent of THIS one, and
  charging that stranger's cost to the attempt would be a wrong number
  reported as a measurement. "Not observable from here" is the honest answer;
  it is never zero and never borrowed.

The transcript is looked up in the **recorded** session's directory, never the
current one. That is what lets a new session on the same host still measure an
earlier session's attempt — and what makes another host come back honestly
empty. No hostname is recorded anywhere: a missing session directory already
says "elsewhere", and a hostname in a public repo's committed cursor is
identity nobody needs.

**No harness API is called.** Everything here reads files the harness already
writes. Claude Code is the one full implementation. OpenCode has a reader for
the MAIN session only (its SQLite session store, read-only — spec
`2026-09-24-fr-goal-scope-proportion-cost-design.md` §D); its dispatched units
keep the V1 estimates. Hermes has no reader at all (`reader_for` returns `None`,
which is what makes the degradation loud rather than silent).

## The shape, as captured — not as first assumed

`tests/fixtures/transcripts/claude-code-session.NOTE.md` holds a real capture,
and it disproved §5.C's original attribution design (plan journal finding
`f-p1-sidechain-file-split`). What is actually on disk:

    ~/.claude/projects/<cwd-slug>/
        <session-id>.jsonl                  # orchestrator: isSidechain false throughout
        <session-id>/subagents/
            agent-<agentId>.jsonl           # one subagent: isSidechain true throughout
            agent-<agentId>.meta.json       # carries toolUseId / agentType / model

So the two streams are **separate files**, and a parser that filters one file
on `isSidechain` reads zero subagent tokens from every real transcript on disk
while passing a naive test. Attribution is file-to-file: the subagent's
metadata carries the `toolUseId` of the tool_use in the orchestrator stream
that dispatched it — an exact key.

Three fields that look like identifiers and are not, each verified on the
capture, none of them read by this module:

- a subagent record's session id is the ORCHESTRATOR's, shared by every
  dispatch of that session;
- `cwd` is the harness's launch directory, and stays pinned there even when
  the agent did all its work inside an fr-isolation worktree;
- `parentUuid` inside a subagent file chains only that subagent's own turns
  and starts at `null` — it never crosses into the orchestrator's file.

The one thing that separates two dispatches of the same session is the
tool_use id, plus the window the run cursor already records.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
import sqlite3
from collections.abc import Iterable, Iterator, Mapping, Sequence
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Protocol, TypeGuard

from fr.harness.detect import detect_harness
from fr.harness.model import HarnessError

if TYPE_CHECKING:
    from fr.isolation.types import IsolationState
    from fr.run.model import MainSessionUsage, RunState

USAGE_KEYS: tuple[str, ...] = (
    "input_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
    "output_tokens",
)
"""The four figures fr records — #464's columns, and all this module reads.

The real usage object carries far more (`cache_creation`,
`output_tokens_details`, `server_tool_use`, `service_tier`, `inference_geo`,
`speed`, and sometimes an `iterations` list that REPEATS these same four
numbers). Projecting onto a named tuple of keys rather than walking the object
is therefore not tidiness: a walker double-counts every record that carries
`iterations`.
"""

CLAUDE_CODE_PROJECTS = Path(".claude") / "projects"
"""Where Claude Code writes transcripts, under `$HOME`."""

TRANSCRIPT_ROOT_ENV = "FR_TRANSCRIPT_ROOT"
"""Override for that root — the whole of this module's configuration surface,
and what keeps the test suite off the operator's own transcripts."""

SESSION_ID_ENV = "CLAUDE_CODE_SESSION_ID"
"""Set in every Claude Code tool call. Verified live (2026-09-20) from inside
a dispatched subagent: the value there is the ORCHESTRATOR's session id, which
is exactly what this module needs — the orchestrator's file is where the
dispatch tool_use ids live."""


# --- 1. reading: a path in, numbers out ----------------------------------


@dataclass(frozen=True)
class UsageTotals:
    """Summed usage for one transcript. A value, not a measurement verdict:
    "no measurement" is `None` *instead of* a `UsageTotals`, never a
    `UsageTotals` of zeros — a unit that genuinely spent nothing is a real
    measurement and must stay distinguishable from one nobody could read."""

    input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    output_tokens: int = 0
    assistant_records: int = 0
    served_models: tuple[str, ...] = field(default=(), compare=False)
    """Distinct `message.model` values of the assistant records, in order of
    first appearance — the model that actually SERVED the transcript. Not the
    agent metadata's `model`, which is the dispatch REQUEST (`"opus"`), i.e.
    the same claim the orchestrator already made (2026-09-21 debug journal C3).
    `compare=False`: this value's equality is the four FIGURES, and who served
    them is provenance beside them, not part of the sum."""

    @property
    def served_model(self) -> str | None:
        """The one model that served every record, or several joined by `+`
        (never observed for a subagent, but a mid-dispatch switch must not be
        reported as either model alone); `None` when no record named one."""
        return "+".join(self.served_models) or None

    @property
    def total(self) -> int:
        return (
            self.input_tokens
            + self.cache_creation_input_tokens
            + self.cache_read_input_tokens
            + self.output_tokens
        )

    def as_fields(self) -> dict[str, int]:
        """The four figures, keyed as `fr.run.model.MeasuredTokens` names them."""
        return {key: getattr(self, key) for key in USAGE_KEYS}


@dataclass(frozen=True)
class SessionUsage:
    """ONE harness session's main-thread usage over one window — the
    per-session half of `MainSessionUsage`, which `sum_sessions` folds. A
    value, like `UsageTotals`: "unreadable" is `None` instead of one."""

    input_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int
    output_tokens: int
    turns: int
    cost_usd: float | None = None


def sum_sessions(parts: Sequence[SessionUsage]) -> MainSessionUsage:
    """Fold per-session usages into the cursor's `MainSessionUsage`.

    `cost_usd` is summed only when EVERY session reported one: a sum over some
    of them would be a partial figure presented as the step's cost.
    """
    from fr.run.model import MainSessionUsage

    costs = [p.cost_usd for p in parts]
    return MainSessionUsage(
        **{key: sum(getattr(p, key) for p in parts) for key in USAGE_KEYS},
        turns=sum(p.turns for p in parts),
        sessions=len(parts),
        cost_usd=None if any(c is None for c in costs) else sum(c for c in costs if c is not None),
    )


def _to_second(stamp: _dt.datetime | None) -> _dt.datetime | None:
    """`stamp` truncated to whole seconds — the precision a step's `at` has."""
    return None if stamp is None else stamp.replace(microsecond=0)


def _read_records(path: Path) -> list[dict[str, Any]] | None:
    """Every complete JSON record of a `.jsonl`, or `None` if unreadable.

    A transcript is appended to live, so the final line can be half-written;
    an incomplete line is skipped rather than failing the file. A file with
    NO complete record is unreadable — not an empty measurement — because
    there is no evidence it is a transcript at all.
    """
    try:
        # encoding="utf-8" explicitly: JSON is UTF-8 by specification, but
        # `read_text()` with no encoding consults the PROCESS LOCALE. Under a
        # container or CI image with no C.UTF-8 (PEP 538 coercion then has
        # nothing to coerce to), preferred encoding is US-ASCII and every
        # transcript carrying one non-ASCII byte raises — returning None, which
        # is indistinguishable from "no transcript exists". The feature would be
        # 100% dead and say nothing. Reproduced against a real transcript with
        # LC_ALL=C. This file is written by another program in a spec'd
        # encoding; fr's own files keep the repo's bare-read_text convention.
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    records: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            records.append(record)
    return records or None


def _usage_of(record: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """`message.usage` of an ASSISTANT record, or `None`.

    Selecting on the record type first is what makes this a sum rather than a
    crash: a session interleaves `last-prompt`, `mode`, `permission-mode`,
    `atis-latch`, `attachment`, `file-history-*`, `system`, `user` and
    `queue-operation` records, none of which carry usage.

    An assistant record with no usage contributes nothing rather than raising.
    That case was never observed (0 of 157 assistant records in the source
    session lacked it) — it is a documented defensive assumption, not a
    verified shape, and an interrupted stream is its plausible producer.
    """
    if record.get("type") != "assistant":
        return None
    message = record.get("message")
    if not isinstance(message, Mapping):
        return None
    usage = message.get("usage")
    return usage if isinstance(usage, Mapping) else None


def _is_real_model(model: object) -> TypeGuard[str]:
    """A model id a request was actually served by — not a harness placeholder.

    Claude Code writes main-thread `assistant` records with `"model":
    "<synthetic>"` and an all-zero `usage` (e.g. a "No response requested."
    filler) — observed twice in this operator's own transcripts (review of
    debug journal 2026-09-21 C3). Such a record served nothing, so its "model"
    must never be recorded as the one that ran a unit. Placeholders are
    angle-bracketed; real ids never are.
    """
    return isinstance(model, str) and bool(model) and not model.startswith("<")


def _distinct_messages(
    records: list[dict[str, Any]],
) -> Iterator[tuple[dict[str, Any], Mapping[str, Any]]]:
    """`(record, usage)` for each usage-bearing record, ONE per `message.id`.

    Claude Code writes one transcript record per CONTENT BLOCK of a message
    (text, then each tool_use), and every one of them repeats the WHOLE
    message's `usage`. Summing records therefore counts a three-block message
    three times — confirmed live on spec §D's own brainstorm transcript, where
    27 of 40 assistant message ids appear on more than one record, each copy
    carrying identical usage. The first occurrence of an id wins.

    A record with no `message.id` is kept and never merged with another: an id
    is the only evidence two records are one message, and without it merging
    would be a guess. Every Claude Code usage reader iterates this one helper,
    so the subagent line and the main-session row of `fr run cost` cannot
    disagree about what a message is.

    `attempts[].measured` values recorded before this dedupe existed were
    summed per record and are NOT rewritten — they are history; `fr run cost`
    flags them as possibly over-counted instead.
    """
    seen: set[str] = set()
    for record in records:
        usage = _usage_of(record)
        if usage is None:
            continue
        # `_usage_of` already proved `message` is a Mapping.
        message_id = record["message"].get("id")
        if isinstance(message_id, str) and message_id:
            if message_id in seen:
                continue
            seen.add(message_id)
        yield record, usage


def _sum_usage(pairs: Iterable[tuple[dict[str, Any], Mapping[str, Any]]]) -> UsageTotals:
    """The four figures summed over already-deduplicated `(record, usage)`
    pairs, with the served models in order of first appearance."""
    totals = dict.fromkeys(USAGE_KEYS, 0)
    seen = 0
    served: list[str] = []
    for record, usage in pairs:
        seen += 1
        model = record["message"].get("model")
        if _is_real_model(model) and model not in served:
            served.append(model)
        for key in USAGE_KEYS:
            value = usage.get(key)
            # `isinstance(True, int)` is True in Python; a boolean is not a count.
            if isinstance(value, int) and not isinstance(value, bool):
                totals[key] += value
    return UsageTotals(**totals, assistant_records=seen, served_models=tuple(served))


def read_claude_code(path: Path) -> UsageTotals | None:
    """Summed usage for one Claude Code transcript, or `None` for *no
    measurement* (the file is missing, unreadable, or holds no record).

    Works on either file of the pair — the orchestrator's own stream or one
    subagent's — because both are the same record format. Deciding WHICH file
    answers for a given unit is the other half of this module's job, below.
    Each MESSAGE is counted once (`_distinct_messages`), so `assistant_records`
    is the number of distinct assistant messages, not of records.
    """
    records = _read_records(path)
    if records is None:
        return None
    return _sum_usage(_distinct_messages(records))


# --- 2. attributing: which dispatch does a transcript answer for? --------


@dataclass(frozen=True)
class Dispatch:
    """One subagent transcript, paired to the tool_use that started it."""

    tool_use_id: str
    agent_id: str
    transcript: Path
    agent_type: str | None = None
    model: str | None = None
    started: _dt.datetime | None = None


@dataclass(frozen=True)
class Measurement:
    """What one dispatched unit actually cost, and where the figure came from."""

    harness: str
    tool_use_id: str
    totals: UsageTotals
    agent_type: str | None = None
    model: str | None = None


def parse_timestamp(value: object) -> _dt.datetime | None:
    """An ISO 8601 instant as an aware UTC `datetime`, or `None`.

    Transcripts write `...Z` with milliseconds; the run cursor writes
    `+00:00` at second precision. Both are `fromisoformat`-parseable on the
    Python this package requires; a naive value is read as UTC, because every
    producer here writes UTC.
    """
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = _dt.datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=_dt.UTC)
    return parsed.astimezone(_dt.UTC)


def session_dir(session: Path) -> Path:
    """The per-session DIRECTORY sitting beside `<session-id>.jsonl`.

    Note the layout: a directory named for the session, next to the file named
    for the session — and the metadata inside it is `agent-<agentId>.meta.json`,
    not a bare `meta.json`. A glob written from a wrong reading of that finds
    nothing and reports it as "no subagents".
    """
    name = session.name
    if name.endswith(".jsonl"):
        name = name[: -len(".jsonl")]
    return session.parent / name


def tool_use_ids(session: Path) -> dict[str, _dt.datetime | None]:
    """Every tool_use id in the orchestrator stream, with when it was issued.

    Indexed by id and NOT filtered by tool name. The pairing below is by id,
    which is unique and exact, so filtering on the dispatch tool's name would
    add nothing except a way to go silent the day that name changes (it has
    already changed once, `Task` -> `Agent`).
    """
    records = _read_records(session)
    if records is None:
        return {}
    found: dict[str, _dt.datetime | None] = {}
    for record in records:
        if record.get("type") != "assistant":
            continue
        message = record.get("message")
        if not isinstance(message, Mapping):
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, Mapping) or block.get("type") != "tool_use":
                continue
            block_id = block.get("id")
            if isinstance(block_id, str):
                found[block_id] = parse_timestamp(record.get("timestamp"))
    return found


def _first_timestamp(path: Path) -> _dt.datetime | None:
    for record in _read_records(path) or []:
        stamp = parse_timestamp(record.get("timestamp"))
        if stamp is not None:
            return stamp
    return None


def attribute_dispatches(session: Path) -> list[Dispatch]:
    """Every subagent transcript of `session` that THIS session dispatched.

    File-to-file, keyed on the metadata's `toolUseId`: an agent file whose id
    matches no tool_use in the orchestrator stream is not attributed at all.
    That is the whole difference between this and a glob over `subagents/`,
    and it is why an unrelated agent file cannot be charged to a unit here.
    """
    known = tool_use_ids(session)
    if not known:
        return []
    subagents = session_dir(session) / "subagents"
    if not subagents.is_dir():
        return []
    dispatches: list[Dispatch] = []
    for transcript in sorted(subagents.glob("agent-*.jsonl")):
        agent_id = transcript.name[len("agent-") : -len(".jsonl")]
        meta_path = subagents / f"agent-{agent_id}.meta.json"
        try:
            # Same reason as `_read_records`, and worse in kind here: this
            # UnicodeDecodeError is swallowed by the `continue`, so one
            # non-ASCII character in a dispatch `description` would silently
            # unattribute that agent rather than failing loudly.
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(meta, dict):
            continue
        tool_use_id = meta.get("toolUseId")
        if not isinstance(tool_use_id, str) or tool_use_id not in known:
            continue
        agent_type = meta.get("agentType")
        model = meta.get("model")
        dispatches.append(
            Dispatch(
                tool_use_id=tool_use_id,
                agent_id=agent_id,
                transcript=transcript,
                agent_type=agent_type if isinstance(agent_type, str) else None,
                model=model if isinstance(model, str) else None,
                started=known[tool_use_id] or _first_timestamp(transcript),
            )
        )
    return dispatches


def select_dispatch(dispatches: list[Dispatch], *, start: str, end: str) -> Dispatch | None:
    """The ONE dispatch issued inside `[start, end]`, or `None`.

    The window is the unit's own dispatch-to-resolve interval, which the run
    cursor already records, and serial dispatch is what makes it unambiguous.
    Two dispatches inside one window means that assumption is broken, so this
    returns nothing rather than summing them: charging another unit's cost to
    this one would be a wrong number reported as a measurement, which is worse
    than no number at all.
    """
    lower = parse_timestamp(start)
    upper = parse_timestamp(end)
    if lower is None or upper is None:
        return None
    inside = [d for d in dispatches if d.started is not None and lower <= d.started <= upper]
    return inside[0] if len(inside) == 1 else None


def select_for_attempt(
    dispatches: list[Dispatch],
    *,
    agent: str | None,
    start: str,
    end: str,
    same_session: bool,
) -> Dispatch | None:
    """THE decision: which of `dispatches` belongs to one attempt (spec §4.D).

    Two paths, ONE function — the session rule lives here and nowhere else,
    so the id path and the window path cannot each grow their own version of
    it:

    - **by agent id** — exact. A CLAIMED attempt carries the harness's own
      agent id, which is also the transcript's filename
      (`subagents/agent-<agentId>.jsonl`), so overlapping dispatches neither
      lose nor swap their measurements and no window is consulted at all. An
      id that matches nothing yields nothing: the window is not a second
      chance at a question already answered exactly.
    - **by window** — the fallback for an UNCLAIMED attempt, where the
      dispatch-to-return interval the cursor already records is all fr has.
      Allowed **only when `same_session`** (§4.D.1). Across sessions a window
      is not merely unhelpful, it is dangerous: host B resolving host A's open
      attempt at T2 gets `[T0, T2]`, which can contain exactly ONE subagent —
      one host B dispatched itself, for something unrelated — and
      `select_dispatch` would accept that stranger's cost as host A's. Wrong,
      and plausible-looking. Never zero, never guessed, never borrowed.

    `same_session` is a PROOF the caller supplies (`dispatched_from_this_
    session`), never a default: an attempt with no recorded session is not
    claimed to be this one's.
    """
    if agent is not None:
        return next((d for d in dispatches if d.agent_id == agent), None)
    if not same_session:
        return None
    return select_dispatch(dispatches, start=start, end=end)


# --- 3. harness scoping --------------------------------------------------


class TranscriptReader(Protocol):
    """What a harness must offer for fr to measure a unit. Two implementations
    exist (Claude Code; OpenCode, main session only); the Protocol is what
    keeps them one shape."""

    harness: str

    def locate_session(self, env: Mapping[str, str], session: str | None = None) -> Path | None:
        """The orchestrator transcript for `session` — the session a run
        cursor RECORDED — or, absent one, for this process's own."""

    def measure(
        self, session: Path, *, agent: str | None, start: str, end: str, same_session: bool
    ) -> Measurement | None:
        """What one attempt cost, if measurable — selected by `agent` when it
        has one, else by the window `[start, end]` and only `same_session`."""

    def measure_step(
        self,
        env: Mapping[str, str],
        sessions: Sequence[str],
        start: str,
        end: str,
        *,
        directories: Sequence[Path],
    ) -> MainSessionUsage | None:
        """What the MAIN session burned over one step's window `(start, end]`,
        summed over the candidate `sessions` — or `None` when any candidate is
        unreadable (spec §D). `directories` are the run's workspace and base
        clone, for a harness that can only find a session by where it ran."""


def transcript_root(env: Mapping[str, str]) -> Path:
    override = env.get(TRANSCRIPT_ROOT_ENV)
    if override:
        return Path(override)
    return Path.home() / CLAUDE_CODE_PROJECTS


def current_session(env: Mapping[str, str]) -> str | None:
    """The harness session id THIS process is running in, or `None`.

    Derived from fr's own environment, the way `detect_harness` derives the
    harness — `fr run advance` records it on every attempt it opens, and
    `fr run status` compares against it, so the two must be one rule and not
    two `env.get(...)` calls that can drift. One harness has a session concept
    today, hence one key; an empty value is `None`, never the empty string,
    because `"" == ""` would make two session-less processes "the same
    session".
    """
    return env.get(SESSION_ID_ENV) or None


def dispatched_from_this_session(env: Mapping[str, str], session: str | None) -> bool:
    """Was `session` the session this process is running in? (§4.D.1)

    A PROOF, never a default. `None` on either side is *not knowing*, and not
    knowing is not a match: an attempt with no recorded session — every one
    written before the field existed, and every harness with no session
    concept — does not get this session's window, and neither does a real
    session id compared against a process that has none.
    """
    current = current_session(env)
    return session is not None and current is not None and session == current


def claude_code_session(env: Mapping[str, str], session: str | None = None) -> Path | None:
    """`<root>/<cwd-slug>/<session-id>.jsonl`, found by session id.

    `session` names the session a run cursor RECORDED, which is the one whose
    transcripts answer for that attempt (§4.D.1); absent, this process's own
    is used. Looking in the recorded session's directory rather than the
    current one is what lets a NEW session on the same host still measure an
    earlier one's attempt — and what makes another HOST come back empty,
    since the directory simply is not there. A missing directory already says
    "elsewhere", so no hostname is recorded anywhere.

    The project directory is named after the harness's LAUNCH directory, which
    is not derivable from fr's own working directory (fr runs inside the
    worktree; the harness was launched in the base clone), so the id is
    matched across every project directory instead of guessing the slug.
    More than one match is ambiguous and yields nothing.
    """
    session_id = session or current_session(env)
    if not session_id:
        return None
    root = transcript_root(env)
    try:
        hits = sorted(root.glob(f"*/{session_id}.jsonl"))
    except OSError:  # pragma: no cover — an unreadable transcript root
        return None
    return hits[0] if len(hits) == 1 else None


class ClaudeCodeReader:
    """The one implemented harness."""

    harness = "claude-code"

    def locate_session(self, env: Mapping[str, str], session: str | None = None) -> Path | None:
        return claude_code_session(env, session)

    def measure(
        self,
        session: Path,
        *,
        agent: str | None = None,
        start: str,
        end: str,
        same_session: bool = True,
    ) -> Measurement | None:
        return measure_dispatch(
            session, agent=agent, start=start, end=end, same_session=same_session
        )

    def measure_main_session(self, session: Path, start: str, end: str) -> SessionUsage | None:
        """The main thread of ONE transcript over the window `(start, end]`.

        Summed over `_distinct_messages` — deduplicated FIRST and windowed
        second, so a message whose content-block records straddle a step
        boundary is charged once, to the step its first record fell in.
        Sidechain records (`isSidechain: true`) are a subagent's and never the
        main session's; a placeholder model (`<synthetic>`) served nothing.

        **Precision.** A transcript timestamp carries milliseconds; a step's
        `at` is whole seconds (`_now()`). The transcript side is truncated to
        the second before the comparison, so a turn at `…:00.9Z` is inside a
        window that closed at `…:00` and outside the next one that opens
        there. `turns` counts distinct message ids. `cost_usd` is `None`:
        Claude Code's transcript reports no cost, and fr computes none.
        """
        records = _read_records(session)
        lower, upper = _to_second(parse_timestamp(start)), _to_second(parse_timestamp(end))
        if records is None or lower is None or upper is None:
            return None

        def in_window(record: Mapping[str, Any]) -> bool:
            if record.get("isSidechain") is True:
                return False
            if not _is_real_model(record["message"].get("model")):
                return False
            stamp = _to_second(parse_timestamp(record.get("timestamp")))
            return stamp is not None and lower < stamp <= upper

        totals = _sum_usage(pair for pair in _distinct_messages(records) if in_window(pair[0]))
        return SessionUsage(**totals.as_fields(), turns=totals.assistant_records)

    def measure_step(
        self,
        env: Mapping[str, str],
        sessions: Sequence[str],
        start: str,
        end: str,
        *,
        directories: Sequence[Path] = (),
    ) -> MainSessionUsage | None:
        """Every candidate session measured and summed; nothing when there is
        no candidate or any one of them cannot be read. `directories` is
        unused: a Claude Code session is found by its id alone."""
        if not sessions:
            return None
        parts: list[SessionUsage] = []
        for session_id in sessions:
            transcript = claude_code_session(env, session_id)
            usage = (
                None if transcript is None else self.measure_main_session(transcript, start, end)
            )
            if usage is None:
                return None
            parts.append(usage)
        return sum_sessions(parts)


_ORCHESTRATOR_TAIL_BYTES = 512 * 1024
"""How far back from the end `orchestrator_model` looks. A live orchestrator
transcript runs to tens of MB and this is read on every `advance`; the last
assistant record is always near the end, so the tail is the whole question."""


def orchestrator_model(env: Mapping[str, str]) -> str | None:
    """The model THIS session's orchestrator is running on right now — the
    `message.model` of the last main-thread assistant record in its transcript
    — or `None` when that cannot be observed.

    2026-09-21 debug journal C3: the orchestrator runs every non-dispatched
    unit (spec-review, plan, review, deliver) and fr recorded no model for any
    of it, on the grounds that it "cannot see" one. It can: the transcript names
    it. Observed, never resolved — a tier binding says what SHOULD run; this
    says what DID, which is the only thing a cursor may record without it being
    a claim. Sidechain (subagent) records are skipped: their model is the
    subagent's. Claude Code only, like the rest of this module; never raises.
    """
    if detect_harness(env) != ClaudeCodeReader.harness:
        return None
    try:
        transcript = claude_code_session(env)
        if transcript is None:
            return None
        with transcript.open("rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - _ORCHESTRATOR_TAIL_BYTES))
            tail = fh.read().decode("utf-8", errors="replace")
    except (OSError, HarnessError):
        return None
    for line in reversed(tail.splitlines()):
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue  # the first line of the tail, or a half-written last one
        if not isinstance(record, dict) or record.get("isSidechain") is True:
            continue
        if _usage_of(record) is None:
            continue
        model = record["message"].get("model")
        if _is_real_model(model):
            return model
    return None


QUESTION_TOOL = "AskUserQuestion"
"""Claude Code's operator-question tool — the one `operator_answered_since`
looks for. Named once, here, beside the only reader that knows its records."""


def operator_answered_since(env: Mapping[str, str], since: str) -> bool | None:
    """Did the operator ANSWER a question in this session at or after `since`?

    `True`/`False` when the transcript was read; `None` when it could not be
    (another harness, no session id, no file) — the caller must be able to tell
    "observed: nobody asked" from "cannot see", because the first refuses a gate
    and the second only degrades loudly (2026-09-21 debug journal C1).

    Answered means BOTH halves, paired by tool_use id: a main-thread assistant
    record with a `QUESTION_TOOL` tool_use stamped at or after `since` (a
    question asked before the gate blocked answered an earlier question), and a
    `tool_result` for it whose `toolUseResult` is an object with a non-empty
    `answers` map. A declined or failed call carries a plain string there
    (captured, `tests/fixtures/transcripts/`), and asking is not answering.
    """
    if detect_harness(env) != ClaudeCodeReader.harness:
        return None
    start = parse_timestamp(since)
    if start is None:
        return None
    try:
        transcript = claude_code_session(env)
    except (OSError, HarnessError):
        return None
    if transcript is None:
        return None
    records = _read_records(transcript)
    if records is None:
        return None
    asked: set[str] = set()
    for record in records:
        if record.get("type") != "assistant" or record.get("isSidechain") is True:
            continue
        stamp = parse_timestamp(record.get("timestamp"))
        if stamp is None or stamp < start:
            continue
        message = record.get("message")
        content = message.get("content") if isinstance(message, Mapping) else None
        for block in content if isinstance(content, list) else ():
            if (
                isinstance(block, Mapping)
                and block.get("type") == "tool_use"
                and block.get("name") == QUESTION_TOOL
                and isinstance(block.get("id"), str)
            ):
                asked.add(block["id"])
    if not asked:
        return False
    for record in records:
        if record.get("type") != "user":
            continue
        result = record.get("toolUseResult")
        if not isinstance(result, Mapping) or not result.get("answers"):
            continue
        message = record.get("message")
        content = message.get("content") if isinstance(message, Mapping) else None
        for block in content if isinstance(content, list) else ():
            if (
                isinstance(block, Mapping)
                and block.get("type") == "tool_result"
                and block.get("tool_use_id") in asked
            ):
                return True
    return False


def _this_session(env: Mapping[str, str]) -> Path | None:
    """This process's own Claude Code session transcript, or `None` when there
    is none to read — another harness included. The shared front half of the
    three "did X happen in this session?" predicates."""
    if detect_harness(env) != ClaudeCodeReader.harness:
        return None
    try:
        return claude_code_session(env)
    except (OSError, HarnessError):
        return None


def subagent_dispatch_since(
    env: Mapping[str, str], agent_id: str, since: str
) -> Dispatch | Literal[False] | None:
    """The dispatch of subagent `agent_id` by THIS session at or after `since`
    — or `False` when the transcript was read and holds none, `None` when it
    could not be read.

    The separate-context review check (2026-09-21 debug journal C6): a review
    unit's `reviewer=<agent-id>` evidence must name a subagent that actually
    ran, and ran after the review unit opened — not the orchestrator's own
    context, which is where the #497 run's "review" was written. Attribution is
    `attribute_dispatches`', the same pairing token measurement already trusts.
    The dispatch is returned (not a bool) so the caller can judge its
    `agent_type`. A dispatch whose start cannot be dated proves nothing about
    the window and does not count. An unreadable transcript is `None`, never
    `False`: "could not read it" is not "nobody was dispatched" (review r1-3).
    """
    start = parse_timestamp(since)
    session = _this_session(env)
    if start is None or session is None or _read_records(session) is None:
        return None
    for dispatch in attribute_dispatches(session):
        if (
            dispatch.agent_id == agent_id
            and dispatch.started is not None
            and dispatch.started >= start
        ):
            return dispatch
    return False


_WRITE_TARGET = re.compile(r"""(?:>>?|\btee(?:\s+-a)?)\s*(["']?)([^\s;&|'"<>]+)\1""")
"""A shell redirect or `tee` and the path it writes. Deliberately syntactic: it
answers "did this command claim to WRITE that file", which a `cat` or `ls` of
the log — accepted before review r1-1 — does not."""


def _writes(command: str, log: Path) -> bool:
    for _quote, target in _WRITE_TARGET.findall(command):
        if Path(target).is_absolute():
            if Path(target) == log:
                return True
        elif str(log).endswith("/" + target.lstrip("./")) or log.name == target:
            return True
    return False


def orchestrator_wrote_since(
    env: Mapping[str, str], log: Path, since: str
) -> list[tuple[_dt.datetime, _dt.datetime]] | None:
    """The run windows `(tool_use, tool_result)` of every main-thread `Bash`
    command, issued at or after `since`, that WROTE `log` (a `>`, `>>` or `tee`
    naming it) and ran to completion (`is_error` not true). `[]` when the
    transcript holds none; `None` when it cannot be read.

    The verification-before-completion check (debug journal C5): `deliver`'s
    `tests=<log>` must be a suite the ORCHESTRATOR ran during delivery, not a
    subagent's report relayed as its own — how the #497 run said "verified
    locally". The caller also requires the file's mtime to fall INSIDE one of
    these windows, which ties the bytes on disk to that command.

    BE HONEST ABOUT THE LIMIT (review r1-1): this proves the orchestrator
    produced the log, in this session, during delivery. It cannot prove the
    command was a real test suite — `echo ok > log` passes. That is forgery,
    not the drift this gate closes (relaying someone else's green), and
    closing it needs a per-repo test-runner declaration fr does not have.
    """
    start = parse_timestamp(since)
    session = _this_session(env)
    if start is None or session is None:
        return None
    records = _read_records(session)
    if records is None:
        return None
    issued: dict[str, _dt.datetime] = {}
    for record in records:
        if record.get("type") != "assistant" or record.get("isSidechain") is True:
            continue
        stamp = parse_timestamp(record.get("timestamp"))
        if stamp is None or stamp < start:
            continue
        message = record.get("message")
        content = message.get("content") if isinstance(message, Mapping) else None
        for block in content if isinstance(content, list) else ():
            if not isinstance(block, Mapping):
                continue
            tool_input = block.get("input")
            command = tool_input.get("command") if isinstance(tool_input, Mapping) else None
            if (
                block.get("type") == "tool_use"
                and block.get("name") == "Bash"
                and isinstance(command, str)
                and isinstance(block.get("id"), str)
                and _writes(command, log)
            ):
                issued[block["id"]] = stamp
    windows: list[tuple[_dt.datetime, _dt.datetime]] = []
    for record in records:
        if record.get("type") != "user" or record.get("isSidechain") is True:
            continue
        done = parse_timestamp(record.get("timestamp"))
        message = record.get("message")
        content = message.get("content") if isinstance(message, Mapping) else None
        for block in content if isinstance(content, list) else ():
            if (
                isinstance(block, Mapping)
                and block.get("type") == "tool_result"
                and block.get("tool_use_id") in issued
                and block.get("is_error") is not True
                and done is not None
            ):
                windows.append((issued[block["tool_use_id"]], done))
    return windows


OPENCODE_DB_ENV = "FR_OPENCODE_DB"
"""Override for OpenCode's session database — the same role
`FR_TRANSCRIPT_ROOT` plays for Claude Code, and what keeps the suite off the
operator's own sessions."""

OPENCODE_DB = Path(".local") / "share" / "opencode" / "opencode.db"
"""Where OpenCode keeps its sessions, under `$HOME`."""


class OpenCodeReader:
    """Main-session usage from OpenCode's SQLite session database (spec §D).

    Read-only by construction: the file is opened with a `mode=ro` URI, so a
    missing database is an error (no measurement), never a new empty file,
    and nothing here can write the harness's own store.

    Dispatch measurement stays `None`, unchanged: `locate_session` finds
    nothing and `measure` measures nothing, so a dispatched unit on OpenCode
    keeps its V1 estimate exactly as before this reader existed.

    **Which session.** OpenCode sessions are never bound automatically —
    `current_session` reads only `CLAUDE_CODE_SESSION_ID` — so the candidates
    are normally the workspace bindings made with `fr isolation attach
    --harness opencode`. With none, `candidate_sessions` falls back to the
    UNIQUE top-level session in the run's workspace or base clone that has
    assistant messages in the window; more than one means nothing is
    recorded, never a guess.
    """

    harness = "opencode"

    def database(self, env: Mapping[str, str]) -> Path:
        override = env.get(OPENCODE_DB_ENV)
        return Path(override) if override else Path.home() / OPENCODE_DB

    def locate_session(self, env: Mapping[str, str], session: str | None = None) -> Path | None:
        return None

    def measure(
        self,
        session: Path,
        *,
        agent: str | None = None,
        start: str,
        end: str,
        same_session: bool = True,
    ) -> Measurement | None:
        return None

    def measure_main_session(
        self, db: Path, session: str, start: str, end: str
    ) -> SessionUsage | None:
        """One session's assistant messages over `(start, end]`, or `None`
        when the database or the session cannot be read.

        Tokens are `opencode_tokens`' mapping (reasoning folded into
        output). `cost_usd` sums `data.cost`, OpenCode's own figure. The
        window compares `time_created` (epoch milliseconds) truncated to the
        second, the same precision rule as Claude Code's.
        """
        bounds = _epoch_window(start, end)
        if bounds is None:
            return None
        try:
            with closing(_open_ro(db)) as con:
                if con.execute("SELECT 1 FROM session WHERE id = ?", (session,)).fetchone() is None:
                    return None
                rows = con.execute(
                    "SELECT data FROM message WHERE session_id = ? "
                    "AND time_created / 1000 > ? AND time_created / 1000 <= ?",
                    (session, *bounds),
                ).fetchall()
        except sqlite3.Error:
            return None
        figures = dict.fromkeys(USAGE_KEYS, 0)
        turns = 0
        cost = 0.0
        for (raw,) in rows:
            try:
                data = json.loads(raw)
            except (TypeError, json.JSONDecodeError):
                continue
            if not isinstance(data, Mapping) or data.get("role") != "assistant":
                continue
            for key, count in opencode_tokens(data).items():
                figures[key] += count
            value = data.get("cost")
            if isinstance(value, int | float) and not isinstance(value, bool):
                cost += float(value)
            turns += 1
        return SessionUsage(**figures, turns=turns, cost_usd=cost)

    def candidate_sessions(
        self, db: Path, directories: Sequence[Path], start: str, end: str
    ) -> list[str]:
        """Top-level sessions (`parent_id IS NULL` — a child is a subagent's)
        whose `directory` is one of `directories` and which have an assistant
        message in `(start, end]`. `[]` when the database cannot be read."""
        bounds = _epoch_window(start, end)
        places = sorted({str(d) for d in directories} | {str(d.resolve()) for d in directories})
        if bounds is None or not places:
            return []
        marks = ", ".join("?" for _ in places)
        try:
            with closing(_open_ro(db)) as con:
                rows = con.execute(
                    f"SELECT s.id FROM session s WHERE s.parent_id IS NULL "  # noqa: S608 — placeholders only
                    f"AND s.directory IN ({marks}) AND EXISTS (SELECT 1 FROM message m "
                    "WHERE m.session_id = s.id AND m.time_created / 1000 > ? "
                    "AND m.time_created / 1000 <= ? "
                    "AND json_extract(m.data, '$.role') = 'assistant') ORDER BY s.id",
                    (*places, *bounds),
                ).fetchall()
        except sqlite3.Error:
            return []
        return [row[0] for row in rows]

    def measure_step(
        self,
        env: Mapping[str, str],
        sessions: Sequence[str],
        start: str,
        end: str,
        *,
        directories: Sequence[Path] = (),
    ) -> MainSessionUsage | None:
        """The bound sessions summed — or, with none bound, the unique
        qualifying top-level session. Any unreadable session, or an ambiguous
        fallback, records nothing."""
        db = self.database(env)
        if not sessions:
            found = self.candidate_sessions(db, directories, start, end)
            if len(found) != 1:
                return None
            sessions = found
        parts: list[SessionUsage] = []
        for session in sessions:
            usage = self.measure_main_session(db, session, start, end)
            if usage is None:
                return None
            parts.append(usage)
        return sum_sessions(parts)


def opencode_tokens(data: Mapping[str, Any]) -> dict[str, int]:
    """One OpenCode assistant message's `data.tokens`, as fr's four figures.

    `input` -> `input_tokens`, `cache.write` -> `cache_creation_input_tokens`,
    `cache.read` -> `cache_read_input_tokens`, and **`output + reasoning` ->
    `output_tokens`**: reasoning is billed as output, and fr records the same
    four figures for every harness rather than a fifth only OpenCode fills.
    `tokens.total` is not read — it is the sum of the others. A missing or
    non-integer field counts 0.
    """
    raw_tokens = data.get("tokens")
    tokens: Mapping[str, Any] = raw_tokens if isinstance(raw_tokens, Mapping) else {}
    raw_cache = tokens.get("cache")
    cache: Mapping[str, Any] = raw_cache if isinstance(raw_cache, Mapping) else {}
    return {
        "input_tokens": _count(tokens.get("input")),
        "cache_creation_input_tokens": _count(cache.get("write")),
        "cache_read_input_tokens": _count(cache.get("read")),
        "output_tokens": _count(tokens.get("output")) + _count(tokens.get("reasoning")),
    }


def _count(value: object) -> int:
    """A token count, or 0 — a boolean is not a count."""
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _epoch_window(start: str, end: str) -> tuple[int, int] | None:
    """`(start, end]` as whole epoch seconds, or `None` if either is unparseable."""
    lower, upper = parse_timestamp(start), parse_timestamp(end)
    if lower is None or upper is None:
        return None
    return int(lower.timestamp()), int(upper.timestamp())


def _open_ro(db: Path) -> sqlite3.Connection:
    """`db` opened read-only; raises `sqlite3.Error` when it does not exist."""
    return sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True)


READERS: Mapping[str, TranscriptReader] = {
    ClaudeCodeReader.harness: ClaudeCodeReader(),
    OpenCodeReader.harness: OpenCodeReader(),
}
"""Harness key -> reader. Deliberately not a fallback-to-Claude-Code default:
an unlisted harness (Hermes) measures NOTHING, which `fr run status` then says out loud,
rather than parsing another harness's transcripts with this one's rules."""


def reader_for(harness: str | None) -> TranscriptReader | None:
    """The reader for `harness`, or `None` when that harness has none."""
    if harness is None:
        return None
    return READERS.get(harness)


def measure_dispatch(
    session: Path,
    *,
    agent: str | None = None,
    start: str,
    end: str,
    same_session: bool = True,
) -> Measurement | None:
    """Read + attribute: what one attempt of `session` cost.

    `None` at every step that cannot be completed honestly — no session file,
    no attributable dispatch, an unmatched agent id, an ambiguous window, a
    window this session may not use, an unreadable transcript. The caller
    records nothing and says so.
    """
    dispatch = select_for_attempt(
        attribute_dispatches(session),
        agent=agent,
        start=start,
        end=end,
        same_session=same_session,
    )
    if dispatch is None:
        return None
    totals = read_claude_code(dispatch.transcript)
    if totals is None:
        return None
    return Measurement(
        harness=ClaudeCodeReader.harness,
        tool_use_id=dispatch.tool_use_id,
        totals=totals,
        agent_type=dispatch.agent_type,
        model=dispatch.model,
    )


def measure_attempt(
    env: Mapping[str, str],
    *,
    session: str | None,
    agent: str | None,
    start: str,
    end: str,
) -> Measurement | None:
    """The whole path, from one ATTEMPT's four facts to numbers — or `None`.

    `(session, agent)` is the attempt's own identity as `fr run advance`
    recorded it, and `[start, end]` is its own `[dispatched, returned]`
    window. Three things follow, all of them §4.D.1:

    1. the transcript is looked up in the **recorded** session's directory,
       not this process's — so a new session on the same host still measures
       an earlier session's attempt;
    2. another host has no such directory, so the answer is honestly nothing;
    3. the window is offered to `select_for_attempt` only with the proof of
       whether the recorded session IS this one. The decision itself lives
       there, once.

    Never raises: telemetry is observability, and an unreadable transcript
    must not be able to fail a dispatch or a resolve.
    """
    try:
        reader = reader_for(detect_harness(env))
        if reader is None:
            return None
        transcript = reader.locate_session(env, session)
        if transcript is None:
            return None
        return reader.measure(
            transcript,
            agent=agent,
            start=start,
            end=end,
            same_session=dispatched_from_this_session(env, session),
        )
    except (OSError, HarnessError):
        # `detect_harness` RAISES on an `FR_HARNESS` value outside the closed
        # set — correct there (a typo must not become an inference) and wrong
        # here: a mistyped env var would fail `fr run resolve`, so a telemetry
        # read could break execution. Observability degrades; it never raises.
        return None


# --- 4. main-session cost per step (spec 2026-09-24 §D) --------------------

_BINDING_HARNESSES: Mapping[str, frozenset[str]] = {
    ClaudeCodeReader.harness: frozenset({"claude", "claude-code", "unknown"}),
    "opencode": frozenset({"opencode"}),
}
"""Which `SessionBinding.harness` values name a session of each reader's
harness. `fr isolation attach --harness` defaults to `unknown`, and every
default-bound session so far has been Claude Code's, so `unknown` is read as
Claude Code's — never as OpenCode's, whose sessions are bound only explicitly."""


def _isolation_state(state: RunState, repo_root: Path) -> IsolationState | None:
    """The run branch's workspace record, or `None` — no workspace, not a git
    repository, or an unreadable record all mean "no bindings", never a
    failure: a binding is traceability, not evidence a session exists."""
    from fr.isolation.types import load_state

    try:
        return load_state(repo_root, state.branch)
    except Exception:  # noqa: BLE001 — observability degrades, never raises
        return None


def candidate_sessions(
    state: RunState,
    env: Mapping[str, str],
    repo_root: Path,
    *,
    harness: str | None = ClaudeCodeReader.harness,
) -> list[str]:
    """Every session whose main thread may hold this run's turns (spec §D),
    first-seen order, no repeats:

    1. every distinct `Attempt.session` recorded on the run;
    2. every session the workspace binding for `state.branch` lists
       (`fr isolation attach` / `up --session`) whose harness is `harness`'s;
    3. this process's own session.

    (1) and (3) are Claude Code session ids — `current_session` reads only
    `CLAUDE_CODE_SESSION_ID`, and `fr run advance` records what it returns —
    so for any other harness only (2) is a candidate.
    """
    found: list[str] = []

    def add(session: str | None) -> None:
        if session and session not in found:
            found.append(session)

    claude = harness == ClaudeCodeReader.harness
    if claude:
        for record in state.steps.values():
            for unit in (record.units or {}).values():
                for attempt in unit.attempts:
                    add(attempt.session)
    workspace = _isolation_state(state, repo_root)
    accepted = _BINDING_HARNESSES.get(harness or "", frozenset())
    for binding in workspace.sessions if workspace is not None else ():
        if binding.harness in accepted:
            add(binding.session_id)
    if claude:
        add(current_session(env))
    return found


def measure_step_main_session(
    state: RunState,
    env: Mapping[str, str],
    repo_root: Path,
    start: str,
    end: str,
) -> MainSessionUsage | None:
    """What the main session(s) burned over one top-level step's window
    `(start, end]` — or `None` when that is not observable here.

    The window is the caller's (`fr.commands.run_cmd._complete_step`): from
    the previous top-level step's `at`, or the run's `started` for the first,
    to this step's `at`. Turns taken before `fr run start` belong to no step
    and are never measured. Measuring the STEP rather than an attempt is what
    covers `brainstorm`, which has no attempt, and the whole `implement` loop.

    Never raises — a completion must not fail because a transcript could not
    be read — and never returns a partial sum (gh#514).
    """
    try:
        harness = detect_harness(env)
        reader = reader_for(harness)
        if reader is None:
            return None
        workspace = _isolation_state(state, repo_root)
        directories = [repo_root]
        if workspace is not None:
            directories += [workspace.worktree, workspace.repo_root]
        return reader.measure_step(
            env,
            candidate_sessions(state, env, repo_root, harness=harness),
            start,
            end,
            directories=directories,
        )
    except Exception:  # noqa: BLE001 — telemetry is observability; it never raises
        return None


__all__ = [
    "READERS",
    "USAGE_KEYS",
    "ClaudeCodeReader",
    "SessionUsage",
    "Dispatch",
    "Measurement",
    "OpenCodeReader",
    "TranscriptReader",
    "UsageTotals",
    "attribute_dispatches",
    "candidate_sessions",
    "claude_code_session",
    "current_session",
    "dispatched_from_this_session",
    "measure_attempt",
    "measure_dispatch",
    "measure_step_main_session",
    "parse_timestamp",
    "read_claude_code",
    "reader_for",
    "select_dispatch",
    "select_for_attempt",
    "session_dir",
    "sum_sessions",
    "tool_use_ids",
    "transcript_root",
]
