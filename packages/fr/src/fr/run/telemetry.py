"""Reading a harness's own transcript — the primitives `fr.usage` and the
transcript gates share (spec §5.C, V2 telemetry).

Per-attempt token MEASUREMENT (`measure_attempt`, `measure_dispatch`,
`TranscriptReader.measure` and the attribution rule they drove) was removed
after run v7 moved usage out of the cursor into `fr.usage` (phase-2 review
p2-r27): nothing called it. What stays:

- the tolerant transcript reader (`_read_records`) and the #597 dedupe
  (`message_groups`), which `fr.usage.readers.claude_code` builds on;
- file-to-file dispatch attribution (`attribute_dispatches`), which the
  separate-context review check (`subagent_dispatch_since`) relies on;
- session location and the transcript gates (`orchestrator_model`,
  `operator_answered_since`, `orchestrator_wrote_since`), each returning
  `None` for "could not read", never `False`.

**No harness API is called.** Everything here reads files the harness already
writes.

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
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal, TypeGuard

from fr.harness.detect import detect_harness
from fr.harness.model import HarnessError

CLAUDE_CODE_PROJECTS = Path(".claude") / "projects"
"""Where Claude Code writes transcripts, under `$HOME`."""

TRANSCRIPT_ROOT_ENV = "FR_TRANSCRIPT_ROOT"
"""Override for that root — the whole of this module's configuration surface,
and what keeps the test suite off the operator's own transcripts."""

UNOBSERVED = "unobserved"
"""The evidence key a resolve records when a transcript gate could not
observe (spec 2026-09-25-lean-cost-aware-process §5.B.7): its value names the
gates, comma-separated. Every gate helper below returns `None` for "could not
read", never `False`, so the caller can tell the two apart."""

SESSION_ID_ENV = "CLAUDE_CODE_SESSION_ID"
"""Set in every Claude Code tool call. Verified live (2026-09-20) from inside
a dispatched subagent: the value there is the ORCHESTRATOR's session id, which
is exactly what this module needs — the orchestrator's file is where the
dispatch tool_use ids live."""


# --- 1. reading: a path in, numbers out ----------------------------------


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


def message_groups(
    records: list[dict[str, Any]],
) -> list[tuple[dict[str, Any], Mapping[str, Any], list[dict[str, Any]]]]:
    """`(first record, usage, every record of that message)` per `message.id`.

    The one dedupe rule (first occurrence of an id wins its usage; a record
    with no id stands alone), returning as well
    the later records of the same message, which carry the message's later
    CONTENT BLOCKS — a tool_use is usually written on a record after the
    one whose usage wins. `fr.usage.readers.claude_code` needs those blocks
    to know what a message did; a sum needs only the first record.
    """
    groups: list[tuple[dict[str, Any], Mapping[str, Any], list[dict[str, Any]]]] = []
    by_id: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        usage = _usage_of(record)
        if usage is None:
            continue
        # `_usage_of` already proved `message` is a Mapping.
        message_id = record["message"].get("id")
        if isinstance(message_id, str) and message_id:
            if message_id in by_id:
                by_id[message_id].append(record)
                continue
            blocks = [record]
            by_id[message_id] = blocks
        else:
            blocks = [record]
        groups.append((record, usage, blocks))
    return groups


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


# --- 3. harness scoping --------------------------------------------------


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

    Exactly "at least one answered round": a round counts when any of its calls
    was answered, so the two readings cannot drift apart.
    """
    rounds = answered_rounds_since(env, since)
    return None if rounds is None else bool(rounds)


ROUND_NEUTRAL_TOOLS = frozenset({"TodoWrite", "TaskCreate", "TaskUpdate", "TaskList", "TaskGet"})
"""Tools whose tool_use does NOT close a question round (review p2-r8).

