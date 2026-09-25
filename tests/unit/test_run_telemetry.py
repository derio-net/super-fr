"""`fr.run.telemetry` — measured tokens from a Claude Code transcript (spec §5.C).

Written against the **captured** transcript shape, not the spec's original
assumption about it: `tests/fixtures/transcripts/claude-code-session.NOTE.md`
records what a real pair of files looks like, and phase 1's finding
`f-p1-sidechain-file-split` records that §5.C's first draft was wrong about it.

The defect this file exists to make impossible: a parser that filters ONE
stream on `isSidechain` passes a naive test and reads **zero** subagent tokens
from every real transcript on disk, because the orchestrator's own file is
`isSidechain: false` throughout and subagent turns live in a separate
`subagents/agent-<agentId>.jsonl`. Attribution is file-to-file, keyed on the
subagent metadata's `toolUseId`.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fr.run.telemetry import (
    UsageTotals,
    attribute_dispatches,
    claude_code_session,
    measure_attempt,
    measure_dispatch,
    read_claude_code,
    reader_for,
    select_for_attempt,
)

from tests.unit.transcript_sessions import (
    AGENT_ID,
    ORCHESTRATOR,
    SUBAGENT,
    TOOL_USE_ID,
    copy_of,
    records,
    write_agent,
    write_session,
)

# Summed by hand from the fixture's two `type: assistant` records — the
# TOP-LEVEL usage keys only (see `iterations` below).
ORCHESTRATOR_TOTALS = UsageTotals(
    input_tokens=2 + 2,
    cache_creation_input_tokens=50909 + 406,
    cache_read_input_tokens=27488 + 173296,
    output_tokens=179 + 1748,
    assistant_records=2,
)
SUBAGENT_TOTALS = UsageTotals(
    input_tokens=2 + 2,
    cache_creation_input_tokens=34529 + 2825,
    cache_read_input_tokens=0 + 154017,
    output_tokens=8 + 22,
    assistant_records=2,
)

# The window a run's accounting record gives us: `at` is written just BEFORE
# the dispatch brief is printed, so it precedes every transcript timestamp of
# the unit it dispatched.
BEFORE = "2026-09-20T11:00:00+00:00"
AFTER = "2026-09-20T12:00:00+00:00"


def _session(tmp_path: Path, session_id: str = "sess-1") -> Path:
    return write_session(tmp_path / "projects", session_id=session_id)


# --- (a) the reader: sum usage over assistant records, projected ----------


def test_usage_is_summed_over_assistant_records_only() -> None:
    assert read_claude_code(ORCHESTRATOR) == ORCHESTRATOR_TOTALS


def test_usage_is_projected_onto_the_four_named_keys_not_walked() -> None:
    """The real `usage` object carries `cache_creation`, `output_tokens_details`,
    `server_tool_use`, `service_tier`, `inference_geo`, `speed` and sometimes an
    `iterations` list that REPEATS the same four numbers. A reader that walks
    the object instead of projecting onto the four named keys double-counts
    every record that carries `iterations` — the fixture has one."""
    record = json.loads(ORCHESTRATOR.read_text().splitlines()[6])
    usage = record["message"]["usage"]
    assert "iterations" in usage and usage["iterations"][0]["output_tokens"] == 179
    assert set(usage) > {
        "input_tokens",
        "cache_creation_input_tokens",
        "cache_read_input_tokens",
        "output_tokens",
    }

    totals = read_claude_code(ORCHESTRATOR)

    assert totals is not None
    assert totals.output_tokens == 179 + 1748  # not 179 + 179 + 1748


def test_a_record_type_with_no_usage_is_not_read_for_usage(tmp_path: Path) -> None:
    """A session interleaves `last-prompt`, `mode`, `permission-mode`,
    `atis-latch`, `user` and `system` records with no `message.usage` at all —
    all present in the fixture. Selecting `type == "assistant"` first is what
    keeps this a sum rather than a `KeyError`."""
    types = {json.loads(line)["type"] for line in ORCHESTRATOR.read_text().splitlines()}
    assert types - {"assistant"}, "fixture no longer interleaves non-assistant records"

    path = tmp_path / "only-chatter.jsonl"
    path.write_text(
        "".join(
            line + "\n"
            for line in ORCHESTRATOR.read_text().splitlines()
            if json.loads(line)["type"] != "assistant"
        )
    )

    totals = read_claude_code(path)

    assert totals == UsageTotals(), (
        "a readable transcript with no assistant turn is a MEASURED zero"
    )
    assert totals is not None


def test_an_assistant_record_without_usage_contributes_nothing_and_does_not_raise(
    tmp_path: Path,
) -> None:
    """Never observed in the capture (0 of 157 assistant records lacked usage),
    so this is a documented defensive assumption, not a verified shape — an
    interrupted stream is the plausible producer."""
    path = tmp_path / "t.jsonl"
    path.write_text(
        json.dumps({"type": "assistant", "message": {"content": []}})
        + "\n"
        + ORCHESTRATOR.read_text()
    )

    assert read_claude_code(path) == ORCHESTRATOR_TOTALS


# --- (d) degradation: no measurement, never a fake zero -------------------


def test_a_missing_transcript_is_no_measurement(tmp_path: Path) -> None:
    assert read_claude_code(tmp_path / "nope.jsonl") is None


def test_an_unreadable_transcript_is_no_measurement(tmp_path: Path) -> None:
    path = tmp_path / "garbage.jsonl"
    path.write_bytes(b"\xff\xfe not json at all\n{ also not json\n")

    assert read_claude_code(path) is None


def test_an_empty_transcript_is_no_measurement(tmp_path: Path) -> None:
    path = tmp_path / "empty.jsonl"
    path.write_text("")

    assert read_claude_code(path) is None


def test_a_truncated_last_line_still_measures_the_records_that_parsed(tmp_path: Path) -> None:
    """A transcript is appended to live, so the last line can be half-written.
    That is not "unreadable" — every complete record before it is real."""
    path = tmp_path / "t.jsonl"
    path.write_text(ORCHESTRATOR.read_text() + '{"type": "assistant", "mess')

    assert read_claude_code(path) == ORCHESTRATOR_TOTALS


def test_no_measurement_is_distinguishable_from_a_measured_zero(tmp_path: Path) -> None:
    zero = tmp_path / "z.jsonl"
    zero.write_text(json.dumps({"type": "user", "message": {"content": "hi"}}) + "\n")

    assert read_claude_code(zero) == UsageTotals()
    assert read_claude_code(tmp_path / "absent.jsonl") is None
    assert UsageTotals() is not None


# --- (e) one message, many records: dedupe by message.id (spec §D) --------


def _content_block_split(record: dict[str, object], blocks: int) -> list[dict[str, object]]:
    """`blocks` copies of one captured assistant record, as Claude Code writes a
    message with that many content blocks: one record per block, every copy
    repeating the WHOLE message's `usage` under the same `message.id`. Only
    `uuid` varies — confirmed live, 27 of 40 assistant message ids of one real
    transcript appear on more than one record, each copy with identical usage."""
    out = []
    for index in range(blocks):
        row = copy_of(record)
        row["uuid"] = f"{row.get('uuid')}-block-{index}"
        out.append(row)
    return out


def test_a_message_split_across_content_block_records_is_summed_once(tmp_path: Path) -> None:
    first, second = [r for r in records(ORCHESTRATOR) if r["type"] == "assistant"]
    path = tmp_path / "t.jsonl"
    path.write_text(
        "".join(json.dumps(r) + "\n" for r in [*_content_block_split(first, 3), second])
    )

    assert read_claude_code(path) == ORCHESTRATOR_TOTALS, (
        "three records of one message.id are ONE message: summing each copy triples its usage"
    )


def test_records_with_no_message_id_are_kept_never_merged(tmp_path: Path) -> None:
    first, _ = [r for r in records(ORCHESTRATOR) if r["type"] == "assistant"]
    rows = _content_block_split(first, 2)
    for row in rows:
        del row["message"]["id"]  # type: ignore[attr-defined]
    path = tmp_path / "t.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))

    totals = read_claude_code(path)

    assert totals is not None
    assert totals.assistant_records == 2
    assert totals.output_tokens == 2 * 179


# --- (b) attribution: file-to-file, keyed on toolUseId --------------------


def test_a_dispatch_is_attributed_by_tool_use_id(tmp_path: Path) -> None:
    session = _session(tmp_path)
    write_agent(session, AGENT_ID, tool_use_id=TOOL_USE_ID)

    dispatches = attribute_dispatches(session)

    assert [d.tool_use_id for d in dispatches] == [TOOL_USE_ID]
    assert dispatches[0].agent_id == AGENT_ID
    assert dispatches[0].agent_type == "super-fr:fr-phase-executor"
    assert dispatches[0].model == "sonnet"
    assert read_claude_code(dispatches[0].transcript) == SUBAGENT_TOTALS


def test_filtering_the_orchestrator_stream_on_issidechain_finds_zero_subagent_tokens(
    tmp_path: Path,
) -> None:
    """The finding this module was rewritten for (`f-p1-sidechain-file-split`).
    Every record of the orchestrator's own file is `isSidechain: false` (or
    omits it); `true` appears only in the separate per-agent file. So the
    subagent's tokens are NOT in the orchestrator's sum, and a one-file
    `isSidechain` filter measures nothing at all."""
    orchestrator_records = records(ORCHESTRATOR)
    assert not any(r.get("isSidechain") for r in orchestrator_records)
    assert all(json.loads(x)["isSidechain"] for x in SUBAGENT.read_text().splitlines())

    session = _session(tmp_path)
    write_agent(session, AGENT_ID, tool_use_id=TOOL_USE_ID)

    measured = measure_dispatch(session, start=BEFORE, end=AFTER)

    assert measured is not None
    assert measured.totals == SUBAGENT_TOTALS
    assert measured.totals != ORCHESTRATOR_TOTALS
    assert measured.totals.cache_read_input_tokens == 154017


def test_a_subagent_file_the_orchestrator_never_dispatched_is_not_attributed(
    tmp_path: Path,
) -> None:
    """The check that a glob over `subagents/*.jsonl` cannot pass: a file whose
    `toolUseId` matches no `Agent` tool_use in THIS orchestrator stream belongs
    to some other dispatch and contributes nothing."""
    session = _session(tmp_path)
    write_agent(session, "stranger", tool_use_id="toolu_not_in_this_stream")

    assert attribute_dispatches(session) == []
    assert measure_dispatch(session, start=BEFORE, end=AFTER) is None


def test_attribution_uses_neither_sessionid_nor_cwd(tmp_path: Path) -> None:
    """(c) `sessionId` on a subagent record is the ORCHESTRATOR's and `cwd` is
    the harness's launch directory, not the worktree the agent worked in — both
    verified on the captured records. Two dispatches in one session therefore
    share both fields exactly, so a reader that keys on either cannot tell them
    apart. This test fails loudly for any such shortcut: each window must
    return its OWN agent's numbers."""
    orchestrator = records(ORCHESTRATOR)
    subagent = records(SUBAGENT)
    agent_tool_use = orchestrator[7]
    assert subagent[0]["sessionId"] == agent_tool_use["sessionId"]
    assert subagent[0]["cwd"] == agent_tool_use["cwd"]

    # A second dispatch, an hour later, same sessionId and same cwd.
    second_tool_use = "toolu_second_dispatch"
    later = copy_of(agent_tool_use)
    later["timestamp"] = "2026-09-20T13:00:00.000Z"
    later["uuid"] = "second-uuid"
    later["message"]["content"][0]["id"] = second_tool_use
    session = _session(tmp_path)
    session.write_text(session.read_text() + json.dumps(later) + "\n")

    write_agent(session, AGENT_ID, tool_use_id=TOOL_USE_ID)
    second_records = copy_of(subagent)
    for record in second_records:
        record["timestamp"] = "2026-09-20T13:00:05.000Z"
        record["agentId"] = "second-agent"
        if record["type"] == "assistant":
            record["message"]["usage"] = {
                "input_tokens": 1,
                "cache_creation_input_tokens": 2,
                "cache_read_input_tokens": 3,
                "output_tokens": 4,
            }
    write_agent(session, "second-agent", tool_use_id=second_tool_use, rows=second_records)

    first = measure_dispatch(session, start=BEFORE, end="2026-09-20T12:00:00+00:00")
    second = measure_dispatch(
        session, start="2026-09-20T12:30:00+00:00", end="2026-09-20T14:00:00+00:00"
    )

    assert first is not None and second is not None
    assert first.tool_use_id == TOOL_USE_ID
    assert first.totals == SUBAGENT_TOTALS
    assert second.tool_use_id == second_tool_use
    assert second.totals == UsageTotals(
        input_tokens=2,
        cache_creation_input_tokens=4,
        cache_read_input_tokens=6,
        output_tokens=8,
        assistant_records=2,
    )


