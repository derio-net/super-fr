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
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal, TypeGuard

from fr.harness.detect import detect_harness
from fr.harness.model import HarnessError
from fr.usage.classify import canonical_tool

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
    for stamp, block in _tool_uses(records):
        block_id = block.get("id")
        if isinstance(block_id, str):
            found[block_id] = stamp
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


def subagent_model(env: Mapping[str, str], session: str | None, agent_id: str) -> str | None:
    """The model subagent `agent_id` of `session` ran on — the `message.model`
    of its last real assistant message — or `None` when that cannot be
    observed (gh#637).

    The counterpart of `orchestrator_model` for a DISPATCHED unit. `advance`
    records the tier binding for a dispatch before anything runs; a dispatch
    sent without a model argument runs on the orchestrator's model instead,
    and the binding then names a model that never ran. The transcript is the
    only witness: the `agent-<id>.meta.json` companion carries no model.
    Paired by `attribute_dispatches`' exact tool_use id (`witness_transcript`),
    so a foreign agent file is never read. Claude Code only; never raises."""
    try:
        if detect_harness(env) != ClaudeCodeReader.harness:
            return None
        transcript = claude_code_session(env, session)
        found = witness_transcript(transcript, agent_id) if transcript is not None else None
        records = _read_records(found) if isinstance(found, Path) else None
    except (OSError, HarnessError):
        return None
    models = [
        first["message"].get("model")
        for first, _usage, _blocks in message_groups(records or [])
        if _is_real_model(first["message"].get("model"))
    ]
    return models[-1] if models else None


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
    calls, in order — where an `a 2nd round may follow` announcement is looked for.
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
    r"""([A-Za-z_]\w*)=([^\s;&|]*)(?=[ \t]*(?:\Z|[;\n]|&&|\|\|))"""
)
"""A `NAME=value` that is a whole command of its own: at the start of the string
or after `;`, `&&`, `||` or a newline, optionally behind `export`/`declare`,
and followed by `;`, `&&`, `||`, a newline or the end. Matched against
`_code`'s mask, never the raw command. NOT recognised (fail closed, review F3
and gh#720): a prefix assignment that scopes to the next word (`L=x pytest >
$L` leaves `$L` unset); one ended by a lone `&` or `|`, which runs it in a
subshell; and — via `_top_level` — one nested in any grouping."""
_QUOTED = re.compile(r"""\"(?:\\.|[^"\\])*\"|'[^']*'""", re.DOTALL)
_HEREDOC = re.compile(
    r"""<<-?[ \t]*(['"]?)(\w+)\1[^\n]*\n(.*?)\n[ \t]*\2[ \t]*(?:\n|\Z)""", re.DOTALL
)
_COMMENT = re.compile(r"(?:(?<=[\s;&|()])|\A)#[^\n]*")
_NESTING = re.compile(
    r"""[()`]|(?:\A|(?<=[;&|()\n])|(?<=\bthen)|(?<=\bdo)|(?<=\belse)|(?<=\{))[ \t]*"""
    r"""(?P<word>\{|\}|if|fi|case|esac|do|done)(?=[\s;&|()]|\Z)"""
)
"""What opens and closes a grouping: parentheses (a subshell, `$( )`, `<( )`),
backticks, and the reserved words `{ }`, `if … fi`, `case … esac` and the
`do … done` of every loop — a reserved word only in command position, since
`echo done` is an argument, not a keyword."""
_OPENER = {")": "(", "}": "{", "fi": "if", "esac": "case", "done": "do"}


def _code(command: str) -> str:
    """`command`, same length, with quoted strings and here-doc bodies filled with
    `_` (still one word, no longer syntax), comments blanked, and each
    backslash-newline joined — the text a shell actually parses as structure."""
    for doc in _HEREDOC.finditer(command):
        command = command[: doc.start(3)] + "_" * len(doc.group(3)) + command[doc.end(3) :]
    for m in _QUOTED.finditer(command):
        command = command[: m.start()] + "_" * len(m.group(0)) + command[m.end() :]
    command = _COMMENT.sub(lambda m: " " * len(m.group(0)), command)
    return command.replace("\\\n", "  ")