These are Claude Code's own progress-tracking tools; they read or write no
project state, so they are not the cross-examination that separates rounds. Any
other tool (Read, Bash, Grep, Agent and so on) still closes a round — without
this exception, a bookkeeping call between two question batches would split one
round into two and, under the never-a-round-3 refusal, could strand a gate."""


@dataclass(frozen=True)
class Round:
    """One operator question round (spec 2026-09-26 §3.C): a maximal run of
    main-thread `QUESTION_TOOL` calls with no other tool_use between them
    (`ROUND_NEUTRAL_TOOLS` excepted). Only answered rounds are ever built.

    `question_texts` holds every `questions[].question` and `header` of its
    calls, in order — where a `Round 1 of 2` announcement is looked for.
    """

    question_texts: tuple[str, ...]


def answered_rounds_since(env: Mapping[str, str], since: str) -> list[Round] | None:
    """The ANSWERED question rounds of this session at or after `since`, in
    order; `None` exactly where `operator_answered_since` is `None` (another
    harness, no session id, no readable transcript).

    Only main-thread (non-sidechain) assistant records stamped at or after
    `since` are walked. Consecutive `QUESTION_TOOL` tool_uses form one round —
    text-only turns, the calls' own tool_results and `ROUND_NEUTRAL_TOOLS` calls
    do not break it, so a batch larger than the tool's per-call limit stays ONE
    round; any other tool_use closes it. A round is answered when any of its
    calls has a `tool_result` whose `toolUseResult` carries a non-empty
    `answers` map; a round that was only declined is not returned.
    """
    start = parse_timestamp(since)
    transcript = _this_session(env)
    if start is None or transcript is None:
        return None
    records = _read_records(transcript)
    if records is None:
        return None
    groups: list[tuple[list[str], list[str]]] = []  # (tool_use ids, question texts)
    open_group: tuple[list[str], list[str]] | None = None
    for record in records:
        if record.get("type") != "assistant" or record.get("isSidechain") is True:
            continue
        stamp = parse_timestamp(record.get("timestamp"))
        if stamp is None or stamp < start:
            continue
        message = record.get("message")
        content = message.get("content") if isinstance(message, Mapping) else None
        for block in content if isinstance(content, list) else ():
            if not isinstance(block, Mapping) or block.get("type") != "tool_use":
                continue
            if block.get("name") in ROUND_NEUTRAL_TOOLS:
                continue
            if block.get("name") != QUESTION_TOOL or not isinstance(block.get("id"), str):
                open_group = None
                continue
            if open_group is None:
                open_group = ([], [])
                groups.append(open_group)
            open_group[0].append(block["id"])
            open_group[1].extend(_question_texts(block.get("input")))
    if not groups:
        return []
    answered = _answered_ids(records)
    return [
        Round(question_texts=tuple(texts))
        for ids, texts in groups
        if any(i in answered for i in ids)
    ]


def _question_texts(tool_input: object) -> list[str]:
    """Every `question` and `header` string of one `QUESTION_TOOL` call's input."""
    questions = tool_input.get("questions") if isinstance(tool_input, Mapping) else None
    texts: list[str] = []
    for question in questions if isinstance(questions, list) else ():
        if not isinstance(question, Mapping):
            continue
        for key in ("question", "header"):
            value = question.get(key)
            if isinstance(value, str):
                texts.append(value)
    return texts


def _answered_ids(records: list[dict[str, Any]]) -> set[str]:
    """The tool_use ids whose `tool_result` carries a non-empty `answers` map."""
    answered: set[str] = set()
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
                and isinstance(block.get("tool_use_id"), str)
            ):
                answered.add(block["tool_use_id"])
    return answered


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
    `attribute_dispatches`' exact tool_use-id pairing.
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
the log — accepted before review r1-1 — does not.