def test_the_module_never_reads_sessionid_or_cwd() -> None:
    """The behavioural test above is the real one; this is the tripwire that
    makes a later shortcut fail HERE, at the line someone would add it."""
    import fr.run.telemetry as telemetry

    source = Path(telemetry.__file__).read_text()
    code = "\n".join(line for line in source.splitlines() if not line.lstrip().startswith("#"))
    body = code.split('"""', 2)[-1]
    # Non-vacuity: the module docstring is excluded (it EXPLAINS those fields),
    # so a restructure that swallowed the whole module would make this pass
    # while checking nothing.
    assert len(body.splitlines()) > len(source.splitlines()) // 2
    assert "sessionId" not in body, "cwd/sessionId identify no unit — see the capture note"
    assert '"cwd"' not in body


# --- the window ----------------------------------------------------------


def test_a_window_with_no_dispatch_in_it_is_no_measurement(tmp_path: Path) -> None:
    session = _session(tmp_path)
    write_agent(session, AGENT_ID, tool_use_id=TOOL_USE_ID)

    assert (
        measure_dispatch(
            session, start="2026-09-21T00:00:00+00:00", end="2026-09-21T01:00:00+00:00"
        )
        is None
    )


def test_two_dispatches_in_one_window_is_no_measurement_not_a_guess(tmp_path: Path) -> None:
    """Serial dispatch is what makes the window unambiguous. If two dispatches
    fall inside one unit's window the serial assumption is broken, and a sum
    over both would silently attribute another unit's cost to this one."""
    session = _session(tmp_path)
    orchestrator = records(ORCHESTRATOR)
    twin = copy_of(orchestrator[7])
    twin["uuid"] = "twin"
    twin["message"]["content"][0]["id"] = "toolu_twin"
    session.write_text(session.read_text() + json.dumps(twin) + "\n")
    write_agent(session, AGENT_ID, tool_use_id=TOOL_USE_ID)
    write_agent(session, "twin-agent", tool_use_id="toolu_twin")

    assert len(attribute_dispatches(session)) == 2
    assert measure_dispatch(session, start=BEFORE, end=AFTER) is None