def _top_level(code: str, at: int) -> bool:
    """Is offset `at` of `_code`'s mask outside every grouping? Only there does
    an assignment run in the shell that later expands the variable.

    A stack, not a count: each closer must meet its own opener, so a stray one
    can never cancel a real grouping into looking closed (review of gh#720). A
    `)` directly inside `case` ends a pattern. Any mismatch fails closed."""
    stack: list[str] = []
    for m in _NESTING.finditer(code):
        if m.start() >= at:
            break
        token = m.group("word") or m.group(0)
        if token == "`" and stack[-1:] == ["`"]:
            stack.pop()
        elif token == ")" and stack[-1:] == ["case"]:
            continue
        elif token in _OPENER:
            if stack[-1:] != [_OPENER[token]]:
                return False
            stack.pop()
        else:
            stack.append(token)
    return not stack


def _assignments(command: str) -> list[tuple[int, str, str]]:
    """`(end, name, value)` of each assignment in `command` that the shell makes
    at top level — the only ones still in force where a later word expands the
    variable (gh#720). The value is read from the raw command, quotes intact."""
    code = _code(command)
    return [
        (m.end(), m.group(1), command[m.start(2) : m.end(2)])
        for m in _ASSIGNMENT.finditer(code)
        if _top_level(code, m.start(1))
    ]


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


def _is_log(target: str | None, log: Path) -> bool:
    """Does the resolved path `target` name `log` (see `_WRITE_TARGET` for how a
    relative one is compared)? An absolute one is compared as a real path on
    both sides: through a symlinked directory (macOS `/tmp` → `/private/tmp`)
    the literal target never equals the resolved log (gh#758). `realpath`,
    not `Path.resolve`: it never raises, and every transcript word lands here."""
    if target is None:
        return False
    if Path(target).is_absolute():
        return os.path.realpath(target) == os.path.realpath(log)
    parts = PurePosixPath(target).parts
    while parts and parts[0] == "..":
        parts = parts[1:]
    return bool(parts) and log.parts[-len(parts) :] == parts


def _writes(command: str, log: Path) -> bool:
    assignments = _assignments(command)
    return any(
        _is_log(_resolve_target(match.group(2), assignments, match.start()), log)
        for match in _WRITE_TARGET.finditer(command)
    )


_WORD = re.compile(r"""[^\s;&|<>()`'"]+""")
_DETACH = re.compile(r"(?<![&>|<])&(?![&>])")
"""A lone `&` — the control operator that backgrounds a command — as opposed
to `&&`, `|&`, `&>` and the `&` of `2>&1`."""
_EXIT_LINE = re.compile(r"^exit=(\d+)[ \t]*$", re.MULTILINE)
"""The marker OpenCode's long-command rule makes a detached suite write last:
`(cmd; echo "exit=$?") > log` (`fr.harness.long_commands`)."""


def _unquoted(command: str) -> str:
    """`command` with every quoted string and here-doc body blanked out, so an
    operator character inside one is not read as syntax."""
    for span in [d.span(3) for d in _HEREDOC.finditer(command)] + [
        m.span() for m in _QUOTED.finditer(command)
    ]:
        command = command[: span[0]] + " " * (span[1] - span[0]) + command[span[1] :]
    return command


def _detaches(command: str) -> bool:
    """Does `command` background something with a lone `&`? The writer then
    outlives the tool call, and the call's own end says nothing about its end."""
    return _DETACH.search(_unquoted(command)) is not None


def _names(command: str, log: Path) -> bool:
    """Does any word of `command` name `log` — a read (`tail`, `cat`, `grep`)
    as much as a write? Quotes are stripped, same-command variables resolved."""
    assignments = _assignments(command)
    bare = command.replace('"', " ").replace("'", " ")
    return any(
        _is_log(_resolve_target(m.group(0), assignments, m.start()), log)
        for m in _WORD.finditer(bare)
    )