A relative target is compared by path SEGMENTS (gh#606): it matches when its
segments, `.` dropped, are the trailing segments of the log's. Leading `..`
segments are dropped too, deliberately: the command's cwd is not in the
transcript, so a parent hop cannot be resolved, and `../x.log` keeps matching
`…/x.log` as it always has. A `..` mid-path is not collapsed and fails closed."""


_ASSIGNMENT = re.compile(
    r"""(?:\A|[;\n]|&&|\|\|)[ \t]*(?:(?:export|declare(?:[ \t]+-\w+)*)[ \t]+)?"""
    r"""([A-Za-z_]\w*)=("[^"]*"|'[^']*'|[^\s;&|]*)(?=[ \t]*(?:\Z|[;&|\n]))"""
)
"""A `NAME=value` that is a whole command of its own: at the start of the string
or after `;`, `&&`, `||` or a newline, optionally behind `export`/`declare`,
and followed by a command separator or the end. NOT recognised (fail closed,
review F3): a prefix assignment that scopes to the next word (`L=x pytest >
$L` leaves `$L` unset), and anything inside quotes or a here-doc body."""
_QUOTED = re.compile(r"""\"(?:\\.|[^"\\])*\"|'[^']*'""", re.DOTALL)
_HEREDOC = re.compile(
    r"""<<-?[ \t]*(['"]?)(\w+)\1[^\n]*\n(.*?)\n[ \t]*\2[ \t]*(?:\n|\Z)""", re.DOTALL
)


def _assignments(command: str) -> list[tuple[int, str, str]]:
    """`(end, name, value)` of each command-start assignment in `command` that
    does not sit inside a quoted string or a here-doc body."""
    scratch = command
    protected: list[tuple[int, int]] = []
    for doc in _HEREDOC.finditer(command):
        protected.append(doc.span(3))
        scratch = (
            scratch[: doc.start(3)] + " " * (doc.end(3) - doc.start(3)) + scratch[doc.end(3) :]
        )
    protected += [m.span() for m in _QUOTED.finditer(scratch)]
    found = []
    for m in _ASSIGNMENT.finditer(command):
        at = m.start(1)
        if any(start <= at < end for start, end in protected):
            continue
        found.append((m.end(), m.group(1), m.group(2)))
    return found


_VARIABLE = re.compile(r"\$(?:\{([A-Za-z_]\w*)\}|([A-Za-z_]\w*))")
_SUBSTITUTION_ROUNDS = 5


def _resolve_target(target: str, assignments: list[tuple[int, str, str]], at: int) -> str | None:
    """`target` with same-command variables substituted (spec §3.B). Only
    assignments that END before `at` (the redirect) count. A variable still
    unresolved is dropped when it LEADS the path — the environment root is as
    unknowable from the transcript as the cwd — and anything else (mid-path,
    the whole target, a command substitution) is `None`: fail closed."""
    known = {name: value.strip("\"'") for end, name, value in assignments if end <= at}
    for _ in range(_SUBSTITUTION_ROUNDS):
        replaced = _VARIABLE.sub(lambda m: known.get(m.group(1) or m.group(2), m.group(0)), target)
        if replaced == target:
            break
        target = replaced
    lead = _VARIABLE.match(target)
    if lead:
        target = target[lead.end() :]
        if not target.startswith("/") or target == "/":
            return None
        target = target.lstrip("/")
    return None if "$" in target or "(" in target or "`" in target else target


def _writes(command: str, log: Path) -> bool:
    assignments = _assignments(command)
    for match in _WRITE_TARGET.finditer(command):
        target = _resolve_target(match.group(2), assignments, match.start())
        if target is None:
            continue
        if Path(target).is_absolute():
            if Path(target) == log:
                return True
            continue
        parts = PurePosixPath(target).parts
        while parts and parts[0] == "..":
            parts = parts[1:]
        if parts and log.parts[-len(parts) :] == parts:
            return True
    return False


_BACKGROUND_ACKS = ("Command running in background", "Command did not complete within its")
_NOTIFIED_ID = re.compile(r"<tool-use-id>\s*([^<\s]+)\s*</tool-use-id>")
_NOTIFIED_STATUS = re.compile(r"<status>([^<]*)</status>")
_NOTIFIED_SUMMARY = re.compile(r"<summary>(.*?)</summary>", re.DOTALL)
_NOTIFIED_EXIT = re.compile(r"\bexit code (-?\d+)\)?\s*$")