def test_a_session_with_no_subagents_directory_is_no_measurement(tmp_path: Path) -> None:
    session = _session(tmp_path)

    assert attribute_dispatches(session) == []
    assert measure_dispatch(session, start=BEFORE, end=AFTER) is None


def test_a_missing_session_file_is_no_measurement(tmp_path: Path) -> None:
    assert attribute_dispatches(tmp_path / "gone.jsonl") == []
    assert measure_dispatch(tmp_path / "gone.jsonl", start=BEFORE, end=AFTER) is None


# --- harness scoping and session location --------------------------------


def test_the_reader_is_harness_scoped() -> None:
    assert reader_for("claude-code") is not None
    # OpenCode has a reader since spec 2026-09-24 §D — for the MAIN session
    # only; its dispatch measurement is still nothing (V1 estimates stand).
    opencode = reader_for("opencode")
    assert opencode is not None
    assert opencode.measure(Path("x"), agent=None, start="", end="", same_session=True) is None
    assert reader_for("hermes") is None
    assert reader_for("nonesuch") is None


def test_the_session_is_located_from_the_harness_env(tmp_path: Path) -> None:
    """`CLAUDE_CODE_SESSION_ID` is set in every Claude Code tool call, and is
    the ORCHESTRATOR's id even inside a subagent (verified live 2026-09-20).
    No harness API is called — this reads a file the harness already wrote."""
    session = _session(tmp_path, session_id="abc-123")
    env = {
        "CLAUDECODE": "1",
        "CLAUDE_CODE_SESSION_ID": "abc-123",
        "FR_TRANSCRIPT_ROOT": str(tmp_path / "projects"),
    }

    assert claude_code_session(env) == session