def _tool_uses(
    records: list[dict[str, Any]], *, main_thread: bool = False
) -> Iterator[tuple[_dt.datetime | None, Mapping[str, Any]]]:
    """`(timestamp, block)` for every `tool_use` block of every assistant record,
    in file order. The file IS the scope: a subagent's transcript is
    `isSidechain` throughout, so it is read unfiltered. `main_thread` is for
    the orchestrator's own session file, where a sidechain record is some
    subagent's, not the orchestrator's (as `orchestrator_wrote_since`)."""
    for record in records:
        if record.get("type") != "assistant":
            continue
        if main_thread and record.get("isSidechain") is True:
            continue
        message = record.get("message")
        content = message.get("content") if isinstance(message, Mapping) else None
        stamp = parse_timestamp(record.get("timestamp"))
        for block in content if isinstance(content, list) else ():
            if isinstance(block, Mapping) and block.get("type") == "tool_use":
                yield stamp, block


def _first_call_since(
    transcript: Path,
    since: str,
    tool: str,
    matches: Callable[[Mapping[str, Any]], bool],
    *,
    not_before: _dt.datetime | None = None,
    main_thread: bool = False,
) -> _dt.datetime | Literal[False] | None:
    """When the first `tool` call (alias-normalised) at or after `since` — and
    `not_before`, when given — whose input `matches` was issued; `False` when
    the transcript holds none, `None` when it cannot be read (or `since` does
    not parse)."""
    start = parse_timestamp(since)
    records = _read_records(transcript)
    if start is None or records is None:
        return None
    if not_before is not None and not_before > start:
        start = not_before
    for stamp, block in _tool_uses(records, main_thread=main_thread):
        tool_input = block.get("input")
        if (
            stamp is not None
            and stamp >= start
            and canonical_tool(str(block.get("name"))) == tool
            and isinstance(tool_input, Mapping)
            and matches(tool_input)
        ):
            return stamp
    return False


def read_file_since(
    transcript: Path,
    path: Path,
    since: str,
    *,
    not_before: _dt.datetime | None = None,
    main_thread: bool = False,
) -> _dt.datetime | Literal[False] | None:
    """The first file read of `path` in `transcript` at or after `since` (and
    `not_before` — the caller's "after the file's last write") — or `False`
    when the transcript was read and holds none, `None` when it could not be
    read (spec 2026-09-28-ui-visual-evidence §C, check 4).

    A read is a tool call whose name normalises to `Read` through
    `fr.usage.classify`'s alias table (`read_file`, `view` count), naming the
    file in `file_path` or `path` by an ABSOLUTE path, compared as real paths
    on both sides. A relative target never matches: the transcript carries no
    cwd, so `shots/a.png` could be any `a.png` under any `shots/`. What the
    tool returned is not inspected. `main_thread` skips sidechain records (the
    orchestrator's own session file)."""
    real = os.path.realpath(path)

    def names(tool_input: Mapping[str, Any]) -> bool:
        target = tool_input.get("file_path") or tool_input.get("path")
        return (
            isinstance(target, str) and os.path.isabs(target) and os.path.realpath(target) == real
        )

    return _first_call_since(
        transcript, since, "Read", names, not_before=not_before, main_thread=main_thread
    )


_INTERPRETERS = frozenset({"node", "python", "python3", "bash", "sh", "npx", "deno", "bun"})
"""Words whose first non-flag argument is the program they execute."""
_SUBCOMMAND_RUNNERS = frozenset({"deno", "bun", "uv"})
"""Interpreters that may put a `run` subcommand before the program."""
_SEPARATORS = frozenset({"&&", "||", ";", "|", "|&", "&", "(", ")"})
_LEADING_ASSIGNMENT = re.compile(r"^[A-Za-z_]\w*=")


