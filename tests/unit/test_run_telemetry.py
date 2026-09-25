"""`fr.run.telemetry` — reading a Claude Code transcript (spec §5.C). Per-attempt
token measurement was removed after run v7 (p2-r27); these tests keep the
reading and attribution primitives the usage readers and transcript gates use.

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
    attribute_dispatches,
    claude_code_session,
)

from tests.unit.transcript_sessions import (
    AGENT_ID,
    ORCHESTRATOR,
    TOOL_USE_ID,
    copy_of,
    records,
    write_agent,
    write_session,
)


def _session(tmp_path: Path, session_id: str = "sess-1") -> Path:
    return write_session(tmp_path / "projects", session_id=session_id)


# --- (b) attribution: file-to-file, keyed on toolUseId --------------------


def test_the_module_never_reads_sessionid_or_cwd() -> None:
    """Attribution keys on `toolUseId` alone; this is the tripwire that makes a
    shortcut through `sessionId` or `cwd` fail HERE, at the line someone would
    add it."""
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


# --- harness scoping and session location --------------------------------


def test_a_dispatch_is_attributed_by_tool_use_id(tmp_path: Path) -> None:
    session = _session(tmp_path)
    write_agent(session, AGENT_ID, tool_use_id=TOOL_USE_ID)

    dispatches = attribute_dispatches(session)

    assert [d.tool_use_id for d in dispatches] == [TOOL_USE_ID]
    assert dispatches[0].agent_id == AGENT_ID
    assert dispatches[0].agent_type == "super-fr:fr-phase-executor"
    assert dispatches[0].model == "sonnet"


def test_a_subagent_file_the_orchestrator_never_dispatched_is_not_attributed(
    tmp_path: Path,
) -> None:
    """The check that a glob over `subagents/*.jsonl` cannot pass: a file whose
    `toolUseId` matches no `Agent` tool_use in THIS orchestrator stream belongs
    to some other dispatch and is not attributed."""
    session = _session(tmp_path)
    write_agent(session, "stranger", tool_use_id="toolu_not_in_this_stream")

    assert attribute_dispatches(session) == []


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
        "from fr.run.telemetry import _read_records\n"
        f"t = _read_records(Path({str(transcript)!r}))\n"
        "print(json.dumps(None if t is None else len(t)))\n"
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
    assert json.loads(done.stdout.strip()) == 1, (
        "a non-ASCII transcript must still be readable under a non-UTF-8 "
        f"locale; got {done.stdout!r}"
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


def test_an_unknown_session_id_locates_nothing(tmp_path: Path) -> None:
    _session(tmp_path, session_id="abc-123")
    env = {
        "CLAUDECODE": "1",
        "CLAUDE_CODE_SESSION_ID": "other",
        "FR_TRANSCRIPT_ROOT": str(tmp_path / "projects"),
    }

    assert claude_code_session(env) is None