def test_an_unknown_session_id_locates_nothing(tmp_path: Path) -> None:
    _session(tmp_path, session_id="abc-123")
    env = {
        "CLAUDECODE": "1",
        "CLAUDE_CODE_SESSION_ID": "other",
        "FR_TRANSCRIPT_ROOT": str(tmp_path / "projects"),
    }

    assert claude_code_session(env) is None
    assert measure_attempt(env, session="other", agent=None, start=BEFORE, end=AFTER) is None


def test_measure_attempt_ties_the_three_together(tmp_path: Path) -> None:
    session = _session(tmp_path, session_id="abc-123")
    write_agent(session, AGENT_ID, tool_use_id=TOOL_USE_ID)
    env = {
        "CLAUDECODE": "1",
        "CLAUDE_CODE_SESSION_ID": "abc-123",
        "FR_TRANSCRIPT_ROOT": str(tmp_path / "projects"),
    }

    measured = measure_attempt(env, session="abc-123", agent=None, start=BEFORE, end=AFTER)

    assert measured is not None
    assert measured.harness == "claude-code"
    assert measured.totals == SUBAGENT_TOTALS


@pytest.mark.parametrize("env", [{}, {"OPENCODE_BIN": "x"}, {"HERMES_HOME": "/h"}])
def test_a_harness_with_no_reader_measures_nothing(env: dict[str, str]) -> None:
    assert measure_attempt(env, session=None, agent=None, start=BEFORE, end=AFTER) is None


def test_a_mistyped_fr_harness_degrades_instead_of_raising() -> None:
    """`detect_harness` refuses an `FR_HARNESS` outside the closed set — right
    there, wrong here: telemetry is observability and must never be able to
    fail the `fr run resolve` that asked for it."""
    from fr.harness.detect import detect_harness
    from fr.harness.model import HarnessError

    with pytest.raises(HarnessError):
        detect_harness({"FR_HARNESS": "claude-kode"})

    assert (
        measure_attempt(
            {"FR_HARNESS": "claude-kode"}, session=None, agent=None, start=BEFORE, end=AFTER
        )
        is None
    )


def test_a_transcript_with_non_ascii_bytes_is_read_under_a_non_utf8_locale(
    tmp_path: Path,
) -> None:
    """Transcripts are JSON — UTF-8 by specification — so the reader must not
    consult the process locale.

    `Path.read_text()` with no `encoding=` uses the preferred encoding. In a
    container or CI image with no `C.UTF-8` (PEP 538 coercion has nothing to
    coerce to) that is US-ASCII, and every transcript carrying one non-ASCII
    byte raises `UnicodeDecodeError` — which this module turns into `None`,
    i.e. "no measurement", indistinguishable from "no transcript exists". The
    whole feature would be dead and say nothing. Reproduced against a real
    transcript under `LC_ALL=C` before the fix.

    This runs OUT OF PROCESS on purpose. The first version of this test
    monkeypatched `locale.getpreferredencoding` and passed with the bug still
    in place: `Path.read_text()` resolves its encoding below the Python name
    that was patched, so the test proved nothing. A process cannot change its
    own locale after start, so the only honest way to assert this is to start
    one that has the hostile locale — the same reason
    `test_registration_rides_the_package_import_not_the_callers_memory` is a
    subprocess test.
    """
    transcript = tmp_path / "agent-x.jsonl"
    transcript.write_text(
        json.dumps(
            {
                "type": "assistant",
                "isSidechain": True,
                "message": {
                    "usage": {
                        "input_tokens": 1,
                        "cache_creation_input_tokens": 2,
                        "cache_read_input_tokens": 3,
                        "output_tokens": 4,
                    },
                    # A real dispatch brief routinely carries an em dash, a
                    # curly quote or a section sign.
                    "content": "phase 4 — the executor's brief §5.C",
                },
            },
            # ensure_ascii=False, or json escapes the em dash to \\u2014 and the
            # fixture is pure ASCII — which is how the first version of this
            # test passed with the bug still in place. Real transcripts are not
            # escaped: one sampled on this machine carries 9,189 non-ASCII
            # bytes.
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    probe = (
        "import sys, json\n"
        "from pathlib import Path\n"
        "from fr.run.telemetry import read_claude_code\n"
        f"t = read_claude_code(Path({str(transcript)!r}))\n"
        "print(json.dumps(None if t is None else t.total))\n"
    )
    env = {
        **os.environ,
        "LC_ALL": "C",
        "LANG": "C",
        "PYTHONUTF8": "0",
        "PYTHONCOERCECLOCALE": "0",
    }
    done = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        env=env,
        cwd=Path(__file__).resolve().parents[2],
    )

    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout.strip()) == 10, (
        "a non-ASCII transcript must still be readable under a non-UTF-8 "
        f"locale; got {done.stdout!r}"
    )


# --- (e) which transcript is THIS attempt's: (session, agent), never a ----
# --- borrowed window (spec §4.D / §4.D.1, phase 4) ------------------------
#
# Every test below DECLARES its harness and its session. Reading either off
# the machine is how three tests in this file once passed only because the
# authoring machine happened to be a Claude Code session — and this section is
# about session identity, so the environment it asserts over must be the one
# it wrote.

_THEIRS = {
    "input_tokens": 5,
    "cache_creation_input_tokens": 50,
    "cache_read_input_tokens": 500,
    "output_tokens": 5000,
}
_OURS = {
    "input_tokens": 9,
    "cache_creation_input_tokens": 90,
    "cache_read_input_tokens": 900,
    "output_tokens": 9000,
}
_THEIRS_TOTAL = 2 * (5 + 50 + 500 + 5000)
_OURS_TOTAL = 2 * (9 + 90 + 900 + 9000)