def _text_of(content: object) -> str:
    """A message/tool_result `content` as text: a plain string, or a list of
    `text` blocks (both shapes occur)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            b["text"]
            for b in content
            if isinstance(b, Mapping) and b.get("type") == "text" and isinstance(b.get("text"), str)
        )
    return ""


def _notification_text(record: Mapping[str, Any]) -> str | None:
    """The `<task-notification>` text of a main-thread record, in either shape
    Claude Code writes it (both observed live): a `type: user` record with
    `origin.kind: task-notification`, or a `type: attachment` record carrying a
    `queued_command` in `commandMode: task-notification` whose `prompt` is the
    text. Sidechain records are never the orchestrator's."""
    if record.get("isSidechain") is True:
        return None
    if record.get("type") == "user":
        origin = record.get("origin")
        if not isinstance(origin, Mapping) or origin.get("kind") != "task-notification":
            return None
        message = record.get("message")
        return _text_of(message.get("content") if isinstance(message, Mapping) else None)
    if record.get("type") == "attachment":
        attachment = record.get("attachment")
        if (
            isinstance(attachment, Mapping)
            and attachment.get("type") == "queued_command"
            and attachment.get("commandMode") == "task-notification"
        ):
            return _text_of(attachment.get("prompt"))
    return None


def _successful_notification(record: Mapping[str, Any]) -> str | None:
    """The tool_use id a `task-notification` record reports as COMPLETED with no
    non-zero exit code, else `None` (spec §3.A). The exit code is the one that
    ENDS the `<summary>` (`... completed (exit code 0)`), so a description the
    model wrote cannot fake or hide it."""
    text = _notification_text(record)
    if text is None:
        return None
    ident, status = _NOTIFIED_ID.search(text), _NOTIFIED_STATUS.search(text)
    if not ident or not status or status.group(1).strip() != "completed":
        return None
    summary = _NOTIFIED_SUMMARY.search(text)
    code = _NOTIFIED_EXIT.search(summary.group(1).strip()) if summary else None
    if code and code.group(1) != "0":
        return None
    return ident.group(1)


