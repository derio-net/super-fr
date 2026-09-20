"""Measured tokens from a harness's own transcript — spec §5.C (V2 telemetry).

Two jobs, kept apart on purpose:

1. **Reading** — parse one transcript file into token numbers. It takes a
   path, selects `type == "assistant"` records, PROJECTS `message.usage` onto
   the four named keys, and returns a sum. It knows nothing about phases,
   runs, agents or fr-goal.
2. **Attributing** — decide which dispatched unit a transcript belongs to. It
   takes a session file and a time window and returns at most one dispatch.
   This half is the fr-goal-shaped one.

`measure_unit` is the only place they meet.

**No harness API is called.** Everything here reads files the harness already
writes. Claude Code is the one implementation; OpenCode and Hermes keep the V1
estimates until their readers land (`reader_for` returns `None` for them, which
is what makes the degradation loud rather than silent).

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
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from fr.harness.detect import detect_harness
from fr.harness.model import HarnessError

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

    @property
    def total(self) -> int:
        return (
            self.input_tokens
            + self.cache_creation_input_tokens
            + self.cache_read_input_tokens
            + self.output_tokens
        )

    def as_fields(self) -> dict[str, int]:
        """The four figures, keyed as `PhaseAccounting` names them."""
        return {key: getattr(self, key) for key in USAGE_KEYS}


def _read_records(path: Path) -> list[dict[str, Any]] | None:
    """Every complete JSON record of a `.jsonl`, or `None` if unreadable.

    A transcript is appended to live, so the final line can be half-written;
    an incomplete line is skipped rather than failing the file. A file with
    NO complete record is unreadable — not an empty measurement — because
    there is no evidence it is a transcript at all.
    """
    try:
        text = path.read_text()
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


def read_claude_code(path: Path) -> UsageTotals | None:
    """Summed usage for one Claude Code transcript, or `None` for *no
    measurement* (the file is missing, unreadable, or holds no record).

    Works on either file of the pair — the orchestrator's own stream or one
    subagent's — because both are the same record format. Deciding WHICH file
    answers for a given unit is the other half of this module's job, below.
    """
    records = _read_records(path)
    if records is None:
        return None
    totals = dict.fromkeys(USAGE_KEYS, 0)
    seen = 0
    for record in records:
        usage = _usage_of(record)
        if usage is None:
            continue
        seen += 1
        for key in USAGE_KEYS:
            value = usage.get(key)
            # `isinstance(True, int)` is True in Python; a boolean is not a count.
            if isinstance(value, int) and not isinstance(value, bool):
                totals[key] += value
    return UsageTotals(**totals, assistant_records=seen)


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
            meta = json.loads(meta_path.read_text())
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


# --- 3. harness scoping --------------------------------------------------


class TranscriptReader(Protocol):
    """What a harness must offer for fr to measure a unit. One implementation
    exists; the Protocol is here so the second one cannot quietly acquire a
    different shape."""

    harness: str

    def locate_session(self, env: Mapping[str, str]) -> Path | None:
        """The orchestrator transcript for this process's session, if findable."""

    def measure(self, session: Path, *, start: str, end: str) -> Measurement | None:
        """What the unit dispatched inside `[start, end]` cost, if measurable."""


def transcript_root(env: Mapping[str, str]) -> Path:
    override = env.get(TRANSCRIPT_ROOT_ENV)
    if override:
        return Path(override)
    return Path.home() / CLAUDE_CODE_PROJECTS


def claude_code_session(env: Mapping[str, str]) -> Path | None:
    """`<root>/<cwd-slug>/<session-id>.jsonl`, found by session id.

    The project directory is named after the harness's LAUNCH directory, which
    is not derivable from fr's own working directory (fr runs inside the
    worktree; the harness was launched in the base clone), so the id is
    matched across every project directory instead of guessing the slug.
    More than one match is ambiguous and yields nothing.
    """
    session_id = env.get(SESSION_ID_ENV)
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

    def locate_session(self, env: Mapping[str, str]) -> Path | None:
        return claude_code_session(env)

    def measure(self, session: Path, *, start: str, end: str) -> Measurement | None:
        return measure_dispatch(session, start=start, end=end)


READERS: Mapping[str, TranscriptReader] = {ClaudeCodeReader.harness: ClaudeCodeReader()}
"""Harness key -> reader. Deliberately not a fallback-to-Claude-Code default:
an unlisted harness measures NOTHING, which `fr run status` then says out loud,
rather than parsing another harness's transcripts with this one's rules."""


def reader_for(harness: str | None) -> TranscriptReader | None:
    """The reader for `harness`, or `None` when that harness has none."""
    if harness is None:
        return None
    return READERS.get(harness)


def measure_dispatch(session: Path, *, start: str, end: str) -> Measurement | None:
    """Read + attribute: what the unit dispatched inside `[start, end]` cost.

    `None` at every step that cannot be completed honestly — no session file,
    no attributable dispatch, an ambiguous window, an unreadable transcript.
    The caller records nothing and says so.
    """
    dispatch = select_dispatch(attribute_dispatches(session), start=start, end=end)
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


def measure_unit(env: Mapping[str, str], *, start: str, end: str) -> Measurement | None:
    """The whole path, from a process environment to numbers — or `None`.

    Never raises: telemetry is observability, and an unreadable transcript
    must not be able to fail a dispatch or a resolve.
    """
    try:
        reader = reader_for(detect_harness(env))
        if reader is None:
            return None
        session = reader.locate_session(env)
        if session is None:
            return None
        return reader.measure(session, start=start, end=end)
    except (OSError, HarnessError):
        # `detect_harness` RAISES on an `FR_HARNESS` value outside the closed
        # set — correct there (a typo must not become an inference) and wrong
        # here: a mistyped env var would fail `fr run resolve`, so a telemetry
        # read could break execution. Observability degrades; it never raises.
        return None


__all__ = [
    "READERS",
    "USAGE_KEYS",
    "ClaudeCodeReader",
    "Dispatch",
    "Measurement",
    "TranscriptReader",
    "UsageTotals",
    "attribute_dispatches",
    "claude_code_session",
    "measure_dispatch",
    "measure_unit",
    "parse_timestamp",
    "read_claude_code",
    "reader_for",
    "select_dispatch",
    "session_dir",
    "tool_use_ids",
    "transcript_root",
]