def _env(root: Path, session_id: str | None) -> dict[str, str]:
    """A declared Claude Code environment — harness and session, never the
    machine's own."""
    env = {"FR_HARNESS": "claude-code", "FR_TRANSCRIPT_ROOT": str(root)}
    if session_id is not None:
        env["CLAUDE_CODE_SESSION_ID"] = session_id
    return env


def test_a_claimed_attempt_is_measured_by_its_agent_id_when_dispatches_overlap(
    tmp_path: Path,
) -> None:
    """Two dispatches at the SAME instant — the concurrency the window cannot
    resolve and `--redispatch` produces on purpose. The agent id is also the
    transcript's filename, so selection is exact; the assertion that the
    window alone yields NOTHING is what keeps this test non-vacuous."""
    from tests.unit.transcript_sessions import add_dispatch

    root = tmp_path / "projects"
    session = write_session(root, session_id="sess-1")
    same = "2026-09-20T11:30:00.000Z"
    add_dispatch(session, timestamp=same, agent_id="a1f1", tool_use_id="t1", usage=_THEIRS)
    add_dispatch(session, timestamp=same, agent_id="b2e2", tool_use_id="t2", usage=_OURS)

    first = measure_attempt(
        _env(root, "sess-1"), session="sess-1", agent="a1f1", start=BEFORE, end=AFTER
    )
    second = measure_attempt(
        _env(root, "sess-1"), session="sess-1", agent="b2e2", start=BEFORE, end=AFTER
    )

    assert first is not None and first.totals.total == _THEIRS_TOTAL
    assert second is not None and second.totals.total == _OURS_TOTAL
    assert measure_dispatch(session, start=BEFORE, end=AFTER) is None, (
        "non-vacuity: the WINDOW cannot separate these two, so neither figure "
        "above can have come from it"
    )


def test_an_earlier_sessions_attempt_is_measured_in_that_sessions_directory(
    tmp_path: Path,
) -> None:
    """Same host, new session. The transcript is looked up in the RECORDED
    session's directory, not the current one — so stopping and resuming on the
    same machine still measures what the earlier session dispatched."""
    from tests.unit.transcript_sessions import add_dispatch

    root = tmp_path / "projects"
    theirs = write_session(root, session_id="sess-old")
    add_dispatch(
        theirs,
        timestamp="2026-09-20T11:30:00.000Z",
        agent_id="a1f1",
        tool_use_id="t1",
        usage=_THEIRS,
    )
    write_session(root, session_id="sess-new", slug="-home-user-other")

    measured = measure_attempt(
        _env(root, "sess-new"), session="sess-old", agent="a1f1", start=BEFORE, end=AFTER
    )

    assert measured is not None
    assert measured.totals.total == _THEIRS_TOTAL


def test_an_attempt_whose_session_directory_is_absent_is_not_observable(tmp_path: Path) -> None:
    """Another HOST: the cursor travelled with the branch, the transcripts did
    not. A missing session directory already says "elsewhere" — which is why
    no hostname is recorded. Never zero, never guessed."""
    root = tmp_path / "projects"
    write_session(root, session_id="sess-here")

    measured = measure_attempt(
        _env(root, "sess-here"),
        session="sess-on-another-host",
        agent="a1f1",
        start=BEFORE,
        end=AFTER,
    )

    assert measured is None


def test_the_window_is_refused_for_an_attempt_this_session_did_not_dispatch(
    tmp_path: Path,
) -> None:
    """Spec §4.D.1, exactly: host B resolves host A's open attempt at T2, and
    the window [T0, T2] contains exactly ONE subagent — one host B dispatched
    itself, for something unrelated. gh#514's `select_dispatch` accepts it,
    and that stranger's cost would be recorded against host A's attempt.

    The non-vacuity assertion is the whole test: `select_dispatch` over the
    very same session DOES return that dispatch, so the refusal can only come
    from the session check."""
    from tests.unit.transcript_sessions import add_dispatch

    root = tmp_path / "projects"
    ours = write_session(root, session_id="sess-b")
    add_dispatch(
        ours,
        timestamp="2026-09-20T11:30:00.000Z",
        agent_id="unrelated",
        tool_use_id="t9",
        usage=_OURS,
    )

    borrowed = measure_attempt(
        _env(root, "sess-b"), session="sess-a", agent=None, start=BEFORE, end=AFTER
    )

    assert borrowed is None, "another session's attempt never borrows this session's spend"

    # TWO independent defences, and the test pins both, because the mutation
    # that removes either must fail here. (1) fr looks in the RECORDED
    # session's directory, which on host B does not exist — and it must never
    # fall back to the current one, which is precisely how the stranger would
    # be reached. (2) even offered host B's OWN dispatches, the window is shut
    # unless the attempt was dispatched from this session.
    assert claude_code_session(_env(root, "sess-b"), "sess-a") is None
    assert (
        select_for_attempt(
            attribute_dispatches(ours), agent=None, start=BEFORE, end=AFTER, same_session=False
        )
        is None
    )
    stranger = select_for_attempt(
        attribute_dispatches(ours), agent=None, start=BEFORE, end=AFTER, same_session=True
    )
    assert stranger is not None and stranger.agent_id == "unrelated", (
        "non-vacuity: the window DOES hold exactly one dispatch — gh#514's "
        "`select_dispatch` accepts it — so only the session check refuses it"
    )