def _is_background_ack(record: Mapping[str, Any], text: str) -> bool:
    """Whether a `Bash` tool_result says the command was moved to the background,
    either because it asked for `run_in_background` or because a foreground call
    hit its timeout (spec §3.A). Claude Code sets `toolUseResult.backgroundTaskId`
    on BOTH acks (187 of 187 in real transcripts, none without), so it decides
    when `toolUseResult` is an object — and its id must appear in the text, which
    keeps a record carrying several results honest. A foreground command that
    merely echoes the phrase has an object without the key: not background. Only
    when there is no object at all (an older harness) is the text prefix used."""
    result = record.get("toolUseResult")
    if isinstance(result, Mapping):
        task = result.get("backgroundTaskId")
        return isinstance(task, str) and bool(task) and task in text
    return text.startswith(_BACKGROUND_ACKS) and "background" in text[:120]


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

    Claude Code reads this session's transcript; OpenCode reads its session
    database (`_opencode_wrote_since`, gh#638). Any other harness is `None`.

    BE HONEST ABOUT THE LIMIT (review r1-1): this proves the orchestrator
    produced the log, in this session, during delivery. It cannot prove the
    command was a real test suite — `echo ok > log` passes. That is forgery,
    not the drift this gate closes (relaying someone else's green), and
    closing it needs a per-repo test-runner declaration fr does not have.

    A window may END at a `task-notification` (a backgrounded command: an
    explicit `run_in_background`, or a foreground call moved to the background
    by its timeout), stamped when the harness RECORDED the notification — at or
    after the command finished. A background window can therefore span most of
    the run, so any process that writes the log during it satisfies the mtime
    check: the same documented `echo ok > log` limit, not a new hole.
    """
    start = parse_timestamp(since)
    if start is not None and detect_harness(env) == OpenCodeReader.harness:
        return _opencode_wrote_since(env, log, start)
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
    background: set[str] = set()
    closed: set[str] = set()
    for record in records:
        done = parse_timestamp(record.get("timestamp"))
        finished = _successful_notification(record)
        if finished is not None:
            if finished in background and finished not in closed and done is not None:
                closed.add(finished)
                windows.append((issued[finished], done))
            continue
        if record.get("type") != "user" or record.get("isSidechain") is True:
            continue
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
                if _is_background_ack(record, _text_of(block.get("content"))):
                    background.add(block["tool_use_id"])
                else:
                    windows.append((issued[block["tool_use_id"]], done))
    return windows


OPENCODE_DB_ENV = "FR_OPENCODE_DB"
"""Override for OpenCode's session database — the same role
`FR_TRANSCRIPT_ROOT` plays for Claude Code, and what keeps the suite off the
operator's own sessions."""

OPENCODE_DB = Path(".local") / "share" / "opencode" / "opencode.db"
"""Where OpenCode keeps its sessions, under `$HOME`."""


class OpenCodeReader:
    """Where OpenCode's SQLite session database lives (`database`) — read by
    `fr.usage.readers.opencode`, opened read-only there."""

    harness = "opencode"

    def database(self, env: Mapping[str, str]) -> Path:
        override = env.get(OPENCODE_DB_ENV)
        return Path(override) if override else Path.home() / OPENCODE_DB


def _ms_to_dt(value: object) -> _dt.datetime | None:
    if not isinstance(value, int | float) or isinstance(value, bool):
        return None
    return _dt.datetime.fromtimestamp(value / 1000, tz=_dt.UTC)


def _opencode_wrote_since(
    env: Mapping[str, str], log: Path, start: _dt.datetime
) -> list[tuple[_dt.datetime, _dt.datetime]] | None:
    """`orchestrator_wrote_since` over OpenCode's database (gh#638): the
    `(start, end)` of every `bash` tool part that WROTE `log`, started at or
    after `start`, completed with exit 0 — in a TOP-LEVEL session, the
    orchestrator's (a `task` subagent is a child session, `parent_id` set).
    `None` when the database cannot be read.

    Before this, OpenCode had no reader, so the gate degraded to "a fresh,
    non-empty file" and accepted a log the agent composed with its edit tool.

    No OpenCode session id reaches fr's environment, so this cannot pin THE
    session the way the Claude Code reader does: any top-level session active
    since the unit opened counts. Weaker than one session, still proof that an
    orchestrator's own shell command produced the bytes — which is the drift
    this gate closes. Exit 0 stands in for Claude Code's `is_error`, which a
    non-zero exit sets.
    """
    import sqlite3
    from contextlib import closing

    from fr.usage.readers.opencode import open_ro

    since_ms = int(start.timestamp() * 1000)
    try:
        with closing(open_ro(OpenCodeReader().database(env))) as con:
            rows = con.execute(
                "SELECT p.data FROM part p JOIN session s ON s.id = p.session_id "
                "WHERE s.parent_id IS NULL AND p.time_updated >= ?",
                (since_ms,),
            ).fetchall()
    except sqlite3.Error:
        return None
    windows: list[tuple[_dt.datetime, _dt.datetime]] = []
    for (raw,) in rows:
        try:
            part = json.loads(raw) if isinstance(raw, str | bytes) else None
        except json.JSONDecodeError:
            continue
        if not isinstance(part, Mapping) or part.get("tool") != "bash":
            continue
        state = part.get("state")
        state = state if isinstance(state, Mapping) else {}
        tool_input = state.get("input")
        command = tool_input.get("command") if isinstance(tool_input, Mapping) else None
        meta = state.get("metadata")
        exit_code = meta.get("exit") if isinstance(meta, Mapping) else None
        times = state.get("time")
        times = times if isinstance(times, Mapping) else {}
        began, ended = _ms_to_dt(times.get("start")), _ms_to_dt(times.get("end"))
        if (
            state.get("status") == "completed"
            and type(exit_code) is int
            and exit_code == 0
            and isinstance(command, str)
            and began is not None
            and ended is not None
            and began >= start
            and _writes(command, log)
        ):
            windows.append((began, ended))
    return windows


__all__ = [
    "ClaudeCodeReader",
    "Dispatch",
    "OpenCodeReader",
    "attribute_dispatches",
    "claude_code_session",
    "current_session",
    "dispatched_from_this_session",
    "parse_timestamp",
    "session_dir",
    "tool_use_ids",
    "transcript_root",
]