def _simple_commands(command: str) -> Iterator[list[str]]:
    """The words of each simple command in `command`: split on lines and on
    unquoted control operators, quotes removed. Unbalanced quotes fall back to
    whitespace splitting for that line."""
    import shlex

    for line in command.replace("\\\n", " ").splitlines():
        try:
            lexer = shlex.shlex(line, posix=True, punctuation_chars=True)
            lexer.whitespace_split = True
            lexer.commenters = ""
            words = list(lexer)
        except ValueError:
            words = line.split()
        current: list[str] = []
        for word in words:
            if word in _SEPARATORS or (word and set(word) <= set("&|;()")):
                if current:
                    yield current
                current = []
            else:
                current.append(word)
        if current:
            yield current


def _program(words: list[str], depth: int = 0) -> list[str]:
    """The program(s) a simple command executes: its command word and, after an
    interpreter word (`_INTERPRETERS`, `uv run`, a `deno`/`bun` `run`), the first
    non-flag argument — recursively (`uv run python x`, `npx node x`). An
    `fr isolation exec … --` prefix is stepped over, and a lone quoted argument
    after it, or after `bash -c`/`sh -c`, is read as a command of its own."""
    if depth > 4:
        return []
    while words and _LEADING_ASSIGNMENT.match(words[0]):
        words = words[1:]
    if not words:
        return []
    if words[:3] == ["uv", "run", "fr"]:
        words = words[2:]
    if words[:3] == ["fr", "isolation", "exec"]:
        rest = words[words.index("--") + 1 :] if "--" in words else []
        if len(rest) == 1:
            return [p for sub in _simple_commands(rest[0]) for p in _program(sub, depth + 1)]
        return _program(rest, depth + 1)
    head = words[0]
    found = [head]
    name = os.path.basename(head)
    if name not in _INTERPRETERS and name != "uv":
        return found
    args = words[1:]
    if name in ("bash", "sh") and "-c" in args:
        after = args[args.index("-c") + 1 :]
        if after:
            return [
                *found,
                *(p for sub in _simple_commands(after[0]) for p in _program(sub, depth + 1)),
            ]
        return found
    operands = [a for a in args if not a.startswith("-")]
    if name in _SUBCOMMAND_RUNNERS and operands[:1] == ["run"]:
        operands = operands[1:]
    elif name == "uv":
        return found
    if not operands:
        return found
    index = args.index(operands[0])
    return [*found, *_program(args[index:], depth + 1)]


def _executes(command: str, script: Path) -> bool:
    """Does `command` execute `script` — as a command word, or as the program
    an interpreter word runs (`_program`)?"""
    return any(
        _is_log(word, script) for words in _simple_commands(command) for word in _program(words)
    )


def shell_named_since(
    transcript: Path,
    name: str | Path,
    since: str,
    *,
    main_thread: bool = False,
) -> _dt.datetime | Literal[False] | None:
    """The first shell call in `transcript` at or after `since` that EXECUTES
    `name` — or `False` / `None` as `read_file_since` (spec §C, check 5: the
    stage that names a capture script re-ran it).

    Executes: the script is a simple command's command word (`./shots.cjs`),
    or the first non-flag argument of an interpreter word — `node`, `python`,
    `python3`, `bash`, `sh`, `npx`, `deno`, `bun`, `uv run [python]` — with
    an `fr isolation exec -- …` prefix stepped over. `cat shots.cjs`,
    `ls shots.cjs`, `echo shots.cjs` name it and do not run it.

    BE HONEST ABOUT THE LIMIT (review p2-r7): this is syntax, not execution.
    An indirection names no script — `npm run shots`, `make shots`, a
    wrapper script, a shell function — and is NOT recognised: name the script
    directly (`node shots.cjs`). An interpreter flag that takes a value
    (`node --require x shots.cjs`) is read as the program being `x`. And the
    transcript records that the command was issued, not that it succeeded."""
    script = Path(name)

    def runs(tool_input: Mapping[str, Any]) -> bool:
        command = tool_input.get("command")
        return isinstance(command, str) and _executes(command, script)

    return _first_call_since(transcript, since, "Bash", runs, main_thread=main_thread)