def test_the_window_still_measures_an_unclaimed_attempt_of_this_session(tmp_path: Path) -> None:
    """The fallback is not removed, only fenced: an UNCLAIMED attempt this
    same session dispatched has no agent id to match on, and the window is all
    fr has. Refusing here would delete the measurement of every attempt an
    orchestrator forgot to claim."""
    from tests.unit.transcript_sessions import add_dispatch

    root = tmp_path / "projects"
    session = write_session(root, session_id="sess-1")
    add_dispatch(
        session,
        timestamp="2026-09-20T11:30:00.000Z",
        agent_id="a1f1",
        tool_use_id="t1",
        usage=_THEIRS,
    )

    measured = measure_attempt(
        _env(root, "sess-1"), session="sess-1", agent=None, start=BEFORE, end=AFTER
    )

    assert measured is not None and measured.totals.total == _THEIRS_TOTAL


def test_an_attempt_with_no_recorded_session_never_borrows_the_window(tmp_path: Path) -> None:
    """`session is None` — every attempt written before the field existed, and
    every harness with no session concept. Not knowing is not the same as
    knowing it was this one, so the window stays shut; the agent-id path,
    which is exact, still answers."""
    from tests.unit.transcript_sessions import add_dispatch

    root = tmp_path / "projects"
    session = write_session(root, session_id="sess-1")
    add_dispatch(
        session,
        timestamp="2026-09-20T11:30:00.000Z",
        agent_id="a1f1",
        tool_use_id="t1",
        usage=_THEIRS,
    )
    env = _env(root, "sess-1")

    assert measure_attempt(env, session=None, agent=None, start=BEFORE, end=AFTER) is None
    by_id = measure_attempt(env, session=None, agent="a1f1", start=BEFORE, end=AFTER)
    assert by_id is not None and by_id.totals.total == _THEIRS_TOTAL


def test_a_process_with_no_session_of_its_own_measures_nothing_by_window(tmp_path: Path) -> None:
    """Symmetric to the above: the attempt names a session, this process has
    none to compare it to (no `CLAUDE_CODE_SESSION_ID` at all). Equality
    against an absent value is not a match."""
    from tests.unit.transcript_sessions import add_dispatch

    root = tmp_path / "projects"
    session = write_session(root, session_id="sess-1")
    add_dispatch(
        session,
        timestamp="2026-09-20T11:30:00.000Z",
        agent_id="a1f1",
        tool_use_id="t1",
        usage=_THEIRS,
    )

    assert (
        measure_attempt(_env(root, None), session="sess-1", agent=None, start=BEFORE, end=AFTER)
        is None
    )


def test_no_hostname_is_recorded_or_read_anywhere_in_telemetry() -> None:
    """§4.D.1: a missing session directory already says "elsewhere", and a
    hostname in a public repo's committed cursor is identity nobody needs."""
    import fr.run.telemetry as telemetry

    source = Path(telemetry.__file__).read_text()
    assert "gethostname" not in source
    assert "socket" not in source
    assert "platform.node" not in source


# --- the orchestrator's own model (2026-09-21 debug journal C3) ----------


def test_orchestrator_model_is_the_last_main_thread_assistant_model(tmp_path: Path) -> None:
    """The orchestrator runs every non-dispatched unit in its own session, and
    until now fr recorded no model for that work because it "could not see"
    one. The session transcript names it on every assistant record. The LAST
    one is the model running now — a `/model` switch mid-session moves it."""
    from fr.run.telemetry import orchestrator_model

    root = tmp_path / "projects"
    rows = records(ORCHESTRATOR)
    later = copy_of(next(r for r in rows if r.get("type") == "assistant"))
    later["message"]["model"] = "claude-sonnet-5"
    write_session(root, session_id="sess-o", rows=[*rows, later])
    env = {
        "FR_TRANSCRIPT_ROOT": str(root),
        "CLAUDE_CODE_SESSION_ID": "sess-o",
        "CLAUDECODE": "1",
    }
    assert orchestrator_model(env) == "claude-sonnet-5"


def test_orchestrator_model_is_none_when_no_transcript_is_readable(tmp_path: Path) -> None:
    """Not observable is `None`, never a guess — and never the binding."""
    from fr.run.telemetry import orchestrator_model

    env = {"FR_TRANSCRIPT_ROOT": str(tmp_path), "CLAUDE_CODE_SESSION_ID": "nope", "CLAUDECODE": "1"}
    assert orchestrator_model(env) is None
    assert orchestrator_model({"FR_TRANSCRIPT_ROOT": str(tmp_path)}) is None


def test_orchestrator_model_ignores_sidechain_records(tmp_path: Path) -> None:
    """A subagent's records can be interleaved in some harness builds; they are
    the SUBAGENT's model, not the orchestrator's."""
    from fr.run.telemetry import orchestrator_model

    root = tmp_path / "projects"
    rows = records(ORCHESTRATOR)
    side = copy_of(next(r for r in rows if r.get("type") == "assistant"))
    side["isSidechain"] = True
    side["message"]["model"] = "claude-haiku-4-5"
    write_session(root, session_id="sess-s", rows=[*rows, side])
    env = {"FR_TRANSCRIPT_ROOT": str(root), "CLAUDE_CODE_SESSION_ID": "sess-s", "CLAUDECODE": "1"}
    assert orchestrator_model(env) == "claude-opus-5"


# --- was the operator actually asked? (2026-09-21 debug journal C1) ------


def _question_env(root: Path, session_id: str) -> dict[str, str]:
    return {
        "FR_TRANSCRIPT_ROOT": str(root),
        "CLAUDE_CODE_SESSION_ID": session_id,
        "CLAUDECODE": "1",
    }


