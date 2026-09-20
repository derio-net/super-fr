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
    measure_dispatch,
    measure_unit,
    read_claude_code,
    reader_for,
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
    assert reader_for("opencode") is None, "OpenCode keeps V1 estimates until its reader lands"
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
    assert measure_unit(env, start=BEFORE, end=AFTER) is None


def test_measure_unit_ties_the_three_together(tmp_path: Path) -> None:
    session = _session(tmp_path, session_id="abc-123")
    write_agent(session, AGENT_ID, tool_use_id=TOOL_USE_ID)
    env = {
        "CLAUDECODE": "1",
        "CLAUDE_CODE_SESSION_ID": "abc-123",
        "FR_TRANSCRIPT_ROOT": str(tmp_path / "projects"),
    }

    measured = measure_unit(env, start=BEFORE, end=AFTER)

    assert measured is not None
    assert measured.harness == "claude-code"
    assert measured.totals == SUBAGENT_TOTALS


@pytest.mark.parametrize("env", [{}, {"OPENCODE_BIN": "x"}, {"HERMES_HOME": "/h"}])
def test_a_harness_with_no_reader_measures_nothing(env: dict[str, str]) -> None:
    assert measure_unit(env, start=BEFORE, end=AFTER) is None


def test_a_mistyped_fr_harness_degrades_instead_of_raising() -> None:
    """`detect_harness` refuses an `FR_HARNESS` outside the closed set — right
    there, wrong here: telemetry is observability and must never be able to
    fail the `fr run resolve` that asked for it."""
    from fr.harness.detect import detect_harness
    from fr.harness.model import HarnessError

    with pytest.raises(HarnessError):
        detect_harness({"FR_HARNESS": "claude-kode"})

    assert measure_unit({"FR_HARNESS": "claude-kode"}, start=BEFORE, end=AFTER) is None


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