def witness_transcript(session: Path, agent_id: str | None) -> Path | Literal[False] | None:
    """The transcript that owes a unit's image reads (spec §C, check 4): the
    orchestrator's own stream when `agent_id` is `None`, else the subagent
    transcript of the dispatch `attribute_dispatches` pairs to `agent_id`.

    Three-valued (review p2-r1): `None` ONLY when the session file cannot be
    read (the gate records unobserved); `False` when it reads but no dispatch
    of this session pairs to `agent_id` — a bogus or foreign id, which the gate
    refuses, never records as unobserved."""
    if _read_records(session) is None:
        return None
    if agent_id is None:
        return session
    for dispatch in attribute_dispatches(session):
        if dispatch.agent_id == agent_id:
            return dispatch.transcript
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

    Claude Code reads this session's transcript; OpenCode reads its session
    database (`_opencode_wrote_since`, gh#638). Any other harness is `None`.

    BE HONEST ABOUT THE LIMIT (review r1-1): this proves the orchestrator
    produced the log, in this session, during delivery. It cannot prove the
    command was a real test suite — `echo ok > log` passes. That is forgery,
    not the drift this gate closes (relaying someone else's green), and
    closing it needs a per-repo test-runner declaration fr does not have.
    """
    start = parse_timestamp(since)
    if start is not None and detect_harness(env) == OpenCodeReader.harness:
        return _opencode_wrote_since(env, log, start)
    session = _this_session(env)
    if start is None or session is None:
        return None
    return wrote_since(session, log, since, main_thread=True)


def wrote_since(
    transcript: Path, log: Path, since: str, *, main_thread: bool
) -> list[tuple[_dt.datetime, _dt.datetime]] | None:
    """`orchestrator_wrote_since` over ONE Claude Code transcript file: the run
    windows of every completed `Bash` command in `transcript`, issued at or
    after `since`, that wrote `log`. `[]` when it holds none, `None` when it
    cannot be read.

    `main_thread` skips sidechain records — the orchestrator's own session
    file. A subagent's transcript (`witness_transcript`) is ALL sidechain, so
    it is read with `main_thread=False` (spec 2026-09-29-fr-goal-light-path
    §D: a phase unit's suite log is witnessed by its holder's transcript)."""
    start = parse_timestamp(since)
    if start is None:
        return None
    records = _read_records(transcript)
    if records is None:
        return None
    issued: dict[str, _dt.datetime] = {}
    for record in records:
        if record.get("type") != "assistant" or (main_thread and record.get("isSidechain") is True):
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
    backgrounded: set[str] = set()
    for record in records:
        if record.get("type") != "user" or (main_thread and record.get("isSidechain") is True):
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
                if _is_launch_ack(record):
                    # A `run_in_background` command's result is only its launch
                    # ack, a second after the call. Its real end is the
                    # notification below; the ack must not stand in for it.
                    backgrounded.add(block["tool_use_id"])
                else:
                    windows.append((issued[block["tool_use_id"]], done))
    # When the harness QUEUED a notice (the command's end), which can precede
    # its delivery by a whole turn. Used only to NARROW a window, never to open
    # one, so a queued prompt that merely looks like a notice can only refuse.
    queued: dict[str, _dt.datetime] = {}
    for record in records:
        if record.get("type") != "queue-operation" or record.get("operation") != "enqueue":
            continue
        stamp = parse_timestamp(record.get("timestamp"))
        parsed = _task_notice(record.get("content"))
        if parsed is not None and stamp is not None and parsed[0] not in queued:
            queued[parsed[0]] = stamp
    for record in records:
        if main_thread and record.get("isSidechain") is True:
            continue
        # Only the harness's own notice counts: an operator prompt or `!cmd`
        # output is also a string-content `user` record (Opus review r2).
        text = _notice_carrier(record)
        if text is None:
            continue
        done = parse_timestamp(record.get("timestamp"))
        parsed = _task_notice(text)
        if parsed is None or done is None:
            continue
        tool_use_id, status = parsed
        if tool_use_id not in backgrounded:
            continue
        # The first notice is final, whatever it says: a later one — duplicate
        # or forged — can neither widen a window nor revive a failed command.
        backgrounded.discard(tool_use_id)
        if status == "completed":
            start = issued[tool_use_id]
            end = min(done, queued.get(tool_use_id, done))
            windows.append((start, end if end >= start else done))
    return windows


def _notice_carrier(record: Mapping[str, Any]) -> object:
    """The text of a record that carries the harness's own task notice, else
    `None`. Two carriers exist in real transcripts: a `user` record with
    `origin.kind: task-notification`, and — when the orchestrator was busy as the
    command ended — an `attachment` record of type `queued_command` and
    `commandMode: task-notification` whose `prompt` is the notice. About a
    fifth of real notices arrive ONLY as the attachment, so reading just the
    first left those runs with no window and refused (gh#594)."""
    if record.get("type") == "user":
        origin = record.get("origin")
        if isinstance(origin, Mapping) and origin.get("kind") == "task-notification":
            message = record.get("message")
            return message.get("content") if isinstance(message, Mapping) else None
        return None
    if record.get("type") == "attachment":
        attachment = record.get("attachment")
        if (
            isinstance(attachment, Mapping)
            and attachment.get("type") == "queued_command"
            and attachment.get("commandMode") == "task-notification"
        ):
            return attachment.get("prompt")
    return None


_NOTICE_FIELD = re.compile(r"<(tool-use-id|status)>\s*([^<]*?)\s*</\1>")


def _is_launch_ack(record: Mapping[str, Any]) -> bool:
    """Is this `tool_result` the ack of a backgrounded command (its
    `toolUseResult.backgroundTaskId` is set), not the command's own result?"""
    result = record.get("toolUseResult")
    return isinstance(result, Mapping) and bool(result.get("backgroundTaskId"))


def _task_notice(content: object) -> tuple[str, str] | None:
    """`(tool_use_id, status)` of a `<task-notification>` — the text the
    harness writes when a backgrounded command ends (`status` is `completed`,
    `failed` or `killed`) — else `None`.

    Read from the notice's HEADER only, first occurrence of each field: its
    `<summary>` quotes the command's own `description`, which the agent wrote
    and could carry a `<status>completed</status>` of its own (Opus review r1).
    """
    if not isinstance(content, str) or not content.lstrip().startswith("<task-notification>"):
        return None
    header = content.split("<summary>", 1)[0]
    fields: dict[str, str] = {}
    for name, value in _NOTICE_FIELD.findall(header):
        fields.setdefault(name, value)
    tool_use_id, status = fields.get("tool-use-id"), fields.get("status")
    return (tool_use_id, status) if tool_use_id and status else None


OPENCODE_DB_ENV = "FR_OPENCODE_DB"
"""Override for OpenCode's session database — the same role
`FR_TRANSCRIPT_ROOT` plays for Claude Code, and what keeps the suite off the
operator's own sessions."""

OPENCODE_DB = Path(".local") / "share" / "opencode" / "opencode.db"
"""Where OpenCode keeps its sessions, under `$HOME`, when `XDG_DATA_HOME` is unset."""


class OpenCodeReader:
    """Where OpenCode's SQLite session database lives (`database`) — read by
    `fr.usage.readers.opencode`, opened read-only there."""

    harness = "opencode"

    def database(self, env: Mapping[str, str]) -> Path:
        """`FR_OPENCODE_DB`, else `$XDG_DATA_HOME/opencode/opencode.db`, else
        `~/.local/share/opencode/opencode.db` — OpenCode's own order (its
        xdg-basedir takes `XDG_DATA_HOME` when set and non-empty). OpenCode's
        bash tool passes its environment through, so fr sees the same value.
        Ignoring it read the operator's global database instead (gh#740)."""
        override = env.get(OPENCODE_DB_ENV)
        if override:
            return Path(override)
        data = env.get("XDG_DATA_HOME")
        if data:
            return Path(data) / "opencode" / OPENCODE_DB.name
        return Path.home() / OPENCODE_DB


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

    A READABLE database is not necessarily the right one (gh#740: OpenCode ran
    under `XDG_DATA_HOME`, fr read `~/.local/share`). The orchestrator calling
    this is itself mid-`bash`, a part of its session, so a database that
    recorded no part at all since the unit opened cannot hold it: that is
    `None` (unobserved), never `[]`, which refuses as "nobody wrote it".
    Activity is read from `part`, not `session.time_updated`, which nothing
    shows OpenCode bumps per part.
    """
    import sqlite3
    from contextlib import closing

    from fr.usage.readers.opencode import open_ro

    since_ms = int(start.timestamp() * 1000)
    try:
        with closing(open_ro(OpenCodeReader().database(env))) as con:
            (active,) = con.execute(
                "SELECT EXISTS (SELECT 1 FROM part WHERE time_updated >= ?)", (since_ms,)
            ).fetchone()
            rows = con.execute(
                "SELECT p.data FROM part p JOIN session s ON s.id = p.session_id "
                "WHERE s.parent_id IS NULL AND p.time_updated >= ?",
                (since_ms,),
            ).fetchall()
    except sqlite3.Error:
        return None
    if not active:
        return None
    calls: list[_BashCall] = []
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
        meta = meta if isinstance(meta, Mapping) else {}
        output = state.get("output")
        output = output if isinstance(output, str) else meta.get("output")
        times = state.get("time")
        times = times if isinstance(times, Mapping) else {}
        began, ended = _ms_to_dt(times.get("start")), _ms_to_dt(times.get("end"))
        if (
            state.get("status") == "completed"
            and isinstance(command, str)
            and began is not None
            and ended is not None
            and began >= start
        ):
            exit_code = meta.get("exit")
            calls.append(
                _BashCall(
                    began,
                    ended,
                    command,
                    exit_code if type(exit_code) is int else None,
                    output if isinstance(output, str) else "",
                )
            )
    calls.sort(key=lambda c: (c.began, c.ended))
    windows: list[tuple[_dt.datetime, _dt.datetime]] = []
    for call in calls:
        if call.exit_code != 0 or not _writes(call.command, log):
            continue
        windows.append((call.began, call.ended))
        if _detaches(call.command):
            seen = _seen_exit(call, calls, log)
            if seen is not None:
                windows.append((call.began, seen))
    return windows


@dataclass(frozen=True)
class _BashCall:
    """One completed, top-level OpenCode `bash` part, as the gate reads it."""

    began: _dt.datetime
    ended: _dt.datetime
    command: str
    exit_code: int | None
    output: str


def _seen_exit(launch: _BashCall, calls: list[_BashCall], log: Path) -> _dt.datetime | None:
    """The end of the orchestrator's first command, after `launch`, that named
    `log` and printed its `exit=N` line — when N is 0 — else `None` (gh#719).

    OpenCode records no event when a detached command ends; Claude Code's
    reader closes the window at the harness's task notice. The stand-in here is
    what OpenCode DOES record: the output of the orchestrator's own later
    command. The rule makes `exit=$?` the log's last write, so a command that
    showed it ran after the suite finished, and the window it closes is bounded
    by what the orchestrator saw — a later overwrite of the log still refuses.
    The first `exit=` seen is final, as the first notice is there: a later
    `exit=0` can neither revive a failure nor stretch a window already closed.

    WEAKER THAN THE NOTICE, AND SAYS SO (review of gh#719): a Claude Code notice
    is the harness reporting the process's own exit; this is file CONTENT the
    orchestrator read back. A co-resident process (a phase executor shares the
    worktree) that writes `exit=0` into this exact log before that read closes
    the window on its bytes. That takes deliberately writing the rule's marker
    into the orchestrator's log — forgery, which this gate does not claim to
    stop (`orchestrator_wrote_since`), not the relayed green it closes. Tying
    the marker to the pid would not change that: `log.pid` is as readable.
    """
    for call in calls:
        if call is launch or call.began < launch.ended or not _names(call.command, log):
            continue
        marks = _EXIT_LINE.findall(call.output)
        if marks:
            return call.ended if marks[-1] == "0" else None
    return None


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