def test_an_answered_question_after_the_gate_blocked_counts(tmp_path: Path) -> None:
    """The captured exchange: an AskUserQuestion tool_use and a tool_result whose
    `toolUseResult.answers` is non-empty — asked after the gate blocked."""
    from fr.run.telemetry import operator_answered_since

    from tests.unit.transcript_sessions import asked_at

    root = tmp_path / "projects"
    asked_at(root, "2026-09-21T16:05:00.000Z", session_id="s-q")
    assert operator_answered_since(_question_env(root, "s-q"), "2026-09-21T16:00:00+00:00") is True


def test_a_question_asked_before_the_gate_blocked_does_not_count(tmp_path: Path) -> None:
    """An earlier session question answers an earlier gate, not this one."""
    from fr.run.telemetry import operator_answered_since

    from tests.unit.transcript_sessions import asked_at

    root = tmp_path / "projects"
    asked_at(root, "2026-09-21T15:00:00.000Z", session_id="s-q")
    assert operator_answered_since(_question_env(root, "s-q"), "2026-09-21T16:00:00+00:00") is False


def test_a_declined_question_does_not_count(tmp_path: Path) -> None:
    from fr.run.telemetry import operator_answered_since

    from tests.unit.transcript_sessions import asked_at

    root = tmp_path / "projects"
    asked_at(root, "2026-09-21T16:05:00.000Z", session_id="s-q", answered=False)
    assert operator_answered_since(_question_env(root, "s-q"), "2026-09-21T16:00:00+00:00") is False


def test_a_session_with_no_question_is_observed_false(tmp_path: Path) -> None:
    """The #497 run exactly: a readable transcript, no question in it."""
    from fr.run.telemetry import operator_answered_since

    root = tmp_path / "projects"
    write_session(root, session_id="s-none")
    assert (
        operator_answered_since(_question_env(root, "s-none"), "2020-01-01T00:00:00+00:00") is False
    )


def test_unobservable_is_none_never_false(tmp_path: Path) -> None:
    """No transcript, or a harness with no reader: fr cannot say, so it says
    nothing — `None` is what lets the caller degrade loudly instead of refusing."""
    from fr.run.telemetry import operator_answered_since

    assert (
        operator_answered_since(_question_env(tmp_path, "missing"), "2026-09-21T16:00:00+00:00")
        is None
    )
    assert operator_answered_since({"FR_HARNESS": "opencode"}, "2026-09-21T16:00:00+00:00") is None


# --- separate-context review and orchestrator-run tests (debug C6 / C5) ---


def test_a_subagent_dispatched_after_the_window_opened_is_observed(tmp_path: Path) -> None:
    from fr.run.telemetry import subagent_dispatch_since

    from tests.unit.transcript_sessions import dispatched_at

    root = tmp_path / "projects"
    dispatched_at(root, "2026-09-21T16:05:00.000Z", session_id="s-r", usage={})
    env = _question_env(root, "s-r")
    found = subagent_dispatch_since(env, AGENT_ID, "2026-09-21T16:00:00+00:00")
    assert found and found.agent_id == AGENT_ID
    # The capture IS a phase executor — the caller refuses that as a reviewer.
    assert found.agent_type == "super-fr:fr-phase-executor"
    assert subagent_dispatch_since(env, AGENT_ID, "2026-09-21T16:10:00+00:00") is False
    assert subagent_dispatch_since(env, "someone-else", "2026-09-21T16:00:00+00:00") is False


def test_subagent_dispatch_is_unobservable_without_a_readable_transcript(tmp_path: Path) -> None:
    """Review r1-3: an unreadable transcript is `None`, never `False` — "could
    not read it" must not become "nobody was dispatched" and refuse a review."""
    from fr.run.telemetry import subagent_dispatch_since

    since = "2026-09-21T16:00:00+00:00"
    assert subagent_dispatch_since(_question_env(tmp_path, "missing"), AGENT_ID, since) is None
    root = tmp_path / "projects"
    session = write_session(root, session_id="s-bad")
    session.write_text("not json\n{half")
    assert subagent_dispatch_since(_question_env(root, "s-bad"), AGENT_ID, since) is None


def _bash_env(tmp_path: Path, **kw: object) -> dict[str, str]:
    from tests.unit.transcript_sessions import ran_at

    root = tmp_path / "projects"
    ran_at(root, "2026-09-21T16:05:00.000Z", session_id="s-b", **kw)  # type: ignore[arg-type]
    return _question_env(root, "s-b")


def test_a_command_that_writes_the_log_yields_its_run_window(tmp_path: Path) -> None:
    """The captured command writes its suite output to the (redacted) log."""
    from fr.run.telemetry import orchestrator_wrote_since, parse_timestamp

    from tests.unit.transcript_sessions import CAPTURED_LOG

    env = _bash_env(tmp_path, until="2026-09-21T16:09:00.000Z")
    windows = orchestrator_wrote_since(env, Path(CAPTURED_LOG), "2026-09-21T16:00:00+00:00")
    assert windows == [
        (parse_timestamp("2026-09-21T16:05:00.000Z"), parse_timestamp("2026-09-21T16:09:00.000Z"))
    ]
    assert orchestrator_wrote_since(env, Path(CAPTURED_LOG), "2026-09-21T16:06:00+00:00") == []
    assert orchestrator_wrote_since(env, Path("/tmp/other.log"), "2026-01-01T00:00:00+00:00") == []
    gone = _question_env(tmp_path, "gone")
    assert orchestrator_wrote_since(gone, Path(CAPTURED_LOG), "2026-01-01T00:00:00+00:00") is None


def test_a_relative_dot_directory_log_is_matched(tmp_path: Path) -> None:
    """gh#606: `lstrip("./")` stripped the leading dot of `.fr-deliver`, so a
    suite logged to `.fr-deliver/tests.log` was never recognised as written."""
    from fr.run.telemetry import orchestrator_wrote_since, parse_timestamp

    env = _bash_env(tmp_path, log=".fr-deliver/tests.log", until="2026-09-21T16:09:00.000Z")
    windows = orchestrator_wrote_since(
        env, Path("/repo/.fr-deliver/tests.log"), "2026-09-21T16:00:00+00:00"
    )
    assert windows == [
        (parse_timestamp("2026-09-21T16:05:00.000Z"), parse_timestamp("2026-09-21T16:09:00.000Z"))
    ]


@pytest.mark.parametrize(
    ("target", "log", "expected"),
    [
        (".fr-deliver/tests.log", "/repo/.fr-deliver/tests.log", True),
        ("./.fr-deliver/tests.log", "/repo/.fr-deliver/tests.log", True),
        ("tests.log", "/repo/.fr-deliver/tests.log", True),
        ("x.log", "/repo/x.log", True),
        ("./x.log", "/repo/x.log", True),
        ("../x.log", "/repo/x.log", True),
        ("fr-deliver/tests.log", "/repo/.fr-deliver/tests.log", False),
        ("foo/tests.log", "/repo/xfoo/tests.log", False),
        ("a/../b.log", "/repo/b.log", False),
        ("..", "/repo/x.log", False),
    ],
)
def test_writes_matches_relative_targets_segment_wise(
    target: str, log: str, expected: bool
) -> None:
    """Spec §2 (gh#606), pinned on `_writes` itself for both write forms."""
    from fr.run.telemetry import _writes

    assert _writes(f"pytest > {target}", Path(log)) is expected
    assert _writes(f"pytest 2>&1 | tee -a {target}", Path(log)) is expected


def test_a_command_that_only_reads_the_log_does_not_count(tmp_path: Path) -> None:
    """Review r1-1: before, any command MENTIONING the log's name passed —
    `cat c1.log`, `ls c1.log`. Only a write names the log as its output."""
    import json

    from fr.run.telemetry import orchestrator_wrote_since

    env = _bash_env(tmp_path)
    session = next((tmp_path / "projects").glob("*/s-b.jsonl"))
    rows = [json.loads(line) for line in session.read_text().splitlines()]
    rows[-2]["message"]["content"][0]["input"]["command"] = "cat /tmp/scratchpad/c1.log"
    session.write_text("".join(json.dumps(r) + "\n" for r in rows))
    since = "2026-09-21T16:00:00+00:00"
    assert orchestrator_wrote_since(env, Path("/tmp/scratchpad/c1.log"), since) == []


def test_a_writing_command_that_errored_does_not_count(tmp_path: Path) -> None:
    import json

    from fr.run.telemetry import orchestrator_wrote_since

    from tests.unit.transcript_sessions import CAPTURED_LOG

    env = _bash_env(tmp_path)
    session = next((tmp_path / "projects").glob("*/s-b.jsonl"))
    rows = [json.loads(line) for line in session.read_text().splitlines()]
    rows[-1]["message"]["content"][0]["is_error"] = True
    session.write_text("".join(json.dumps(r) + "\n" for r in rows))
    since = "2026-09-21T16:00:00+00:00"
    assert orchestrator_wrote_since(env, Path(CAPTURED_LOG), since) == []


def test_a_malformed_tool_input_never_raises(tmp_path: Path) -> None:
    """Review r1-9: the module's contract is "never raises"."""
    import json

    from fr.run.telemetry import orchestrator_wrote_since

    from tests.unit.transcript_sessions import CAPTURED_LOG

    env = _bash_env(tmp_path)
    session = next((tmp_path / "projects").glob("*/s-b.jsonl"))
    rows = [json.loads(line) for line in session.read_text().splitlines()]
    rows[-2]["message"]["content"][0]["input"] = "not a mapping"
    rows[-2]["message"]["content"].append("not a block either")
    session.write_text("".join(json.dumps(r) + "\n" for r in rows))
    since = "2026-09-21T16:00:00+00:00"
    assert orchestrator_wrote_since(env, Path(CAPTURED_LOG), since) == []


# --- `<synthetic>` is not a model (review r1-2) ----------------------------


def _synthetic(row: dict) -> dict:
    """A harness-written filler record: Claude Code emits main-thread assistant
    records with `"model": "<synthetic>"` and all-zero usage (observed twice in
    this operator's own transcripts). Derived from a captured record."""
    row = copy_of(row)
    row["message"]["model"] = "<synthetic>"
    row["message"]["usage"] = {
        k: 0
        for k in (
            "input_tokens",
            "output_tokens",
            "cache_creation_input_tokens",
            "cache_read_input_tokens",
        )
    }
    return row


def test_a_synthetic_record_is_never_the_orchestrators_model(tmp_path: Path) -> None:
    from fr.run.telemetry import orchestrator_model

    root = tmp_path / "projects"
    rows = records(ORCHESTRATOR)
    last = next(r for r in reversed(rows) if r.get("type") == "assistant")
    write_session(root, session_id="s-syn", rows=[*rows, _synthetic(last)])
    assert orchestrator_model(_question_env(root, "s-syn")) == "claude-opus-5"


def test_a_synthetic_record_never_joins_the_served_models(tmp_path: Path) -> None:
    rows = records(SUBAGENT)
    first = next(r for r in rows if r.get("type") == "assistant")
    path = tmp_path / "agent.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in [*rows, _synthetic(first)]))
    totals = read_claude_code(path)
    assert totals is not None
    assert totals.served_models == ("claude-sonnet-5",)
